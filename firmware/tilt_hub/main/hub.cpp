// Tilt Hub. Always on, on a USB wall plug. It lets the controllers sleep:
//
//   Apple Home -- Matter over Wi-Fi --> hub: one Window covering tile per blind (a Matter bridge). The hub answers
//                                       Home from what the controllers last told it, and passes moves on.
//   Tilt app   -- HTTP over Wi-Fi ----> hub: /c/<controller id>/x...  The app's sealed commands are passed on as they
//                                       are (the hub cannot read them). The hub announces each controller as
//                                       _tilt._tcp with ip "<hub address>/c/<id>", so the app finds it as before.
//   controllers -- UDP over Thread ---> hub: the hub's own Thread network; the hub leads it, the controllers are its
//                                       sleepy children. Protocol: blinds_matter/main/hub_link.h.
//
// The hub moves blinds with its own key, like a phone: it asks to join each controller ("Tilt Hub"), and the owner
// The owner's Tilt app lets it in by itself (as a guest) and tells the controller which key is the hub's.
#include <string>
#include <vector>
#include <esp_err.h>
#include <esp_log.h>
#include <esp_random.h>
#include <esp_app_desc.h>
#include <esp_wifi.h>
#include <esp_netif.h>
#include <esp_netif_sntp.h>
#include <nvs_flash.h>
#include <nvs.h>
#include <esp_http_server.h>
#include <mdns.h>
#include <cJSON.h>
#include <lwip/sockets.h>
#include <mbedtls/ecdh.h>
#include <mbedtls/ecp.h>
#include <mbedtls/gcm.h>
#include <mbedtls/hkdf.h>
#include <mbedtls/md.h>
#include <mbedtls/base64.h>
#include <esp_mac.h>
#include <esp_coexist.h>
#include <esp_partition.h>
#include <esp_ota_ops.h>
#include <esp_heap_caps.h>
#include <driver/gpio.h>
#include "lights.h"
#include <host/ble_hs.h>
#include <host/ble_gap.h>
#include <esp_openthread.h>
#include <esp_openthread_lock.h>
#include <esp_openthread_types.h>
#include <esp_openthread_netif_glue.h>
#include <openthread/dataset.h>
#include <openthread/dataset_ftd.h>
#include <openthread/thread.h>
#include <openthread/thread_ftd.h>
#include <openthread/ip6.h>
#include <openthread/link.h>
#include <esp_matter.h>
#include <esp_matter_providers.h>
#include <bootloader_random.h>
#include <platform/CommissionableDataProvider.h>
#include <platform/ESP32/ConfigurationManagerImpl.h>
#include <platform/internal/GenericDeviceInstanceInfoProvider.h>
#include <crypto/CHIPCryptoPAL.h>
#include <setup_payload/SetupPayload.h>
#include <setup_payload/ManualSetupPayloadGenerator.h>
#include <setup_payload/QRCodeSetupPayloadGenerator.h>
#include <app/server/Server.h>
#include <app/server/CommissioningWindowManager.h>
#include <platform/ESP32/OpenthreadLauncher.h>
#include "logic.h"                               // battLevel (the controller's own rules)
#include "home_view.h"                          // what Home sees, the same rules as a controller on Wi-Fi
#include "tilt_crypto.h"                         // hexOf, unhex, hmac256, gcm: the same as the controller's
#include "tilt_link.h"                           // the link to the controllers: proofs, pushes, datagrams, sealed frames
#include "tilt_pair.h"                           // the key exchange in Pairing: the same as the controller's
#include "ctrl_link.h"                           // CtrlLink: one controller's boot id and counter, behind one lock
#if defined(TILT_RELEASE)                         // an update file carries no Wi-Fi of anyone's
#define WIFI_SSID ""
#define WIFI_PASSWORD ""
#else
#include "secrets.h"                             // WIFI_SSID, WIFI_PASSWORD (bench: until Apple Home gives the network)
#endif
// HUB_SETUP_PIN: on the hub's label; made by build.sh, never in the repo. It is copied to flash at the first start, so
// update files (built with TILT_RELEASE) carry no code at all.
#if __has_include("setup_pin.h") && !defined(TILT_RELEASE)
#include "setup_pin.h"
#else
#define HUB_SETUP_PIN ""
#endif
#include "fwkey.h"                               // FW_SIGN_PUB: the key Tilt firmware is signed with (blinds_matter/main)
#include "hub_file.h"                            // the update-file checks (tested on the Mac)
#include "hub_people.h"                          // the hub's people and who may do what (tested on the Mac)

