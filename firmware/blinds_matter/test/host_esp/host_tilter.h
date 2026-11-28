// A stand-in tilter on each port of the host board (host_board.h), behind the controller's pins, built on the rod
// model in test/sim_rod.h. The controller's code (main/motion.h) drives it as it drives the real one. Tests only.
//
// What a test can do (namespace host):
//   plugAnalog(p, deg) / plugPwm(p, deg)   plug a tilter with its rod at deg into port p; unplug(p) leaves it empty
//   tilter(p)                              the port's tilter: its rod (angle, gear play, speed, end stops, phys = -1
//                                          for a motor wired the other way round), and the switches below
//   hold(p) / letGo(p)                     hold the rod where it is (a stall), or let it go
//   turnByHand(p, deg)                     a Manual move: a jump of deg; turnByHand(p, degPerS, ms): a steady turn
//   dropout(p, ms)                         the sensor gives nothing for a while (analog: 0 V; PWM: no pulses)
//   rest(p, high)                          a PWM sensor at its zero: no pulses, the line at 0 V (or the rail)
//   railMv                                 the rail the sensor's supply comes from (millivolts)
//
// What it does by itself:
//   it reads the port's motor pins from the LEDC duties as the DRV8833 does (one pin at 255 and the other lower:
//   turning, at the share the other is below 255; both at 255: braked), and turns the rod as the clock moves;
//   it is off while the port's EN pin is low, and gives nothing for the first WARM_MS after EN goes high;
//   it reads about 3 degrees high while its motor runs (the shared ground wire);
//   it answers the angle pin's ADC read: an analog sensor with its angle as a share of its supply (the rail less
//   EN_DROP_V), a PWM sensor resting with 0 V or the rail, a PWM sensor sending with the frame's average; an empty
//   port with the level the pin was last pushed to (a floating pin keeps it; never pushed: what the test set);
//   a PWM sensor that is on sends 115 frames a second to the capture channel on its pin (driver/mcpwm_cap.h), in
//   time order, with the board's clock set to each edge's time.
#pragma once
#include "config.h"                                    // the controller's pins and EN_DROP_V
#include "driver/mcpwm_cap.h"
#include "host_board.h"
#include "../sim_rod.h"

