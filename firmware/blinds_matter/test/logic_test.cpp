// Tests for main/logic.h, main/handwatch.h, main/home_view.h, main/request.h, main/tilter.h, main/wire.h and the Tilt
// Hub's alert_rules.h, run on the Mac:
// tools/firmware_tests.sh. No hardware, no ESP-IDF.
#include "../main/logic.h"
#include "../main/home_view.h"
#include "../main/handwatch.h"
#include "../main/request.h"
#include "../main/tilter.h"
#include "../main/wire.h"
#include "../../tilt_hub/main/alert_rules.h"
#include <cstdio>
#include <ctime>
#include <fstream>
#include <map>
#include <vector>
#include <sstream>
#include <string>

static int passed = 0, failed = 0;
#define CHECK(cond, what) do { if (cond) passed++; else { failed++; printf("FAIL line %d: %s\n", __LINE__, what); } } while (0)
static bool near(double a, double b, double tol) { return fabs(a - b) <= tol; }
static std::string readFile(const char *path) {               // the whole file, without its last newline
  std::ifstream f(path);
  std::stringstream ss;
  ss << f.rdbuf();
  std::string s = ss.str();
  while (!s.empty() && (s.back() == '\n' || s.back() == '\r')) s.pop_back();
  return s;
}

// The known controller state behind the shared fixture test/wire/cfg.json (the app's tests decode the same file).
static const WireBlind FIX_B[3] = {{"Mom\xE2\x80\x99s caf\xC3\xA9", 0, 100, 0}, {"Middle", 0, 80, -50}, {"Right", 1, 50, 100}};
static const WireSlot FIX_EMPTY = {0, 127, 0, 480, 0, 0, 0, 0, 0, 0, 0};
static const WireSlot FIX_S[8] = {{1, 62, 7, 420, 0, 0, 0, 0, 1, 0, 0}, FIX_EMPTY, {1, 127, 5, 480, -100, 4, -15, 10, 4000000000u, 1795385700u, 1},
                                  FIX_EMPTY, FIX_EMPTY, FIX_EMPTY, FIX_EMPTY, FIX_EMPTY};
static const WireCfg FIX = {"Den \"East\"", 1, 1, 0, 20, "CST6CDT,M3.2.0,M11.1.0", "America/Chicago", 0, FIX_B, 3, FIX_S, 8,
                            41.88f, -87.63f, 1795351560u, 1795386240u, 1};

// A controller that only writes down what a Move request asked of it.
struct RecMoves : MoveSeam {
  bool fol = false, mov[PORTS] = {true, true, true}, cal[PORTS] = {true, true, true};
  float cur[PORTS] = {0, 0, 0};
  const char *refuse[PORTS] = {nullptr, nullptr, nullptr};
  std::string log;                                    // "n0:50 g1:0>30/60000 x" = now, gently, gentle moves stopped
  bool follow() override { return fol; }
  bool movable(int p) override { return mov[p]; }
  bool calibrated(int p) override { return cal[p]; }
  float tilt(int p) override { return cur[p]; }
  const char *now(int p, float t) override { log += "n" + std::to_string(p) + ":" + std::to_string((int)t) + " "; return refuse[p]; }
  void gently(int p, float from, float to, uint32_t ms) override {
    log += "g" + std::to_string(p) + ":" + std::to_string((int)from) + ">" + std::to_string((int)to) + "/" + std::to_string(ms) + " ";
  }
  void stopGentle() override { log += "x "; }
  bool crit = false;
  bool batteryCritical() override { return crit; }
};
static void requestTests() {
  { RecMoves s; MoveResult r = moveRequest(moveAsk(FROM_APP, 1, 50), s);
    CHECK(s.log == "x n1:50 " && r.started == 1 && !r.why, "app: one blind, gentle moves end"); }
  CHECK(fwIsOlder("2.2.0", "2.3.0-dev7") && !fwIsOlder("2.3.0", "2.3.0-dev7") && fwIsOlder("2.3.0-dev6", "2.3.0-dev7"), "firmware: older and newer");
  CHECK(!fwIsOlder("2.3.0-dev7", "2.3.0-dev7") && fwIsOlder("2.3.0-dev7", "2.3.0") && !fwIsOlder("10.0.0", "9.9.9") && fwIsOlder("junk", "2.3.0"), "firmware: same, release, junk");
  { RecMoves s; s.fol = true; MoveResult r = moveRequest(moveAsk(FROM_APP, 1, 50), s);
    CHECK(s.log == "x n1:50 " && r.started == 1, "app: one blind moves alone, even with follow on"); }
  { RecMoves s; s.mov[0] = false; MoveResult r = moveRequest(moveAsk(FROM_APP, -1, -100), s);
    CHECK(s.log == "x n1:-100 n2:-100 " && r.started == 2, "app: all = every movable blind"); }
  { RecMoves s; s.mov[1] = false; s.refuse[1] = "not set up yet"; MoveResult r = moveRequest(moveAsk(FROM_APP, 1, 50), s);
    CHECK(r.started == 0 && r.why && !strcmp(r.why, "not set up yet"), "app: a named blind's refusal is the answer"); }
  { RecMoves s; s.fol = true; s.refuse[1] = "battery too low"; MoveResult r = moveRequest(moveAsk(FROM_APP, 1, 50), s);
    CHECK(s.log == "x n1:50 " && r.started == 0 && !strcmp(r.why, "battery too low"), "app: named refused, nobody follows"); }
  { RecMoves s; s.refuse[0] = s.refuse[1] = s.refuse[2] = "battery too low"; MoveResult r = moveRequest(moveAsk(FROM_APP, -1, 0), s);
    CHECK(r.started == 0 && !strcmp(r.why, "battery too low"), "app: all refused gives the reason"); }
  { RecMoves s; s.mov[0] = s.mov[1] = s.mov[2] = false; MoveResult r = moveRequest(moveAsk(FROM_APP, -1, 0), s);
    CHECK(r.started == 0 && !strcmp(r.why, "no blind is set up"), "app: nothing movable"); }
  { RecMoves s; MoveResult r = moveRequest(moveAsk(FROM_APP, 0, NAN), s);
    CHECK(s.log == "x " && r.started == 0 && !strcmp(r.why, "unknown position"), "app: unknown word refused"); }
  { RecMoves s; s.cur[2] = NAN; MoveResult r = moveRequest(moveAsk(FROM_APP, -1, 80, 600000), s);
    CHECK(s.log == "x g0:0>80/600000 g1:0>80/600000 n2:80 " && r.started == 3, "app: gently, straight there when the tilt is not known"); }
  { RecMoves s; s.crit = true; MoveResult r = moveRequest(moveAsk(FROM_SCHEDULE, -1, 30, 0, 0x07), s);
    CHECK(r.started == 0 && r.why && strstr(r.why, "Schedules paused") && s.log.empty(), "Critical battery pauses Schedules"); }
  { RecMoves s; s.crit = true; MoveResult r = moveRequest(moveAsk(FROM_APP, 0, 30), s);
    CHECK(r.started == 1, "Critical battery: a move from the app still goes"); }
  { RecMoves s; s.crit = true; MoveResult r = moveRequest(moveAsk(FROM_HOME, -1, 30), s);
    CHECK(r.started == 3, "Critical battery: a move from Home still goes"); }
  { RecMoves s; s.fol = true; s.mov[2] = false; MoveResult r = moveRequest(moveAsk(FROM_SCHEDULE, -1, 30, 0, 0x06), s);
    CHECK(s.log == "n1:30 " && r.started == 1, "schedule: its blinds that can move, no follow, gentle moves kept"); }
  { RecMoves s; moveRequest(moveAsk(FROM_SCHEDULE, -1, 30, 120000, 0x01), s);
    CHECK(s.log == "g0:0>30/120000 ", "schedule: gently"); }
  { RecMoves s; MoveResult r = moveRequest(moveAsk(FROM_HOME, 2, -40), s);
    CHECK(s.log == "x n2:-40 " && r.started == 1, "Home: its covering's blind"); }
  { RecMoves s; s.fol = true; moveRequest(moveAsk(FROM_HOME, 2, -40), s);
    CHECK(s.log == "x n2:-40 ", "Home: its own blind moves alone, even with follow on"); }
  { RecMoves s; moveRequest(moveAsk(FROM_HOME, -1, 10), s);
    CHECK(s.log == "x n0:10 n1:10 n2:10 ", "Home: one covering for all"); }
  { RecMoves s; MoveResult r = moveRequest(moveAsk(FROM_HAND, 1, 50), s);
    CHECK(s.log.empty() && r.started == 0, "hand, follow off: nobody follows"); }
  { RecMoves s; s.fol = true; s.cur[0] = 48; s.cur[2] = NAN; MoveResult r = moveRequest(moveAsk(FROM_HAND, 1, 50), s);
    CHECK(s.log == "n2:50 " && r.started == 1, "hand: the others follow, unless already there; gentle moves kept"); }
}

