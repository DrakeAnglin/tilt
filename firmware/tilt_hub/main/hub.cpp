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
#include "secrets.h"                             // WIFI_SSID, WIFI_PASSWORD (bench: until Apple Home gives the network)
// HUB_SETUP_PIN: on the hub's label; made by build.sh, never in the repo. It is copied to flash at the first start, so
// update files (built with TILT_RELEASE) carry no code at all.
#if __has_include("setup_pin.h") && !defined(TILT_RELEASE)
#include "setup_pin.h"
#else
#define HUB_SETUP_PIN ""
#endif
#include "fwkey.h"                               // FW_SIGN_PUB: the key Tilt firmware is signed with (blinds_matter/main)
#include <mbedtls/sha256.h>
#include <mbedtls/ecdsa.h>

static const char *TAG = "hub";
using namespace esp_matter;
using namespace esp_matter::attribute;
using namespace chip::app::Clusters;

const uint16_t HUB_PORT = 49100;
const int MAX_CTRL = 4;                          // PORTS: logic.h
static uint32_t ms() { return (uint32_t)(esp_timer_get_time() / 1000); }

// ---- what the hub knows about each controller (the part in flash: Saved)
struct Saved {
  char id[13];
  uint8_t keyState;                              // KeyState: the hub's own key on this controller
  uint8_t cid[8], key[32];
  uint16_t ep[PORTS];                            // Home tiles (Matter endpoints, 0 = none): ep[0] alone = all the blinds,
  uint8_t sep;                                   //   or with sep = 1 one tile per blind (the controller's "hksep")
};
enum KeyState : uint8_t { KEY_NONE = 0, KEY_ASKED = 1, KEY_IN = 2 };   // no key / asked to join, waiting / let in
enum OtaState { OTA_NONE = 0, OTA_SENDING = 1, OTA_CHECKING = 2, OTA_DONE = 3, OTA_FAILED = 4 };   // the app reads these numbers
struct SavedV1 { char id[13]; uint8_t keyState; uint8_t cid[8], key[32]; uint16_t ep[PORTS]; };
struct Ctrl {
  Saved s;
  bool used;
  char name[33];
  char fw[24];                                   // its firmware version (from its pushes)
  sockaddr_in6 addr;
  bool addrOk;
  uint32_t seen;                                 // ms of the last message from it
  uint8_t boot[4];
  bool bootOk;
  uint64_t ctr;
  int closeUp, pct, low;
  struct B { char name[33]; int hid, ok, tilt, tgt, mov; } b[PORTS];
  int sep;                                       // what the controller says now (-1 = not heard yet)
  int tileLift[PORTS], tileOp[PORTS];            // what each tile last showed Home (-1 = nothing yet)
  char tileLabel[PORTS][33];
  char pushBoot[9];                              // the controller's boot id from its last push
  std::string hello;                             // its last hello answer, given to the app straight from the hub
  char helloBoot[9];
  bool announced;
  uint32_t cv;                                   // checksum of its settings (from its pushes)
  int own;                                       // it has an owner (from its pushes; -1 not known yet)
  uint32_t firstSeen;                            // ms when the hub first heard from it since this start
  int otaSt;                                     // OtaState: firmware through the hub
  int otaPct;
  char otaErr[64];
  uint16_t rloc;                                 // its Thread short address, while known
  uint32_t pushN;                                // the count on its last proven push (this boot)
  SemaphoreHandle_t mx;                          // one request to this controller at a time
};
static Ctrl ctrls[MAX_CTRL];
// Per controller (flash "proof"): it has sent a proven push (from then on only proven ones count), and the boot count
// of the newest one (an older boot's push is never taken again).
struct Proof { uint8_t on; uint32_t bn; };
static Proof proofs[MAX_CTRL];
static void proofsSave();
static uint32_t constrain_u(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }
struct OtaAck { bool ok, num; uint32_t next; };   // a controller's answer to a firmware piece (num: it gave an offset)
static QueueHandle_t otaAcks;
static bool hubTrial = false;                    // the hub runs new firmware it has not kept yet
static volatile uint32_t homeWindowUntil = 0;    // the owner asked to add the hub to Apple Home: pairing open until then
static volatile int otaFor = -1;                 // the controller being updated (one at a time)
static std::string homeManual, homeQr;           // the code to type and the QR text (USB log, and to the controllers)
static std::string shareManual, shareQr;         // the one-time code for another home app (shareCodeJson)
static volatile uint32_t shareUntil = 0;          // that code's pairing window is open until then (0: none)
static volatile bool inHome = false;             // added to Apple Home (or another Matter home)
static std::string homesJson();                  // the homes it is in, read fresh (below)
static std::string shareCodeJson();              // a one-time code for another home app (below)
static SemaphoreHandle_t stateMx;              // ctrls[] (not the per-controller request lock)
static nvs_handle_t nv;
static void proofsSave() { nvs_set_blob(nv, "proof", proofs, sizeof proofs); nvs_commit(nv); }
static void saveCtrls() {
  Saved all[MAX_CTRL] = {};
  for (int i = 0; i < MAX_CTRL; i++) if (ctrls[i].used) all[i] = ctrls[i].s;
  nvs_set_blob(nv, "ctrls", all, sizeof all);
  nvs_commit(nv);
}
static void loadCtrls() {
  { size_t pn = sizeof proofs; if (nvs_get_blob(nv, "proof", proofs, &pn) != ESP_OK || pn != sizeof proofs) memset(proofs, 0, sizeof proofs); }
  Saved all[MAX_CTRL] = {};
  size_t n = sizeof all;
  if (nvs_get_blob(nv, "ctrls", all, &n) != ESP_OK || n != sizeof all) {   // the first layout (no sep): keep the keys
    SavedV1 v1[MAX_CTRL];
    n = sizeof v1;
    if (nvs_get_blob(nv, "ctrls", v1, &n) != ESP_OK || n != sizeof v1) return;
    for (int i = 0; i < MAX_CTRL; i++) { memcpy(&all[i], &v1[i], sizeof v1[i]); all[i].sep = 1; }
  }
  for (int i = 0; i < MAX_CTRL; i++) if (all[i].id[0]) { ctrls[i].used = true; ctrls[i].s = all[i]; strlcpy(ctrls[i].name, "Blinds", sizeof ctrls[i].name); }
}
static int findCtrl(const char *id) { for (int i = 0; i < MAX_CTRL; i++) if (ctrls[i].used && !strcmp(ctrls[i].s.id, id)) return i; return -1; }

// ---- UDP to the controllers: send one request, wait for its answer
static int sock = -1;
struct Pending { uint16_t seq; bool used, done; std::string ans; SemaphoreHandle_t sem; in6_addr to;   // to: only its answer counts
                 std::string part[16]; uint16_t have; uint8_t count; };                             // a long answer, in pieces
static Pending pend[8];
static SemaphoreHandle_t pendMx;
static uint16_t nextSeq = 1;
// Returns the 3-digit status (0 = no answer) and the answer.
static int ask(int c, char type, const std::string &payload, std::string &ans, uint32_t waitMs = 2500) {
  Ctrl &k = ctrls[c];
  if (!k.addrOk) return 0;
  xSemaphoreTake(k.mx, portMAX_DELAY);
  int st = 0;
  for (int attempt = 0; attempt < 2 && !st; attempt++) {
    xSemaphoreTake(pendMx, portMAX_DELAY);
    int slot = -1;
    for (int i = 0; i < 8; i++) if (!pend[i].used) { slot = i; break; }
    uint16_t seq = nextSeq++;
    if (!nextSeq) nextSeq = 1;
    if (slot >= 0) {
      Pending &p = pend[slot];
      p.used = true; p.done = false; p.seq = seq; p.ans.clear(); p.to = k.addr.sin6_addr; p.have = 0; p.count = 0;
      for (auto &s : p.part) s.clear();
      xSemaphoreTake(p.sem, 0);
    }
    xSemaphoreGive(pendMx);
    if (slot < 0) break;
    std::string m(1, type);
    m += (char)(seq >> 8); m += (char)(seq & 0xFF);
    m += payload;
    sendto(sock, m.data(), m.size(), 0, (sockaddr *)&k.addr, sizeof k.addr);
    if (xSemaphoreTake(pend[slot].sem, pdMS_TO_TICKS(waitMs)) == pdTRUE && pend[slot].ans.size() >= 3) {
      st = atoi(pend[slot].ans.substr(0, 3).c_str());
      ans = pend[slot].ans.substr(3);
    }
    xSemaphoreTake(pendMx, portMAX_DELAY);
    pend[slot].used = false;
    xSemaphoreGive(pendMx);
  }
  xSemaphoreGive(k.mx);
  return st;
}

// ---- the hub's own key for each controller (it moves blinds like a phone would)
static int rng(void *, unsigned char *b, size_t n) { esp_fill_random(b, n); return 0; }
#include "cloud.h"                               // alertRaise: push alerts through iCloud
// The proof on messages between the hub and a controller that has let the hub in (and been told which key is the
// hub's): the first 16 bytes of HMAC-SHA256 with the link key, in hex. Protocol: blinds_matter/main/hub_link.h.
static std::string macOf(int c, const std::string &what) {
  if (ctrls[c].s.keyState != KEY_IN) return "";
  uint8_t link[32], m[32];
  const mbedtls_md_info_t *md = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  mbedtls_md_hmac(md, ctrls[c].s.key, 32, (const uint8_t *)"tilt-hub-link", 13, link);
  mbedtls_md_hmac(md, link, 32, (const uint8_t *)what.data(), what.size(), m);
  return hexOf(m, 16);
}
static bool macOk(int c, const std::string &what, const std::string &mac) {
  std::string want = macOf(c, what);
  if (want.empty() || mac.size() != want.size()) return false;
  uint8_t d = 0;
  for (size_t i = 0; i < want.size(); i++) d |= want[i] ^ mac[i];
  return d == 0;
}
static void cleanName(char *out, size_t n, const std::string &in);
// Ask to join, as "Tilt Hub" (the controller's /x/ask). The owner lets it in from the app.
static void askToJoin(int c) {
  mbedtls_ecp_group grp; mbedtls_mpi d, z; mbedtls_ecp_point Q, Qp;
  mbedtls_ecp_group_init(&grp); mbedtls_mpi_init(&d); mbedtls_mpi_init(&z); mbedtls_ecp_point_init(&Q); mbedtls_ecp_point_init(&Qp);
  uint8_t cpub[65], dpub[65], shared[32], okm[32], info[9 + 130];
  size_t cn = 0, n = 0;
  bool ok = mbedtls_ecp_group_load(&grp, MBEDTLS_ECP_DP_SECP256R1) == 0 && mbedtls_ecdh_gen_public(&grp, &d, &Q, rng, nullptr) == 0 &&
            mbedtls_ecp_point_write_binary(&grp, &Q, MBEDTLS_ECP_PF_UNCOMPRESSED, &cn, cpub, sizeof cpub) == 0 && cn == 65;
  std::string ans;
  if (ok) {
    uint8_t b64[100];
    size_t bn = 0;
    mbedtls_base64_encode(b64, sizeof b64, &bn, cpub, 65);
    std::string body = "{\"pub\":\"" + std::string((char *)b64, bn) + "\",\"name\":\"Tilt Hub\"}";
    int st = ask(c, 'A', body, ans, 4000);
    ok = st == 200;
    if (!ok) ESP_LOGW(TAG, "%s: ask to join refused (%d) %s", ctrls[c].s.id, st, ans.c_str());
  }
  cJSON *j = ok ? cJSON_Parse(ans.c_str()) : nullptr;
  const char *pub = j ? cJSON_GetStringValue(cJSON_GetObjectItem(j, "pub")) : nullptr, *cid = j ? cJSON_GetStringValue(cJSON_GetObjectItem(j, "cid")) : nullptr;
  ok = pub && cid && mbedtls_base64_decode(dpub, sizeof dpub, &n, (const uint8_t *)pub, strlen(pub)) == 0 && n == 65 &&
       mbedtls_ecp_point_read_binary(&grp, &Qp, dpub, 65) == 0 && mbedtls_ecdh_compute_shared(&grp, &z, &Qp, &d, rng, nullptr) == 0 &&
       mbedtls_mpi_write_binary(&z, shared, 32) == 0;
  if (ok) {
    memcpy(info, "blinds-v1", 9); memcpy(info + 9, cpub, 65); memcpy(info + 74, dpub, 65);
    ok = mbedtls_hkdf(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), nullptr, 0, shared, 32, info, sizeof info, okm, 32) == 0 && unhex(cid, ctrls[c].s.cid, 8);
  }
  if (ok) {
    xSemaphoreTake(stateMx, portMAX_DELAY);
    memcpy(ctrls[c].s.key, okm, 32);
    ctrls[c].s.keyState = KEY_ASKED;
    saveCtrls();
    xSemaphoreGive(stateMx);
    ESP_LOGI(TAG, "%s: asked to join as Tilt Hub (the owner's Tilt app lets it in by itself).", ctrls[c].s.id);
  }
  if (j) cJSON_Delete(j);
  mbedtls_ecp_group_free(&grp); mbedtls_mpi_free(&d); mbedtls_mpi_free(&z); mbedtls_ecp_point_free(&Q); mbedtls_ecp_point_free(&Qp);
}
// A command with the hub's key: "/api/home?b=0&lift=5000". Returns the controller's JSON answer, or "" on failure.
static std::string ctrlCommand(int c, const std::string &cmd) {
  Ctrl &k = ctrls[c];
  if (k.s.keyState == KEY_NONE) return "";
  for (int attempt = 0; attempt < 2; attempt++) {
    if (!k.bootOk) {
      std::string h;
      if (ask(c, 'H', "", h) != 200) return "";
      cJSON *j = cJSON_Parse(h.c_str());
      const char *b = j ? cJSON_GetStringValue(cJSON_GetObjectItem(j, "boot")) : nullptr;
      k.bootOk = b && unhex(b, k.boot, 4);
      if (j) cJSON_Delete(j);
      if (!k.bootOk) return "";
    }
    uint64_t now = (uint64_t)time(nullptr) * 1000ULL + ms() % 1000;
    k.ctr = now > k.ctr ? now : k.ctr + 1;
    std::string pkt(20 + cmd.size() + 16, 0);
    uint8_t *p = (uint8_t *)&pkt[0], aad[17];
    memcpy(p, k.s.cid, 8);
    memcpy(p + 8, k.boot, 4);
    for (int i = 0; i < 8; i++) p[12 + i] = (uint8_t)(k.ctr >> (56 - 8 * i));
    memcpy(aad, "blinds-v1", 9); memcpy(aad + 9, k.s.cid, 8);
    gcm(true, k.s.key, p + 8, aad, 17, (const uint8_t *)cmd.data(), cmd.size(), p + 20, p + 20 + cmd.size());
    std::string ans;
    int st = ask(c, 'X', pkt, ans);
    if (st == 409) { k.bootOk = false; continue; }  // the controller restarted (new boot id): once more
    if (st == 403 && ans.find("waiting") != std::string::npos) { ESP_LOGW(TAG, "%s: Tilt Hub is waiting to be let in (open the owner's Tilt app)", k.s.id); return ""; }
    if (st != 200 || ans.size() < 28) { ESP_LOGW(TAG, "%s: command %s failed (%d) %s", k.s.id, cmd.c_str(), st, st == 200 ? "" : ans.c_str()); if (st == 401) { k.s.keyState = KEY_NONE; proofs[c] = {}; saveCtrls(); proofsSave(); } return ""; }
    std::string out(ans.size() - 28, 0);
    uint8_t aad2[30];
    memcpy(aad2, "blinds-v1r", 10); memcpy(aad2 + 10, k.s.cid, 8); memcpy(aad2 + 18, p + 8, 12);
    const uint8_t *a = (const uint8_t *)ans.data();
    if (!gcm(false, k.s.key, a, aad2, 30, a + 12, out.size(), (uint8_t *)&out[0], (uint8_t *)(a + 12 + out.size()))) return "";
    if (k.s.keyState != KEY_IN) { k.s.keyState = KEY_IN; saveCtrls(); ESP_LOGI(TAG, "%s: Tilt Hub let in", k.s.id); }
    return out;
  }
  return "";
}

