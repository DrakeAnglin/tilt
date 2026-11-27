// Pure logic: no ESP-IDF, no hardware, no shared state. Everything here is plain math or a rule on its inputs, so it
// is tested on the Mac (test/logic_test.cpp, run with tools/firmware_tests.sh). The firmware calls these.
#pragma once
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <string>
#include "routes.h"                              // Who: the roles permitRule decides by

const int PORTS = 3;                                         // a controller has 3 ports

// ---- angles
inline float angDiff(float to, float from) { return fmodf(to - from + 540.0f, 360.0f) - 180.0f; }   // shortest, -180..180
inline float sgn(float v) { return v < 0 ? -1.0f : 1.0f; }
// One AS5600 PWM frame as a share of a turn (0..1). The high time is 128 clocks of lead-in plus the angle in 4095 steps,
// out of 4351 clocks. A frame outside that (a noise edge while the motor runs) is no reading: -1, never a clamped 0
// (a clamped 0 looked like a jump to the sensor's zero and stopped moves, 2026-11-23).
inline float as5600Share(uint32_t high, uint32_t period) {
  if (!period) return -1.0f;
  float s = ((float)high / (float)period * 4351.0f - 128.0f) / 4095.0f;
  if (s < -0.01f || s > 1.01f) return -1.0f;
  return s < 0 ? 0 : s > 1 ? 1 : s;
}
// No pulses means the sensor sits within a few degrees of its zero, but only if it was last seen near there. Anywhere
// else, missing pulses are noise: keep the last good reading and keep checking for a stall.
inline bool pwmBlindSpot(float lastShare) { return lastShare < 15.0f / 360.0f || lastShare > 345.0f / 360.0f; }
// A reading at a rail: a PWM sensor with no pulses, or an analog one at 0 V. That is the sensor's zero only if it was
// last seen near there. Anywhere else, or with no good reading yet (just after a restart: its zero or a dead sensor,
// nobody can tell), it is a dropout (the sensor gave nothing: 2026-11-25, Dining read 0 deg at rest, and moves and
// Follow took it as real): no reading. Either way the angle given is the last good one (raw when there is none), and
// `guess` says the angle is not fresh. raw: what the sensor gave; last: the last good angle (NAN: none).
const float ANALOG_RAIL_MV = 30.0f;                 // an analog output under this is at 0 V (about 4 degrees)
struct SensorRead { float ang; bool guess, lost; };
inline SensorRead judgeReading(float raw, bool atRail, float last) {
  if (!atRail) return {raw, false, false};
  if (std::isnan(last)) return {raw, true, true};                       // nothing known yet: no reading
  if (pwmBlindSpot(fmodf(last + 360.0f, 360.0f) / 360.0f)) return {last, true, false};   // near zero before: still there
  return {last, true, true};                                            // a dropout
}
// One sensor's readings, judged in turn. `good` is the last fresh angle, kept on every reading (while a motor runs
// too), so a dropout mid-move keeps where the rod really was, not where the move started.
struct ReadingJudge {
  float good = NAN;
  bool lost = false;                                  // the last reading was a dropout
  SensorRead judge(float raw, bool atRail) {
    SensorRead r = judgeReading(raw, atRail, good);
    if (!r.guess) good = raw;
    lost = r.lost;
    return r;
  }
  void forget() { good = NAN; lost = false; }         // unplugged: whatever comes next is a new tilter
};

