// Motion. Every blind has its own move, so several can turn at the same time (parMode on), or one after another with
// the rest waiting their turn (parMode off: easiest on the battery). Tilt is -100 (closed, slats down) .. 0 (open, level) ..
// +100 (closed, slats up), from three marked sensor angles. Every move is timed, stops on a stall, and ends with a
// reading taken with the motor stopped (the angle reads high while the motor runs: shared ground wire).
#pragma once
#include "power.h"
#include "pwmin.h"
#include "request.h"

struct BlindState {
  bool present = false, seen = false;
  bool pwm = false;             // this port's sensor sends PWM (found by listening when it wakes)
  int misses = 0;               // "nothing plugged in" results in a row
  bool blind = false;           // PWM sensor, but no pulses just now: within a few degrees of its zero
  float ang = NAN, mv = 0;      // last true angle (motor stopped)
  float tilt = NAN;             // from the marks; NAN = not set up or not read yet
  float target = NAN;           // tilt it is moving to
  bool queued = false;
  float qTilt = 0;
  char last[48] = "";           // how the last move ended
  int lastRaw = 0;              // which way the motor last turned (0 = not known): the other way has gear play to take up
  // How far the settled angle ends up beyond the last reading taken while running, per direction of turn
  // ([0] angle falling, [1] angle rising). It covers the sensor reading off while the motor runs, the delay of the
  // readings, and the rod carrying on. Learned at every stop; the motor is stopped this much early.
  float lead[2] = {2.5f, -3.0f};   // measured: it reads about 3 deg high while running, either way
};
BlindState bs[PORTS];

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
};
Move mvs[PORTS];                // one per port
Move *cur = &mvs[0];            // the one being worked on right now
#define MVX (*cur)
struct Use { Move *old; Use(int p) : old(cur) { cur = &mvs[p]; } ~Use() { cur = old; } };   // "work on port p's move in this scope"
bool motOn[PORTS] = {false, false, false};
bool movingPort(int p) { return mvs[p].kind != MV_NONE; }
bool moving() { for (int i = 0; i < PORTS; i++) if (mvs[i].kind != MV_NONE) return true; return false; }
int firstMoving() { for (int i = 0; i < PORTS; i++) if (mvs[i].kind != MV_NONE) return i; return -1; }

int msign(int p) { return cfg.b[p].motSign > 0 ? 1 : -1; }

// ---- marks (the math is in logic.h)
Marks marksOf(int p) { const BlindCfg &c = cfg.b[p]; return Marks{c.up, c.open, c.down}; }
const char *marksProblem(int p) { return marksProblemOf(marksOf(p)); }      // nullptr = good
bool calibrated(int p) { return marksProblem(p) == nullptr; }
// The one "can this blind be moved?" rule (logic.h), for commands, schedules, following and Apple Home alike.
bool movable(int p) { return movableRule(cfg.b[p].hidden, calibrated(p), bs[p].seen, bs[p].present); }
float arcX(int p, float ang) { return arcXOf(marksOf(p), ang); }           // degrees from open, + toward closed-up
float tiltOf(int p, float ang) { return tiltOfMarks(marksOf(p), ang); }
float xOfTilt(int p, float t) { return xOfTiltMarks(marksOf(p), t); }