// ---- Alert rules: when the hub tells the owners (cloud.h sends it). Each alert is sent once:
//   stall       a blind stalled during an ordinary move (the controller's status counts them, b[].st)
//   silent      a controller set up with the hub has not been heard for 25 minutes (cleared when it is heard again)
//   batt-low / batt-crit / batt-dead   under 20 %, under 10 %, too low to move: each level once, all reset only
//               when the battery is back at 25 % or more (a little above the low line, so a reading near it can't flap)
//   update      a firmware update through the hub failed;  hub-update   the hub's own new firmware went back
struct Memo {                                    // per controller, by id (flash "amemo"): what was already told
  char id[13];
  char name[33];                                 // its room's name (kept: the hub may restart while it is silent)
  uint8_t topic[16];                             // its iCloud topic (its status, asked once with the hub's key)
  uint8_t silent, batt, stBase;                  // "not responding" sent; battery level told (0-3); stall counts known
  uint32_t bn;                                   // the controller start the stall counts belong to
  uint16_t st[PORTS];
};
static Memo memos[MAX_CTRL];
static const uint32_t SILENT_MS = 1500000;      // the app's HubInfo.Member.silentAfter (25 minutes)
static void memosSave() { nvs_set_blob(nv, "amemo", memos, sizeof memos); nvs_commit(nv); }
static void memosLoad() { size_t n = sizeof memos; if (nvs_get_blob(nv, "amemo", memos, &n) != ESP_OK || n != sizeof memos) memset(memos, 0, sizeof memos); }
static Memo &memoOf(int c) {
  const char *id = ctrls[c].s.id;
  for (auto &m : memos) if (!strcmp(m.id, id)) return m;
  int slot = -1;
  for (int i = 0; i < MAX_CTRL && slot < 0; i++) if (!memos[i].id[0] || findCtrl(memos[i].id) < 0) slot = i;
  if (slot < 0) slot = c;
  memos[slot] = Memo{};
  strlcpy(memos[slot].id, id, sizeof memos[slot].id);
  return memos[slot];
}
static bool topicKnown(const Memo &m) { for (auto b : m.topic) if (b) return true; return false; }
static int battLevelOf(int pct, int low) { return low == 1 ? 3 : pct < 0 ? -1 : pct < 10 ? 2 : pct < 20 ? 1 : 0; }
// A status push came in (under stateMx): battery levels, stalls, and it is no longer silent.
static void alertsFromPush(int c, cJSON *j) {
  Ctrl &k = ctrls[c];
  Memo &m = memoOf(c);
  bool save = false, told = topicKnown(m);
  if (strcmp(m.name, k.name)) { strlcpy(m.name, k.name, sizeof m.name); save = true; }
  if (m.silent) { m.silent = 0; save = true; ESP_LOGI(TAG, "%s heard again", k.s.id); }
  int lv = battLevelOf(k.pct, k.low);
  static const char *const battKinds[] = {"", "batt-low", "batt-crit", "batt-dead"};
  if (told && lv > m.batt) { alertRaise(m.topic, battKinds[lv], 9, k.name, std::to_string(k.pct).c_str()); m.batt = lv; save = true; }
  else if (lv == 0 && m.batt && k.pct >= 25) { m.batt = 0; save = true; }
  cJSON *bl = cJSON_GetObjectItem(j, "b"), *bnj = cJSON_GetObjectItem(j, "bn");
  if (cJSON_IsNumber(cJSON_GetObjectItem(cJSON_GetArrayItem(bl, 0), "st")) && cJSON_IsNumber(bnj)) {   // a controller that counts stalls
    uint32_t bn = (uint32_t)bnj->valuedouble;
    bool fresh = !m.stBase;                      // the first push: only learn the counts
    if (bn != m.bn) { if (!fresh) memset(m.st, 0, sizeof m.st); m.bn = bn; save = true; }   // it restarted: counts from 0 again
    for (int p = 0; p < PORTS; p++) {
      cJSON *sv = cJSON_GetObjectItem(cJSON_GetArrayItem(bl, p), "st");
      if (!cJSON_IsNumber(sv)) continue;
      uint16_t st = (uint16_t)sv->valueint;
      if (st == m.st[p]) continue;
      if (st > m.st[p] && !fresh && told) alertRaise(m.topic, "stall", p, k.name, k.b[p].name);
      m.st[p] = st; save = true;
    }
    if (fresh) { m.stBase = 1; save = true; }
  }
  if (save) memosSave();
}
// Every care round: silent controllers, and learning each controller's topic (once, with the hub's key).
static void alertsCare() {
  for (int c = 0; c < MAX_CTRL; c++) {
    if (!ctrls[c].used || ctrls[c].s.keyState != KEY_IN) continue;
    xSemaphoreTake(stateMx, portMAX_DELAY);
    Memo &m = memoOf(c);
    uint32_t quiet = ctrls[c].seen ? ms() - ctrls[c].seen : ms();
    if (!m.silent && quiet > SILENT_MS && topicKnown(m) && otaFor != c) {
      alertRaise(m.topic, "silent", 9, m.name[0] ? m.name : ctrls[c].name);
      m.silent = 1; memosSave();
    }
    bool ask = !topicKnown(m) && ctrls[c].seen && ms() - ctrls[c].seen < 60000;
    xSemaphoreGive(stateMx);
    static uint32_t askedAt[MAX_CTRL];
    if (!ask || (askedAt[c] && ms() - askedAt[c] < 600000)) continue;
    askedAt[c] = ms() | 1;
    std::string r = ctrlCommand(c, "/api/s");
    cJSON *j = cJSON_Parse(r.c_str());
    const char *t = j ? cJSON_GetStringValue(cJSON_GetObjectItem(j, "topic")) : nullptr;
    uint8_t tb[16];
    if (t && unhex(t, tb, 16)) {
      xSemaphoreTake(stateMx, portMAX_DELAY);
      memcpy(memoOf(c).topic, tb, 16); memosSave();
      xSemaphoreGive(stateMx);
      ESP_LOGI(TAG, "%s: alert topic known", ctrls[c].s.id);
    }
    if (j) cJSON_Delete(j);
  }
}
static void alertUpdateFailed(int c, const char *why) {
  Memo &m = memoOf(c);
  alertRaise(m.topic, "update", 9, ctrls[c].name, why);
}
// The hub's own new firmware went back to the old one (it did not work): tell its owners once per version.
static uint8_t htopic[16];
static void alertHubUpdate() {
  const esp_partition_t *bad = esp_ota_get_last_invalid_partition();
  esp_app_desc_t d;
  if (!bad || esp_ota_get_partition_description(bad, &d) != ESP_OK) return;
  char seen[32] = {0};
  size_t n = sizeof seen;
  bool first = nvs_get_str(nv, "badver", seen, &n) != ESP_OK;   // an old failure from before alerts existed: no alert
  if (!strcmp(seen, d.version)) return;
  nvs_set_str(nv, "badver", d.version); nvs_commit(nv);
  if (!first) alertRaise(htopic, "hub-update", 9, "Tilt Hub", d.version);
}

// ---- Matter: one bridged Window covering per blind
static node_t *gNode;
static endpoint_t *aggregator;
static bool matterUp = false;
static uint16_t epOf(int c, int p) { return ctrls[c].s.ep[p]; }
static bool epFind(uint16_t ep, int &c, int &p) {
  for (c = 0; c < MAX_CTRL; c++) if (ctrls[c].used) for (p = 0; p < PORTS; p++) if (ctrls[c].s.ep[p] == ep) return true;
  return false;
}
static endpoint_t *makeTile(int c, int p, uint16_t resumeId, const char *name) {
  endpoint::bridged_node::config_t bc;
  endpoint_t *ep = resumeId ? endpoint::bridged_node::resume(gNode, &bc, ENDPOINT_FLAG_DESTROYABLE | ENDPOINT_FLAG_BRIDGE, resumeId, nullptr)
                            : endpoint::bridged_node::create(gNode, &bc, ENDPOINT_FLAG_DESTROYABLE | ENDPOINT_FLAG_BRIDGE, nullptr);
  if (!ep) return nullptr;
  endpoint::window_covering::config_t wc((uint8_t)WindowCovering::EndProductType::kInteriorBlind);
  wc.window_covering.type = (uint8_t)WindowCovering::Type::kTiltBlindLiftAndTilt;
  wc.window_covering.feature_flags = cluster::window_covering::feature::lift::get_id() | cluster::window_covering::feature::position_aware_lift::get_id();
  wc.window_covering.features.position_aware_lift.current_position_lift_percent_100ths = (uint16_t)0;
  wc.window_covering.features.position_aware_lift.target_position_lift_percent_100ths = (uint16_t)0;
  endpoint::window_covering::add(ep, &wc);
  endpoint::power_source::config_t ps;
  ps.power_source.status = 1;
  strlcpy(ps.power_source.description, "Battery", sizeof ps.power_source.description);
  ps.power_source.feature_flags = cluster::power_source::feature::battery::get_id();
  if (endpoint::power_source::add(ep, &ps) == ESP_OK) {
    cluster_t *pc = cluster::get(ep, PowerSource::Id);
    if (pc) cluster::power_source::attribute::create_bat_percent_remaining(pc, nullable<uint8_t>(200), nullable<uint8_t>((uint8_t)0), nullable<uint8_t>((uint8_t)200));
  }
  cluster_t *bi = cluster::get(ep, BridgedDeviceBasicInformation::Id);
  if (bi) {
    char label[33];
    strlcpy(label, name && name[0] ? name : "Blinds", sizeof label);
    cluster::bridged_device_basic_information::attribute::create_node_label(bi, label, strlen(label));
    char vn[] = "Tilt";
    cluster::bridged_device_basic_information::attribute::create_vendor_name(bi, vn, strlen(vn));
    char pn[] = "Tilt blind";
    cluster::bridged_device_basic_information::attribute::create_product_name(bi, pn, strlen(pn));
    char uid[24];
    snprintf(uid, sizeof uid, "%s-%d", ctrls[c].s.id, ctrls[c].s.sep ? p + 1 : 0);
    cluster::bridged_device_basic_information::attribute::create_unique_id(bi, uid, strlen(uid));
  }
  endpoint::set_parent_endpoint(ep, aggregator);
  return ep;
}
// Called with the CHIP stack lock held (ScheduleWork).
static void setU16(uint16_t ep, uint32_t cl, uint32_t at, uint16_t v) { esp_matter_attr_val_t x = esp_matter_nullable_uint16(nullable<uint16_t>(v)); attribute::update(ep, cl, at, &x); }
static bool selfUpd = false;
static void dropTile(Ctrl &k, int p) {
  endpoint_t *e = endpoint::get(gNode, k.s.ep[p]);
  if (e) endpoint::destroy(gNode, e);
  ESP_LOGI(TAG, "%s: Home tile %d removed", k.s.id, k.s.ep[p]);
  k.s.ep[p] = 0;
  k.tileLift[p] = k.tileOp[p] = -1;
  k.tileLabel[p][0] = 0;
}
// The blinds tile t stands for: all the shown ones (one tile), or blind t (one tile per blind).
static int tileBlinds(const Ctrl &k, int t, BlindNow *out) {
  int n = 0;
  for (int p = 0; p < PORTS; p++) {
    const Ctrl::B &b = k.b[p];
    if (b.hid || !b.ok || (k.s.sep && p != t)) continue;
    out[n++] = {b.tilt == INT32_MIN ? NAN : (float)b.tilt, b.mov != 0, b.tgt == INT32_MIN ? NAN : (float)b.tgt};
  }
  return n;
}
static void applyStatus(intptr_t ci) {
  int c = (int)ci;
  xSemaphoreTake(stateMx, portMAX_DELAY);
  Ctrl &k = ctrls[c];
  bool saved = false;
  if (k.sep >= 0 && k.sep != k.s.sep) {          // the controller's tile setting changed: start the tiles again
    for (int p = 0; p < PORTS; p++) if (k.s.ep[p]) dropTile(k, p);
    k.s.sep = k.sep;
    saved = true;
  }
  for (int t = 0; t < PORTS; t++) {
    BlindNow bl[PORTS];
    int n = tileBlinds(k, t, bl);
    // A tile is made for a blind that is set up; it stays when the blind is unplugged or not set up for a while
    // (Home keeps its room and automations). It goes only when the blind is hidden, or the tile setting changes.
    bool anyShown = false;
    for (int p = 0; p < PORTS; p++) anyShown = anyShown || (!k.b[p].hid && (!k.s.sep || p == t));
    bool want = k.sep >= 0 && (k.s.sep || t == 0) && (k.s.ep[t] ? anyShown : n > 0);
    const char *label = k.s.sep ? k.b[t].name : k.name;
    if (!want) { if (k.s.ep[t] && k.sep >= 0) { dropTile(k, t); saved = true; } continue; }
    if (!k.s.ep[t]) {                            // a tile Home has not seen
      endpoint_t *ep = makeTile(c, t, 0, label);
      if (ep) { k.s.ep[t] = endpoint::get_id(ep); endpoint::enable(ep); saved = true; strlcpy(k.tileLabel[t], label, 33); ESP_LOGI(TAG, "%s: new Home tile '%s' (endpoint %d)", k.s.id, label, k.s.ep[t]); }
    }
    uint16_t ep = k.s.ep[t];
    if (!ep) continue;
    selfUpd = true;
    if (strcmp(k.tileLabel[t], label)) {         // renamed in the app
      strlcpy(k.tileLabel[t], label, 33);
      esp_matter_attr_val_t nl = esp_matter_char_str(k.tileLabel[t], strlen(k.tileLabel[t]));
      attribute::update(ep, BridgedDeviceBasicInformation::Id, BridgedDeviceBasicInformation::Attributes::NodeLabel::Id, &nl);
    }
    esp_matter_attr_val_t r = esp_matter_bool(k.seen && ms() - k.seen < 1500000);   // not heard for 25 minutes: not responding
    attribute::update(ep, BridgedDeviceBasicInformation::Id, BridgedDeviceBasicInformation::Attributes::Reachable::Id, &r);
    HomeView v = homeViewOf(bl, n);
    HomeSend s = homeSendOf(v, k.tileLift[t] < 0, k.tileLift[t], k.tileOp[t]);
    if (s.lift) {
      k.tileLift[t] = v.lift;
      setU16(ep, WindowCovering::Id, WindowCovering::Attributes::CurrentPositionLiftPercent100ths::Id, (uint16_t)v.lift);
      if (s.target) setU16(ep, WindowCovering::Id, WindowCovering::Attributes::TargetPositionLiftPercent100ths::Id, (uint16_t)v.lift);
    }
    if (s.op) { k.tileOp[t] = v.op; esp_matter_attr_val_t o = esp_matter_bitmap8(s.opBits); attribute::update(ep, WindowCovering::Id, WindowCovering::Attributes::OperationalStatus::Id, &o); }
    if (k.pct >= 0) {
      esp_matter_attr_val_t bp = esp_matter_nullable_uint8(nullable<uint8_t>(homeBatPercent(k.pct)));
      attribute::update(ep, PowerSource::Id, PowerSource::Attributes::BatPercentRemaining::Id, &bp);
      esp_matter_attr_val_t bl2 = esp_matter_enum8(homeChargeLevel(k.pct));
      attribute::update(ep, PowerSource::Id, PowerSource::Attributes::BatChargeLevel::Id, &bl2);
    }
    selfUpd = false;
  }
  if (saved) saveCtrls();
  xSemaphoreGive(stateMx);
}
// Home asked a tile to move. Done on a worker task (it waits for the controller).
struct Move { int c, t, lift; };
static QueueHandle_t moves;
static esp_err_t attr_cb(attribute::callback_type_t type, uint16_t ep, uint32_t cl, uint32_t at, esp_matter_attr_val_t *val, void *) {
  if (type != PRE_UPDATE || selfUpd || cl != WindowCovering::Id || at != WindowCovering::Attributes::TargetPositionLiftPercent100ths::Id) return ESP_OK;
  int c, t;
  if (!homeLiftValid(val->val.u16) || !epFind(ep, c, t)) return ESP_OK;
  Move m = {c, t, val->val.u16};
  xQueueSend(moves, &m, 0);
  return ESP_OK;
}
static void moveTask(void *) {
  for (;;) {
    Move m;
    if (xQueueReceive(moves, &m, portMAX_DELAY) != pdTRUE) continue;
    Ctrl &k = ctrls[m.c];
    BlindNow bl[PORTS];
    int n = tileBlinds(k, m.t, bl);
    bool moving = false;
    for (int i = 0; i < n; i++) moving = moving || bl[i].busy;
    bool stop = homeAskIsStop(moving, m.lift, k.tileLift[m.t]);    // Home's "stop": go to where you are
    char cmd[60];
    if (stop) strlcpy(cmd, "/api/stop", sizeof cmd);
    else if (k.s.sep) snprintf(cmd, sizeof cmd, "/api/home?b=%d&lift=%d", m.t, m.lift);
    else snprintf(cmd, sizeof cmd, "/api/home?b=all&lift=%d", m.lift);
    uint32_t t0 = ms();
    std::string r = ctrlCommand(m.c, cmd);
    ESP_LOGI(TAG, "Home: %s %s -> %s (%lu ms)", k.s.id, cmd, r.empty() ? "no answer" : r.c_str(), (unsigned long)(ms() - t0));
  }
}

