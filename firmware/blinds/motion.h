// Motion: one blind moves at a time (the others wait). Tilt is -100 (closed, slats down) .. 0 (open, level) ..
// +100 (closed, slats up), from three marked sensor angles. Every move is timed, stops on a stall, and ends with a
// reading taken with the motor stopped (the angle reads high while the motor runs: shared ground wire).
#pragma once
#include "power.h"

struct BlindState {
  bool present = false, seen = false;
  float ang = NAN, mv = 0;      // last true angle (motor stopped)
  float tilt = NAN;             // from the marks; NAN = not set up or not read yet
  float target = NAN;           // tilt it is moving to
  bool queued = false;
  float qTilt = 0;
  char last[48] = "";           // how the last move ended
  int lastRaw = 0;              // which way the motor last turned (0 = not known): the other way has gear play to take up
  float runBias = 4.0f;         // how much high the angle reads while the motor runs (learned at every stop)
};
BlindState bs[PORTS];

enum { MV_NONE, MV_TILT, MV_ANGLE, MV_JOG };
enum { MS_WAKE, MS_RUN, MS_SETTLE, MS_PULSE };
struct Move {
  int kind = MV_NONE, port = -1, st = MS_WAKE;
  float tgt = 0;                // tilt (MV_TILT) or sensor angle (MV_ANGLE)
  int jogDir = 0, pct = 100;
  uint32_t t0 = 0, ts = 0, deadline = 0, stallT = 0, lastTick = 0, runMs = 0, spT = 0;
  uint32_t winT = 0;
  int winN = 0;
  float winRef = 0, winAcc = 0, fAng = NAN, h1 = NAN, h2 = NAN;   // quarter-second averages; last two raw readings
  float spRef = 0, slowest = 999, stallRef = 0, startErr = 0, runErr = 0, startAng = 0, live = NAN;
  int angDir = 0, travel = 0, nudges = 0, rawDir = 0;
  bool stalled = false, flipped = false, refSet = false, graceSet = false, fromRun = false;
  uint32_t grace = 12000;
  float lastA = NAN;
  const char *why = nullptr;    // forced stop reason
} mv;

float angDiff(float to, float from) { return fmodf(to - from + 540.0f, 360.0f) - 180.0f; }   // shortest, -180..180
float sgn(float v) { return v < 0 ? -1.0f : 1.0f; }
int msign(int p) { return cfg.b[p].motSign > 0 ? 1 : -1; }

// ---- marks
const char *marksProblem(int p) {             // nullptr = good
  BlindCfg &c = cfg.b[p];
  if (isnan(c.up) || isnan(c.open) || isnan(c.down)) return "not all three positions are marked";
  float u = angDiff(c.up, c.open), d = angDiff(c.down, c.open);
  if (fabsf(u) < MIN_HALF_SPAN || fabsf(d) < MIN_HALF_SPAN) return "open is too close to a closed mark";
  if (fabsf(u) > MAX_HALF_SPAN || fabsf(d) > MAX_HALF_SPAN) return "a closed mark is more than half a turn from open";
  if ((u > 0) == (d > 0)) return "open must be between the two closed marks";
  return nullptr;
}
bool calibrated(int p) { return marksProblem(p) == nullptr; }
float arcX(int p, float ang) {                // degrees from open, + toward closed-up
  BlindCfg &c = cfg.b[p];
  return angDiff(ang, c.open) * sgn(angDiff(c.up, c.open));
}
float tiltOf(int p, float ang) {
  BlindCfg &c = cfg.b[p];
  float x = arcX(p, ang);
  return x >= 0 ? x / fabsf(angDiff(c.up, c.open)) * 100.0f : x / fabsf(angDiff(c.down, c.open)) * 100.0f;
}
float xOfTilt(int p, float t) {
  BlindCfg &c = cfg.b[p];
  return t >= 0 ? t / 100.0f * fabsf(angDiff(c.up, c.open)) : t / 100.0f * fabsf(angDiff(c.down, c.open));
}