// A simulated Tilter: a rod turned through gear play, an Angle that reads 3 degrees high while the motor runs, hard
// stops, a PWM sensor's blind spot near its zero, and a hand that can turn the wand.
struct SimTilter : Tilter {
  uint32_t t = 0;
  float rod = 290, gear = 290;  // the rod's true angle; where the motor side of the gear play is
  float play = 5;               // gear play, degrees of rod turn
  float degPerS = 2.5f;         // at full duty
  int phys = 1;                 // +1: motor "forward" makes the angle rise
  float lo = -1e9f, hi = 1e9f;  // hard stops (unwrapped degrees)
  float blindLo = -1, blindHi = -1;  // the sensor sees nothing while the rod is past blindLo or before blindHi (reads 0); -1 = never
  uint32_t wandAt = 0; float wandBy = 0;   // a hand turns the wand this much at this time
  uint32_t handAt = 0, handMs = 0; float handRate = 0;   // a hand turning the wand steadily (deg/s) for a while
  uint32_t glitchAt = 0, glitchMs = 0; float glitchBy = 0;   // the reading is off by this much for a while
  int spikeEvery = 0; float spikeBy = 0; int reads = 0;      // every Nth reading is off by this much (brush noise)
  bool firstZero = false;       // the first reading after the sensor wakes is 0 (Left, 2026-11-23)
  bool strainZeros = false;     // straining against an end stop, the PWM sensor reads 0 in bursts (Left, 2026-11-23)
  uint32_t motorAfterHand = 0;  // ms the motor ran once the hand started
  uint32_t dropAt = 0, dropMs = 0;   // the sensor gives nothing for a while (a dropout: Dining, 2026-11-25)
  ReadingJudge judge;           // the controller's own rule (logic.h) for what a reading at a rail is
  float rodMin = 1e9f, rodMax = -1e9f;   // how far the rod went, either way
  int dir = 0, duty = 0;
  int8_t sign = 1;
  TiltMemory mem;
  TiltSettings set{Marks{200, 290, 40}, 100, 12000, 2500, 180000, 1.0f};
  int keeps = 0;
  std::string log, endMsg;
  Move last;
  void step(uint32_t dt) {
    t += dt;
    if (wandAt && t >= wandAt) { rod += wandBy; gear += wandBy; wandAt = 0; }
    if (handMs && t >= handAt && t < handAt + handMs) { rod += handRate * dt / 1000.0f; gear += handRate * dt / 1000.0f; }
    if (handMs && t >= handAt && dir) motorAfterHand += dt;
    gear += phys * dir * degPerS * duty / 100.0f * dt / 1000.0f;
    if (gear > rod + play / 2) rod = gear - play / 2;
    if (gear < rod - play / 2) rod = gear + play / 2;
    if (rod > hi) rod = hi;
    if (rod < lo) rod = lo;
    gear = std::min(std::max(gear, rod - play / 2), rod + play / 2);
    rodMin = std::min(rodMin, rod); rodMax = std::max(rodMax, rod);
  }
  float wrapped() { return fmodf(fmodf(rod, 360.0f) + 360.0f, 360.0f); }
  bool inBlind() { float a = wrapped(); return blindLo >= 0 && (a >= blindLo || a <= blindHi); }
  uint32_t ms() override { return t; }
  bool wake() override { return true; }
  bool dropping() { return dropMs && t >= dropAt && t - dropAt < dropMs; }
  float angle() override { return dropping() ? judge.judge(0, true).ang : judge.judge(fresh(), false).ang; }
  float fresh() {
    if (firstZero) { firstZero = false; return 0; }
    float g = dir && glitchMs && t >= glitchAt && t < glitchAt + glitchMs ? glitchBy : 0;   // motor noise: only while it runs
    if (spikeEvery && ++reads % spikeEvery == 0) g += spikeBy;
    if (strainZeros && dir && (rod <= lo + 0.5f || rod >= hi - 0.5f) && ++reads % 60 < 15) return 0;
    return inBlind() ? 0 : fmodf(wrapped() + (dir ? 3.0f : 0) + g + 360.0f, 360.0f);
  }
  bool noReading() override { return inBlind() || dropping(); }
  bool lost() override { return dropping() && judge.lost; }
  float note(float a) override { return a; }
  void motor(int d, int pct) override { dir = d; duty = pct; }
  TiltSettings settings() override { return set; }
  int8_t &motSign() override { return sign; }
  TiltMemory &memory() override { return mem; }
  void keep() override { keeps++; }
  void say(const char *msg) override { log += msg; log += "; "; }
  void ended(const Move &m, const char *msg) override { last = m; endMsg = msg; }
  // Run a move to a tilt until it ends (100 ticks a second, as motionTick does). Returns the tilt it ended at.
  float go(float tilt, uint32_t limitMs = 300000) {
    Move m;
    moveFresh(m, MV_TILT, 0, t);
    m.tgt = tilt;
    while (m.kind != MV_NONE && t < limitMs) { step(10); moveTick(m, *this, t); }
    return tiltOfMarks(set.marks, wrapped());
  }
};
static void sensorTests() {
  CHECK(near(as5600Share(128 + 2048 * 4351 / 4351, 4351), 2048.0f / 4095.0f, 0.001f), "a good frame reads its angle");
  CHECK(as5600Share(128, 4351) == 0.0f, "a frame at the sensor's zero reads 0");
  CHECK(as5600Share(20, 4351) < 0, "a frame shorter than the lead-in is noise, not 0");
  CHECK(as5600Share(4351, 4351) < 0, "a frame high the whole time is noise, not a full turn");
  CHECK(as5600Share(500, 0) < 0, "no frame yet: no reading");
  CHECK(pwmBlindSpot(3.0f / 360) && pwmBlindSpot(358.0f / 360), "no pulses just above or below zero: the blind spot");
  CHECK(!pwmBlindSpot(252.0f / 360), "no pulses at 252 degrees: noise, not the blind spot");
}
// A sensor dropout (issue #135): the AS5600 sometimes gives nothing (PWM: no pulses, analog: 0 V) far from its zero.
// It is no reading: never the angle, never a stop "near the target", never a turn by hand, and tilt stays in -100..100.
static void dropoutTests() {
  { SensorRead r = judgeReading(83.4f, false, 80); CHECK(r.ang == 83.4f && !r.guess && !r.lost, "a fresh reading is the angle"); }
  { SensorRead r = judgeReading(0, true, 83.4f); CHECK(r.lost && r.guess && r.ang == 83.4f, "no pulses at 83 degrees: a dropout, the last angle kept"); }
  { SensorRead r = judgeReading(0, true, 285.9f); CHECK(r.lost && r.ang == 285.9f, "analog at 0 V, last at 286 degrees: a dropout"); }
  { SensorRead r = judgeReading(0, true, 3); CHECK(!r.lost && r.guess && r.ang == 3, "no pulses, last near zero: its zero, not a dropout"); }
  { SensorRead r = judgeReading(0, true, 358); CHECK(!r.lost && r.guess, "no pulses, last just below a full turn: its zero"); }
  { SensorRead r = judgeReading(0, true, NAN); CHECK(r.lost && r.guess && r.ang == 0, "no pulses, nothing known yet (a restart): no reading"); }
  // Analog, read while the motor turns it: a dropout keeps the last fresh angle, not where the move started (Right).
  { ReadingJudge j;
    j.judge(200, false); j.judge(215, false); j.judge(231.5f, false);
    SensorRead r = j.judge(0, true);
    CHECK(r.lost && j.lost && r.ang == 231.5f, "a dropout mid-move: the angle kept is the last fresh one");
    r = j.judge(233, false);
    CHECK(!r.lost && !j.lost && r.ang == 233, "readings back: fresh again");
    j.forget();
    CHECK(j.judge(0, true).lost, "unplugged and back: nothing known, so no reading at the rail"); }
  // Middle's samples at rest, one a second (83.4, then 0.0 with no pulses ten times), and Right's (analog 285.9, then
  // 0 V), read the way the idle look-round reads them, with Follow on. 0 degrees is far past Middle's closed-up mark.
  { Marks mid{60, 100, 160}, right{250, 286, 330};
    CHECK(tiltOfMarks(mid, 0) > 200, "(the dropout as an angle would be a tilt far over 100)");
    HandWatch h;
    float last[2] = {NAN, NAN}, noted[2] = {NAN, NAN};
    bool watched = false, followed = false, inRange = true;
    uint32_t now = 1000;
    auto look = [&](int p, const Marks &k, float raw, bool rail) {
      SensorRead r = judgeReading(raw, rail, last[p]);
      last[p] = r.ang;                                         // noteAngle keeps what readAngle gave
      noted[p] = tiltOfMarks(k, r.ang);
      h.reading(p, noted[p], r.ang, r.guess, now);
      HandWatchNow w = h.tick(now);
      watched |= w.watchPort >= 0; followed |= w.followFrom >= 0;
      float c = currentTiltOf(k, false, NAN, noted[p]);
      inRange &= c >= -100 && c <= 100;
      now += 500;
    };
    for (int i = 0; i < 3; i++) { look(0, mid, 83.4f, false); look(1, right, 285.9f, false); }
    for (int i = 0; i < 10; i++) { look(0, mid, 0, true); look(1, right, 0, true); }
    for (int i = 0; i < 3; i++) { look(0, mid, 83.4f, false); look(1, right, 285.9f, false); }
    CHECK(!watched && !followed, "dropouts at rest: no turn by hand, nothing follows");
    CHECK(inRange && near(noted[0], 41.5f, 0.1f), "dropouts at rest: the tilt stays where it was, inside -100..100"); }
  // Past a closed mark (the rod carries on, or a bad reading): still told as closed, never over 100.
  { Marks k{200, 290, 40};
    CHECK(currentTiltOf(k, false, NAN, 112.6f) == 100 && currentTiltOf(k, false, NAN, -130) == -100, "Current tilt: never outside -100..100 at rest");
    CHECK(currentTiltOf(k, true, 180, 0) == 100, "Current tilt: never outside -100..100 while moving"); }
  // Moves.
  { SimTilter s; s.dropMs = 1000000000;                       // dead from the start, nothing known (a restart)
    s.go(50);
    CHECK(s.endMsg == "stopped: no reading from the sensor" && s.last.runMs == 0 && s.rodMax == 290, "no reading at all: the motor never starts"); }
  { SimTilter s; s.go(50); s.dropAt = s.t; s.dropMs = 1000000000;   // known, then dead before the next move
    s.go(-50);
    CHECK(s.endMsg == "stopped: no reading from the sensor" && s.last.runMs == 0, "dead after a good move: the next move never starts"); }
  { SimTilter s; s.dropMs = 1000000000;                       // Setup's jog still turns a blind with no reading
    Move m; moveFresh(m, MV_JOG, 0, s.t); m.jogDir = 1; m.pct = 100; m.deadline = s.t + 1500;
    while (m.kind != MV_NONE && s.t < 10000) { s.step(10); moveTick(m, s, s.t); }
    CHECK(s.endMsg == "jog" && s.last.runMs > 1000, "no reading: a jog still runs (hold-to-run), and ends on time"); }
  { SimTilter s; s.dropMs = 1000000000;                       // but a seek, which ends at a stall, does not
    Move m; moveFresh(m, MV_JOG, 0, s.t); m.jogDir = 1; m.pct = 100; m.seek = true; m.deadline = s.t + 30000;
    while (m.kind != MV_NONE && s.t < 40000) { s.step(10); moveTick(m, s, s.t); }
    CHECK(s.endMsg == "stopped: no reading from the sensor" && s.last.runMs == 0, "no reading: a seek never starts"); }
  { SimTilter s; s.dropMs = 150; float t = s.go(50);          // slow to start
    CHECK(s.endMsg == "reached" && near(t, 50, 5), "a sensor slow to wake: the move waits for it and reaches the Target"); }
  { SimTilter s; s.degPerS = 15; s.dropAt = 1500; s.dropMs = 1000000000;   // gone mid-move
    Move m; moveFresh(m, MV_TILT, 0, s.t); m.tgt = -100;
    uint32_t off = 0;
    while (m.kind != MV_NONE && s.t < 60000) { s.step(10); moveTick(m, s, s.t); if (s.dir && s.t >= s.dropAt) off = s.t; }
    CHECK(s.endMsg == "stopped: no reading from the sensor", "a dropout mid-move: it stops and says why");
    CHECK(off < s.dropAt + LOST_STOP_MS + 50, "a dropout mid-move: the motor stops within about a second");
    CHECK(s.log.find("wrong way") == std::string::npos && s.sign > 0, "a dropout mid-move: not taken for going the wrong way"); }
  { SimTilter s; s.dropAt = 4000; s.dropMs = 400; float t = s.go(50);   // a short dropout mid-move
    CHECK(s.endMsg == "reached" && near(t, 50, 5), "a short dropout mid-move: it carries on and reaches the Target"); }
  { SimTilter s; s.degPerS = 15; s.go(50); uint32_t at = s.t;           // a dropout while it settles at the Target
    s.dropAt = at + 2000; s.dropMs = 600; float t = s.go(50);
    CHECK(s.endMsg == "already there" && near(t, 50, 5), "a dropout after a move: the next move to the same tilt does nothing"); }
}
static void tilterTests() {
  { SimTilter s; float t = s.go(50);
    CHECK(s.endMsg == "reached" && near(t, 50, 5), "reaches a Target through gear play and the high reading"); }
  { SimTilter s; s.go(50); float before = s.mem.lead[0];
    SimTilter s2; s2.mem.lead[0] = -1; s2.go(50);
    CHECK(s2.mem.lead[0] > -1 && near(before, 2.5f, 1.5f), "lead is learned toward what the rod really does"); }
  { SimTilter s; s.set.leadMax = 1.0f; s.mem.lead[0] = 6; s.mem.lead[1] = -6;
    for (int i = 0; i < 3; i++) { s.go(50); s.go(-50); }
    CHECK(fabsf(s.mem.lead[0]) <= 1.0f && fabsf(s.mem.lead[1]) <= 1.0f, "the learned lead stays inside the lead limit setting"); }
  { SimTilter s; s.lo = 270; s.go(50);
    CHECK(s.endMsg == "blocked (stalled)" && s.last.stalled, "a stall short of the Target reports blocked"); }
  { SimTilter s; s.lo = 206; s.go(100);
    CHECK(s.endMsg == "reached (end stop)", "a stall near a closed mark counts as reached"); }
  { SimTilter s; s.mem.lead[0] = -1; s.go(50);                    // stops about 3 degrees late
    float over = fabsf(angDiff(s.wrapped(), 245));
    CHECK(s.endMsg == "reached" && s.last.turnBacks == 0 && over > TOL_DEG && over <= OVER_OK_DEG, "overshoot under the limit is left alone"); }
  { SimTilter s; s.mem.lead[0] = -6; s.go(50);                    // stops about 8 degrees late
    CHECK(s.endMsg == "reached" && s.last.turnBacks >= 1, "overshoot past the limit turns back"); }
  { SimTilter s; s.phys = -1; s.hi = 320; float t = s.go(50);     // wired the other way round
    CHECK(s.log.find("going the wrong way") != std::string::npos, "wrong way: tries the other direction");
    CHECK(s.endMsg == "reached" && near(t, 50, 5) && s.sign == -2 && s.keeps == 1, "direction learned and kept"); }
  { SimTilter s; s.sign = 2; s.phys = -1; s.hi = 320; float t = s.go(50);   // learned, then the motor wires were swapped
    CHECK(s.endMsg == "reached" && near(t, 50, 5) && s.sign == -2 && s.keeps == 1, "swapped wires: a learned direction is corrected and kept"); }
  { SimTilter s; s.sign = 2; s.phys = -1; s.go(50);               // swapped, no end stop in the way: caught while running
    CHECK(s.endMsg == "reached" && s.sign == -2, "swapped wires: caught while running, before any end stop"); }
  { SimTilter s; s.set.marks = Marks{15.4f, 138.2f, 247.7f}; s.set.graceMs = 8000;   // Middle, 2026-11-23: wires
    s.rod = s.gear = 251.6f; s.hi = 252; s.sign = 2; s.phys = -1;                   // swapped, resting on its down stop
    float t = s.go(0);
    CHECK(s.endMsg == "reached" && near(t, 0, 5) && s.sign == -2, "swapped wires, starting on the end stop: turns round and reaches Open");
    if (s.endMsg != "reached") printf("    ended \"%s\" at tilt %.1f, log: %s\n", s.endMsg.c_str(), t, s.log.c_str()); }
  { SimTilter s; s.sign = 2; s.lo = 270; s.go(50);                // right direction, but something blocks the blind
    CHECK(s.endMsg == "blocked (stalled)" && s.sign == 2 && s.keeps == 0, "blocked: the learned direction stays"); }
  { SimTilter s; s.wandAt = 6000; s.wandBy = 6; float t = s.go(50);
    CHECK(s.endMsg == "reached" && near(t, 50, 5), "a small bump on the wand during the move: still reaches"); }
  // A hand on the wand wins: the motor stops and the learned direction stays (2026-11-23: Left flipped its direction
  // when the wand was turned during a follow, then drove to closed up).
  { SimTilter s; s.degPerS = 15; s.sign = 2; s.handAt = 2000; s.handMs = 3000; s.handRate = 25; s.go(50);
    CHECK(s.endMsg == "stopped: turned by hand" && s.sign == 2 && s.keeps == 0, "hand against the motor: it stops, direction kept");
    CHECK(s.motorAfterHand < 2000, "slow hand against the motor: the motor stops within 2 s");
    if (s.motorAfterHand >= 2000 || s.endMsg != "stopped: turned by hand") printf("    ended \"%s\", motor ran %u ms after the hand, sign %d, log: %s\n", s.endMsg.c_str(), s.motorAfterHand, s.sign, s.log.c_str()); }
  { SimTilter s; s.degPerS = 15; s.sign = 2; s.handAt = 2000; s.handMs = 1500; s.handRate = 60; s.go(50);
    CHECK(s.endMsg == "stopped: turned by hand" && s.motorAfterHand < 1000, "a quick wand turn against the motor: stops within 1 s");
    if (s.motorAfterHand >= 1000) printf("    motor ran %u ms after the hand\n", s.motorAfterHand); }
  { SimTilter s; s.degPerS = 15; s.sign = 2; s.handAt = 1000; s.handMs = 4000; s.handRate = -40; s.go(50);   // the same way as the motor, and on past the target
    CHECK(s.motorAfterHand < 2500 && s.sign == 2, "a hand turning the same way and on past the target: the motor does not fight it for long");
    if (s.motorAfterHand >= 2500) printf("    ended \"%s\", motor ran %u ms after the hand\n", s.endMsg.c_str(), s.motorAfterHand); }
  { SimTilter s; s.degPerS = 15; s.sign = 2; s.mem.lastRaw = 1; s.handAt = 300; s.handMs = 3000; s.handRate = 25; s.go(50);
    CHECK(s.endMsg == "stopped: turned by hand" && s.sign == 2 && s.motorAfterHand < 1500, "hand at the start, while the gear play is taken up: it stops too"); }
  { SimTilter s; s.degPerS = 15; s.sign = 1; s.handAt = 2000; s.handMs = 3000; s.handRate = 25; s.go(50);
    CHECK(s.endMsg == "stopped: turned by hand" && s.sign > 0, "hand against a direction not yet learned: stops, does not flip it"); }
  // A bad reading that makes it look like the wrong way, near the end: the direction must not be "learned" backwards.
  { SimTilter s; s.degPerS = 15; s.sign = 1; s.glitchAt = 4500; s.glitchMs = 600; s.glitchBy = 30; s.go(50);
    CHECK(s.sign > 0, "a bad reading: the right direction is not turned round and kept");
    if (s.sign <= 0) printf("    ended \"%s\", sign %d, log: %s\n", s.endMsg.c_str(), s.sign, s.log.c_str()); }
  // Middle, 2026-11-23: a burst of bad readings toward the target (short of it), then true again. Not "the wrong way".
  { SimTilter s; s.degPerS = 15; s.sign = 2; s.glitchAt = 1500; s.glitchMs = 120; s.glitchBy = 35; float t = s.go(-60);
    CHECK(s.endMsg == "reached" && near(t, -60, 5) && s.sign == 2 && s.log.empty(), "a burst of readings toward the target: carries on, no turning round");
    if (s.endMsg != "reached" || !s.log.empty()) printf("    ended \"%s\" at tilt %.1f, log: %s\n", s.endMsg.c_str(), t, s.log.c_str()); }
  { SimTilter s; s.degPerS = 15; s.sign = 2; s.spikeEvery = 7; s.spikeBy = 25; float t = s.go(50);
    CHECK(s.endMsg == "reached" && near(t, 50, 5) && s.sign == 2, "single bad readings, moving and stopped: not a hand, still reaches");
    if (s.endMsg != "reached") printf("    ended \"%s\" at tilt %.1f, log: %s\n", s.endMsg.c_str(), t, s.log.c_str()); }
  { SimTilter s; s.degPerS = 15; s.sign = 2; s.hi = 400 - 4; s.strainZeros = true;
    s.go(-100);                                                 // closed down at 40 (400 unwrapped), the stop 4 degrees short of it
    CHECK(s.endMsg == "reached (end stop)", "closed down against the stop, readings of 0 while it strains: reached");
    if (s.endMsg != "reached (end stop)") printf("    ended \"%s\", log: %s\n", s.endMsg.c_str(), s.log.c_str()); }
  // Left, 2026-11-23: from closed up (against its stop) to Open, across the sensor's zero. Its first reading after
  // waking was 0, and pulling off the stop it reads 0 in bursts. It must go straight to Open, not first push further into closed up.
  { SimTilter s; s.degPerS = 15; s.sign = 2; s.set.marks = Marks{295.7f, 35.4f, 146.3f}; s.set.graceMs = 8000;
    s.rod = s.gear = 296.4f; s.lo = 295.5f; s.mem.lastRaw = -1; s.strainZeros = true; s.blindLo = 357; s.blindHi = 3; s.firstZero = true;
    float t = s.go(0);
    CHECK(s.endMsg == "reached" && near(t, 0, 5) && s.sign == 2 && s.log.empty(), "closed up to Open with bad readings at the stop: straight there");
    if (s.endMsg != "reached" || !s.log.empty()) printf("    ended \"%s\" at tilt %.1f, log: %s\n", s.endMsg.c_str(), t, s.log.c_str()); }
  // Setup's first move (2026-11-23, Right): wires the other way round, at closed down, going to Open. It may turn past
  // closed down first, but only a little before it turns round, not for seconds.
  { SimTilter s; s.degPerS = 15; s.play = 20; s.set.graceMs = 8000; s.set.marks = Marks{161.3f, 270.0f, 10.6f};
    s.rod = s.gear = 10.6f + 360; s.sign = 1; s.phys = -1;
    float t = s.go(0);
    float past = s.rodMax - (10.6f + 360);                       // degrees beyond closed down (the angle rising)
    CHECK(s.endMsg == "reached" && near(t, 0, 5) && s.sign == -2, "setup, wires the other way: reaches Open, direction learned");
    CHECK(past < 20, "setup, wires the other way: only a little past closed down before turning round");
    if (past >= 20 || s.endMsg != "reached") printf("    ended \"%s\" at tilt %.1f, %.1f deg past closed down, log: %s\n", s.endMsg.c_str(), t, past, s.log.c_str()); }
  { SimTilter s; s.set.marks = Marks{300, 10, 100}; s.rod = s.gear = 50; s.blindLo = 351; s.blindHi = 4;
    float t = s.go(100);                                         // passes the PWM sensor's zero on the way
    CHECK(s.endMsg == "reached" && !s.last.stalled && near(t, 100, 5), "no reading at the sensor's zero is not a stall"); }
  { SimTilter s; s.rod = s.gear = 244; s.go(50);
    CHECK(s.endMsg == "already there" && s.dir == 0, "already there: the motor never runs"); }
}

