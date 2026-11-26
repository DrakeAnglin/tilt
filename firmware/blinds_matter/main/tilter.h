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
// Farther from the target than the closest it got in this run by this much: it may be going the wrong way. Checked from
// the first moment (no wait for the gear play: during the play nothing moves, so nothing looks wrong), so a motor
// turning the wrong way is caught after a few degrees. "The closest" counts only when two quarter-seconds in a row agree
// (a burst of bad readings toward the target must not set it: Middle, 2026-11-23). Then the motor stops and the
// controller looks for LOOK_MS: if the blind keeps moving with the motor off, a hand is on the wand and the hand wins
// (the move ends, the direction stays). If it holds still farther away than where this run started, it was the motor:
// turn round once (tryFlip). Otherwise it was only bad readings, and the move carries on.
const float WRONG_WAY_DEG = 10.0f;
const uint32_t LOOK_MS = 500;
const float HAND_MOVE_DEG = 5.0f;               // moved this much in LOOK_MS with the motor off: a hand (a still reading wanders +-1.5)
// A dropout (Tilter::lost: the sensor gives nothing, away from its zero) is never taken as the position. Waking, the
// sensor gets this long to give a reading before the move gives up; running, the move stops after this long without one.
// A plain jog (Setup's hold-to-run, 2 s at most) runs without one: it is how a blind is turned off a sensor that reads
// nothing (sitting at its zero just after a restart).
const uint32_t WAKE_LOST_MS = 300, LOST_STOP_MS = 1000;

// Seek: the end is where the rod has not gained SEEK_STEP_DEG in its direction of travel for SEEK_STALL_MS (it has to
// first move SEEK_START_DEG either way to know which way that is). Jitter at a stall is about +-1.5 degrees.
const float SEEK_STEP_DEG = 2.5f, SEEK_START_DEG = 5.0f;
const uint32_t SEEK_STALL_MS = 1200;
enum { MV_NONE, MV_TILT, MV_ANGLE, MV_JOG };
enum { MS_WAKE, MS_RUN, MS_SETTLE, MS_PULSE, MS_POST, MS_LOOK };
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
  float bestErr = 0;            // the closest to the target this run got (degrees)
  float flipErr = 0;            // how far from the target it was when it turned round (finishMove judges from there)
  float fePrev = NAN;           // the last quarter-second's distance from the target
  float lookRef = NAN;          // MS_LOOK: the first steady reading with the motor off
  int looks = 0;
  int angDir = 0, travel = 0, nudges = 0, rawDir = 0;
  bool stalled = false, flipped = false, refSet = false, graceSet = false, fromRun = false;
  int8_t signBefore = 0;        // the motor direction before this move turned round (put back if that did not help)
  uint32_t grace = 8000;
  float lastA = NAN;
  int lastDir = 0, turnBacks = 0;
  const char *endMsg = nullptr;
  // Seek (setup: run to an end): progress is counted only one way, so the reading's jitter while the motor strains at
  // the end can't look like movement. seekDir: which way the angle goes (0 until it has clearly moved).
  bool seek = false;
  int seekDir = 0;
  float seekRef = NAN;
  uint32_t seekT = 0;
  bool woke = false, here = false;   // MS_WAKE: the sensor is on; a tilter answered
  const char *why = nullptr;    // forced stop reason
  bool motorOn = false;         // the motor is driven just now
  float noted = NAN;            // the last true reading (motor stopped); NAN = no tilter
  uint32_t lostT = 0;           // MS_RUN: when the sensor stopped giving readings (0: it gives them)
};
// The middle one of the last five readings (around `near`, so it works across the sensor's zero).
inline float median5(const float hb[5], float near) {
  float d[5];
  for (int k = 0; k < 5; k++) d[k] = angDiff(hb[k], near);
  for (int x = 1; x < 5; x++) for (int y = x; y > 0 && d[y - 1] > d[y]; y--) { float tmp = d[y]; d[y] = d[y - 1]; d[y - 1] = tmp; }
  return fmodf(near + d[2] + 360.0f, 360.0f);
}
inline void moveFresh(Move &m, int kind, int port, uint32_t now) { m = Move(); m.kind = kind; m.port = port; m.t0 = m.ts = m.lastTick = now; }