// ---- a blind's three marks (sensor angles, degrees) and tilt (-100 closed down .. 0 open .. +100 closed up)
const float MAX_HALF_SPAN = 170.0f, MIN_HALF_SPAN = 8.0f;   // open -> closed, each way (degrees of rod turn)
struct Marks { float up, open, down; };
inline const char *marksProblemOf(const Marks &m) {          // nullptr = good
  if (std::isnan(m.up) || std::isnan(m.open) || std::isnan(m.down)) return "not all three positions are marked";
  float u = angDiff(m.up, m.open), d = angDiff(m.down, m.open);
  if (fabsf(u) < MIN_HALF_SPAN || fabsf(d) < MIN_HALF_SPAN) return "open is too close to a closed mark";
  if (fabsf(u) > MAX_HALF_SPAN || fabsf(d) > MAX_HALF_SPAN) return "a closed mark is more than half a turn from open";
  if ((u > 0) == (d > 0)) return "open must be between the two closed marks";
  return nullptr;
}
inline float arcXOf(const Marks &m, float ang) { return angDiff(ang, m.open) * sgn(angDiff(m.up, m.open)); }   // degrees from open, + toward closed-up
inline float tiltOfMarks(const Marks &m, float ang) {
  float x = arcXOf(m, ang);
  return x >= 0 ? x / fabsf(angDiff(m.up, m.open)) * 100.0f : x / fabsf(angDiff(m.down, m.open)) * 100.0f;
}
inline float xOfTiltMarks(const Marks &m, float t) {
  return t >= 0 ? t / 100.0f * fabsf(angDiff(m.up, m.open)) : t / 100.0f * fabsf(angDiff(m.down, m.open));
}
// Does a settings change pull the ground from under a running move? A move steers by the Marks and the motor's
// direction (only which way: +-1 to +-2 is the move itself learning it).
inline bool sameAngle(float a, float b) { return (std::isnan(a) && std::isnan(b)) || a == b; }
inline bool steeringChanged(const Marks &a, int signA, const Marks &b, int signB) {
  return !sameAngle(a.up, b.up) || !sameAngle(a.open, b.open) || !sameAngle(a.down, b.down) || (signA > 0) != (signB > 0);
}
// The motor direction after a settings change that stopped a move: the one asked for if the change set it, else
// what the stopped move left (it may have learned or put back the direction while ending).
inline int8_t keptSign(int8_t asked, int8_t before, int8_t afterStop) { return asked != before ? asked : afterStop; }
// Current tilt (CONTEXT.md: it always wins): the sensor now. While a move runs, its live reading; at rest, the last
// true reading (noted, worked out when it was read). Not set up: unknown, moving or not. Always -100..100.
inline float currentTiltOf(const Marks &m, bool moving, float live, float noted) {
  if (marksProblemOf(m)) return NAN;
  float t = moving && !std::isnan(live) ? tiltOfMarks(m, live) : noted;
  return std::isnan(t) ? t : fminf(fmaxf(t, -100.0f), 100.0f);     // past a closed mark is still closed: never over 100
}

// ---- a reading for a mark (motion.h setMark): the sensor has to hold still for 0.6 s. One first reading, then 12 more
// with a 50 ms wait before each. A still PWM reading wanders about +-1.5 degrees (brush noise on the shared wires), so
// "still" is a spread within STEADY_DEG; a wand being turned moves far more. The answer is the mean, taken the short
// way round across the sensor's zero. Any dropout among the readings: no mark is taken from that.
const float STEADY_DEG = 3.5f;
struct SteadySensor {
  virtual float angle() = 0;                    // the Angle now (degrees)
  virtual bool lost() = 0;                      // that reading was a dropout
  virtual bool wait(uint32_t ms) = 0;           // wait; false = stop, the reading can no longer be trusted
};
enum SteadyIs { STEADY_OK, STEADY_MOVING, STEADY_LOST, STEADY_CUT };
struct SteadyResult { float ang; SteadyIs is; };   // ang: the mean (NAN unless STEADY_OK)
inline SteadyResult steadyRead(SteadySensor &s) {
  float a0 = s.angle(), lo = 0, hi = 0, sum = 0;
  bool lost = s.lost();
  for (int k = 0; k < 12; k++) {
    if (!s.wait(50)) return {NAN, STEADY_CUT};
    float d = angDiff(s.angle(), a0);
    lost |= s.lost();
    lo = fminf(lo, d); hi = fmaxf(hi, d); sum += d;
  }
  if (lost) return {NAN, STEADY_LOST};
  if (hi - lo > STEADY_DEG) return {NAN, STEADY_MOVING};
  return {fmodf(a0 + sum / 13 + 360.0f, 360.0f), STEADY_OK};
}

