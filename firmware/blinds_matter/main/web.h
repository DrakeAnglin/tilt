// The JSON interface the Tilt app talks to, on ESP-IDF's HTTP server.
// Also: firmware update over Wi-Fi, schedules, the clock.
#pragma once
#include <esp_http_server.h>
#include <esp_ota_ops.h>
#include <esp_image_format.h>
#include <esp_wifi.h>
#include <esp_netif.h>
#include <esp_netif_sntp.h>
#include <esp_mac.h>
#include <esp_chip_info.h>
#include <esp_system.h>
#include <driver/temperature_sensor.h>
#include "motion.h"
#include "sec.h"
#include "fwkey.h"
#include "wire.h"
#include <mbedtls/sha256.h>
#include <mbedtls/ecdsa.h>
#ifdef TILT_RELEASE
// A public release carries no secrets: Wi-Fi comes from Bluetooth setup, and updates must be signed.
#define WIFI_SSID ""
#define WIFI_PASSWORD ""
#define OTA_PASSWORD ""
#else
#include "secrets.h"
#endif
#include <mdns.h>

#define FW_VERSION "2.2.1-dev5"
SemaphoreHandle_t mx;                    // the blinds' state is touched by the web server and by the blinds task
uint32_t lastWeb = 0;                    // millis of the last request (0 = none yet)
bool otaPending = false, restartSoon = false;
extern uint8_t hkSeparate;
int homesPaired();                       // app_main.cpp
void pokeBlinds();
static temperature_sensor_handle_t tsens = nullptr;
static uint32_t appSize = 0;

bool timeValid() { return time(nullptr) > 1700000000; }

#include "schedules.h"

// ---- small helpers (ap, jq, jn: wire.h)
std::string arg(httpd_req_t *r, const char *key) {       // a value from the address's ?a=b&c=d part, decoded
  char q[600], v[300];
  if (secQuery) { if (httpd_query_key_value(secQuery, key, v, sizeof v) != ESP_OK) return ""; }      // a secured command
  else if (httpd_req_get_url_query_str(r, q, sizeof q) != ESP_OK || httpd_query_key_value(q, key, v, sizeof v) != ESP_OK) return "";
  std::string o;
  for (char *p = v; *p; p++) {
    if (*p == '+') o += ' ';
    else if (*p == '%' && isxdigit((unsigned char)p[1]) && isxdigit((unsigned char)p[2])) { char h[3] = {p[1], p[2], 0}; o += (char)strtol(h, nullptr, 16); p += 2; }
    else o += *p;
  }
  return o;
}
int argi(httpd_req_t *r, const char *key) { return atoi(arg(r, key).c_str()); }
esp_err_t sendJson(httpd_req_t *r, const std::string &j) {
  if (secOut) { *secOut = j; return ESP_OK; }    // a secured command: the answer is sealed by hSecure
  httpd_resp_set_type(r, "application/json");
  httpd_resp_set_hdr(r, "Cache-Control", "no-store");
  return httpd_resp_send(r, j.c_str(), j.size());
}
esp_err_t ok(httpd_req_t *r) { return sendJson(r, "{\"ok\":1}"); }
esp_err_t fail(httpd_req_t *r, const char *e) { return sendJson(r, std::string("{\"ok\":0,\"err\":") + jq(e) + "}"); }
esp_err_t done(httpd_req_t *r, const char *e) { return e ? fail(r, e) : ok(r); }
struct Lock {                             // every handler holds this while it touches the blinds
  Lock() { xSemaphoreTake(mx, portMAX_DELAY); lastWeb = millis() ? millis() : 1; }
  ~Lock() { xSemaphoreGive(mx); pokeBlinds(); }
};
const char *resetReason() {
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON: return "power on";
    case ESP_RST_SW: return "restart / update";
    case ESP_RST_PANIC: return "crash";
    case ESP_RST_BROWNOUT: return "brownout (supply dipped)";
    case ESP_RST_INT_WDT: case ESP_RST_TASK_WDT: case ESP_RST_WDT: return "watchdog";
    case ESP_RST_USB: return "USB";
    default: return "other";
  }
}
float tiltWord(int p, const std::string &to) {
  if (to == "open") return 0;
  if (to == "up") return 100;
  if (to == "down") return -100;
  if (to == "close") return cfg.closeUp ? 100 : -100;
  if (to == "fav") return cfg.b[p].fav;
  return NAN;
}