// ---- hardware
void motorRaw(int p, int d, int pct) {        // DRV8833 slow decay: one input high, PWM the other (both high = brake)
  int du = constrain(pct, 0, 100) * 255 / 100;
  if (d > 0) { ledcWrite(P_IN1[p], 255); ledcWrite(P_IN2[p], 255 - du); }
  else if (d < 0) { ledcWrite(P_IN1[p], 255 - du); ledcWrite(P_IN2[p], 255); }
  else { ledcWrite(P_IN1[p], 255); ledcWrite(P_IN2[p], 255); }
  motorOn = d != 0;
  if (d && p == mv.port) {
    mv.rawDir = d;
    if (!mv.graceSet) { mv.graceSet = true; mv.grace = bs[p].lastRaw == d ? (uint32_t)SAME_DIR_GRACE_MS : tune.graceMs; }
    bs[p].lastRaw = d;
  }
}
float degOf(float mv) { return constrain(mv / 1000.0f / (vdd - EN_DROP_V), 0.0f, 1.0f) * 360.0f; }   // output is a fraction of the sensor's supply
// The rail dips for a millisecond or two whenever Wi-Fi transmits, and the sensor's output dips with it. So the rail is
// measured just before and just after the angle: if the two disagree, the reading is thrown away and taken again.
float readAngle(int p) {
  float v1 = 0, v2 = 0;
  for (int k = 0; k < 4; k++) {
    v1 = probeVdd();
    uint32_t mv = 0;
    for (int i = 0; i < 8; i++) mv += analogReadMilliVolts(P_ANG[p]);
    v2 = probeVdd();
    bs[p].mv = mv / 8.0f;
    if (v1 > 2.5f && v1 < 3.6f && fabsf(v1 - v2) < 0.03f) break;
  }
  if (v1 > 2.5f && v1 < 3.6f && v2 > 2.5f && v2 < 3.6f) vdd = (v1 + v2) / 2;
  return degOf(bs[p].mv);
}
// Is a tilter plugged in? An empty port floats: it keeps whatever voltage the pin was last pushed to. A sensor
// pulls the line back to its own value. Push it low, then high, and compare. EN must be on. Leaves bs[p].mv fresh.
bool probePresent(int p) {
  float v[2];
  for (int k = 0; k < 2; k++) {
    pinMode(P_ANG[p], OUTPUT);
    digitalWrite(P_ANG[p], k ? HIGH : LOW);
    delay(2);
    pinMode(P_ANG[p], INPUT);
    delay(10);
    v[k] = readMv(P_ANG[p]);
  }
  bs[p].mv = v[1];
  return fabsf(v[1] - v[0]) < 150.0f;
}
void noteAngle(int p, float a) {              // a true reading (motor stopped)
  bs[p].seen = true;
  bs[p].ang = bs[p].present ? a : NAN;
  bs[p].tilt = (bs[p].present && calibrated(p)) ? tiltOf(p, a) : NAN;
}
void pulseRead(int p) {                       // wake the sensor for a moment (blocks ~30 ms). Not during a move.
  digitalWrite(P_EN[p], HIGH);
  delay(20);
  bs[p].present = probePresent(p);
  noteAngle(p, readAngle(p));
  digitalWrite(P_EN[p], LOW);
}
void motionBegin() {
  for (int i = 0; i < PORTS; i++) {           // every driver asleep, every motor braked
    pinMode(P_EN[i], OUTPUT);
    digitalWrite(P_EN[i], LOW);
    ledcAttach(P_IN1[i], PWM_HZ, PWM_BITS);
    ledcAttach(P_IN2[i], PWM_HZ, PWM_BITS);
    ledcWrite(P_IN1[i], 255);
    ledcWrite(P_IN2[i], 255);
    analogSetPinAttenuation(P_ANG[i], ADC_11db);
  }
}

