// Blinds controller with Matter over Thread: Apple Home (and Alexa) see the blinds as window coverings.
//
//   One covering for all blinds by default (they move together). Setting "hksep" = 1: one covering per blind.
//   Apple Home's slider: 100 % open = slats level, 0 % = closed in the "Close" direction (cfg.closeUp).
//   Matter counts the other way round ("percent closed", in hundredths): lift 0 = open, 10000 = closed.
//
// The moves, marks, stall rules and settings are the same code as the Wi-Fi firmware (config.h, store.h, power.h,
// motion.h), running on ardu.h instead of Arduino.
#include <esp_err.h>
#include <esp_log.h>
#include <esp_pm.h>
#include <nvs_flash.h>
#include <esp_matter.h>
#include <common_macros.h>
#include <app/server/Server.h>
#if CHIP_DEVICE_CONFIG_ENABLE_THREAD
#include <platform/ESP32/OpenthreadLauncher.h>
#include "ot_config.h"
#endif
#include <driver/usb_serial_jtag.h>
#include "ardu.h"
#include "web.h"
#include "ble.h"
#include "home_view.h"
#include <app/server/CommissioningWindowManager.h>

static const char *TAG = "blinds";
// 1 while this firmware is being developed over USB: never doze (the Mac suspends an idle USB port, the chip then
// thinks the cable is gone, dozes, and its USB port stays off). Set to 0 for battery use.
#define DEV_STAY_AWAKE 0
using namespace esp_matter;
using namespace esp_matter::attribute;
using namespace esp_matter::endpoint;
using namespace chip::app::Clusters;

// The shown positions are refreshed (wand turned by hand?) for a few seconds every minute.
bool uiActive() { return (lastWeb && millis() - lastWeb < 8000) || millis() % 60000 < 3500; }
int homesPaired() { return chip::Server::GetInstance().GetFabricTable().FabricCount(); }
void openHomeWindow()
{
    chip::DeviceLayer::PlatformMgr().ScheduleWork([](intptr_t) {
        auto &mgr = chip::Server::GetInstance().GetCommissioningWindowManager();
        if (!mgr.IsCommissioningWindowOpen()) mgr.OpenBasicCommissioningWindow(chip::System::Clock::Seconds16(600), chip::CommissioningWindowAdvertisement::kDnssdOnly);
    }, 0);
}

uint8_t hkSeparate = 0;
int nEp = 0;
uint16_t epId[PORTS];
int epPort[PORTS];                       // which blind an endpoint stands for; -1 = all of them
volatile int32_t pend[PORTS];            // a target that arrived from Matter, lift hundredths; -1 = none
int lastLift[PORTS], lastOp[PORTS];
bool selfUpd = false;
esp_pm_lock_handle_t awake;

float tiltOfLift(int lift) { return tiltOfHomeLift(lift, cfg.closeUp); }
float liveTilt(int p) { return (movingPort(p) && !isnan(mvs[p].live)) ? tiltOf(p, mvs[p].live) : bs[p].tilt; }

static esp_err_t attr_cb(attribute::callback_type_t type, uint16_t endpoint_id, uint32_t cluster_id, uint32_t attribute_id,
                         esp_matter_attr_val_t *val, void *priv_data)
{
    if (type != PRE_UPDATE || selfUpd || cluster_id != WindowCovering::Id) return ESP_OK;
    if (attribute_id != WindowCovering::Attributes::TargetPositionLiftPercent100ths::Id) return ESP_OK;
    if ((val->type == ESP_MATTER_VAL_TYPE_NULLABLE_UINT16 || val->type == ESP_MATTER_VAL_TYPE_UINT16) && homeLiftValid(val->val.u16))
        for (int e = 0; e < nEp; e++) if (epId[e] == endpoint_id) { pend[e] = val->val.u16; pokeBlinds(); }
    return ESP_OK;
}
static esp_err_t ident_cb(identification::callback_type_t, uint16_t, uint8_t, uint8_t, void *) { return ESP_OK; }
static void event_cb(const ChipDeviceEvent *ev, intptr_t)
{
    if (ev->Type == chip::DeviceLayer::DeviceEventType::kCommissioningComplete) ::event("added to a home");
    else if (ev->Type == chip::DeviceLayer::DeviceEventType::kFabricRemoved) ::event("removed from a home");
}