// ---- can a blind be moved? Set up (all three marks good), its tilter not missing, and the battery above the motor
// cut-off (CONTEXT.md: under 3.35 V resting, no motor runs, whoever asks). nullptr = yes, else why not.
inline const char *cannotMoveWhy(bool calibrated, bool seen, bool present, bool battOk) {
  if (!calibrated) return "not set up yet";
  if (seen && !present) return "no tilter plugged in";
  if (!battOk) return "battery too low";
  return nullptr;
}
// Movable: the same, and shown (not hidden in the app). Battery is left to the move itself (it gives the reason).
inline bool movableRule(bool hidden, bool calibrated, bool seen, bool present) { return !hidden && !cannotMoveWhy(calibrated, seen, present, true); }

// ---- Battery level (CONTEXT.md): Low under 20 % warns; Critical under 10 % also pauses Schedules. From the cell voltage
// only: input power doesn't count, because a solar panel in weak light shows a voltage but charges nothing.
// (The motor cut-off, VBAT_CUTOFF in config.h, is lower still: no motor moves at all below it.)
const int BATT_LOW_PCT = 20, BATT_CRITICAL_PCT = 10;
enum BattLevel { BATT_OK, BATT_LOW, BATT_CRITICAL };
inline BattLevel battLevel(int pct) {
  return pct < BATT_CRITICAL_PCT ? BATT_CRITICAL : pct < BATT_LOW_PCT ? BATT_LOW : BATT_OK;
}

// ---- battery: resting Li-ion voltage -> percent (rough: a loaded or charging cell reads off by a few percent)
inline int battPercent(float v) {
  static const float V[] = {3.20f, 3.45f, 3.60f, 3.70f, 3.80f, 3.90f, 4.00f, 4.10f, 4.18f};
  static const int P[] = {0, 5, 15, 35, 55, 70, 82, 93, 100};
  if (v <= V[0]) return 0;
  for (int k = 1; k < 9; k++)
    if (v < V[k]) return P[k - 1] + (int)((P[k] - P[k - 1]) * (v - V[k - 1]) / (V[k] - V[k - 1]));
  return 100;
}

// ---- sun: sunrise or sunset (epoch seconds) on the day that holds `noon`, at a place. 0 if the sun does not rise or set.
inline uint32_t sunEventAt(time_t noon, double lat, double lon, bool rise) {
  if (std::isnan(lat) || std::isnan(lon)) return 0;
  const double R = M_PI / 180.0;
  // The solar day whose mean noon at this longitude is nearest `noon`. (Rounding up from the Julian date instead picked
  // the next day whenever local noon falls after 12:00 UTC, as it does in the Americas.)
  double n = round(noon / 86400.0 + 2440587.5 - 2451545.0 + 0.0008 + lon / 360.0), js = n - lon / 360.0;
  double M = fmod(357.5291 + 0.98560028 * js, 360.0), C = 1.9148 * sin(M * R) + 0.02 * sin(2 * M * R) + 0.0003 * sin(3 * M * R);
  double lam = fmod(M + C + 180.0 + 102.9372, 360.0), jt = 2451545.0 + js + 0.0053 * sin(M * R) - 0.0069 * sin(2 * lam * R);
  double sd = sin(lam * R) * sin(23.4397 * R), cd = cos(asin(sd));
  double ch = (sin(-0.833 * R) - sin(lat * R) * sd) / (cos(lat * R) * cd);
  if (ch < -1 || ch > 1) return 0;
  double w = acos(ch) / R, jd = jt + (rise ? -w : w) / 360.0;
  return (uint32_t)((jd - 2440587.5) * 86400.0);
}