// ---- moves
float moveErr(float ang) {                    // signed degrees; + means the angle has to rise
  if (mv.kind == MV_TILT) return (xOfTilt(mv.port, mv.tgt) - arcX(mv.port, ang)) * sgn(angDiff(cfg.b[mv.port].up, cfg.b[mv.port].open));
  return angDiff(mv.tgt, ang);
}
void finishMove(const char *msg) {
  int p = mv.port;
  motorRaw(p, 0, 0);
  digitalWrite(P_EN[p], LOW);
  if (mv.kind != MV_JOG) {
    bool better = fabsf(moveErr(bs[p].ang)) < mv.startErr - 3.0f;
    if (mv.flipped && !better) cfg.b[p].motSign = -cfg.b[p].motSign;      // the flip did not help: undo it
    else if (better && abs(cfg.b[p].motSign) != 2) {                      // it went the right way: direction is now known
      cfg.b[p].motSign = msign(p) * 2;
      cfgSave();
      event("%s: motor direction confirmed (%+d)", cfg.b[p].name, msign(p));
    }
    stats.moves[p]++;
    if (mv.stalled) stats.stalls[p]++;
    float trav = fabsf(angDiff(bs[p].ang, mv.startAng)), avg = mv.runMs ? trav * 1000.0f / mv.runMs : 0;
    char sp[40];
    snprintf(sp, sizeof sp, "%.1f deg/s, slowest %.1f", avg, mv.slowest > 900 ? avg : mv.slowest);
    if (isnan(bs[p].tilt)) event("%s: %s at %.1f deg (%.1f s, %s)", cfg.b[p].name, msg, bs[p].ang, mv.runMs / 1000.0f, sp);
    else event("%s: %s at tilt %.0f (%.1f deg, %.1f s, %s)", cfg.b[p].name, msg, bs[p].tilt, bs[p].ang, mv.runMs / 1000.0f, sp);
  } else if (mv.runMs > 800) event("%s: jog %.1f deg in %.1f s%s", cfg.b[p].name, angDiff(bs[p].ang, mv.startAng), mv.runMs / 1000.0f, mv.stalled ? " (stalled)" : "");
  stats.motorMs += mv.runMs;
  if (!powered) stats.battMotorMs += mv.runMs;
  strlcpy(bs[p].last, msg, sizeof bs[p].last);
  bs[p].target = NAN;
  mv = Move();
}
void toSettle(const char *why) {
  mv.fromRun = mv.st == MS_RUN;
  motorRaw(mv.port, 0, 0);
  mv.why = why;
  mv.st = MS_SETTLE;
  mv.ts = millis();
}
void beginRun(float a) {
  mv.st = MS_RUN;
  mv.ts = mv.stallT = mv.spT = mv.winT = millis();
  mv.stallRef = mv.spRef = mv.winRef = mv.fAng = a;
  mv.winAcc = 0; mv.winN = 0; mv.h1 = mv.h2 = NAN;
  mv.graceSet = false;
  mv.stalled = false;
  mv.runErr = fabsf(moveErr(a));
  mv.refSet = false;
  mv.angDir = 0;
}
bool beginMove(int kind, int p) {
  if (mv.kind != MV_NONE) { motorRaw(mv.port, 0, 0); digitalWrite(P_EN[mv.port], LOW); bs[mv.port].target = NAN; }
  mv = Move();
  mv.kind = kind;
  mv.port = p;
  mv.t0 = mv.ts = mv.lastTick = millis();
  digitalWrite(P_EN[p], HIGH);
  return true;
}
// Go to a tilt. Returns nullptr if accepted, else why not.
const char *startTilt(int p, float t) {
  if (p < 0 || p >= PORTS) return "no such blind";
  if (!calibrated(p)) return "not set up yet";
  if (bs[p].seen && !bs[p].present) return "no tilter plugged in";
  if (!battOkToMove()) return "battery too low";
  t = constrain(t, -100.0f, 100.0f);
  if (mv.kind != MV_NONE && mv.port != p) { bs[p].queued = true; bs[p].qTilt = t; bs[p].target = t; return nullptr; }
  if (mv.kind == MV_TILT && mv.port == p) {   // new target while moving: carry on from here
    mv.tgt = t; mv.nudges = 0; mv.t0 = millis(); bs[p].target = t;
    if (mv.st != MS_WAKE) beginRun(isnan(mv.live) ? bs[p].ang : mv.live);
    return nullptr;
  }
  beginMove(MV_TILT, p);
  mv.tgt = t;
  bs[p].target = t;
  return nullptr;
}
const char *startAngle(int p, float deg) {    // developer: go to a raw sensor angle
  if (p < 0 || p >= PORTS) return "no such blind";
  if (!battOkToMove()) return "battery too low";
  beginMove(MV_ANGLE, p);
  mv.tgt = fmodf(deg + 360.0f, 360.0f);
  return nullptr;
}
const char *jog(int p, int d, int pct, uint32_t ms) {   // hold-to-run: call again before the time is up
  if (p < 0 || p >= PORTS) return "no such blind";
  if (!battOkToMove()) return "battery too low";
  ms = min(ms, (uint32_t)2000);
  if (mv.kind == MV_JOG && mv.port == p && mv.jogDir == d) { mv.deadline = millis() + ms; mv.pct = pct; return nullptr; }
  beginMove(MV_JOG, p);
  mv.jogDir = d;
  mv.pct = pct;
  mv.deadline = millis() + ms + 30;
  return nullptr;
}
void stopAll(const char *why) {
  for (int i = 0; i < PORTS; i++) { if (bs[i].queued) bs[i].target = NAN; bs[i].queued = false; }
  if (mv.kind == MV_NONE) return;
  if (mv.st == MS_WAKE) { noteAngle(mv.port, readAngle(mv.port)); finishMove(why); }
  else if (mv.st != MS_SETTLE || !mv.why) { mv.nudges = MAX_NUDGES + 1; toSettle(why); }
}
bool moving() { return mv.kind != MV_NONE; }

