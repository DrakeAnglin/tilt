// Motion. Every blind has its own move, so several can turn at the same time (parMode on), or one after another with
// the rest waiting their turn (parMode off: easiest on the battery). Tilt is -100 (closed, slats down) .. 0 (open, level) ..
// +100 (closed, slats up), from three marked sensor angles. The move itself is tilter.h; this file is the controller's
// side: the sensors, the motor drivers, and the Tilter adapter (EspTilter) that tilter.h works through.
#pragma once
#include "power.h"
#include "pwmin.h"
#include "request.h"
#include "handwatch.h"
#include "lock.h"                                // mx, Unlocked: the mark's steady reading waits unlocked

struct BlindState {
  bool present = false, seen = false;
  bool pwm = false;             // this port's sensor sends PWM (found by listening when it wakes)
  int misses = 0;               // "nothing plugged in" results in a row
  bool blind = false;           // no fresh reading just now (at its zero, or a dropout): the angle is the last good one
  bool lost = false;            // a dropout: the sensor gave nothing, away from its zero (logic.h ReadingJudge)
  ReadingJudge judge;           // this port's readings in turn, and the last fresh angle
  uint32_t drops = 0, dropLogMs = 0;   // dropouts since the last log line; when that was
  float ang = NAN, mv = 0;      // last true angle (motor stopped)
  float tilt = NAN;             // from the marks; NAN = not set up or not read yet
  float target = NAN;           // tilt it is moving to
  bool queued = false;
  float qTilt = 0;
  char last[48] = "";           // how the last move ended
  TiltMemory mem;               // which way it last turned, and how far it carries on (tilter.h)
};
BlindState bs[PORTS];

// (Move: tilter.h)
Move mvs[PORTS];                // one per port
Move *cur = &mvs[0];            // the one being worked on right now
#define MVX (*cur)
struct Use { Move *old; Use(int p) : old(cur) { cur = &mvs[p]; } ~Use() { cur = old; } };   // "work on port p's move in this scope"
bool motOn[PORTS] = {false, false, false};
bool motorsHeld = false;                       // restarting (web.h restartNow): no motor may start again
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
// What Apple Home, the app and the hub are all told about a blind (one answer, so they never disagree). tilt is the
// Current tilt (NAN: unknown or not set up); busy: moving or waiting its turn.
struct BlindReport { float tilt; bool busy; float target; bool movable; };
BlindReport blindNow(int p) {
  return {currentTiltOf(marksOf(p), movingPort(p), mvs[p].live, bs[p].tilt), movingPort(p) || bs[p].queued, bs[p].target, movable(p)};
}

