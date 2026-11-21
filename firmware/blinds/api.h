// The web app and its JSON interface.
#pragma once
#include <WebServer.h>
#include <Update.h>
#include "sleep.h"
#include "ui.h"

WebServer web(80);
bool updAuth = false;

String jq(const char *s) {                      // a JSON string, quoted and escaped
  String o = "\"";
  for (; *s; s++) {
    if (*s == '"' || *s == '\\') { o += '\\'; o += *s; }
    else if ((unsigned char)*s >= 32) o += *s;
  }
  return o + "\"";
}
String jn(float v, int dp) { return isnan(v) ? String("null") : String(v, dp); }
void ok() { web.send(200, "application/json", "{\"ok\":1}"); }
void fail(const char *e) { web.send(200, "application/json", String("{\"ok\":0,\"err\":") + jq(e) + "}"); }
void done(const char *e) { if (e) fail(e); else ok(); }
void touch() { lastActivity = millis(); if (!lastActivity) lastActivity = 1; }

float tiltWord(int p, const String &to) {
  if (to == "open") return 0;
  if (to == "up") return 100;
  if (to == "down") return -100;
  if (to == "close") return cfg.closeUp ? 100 : -100;
  if (to == "fav") return cfg.b[p].fav;
  return NAN;
}

void hState() {
  touch();
  String j;
  j.reserve(1100);
  j += "{\"v\":\"" FW_VERSION "\",\"name\":"; j += jq(cfg.name);
  j += ",\"t\":"; j += (uint32_t)time(nullptr);
  j += ",\"tok\":"; j += timeValid() ? 1 : 0;
  j += ",\"up\":"; j += millis() / 1000;
  j += ",\"batt\":{\"v\":"; j += String(vbatRest, 2);
  j += ",\"pct\":"; j += battPercent(vbatRest);
  j += ",\"st\":\""; j += chargeState();
  j += "\",\"vin\":"; j += String(vin, 2);
  j += ",\"low\":"; j += battOkToMove() ? 0 : 1;
  j += "},\"pw\":{\"mode\":"; j += cfg.battMode;
  j += ",\"sleepIn\":"; j += sleepIn;
  j += ",\"checkin\":"; j += cfg.checkinMin;
  j += "},\"closeUp\":"; j += cfg.closeUp;
  j += ",\"sync\":"; j += syncMode;
  j += ",\"ap\":"; j += apOn ? 1 : 0;
  j += ",\"mv\":"; j += moving() ? mv.port : -1;
  j += ",\"log\":"; j += logSeq;
  j += ",\"b\":[";
  for (int i = 0; i < PORTS; i++) {
    BlindCfg &c = cfg.b[i];
    bool live = moving() && mv.port == i && !isnan(mv.live) && calibrated(i);
    if (i) j += ",";
    j += "{\"name\":"; j += jq(c.name);
    j += ",\"hid\":"; j += c.hidden;
    j += ",\"pres\":"; j += bs[i].present ? 1 : 0;
    j += ",\"seen\":"; j += bs[i].seen ? 1 : 0;
    j += ",\"cal\":"; j += calibrated(i) ? 1 : 0;
    j += ",\"tilt\":"; j += jn(live ? tiltOf(i, mv.live) : bs[i].tilt, 1);
    j += ",\"tgt\":"; j += jn(bs[i].target, 0);
    j += ",\"mov\":"; j += (moving() && mv.port == i) ? 1 : 0;
    j += ",\"q\":"; j += bs[i].queued ? 1 : 0;
    j += ",\"fav\":"; j += c.fav;
    j += ",\"ang\":"; j += jn(bs[i].ang, 1);
    j += ",\"last\":"; j += jq(bs[i].last);
    j += "}";
  }
  j += "]}";
  web.send(200, "application/json", j);
}