// ---- pages
esp_err_t hRoot(httpd_req_t *r) {
  lastWeb = millis() ? millis() : 1;
  httpd_resp_set_type(r, "text/plain");           // the built-in web page is gone: the Tilt app is the way in
  return httpd_resp_sendstr(r, "Tilt blinds controller. Use the Tilt app.");
}
esp_err_t hState(httpd_req_t *r) {
  Lock l;
  std::string j;
  j.reserve(1200);
  ap(j, "{\"v\":\"" FW_VERSION "\",\"name\":%s,\"t\":%lu,\"tok\":%d,\"up\":%lu", jq(cfg.name).c_str(), (unsigned long)time(nullptr), timeValid() ? 1 : 0, (unsigned long)(millis() / 1000));
  ap(j, ",\"batt\":{\"v\":%.2f,\"pct\":%d,\"st\":\"%s\",\"vin\":%.2f,\"low\":%d}", vbatRest, battPercent(vbatRest), chargeState(), vin, battOkToMove() ? 0 : 1);
  ap(j, ",\"pw\":{\"mode\":1,\"sleepIn\":-1,\"checkin\":0},\"closeUp\":%d,\"sync\":%d,\"par\":%d,\"ap\":0,\"mv\":%d,\"log\":%lu,\"hk\":%d,\"asks\":%d,\"me\":%d,\"gentle\":%d,\"topic\":\"%s\",\"b\":[", cfg.closeUp, syncMode, parMode, firstMoving(), (unsigned long)logSeq, homesPaired(), asksWaiting(), secClient >= 0 ? keys[secClient].role : 1, rampAny() ? 1 : 0, secClient >= 0 ? hexOf(cloudTopic, 16).c_str() : "");
  for (int i = 0; i < PORTS; i++) {
    BlindCfg &c = cfg.b[i];
    bool live = movingPort(i) && !isnan(mvs[i].live) && calibrated(i);
    ap(j, "%s{\"name\":%s,\"hid\":%d,\"pres\":%d,\"seen\":%d,\"cal\":%d,\"tilt\":%s,\"tgt\":%s,\"mov\":%d,\"q\":%d,\"fav\":%d,\"ang\":%s,\"last\":%s}", i ? "," : "",
       jq(c.name).c_str(), c.hidden, bs[i].present ? 1 : 0, bs[i].seen ? 1 : 0, calibrated(i) ? 1 : 0, jn(live ? tiltOf(i, mvs[i].live) : bs[i].tilt, 1).c_str(),
       jn(bs[i].target, 0).c_str(), movingPort(i) ? 1 : 0, bs[i].queued ? 1 : 0, c.fav, jn(bs[i].ang, 1).c_str(), jq(bs[i].last).c_str());
  }
  j += "]}";
  return sendJson(r, j);
}
esp_err_t hDev(httpd_req_t *r) {
  Lock l;
  std::string j;
  j.reserve(2400);
  const esp_partition_t *part = esp_ota_get_running_partition();
  esp_chip_info_t ci;
  esp_chip_info(&ci);
  uint8_t mac[6] = {0};
  esp_read_mac(mac, ESP_MAC_WIFI_STA);
  float temp = 0;
  if (tsens) temperature_sensor_get_celsius(tsens, &temp);
  wifi_ap_record_t apr = {};
  bool up = esp_wifi_sta_get_ap_info(&apr) == ESP_OK;
  esp_netif_ip_info_t ip = {};
  esp_netif_t *nif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
  if (nif) esp_netif_get_ip_info(nif, &ip);
  char ips[20];
  snprintf(ips, sizeof ips, IPSTR, IP2STR(&ip.ip));
  ap(j, "{\"sys\":{\"fw\":\"" FW_VERSION "\",\"build\":\"" __DATE__ " " __TIME__ "\",\"core\":\"esp-matter 1.5\",\"idf\":%s,\"chip\":\"ESP32-C6\",\"rev\":%d,\"mhz\":160,\"flash\":4194304", jq(esp_get_idf_version()).c_str(), ci.revision);
  ap(j, ",\"app\":%lu,\"appMax\":%lu,\"part\":%s,\"md5\":\"\",\"heap\":%lu,\"heapMin\":%lu,\"temp\":%.1f,\"rst\":%s,\"up\":%lu,\"pending\":%d", (unsigned long)appSize, (unsigned long)(part ? part->size : 0),
     jq(part ? part->label : "?").c_str(), (unsigned long)esp_get_free_heap_size(), (unsigned long)esp_get_minimum_free_heap_size(), temp, jq(resetReason()).c_str(), (unsigned long)(millis() / 1000), otaPending ? 1 : 0);
  ap(j, ",\"mac\":\"%02X:%02X:%02X:%02X:%02X:%02X\"}", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  ap(j, ",\"wifi\":{\"ssid\":%s,\"cfg\":%s,\"own\":0,\"ip\":\"%s\",\"rssi\":%d,\"ch\":%d,\"host\":\"blinds-pcb.local\",\"tx\":%d,\"ap\":0}", jq(up ? (const char *)apr.ssid : "").c_str(), jq(WIFI_SSID).c_str(), ips, up ? apr.rssi : 0, up ? apr.primary : 0, cfg.txPower);
  ap(j, ",\"pwr\":{\"vbat\":%.3f,\"rest\":%.3f,\"vin\":%.3f,\"vdd\":%.3f,\"powered\":%d,\"awakeS\":%lu,\"motorMs\":%lu,\"wakes\":0,\"since\":%lu,\"keep\":0,\"next\":%lu}", vbat, vbatRest, vin, vdd, powered ? 1 : 0,
     (unsigned long)stats.battAwakeS, (unsigned long)stats.battMotorMs, (unsigned long)stats.battSince, (unsigned long)schedNext());
  ap(j, ",\"st\":{\"boots\":%lu,\"brown\":%lu,\"crash\":%lu,\"wdt\":%lu,\"wakes\":0,\"checkins\":0,\"ota\":%lu,\"motorS\":%lu}", (unsigned long)stats.boots, (unsigned long)stats.brownouts, (unsigned long)stats.crashes,
     (unsigned long)stats.wdt, (unsigned long)stats.otaOk, (unsigned long)(stats.motorMs / 1000));
  Move &dm = mvs[max(firstMoving(), 0)];          // the developer page shows one move: the first blind that is moving
  ap(j, ",\"tune\":{\"grace\":%d,\"stall\":%d,\"deg10\":%d,\"max\":%d},\"mv\":{\"kind\":%d,\"port\":%d,\"st\":%d,\"nudges\":%d,\"live\":%s},\"p\":[", tune.graceMs, tune.stallMs, tune.stallDeg10, tune.moveMaxS, dm.kind, dm.port, dm.st, dm.nudges, jn(dm.live, 1).c_str());
  for (int i = 0; i < PORTS; i++) {
    BlindCfg &c = cfg.b[i];
    const char *pr = marksProblem(i);
    ap(j, "%s{\"ang\":%s,\"mv\":%.0f,\"sig\":\"%s\",\"pres\":%d,\"up\":%s,\"open\":%s,\"down\":%s,\"sign\":%d,\"bias\":%.1f,\"lead0\":%.1f,\"signSeen\":%d,\"speed\":%d,\"moves\":%lu,\"stalls\":%lu,\"prob\":%s}", i ? "," : "", jn(bs[i].ang, 1).c_str(), bs[i].mv, (bs[i].pwm || ((pwmSaved >> i) & 1)) ? "PWM" : "analog",
       bs[i].present ? 1 : 0, jn(c.up, 1).c_str(), jn(c.open, 1).c_str(), jn(c.down, 1).c_str(), msign(i), bs[i].mem.lead[1], bs[i].mem.lead[0], abs(c.motSign) == 2 ? 1 : 0, c.speed, (unsigned long)stats.moves[i], (unsigned long)stats.stalls[i], pr ? jq(pr).c_str() : "null");
  }
  j += "]}";
  return sendJson(r, j);
}
esp_err_t hCfg(httpd_req_t *r) {
  Lock l;
  WireBlind b[PORTS];
  WireSlot sl[SCHEDS];
  for (int i = 0; i < PORTS; i++) b[i] = {cfg.b[i].name, cfg.b[i].hidden, cfg.b[i].speed, cfg.b[i].fav};
  for (int i = 0; i < SCHEDS; i++) { const Sched &s = cfg.sched[i]; sl[i] = {s.on, s.days, s.mask, s.minute, s.tilt, sx.x[i].kind, sx.x[i].off, sx.x[i].ramp, sx.x[i].gid}; }
  time_t now = time(nullptr);
  WireCfg c = {cfg.name, cfg.closeUp, syncMode, parMode, cfg.txPower, cfg.tz, cfg.tzName, hkSeparate, b, PORTS, sl, SCHEDS, sx.lat, sx.lon, sunEvent(now, true), sunEvent(now, false)};
  return sendJson(r, cfgJson(c));
}
esp_err_t hLog(httpd_req_t *r) {
  Lock l;
  LogLock ll;
  uint32_t since = strtoul(arg(r, "since").c_str(), nullptr, 10), first = logSeq > LOG_N ? logSeq - LOG_N : 0;
  if (since < first || since > logSeq) since = first;
  std::string j;
  ap(j, "{\"seq\":%lu,\"lines\":[", (unsigned long)logSeq);
  for (uint32_t k = since; k < logSeq; k++) { if (k > since) j += ","; j += jq(logLines[k % LOG_N].c_str()); }
  j += "]}";
  return sendJson(r, j);
}
esp_err_t hHist(httpd_req_t *r) {
  Lock l;
  std::string j = "{\"h\":[";
  for (int i = 0; i < BATT_HIST; i++) ap(j, "%s%d", i ? "," : "", battHist[i]);
  j += "]}";
  return sendJson(r, j);
}
esp_err_t hSet(httpd_req_t *r) {
  Lock l;
  std::string k = arg(r, "k"), v = arg(r, "v");
  int n = atoi(v.c_str());
  if (k == "name") cleanText(cfg.name, sizeof cfg.name, v);
  else if (k == "closeUp") cfg.closeUp = n ? 1 : 0;
  else if (k == "loc") { float la = NAN, lo = NAN; if (sscanf(v.c_str(), "%f,%f", &la, &lo) != 2 || fabsf(la) > 90 || fabsf(lo) > 180) return fail(r, "bad place"); sx.lat = la; sx.lon = lo; sxSave(); }
  else if (k == "sync") { syncMode = n ? 1 : 0; syncSave(); for (int i = 0; i < PORTS; i++) handRef[i] = NAN; }   // start fresh: no following of old turns
  else if (k == "par") { parMode = n ? 1 : 0; syncSave(); }
  else if (k == "hksep") { hkSeparate = n ? 1 : 0; nvs.putUChar("hksep", hkSeparate); restartSoon = true; }   // Home's layout changes: restart
  else if (k == "tune.grace") { tune.graceMs = constrain(n, 0, 30000); tuneSave(); }
  else if (k == "tune.stall") { tune.stallMs = constrain(n, 200, 10000); tuneSave(); }
  else if (k == "tune.deg10") { tune.stallDeg10 = constrain(n, 1, 100); tuneSave(); }
  else if (k == "tune.max") { tune.moveMaxS = constrain(n, 5, 600); tuneSave(); }
  else if (k == "battMode" || k == "checkin" || k == "tx") return fail(r, "not in this version");
  else if (k == "tz") {
    if (v.length() < 3 || v.length() >= sizeof cfg.tz) return fail(r, "bad time zone");
    strlcpy(cfg.tz, v.c_str(), sizeof cfg.tz);
    cleanText(cfg.tzName, sizeof cfg.tzName, arg(r, "n"));
    setenv("TZ", cfg.tz, 1);
    tzset();
  } else if (k.length() >= 4 && k[0] == 'b' && k[2] == '.') {
    int p = k[1] - '0';
    if (p < 0 || p >= PORTS) return fail(r, "no such blind");
    std::string f = k.substr(3);
    BlindCfg &c = cfg.b[p];
    if (f == "name") { cleanText(c.name, sizeof c.name, v); if (!c.name[0]) snprintf(c.name, sizeof c.name, "Blind %d", p + 1); }
    else if (f == "speed") c.speed = constrain(n, 50, 100);
    else if (f == "fav") c.fav = constrain(n, -100, 100);
    else if (f == "hid") c.hidden = n ? 1 : 0;
    else if (f == "sign") c.motSign = n < 0 ? -1 : 1;
    else return fail(r, "unknown setting");
  } else return fail(r, "unknown setting");
  cfgSave();
  return ok(r);
}
esp_err_t hSched(httpd_req_t *r) {
  Lock l;
  int i = argi(r, "i");
  if (i < 0 || i >= SCHEDS) return fail(r, "no such schedule");
  WireSlot w = slotOfArgs([&](const char *k) { return arg(r, k); }, PORTS);
  Sched &s = cfg.sched[i];
  s.on = w.on; s.days = w.days; s.mask = w.mask; s.minute = w.min; s.tilt = w.tilt;
  sx.x[i] = {(uint8_t)w.kind, (uint8_t)w.ramp, (int16_t)w.off, w.gid};
  sxSave();
  cfgSave();
  lastSched = time(nullptr);
  return ok(r);
}
esp_err_t hGo(httpd_req_t *r) {
  Lock l;
  std::string b = arg(r, "b"), to = arg(r, "to");
  int one = b == "all" ? -1 : constrain(atoi(b.c_str()), 0, PORTS - 1);
  // ramp=N: gently, taking N minutes (the same slow move a schedule can make), instead of going straight there
  MoveAsk a = moveAsk(FROM_APP, one, NAN, (uint32_t)constrain(argi(r, "ramp"), 0, 60) * 60000u);
  a.solo = argi(r, "solo");
  float tOne = one < 0 ? NAN : to.length() ? tiltWord(one, to) : (float)atof(arg(r, "t").c_str());
  for (int p = 0; p < PORTS; p++) a.tilt[p] = one >= 0 ? tOne : tiltWord(p, to);   // the others go where the named one goes
  MoveResult m = moveBlinds(a);
  if (a.gentleMs && m.started) event("gentle move started (%d min)", (int)(a.gentleMs / 60000));
  return m.started ? ok(r) : fail(r, m.why);
}
esp_err_t hStop(httpd_req_t *r) { Lock l; moveStop(); return ok(r); }
esp_err_t hJog(httpd_req_t *r) { Lock l; return done(r, jog(argi(r, "b"), argi(r, "d") < 0 ? -1 : 1, constrain(argi(r, "p"), 30, 100), argi(r, "ms"))); }
esp_err_t hAngle(httpd_req_t *r) { Lock l; return done(r, startAngle(argi(r, "b"), atof(arg(r, "a").c_str()))); }
esp_err_t hMark(httpd_req_t *r) {
  Lock l;
  int p = argi(r, "b");
  const char *e = setMark(p, arg(r, "w"));
  if (e) return fail(r, e);
  const char *pr = marksProblem(p);
  return sendJson(r, std::string("{\"ok\":1,\"ang\":") + jn(bs[p].ang, 1) + ",\"prob\":" + (pr ? jq(pr) : "null") + "}");
}
esp_err_t hReset(httpd_req_t *r) {
  Lock l;
  std::string w = arg(r, "what");
  if (w == "stats") { uint32_t m = stats.magic; memset(&stats, 0, sizeof stats); stats.magic = m; statsSave(); }
  else if (w == "hist") { memset(battHist, 0, sizeof battHist); histSave(); }
  else if (w == "all") { cfgDefaults(); cfgSave(); }
  else return fail(r, "unknown");
  event("reset: %s", w.c_str());
  return ok(r);
}
esp_err_t hReboot(httpd_req_t *r) { Lock l; restartSoon = true; return ok(r); }
esp_err_t hNotYet(httpd_req_t *r) { return fail(r, "not in this version"); }
esp_err_t hWatch(httpd_req_t *r) {              // setup is open for this blind: keep its reading live for 3 more seconds
  Lock l;
  int p = argi(r, "b");
  if (p < 0 || p >= PORTS) return fail(r, "no such blind");
  if (watchPort >= 0 && watchPort != p) watchStop();
  watchPort = p;
  handBusy = false;
  watchUntil = millis() + 3000;
  setupSeen = millis() ? millis() : 1;           // a setup screen is open: turning by hand is expected, the others stay put
  return ok(r);
}
esp_err_t hTrace(httpd_req_t *r) {              // the recording of the last move
  std::string j;
  {
    Lock l;
    j.reserve(traceN * 14 + 80);
    ap(j, "{\"n\":%d,\"moving\":%d,\"p\":[", traceN, moving() ? 1 : 0);
    for (int i = 0; i < traceN; i++) ap(j, "%s[%u,%u,%u]", i ? "," : "", trace[i].t, trace[i].a, trace[i].st);
    j += "]}";
  }
  return sendJson(r, j);
}
esp_err_t hAwake(httpd_req_t *r) { Lock l; keepAwakeUntil = millis() + (uint32_t)constrain(argi(r, "min"), 0, 720) * 60000; return ok(r); }
// Keep the firmware that is on trial (sent by tools/flash_matter.sh once it has checked the board).
esp_err_t hKeep(httpd_req_t *r) {
  Lock l;
  if (otaPending) { esp_ota_mark_app_valid_cancel_rollback(); otaPending = false; stats.otaOk++; statsSave(); event("new firmware %s confirmed", FW_VERSION); }
  return ok(r);
}
// Wi-Fi networks in range, for first setup. The look-around itself runs in webTick; the app asks again until busy is 0.
std::string scanJson = "{\"ok\":1,\"busy\":1,\"nets\":[]}";
bool scanWanted = false;
uint32_t scanAt = 0;
esp_err_t hScan(httpd_req_t *r) {
  if (argi(r, "new") || !scanAt) scanWanted = true;          // new=1: look again
  return sendJson(r, scanWanted ? std::string("{\"ok\":1,\"busy\":1,\"nets\":[]}") : scanJson);
}
void scanRun() {
  wifi_scan_config_t sc = {};
  sc.show_hidden = false;
  std::string j = "{\"ok\":1,\"busy\":0,\"nets\":[";
  if (esp_wifi_scan_start(&sc, true) == ESP_OK) {
    static wifi_ap_record_t recs[20];
    uint16_t n = 20;
    if (esp_wifi_scan_get_ap_records(&n, recs) != ESP_OK) n = 0;
    int shown = 0;
    for (int i = 0; i < n && j.length() < 400; i++) {            // strongest first; the answer must stay small for Bluetooth
      const char *s = (const char *)recs[i].ssid;
      if (!s[0]) continue;
      bool dup = false;
      for (int k = 0; k < i; k++) if (!strcmp((const char *)recs[k].ssid, s)) dup = true;
      if (dup) continue;
      ap(j, "%s{\"s\":%s,\"r\":%d,\"l\":%d}", shown++ ? "," : "", jq(s).c_str(), recs[i].rssi, recs[i].authmode == WIFI_AUTH_OPEN ? 0 : 1);
    }
  }
  scanJson = j + "]}";
  scanAt = millis() ? millis() : 1;
}

// Firmware update: the .bin as the body of a POST, with the update password in a header. The new firmware runs on
// trial: it is kept once it has joined Wi-Fi and answered a request; a reset before that goes back to this one.
extern uint8_t openApi;
extern uint32_t otaWindow;
// A firmware file may carry a signature at its end: image | signature (64 bytes, r then s) | "TILTSIG1".
// A signed file needs no update password: the signature proves it came from whoever holds the release key. Either way
// an owner must have allowed updates first (/api/otaopen, 5 minutes).
#include "update.h"

// ---- who may use this controller
uint8_t openApi = 1;                             // 1: the plain /api and the web page still answer (until the app replaces them)
std::string ctrlId() { uint8_t m[6] = {0}; esp_read_mac(m, ESP_MAC_WIFI_STA); return hexOf(m, 6); }
bool wifiUp(char *ip, size_t n, char *ssid, size_t sn) {
  wifi_ap_record_t apr = {};
  bool up = esp_wifi_sta_get_ap_info(&apr) == ESP_OK;
  esp_netif_ip_info_t info = {};
  esp_netif_t *nif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
  if (nif) esp_netif_get_ip_info(nif, &info);
  snprintf(ip, n, IPSTR, IP2STR(&info.ip));
  strlcpy(ssid, up ? (const char *)apr.ssid : "", sn);
  return up && info.ip.addr != 0;
}
std::string helloJson() {
  std::string j;
  char ip[20], ssid[34];
  bool up = wifiUp(ip, sizeof ip, ssid, sizeof ssid);
  ap(j, "{\"id\":\"%s\",\"name\":%s,\"fw\":\"" FW_VERSION "\",\"boot\":\"%s\",\"owned\":%d,\"open\":%d,\"wifi\":%d,\"ip\":\"%s\",\"home\":%d}", ctrlId().c_str(), jq(cfg.name).c_str(), hexOf(bootId, 4).c_str(), owned() ? 1 : 0, openApi, up ? 1 : 0, up ? ip : "", homesPaired() ? 1 : 0);
  return j;
}
esp_err_t hHello(httpd_req_t *r) { return plain(r, "200 OK", helloJson()); }
// Owner, over the secured connection (Bluetooth at first setup): join this Wi-Fi network.
std::string newSsid, newPass;
bool wifiChange = false;
esp_err_t hSetWifi(httpd_req_t *r) {
  Lock l;
  std::string s = arg(r, "ssid"), p = arg(r, "pass");
  if (s.empty() || s.length() > 32 || p.length() > 63) return fail(r, "bad network name or password");
  newSsid = s; newPass = p; wifiChange = true;       // done by webTick, after this answer has gone out
  event("Wi-Fi set to '%s'", s.c_str());
  return ok(r);
}
esp_err_t hWifiState(httpd_req_t *r) {
  char ip[20], ssid[34];
  bool up = wifiUp(ip, sizeof ip, ssid, sizeof ssid);
  std::string j;
  ap(j, "{\"ok\":1,\"up\":%d,\"ssid\":%s,\"ip\":\"%s\"}", up ? 1 : 0, jq(ssid).c_str(), up ? ip : "");
  return sendJson(r, j);
}
void openHomeWindow();                           // app_main.cpp
esp_err_t hHomeOpen(httpd_req_t *r) {            // let Apple Home (or Alexa) add this controller in the next 10 minutes
  openHomeWindow();
  return sendJson(r, "{\"ok\":1,\"code\":\"3497-011-2332\",\"qr\":\"MT:Y.K9042C00KA0648G00\"}");
}
#include "people.h"

uint32_t otaWindow = 0;                          // millis until which a firmware upload is accepted
esp_err_t hOtaOpen(httpd_req_t *r) { Lock l; otaWindow = millis() + 300000; event("firmware updates allowed for 5 minutes"); return ok(r); }
// Found by the app with Bonjour: _tilt._tcp, with this controller's id and address.
void bonjourTick(bool up) {
  static bool added = false;
  static char lastIp[20] = "", lastOwned = 2;
  if (!up) return;
  char ip[20], ssid[34];
  wifiUp(ip, sizeof ip, ssid, sizeof ssid);
  char own = owned() ? 1 : 0;
  if (added && !strcmp(ip, lastIp) && own == lastOwned) return;
  std::string id = ctrlId();
  mdns_txt_item_t txt[] = {{"id", id.c_str()}, {"ip", ip}, {"owned", own ? "1" : "0"}, {"name", cfg.name}};
  if (!added) added = mdns_service_add(nullptr, "_tilt", "_tcp", 80, txt, 4) == ESP_OK;
  else mdns_service_txt_set("_tilt", "_tcp", txt, 4);
  if (added) { strlcpy(lastIp, ip, sizeof lastIp); lastOwned = own; }
}
esp_err_t hOpenApi(httpd_req_t *r) { Lock l; openApi = argi(r, "v") ? 1 : 0; nvs.putUChar("openapi", openApi); return ok(r); }
// Every plain (not secured) request comes through here: once a phone is paired and the plain side is switched off,
// only the secured connection answers.
esp_err_t hGuard(httpd_req_t *r) {
  const Route *rt = (const Route *)r->user_ctx;
  if (const char *why = permit(rt, rt->uri, "", Caller{false, false, nullptr})) return plain(r, "401 Unauthorized", std::string("{\"err\":\"") + why + "\"}");
  return rt->fn(r);
}

esp_err_t hRoot(httpd_req_t *r);
esp_err_t hUpdate(httpd_req_t *r);
const Route routes[] = {
  {"/", HTTP_GET, hRoot}, {"/api/s", HTTP_GET, hState}, {"/api/dev", HTTP_GET, hDev}, {"/api/cfg", HTTP_GET, hCfg}, {"/api/log", HTTP_GET, hLog},
  {"/api/hist", HTTP_GET, hHist}, {"/api/set", HTTP_GET, hSet}, {"/api/sched", HTTP_GET, hSched}, {"/api/go", HTTP_GET, hGo}, {"/api/stop", HTTP_GET, hStop},
  {"/api/jog", HTTP_GET, hJog}, {"/api/angle", HTTP_GET, hAngle}, {"/api/mark", HTTP_GET, hMark}, {"/api/reset", HTTP_GET, hReset}, {"/api/reboot", HTTP_GET, hReboot},
  {"/api/scan", HTTP_GET, hScan}, {"/api/wifi", HTTP_POST, hNotYet}, {"/api/awake", HTTP_GET, hAwake}, {"/api/sleepnow", HTTP_GET, hNotYet}, {"/api/update", HTTP_POST, hUpdate},
  {"/api/keep", HTTP_GET, hKeep}, {"/api/watch", HTTP_GET, hWatch}, {"/api/trace", HTTP_GET, hTrace},
  {"/api/setwifi", HTTP_GET, hSetWifi}, {"/api/wifistate", HTTP_GET, hWifiState}, {"/api/homeopen", HTTP_GET, hHomeOpen},
  {"/api/keys", HTTP_GET, hKeys}, {"/api/revoke", HTTP_GET, hRevoke}, {"/api/approve", HTTP_GET, hApprove}, {"/api/keyname", HTTP_GET, hKeyName}, {"/api/makeowner", HTTP_GET, hMakeOwner}, {"/api/openapi", HTTP_GET, hOpenApi}, {"/api/otaopen", HTTP_GET, hOtaOpen},
};
const int routeCount = sizeof routes / sizeof routes[0];

void webBegin() {
  secBegin();
  sxLoad();
  openApi = nvs.getUChar("openapi", 1);
  temperature_sensor_config_t tc = TEMPERATURE_SENSOR_CONFIG_DEFAULT(10, 80);
  if (temperature_sensor_install(&tc, &tsens) == ESP_OK) temperature_sensor_enable(tsens); else tsens = nullptr;
  const esp_partition_t *part = esp_ota_get_running_partition();
  esp_image_metadata_t md = {};
  esp_partition_pos_t pos = {part->address, part->size};
  if (esp_image_get_metadata(&pos, &md) == ESP_OK) appSize = md.image_len;
  esp_ota_img_states_t st;
  otaPending = esp_ota_get_state_partition(part, &st) == ESP_OK && st == ESP_OTA_IMG_PENDING_VERIFY;

  httpd_config_t hc = HTTPD_DEFAULT_CONFIG();
  hc.max_uri_handlers = 48;
  hc.stack_size = 8192;
  hc.lru_purge_enable = true;
  hc.recv_wait_timeout = 15;
  httpd_handle_t srv = nullptr;
  if (httpd_start(&srv, &hc) != ESP_OK) { event("web server did not start"); return; }
  for (int i = 0; i < routeCount; i++) {
    httpd_uri_t u = {};
    u.uri = routes[i].uri; u.method = routes[i].m; u.handler = hGuard; u.user_ctx = (void *)&routes[i];
    httpd_register_uri_handler(srv, &u);
  }
  httpd_uri_t x[] = {{"/x/hello", HTTP_GET, hHello, nullptr}, {"/x/pair", HTTP_POST, hPair, nullptr}, {"/x/ask", HTTP_POST, hAsk, nullptr}, {"/x/recover", HTTP_POST, hRecover, nullptr}, {"/x/recstate", HTTP_GET, hRecoverState, nullptr}, {"/x", HTTP_POST, hSecure, nullptr}};
  for (auto &u : x) httpd_register_uri_handler(srv, &u);
}

// Once a second, from the blinds task (the lock is held).
void webTick() {
  static uint32_t upSince = 0;
  uint32_t now = millis();
  wifi_ap_record_t apr;
  bool up = esp_wifi_sta_get_ap_info(&apr) == ESP_OK;
  if (up && !upSince) { upSince = now ? now : 1; esp_wifi_set_ps(WIFI_PS_MIN_MODEM); }   // radio dozes between beacons
  if (!up) upSince = 0;
  bonjourTick(up);
  if (otaPending) {
    if (up && now - upSince > 600000) {            // nobody said keep or drop: after ten minutes on Wi-Fi, keep it
      esp_ota_mark_app_valid_cancel_rollback();
      otaPending = false;
      stats.otaOk++;
      statsSave();
      event("new firmware %s confirmed", FW_VERSION);
    } else if (!up && now > 120000) {
      event("new firmware could not join Wi-Fi: going back");
      vTaskDelay(pdMS_TO_TICKS(200));
      esp_ota_mark_app_invalid_rollback_and_reboot();
    }
  }
  if (scanWanted) { scanRun(); scanWanted = false; }
  if (wifiChange) {                              // a new network from the app
    wifiChange = false;
    wifi_config_t wc = {};
    strlcpy((char *)wc.sta.ssid, newSsid.c_str(), sizeof wc.sta.ssid);
    strlcpy((char *)wc.sta.password, newPass.c_str(), sizeof wc.sta.password);
    newPass.clear();
    esp_wifi_set_storage(WIFI_STORAGE_FLASH);
    esp_wifi_disconnect();
    esp_wifi_set_config(WIFI_IF_STA, &wc);
    esp_wifi_connect();
  }
  schedRun();
  rampTick();
  recoverTick();
  static uint32_t lastHist = 0;
  uint32_t ep = time(nullptr);
  if (lastHist > ep || ep - lastHist >= 3600) { lastHist = ep; histPush(vbatRest); }
  static bool wasPowered = powered;
  if (wasPowered != powered) { wasPowered = powered; event(powered ? "input power connected (%.2f V)" : "on battery (%.2f V)", powered ? vin : vbatRest); }
  if (restartSoon) { vTaskDelay(pdMS_TO_TICKS(600)); for (int i = 0; i < PORTS; i++) { motorRaw(i, 0, 0); digitalWrite(P_EN[i], LOW); } esp_restart(); }
}
