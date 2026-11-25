// Follow and the watch, as one plain value: which blind's sensor is kept on and read live, and when a turn of the
// wand sends the other blinds to the same tilt (ADR 0004: only a Manual move is followed). No hardware, no shared
// state: motion.h is its adapter (it powers the sensor, reads it, and starts the follow), and test/logic_test.cpp
// tests it on the Mac.
//
// Two reasons to watch a blind:
//   Setup is open for it (the app asks every second, setupOpen), or a recovery is under way: keep its reading live.
//     Hands on the wands are expected then, so nothing is followed for SETUP_QUIET_MS after.
//   Its wand is being turned (hand): the idle look-round saw it away from where the controller left it. It stays
//     watched until it has held still for HAND_STILL_MS, then the others follow, once.
#pragma once
#include <cmath>
#include <cstdint>
#include "logic.h"                               // PORTS, angDiff

struct HandWatchNow {
  int watchPort;             // the blind whose sensor stays on and is read every 100 ms; -1 = none
  int followFrom;            // a wand turn just ended on this blind: send the others to followTilt (once); -1 = none
  float followTilt;
};

struct HandWatch {
  static constexpr float HAND_TILT = 6.0f;            // a change of this much (tilt units) starts a hand watch
  static constexpr float HAND_MOVED = HAND_TILT * 0.6f;   // and it ends as a turn if it moved at least this much
  static constexpr float STILL_DEG = 0.7f;            // a reading that moves less than this is "still"
  static constexpr uint32_t HAND_STILL_MS = 1500;     // still this long: the hand is done (a pause while turning is shorter)
  static constexpr uint32_t HAND_MAX_MS = 60000;      // a hand watch never lasts longer: nothing is followed then
  static constexpr uint32_t WATCH_MS = 3000;          // a watch ends this long after its last reason
  static constexpr uint32_t SETUP_QUIET_MS = 15000;   // no following this long after a setup screen was open

  float ref[PORTS] = {NAN, NAN, NAN};                 // each blind's tilt as the controller last left it
  int port = -1;
  bool hand = false;                                  // the watch is on a blind being turned by hand
  uint32_t until = 0, setupAt = 0;                    // setupAt: the last "setup is open" (0 = never)
  uint32_t still = 0, since = 0;                      // hand: last time it moved; when the watch started
  float last = 0;                                     // hand: the angle it last moved to
  int followFrom = -1;
  float followTilt = NAN;

  // A fresh reading of blind p with its motor stopped. tilt is NAN when the blind cannot be moved (not set up,
  // hidden, no tilter); noReading: a PWM sensor at its zero, the angle is a guess. Readings of a blind that is not
  // being watched start a hand watch when it has moved; the adapter gives them only with Follow on.
  void reading(int p, float tilt, float ang, bool noReading, uint32_t now) {
    if (p < 0 || p >= PORTS) return;
    if (port < 0) { look(p, tilt, ang, noReading, now); return; }
    if (port != p || !hand) return;
    until = now + WATCH_MS;
    bool timeout = now - since > HAND_MAX_MS;
    if (!timeout) {
      if (noReading) { still = now; return; }
      if (fabsf(angDiff(ang, last)) > STILL_DEG) { last = ang; still = now; }
      if (now - still < HAND_STILL_MS) return;
    }
    float t = std::isnan(tilt) ? NAN : fminf(fmaxf(tilt, -100.0f), 100.0f);
    bool moved = !timeout && !std::isnan(t) && fabsf(t - ref[p]) >= HAND_MOVED;
    ref[p] = tilt;
    end();
    if (moved) { followFrom = p; followTilt = t; }
  }
  // Setup (or a recovery) is open for blind p: watch it, and follow nothing for a while.
  void setupOpen(int p, uint32_t now) {
    if (p < 0 || p >= PORTS) return;
    end();
    port = p;
    until = now + WATCH_MS;
    setupAt = now ? now : 1;
  }
  // A mark was set on p: its tilt is on a new scale, so where the controller left it is not known.
  void marked(int p, uint32_t now) { setupOpen(p, now); ref[p] = NAN; }
  // A motor started on some blind: any watch ends (the move reads its own sensor), and nothing is followed.
  void motorStarted() { end(); }
  // A move of blind p ended at tilt: the motor put it there, so it is not a turn by hand.
  void motorLeft(int p, float tilt) { if (p >= 0 && p < PORTS) ref[p] = tilt; }
  // Follow was just turned on (or Setup changed under every blind): start fresh, old turns are not followed.
  void reset() { for (float &r : ref) r = NAN; }
  void forget(int p) { if (p >= 0 && p < PORTS) ref[p] = NAN; }
  // Where things stand now. A follow is handed out once.
  HandWatchNow tick(uint32_t now) {
    if (port >= 0 && (int32_t)(until - now) <= 0) end();
    HandWatchNow n{port, followFrom, followTilt};
    followFrom = -1; followTilt = NAN;
    return n;
  }

 private:
  void end() { port = -1; hand = false; followFrom = -1; followTilt = NAN; }
  void look(int p, float tilt, float ang, bool noReading, uint32_t now) {
    if (std::isnan(tilt) || noReading) return;
    if (setupAt && now - setupAt < SETUP_QUIET_MS) { ref[p] = tilt; return; }   // a setup screen is open: hands are expected
    if (std::isnan(ref[p])) { ref[p] = tilt; return; }
    if (fabsf(tilt - ref[p]) < HAND_TILT) return;
    port = p; hand = true; until = now + WATCH_MS;
    last = ang; still = since = now;
  }
};