namespace host {

const int64_t WARM_MS = 5;                             // after EN goes high: nothing yet
const int64_t FRAME_TICKS = CAP_HZ / 115;              // one PWM frame
inline int &railMv() { static int mv = 3300; return mv; }

struct HostTilter : Rod {
  bool plugged = false, pwm = false;
  bool resting = false, restHigh = false;              // PWM: at its zero, no pulses
  int64_t dropUntil = 0;                               // the sensor gives nothing until then (board microseconds)
  float handRate = 0;                                  // a hand turning it steadily (deg/s) ...
  int64_t handUntil = 0;                               // ... until then
  int angleReads = 0;                                  // ADC reads of its angle pin (any port state)
  // the board side
  bool on = false;                                     // EN high
  int64_t onAt = 0;
  bool sending = false;                                // PWM frames going out
  int64_t edgeTick = 0;                                // the next edge, in capture ticks (us * 80)
  bool edgeRise = true;
  int64_t frameTick = 0;                               // the frame's start
};
inline HostTilter *tilters() { static HostTilter t[PORTS]; return t; }
inline HostTilter &tilter(int p) { return tilters()[p]; }

inline int motorDir(int p, int *duty) {                // the DRV8833 inputs: -1 / 0 / +1, and the duty in percent
  int a = dutyOf(P_IN1[p]), b = dutyOf(P_IN2[p]);
  *duty = 0;
  if (a < 0 || b < 0) return 0;
  if (a == 255 && b < 255) { *duty = (255 - b) * 100 / 255; return 1; }
  if (b == 255 && a < 255) { *duty = (255 - a) * 100 / 255; return -1; }
  return 0;
}
inline bool enHigh(int p) { return pinLevel(P_EN[p]) == 1; }
inline bool motorRunning(int p) { int d; return enHigh(p) && motorDir(p, &d) != 0; }
inline bool warm(int p, int64_t us) { HostTilter &t = tilter(p); return t.on && us - t.onAt >= WARM_MS * 1000; }
inline bool dropping(int p, int64_t us) { return us < tilter(p).dropUntil; }
inline float seenDeg(int p) {                          // what the sensor sees now: 3 degrees high while the motor runs
  return fmodf(tilter(p).wrapped() + (motorRunning(p) ? 3.0f : 0) + 360.0f, 360.0f);
}
inline bool pulsing(int p, int64_t us) {
  HostTilter &t = tilter(p);
  return t.plugged && t.pwm && warm(p, us) && !dropping(p, us) && !t.resting;
}
inline int64_t highTicks(int p) {                      // AS5600: 128 clocks of lead-in, 4095 for the angle, of 4351
  return (int64_t)llround((128.0 + seenDeg(p) / 360.0 * 4095.0) / 4351.0 * FRAME_TICKS);
}

// EN, followed as it is written (onLevel).
inline void syncEn(int p) {
  HostTilter &t = tilter(p);
  bool en = t.plugged && enHigh(p);
  if (en && !t.on) { t.on = true; t.onAt = nowUs(); t.sending = false; }
  if (!en) { t.on = false; t.sending = false; }
}
inline void syncSending(int p) {
  HostTilter &t = tilter(p);
  bool s = pulsing(p, nowUs());
  if (s && !t.sending) { t.frameTick = t.edgeTick = nowUs() * 80; t.edgeRise = true; }
  t.sending = s;
}
inline int64_t edgeUs(int64_t tick) { return (tick + 79) / 80; }

// The next time something about port p changes by itself after `now` (an edge, the warm-up's end, a dropout's end,
// a hand that lets go); `to` if none comes first.
inline int64_t nextChange(int p, int64_t now, int64_t to) {
  HostTilter &t = tilter(p);
  int64_t n = to;
  if (t.sending) n = std::min(n, std::max(edgeUs(t.edgeTick), now));
  if (t.on && !warm(p, now)) n = std::min(n, t.onAt + WARM_MS * 1000);
  if (dropping(p, now)) n = std::min(n, t.dropUntil);
  if (t.handUntil > now) n = std::min(n, t.handUntil);
  return n;
}
inline void turnFor(int p, int64_t dUs) {              // the motor and a hand turn the rod for dUs
  HostTilter &t = tilter(p);
  if (!t.plugged || dUs <= 0) return;
  float ms = dUs / 1000.0f;
  if (t.handUntil > nowUs()) { t.rod += t.handRate * ms / 1000.0f; t.gear += t.handRate * ms / 1000.0f; }
  int duty, d = t.on ? motorDir(p, &duty) : 0;
  t.turn(d, d ? duty : 0, ms);
}
inline void sendEdges(int p) {                         // the edges due now
  HostTilter &t = tilter(p);
  while (t.sending && edgeUs(t.edgeTick) <= nowUs()) {
    capEdge(P_ANG[p], t.edgeRise, (uint32_t)t.edgeTick);
    if (t.edgeRise) { t.edgeTick = t.frameTick + highTicks(p); t.edgeRise = false; }
    else { t.frameTick += FRAME_TICKS; t.edgeTick = t.frameTick; t.edgeRise = true; }
  }
}
inline void clockMoves(int64_t to) {
  for (int p = 0; p < PORTS; p++) { syncEn(p); syncSending(p); sendEdges(p); }
  while (nowUs() < to) {
    int64_t now = nowUs(), next = to;
    for (int p = 0; p < PORTS; p++) next = std::min(next, nextChange(p, now, to));
    if (next <= now) next = now + 1;
    for (int p = 0; p < PORTS; p++) turnFor(p, next - now);
    setUs(next);
    for (int p = 0; p < PORTS; p++) { syncSending(p); sendEdges(p); }
  }
}

inline bool answerAdc(int pin, int *mv) {
  for (int p = 0; p < PORTS; p++) {
    if (pin != P_ANG[p]) continue;
    HostTilter &t = tilter(p);
    syncEn(p);
    t.angleReads++;
    int64_t now = nowUs();
    if (!t.plugged) {                                  // a floating pin: the level it was last pushed to
      int lv = pinLevel(pin);
      if (lv < 0) return false;
      *mv = lv ? railMv() : 0;
      return true;
    }
    float supply = railMv() - EN_DROP_V * 1000.0f;
    if (!warm(p, now) || dropping(p, now)) *mv = 0;
    else if (t.pwm && t.resting) *mv = t.restHigh ? railMv() : 0;
    else if (t.pwm) *mv = (int)lroundf(highTicks(p) / (float)FRAME_TICKS * railMv());
    else *mv = (int)lroundf(seenDeg(p) / 360.0f * supply);
    return true;
  }
  return false;
}

inline void tiltersRestart() {                         // the board starts again: the tilters stay plugged in, all off
  for (int p = 0; p < PORTS; p++) { HostTilter &t = tilter(p); t.on = t.sending = false; t.dropUntil = t.handUntil = 0; }
}
inline void levelWritten(int pin) { for (int p = 0; p < PORTS; p++) if (pin == P_EN[p]) syncEn(p); }
inline const bool tiltersHooked =
    (onClock(clockMoves), onLevel(levelWritten), adcSource(answerAdc), onRestart(tiltersRestart), true);

inline HostTilter &plug(int p, float deg, bool pwm) {
  HostTilter &t = tilter(p);
  t = HostTilter();
  t.plugged = true;
  t.pwm = pwm;
  t.rod = t.gear = deg;
  syncEn(p);
  return t;
}
inline HostTilter &plugAnalog(int p, float deg) { return plug(p, deg, false); }
inline HostTilter &plugPwm(int p, float deg) { return plug(p, deg, true); }
inline void unplug(int p) { HostTilter &t = tilter(p); t = HostTilter(); }
inline void hold(int p) { HostTilter &t = tilter(p); t.lo = t.hi = t.rod; }
inline void letGo(int p) { HostTilter &t = tilter(p); t.lo = -1e9f; t.hi = 1e9f; }
inline void turnByHand(int p, float deg) { HostTilter &t = tilter(p); t.rod += deg; t.gear += deg; }
inline void turnByHand(int p, float degPerS, int64_t ms) { HostTilter &t = tilter(p); t.handRate = degPerS; t.handUntil = nowUs() + ms * 1000; }
inline void dropout(int p, int64_t ms) { tilter(p).dropUntil = nowUs() + ms * 1000; }
inline void rest(int p, bool high = false) { HostTilter &t = tilter(p); t.resting = true; t.restHigh = high; }

}  // namespace host