// ---- Power source (CONTEXT.md): where input power comes from, sent as `src` next to `chg`. On the v2.2 board solar and
// USB share one input line and overlap in voltage, so the only safe call is "input power while the sun is well down":
// a panel gives nothing in the dark, so it can only be the cable. Anything else with input power is unknown. Solar (1)
// is never sent here; a v3 board that reads the sources apart replaces this rule. rise/set: today's, 0 if not known.
enum PowerSource { SRC_BATTERY = 0, SRC_SOLAR = 1, SRC_USB = 2, SRC_UNKNOWN = 3 };
const uint32_t SRC_NIGHT_MARGIN_S = 3600;      // past twilight: the nearly unloaded input line can hold a panel's voltage
inline PowerSource powerSourceOf(bool powered, bool clockOk, uint32_t now, uint32_t rise, uint32_t set) {
  if (!powered) return SRC_BATTERY;
  if (clockOk && rise && set && (now + SRC_NIGHT_MARGIN_S < rise || now > set + SRC_NIGHT_MARGIN_S)) return SRC_USB;
  return SRC_UNKNOWN;
}

// ---- time zone: the POSIX zone string Schedules run on (Settings.tz: cap bytes, its end included)
// A zone a controller takes: at least 3 characters, and it fits the field.
inline bool zoneOk(const char *tz, size_t cap) { size_t n = strlen(tz); return n >= 3 && n < cap; }
// Run on this zone. The only place the firmware sets it (cfgApply when tz changes, schedBegin at start). It changes the
// process's TZ: the one piece of shared state this file touches.
inline void zoneUse(const char *tz) { setenv("TZ", tz, 1); tzset(); }
// A slot's local clock time on the day (now + dayOff): that day at minuteOfDay in the running zone, daylight time
// worked out by mktime. 0 when that day's weekday is not in days (bit 0 = Sunday).
inline uint32_t slotDayTime(time_t now, int dayOff, int minuteOfDay, uint8_t days) {
  struct tm tm, chk;
  localtime_r(&now, &tm);
  tm.tm_mday += dayOff;
  tm.tm_hour = 0; tm.tm_min = minuteOfDay; tm.tm_sec = 0; tm.tm_isdst = -1;
  time_t t = mktime(&tm);
  localtime_r(&t, &chk);
  if (!((days >> chk.tm_wday) & 1)) return 0;
  return (uint32_t)t;
}

// ---- Schedule kinds (the kind byte of a slot): 0 at a clock time, 1 at sunrise, 2 at sunset, 3 when it gets light
// (around sunrise), 4 when it gets dark (around sunset). 3 and 4 are the Light trigger (CONTEXT.md).
const int LIGHT_KIND_LIGHT = 3, LIGHT_KIND_DARK = 4;      // the highest kind: wire.h slotOfArgs clamps to 4
inline bool isSunKind(int k) { return k >= 1 && k <= 4; }
inline bool onSunrise(int k) { return k == 1 || k == 3; }
inline bool isLightKind(int k) { return k == LIGHT_KIND_LIGHT || k == LIGHT_KIND_DARK; }

