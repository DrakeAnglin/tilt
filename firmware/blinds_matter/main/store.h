// Settings and counters, kept in NVS. Also the event log (RAM) and a week of hourly battery readings.
#pragma once
#include "ardu.h"
#include "config.h"
#include "freertos/semphr.h"
#include <esp_system.h>

struct BlindCfg {
  char name[20];
  float up, open, down;        // sensor angle (deg) at closed-up, open (slats level), closed-down. NAN = not marked
  int8_t motSign;              // > 0: motor "forward" makes the angle rise. +-1 = assumed, +-2 = seen to be so.
  uint8_t speed;               // percent, 50..100
  int8_t fav;                  // favorite tilt, -100..100
  uint8_t hidden;              // 1: don't show (port not used)
};
struct Sched {
  uint8_t on, days, mask;      // days: bit 0 = Sunday. mask: bit n = blind n
  uint16_t minute;             // minute of the day, local time
  int8_t tilt;                 // -100 closed down, 0 open, 100 closed up
};
const int SCHEDS = 8;
struct Settings {
  uint32_t magic;
  char name[24];
  uint8_t closeUp;             // "Close" means closed-up (1) or closed-down (0)
  uint8_t battMode;            // unused (Wi-Fi firmware's battery sleep): kept for the stored layout
  uint16_t checkinMin;         // unused (Wi-Fi firmware's check-ins): kept for the stored layout
  uint8_t txPower;             // Wi-Fi transmit power, dBm (8..20)
  char tz[44];                 // POSIX time zone string
  char tzName[36];             // its IANA name, for display
  char ssid[33], pass[65];     // unused (Matter keeps the Wi-Fi network): kept for the stored layout
  Sched sched[SCHEDS];
  BlindCfg b[PORTS];
};
struct Stats {
  uint32_t magic;
  uint32_t boots, brownouts, crashes, wdt, wakes, checkins;   // wakes, checkins: unused, kept for the stored layout
  uint32_t moves[PORTS], stalls[PORTS];
  uint32_t motorMs;            // all time
  uint32_t battAwakeS, battMotorMs, battWakes;   // since the charger was last connected (battWakes: unused, kept for the stored layout)
  uint32_t battSince;          // epoch when it went on battery (0 = unknown)
  uint32_t otaOk;
};
// Stalls during an ordinary move since this start (not setup or jogs): the hub sends an alert for each new one.
inline uint16_t movesStalled[PORTS];
const uint32_t CFG_MAGIC = 0xB11D0003, STAT_MAGIC = 0x57A70002;
const int BATT_HIST = 168;     // hourly, one week

Settings cfg;
// The drive has play: after a change of direction the motor turns for a while before the rod, and the sensor on it,
// moves at all. So a stall is only called after a long quiet time. The play was 6 to 8.5 s on the old 88:1 train; on
// today's 20:1 tilter with the 150 RPM N20 it is 0.3 to 1.7 s (dining room jogs, 2026-11-25), and a 300 RPM motor
// takes it up in about half that. The grace keeps a wide margin over that (a slow speed setting or a low battery
// stretches it), so it suits 100 to 300 RPM motors as it is.
struct Tune {
  uint16_t magic;
  uint16_t graceMs;            // after a change of direction: no stall check for this long (gear play being taken up)
  uint16_t stallMs;            // after that: the angle must change within this time ...
  uint16_t stallDeg10;         // ... by this much (tenths of a degree)
  uint16_t moveMaxS;           // no move lasts longer (seconds)
};
const uint16_t TUNE_MAGIC = 0x7403;
Tune tune = {TUNE_MAGIC, 8000, 2500, 10, 180};    // grace about twice the expected play; a saved tune (app) wins
uint8_t leadMax10 = 80;         // the most a blind may learn to stop early, tenths of a degree (TiltSettings::leadMax). Own NVS key ("lmax"), so a saved tune keeps working.
uint8_t syncMode = 1;           // 1: blinds follow each other: moving one (app, Home, or its wand by hand) sends them all to the same tilt. Own NVS key.
uint8_t parMode = 1;            // 1: blinds that have to move all move at the same time; 0: one after another. Own NVS key.
uint8_t hkSeparate = 0;         // 1: Apple Home shows one Window covering per blind; 0: one for all. Own NVS key ("hksep").
Stats stats;
uint8_t battHist[BATT_HIST];   // (volts - 2.5) * 100, 0 = no reading; newest last
Preferences nvs;

