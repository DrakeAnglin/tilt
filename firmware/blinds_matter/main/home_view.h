// What Apple Home sees and asks, as plain rules: no esp-matter, no hardware, no shared state. Tested on the Mac
// (test/logic_test.cpp). app_main.cpp hands the results to Matter.
//
// A Window covering today carries tilt on Matter's lift channel as "percent closed" in hundredths:
// 0 = open (slats level), 10000 = closed, whichever way the slats are closed. Home's slider shows 100 - that.
#pragma once
#include <cmath>
#include <cstdint>
#include <cstdlib>

// ---- what Home asked for (TargetPositionLiftPercent100ths)
const uint16_t HOME_LIFT_NULL = 0xFFFF;                 // a null target (esp-matter stores null as the top value)
inline bool homeLiftValid(uint32_t lift) { return lift <= 10000; }   // anything else (null) is ignored, never a close
// lift hundredths -> tilt Target: closed in the "Close" direction (closeUp: up = +100, else down = -100)
inline float tiltOfHomeLift(int lift, bool closeUp) { return (closeUp ? 1.0f : -1.0f) * lift / 100.0f; }
// Home's "stop" arrives as "go to where you are": a target within 1 % of what was last reported, while moving.
inline bool homeAskIsStop(bool moving, int lift, int lastLift) { return moving && abs(lift - lastLift) < 100; }

// ---- what Home should see for one endpoint
struct BlindNow { float tilt; bool busy; float target; };   // Current tilt (NaN = unknown); busy = moving or queued
struct HomeView {
  bool any;          // false: no blind with a known tilt, send nothing
  int lift;          // percent closed, hundredths (whole percents)
  int op;            // 0 still, 1 opening, 2 closing
};
inline HomeView homeViewOf(const BlindNow *b, int n) {
  HomeView v{false, 0, 0};
  float sum = 0;
  int k = 0;
  for (int i = 0; i < n; i++) {
    float t = b[i].tilt;
    if (std::isnan(t)) continue;
    float c = fminf(fabsf(t), 100.0f);
    // A blind at rest within its stopping band of an end IS at that end: a move to "closed" may stop at 97 to 99,
    // and Home would show "1 % open" for good. While it moves, the true value is sent.
    if (!b[i].busy) { if (c >= 94.0f) c = 100.0f; else if (c <= 6.0f) c = 0.0f; }
    sum += c;
    k++;
    if (!std::isnan(b[i].target) && b[i].busy) v.op = fabsf(b[i].target) > fabsf(t) ? 2 : 1;
  }
  if (!k) return v;
  v.any = true;
  v.lift = (int)lroundf(sum / k) * 100;
  return v;
}
// Which attributes to send, given what was sent last (-1 = nothing yet).
struct HomeSend { bool lift, target, op; uint8_t opBits; };
inline HomeSend homeSendOf(const HomeView &v, bool force, int lastLift, int lastOp) {
  HomeSend s{false, false, false, 0};
  if (!v.any) return s;
  s.lift = force || abs(v.lift - lastLift) >= 100;   // a change of at least 1 %
  s.target = s.lift && !v.op;                       // at rest the target is where it is
  s.op = v.op != lastOp;
  s.opBits = (uint8_t)(v.op | (v.op << 2));         // global and lift bits: 1 opening, 2 closing
  return s;
}

// ---- battery attributes from Battery level (percent)
inline uint8_t homeBatPercent(int pct) { return (uint8_t)(pct * 2); }   // Matter counts half percents
inline uint8_t homeChargeLevel(int pct) { return pct < 10 ? 2 : pct < 20 ? 1 : 0; }   // 2 Critical, 1 Low, 0 OK