void hDev() {
  touch();
  String j;
  j.reserve(2200);
  const esp_partition_t *part = esp_ota_get_running_partition();
  static String md5;                             // slow to work out: once, and never during a move
  if (!md5.length() && !moving()) md5 = ESP.getSketchMD5();
  static uint32_t appSize = ESP.getSketchSize();
  j += "{\"sys\":{\"fw\":\"" FW_VERSION "\",\"build\":\"" FW_BUILD "\",\"core\":\"" ESP_ARDUINO_VERSION_STR "\"";
  j += ",\"idf\":"; j += jq(ESP.getSdkVersion());
  j += ",\"chip\":"; j += jq(ESP.getChipModel());
  j += ",\"rev\":"; j += ESP.getChipRevision();
  j += ",\"mhz\":"; j += getCpuFrequencyMhz();
  j += ",\"flash\":"; j += ESP.getFlashChipSize();
  j += ",\"app\":"; j += appSize;
  j += ",\"appMax\":"; j += part ? part->size : 0;
  j += ",\"part\":"; j += jq(part ? part->label : "?");
  j += ",\"md5\":"; j += jq(md5.c_str());
  j += ",\"heap\":"; j += ESP.getFreeHeap();
  j += ",\"heapMin\":"; j += ESP.getMinFreeHeap();
  j += ",\"temp\":"; j += String(temperatureRead(), 1);
  j += ",\"rst\":"; j += jq(resetReason());
  j += ",\"up\":"; j += millis() / 1000;
  j += ",\"pending\":"; j += otaPending ? 1 : 0;
  j += ",\"mac\":"; j += jq(WiFi.macAddress().c_str());
  j += "},\"wifi\":{\"ssid\":"; j += jq(WiFi.SSID().c_str());
  j += ",\"cfg\":"; j += jq(wifiSsid());
  j += ",\"own\":"; j += cfg.ssid[0] ? 1 : 0;
  j += ",\"ip\":"; j += jq(WiFi.localIP().toString().c_str());
  j += ",\"rssi\":"; j += WiFi.RSSI();
  j += ",\"ch\":"; j += WiFi.channel();
  j += ",\"host\":\"" DEFAULT_HOSTNAME ".local\",\"tx\":"; j += cfg.txPower;
  j += ",\"ap\":"; j += apOn ? 1 : 0;
  j += "},\"pwr\":{\"vbat\":"; j += String(vbat, 3);
  j += ",\"rest\":"; j += String(vbatRest, 3);
  j += ",\"vin\":"; j += String(vin, 3);
  j += ",\"vdd\":"; j += String(vdd, 3);
  j += ",\"powered\":"; j += powered ? 1 : 0;
  j += ",\"awakeS\":"; j += stats.battAwakeS;
  j += ",\"motorMs\":"; j += stats.battMotorMs;
  j += ",\"wakes\":"; j += stats.battWakes;
  j += ",\"since\":"; j += stats.battSince;
  j += ",\"keep\":"; j += keepAwakeUntil > millis() ? (keepAwakeUntil - millis()) / 1000 : 0;
  j += ",\"next\":"; j += schedNext();
  j += "},\"st\":{\"boots\":"; j += stats.boots;
  j += ",\"brown\":"; j += stats.brownouts;
  j += ",\"crash\":"; j += stats.crashes;
  j += ",\"wdt\":"; j += stats.wdt;
  j += ",\"wakes\":"; j += stats.wakes;
  j += ",\"checkins\":"; j += stats.checkins;
  j += ",\"ota\":"; j += stats.otaOk;
  j += ",\"motorS\":"; j += stats.motorMs / 1000;
  j += "},\"tune\":{\"grace\":"; j += tune.graceMs;
  j += ",\"stall\":"; j += tune.stallMs;
  j += ",\"deg10\":"; j += tune.stallDeg10;
  j += ",\"max\":"; j += tune.moveMaxS;
  j += "},\"mv\":{\"kind\":"; j += mv.kind;
  j += ",\"port\":"; j += mv.port;
  j += ",\"st\":"; j += mv.st;
  j += ",\"nudges\":"; j += mv.nudges;
  j += ",\"live\":"; j += jn(mv.live, 1);
  j += "},\"p\":[";
  for (int i = 0; i < PORTS; i++) {
    BlindCfg &c = cfg.b[i];
    const char *pr = marksProblem(i);
    if (i) j += ",";
    j += "{\"ang\":"; j += jn(bs[i].ang, 1);
    j += ",\"mv\":"; j += String(bs[i].mv, 0);
    j += ",\"pres\":"; j += bs[i].present ? 1 : 0;
    j += ",\"up\":"; j += jn(c.up, 1);
    j += ",\"open\":"; j += jn(c.open, 1);
    j += ",\"down\":"; j += jn(c.down, 1);
    j += ",\"sign\":"; j += msign(i);
    j += ",\"bias\":"; j += String(bs[i].runBias, 1);
    j += ",\"signSeen\":"; j += abs(c.motSign) == 2 ? 1 : 0;
    j += ",\"speed\":"; j += c.speed;
    j += ",\"moves\":"; j += stats.moves[i];
    j += ",\"stalls\":"; j += stats.stalls[i];
    j += ",\"prob\":"; j += pr ? jq(pr) : String("null");
    j += "}";
  }
  j += "]}";
  web.send(200, "application/json", j);
}

