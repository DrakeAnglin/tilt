// The link to the Tilt Hub over Thread. The hub is Apple Home's Matter device for these blinds and
// passes the app's secured commands along, so this controller can sleep: it only wakes to check in with the hub.
//
// UDP on port 49100, one datagram each way:
//   hub -> controller   type (1) | seq (2) | payload       H hello, X secured command (sec.h), A ask to join,
//                                                        R recover (people.h), Q recovery progress. (No P: the first
//                                                        owner pairs over Bluetooth only.)
//   controller -> hub   type in lower case | seq | status (3 digits, "200") | answer
//   controller -> hub   '#' | seq | piece (1) | count (1) | part   an answer longer than 1000 bytes (status and answer),
//                                                        in up to 16 pieces; the hub joins them before passing it on
//   controller -> hub   'S' | "00" | status JSON           pushed when something changed, and every 10 minutes
//                                                        (b[].st: stalls since this start, for the hub's alerts)
//   controller -> hub   'L' | "00" | one event log line
//   controller -> hub   'G' | "00"                          leaving (factory reset): the hub stops announcing it
//   hub -> controller   's' | seq | "200" | epoch "." mac   the hub's answer to a push: the time, for the Schedules
//   hub -> controller   'B' | seq | size "." mac            begin a firmware file ('W' pieces, 'E' end follow)
// Proof ("mac"): the hub's own key here (an owner marks it, /api/hubkey) makes a link key both sides know; each message
// from the hub, and each push and goodbye from the controller, carries the first 16 bytes of an HMAC with it (sec.h
// hubMac), over a label, this controller's boot id and the message. Only a message with a good proof (or a command
// sealed with the hub's key) counts as the hub's: anything else on the Thread network is not trusted. Pushes carry a
// count ("\n" N "." mac after the JSON), so an old one cannot be sent again.
// After any message from the hub the controller checks in fast (Matter's active mode, 200 ms) for a few seconds.
// The controller finds the hub with a link-local multicast (the hub is its parent), then uses the hub's own address. Commands are
// sealed end to end with the sender's own key: the hub can pass a phone's command along but cannot read or change it.
//
#pragma once
#include <string>
#include <lwip/sockets.h>
#include <esp_ota_ops.h>
#include <nvs_flash.h>
#include <esp_crc.h>
#include <esp_openthread.h>
#include <esp_openthread_lock.h>
#include <esp_openthread_netif_glue.h>
#include <esp_netif.h>
#include <openthread/dataset.h>
#include <openthread/thread.h>
#include <openthread/ip6.h>
#include <openthread/link.h>
#include <app/server/Server.h>
#include <app/icd/server/ICDNotifier.h>
#include <app/server/CommissioningWindowManager.h>
#include "api.h"
#include "sec.h"
#include "home_view.h"
#include "update.h"                              // otaWindow, fwSignatureOk, otaPending
#include "ota.h"                                 // OtaReceiver: the decisions about a firmware file
#include <esp_delta_ota.h>

const uint16_t HUB_PORT = 49100;
volatile uint32_t hubSeen = 0;                   // millis of the last message from the hub (0 = none since this start)
// Thread to the hub works (a hello from it, or a sealed command through it): enough to keep a new firmware on trial,
// even before this controller knows which key is the hub's (an update does not wait for that).
volatile uint32_t hubLinkSeen = 0;
volatile bool hubWantsStatus = false;
static uint32_t bootN = 0;                       // counts every start (flash): pushes carry it, so an old one is never taken again
static volatile bool hubOtaStallReq = false;     // the blinds task saw an update stall; the hub task stops it
static int hubSock = -1;
// The hub's addresses: written by the hub task and read by the blinds task, so both hold mx for them.
static sockaddr_in6 hubAddr;                     // where the hub last answered from (Thread build)
static bool hubAddrOk = false;
static sockaddr_in6 hubHelloAddr;                // where the hub's last hello came from (not proven: only for sending)
static bool hubHelloOk = false;

// One Thread message carries about 1.2 KB; a longer answer to the hub goes in pieces (tilt_link.h LINK_PIECE, the hub
// joins them).
bool hubOk() { return hubSeen && millis() - hubSeen < 1200000; }   // heard from the hub in the last 20 minutes