// Follow and the watch (handwatch.h), driven the way motionTick drives it: with no watch, an idle look at one blind
// every 350 ms; with a watch, its blind read every 100 ms. tilt[] is where each blind really is (a hand moves it).
struct WandSim {
  HandWatch h;
  float tilt[PORTS] = {0, 0, 0};
  bool blindSpot = false;                             // the watched blind's sensor gives no reading
  uint32_t now = 1000, lastIdle = 0, lastRead = 0;
  int idle = 0, follows = 0, from = -1;
  float to = NAN;
  float ang(int p) { return 290 - tilt[p] * 0.9f; }
  void step() {                                       // 10 ms
    now += 10;
    HandWatchNow w = h.tick(now);
    if (w.followFrom >= 0) { follows++; from = w.followFrom; to = w.followTilt; return; }
    if (w.watchPort >= 0) {
      if (now - lastRead >= 100) { lastRead = now; int p = w.watchPort; h.reading(p, tilt[p], ang(p), blindSpot, now); }
      return;
    }
    if (now - lastIdle >= 350) { lastIdle = now; h.reading(idle, tilt[idle], ang(idle), false, now); idle = (idle + 1) % PORTS; }
  }
  void run(uint32_t ms) { for (uint32_t e = 0; e < ms; e += 10) step(); }
  void turn(int p, float by, uint32_t ms) {           // a hand turns blind p's wand steadily
    int n = ms / 10;
    for (int i = 0; i < n; i++) { tilt[p] += by / n; step(); }
  }
};
static void handWatchTests() {
  { WandSim s; s.run(2000);                            // every blind looked at: where the controller left them
    s.turn(0, 40, 2000);
    s.run(1400);
    CHECK(s.follows == 0, "follow: not while the hand may still be at work");
    s.run(3000);
    CHECK(s.follows == 1 && s.from == 0 && near(s.to, 40, 1), "follow: a wand turn makes the others follow");
    s.run(10000);
    CHECK(s.follows == 1, "follow: exactly once"); }
  { WandSim s; s.run(2000);
    s.turn(1, 20, 1000);
    s.run(1200);                                       // a pause under 1.5 s
    CHECK(s.follows == 0, "follow: a pause under 1.5 s does not start the others early");
    s.turn(1, 30, 1000);
    s.run(3000);
    CHECK(s.follows == 1 && s.from == 1 && near(s.to, 50, 1), "follow: after the pause, the whole turn is followed"); }
  { WandSim s; s.run(2000);
    s.turn(0, 4, 1000); s.run(5000);
    CHECK(s.follows == 0 && s.h.tick(s.now).watchPort < 0, "follow: a small bump is not a turn"); }
  { WandSim s; s.run(2000);
    s.turn(0, 40, 1000);                               // a hand watch is under way
    s.h.setupOpen(2, s.now);                           // and a setup screen opens
    s.run(3000);
    CHECK(s.follows == 0, "follow: an open Setup screen stops it");
    for (int k = 0; k < 5; k++) { s.h.setupOpen(2, s.now); s.turn(1, -10, 1000); }   // turning wands while Setup is open
    s.run(20000);
    CHECK(s.follows == 0, "follow: wands turned while Setup is open are not followed, then or later"); }
  { WandSim s; s.run(2000);
    s.turn(0, 40, 500);
    s.blindSpot = true;                                // stuck at the sensor's zero: no reading at all
    s.run(65000);
    CHECK(s.follows == 0 && s.h.tick(s.now).watchPort < 0, "follow: the watch gives up after 60 s, nothing followed"); }
  { WandSim s; s.run(2000);
    for (int i = 0; i < 70; i++) s.turn(0, i % 2 ? 3 : -3, 1000);   // a hand that never holds still
    s.run(5000);
    CHECK(s.follows == 0, "follow: a turn that lasts over 60 s is not followed"); }
  { WandSim s; s.run(2000);
    s.tilt[0] = 50;                                    // moved while Follow was off (no readings went to it)
    s.h.reset();                                       // Follow turned on
    s.run(5000);
    CHECK(s.follows == 0, "follow: turning it on starts fresh, old turns are not followed"); }
  { WandSim s; s.run(2000);                            // a recovery: the blind is turned to its ends by hand
    for (int k = 0; k < 6; k++) { s.h.setupOpen(0, s.now); s.turn(0, k % 2 ? -60 : 60, 1000); }
    s.run(25000);
    CHECK(s.follows == 0, "follow: recovery turns are not followed"); }
  { WandSim s; s.run(2000);
    s.h.motorStarted(); s.tilt[2] = -70; s.h.motorLeft(2, -70);   // a motor moved it
    s.run(5000);
    CHECK(s.follows == 0, "follow: a blind moved by its motor is not followed"); }
  { WandSim s; s.run(2000);
    s.turn(0, 40, 1000);
    s.h.motorStarted();                                // the app moves this blind while its wand is being turned
    CHECK(s.h.tick(s.now).watchPort < 0, "follow: a motor starting ends the watch");
    s.tilt[0] = 10; s.h.motorLeft(0, 10);              // and leaves it at 10
    s.run(5000);
    CHECK(s.follows == 0, "follow: the turn before the motor moved it is not followed"); }
  { HandWatch h; h.reading(0, NAN, 100, false, 100); h.reading(0, NAN, 200, false, 500);
    CHECK(h.tick(600).watchPort < 0 && std::isnan(h.ref[0]), "follow: a blind that cannot move is never watched"); }
}