static const char *TAG = "hub";
using namespace esp_matter;
using namespace esp_matter::attribute;
using namespace chip::app::Clusters;

const uint16_t HUB_PORT = 49100;
const int MAX_CTRL = 4;                          // PORTS: logic.h

// The parts, in order: each one uses what the ones before it hold (firmware/tilt_hub/README.md, "Code").
#include "wire.h"                                // keptName, jq: names as the controller keeps them
#include "hub_store.h"                           // what it keeps about each controller
#include "hub_matter.h"                          // Apple Home (Matter)
#include "hub_ctrl.h"                            // the link to the controllers
#include "hub_alerts.h"                          // push alerts to the owners
#include "hub_care.h"                            // backups, the care task, new controllers
#include "hub_update.h"                          // firmware updates
#include "hub_pair.h"                            // the hub's people
#include "hub_api.h"                             // what the app asks the hub

// ---- Thread: the hub's own network, made once and kept
static void threadBegin() {
  esp_openthread_lock_acquire(portMAX_DELAY);
  otInstance *ot = esp_openthread_get_instance();
  otOperationalDatasetTlvs tlv;
  if (otDatasetGetActiveTlvs(ot, &tlv) != OT_ERROR_NONE) {
    otOperationalDataset ds;
    memset(&ds, 0, sizeof ds);
    otDatasetCreateNewNetwork(ot, &ds);
    strlcpy(ds.mNetworkName.m8, "TiltHub", sizeof ds.mNetworkName.m8);
    ds.mComponents.mIsNetworkNamePresent = true;
    otDatasetSetActive(ot, &ds);
    otDatasetGetActiveTlvs(ot, &tlv);
    ESP_LOGI(TAG, "new Thread network made");
  }
  otThreadSetRouterEligible(ot, true);
  if (!otIp6IsEnabled(ot)) otIp6SetEnabled(ot, true);
  otThreadSetEnabled(ot, true);
  esp_openthread_lock_release();
  // The network for the controllers (/api/hubjoin?ds=...). Printed on the USB log only: it is the network's key.
  printf("HUB DATASET %s\n", hexOf(tlv.mTlvs, tlv.mLength).c_str());
}