// What a Tilter learns on every move and keeps while the controller runs.
struct TiltMemory {
  int lastRaw = 0;              // which way the motor last turned (0 = not known): the other way has gear play to take up
  // How far the settled angle ends up beyond the last reading taken while running, per direction of turn
  // ([0] angle falling, [1] angle rising). It covers the sensor reading off while the motor runs, the delay of the
  // readings, and the rod carrying on. Learned at every stop; the motor is stopped this much early.
  float lead[2] = {2.5f, -3.0f};   // measured: it reads about 3 deg high while running, either way
};
// leadMax: the most the learned stop-early amount (TiltMemory::lead) may grow to, either way. A faster motor coasts
// further after it stops, so it may need more than the default.
struct TiltSettings { Marks marks; int speed; uint32_t graceMs, stallMs, maxMs; float stallDeg; float leadMax = 8.0f; };

// The seam: what a Move needs from its blind's Tilter and settings.
struct Tilter {
  virtual uint32_t ms() = 0;                    // the clock
  virtual bool wake() = 0;                      // sensor on: is a tilter plugged in?
  virtual float angle() = 0;                    // the Angle now (degrees); reads high while the motor runs
  virtual bool noReading() = 0;                 // no fresh reading (passing its zero, or lost): the last angle() was a guess
  virtual bool lost() { return false; }         // a dropout: the sensor gave nothing, and the last angle() is only the last good one
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
    // Better: closer than when it started, or (if it turned round) than when it turned round. Not from the start then:
    // what it gained before turning round says nothing about the new direction (2026-11-23: Left kept a wrong direction).
    bool better = fabsf(moveErr(m, t, m.noted)) < (m.flipped ? m.flipErr : m.startErr) - 3.0f;
    if (m.flipped && !better) sign = m.signBefore;                  // turning round did not help: as it was
    else if (better && abs(sign) != 2) {                            // it went the right way: direction is now known
      sign = msignOf(t) * 2;
      t.keep();
      sayf(t, "motor direction confirmed (%+d)", msignOf(t));
    }
  }
  t.ended(m, msg);
  m = Move();
}
// End a move at once, motor braked, because the settings it steers by are about to change (motion.h cfgApply). The
// reading is taken with the motor stopped; a move still waking its sensor has none.
inline void stopNow(Move &m, Tilter &t, const char *why) {
  if (m.kind == MV_NONE) return;
  drive(m, t, 0, 0);
  if (m.st != MS_WAKE || m.woke) m.noted = t.note(t.angle());
  finishMove(m, t, why);
}
inline void toSettle(Move &m, Tilter &t, const char *why) {
  m.fromRun = m.st == MS_RUN;
  drive(m, t, 0, 0);
  m.hn = 0;
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
  m.runErr = m.bestErr = fabsf(moveErr(m, t, a));
  m.fePrev = NAN;
  m.refSet = false;
  // Which way to go: from this reading (taken with the motor stopped), not the first one while running, which can be
  // a bad one and send the run the wrong way.
  m.angDir = m.travel = m.kind == MV_JOG ? 0 : moveErr(m, t, a) > 0 ? 1 : -1;
}
inline void endMove(Move &m, Tilter &t, const char *msg) { drive(m, t, 0, 0); m.endMsg = msg; m.st = MS_POST; m.ts = t.ms(); m.hn = 0; }
// The motor may turn the other way round from what is stored (never learned, or its wires swapped since): try the other
// direction once. Stored only if that brings the blind closer (finishMove); otherwise the old direction is put back.
inline bool tryFlip(Move &m, Tilter &t, float a) {
  if (m.flipped || m.kind == MV_JOG) return false;
  m.flipped = true;
  m.flipErr = fabsf(moveErr(m, t, a));
  m.signBefore = t.motSign();
  t.motSign() = -msignOf(t);                     // not "seen to be so" until this move proves it
  t.say("going the wrong way, trying the other direction");
  drive(m, t, 0, 0);
  beginRun(m, t, a);
  return true;
}