// Hand a value to Matter without waiting for it: the blinds task must never stall while a motor runs.
struct Upd { uint16_t ep; uint32_t attr; esp_matter_attr_val_t v; };
void setAttr(int e, uint32_t attr, esp_matter_attr_val_t v)
{
    Upd *u = new Upd{epId[e], attr, v};
    chip::DeviceLayer::PlatformMgr().ScheduleWork([](intptr_t a) {
        Upd *u = (Upd *)a;
        selfUpd = true;                          // our own report, not a command from a home
        attribute::update(u->ep, WindowCovering::Id, u->attr, &u->v);
        selfUpd = false;
        delete u;
    }, (intptr_t)u);
}
TaskHandle_t blindsTaskH = nullptr;
void pokeBlinds() { if (blindsTaskH) xTaskNotifyGive(blindsTaskH); }

// Tell Matter where the blinds are. Lift = how far closed, whichever way the slats are closed.
void reportBattery()                           // every few minutes
{
    static int lastPct = -1, lastLvl = -1;
    int pct = battPercent(vbatRest), lvl = homeChargeLevel(pct);
    if (pct == lastPct && lvl == lastLvl) return;
    lastPct = pct; lastLvl = lvl;
    for (int e = 0; e < nEp; e++) {
        Upd *a = new Upd{epId[e], PowerSource::Attributes::BatPercentRemaining::Id, esp_matter_nullable_uint8(nullable<uint8_t>(homeBatPercent(pct)))};
        Upd *b = new Upd{epId[e], PowerSource::Attributes::BatChargeLevel::Id, esp_matter_enum8((uint8_t)lvl)};
        for (Upd *u : {a, b})
            chip::DeviceLayer::PlatformMgr().ScheduleWork([](intptr_t x) { Upd *u = (Upd *)x; attribute::update(u->ep, PowerSource::Id, u->attr, &u->v); delete u; }, (intptr_t)u);
    }
}
void report(bool force)
{
    for (int e = 0; e < nEp; e++) {
        BlindNow b[PORTS];
        int n = 0;
        for (int p = 0; p < PORTS; p++)
            if ((epPort[e] < 0 || epPort[e] == p) && movable(p)) b[n++] = {liveTilt(p), movingPort(p) || bs[p].queued, bs[p].target};
        HomeView v = homeViewOf(b, n);
        HomeSend s = homeSendOf(v, force, lastLift[e], lastOp[e]);
        if (s.lift) {
            lastLift[e] = v.lift;
            setAttr(e, WindowCovering::Attributes::CurrentPositionLiftPercent100ths::Id, esp_matter_nullable_uint16(nullable<uint16_t>((uint16_t)v.lift)));
            if (s.target) setAttr(e, WindowCovering::Attributes::TargetPositionLiftPercent100ths::Id, esp_matter_nullable_uint16(nullable<uint16_t>((uint16_t)v.lift)));
        }
        if (s.op) {
            lastOp[e] = v.op;
            setAttr(e, WindowCovering::Attributes::OperationalStatus::Id, esp_matter_bitmap8(s.opBits));
        }
    }
}