static uint32_t backupCrc();
// What the hub needs to show the blinds in Apple Home. Whole numbers, so it only changes when a blind really moves.
std::string hubStatusJson(int pct) {
  std::string j;
  ap(j, "{\"id\":\"%s\",\"name\":%s,\"fw\":\"" FW_VERSION "\",\"boot\":\"%s\",\"bn\":%lu,\"sep\":%d,\"pct\":%d,\"low\":%d,\"chg\":%d,\"closeUp\":%d,\"mv\":%d,\"cv\":%lu,\"own\":%d,\"b\":[", ctrlId().c_str(),
     jq(cfg.name).c_str(), hexOf(bootId, 4).c_str(), (unsigned long)bootN, hkSeparate, pct, battOkToMove() ? 0 : 1, strcmp(chargeState(), "battery") ? 1 : 0, cfg.closeUp, firstMoving(), (unsigned long)backupCrc(), owned() ? 1 : 0);
  for (int i = 0; i < PORTS; i++) {
    BlindReport b = blindNow(i);
    ap(j, "%s{\"n\":%s,\"h\":%d,\"ok\":%d,\"t\":%s,\"g\":%s,\"m\":%d,\"st\":%u}", i ? "," : "", jq(cfg.b[i].name).c_str(), cfg.b[i].hidden, b.movable ? 1 : 0,
       jn(b.tilt, 0).c_str(), jn(b.target, 0).c_str(), b.busy ? 1 : 0, (unsigned)movesStalled[i]);
  }
  j += "]}";
  return j;
}