// ---- the controllers' pushes and answers
static void announce(int c);
static bool sameAddr(const sockaddr_in6 &a, const sockaddr_in6 &b) { return !memcmp(&a.sin6_addr, &b.sin6_addr, 16); }
static void udpTask(void *) {
  static char buf[2400];
  for (;;) {
    sockaddr_in6 from;
    socklen_t fl = sizeof from;
    int n = recvfrom(sock, buf, sizeof buf - 1, 0, (sockaddr *)&from, &fl);   // room for the end mark
    if (n < 3) continue;
    char t = buf[0];
    uint16_t seq = ((uint8_t)buf[1] << 8) | (uint8_t)buf[2];
    { char ip[48]; inet6_ntoa_r(from.sin6_addr, ip, sizeof ip); ESP_LOGD(TAG, "udp '%c' %d bytes from %s", t, n, ip); if (t == 'S') ESP_LOGI(TAG, "push from %s", ip); }
    if (t == 'G') {                             // a controller leaving (factory reset): stop pointing the app here
      xSemaphoreTake(stateMx, portMAX_DELAY);
      for (int i = 0; i < MAX_CTRL; i++) if (ctrls[i].used && ctrls[i].addrOk && sameAddr(ctrls[i].addr, from)) {
        // One that let the hub in proves it is really leaving (anyone else could say it for it).
        if (ctrls[i].s.keyState == KEY_IN && (!ctrls[i].bootOk || !macOk(i, "ctl-bye" + std::string((const char *)ctrls[i].boot, 4), std::string(buf + 3, n - 3)))) continue;
        std::string inst = ctrls[i].s.id;
        for (auto &ch : inst) ch = toupper(ch);
        mdns_service_remove_for_host((inst + " via Tilt Hub").c_str(), "_tilt", "_tcp", nullptr);
        ctrls[i].announced = false;
        ctrls[i].seen = 0;
        ctrls[i].hello.clear();
        // It forgot everything: the hub's key there is gone too. Ask to join again once it is set up anew.
        ctrls[i].s.keyState = KEY_NONE; proofs[i] = {};
        saveCtrls(); proofsSave();
        ESP_LOGI(TAG, "%s was reset: it is new again", ctrls[i].s.id);
      }
      xSemaphoreGive(stateMx);
      continue;
    }
    if (t == 'L') {                             // a line of a controller's event log
      buf[n] = 0;
      int c = -1;
      xSemaphoreTake(stateMx, portMAX_DELAY);
      for (int i = 0; i < MAX_CTRL; i++) if (ctrls[i].used && ctrls[i].addrOk && !memcmp(&ctrls[i].addr.sin6_addr, &from.sin6_addr, 16)) c = i;
      xSemaphoreGive(stateMx);
      ESP_LOGI(TAG, "[%s] %s", c >= 0 ? ctrls[c].s.id : "?", buf + 3);
      continue;
    }
    if (t == 'h' && seq == 0 && n > 6) {       // the answer to a hello the hub sent an attached device
      buf[n] = 0;
      cJSON *j = cJSON_Parse(buf + 6);
      const char *id = j ? cJSON_GetStringValue(cJSON_GetObjectItem(j, "id")) : nullptr;
      if (id && strlen(id) == 12) {
        xSemaphoreTake(stateMx, portMAX_DELAY);
        int c = findCtrl(id);
        if (c < 0) for (int i = 0; i < MAX_CTRL; i++) if (!ctrls[i].used) { c = i; memset(&ctrls[i].s, 0, sizeof ctrls[i].s); strlcpy(ctrls[i].s.id, id, 13); ctrls[i].used = true; saveCtrls(); break; }
        if (c >= 0) {
          // A hello answer carries no proof. It points the hub at a controller it has no key for yet, or at one that
          // has gone quiet for a minute (it restarted and its address changed); otherwise only proven pushes move it.
          if (ctrls[c].s.keyState != KEY_IN || !ctrls[c].addrOk || (ms() - ctrls[c].seen > 60000 && otaFor != c)) {
            ctrls[c].addr = from; ctrls[c].addrOk = true; ctrls[c].seen = ms() ? ms() : 1;
            const uint8_t *a = (const uint8_t *)&from.sin6_addr;
            ctrls[c].rloc = (a[11] == 0xff && a[12] == 0xfe) ? (a[14] << 8 | a[15]) : 0;
            const char *nm = cJSON_GetStringValue(cJSON_GetObjectItem(j, "name"));
            if (nm) cleanName(ctrls[c].name, sizeof ctrls[c].name, nm);
            ESP_LOGI(TAG, "controller %s (%s) answered on Thread", id, ctrls[c].name);
            ctrls[c].announced = false;
          }
        }
        xSemaphoreGive(stateMx);
      }
      if (j) cJSON_Delete(j);
      continue;
    }
    if (t == 'h' && n > 6 && !memcmp(buf + 3, "200", 3)) {   // keep the controller's hello for the app
      buf[n] = 0;
      cJSON *hj = cJSON_Parse(buf + 6);
      const char *hid = hj ? cJSON_GetStringValue(cJSON_GetObjectItem(hj, "id")) : nullptr, *hb = hj ? cJSON_GetStringValue(cJSON_GetObjectItem(hj, "boot")) : nullptr;
      xSemaphoreTake(stateMx, portMAX_DELAY);
      int hc = hid ? findCtrl(hid) : -1;
      if (hc >= 0 && hb && strlen(hb) == 8) { ctrls[hc].hello.assign(buf + 6, n - 6); strlcpy(ctrls[hc].helloBoot, hb, 9); }
      xSemaphoreGive(stateMx);
      if (hj) cJSON_Delete(hj);
    }
    if (t == 'w' && n >= 6) {                   // a firmware piece arrived: the next offset it wants
      int f = otaFor;
      if (f < 0 || !sameAddr(ctrls[f].addr, from)) continue;   // only from the controller being updated
      ctrls[f].seen = ms() ? ms() : 1;
      buf[n] = 0;
      OtaAck a = {!memcmp(buf + 3, "200", 3), buf[6] >= '0' && buf[6] <= '9', (uint32_t)strtoul(buf + 6, nullptr, 10)};   // 3-digit status, then the offset
      if (!a.ok) { static int shown = 0; if (shown++ < 3) ESP_LOGW(TAG, "piece answer: '%.40s'", buf + 3); }
      if (otaAcks) xQueueSend(otaAcks, &a, 0);
      continue;
    }
    if (t == '#' && n > 5) {                   // a piece of a long answer: '#' seq, piece, count, part
      int i = (uint8_t)buf[3], count = (uint8_t)buf[4];
      if (count < 2 || count > 16 || i >= count) continue;
      xSemaphoreTake(pendMx, portMAX_DELAY);
      for (auto &p : pend) {
        if (!p.used || p.done || p.seq != seq || memcmp(&p.to, &from.sin6_addr, 16)) continue;
        if (p.count && p.count != count) break;
        p.count = count;
        p.part[i].assign(buf + 5, n - 5);
        p.have |= 1 << i;
        if (p.have == (1 << count) - 1) {
          p.ans.clear();
          for (int k = 0; k < count; k++) { p.ans += p.part[k]; p.part[k].clear(); }
          p.done = true;
          xSemaphoreGive(p.sem);
          for (auto &k : ctrls) if (k.used && k.addrOk && sameAddr(k.addr, from)) k.seen = ms() ? ms() : 1;
        }
        break;
      }
      xSemaphoreGive(pendMx);
      continue;
    }
    if (t != 'S') {                             // an answer to one of our requests
      xSemaphoreTake(pendMx, portMAX_DELAY);
      bool matched = false;
      for (auto &p : pend) if (p.used && !p.done && p.seq == seq && !memcmp(&p.to, &from.sin6_addr, 16)) { p.ans.assign(buf + 3, n - 3); p.done = true; matched = true; xSemaphoreGive(p.sem); }
      if (matched) for (auto &k : ctrls) if (k.used && k.addrOk && sameAddr(k.addr, from)) k.seen = ms() ? ms() : 1;   // it answered: heard from
      xSemaphoreGive(pendMx);
      continue;
    }
    // A status push: JSON, then (from a controller that has let the hub in) "\n" count "." proof.
    buf[n] = 0;
    char *nl = strchr(buf + 3, '\n');
    std::string json(buf + 3, nl ? nl - (buf + 3) : n - 3), tail = nl ? std::string(nl + 1) : std::string();
    cJSON *j = cJSON_Parse(json.c_str());
    const char *id = j ? cJSON_GetStringValue(cJSON_GetObjectItem(j, "id")) : nullptr;
    const char *pb = j ? cJSON_GetStringValue(cJSON_GetObjectItem(j, "boot")) : nullptr;
    uint8_t boot[4];
    if (!id || strlen(id) != 12 || !pb || !unhex(pb, boot, 4)) { if (j) cJSON_Delete(j); continue; }
    xSemaphoreTake(stateMx, portMAX_DELAY);
    int c = findCtrl(id);
    bool isNew = c < 0;
    if (c >= 0 && ctrls[c].s.keyState == KEY_IN) {    // let the hub in: a proven push, never an old one (boot count, then count)
      size_t dot = tail.find('.');
      uint32_t pn = dot == std::string::npos ? 0 : strtoul(tail.c_str(), nullptr, 10);
      cJSON *bnj = cJSON_GetObjectItem(j, "bn");
      uint32_t bn = cJSON_IsNumber(bnj) ? (uint32_t)bnj->valuedouble : 0;
      bool proven = pn && macOk(c, "ctl-push" + std::string((const char *)boot, 4) + json + std::to_string(pn), tail.substr(dot + 1));
      bool fresh = bn > proofs[c].bn || (bn == proofs[c].bn && (strcmp(pb, ctrls[c].pushBoot) || pn > ctrls[c].pushN));
      if (proven && fresh) {
        ctrls[c].pushN = pn;
        if (!proofs[c].on || bn != proofs[c].bn) { proofs[c].on = 1; proofs[c].bn = bn; proofsSave(); }
      } else if (proofs[c].on || proven) {       // once it proves its pushes, nothing else counts (nor an old one)
        static uint32_t told = 0;
        if (ms() - told > 60000) { told = ms(); ESP_LOGW(TAG, "%s: a push without a good proof was ignored", id); }
        xSemaphoreGive(stateMx); cJSON_Delete(j); continue;
      }
      // (not proven yet: it has not been told which key is the hub's; taken as before setup)
    }
    if (isNew) {
      for (int i = 0; i < MAX_CTRL && c < 0; i++) if (!ctrls[i].used) c = i;
      // Full: a place held by one that never let the hub in and has been quiet for 10 minutes is taken over (so made-up
      // ids cannot fill the hub for good).
      for (int i = 0; i < MAX_CTRL && c < 0; i++) {
        bool tiles = false;
        for (int p = 0; p < PORTS; p++) tiles = tiles || ctrls[i].s.ep[p];
        if (ctrls[i].s.keyState == KEY_NONE && !tiles && !ctrls[i].announced && ms() - ctrls[i].seen > 600000) c = i;
      }
      if (c >= 0) {                              // a clean place (the request lock stays)
        SemaphoreHandle_t m = ctrls[c].mx;
        ctrls[c] = Ctrl{};
        Ctrl &f = ctrls[c];
        f.mx = m; f.pct = -1; f.sep = -1; f.own = -1;
        for (auto &b : f.b) b.tilt = b.tgt = INT32_MIN;
        for (int t = 0; t < PORTS; t++) f.tileLift[t] = f.tileOp[t] = -1;
        strlcpy(f.s.id, id, 13); f.used = true;
        saveCtrls();
      }
    }
    if (c < 0) { xSemaphoreGive(stateMx); cJSON_Delete(j); continue; }
    Ctrl &k = ctrls[c];
    // Answer with the time (the controller's Schedules need it), with the proof so it can trust it.
    {
      std::string ts = std::to_string((long)time(nullptr)), mac = macOf(c, "hub-time" + std::string((const char *)boot, 4) + ts);
      if (!mac.empty() && time(nullptr) > 1700000000) {
        std::string ack = std::string("s") + buf[1] + buf[2] + "200" + ts + "." + mac;
        sendto(sock, ack.data(), ack.size(), 0, (sockaddr *)&from, fl);
      }
    }
    bool moved = !k.addrOk || memcmp(&k.addr.sin6_addr, &from.sin6_addr, 16);
    k.addr = from; k.addrOk = true; k.seen = ms() ? ms() : 1;
    const char *nm = cJSON_GetStringValue(cJSON_GetObjectItem(j, "name"));
    char clean[33];
    if (nm) cleanName(clean, sizeof clean, nm);
    if (nm && strcmp(clean, k.name)) { strlcpy(k.name, clean, sizeof k.name); k.announced = false; }
    k.pct = cJSON_GetNumberValue(cJSON_GetObjectItem(j, "pct"));
    k.low = cJSON_GetNumberValue(cJSON_GetObjectItem(j, "low"));
    cJSON *ownj = cJSON_GetObjectItem(j, "own");
    if (cJSON_IsNumber(ownj) && ownj->valueint != k.own) { k.own = ownj->valueint; k.announced = false; k.hello.clear(); }   // its hello says "owned": ask it again
    cJSON *cvj = cJSON_GetObjectItem(j, "cv");
    if (cJSON_IsNumber(cvj)) k.cv = (uint32_t)cvj->valuedouble;
    if (!k.firstSeen) k.firstSeen = ms() ? ms() : 1;
    const char *fwv = cJSON_GetStringValue(cJSON_GetObjectItem(j, "fw"));
    if (fwv) cleanName(k.fw, sizeof k.fw, fwv);
    k.closeUp = cJSON_GetNumberValue(cJSON_GetObjectItem(j, "closeUp"));
    cJSON *sp = cJSON_GetObjectItem(j, "sep");
    k.sep = cJSON_IsNumber(sp) ? (sp->valueint ? 1 : 0) : 0;
    const char *bt = cJSON_GetStringValue(cJSON_GetObjectItem(j, "boot"));
    if (bt && strlen(bt) == 8 && strcmp(bt, k.pushBoot)) {   // it restarted: its new boot id (for the hub's own commands too)
      strlcpy(k.pushBoot, bt, sizeof k.pushBoot);
      k.bootOk = unhex(bt, k.boot, 4);
    }
    cJSON *bl = cJSON_GetObjectItem(j, "b");
    for (int p = 0; p < PORTS && bl; p++) {
      cJSON *b = cJSON_GetArrayItem(bl, p);
      if (!b) break;
      Ctrl::B &x = k.b[p];
      const char *bn = cJSON_GetStringValue(cJSON_GetObjectItem(b, "n"));
      cleanName(x.name, sizeof x.name, bn ? bn : "");
      x.hid = cJSON_GetNumberValue(cJSON_GetObjectItem(b, "h"));
      x.ok = cJSON_GetNumberValue(cJSON_GetObjectItem(b, "ok"));
      cJSON *tv = cJSON_GetObjectItem(b, "t"), *gv = cJSON_GetObjectItem(b, "g");
      x.tilt = cJSON_IsNumber(tv) ? (int)tv->valuedouble : INT32_MIN;
      x.tgt = cJSON_IsNumber(gv) ? (int)gv->valuedouble : INT32_MIN;
      x.mov = cJSON_GetNumberValue(cJSON_GetObjectItem(b, "m"));
    }
    alertsFromPush(c, j);
    xSemaphoreGive(stateMx);
    cJSON_Delete(j);
    if (isNew || moved) ESP_LOGI(TAG, "controller %s (%s) on Thread", k.s.id, k.name);
    if (matterUp) chip::DeviceLayer::PlatformMgr().ScheduleWork(applyStatus, (intptr_t)c);
    if (!k.announced) announce(c);
  }
}
// Every few seconds: ask to join any controller the hub has no key for, and mark quiet ones not responding.
static std::string hubIp();
static void bleScan();
static std::string ctrlCommand(int c, const std::string &cmd);
// ---- settings backups: one per controller id (also after it is gone: that is when it is needed). In flash:
// "bm<n>" = BackupMeta, "bk<n>" = the controller's backup blob (blinds_matter/main/hub_link.h backupBlob).
struct BackupMeta { char id[13]; char name[33]; uint32_t cv, when; };
const int MAX_BACKUPS = 8;
static int backupSlot(const char *id, bool make) {
  int freeSlot = -1;
  for (int i = 0; i < MAX_BACKUPS; i++) {
    char key[16]; snprintf(key, sizeof key, "bm%d", i);
    BackupMeta m; size_t n = sizeof m;
    if (nvs_get_blob(nv, key, &m, &n) == ESP_OK && n == sizeof m) { if (!strcmp(m.id, id)) return i; }
    else if (freeSlot < 0) freeSlot = i;
  }
  return make ? (freeSlot >= 0 ? freeSlot : 0) : -1;
}
static uint32_t backupCv(const char *id) {
  int i = backupSlot(id, false);
  if (i < 0) return 0;
  char key[16]; snprintf(key, sizeof key, "bm%d", i);
  BackupMeta m; size_t n = sizeof m;
  return nvs_get_blob(nv, key, &m, &n) == ESP_OK ? m.cv : 0;
}
static void takeBackup(int c) {                  // with the hub's own key (a user may read the backup)
  std::string r = ctrlCommand(c, "/api/backup");
  cJSON *j = r.empty() ? nullptr : cJSON_Parse(r.c_str());
  const char *d = j ? cJSON_GetStringValue(cJSON_GetObjectItem(j, "d")) : nullptr;
  cJSON *cvj = j ? cJSON_GetObjectItem(j, "cv") : nullptr;
  if (d && cJSON_IsNumber(cvj) && strlen(d) % 2 == 0 && strlen(d) / 2 <= 2048) {
    std::string blob(strlen(d) / 2, 0);
    if (unhex(d, (uint8_t *)&blob[0], blob.size())) {
      int i = backupSlot(ctrls[c].s.id, true);
      BackupMeta m = {};
      strlcpy(m.id, ctrls[c].s.id, sizeof m.id); strlcpy(m.name, ctrls[c].name, sizeof m.name);
      m.cv = (uint32_t)cvj->valuedouble; m.when = time(nullptr) > 1700000000 ? (uint32_t)time(nullptr) : 0;   // 0: the clock was not set yet
      char key[16];
      snprintf(key, sizeof key, "bk%d", i); nvs_set_blob(nv, key, blob.data(), blob.size());
      snprintf(key, sizeof key, "bm%d", i); nvs_set_blob(nv, key, &m, sizeof m);
      nvs_commit(nv);
      ESP_LOGI(TAG, "%s: settings backed up (%u bytes)", m.id, (unsigned)blob.size());
    }
  }
  if (j) cJSON_Delete(j);
}
static void careTask(void *) {
  vTaskDelay(pdMS_TO_TICKS(20000));
  if (hubIp() == "0.0.0.0") {                      // no Wi-Fi after 20 s: show what the hub can see (USB log)
    esp_wifi_disconnect();
    wifi_scan_config_t sc = {};
    sc.show_hidden = true;
    if (esp_wifi_scan_start(&sc, true) == ESP_OK) {
      uint16_t n = 20;
      static wifi_ap_record_t aps[20];
      esp_wifi_scan_get_ap_records(&n, aps);
      ESP_LOGW(TAG, "no Wi-Fi: %d networks in range", n);
      for (int i = 0; i < n; i++) ESP_LOGW(TAG, "  '%s' channel %d %d dBm", (const char *)aps[i].ssid, aps[i].primary, aps[i].rssi);
    } else ESP_LOGW(TAG, "no Wi-Fi, and the scan did not start");
    esp_wifi_connect();
  }
  for (;;) {
    vTaskDelay(pdMS_TO_TICKS(ms() < 90000 ? 5000 : 15000));   // quicker just after a start: find the controllers again
    if (hubTrial) {                              // new hub firmware: keep it once Wi-Fi and Apple Home are up for a minute
      static uint32_t upSince = 0;
      bool up = hubIp() != "0.0.0.0" && matterUp;
      if (up && !upSince) upSince = ms() ? ms() : 1;
      if (!up) upSince = 0;
      if (upSince && ms() - upSince > 60000) { esp_ota_mark_app_valid_cancel_rollback(); hubTrial = false; ESP_LOGI(TAG, "new hub firmware %s kept", esp_app_get_description()->version); }
      else if (ms() > 300000) { ESP_LOGE(TAG, "new hub firmware did not get Wi-Fi and Apple Home up: going back"); vTaskDelay(pdMS_TO_TICKS(200)); esp_ota_mark_app_invalid_rollback_and_reboot(); }
    }
    static uint32_t lastScan = 0;
    if (ms() - lastScan > 30000) { lastScan = ms(); bleScan(); }
    // Not in a home yet: Apple Home can add the hub in its first 15 minutes after power-on, and for 15 minutes after the
    // owner opens "Add Tilt Hub to Apple Home" in the app (sealed /api/homecode). Not open all the time.
    if (matterUp && (ms() < 900000 || (int32_t)(homeWindowUntil - ms()) > 0)) chip::DeviceLayer::PlatformMgr().ScheduleWork([](intptr_t) {
      auto &mgr = chip::Server::GetInstance().GetCommissioningWindowManager();
      if (chip::Server::GetInstance().GetFabricTable().FabricCount() == 0 && !mgr.IsCommissioningWindowOpen()) {
        mgr.OpenBasicCommissioningWindow(chip::System::Clock::Seconds16(900), chip::CommissioningWindowAdvertisement::kAllSupported);
        ESP_LOGI(TAG, "pairing window open again (not in a home yet)");
      }
    }, 0);
    {                                            // who is on the Thread network (USB log)
      esp_openthread_lock_acquire(portMAX_DELAY);
      otInstance *ot = esp_openthread_get_instance();
      int role = otThreadGetDeviceRole(ot), kids = 0;
      otChildInfo ci;
      for (uint16_t i = 0; i < otThreadGetMaxAllowedChildren(ot); i++) if (otThreadGetChildInfoByIndex(ot, i, &ci) == OT_ERROR_NONE) {
        kids++;
        ESP_LOGI(TAG, "  child %04x ext %02x%02x%02x%02x age %lu s timeout %lu s rx-on %d state %d", ci.mRloc16, ci.mExtAddress.m8[0], ci.mExtAddress.m8[1], ci.mExtAddress.m8[2],
                 ci.mExtAddress.m8[3], (unsigned long)ci.mAge, (unsigned long)ci.mTimeout, ci.mRxOnWhenIdle, ci.mIsStateRestoring);
      }
      uint8_t ch = otLinkGetChannel(ot);
      otExtAddress kidAddr[8];
      int kidN = 0;
      for (uint16_t i = 0; i < otThreadGetMaxAllowedChildren(ot) && kidN < 8; i++) if (otThreadGetChildInfoByIndex(ot, i, &ci) == OT_ERROR_NONE) kidAddr[kidN++] = ci.mExtAddress;
      esp_openthread_lock_release();
      static int lastKids = -1, lastRole = -1;
      // A device is attached that the hub has not heard from lately: say hello to it, at its own link-local address
      // (fe80:: + its Thread address with the local bit flipped). Thread keeps the message until the device checks in
      // (a multicast would be missed by a sleeping one). A controller answers with its id and learns where the hub is.
      bool quiet = true;
      for (int c = 0; c < MAX_CTRL; c++) if (ctrls[c].used && ctrls[c].addrOk && ms() - ctrls[c].seen < 60000) quiet = false;
      for (int i = 0; quiet && i < kidN; i++) {
        sockaddr_in6 d = {};
        d.sin6_family = AF_INET6;
        d.sin6_port = htons(HUB_PORT);
        uint8_t *a = (uint8_t *)&d.sin6_addr;
        a[0] = 0xfe; a[1] = 0x80;
        memcpy(a + 8, kidAddr[i].m8, 8);
        a[8] ^= 0x02;
        d.sin6_scope_id = esp_netif_get_netif_impl_index(esp_openthread_get_netif());
        const char h[] = {'H', 0, 0};
        if (sendto(sock, h, 3, 0, (sockaddr *)&d, sizeof d) != 3) ESP_LOGW(TAG, "hello not sent (errno %d)", errno);
      }
      if (kids != lastKids || role != lastRole) { ESP_LOGI(TAG, "Thread: role %d, channel %d, %d child%s", role, ch, kids, kids == 1 ? "" : "ren"); lastKids = kids; lastRole = role; }
    }
    for (int c = 0; c < MAX_CTRL; c++) {
      if (!ctrls[c].used || !ctrls[c].addrOk) continue;
      if (!ctrls[c].announced && ctrls[c].seen && ms() - ctrls[c].seen < 1200000) announce(c);
      if (ctrls[c].announced && ms() - ctrls[c].seen > 1500000) {   // quiet for 25 minutes (on Wi-Fi again?): stop pointing the app here
        std::string inst = ctrls[c].s.id;
        for (auto &ch : inst) ch = toupper(ch);
        mdns_service_remove_for_host((inst + " via Tilt Hub").c_str(), "_tilt", "_tcp", nullptr);
        ctrls[c].announced = false;
        ESP_LOGI(TAG, "%s quiet: no longer announced", ctrls[c].s.id);
      }
      if (ctrls[c].s.keyState == KEY_IN && ctrls[c].cv && ctrls[c].cv != backupCv(ctrls[c].s.id)) takeBackup(c);
      if (ctrls[c].s.keyState == KEY_NONE) askToJoin(c);
      else if (ctrls[c].s.keyState == KEY_ASKED) ctrlCommand(c, "/api/s");   // let in yet? (also tells us at once)
      if (matterUp) chip::DeviceLayer::PlatformMgr().ScheduleWork(applyStatus, (intptr_t)c);
    }
    alertsCare();
  }
}