void blindsTask(void *)
{
    uint32_t lastP = 0, lastR = 0;
    bool was = false, held = true;
    uint32_t lastW = 0;
    for (;;) {
        xSemaphoreTake(mx, portMAX_DELAY);
        uint32_t now = millis();
        if (now - lastP >= 200) { lastP = now; powerSample(); }
        if (now - lastW >= 1000) { lastW = now; webTick(); }
        static uint32_t lastB = 0;
        if (now - lastB >= 300000 || !lastB) { lastB = now ? now : 1; reportBattery(); }
        for (int e = 0; e < nEp; e++) {
            int32_t v = pend[e];
            if (v < 0) continue;
            pend[e] = -1;
            if (homeAskIsStop(moving(), v, lastLift[e])) { moveStop(); continue; }   // "stop" arrives as: go to where you are
            int started = moveBlinds(moveAsk(FROM_HOME, epPort[e], tiltOfLift(v))).started;   // (ends a gentle move too)
            ::event("Home: %d %% closed (%d blind%s)", (int)v / 100, started, started == 1 ? "" : "s");
        }
        if (!held) { esp_pm_lock_acquire(awake); held = true; }      // no dozing while a sensor or motor is on
        motionTick();
        bool busy = moving() || bs[0].queued || bs[1].queued || bs[2].queued;
        // Dozing switches the chip's USB port off (no logs, no flashing). So: stay awake for the first minute after
        // every start, and for as long as a computer is connected by USB.
        // On battery, with nothing to do, the chip dozes between Wi-Fi beacons (it still hears the router, so Home and the
        // web app still reach it). It stays fully awake: while moving, on input power, for a minute after a start, while
        // a computer is on its USB port, while someone uses the web app, or when asked to (/api/awake).
        bool stay = DEV_STAY_AWAKE || busy || powered || now < 60000 || usb_serial_jtag_is_connected() ||
                    (lastWeb && now - lastWeb < 15000) || (int32_t)(keepAwakeUntil - now) > 0;
        if (!stay && held) { esp_pm_lock_release(awake); held = false; }
        static uint32_t lastS = 0;
        if (now - lastS >= 10000) {   // a status line for whoever is watching the USB log
            lastS = now;
            ESP_LOGI(TAG, "battery %.2f V  rail %.2f V  input %.2f V | 1: %s %.0f mV %.1f deg tilt %.0f | 2: %s %.0f mV | 3: %s %.0f mV", vbatRest, vdd, vin,
                     bs[0].present ? "plugged" : "empty", bs[0].mv, bs[0].ang, bs[0].tilt, bs[1].present ? "plugged" : "empty", bs[1].mv, bs[2].present ? "plugged" : "empty", bs[2].mv);
        }
        if (busy != was || now - lastR >= (busy ? 1000u : 5000u)) { lastR = now; report(busy != was); was = busy; }
        xSemaphoreGive(mx);
        ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(busy ? 2 : stay ? 20 : 500));   // a command or a web request wakes it at once
    }
}