// ---- the status light (docs: firmware/tilt_hub/README.md, the app's hub page). Off when all is well; bright and
// plain when something needs a look. The most urgent one shows:
//   blinking white   factory reset (BOOT held)
//   blinking blue    being added to Apple Home or Alexa right now
//   flashing red     a problem: no Wi-Fi (once in a home: a new hub gets its Wi-Fi from Apple Home as it is added),
//                    no Thread network, Matter not running, or a controller set up with the hub silent for 30 min
//                    (not in the first 90 s after a start, while all that comes up)
//   blinking purple  installing an update (the hub's own, or one it sends to a controller)
//   solid blue       ready to be added to Apple Home or Alexa
//   solid green      a new controller nearby, waiting for setup in the app
//   slow yellow      a controller's battery is too low to move its blinds (its `low` flag)
static volatile int resetHeld = 0;               // resetTask: tenths of a second BOOT has been held (1000: resetting)
static volatile bool pairOpen = false, pairing = false;   // Matter, read on its own thread (statusTask asks)
static void statusTask(void *) {
  // The board's one-color LED (GPIO15) lights when its pin is high: kept dark, the color light (GPIO8) says it all.
  gpio_reset_pin(GPIO_NUM_15);
  gpio_set_direction(GPIO_NUM_15, GPIO_MODE_OUTPUT);
  gpio_set_level(GPIO_NUM_15, 0);
  uint32_t shown = 0xFFFFFFFF;                   // the color now on the light (0xRRGGBB), to send only changes
  int role = 0;
  bool wifi = false;
  for (int tick = 0;; tick++) {
    vTaskDelay(pdMS_TO_TICKS(100));
    if (lightTestUntil) {                        // the owner's light test (/api/light); 0: none (so no false "on" after 25 days)
      if ((int32_t)(lightTestUntil - ms()) > 0) { shown = 0xFFFFFFFF; continue; }
      lightTestUntil = 0;
    }
    if (tick % 10 == 0) {                        // once a second: Thread and Matter
      esp_openthread_lock_acquire(portMAX_DELAY);
      role = otThreadGetDeviceRole(esp_openthread_get_instance());
      esp_openthread_lock_release();
      wifi = hubIp() != "0.0.0.0";
      if (matterUp) chip::DeviceLayer::PlatformMgr().ScheduleWork([](intptr_t) {
        pairOpen = chip::Server::GetInstance().GetCommissioningWindowManager().IsCommissioningWindowOpen();
        pairing = chip::Server::GetInstance().GetFailSafeContext().IsFailSafeArmed();
      }, 0);
    }
    uint32_t now = ms();
    bool silent = false, low = false, fresh = false;
    for (int c = 0; c < MAX_CTRL; c++) {
      const Ctrl &k = ctrls[c];
      if (!k.used || k.s.keyState != KEY_IN) continue;   // not set up with the hub (new, or factory reset): not missed
      if (now > 1800000 && (!k.seen || now - k.seen > 1800000)) silent = true;
      if (k.low) low = true;
    }
    for (auto &n : newOnes) if (n.seen && now - n.seen < 300000) fresh = true;
    bool problem = now > 90000 && (!matterUp || (!wifi && inHome) || role < OT_DEVICE_ROLE_CHILD || silent);
    auto blink = [&](int onTicks, int offTicks) { return tick % (onTicks + offTicks) < onTicks; };
    uint32_t want = 0;
    if (resetHeld >= 1000) want = blink(1, 1) ? 0xFFFFFF : 0;
    else if (resetHeld >= 5) want = blink(3, 3) ? 0xFFFFFF : 0;
    else if (pairing) want = blink(2, 2) ? 0x0000FF : 0;
    else if (problem) want = blink(5, 5) ? 0xFF0000 : 0;
    else if (otaFor >= 0) want = blink(2, 2) ? 0xA000FF : 0;
    else if (pairOpen) want = 0x0000FF;
    else if (fresh) want = 0x00FF00;
    else if (low) want = blink(10, 20) ? 0xFFA000 : 0;
    if (want != shown) { rgbSet(want >> 16, (want >> 8) & 0xFF, want & 0xFF); shown = want; }
  }
}

// ---- factory reset: hold the BOOT button (GPIO9) for 10 seconds. Everything is forgotten (Apple Home, the Thread
// network, the controllers, the backups) except the hub's own setup code, as if it were printed on a label.
static void resetTask(void *) {
  gpio_config_t io = {};
  io.pin_bit_mask = 1ULL << 9;
  io.mode = GPIO_MODE_INPUT;
  io.pull_up_en = GPIO_PULLUP_ENABLE;
  gpio_config(&io);
  // The status light shows it (statusTask): white blinking while BOOT is held, fast as it resets.
  int held = 0;
  for (;;) {
    vTaskDelay(pdMS_TO_TICKS(100));
    held = gpio_get_level(GPIO_NUM_9) == 0 ? held + 1 : 0;
    resetHeld = held;
    if (held == 30) ESP_LOGW(TAG, "BOOT held: keep holding for a factory reset");
    if (held < 100) continue;
    resetHeld = 1000;                            // resetting: fast white
    vTaskDelay(pdMS_TO_TICKS(1200));
    ESP_LOGW(TAG, "factory reset");
    HomeCode keep = homeCode;
    nvs_close(nv);
    nvs_flash_deinit();
    nvs_flash_erase();
    nvs_flash_init();
    if (nvs_open("hub", NVS_READWRITE, &nv) == ESP_OK) { nvs_set_blob(nv, "homecode", &keep, sizeof keep); nvs_commit(nv); }
    vTaskDelay(pdMS_TO_TICKS(200));
    esp_restart();
  }
}