// ---- new controllers nearby: a controller nobody owns yet says "Tilt new" in its Bluetooth scan response (first
// 15 minutes after it is powered on). The app shows them as "New controller found".
struct NewOne { uint8_t addr[6]; int rssi; uint32_t seen; };
static NewOne newOnes[6];
static SemaphoreHandle_t newMx;
static int bleSeen(ble_gap_event *ev, void *) {
  if (ev->type != BLE_GAP_EVENT_DISC) return 0;
  ble_hs_adv_fields f;
  if (ble_hs_adv_parse_fields(&f, ev->disc.data, ev->disc.length_data) || !f.name || f.name_len != 8 || memcmp(f.name, "Tilt new", 8)) return 0;
  xSemaphoreTake(newMx, portMAX_DELAY);
  int slot = -1, oldest = 0;
  for (int i = 0; i < 6; i++) {
    if (newOnes[i].seen && !memcmp(newOnes[i].addr, ev->disc.addr.val, 6)) { slot = i; break; }
    if (newOnes[i].seen < newOnes[oldest].seen) oldest = i;
  }
  if (slot < 0) {
    slot = oldest;
    memcpy(newOnes[slot].addr, ev->disc.addr.val, 6);
    const uint8_t *a = ev->disc.addr.val;
    ESP_LOGI(TAG, "new controller nearby (Bluetooth %02x:%02x:%02x:%02x:%02x:%02x, %d dBm)", a[5], a[4], a[3], a[2], a[1], a[0], ev->disc.rssi);
  }
  newOnes[slot].rssi = ev->disc.rssi;
  newOnes[slot].seen = ms() ? ms() : 1;
  xSemaphoreGive(newMx);
  return 0;
}
static void bleScan() {                          // 4 s, listening 10 % of the time: Wi-Fi and Thread keep the radio
  if (!ble_hs_synced() || ble_gap_disc_active()) return;
  uint8_t own;
  if (ble_hs_id_infer_auto(0, &own)) return;
  ble_gap_disc_params dp = {};
  dp.itvl = 160;                                 // 100 ms
  dp.window = 16;                                // 10 ms
  dp.passive = 0;                                // ask for the scan response (the name is there)
  int e = ble_gap_disc(own, 4000, &dp, bleSeen, nullptr);
  if (e) ESP_LOGW(TAG, "Bluetooth scan did not start (%d)", e);
}
static bool newNearby(uint32_t withinMs = 300000) {
  bool any = false;
  xSemaphoreTake(newMx, portMAX_DELAY);
  for (auto &n : newOnes) any = any || (n.seen && ms() - n.seen < withinMs);
  xSemaphoreGive(newMx);
  return any;
}