bool tryFlip(float a) {                        // direction never seen to be right: the motor may be the other way round, try once
  if (mv.flipped || mv.kind == MV_JOG || abs(cfg.b[mv.port].motSign) == 2) return false;
  mv.flipped = true;
  cfg.b[mv.port].motSign = -cfg.b[mv.port].motSign;
  event("%s: going the wrong way, trying the other direction", cfg.b[mv.port].name);
  beginRun(a);
  return true;
}

bool uiActive();                               // net.h
void motionTick() {
  uint32_t now = millis();
  static uint32_t lastT = 0, lastIdle = 0;
  static int idlePort = 0;
  if (mv.kind == MV_NONE) {
    for (int i = 0; i < PORTS; i++)
      if (bs[i].queued) { bs[i].queued = false; const char *e = startTilt(i, bs[i].qTilt); if (e) { strlcpy(bs[i].last, e, sizeof bs[i].last); bs[i].target = NAN; } return; }
    // keep the shown positions fresh (the wand may have been turned by hand): one port a second while someone looks
    if (now - lastIdle >= 1000 && (uiActive() || !bs[idlePort].seen)) { lastIdle = now; pulseRead(idlePort); idlePort = (idlePort + 1) % PORTS; }
    return;
  }
  if (now - lastT < 10) return;                // 100 Hz
  lastT = now;
  int p = mv.port;
  BlindCfg &c = cfg.b[p];
  if (motorOn) mv.runMs += now - mv.lastTick;
  mv.lastTick = now;

  if (mv.st == MS_WAKE) {
    if (now - mv.ts < 20) return;
    bs[p].present = probePresent(p);
    float a = readAngle(p);
    noteAngle(p, a);
    if (!bs[p].present) { finishMove("no tilter plugged in"); return; }
    mv.startAng = a;
    mv.live = a;
    if (mv.kind != MV_JOG) {
      mv.startErr = fabsf(moveErr(a));
      if (mv.startErr <= TOL_DEG) { finishMove("already there"); return; }
    }
    beginRun(a);
  } else if (mv.st == MS_RUN) {
    // While the motor runs the reading jumps about by a couple of degrees (brush noise on the shared wires).
    // For stopping: the middle one of the last three readings. For speed and stall: quarter-second averages.
    float raw = readAngle(p), a = raw;
    if (!isnan(mv.h1) && !isnan(mv.h2)) {
      float d1 = angDiff(mv.h1, raw), d2 = angDiff(mv.h2, raw);
      float mid = (d1 > 0) == (d2 > 0) ? (fabsf(d1) < fabsf(d2) ? d1 : d2) : 0;
      a = fmodf(raw + mid + 360.0f, 360.0f);
    }
    mv.h2 = mv.h1; mv.h1 = raw;
    a = fmodf(a - bs[p].runBias + 360.0f, 360.0f);          // it reads high while running
    mv.lastA = a;
    mv.winAcc += angDiff(a, mv.winRef); mv.winN++;
    if (now - mv.winT >= 250) {
      mv.fAng = fmodf(mv.winRef + mv.winAcc / mv.winN + 360.0f, 360.0f);
      mv.winRef = mv.fAng; mv.winAcc = 0; mv.winN = 0; mv.winT = now;
    }
    mv.live = mv.fAng;
    uint32_t el = now - mv.ts;
    int sp;
    if (now - mv.t0 > (uint32_t)tune.moveMaxS * 1000) { mv.nudges = MAX_NUDGES + 1; toSettle("stopped: time limit"); return; }
    if (mv.kind == MV_JOG) {
      if ((int32_t)(now - mv.deadline) >= 0) { toSettle(nullptr); return; }
      sp = mv.pct;
      if (el < RAMP_MS) sp = min(sp, (int)(START_DUTY + (sp - START_DUTY) * (int)el / (int)RAMP_MS));
      motorRaw(p, mv.jogDir, sp);
    } else {
      float e = moveErr(a);
      int want = e > 0 ? 1 : -1;
      if (mv.angDir == 0) mv.angDir = mv.travel = want;
      if (want != mv.angDir || fabsf(e) <= 1.0f) { toSettle(nullptr); return; }     // there, or just past it
      sp = c.speed;                            // no slowing near the target: the drive is slow and stops dead
      if (el < RAMP_MS) sp = min(sp, (int)(START_DUTY + (sp - START_DUTY) * (int)el / (int)RAMP_MS));
      motorRaw(p, mv.angDir * msign(p), sp);
    }
    if (el > mv.grace && now - mv.spT >= 500) {         // speed, for the log (after the gear play is taken up)
      float s = fabsf(angDiff(mv.fAng, mv.spRef)) * 1000.0f / (now - mv.spT);
      if (s < mv.slowest) mv.slowest = s;
      mv.spT = now;
      mv.spRef = mv.fAng;
    } else if (el <= mv.grace) { mv.spT = now; mv.spRef = mv.fAng; }
    // Stall: no check while the gear play is taken up, then the angle has to change by stallDeg every stallMs.
    if (el > mv.grace && now - mv.stallT >= tune.stallMs) {
      if (fabsf(angDiff(mv.fAng, mv.stallRef)) < tune.stallDeg10 / 10.0f) { mv.stalled = true; toSettle(nullptr); return; }
      mv.stallT = now;
      mv.stallRef = mv.fAng;
    }
  } else if (mv.st == MS_PULSE) {
    if ((int32_t)(now - mv.deadline) >= 0) toSettle(nullptr);
  } else if (mv.st == MS_SETTLE) {
    if (now - mv.ts < SETTLE_MS) return;
    float a = readAngle(p);
    noteAngle(p, a);
    if (mv.fromRun && !isnan(mv.lastA)) {       // learn how much high it read while running
      float b = angDiff(mv.lastA, a) + bs[p].runBias;
      if (fabsf(b) < 15.0f) bs[p].runBias += (b - bs[p].runBias) * 0.3f;
      mv.fromRun = false;
    }
    mv.live = a;
    if (mv.kind == MV_JOG) {                   // a jog also shows which way the motor turns the sensor
      float d = angDiff(a, mv.startAng);
      if (fabsf(d) > 4.0f) {
        int s = (d > 0 ? 1 : -1) * mv.jogDir * 2;
        if (s != c.motSign) { c.motSign = s; cfgSave(); event("%s: motor direction learned (%+d)", c.name, s / 2); }
      }
      finishMove(mv.stalled ? "jog: stalled" : (mv.why ? mv.why : "jog"));
      return;
    }
    float e = moveErr(a);
    if (mv.why) { finishMove(mv.why); return; }
    if (fabsf(e) <= TOL_DEG) { finishMove("reached"); return; }
    if (mv.stalled) {
      bool atEnd = mv.kind == MV_TILT && fabsf(mv.tgt) >= 99.5f && fabsf(e) < END_STALL_DEG;
      if (atEnd) { finishMove("reached (end stop)"); return; }
      if (fabsf(e) > mv.startErr - 2.0f && tryFlip(a)) return;                      // no progress at all
      finishMove("blocked (stalled)");
      return;
    }
    int dir = e > 0 ? 1 : -1;
    if (dir != mv.travel) {                    // went past it. Turning back means taking up the gear play again.
      if (fabsf(e) <= OVER_OK_DEG) { finishMove("reached"); return; }
      if (mv.nudges < MAX_NUDGES) { mv.nudges++; beginRun(a); return; }
    } else if (mv.nudges < MAX_NUDGES) {       // a little short: push on the same way, then look again
      mv.nudges++;
      motorRaw(p, dir * msign(p), 100);
      mv.st = MS_PULSE;
      mv.deadline = now + (uint32_t)constrain(fabsf(e) * NUDGE_MS_PER_DEG, 200.0f, 3000.0f);
      return;
    }
    finishMove("stopped near the target");
  }
}

// ---- marks (setup): take the blind's present position as closed-up / open / closed-down
const char *setMark(int p, const String &w) {
  if (p < 0 || p >= PORTS) return "no such blind";
  if (moving()) return "wait until it stops";
  BlindCfg &c = cfg.b[p];
  if (w == "clear") { c.up = c.open = c.down = NAN; cfgSave(); noteAngle(p, bs[p].ang); event("%s: marks cleared", c.name); return nullptr; }
  pulseRead(p);
  if (!bs[p].present) return "no tilter plugged in";
  if (w == "up") c.up = bs[p].ang;
  else if (w == "open") c.open = bs[p].ang;
  else if (w == "down") c.down = bs[p].ang;
  else return "unknown mark";
  cfgSave();
  noteAngle(p, bs[p].ang);
  event("%s: marked %s at %.1f deg", c.name, w.c_str(), bs[p].ang);
  return nullptr;
}
