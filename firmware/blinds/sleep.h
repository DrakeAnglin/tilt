// Schedules and the battery plan.
//   Input power present (USB, or a solar panel in sun): Wi-Fi stays on.
//   On battery, mode "sleep": deep sleep. It wakes every 30 s for a moment (no Wi-Fi) to look for input power and to
//     run schedules, and joins Wi-Fi for a short check-in every cfg.checkinMin minutes.
//   On battery, mode "connected": Wi-Fi stays on in its power-save mode (days, not months, on one cell).
#pragma once
#include <esp_sleep.h>
#include "net.h"

struct RtcData { uint32_t magic, wakes, lastSched, lastCheckin, lastHist; };
RTC_DATA_ATTR RtcData rtc;
const uint32_t RTC_MAGIC = 0x52544331;
bool checkinBoot = false, wokeFromSleep = false;
uint32_t unpluggedAt = 0;                       // millis when input power went away (0 = at boot)

const char *resetReason() {
  if (wokeFromSleep) return "woke from sleep";
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON: return "power on";
    case ESP_RST_SW: return "restart / update";
    case ESP_RST_PANIC: return "crash";
    case ESP_RST_BROWNOUT: return "brownout (supply dipped)";
    case ESP_RST_INT_WDT: case ESP_RST_TASK_WDT: case ESP_RST_WDT: return "watchdog";
    case ESP_RST_USB: return "USB";
    case ESP_RST_DEEPSLEEP: return "woke from sleep";
    default: return "other";
  }
}

// ---- schedules
uint32_t schedTime(const Sched &s, time_t now, int dayOff) {   // epoch of this schedule's time on (today + dayOff), 0 = not that day
  struct tm tm;
  localtime_r(&now, &tm);
  tm.tm_mday += dayOff;
  tm.tm_hour = 0; tm.tm_min = s.minute; tm.tm_sec = 0; tm.tm_isdst = -1;
  time_t t = mktime(&tm);
  struct tm chk;
  localtime_r(&t, &chk);
  return (s.days >> chk.tm_wday) & 1 ? (uint32_t)t : 0;
}
int schedRun() {                                // start every schedule that came due since the last look; returns how many
  if (!timeValid()) return 0;
  uint32_t now = time(nullptr);
  if (rtc.lastSched > now || now - rtc.lastSched > 1800) rtc.lastSched = now - 90;   // never replay old ones
  int n = 0;
  for (int i = 0; i < SCHEDS; i++) {
    Sched &s = cfg.sched[i];
    if (!s.on) continue;
    for (int d = -1; d <= 0; d++) {
      uint32_t t = schedTime(s, now, d);
      if (t && t > rtc.lastSched && t <= now) {
        event("schedule %d: tilt %d", i + 1, s.tilt);
        for (int p = 0; p < PORTS; p++) if (((s.mask >> p) & 1) && !cfg.b[p].hidden && calibrated(p)) startTilt(p, s.tilt);
        n++;
      }
    }
  }
  rtc.lastSched = now;
  return n;
}
uint32_t schedNext() {                          // epoch of the next schedule, 0 = none
  if (!timeValid()) return 0;
  uint32_t now = time(nullptr), best = 0;
  for (int i = 0; i < SCHEDS; i++) {
    if (!cfg.sched[i].on) continue;
    for (int d = 0; d <= 7; d++) {
      uint32_t t = schedTime(cfg.sched[i], now, d);
      if (t > now) { if (!best || t < best) best = t; break; }
    }
  }
  return best;
}

// ---- sleep
void goSleep(uint32_t seconds, const char *why, bool save = true) {
  allOff();
  if (save) statsSave();                         // not on the 30 s look-arounds: that would wear the flash
  if (Serial) { Serial.printf("sleep %lu s (%s)\n", (unsigned long)seconds, why); Serial.flush(); }
  if (wifiStarted) { WiFi.disconnect(true); WiFi.mode(WIFI_OFF); }
  esp_sleep_enable_timer_wakeup((uint64_t)seconds * 1000000ULL);
  esp_deep_sleep_start();
}

