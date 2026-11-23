// The JSON interface the Tilt app talks to, on ESP-IDF's HTTP server: the pages, the routes, and webTick.
// Schedules, firmware upload and the people handlers live in their own files, included here at the top.
#pragma once
#include <esp_http_server.h>
#include <esp_ota_ops.h>
#include <esp_netif.h>
#include <esp_mac.h>
#include <esp_chip_info.h>
#include <esp_system.h>
#include <driver/temperature_sensor.h>
#include "config.h"
#include "motion.h"
#include "sec.h"
#include "wire.h"                                // the wire contract for /api/cfg and Schedule slots
#include "api.h"                                 // the reply helpers and Lock
#include "schedules.h"
#include "update.h"
#include "people.h"

#define FW_VERSION "2.3.0-dev15"
int homesPaired();                       // app_main.cpp
static temperature_sensor_handle_t tsens = nullptr;

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

std::string hubThreadJson();                     // hub_link.h
bool hubJoined();
// ---- pages
esp_err_t hRoot(httpd_req_t *r) {
  lastWeb = millis() ? millis() : 1;
  httpd_resp_set_type(r, "text/plain");           // the built-in web page is gone: the Tilt app is the way in
  return httpd_resp_sendstr(r, "Tilt blinds controller. Use the Tilt app.");
}
// The status the app polls (/api/s). Short keys, kept short on purpose (it goes over Thread often):
//   t epoch, tok clock set, up seconds running, batt {v rest volts, pct, st charge state, vin, low}, closeUp, sync
//   follow mode, par move at the same time, mv the blind moving (-1 none), log event count, hk in a Matter home,
//   asks join requests waiting, hkey knows the Tilt Hub's key, me caller is an owner, gentle a slow move running,
//   topic iCloud notice topic; b[] per blind: hid hidden, pres plugged in, seen checked, cal marks set, tilt, tgt
//   target, mov moving, q queued, fav, ang raw sensor angle, last what it last did.
esp_err_t hState(httpd_req_t *r) {
  Lock l;
  std::string j;
  j.reserve(1200);
  ap(j, "{\"v\":\"" FW_VERSION "\",\"name\":%s,\"t\":%lu,\"tok\":%d,\"up\":%lu", jq(cfg.name).c_str(), (unsigned long)time(nullptr), timeValid() ? 1 : 0, (unsigned long)(millis() / 1000));
  ap(j, ",\"batt\":{\"v\":%.2f,\"pct\":%d,\"st\":\"%s\",\"vin\":%.2f,\"low\":%d}", vbatRest, battPercent(vbatRest), chargeState(), vin, battOkToMove() ? 0 : 1);   // low: 1 = below the motor cut-off, no moves
  ap(j, ",\"pw\":{\"mode\":1,\"sleepIn\":-1,\"checkin\":0},\"closeUp\":%d,\"sync\":%d,\"par\":%d,\"ap\":0,\"mv\":%d,\"log\":%lu,\"hk\":%d,\"asks\":%d,\"hkey\":%d,\"me\":%d,\"gentle\":%d,\"topic\":\"%s\",\"b\":[", cfg.closeUp, syncMode, parMode, firstMoving(), (unsigned long)logSeq, homesPaired(), asksWaiting(), hubSlot() >= 0 ? 1 : 0, secClient >= 0 ? keys[secClient].role : 1, rampAny() ? 1 : 0, secClient >= 0 ? hexOf(cloudTopic, 16).c_str() : "");
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
  ap(j, "{\"sys\":{\"fw\":\"" FW_VERSION "\",\"build\":\"" __DATE__ " " __TIME__ "\",\"core\":\"esp-matter 1.5\",\"idf\":%s,\"chip\":\"ESP32-C6\",\"rev\":%d,\"mhz\":160,\"flash\":4194304", jq(esp_get_idf_version()).c_str(), ci.revision);
  ap(j, ",\"app\":%lu,\"appMax\":%lu,\"part\":%s,\"md5\":\"\",\"heap\":%lu,\"heapMin\":%lu,\"temp\":%.1f,\"rst\":%s,\"up\":%lu,\"pending\":%d", (unsigned long)appSize, (unsigned long)(part ? part->size : 0),
     jq(part ? part->label : "?").c_str(), (unsigned long)esp_get_free_heap_size(), (unsigned long)esp_get_minimum_free_heap_size(), temp, jq(resetReason()).c_str(), (unsigned long)(millis() / 1000), otaPending ? 1 : 0);
  ap(j, ",\"mac\":\"%02X:%02X:%02X:%02X:%02X:%02X\"}", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  ap(j, ",\"thread\":%s", hubThreadJson().c_str());
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

// ---- who may use this controller (the rules and openApi: sec.h)
std::string ctrlId() { uint8_t m[6] = {0}; esp_read_mac(m, ESP_MAC_WIFI_STA); return hexOf(m, 6); }
bool hubOk();                                    // hub_link.h
void hubTick();
std::string helloJson() {
  std::string j;
  // img: the running firmware's SHA-256 (as esptool shows it), so an update can be a patch made from exactly it.
  static std::string img;
  if (img.empty()) { uint8_t h[32]; if (esp_partition_get_sha256(esp_ota_get_running_partition(), h) == ESP_OK) img = hexOf(h, 32); }
  ap(j, "{\"id\":\"%s\",\"name\":%s,\"fw\":\"" FW_VERSION "\",\"img\":\"%s\",\"boot\":\"%s\",\"owned\":%d,\"open\":%d,\"home\":%d,\"net\":\"thread\",\"hub\":%d}", ctrlId().c_str(),
     jq(cfg.name).c_str(), img.c_str(), hexOf(bootId, 4).c_str(), owned() ? 1 : 0, openApi, homesPaired() ? 1 : 0, hubOk() ? 1 : 0);
  return j;
}
esp_err_t hHello(httpd_req_t *r) { return plain(r, "200 OK", helloJson()); }
void openHomeWindow();                           // app_main.cpp
std::string homeCodeJson();                      // home_code.h
esp_err_t hHomeOpen(httpd_req_t *r) {            // let Apple Home (or Alexa) add this controller in the next 10 minutes
  openHomeWindow();
  return sendJson(r, homeCodeJson());
}
esp_err_t hOtaOpen(httpd_req_t *r) { Lock l; otaWindow = millis() + 300000; event("firmware updates allowed for 5 minutes"); return ok(r); }
esp_err_t hOpenApi(httpd_req_t *r) { Lock l; openApi = argi(r, "v") ? 1 : 0; nvs.putUChar("plainopen", openApi); return ok(r); }
// Every plain (not secured) request comes through here: once a phone is paired and the plain side is switched off,
// only the secured connection answers.
esp_err_t hGuard(httpd_req_t *r) {
  const Route *rt = (const Route *)r->user_ctx;
  if (const char *why = permit(rt, rt->uri, "", Caller{false, false, nullptr})) return plain(r, "401 Unauthorized", std::string("{\"err\":\"") + why + "\"}");
  return rt->fn(r);
}

esp_err_t hRoot(httpd_req_t *r);
esp_err_t hHome(httpd_req_t *r);                // hub_link.h
esp_err_t hHubJoin(httpd_req_t *r);
esp_err_t hSwapFw(httpd_req_t *r);
esp_err_t hHubKey(httpd_req_t *r);
esp_err_t hHubNet(httpd_req_t *r);
esp_err_t hFactory(httpd_req_t *r);
esp_err_t hBackup(httpd_req_t *r);
esp_err_t hRestore(httpd_req_t *r);
const Route routes[] = {
  {"/", HTTP_GET, hRoot}, {"/api/s", HTTP_GET, hState}, {"/api/dev", HTTP_GET, hDev}, {"/api/cfg", HTTP_GET, hCfg}, {"/api/log", HTTP_GET, hLog},
  {"/api/hist", HTTP_GET, hHist}, {"/api/set", HTTP_GET, hSet}, {"/api/sched", HTTP_GET, hSched}, {"/api/go", HTTP_GET, hGo}, {"/api/stop", HTTP_GET, hStop},
  {"/api/jog", HTTP_GET, hJog}, {"/api/angle", HTTP_GET, hAngle}, {"/api/mark", HTTP_GET, hMark}, {"/api/reset", HTTP_GET, hReset}, {"/api/reboot", HTTP_GET, hReboot},
  {"/api/awake", HTTP_GET, hAwake},
  {"/api/keep", HTTP_GET, hKeep}, {"/api/watch", HTTP_GET, hWatch}, {"/api/trace", HTTP_GET, hTrace},
  {"/api/homeopen", HTTP_GET, hHomeOpen},
  {"/api/keys", HTTP_GET, hKeys}, {"/api/revoke", HTTP_GET, hRevoke}, {"/api/approve", HTTP_GET, hApprove}, {"/api/keyname", HTTP_GET, hKeyName}, {"/api/makeowner", HTTP_GET, hMakeOwner}, {"/api/openapi", HTTP_GET, hOpenApi}, {"/api/otaopen", HTTP_GET, hOtaOpen},
  {"/api/home", HTTP_GET, hHome}, {"/api/hubjoin", HTTP_GET, hHubJoin}, {"/api/swapfw", HTTP_GET, hSwapFw}, {"/api/hubkey", HTTP_GET, hHubKey},
  {"/api/hubnet", HTTP_GET, hHubNet}, {"/api/factory", HTTP_GET, hFactory},
  {"/api/backup", HTTP_GET, hBackup}, {"/api/restore", HTTP_GET, hRestore},
};
const int routeCount = sizeof routes / sizeof routes[0];

// The chip's temperature sensor, for the developer page. (No web server: everything comes over Bluetooth or through
// the Tilt Hub, hub_link.h.)
void webBegin() {
  temperature_sensor_config_t tc = TEMPERATURE_SENSOR_CONFIG_DEFAULT(10, 80);
  if (temperature_sensor_install(&tc, &tsens) == ESP_OK) temperature_sensor_enable(tsens); else tsens = nullptr;
}

extern volatile uint32_t hubLinkSeen;            // hub_link.h
// Once a second, from the blinds task (the lock is held).
void webTick() {
  uint32_t now = millis();
  // A new firmware is on trial until Thread to the Tilt Hub has worked for a minute.
  static uint32_t hubSince = 0;
  bool linkUp = hubOk() || (hubLinkSeen && now - hubLinkSeen < 120000);
  if (linkUp && !hubSince) hubSince = now ? now : 1;
  if (!linkUp) hubSince = 0;
  hubTick();
  if (otaPending) {
    if (hubSince && now - hubSince > 60000) {
      esp_ota_mark_app_valid_cancel_rollback();
      otaPending = false;
      stats.otaOk++;
      statsSave();
      event("new firmware %s confirmed", FW_VERSION);
    } else if (!hubSince && now > 300000 && hubJoined()) {   // it has a hub to reach (setup is done) and did not
      event("new firmware could not reach the Tilt Hub: going back");
      vTaskDelay(pdMS_TO_TICKS(200));
      esp_ota_mark_app_invalid_rollback_and_reboot();
    }
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
