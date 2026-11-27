// Schedules (clock, sunrise, sunset, the Light trigger) and gentle moves, run by the controller itself. Also the clock.
// Its state (sx, lite, lastSched) is under the controller lock (lock.h); schedRun and rampTick run in the blinds task.
#pragma once
#include <time.h>
#include "motion.h"                              // cfg, nvs, event, moveBlinds, startTilt, ramp

bool timeValid() { return time(nullptr) > 1700000000; }

// ---- schedules (as in the Wi-Fi firmware's sleep.h, without the sleeping)
uint32_t lastSched = 0;
// Extra facts per schedule slot (kept beside the settings, so adding them did not disturb the saved marks):
//   kind 0 = at a clock time, 1 = at sunrise, 2 = at sunset, 3 = when it gets light, 4 = when it gets dark (logic.h;
//   the sun kinds plus `off` minutes);  ramp = gentle: take this many minutes;
//   gid = the app's own number for a schedule, the same on every controller it covers.
struct SchedX { uint8_t kind, ramp; int16_t off; uint32_t gid; };
struct SchedExtra { uint32_t magic; SchedX x[SCHEDS]; float lat, lon; } sx;
const uint32_t SX_MAGIC = 0x53580001;
void sxSave() { nvs.putBytes("schx", &sx, sizeof sx); }
// The Light trigger's memory (NVS key "lite"): per slot the day it last fired, when and why (logic.h LightLatch), and
// when the input was last seen dark at night and lit by day (PanelWatch). Written on a fire, and at most twice a day
// for the panel. Not in the settings backup.
struct LiteStore { uint32_t magic; LightLatch l[SCHEDS]; PanelWatch pw; } lite;
const uint32_t LITE_MAGIC = 0x4C540001;
void liteSave() { nvs.putBytes("lite", &lite, sizeof lite); }
void schedBegin() {                              // the Schedules' extra facts and place; the saved time zone
  if (nvs.getBytes("schx", &sx, sizeof sx) != sizeof sx || sx.magic != SX_MAGIC) { memset(&sx, 0, sizeof sx); sx.magic = SX_MAGIC; sx.lat = sx.lon = NAN; }
  if (nvs.getBytes("lite", &lite, sizeof lite) != sizeof lite || lite.magic != LITE_MAGIC) { memset(&lite, 0, sizeof lite); lite.magic = LITE_MAGIC; }
  for (int i = 0; i < SCHEDS; i++) lite.l[i].run = 0;       // a steady run does not carry over a restart
  lite.pw.darkRun = lite.pw.litRun = 0;
  zoneUse(cfg.tz);                               // logic.h; later changes: cfgApply (motion.h)
}
// Sunrise or sunset (epoch seconds) on the day that holds `noon`, at the saved place (the math: logic.h).
uint32_t sunEvent(time_t noon, bool rise) { return sunEventAt(noon, sx.lat, sx.lon, rise); }
// Power source (logic.h) from input power, the clock and today's sunrise and sunset at the place.
int powerSource() { time_t now = time(nullptr); return powerSourceOf(powered, timeValid(), now, sunEvent(now, true), sunEvent(now, false)); }
uint32_t schedTime(int i, time_t now, int dayOff) {      // when slot i fires on (today + dayOff); 0 = not that day
  const Sched &s = cfg.sched[i];
  bool sun = isSunKind(sx.x[i].kind);            // logic.h; a light slot counts as its sun time here
  uint32_t t = slotDayTime(now, dayOff, sun ? 720 : s.minute, s.days);   // a sun slot: that day's noon
  if (!t || !sun) return t;
  uint32_t e = sunEvent(t, onSunrise(sx.x[i].kind));
  return e ? e + sx.x[i].off * 60 : 0;
}
// Gentle moves (started by moveBlinds, motion.h): a little nearer the Target every 20 seconds.
void rampTick() {
  uint32_t now = millis();
  for (int p = 0; p < PORTS; p++) {
    Ramp &r = ramp[p];
    if (!r.on || now - r.last < 20000 || moving()) continue;
    r.last = now;
    float f = min(1.0f, (float)(now - r.t0) / r.durMs);
    startTilt(p, r.from + (r.to - r.from) * f);
    if (f >= 1.0f) r.on = false;
  }
}
// A solar panel seen in the last 3 days (logic.h panelSeenRule).
bool panelSeen() { return panelSeenRule(time(nullptr), lite.pw.lastDark, lite.pw.lastLit); }
// The Light trigger, once a minute: the minute's mean of the input `vin` (power.h already reads it 5 times a second;
// nothing new is read) goes to the panel watch and to each light slot's rule (logic.h lightStep).
MinuteMean lightMean;
uint32_t lastLight = 0;                          // the step before (0 at start: nothing is run late)
void lightRun(uint32_t now) {
  float v;
  if (!lightMean.add(now, vin, &v)) return;
  uint32_t rise = sunEvent(now, true), set = sunEvent(now, false);
  bool save = panelStep(lite.pw, now, v, rise, set);
#ifdef TILT_DEVLOG
  llogMinute(now, v, rise, set);                 // store.h: the dev log around sunrise and sunset
#endif
  bool panel = panelSeen();
  for (int i = 0; i < SCHEDS; i++) {
    Sched &s = cfg.sched[i];
    int kind = sx.x[i].kind;
    if (!s.on || !isLightKind(kind)) { lite.l[i].run = 0; continue; }
    LightDay d = lightDayOf(now, kind, sx.x[i].off, s.days, sx.lat, sx.lon);
    LightWhy w = lightStep(lite.l[i], kind, now, lastLight, d.base, d.key, v, panel);
    if (!w) continue;
    event("schedule %d: tilt %d (%s)", i + 1, s.tilt, w == LIGHT_BY_LIGHT ? "by light" : w == LIGHT_FELL_BACK ? "fell back" : "no panel: sun time");
    // The same move as any Schedule. Under Critical battery it is refused, and still counts as fired for the day.
    moveBlinds(moveAsk(FROM_SCHEDULE, -1, s.tilt, (uint32_t)sx.x[i].ramp * 60000u, s.mask));
    save = true;
  }
  lastLight = now;
  if (save) liteSave();
}
void schedRun() {
  if (!timeValid()) return;
  uint32_t now = time(nullptr);
  if (lastSched > now || now - lastSched > 1800) lastSched = now - 90;
  for (int i = 0; i < SCHEDS; i++) {
    Sched &s = cfg.sched[i];
    if (!s.on || isLightKind(sx.x[i].kind)) continue;     // light slots: lightRun
    for (int d = -1; d <= 0; d++) {
      uint32_t t = schedTime(i, now, d);
      if (t && t > lastSched && t <= now) {
        event("schedule %d: tilt %d", i + 1, s.tilt);
        moveBlinds(moveAsk(FROM_SCHEDULE, -1, s.tilt, (uint32_t)sx.x[i].ramp * 60000u, s.mask));
      }
    }
  }
  lastSched = now;
  lightRun(now);
}
uint32_t schedNext() {
  if (!timeValid()) return 0;
  uint32_t now = time(nullptr), best = 0;
  for (int i = 0; i < SCHEDS; i++) {
    if (!cfg.sched[i].on) continue;
    for (int d = 0; d <= 7; d++) {
      uint32_t t = schedTime(i, now, d);
      if (t > now) { if (!best || t < best) best = t; break; }
    }
  }
  return best;
}