// Settings that change under a running move (motion.h cfgApply), and the one Current tilt everyone is told.
static void settingsChangeTests() {
  Marks k{200, 290, 40}, none{NAN, NAN, NAN};
  CHECK(!steeringChanged(k, 1, k, 1) && !steeringChanged(none, 1, none, 1), "steering: the same Marks (unmarked too) are no change");
  CHECK(!steeringChanged(k, 1, k, 2) && !steeringChanged(k, -2, k, -1), "steering: the motor direction learned or forgotten is no change");
  CHECK(steeringChanged(k, 1, none, 1) && steeringChanged(k, 1, Marks{200, 291, 40}, 1), "steering: Marks cleared or moved");
  CHECK(steeringChanged(k, 2, k, -1), "steering: the motor direction turned round");
  CHECK(keptSign(-1, 2, 2) == -1 && keptSign(1, 2, 2) == 1, "settings change: a motor direction that was set wins");
  CHECK(keptSign(1, 1, 2) == 2 && keptSign(-1, -1, 1) == 1, "settings change: else what the stopped move learned or put back stays");
  // Current tilt always wins (CONTEXT.md): what the sensor reads, not the Target.
  CHECK(near(currentTiltOf(k, false, NAN, 40), 40, 0.01), "Current tilt: at rest, the last true reading (not the Target)");
  CHECK(near(currentTiltOf(k, true, 245, 0), 50, 0.01), "Current tilt: while moving, the live reading");
  CHECK(near(currentTiltOf(k, true, NAN, 12), 12, 0.01), "Current tilt: moving, no live reading yet: the last true one");
  CHECK(std::isnan(currentTiltOf(none, true, 245, 30)) && std::isnan(currentTiltOf(none, false, NAN, 30)), "Current tilt: not set up is unknown, moving or not");
  // Marks cleared mid-move: the move ends at once and cleanly, not at a stall or the time limit.
  { SimTilter s; s.degPerS = 15;
    Move m; moveFresh(m, MV_TILT, 0, s.t); m.tgt = -100;
    while (m.kind != MV_NONE && s.t < 1500) { s.step(10); moveTick(m, s, s.t); }
    bool wasRunning = m.kind != MV_NONE && s.dir != 0;
    s.set.marks = none; uint32_t at = s.t;
    while (m.kind != MV_NONE && s.t < at + 30000) { s.step(10); moveTick(m, s, s.t); }
    CHECK(wasRunning && m.kind == MV_NONE && s.endMsg == "stopped: Setup changed" && s.dir == 0, "Marks cleared mid-move: the move ends, motor off");
    CHECK(s.t - at < 1000 && s.sign == 1 && s.keeps == 0, "Marks cleared mid-move: within a second, nothing learned from it"); }
  { SimTilter s; s.degPerS = 15; s.sign = 1;               // the gate stops it before the settings change under it
    Move m; moveFresh(m, MV_TILT, 0, s.t); m.tgt = -100;     // open (290) toward closed down (40): 110 degrees away
    while (m.kind != MV_NONE && s.t < 4000) { s.step(10); moveTick(m, s, s.t); }
    float gone = fabsf(angDiff(s.wrapped(), 290));
    bool running = m.kind != MV_NONE && s.dir != 0;
    stopNow(m, s, "stopped: settings changed");
    CHECK(running && gone > 20 && m.kind == MV_NONE && s.dir == 0 && s.endMsg == "stopped: settings changed", "settings change: the move is ended at once, motor off");
    CHECK(s.sign == 2 && s.keeps == 1, "settings change: a move that got clearly closer keeps its direction as learned"); }
  { SimTilter s; s.degPerS = 15; s.sign = 1;
    Move m; moveFresh(m, MV_TILT, 0, s.t); m.tgt = -100;
    while (m.kind != MV_NONE && s.t < 300) { s.step(10); moveTick(m, s, s.t); }   // barely started: not closer yet
    stopNow(m, s, "stopped: settings changed");
    CHECK(m.kind == MV_NONE && s.sign == 1 && s.keeps == 0, "settings change: a move stopped before it got closer learns nothing"); }
  { SimTilter s; Move m; moveFresh(m, MV_TILT, 0, s.t); m.tgt = 50;   // still waking its sensor
    stopNow(m, s, "stopped: settings changed");
    CHECK(m.kind == MV_NONE && s.dir == 0 && s.endMsg == "stopped: settings changed", "settings change while waking: ended, nothing read"); }
}

// A sensor for a mark's steady reading: plays back a list of readings (and which were dropouts), writes down each
// wait, and stops the reading at one wait when asked to.
struct PlaySteady : SteadySensor {
  std::vector<float> ang;
  std::vector<bool> drop;
  std::vector<uint32_t> waits;
  int reads = 0, stopAt = 0;                                // stopAt: the wait (1, 2, ...) that says stop; 0 = none
  bool last = false;
  float angle() override { int k = reads++; last = k < (int)drop.size() && drop[k]; return ang[k % ang.size()]; }
  bool lost() override { return last; }
  bool wait(uint32_t ms) override { waits.push_back(ms); return (int)waits.size() != stopAt; }
};
static void testSteadyRead() {
  { PlaySteady s; s.ang = {120, 121.5f, 118.5f, 120.5f, 119.5f, 121, 119, 120, 120.2f, 119.8f, 120, 121, 119};
    SteadyResult r = steadyRead(s);
    bool fifty = s.waits.size() == 12;
    for (uint32_t w : s.waits) fifty &= w == 50;
    CHECK(r.is == STEADY_OK && near(r.ang, 120, 0.2), "a still sensor: steady, the mean");
    CHECK(s.reads == 13 && fifty, "13 readings, 12 waits of 50 ms"); }
  { PlaySteady s; s.ang = {359, 1, 0.5f, 359.5f};
    SteadyResult r = steadyRead(s);
    CHECK(r.is == STEADY_OK && fabsf(angDiff(r.ang, 0)) < 0.5f, "readings either side of zero: steady, a mean near 0 (not 180)"); }
  { PlaySteady s; s.ang = {100, 100.5f, 101, 101.5f, 102, 102.5f, 103, 103.5f, 104, 104.5f, 105, 105.5f, 106};
    CHECK(steadyRead(s).is == STEADY_MOVING, "a sensor that drifts over 3.5 degrees: not still"); }
  for (int at : {0, 6, 12}) {
    PlaySteady s; s.ang = {120}; s.drop.assign(13, false); s.drop[at] = true;
    CHECK(steadyRead(s).is == STEADY_LOST, "one dropout anywhere (the first included), angles still: dropout");
  }
  { PlaySteady s; s.ang = {120}; s.stopAt = 3;
    CHECK(steadyRead(s).is == STEADY_CUT && s.reads == 3 && s.waits.size() == 3, "wait says stop on the third: cut short, no more readings"); }
  { PlaySteady s; s.ang = {200, 203.4f};
    CHECK(steadyRead(s).is == STEADY_OK, "a spread just under 3.5 degrees: steady"); }
  { PlaySteady s; s.ang = {200, 203.6f};
    CHECK(steadyRead(s).is == STEADY_MOVING, "a spread just over 3.5 degrees: not still"); }
}

// ---- the time zone: running zone = saved zone, and Schedules follow it at once (issue #125)
static time_t utcAt(int y, int mo, int d, int h, int mi) {
  struct tm u = {}; u.tm_year = y - 1900; u.tm_mon = mo - 1; u.tm_mday = d; u.tm_hour = h; u.tm_min = mi;
  return timegm(&u);
}
static void zoneTests() {
  const char *was = getenv("TZ");
  std::string keep = was ? was : "";
  CHECK(zoneOk("CST6CDT,M3.2.0,M11.1.0", 44) && zoneOk("UTC0", 44), "a real zone is taken");
  CHECK(!zoneOk("", 44) && !zoneOk("ab", 44), "an empty or too short zone is refused");
  CHECK(!zoneOk(std::string(44, 'x').c_str(), 44) && zoneOk(std::string(43, 'x').c_str(), 44), "a zone must fit the field with its end");
  const uint8_t ALL = 0x7f;
  time_t winter = utcAt(2026, 1, 15, 18, 0);                 // a Thursday, noon in Chicago
  zoneUse("CST6CDT,M3.2.0,M11.1.0");
  CHECK(slotDayTime(winter, 0, 420, ALL) == (uint32_t)utcAt(2026, 1, 15, 13, 0), "07:00 Central in winter is 13:00 UTC");
  zoneUse("PST8PDT,M3.2.0,M11.1.0");
  CHECK(slotDayTime(winter, 0, 420, ALL) == (uint32_t)utcAt(2026, 1, 15, 15, 0), "a new zone moves the slot at once: 07:00 Pacific is 15:00 UTC");
  zoneUse("CST6CDT,M3.2.0,M11.1.0");
  time_t summer = utcAt(2026, 7, 15, 17, 0);                 // a Wednesday, noon in Chicago (daylight time)
  CHECK(slotDayTime(summer, 0, 420, ALL) == (uint32_t)utcAt(2026, 7, 15, 12, 0), "07:00 Central in summer is 12:00 UTC");
  CHECK(slotDayTime(winter, 0, 420, ALL & ~(1 << 4)) == 0, "not on a Thursday: no slot that day");
  CHECK(slotDayTime(winter, 1, 420, 1 << 5) == (uint32_t)utcAt(2026, 1, 16, 13, 0), "the next day is a Friday: its slot");
  CHECK(slotDayTime(winter, 1, 420, 1 << 4) == 0, "the next day is not a Thursday");
  if (was) zoneUse(keep.c_str()); else { unsetenv("TZ"); tzset(); }
}

// ---- a settings backup the controller takes or refuses (issue #181); a refused one changes nothing
// A made-up layout: settings 16 bytes (magic, then a 6-byte zone at 6), tune 4, schedule extras 8 (magic first).
static const BackupLayout TEST_LAYOUT = {16, 4, 8, 0xB11D0003, 0x53580001, 6, 6};
static std::string goodBackup() {
  std::string b = "TB1";
  uint16_t sz[3] = {16, 4, 8};
  b.append((const char *)sz, sizeof sz);
  std::string s(16, 0); uint32_t m = 0xB11D0003; memcpy(&s[0], &m, 4); memcpy(&s[6], "UTC0", 5);
  std::string x(8, 0); uint32_t xm = 0x53580001; memcpy(&x[0], &xm, 4);
  return b + s + std::string(4, 7) + x + std::string(4, 1);
}
static void backupTests() {
  auto refusal = [](const std::string &b) {
    std::string keep = b;
    const char *why = backupRefusal((const uint8_t *)b.data(), b.size(), TEST_LAYOUT);
    CHECK(b == keep, "backup: the rule only reads the blob");
    return std::string(why ? why : "");
  };
  CHECK(refusal(goodBackup()).empty(), "backup: a well-formed one is taken");
  CHECK(refusal(goodBackup().substr(0, 8)) == "not a Tilt backup", "backup: under 9 bytes");
  { std::string b = goodBackup(); b[0] = 'X'; b[1] = 'Y'; b[2] = 'Z'; CHECK(refusal(b) == "not a Tilt backup", "backup: no TB1 at the start"); }
  { std::string b = goodBackup(); b[5] = 5; CHECK(refusal(b) == "this backup is from a different firmware", "backup: a size differs"); }
  CHECK(refusal(goodBackup() + "x") == "this backup is from a different firmware", "backup: one byte too many");
  { std::string b = goodBackup(); memcpy(&b[9 + 6], "ab\0", 3); CHECK(refusal(b) == "bad time zone", "backup: a 2-character zone"); }
  { std::string b = goodBackup(); memcpy(&b[9 + 6], "ABCDEF", 6); CHECK(refusal(b) == "bad time zone", "backup: a zone with no end in its field"); }
  { std::string b = goodBackup(); b[9] ^= 1; CHECK(refusal(b) == "not a Tilt backup", "backup: right sizes, wrong settings magic (#181)"); }
  { std::string b = goodBackup(); b[9 + 16 + 4] ^= 1; CHECK(refusal(b) == "not a Tilt backup", "backup: wrong schedule-extras magic"); }
}