// ---- hardware
void motorRaw(int p, int d, int pct) {        // DRV8833 slow decay: one input high, PWM the other (both high = brake)
  int du = constrain(pct, 0, 100) * 255 / 100;
  if (d > 0) { ledcWrite(P_IN1[p], 255); ledcWrite(P_IN2[p], 255 - du); }
  else if (d < 0) { ledcWrite(P_IN1[p], 255 - du); ledcWrite(P_IN2[p], 255); }
  else { ledcWrite(P_IN1[p], 255); ledcWrite(P_IN2[p], 255); }
  motOn[p] = d != 0;
  motorOn = motOn[0] || motOn[1] || motOn[2];
}
float degOf(float mv) { return constrain(mv / 1000.0f / (vdd - EN_DROP_V), 0.0f, 1.0f) * 360.0f; }   // output is a fraction of the sensor's supply
// The rail dips for a millisecond or two whenever Wi-Fi transmits, and the sensor's output dips with it. So the rail is
// measured just before and just after the angle: if the two disagree, the reading is thrown away and taken again.
float capLast[PORTS] = {0, 0, 0};
uint32_t capLastMs[PORTS] = {0, 0, 0};       // each port's last good PWM frame
// A reading at a rail, judged (logic.h judgeReading): the sensor's zero, or a dropout. A dropout is logged, but at most
// one line every 10 minutes for each blind, with how many there were.
float judged(int p, float raw, bool atRail) {
  SensorRead r = bs[p].judge.judge(raw, atRail);
  if (r.lost && !bs[p].lost) {
    bs[p].drops++;
    uint32_t t = millis();
    if (!bs[p].dropLogMs || t - bs[p].dropLogMs > 600000) {
      event("%s: the sensor gave no reading (%lu time%s): the last angle is kept", cfg.b[p].name, (unsigned long)bs[p].drops, bs[p].drops == 1 ? "" : "s");
      bs[p].dropLogMs = t ? t : 1;
      bs[p].drops = 0;
    }
  }
  bs[p].blind = r.guess;
  bs[p].lost = r.lost;
  return r.ang;
}
float readAngle(int p) {
  if (bs[p].pwm) {                            // PWM sensor: the share of the frame that is high
    float sh = capShare(p);
    uint32_t t = millis();
    if (sh >= 0) { capLast[p] = sh; capLastMs[p] = t ? t : 1; }
    else if (capLastMs[p] && t - capLastMs[p] < 200) sh = capLast[p];     // a few frames lost to noise: keep the last good one
    bs[p].mv = sh >= 0 ? sh * 3300.0f : 0;    // shown on the developer page in place of the voltage
    // No pulses for a while: within a few degrees of its zero (resting low just above it, or high just below a full
    // turn), if it was last seen there; the last good reading is kept, which is on the right side of zero (a flat 0
    // could be read as a jump of tens of degrees). Anywhere else: a dropout.
    return judged(p, sh >= 0 ? sh * 360.0f : 0, sh < 0);
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
  return judged(p, degOf(bs[p].mv), bs[p].mv < ANALOG_RAIL_MV);   // 0 V: its zero, or a dropout
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
  // No pulses or 0 V with no good reading yet (just after a restart): its zero or a dropout, nobody can tell. The
  // tilt stays unknown until a good reading, rather than a guess of 0 degrees (Middle showed tilt 112.6: #135).
  if (bs[p].blind && isnan(bs[p].ang)) { bs[p].tilt = NAN; return; }
  if (!bs[p].present) bs[p].judge.forget();
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
  pwmSaved = nvs.getUChar("pwm", 0);
}

// ---- the watch and Follow: handwatch.h decides, the watch code below is its adapter
HandWatch hand;
int sensorPort = -1;                           // the blind whose sensor the watch has switched on; -1 = none
void watchTick(uint32_t now, int p);
void watchSync(int p);
void followHand(int p, float t);
// ---- moves
// A recording of the last move, for the developer page: the angle every 40 ms from the start until 1.5 s after the stop.
struct TracePt { uint16_t t, a; uint8_t st; };          // t: 10 ms units; a: tenths of a degree; st: state, +16 = motor on
const int TRACE_N = 1500;
TracePt trace[TRACE_N];
int traceN = 0;
uint32_t traceT0 = 0, traceLast = 0;
float traceTgt = NAN;
int tracePort = -1;                            // whose move is being recorded (the first one that started)
void tr(const Move &m, uint32_t now, float a) {
  if (m.port != tracePort || traceN >= TRACE_N || now - traceLast < 40 || isnan(a)) return;
  traceLast = now;
  trace[traceN++] = {(uint16_t)((now - traceT0) / 10), (uint16_t)lroundf(a * 10.0f), (uint8_t)(m.st | (motOn[m.port] ? 16 : 0))};
}
// The Tilter seam's controller adapter: today's sensor, motor, clock, settings and log calls for one port.
struct EspTilter : Tilter {
  int p;
  EspTilter(int port) : p(port) {}
  uint32_t ms() override { return millis(); }
  bool wake() override { senseWake(p); return bs[p].present; }
  float angle() override { return readAngle(p); }
  bool noReading() override { return bs[p].blind; }
  bool lost() override { return bs[p].lost; }
  float note(float a) override { noteAngle(p, a); return bs[p].ang; }
  void motor(int d, int pct) override { motorRaw(p, d, pct); }
  TiltSettings settings() override {
    return {marksOf(p), cfg.b[p].speed, tune.graceMs, tune.stallMs, (uint32_t)tune.moveMaxS * 1000, tune.stallDeg10 / 10.0f, leadMax10 / 10.0f};
  }
  int8_t &motSign() override { return cfg.b[p].motSign; }
  TiltMemory &memory() override { return bs[p].mem; }
  void keep() override { cfgSave(); }
  void say(const char *msg) override { event("%s: %s", cfg.b[p].name, msg); }
  void trace(uint32_t now, float a, const Move &m) override { tr(m, now, a); }
  void ended(const Move &m, const char *msg) override {
    sensorOff(p);
    if (m.kind != MV_JOG) {
      stats.moves[p]++;
      if (m.stalled) stats.stalls[p]++;
      if (m.stalled && m.kind == MV_TILT) movesStalled[p]++;
      float trav = fabsf(angDiff(bs[p].ang, m.startAng)), avg = m.runMs ? trav * 1000.0f / m.runMs : 0;
      char sp[40];
      snprintf(sp, sizeof sp, "%.1f deg/s, %d nudge%s, %d turn-back%s", avg, m.nudges - m.turnBacks, m.nudges - m.turnBacks == 1 ? "" : "s", m.turnBacks, m.turnBacks == 1 ? "" : "s");
      if (isnan(bs[p].tilt)) event("%s: %s at %.1f deg (%.1f s, %s)", cfg.b[p].name, msg, bs[p].ang, m.runMs / 1000.0f, sp);
      else event("%s: %s at tilt %.0f (%.1f deg, %.1f s, %s)", cfg.b[p].name, msg, bs[p].tilt, bs[p].ang, m.runMs / 1000.0f, sp);
    } else if (m.runMs > 800) event("%s: jog %.1f deg in %.1f s%s", cfg.b[p].name, angDiff(bs[p].ang, m.startAng), m.runMs / 1000.0f, m.stalled ? " (stalled)" : "");
    stats.motorMs += m.runMs;
    if (!powered) stats.battMotorMs += m.runMs;
    strlcpy(bs[p].last, msg, sizeof bs[p].last);
    bs[p].target = NAN;
    hand.motorLeft(p, bs[p].tilt);               // the motor put it here: not a turn by hand
  }
};
EspTilter tilters[PORTS] = {EspTilter(0), EspTilter(1), EspTilter(2)};
bool beginMove(int kind, int p) {             // leaves cur on port p
  cur = &mvs[p];
  if (MVX.kind != MV_NONE) { motorRaw(p, 0, 0); sensorOff(p); bs[p].target = NAN; }
  bool others = false;
  for (int i = 0; i < PORTS; i++) if (i != p && mvs[i].kind != MV_NONE) others = true;
  if (sensorPort >= 0 && sensorPort != p) sensorOff(sensorPort);   // the move reads its own sensor: the watch ends
  sensorPort = -1;
  hand.motorStarted();
  moveFresh(MVX, kind, p, millis());
  if (!others) { tracePort = p; traceN = 0; traceT0 = MVX.t0; traceLast = 0; traceTgt = NAN; }
  digitalWrite(P_EN[p], HIGH);
  return true;
}
// Go to a tilt. Returns nullptr if accepted, else why not.
const char *startTilt(int p, float t) {
  if (p < 0 || p >= PORTS) return "no such blind";
  if (motorsHeld) return "restarting";
  if (const char *e = cannotMoveWhy(calibrated(p), bs[p].seen, bs[p].present, battOkToMove())) return e;   // logic.h
  t = constrain(t, -100.0f, 100.0f);
  bool others = false;
  for (int i = 0; i < PORTS; i++) if (i != p && mvs[i].kind != MV_NONE) others = true;
  if (others && !parMode && mvs[p].kind == MV_NONE) { bs[p].queued = true; bs[p].qTilt = t; bs[p].target = t; return nullptr; }   // one at a time: wait
  Use u(p);
  if (MVX.kind == MV_TILT) {                    // new target while moving: carry on from here
    MVX.tgt = t; MVX.nudges = 0; MVX.t0 = millis(); bs[p].target = t;
    if (MVX.st != MS_WAKE) beginRun(MVX, tilters[p], isnan(MVX.live) ? bs[p].ang : MVX.live);
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
  if (motorsHeld) return "restarting";
  if (!battOkToMove()) return "battery too low";
  Use u(p);
  beginMove(MV_ANGLE, p);
  MVX.tgt = fmodf(deg + 360.0f, 360.0f);
  return nullptr;
}
// Hold-to-run: call again before the time is up. seek (setup): one long run that ends on its own when the motor stalls
// at an end (the stall check below reads the sensor every few ms), so the phone doesn't judge the end over a slow link.
const char *jog(int p, int d, int pct, uint32_t ms, bool seek) {
  if (p < 0 || p >= PORTS) return "no such blind";
  if (motorsHeld) return "restarting";
  if (!battOkToMove()) return "battery too low";
  ms = min(ms, (uint32_t)(seek ? 30000 : 2000));
  Use u(p);
  if (MVX.kind == MV_JOG && MVX.jogDir == d) { MVX.deadline = millis() + ms; MVX.pct = pct; return nullptr; }
  beginMove(MV_JOG, p);
  MVX.jogDir = d;
  MVX.seek = seek;
  MVX.pct = pct;
  MVX.deadline = millis() + ms + 30;
  return nullptr;
}
void stopAll(const char *why) {
  for (int i = 0; i < PORTS; i++) { if (bs[i].queued) bs[i].target = NAN; bs[i].queued = false; }
  for (int i = 0; i < PORTS; i++) {
    if (mvs[i].kind == MV_NONE) continue;
    Use u(i);
    Tilter &t = tilters[i];
    if (MVX.st == MS_WAKE) { MVX.noted = t.note(t.angle()); finishMove(MVX, t, why); continue; }
    if (MVX.st != MS_SETTLE || !MVX.why) { MVX.nudges = MAX_NUDGES + 1; toSettle(MVX, t, why); }
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
  bool batteryCritical() override { return battCritical(); }
  bool calibrated(int p) override { return ::calibrated(p); }
  float tilt(int p) override { return bs[p].tilt; }
  const char *now(int p, float t) override { return startTilt(p, t); }
  void gently(int p, float from, float to, uint32_t ms) override { ramp[p] = {true, from, to, millis(), ms, 0}; }
  void stopGentle() override { rampCancel(); }
} espMoves;
MoveResult moveBlinds(const MoveAsk &a) { return moveRequest(a, espMoves); }
void moveStop() { rampCancel(); stopAll("stopped"); }   // the app's or Home's stop: also ends a gentle move

// ---- settings changes: the one way a handler writes cfg. A move steers by its blind's Marks and motor direction, so
// a blind whose Marks or direction change has its move (running, queued or gentle) ended first. Then the new settings
// are kept, its tilt is worked out again from the new Marks, and they are saved. A new time zone is used at once, so
// the running zone is always the saved one and Schedules follow a set, a restore or Reset all with no restart. (A
// running move that learns its motor direction writes that itself: tilter.h.)
bool blindCfgChanged(int p, const BlindCfg &n) { return steeringChanged(marksOf(p), cfg.b[p].motSign, Marks{n.up, n.open, n.down}, n.motSign); }
void cfgApply(const Settings &n) {
  Settings next = n;
  bool hit[PORTS];
  for (int p = 0; p < PORTS; p++) {
    int8_t was = cfg.b[p].motSign;
    hit[p] = blindCfgChanged(p, next.b[p]);
    if (hit[p]) {
      ramp[p].on = false;
      if (bs[p].queued) { bs[p].queued = false; bs[p].target = NAN; }
      if (movingPort(p)) { Use u(p); stopNow(MVX, tilters[p], "stopped: settings changed"); }
    }
    next.b[p].motSign = keptSign(next.b[p].motSign, was, cfg.b[p].motSign);   // what the stopped move learned is kept
  }
  bool zoneChanged = strcmp(cfg.tz, next.tz) != 0;
  cfg = next;
  if (zoneChanged) zoneUse(cfg.tz);              // logic.h
  for (int p = 0; p < PORTS; p++) {
    if (!hit[p]) continue;
    if (bs[p].seen) noteAngle(p, bs[p].ang); else bs[p].tilt = NAN;    // not read yet: it stays "not seen"
    hand.forget(p);
  }
  cfgSave();
}

bool uiActive();                               // app_main.cpp
void motionTick() {
  uint32_t now = millis();
  static uint32_t lastT = 0, lastIdle = 0;
  static int idlePort = 0;
  if (!moving()) {
    for (int i = 0; i < PORTS; i++)
      if (bs[i].queued) { bs[i].queued = false; const char *e = startTilt(i, bs[i].qTilt); if (e) { strlcpy(bs[i].last, e, sizeof bs[i].last); bs[i].target = NAN; } return; }
    HandWatchNow w = hand.tick(now);
    if (w.followFrom >= 0) { watchSync(-1); followHand(w.followFrom, w.followTilt); return; }
    if (w.watchPort >= 0) { watchTick(now, w.watchPort); return; }
    watchSync(-1);
    // Keep the positions fresh: the wand may have been turned by hand. One port at a time. With "blinds follow each
    // other" on and two or more blinds, always (quicker while someone looks); otherwise only while someone looks.
    int n = 0;
    for (int i = 0; i < PORTS; i++) if (movable(i)) n++;
    bool follow = syncMode && n >= 2;
    uint32_t step = follow && uiActive() ? 350 : 1000;
    if (now - lastIdle >= step && (follow || uiActive() || !bs[idlePort].seen)) {
      lastIdle = now;
      pulseRead(idlePort);
      if (follow) hand.reading(idlePort, movable(idlePort) ? bs[idlePort].tilt : NAN, bs[idlePort].ang, bs[idlePort].blind, now);
      idlePort = (idlePort + 1) % PORTS;
    }
    return;
  }
  if (now - lastT < 10) return;                // 100 Hz
  lastT = now;
  for (int i = 0; i < PORTS; i++) if (mvs[i].kind != MV_NONE) { Use u(i); moveTick(mvs[i], tilters[i], now); }
}
// ---- the watch: one blind's sensor kept on and read every 100 ms (setup, a recovery, or a wand being turned)
void watchSync(int p) {                        // the watch's sensor on for blind p only (-1: none)
  if (sensorPort == p) return;
  if (sensorPort >= 0 && !movingPort(sensorPort)) sensorOff(sensorPort);
  sensorPort = -1;
  if (p < 0) return;
  digitalWrite(P_EN[p], HIGH);
  delay(20);
  senseWake(p);
  sensorPort = p;
}
void watchTick(uint32_t now, int p) {          // from motionTick, only while nothing moves
  static uint32_t last = 0;
  watchSync(p);
  if (now - last < 100) return;
  last = now;
  noteAngle(p, readAngle(p));
  hand.reading(p, movable(p) ? bs[p].tilt : NAN, bs[p].ang, bs[p].blind, now);
}
// ---- turned by hand: with "blinds follow each other" on, a blind turned with its wand takes the others along
// (ADR 0004). The idle look-round (motionTick) gives HandWatch each reading; it says when the hand is done.
void followHand(int p, float t) {
  int n = moveBlinds(moveAsk(FROM_HAND, p, t)).started;
  event("%s turned by hand to tilt %.0f: %d other blind%s follow%s", cfg.b[p].name, t, n, n == 1 ? "" : "s", n == 1 ? "s" : "");
}
// ---- marks (setup): take the blind's present position as closed-up / open / closed-down
uint32_t movesEver() { uint32_t n = 0; for (int p = 0; p < PORTS; p++) n += stats.moves[p]; return n; }
// The mark's steady reading (logic.h steadyRead) on blind p. Each read is under the lock; each 50 ms wait lets it go,
// so the blinds task, a Bluetooth hello and the hub task carry on meanwhile. Back under the lock, the reading is cut
// short if a motor ran or the watch left this blind (its sensor may have been switched off).
struct MarkSensor : SteadySensor {
  int p;
  uint32_t moves = movesEver();
  bool motorRan = false;
  explicit MarkSensor(int port) : p(port) {}
  float angle() override { return readAngle(p); }
  bool lost() override { return bs[p].lost; }
  bool wait(uint32_t ms) override {
    { Unlocked u; delay(ms); }
    motorRan = moving() || movesEver() != moves;
    return !motorRan && sensorPort == p && bs[p].present;
  }
};
const char *setMark(int p, const String &w) {
  if (p < 0 || p >= PORTS) return "no such blind";
  if (moving()) return "wait until it stops";
  if (w == "clear") {
    Settings n = cfg;
    BlindCfg &c = n.b[p];
    c.up = c.open = c.down = NAN; cfgApply(n); event("%s: marks cleared", c.name); return nullptr;
  }
  hand.setupOpen(p, millis());                 // keep its sensor on: the steady reading reads it
  watchSync(p);
  if (!bs[p].present) return "no tilter plugged in";
  MarkSensor ms(p);
  SteadyResult sr = steadyRead(ms);
  if (sr.is == STEADY_CUT) return ms.motorRan ? "wait until it stops" : "interrupted: tap again";
  if (sr.is == STEADY_LOST) return "the sensor gave no reading: check the tilter's cable, then tap again";
  if (sr.is == STEADY_MOVING) return "the slats are still moving: let them settle, then tap again";
  float st = sr.ang;
  Settings n = cfg;                            // taken after the reading: what the blinds task saved meanwhile is kept
  BlindCfg &c = n.b[p];
  noteAngle(p, st);
  // Setup starts (closed up is its first mark): the first move after it checks the motor's direction again, so a
  // motor or tilter changed since is learned afresh. The direction is kept as the first guess.
  if (w == "up") { c.up = bs[p].ang; c.motSign = c.motSign < 0 ? -1 : 1; }
  else if (w == "open") c.open = bs[p].ang;
  else if (w == "down") c.down = bs[p].ang;
  else return "unknown mark";
  cfgApply(n);                                 // the tilt is worked out again from the new mark
  hand.marked(p, millis());
  event("%s: marked %s at %.1f deg", c.name, w.c_str(), bs[p].ang);
  return nullptr;
}
