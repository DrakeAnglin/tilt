// Tests for main/logic.h, main/home_view.h, main/request.h, main/tilter.h and main/wire.h, run on the Mac:
// tools/firmware_tests.sh. No hardware, no ESP-IDF.
#include "../main/logic.h"
#include "../main/home_view.h"
#include "../main/request.h"
#include "../main/tilter.h"
#include "../main/wire.h"
#include <cstdio>
#include <ctime>
#include <fstream>
#include <map>
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
static const WireBlind FIX_B[3] = {{"Left", 0, 100, 0}, {"Middle", 0, 80, -50}, {"Right", 1, 50, 100}};
static const WireSlot FIX_EMPTY = {0, 127, 0, 480, 0, 0, 0, 0, 0};
static const WireSlot FIX_S[8] = {{1, 62, 7, 420, 0, 0, 0, 0, 1}, FIX_EMPTY, {1, 127, 5, 480, -100, 2, -15, 10, 4000000000u},
                                  FIX_EMPTY, FIX_EMPTY, FIX_EMPTY, FIX_EMPTY, FIX_EMPTY};
static const WireCfg FIX = {"Den \"East\"", 1, 1, 0, 20, "CST6CDT,M3.2.0,M11.1.0", "America/Chicago", 0, FIX_B, 3, FIX_S, 8,
                            41.88f, -87.63f, 1795351560u, 1795386240u};

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
  float angle() override {
    if (firstZero) { firstZero = false; return 0; }
    float g = dir && glitchMs && t >= glitchAt && t < glitchAt + glitchMs ? glitchBy : 0;   // motor noise: only while it runs
    if (spikeEvery && ++reads % spikeEvery == 0) g += spikeBy;
    if (strainZeros && dir && (rod <= lo + 0.5f || rod >= hi - 0.5f) && ++reads % 60 < 15) return 0;
    return inBlind() ? 0 : fmodf(wrapped() + (dir ? 3.0f : 0) + g + 360.0f, 360.0f);
  }
  bool noReading() override { return inBlind(); }
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
static void tilterTests() {
  { SimTilter s; float t = s.go(50);
    CHECK(s.endMsg == "reached" && near(t, 50, 5), "reaches a Target through gear play and the high reading"); }
  { SimTilter s; s.go(50); float before = s.mem.lead[0];
    SimTilter s2; s2.mem.lead[0] = -1; s2.go(50);
    CHECK(s2.mem.lead[0] > -1 && near(before, 2.5f, 1.5f), "lead is learned toward what the rod really does"); }
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
  tilterTests();

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
  for (const char *p : {"/api/s", "/api/cfg", "/api/go", "/api/stop", "/api/home", "/api/backup", "/api/keys"})
    CHECK(rule(p, false, "") == nullptr, "a guest may see and move");
  for (const char *p : {"/api/set", "/api/sched", "/api/mark", "/api/approve", "/api/revoke", "/api/makeowner", "/api/otaopen", "/api/hubjoin", "/api/hubnet", "/api/restore", "/api/factory", "/api/swapfw", "/api/homeopen", "/api/openapi", "/api/hubkey", "/api/reboot", "/api/reset"})
    CHECK(rule(p, false, "") != nullptr, "a guest is refused an owner command");
  {
    int guestOk = 0;
    for (int i = 0; i < routeRuleCount; i++) if (permitRule(routeRules[i].who, false, "", me) == nullptr) guestOk++;
    CHECK(guestOk == 7, "a guest may send exactly the seven guest commands");
  }
  CHECK(rule("/api/keyname", false, me) == nullptr, "a guest may rename themself");
  CHECK(rule("/api/keyname", false, them) != nullptr, "a guest may not rename others");
  CHECK(rule("/api/keyname", false, "") != nullptr, "rename with no id refused");
  CHECK(rule("/api/keyname", true, them) == nullptr, "an owner may rename anyone");
  CHECK(routeRule("/api/nothing") == nullptr && routeRule("/") == nullptr && routeRule("/x/pair") == nullptr, "an unknown command is not a route");

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

  printf("%d passed, %d failed\n", passed, failed);
  return failed ? 1 : 0;
}