void hCfg() {
  touch();
  String j = "{\"name\":";
  j += jq(cfg.name);
  j += ",\"closeUp\":"; j += cfg.closeUp;
  j += ",\"sync\":"; j += syncMode;
  j += ",\"battMode\":"; j += cfg.battMode;
  j += ",\"checkin\":"; j += cfg.checkinMin;
  j += ",\"tx\":"; j += cfg.txPower;
  j += ",\"tz\":"; j += jq(cfg.tz);
  j += ",\"tzn\":"; j += jq(cfg.tzName);
  j += ",\"b\":[";
  for (int i = 0; i < PORTS; i++) {
    if (i) j += ",";
    j += "{\"name\":"; j += jq(cfg.b[i].name);
    j += ",\"hid\":"; j += cfg.b[i].hidden;
    j += ",\"speed\":"; j += cfg.b[i].speed;
    j += ",\"fav\":"; j += cfg.b[i].fav; j += "}";
  }
  j += "],\"sched\":[";
  for (int i = 0; i < SCHEDS; i++) {
    Sched &s = cfg.sched[i];
    if (i) j += ",";
    j += "{\"on\":"; j += s.on;
    j += ",\"days\":"; j += s.days;
    j += ",\"mask\":"; j += s.mask;
    j += ",\"min\":"; j += s.minute;
    j += ",\"tilt\":"; j += s.tilt; j += "}";
  }
  j += "]}";
  web.send(200, "application/json", j);
}

void hLog() {
  touch();
  uint32_t since = strtoul(web.arg("since").c_str(), nullptr, 10);
  uint32_t first = logSeq > LOG_N ? logSeq - LOG_N : 0;
  if (since < first || since > logSeq) since = first;
  String j = "{\"seq\":";
  j += logSeq;
  j += ",\"lines\":[";
  for (uint32_t k = since; k < logSeq; k++) { if (k > since) j += ","; j += jq(logLines[k % LOG_N].c_str()); }
  j += "]}";
  web.send(200, "application/json", j);
}

void hSet() {
  touch();
  String k = web.arg("k"), v = web.arg("v");
  int n = v.toInt();
  if (k == "name") cleanText(cfg.name, sizeof cfg.name, v);
  else if (k == "closeUp") cfg.closeUp = n ? 1 : 0;
  else if (k == "sync") { syncMode = n ? 1 : 0; syncSave(); }
  else if (k == "tune.grace") { tune.graceMs = constrain(n, 0, 30000); tuneSave(); }
  else if (k == "tune.stall") { tune.stallMs = constrain(n, 200, 10000); tuneSave(); }
  else if (k == "tune.deg10") { tune.stallDeg10 = constrain(n, 1, 100); tuneSave(); }
  else if (k == "tune.max") { tune.moveMaxS = constrain(n, 5, 600); tuneSave(); }
  else if (k == "battMode") cfg.battMode = n ? 1 : 0;
  else if (k == "checkin") cfg.checkinMin = constrain(n, 0, 1440);
  else if (k == "tx") { cfg.txPower = constrain(n, 8, 20); WiFi.setTxPower((wifi_power_t)(cfg.txPower * 4)); }
  else if (k == "tz") {
    if (v.length() < 3 || v.length() >= sizeof cfg.tz) return fail("bad time zone");
    strlcpy(cfg.tz, v.c_str(), sizeof cfg.tz);
    cleanText(cfg.tzName, sizeof cfg.tzName, web.arg("n"));
    applyTz();
  } else if (k.length() >= 4 && k[0] == 'b' && k[2] == '.') {
    int p = k[1] - '0';
    if (p < 0 || p >= PORTS) return fail("no such blind");
    String f = k.substring(3);
    BlindCfg &c = cfg.b[p];
    if (f == "name") { cleanText(c.name, sizeof c.name, v); if (!c.name[0]) snprintf(c.name, sizeof c.name, "Blind %d", p + 1); }
    else if (f == "speed") c.speed = constrain(n, 50, 100);
    else if (f == "fav") c.fav = constrain(n, -100, 100);
    else if (f == "hid") c.hidden = n ? 1 : 0;
    else if (f == "sign") c.motSign = n < 0 ? -1 : 1;
    else return fail("unknown setting");
  } else return fail("unknown setting");
  cfgSave();
  ok();
}