// ---- a controller's firmware through the hub: the app uploads the signed file here (fast, Wi-Fi), the hub keeps it
// in its staging area and feeds it to the controller over Thread (protocol: blinds_matter/main/hub_link.h).
// The hub's spare firmware slot: a controller's file is kept here while it is sent, and the hub's own next firmware
// is written here. (So nothing else uses it while the hub tries new firmware: then it is the way back.)
static const esp_partition_t *stage;
static uint32_t stageSize;
static bool stageDelta;                           // the staged file is a patch (blinds_matter/main/hub_link.h)
static uint32_t pieceBytes = 480, piecesInFlight = 6;      // measured: 480 x 6 is about 4 KB/s; 960 x 8 lost most pieces          // piece size and pieces in flight (?ch=&win= on the upload, for tuning)
static uint32_t uploadUntil[MAX_CTRL];           // an owner allowed an upload for this controller (sealed /api/upload)
static void otaFail(Ctrl &k, const char *why) { k.otaSt = OTA_FAILED; cleanName(k.otaErr, sizeof k.otaErr, why); ESP_LOGW(TAG, "%s: update failed: %s", k.s.id, why); alertUpdateFailed((int)(&k - ctrls), why); }
static void otaTask(void *arg) {
  int c = (int)(intptr_t)arg;
  Ctrl &k = ctrls[c];
  uint32_t CH = pieceBytes, WIN = piecesInFlight;               // a controller that keeps its radio on takes big pieces
  std::string ans;
  if (ctrlCommand(c, "/api/s").empty()) { otaFail(k, "the controller did not answer"); otaFor = -1; vTaskDelete(nullptr); return; }   // fresh boot id
  std::string sz = std::to_string(stageSize) + (stageDelta ? ",d" : "") + "@" + std::to_string((long)time(nullptr)), mac = k.bootOk ? macOf(c, "hub-ota" + std::string((const char *)k.boot, 4) + sz) : "";
  if (mac.empty()) { otaFail(k, "the hub has no key on this controller yet"); otaFor = -1; vTaskDelete(nullptr); return; }
  int st = ask(c, 'B', sz + "." + mac, ans, 45000);   // an older controller erases its whole slot first
  if (st != 200) { otaFail(k, st == 403 ? "updates are locked (allow them first)" : st ? "the controller refused to start" : "no answer"); otaFor = -1; vTaskDelete(nullptr); return; }
  xQueueReset(otaAcks);
  uint32_t acked = 0, next = 0, misses = 0, t0 = ms(), moved = ms();
  static uint8_t pkt[3 + 4 + 1200];
  while (acked < stageSize && misses < 25 && ms() - moved < 120000) {
    while (next < stageSize && next < acked + WIN * CH) {
      uint32_t n = stageSize - next < CH ? stageSize - next : CH;
      pkt[0] = 'W'; pkt[1] = 0; pkt[2] = 0;
      pkt[3] = next >> 24; pkt[4] = next >> 16; pkt[5] = next >> 8; pkt[6] = next;
      esp_partition_read(stage, next, pkt + 7, n);
      sendto(sock, pkt, 7 + n, 0, (sockaddr *)&k.addr, sizeof k.addr);
      next += n;
    }
    OtaAck a;
    if (xQueueReceive(otaAcks, &a, pdMS_TO_TICKS(2500)) != pdTRUE) {
      if (acked == 0 && misses >= 1 && CH > 80) { CH = 80; WIN = 8; ESP_LOGW(TAG, "%s: small pieces (older controller)", k.s.id); }
      misses++; ESP_LOGW(TAG, "%s: no answer to pieces (%lu)", k.s.id, (unsigned long)misses); next = acked; continue; }   // nothing back: again from the last good place
    misses = 0;
    static uint32_t logged = 0;
    if (a.next / 50000 != logged / 50000 || !a.ok) ESP_LOGI(TAG, "%s: piece answer %s at %lu", k.s.id, a.ok ? "ok" : "MISSED", (unsigned long)a.next);
    logged = a.next;
    if (!a.num) { otaFail(k, "the controller dropped the update"); otaFor = -1; vTaskDelete(nullptr); return; }
    if (a.next > acked) { acked = a.next; moved = ms(); }
    if (!a.ok) {                                 // it missed a piece: go back to where it is
      next = a.next;
      static uint32_t lost = 0;
      if (++lost >= 12 && CH > 240) { lost = 0; CH /= 2; ESP_LOGW(TAG, "%s: many pieces lost, smaller pieces (%lu bytes)", k.s.id, (unsigned long)CH); }
    }
    k.otaPct = (int)(100ULL * acked / stageSize);
  }
  if (acked < stageSize) { otaFail(k, "the controller stopped answering"); otaFor = -1; vTaskDelete(nullptr); return; }
  k.otaSt = OTA_CHECKING;
  ESP_LOGI(TAG, "%s: %lu bytes sent in %lu s, checking", k.s.id, (unsigned long)stageSize, (unsigned long)((ms() - t0) / 1000));
  st = ask(c, 'E', "", ans, 15000);
  if (st != 200) { cJSON *j = cJSON_Parse(ans.c_str()); const char *e = j ? cJSON_GetStringValue(cJSON_GetObjectItem(j, "err")) : nullptr; otaFail(k, e ? e : "the controller did not take it"); if (j) cJSON_Delete(j); }
  else { k.otaSt = OTA_DONE; k.otaPct = 100; k.bootOk = false; ESP_LOGI(TAG, "%s: update accepted, it restarts", k.s.id); }
  otaFor = -1;
  vTaskDelete(nullptr);
}
// A file written to a partition as it came (its last 72 bytes: signature (64) and magic (8)): signed with the Tilt
// release key over everything before the signature.
static bool fileSigned(const esp_partition_t *p, uint32_t size, const char magic[8]) {
  if (size < 1000) return false;
  uint8_t tail[72], hash[32];
  esp_partition_read(p, size - 72, tail, 72);
  if (memcmp(tail + 64, magic, 8)) return false;
  mbedtls_sha256_context sh;
  mbedtls_sha256_init(&sh); mbedtls_sha256_starts(&sh, 0);
  static uint8_t buf[4096];
  for (uint32_t o = 0, end = size - 72; o < end;) {
    uint32_t n = end - o < sizeof buf ? end - o : sizeof buf;
    esp_partition_read(p, o, buf, n);
    mbedtls_sha256_update(&sh, buf, n);
    o += n;
  }
  mbedtls_sha256_finish(&sh, hash); mbedtls_sha256_free(&sh);
  mbedtls_ecp_group grp; mbedtls_ecp_point q; mbedtls_mpi r, sv;
  mbedtls_ecp_group_init(&grp); mbedtls_ecp_point_init(&q); mbedtls_mpi_init(&r); mbedtls_mpi_init(&sv);
  bool ok = mbedtls_ecp_group_load(&grp, MBEDTLS_ECP_DP_SECP256R1) == 0 && mbedtls_ecp_point_read_binary(&grp, &q, FW_SIGN_PUB, 65) == 0 &&
            mbedtls_mpi_read_binary(&r, tail, 32) == 0 && mbedtls_mpi_read_binary(&sv, tail + 32, 32) == 0 && mbedtls_ecdsa_verify(&grp, hash, 32, &q, &r, &sv) == 0;
  mbedtls_ecp_group_free(&grp); mbedtls_ecp_point_free(&q); mbedtls_mpi_free(&r); mbedtls_mpi_free(&sv);
  return ok;
}
static const char SIG_MAGIC[8] = {'T', 'I', 'L', 'T', 'S', 'I', 'G', '1'}, DLT_MAGIC[8] = {'T', 'I', 'L', 'T', 'D', 'L', 'T', '1'};
// The file in the staging area: signed, and (a full file) not older than what the controller runs. A patch is
// signed as a file too; the controller checks the image it makes and its version.
static const char *stageCheck(const Ctrl &k) {
  if (stageSize < 1000) return "that is not a firmware file";
  uint8_t head[4];
  esp_partition_read(stage, 0, head, 4);
  stageDelta = head[0] == 0x10 && head[1] == 0xde && head[2] == 0xcd && head[3] == 0xfc;
  bool ok = fileSigned(stage, stageSize, stageDelta ? DLT_MAGIC : SIG_MAGIC);
  if (!ok) return "the file's signature is not valid";
  if (stageDelta) return nullptr;
  esp_app_desc_t d;                                // after the image header (24 bytes) and the first segment header (8)
  esp_partition_read(stage, 32, &d, sizeof d);
  if (d.magic_word != ESP_APP_DESC_MAGIC_WORD) return "that is not a firmware file";
  d.version[sizeof d.version - 1] = 0;
  if (k.fw[0] && fwIsOlder(d.version, k.fw)) return "that firmware is older than the one it runs";
  return nullptr;
}
// ---- the hub's own firmware, over Wi-Fi: POST /hub/api/update, in the 5 minutes after its owner allowed it (sealed
// /api/hubupdate). The signed file goes into the spare slot; the hub checks the signature and that it is not older,
// then starts it on trial. Kept once Wi-Fi and Apple Home have worked for a minute; otherwise it goes back by itself.
static uint32_t hubUpdUntil = 0;
static esp_err_t hHubUpdate(httpd_req_t *r) {
  auto no = [&](const char *st, const char *why) { httpd_resp_set_status(r, st); return httpd_resp_sendstr(r, (std::string("{\"ok\":0,\"err\":\"") + why + "\"}").c_str()); };
  if (!hubUpdUntil || (int32_t)(ms() - hubUpdUntil) > 0) return no("403 Forbidden", "the Tilt Hub's owner has to allow this update first");
  if (hubTrial) return no("409 Conflict", "the hub is still trying the last update");
  if (otaFor >= 0) return no("409 Conflict", "the hub is updating a controller");
  if (!stage || r->content_len < 100000 || r->content_len > stage->size) return no("400 Bad Request", "that is not a hub firmware file");
  hubUpdUntil = 0;
  otaFor = MAX_CTRL;                             // nothing else writes the spare slot meanwhile
  esp_partition_erase_range(stage, 0, (r->content_len + 4095) & ~4095u);
  static char buf[4096];
  uint32_t got = 0;
  while (got < r->content_len) {
    int n = httpd_req_recv(r, buf, sizeof buf);
    if (n == HTTPD_SOCK_ERR_TIMEOUT) continue;
    if (n <= 0) { otaFor = -1; return ESP_FAIL; }
    esp_partition_write(stage, got, buf, n);
    got += n;
  }
  otaFor = -1;
  if (!fileSigned(stage, got, SIG_MAGIC)) return no("403 Forbidden", "the file's signature is not valid");
  esp_app_desc_t d;
  esp_partition_read(stage, 32, &d, sizeof d);   // after the image header (24) and the first segment header (8)
  d.version[sizeof d.version - 1] = 0;
  if (d.magic_word != ESP_APP_DESC_MAGIC_WORD || strncmp(d.project_name, "tilt_hub", sizeof d.project_name)) return no("400 Bad Request", "that is not a hub firmware file");
  if (fwIsOlder(d.version, esp_app_get_description()->version)) return no("403 Forbidden", "that firmware is older than the one the hub runs");
  if (esp_ota_set_boot_partition(stage) != ESP_OK) return no("500 Internal Server Error", "the file was not accepted");
  ESP_LOGW(TAG, "hub firmware %s accepted: restarting", d.version);
  httpd_resp_set_type(r, "application/json");
  httpd_resp_sendstr(r, (std::string("{\"ok\":1,\"fw\":\"") + d.version + "\"}").c_str());
  xTaskCreate([](void *) { vTaskDelay(pdMS_TO_TICKS(1500)); esp_restart(); }, "restart", 2048, nullptr, 3, nullptr);
  return ESP_OK;
}
// POST /c/<id>/api/update: the signed file. Only just after the hub's owner allowed it (sealed /api/upload?id=), so
// nobody else on the Wi-Fi can fill the hub or keep a controller busy. Answers once it is stored and checked; the
// progress is in /hub ("ota").
static esp_err_t hUpload(httpd_req_t *r, int c) {
  if (hubTrial) { httpd_resp_set_status(r, "409 Conflict"); return httpd_resp_sendstr(r, "{\"ok\":0,\"err\":\"the Tilt Hub is trying its own new firmware: try again in a few minutes\"}"); }
  if (!uploadUntil[c] || (int32_t)(ms() - uploadUntil[c]) > 0) { httpd_resp_set_status(r, "403 Forbidden"); return httpd_resp_sendstr(r, "{\"ok\":0,\"err\":\"the Tilt Hub's owner has to allow this update first\"}"); }
  if (!stage) { httpd_resp_set_status(r, "500 Internal Server Error"); return httpd_resp_sendstr(r, "{\"ok\":0,\"err\":\"the hub has no room for firmware\"}"); }
  if (otaFor >= 0) { httpd_resp_set_status(r, "409 Conflict"); return httpd_resp_sendstr(r, "{\"ok\":0,\"err\":\"the hub is updating another controller\"}"); }
  if (r->content_len < 1000 || r->content_len > stage->size) { httpd_resp_set_status(r, "400 Bad Request"); return httpd_resp_sendstr(r, "{\"ok\":0,\"err\":\"that is not a firmware file\"}"); }
  char q[64], v[12];
  pieceBytes = 480; piecesInFlight = 6;
  if (httpd_req_get_url_query_str(r, q, sizeof q) == ESP_OK) {
    if (httpd_query_key_value(q, "ch", v, sizeof v) == ESP_OK) pieceBytes = constrain_u(atoi(v), 32, 1200);
    if (httpd_query_key_value(q, "win", v, sizeof v) == ESP_OK) piecesInFlight = constrain_u(atoi(v), 1, 16);
  }
  otaFor = c;
  uploadUntil[c] = 0;                              // one upload per allowance
  esp_partition_erase_range(stage, 0, (r->content_len + 4095) & ~4095u);
  static char buf[4096];
  uint32_t got = 0;
  while (got < r->content_len) {
    int n = httpd_req_recv(r, buf, sizeof buf);
    if (n == HTTPD_SOCK_ERR_TIMEOUT) continue;
    if (n <= 0) { otaFor = -1; return ESP_FAIL; }
    esp_partition_write(stage, got, buf, n);
    got += n;
  }
  stageSize = got;
  Ctrl &k = ctrls[c];
  if (const char *why = stageCheck(k)) {
    otaFor = -1;
    ESP_LOGW(TAG, "%s: upload refused: %s", k.s.id, why);
    httpd_resp_set_status(r, "403 Forbidden");
    return httpd_resp_sendstr(r, (std::string("{\"ok\":0,\"err\":\"") + why + "\"}").c_str());
  }
  k.otaSt = OTA_SENDING; k.otaPct = 0; k.otaErr[0] = 0;
  xTaskCreate(otaTask, "ota", 6144, (void *)(intptr_t)c, 5, nullptr);
  ESP_LOGI(TAG, "%s: firmware stored (%lu bytes), sending it over Thread", k.s.id, (unsigned long)got);
  httpd_resp_set_type(r, "application/json");
  return httpd_resp_sendstr(r, "{\"ok\":1,\"hub\":1}");
}