// A reading with the motor stopped: the middle of the last five in this state (one bad reading is not the position).
inline float settledRead(Move &m, Tilter &t, uint32_t now) {
  float a = t.angle();
  t.trace(now, a, m);
  m.hb[m.hn % 5] = a;
  m.hn++;
  return m.hn >= 5 ? median5(m.hb, a) : a;
}
inline void moveTick(Move &m, Tilter &t, uint32_t now) {   // 100 times a second while the move lasts
  if (m.motorOn) m.runMs += now - m.lastTick;
  m.lastTick = now;
  // A move to a tilt steers by the Marks. If they stop being good under it (cleared, or Setup redone), it ends now,
  // not at a stall or the time limit with a distance of NaN.
  if (m.kind == MV_TILT && m.st != MS_POST && marksProblemOf(t.settings().marks)) {
    if (m.st == MS_WAKE) finishMove(m, t, "stopped: Setup changed"); else endMove(m, t, "stopped: Setup changed");
    return;
  }

  if (m.st == MS_WAKE) {
    if (now - m.ts < 20) return;
    if (!m.woke) { m.woke = true; m.here = t.wake(); m.hn = 0; }
    // The middle of five readings, not the first one alone: the first after waking can be anything (Left read 0,
    // 2026-11-23, and the move then took the true reading for going the wrong way). A dropout is not a reading: the
    // sensor gets WAKE_LOST_MS to give some, and with none the motor never starts.
    float w = t.angle();
    if (!m.here || !t.lost()) m.hb[m.hn++] = w;
    bool late = now - m.ts >= 20 + WAKE_LOST_MS;
    if (m.here && m.hn < 5 && !late) return;
    if (m.here && !m.hn && (m.kind != MV_JOG || m.seek)) { finishMove(m, t, "stopped: no reading from the sensor"); return; }
    if (!m.hn) m.hb[m.hn++] = w;
    float a = m.hn >= 5 ? median5(m.hb, m.hb[m.hn - 1]) : m.hb[m.hn - 1];
    m.hn = 0;
    m.noted = t.note(a);
    if (!m.here) { finishMove(m, t, "no tilter plugged in"); return; }
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
    if (!t.lost()) m.lostT = 0;                // no reading for a while: stop (not a stall, not the wrong way, not there)
    else if (!m.lostT) m.lostT = now ? now : 1;
    else if (now - m.lostT >= LOST_STOP_MS && (m.kind != MV_JOG || m.seek)) { m.nudges = MAX_NUDGES + 1; toSettle(m, t, "stopped: no reading from the sensor"); return; }
    m.hb[m.hn % 5] = raw;
    m.hn++;
    if (m.hn >= 5) a = median5(m.hb, raw);     // the middle one of the last five (measured: +-1 deg jitter, spikes to +10)
    m.lastA = a;
    t.trace(now, a, m);
    m.lastDir = m.rawDir * msignOf(t);                         // +1: the angle is rising
    if (m.lastDir) a = fmodf(a + m.lastDir * t.memory().lead[m.lastDir > 0] + 360.0f, 360.0f);   // where it will settle if stopped now
    m.winAcc += angDiff(a, m.winRef); m.winN++;
    bool newWin = now - m.winT >= 250;
    if (newWin) {
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
      if (m.seek && el > m.grace && !std::isnan(m.fAng) && !t.noReading()) {
        if (std::isnan(m.seekRef)) { m.seekRef = m.fAng; m.seekT = now; }
        float d = angDiff(m.fAng, m.seekRef);
        bool ahead = m.seekDir ? d * m.seekDir >= SEEK_STEP_DEG : fabsf(d) >= SEEK_START_DEG;
        if (ahead) { if (!m.seekDir) m.seekDir = d > 0 ? 1 : -1; m.seekRef = m.fAng; m.seekT = now; }
        else if (now - m.seekT >= SEEK_STALL_MS) { m.stalled = true; toSettle(m, t, nullptr); return; }   // at the end
      }
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
      // Going the wrong way: stop and look (MS_LOOK). Not while the sensor is in its blind spot near zero: the reading
      // there is only the last good one.
      if (newWin && !t.noReading()) {
        float fe = fabsf(moveErr(m, t, m.fAng));
        if (!std::isnan(m.fePrev)) m.bestErr = std::min(m.bestErr, std::max(fe, m.fePrev));
        m.fePrev = fe;
        if (fe > m.bestErr + WRONG_WAY_DEG) {
          drive(m, t, 0, 0);
          m.st = MS_LOOK; m.ts = now; m.lookRef = NAN; m.hn = 0;
          return;
        }
      } else if (t.noReading()) m.fePrev = NAN;
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
  } else if (m.st == MS_LOOK) {               // motor off: is a hand turning it, or was it the motor?
    float a = t.angle();
    t.trace(now, a, m);
    uint32_t el = now - m.ts;
    if (el < SETTLE_MS) return;                 // the rod's run-on after braking
    if (!t.noReading()) {                       // the middle of five, first and last: one bad reading is not a hand
      m.hb[m.hn % 5] = a;
      if (++m.hn == 5) m.lookRef = median5(m.hb, a);
    }
    if (el < SETTLE_MS + LOOK_MS) return;
    float now5 = m.hn >= 10 ? median5(m.hb, a) : a;
    m.noted = t.note(now5);
    m.live = now5;
    float e = fabsf(moveErr(m, t, now5));
    if (!std::isnan(m.lookRef) && m.hn >= 10 && fabsf(angDiff(now5, m.lookRef)) > HAND_MOVE_DEG) { endMove(m, t, "stopped: turned by hand"); return; }   // the hand wins
    if (e <= TOL_DEG) { endMove(m, t, "reached"); return; }
    // Still at a closed mark it was going to: it is against the end stop (the PWM sensor reads 0 in bursts while the
    // motor strains there: Left, 2026-11-23).
    if (m.kind == MV_TILT && fabsf(m.tgt) >= 99.5f && e < END_STALL_DEG) { endMove(m, t, "reached (end stop)"); return; }
    if (e < m.runErr + WRONG_WAY_DEG / 2) {     // no farther than where this run started: bad readings. Carry on.
      if (++m.looks > 4) { endMove(m, t, "stopped: the sensor reads unsteadily"); return; }
      beginRun(m, t, now5);
      return;
    }
    a = now5;
    if (tryFlip(m, t, a)) return;               // the motor took it the wrong way: turn round (once)
    endMove(m, t, "stopped: it went the wrong way both ways");   // the old direction is put back (finishMove)
  } else if (m.st == MS_PULSE) {
    t.trace(now, t.angle(), m);
    if ((int32_t)(now - m.deadline) >= 0) toSettle(m, t, nullptr);
  } else if (m.st == MS_POST) {               // stopped: keep watching for a moment (the rod springs back a little)
    float a = settledRead(m, t, now);
    if (now - m.ts < POST_MS) return;
    m.noted = t.note(a);
    finishMove(m, t, m.endMsg ? m.endMsg : "stopped");
  } else if (m.st == MS_SETTLE) {
    float a = settledRead(m, t, now);
    if (now - m.ts < SETTLE_MS) return;
    m.noted = t.note(a);
    if (m.fromRun && !std::isnan(m.lastA) && m.lastDir && !t.lost()) {   // learn how far it went on after the last running reading
      float c = angDiff(a, m.lastA) * m.lastDir;
      float &ld = t.memory().lead[m.lastDir > 0];
      float lm = t.settings().leadMax;                    // readings further off than this (plus some slack) are noise
      if (c > -lm - 2.0f && c < lm + 4.0f) { float v = ld + (c - ld) * 0.4f; ld = v < -lm ? -lm : v > lm ? lm : v; }
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
