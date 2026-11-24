// Tests for main/ctrl_link.h (the hub's link to one controller), run on the Mac: tools/firmware_tests.sh. A fake
// controller answers the way blinds_matter/main/sec.h secDo does: a hello with its boot id, and sealed commands whose
// counter must rise (409 stale otherwise, 401 for a key it does not know).
#include "../main/ctrl_link.h"
#include <atomic>
#include <cstdio>
#include <set>
#include <thread>
#include <vector>

static int passed = 0, failed = 0;
#define CHECK(cond, what) do { if (cond) passed++; else { failed++; printf("FAIL line %d: %s\n", __LINE__, what); } } while (0)

struct FakeController : LinkSeam {
  std::mutex m;
  uint8_t key[32], cid[8] = {1, 2, 3, 4, 5, 6, 7, 8}, bootId[4] = {0xa1, 0xb2, 0xc3, 0xd4};
  uint64_t last = 0;
  KeyState ks = KEY_IN;
  bool knowsKey = true, waiting = false;
  int hellos = 0, commands = 0, stale = 0, drops = 0, letIns = 0;
  std::vector<uint64_t> taken;                   // the counters it took, in order
  std::atomic<uint64_t> clock{1795319000000ULL};
  FakeController() { for (int i = 0; i < 32; i++) key[i] = (uint8_t)i; }
  void restart() { std::lock_guard<std::mutex> l(m); bootId[0]++; last = 0; }
  int ask(char type, const std::string &payload, std::string &ans) override {
    std::lock_guard<std::mutex> l(m);
    if (type == DG_HELLO) { hellos++; ans = "{\"id\":\"a0b1c2d3e4f5\",\"boot\":\"" + hexOf(bootId, 4) + "\"}"; return 200; }
    if (type != DG_COMMAND) return 400;
    commands++;
    Frame f;
    std::string cmd;
    FrameErr e = frameOpen(payload, [&](const Frame &fr, uint8_t k[32]) {
      if (!knowsKey || memcmp(fr.cid, cid, 8)) return FrameErr::NotPaired;
      if (memcmp(fr.nonce, bootId, 4) || fr.ctr <= last) return FrameErr::Stale;
      memcpy(k, key, 32);
      return FrameErr::Ok;
    }, f, cmd);
    if (e == FrameErr::NotPaired || e == FrameErr::BadKey) { ans = "{\"err\":\"not paired\"}"; return 401; }
    if (e == FrameErr::Stale) { stale++; ans = "{\"err\":\"stale\",\"boot\":\"" + hexOf(bootId, 4) + "\"}"; return 409; }
    if (e != FrameErr::Ok) return 400;
    last = f.ctr;
    taken.push_back(f.ctr);
    if (waiting) { ans = "{\"err\":\"waiting\"}"; return 403; }
    uint8_t rnd[12] = {7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7};
    ans = replySeal(key, cid, f.nonce, rnd, "{\"ok\":1,\"cmd\":\"" + cmd + "\"}");
    return 200;
  }
  KeyState hubKey(uint8_t k[32], uint8_t c[8]) override {
    std::lock_guard<std::mutex> l(m);
    if (ks != KEY_NONE) { memcpy(k, key, 32); memcpy(c, cid, 8); }
    return ks;
  }
  void dropped() override { std::lock_guard<std::mutex> l(m); drops++; ks = KEY_NONE; }
  void letIn() override { std::lock_guard<std::mutex> l(m); letIns++; ks = KEY_IN; }
  uint64_t clockMs() override { return clock.load(); }
};

int main() {
  { FakeController c; CtrlLink link;
    CallResult r = link.call(c, "/api/s");
    CHECK(r.why == CallResult::OK && r.out == "{\"ok\":1,\"cmd\":\"/api/s\"}", "a command goes through and its answer opens");
    CHECK(c.hellos == 1 && c.commands == 1, "one hello first (the boot id), then the command");
    link.call(c, "/api/s");
    CHECK(c.hellos == 1, "the boot id is kept");
    CHECK(c.letIns == 0, "already let in: nothing to note"); }

  { FakeController c; CtrlLink link; c.ks = KEY_ASKED;
    CHECK(link.call(c, "/api/s").why == CallResult::OK && c.letIns == 1 && c.ks == KEY_IN, "a key that was waiting is let in at its first answer"); }

  { FakeController c; CtrlLink link; c.ks = KEY_NONE;
    CHECK(link.call(c, "/api/s").why == CallResult::NO_KEY && c.hellos == 0, "no key: nothing is sent"); }

  { FakeController c; CtrlLink link;
    link.call(c, "/api/s");
    c.restart();                                   // the controller restarted: the hub's boot id is old now
    CallResult r = link.call(c, "/api/go?b=0&t=50");
    CHECK(r.why == CallResult::OK && c.stale == 1 && c.hellos == 2, "restart: 409, hello again, then it goes through"); }

  { FakeController c; CtrlLink link;
    link.call(c, "/api/s");
    c.knowsKey = false;                            // the owner removed the hub
    CallResult r = link.call(c, "/api/s");
    CHECK(r.why == CallResult::DROPPED && r.st == 401 && c.drops == 1 && c.ks == KEY_NONE, "401 drops the key");
    CHECK(link.call(c, "/api/s").why == CallResult::NO_KEY, "and then nothing more is sent"); }

  { FakeController c; CtrlLink link; c.ks = KEY_ASKED; c.waiting = true;
    CHECK(link.call(c, "/api/s").why == CallResult::WAITING && c.letIns == 0, "still waiting for the owner"); }

  { FakeController c; CtrlLink link;
    link.call(c, "/api/s");
    c.clock = 1000;                                // the clock went back (no time yet after a restart)
    CHECK(link.call(c, "/api/s").why == CallResult::OK && c.stale == 0, "the counter rises even when the clock goes back"); }

  { FakeController c; CtrlLink link;              // a push says the controller has a new boot id
    link.call(c, "/api/s");
    c.restart();
    link.setBoot(c.bootId);
    CHECK(link.call(c, "/api/s").why == CallResult::OK && c.stale == 0 && c.hellos == 1, "a boot id from a push is used at once");
    link.forgetBoot();
    link.call(c, "/api/s");
    CHECK(c.hellos == 2, "a forgotten boot id (after an update): hello again"); }

  { FakeController c; CtrlLink link;              // moves, care and updates at once: the bug in #78
    const int T = 6, N = 40;
    std::atomic<int> ok{0};
    std::atomic<bool> stop{false};
    std::thread pushes([&] { while (!stop) { uint8_t b[4]; memcpy(b, c.bootId, 4); link.setBoot(b); std::this_thread::yield(); } });
    std::vector<std::thread> ts;
    for (int t = 0; t < T; t++) ts.emplace_back([&, t] { for (int i = 0; i < N; i++) if (link.call(c, "/api/s?t=" + std::to_string(t)).why == CallResult::OK) ok++; });
    for (auto &t : ts) t.join();
    stop = true;
    pushes.join();
    std::set<uint64_t> unique(c.taken.begin(), c.taken.end());
    bool rising = true;
    for (size_t i = 1; i < c.taken.size(); i++) rising = rising && c.taken[i] > c.taken[i - 1];
    CHECK(ok == T * N && c.stale == 0, "every command from every task goes through, none stale");
    CHECK(unique.size() == c.taken.size() && c.taken.size() == (size_t)(T * N) && rising, "two callers never share a counter, and counters arrive in order"); }

  printf("hub link: %d passed, %d failed\n", passed, failed);
  return failed ? 1 : 0;
}