// ---- the app: http://<hub>/c/<id>/x...  (the same requests as to a controller on Wi-Fi)
static std::string hubIp() {
  esp_netif_ip_info_t info = {};
  esp_netif_t *nif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
  if (nif) esp_netif_get_ip_info(nif, &info);
  char ip[20];
  snprintf(ip, sizeof ip, IPSTR, IP2STR(&info.ip));
  return ip;
}
static bool netUp() { return hubIp() != "0.0.0.0"; }
static void announce(int c) {
  std::string ip = hubIp();
  if (ip == "0.0.0.0") return;
  Ctrl &k = ctrls[c];
  std::string host = ip + "/c/" + k.s.id, inst = k.s.id;
  for (auto &ch : inst) ch = toupper(ch);
  inst += " via Tilt Hub";                         // not the controller's own name (it uses that on Wi-Fi)
  mdns_txt_item_t txt[] = {{"id", k.s.id}, {"ip", host.c_str()}, {"owned", k.own == 0 ? "0" : "1"}, {"name", k.name}, {"via", "hub"}};
  esp_err_t e = mdns_service_txt_set_for_host(inst.c_str(), "_tilt", "_tcp", nullptr, txt, 5);
  if (e != ESP_OK) e = mdns_service_add_for_host(inst.c_str(), "_tilt", "_tcp", nullptr, 80, txt, 5);
  k.announced = e == ESP_OK;
  ESP_LOGI(TAG, "announced %s as %s: %s", inst.c_str(), host.c_str(), esp_err_to_name(e));
}
static const char *reason(int st) {
  switch (st) { case 200: return "200 OK"; case 400: return "400 Bad Request"; case 401: return "401 Unauthorized"; case 403: return "403 Forbidden";
    case 409: return "409 Conflict"; case 429: return "429 Too Many Requests"; case 500: return "500 Internal Server Error"; default: return "504 Gateway Timeout"; }
}
static esp_err_t hRelay(httpd_req_t *r) {
  const char *u = r->uri + 3;                    // after "/c/"
  char id[13] = {0};
  strlcpy(id, u, sizeof id);
  const char *rest = u + strlen(id);
  std::string path(rest);
  size_t q = path.find('?');
  if (q != std::string::npos) path.resize(q);
  xSemaphoreTake(stateMx, portMAX_DELAY);
  int c = findCtrl(id);
  xSemaphoreGive(stateMx);
  // Unknown here: gone (reset, or the hub was reset); the app offers to remove it. Known but not heard from since the
  // hub started: not answering yet.
  if (c < 0) { httpd_resp_set_status(r, "410 Gone"); return httpd_resp_sendstr(r, "{\"err\":\"not on this hub\"}"); }
  if (!ctrls[c].addrOk) { httpd_resp_set_status(r, "504 Gateway Timeout"); return httpd_resp_sendstr(r, "{\"err\":\"the controller has not checked in yet\"}"); }
  if (r->method == HTTP_POST && path == "/api/update") return hUpload(r, c);
  char type = 0;
  if (r->method == HTTP_GET && path == "/x/hello") type = 'H';
  else if (r->method == HTTP_POST && path == "/x") type = 'X';
  else if (r->method == HTTP_POST && path == "/x/ask") type = 'A';
  else if (r->method == HTTP_POST && path == "/x/pair") type = 'P';
  if (!type) { httpd_resp_set_status(r, "404 Not Found"); return httpd_resp_sendstr(r, "{\"err\":\"not through the hub\"}"); }
  std::string body;
  if (r->method == HTTP_POST) {
    if (r->content_len > 2200) { httpd_resp_set_status(r, "400 Bad Request"); return httpd_resp_sendstr(r, "{\"err\":\"too big\"}"); }
    body.resize(r->content_len);
    size_t got = 0;
    while (got < body.size()) { int n = httpd_req_recv(r, &body[got], body.size() - got); if (n == HTTPD_SOCK_ERR_TIMEOUT) continue; if (n <= 0) return ESP_FAIL; got += n; }
  }
  if (type == 'H') {                             // the hello from memory, while it is still the same start of the controller
    xSemaphoreTake(stateMx, portMAX_DELAY);
    Ctrl &k = ctrls[c];
    std::string h = (!k.hello.empty() && !strcmp(k.helloBoot, k.pushBoot) && ms() - k.seen < 1200000) ? k.hello : "";
    xSemaphoreGive(stateMx);
    if (!h.empty()) { httpd_resp_set_type(r, "application/json"); httpd_resp_set_hdr(r, "Cache-Control", "no-store"); return httpd_resp_send(r, h.data(), h.size()); }
  }
  std::string ans;
  int st = ask(c, type, body, ans, type == 'A' || type == 'P' ? 4000 : 2500);
  httpd_resp_set_status(r, reason(st));
  if (!st) return httpd_resp_sendstr(r, "{\"err\":\"the controller did not answer through the hub\"}");
  httpd_resp_set_type(r, st == 200 && type == 'X' ? "application/octet-stream" : "application/json");
  httpd_resp_set_hdr(r, "Cache-Control", "no-store");
  return httpd_resp_send(r, ans.data(), ans.size());
}
// What the hub knows, for whoever is looking (no keys, no network key).
// The Thread signal of an attached controller, from the hub's list of attached devices (its link-local address is
// fe80:: + its Thread address with the local bit flipped). rssi 127: not attached right now.
static void childSignal(const Ctrl &k, int &rssi, int &lqi) {
  rssi = 127; lqi = 0;
  if (!k.addrOk) return;
  const uint8_t *a = (const uint8_t *)&k.addr.sin6_addr;
  uint8_t ext[8];
  memcpy(ext, a + 8, 8);
  ext[0] ^= 0x02;
  esp_openthread_lock_acquire(portMAX_DELAY);
  otInstance *ot = esp_openthread_get_instance();
  otChildInfo ci;
  for (uint16_t i = 0; i < otThreadGetMaxAllowedChildren(ot); i++)
    if (otThreadGetChildInfoByIndex(ot, i, &ci) == OT_ERROR_NONE && !memcmp(ci.mExtAddress.m8, ext, 8)) { rssi = ci.mAverageRssi; lqi = ci.mLinkQualityIn; }
  esp_openthread_lock_release();
}
static void announceHub();
// ---- what the hub tells its people (inside the secured channel; the public /hub only says "a Tilt Hub, owned or not")
static std::string infoJson() {
  wifi_ap_record_t ap = {};
  int wifiRssi = esp_wifi_sta_get_ap_info(&ap) == ESP_OK ? ap.rssi : 0;
  esp_openthread_lock_acquire(portMAX_DELAY);
  int channel = otLinkGetChannel(esp_openthread_get_instance());
  esp_openthread_lock_release();
  std::string j = "{\"ok\":1,\"hub\":\"tilt\",\"fw\":\"" + std::string(esp_app_get_description()->version) + "\",\"up\":" + std::to_string(ms() / 1000) +
                  ",\"ip\":\"" + hubIp() + "\",\"wifi\":" + std::to_string(wifiRssi) + ",\"ch\":" + std::to_string(channel) + ",\"c\":[";
  xSemaphoreTake(stateMx, portMAX_DELAY);
  bool first = true;
  for (int c = 0; c < MAX_CTRL; c++) {
    if (!ctrls[c].used) continue;
    Ctrl &k = ctrls[c];
    int rssi, lqi;
    childSignal(k, rssi, lqi);
    char nums[200];
    snprintf(nums, sizeof nums, ",\"key\":%d,\"seenS\":%ld,\"pct\":%d,\"low\":%d,\"rssi\":%d,\"lqi\":%d,\"ota\":%d,\"otaPct\":%d,\"ep\":[%d,%d,%d]", k.s.keyState, k.seen ? (long)((ms() - k.seen) / 1000) : -1L,
             k.pct, k.low, rssi, lqi, k.otaSt, k.otaPct, k.s.ep[0], k.s.ep[1], k.s.ep[2]);
    std::string tailj = std::string(nums) + (k.otaErr[0] ? ",\"otaErr\":\"" + std::string(k.otaErr) + "\"" : std::string()) +
                        (k.s.keyState ? ",\"hubCid\":\"" + hexOf(k.s.cid, 8) + "\"" : std::string()) +   // the hub's own key on it (its join request)
                        ",\"own\":" + std::to_string(k.own) + "}";                                            // it has an owner (-1 not known)
    j += std::string(first ? "" : ",") + "{\"id\":\"" + std::string(k.s.id, strnlen(k.s.id, 12)) + "\",\"name\":\"" + std::string(k.name, strnlen(k.name, 32)) +
         "\",\"fw\":\"" + std::string(k.fw, strnlen(k.fw, 23)) + "\"" + tailj;
    first = false;
  }
  xSemaphoreGive(stateMx);
  j += "]," + homesJson() + "," + cloudJson() + ",\"heap\":" + std::to_string(esp_get_free_heap_size()) + ",\"heapMin\":" + std::to_string(esp_get_minimum_free_heap_size()) + ",\"new\":[";
  xSemaphoreTake(newMx, portMAX_DELAY);
  first = true;
  for (auto &n : newOnes) {
    if (!n.seen || ms() - n.seen > 300000) continue;
    char line[100];
    snprintf(line, sizeof line, "%s{\"ble\":\"%02x:%02x:%02x:%02x:%02x:%02x\",\"rssi\":%d,\"ageS\":%lu}", first ? "" : ",", n.addr[5], n.addr[4], n.addr[3], n.addr[2], n.addr[1], n.addr[0],
             n.rssi, (unsigned long)((ms() - n.seen) / 1000));
    j += line;
    first = false;
  }
  xSemaphoreGive(newMx);
  return j + "]}";
}
static std::string backupsJson() {
  std::string j = "{\"ok\":1,\"b\":[";
  bool first = true;
  for (int i = 0; i < MAX_BACKUPS; i++) {
    char key[16]; snprintf(key, sizeof key, "bm%d", i);
    BackupMeta m; size_t n = sizeof m;
    if (nvs_get_blob(nv, key, &m, &n) != ESP_OK || n != sizeof m) continue;
    m.name[32] = 0;
    for (char *p = m.name; *p; p++) if (*p == '"' || *p == '\\') *p = '\'';
    j += std::string(first ? "" : ",") + "{\"id\":\"" + m.id + "\",\"name\":\"" + m.name + "\",\"when\":" + std::to_string(m.when) + "}";
    first = false;
  }
  return j + "]}";
}
static std::string backupJson(const char *id) {
  int i = backupSlot(id, false);
  if (i < 0) return "{\"ok\":0,\"err\":\"no backup of that controller\"}";
  char key[16]; snprintf(key, sizeof key, "bk%d", i);
  static uint8_t blob[2048];
  size_t n = sizeof blob;
  if (nvs_get_blob(nv, key, blob, &n) != ESP_OK) return "{\"ok\":0,\"err\":\"no backup\"}";
  return "{\"ok\":1,\"d\":\"" + hexOf(blob, n) + "\"}";
}
// A new controller takes the place of an old one: its Apple Home tiles move over (Home keeps the same blinds, rooms
// and automations). Only for a controller the hub met in the last 15 minutes.
static std::string replaceJson(const char *o, const char *n2) {
  xSemaphoreTake(stateMx, portMAX_DELAY);
  int a = findCtrl(o), b = findCtrl(n2);
  const char *why = a < 0 || b < 0 || a == b ? "unknown controller" : !ctrls[b].firstSeen || ms() - ctrls[b].firstSeen > 900000 ? "only just after setup" : nullptr;
  if (!why) {
    for (int p = 0; p < PORTS; p++) {
      if (ctrls[b].s.ep[p]) { endpoint_t *e = endpoint::get(gNode, ctrls[b].s.ep[p]); if (e) endpoint::destroy(gNode, e); }
      ctrls[b].s.ep[p] = ctrls[a].s.ep[p]; ctrls[b].tileLift[p] = ctrls[b].tileOp[p] = -1; ctrls[b].tileLabel[p][0] = 0;
    }
    ctrls[b].s.sep = ctrls[a].s.sep;
    memset(&ctrls[a].s, 0, sizeof ctrls[a].s);
    ctrls[a].used = false; ctrls[a].addrOk = false;
    saveCtrls();
    ESP_LOGI(TAG, "%s replaces %s (Home tiles moved)", n2, o);
  }
  xSemaphoreGive(stateMx);
  if (why) return std::string("{\"ok\":0,\"err\":\"") + why + "\"}";
  if (matterUp) chip::DeviceLayer::PlatformMgr().ScheduleWork(applyStatus, (intptr_t)b);
  return "{\"ok\":1}";
}
static std::string netJson() {
  esp_openthread_lock_acquire(portMAX_DELAY);
  otOperationalDatasetTlvs tlv;
  bool ok = otDatasetGetActiveTlvs(esp_openthread_get_instance(), &tlv) == OT_ERROR_NONE;
  esp_openthread_lock_release();
  if (!ok) return "{\"ok\":0,\"err\":\"no Thread network\"}";
  return "{\"ok\":1,\"ds\":\"" + hexOf(tlv.mTlvs, tlv.mLength) + "\"}";
}

