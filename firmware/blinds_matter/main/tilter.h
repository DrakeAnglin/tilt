// One blind's Move: the state machine that turns its Tilter to a Target and stops it there. No ESP-IDF here: it works
// through the Tilter seam below (motion.h has the controller's adapter; test/logic_test.cpp has a simulated Tilter).
// Every move is timed, stops on a stall, and ends with a reading taken with the motor stopped (the Angle reads high
// while the motor runs: shared ground wire).
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include "logic.h"

// ---- limits (stall and time limits are settings: Tune in store.h)
const float SAME_DIR_GRACE_MS = 2500;           // stall wait when the motor carries on the way it last turned (no gear play)
const float TOL_DEG = 2.0f;                     // "reached"
const float OVER_OK_DEG = 5.0f;                 // past the target by less than this: leave it (turning back costs the gear play)
const int START_DUTY = 45;                      // percent
const uint32_t RAMP_MS = 150, SETTLE_MS = 120;  // soft start; wait after braking before the true reading
const int MAX_NUDGES = 8;
const uint32_t POST_MS = 400;                   // after a move: keep the sensor on this long and take the final position then
const float END_STALL_DEG = 10.0f;              // a stall this close to a closed mark counts as "at the end stop"

enum { MV_NONE, MV_TILT, MV_ANGLE, MV_JOG };
enum { MS_WAKE, MS_RUN, MS_SETTLE, MS_PULSE, MS_POST };
struct Move {
  int kind = MV_NONE, port = -1, st = MS_WAKE;
  float tgt = 0;                // tilt (MV_TILT) or sensor angle (MV_ANGLE)
  int jogDir = 0, pct = 100;
  uint32_t t0 = 0, ts = 0, deadline = 0, stallT = 0, lastTick = 0, runMs = 0, spT = 0;
  uint32_t winT = 0;
  int winN = 0;
  float winRef = 0, winAcc = 0, fAng = NAN, hb[5];   // quarter-second averages; the last five raw readings
  int hn = 0, hit = 0;
  float spRef = 0, slowest = 999, stallRef = 0, startErr = 0, runErr = 0, startAng = 0, live = NAN;
  int angDir = 0, travel = 0, nudges = 0, rawDir = 0;
  bool stalled = false, flipped = false, refSet = false, graceSet = false, fromRun = false;
  uint32_t grace = 12000;
  float lastA = NAN;
  int lastDir = 0, turnBacks = 0;
  const char *endMsg = nullptr;
  const char *why = nullptr;    // forced stop reason
  bool motorOn = false;         // the motor is driven just now
  float noted = NAN;            // the last true reading (motor stopped); NAN = no tilter
};
inline void moveFresh(Move &m, int kind, int port, uint32_t now) { m = Move(); m.kind = kind; m.port = port; m.t0 = m.ts = m.lastTick = now; }

// What a Tilter learns on every move and keeps while the controller runs.
struct TiltMemory {
  int lastRaw = 0;              // which way the motor last turned (0 = not known): the other way has gear play to take up
  // How far the settled angle ends up beyond the last reading taken while running, per direction of turn
  // ([0] angle falling, [1] angle rising). It covers the sensor reading off while the motor runs, the delay of the
  // readings, and the rod carrying on. Learned at every stop; the motor is stopped this much early.
  float lead[2] = {2.5f, -3.0f};   // measured: it reads about 3 deg high while running, either way
};
struct TiltSettings { Marks marks; int speed; uint32_t graceMs, stallMs, maxMs; float stallDeg; };

