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
const uint32_t CFG_MAGIC = 0xB11D0003, STAT_MAGIC = 0x57A70002;
const int BATT_HIST = 168;     // hourly, one week

Settings cfg;
// The drive has play: after a change of direction the motor turns for a while before the rod, and the sensor on it,
// moves at all. So a stall is only called after a long quiet time. The play was measured at 6 to 8.5 s with the old
// 150 RPM motor; the 300 RPM N20 (about 185 RPM on the cell) takes it up in roughly half that, 3 to 4.5 s. The grace
// keeps a wide margin over that (a slow speed setting or a low battery stretches it).
struct Tune {
  uint16_t magic;
  uint16_t graceMs;            // after a change of direction: no stall check for this long (gear play being taken up)
  uint16_t stallMs;            // after that: the angle must change within this time ...
  uint16_t stallDeg10;         // ... by this much (tenths of a degree)
  uint16_t moveMaxS;           // no move lasts longer (seconds)
};
const uint16_t TUNE_MAGIC = 0x7403;
Tune tune = {TUNE_MAGIC, 8000, 2500, 10, 180};    // grace about twice the expected play; a saved tune (app) wins
uint8_t syncMode = 1;           // 1: blinds follow each other: moving one (app, Home, or its wand by hand) sends them all to the same tilt. Own NVS key.
uint8_t parMode = 1;            // 1: blinds that have to move all move at the same time; 0: one after another. Own NVS key.
uint8_t hkSeparate = 0;         // 1: Apple Home shows one Window covering per blind; 0: one for all. Own NVS key ("hksep").
Stats stats;
uint8_t battHist[BATT_HIST];   // (volts - 2.5) * 100, 0 = no reading; newest last
Preferences nvs;

void cfgDefaults() {
  memset(&cfg, 0, sizeof cfg);
  cfg.magic = CFG_MAGIC;
  strlcpy(cfg.name, "Blinds", sizeof cfg.name);
  cfg.closeUp = 1;
  cfg.battMode = 0;
  cfg.checkinMin = 15;
  cfg.txPower = 15;
  strlcpy(cfg.tz, "CST6CDT,M3.2.0,M11.1.0", sizeof cfg.tz);
  strlcpy(cfg.tzName, "America/Chicago", sizeof cfg.tzName);
  for (int i = 0; i < PORTS; i++) {
    snprintf(cfg.b[i].name, sizeof cfg.b[i].name, "Blind %d", i + 1);
    cfg.b[i].up = cfg.b[i].open = cfg.b[i].down = NAN;
    cfg.b[i].motSign = 1;
    cfg.b[i].speed = 100;
    cfg.b[i].fav = 50;
  }
  for (int i = 0; i < SCHEDS; i++) { cfg.sched[i].days = 0x7F; cfg.sched[i].mask = 0; cfg.sched[i].minute = 8 * 60; }   // mask 0 = unused slot
}
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

// Names come from a browser: keep only characters that are safe inside JSON and HTML.
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
  ESP_LOGI("blinds", "%s", line);
}