// ---- the hub's people: the same scheme as a controller's (blinds_matter/main/sec.h), so the app pairs with it the
// same way (its address "<hub>/hub"). The first phone is the owner; others ask to join and an owner lets them in.
// Owners can add controllers (the network), add the hub to Apple Home (its code), use backups and invite people.
struct HubKey { uint8_t used, role; uint8_t id[8]; uint8_t key[32]; char name[20]; };   // used 1 in, 2 asked, 3 first owner not yet proven; role 1 owner
static HubKey hkeys[8];
// The first owner (a new hub, or after its people were reset) must know the setup code on the hub's label: it is
// mixed into the key, so a phone with the wrong code makes a key the hub does not share, and its first command fails.
// Until then the place is held for a minute; five wrong codes close connecting for five minutes.
static uint32_t claimAt[8], askAt[8], pinLockUntil = 0;
static int pinFails = 0;
static uint64_t hlast[8];
static uint8_t hboot[4];
static SemaphoreHandle_t keyMx;
static void keysSave() { nvs_set_blob(nv, "hkeys", hkeys, sizeof hkeys); nvs_commit(nv); }
static void pinBegin();
static void keysBegin() {
  keyMx = xSemaphoreCreateMutex();
  size_t n = sizeof hkeys;
  if (nvs_get_blob(nv, "hkeys", hkeys, &n) != ESP_OK || n != sizeof hkeys) memset(hkeys, 0, sizeof hkeys);
  n = sizeof htopic;
  if (nvs_get_blob(nv, "htopic", htopic, &n) != ESP_OK || n != sizeof htopic) { esp_fill_random(htopic, sizeof htopic); nvs_set_blob(nv, "htopic", htopic, sizeof htopic); nvs_commit(nv); }
  esp_fill_random(hboot, sizeof hboot);
  pinBegin();
}
static char setupPin[12];                        // the code on the label (flash "pin")
static void pinBegin() {
  size_t n = sizeof setupPin;
  if (nvs_get_str(nv, "pin", setupPin, &n) == ESP_OK && setupPin[0]) return;
  strlcpy(setupPin, HUB_SETUP_PIN, sizeof setupPin);
  if (setupPin[0]) { nvs_set_str(nv, "pin", setupPin); nvs_commit(nv); }
  else ESP_LOGE(TAG, "no setup code: build once over USB with main/setup_pin.h");
}
static bool hubOwned() { for (auto &k : hkeys) if (k.used == 1 && k.role == 1) return true; return false; }
// The hub's id: made from its chip's MAC the first time, then kept in its saved data. So a new hub that takes over an
// old one's saved data (copied from the old chip) is the same hub to the app. A factory reset forgets it too.
static std::string hubIdKept;
static std::string hubId() {
  if (!hubIdKept.empty()) return hubIdKept;      // set once at start (app_main), before any other task asks
  char b[24] = {0};
  size_t n = sizeof b;
  if (nvs_get_str(nv, "hubid", b, &n) == ESP_OK && b[0]) return hubIdKept = b;
  uint8_t m[6];
  esp_read_mac(m, ESP_MAC_WIFI_STA);
  hubIdKept = "hub" + hexOf(m, 6);
  nvs_set_str(nv, "hubid", hubIdKept.c_str());
  nvs_commit(nv);
  return hubIdKept;
}
static std::string askCode(const HubKey &k) {
  uint8_t h[32]; char c[6];
  mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), k.key, 32, (const uint8_t *)"code", 4, h);
  snprintf(c, sizeof c, "%04u", (unsigned)(((h[0] << 8) | h[1]) % 10000));
  return c;
}
static std::string jsonStr(const std::string &j, const char *key) {
  cJSON *o = cJSON_Parse(j.c_str());
  const char *v = o ? cJSON_GetStringValue(cJSON_GetObjectItem(o, key)) : nullptr;
  std::string r = v ? v : "";
  if (o) cJSON_Delete(o);
  return r;
}
static void cleanName(char *out, size_t n, const std::string &in) {
  size_t k = 0;
  for (char ch : in) if (k + 1 < n && (unsigned char)ch >= 32 && ch != '"' && ch != '\\') out[k++] = ch;
  out[k] = 0;
}
// pair (first phone, becomes the owner) or ask (later phones; waits for an owner)
static int pairDo(const std::string &b, std::string &out, bool ask) {
  std::string pubB64 = jsonStr(b, "pub");
  uint8_t cpub[65];
  size_t n = 0;
  if (mbedtls_base64_decode(cpub, sizeof cpub, &n, (const uint8_t *)pubB64.c_str(), pubB64.length()) != 0 || n != 65) { out = "{\"err\":\"bad key\"}"; return 400; }
  bool first = !hubOwned();
  if (ask && first) { out = "{\"err\":\"this hub has no owner yet: connect to it\"}"; return 403; }
  if (!ask && !first) { out = "{\"err\":\"this hub has an owner. Ask to join from the app.\"}"; return 403; }
  if (!ask) {
    if (pinLockUntil && (int32_t)(ms() - pinLockUntil) < 0) { out = "{\"err\":\"too many wrong codes: try again in a few minutes\"}"; return 429; }
    xSemaphoreTake(keyMx, portMAX_DELAY);
    bool busy = false;
    for (int i = 0; i < 8; i++) if (hkeys[i].used == 3) { if (ms() - claimAt[i] < 60000) busy = true; else memset(&hkeys[i], 0, sizeof hkeys[i]); }
    xSemaphoreGive(keyMx);
    if (busy) { out = "{\"err\":\"someone else is connecting to this hub: try again in a minute\"}"; return 409; }
  }
  static uint32_t lastAsk = 0;
  if (ask && lastAsk && ms() - lastAsk < 10000) { out = "{\"err\":\"try again in a few seconds\"}"; return 429; }
  if (ask) lastAsk = ms();
  mbedtls_ecp_group grp; mbedtls_mpi d, z; mbedtls_ecp_point Q, Qp;
  mbedtls_ecp_group_init(&grp); mbedtls_mpi_init(&d); mbedtls_mpi_init(&z); mbedtls_ecp_point_init(&Q); mbedtls_ecp_point_init(&Qp);
  uint8_t dpub[65], shared[32], okm[32], okm0[32], info[9 + 130];   // okm0: the same without the setup code (for the check)
  size_t dn = 0;
  bool ok = mbedtls_ecp_group_load(&grp, MBEDTLS_ECP_DP_SECP256R1) == 0 && mbedtls_ecdh_gen_public(&grp, &d, &Q, rng, nullptr) == 0 &&
            mbedtls_ecp_point_read_binary(&grp, &Qp, cpub, 65) == 0 && mbedtls_ecp_check_pubkey(&grp, &Qp) == 0 &&
            mbedtls_ecdh_compute_shared(&grp, &z, &Qp, &d, rng, nullptr) == 0 && mbedtls_mpi_write_binary(&z, shared, 32) == 0 &&
            mbedtls_ecp_point_write_binary(&grp, &Q, MBEDTLS_ECP_PF_UNCOMPRESSED, &dn, dpub, sizeof dpub) == 0 && dn == 65;
  if (ok) {
    memcpy(info, "blinds-v1", 9); memcpy(info + 9, cpub, 65); memcpy(info + 74, dpub, 65);
    // The first owner's key also takes the setup code (as the HKDF salt): the phone must know it.
    const char *salt = first ? setupPin : "";
    ok = mbedtls_hkdf(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), (const uint8_t *)salt, strlen(salt), shared, 32, info, sizeof info, okm, 32) == 0 &&
         mbedtls_hkdf(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), nullptr, 0, shared, 32, info, sizeof info, okm0, 32) == 0;
  }
  mbedtls_ecp_group_free(&grp); mbedtls_mpi_free(&d); mbedtls_mpi_free(&z); mbedtls_ecp_point_free(&Q); mbedtls_ecp_point_free(&Qp);
  if (!ok) { out = "{\"err\":\"key exchange failed\"}"; return 400; }
  xSemaphoreTake(keyMx, portMAX_DELAY);
  int slot = -1, waiting = 0;
  for (auto &k : hkeys) if (k.used == 2) waiting++;
  if (ask && waiting >= 2) {                     // at most two waiting: a new ask takes the place of one older than 10 minutes
    for (int i = 0; i < 8; i++) if (hkeys[i].used == 2 && (!askAt[i] || ms() - askAt[i] > 600000)) { slot = i; break; }
    if (slot < 0) { xSemaphoreGive(keyMx); out = "{\"err\":\"two requests are waiting already. Try again later.\"}"; return 429; }
  }
  else for (int i = 0; i < 8; i++) if (!hkeys[i].used) { slot = i; break; }
  if (slot < 0) { xSemaphoreGive(keyMx); out = "{\"err\":\"no room for another phone\"}"; return 403; }
  HubKey &k = hkeys[slot];
  memset(&k, 0, sizeof k);
  k.used = ask ? 2 : 3; k.role = first ? 1 : 0;
  askAt[slot] = ask ? (ms() ? ms() : 1) : 0;
  claimAt[slot] = ask ? 0 : ms();
  esp_fill_random(k.id, 8);
  memcpy(k.key, okm, 32);
  cleanName(k.name, sizeof k.name, jsonStr(b, "name"));
  if (!k.name[0]) strlcpy(k.name, "iPhone", sizeof k.name);
  hlast[slot] = 0;
  keysSave();
  if (ask) ESP_LOGI(TAG, "%s asked to join the hub", k.name); else ESP_LOGI(TAG, "%s is connecting (owner, once its code is right)", k.name);
  uint8_t chk[32], pb[100];
  mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), okm0, 32, (const uint8_t *)"confirm", 7, chk);   // never from the code
  size_t pn = 0;
  mbedtls_base64_encode(pb, sizeof pb, &pn, dpub, 65);
  out = std::string("{\"pub\":\"") + std::string((char *)pb, pn) + "\",\"cid\":\"" + hexOf(k.id, 8) + "\",\"check\":\"" + hexOf(chk, 8) + "\",\"owner\":" + (first ? "1" : "0") +
        ",\"wait\":" + (ask ? "1" : "0") + ",\"topic\":\"" + hexOf(htopic, 16) + "\",\"code\":\"" + (ask ? askCode(k) : std::string()) + "\"}";
  xSemaphoreGive(keyMx);
  return 200;
}
static std::string qv(const std::string &q, const char *key) {
  char v[300] = "";
  return httpd_query_key_value(q.c_str(), key, v, sizeof v) == ESP_OK ? std::string(v) : std::string();
}
// One command from a phone that is in. Owner-only unless said otherwise.
static std::string hubCommand(int slot, const std::string &cmd) {
  size_t qi = cmd.find('?');
  std::string path = cmd.substr(0, qi), q = qi == std::string::npos ? "" : cmd.substr(qi + 1);
  bool owner = hkeys[slot].role == 1;
  if (path == "/api/info") return infoJson();
  if (path == "/api/keys") {                     // the hub's people (as a controller lists its phones)
    xSemaphoreTake(keyMx, portMAX_DELAY);
    std::string j = "{\"ok\":1,\"keys\":[";
    bool first = true;
    for (int i = 0; i < 8; i++) {
      HubKey &k = hkeys[i];
      if (!k.used) continue;
      j += std::string(first ? "" : ",") + "{\"cid\":\"" + hexOf(k.id, 8) + "\",\"name\":\"" + k.name + "\",\"owner\":" + (k.role ? "1" : "0") + ",\"me\":" + (i == slot ? "1" : "0") +
           ",\"wait\":" + (k.used == 2 ? "1" : "0") + ",\"code\":\"" + (k.used == 2 && owner ? askCode(k) : std::string()) + "\"}";   // the code: owners only
      first = false;
    }
    xSemaphoreGive(keyMx);
    return j + "]}";
  }
  if (path == "/api/leave") {                    // this phone leaves the hub (everywhere, not just on the phone)
    xSemaphoreTake(keyMx, portMAX_DELAY);
    int owners = 0, others = 0;
    for (int i = 0; i < 8; i++) if (i != slot && hkeys[i].used) { others++; if (hkeys[i].used == 1 && hkeys[i].role == 1) owners++; }
    if (owner && owners == 0 && others > 0) { xSemaphoreGive(keyMx); return "{\"ok\":0,\"err\":\"you are the hub's only owner: make someone else an owner first, or reset its people\"}"; }
    ESP_LOGI(TAG, "%s left the hub", hkeys[slot].name);
    memset(&hkeys[slot], 0, sizeof hkeys[slot]);
    keysSave();
    xSemaphoreGive(keyMx);
    announceHub();                               // no owner left: it says so (a new person can connect)
    return "{\"ok\":1}";
  }
  if (!owner) return "{\"ok\":0,\"err\":\"only the hub's owner can do that\"}";
  if (path == "/api/light") {                    // test: which light is which on this board (lights.h). For a minute.
    lightTestUntil = (ms() + 60000) | 1;
    std::string l = qv(q, "l");
    if (l == "15") { gpio_set_level(GPIO_NUM_15, qv(q, "v") == "1" ? 1 : 0); return "{\"ok\":1}"; }
    if (l == "8") { rgbSet(atoi(qv(q, "r").c_str()), atoi(qv(q, "g").c_str()), atoi(qv(q, "b").c_str())); return "{\"ok\":1}"; }
    return "{\"ok\":0,\"err\":\"l=15&v=0|1 or l=8&r=&g=&b=\"}";
  }
  if (path == "/api/resetpeople") {              // forget every phone: the next one to connect becomes the owner.
    xSemaphoreTake(keyMx, portMAX_DELAY);        // (Its controllers, their Home tiles and Apple Home stay.)
    memset(hkeys, 0, sizeof hkeys);
    keysSave();
    xSemaphoreGive(keyMx);
    ESP_LOGW(TAG, "people reset: waiting for a new owner");
    announceHub();
    return "{\"ok\":1}";
  }
  if (path == "/api/approve" || path == "/api/revoke" || path == "/api/makeowner") {
    uint8_t id[8];
    if (!unhex(qv(q, "cid").c_str(), id, 8)) return "{\"ok\":0,\"err\":\"bad id\"}";
    xSemaphoreTake(keyMx, portMAX_DELAY);
    std::string r = "{\"ok\":0,\"err\":\"no such phone\"}";
    for (int i = 0; i < 8; i++) {
      HubKey &k = hkeys[i];
      if (!k.used || memcmp(k.id, id, 8)) continue;
      HubKey before = k;                         // put back if the change would leave the hub with no owner
      if (path == "/api/approve") {
        if (k.used != 2) break;
        if (qv(q, "ok") == "1") { k.used = 1; k.role = qv(q, "owner") == "1"; hlast[i] = 0; ESP_LOGI(TAG, "%s let into the hub", k.name); }
        else memset(&k, 0, sizeof k);
      } else if (path == "/api/makeowner") k.role = qv(q, "on") == "1";
      else { if (i == slot) { r = "{\"ok\":0,\"err\":\"you cannot remove yourself\"}"; break; } memset(&k, 0, sizeof k); }
      if (!hubOwned()) { k = before; r = "{\"ok\":0,\"err\":\"the hub needs an owner: make someone else an owner first\"}"; break; }
      keysSave();
      r = "{\"ok\":1}";
      break;
    }
    xSemaphoreGive(keyMx);
    return r;
  }
  if (path == "/api/net") return netJson();
  if (path == "/api/testalert") { alertRaise(htopic, "test", 9, "Tilt Hub"); return "{\"ok\":1}"; }   // a push to the hub's owners, to try the path
  if (path == "/api/hubupdate") { hubUpdUntil = (ms() + 300000) | 1; return "{\"ok\":1}"; }   // one hub update, 5 minutes
  if (path == "/api/upload") {                   // allow one firmware upload for this controller, for 5 minutes
    xSemaphoreTake(stateMx, portMAX_DELAY);
    int c = findCtrl(qv(q, "id").c_str());
    if (c >= 0) uploadUntil[c] = (ms() + 300000) | 1;
    xSemaphoreGive(stateMx);
    return c >= 0 ? "{\"ok\":1}" : "{\"ok\":0,\"err\":\"no such controller\"}";
  }
  if (path == "/api/homecode" && matterUp) {      // open Apple Home's pairing now (Apple's add screen comes next)
    // Also when the hub still counts a home: the owner asked, and that home may be gone (removed in its own app
    // without the hub hearing of it). Matter allows a hub in several homes. The automatic window (above) stays for a
    // hub in no home only.
    homeWindowUntil = (ms() + 900000) | 1;
    chip::DeviceLayer::PlatformMgr().ScheduleWork([](intptr_t) {
      auto &mgr = chip::Server::GetInstance().GetCommissioningWindowManager();
      // A window open for an Alexa code takes only that code: swap it for one that takes the hub's own code.
      if (mgr.IsCommissioningWindowOpen() && shareUntil && (int32_t)(shareUntil - ms()) > 0) { mgr.CloseCommissioningWindow(); shareUntil = 0; }
      if (!mgr.IsCommissioningWindowOpen())
        mgr.OpenBasicCommissioningWindow(chip::System::Clock::Seconds16(900), chip::CommissioningWindowAdvertisement::kAllSupported);
    }, 0);
  }
  if (path == "/api/homecode") return "{\"ok\":1,\"code\":\"" + homeManual + "\",\"qr\":\"" + homeQr + "\"," + homesJson() + "}";
  if (path == "/api/sharecode") return shareCodeJson();   // a one-time code for a second home app (Alexa)
  if (path == "/api/backups") return backupsJson();
  if (path == "/api/backup") return backupJson(qv(q, "id").c_str());
  if (path == "/api/replace") return replaceJson(qv(q, "old").c_str(), qv(q, "new").c_str());
  return "{\"ok\":0,\"err\":\"unknown command\"}";
}
// POST /hub/x: id (8) | nonce (12: boot 4 | counter 8) | ciphertext | tag (16); the answer: nonce | ciphertext | tag.
static int secDo(const std::string &b, std::string &resp) {
  if (b.size() < 8 + 12 + 16 + 1) { resp = "{\"err\":\"short\"}"; return 400; }
  const uint8_t *p = (const uint8_t *)b.data(), *nonce = p + 8, *ct = p + 20;
  size_t n = b.size() - 36;
  uint64_t ctr = 0;
  for (int i = 4; i < 12; i++) ctr = (ctr << 8) | nonce[i];
  uint8_t aad[17], key[32];
  memcpy(aad, "blinds-v1", 9); memcpy(aad + 9, p, 8);
  std::string cmd(n, 0);
  xSemaphoreTake(keyMx, portMAX_DELAY);
  int slot = -1;
  for (int i = 0; i < 8; i++) if (hkeys[i].used && !memcmp(hkeys[i].id, p, 8)) slot = i;
  if (slot < 0) { xSemaphoreGive(keyMx); resp = "{\"err\":\"not paired\"}"; return 401; }
  if (memcmp(nonce, hboot, 4) || ctr <= hlast[slot]) { xSemaphoreGive(keyMx); resp = "{\"err\":\"stale\",\"boot\":\"" + hexOf(hboot, 4) + "\"}"; return 409; }
  memcpy(key, hkeys[slot].key, 32);
  if (!gcm(false, key, nonce, aad, 17, ct, n, (uint8_t *)&cmd[0], (uint8_t *)(ct + n))) {
    bool claim = hkeys[slot].used == 3;
    if (claim) {                                 // a first owner with the wrong setup code: the place goes
      memset(&hkeys[slot], 0, sizeof hkeys[slot]);
      if (++pinFails >= 5) { pinFails = 0; pinLockUntil = (ms() + 300000) | 1; ESP_LOGW(TAG, "five wrong setup codes: connecting closed for 5 minutes"); }
    }
    xSemaphoreGive(keyMx);
    resp = claim ? "{\"err\":\"wrong setup code\"}" : "{\"err\":\"bad key\"}";
    return 401;
  }
  hlast[slot] = ctr;
  if (hkeys[slot].used == 3) {                   // the right code: this phone is the owner now
    hkeys[slot].used = 1; pinFails = 0;
    keysSave();
    ESP_LOGI(TAG, "%s connected (owner)", hkeys[slot].name);
  }
  bool waiting = hkeys[slot].used != 1;
  if (waiting && cmd == "/api/leave") { memset(&hkeys[slot], 0, sizeof hkeys[slot]); keysSave(); xSemaphoreGive(keyMx); resp = "{\"err\":\"not paired\"}"; return 401; }
  xSemaphoreGive(keyMx);
  if (waiting) { resp = "{\"err\":\"waiting\"}"; return 403; }
  std::string out = hubCommand(slot, cmd);
  resp.assign(12 + out.size() + 16, 0);
  uint8_t *o = (uint8_t *)&resp[0], aad2[30];
  esp_fill_random(o, 12);
  memcpy(aad2, "blinds-v1r", 10); memcpy(aad2 + 10, p, 8); memcpy(aad2 + 18, nonce, 12);
  gcm(true, key, o, aad2, 30, (const uint8_t *)out.data(), out.size(), o + 12, o + 12 + out.size());
  return 200;
}
static std::string helloJson() {
  return "{\"id\":\"" + hubId() + "\",\"name\":\"Tilt Hub\",\"fw\":\"" + std::string(esp_app_get_description()->version) + "\",\"boot\":\"" + hexOf(hboot, 4) +
         "\",\"owned\":" + (hubOwned() ? "1" : "0") + ",\"kind\":\"hub\"}";
}
static esp_err_t sendStatus(httpd_req_t *r, int st, const std::string &body, bool binary = false) {
  httpd_resp_set_status(r, reason(st));
  httpd_resp_set_type(r, binary ? "application/octet-stream" : "application/json");
  httpd_resp_set_hdr(r, "Cache-Control", "no-store");
  return httpd_resp_send(r, body.data(), body.size());
}
static bool readBody(httpd_req_t *r, std::string &b, size_t max) {
  if (r->content_len > max) return false;
  b.resize(r->content_len);
  size_t got = 0;
  while (got < b.size()) { int n = httpd_req_recv(r, &b[got], b.size() - got); if (n == HTTPD_SOCK_ERR_TIMEOUT) continue; if (n <= 0) return false; got += n; }
  return true;
}
static esp_err_t hHello(httpd_req_t *r) { return sendStatus(r, 200, helloJson()); }
static esp_err_t hPair(httpd_req_t *r) { std::string b, out; if (!readBody(r, b, 600)) return sendStatus(r, 400, "{\"err\":\"bad request\"}"); return sendStatus(r, pairDo(b, out, false), out); }
static esp_err_t hAsk(httpd_req_t *r) { std::string b, out; if (!readBody(r, b, 600)) return sendStatus(r, 400, "{\"err\":\"bad request\"}"); return sendStatus(r, pairDo(b, out, true), out); }
static esp_err_t hSecure(httpd_req_t *r) { std::string b, out; if (!readBody(r, b, 2200)) return sendStatus(r, 400, "{\"err\":\"bad request\"}"); int st = secDo(b, out); return sendStatus(r, st, out, st == 200); }
// GET /hub: public, so a phone can tell a new hub from one that has an owner. Nothing more.
static esp_err_t hInfo(httpd_req_t *r) { return sendStatus(r, 200, "{\"hub\":\"tilt\",\"id\":\"" + hubId() + "\",\"owned\":" + (hubOwned() ? "1" : "0") + "}"); }
static void httpBegin() {
  httpd_config_t hc = HTTPD_DEFAULT_CONFIG();
  hc.uri_match_fn = httpd_uri_match_wildcard;
  hc.stack_size = 10240;
  hc.lru_purge_enable = true;
  hc.max_open_sockets = 5;
  hc.max_uri_handlers = 12;
  hc.recv_wait_timeout = 30;                     // a firmware file can be slow to arrive
  httpd_handle_t srv = nullptr;
  if (httpd_start(&srv, &hc) != ESP_OK) { ESP_LOGE(TAG, "web server did not start"); return; }
  httpd_uri_t u[] = {{"/c/*", HTTP_GET, hRelay, nullptr}, {"/c/*", HTTP_POST, hRelay, nullptr}, {"/hub", HTTP_GET, hInfo, nullptr},
                     {"/hub/x/hello", HTTP_GET, hHello, nullptr}, {"/hub/x/pair", HTTP_POST, hPair, nullptr}, {"/hub/x/ask", HTTP_POST, hAsk, nullptr},
                     {"/hub/x", HTTP_POST, hSecure, nullptr}, {"/hub/api/update", HTTP_POST, hHubUpdate, nullptr}};
  for (auto &x : u) httpd_register_uri_handler(srv, &x);
}

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