// The seam: what a Move needs from its blind's Tilter and settings.
struct Tilter {
  virtual uint32_t ms() = 0;                    // the clock
  virtual bool wake() = 0;                      // sensor on: is a tilter plugged in?
  virtual float angle() = 0;                    // the Angle now (degrees); reads high while the motor runs
  virtual bool noReading() = 0;                 // a PWM sensor passing its zero: the last angle() was a guess
  virtual float note(float a) = 0;              // a true reading (motor stopped): the Current tilt. Returns the angle kept (NAN: no tilter)
  virtual void motor(int dir, int duty) = 0;    // dir -1 / 0 (brake) / +1, duty percent
  virtual TiltSettings settings() = 0;
  virtual int8_t &motSign() = 0;                // > 0: motor "forward" makes the angle rise. +-1 = assumed, +-2 = seen to be so
  virtual TiltMemory &memory() = 0;
  virtual void keep() = 0;                      // save what was learned (the motor direction)
  virtual void say(const char *msg) = 0;        // the event log (the blind's name is added)
  virtual void trace(uint32_t, float, const Move &) {}   // the developer page's recording of the move
  virtual void ended(const Move &m, const char *msg) = 0;   // the move is over (motor braked): sensor off, counters, report
};
inline void sayf(Tilter &t, const char *fmt, ...) {
  char buf[100];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(buf, sizeof buf, fmt, ap);
  va_end(ap);
  t.say(buf);
}
inline int msignOf(Tilter &t) { return t.motSign() > 0 ? 1 : -1; }

inline float moveErr(const Move &m, Tilter &t, float ang) {    // signed degrees; + means the angle has to rise
  if (m.kind == MV_TILT) { Marks k = t.settings().marks; return (xOfTiltMarks(k, m.tgt) - arcXOf(k, ang)) * sgn(angDiff(k.up, k.open)); }
  return angDiff(m.tgt, ang);
}
inline void drive(Move &m, Tilter &t, int d, int pct) {
  t.motor(d, pct);
  m.motorOn = d != 0;
  if (d && m.kind != MV_NONE) {
    TiltMemory &mem = t.memory();
    m.rawDir = d;
    if (!m.graceSet) { m.graceSet = true; m.grace = mem.lastRaw == d ? (uint32_t)SAME_DIR_GRACE_MS : t.settings().graceMs; }
    mem.lastRaw = d;
  }
}
inline void finishMove(Move &m, Tilter &t, const char *msg) {
  drive(m, t, 0, 0);
  if (m.kind != MV_JOG) {
    int8_t &sign = t.motSign();
    bool better = fabsf(moveErr(m, t, m.noted)) < m.startErr - 3.0f;
    if (m.flipped && !better) sign = -sign;                         // the flip did not help: undo it
    else if (better && abs(sign) != 2) {                            // it went the right way: direction is now known
      sign = msignOf(t) * 2;
      t.keep();
      sayf(t, "motor direction confirmed (%+d)", msignOf(t));
    }
  }
  t.ended(m, msg);
  m = Move();
}
inline void toSettle(Move &m, Tilter &t, const char *why) {
  m.fromRun = m.st == MS_RUN;
  drive(m, t, 0, 0);
  m.why = why;
  m.st = MS_SETTLE;
  m.ts = t.ms();
}
inline void beginRun(Move &m, Tilter &t, float a) {
  m.st = MS_RUN;
  m.ts = m.stallT = m.spT = m.winT = t.ms();
  m.stallRef = m.spRef = m.winRef = m.fAng = a;
  m.winAcc = 0; m.winN = 0; m.hn = 0; m.hit = 0;
  m.graceSet = false;
  m.stalled = false;
  m.runErr = fabsf(moveErr(m, t, a));
  m.refSet = false;
  m.angDir = 0;
}
inline void endMove(Move &m, Tilter &t, const char *msg) { drive(m, t, 0, 0); m.endMsg = msg; m.st = MS_POST; m.ts = t.ms(); }
inline bool tryFlip(Move &m, Tilter &t, float a) {   // direction never seen to be right: the motor may be the other way round, try once
  if (m.flipped || m.kind == MV_JOG || abs(t.motSign()) == 2) return false;
  m.flipped = true;
  t.motSign() = -t.motSign();
  t.say("going the wrong way, trying the other direction");
  beginRun(m, t, a);
  return true;
}

