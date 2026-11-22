// Tests for main/logic.h and main/request.h, run on the Mac: tools/firmware_tests.sh. No hardware, no ESP-IDF.
#include "../main/logic.h"
#include "../main/request.h"
#include <cstdio>
#include <ctime>
#include <string>

static int passed = 0, failed = 0;
#define CHECK(cond, what) do { if (cond) passed++; else { failed++; printf("FAIL line %d: %s\n", __LINE__, what); } } while (0)
static bool near(double a, double b, double tol) { return fabs(a - b) <= tol; }

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
};
static void requestTests() {
  { RecMoves s; MoveResult r = moveRequest(moveAsk(FROM_APP, 1, 50), s);
    CHECK(s.log == "x n1:50 " && r.started == 1 && !r.why, "app: one blind, gentle moves end"); }
  { RecMoves s; s.fol = true; MoveResult r = moveRequest(moveAsk(FROM_APP, 1, 50), s);
    CHECK(s.log == "x n1:50 n0:50 n2:50 " && r.started == 3, "app: follow mode takes the others along"); }
  { RecMoves s; s.fol = true; MoveAsk a = moveAsk(FROM_APP, 1, 50); a.solo = true; moveRequest(a, s);
    CHECK(s.log == "x n1:50 ", "app: solo leaves the others"); }
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
  { RecMoves s; s.fol = true; s.mov[2] = false; MoveResult r = moveRequest(moveAsk(FROM_SCHEDULE, -1, 30, 0, 0x06), s);
    CHECK(s.log == "n1:30 " && r.started == 1, "schedule: its blinds that can move, no follow, gentle moves kept"); }
  { RecMoves s; moveRequest(moveAsk(FROM_SCHEDULE, -1, 30, 120000, 0x01), s);
    CHECK(s.log == "g0:0>30/120000 ", "schedule: gently"); }
  { RecMoves s; MoveResult r = moveRequest(moveAsk(FROM_HOME, 2, -40), s);
    CHECK(s.log == "x n2:-40 " && r.started == 1, "Home: its covering's blind"); }
  { RecMoves s; s.fol = true; s.mov[2] = false; moveRequest(moveAsk(FROM_HOME, 2, -40), s);
    CHECK(s.log == "x n0:-40 n1:-40 ", "Home: follow mode, can-move rule even for its own blind"); }
  { RecMoves s; moveRequest(moveAsk(FROM_HOME, -1, 10), s);
    CHECK(s.log == "x n0:10 n1:10 n2:10 ", "Home: one covering for all"); }
  { RecMoves s; s.cur[0] = 48; s.cur[2] = NAN; MoveResult r = moveRequest(moveAsk(FROM_HAND, 1, 50), s);
    CHECK(s.log == "n2:50 " && r.started == 1, "hand: the others follow, unless already there; gentle moves kept"); }
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
  CHECK(!strcmp(cannotMoveWhy(true, false, false, false), "battery too low"), "then the battery");

  // ---- Move requests
  requestTests();

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

  // ---- who may do what
  std::string me = "aabbccddeeff0011", them = "1122334455667788";
  CHECK(permitRule(false, false, false, false, "/api/s", "", "") != nullptr, "plain closed once owned");
  CHECK(permitRule(false, false, true, false, "/api/set", "", "") == nullptr, "plain open before pairing or with the switch");
  CHECK(permitRule(false, false, false, true, "/api/update", "", "") == nullptr, "update checks its own signature");
  CHECK(permitRule(true, true, false, false, "/api/set", "", me) == nullptr, "owner may change settings");
  for (const char *p : {"/api/s", "/api/cfg", "/api/go", "/api/stop", "/api/keys", "/api/wifistate"})
    CHECK(permitRule(true, false, false, false, p, "", me) == nullptr, "user may see and move");
  for (const char *p : {"/api/set", "/api/sched", "/api/mark", "/api/approve", "/api/revoke", "/api/makeowner", "/api/otaopen", "/api/setwifi", "/api/homeopen"})
    CHECK(permitRule(true, false, false, false, p, "", me) != nullptr, "user refused owner-only command");
  CHECK(permitRule(true, false, false, false, "/api/keyname", me, me) == nullptr, "user may rename themself");
  CHECK(permitRule(true, false, false, false, "/api/keyname", them, me) != nullptr, "user may not rename others");
  CHECK(permitRule(true, false, false, false, "/api/keyname", "", me) != nullptr, "rename with no id refused");

  printf("%d passed, %d failed\n", passed, failed);
  return failed ? 1 : 0;
}