// ---- the Light trigger: dark or light read from the solar panel's input, inside a window around the slot's base time
// (that day's sunrise or sunset plus the offset), at most once a day, falling back to the window's end. Real levels and
// minutes come from dusk and dawn data (#212); these are the starting ones (#207).
const uint32_t LIGHT_WINDOW_S = 90 * 60;       // readings count only within this of the base time, either way
const float LIGHT_DARK_V = 0.3f, LIGHT_LIT_V = 1.5f;   // dark: under; light: over. Between: neither, and a run is broken
const int LIGHT_DARK_MIN = 15, LIGHT_LIT_MIN = 10;     // minutes in a row it takes
const uint32_t LIGHT_GAP_S = 1800;             // a step gap over this (off, clock jump): nothing that passed is run late
enum LightWhy { LIGHT_NONE = 0, LIGHT_BY_LIGHT = 1, LIGHT_FELL_BACK = 2, LIGHT_SUN_TIME = 3 };
// One slot's memory. day: the key of the day it last fired (kept in flash, so a restart does not fire it again);
// at/why: when and why; run: minutes in a row of the steady reading so far; armed: a reading on the other side was
// seen inside today's window, so a run that follows is a real change (run and armed are not kept over a restart).
struct LightLatch { uint32_t day, at; uint8_t why, run, armed, pad; };
// Does a slot keep its latch when it is written again (web.h hSched, a settings restore)? Only when it is the same
// Schedule: the same id and kind. An edit is not a new day; another Schedule in the slot has not run.
inline bool lightLatchKept(uint32_t oldGid, int oldKind, uint32_t newGid, int newKind) { return oldGid == newGid && oldKind == newKind; }
// A slot's base time and day key for the day nearest `now` (yesterday, today, tomorrow). The key is the local date of
// the sun event's day, as yyyymmdd. {0, 0}: no base (not one of its days, no place, no sunrise or sunset).
struct LightDay { uint32_t base, key; };
inline LightDay lightDayOf(time_t now, int kind, int off, uint8_t days, double lat, double lon) {
  LightDay best = {0, 0};
  for (int d = -1; d <= 1; d++) {
    uint32_t noon = slotDayTime(now, d, 720, days);
    if (!noon) continue;
    uint32_t e = sunEventAt(noon, lat, lon, onSunrise(kind));
    if (!e) continue;
    uint32_t base = e + off * 60;
    if (best.base && llabs((long long)now - base) >= llabs((long long)now - best.base)) continue;
    struct tm tm;
    time_t n = noon;
    localtime_r(&n, &tm);
    best = {base, (uint32_t)((tm.tm_year + 1900) * 10000 + (tm.tm_mon + 1) * 100 + tm.tm_mday)};
  }
  return best;
}
// One step, once a minute, for one light slot. now / prev: this step and the one before; base, key: lightDayOf;
// v: the minute's mean input voltage; panel: a panel seen (panelSeenRule). Answers whether the slot fires now, and why.
// A run counts only once the slot is armed: a reading on the other side inside the window. An input that was already
// dark (or light) when the window opened, such as a panel unplugged at midday or a USB cable at dawn, falls back.
inline LightWhy lightStep(LightLatch &l, int kind, uint32_t now, uint32_t prev, uint32_t base, uint32_t key, float v, bool panel) {
  bool gap = prev >= now || now - prev > LIGHT_GAP_S;       // as schedRun: what passed while off is not run late
  if (gap) l.run = l.armed = 0;
  if (!base || l.day == key) { l.run = l.armed = 0; return LIGHT_NONE; }
  uint32_t end = base + LIGHT_WINDOW_S;
  bool endNow = !gap && end > prev && end <= now;
  LightWhy why = LIGHT_NONE;
  if (!panel) {
    l.run = l.armed = 0;
    if (!gap && base > prev && base <= now) why = LIGHT_SUN_TIME;
  } else if (now + LIGHT_WINDOW_S >= base && now <= end) {
    bool steady = kind == LIGHT_KIND_DARK ? v < LIGHT_DARK_V : v > LIGHT_LIT_V;
    if (!steady) { l.run = 0; l.armed = 1; }
    else if (l.armed) l.run = (uint8_t)(l.run < 255 ? l.run + 1 : 255);
    if (l.run >= (kind == LIGHT_KIND_DARK ? LIGHT_DARK_MIN : LIGHT_LIT_MIN)) why = LIGHT_BY_LIGHT;
    else if (endNow) why = LIGHT_FELL_BACK;
  } else {
    l.run = l.armed = 0;
    if (endNow) why = LIGHT_FELL_BACK;                      // a step just past the end
  }
  if (why) { l.day = key; l.at = now; l.why = (uint8_t)why; l.run = l.armed = 0; }
  return why;
}
// A minute's mean of readings taken every second or so. add: true when a minute just ended, with its mean in *mean.
struct MinuteMean {
  uint32_t minute = 0; float sum = 0; int n = 0;
  bool add(uint32_t now, float v, float *mean) {
    bool done = false;
    if (now / 60 != minute) {
      if (n && minute) { *mean = sum / n; done = true; }
      minute = now / 60; sum = 0; n = 0;
    }
    sum += v; n++;
    return done;
  }
};
// Solar panel seen: the input was dark for a steady run at night (sun down over an hour) and lit for a steady run by
// day, both within 3 days. The v2.2 board cannot tell solar from USB by voltage (powerSourceOf), but a cable left in
// never goes dark and nothing plugged in never goes lit. lastDark / lastLit: when each was last seen (0: never).
const uint32_t PANEL_SEEN_S = 3 * 86400, PANEL_SAVE_S = 24 * 3600;
inline bool panelSeenRule(uint32_t now, uint32_t lastDark, uint32_t lastLit) {
  return lastDark && lastLit && lastDark <= now && lastLit <= now && now - lastDark <= PANEL_SEEN_S && now - lastLit <= PANEL_SEEN_S;
}
// The day and night watch behind it, once a minute. rise / set: today's (0 not known). A time is taken only when the
// one held is a day old or more, so flash is written at most twice a day: true = it changed, save it.
struct PanelWatch { uint32_t lastDark, lastLit; uint8_t darkRun, litRun, pad[2]; };
inline bool panelStep(PanelWatch &w, uint32_t now, float v, uint32_t rise, uint32_t set) {
  if (!rise || !set) { w.darkRun = w.litRun = 0; return false; }
  bool night = now + SRC_NIGHT_MARGIN_S < rise || now > set + SRC_NIGHT_MARGIN_S, day = now > rise && now < set;
  w.darkRun = night && v < LIGHT_DARK_V ? (uint8_t)(w.darkRun < 255 ? w.darkRun + 1 : 255) : 0;
  w.litRun = day && v > LIGHT_LIT_V ? (uint8_t)(w.litRun < 255 ? w.litRun + 1 : 255) : 0;
  bool changed = false;
  if (w.darkRun >= LIGHT_DARK_MIN && (!w.lastDark || now - w.lastDark >= PANEL_SAVE_S)) { w.lastDark = now; changed = true; }
  if (w.litRun >= LIGHT_LIT_MIN && (!w.lastLit || now - w.lastLit >= PANEL_SAVE_S)) { w.lastLit = now; changed = true; }
  return changed;
}