// ---- the light trigger (issue #207): "when it gets dark / light", read from the solar panel's input
// One slot, stepped once a minute from `from` to `to` (inclusive). v(t): the minute's mean input, the minute ending at t.
struct LightSim {
  LightLatch l{};
  int kind = LIGHT_KIND_DARK;
  uint32_t base = 0, key = 1;
  bool panel = true;
  std::vector<std::pair<uint32_t, LightWhy>> fires;
  template <class V> void run(uint32_t from, uint32_t to, V v) {
    for (uint32_t t = from; t <= to; t += 60) {
      LightWhy w = lightStep(l, kind, t, t - 60, base, key, v(t), panel);
      if (w) fires.push_back({t, w});
    }
  }
};
static void lightTests() {
  const uint32_t SET = 1795386240u, M = 60, H = 3600;        // a sunset (the fixture's); a day of readings around it
  CHECK(isSunKind(1) && isSunKind(2) && isSunKind(3) && isSunKind(4) && !isSunKind(0), "kinds 1-4 run on the sun");
  CHECK(onSunrise(1) && onSunrise(3) && !onSunrise(2) && !onSunrise(4), "kinds 1 and 3 on sunrise");
  CHECK(isLightKind(3) && isLightKind(4) && !isLightKind(1) && !isLightKind(2) && !isLightKind(0), "kinds 3 and 4 by light");
  { LightSim s; s.base = SET;                                 // clear dusk: under 0.3 V from 20 min before the base and stays
    uint32_t under = SET - 20 * M;
    s.run(SET - 6 * H, SET + 6 * H, [&](uint32_t t) { return t > under ? 0.05f : 4.5f; });
    CHECK(s.fires.size() == 1 && s.fires[0].first == under + 15 * M && s.fires[0].second == LIGHT_BY_LIGHT, "clear dusk: one fire by light, 15 min after it went dark");
    CHECK(s.l.day == 1 && s.l.at == under + 15 * M && s.l.why == LIGHT_BY_LIGHT, "the latch holds the day, when and why"); }
  { LightSim s; s.base = SET;                                 // overcast: near 1 V all afternoon, then dark 30 min after the base
    uint32_t under = SET + 30 * M;
    s.run(SET - 6 * H, SET + 6 * H, [&](uint32_t t) { return t > under ? 0.1f : 1.0f; });
    CHECK(s.fires.size() == 1 && s.fires[0].first == under + 15 * M && s.fires[0].second == LIGHT_BY_LIGHT, "overcast dusk: one fire by light, not earlier"); }
  { LightSim s; s.base = SET;                                 // a midday storm: 0 V for an hour at about 2 pm, sun after, dark at the base
    s.run(SET - 9 * H, SET + 6 * H, [&](uint32_t t) { return (t > SET - 4 * H && t <= SET - 3 * H) || t > SET ? 0.0f : 3.0f; });
    CHECK(s.fires.size() == 1 && s.fires[0].first == SET + 15 * M, "midday storm: ignored; the real dusk fires"); }
  { LightSim s; s.base = SET;                                 // a cloud at dusk: 10 dark minutes, 3 brighter, then dark
    uint32_t a = SET - 30 * M, b = a + 10 * M, c = b + 3 * M;
    s.run(SET - 6 * H, SET + 6 * H, [&](uint32_t t) { return t <= a ? 3.0f : t <= b ? 0.1f : t <= c ? 0.8f : 0.1f; });
    CHECK(s.fires.size() == 1 && s.fires[0].first == c + 15 * M, "a cloud passing at dusk: one fire, 15 min after the second run began"); }
  { LightSim s; s.kind = LIGHT_KIND_LIGHT; s.base = SET - 11 * H;          // a sunrise at about 7 am; headlights at 1 am
    uint32_t h = s.base - 6 * H, up = s.base + 5 * M;
    s.run(s.base - 8 * H, s.base + 4 * H, [&](uint32_t t) { return (t > h && t <= h + 12 * M) || t > up ? 3.0f : 0.0f; });
    CHECK(s.fires.size() == 1 && s.fires[0].first == up + 10 * M && s.fires[0].second == LIGHT_BY_LIGHT, "headlights at night: ignored; dawn fires 10 min after it got light"); }
  { LightSim s; s.base = SET;                                 // USB plugged in (never dark), or the panel unplugged and gone high
    s.run(SET - 6 * H, SET + 6 * H, [](uint32_t) { return 5.0f; });
    CHECK(s.fires.size() == 1 && s.fires[0].first == SET + LIGHT_WINDOW_S && s.fires[0].second == LIGHT_FELL_BACK, "never dark: one fire, fell back at the window's end"); }
  { LightSim s; s.base = SET;                                 // a panel unplugged mid-day: 0 V from noon, the window never sees it lit
    s.run(SET - 6 * H, SET + 6 * H, [&](uint32_t t) { return t > SET - 6 * H + M ? 0.0f : 3.0f; });
    CHECK(s.fires.size() == 1 && s.fires[0].first == SET + LIGHT_WINDOW_S && s.fires[0].second == LIGHT_FELL_BACK, "panel unplugged mid-day: one fire, fell back at the window's end"); }
  { LightSim s; s.kind = LIGHT_KIND_LIGHT; s.base = SET - 11 * H;          // a USB cable in at dawn: light all along
    s.run(s.base - 6 * H, s.base + 6 * H, [](uint32_t) { return 5.0f; });
    CHECK(s.fires.size() == 1 && s.fires[0].first == s.base + LIGHT_WINDOW_S && s.fires[0].second == LIGHT_FELL_BACK, "USB at dawn: no fire by light, fell back at the window's end"); }
  { LightSim s; s.base = SET;                                 // lit for one minute as the window opens, then dark: a real fall
    s.run(SET - 6 * H, SET + 6 * H, [&](uint32_t t) { return t == SET - LIGHT_WINDOW_S ? 2.0f : t > SET - 6 * H + M ? 0.0f : 3.0f; });
    CHECK(s.fires.size() == 1 && s.fires[0].first == SET - LIGHT_WINDOW_S + 15 * M && s.fires[0].second == LIGHT_BY_LIGHT, "one lit minute inside the window arms it"); }
  CHECK(lightLatchKept(7, 4, 7, 4) && !lightLatchKept(7, 4, 8, 4) && !lightLatchKept(7, 4, 7, 3), "an edit keeps the latch; another id or kind clears it");
  { LightSim s; s.base = SET; s.panel = false;               // no panel seen: a plain sunset slot
    s.run(SET - 6 * H + 17, SET + 6 * H, [](uint32_t) { return 0.0f; });
    CHECK(s.fires.size() == 1 && s.fires[0].first == SET + 17 && s.fires[0].second == LIGHT_SUN_TIME, "no panel seen: one fire at the base time, why = sun time"); }
  { LightSim s; s.base = SET;                                 // a manual move after the fire: more dark runs that day fire nothing
    s.run(SET - 6 * H, SET + 6 * H, [&](uint32_t t) { return (t > SET - 60 * M && t <= SET - 40 * M) || t > SET ? 0.0f : 3.0f; });
    CHECK(s.fires.size() == 1 && s.fires[0].first == SET - 45 * M, "more dark after the fire, same day: no second fire");
    s.key = 2; s.base = SET + 86400; s.fires.clear();       // the next day
    s.run(SET + 6 * H + M, SET + 30 * H, [&](uint32_t t) { return t > SET + 86400 ? 0.0f : 3.0f; });
    CHECK(s.fires.size() == 1 && s.fires[0].first == SET + 86400 + 15 * M, "the next day's key fires again"); }
  { LightSim s; s.kind = LIGHT_KIND_LIGHT; s.base = SET - 11 * H;          // dawn: a reading between the levels fires nothing by light
    s.run(s.base - 6 * H, s.base + 6 * H, [&](uint32_t t) { return t > s.base - 30 * M ? 1.0f : 0.0f; });
    CHECK(s.fires.size() == 1 && s.fires[0].second == LIGHT_FELL_BACK, "dawn between the levels: no fire by light, only the fallback"); }
  { LightSim s; s.base = SET;                                 // a restart over the window's end: not run late
    s.l = LightLatch{};
    LightWhy w = lightStep(s.l, LIGHT_KIND_DARK, SET + LIGHT_WINDOW_S + 10 * M, SET + LIGHT_WINDOW_S - 40 * M, SET, 1, 5.0f, true);
    CHECK(w == LIGHT_NONE && s.l.day == 0, "a step gap over 30 min across the window's end: nothing fires");
    w = lightStep(s.l, LIGHT_KIND_DARK, SET + 10 * M, SET - 50 * M, SET, 1, 0.0f, false);
    CHECK(w == LIGHT_NONE, "a gap over the base time with no panel: not run late either"); }
  { LightSim s; s.base = SET; s.l.day = 1; s.l.why = LIGHT_BY_LIGHT;       // a latch from flash with today's key
    s.run(SET - 6 * H, SET + 6 * H, [&](uint32_t t) { return t > SET ? 0.0f : 3.0f; });
    CHECK(s.fires.empty(), "a latch loaded with today's key blocks a re-fire (restart after the evening close)"); }
  { LightSim s;                                               // no base today (not one of its days, no place)
    s.run(SET - 6 * H, SET + 6 * H, [](uint32_t) { return 0.0f; });
    CHECK(s.fires.empty(), "no base time: nothing"); }
  // ---- a day's base and key, through time zones and DST: each slot fires once a day, only on its days
  {
    const char *was = getenv("TZ");
    std::string keep = was ? was : "";
    zoneUse("CST6CDT,M3.2.0,M11.1.0");
    for (int k = 0; k < 2; k++) {                             // spring forward (Sun 8 Mar 2026), fall back (Sun 1 Nov 2026)
      uint32_t day0 = k ? (uint32_t)utcAt(2026, 10, 30, 12, 0) : (uint32_t)utcAt(2026, 3, 6, 12, 0);
      for (int kind : {LIGHT_KIND_LIGHT, LIGHT_KIND_DARK}) {
        LightLatch l{};
        std::map<uint32_t, int> perDay;
        uint32_t prev = day0 - 60;
        for (uint32_t t = day0; t < day0 + 4 * 86400; t += 60) {
          LightDay d = lightDayOf(t, kind, 0, 0x7f, 41.88, -87.63);
          struct tm lt; time_t tt = t; localtime_r(&tt, &lt);
          bool dark = lt.tm_hour < 6 || lt.tm_hour >= 19;     // a plain day: dark at night
          if (lightStep(l, kind, t, prev, d.base, d.key, dark ? 0.0f : 3.0f, true)) perDay[d.key]++;
          prev = t;
        }
        bool once = perDay.size() >= 3;
        for (auto &e : perDay) once &= e.second == 1;
        CHECK(once, k ? "fall back day: each day fires once" : "spring forward day: each day fires once");
      }
    }
    uint32_t thu = (uint32_t)utcAt(2026, 1, 15, 18, 0);       // a Thursday, noon in Chicago
    LightDay off = lightDayOf(thu, LIGHT_KIND_DARK, 0, 0x7f & ~(1 << 4), 41.88, -87.63);
    CHECK(off.key != 20260115 && llabs((long long)off.base - thu) > 12 * 3600, "not one of its days: that day has no base (the nearest is another day's)");
    LightDay d = lightDayOf(thu, LIGHT_KIND_DARK, -15, 0x7f, 41.88, -87.63);
    CHECK(d.base == sunEventAt(thu, 41.88, -87.63, false) - 15 * 60 && d.key == 20260115, "base = that day's sunset + offset; key = its local day");
    CHECK(lightDayOf(thu, LIGHT_KIND_DARK, 0, 0x7f, NAN, NAN).base == 0, "no place: no base");
    if (was) zoneUse(keep.c_str()); else { unsetenv("TZ"); tzset(); }
  }
  // ---- minute means
  { MinuteMean m;
    float got = -1;
    for (uint32_t t = 600; t < 600 + 60; t++) CHECK(!m.add(t, t < 630 ? 1.0f : 3.0f, &got), "inside a minute: no mean yet");
    CHECK(m.add(660, 0.0f, &got) && near(got, 2.0, 1e-4), "a new minute: the last one's mean");
    CHECK(!m.add(661, 0.0f, &got), "then on again"); }
  // ---- panel seen: dark at night and lit by day, within 3 days
  {
    const uint32_t D = 86400, T0 = 1795300000u;
    CHECK(panelSeenRule(T0, T0 - D, T0 - 2 * D), "dark night + lit day inside 3 days: seen");
    CHECK(!panelSeenRule(T0, 0, T0 - H), "always lit (a USB cable): not seen");
    CHECK(!panelSeenRule(T0, T0 - H, 0), "always dark (nothing plugged in): not seen");
    CHECK(!panelSeenRule(T0, T0 - 4 * D, T0 - H), "a dark night over 3 days ago: not seen");
    uint32_t rise = T0 + 6 * H, set = T0 + 18 * H;          // a day: rise at 6, set at 18 (after T0)
    PanelWatch w{};
    int saves = 0;
    for (uint32_t t = T0; t < T0 + D; t += 60) {
      bool lit = t > rise + 30 * M && t < set - 30 * M;
      if (panelStep(w, t, lit ? 3.0f : 0.0f, rise, set)) saves++;
    }
    CHECK(w.lastDark && w.lastLit && panelSeenRule(T0 + D, w.lastDark, w.lastLit), "a panel's day and night: seen");
    CHECK(saves <= 2, "at most two writes a day");
    PanelWatch u{};
    for (uint32_t t = T0; t < T0 + D; t += 60) panelStep(u, t, 5.0f, rise, set);
    CHECK(u.lastLit && !u.lastDark && !panelSeenRule(T0 + D, u.lastDark, u.lastLit), "a USB cable left in never goes dark: not seen");
    PanelWatch z{};
    for (uint32_t t = T0; t < T0 + D; t += 60) panelStep(z, t, 0.0f, rise, set);
    CHECK(!z.lastLit && !panelSeenRule(T0 + D, z.lastDark, z.lastLit), "nothing plugged in never goes lit: not seen");
    PanelWatch e{};
    for (uint32_t t = T0 + 17 * H; t < T0 + 19 * H; t += 60) panelStep(e, t, 0.0f, rise, set);
    CHECK(!e.lastDark, "dark just after sunset (under an hour): not yet night");
  }
}