// ---- the commands (owner; /api/home also for a user, so a hub let in as a user can move the blinds)
// Apple Home through the hub: the move a Matter command makes. lift = percent closed, hundredths.
esp_err_t hHome(httpd_req_t *r) {
  Lock l;
  std::string b = arg(r, "b");
  int one = b == "all" || b.empty() ? -1 : constrain(atoi(b.c_str()), 0, PORTS - 1), lift = argi(r, "lift");
  if (!homeLiftValid(lift)) return fail(r, "bad tilt");
  MoveResult m = moveBlinds(moveAsk(FROM_HOME, one, tiltOfHomeLift(lift, cfg.closeUp)));
  event("Home (hub): %d %% closed (%d blind%s)", lift / 100, m.started, m.started == 1 ? "" : "s");
  return m.started ? ok(r) : fail(r, m.why);
}
// The hub's Thread network (its dataset, hex). Kept in flash; the Thread build joins it at once.
void hubApply();
esp_err_t hHubJoin(httpd_req_t *r) {
  Lock l;
  std::string hex = arg(r, "ds");
  uint8_t tlv[254];
  size_t n = hex.length() / 2;
  if (n < 20 || n > sizeof tlv || !unhex(hex, tlv, n)) return fail(r, "bad network");
  nvs.putBytes("hubds", tlv, n);
  event("Tilt Hub network saved");
  hubApply();
  return ok(r);
}
// ---- settings backup: everything a replacement needs to carry on (names, schedules, marks, place, tuning, switches).
// Layout: "TB1" | sizes (3 x uint16) | settings (the old Wi-Fi fields cleared) | tune | schedule extras | sync par hksep pwm.
// A Tilt Hub keeps a copy (it fetches it when "cv", the checksum in the status push, changes) for the app to restore.
static std::string backupBlob() {
  Settings c = cfg;
  memset(c.ssid, 0, sizeof c.ssid); memset(c.pass, 0, sizeof c.pass);
  uint16_t sz[3] = {sizeof c, sizeof tune, sizeof sx};
  std::string b("TB1", 3);
  b.append((const char *)sz, sizeof sz);
  b.append((const char *)&c, sizeof c);
  b.append((const char *)&tune, sizeof tune);
  b.append((const char *)&sx, sizeof sx);
  uint8_t f[4] = {syncMode, parMode, hkSeparate, pwmSaved};
  b.append((const char *)f, sizeof f);
  return b;
}
static uint32_t backupCrc() { std::string b = backupBlob(); return esp_crc32_le(0, (const uint8_t *)b.data(), b.size()); }
esp_err_t hBackup(httpd_req_t *r) {              // the owner, or the hub (a user): read only
  Lock l;
  std::string b = backupBlob();
  return sendJson(r, "{\"ok\":1,\"cv\":" + std::to_string(esp_crc32_le(0, (const uint8_t *)b.data(), b.size())) + ",\"d\":\"" + hexOf((const uint8_t *)b.data(), b.size()) + "\"}");
}
// Owner: put a backup back, in pieces (o = offset in bytes, d = hex, end=1 on the last). It takes effect at the next
// start (setup restarts the controller anyway).
esp_err_t hRestore(httpd_req_t *r) {
  Lock l;
  static std::string in;
  uint32_t o = strtoul(arg(r, "o").c_str(), nullptr, 10);
  std::string hex = arg(r, "d");
  if (o == 0) in.clear();
  if (o != in.size() || hex.size() % 2 || in.size() + hex.size() / 2 > 2048) return fail(r, "pieces out of order");
  std::string piece(hex.size() / 2, 0);
  if (!unhex(hex, (uint8_t *)&piece[0], piece.size())) return fail(r, "bad piece");
  in += piece;
  if (arg(r, "end") != "1") return ok(r);
  uint16_t sz[3];
  if (in.size() < 9 || in.compare(0, 3, "TB1")) return fail(r, "not a Tilt backup");
  memcpy(sz, in.data() + 3, sizeof sz);
  if (sz[0] != sizeof cfg || sz[1] != sizeof tune || sz[2] != sizeof sx || in.size() != 9 + sizeof cfg + sizeof tune + sizeof sx + 4) return fail(r, "this backup is from a different firmware");
  const char *p = in.data() + 9;
  Settings c; memcpy(&c, p, sizeof c); p += sizeof c;
  Tune t; memcpy(&t, p, sizeof t); p += sizeof t;
  memcpy(&sx, p, sizeof sx); p += sizeof sx;
  if (c.magic != CFG_MAGIC) return fail(r, "not a Tilt backup");
  // The backup comes through the hub: end every string, and clean the names as if they were typed in the app.
  c.tz[sizeof c.tz - 1] = 0; c.tzName[sizeof c.tzName - 1] = 0;
  { std::string n(c.name, strnlen(c.name, sizeof c.name)); cleanText(c.name, sizeof c.name, n); }
  for (int i = 0; i < PORTS; i++) { std::string n(c.b[i].name, strnlen(c.b[i].name, sizeof c.b[i].name)); cleanText(c.b[i].name, sizeof c.b[i].name, n); }
  cfgApply(c); tune = t;                         // a move on a blind whose Marks change is stopped first (motion.h)
  syncMode = p[0]; parMode = p[1]; hkSeparate = p[2]; pwmSaved = p[3];
  tuneSave(); sxSave(); syncSave(); nvs.putUChar("hksep", hkSeparate); nvs.putUChar("pwm", pwmSaved); nvs.putUChar("angv", 2);
  in.clear();
  event("settings restored from a backup");
  return ok(r);
}
// Owner: the hub's Thread network this controller keeps, so the app can give it to a new controller.
esp_err_t hHubNet(httpd_req_t *r) {
  Lock l;
  uint8_t tlv[254];
  size_t n = nvs.getBytes("hubds", tlv, sizeof tlv);
  if (!n) return fail(r, "no Tilt Hub network");
  return sendJson(r, "{\"ok\":1,\"ds\":\"" + hexOf(tlv, n) + "\"}");
}
// Owner: back to how it came. Everything in flash is erased (owners, settings, marks, homes, the hub network); it
// keeps the firmware it runs, and setup puts it on a hub again.
esp_err_t hFactory(httpd_req_t *r) {
  Lock l;
  if (arg(r, "sure") != "yes") return fail(r, "add sure=yes");
  event("factory reset");
  if (hubSock >= 0 && hubAddrOk) {               // tell the hub: gone (with proof, so nobody else can say it)
    std::string g = dgEncode(DG_BYE, 0x3030, hubMac(proofText(Proof::CtlBye, bootId, "")));   // seq "00"
    sendto(hubSock, g.data(), g.size(), 0, (sockaddr *)&hubAddr, sizeof hubAddr);
  }
  ok(r);
  xTaskCreate([](void *) {
    vTaskDelay(pdMS_TO_TICKS(1500));             // the answer goes out first
    for (int i = 0; i < PORTS; i++) { motorRaw(i, 0, 0); digitalWrite(P_EN[i], LOW); }
    nvs_flash_deinit();
    nvs_flash_erase();
    esp_restart();
  }, "factory", 4096, nullptr, 3, nullptr);
  return ESP_OK;
}
// Owner: mark which key is the Tilt Hub's (the app does this right after letting the hub in). From then on only
// messages proven with it count as the hub's.
esp_err_t hHubKey(httpd_req_t *r) {
  Lock l;
  uint8_t id[8];
  if (!unhex(arg(r, "cid"), id, 8)) return fail(r, "bad id");
  bool found = false;
  for (int i = 0; i < MAX_KEYS; i++) found = found || (keys[i].used == 1 && !memcmp(keys[i].id, id, 8));
  if (!found) return fail(r, "no such key");
  memcpy(hubKeyId, id, 8);
  hubKeySet = true;
  nvs.putBytes("hubkey", id, 8);
  hubLinkRefresh();
  event("Tilt Hub key marked");
  return ok(r);
}
// Go back to the firmware in the other slot (the one before the last update), without a cable.
esp_err_t hSwapFw(httpd_req_t *r) {
  Lock l;
  const esp_partition_t *other = esp_ota_get_next_update_partition(nullptr);
  esp_app_desc_t d;
  if (!other || esp_ota_get_partition_description(other, &d) != ESP_OK) return fail(r, "no other firmware");
  if (esp_ota_set_boot_partition(other) != ESP_OK) return fail(r, "could not switch");
  event("switching to the other firmware (%s)", d.version);
  restartSoon = true;
  std::string j;
  ap(j, "{\"ok\":1,\"fw\":%s}", jq(d.version).c_str());
  return sendJson(r, j);
}