// ---- stall: once the gear play is taken up, the angle has to change by minDeg every stallMs
enum StallVerdict { STALL_WAIT, STALL_MOVED, STALL_YES };
inline StallVerdict stallCheck(uint32_t elapsed, uint32_t grace, uint32_t sinceRef, uint32_t stallMs, float ang, float ref, float minDeg) {
  if (elapsed <= grace || sinceRef < stallMs) return STALL_WAIT;
  return fabsf(angDiff(ang, ref)) < minDeg ? STALL_YES : STALL_MOVED;
}

// ---- this controller's own Apple Home setup code (home_code.h keeps it in flash; made once, never changed)
const uint32_t HOME_CODE_MAGIC = 0x48430001;
struct HomeCode { uint32_t magic, pin, iter; uint16_t disc; uint8_t salt[32], verifier[97]; };
inline bool setupPinValid(uint32_t pin) {                    // the Matter rules: 1..99999998, not 11111111 and the like
  if (pin == 0 || pin > 99999998 || pin == 12345678 || pin == 87654321) return false;
  return pin % 11111111 != 0;
}
// Keep what flash holds (n bytes read), or make a new one?
inline bool homeCodeKeep(const HomeCode &c, size_t n) {
  return n == sizeof c && c.magic == HOME_CODE_MAGIC && setupPinValid(c.pin) && c.disc <= 0xFFF && c.iter >= 1000 && c.iter <= 100000;
}
// "12345678901" -> "1234-567-8901", as Apple Home shows it
inline std::string manualCodeDashed(const std::string &d) {
  return d.size() == 11 ? d.substr(0, 4) + "-" + d.substr(4, 3) + "-" + d.substr(7) : d;
}

// ---- secured commands: nonce = boot id (4) | counter (8, big-endian). Fresh = this start's boot id and a counter
// above the last one accepted from that phone (so a captured command cannot be replayed).
inline uint64_t nonceCounter(const uint8_t nonce[12]) { uint64_t c = 0; for (int i = 4; i < 12; i++) c = (c << 8) | nonce[i]; return c; }
inline bool nonceFresh(const uint8_t nonce[12], const uint8_t boot[4], uint64_t last) {
  return !memcmp(nonce, boot, 4) && nonceCounter(nonce) > last;
}