#ifdef TILT_DEVLOG
// Dev builds only: one line per hour for a week, to see the battery, the solar input and what used power over days.
// Kept in NVS, so restarts and updates do not clear it. Read it with /api/powerlog (owner).
struct PowerHour {
  uint32_t at;          // epoch at the end of the hour
  uint8_t rest;         // resting cell volts: (v - 2.5) * 100
  uint8_t vinMax;       // highest input (solar or USB) in the hour: volts * 40
  uint8_t poweredMin;   // minutes with input power
  int8_t tempC;         // chip temperature
  uint16_t motorS;      // motor seconds in the hour
  uint8_t flags;        // 1: restarted in this hour, 2: new firmware started
  uint8_t litMin;       // minutes the solar input showed any light (above SOLAR_LIT_V)
  uint8_t vinAvg;       // average input over the hour: volts * 40 (with litMin: how much sun the panel gets)
  uint8_t pad[2];
};
const float SOLAR_LIT_V = 1.0f;   // the panel's input is ~0 V in the dark; anything above this means some light
const int PLOG_N = 168;
PowerHour plog[PLOG_N];   // newest last; at == 0 is an empty slot
struct PowerAcc { float vinMax; uint32_t poweredMs; uint32_t motorMs0; uint8_t flags; uint32_t litMs; float vinMsSum; uint32_t ms; } plogAcc = {0, 0, 0, 1, 0, 0, 0};
void plogBegin() {
  if (nvs.getBytes("plog", plog, sizeof plog) != sizeof plog) memset(plog, 0, sizeof plog);
  plogAcc.motorMs0 = stats.motorMs;
}
// Called often: keep the hour's highest input and the time on input power.
void plogTick(float vin, bool powered, uint32_t dtMs) {
  if (vin > plogAcc.vinMax) plogAcc.vinMax = vin;
  if (powered) plogAcc.poweredMs += dtMs;
  if (vin >= SOLAR_LIT_V) plogAcc.litMs += dtMs;
  plogAcc.vinMsSum += vin * dtMs;
  plogAcc.ms += dtMs;
}
void plogPush(uint32_t at, float rest, float tempC) {
  memmove(plog, plog + 1, sizeof(PowerHour) * (PLOG_N - 1));
  PowerHour &h = plog[PLOG_N - 1];
  h.at = at;
  h.rest = (uint8_t)constrain((int)lroundf((rest - 2.5f) * 100.0f), 1, 255);
  h.vinMax = (uint8_t)constrain((int)lroundf(plogAcc.vinMax * 40.0f), 0, 255);
  h.poweredMin = (uint8_t)min<uint32_t>(plogAcc.poweredMs / 60000, 255);
  h.tempC = (int8_t)constrain((int)lroundf(tempC), -100, 100);
  h.motorS = (uint16_t)min<uint32_t>((stats.motorMs - plogAcc.motorMs0) / 1000, 65535);
  h.flags = plogAcc.flags;
  h.litMin = (uint8_t)min<uint32_t>(plogAcc.litMs / 60000, 255);
  h.vinAvg = (uint8_t)constrain((int)lroundf(plogAcc.ms ? plogAcc.vinMsSum / plogAcc.ms * 40.0f : 0), 0, 255);
  h.pad[0] = h.pad[1] = 0;
  nvs.putBytes("plog", plog, sizeof plog);
  plogAcc = {0, 0, stats.motorMs, 0, 0, 0, 0};
}
// Dev builds only: the input by the minute for 2 hours either side of each sunrise and sunset, the data the Light
// trigger's levels are tuned from (#212). The last 6 windows, kept in NVS: one write as each window ends. A restart
// inside a window loses that window. Read it with /api/lightlog (owner).
const int LLOG_N = 6, LLOG_MIN = 241;            // minutes in a window: event - 120 .. event + 120
const uint32_t LLOG_HALF_S = 120 * 60;
struct LightWin { uint32_t start; uint8_t rise, pad[3]; uint8_t v[LLOG_MIN]; };   // v: volts * 40, 0 = no reading
LightWin llog[LLOG_N];                           // newest last; start == 0 is an empty slot
LightWin llCur;                                  // the window being filled (start 0: none)
void llogBegin() {
  if (nvs.getBytes("llog", llog, sizeof llog) != sizeof llog) memset(llog, 0, sizeof llog);
  memset(&llCur, 0, sizeof llCur);
}
// Once a minute with the minute's mean input, and today's sunrise and sunset (0 not known).
void llogMinute(uint32_t now, float v, uint32_t rise, uint32_t set) {
  uint32_t ev = 0;
  bool isRise = false;
  if (rise && now + LLOG_HALF_S >= rise && now <= rise + LLOG_HALF_S) { ev = rise; isRise = true; }
  else if (set && now + LLOG_HALF_S >= set && now <= set + LLOG_HALF_S) ev = set;
  if (llCur.start && (!ev || ev - LLOG_HALF_S != llCur.start)) {      // the window ended: keep it
    memmove(llog, llog + 1, sizeof(LightWin) * (LLOG_N - 1));
    llog[LLOG_N - 1] = llCur;
    nvs.putBytes("llog", llog, sizeof llog);
    memset(&llCur, 0, sizeof llCur);
  }
  if (!ev) return;
  if (!llCur.start) { llCur.start = ev - LLOG_HALF_S; llCur.rise = isRise ? 1 : 0; }
  uint32_t k = (now - llCur.start) / 60;
  if (k < (uint32_t)LLOG_MIN) llCur.v[k] = (uint8_t)constrain((int)lroundf(v * 40.0f), 1, 255);
}
#endif
void cfgDefaultsOf(Settings &c) {             // (a handler puts them in place with cfgApply, motion.h)
  memset(&c, 0, sizeof c);
  c.magic = CFG_MAGIC;
  strlcpy(c.name, "Blinds", sizeof c.name);
  c.closeUp = 1;
  c.battMode = 0;
  c.checkinMin = 15;
  c.txPower = 15;
  strlcpy(c.tz, "CST6CDT,M3.2.0,M11.1.0", sizeof c.tz);
  strlcpy(c.tzName, "America/Chicago", sizeof c.tzName);
  for (int i = 0; i < PORTS; i++) {
    snprintf(c.b[i].name, sizeof c.b[i].name, "Blind %d", i + 1);
    c.b[i].up = c.b[i].open = c.b[i].down = NAN;
    c.b[i].motSign = 1;
    c.b[i].speed = 100;
    c.b[i].fav = 50;
  }
  for (int i = 0; i < SCHEDS; i++) { c.sched[i].days = 0x7F; c.sched[i].mask = 0; c.sched[i].minute = 8 * 60; }   // mask 0 = unused slot
}
void cfgDefaults() { cfgDefaultsOf(cfg); }
void cfgSave() { nvs.putBytes("cfg", &cfg, sizeof cfg); }
void syncSave() { nvs.putUChar("sync", syncMode); nvs.putUChar("par", parMode); }
void tuneSave() { nvs.putBytes("tune", &tune, sizeof tune); }
void statsSave() { nvs.putBytes("stat", &stats, sizeof stats); }
void histSave() { nvs.putBytes("bhist", battHist, sizeof battHist); }
void storeBegin() {
  nvs.begin("blinds", false);
  if (nvs.getBytes("cfg", &cfg, sizeof cfg) != sizeof cfg || cfg.magic != CFG_MAGIC) { cfgDefaults(); cfgSave(); }
  if (nvs.getBytes("stat", &stats, sizeof stats) != sizeof stats || stats.magic != STAT_MAGIC) {
    memset(&stats, 0, sizeof stats);
    stats.magic = STAT_MAGIC;
  }
  syncMode = nvs.getUChar("sync", 1);
  parMode = nvs.getUChar("par", 1);
  hkSeparate = nvs.getUChar("hksep", 0);
  leadMax10 = nvs.getUChar("lmax", 80);
  if (nvs.getUChar("angv", 1) < 2) {             // marks made with the first angle scale (rail - 0.10 V): rescale once
    for (int i = 0; i < PORTS; i++) {
      float *m[3] = {&cfg.b[i].up, &cfg.b[i].open, &cfg.b[i].down};
      for (int k = 0; k < 3; k++) if (!isnan(*m[k])) *m[k] = fmodf(*m[k] * 1.057f, 360.0f);
    }
    cfgSave();
    nvs.putUChar("angv", 2);
  }
  Tune t;
  if (nvs.getBytes("tune", &t, sizeof t) == sizeof t && t.magic == TUNE_MAGIC) tune = t;
  if (nvs.getBytes("bhist", battHist, sizeof battHist) != sizeof battHist) memset(battHist, 0, sizeof battHist);
#ifdef TILT_DEVLOG
  plogBegin();
  llogBegin();
#endif
  stats.boots++;                                 // count this start, and why the last one ended
  esp_reset_reason_t rr = esp_reset_reason();
  if (rr == ESP_RST_BROWNOUT) stats.brownouts++;
  else if (rr == ESP_RST_PANIC) stats.crashes++;
  else if (rr == ESP_RST_INT_WDT || rr == ESP_RST_TASK_WDT || rr == ESP_RST_WDT) stats.wdt++;
  statsSave();
}
void histPush(float v) {
  memmove(battHist, battHist + 1, BATT_HIST - 1);
  battHist[BATT_HIST - 1] = (uint8_t)constrain((int)lroundf((v - 2.5f) * 100.0f), 1, 255);
  histSave();
}