inline void moveTick(Move &m, Tilter &t, uint32_t now) {   // 100 times a second while the move lasts
  if (m.motorOn) m.runMs += now - m.lastTick;
  m.lastTick = now;

  if (m.st == MS_WAKE) {
    if (now - m.ts < 20) return;
    bool here = t.wake();
    float a = t.angle();
    m.noted = t.note(a);
    if (!here) { finishMove(m, t, "no tilter plugged in"); return; }
    m.startAng = a;
    m.live = a;
    if (m.kind != MV_JOG) {
      m.startErr = fabsf(moveErr(m, t, a));
      if (m.startErr <= TOL_DEG) { finishMove(m, t, "already there"); return; }
    }
    beginRun(m, t, a);
  } else if (m.st == MS_RUN) {
    // While the motor runs the reading jumps about by a couple of degrees (brush noise on the shared wires).
    // For stopping: the middle one of the last five readings, twice in a row. For speed and stall: quarter-second averages.
    TiltSettings s = t.settings();
    float raw = t.angle(), a = raw;
    m.hb[m.hn % 5] = raw;
    m.hn++;
    if (m.hn >= 5) {                           // the middle one of the last five (measured: +-1 deg jitter, spikes to +10)
      float d[5];
      for (int k = 0; k < 5; k++) d[k] = angDiff(m.hb[k], raw);
      for (int x = 1; x < 5; x++) for (int y = x; y > 0 && d[y - 1] > d[y]; y--) { float tmp = d[y]; d[y] = d[y - 1]; d[y - 1] = tmp; }
      a = fmodf(raw + d[2] + 360.0f, 360.0f);
    }
    m.lastA = a;
    t.trace(now, a, m);
    m.lastDir = m.rawDir * msignOf(t);                         // +1: the angle is rising
    if (m.lastDir) a = fmodf(a + m.lastDir * t.memory().lead[m.lastDir > 0] + 360.0f, 360.0f);   // where it will settle if stopped now
    m.winAcc += angDiff(a, m.winRef); m.winN++;
    if (now - m.winT >= 250) {
      m.fAng = fmodf(m.winRef + m.winAcc / m.winN + 360.0f, 360.0f);
      m.winRef = m.fAng; m.winAcc = 0; m.winN = 0; m.winT = now;
    }
    m.live = m.fAng;
    uint32_t el = now - m.ts;
    int sp;
    if (now - m.t0 > s.maxMs) { m.nudges = MAX_NUDGES + 1; toSettle(m, t, "stopped: time limit"); return; }
    if (m.kind == MV_JOG) {
      if ((int32_t)(now - m.deadline) >= 0) { toSettle(m, t, nullptr); return; }
      sp = m.pct;
      if (el < RAMP_MS) sp = std::min(sp, (int)(START_DUTY + (sp - START_DUTY) * (int)el / (int)RAMP_MS));
      drive(m, t, m.jogDir, sp);
    } else {
      float e = moveErr(m, t, a);
      int want = e > 0 ? 1 : -1;
      if (m.angDir == 0) m.angDir = m.travel = want;
      if (m.hn < 5) want = m.angDir;                            // not enough readings yet to judge
      if (want != m.angDir || fabsf(e) <= 1.0f) { if (++m.hit >= 2) { toSettle(m, t, nullptr); return; } }   // there, or just past it
      else m.hit = 0;
      sp = s.speed;                            // no slowing near the target: the drive is slow and stops dead
      if (el < RAMP_MS) sp = std::min(sp, (int)(START_DUTY + (sp - START_DUTY) * (int)el / (int)RAMP_MS));
      drive(m, t, m.angDir * msignOf(t), sp);
    }
    if (el > m.grace && now - m.spT >= 500) {           // speed, for the log (after the gear play is taken up)
      float v = fabsf(angDiff(m.fAng, m.spRef)) * 1000.0f / (now - m.spT);
      if (v < m.slowest) m.slowest = v;
      m.spT = now;
      m.spRef = m.fAng;
    } else if (el <= m.grace) { m.spT = now; m.spRef = m.fAng; }
    if (t.noReading()) m.stallT = now;            // PWM sensor passing its zero: no reading for a few degrees, not a stall
    // Stall: no check while the gear play is taken up, then the angle has to change by stallDeg every stallMs.
    StallVerdict sv = stallCheck(el, m.grace, now - m.stallT, s.stallMs, m.fAng, m.stallRef, s.stallDeg);
    if (sv == STALL_YES) { m.stalled = true; toSettle(m, t, nullptr); return; }
    if (sv == STALL_MOVED) { m.stallT = now; m.stallRef = m.fAng; }
  } else if (m.st == MS_PULSE) {
    t.trace(now, t.angle(), m);
    if ((int32_t)(now - m.deadline) >= 0) toSettle(m, t, nullptr);
  } else if (m.st == MS_POST) {               // stopped: keep watching for a moment (the rod springs back a little)
    float a = t.angle();
    t.trace(now, a, m);
    if (now - m.ts < POST_MS) return;
    m.noted = t.note(a);
    finishMove(m, t, m.endMsg ? m.endMsg : "stopped");
  } else if (m.st == MS_SETTLE) {
    float a = t.angle();
    t.trace(now, a, m);
    if (now - m.ts < SETTLE_MS) return;
    m.noted = t.note(a);
    if (m.fromRun && !std::isnan(m.lastA) && m.lastDir) {     // learn how far it went on after the last running reading
      float c = angDiff(a, m.lastA) * m.lastDir;
      float &ld = t.memory().lead[m.lastDir > 0];
      if (c > -10.0f && c < 12.0f) { float v = ld + (c - ld) * 0.4f; ld = v < -8.0f ? -8.0f : v > 8.0f ? 8.0f : v; }
      m.fromRun = false;
    }
    m.live = a;
    if (m.kind == MV_JOG) {                   // a jog also shows which way the motor turns the sensor
      float d = angDiff(a, m.startAng);
      if (fabsf(d) > 4.0f) {
        int s = (d > 0 ? 1 : -1) * m.jogDir * 2;
        if (s != t.motSign()) { t.motSign() = s; t.keep(); sayf(t, "motor direction learned (%+d)", s / 2); }
      }
      endMove(m, t, m.stalled ? "jog: stalled" : (m.why ? m.why : "jog"));
      return;
    }
    float e = moveErr(m, t, a);
    if (m.why) { endMove(m, t, m.why); return; }
    if (fabsf(e) <= TOL_DEG) { endMove(m, t, "reached"); return; }
    if (m.stalled) {
      bool atEnd = m.kind == MV_TILT && fabsf(m.tgt) >= 99.5f && fabsf(e) < END_STALL_DEG;
      if (atEnd) { endMove(m, t, "reached (end stop)"); return; }
      if (fabsf(e) > m.startErr - 2.0f && tryFlip(m, t, a)) return;                      // no progress at all
      endMove(m, t, "blocked (stalled)");
      return;
    }
    int dir = e > 0 ? 1 : -1;
    if (dir != m.travel) {                    // went past it. Turning back means taking up the gear play again.
      if (fabsf(e) <= OVER_OK_DEG) { endMove(m, t, "reached"); return; }
      if (m.nudges < MAX_NUDGES) { m.nudges++; m.turnBacks++; beginRun(m, t, a); return; }
    } else if (m.nudges < MAX_NUDGES) {       // short: run on the same way, watching the angle (no blind timed push)
      m.nudges++;
      beginRun(m, t, a);
      return;
    }
    endMove(m, t, "stopped near the target");
  }
}