// ---- firmware versions: "2.3.0", "2.3.0-dev7". A release is newer than its own dev builds. A firmware file may not
// be older than the one running (a known-bad old build could otherwise be put back). Unreadable: treated as older.
inline bool fwParse(const char *s, long v[4]) {
  char *e;
  for (int i = 0; i < 3; i++) {
    if (!s || *s < '0' || *s > '9') return false;
    v[i] = strtol(s, &e, 10);
    s = e;
    if (i < 2) { if (*s != '.') return false; s++; }
  }
  if (!*s) { v[3] = 1L << 30; return true; }   // a release
  if (*s != '-') return false;
  while (*s && (*s < '0' || *s > '9')) s++;
  v[3] = *s ? strtol(s, nullptr, 10) : 0;
  return true;
}
inline bool fwIsOlder(const char *candidate, const char *running) {
  long a[4], b[4];
  if (!fwParse(running, b)) return false;        // nothing to compare with
  if (!fwParse(candidate, a)) return true;
  for (int i = 0; i < 4; i++) if (a[i] != b[i]) return a[i] < b[i];
  return false;
}

// ---- which slot a new phone key takes (sec.h pairDo). used: 0 free, 1 paired, 2 asked to join and waiting; waitMs:
// how long each waiting one has waited (a very large number when not known). At most two asks wait: a new ask takes
// the place of one that has waited over 10 minutes. A recovery (people.h) is never kept out by waiting asks (the
// phone's own ask and the Tilt Hub's are often among them): it takes a free slot, else the oldest waiting ask.
// Returns the slot, KEY_TWO_WAITING or KEY_FULL.
const int KEY_TWO_WAITING = -1, KEY_FULL = -2;
inline int keySlot(const uint8_t *used, const uint32_t *waitMs, int n, bool ask, bool recovering) {
  int waiting = 0, oldest = -1;
  for (int i = 0; i < n; i++) if (used[i] == 2) { waiting++; if (oldest < 0 || waitMs[i] > waitMs[oldest]) oldest = i; }
  if (ask && !recovering && waiting >= 2) {
    for (int i = 0; i < n; i++) if (used[i] == 2 && waitMs[i] > 600000) return i;
    return KEY_TWO_WAITING;
  }
  for (int i = 0; i < n; i++) if (!used[i]) return i;
  if (recovering && oldest >= 0) return oldest;
  return KEY_FULL;
}

// ---- an answer kept for a request that may come again: the hub sends a request a second time when no answer came
// (its answer was lost, or late), and an ask or a recovery must not run twice for the same key (hub_link.h).
struct KeptAnswer {
  std::string in, out;
  const char *st = nullptr;
  uint32_t at = 0;
  bool again(const std::string &req, uint32_t now, uint32_t forMs = 30000) const { return st && in == req && now - at < forMs; }
  void keep(const std::string &req, const char *status, const std::string &answer, uint32_t now) { in = req; st = status; out = answer; at = now; }
};

// ---- the requests the Tilt Hub may send this controller (hub_link.h); anything else is ignored, never answered
inline bool hubAsks(char t) { return t && strchr("HXAQRBWEs", t); }

// ---- who may do what (sec.h permit() gathers the facts and asks this; the roles are in routes.h)
// owner: the caller is an Owner (else a Guest). cidArg: the "cid" in the command; ownCid: the caller's own id (hex).
// nullptr: allowed. Otherwise the reason it is refused.
inline const char *permitRule(Who who, bool owner, const std::string &cidArg, const std::string &ownCid) {
  if (owner || who == GUEST) return nullptr;
  if (who == SELF && !cidArg.empty() && cidArg == ownCid) return nullptr;
  return "only the owner can do that";
}

// ---- the owner's firmware update window (web.h hOtaOpen sets until; hub_link.h hubOtaBegin asks)
// until: millis() when the window shuts (0: never opened). Safe across the 32-bit millis wrap.
inline bool otaWindowOpen(uint32_t until, uint32_t now) { return (int32_t)(until - now) > 0; }