void hSched() {
  touch();
  int i = web.arg("i").toInt();
  if (i < 0 || i >= SCHEDS) return fail("no such schedule");
  Sched &s = cfg.sched[i];
  s.on = web.arg("on").toInt() ? 1 : 0;
  s.days = web.arg("days").toInt() & 0x7F;
  s.mask = web.arg("mask").toInt() & 0x07;
  s.minute = constrain((int)web.arg("min").toInt(), 0, 1439);
  s.tilt = constrain((int)web.arg("tilt").toInt(), -100, 100);
  cfgSave();
  rtc.lastSched = time(nullptr);                // a schedule saved for "a minute ago" does not fire now
  ok();
}

void hGo() {
  touch();
  String b = web.arg("b"), to = web.arg("to");
  const char *err = nullptr;
  int started = 0;
  // Sync mode: a move of one blind goes to every blind that is set up, at that blind's tilt. solo=1 (setup test) skips it.
  int one = b == "all" ? -1 : constrain((int)b.toInt(), 0, PORTS - 1);
  bool all = one < 0 || (syncMode && !web.arg("solo").toInt());
  float tOne = NAN;
  if (one >= 0) {
    tOne = to.length() ? tiltWord(one, to) : web.arg("t").toFloat();
    if (isnan(tOne)) return fail("unknown position");
    const char *e = startTilt(one, tOne);
    if (e) return fail(e);
    started++;
  }
  for (int p = 0; all && p < PORTS; p++) {
    if (p == one || cfg.b[p].hidden || !calibrated(p) || (bs[p].seen && !bs[p].present)) continue;
    float t = one >= 0 ? tOne : tiltWord(p, to);
    if (isnan(t)) return fail("unknown position");
    const char *e = startTilt(p, t);
    if (e) err = e; else started++;
  }
  if (!started) return fail(err ? err : "no blind is set up");
  ok();
}

void hUpdateDone() {
  bool good = updAuth && !Update.hasError();
  if (good) { ok(); statsSave(); delay(400); ESP.restart(); }
  else { otaBusy = false; fail(updAuth ? "the file was not accepted" : "wrong update password"); }
}
void hUpdateData() {
  HTTPUpload &u = web.upload();
  if (u.status == UPLOAD_FILE_START) {
    updAuth = web.header("X-Update-Password") == OTA_PASSWORD;
    if (!updAuth) return;
    otaBusy = true;
    allOff();
    event("update from the browser: %s", u.filename.c_str());
    Update.begin(UPDATE_SIZE_UNKNOWN);
  } else if (!updAuth) return;
  else if (u.status == UPLOAD_FILE_WRITE) Update.write(u.buf, u.currentSize);
  else if (u.status == UPLOAD_FILE_END) Update.end(true);
  else if (u.status == UPLOAD_FILE_ABORTED) { Update.abort(); otaBusy = false; }
}