// The time zone name and phone names only: keeps letters, digits and a few signs. Blind, controller and Scene names
// are kept as typed (wire.h keptName).
void cleanText(char *dst, size_t n, const String &src) {
  size_t k = 0;
  for (size_t i = 0; i < src.length() && k + 1 < n; i++) {
    char c = src[i];
    if (isalnum((unsigned char)c) || strchr(" _-.,'/+:()#&", c)) dst[k++] = c;
  }
  while (k && dst[k - 1] == ' ') k--;
  dst[k] = 0;
}

// ---- event log (RAM): the last lines, for the developer page
// event() is called from every task (the blinds task, the web server, Bluetooth, Matter), so the lines have their own
// small lock. It is the innermost lock (see lock.h): held only to store or copy lines, never while taking another.
const int LOG_N = 60;
String logLines[LOG_N];
uint32_t logSeq = 0;
SemaphoreHandle_t logMx = nullptr;
void logBegin() { logMx = xSemaphoreCreateMutex(); }    // first thing at start: before it there is only one task
struct LogLock {
  LogLock() { if (logMx) xSemaphoreTake(logMx, portMAX_DELAY); }
  ~LogLock() { if (logMx) xSemaphoreGive(logMx); }
};
void (*eventHook)(const char *line) = nullptr;   // also keep it somewhere else (hub_link.h, the Thread build)
void event(const char *fmt, ...) {
  char buf[128], line[160];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(buf, sizeof buf, fmt, ap);
  va_end(ap);
  time_t t = time(nullptr);
  if (t > 1700000000) {
    struct tm tm;
    localtime_r(&t, &tm);
    snprintf(line, sizeof line, "%02d:%02d:%02d  %s", tm.tm_hour, tm.tm_min, tm.tm_sec, buf);
  } else snprintf(line, sizeof line, "+%lus  %s", (unsigned long)(millis() / 1000), buf);
  for (char *p = line; *p; p++) if (*p == '"' || *p == '\\' || (unsigned char)*p < 32) *p = '\'';
  {
    LogLock l;
    logLines[logSeq % LOG_N] = line;
    logSeq++;
  }
  if (eventHook) eventHook(line);
  ESP_LOGI("blinds", "%s", line);
}