extern "C" void app_main()
{
    nvs_flash_init();
#if CONFIG_PM_ENABLE
    esp_pm_config_t pm = {.max_freq_mhz = CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ, .min_freq_mhz = CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ, .light_sleep_enable = true};
    esp_pm_configure(&pm);
#endif
    esp_pm_lock_create(ESP_PM_NO_LIGHT_SLEEP, 0, "blinds", &awake);
    esp_pm_lock_acquire(awake);                  // released by blindsTask (see there)

    adcBegin();
    analogSetPinAttenuation(PIN_VBAT, ADC_11db);
    analogSetPinAttenuation(PIN_VIN, ADC_11db);
    motionBegin();
    nvs.begin("blinds", false);
    storeBegin();
    hkSeparate = nvs.getUChar("hksep", 0);
    pwmSaved = nvs.getUChar("pwm", 0);
    setenv("TZ", cfg.tz, 1);
    tzset();
    powerSample(true);
    stats.boots++;
    esp_reset_reason_t rr = esp_reset_reason();
    if (rr == ESP_RST_BROWNOUT) stats.brownouts++;
    else if (rr == ESP_RST_PANIC) stats.crashes++;
    else if (rr == ESP_RST_INT_WDT || rr == ESP_RST_TASK_WDT || rr == ESP_RST_WDT) stats.wdt++;
    statsSave();
    mx = xSemaphoreCreateMutex();

    node::config_t node_config;
    node_t *node = node::create(&node_config, attr_cb, ident_cb);
    ABORT_APP_ON_FAILURE(node != nullptr, ESP_LOGE(TAG, "no node"));
    for (int i = 0; i < PORTS; i++) {
        pend[i] = -1; lastLift[i] = -1; lastOp[i] = -1;
        if (hkSeparate ? cfg.b[i].hidden : i > 0) continue;       // one covering for all, or one per blind that is shown
        window_covering::config_t wc((uint8_t)WindowCovering::EndProductType::kInteriorBlind);
        wc.window_covering.type = (uint8_t)WindowCovering::Type::kTiltBlindLiftAndTilt;
        wc.window_covering.feature_flags = cluster::window_covering::feature::lift::get_id() |
                                           cluster::window_covering::feature::position_aware_lift::get_id();
        wc.window_covering.features.position_aware_lift.current_position_lift_percent_100ths = (uint16_t)0;
        wc.window_covering.features.position_aware_lift.target_position_lift_percent_100ths = (uint16_t)0;
        endpoint_t *ep = window_covering::create(node, &wc, ENDPOINT_FLAG_NONE, NULL);
        ABORT_APP_ON_FAILURE(ep != nullptr, ESP_LOGE(TAG, "no endpoint"));
        // Battery, so Apple Home can show its level and warn when it is low.
        endpoint::power_source::config_t ps;
        ps.power_source.status = 1;
        strlcpy(ps.power_source.description, "Battery", sizeof ps.power_source.description);
        ps.power_source.feature_flags = cluster::power_source::feature::battery::get_id();
        if (endpoint::power_source::add(ep, &ps) == ESP_OK) {
            cluster_t *pc = cluster::get(ep, PowerSource::Id);
            if (pc) cluster::power_source::attribute::create_bat_percent_remaining(pc, nullable<uint8_t>(homeBatPercent(battPercent(vbatRest))), nullable<uint8_t>((uint8_t)0), nullable<uint8_t>((uint8_t)200));
        }
        epId[nEp] = endpoint::get_id(ep);
        epPort[nEp] = hkSeparate ? i : -1;
        nEp++;
    }

#if CHIP_DEVICE_CONFIG_ENABLE_THREAD
    esp_openthread_platform_config_t config = {
        .radio_config = ESP_OPENTHREAD_DEFAULT_RADIO_CONFIG(),
        .host_config = ESP_OPENTHREAD_DEFAULT_HOST_CONFIG(),
        .port_config = ESP_OPENTHREAD_DEFAULT_PORT_CONFIG(),
    };
    set_openthread_platform_config(&config);
#endif
    bleSetupBegin();
    esp_err_t err = esp_matter::start(event_cb);
    ABORT_APP_ON_FAILURE(err == ESP_OK, ESP_LOGE(TAG, "Matter did not start: %d", err));

    // Wi-Fi: Matter owns the radio. The first time, give it the home network from secrets.h and restart, so the web app
    // is reachable before (and without) pairing with a home.
    wifi_config_t wcfg = {};
    // (Only the development controller gets the built-in network. Any other board starts with none and is set up from
    // the app over Bluetooth.)
    if (WIFI_SSID[0] && ctrlId() == "9888e0710610" && esp_wifi_get_config(WIFI_IF_STA, &wcfg) == ESP_OK && !wcfg.sta.ssid[0]) {
        strlcpy((char *)wcfg.sta.ssid, WIFI_SSID, sizeof wcfg.sta.ssid);
        strlcpy((char *)wcfg.sta.password, WIFI_PASSWORD, sizeof wcfg.sta.password);
        esp_wifi_set_storage(WIFI_STORAGE_FLASH);
        esp_wifi_set_config(WIFI_IF_STA, &wcfg);
        ESP_LOGI(TAG, "Wi-Fi network saved, restarting once");
        vTaskDelay(pdMS_TO_TICKS(500));
        esp_restart();
    }
    esp_sntp_config_t sntp = ESP_NETIF_SNTP_DEFAULT_CONFIG("pool.ntp.org");
    esp_netif_sntp_init(&sntp);
    webBegin();
    ::event("start %s (%s), battery %.2f V, input %.2f V, %d covering%s for Home", FW_VERSION, resetReason(), vbatRest, vin, nEp, nEp == 1 ? "" : "s");
    xTaskCreate(blindsTask, "blinds", 6144, NULL, 5, &blindsTaskH);
}