void apiBegin() {
  static const char *hdrs[] = {"X-Update-Password"};
  web.collectHeaders(hdrs, 1);
  web.on("/", []() {
    touch();
    web.sendHeader("Content-Encoding", "gzip");
    web.sendHeader("Cache-Control", "no-cache");
    web.send_P(200, "text/html", (const char *)UI_GZ, UI_GZ_LEN);
  });
  web.on("/api/s", hState);
  web.on("/api/dev", hDev);
  web.on("/api/cfg", hCfg);
  web.on("/api/log", hLog);
  web.on("/api/hist", []() {
    touch();
    String j = "{\"h\":[";
    for (int i = 0; i < BATT_HIST; i++) { if (i) j += ","; j += battHist[i]; }
    j += "]}";
    web.send(200, "application/json", j);
  });
  web.on("/api/set", hSet);
  web.on("/api/sched", hSched);
  web.on("/api/go", hGo);
  web.on("/api/stop", []() { touch(); stopAll("stopped"); ok(); });
  web.on("/api/jog", []() {
    touch();
    done(jog(web.arg("b").toInt(), web.arg("d").toInt() < 0 ? -1 : 1, constrain((int)web.arg("p").toInt(), 30, 100), web.arg("ms").toInt()));
  });
  web.on("/api/mark", []() {
    touch();
    int p = web.arg("b").toInt();
    const char *e = setMark(p, web.arg("w"));
    if (e) return fail(e);
    const char *pr = marksProblem(p);
    web.send(200, "application/json", String("{\"ok\":1,\"ang\":") + jn(bs[p].ang, 1) + ",\"prob\":" + (pr ? jq(pr) : String("null")) + "}");
  });
  web.on("/api/angle", []() { touch(); done(startAngle(web.arg("b").toInt(), web.arg("a").toFloat())); });
  web.on("/api/scan", []() {
    touch();
    if (moving()) return fail("wait until the blind stops");
    int n = WiFi.scanNetworks();
    String j = "{\"nets\":[";
    for (int i = 0; i < n && i < 15; i++) {
      if (i) j += ",";
      j += "{\"ssid\":"; j += jq(WiFi.SSID(i).c_str());
      j += ",\"rssi\":"; j += WiFi.RSSI(i);
      j += ",\"lock\":"; j += WiFi.encryptionType(i) == WIFI_AUTH_OPEN ? 0 : 1; j += "}";
    }
    j += "]}";
    WiFi.scanDelete();
    web.send(200, "application/json", j);
  });
  web.on("/api/wifi", HTTP_POST, []() {
    touch();
    String s = web.arg("ssid"), pw = web.arg("pass");
    if (s.length() >= sizeof cfg.ssid || pw.length() >= sizeof cfg.pass) return fail("too long");
    strlcpy(cfg.ssid, s.c_str(), sizeof cfg.ssid);
    strlcpy(cfg.pass, pw.c_str(), sizeof cfg.pass);
    cfgSave();
    ok();
    event("Wi-Fi set to '%s'", wifiSsid());
    delay(300);
    WiFi.disconnect();
    WiFi.begin(wifiSsid(), wifiPass());
    wifiT0 = millis();
  });
  web.on("/api/awake", []() { touch(); keepAwakeUntil = millis() + (uint32_t)constrain((int)web.arg("min").toInt(), 0, 720) * 60000; ok(); });
  web.on("/api/sleepnow", []() {
    touch();
    if (powered) return fail("input power is connected: it stays awake");
    if (otaPending) return fail("new firmware is still on trial");
    ok();
    delay(200);
    rtc.lastCheckin = time(nullptr);
    goSleep(POLL_SLEEP_S, "asked");
  });
  web.on("/api/reboot", []() { touch(); ok(); allOff(); statsSave(); delay(300); ESP.restart(); });
  web.on("/api/reset", []() {
    touch();
    String w = web.arg("what");
    if (w == "stats") { uint32_t m = stats.magic; memset(&stats, 0, sizeof stats); stats.magic = m; statsSave(); }
    else if (w == "hist") { memset(battHist, 0, sizeof battHist); histSave(); }
    else if (w == "all") { cfgDefaults(); cfgSave(); applyTz(); }
    else return fail("unknown");
    event("reset: %s", w.c_str());
    ok();
  });
  web.on("/api/update", HTTP_POST, hUpdateDone, hUpdateData);
  web.onNotFound([]() {
    if (apOn) { web.sendHeader("Location", "http://192.168.4.1/"); web.send(302, "text/plain", ""); }
    else web.send(404, "text/plain", "not found");
  });
  web.begin();
}
