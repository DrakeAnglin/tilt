// Pure logic: no ESP-IDF, no hardware, no shared state. Everything here is plain math or a rule on its inputs, so it
// is tested on the Mac (test/logic_test.cpp, run with tools/firmware_tests.sh). The firmware calls these.
#pragma once
#include <cmath>
#include <cstdint>
#include <cstring>
#include <ctime>
#include <string>

// ---- angles
inline float angDiff(float to, float from) { return fmodf(to - from + 540.0f, 360.0f) - 180.0f; }   // shortest, -180..180
inline float sgn(float v) { return v < 0 ? -1.0f : 1.0f; }

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

// ---- can a blind be moved? Shown (not hidden in the app), set up (all three marks good), and its tilter not missing.
inline bool movableRule(bool hidden, bool calibrated, bool seen, bool present) { return !hidden && calibrated && !(seen && !present); }

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

// ---- secured commands: nonce = boot id (4) | counter (8, big-endian). Fresh = this start's boot id and a counter
// above the last one accepted from that phone (so a captured command cannot be replayed).
inline uint64_t nonceCounter(const uint8_t nonce[12]) { uint64_t c = 0; for (int i = 4; i < 12; i++) c = (c << 8) | nonce[i]; return c; }
inline bool nonceFresh(const uint8_t nonce[12], const uint8_t boot[4], uint64_t last) {
  return !memcmp(nonce, boot, 4) && nonceCounter(nonce) > last;
}

// ---- who may do what (sec.h permit() gathers the facts and asks this)
// plainOpen: no phone owns the controller yet, or the developer switch is on. cidArg: the "cid" in the command; ownCid: the
// caller's own id (hex). nullptr: allowed. Otherwise the reason it is refused.
inline const char *permitRule(bool secure, bool owner, bool plainOpen, bool isUpdate, const std::string &path,
                              const std::string &cidArg, const std::string &ownCid) {
  if (!secure) return (isUpdate || plainOpen) ? nullptr : "use the app";   // an update checks its own signature
  if (owner) return nullptr;
  // a user: see the blinds and move them, see the people, rename only themself
  for (const char *ok : {"/api/s", "/api/cfg", "/api/go", "/api/stop", "/api/keys", "/api/wifistate"}) if (path == ok) return nullptr;
  if (path == "/api/keyname" && !cidArg.empty() && cidArg == ownCid) return nullptr;
  return "only the owner can do that";
}