extern "C" void app_main() {
  esp_log_level_set(TAG, ESP_LOG_INFO);  // the rest of the firmware logs warnings and errors only (sdkconfig.defaults)
  nvs_flash_init();
  nvs_open("hub", NVS_READWRITE, &nv);
  ESP_LOGI(TAG, "hub id %s", hubId().c_str());
  stateMx = xSemaphoreCreateMutex();
  newMx = xSemaphoreCreateMutex();
  keysBegin();
  cloudBegin();
  otaAcks = xQueueCreate(16, sizeof(OtaAck));
  stage = esp_ota_get_next_update_partition(nullptr);
  {
    esp_ota_img_states_t st;
    hubTrial = esp_ota_get_state_partition(esp_ota_get_running_partition(), &st) == ESP_OK && st == ESP_OTA_IMG_PENDING_VERIFY;
    if (hubTrial) ESP_LOGW(TAG, "new hub firmware on trial: kept once Wi-Fi and Apple Home are up for a minute");
  }
  pendMx = xSemaphoreCreateMutex();
  for (auto &p : pend) p.sem = xSemaphoreCreateBinary();
  for (auto &k : ctrls) {
    k.mx = xSemaphoreCreateMutex(); k.pct = -1; k.chg = -1; k.src = -1; k.sep = -1; k.own = -1;
    for (auto &b : k.b) b.tilt = b.tgt = INT32_MIN;
    for (int t = 0; t < PORTS; t++) { k.tileLift[t] = k.tileOp[t] = -1; k.tileLabel[t][0] = 0; }
  }
  moves = xQueueCreate(8, sizeof(Move));
  loadCtrls();
  memosLoad();
  alertHubUpdate();

  node::config_t nc;
  strlcpy(nc.root_node.basic_information.node_label, "Tilt Hub", sizeof nc.root_node.basic_information.node_label);
  gNode = node::create(&nc, attr_cb, nullptr);
  endpoint::aggregator::config_t ac;
  aggregator = endpoint::aggregator::create(gNode, &ac, ENDPOINT_FLAG_NONE, nullptr);

  esp_openthread_platform_config_t ot = {
      .radio_config = {.radio_mode = RADIO_MODE_NATIVE},
      .host_config = {.host_connection_mode = HOST_CONNECTION_MODE_NONE},
      .port_config = {.storage_partition_name = "nvs", .netif_queue_size = 10, .task_queue_size = 10},
  };
  set_openthread_platform_config(&ot);
  homeCodeBegin();
  esp_err_t err = esp_matter::start(event_cb);
  if (err != ESP_OK) ESP_LOGE(TAG, "Matter did not start: %d", err);
  matterUp = err == ESP_OK;
  // Wi-Fi and Thread share the one radio: let them take turns from the start, before Wi-Fi has found the router
  // (with Thread listening all the time and no sharing, Wi-Fi saw no network at all).
  esp_err_t cx = esp_coex_wifi_i154_enable();
  ESP_LOGI(TAG, "radio sharing on: %s", esp_err_to_name(cx));
  // The tiles Home already knows, at the same endpoints as before (only possible once Matter has started: it reads
  // which endpoint numbers are taken).
  chip::DeviceLayer::PlatformMgr().ScheduleWork([](intptr_t) {
    inHome = chip::Server::GetInstance().GetFabricTable().FabricCount() > 0;
    xSemaphoreTake(stateMx, portMAX_DELAY);
    for (int c = 0; c < MAX_CTRL; c++)
      for (int p = 0; p < PORTS; p++) {
        if (!ctrls[c].used || !ctrls[c].s.ep[p]) continue;
        endpoint_t *e = makeTile(c, p, ctrls[c].s.ep[p], nullptr);
        if (e) endpoint::enable(e); else { ESP_LOGW(TAG, "%s: tile %d could not come back", ctrls[c].s.id, ctrls[c].s.ep[p]); ctrls[c].s.ep[p] = 0; }
      }
    xSemaphoreGive(stateMx);
  }, 0);

  // Bench: the home Wi-Fi from secrets.h the first time (Apple Home replaces it when it adds the hub).
  wifi_config_t w = {};
  esp_wifi_get_config(WIFI_IF_STA, &w);
  ESP_LOGI(TAG, "Wi-Fi network: '%s' (channel %d)", (const char *)w.sta.ssid, w.sta.channel);
  if (w.sta.ssid[0] && (w.sta.channel || w.sta.scan_method != WIFI_ALL_CHANNEL_SCAN)) {
    // Never stick to the channel of the last connection: the router may move to another one (it did, and the hub
    // could not find it again). Look on every channel and take the strongest.
    w.sta.channel = 0;
    w.sta.scan_method = WIFI_ALL_CHANNEL_SCAN;
    w.sta.sort_method = WIFI_CONNECT_AP_BY_SIGNAL;
    esp_wifi_set_storage(WIFI_STORAGE_FLASH);
    esp_wifi_set_config(WIFI_IF_STA, &w);
    esp_wifi_disconnect();
    esp_wifi_connect();
  }
  if (WIFI_SSID[0] && esp_wifi_get_config(WIFI_IF_STA, &w) == ESP_OK && !w.sta.ssid[0]) {
    strlcpy((char *)w.sta.ssid, WIFI_SSID, sizeof w.sta.ssid);
    strlcpy((char *)w.sta.password, WIFI_PASSWORD, sizeof w.sta.password);
    esp_wifi_set_storage(WIFI_STORAGE_FLASH);
    esp_wifi_set_config(WIFI_IF_STA, &w);
    ESP_LOGI(TAG, "Wi-Fi network saved, restarting once");
    vTaskDelay(pdMS_TO_TICKS(500));
    esp_restart();
  }
  esp_sntp_config_t sntp = ESP_NETIF_SNTP_DEFAULT_CONFIG("pool.ntp.org");
  esp_netif_sntp_init(&sntp);

  threadBegin();
  sock = socket(AF_INET6, SOCK_DGRAM, IPPROTO_UDP);
  sockaddr_in6 me = {};
  me.sin6_family = AF_INET6;
  me.sin6_port = htons(HUB_PORT);
  me.sin6_addr = in6addr_any;
  if (sock < 0 || bind(sock, (sockaddr *)&me, sizeof me) < 0) ESP_LOGE(TAG, "UDP did not start");
  // The controllers' port is on the Thread side only: nothing on the Wi-Fi can send to it (or get answers from it).
  ifreq ifr = {};
  if (esp_netif_get_netif_impl_name(esp_openthread_get_netif(), ifr.ifr_name) != ESP_OK ||
      setsockopt(sock, SOL_SOCKET, SO_BINDTODEVICE, &ifr, sizeof ifr) != 0) ESP_LOGE(TAG, "the controllers' port could not be kept to Thread (errno %d)", errno);
  else ESP_LOGI(TAG, "controllers' port: Thread only (%s)", ifr.ifr_name);
  xTaskCreate(udpTask, "udp", 5120, nullptr, 6, nullptr);
  xTaskCreate(moveTask, "moves", 6144, nullptr, 5, nullptr);
  xTaskCreate(careTask, "care", 6144, nullptr, 4, nullptr);
  httpBegin();
  rgbBegin();                                    // the color light's pulse channel, once, before anyone uses it
  xTaskCreate(resetTask, "reset", 3072, nullptr, 2, nullptr);
  xTaskCreate(statusTask, "status", 4096, nullptr, 2, nullptr);
  ESP_LOGI(TAG, "Tilt Hub %s started", esp_app_get_description()->version);
}
