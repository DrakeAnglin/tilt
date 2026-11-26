// Pure logic: no ESP-IDF, no hardware, no shared state. Everything here is plain math or a rule on its inputs, so it
// is tested on the Mac (test/logic_test.cpp, run with tools/firmware_tests.sh). The firmware calls these.
#pragma once
#include <cmath>
#include <cstdint>
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
// last seen near there (or nothing is known yet). Anywhere else it is a dropout (the sensor gave nothing: 2026-11-25,
// Dining read 0 deg at rest and moves and Follow took it as real): no reading. Either way the angle given is the last
// good one, and `guess` says the angle is not fresh. raw: what the sensor gave; last: the last good angle (NAN: none).
const float ANALOG_RAIL_MV = 30.0f;                 // an analog output under this is at 0 V (about 4 degrees)
struct SensorRead { float ang; bool guess, lost; };
inline SensorRead judgeReading(float raw, bool atRail, float last) {
  if (!atRail) return {raw, false, false};
  if (std::isnan(last)) return {raw, true, false};                      // nothing known yet: it may sit at its zero
  if (pwmBlindSpot(fmodf(last + 360.0f, 360.0f) / 360.0f)) return {last, true, false};   // near zero before: still there
  return {last, true, true};                                            // a dropout
}

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
