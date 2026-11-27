// The JSON interface the Tilt app talks to, on ESP-IDF's HTTP server: the pages, the routes, and webTick.
// Schedules, Scenes, firmware upload and the people handlers live in their own files, included here at the top.
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
#include "scenes.h"
#include "update.h"
#include "ota.h"                                 // Trial
#include "people.h"

#define FW_VERSION "2.3.0-dev36"
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
// The status the app polls (/api/s). Short keys, kept short on purpose (it goes over Thread often):
//   t epoch, tok clock set, up seconds running, batt {v rest volts, pct, st charge state, vin, low, src Power source}, closeUp, sync
//   follow mode, par move at the same time, mv the blind moving (-1 none), log event count, hk in a Matter home,
//   asks join requests waiting, hkey knows the Tilt Hub's key, me caller is an owner, gentle a slow move running,
//   topic iCloud notice topic; b[] per blind: hid hidden, pres plugged in, seen checked, cal marks set, tilt, tgt
//   target, mov moving, q queued, fav, ang raw sensor angle, last what it last did.
esp_err_t hState(httpd_req_t *r) {
  Lock l;
  std::string j;
  j.reserve(1200);
  ap(j, "{\"v\":\"" FW_VERSION "\",\"name\":%s,\"t\":%lu,\"tok\":%d,\"up\":%lu", jq(cfg.name).c_str(), (unsigned long)time(nullptr), timeValid() ? 1 : 0, (unsigned long)(millis() / 1000));
  ap(j, ",\"batt\":{\"v\":%.2f,\"pct\":%d,\"st\":\"%s\",\"vin\":%.2f,\"low\":%d,\"src\":%d}", vbatRest, battPercent(vbatRest), chargeState(), vin, battOkToMove() ? 0 : 1, powerSource());   // low: 1 = below the motor cut-off, no moves; src: Power source (logic.h)
  ap(j, ",\"pw\":{\"mode\":1,\"sleepIn\":-1,\"checkin\":0},\"closeUp\":%d,\"sync\":%d,\"par\":%d,\"ap\":0,\"mv\":%d,\"log\":%lu,\"hk\":%d,\"asks\":%d,\"hkey\":%d,\"me\":%d,\"gentle\":%d,\"topic\":\"%s\",\"b\":[", cfg.closeUp, syncMode, parMode, firstMoving(), (unsigned long)logSeq, homesPaired(), asksWaiting(), hubSlot() >= 0 ? 1 : 0, secClient >= 0 ? keys[secClient].role : 1, rampAny() ? 1 : 0, secClient >= 0 ? hexOf(cloudTopic, 16).c_str() : "");
  for (int i = 0; i < PORTS; i++) {
    BlindCfg &c = cfg.b[i];
    ap(j, "%s{\"name\":%s,\"hid\":%d,\"pres\":%d,\"seen\":%d,\"cal\":%d,\"tilt\":%s,\"tgt\":%s,\"mov\":%d,\"q\":%d,\"fav\":%d,\"ang\":%s,\"last\":%s}", i ? "," : "",
       jq(c.name).c_str(), c.hidden, bs[i].present ? 1 : 0, bs[i].seen ? 1 : 0, calibrated(i) ? 1 : 0, jn(blindNow(i).tilt, 1).c_str(),
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
  ap(j, ",\"tune\":{\"grace\":%d,\"stall\":%d,\"deg10\":%d,\"max\":%d,\"lead10\":%d},\"mv\":{\"kind\":%d,\"port\":%d,\"st\":%d,\"nudges\":%d,\"live\":%s},\"p\":[", tune.graceMs, tune.stallMs, tune.stallDeg10, tune.moveMaxS, leadMax10, dm.kind, dm.port, dm.st, dm.nudges, jn(dm.live, 1).c_str());
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
  for (int i = 0; i < SCHEDS; i++) {
    const Sched &s = cfg.sched[i];
    const LightLatch &l = lite.l[i];             // the Light trigger's last fire (schedules.h)
    sl[i] = {s.on, s.days, s.mask, s.minute, s.tilt, sx.x[i].kind, sx.x[i].off, sx.x[i].ramp, sx.x[i].gid, l.day ? l.at : 0, l.day ? (int)l.why : 0};
  }
  time_t now = time(nullptr);
  WireCfg c = {cfg.name, cfg.closeUp, syncMode, parMode, cfg.txPower, cfg.tz, cfg.tzName, hkSeparate, b, PORTS, sl, SCHEDS, sx.lat, sx.lon, sunEvent(now, true), sunEvent(now, false),
               panelSeen() ? 1 : 0};
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
#ifdef TILT_DEVLOG
// The dev power log: one row per hour, oldest first. rest/vin/vinAvg in volts, on = minutes on input power (USB or
// strong sun, enough to count as powered), lit = minutes the solar input saw any light, motor = seconds.
esp_err_t hPowerLog(httpd_req_t *r) {
  Lock l;
  std::string j = "{\"cols\":[\"at\",\"rest\",\"vin\",\"on\",\"temp\",\"motor\",\"flags\",\"lit\",\"vinAvg\"],\"rows\":[";
  bool any = false;
  for (int i = 0; i < PLOG_N; i++) {
    const PowerHour &h = plog[i];
    if (!h.at) continue;
    ap(j, "%s[%lu,%.2f,%.2f,%u,%d,%u,%u,%u,%.2f]", any ? "," : "", (unsigned long)h.at, 2.5f + h.rest / 100.0f, h.vinMax / 40.0f,
       h.poweredMin, h.tempC, h.motorS, h.flags, h.litMin, h.vinAvg / 40.0f);
    any = true;
  }
  j += "]}";
  return sendJson(r, j);
}
// The dev light log (store.h): the input by the minute, 2 hours either side of each sunrise and sunset, oldest first.
// start: epoch of the first minute; rise: 1 sunrise, 0 sunset; v: volts * 40 per minute, 0 = no reading. The window
// being filled now comes last.
esp_err_t hLightLog(httpd_req_t *r) {
  Lock l;
  std::string j;
  j.reserve((LLOG_N + 1) * (LLOG_MIN * 4 + 40) + 40);
  j += "{\"scale\":40,\"w\":[";
  bool any = false;
  for (int i = 0; i <= LLOG_N; i++) {
    const LightWin &w = i < LLOG_N ? llog[i] : llCur;
    if (!w.start) continue;
    ap(j, "%s{\"start\":%lu,\"rise\":%d,\"v\":[", any ? "," : "", (unsigned long)w.start, w.rise);
    for (int k = 0; k < LLOG_MIN; k++) ap(j, "%s%d", k ? "," : "", w.v[k]);
    j += "]}";
    any = true;
  }
  j += "]}";
  return sendJson(r, j);
}
#endif
esp_err_t hSet(httpd_req_t *r) {
  Lock l;
  std::string k = arg(r, "k"), v = arg(r, "v");
  int n = atoi(v.c_str());
  Settings c = cfg;                              // changed here, then put in place by cfgApply (motion.h)
  if (k == "name") {                             // as typed (UTF-8), not cleanText: see wire.h keptName
    strlcpy(c.name, keptName(v, sizeof c.name - 1).c_str(), sizeof c.name);
    if (!c.name[0]) strlcpy(c.name, "Blinds", sizeof c.name);   // the default (store.h)
  }
  else if (k == "closeUp") c.closeUp = n ? 1 : 0;
  else if (k == "loc") { float la = NAN, lo = NAN; if (sscanf(v.c_str(), "%f,%f", &la, &lo) != 2 || fabsf(la) > 90 || fabsf(lo) > 180) return fail(r, "bad place"); sx.lat = la; sx.lon = lo; sxSave(); }
  else if (k == "sync") { syncMode = n ? 1 : 0; syncSave(); hand.reset(); }   // start fresh: no following of old turns
  else if (k == "par") { parMode = n ? 1 : 0; syncSave(); }
  // Home layout: the restart is only for the controller's own Matter endpoints (made at a start, app_main.cpp). On a
  // Tilt Hub, Apple Home's tiles follow sep in the status at once, without it.
  else if (k == "hksep") { hkSeparate = n ? 1 : 0; nvs.putUChar("hksep", hkSeparate); restartSoon = true; }
  else if (k == "tune.grace") { tune.graceMs = constrain(n, 0, 30000); tuneSave(); }
  else if (k == "tune.stall") { tune.stallMs = constrain(n, 200, 10000); tuneSave(); }
  else if (k == "tune.deg10") { tune.stallDeg10 = constrain(n, 1, 100); tuneSave(); }
  else if (k == "tune.max") { tune.moveMaxS = constrain(n, 5, 600); tuneSave(); }
  else if (k == "tune.lead10") { leadMax10 = constrain(n, 20, 250); nvs.putUChar("lmax", leadMax10); }   // 2..25 degrees
  else if (k == "battMode" || k == "checkin" || k == "tx") return fail(r, "not in this version");
  else if (k == "tz") {
    if (!zoneOk(v.c_str(), sizeof c.tz)) return fail(r, "bad time zone");
    strlcpy(c.tz, v.c_str(), sizeof c.tz);       // used once cfgApply keeps it (motion.h)
    cleanText(c.tzName, sizeof c.tzName, arg(r, "n"));
  } else if (k.length() >= 4 && k[0] == 'b' && k[2] == '.') {
    int p = k[1] - '0';
    if (p < 0 || p >= PORTS) return fail(r, "no such blind");
    std::string f = k.substr(3);
    BlindCfg &b = c.b[p];
    if (f == "name") {                           // as typed (UTF-8): see wire.h keptName
      strlcpy(b.name, keptName(v, sizeof b.name - 1).c_str(), sizeof b.name);
      if (!b.name[0]) snprintf(b.name, sizeof b.name, "Blind %d", p + 1);
    }
    else if (f == "speed") b.speed = constrain(n, 50, 100);
    else if (f == "fav") b.fav = constrain(n, -100, 100);
    else if (f == "hid") b.hidden = n ? 1 : 0;   // own endpoints: next start, no restart here; Tilt Hub tiles: at once
    else if (f == "sign") b.motSign = n < 0 ? -1 : 1;   // a move on this blind is stopped first (cfgApply)
    else return fail(r, "unknown setting");
  } else return fail(r, "unknown setting");
  cfgApply(c);
  return ok(r);
}
esp_err_t hSched(httpd_req_t *r) {
  Lock l;
  int i = argi(r, "i");
  if (i < 0 || i >= SCHEDS) return fail(r, "no such schedule");
  WireSlot w = slotOfArgs([&](const char *k) { return arg(r, k); }, PORTS);
  Settings c = cfg;
  Sched &s = c.sched[i];
  s.on = w.on; s.days = w.days; s.mask = w.mask; s.minute = w.min; s.tilt = w.tilt;
  // Another Schedule in the slot starts with no Light trigger fire; an edit of the same one keeps today's (logic.h).
  if (!lightLatchKept(sx.x[i].gid, sx.x[i].kind, w.gid, w.kind)) { memset(&lite.l[i], 0, sizeof lite.l[i]); liteSave(); }
  sx.x[i] = {(uint8_t)w.kind, (uint8_t)w.ramp, (int16_t)w.off, w.gid};
  sxSave();
  cfgApply(c);
  lastSched = time(nullptr);
  return ok(r);
}
esp_err_t hGo(httpd_req_t *r) {
  Lock l;
  std::string b = arg(r, "b"), to = arg(r, "to");
  int one = b == "all" ? -1 : constrain(atoi(b.c_str()), 0, PORTS - 1);
  // ramp=N: gently, taking N minutes (the same slow move a schedule can make), instead of going straight there
  MoveAsk a = moveAsk(FROM_APP, one, NAN, (uint32_t)constrain(argi(r, "ramp"), 0, 60) * 60000u);
  float tOne = one < 0 ? NAN : to.length() ? tiltWord(one, to) : (float)atof(arg(r, "t").c_str());
  for (int p = 0; p < PORTS; p++) a.tilt[p] = one >= 0 ? tOne : tiltWord(p, to);   // the others go where the named one goes
  MoveResult m = moveBlinds(a);
  if (a.gentleMs && m.started) event("gentle move started (%d min)", (int)(a.gentleMs / 60000));
  return m.started ? ok(r) : fail(r, m.why);
}
esp_err_t hStop(httpd_req_t *r) { Lock l; moveStop(); return ok(r); }
esp_err_t hJog(httpd_req_t *r) { Lock l; return done(r, jog(argi(r, "b"), argi(r, "d") < 0 ? -1 : 1, constrain(argi(r, "p"), 30, 100), argi(r, "ms"), argi(r, "seek") == 1)); }
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
  else if (w == "all") { Settings c; cfgDefaultsOf(c); cfgApply(c); }   // a move on a blind whose Marks go is stopped first
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
  hand.setupOpen(p, millis());                   // a setup screen is open: turning by hand is expected, the others stay put
  return ok(r);
}
esp_err_t hTrace(httpd_req_t *r) {              // the recording of the last move
  std::string j;
  {
    Lock l;
    j.reserve(traceN * 14 + 80);
    // In pages (?from=) of 300 points (about 4 KB), so a whole recording (up to 1500) is not one huge answer.
    int from = constrain(argi(r, "from"), 0, traceN), to = std::min(traceN, from + 300);
    ap(j, "{\"n\":%d,\"from\":%d,\"moving\":%d,\"p\":[", traceN, from, moving() ? 1 : 0);
    for (int i = from; i < to; i++) ap(j, "%s[%u,%u,%u]", i > from ? "," : "", trace[i].t, trace[i].a, trace[i].st);
    j += "]}";
  }
  return sendJson(r, j);
}
esp_err_t hAwake(httpd_req_t *r) { Lock l; keepAwakeUntil = millis() + (uint32_t)constrain(argi(r, "min"), 0, 720) * 60000; return ok(r); }
// Keep the firmware on trial: it is the one this controller starts from from now on (hKeep, and trialTick below).
void trialKeep() {
  if (!otaPending) return;
  esp_ota_mark_app_valid_cancel_rollback();
  otaPending = false;
  stats.otaOk++;
  statsSave();
  event("new firmware %s confirmed", FW_VERSION);
}
// Keep the firmware that is on trial (sent by tools/flash_matter.sh once it has checked the board).
esp_err_t hKeep(httpd_req_t *r) {
  Lock l;
  trialKeep();
  return ok(r);
}

// ---- who may use this controller (the rules: sec.h)
std::string ctrlId() { uint8_t m[6] = {0}; esp_read_mac(m, ESP_MAC_WIFI_STA); return hexOf(m, 6); }
bool hubOk();                                    // hub_link.h
void hubTick();
std::string helloJson() {                       // from the hub task and Bluetooth, which do not hold mx: it is taken here
  std::string j;
  // img: the running firmware's SHA-256 (as esptool shows it), so an update can be a patch made from exactly it.
  static std::string img;
  if (img.empty()) { uint8_t h[32]; if (esp_partition_get_sha256(esp_ota_get_running_partition(), h) == ESP_OK) img = hexOf(h, 32); }
  std::string name;
  bool own;
  { QuietLock l; name = jq(cfg.name); own = owned(); }
  ap(j, "{\"id\":\"%s\",\"name\":%s,\"fw\":\"" FW_VERSION "\",\"img\":\"%s\",\"boot\":\"%s\",\"owned\":%d,\"home\":%d,\"net\":\"thread\",\"hub\":%d,\"proto\":%d}", ctrlId().c_str(),
     name.c_str(), img.c_str(), hexOf(bootId, 4).c_str(), own ? 1 : 0, homesPaired() ? 1 : 0, hubOk() ? 1 : 0, LINK_PROTO);
  return j;
}
void openHomeWindow();                           // app_main.cpp
std::string homeCodeJson();                      // home_code.h
esp_err_t hHomeOpen(httpd_req_t *r) {            // let Apple Home (or Alexa) add this controller in the next 10 minutes
  openHomeWindow();
  return sendJson(r, homeCodeJson());
}
esp_err_t hOtaOpen(httpd_req_t *r) { Lock l; otaWindow = uptimeMs() + OTA_WINDOW_MS; event("firmware updates allowed for 5 minutes"); return ok(r); }
esp_err_t hHome(httpd_req_t *r);                // hub_link.h
esp_err_t hHubJoin(httpd_req_t *r);
esp_err_t hSwapFw(httpd_req_t *r);
esp_err_t hHubKey(httpd_req_t *r);
esp_err_t hHubNet(httpd_req_t *r);
esp_err_t hFactory(httpd_req_t *r);
esp_err_t hBackup(httpd_req_t *r);
esp_err_t hRestore(httpd_req_t *r);
#define TILT_ROUTE(p, fn, w) {p, fn, w},
const Route routes[] = { TILT_ROUTES(TILT_ROUTE) };      // the commands and who may send each: routes.h
#undef TILT_ROUTE
const int routeCount = sizeof routes / sizeof routes[0];

// The chip's temperature sensor, for the developer page. (No web server: everything comes over Bluetooth or through
// the Tilt Hub, hub_link.h.)
void webBegin() {
  temperature_sensor_config_t tc = TEMPERATURE_SENSOR_CONFIG_DEFAULT(10, 80);
  if (temperature_sensor_install(&tc, &tsens) == ESP_OK) temperature_sensor_enable(tsens); else tsens = nullptr;
}

extern volatile uint32_t hubLinkSeen;            // hub_link.h
// Restart (or go back to the firmware before, rollback) once the last answers have gone out. From the blinds task,
// which holds mx: mx is let go for the wait, so no other task waits behind it. A restart stops and holds the motors
// first (no handler may start one meanwhile). A rollback leaves the moves alone, as before: if going back is refused
// (no valid firmware in the other slot), it returns why, and the controller carries on as it was, moves included.
esp_err_t restartNow(bool rollback, uint32_t waitMs) {
  if (!rollback) {
    motorsHeld = true;
    rampCancel();
    for (int i = 0; i < PORTS; i++) {
      bs[i].queued = false;
      if (movingPort(i)) { Use u(i); stopNow(MVX, tilters[i], "stopped: restarting"); }
      motorRaw(i, 0, 0); digitalWrite(P_EN[i], LOW);
    }
  }
  xSemaphoreGive(mx);
  vTaskDelay(pdMS_TO_TICKS(waitMs));
  if (!rollback) esp_restart();
  esp_err_t e = esp_ota_mark_app_invalid_rollback_and_reboot();  // returns only if refused
  xSemaphoreTake(mx, portMAX_DELAY);
  return e;
}
// A new firmware is on trial until Thread to the Tilt Hub has worked for a minute (ota.h Trial). Going back refused:
// it is asked and logged once, then the controller stays on this firmware, still on trial (it can still be kept).
static void trialTick(uint32_t now) {
  static Trial trial;
  TrialVerdict v = trial.tick(now, trialLinkUp(hubOk(), hubLinkSeen, now), hubJoined());
  if (!otaPending) return;
  if (v == TRIAL_KEEP) trialKeep();
  else if (v == TRIAL_ROLLBACK) {
    event("new firmware could not reach the Tilt Hub: going back");
    esp_err_t e = restartNow(true, 200);
    trial.rollbackRefused();
    event("cannot go back (%s): staying on this firmware", esp_err_to_name(e));
  }
}
// Once an hour: the battery history (and, on a developer build, the power log's temperature).
static void histTick() {
  static uint32_t lastHist = 0;
  uint32_t ep = time(nullptr);
  if (lastHist > ep || ep - lastHist >= 3600) {
    bool first = lastHist == 0;
    lastHist = ep;
    histPush(vbatRest);
#ifdef TILT_DEVLOG
    if (!first) { float t = 0; if (tsens) temperature_sensor_get_celsius(tsens, &t); plogPush(ep, vbatRest, t); }
#else
    (void)first;
#endif
  }
}
#ifdef TILT_DEVLOG
static void devlogTick() {
  static uint32_t lastPl = 0;
  uint32_t nowMs = millis();
  if (!lastPl && otaPending) plogAcc.flags |= 2;   // this start is new firmware on trial
  if (lastPl) plogTick(vin, powered, nowMs - lastPl);
  lastPl = nowMs ? nowMs : 1;
}
#endif
static void powerTick() {                        // input power connected or gone: a line in the log
  static bool wasPowered = powered;
  if (wasPowered != powered) { wasPowered = powered; event(powered ? "input power connected (%.2f V)" : "on battery (%.2f V)", powered ? vin : vbatRest); }
}
static void restartTick() {                      // asked for (an update, a setting): motors off and held first
  if (restartSoon) restartNow(false, 600);
}
// Once a second, from the blinds task (the lock is held).
void webTick() {
  trialTick(millis());
  hubTick();
  schedRun();
  rampTick();
  recoverTick();
  histTick();
#ifdef TILT_DEVLOG
  devlogTick();
#endif
  powerTick();
  restartTick();
}