int main() {
  // ---- angles
  CHECK(near(angDiff(10, 350), 20, 1e-4), "angDiff crosses zero forward");
  CHECK(near(angDiff(350, 10), -20, 1e-4), "angDiff crosses zero backward");
  CHECK(near(angDiff(190, 10), -180, 1e-4) || near(angDiff(190, 10), 180, 1e-4), "half a turn");

  // ---- marks and tilt (open 290, closed up 200, closed down 40: like the dining room blind)
  Marks m{200, 290, 40};
  CHECK(marksProblemOf(m) == nullptr, "good marks accepted");
  CHECK(near(tiltOfMarks(m, 200), 100, 0.01), "closed up reads +100");
  CHECK(near(tiltOfMarks(m, 40), -100, 0.01), "closed down reads -100");
  CHECK(near(tiltOfMarks(m, 290), 0, 0.01), "open reads 0");
  CHECK(near(tiltOfMarks(m, 245), 50, 0.01), "halfway to closed up reads +50");
  for (float t : {-100.0f, -37.0f, 0.0f, 12.5f, 100.0f}) {
    float ang = m.open + xOfTiltMarks(m, t) * sgn(angDiff(m.up, m.open));     // tilt -> angle -> tilt
    CHECK(near(tiltOfMarks(m, ang), t, 0.01), "tilt round trip");
  }
  Marks wrap{300, 10, 100};                                                   // marks either side of the sensor's zero
  CHECK(marksProblemOf(wrap) == nullptr && near(tiltOfMarks(wrap, 300), 100, 0.01) && near(tiltOfMarks(wrap, 100), -100, 0.01), "marks across zero");
  CHECK(marksProblemOf(Marks{NAN, 290, 40}) != nullptr, "missing mark refused");
  CHECK(marksProblemOf(Marks{285, 290, 40}) != nullptr, "open too close to a closed mark refused");
  CHECK(marksProblemOf(Marks{200, 290, 250}) != nullptr, "both closed marks on one side refused");

  // ---- can a blind move?
  CHECK(movableRule(false, true, true, true), "shown, set up, plugged in: movable");
  CHECK(movableRule(false, true, false, false), "not looked at yet: movable (the move itself finds out)");
  CHECK(!movableRule(true, true, true, true), "hidden: not movable");
  CHECK(!movableRule(false, false, true, true), "not set up: not movable");
  CHECK(!movableRule(false, true, true, false), "tilter missing: not movable");
  CHECK(!cannotMoveWhy(true, true, true, true), "can move");
  CHECK(!strcmp(cannotMoveWhy(false, true, false, false), "not set up yet"), "set up is checked first");
  CHECK(!strcmp(cannotMoveWhy(true, true, false, false), "no tilter plugged in"), "then the tilter");
  CHECK(!strcmp(cannotMoveWhy(true, false, false, false), "battery too low"), "then the motor cut-off");
  CHECK(!cannotMoveWhy(true, false, false, true), "a tilter never seen is not missing");
  CHECK(battLevel(9) == BATT_CRITICAL && battLevel(10) == BATT_LOW && battLevel(19) == BATT_LOW && battLevel(20) == BATT_OK, "Battery levels");

  // ---- Move requests
  requestTests();

  // ---- one blind's Move, on a simulated Tilter
  sensorTests();
  dropoutTests();
  tilterTests();
  handWatchTests();
  settingsChangeTests();
  zoneTests();
  backupTests();
  lightTests();

  // ---- battery
  CHECK(battPercent(3.0f) == 0 && battPercent(3.2f) == 0, "empty");
  CHECK(battPercent(3.7f) == 35, "table point 3.70 V");
  CHECK(battPercent(3.75f) == 45, "between table points");
  CHECK(battPercent(4.18f) == 100 && battPercent(4.3f) == 100, "full");
  int last = -1; bool rising = true;
  for (float v = 3.0f; v <= 4.3f; v += 0.01f) { int p = battPercent(v); if (p < last) rising = false; last = p; }
  CHECK(rising, "percent never drops as voltage rises");

  // ---- sun (Chicago, Nov 21 2026; reference: sunrise about 6:46 am CST = 12:46 UTC, sunset about 4:24 pm = 22:24 UTC)
  struct tm noon = {}; noon.tm_year = 126; noon.tm_mon = 10; noon.tm_mday = 21; noon.tm_hour = 18;
  time_t n = timegm(&noon);
  uint32_t rise = sunEventAt(n, 41.88, -87.63, true), set = sunEventAt(n, 41.88, -87.63, false);
  CHECK(near(rise, n - 18 * 3600 + 12 * 3600 + 46 * 60, 8 * 60), "Chicago sunrise within 8 minutes");
  CHECK(near(set, n - 18 * 3600 + 22 * 3600 + 24 * 60, 8 * 60), "Chicago sunset within 8 minutes");
  // Tokyo, the other side of the date line: local noon Nov 21 = 03:00 UTC. Reference: sunrise about 6:22 am JST
  // (21:22 UTC on Nov 20), sunset about 4:31 pm JST (07:31 UTC Nov 21).
  struct tm tk = {}; tk.tm_year = 126; tk.tm_mon = 10; tk.tm_mday = 21; tk.tm_hour = 3;
  time_t tn = timegm(&tk);
  CHECK(near(sunEventAt(tn, 35.68, 139.69, true), tn - 3 * 3600 - 2 * 3600 - 38 * 60, 8 * 60), "Tokyo sunrise within 8 minutes");
  CHECK(near(sunEventAt(tn, 35.68, 139.69, false), tn + 4 * 3600 + 31 * 60, 8 * 60), "Tokyo sunset within 8 minutes");
  struct tm dec = {}; dec.tm_year = 126; dec.tm_mon = 11; dec.tm_mday = 21; dec.tm_hour = 12;
  CHECK(sunEventAt(timegm(&dec), 80, 15, true) == 0, "no sunrise in the polar night");
  CHECK(sunEventAt(n, NAN, NAN, true) == 0, "no place set");

  // ---- Power source (v2.2 board): USB only when input power is there while the sun is well down; never Solar
  {
    const uint32_t H = 3600, M = 60;
    time_t mid = n - 18 * H + 6 * H;                     // local midnight in Chicago (CST = UTC-6), Nov 21 2026
    CHECK(powerSourceOf(false, true, n, rise, set) == SRC_BATTERY, "no input power at noon: battery");
    CHECK(powerSourceOf(false, true, mid, rise, set) == SRC_BATTERY, "no input power at midnight: battery");
    CHECK(powerSourceOf(true, true, mid, rise, set) == SRC_USB, "input power at midnight: USB");
    CHECK(powerSourceOf(true, true, set + 61 * M, rise, set) == SRC_USB, "61 minutes after sunset: USB");
    CHECK(powerSourceOf(true, true, rise - 61 * M, rise, set) == SRC_USB, "61 minutes before sunrise: USB");
    CHECK(powerSourceOf(true, true, n, rise, set) == SRC_UNKNOWN, "input power at noon: unknown");
    CHECK(powerSourceOf(true, true, set + 59 * M, rise, set) == SRC_UNKNOWN, "59 minutes after sunset: unknown (twilight)");
    CHECK(powerSourceOf(true, true, rise - 59 * M, rise, set) == SRC_UNKNOWN, "59 minutes before sunrise: unknown");
    CHECK(powerSourceOf(true, false, mid, rise, set) == SRC_UNKNOWN, "clock not set: unknown");
    CHECK(powerSourceOf(true, true, mid, 0, 0) == SRC_UNKNOWN, "no place set: unknown");
    time_t dn = timegm(&dec);
    uint32_t pr = sunEventAt(dn, 80, 15, true), ps = sunEventAt(dn, 80, 15, false);
    CHECK(powerSourceOf(true, true, dn - 12 * H, pr, ps) == SRC_UNKNOWN, "the sun does not set or rise there: unknown");
    bool only = true, darkOnly = true;
    for (int h = 0; h < 24; h++) {
      uint32_t t = mid + h * H;
      int s = powerSourceOf(true, true, t, rise, set);
      if (s != SRC_USB && s != SRC_UNKNOWN) only = false;
      if (s == SRC_USB && t + SRC_NIGHT_MARGIN_S >= rise && t <= set + SRC_NIGHT_MARGIN_S) darkOnly = false;
    }
    CHECK(only, "every hour of a day: only USB or unknown, never Solar");
    CHECK(darkOnly, "USB only in the dark hours");
  }

  // ---- stall
  CHECK(stallCheck(100, 300, 999, 500, 10, 10, 2) == STALL_WAIT, "no check while the gear play is taken up");
  CHECK(stallCheck(900, 300, 200, 500, 10, 10, 2) == STALL_WAIT, "not time to check yet");
  CHECK(stallCheck(900, 300, 600, 500, 10.5f, 10, 2) == STALL_YES, "barely moved: stalled");
  CHECK(stallCheck(900, 300, 600, 500, 15, 10, 2) == STALL_MOVED, "moved enough");
  CHECK(stallCheck(900, 300, 600, 500, 1, 359, 2) == STALL_MOVED, "moved enough across zero");

  // ---- secured command freshness
  uint8_t boot[4] = {1, 2, 3, 4}, nonce[12] = {1, 2, 3, 4, 0, 0, 0, 0, 0, 0, 0x01, 0x00};
  CHECK(nonceCounter(nonce) == 256, "counter is big-endian");
  CHECK(nonceFresh(nonce, boot, 255) && !nonceFresh(nonce, boot, 256), "counter must rise");
  uint8_t other[4] = {9, 9, 9, 9};
  CHECK(!nonceFresh(nonce, other, 0), "a command from before a restart is refused");

  // ---- who may do what: the one route table (routes.h) and the rule that reads it
  std::string me = "aabbccddeeff0011", them = "1122334455667788";
  auto rule = [&](const char *path, bool owner, const std::string &cid) {
    const RouteRule *r = routeRule(path);
    return r ? permitRule(r->who, owner, cid, me) : "not a command";
  };
  // permit() reads the cid from the whole query with the parser the handlers use (wire.h queryValue), so a Guest
  // cannot show one cid to the rule and another to the handler (#173 review M2).
  {
    const RouteRule *kn = routeRule("/api/keyname");
    CHECK(kn && !permitQuery(kn->who, false, "cid=" + me + "&name=x", me), "a Guest renames itself");
    CHECK(kn && permitQuery(kn->who, false, "cid=" + them + "&name=x", me), "a Guest may not rename another phone");
    CHECK(kn && permitQuery(kn->who, false, "CID=" + me + "&cid=" + them + "&name=x", me), "a cid in other case is not this phone's: refused");
    CHECK(kn && permitQuery(kn->who, false, "z&cid=" + them + "&cid=" + me + "&name=x", me), "a key with no value cannot hide the cid the handler reads: refused");
    CHECK(kn && queryValue("z&cid=" + them + "&cid=" + me, "cid") == them, "the handler reads the same first cid the rule refused");
    CHECK(kn && !permitQuery(kn->who, true, "cid=" + them + "&name=x", me), "an Owner renames any phone");
  }
  {
    bool roles = routeRuleCount > 30, paths = true, once = true;
    for (int i = 0; i < routeRuleCount; i++) {
      Who w = routeRules[i].who;
      if (w != OWNER && w != GUEST && w != SELF) roles = false;
      if (strncmp(routeRules[i].path, "/api/", 5)) paths = false;
      for (int k = 0; k < i; k++) if (!strcmp(routeRules[i].path, routeRules[k].path)) once = false;
    }
    CHECK(roles, "every route has a role");
    CHECK(paths && once, "every route is an /api/ command, listed once");
  }
  for (const char *p : {"/api/s", "/api/cfg", "/api/go", "/api/stop", "/api/home", "/api/backup", "/api/keys", "/api/scenes", "/api/scene"})
    CHECK(rule(p, false, "") == nullptr, "a guest may see and move, and make Scenes");
  for (const char *p : {"/api/set", "/api/sched", "/api/mark", "/api/approve", "/api/revoke", "/api/makeowner", "/api/otaopen", "/api/hubjoin", "/api/hubnet", "/api/restore", "/api/factory", "/api/swapfw", "/api/homeopen", "/api/hubkey", "/api/reboot", "/api/reset"})
    CHECK(rule(p, false, "") != nullptr, "a guest is refused an owner command");
  {
    int guestOk = 0;
    for (int i = 0; i < routeRuleCount; i++) if (permitRule(routeRules[i].who, false, "", me) == nullptr) guestOk++;
    CHECK(guestOk == 9, "a guest may send exactly the nine guest commands");
  }
  CHECK(rule("/api/keyname", false, me) == nullptr, "a guest may rename themself");
  CHECK(rule("/api/keyname", false, them) != nullptr, "a guest may not rename others");
  CHECK(rule("/api/keyname", false, "") != nullptr, "rename with no id refused");
  CHECK(rule("/api/keyname", true, them) == nullptr, "an owner may rename anyone");
  CHECK(routeRule("/api/nothing") == nullptr && routeRule("/") == nullptr && routeRule("/x/pair") == nullptr, "an unknown command is not a route");
  CHECK(routeRule("/api/openapi") == nullptr, "the old open-API switch is gone: refused like any unknown command");

  // ---- the owner's firmware update window (web.h hOtaOpen sets it; hub_link.h hubOtaBegin asks this)
  {
    const uint64_t B31 = 1ULL << 31, B32 = 1ULL << 32;
    const uint64_t never[] = {1000, B31 - 1, B31, B31 + 1, B32 - 1, B32, B32 + 1, 1ULL << 40};
    bool shut = true;
    for (uint64_t t : never) shut = shut && !otaWindowOpen(0, t);
    CHECK(shut, "no window ever opened: an update is refused, however long the uptime");
    const uint64_t now = 1000, end = now + OTA_WINDOW_MS;
    CHECK(otaWindowOpen(end, now) && otaWindowOpen(end, end - 1), "inside the window: an update may start");
    CHECK(!otaWindowOpen(end, end) && !otaWindowOpen(end, end + 1), "at or after the end: refused");
    CHECK(!otaWindowOpen(end, end + B31) && !otaWindowOpen(end, end + B31 + 1) &&
          !otaWindowOpen(end, end + B32) && !otaWindowOpen(end, end + B32 + 1), "a window that ran out stays shut");
    const uint64_t late = (uint64_t)UINT32_MAX - 1000, lateEnd = late + OTA_WINDOW_MS;   // the old 32-bit count would wrap here
    CHECK(lateEnd > late && otaWindowOpen(lateEnd, late) && otaWindowOpen(lateEnd, lateEnd - 1), "a window opened just before the old 32-bit wrap is open before its end");
    CHECK(!otaWindowOpen(lateEnd, lateEnd) && !otaWindowOpen(lateEnd, lateEnd + 1), "a window opened just before the old 32-bit wrap is shut after its end");
    const uint64_t veryLate = 1ULL << 33;
    CHECK(otaWindowOpen(veryLate + OTA_WINDOW_MS, veryLate + OTA_WINDOW_MS - 1) &&
          !otaWindowOpen(veryLate + OTA_WINDOW_MS, veryLate + OTA_WINDOW_MS), "a window opened after very long uptime");
  }

  // ---- which slot a new key takes (sec.h pairDo)
  {
    const uint32_t NEW = 1000, OLD = 700000, UNKNOWN = UINT32_MAX;
    uint8_t u1[4] = {1, 2, 2, 0};                          // an owner gone quiet, two asks waiting (the phone's and the hub's)
    uint32_t w1[4] = {0, NEW, NEW, 0};
    CHECK(keySlot(u1, w1, 4, true, false) == KEY_TWO_WAITING, "a third ask waits for an old one to go");
    CHECK(keySlot(u1, w1, 4, true, true) == 3, "a recovery gets in past two waiting asks");
    uint8_t u2[4] = {1, 2, 2, 1};
    uint32_t w2[4] = {0, NEW, NEW + 5, 0};
    CHECK(keySlot(u2, w2, 4, true, true) == 2, "no free slot: a recovery takes the oldest waiting ask's place");
    CHECK(keySlot(u2, w2, 4, true, false) == KEY_TWO_WAITING, "no free slot, asks still new: a plain ask waits");
    uint32_t w3[4] = {0, NEW, OLD, 0};
    CHECK(keySlot(u2, w3, 4, true, false) == 2, "an ask takes the place of one waiting over 10 minutes");
    uint32_t w4[4] = {0, UNKNOWN, NEW, 0};
    CHECK(keySlot(u2, w4, 4, true, false) == 1, "an ask of unknown age counts as old");
    uint8_t u3[4] = {1, 2, 0, 0};
    uint32_t w5[4] = {0, NEW, 0, 0};
    CHECK(keySlot(u3, w5, 4, true, false) == 2 && keySlot(u3, w5, 4, false, false) == 2, "room: the first free slot");
    uint8_t u4[2] = {1, 1};
    uint32_t w6[2] = {0, 0};
    CHECK(keySlot(u4, w6, 2, true, true) == KEY_FULL && keySlot(u4, w6, 2, false, false) == KEY_FULL, "every slot paired: full");
  }

  // ---- a request the hub sends again gets the answer the first one got (hub_link.h, 'A' and 'R')
  {
    KeptAnswer k;
    CHECK(!k.again("R{\"pub\":\"a\"}", 5000), "nothing kept yet");
    k.keep("R{\"pub\":\"a\"}", "200 OK", "{\"cid\":\"1\",\"recover\":1}", 5000);
    CHECK(k.again("R{\"pub\":\"a\"}", 9000) && !strcmp(k.st, "200 OK") && k.out == "{\"cid\":\"1\",\"recover\":1}", "a resent recovery gets the same answer (not 429)");
    CHECK(!k.again("R{\"pub\":\"b\"}", 9000), "a new key is a new request");
    CHECK(!k.again("A{\"pub\":\"a\"}", 9000), "an ask is not the recovery");
    CHECK(!k.again("R{\"pub\":\"a\"}", 5000 + 30000), "kept for 30 seconds only");
    k.keep("R{\"pub\":\"c\"}", "200 OK", "{}", 0xFFFFF000u);
    CHECK(k.again("R{\"pub\":\"c\"}", 0x1000u), "kept across the millisecond clock wrapping");
  }

  // ---- what the Tilt Hub may send (hub_link.h)
  for (char t : std::string("HXAQRBWEs")) CHECK(hubAsks(t), "the hub's requests are taken");
  for (char t : std::string("PGSLhx#Zr")) CHECK(!hubAsks(t), "an unknown datagram type is refused (no P: first pairing is Bluetooth only)");
  CHECK(!hubAsks(0), "a zero type is refused");

  // ---- Apple Home: what Home asked for
  CHECK(near(tiltOfHomeLift(10000, true), 100, 1e-4) && near(tiltOfHomeLift(10000, false), -100, 1e-4), "closed: up or down by closeUp");
  CHECK(near(tiltOfHomeLift(2500, true), 25, 1e-4) && near(tiltOfHomeLift(2500, false), -25, 1e-4), "quarter closed, both ways");
  CHECK(near(tiltOfHomeLift(0, true), 0, 1e-4) && near(tiltOfHomeLift(0, false), 0, 1e-4), "open is level either way");
  CHECK(homeLiftValid(0) && homeLiftValid(10000), "0 and 10000 are targets");
  CHECK(!homeLiftValid(HOME_LIFT_NULL) && !homeLiftValid(10001), "a null target is ignored, not a full close");
  CHECK(homeAskIsStop(true, 4000, 4000) && homeAskIsStop(true, 4099, 4000) && homeAskIsStop(true, 3901, 4000), "moving, asked for where it is: stop");
  CHECK(!homeAskIsStop(true, 4100, 4000) && !homeAskIsStop(true, 3900, 4000), "moving, asked 1 % away: a new target");
  CHECK(!homeAskIsStop(false, 4000, 4000), "at rest, asked for where it is: not a stop");

  // ---- Apple Home: what Home sees
  BlindNow one[1] = {{-50, false, NAN}};
  HomeView hv = homeViewOf(one, 1);
  CHECK(hv.any && hv.lift == 5000 && hv.op == 0, "half closed down: 50 % closed, still");
  one[0].tilt = 50;
  CHECK(homeViewOf(one, 1).lift == 5000, "half closed up: also 50 % closed");
  one[0].tilt = 94; CHECK(homeViewOf(one, 1).lift == 10000, "at rest at 94: closed");
  one[0].tilt = -93.9f; CHECK(homeViewOf(one, 1).lift == 9400, "at rest at 93.9: as it is");
  one[0].tilt = 6; CHECK(homeViewOf(one, 1).lift == 0, "at rest at 6: open");
  one[0].tilt = 6.5f; CHECK(homeViewOf(one, 1).lift == 700, "at rest at 6.5: as it is (rounded)");
  one[0].tilt = 120; CHECK(homeViewOf(one, 1).lift == 10000, "past the end: closed");
  BlindNow mv[1] = {{97, true, 100}};
  hv = homeViewOf(mv, 1);
  CHECK(hv.lift == 9700 && hv.op == 2, "moving: true value, closing");
  mv[0] = {3, true, 0};
  hv = homeViewOf(mv, 1);
  CHECK(hv.lift == 300 && hv.op == 1, "moving toward open: opening");
  mv[0] = {-40, true, 80};
  CHECK(homeViewOf(mv, 1).op == 2, "closing the other way counts as closing");
  mv[0] = {40, true, NAN};
  CHECK(homeViewOf(mv, 1).op == 0, "busy with no target: still");
  BlindNow three[3] = {{20, false, NAN}, {-60, false, NAN}, {NAN, false, NAN}};
  hv = homeViewOf(three, 3);
  CHECK(hv.any && hv.lift == 4000, "average of the known blinds, unknown left out");
  BlindNow none[1] = {{NAN, false, NAN}};
  CHECK(!homeViewOf(none, 1).any && !homeViewOf(none, 0).any, "nothing known: nothing to show");

  // ---- Apple Home: what to send
  HomeView still{true, 5000, 0}, closing{true, 5000, 2};
  HomeSend hs = homeSendOf(still, false, -1, -1);
  CHECK(hs.lift && hs.target && hs.op && hs.opBits == 0, "first report: everything");
  hs = homeSendOf(still, false, 4900, 0);
  CHECK(hs.lift && hs.target && !hs.op, "a change of 1 %: sent");
  hs = homeSendOf(HomeView{true, 5000, 0}, false, 5000, 0);
  CHECK(!hs.lift && !hs.target && !hs.op, "no change: nothing sent");
  CHECK(homeSendOf(still, true, 5000, 0).lift, "forced: sent anyway");
  hs = homeSendOf(closing, false, 4000, 0);
  CHECK(hs.lift && !hs.target && hs.op && hs.opBits == 0x0A, "moving: current only, status closing");
  CHECK(homeSendOf(HomeView{true, 0, 1}, false, -1, 0).opBits == 0x05, "status opening");
  CHECK(!homeSendOf(HomeView{false, 0, 0}, true, -1, -1).lift, "nothing known: nothing sent, even forced");

  // ---- Apple Home: battery
  CHECK(homeBatPercent(0) == 0 && homeBatPercent(37) == 74 && homeBatPercent(100) == 200, "half percents");
  CHECK(homeChargeLevel(9) == 2 && homeChargeLevel(10) == 1, "Critical below 10 %");
  CHECK(homeChargeLevel(19) == 1 && homeChargeLevel(20) == 0, "Low below 20 %");

  // ---- the wire contract: the shared fixture (test/wire/), also checked by the app's tests
  std::string fixCfg = readFile("wire/cfg.json");
  CHECK(!fixCfg.empty(), "wire/cfg.json is there");
  CHECK(cfgJson(FIX) == fixCfg, "/api/cfg matches wire/cfg.json byte for byte");
  if (cfgJson(FIX) != fixCfg) printf("  got: %s\n", cfgJson(FIX).c_str());
  std::string write = readFile("wire/slot_write.txt");       // the app's command that writes slot 2 of the fixture
  std::map<std::string, std::string> q;
  std::stringstream qs(write.substr(write.find('?') + 1));
  for (std::string kv; std::getline(qs, kv, '&');) { size_t e = kv.find('='); q[kv.substr(0, e)] = e == std::string::npos ? "" : kv.substr(e + 1); }
  auto arg = [&](const char *k) { auto it = q.find(k); return it == q.end() ? std::string() : it->second; };
  WireSlot got = slotOfArgs(arg, 3);
  const WireSlot &want = FIX_S[2];
  CHECK(write.rfind("/api/sched?", 0) == 0 && q["i"] == "2", "the slot write is for slot 2");
  CHECK(got.on == want.on && got.days == want.days && got.mask == want.mask && got.min == want.min && got.tilt == want.tilt &&
        got.kind == want.kind && got.off == want.off && got.ramp == want.ramp && got.gid == want.gid, "the slot write reads back as slot 2");
  q["mask"] = "15"; q["tilt"] = "-300"; q["min"] = "2000";
  got = slotOfArgs(arg, 3);
  CHECK(got.mask == 7 && got.tilt == -100 && got.min == 1439, "out-of-range values are brought into range (mask to 3 Ports)");
  CHECK(slotOfArgs(arg, 2).mask == 3, "the mask follows the number of Ports");
  q["kind"] = "3"; CHECK(slotOfArgs(arg, 3).kind == 3, "kind 3 (when it gets light) is kept");
  q["kind"] = "4"; CHECK(slotOfArgs(arg, 3).kind == 4, "kind 4 (when it gets dark) is kept");
  q["kind"] = "5"; CHECK(slotOfArgs(arg, 3).kind == 4, "a kind past 4 is brought to 4");

  // ---- Scenes on the wire: the same fixture the app's tests read and write
  {
    WireScene fs[2] = {{4000000000u, 1795319000u, "Movie \"night\"", "film", 5, {-100, 0, -100}},
                       {7u, 1795300000u, "Morning", "sunrise", 2, {0, 50, 0}}};
    std::string fixSc = readFile("wire/scenes.json");
    CHECK(!fixSc.empty() && scenesJson(fs, 2, 16, 3) == fixSc, "/api/scenes matches wire/scenes.json byte for byte");
    if (scenesJson(fs, 2, 16, 3) != fixSc) printf("  got: %s\n", scenesJson(fs, 2, 16, 3).c_str());
    std::string sw = readFile("wire/scene_write.txt");        // the app's command that writes the first fixture Scene
    std::map<std::string, std::string> sq;
    std::stringstream ss(sw.substr(sw.find('?') + 1));
    for (std::string kv; std::getline(ss, kv, '&');) { size_t e = kv.find('='); sq[kv.substr(0, e)] = e == std::string::npos ? "" : kv.substr(e + 1); }
    auto sarg = [&](const char *k) { auto it = sq.find(k); return it == sq.end() ? std::string() : it->second; };
    WireScene g = sceneOfArgs(sarg, 3);
    CHECK(sw.rfind("/api/scene?", 0) == 0 && g.gid == fs[0].gid && g.ver == fs[0].ver && g.sym == "film" && g.mask == 5 &&
          g.t[0] == -100 && g.t[1] == 0 && g.t[2] == -100, "the Scene write reads back as the fixture's Scene");
    sq["t"] = "-300,40,300"; sq["mask"] = "15"; sq["sym"] = "Bed.Double\"x";
    g = sceneOfArgs(sarg, 3);
    CHECK(g.mask == 7 && g.t[0] == -100 && g.t[1] == 40 && g.t[2] == 100 && g.sym == "ed.oublex", "Scene values brought into range, icon cleaned");
    CHECK(keptName("Movie \"night\"", 47) == "Movie \"night\"", "a Scene name keeps its quotes");
    CHECK(keptName("Mom\xE2\x80\x99s caf\xC3\xA9 \xF0\x9F\x8E\xAC", 47) == "Mom\xE2\x80\x99s caf\xC3\xA9 \xF0\x9F\x8E\xAC", "curly apostrophe, accent and emoji kept");
    CHECK(keptName("a\nb\x01" "c", 47) == "abc", "control characters dropped");
    CHECK(keptName("abcd\xF0\x9F\x8E\xAC", 6) == "abcd", "a name cut to fit never ends inside a character");
    CHECK(keptName("ab  ", 47) == "ab" && keptName(std::string(60, 'x'), 47).size() == 47, "trailing spaces trimmed, 47 bytes at most");
    CHECK(keptName("a\xC3" "b", 47) == "ab" && keptName("a\x80" "b", 47) == "ab" && keptName("a\xC0\xAF" "b", 47) == "ab",
          "a lone lead byte, a lone continuation byte and an overlong pair are dropped, the text around them kept");
    CHECK(keptName("ab\xE2\x80", 47) == "ab" && keptName("\xED\xA0\x80x\xF5\x80\x80\x80y", 47) == "xy", "a cut-off character, a surrogate and a byte past U+10FFFF are dropped");
    // Blind (19 bytes) and controller (23 bytes) names: the same list as app/Tilt/Tests/main.swift (NameRule.fit).
    struct NameCase { const char *in; size_t bytes; const char *kept; };
    const NameCase names[] = {
        {"Left", 19, "Left"},
        {"Mom\xE2\x80\x99s caf\xC3\xA9", 19, "Mom\xE2\x80\x99s caf\xC3\xA9"},
        {"Cr\xC3\xA8me br\xC3\xBBl\xC3\xA9" "e", 19, "Cr\xC3\xA8me br\xC3\xBBl\xC3\xA9" "e"},
        {"Living Room Left \xF0\x9F\x8E\xAC", 19, "Living Room Left"},
        {"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", 19, "aaaaaaaaaaaaaaaaaaa"},
        {"Den \"Caf\xC3\xA9\"", 23, "Den \"Caf\xC3\xA9\""},
        {"Master Bedroom East \xF0\x9F\x8E\xAC", 23, "Master Bedroom East"},
        {"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", 23, "bbbbbbbbbbbbbbbbbbbbbbb"},
        {"O\xE2\x80\x99" "Brien", 19, "O\xE2\x80\x99" "Brien"},                        // a phone's name (19 bytes)
        {"cccccccccccccccccccccccccccccc", 19, "ccccccccccccccccccc"},
    };
    for (const NameCase &c : names) CHECK(keptName(c.in, c.bytes) == c.kept, "a blind, controller or phone name kept as the app fits it");

    // ---- the People list on the wire (/api/keys on a controller; the Tilt Hub builds its rows the same way)
    std::string fixKeys = readFile("wire/keys.json");
    std::string rows = "{\"keys\":[" + keyJson("0102030405060708", "Mom\xE2\x80\x99s \"caf\xC3\xA9\"", 1, 1, 0, "") + "," +
                       keyJson("a1b2c3d4e5f60718", "Den\\Kid", 0, 0, 0, "") + "," + keyJson("ffeeddccbbaa9988", "Guest", 0, 0, 1, "0427") + "]}";
    CHECK(!fixKeys.empty() && rows == fixKeys, "/api/keys matches wire/keys.json byte for byte");
    if (rows != fixKeys) printf("  got: %s\n", rows.c_str());
    CHECK(keyJson("01", "Bj\xC3\xB6rn Anders Lin\xC3", 0, 0, 0, "") == "{\"cid\":\"01\",\"name\":\"Bj\xC3\xB6rn Anders Lin\",\"owner\":0,\"me\":0,\"wait\":0,\"code\":\"\"}",
          "a name cut inside a character (an old hub name) is written as valid UTF-8, the broken byte dropped");
    // ---- a value from a command's query, decoded (the app sends names percent-encoded: Api.swift urlQuery)
    CHECK(queryValue("cid=a1&name=O%E2%80%99Brien", "name") == "O\xE2\x80\x99" "Brien", "a curly apostrophe, percent-encoded, decoded");
    CHECK(queryValue("name=John%20Smith", "name") == "John Smith" && queryValue("name=John+Smith", "name") == "John Smith", "%20 and + are a space");
    CHECK(queryValue("name=%22Den%5CKid%22&cid=a1", "cid") == "a1" && queryValue("name=%22Den%5CKid%22", "name") == "\"Den\\Kid\"", "quotes and a backslash decoded; the right key");
    CHECK(queryValue("xname=a&name=b", "name") == "b" && queryValue("name=a", "nam").empty() && queryValue("", "name").empty(), "only the whole key; missing: empty");
    CHECK(queryValue("name=50%", "name") == "50%" && queryValue("name=%zz", "name") == "%zz", "a % without two hex digits is kept as it is");
    sq["mask"] = "1"; sq["t"] = "20";
    g = sceneOfArgs(sarg, 3);
    CHECK(g.t[0] == 20 && g.t[1] == 0 && g.t[2] == 0, "a short tilt list: the rest are 0, and blinds not in the Scene are 0");
  }

  // ---- Apple Home setup code: kept once made
  CHECK(setupPinValid(1) && setupPinValid(99999998) && setupPinValid(24681357), "ordinary passcodes are valid");
  CHECK(!setupPinValid(0) && !setupPinValid(99999999) && !setupPinValid(33333333) && !setupPinValid(12345678) &&
        !setupPinValid(87654321) && !setupPinValid(100000000), "the forbidden passcodes are not");
  HomeCode hc = {HOME_CODE_MAGIC, 51234567, 1000, 0xABC, {}, {}};
  CHECK(homeCodeKeep(hc, sizeof hc), "a good stored code is kept");
  CHECK(!homeCodeKeep(hc, 0), "nothing stored: make one");
  CHECK(!homeCodeKeep(hc, sizeof hc - 1), "wrong size: make one");
  HomeCode bad = hc; bad.magic = 0;
  CHECK(!homeCodeKeep(bad, sizeof bad), "wrong magic: make one");
  bad = hc; bad.pin = 11111111;
  CHECK(!homeCodeKeep(bad, sizeof bad), "forbidden passcode: make one");
  bad = hc; bad.disc = 0x1000;
  CHECK(!homeCodeKeep(bad, sizeof bad), "discriminator over 12 bits: make one");
  bad = hc; bad.iter = 999;
  CHECK(!homeCodeKeep(bad, sizeof bad), "too few iterations: make one");
  CHECK(manualCodeDashed("12345678901") == "1234-567-8901" && manualCodeDashed("123") == "123", "the manual code is dashed 4-3-4");
  {
    // The 144 bytes tools/device_identity.py writes for a hub (home_code_blob, the same hex in tools/test_tools.py):
    // the SDK test passcode and discriminator and its verifier, salt 00..1f. The firmware has to read them as written.
    const char *hex = "0100434825423401e8030000000f000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
                      "b96170aae803346884724fe9a3b287c30330c2a660375d17bb205a8cf1aecb350457f8ab79ee253ab6a8e46bb09e54"
                      "3ae422736de501e3db37d441fe344920d09548e4c18240630c4ff4913c53513839b7c07fcc0627a1b8573a149fcd1fa4"
                      "66cf00";
    CHECK(sizeof(HomeCode) == 144 && strlen(hex) == 2 * sizeof(HomeCode), "HomeCode is 144 bytes, as the Mac's tool writes it");
    HomeCode t;
    uint8_t *b = (uint8_t *)&t;
    for (size_t i = 0; i < sizeof t; i++) { char h[3] = {hex[2 * i], hex[2 * i + 1], 0}; b[i] = (uint8_t)strtol(h, nullptr, 16); }
    CHECK(homeCodeKeep(t, sizeof t), "the tool's Apple Home code is kept");
    CHECK(t.pin == 20202021 && t.disc == 3840 && t.iter == 1000 && t.salt[0] == 0 && t.salt[31] == 0x1f,
          "the tool's passcode, discriminator, iterations and salt land in their fields");
    CHECK(t.verifier[0] == 0xb9 && t.verifier[32] == 0x04 && t.verifier[96] == 0xcf, "the verifier lands in its field");
  }

  // ---- the Tilt Hub's alert rules: each alert once; the battery's three levels each once
  {
    AlertMemo m = {};
    bool ch = false;
    CHECK(!alertBattery(m, 55, 0, &ch), "a full battery: nothing");
    CHECK(!strcmp(alertBattery(m, 19, 0, &ch), "batt-low"), "under 20: low");
    CHECK(!alertBattery(m, 18, 0, &ch) && !alertBattery(m, 20, 0, &ch) && !alertBattery(m, 19, 0, &ch), "low again, or back at the line: no repeat");
    CHECK(!strcmp(alertBattery(m, 9, 0, &ch), "batt-crit"), "under 10: critical");
    CHECK(!alertBattery(m, 8, 0, &ch), "critical again: no repeat");
    CHECK(!strcmp(alertBattery(m, 7, 1, &ch), "batt-dead"), "too low to move: dead");
    CHECK(!alertBattery(m, 6, 1, &ch) && !alertBattery(m, 15, 0, &ch), "dead again, or charging a little: nothing");
    CHECK(!alertBattery(m, 25, 0, &ch) && m.batt == 0, "charged to 25: all levels reset");
    CHECK(!strcmp(alertBattery(m, 19, 0, &ch), "batt-low"), "and low can come again");
    AlertMemo d = {};
    CHECK(!strcmp(alertBattery(d, 12, 1, &ch), "batt-dead") && !alertBattery(d, 5, 0, &ch), "straight to too low to move: one alert, not three");
    CHECK(!alertBattery(d, -1, 0, &ch) && alertBattLevel(-1, 0) == -1, "no reading yet: nothing");
  }
  {
    AlertMemo m = {};
    bool ch = false;
    int st[3] = {2, 0, 0};
    CHECK(alertStalls(m, 7, st, 3, &ch) == 0 && ch, "the first push only learns the counts");
    CHECK(alertStalls(m, 7, st, 3, &ch) == 0, "the same counts: nothing");
    st[1] = 1;
    CHECK(alertStalls(m, 7, st, 3, &ch) == 2, "blind 2 stalled once: one alert, for it");
    CHECK(alertStalls(m, 7, st, 3, &ch) == 0, "told once only");
    int again[3] = {1, 0, 0};
    CHECK(alertStalls(m, 8, again, 3, &ch) == 1, "after a restart the count starts at 0: its first stall is new");
    int none[3] = {-1, -1, -1};
    CHECK(alertStalls(m, 8, none, 3, &ch) == 0, "an older controller (no counts): nothing");
  }
  {
    AlertMemo m = {};
    CHECK(!alertSilent(m, ALERT_SILENT_MS), "quiet for exactly the check-in allowance: fine");
    CHECK(alertSilent(m, ALERT_SILENT_MS + 1) && !alertSilent(m, ALERT_SILENT_MS * 3), "silent: one alert, not more");
    CHECK(alertHeard(m) && !alertHeard(m), "heard again: cleared (no alert for that)");
    CHECK(alertSilent(m, ALERT_SILENT_MS + 1), "silent again later: a new alert");
  }

  testSteadyRead();

  printf("%d passed, %d failed\n", passed, failed);
  return failed ? 1 : 0;
}