// ---- hardware
void motorRaw(int p, int d, int pct) {        // DRV8833 slow decay: one input high, PWM the other (both high = brake)
  int du = constrain(pct, 0, 100) * 255 / 100;
  if (d > 0) { ledcWrite(P_IN1[p], 255); ledcWrite(P_IN2[p], 255 - du); }
  else if (d < 0) { ledcWrite(P_IN1[p], 255 - du); ledcWrite(P_IN2[p], 255); }
  else { ledcWrite(P_IN1[p], 255); ledcWrite(P_IN2[p], 255); }
  motOn[p] = d != 0;
  motorOn = motOn[0] || motOn[1] || motOn[2];
  Move &m = mvs[p];
  if (d && m.kind != MV_NONE) {
    m.rawDir = d;
    if (!m.graceSet) { m.graceSet = true; m.grace = bs[p].lastRaw == d ? (uint32_t)SAME_DIR_GRACE_MS : tune.graceMs; }
    bs[p].lastRaw = d;
  }
}
float degOf(float mv) { return constrain(mv / 1000.0f / (vdd - EN_DROP_V), 0.0f, 1.0f) * 360.0f; }   // output is a fraction of the sensor's supply
// The rail dips for a millisecond or two whenever Wi-Fi transmits, and the sensor's output dips with it. So the rail is
// measured just before and just after the angle: if the two disagree, the reading is thrown away and taken again.
float capLast[PORTS] = {0, 0, 0};
uint32_t capLastMs[PORTS] = {0, 0, 0};       // each port's last good PWM frame
float readAngle(int p) {
  if (bs[p].pwm) {                            // PWM sensor: the share of the frame that is high
    float sh = capShare(p);
    uint32_t t = millis();
    if (sh >= 0) { capLast[p] = sh; capLastMs[p] = t ? t : 1; }
    else if (capLastMs[p] && t - capLastMs[p] < 200) sh = capLast[p];     // a few frames lost to noise: keep the last good one
    bs[p].blind = sh < 0;
    if (sh < 0) sh = 0;                       // no pulses for a while: resting low (just above zero) or high (just below a full turn)
    bs[p].mv = sh * 3300.0f;                  // shown on the developer page in place of the voltage
    return sh * 360.0f;
  }
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
// Analog or PWM? Listen on the line for pulses. A PWM sensor that is resting (no pulses) sits at 0 V or at the supply,
// an analog one in the middle of its range does not: only then is a port that was PWM taken back to analog.
uint8_t pwmSaved = 0;                          // which ports were last seen sending PWM (kept in storage)
void sensorOff(int p) { capStop(p); digitalWrite(P_EN[p], LOW); }
void setSignal(int p, bool pwm) {
  if (pwm != (bool)((pwmSaved >> p) & 1)) {
    pwmSaved = pwm ? (pwmSaved | (1 << p)) : (pwmSaved & ~(1 << p));
    nvs.putUChar("pwm", pwmSaved);
    event("%s: sensor signal is %s", cfg.b[p].name, pwm ? "PWM" : "analog");
  }
  bs[p].pwm = pwm;
}
// Called with EN on and settled; blocks 40 to 70 ms. Works out: is a tilter plugged in, and is its sensor PWM or analog.
// Pulses first: the push test below is for a steady line, pulses would fool it.
void senseWake(int p) {
  bool was = bs[p].pwm || ((pwmSaved >> p) & 1);
  capLastMs[p] = 0;
  capStart(p, P_ANG[p]);
  for (int k = 0; k < (was ? 16 : 5) && capFrames[p] < 2; k++) delay(10);     // a known PWM sensor gets longer to start up
  if (capFrames[p] >= 2) { bs[p].present = true; bs[p].misses = 0; setSignal(p, true); return; }
  capStop(p);
  bool here = probePresent(p);                // steady line: empty port, analog sensor, or a PWM sensor resting
  if (here) bs[p].misses = 0;
  else if (bs[p].present && ++bs[p].misses < 3) return;        // one odd result does not unplug a blind
  bs[p].present = here;
  bool pwm = false;
  if (bs[p].present && was) {
    float mv = 0;
    for (int i = 0; i < 4; i++) mv += analogReadMilliVolts(P_ANG[p]);
    mv /= 4;
    pwm = mv < 250 || mv > (vdd - 0.45f) * 1000;      // resting at a rail: still the PWM sensor (near its zero, or no magnet)
  }
  if (bs[p].present) setSignal(p, pwm); else bs[p].pwm = false;
  if (pwm) capStart(p, P_ANG[p]);
}
void pulseRead(int p) {                       // wake the sensor for a moment (blocks ~30 ms). Not during a move.
  digitalWrite(P_EN[p], HIGH);
  delay(20);
  senseWake(p);
  noteAngle(p, readAngle(p));
  sensorOff(p);
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

// (setup's live reading, see watchTick)
void watchTick(uint32_t now);
int watchPort = -1;
bool watchOn = false;
uint32_t watchUntil = 0;
bool handBusy = false;                         // the watch is on a blind that is being turned by hand (see handTick)
void handCheck(int p, uint32_t now);
uint32_t setupSeen = 0;                        // millis of the app's last "setup is open" call: no following by hand then
// ---- moves
float moveErr(float ang) {                    // signed degrees; + means the angle has to rise
  if (MVX.kind == MV_TILT) return (xOfTilt(MVX.port, MVX.tgt) - arcX(MVX.port, ang)) * sgn(angDiff(cfg.b[MVX.port].up, cfg.b[MVX.port].open));
  return angDiff(MVX.tgt, ang);
}
// A recording of the last move, for the developer page: the angle every 40 ms from the start until 1.5 s after the stop.
struct TracePt { uint16_t t, a; uint8_t st; };          // t: 10 ms units; a: tenths of a degree; st: state, +16 = motor on
const int TRACE_N = 1500;
TracePt trace[TRACE_N];
int traceN = 0;
uint32_t traceT0 = 0, traceLast = 0;
float traceTgt = NAN;
int tracePort = -1;                            // whose move is being recorded (the first one that started)
void tr(uint32_t now, float a) {
  if (MVX.port != tracePort || traceN >= TRACE_N || now - traceLast < 40 || isnan(a)) return;
  traceLast = now;
  trace[traceN++] = {(uint16_t)((now - traceT0) / 10), (uint16_t)lroundf(a * 10.0f), (uint8_t)(MVX.st | (motOn[MVX.port] ? 16 : 0))};
}
float handRef[PORTS] = {NAN, NAN, NAN};        // each blind's tilt as the controller last left it (see "turned by hand")
void finishMove(const char *msg) {
  int p = MVX.port;
  motorRaw(p, 0, 0);
  sensorOff(p);
  if (MVX.kind != MV_JOG) {
    bool better = fabsf(moveErr(bs[p].ang)) < MVX.startErr - 3.0f;
    if (MVX.flipped && !better) cfg.b[p].motSign = -cfg.b[p].motSign;      // the flip did not help: undo it
    else if (better && abs(cfg.b[p].motSign) != 2) {                      // it went the right way: direction is now known
      cfg.b[p].motSign = msign(p) * 2;
      cfgSave();
      event("%s: motor direction confirmed (%+d)", cfg.b[p].name, msign(p));
    }
    stats.moves[p]++;
    if (MVX.stalled) stats.stalls[p]++;
    float trav = fabsf(angDiff(bs[p].ang, MVX.startAng)), avg = MVX.runMs ? trav * 1000.0f / MVX.runMs : 0;
    char sp[40];
    snprintf(sp, sizeof sp, "%.1f deg/s, %d nudge%s, %d turn-back%s", avg, MVX.nudges - MVX.turnBacks, MVX.nudges - MVX.turnBacks == 1 ? "" : "s", MVX.turnBacks, MVX.turnBacks == 1 ? "" : "s");
    if (isnan(bs[p].tilt)) event("%s: %s at %.1f deg (%.1f s, %s)", cfg.b[p].name, msg, bs[p].ang, MVX.runMs / 1000.0f, sp);
    else event("%s: %s at tilt %.0f (%.1f deg, %.1f s, %s)", cfg.b[p].name, msg, bs[p].tilt, bs[p].ang, MVX.runMs / 1000.0f, sp);
  } else if (MVX.runMs > 800) event("%s: jog %.1f deg in %.1f s%s", cfg.b[p].name, angDiff(bs[p].ang, MVX.startAng), MVX.runMs / 1000.0f, MVX.stalled ? " (stalled)" : "");
  stats.motorMs += MVX.runMs;
  if (!powered) stats.battMotorMs += MVX.runMs;
  strlcpy(bs[p].last, msg, sizeof bs[p].last);
  bs[p].target = NAN;
  handRef[p] = bs[p].tilt;                     // the motor put it here: not a turn by hand
  MVX = Move();
}
void toSettle(const char *why) {
  MVX.fromRun = MVX.st == MS_RUN;
  motorRaw(MVX.port, 0, 0);
  MVX.why = why;
  MVX.st = MS_SETTLE;
  MVX.ts = millis();
}
void beginRun(float a) {
  MVX.st = MS_RUN;
  MVX.ts = MVX.stallT = MVX.spT = MVX.winT = millis();
  MVX.stallRef = MVX.spRef = MVX.winRef = MVX.fAng = a;
  MVX.winAcc = 0; MVX.winN = 0; MVX.hn = 0; MVX.hit = 0;
  MVX.graceSet = false;
  MVX.stalled = false;
  MVX.runErr = fabsf(moveErr(a));
  MVX.refSet = false;
  MVX.angDir = 0;
}
bool beginMove(int kind, int p) {             // leaves cur on port p
  cur = &mvs[p];
  if (MVX.kind != MV_NONE) { motorRaw(p, 0, 0); sensorOff(p); bs[p].target = NAN; }
  bool others = false;
  for (int i = 0; i < PORTS; i++) if (i != p && mvs[i].kind != MV_NONE) others = true;
  MVX = Move();
  MVX.kind = kind;
  MVX.port = p;
  if (watchOn) { if (watchPort != p) sensorOff(watchPort); watchOn = false; }
  watchPort = -1; handBusy = false;
  MVX.t0 = MVX.ts = MVX.lastTick = millis();
  if (!others) { tracePort = p; traceN = 0; traceT0 = MVX.t0; traceLast = 0; traceTgt = NAN; }
  digitalWrite(P_EN[p], HIGH);
  return true;
}
// Go to a tilt. Returns nullptr if accepted, else why not.
const char *startTilt(int p, float t) {
  if (p < 0 || p >= PORTS) return "no such blind";
  if (const char *e = cannotMoveWhy(calibrated(p), bs[p].seen, bs[p].present, battOkToMove())) return e;   // logic.h
  t = constrain(t, -100.0f, 100.0f);
  bool others = false;
  for (int i = 0; i < PORTS; i++) if (i != p && mvs[i].kind != MV_NONE) others = true;
  if (others && !parMode && mvs[p].kind == MV_NONE) { bs[p].queued = true; bs[p].qTilt = t; bs[p].target = t; return nullptr; }   // one at a time: wait
  Use u(p);
  if (MVX.kind == MV_TILT) {                    // new target while moving: carry on from here
    MVX.tgt = t; MVX.nudges = 0; MVX.t0 = millis(); bs[p].target = t;
    if (MVX.st != MS_WAKE) beginRun(isnan(MVX.live) ? bs[p].ang : MVX.live);
    return nullptr;
  }
  beginMove(MV_TILT, p);
  MVX.tgt = t;
  bs[p].target = t;
  bs[p].queued = false;
  return nullptr;
}
const char *startAngle(int p, float deg) {    // developer: go to a raw sensor angle
  if (p < 0 || p >= PORTS) return "no such blind";
  if (!battOkToMove()) return "battery too low";
  Use u(p);
  beginMove(MV_ANGLE, p);
  MVX.tgt = fmodf(deg + 360.0f, 360.0f);
  return nullptr;
}
const char *jog(int p, int d, int pct, uint32_t ms) {   // hold-to-run: call again before the time is up
  if (p < 0 || p >= PORTS) return "no such blind";
  if (!battOkToMove()) return "battery too low";
  ms = min(ms, (uint32_t)2000);
  Use u(p);
  if (MVX.kind == MV_JOG && MVX.jogDir == d) { MVX.deadline = millis() + ms; MVX.pct = pct; return nullptr; }
  beginMove(MV_JOG, p);
  MVX.jogDir = d;
  MVX.pct = pct;
  MVX.deadline = millis() + ms + 30;
  return nullptr;
}
void stopAll(const char *why) {
  for (int i = 0; i < PORTS; i++) { if (bs[i].queued) bs[i].target = NAN; bs[i].queued = false; }
  for (int i = 0; i < PORTS; i++) {
    if (mvs[i].kind == MV_NONE) continue;
    Use u(i);
    if (MVX.st == MS_WAKE) { noteAngle(i, readAngle(i)); finishMove(why); continue; }
    if (MVX.st != MS_SETTLE || !MVX.why) { MVX.nudges = MAX_NUDGES + 1; toSettle(why); }
  }
}

// ---- Move requests (request.h decides; this is the controller's side of its seam)
// Gentle moves: a blind that is being taken to a tilt slowly, a little every 20 seconds (schedules.h: rampTick).
struct Ramp { bool on; float from, to; uint32_t t0, durMs, last; } ramp[PORTS];
void rampCancel() { for (auto &r : ramp) r.on = false; }
bool rampAny() { for (auto &r : ramp) if (r.on) return true; return false; }
struct EspMoves : MoveSeam {
  bool follow() override { return syncMode; }
  bool movable(int p) override { return ::movable(p); }
  bool calibrated(int p) override { return ::calibrated(p); }
  float tilt(int p) override { return bs[p].tilt; }
  const char *now(int p, float t) override { return startTilt(p, t); }
  void gently(int p, float from, float to, uint32_t ms) override { ramp[p] = {true, from, to, millis(), ms, 0}; }
  void stopGentle() override { rampCancel(); }
} espMoves;
MoveResult moveBlinds(const MoveAsk &a) { return moveRequest(a, espMoves); }
void moveStop() { rampCancel(); stopAll("stopped"); }   // the app's or Home's stop: also ends a gentle move

void endMove(const char *msg) { motorRaw(MVX.port, 0, 0); MVX.endMsg = msg; MVX.st = MS_POST; MVX.ts = millis(); }
bool tryFlip(float a) {                        // direction never seen to be right: the motor may be the other way round, try once
  if (MVX.flipped || MVX.kind == MV_JOG || abs(cfg.b[MVX.port].motSign) == 2) return false;
  MVX.flipped = true;
  cfg.b[MVX.port].motSign = -cfg.b[MVX.port].motSign;
  event("%s: going the wrong way, trying the other direction", cfg.b[MVX.port].name);
  beginRun(a);
  return true;
}

bool uiActive();                               // app_main.cpp
void moveTick(int p, uint32_t now);
void motionTick() {
  uint32_t now = millis();
  static uint32_t lastT = 0, lastIdle = 0;
  static int idlePort = 0;
  if (!moving()) {
    for (int i = 0; i < PORTS; i++)
      if (bs[i].queued) { bs[i].queued = false; const char *e = startTilt(i, bs[i].qTilt); if (e) { strlcpy(bs[i].last, e, sizeof bs[i].last); bs[i].target = NAN; } return; }
    if (watchPort >= 0) { watchTick(now); return; }
    // Keep the positions fresh: the wand may have been turned by hand. One port at a time. With "blinds follow each
    // other" on and two or more blinds, always (quicker on input power); otherwise only while someone looks.
    int n = 0;
    for (int i = 0; i < PORTS; i++) if (movable(i)) n++;
    bool follow = syncMode && n >= 2;
    uint32_t step = follow && (powered || uiActive()) ? 350 : 1000;
    if (now - lastIdle >= step && (follow || uiActive() || !bs[idlePort].seen)) {
      lastIdle = now;
      pulseRead(idlePort);
      if (follow) handCheck(idlePort, now);
      idlePort = (idlePort + 1) % PORTS;
    }
    return;
  }
  if (now - lastT < 10) return;                // 100 Hz
  lastT = now;
  for (int i = 0; i < PORTS; i++) if (mvs[i].kind != MV_NONE) { Use u(i); moveTick(i, now); }
}
void moveTick(int p, uint32_t now) {           // one blind's move, 100 times a second (cur is its move)
  BlindCfg &c = cfg.b[p];
  if (motOn[p]) MVX.runMs += now - MVX.lastTick;
  MVX.lastTick = now;

  if (MVX.st == MS_WAKE) {
    if (now - MVX.ts < 20) return;
    senseWake(p);
    float a = readAngle(p);
    noteAngle(p, a);
    if (!bs[p].present) { finishMove("no tilter plugged in"); return; }
    MVX.startAng = a;
    MVX.live = a;
    if (MVX.kind != MV_JOG) {
      MVX.startErr = fabsf(moveErr(a));
      if (MVX.startErr <= TOL_DEG) { finishMove("already there"); return; }
    }
    beginRun(a);
  } else if (MVX.st == MS_RUN) {
    // While the motor runs the reading jumps about by a couple of degrees (brush noise on the shared wires).
    // For stopping: the middle one of the last five readings, twice in a row. For speed and stall: quarter-second averages.
    float raw = readAngle(p), a = raw;
    MVX.hb[MVX.hn % 5] = raw;
    MVX.hn++;
    if (MVX.hn >= 5) {                           // the middle one of the last five (measured: +-1 deg jitter, spikes to +10)
      float d[5];
      for (int k = 0; k < 5; k++) d[k] = angDiff(MVX.hb[k], raw);
      for (int x = 1; x < 5; x++) for (int y = x; y > 0 && d[y - 1] > d[y]; y--) { float t = d[y]; d[y] = d[y - 1]; d[y - 1] = t; }
      a = fmodf(raw + d[2] + 360.0f, 360.0f);
    }
    MVX.lastA = a;
    tr(now, a);
    MVX.lastDir = MVX.rawDir * msign(p);                       // +1: the angle is rising
    if (MVX.lastDir) a = fmodf(a + MVX.lastDir * bs[p].lead[MVX.lastDir > 0] + 360.0f, 360.0f);   // where it will settle if stopped now
    MVX.winAcc += angDiff(a, MVX.winRef); MVX.winN++;
    if (now - MVX.winT >= 250) {
      MVX.fAng = fmodf(MVX.winRef + MVX.winAcc / MVX.winN + 360.0f, 360.0f);
      MVX.winRef = MVX.fAng; MVX.winAcc = 0; MVX.winN = 0; MVX.winT = now;
    }
    MVX.live = MVX.fAng;
    uint32_t el = now - MVX.ts;
    int sp;
    if (now - MVX.t0 > (uint32_t)tune.moveMaxS * 1000) { MVX.nudges = MAX_NUDGES + 1; toSettle("stopped: time limit"); return; }
    if (MVX.kind == MV_JOG) {
      if ((int32_t)(now - MVX.deadline) >= 0) { toSettle(nullptr); return; }
      sp = MVX.pct;
      if (el < RAMP_MS) sp = min(sp, (int)(START_DUTY + (sp - START_DUTY) * (int)el / (int)RAMP_MS));
      motorRaw(p, MVX.jogDir, sp);
    } else {
      float e = moveErr(a);
      int want = e > 0 ? 1 : -1;
      if (MVX.angDir == 0) MVX.angDir = MVX.travel = want;
      if (MVX.hn < 5) want = MVX.angDir;                          // not enough readings yet to judge
      if (want != MVX.angDir || fabsf(e) <= 1.0f) { if (++MVX.hit >= 2) { toSettle(nullptr); return; } }   // there, or just past it
      else MVX.hit = 0;
      sp = c.speed;                            // no slowing near the target: the drive is slow and stops dead
      if (el < RAMP_MS) sp = min(sp, (int)(START_DUTY + (sp - START_DUTY) * (int)el / (int)RAMP_MS));
      motorRaw(p, MVX.angDir * msign(p), sp);
    }
    if (el > MVX.grace && now - MVX.spT >= 500) {         // speed, for the log (after the gear play is taken up)
      float s = fabsf(angDiff(MVX.fAng, MVX.spRef)) * 1000.0f / (now - MVX.spT);
      if (s < MVX.slowest) MVX.slowest = s;
      MVX.spT = now;
      MVX.spRef = MVX.fAng;
    } else if (el <= MVX.grace) { MVX.spT = now; MVX.spRef = MVX.fAng; }
    if (bs[p].blind) MVX.stallT = now;            // PWM sensor passing its zero: no reading for a few degrees, not a stall
    // Stall: no check while the gear play is taken up, then the angle has to change by stallDeg every stallMs.
    StallVerdict sv = stallCheck(el, MVX.grace, now - MVX.stallT, tune.stallMs, MVX.fAng, MVX.stallRef, tune.stallDeg10 / 10.0f);
    if (sv == STALL_YES) { MVX.stalled = true; toSettle(nullptr); return; }
    if (sv == STALL_MOVED) { MVX.stallT = now; MVX.stallRef = MVX.fAng; }
  } else if (MVX.st == MS_PULSE) {
    tr(now, readAngle(p));
    if ((int32_t)(now - MVX.deadline) >= 0) toSettle(nullptr);
  } else if (MVX.st == MS_POST) {               // stopped: keep watching for a moment (the rod springs back a little)
    float a = readAngle(p);
    tr(now, a);
    if (now - MVX.ts < POST_MS) return;
    noteAngle(p, a);
    finishMove(MVX.endMsg ? MVX.endMsg : "stopped");
  } else if (MVX.st == MS_SETTLE) {
    float a = readAngle(p);
    tr(now, a);
    if (now - MVX.ts < SETTLE_MS) return;
    noteAngle(p, a);
    if (MVX.fromRun && !isnan(MVX.lastA) && MVX.lastDir) {     // learn how far it went on after the last running reading
      float c = angDiff(a, MVX.lastA) * MVX.lastDir;
      float &ld = bs[p].lead[MVX.lastDir > 0];
      if (c > -10.0f && c < 12.0f) ld = constrain(ld + (c - ld) * 0.4f, -8.0f, 8.0f);
      MVX.fromRun = false;
    }
    MVX.live = a;
    if (MVX.kind == MV_JOG) {                   // a jog also shows which way the motor turns the sensor
      float d = angDiff(a, MVX.startAng);
      if (fabsf(d) > 4.0f) {
        int s = (d > 0 ? 1 : -1) * MVX.jogDir * 2;
        if (s != c.motSign) { c.motSign = s; cfgSave(); event("%s: motor direction learned (%+d)", c.name, s / 2); }
      }
      endMove(MVX.stalled ? "jog: stalled" : (MVX.why ? MVX.why : "jog"));
      return;
    }
    float e = moveErr(a);
    if (MVX.why) { endMove(MVX.why); return; }
    if (fabsf(e) <= TOL_DEG) { endMove("reached"); return; }
    if (MVX.stalled) {
      bool atEnd = MVX.kind == MV_TILT && fabsf(MVX.tgt) >= 99.5f && fabsf(e) < END_STALL_DEG;
      if (atEnd) { endMove("reached (end stop)"); return; }
      if (fabsf(e) > MVX.startErr - 2.0f && tryFlip(a)) return;                      // no progress at all
      endMove("blocked (stalled)");
      return;
    }
    int dir = e > 0 ? 1 : -1;
    if (dir != MVX.travel) {                    // went past it. Turning back means taking up the gear play again.
      if (fabsf(e) <= OVER_OK_DEG) { endMove("reached"); return; }
      if (MVX.nudges < MAX_NUDGES) { MVX.nudges++; MVX.turnBacks++; beginRun(a); return; }
    } else if (MVX.nudges < MAX_NUDGES) {       // short: run on the same way, watching the angle (no blind timed push)
      MVX.nudges++;
      beginRun(a);
      return;
    }
    endMove("stopped near the target");
  }
}

// ---- setup: keep one blind's sensor on and its reading live (the app asks again every second while a setup is open)
void watchStop() { if (watchOn && watchPort >= 0 && !movingPort(watchPort)) sensorOff(watchPort); watchOn = false; watchPort = -1; handBusy = false; }
// ---- turned by hand: with "blinds follow each other" on, a blind that is turned with its wand takes the others along.
// The idle look-round (motionTick) sees a blind away from where the controller left it; its sensor then stays on
// until it has held still for 0.7 s, and the other blinds are sent to the same tilt.
const float HAND_TILT = 6.0f;                  // a change of this much (tilt units) starts it
float handLast = 0;
uint32_t handStill = 0, handSince = 0;
void handCheck(int p, uint32_t now) {          // p has just been read (motor stopped)
  if (!movable(p) || bs[p].blind || isnan(bs[p].tilt)) return;
  if (setupSeen && now - setupSeen < 15000) { handRef[p] = bs[p].tilt; return; }     // a setup screen is open: hands are expected
  if (isnan(handRef[p])) { handRef[p] = bs[p].tilt; return; }
  if (fabsf(bs[p].tilt - handRef[p]) < HAND_TILT) return;
  watchPort = p; watchUntil = now + 3000; handBusy = true;
  handLast = bs[p].ang; handStill = handSince = now;
}
void handTick(uint32_t now) {                  // from watchTick, every 100 ms, with a fresh reading
  int p = watchPort;
  watchUntil = now + 3000;
  if (bs[p].blind) { handStill = now; return; }
  if (fabsf(angDiff(bs[p].ang, handLast)) > 0.7f) { handLast = bs[p].ang; handStill = now; }
  bool timeout = now - handSince > 60000;
  if (now - handStill < 700 && !timeout) return;
  float t = constrain(bs[p].tilt, -100.0f, 100.0f);
  bool moved = !timeout && !isnan(t) && fabsf(t - handRef[p]) >= HAND_TILT * 0.6f;
  handRef[p] = bs[p].tilt;
  watchStop();
  if (!moved) return;
  int n = moveBlinds(moveAsk(FROM_HAND, p, t)).started;
  event("%s turned by hand to tilt %.0f: %d other blind%s follow%s", cfg.b[p].name, t, n, n == 1 ? "" : "s", n == 1 ? "s" : "");
}
void watchTick(uint32_t now) {                 // from motionTick, only while nothing moves
  static uint32_t last = 0;
  if (watchPort < 0) return;
  if ((int32_t)(watchUntil - now) <= 0) { watchStop(); return; }
  if (!watchOn) { digitalWrite(P_EN[watchPort], HIGH); delay(20); senseWake(watchPort); watchOn = true; }
  if (now - last >= 100) { last = now; noteAngle(watchPort, readAngle(watchPort)); if (handBusy) handTick(now); }
}
// A reading for a mark: the sensor has to hold still (within 1 degree) for 0.6 s. Returns NAN if it does not.
float steadyAngle(int p) {
  float a0 = readAngle(p), lo = 0, hi = 0, sum = 0;
  for (int k = 0; k < 12; k++) {
    delay(50);
    float d = angDiff(readAngle(p), a0);
    lo = min(lo, d); hi = max(hi, d); sum += d;
  }
  if (hi - lo > 1.0f) return NAN;
  return fmodf(a0 + sum / 12 + 360.0f, 360.0f);
}
// ---- marks (setup): take the blind's present position as closed-up / open / closed-down
const char *setMark(int p, const String &w) {
  if (p < 0 || p >= PORTS) return "no such blind";
  if (moving()) return "wait until it stops";
  BlindCfg &c = cfg.b[p];
  if (w == "clear") { c.up = c.open = c.down = NAN; cfgSave(); noteAngle(p, bs[p].ang); event("%s: marks cleared", c.name); return nullptr; }
  if (!(watchOn && watchPort == p)) { watchStop(); digitalWrite(P_EN[p], HIGH); delay(20); senseWake(p); watchPort = p; watchOn = true; watchUntil = millis() + 3000; }
  handBusy = false;
  if (!bs[p].present) return "no tilter plugged in";
  float st = steadyAngle(p);
  if (isnan(st)) return "the slats are still moving: let them settle, then tap again";
  noteAngle(p, st);
  if (w == "up") c.up = bs[p].ang;
  else if (w == "open") c.open = bs[p].ang;
  else if (w == "down") c.down = bs[p].ang;
  else return "unknown mark";
  cfgSave();
  noteAngle(p, bs[p].ang);
  handRef[p] = NAN; setupSeen = millis() ? millis() : 1;
  event("%s: marked %s at %.1f deg", c.name, w.c_str(), bs[p].ang);
  return nullptr;
}