// ---- the hub's own Apple Home setup code: made at random on the first start and kept (never the public test code)
static HomeCode homeCode;
struct HomeCodeProvider : chip::DeviceLayer::CommissionableDataProvider {
  CHIP_ERROR GetSetupDiscriminator(uint16_t &d) override { d = homeCode.disc; return CHIP_NO_ERROR; }
  CHIP_ERROR SetSetupDiscriminator(uint16_t) override { return CHIP_ERROR_NOT_IMPLEMENTED; }
  CHIP_ERROR GetSpake2pIterationCount(uint32_t &n) override { n = homeCode.iter; return CHIP_NO_ERROR; }
  CHIP_ERROR GetSpake2pSalt(chip::MutableByteSpan &b) override { return chip::CopySpanToMutableSpan(chip::ByteSpan(homeCode.salt), b); }
  CHIP_ERROR GetSpake2pVerifier(chip::MutableByteSpan &b, size_t &n) override { n = sizeof homeCode.verifier; return chip::CopySpanToMutableSpan(chip::ByteSpan(homeCode.verifier), b); }
  CHIP_ERROR GetSetupPasscode(uint32_t &p) override { p = homeCode.pin; return CHIP_NO_ERROR; }
  CHIP_ERROR SetSetupPasscode(uint32_t) override { return CHIP_ERROR_NOT_IMPLEMENTED; }
};
static HomeCodeProvider homeCodeProvider;
// The maker and product names Apple Home and Alexa show (Basic Information): Tilt's own, not the SDK's "TEST_VENDOR".
// Everything else (serial, dates, versions) as the SDK keeps it.
struct TiltInfo : chip::DeviceLayer::Internal::GenericDeviceInstanceInfoProvider<chip::DeviceLayer::Internal::ESP32Config> {
  TiltInfo() : GenericDeviceInstanceInfoProvider(chip::DeviceLayer::ConfigurationManagerImpl::GetDefaultInstance()) {}
  static CHIP_ERROR put(const char *s, char *buf, size_t n) { if (strlen(s) >= n) return CHIP_ERROR_BUFFER_TOO_SMALL; strcpy(buf, s); return CHIP_NO_ERROR; }
  CHIP_ERROR GetVendorName(char *buf, size_t n) override { return put("Tilt", buf, n); }
  CHIP_ERROR GetProductName(char *buf, size_t n) override { return put("Tilt Hub", buf, n); }
};
static TiltInfo tiltInfo;
static void homeCodeBegin() {                      // before Bluetooth and Matter start (the random source needs the radio off)
  size_t n = sizeof homeCode;
  if (nvs_get_blob(nv, "homecode", &homeCode, &n) != ESP_OK || !homeCodeKeep(homeCode, n)) {
    HomeCode c = {HOME_CODE_MAGIC, 0, 1000, 0, {}, {}};
    bootloader_random_enable();
    do esp_fill_random(&c.pin, sizeof c.pin); while (!setupPinValid(c.pin %= 100000000));
    esp_fill_random(&c.disc, sizeof c.disc);
    c.disc &= 0xFFF;
    esp_fill_random(c.salt, sizeof c.salt);
    bootloader_random_disable();
    chip::Crypto::Spake2pVerifier v;
    chip::MutableByteSpan out(c.verifier);
    if (v.Generate(c.iter, chip::ByteSpan(c.salt), c.pin) == CHIP_NO_ERROR && v.Serialize(out) == CHIP_NO_ERROR) {
      homeCode = c;
      nvs_set_blob(nv, "homecode", &homeCode, sizeof homeCode);
      nvs_commit(nv);
    }
  }
  esp_matter::set_custom_commissionable_data_provider(&homeCodeProvider);
  esp_matter::set_custom_device_instance_info_provider(&tiltInfo);
  chip::PayloadContents p;
  p.vendorID = CONFIG_DEVICE_VENDOR_ID;
  p.productID = CONFIG_DEVICE_PRODUCT_ID;
  p.rendezvousInformation.Emplace(chip::RendezvousInformationFlag::kBLE);
  p.discriminator.SetLongValue(homeCode.disc);
  p.setUpPINCode = homeCode.pin;
  char manual[chip::kManualSetupLongCodeCharLength + 1], qr[chip::QRCodeBasicSetupPayloadGenerator::kMaxQRCodeBase38RepresentationLength + 1];
  chip::MutableCharSpan m(manual), q(qr);
  if (chip::ManualSetupPayloadGenerator(p).payloadDecimalStringRepresentation(m) == CHIP_NO_ERROR &&
      chip::QRCodeBasicSetupPayloadGenerator(p).payloadBase38Representation(q) == CHIP_NO_ERROR)
  {
    homeManual = manualCodeDashed(std::string(m.data(), m.size()));
    homeQr.assign(q.data(), q.size());
    printf("HUB SETUP CODE %s  QR %s\n", homeManual.c_str(), homeQr.c_str());   // USB log
  }
}

// ---- a one-time code for another home app (Alexa, Google Home, SmartThings), issue #18
// Matter lets a device be in several homes. A hub already in one gets the next by an "enhanced" pairing window: a
// fresh random code, good for 15 minutes and one home, over the home Wi-Fi only (Apple Home's "Turn On Pairing Mode"
// does the same). Every Matter home app must take this kind of code. A hub in no home yet gives its own code, opened
// as for Apple Home (Bluetooth too, so the app can give it Wi-Fi). Asking again while a code is still good gives
// the same code, so a second tap does not break the first.
static std::string shareCodeJson() {
  if (!matterUp) return "{\"ok\":0,\"err\":\"the hub's Matter is not running yet: try again in a minute\"}";
  chip::DeviceLayer::PlatformMgr().LockChipStack();
  auto &srv = chip::Server::GetInstance();
  auto &mgr = srv.GetCommissioningWindowManager();
  bool homed = srv.GetFabricTable().FabricCount() > 0;
  bool same = homed && shareUntil && (int32_t)(shareUntil - ms()) > 60000 && mgr.IsCommissioningWindowOpen();
  chip::DeviceLayer::PlatformMgr().UnlockChipStack();
  if (!homed) {                                  // the first home: the hub's own code (like /api/homecode)
    homeWindowUntil = (ms() + 900000) | 1;
    chip::DeviceLayer::PlatformMgr().ScheduleWork([](intptr_t) {
      auto &m = chip::Server::GetInstance().GetCommissioningWindowManager();
      if (!m.IsCommissioningWindowOpen()) m.OpenBasicCommissioningWindow(chip::System::Clock::Seconds16(900), chip::CommissioningWindowAdvertisement::kAllSupported);
    }, 0);
    return "{\"ok\":1,\"code\":\"" + homeManual + "\",\"qr\":\"" + homeQr + "\",\"mins\":15,\"first\":1," + homesJson() + "}";
  }
  if (!same) {
    uint32_t pin;
    uint16_t disc;
    uint8_t salt[32];
    do esp_fill_random(&pin, sizeof pin); while (!setupPinValid(pin %= 100000000));   // the radio is on: true random
    esp_fill_random(&disc, sizeof disc);
    disc &= 0xFFF;
    esp_fill_random(salt, sizeof salt);
    chip::Crypto::Spake2pVerifier v;
    if (v.Generate(1000, chip::ByteSpan(salt), pin) != CHIP_NO_ERROR) return "{\"ok\":0,\"err\":\"could not make a code\"}";
    chip::DeviceLayer::PlatformMgr().LockChipStack();
    chip::FabricIndex fi = chip::kUndefinedFabricIndex;
    chip::VendorId vid = chip::VendorId::Common;
    for (const auto &f : srv.GetFabricTable()) { fi = f.GetFabricIndex(); vid = f.GetVendorId(); break; }   // "opened by": its first home
    mgr.CloseCommissioningWindow();              // a window still open (the start-up one, an older code) goes
    CHIP_ERROR e = mgr.OpenEnhancedCommissioningWindow(chip::System::Clock::Seconds32(900), disc, v, 1000, chip::ByteSpan(salt), fi, vid);
    chip::DeviceLayer::PlatformMgr().UnlockChipStack();
    if (e != CHIP_NO_ERROR) { ESP_LOGE(TAG, "share window: %" CHIP_ERROR_FORMAT, e.Format()); return "{\"ok\":0,\"err\":\"the hub could not open pairing\"}"; }
    chip::PayloadContents p;
    p.vendorID = CONFIG_DEVICE_VENDOR_ID;
    p.productID = CONFIG_DEVICE_PRODUCT_ID;
    p.rendezvousInformation.Emplace(chip::RendezvousInformationFlag::kOnNetwork);
    p.discriminator.SetLongValue(disc);
    p.setUpPINCode = pin;
    char manual[chip::kManualSetupLongCodeCharLength + 1], qr[chip::QRCodeBasicSetupPayloadGenerator::kMaxQRCodeBase38RepresentationLength + 1];
    chip::MutableCharSpan m(manual), q(qr);
    if (chip::ManualSetupPayloadGenerator(p).payloadDecimalStringRepresentation(m) != CHIP_NO_ERROR ||
        chip::QRCodeBasicSetupPayloadGenerator(p).payloadBase38Representation(q) != CHIP_NO_ERROR)
      return "{\"ok\":0,\"err\":\"could not make a code\"}";
    shareManual = manualCodeDashed(std::string(m.data(), m.size()));
    shareQr.assign(q.data(), q.size());
    shareUntil = (ms() + 900000) | 1;
    ESP_LOGI(TAG, "pairing open for another home app for 15 minutes");
  }
  int mins = (int)(((int32_t)(shareUntil - ms())) / 60000);
  return "{\"ok\":1,\"code\":\"" + shareManual + "\",\"qr\":\"" + shareQr + "\",\"mins\":" + std::to_string(mins < 1 ? 1 : mins) + "," + homesJson() + "}";
}

// The hub itself on Bonjour (_tilthub._tcp): its address and whether it has an owner (a new hub says owned=0).
static bool hubOwned();
static std::string hubId();
static void announceHub() {
  std::string ip = hubIp(), id = hubId();
  if (ip == "0.0.0.0") return;
  mdns_txt_item_t t[] = {{"ip", ip.c_str()}, {"id", id.c_str()}, {"owned", hubOwned() ? "1" : "0"}};
  if (mdns_service_txt_set_for_host("Tilt Hub", "_tilthub", "_tcp", nullptr, t, 3) != ESP_OK) mdns_service_add_for_host("Tilt Hub", "_tilthub", "_tcp", nullptr, 80, t, 3);
}
// The homes the hub is in (Matter fabrics), read fresh: `home` is 1 if there is any. Each one with its maker's
// number (Apple's is 4996), the hub's node ID in it, and its label. Apple adds two (the home and the iPhone's iCloud
// Keychain) and leaves the Keychain one when the hub is removed from Home, so `home` alone can't say "in Apple Home":
// the app compares the node IDs with the accessories Apple Home has (HomeSetup.inHome).
static std::string homesJson() {
  if (!matterUp) return std::string("\"homes\":[],\"home\":") + (inHome ? "1" : "0");   // Matter not running: nothing to lock or read
  std::string j = "\"homes\":[";
  int n = 0;
  chip::DeviceLayer::PlatformMgr().LockChipStack();
  for (const auto &f : chip::Server::GetInstance().GetFabricTable()) {
    chip::CharSpan l = f.GetFabricLabel();
    std::string label;
    for (size_t i = 0; i < l.size(); i++) { char c = l.data()[i]; if (c != '"' && c != '\\' && (unsigned char)c >= 32 && (unsigned char)c < 127) label += c; }   // plain ASCII: always good JSON
    char one[128];                               // node: the hub's own ID in that home (Apple Home shows it per accessory)
    snprintf(one, sizeof one, "%s{\"i\":%u,\"vendor\":%u,\"node\":\"%016llX\",\"label\":\"%s\"}", n ? "," : "", (unsigned)f.GetFabricIndex(),
             (unsigned)f.GetVendorId(), (unsigned long long)f.GetNodeId(), label.c_str());
    j += one;
    n++;
  }
  chip::DeviceLayer::PlatformMgr().UnlockChipStack();
  inHome = n > 0;
  return j + "],\"home\":" + (n ? "1" : "0");
}
static void event_cb(const ChipDeviceEvent *ev, intptr_t) {
  if (ev->Type == chip::DeviceLayer::DeviceEventType::kCommissioningComplete) { inHome = true; ESP_LOGI(TAG, "added to a home"); }
  if (ev->Type == chip::DeviceLayer::DeviceEventType::kFabricRemoved) inHome = chip::Server::GetInstance().GetFabricTable().FabricCount() > 0;
  if (ev->Type == chip::DeviceLayer::DeviceEventType::kESPSystemEvent && ev->Platform.ESPSystemEvent.Base == IP_EVENT &&
      ev->Platform.ESPSystemEvent.Id == IP_EVENT_STA_GOT_IP) {
    for (int c = 0; c < MAX_CTRL; c++) ctrls[c].announced = false;
    announceHub();
    for (int c = 0; c < MAX_CTRL; c++) if (ctrls[c].used && ctrls[c].addrOk) announce(c);
    ESP_LOGI(TAG, "on Wi-Fi at %s", hubIp().c_str());
  }
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
    k.mx = xSemaphoreCreateMutex(); k.pct = -1; k.sep = -1; k.own = -1;
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
  xTaskCreate(udpTask, "udp", 6144, nullptr, 6, nullptr);
  xTaskCreate(moveTask, "moves", 6144, nullptr, 5, nullptr);
  xTaskCreate(careTask, "care", 8192, nullptr, 4, nullptr);
  httpBegin();
  rgbBegin();                                    // the color light's pulse channel, once, before anyone uses it
  xTaskCreate(resetTask, "reset", 3072, nullptr, 2, nullptr);
  xTaskCreate(statusTask, "status", 4096, nullptr, 2, nullptr);
  ESP_LOGI(TAG, "Tilt Hub %s started", esp_app_get_description()->version);
}