// Called first thing after a timer wake, before Wi-Fi. Returns only if the board should come up fully.
void quickWake() {
  if (rtc.magic != RTC_MAGIC) { memset(&rtc, 0, sizeof rtc); rtc.magic = RTC_MAGIC; }
  wokeFromSleep = esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_TIMER;
  if (!wokeFromSleep) return;
  rtc.wakes++;
  if (powered || cfg.battMode == 1) return;
  if (vbatRest < VBAT_CRIT) goSleep(CRIT_SLEEP_S, "battery empty", false);
  uint32_t now = time(nullptr);
  if (rtc.lastHist > now || now - rtc.lastHist >= 3600) { rtc.lastHist = now; histPush(vbatRest); }
  if (schedRun()) {                             // move without Wi-Fi, then back to sleep
    uint32_t t0 = millis();
    while ((moving() || bs[0].queued || bs[1].queued || bs[2].queued) && millis() - t0 < 90000) {
      static uint32_t ps = 0;
      if (millis() - ps >= 200) { ps = millis(); powerSample(); }
      motionTick();
      delay(1);
    }
  }
  if (cfg.checkinMin && (rtc.lastCheckin > now || now - rtc.lastCheckin >= (uint32_t)cfg.checkinMin * 60)) {
    rtc.lastCheckin = now;
    checkinBoot = true;
    return;
  }
  goSleep(POLL_SLEEP_S, "battery", false);
}

int sleepIn = -1;                               // seconds until it sleeps (-1 = staying awake), for the app
void sleepTick() {
  static uint32_t lastS = 0, lastSched = 0;
  static bool wasPowered = powered, psBatt = false;   // as it was at start: a check-in on battery is not "just unplugged"
  uint32_t now = millis();
  if (now - lastSched >= 5000) { lastSched = now; schedRun(); }
  if (now - lastS < 1000) return;
  lastS = now;
  if (wasPowered && !powered) {                 // just went on battery
    unpluggedAt = now;
    stats.battAwakeS = stats.battMotorMs = stats.battWakes = 0;
    stats.battSince = timeValid() ? (uint32_t)time(nullptr) : 0;
    event("on battery (%.2f V)", vbatRest);
  }
  if (!wasPowered && powered) event("input power connected (%.2f V)", vin);
  wasPowered = powered;
  if (!powered) stats.battAwakeS++;
  uint32_t ep = time(nullptr);
  if (rtc.lastHist > ep || ep - rtc.lastHist >= 3600) { rtc.lastHist = ep; histPush(vbatRest); }

  bool wantPs = !powered && cfg.battMode == 1;  // connected on battery: slow the processor, let the radio doze
  if (wantPs != psBatt) {
    psBatt = wantPs;
    setCpuFrequencyMhz(wantPs ? 80 : 160);
    WiFi.setSleep(wantPs ? WIFI_PS_MAX_MODEM : WIFI_PS_MIN_MODEM);
  }

  sleepIn = -1;
  if (powered || cfg.battMode == 1 || otaPending || otaBusy) return;
  uint32_t until = unpluggedAt + (checkinBoot && !unpluggedAt ? CHECKIN_AWAKE_S : GRACE_BOOT_S) * 1000;
  if (lastActivity && lastActivity + GRACE_ACTIVITY_S * 1000 > until) until = lastActivity + GRACE_ACTIVITY_S * 1000;
  if (keepAwakeUntil > until) until = keepAwakeUntil;
  if (vbatRest < VBAT_CRIT) until = min(until, unpluggedAt + 20000);
  if (moving()) { sleepIn = max(1, (int)((int32_t)(until - now) / 1000)); return; }
  if ((int32_t)(until - now) > 0) { sleepIn = (int32_t)(until - now) / 1000; return; }
  rtc.lastCheckin = time(nullptr);
  goSleep(vbatRest < VBAT_CRIT ? CRIT_SLEEP_S : POLL_SLEEP_S, "battery");
}
