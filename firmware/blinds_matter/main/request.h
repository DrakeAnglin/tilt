// Move requests: "these blinds (or all, as follow mode says) to this Target, now or gently over N minutes, asked by
// the app, a Schedule, Apple Home or a hand on the wand". One place decides which blinds go, starts or cancels the
// gentle moves, applies the can-move rule and gives the answer. No ESP-IDF here: the controller plugs in through
// MoveSeam (motion.h has its adapter), and test/logic_test.cpp plugs in a recording one.
#pragma once
#include "logic.h"

enum MoveFrom { FROM_APP, FROM_SCHEDULE, FROM_HOME, FROM_HAND };
struct MoveAsk {
  MoveFrom from = FROM_APP;
  int one = -1;            // app: the blind asked for; Home: its covering's blind; hand: the blind that was turned. -1 = all
  uint8_t mask = 0x07;     // a Schedule: its blinds (bit n = port n)
  bool solo = false;       // app: only this blind, even when blinds follow each other
  float tilt[PORTS];       // the Target for each blind (NAN: an unknown position word)
  uint32_t gentleMs = 0;   // > 0: gently, taking this long (app and Schedules)
};
inline MoveAsk moveAsk(MoveFrom from, int one, float t, uint32_t gentleMs = 0, uint8_t mask = 0x07) {
  MoveAsk a;
  a.from = from; a.one = one; a.gentleMs = gentleMs; a.mask = mask;
  for (float &x : a.tilt) x = t;
  return a;
}
struct MoveResult { int started; const char *why; };   // why: nullptr when something started, else why nothing did

struct MoveSeam {                                     // what a request needs from the controller
  virtual bool follow() = 0;                          // "blinds follow each other" is on
  virtual bool movable(int p) = 0;                    // the can-move rule (logic.h)
  virtual bool calibrated(int p) = 0;
  virtual float tilt(int p) = 0;                      // Current tilt; NAN = not known
  virtual const char *now(int p, float t) = 0;        // start the move now: nullptr, or why not
  virtual void gently(int p, float from, float to, uint32_t ms) = 0;
  virtual void stopGentle() = 0;                      // end every gentle move
  virtual bool batteryCritical() = 0;                 // Critical battery (logic.h battLevel)
};

// Is blind p one of the blinds this request is for? (Before the can-move rule.)
inline bool movePicks(const MoveAsk &a, bool follow, int p) {
  switch (a.from) {
    case FROM_APP: return a.one < 0 || p == a.one || (follow && !a.solo);
    case FROM_SCHEDULE: return (a.mask >> p) & 1;
    case FROM_HOME: return a.one < 0 || p == a.one || follow;
    case FROM_HAND: return p != a.one;                // the others follow the blind that was turned
  }
  return false;
}
inline const char *moveOne(const MoveAsk &a, MoveSeam &s, int p) {
  float now = s.tilt(p);
  if (a.gentleMs && !std::isnan(now) && s.calibrated(p)) { s.gently(p, now, a.tilt[p], a.gentleMs); return nullptr; }
  return s.now(p, a.tilt[p]);                         // (also when the Current tilt is not known: straight there)
}
inline MoveResult moveRequest(const MoveAsk &a, MoveSeam &s) {
  if (a.from == FROM_SCHEDULE && s.batteryCritical()) return {0, "battery critical: Schedules paused"};   // asked-for moves still go
  if (a.from == FROM_APP || a.from == FROM_HOME) s.stopGentle();      // a command ends a gentle move
  int started = 0;
  const char *err = nullptr;
  int named = a.from == FROM_APP ? a.one : -1;        // a blind asked for by name: no can-move filter, its refusal is the answer
  if (named >= 0) {
    if (std::isnan(a.tilt[named])) return {0, "unknown position"};
    if (const char *e = moveOne(a, s, named)) return {0, e};
    started++;
  }
  bool follow = s.follow();
  for (int p = 0; p < PORTS; p++) {
    if (p == named || !movePicks(a, follow, p) || !s.movable(p)) continue;
    if (std::isnan(a.tilt[p])) return {0, "unknown position"};
    float cur = s.tilt(p);
    if (a.from == FROM_HAND && !std::isnan(cur) && fabsf(cur - a.tilt[p]) <= 3.0f) continue;   // already there
    if (const char *e = moveOne(a, s, p)) err = e; else started++;
  }
  return {started, started ? nullptr : err ? err : "no blind is set up"};
}