// Join the saved hub network (OpenThread keeps it; Matter then sees a configured Thread network and runs it).
void hubApply() {
  uint8_t tlv[254];
  size_t n = nvs.getBytes("hubds", tlv, sizeof tlv);
  if (!n) return;
  esp_openthread_lock_acquire(portMAX_DELAY);
  otInstance *ot = esp_openthread_get_instance();
  otOperationalDatasetTlvs cur, ds;
  bool same = otDatasetGetActiveTlvs(ot, &cur) == OT_ERROR_NONE && cur.mLength == n && !memcmp(cur.mTlvs, tlv, n);
  if (!same) {
    memcpy(ds.mTlvs, tlv, n);
    ds.mLength = n;
    otThreadSetEnabled(ot, false);
    otDatasetSetActiveTlvs(ot, &ds);
  }
  if (!otIp6IsEnabled(ot)) otIp6SetEnabled(ot, true);
  otThreadSetEnabled(ot, true);
  esp_openthread_lock_release();
}
// Where the hub is: the address it last answered from. Until it has answered, every Thread device next to this one
// (link-local all-nodes, ff02::1): the hub is this controller's parent, so it hears that, and answers from its own address.
static bool hubDest(sockaddr_in6 &d) {
  if (hubAddrOk && hubOk()) { d = hubAddr; return true; }
  // Not proven yet (no hub key here, or just restarted): where the hub's hello came from. A sleepy device's multicast
  // does not reliably reach its parent. Only status and log lines go this way; nothing is trusted from it.
  if (hubHelloOk && hubLinkSeen && millis() - hubLinkSeen < 1200000) { d = hubHelloAddr; return true; }
  memset(&d, 0, sizeof d);
  d.sin6_family = AF_INET6;
  d.sin6_port = htons(HUB_PORT);
  uint8_t *a = (uint8_t *)&d.sin6_addr;
  a[0] = 0xff; a[1] = 0x02; a[15] = 0x01;
  d.sin6_scope_id = esp_netif_get_netif_impl_index(esp_openthread_get_netif());   // link-local: out of the Thread side
  return true;
}
static bool hubTime(const std::string &s) {     // "epoch.mac"
  static long lastT = 0;
  size_t dot = s.find('.');
  if (dot == std::string::npos) return false;
  std::string ts = s.substr(0, dot);
  if (!hubMacOk(proofText(Proof::HubTime, bootId, ts), s.substr(dot + 1))) return false;
  long t = atol(ts.c_str());
  if (t < 1700000000 || t <= lastT) return false;   // never an older one again
  lastT = t;
  long d = t - (long)time(nullptr);
  if (d > 2 || d < -2) { timeval tv = {t, 0}; settimeofday(&tv, nullptr); event("time set by the Tilt Hub"); }
  return true;
}
// ---- a firmware file, through the hub. An owner allowed it (/api/otaopen) and the file carries a valid release
// signature. The new firmware starts on trial. The messages, the two kinds of file and every decision: ota.h
// (OtaReceiver). Here: what it does to this controller (OtaSink).
// A patch is only what changed since the firmware this controller runs (esp_delta_ota): usually a tenth of the size,
// so it comes over Thread in about a minute.
struct EspOtaSink : OtaSink {
  esp_ota_handle_t h = 0;
  const esp_partition_t *to = nullptr;
  mbedtls_sha256_context sha;                    // of the image being written (for a patch: what the patch makes)
  esp_delta_ota_handle_t patch = nullptr;
  // Where the new image's bytes go (the file itself, or what the patch makes): flash, and the hash for the signature.
  static esp_err_t out(const uint8_t *b, size_t n, void *me) {
    EspOtaSink *k = (EspOtaSink *)me;
    if (esp_ota_write(k->h, b, n) != ESP_OK) return ESP_FAIL;
    mbedtls_sha256_update(&k->sha, b, n);
    return ESP_OK;
  }
  static esp_err_t src(uint8_t *b, size_t n, int off, void *) { return esp_partition_read(esp_ota_get_running_partition(), off, b, n); }
  bool open() override {
    to = esp_ota_get_next_update_partition(nullptr);
    if (!to || esp_ota_begin(to, OTA_WITH_SEQUENTIAL_WRITES, &h) != ESP_OK) return false;
    mbedtls_sha256_init(&sha); mbedtls_sha256_starts(&sha, 0);
    return true;
  }
  bool openPatch() override {
    esp_delta_ota_cfg_t dc = {};
    dc.read_cb_with_user_data = src;
    dc.write_cb_with_user_data = out;
    dc.user_data = this;
    patch = esp_delta_ota_init(&dc);
    return patch != nullptr;
  }
  bool write(const uint8_t *b, size_t n) override { return patch ? esp_delta_ota_feed_patch(patch, b, n) == ESP_OK : out(b, n, this) == ESP_OK; }
  bool finishPatch() override { return esp_delta_ota_finalize(patch) == ESP_OK; }
  void closePatch() override { if (patch) { esp_delta_ota_deinit(patch); patch = nullptr; } }
  void hash(uint8_t o[32]) override { mbedtls_sha256_finish(&sha, o); mbedtls_sha256_free(&sha); }
  bool verify(const uint8_t hs[32], const uint8_t sig[64]) override { return fwSignatureOk(hs, sig); }
  bool finalize() override { return esp_ota_end(h) == ESP_OK; }
  bool newVersion(std::string &v) override {
    esp_app_desc_t d;
    if (esp_ota_get_partition_description(to, &d) != ESP_OK) return false;
    v = d.version;
    return true;
  }
  bool setBoot() override { return esp_ota_set_boot_partition(to) == ESP_OK; }
  void abort() override { closePatch(); esp_ota_abort(h); }
  bool runningSha(uint8_t o[32]) override { return esp_partition_get_sha256(esp_ota_get_running_partition(), o) == ESP_OK; }
  // While a file comes in, keep the radio on (like a mains-powered device) so the hub can send at full speed instead of
  // one piece per check-in; back to sleeping once it is done or stalls.
  void radio(bool on) override {
    esp_openthread_lock_acquire(portMAX_DELAY);
    otInstance *ot = esp_openthread_get_instance();
    otLinkModeConfig m = otThreadGetLinkMode(ot);
    if (m.mRxOnWhenIdle != on) { m.mRxOnWhenIdle = on; otThreadSetLinkMode(ot, m); }
    esp_openthread_lock_release();
  }
  void stopBlinds() override { Lock l; stopAll("stopped"); }
  void fastPoll() override {                     // check in quickly while the file comes in
    chip::DeviceLayer::PlatformMgr().ScheduleWork([](intptr_t) { chip::app::ICDNotifier::GetInstance().NotifyNetworkActivityNotification(); }, 0);
  }
  void accepted() override { Lock l; statsSave(); restartSoon = true; }
  void log(const std::string &line) override { event("%s", line.c_str()); }
};
static EspOtaSink hubOtaSink;
static OtaReceiver hubOtaRx(hubOtaSink, FW_VERSION);
bool hubOtaBusy() { return hubOtaRx.busy(millis()); }
// 'B': the proof first (only the hub may start one), then the receiver's own checks.
static OtaReply hubOtaBegin(const std::string &in) {
  size_t dot = in.find('.');
  if (dot == std::string::npos || !hubMacOk(proofText(Proof::HubOta, bootId, in.substr(0, dot)), in.substr(dot + 1)))
    return {"403", "{\"err\":\"not from the Tilt Hub\"}"};
  bool allowed;
  { QuietLock l; allowed = otaWindowOpen(otaWindow, millis()); }   // set by the owner's /api/otaopen
  return hubOtaRx.begin(in.substr(0, dot), (long)time(nullptr), allowed, millis());
}
static void hubTask(void *) {
  hubSock = socket(AF_INET6, SOCK_DGRAM, IPPROTO_UDP);
  sockaddr_in6 me = {};
  me.sin6_family = AF_INET6;
  me.sin6_port = htons(HUB_PORT);
  me.sin6_addr = in6addr_any;
  int no = 0;
  setsockopt(hubSock, IPPROTO_IPV6, IPV6_MULTICAST_LOOP, &no, sizeof no);   // never hear its own call for the hub
  if (hubSock < 0 || bind(hubSock, (sockaddr *)&me, sizeof me) < 0) { event("hub link did not start (socket %d, errno %d)", hubSock, errno); vTaskDelete(nullptr); return; }
  event("hub link listening");
  timeval tmo = {1, 0};                          // wake once a second: an update that stalled is stopped here
  setsockopt(hubSock, SOL_SOCKET, SO_RCVTIMEO, &tmo, sizeof tmo);
  static char buf[2400];
  static KeptAnswer lastJoin;                    // the last ask or recovery ('A', 'R'): the same one sent again gets the same answer
  for (;;) {
    sockaddr_in6 from;
    socklen_t fl = sizeof from;
    int n = recvfrom(hubSock, buf, sizeof buf, 0, (sockaddr *)&from, &fl);
    if (hubOtaStallReq) { hubOtaStallReq = false; hubOtaRx.stopIfStalled(millis()); }
    if (n < 0) { if (errno != EAGAIN && errno != EWOULDBLOCK) vTaskDelay(pdMS_TO_TICKS(100)); continue; }   // never spin on an error
    // Only what the hub sends. (Anything else, such as this controller's own multicast or an answer, is ignored:
    // answering it could start an endless exchange.) Pairing as the first owner is Bluetooth only, never over Thread.
    if (n < 3 || !hubAsks(buf[0])) continue;
    char t = buf[0];
    std::string in(buf + 3, n - 3), out;
    // The hub, proven (a good proof, or a command sealed with its key): where to send pushes, and "the hub is there".
    auto heard = [&]() {
      if (!hubSeen) event("first proven message from the hub ('%c')", t);
      hubSeen = millis() ? millis() : 1;
      QuietLock l;                               // the blinds task sends pushes there (hubDest)
      hubAddr = from; hubAddrOk = true;
    };
    // Check in fast for a few seconds: the next message (the app's command after its hello, or more) comes soon. Only
    // for a message that was accepted (anything else on the network must not keep the radio busy), and a hello at
    // most every 20 seconds.
    auto awake = []() { chip::DeviceLayer::PlatformMgr().ScheduleWork([](intptr_t) { chip::app::ICDNotifier::GetInstance().NotifyNetworkActivityNotification(); }, 0); };
    if (t == 's') { if (in.size() > 3 && hubTime(in.substr(3))) heard(); continue; }
    const char *st = "400";
    if (t == 'H') {
      static uint32_t lastHello = 0;
      out = helloJson(); st = "200";
      hubLinkSeen = millis() ? millis() : 1;
      { QuietLock l; hubHelloAddr = from; hubHelloOk = true; }
      if (!lastHello || millis() - lastHello > 20000) { lastHello = millis() ? millis() : 1; hubWantsStatus = true; awake(); }
    } else if (t == 'X') {
      bool fromHub = false;
      st = secDo(in, out, nullptr, &fromHub);
      if (st[0] == '2') { awake(); hubLinkSeen = millis() ? millis() : 1; if (fromHub) heard(); }
    } else if ((t == 'A' || t == 'R') && lastJoin.again(std::string(1, t) + in, millis())) { st = lastJoin.st; out = lastJoin.out; }   // its answer was lost
    else if (t == 'A' || t == 'R') {
      st = t == 'A' ? pairDo(in, out, true) : recoverDo(in, out);
      if (st[0] == '2') { awake(); lastJoin.keep(std::string(1, t) + in, st, out, millis()); }
    } else if (t == 'Q') {
      out = recoverStateJson(); st = "200";
      if (out.find("\"on\":1") != std::string::npos) awake();   // a recovery is running: its next poll comes in a second
    }
    else if (t == 'B') { OtaReply r = hubOtaBegin(in); st = r.status; out = r.out; if (st[0] == '2') { heard(); awake(); } }
    else if (t == 'E' && !hubOtaRx.going()) { OtaReply r = hubOtaRx.end(millis()); st = r.status; out = r.out; }   // its answer was lost: the same again
    else if (t == 'W' || t == 'E') {             // pieces only from where the proven begin came from
      if (!hubOtaRx.going() || !hubAddrOk || memcmp(&from.sin6_addr, &hubAddr.sin6_addr, 16)) { out = "{\"err\":\"no update going\"}"; st = "409"; }
      else { OtaReply r = t == 'W' ? hubOtaRx.piece(in, millis()) : hubOtaRx.end(millis()); st = r.status; out = r.out; }
    } else out = "{\"err\":\"unknown request\"}";
    // Most answers are one message; a long one (the log, a backup) goes in pieces ('#' seq, piece, count, part).
    uint16_t seq = (uint16_t)((uint8_t)buf[1] << 8 | (uint8_t)buf[2]);
    std::vector<std::string> reps = dgAnswerDatagrams(t, seq, std::string(st, 3) + out);
    if (reps.empty()) reps = dgAnswerDatagrams(t, seq, "500{\"err\":\"answer too long for the Tilt Hub\"}");
    for (size_t i = 0; i < reps.size(); i++) {
      sendto(hubSock, reps[i].data(), reps[i].size(), 0, (sockaddr *)&from, fl);
      if (i + 1 < reps.size()) vTaskDelay(pdMS_TO_TICKS(15));   // let the radio send it before queuing the next
    }
  }
}
// After Matter has started.
void hubBegin() {
  uint32_t b = 0;
  nvs.getBytes("bootn", &b, sizeof b);
  bootN = b + 1;
  nvs.putBytes("bootn", &bootN, sizeof bootN);
  hubApply();
  xTaskCreate(hubTask, "hub", 8192, nullptr, 5, nullptr);
}
static int hubRole() {
  esp_openthread_lock_acquire(portMAX_DELAY);
  int r = otThreadGetDeviceRole(esp_openthread_get_instance());
  esp_openthread_lock_release();
  return r;
}
// Once a second from webTick (the lock is held).
void hubTick() {
  static std::string last;
  static uint32_t lastAt = 0, rejoinAt = 0, lastTry = 0, logSent = 0;
  static int lastRole = -1;
  static bool left = false;
  if (hubSock < 0) return;
  uint32_t now = millis();
  int role = hubRole();
  if (role != lastRole) {
    static const char *names[] = {"off", "detached", "joined (child)", "router", "leader"};
    event("Thread: %s", role >= 0 && role <= 4 ? names[role] : "?");
    lastRole = role;
  }
  if (role < OT_DEVICE_ROLE_CHILD && now - lastTry > 60000) { lastTry = now; hubApply(); }   // not on the network: try again
  // A controller on a hub is not in a home itself: the hub is. Matter forgets its network when it leaves its last
  // home, so this waits until the hub has answered, then joins the hub's network again right away.
  if (!left && hubOk() && homesPaired()) {
    left = true;
    chip::DeviceLayer::PlatformMgr().ScheduleWork([](intptr_t) {
      auto &ft = chip::Server::GetInstance().GetFabricTable();
      chip::FabricIndex idx[8];
      int n = 0;
      for (auto &f : ft) if (n < 8) idx[n++] = f.GetFabricIndex();
      for (int i = 0; i < n; i++) ft.Delete(idx[i]);
    }, 0);
    event("left the home (the Tilt Hub shows these blinds now)");
    rejoinAt = now + 3000;
  }
  if (rejoinAt && (int32_t)(now - rejoinAt) >= 0) { rejoinAt = 0; hubApply(); }
  if (hubOtaRx.stalled(now)) hubOtaStallReq = true;   // the hub task stops it
  // Nobody owns it yet (new, or just reset): keep it findable over Bluetooth until it is set up. Matter's window
  // closes after 15 minutes; open it again (the Tilt service advertises with it).
  static uint32_t lastOpen = 0;
  if (!owned() && !hubOk() && firstPairOpen() && now - lastOpen > 60000) {
    lastOpen = now;
    chip::DeviceLayer::PlatformMgr().ScheduleWork([](intptr_t) {
      auto &mgr = chip::Server::GetInstance().GetCommissioningWindowManager();
      chip::DeviceLayer::ConnectivityMgr().SetBLEAdvertisingEnabled(true);
      if (!mgr.IsCommissioningWindowOpen()) mgr.OpenBasicCommissioningWindow(chip::System::Clock::Seconds16(900), chip::CommissioningWindowAdvertisement::kAllSupported);
    }, 0);
  }
  // On a hub this controller is never added to a home itself: stop offering it for Matter pairing (Apple Home would
  // try to add it over Thread and spin). Checked every minute: Matter opens the window again after a start.
  static uint32_t lastClose = 0;
  if (hubOk() && now - lastClose > 60000) {
    lastClose = now;
    chip::DeviceLayer::PlatformMgr().ScheduleWork([](intptr_t) {
      auto &mgr = chip::Server::GetInstance().GetCommissioningWindowManager();
      if (mgr.IsCommissioningWindowOpen()) { mgr.CloseCommissioningWindow(); event("Matter pairing closed (the Tilt Hub is this controller's home)"); }
      chip::DeviceLayer::ConnectivityMgr().SetBLEAdvertisingEnabled(false);
    }, 0);
  }
  sockaddr_in6 d;
  if (role < OT_DEVICE_ROLE_CHILD || !hubDest(d)) return;
  // The event log, for whoever watches the hub's USB log (a controller on Thread has no other way to show it).
  {
    LogLock ll;
    if (logSent > logSeq || logSeq - logSent > LOG_N) logSent = logSeq > LOG_N ? logSeq - LOG_N : 0;
    for (int k = 0; k < 3 && logSent < logSeq; k++, logSent++) {
      std::string m = std::string("L00") + logLines[logSent % LOG_N].c_str();
      sendto(hubSock, m.data(), m.size(), 0, (sockaddr *)&d, sizeof d);
    }
  }
  // The status, when it changed, and every 10 minutes. The battery percent jitters by a point: it only counts as a
  // change once it has moved by 3 (else every reading would wake the hub and cost battery).
  static int lastPct = -100;
  int pct = battPercent(vbatRest);
  if (abs(pct - lastPct) < 3) pct = lastPct;
  std::string j = hubStatusJson(pct);
  if (j == last && lastAt && now - lastAt < (hubOk() ? 600000u : 5000u) && !hubWantsStatus) return;   // no answer yet: again in 5 s
  lastPct = pct;
  hubWantsStatus = false;
  static uint32_t pushN = 0;
  ++pushN;
  // No hub key yet (setup): no proof, and the hub takes it without.
  std::string m = dgEncode(DG_PUSH, 0x3030, pushPayload(j, pushN, hubMac(proofText(Proof::CtlPush, bootId, j + std::to_string(pushN)))));
  int sent = sendto(hubSock, m.data(), m.size(), 0, (sockaddr *)&d, sizeof d);
  static int fails = 0;
  if (sent != (int)m.size() && fails++ < 3) event("status to hub not sent (errno %d)", errno);
  last = j; lastAt = now ? now : 1;
}

bool hubJoined() { uint8_t t[4]; return nvs.getBytes("hubds", t, sizeof t) > 0; }   // setup gave it a hub network
// For the developer page: where it is on Thread.
std::string hubThreadJson() {
  esp_openthread_lock_acquire(portMAX_DELAY);
  otInstance *ot = esp_openthread_get_instance();
  int role = otThreadGetDeviceRole(ot), ch = otLinkGetChannel(ot);
  int8_t rssi = 0;
  otThreadGetParentAverageRssi(ot, &rssi);
  uint16_t rloc = otThreadGetRloc16(ot);
  esp_openthread_lock_release();
  std::string j;
  ap(j, "{\"role\":%d,\"ch\":%d,\"parentRssi\":%d,\"rloc\":%u,\"hub\":%d}", role, ch, rssi, rloc, hubOk() ? 1 : 0);
  return j;
}
