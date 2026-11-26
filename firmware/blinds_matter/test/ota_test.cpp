// Tests for main/ota.h: a firmware file through the Tilt Hub, and the keep-or-roll-back rule. Run on the Mac by
// tools/firmware_tests.sh, with the files test/make_ota_files.py made (signed by tools/release_firmware.py with a
// throwaway key):  ota_test DIR
#include "../main/ota.h"
#include <cstdio>
#include <fstream>
#include <set>
#include <sstream>
#include <string>
#include <vector>

static int passed = 0, failed = 0;
#define CHECK(cond, what) do { if (cond) passed++; else { failed++; printf("FAIL line %d: %s\n", __LINE__, what); } } while (0)

// ---- SHA-256 (FIPS 180-4), for the fake's hash of what was written
static void sha256(const std::string &m, uint8_t out[32]) {
  static const uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};
  uint32_t h[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
  std::string p = m;
  uint64_t bits = (uint64_t)m.size() * 8;
  p += (char)0x80;
  while (p.size() % 64 != 56) p += (char)0;
  for (int i = 7; i >= 0; i--) p += (char)(bits >> (i * 8));
  auto rr = [](uint32_t x, int n) { return (x >> n) | (x << (32 - n)); };
  for (size_t c = 0; c < p.size(); c += 64) {
    uint32_t w[64];
    for (int i = 0; i < 16; i++) w[i] = (uint32_t)(uint8_t)p[c + 4 * i] << 24 | (uint8_t)p[c + 4 * i + 1] << 16 | (uint8_t)p[c + 4 * i + 2] << 8 | (uint8_t)p[c + 4 * i + 3];
    for (int i = 16; i < 64; i++) {
      uint32_t s0 = rr(w[i - 15], 7) ^ rr(w[i - 15], 18) ^ (w[i - 15] >> 3), s1 = rr(w[i - 2], 17) ^ rr(w[i - 2], 19) ^ (w[i - 2] >> 10);
      w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    uint32_t a = h[0], b = h[1], cc = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
    for (int i = 0; i < 64; i++) {
      uint32_t t1 = hh + (rr(e, 6) ^ rr(e, 11) ^ rr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i];
      uint32_t t2 = (rr(a, 2) ^ rr(a, 13) ^ rr(a, 22)) + ((a & b) ^ (a & cc) ^ (b & cc));
      hh = g; g = f; f = e; e = d + t1; d = cc; cc = b; b = a; a = t1 + t2;
    }
    h[0] += a; h[1] += b; h[2] += cc; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
  }
  for (int i = 0; i < 8; i++) for (int j = 0; j < 4; j++) out[4 * i + j] = h[i] >> (24 - 8 * j);
}
static std::string hex(const uint8_t *b, size_t n) {
  std::string s; char t[3];
  for (size_t i = 0; i < n; i++) { snprintf(t, 3, "%02x", b[i]); s += t; }
  return s;
}

static std::string dir;
static std::string file(const char *name) {
  std::ifstream f(dir + "/" + name, std::ios::binary);
  std::stringstream ss; ss << f.rdbuf();
  return ss.str();
}

// A controller that keeps what is written in memory. The "release key" signed exactly the pairs in signed.txt; a
// patch is applied by copying it (make_ota_files.py puts the new image itself where the detools patch goes).
struct FakeSink : OtaSink {
  std::string image, running, calls;             // calls: what was asked of it, in order
  std::vector<std::string> events;
  std::set<std::string> signedPairs;
  bool patching = false, failOpen = false, failPatchFinish = false, booted = false, restart = false, radioOn = false;
  bool open() override { calls += "open "; image.clear(); return !failOpen; }
  bool openPatch() override { calls += "patch "; patching = true; return true; }
  bool write(const uint8_t *b, size_t n) override { image.append((const char *)b, n); return true; }
  bool finishPatch() override { calls += "finishpatch "; return !failPatchFinish; }
  void closePatch() override { calls += "closepatch "; patching = false; }
  void hash(uint8_t o[32]) override { sha256(image, o); }
  bool verify(const uint8_t h[32], const uint8_t sig[64]) override { return signedPairs.count(hex(h, 32) + " " + hex(sig, 64)) > 0; }
  bool finalize() override { calls += "finalize "; return true; }
  bool newVersion(std::string &v) override {
    if (image.size() < 80 || (uint8_t)image[32] != 0x32 || (uint8_t)image[35] != 0xAB) return false;   // the app description
    v = std::string(image.c_str() + 48);
    return true;
  }
  bool setBoot() override { calls += "boot "; booted = true; return true; }
  void abort() override { calls += "abort "; patching = false; }
  bool runningSha(uint8_t o[32]) override { memcpy(o, running.data() + running.size() - 32, 32); return true; }
  void radio(bool on) override { radioOn = on; calls += on ? "radio+ " : "radio- "; }
  void stopBlinds() override { calls += "stop "; }
  void fastPoll() override {}
  void accepted() override { calls += "accepted "; restart = true; }
  void log(const std::string &l) override { events.push_back(l); }
  bool logged(const char *s) const { for (auto &e : events) if (e.find(s) != std::string::npos) return true; return false; }
};
static FakeSink fresh() {
  FakeSink s;
  s.running = file("base.bin");
  std::istringstream in(file("signed.txt"));
  std::string a, b;
  while (in >> a >> b) s.signedPairs.insert(a + " " + b);
  return s;
}
static std::string piece(uint32_t off, const std::string &bytes) {
  std::string m(4, 0);
  m[0] = off >> 24; m[1] = off >> 16; m[2] = off >> 8; m[3] = off;
  return m + bytes;
}
const long EPOCH = 1795000000;
// Send a whole file in pieces of n; true if every piece was taken. Returns the 'E' answer in *end.
static bool sendAll(OtaReceiver &rx, const std::string &f, size_t n, uint32_t &t, OtaReply *end) {
  bool ok = true;
  for (size_t o = 0; o < f.size(); o += n) {
    OtaReply r = rx.piece(piece(o, f.substr(o, n)), t += 50);
    ok = ok && !strcmp(r.status, "200") && r.out == std::to_string(std::min(f.size(), o + n));
  }
  *end = rx.end(t += 50);
  return ok;
}

static void fullFile() {
  std::string f = file("new.bin.signed"), img = file("new.bin");
  // Every piece size puts the 72 bytes of signature at the end across a different piece boundary (4970 + 72 = 5042:
  // pieces of 1000 leave 42 bytes in the last one, so 30 of the tail come in the piece before).
  for (size_t n : {1000, 999, 1200, 37, 72, 73, 1}) {
    FakeSink s = fresh(); OtaReceiver rx(s, "2.3.0");
    uint32_t t = 1000;
    OtaReply b = rx.begin("5042@1795000000", EPOCH, true, t);
    CHECK(!strcmp(b.status, "200") && b.out == "0", "begin taken");
    CHECK(rx.going() && s.radioOn && s.calls == "stop open radio+ ", "the blinds stop, then the slot opens, then the radio stays on");
    OtaReply e;
    CHECK(sendAll(rx, f, n, t, &e), "every piece taken, the next offset each time");
    CHECK(!strcmp(e.status, "200") && e.out == "{\"ok\":1}", "a good file is accepted");
    CHECK(s.image == img, "exactly the image is written: none of the signature or its magic");
    CHECK(s.booted && s.restart && !s.radioOn && !rx.going(), "starts from it next, restarts, radio back to sleeping");
    CHECK(s.logged("signed update accepted") && s.logged("update through the hub: 5042@1795000000 bytes"), "logged");
  }
}

static void missedPiece() {
  std::string f = file("new.bin.signed");
  FakeSink s = fresh(); OtaReceiver rx(s, "2.3.0");
  rx.begin("5042", EPOCH, true, 1000);
  CHECK(!strcmp(rx.piece(piece(0, f.substr(0, 1000)), 1100).status, "200"), "first piece");
  OtaReply r = rx.piece(piece(2000, f.substr(2000, 1000)), 1200);
  CHECK(!strcmp(r.status, "409") && r.out == "1000", "a piece missed: 409 and where to start again");
  r = rx.piece(piece(0, f.substr(0, 1000)), 1250);
  CHECK(!strcmp(r.status, "409") && r.out == "1000", "a piece sent twice: 409, not written twice");
  uint32_t t = 1300;
  for (size_t o = 1000; o < f.size(); o += 1000) rx.piece(piece(o, f.substr(o, 1000)), t += 50);
  CHECK(!strcmp(rx.end(t).status, "200") && s.image == file("new.bin"), "sent again from there: accepted");
  FakeSink s2 = fresh(); OtaReceiver rx2(s2, "2.3.0");
  rx2.begin("5042", EPOCH, true, 1000);
  CHECK(!strcmp(rx2.piece(std::string(4, '\0'), 1100).status, "400") && rx2.going(), "an offset with no bytes after it: 400");
  CHECK(!strcmp(rx2.piece(piece(0, std::string(1201, 'x')), 1100).status, "400"), "a piece over 1200 bytes: 400");
  CHECK(!strcmp(rx2.piece(piece(0, f.substr(0, 1200)), 1100).status, "200"), "1200 bytes: taken");
}

static OtaReply sendFile(FakeSink &s, const std::string &f, const std::string &spec = "x", const char *running = "2.3.0") {
  OtaReceiver rx(s, running);
  rx.begin(spec, EPOCH, true, 1000);
  uint32_t t = 1000;
  OtaReply e;
  sendAll(rx, f, 1000, t, &e);
  return e;
}
static void refused() {
  std::string f = file("new.bin.signed");
  { FakeSink s = fresh(); OtaReply e = sendFile(s, file("new.bin"));
    CHECK(!strcmp(e.status, "403") && !s.booted && s.calls.find("abort") != std::string::npos && s.logged("bad signature"), "an unsigned file is refused"); }
  { FakeSink s = fresh(); std::string g = f; g[g.size() - 1] = '2';
    CHECK(!strcmp(sendFile(s, g).status, "403") && !s.booted, "a wrong magic at the end is refused"); }
  { FakeSink s = fresh(); std::string g = f; g[500] ^= 1;
    CHECK(!strcmp(sendFile(s, g).status, "403") && !s.booted, "one byte of the image changed: refused"); }
  { FakeSink s = fresh(); std::string g = f; g[g.size() - 72 + 5] ^= 1;
    CHECK(!strcmp(sendFile(s, g).status, "403") && !s.booted, "one byte of the signature changed: refused"); }
  { FakeSink s = fresh(); std::string g = f.substr(0, f.size() - 1);
    CHECK(!strcmp(sendFile(s, g).status, "403") && !s.booted, "a file cut short is refused"); }
  { FakeSink s = fresh(); OtaReply e = sendFile(s, file("old.bin.signed"));
    CHECK(!strcmp(e.status, "403") && e.out.find("older") != std::string::npos && !s.booted && s.logged("2.2.0 is older than 2.3.0"), "a signed but older firmware is refused"); }
  { FakeSink s = fresh(); OtaReply e = sendFile(s, f, "x", "2.4.0");
    CHECK(!strcmp(e.status, "200") && s.booted, "the same version again is taken"); }
  { FakeSink s = fresh(); std::string g = f; g[32] = 0;               // signed, but no app description in it
    s.signedPairs.clear(); uint8_t h[32]; sha256(g.substr(0, g.size() - 72), h);
    s.signedPairs.insert(hex(h, 32) + " " + hex((const uint8_t *)g.data() + g.size() - 72, 64));
    OtaReply e = sendFile(s, g);
    CHECK(!strcmp(e.status, "403") && !s.booted && s.logged("its version could not be read"), "a version that cannot be read is refused"); }
  { FakeSink s = fresh(); OtaReply e = sendFile(s, file("new.patch"));
    CHECK(!strcmp(e.status, "403") && !s.booted, "a patch sent as a full file is refused"); }
  { FakeSink s = fresh(); OtaReply e = sendFile(s, f, "x,d");
    CHECK(!strcmp(e.status, "500") && !s.booted, "a full file sent as a patch is refused"); }
}

static void patches() {
  { FakeSink s = fresh(); OtaReply e = sendFile(s, file("new.patch"), "5170,d@1795000000");
    CHECK(!strcmp(e.status, "200") && s.booted && s.image == file("new.bin"), "a patch for this firmware: the new image, accepted");
    CHECK(s.calls.find("open patch ") != std::string::npos && s.calls.find("finishpatch closepatch") != std::string::npos, "the patch is opened, finished and closed");
    CHECK(s.logged("5170 bytes (a patch)"), "logged as a patch"); }
  { FakeSink s = fresh(); OtaReceiver rx(s, "2.3.0");
    std::string f = file("other.patch");
    rx.begin("5170,d", EPOCH, true, 1000);
    OtaReply r = rx.piece(piece(0, f.substr(0, 1000)), 1100);
    CHECK(!strcmp(r.status, "500") && s.logged("the patch is for another firmware") && s.image.empty(), "a patch for another firmware: refused at its header");
    uint32_t t = 1100;
    for (size_t o = 1000; o < f.size(); o += 1000) rx.piece(piece(o, f.substr(o, 1000)), t += 50);
    OtaReply e = rx.end(t);
    CHECK(!strcmp(e.status, "500") && e.out.find("did not fit") != std::string::npos && !s.booted, "and at the end"); }
  { FakeSink s = fresh(); OtaReceiver rx(s, "2.3.0");   // the header split over pieces of 10
    std::string f = file("new.patch");
    rx.begin("5170,d", EPOCH, true, 1000);
    uint32_t t = 1000;
    OtaReply e;
    CHECK(sendAll(rx, f, 10, t, &e) && !strcmp(e.status, "200") && s.image == file("new.bin"), "a patch header split over pieces: the new image"); }
  { FakeSink s = fresh(); s.failPatchFinish = true; OtaReply e = sendFile(s, file("new.patch"), "x,d");
    CHECK(!strcmp(e.status, "500") && !s.booted && s.calls.find("abort") != std::string::npos, "a patch that does not finish: refused"); }
}

static void beginRules() {
  FakeSink s = fresh(); OtaReceiver rx(s, "2.3.0");
  CHECK(!strcmp(rx.begin("10", EPOCH, false, 1).status, "403") && !rx.going() && s.calls.empty(), "the owner has not allowed updates: refused, nothing touched");
  CHECK(!strcmp(rx.begin("10@1795000000", EPOCH, true, 1).status, "200"), "with the hub's time");
  CHECK(!strcmp(rx.begin("10@1795000000", EPOCH, true, 2).status, "403"), "the same begin again (a recording): refused");
  CHECK(!strcmp(rx.begin("10@1794999999", EPOCH, true, 3).status, "403"), "an older one: refused");
  CHECK(!strcmp(rx.begin("10@1795000700", EPOCH, true, 4).status, "403"), "10 minutes off this controller's clock: refused");
  CHECK(!strcmp(rx.begin("10@1795000700", 0, true, 5).status, "200"), "no clock here yet: only newer counts");
  CHECK(!strcmp(rx.begin("10", EPOCH, true, 6).status, "200"), "a hub from before the time: still taken");
  s.calls.clear();
  CHECK(!strcmp(rx.begin("10", EPOCH, true, 7).status, "200") && s.calls == "abort radio- stop open radio+ ", "a begin while one is going: the old one is dropped first");
  FakeSink s2 = fresh(); s2.failOpen = true; OtaReceiver rx2(s2, "2.3.0");
  CHECK(!strcmp(rx2.begin("10", EPOCH, true, 1).status, "500") && !rx2.going(), "the slot cannot be opened: 500");
  CHECK(!strcmp(rx2.piece(piece(0, "abc"), 2).status, "409") && !strcmp(rx2.end(3).status, "409"), "no update going: 409");
}

static void repeatedEnd() {
  FakeSink s = fresh(); OtaReceiver rx(s, "2.3.0");
  std::string f = file("new.bin.signed");
  rx.begin("x", EPOCH, true, 1000);
  uint32_t t = 1000;
  OtaReply e;
  sendAll(rx, f, 1000, t, &e);
  s.calls.clear();
  OtaReply again = rx.end(t + 5000);
  CHECK(!strcmp(again.status, "200") && again.out == e.out && s.calls.empty(), "its answer was lost: the same answer again, nothing done twice");
  CHECK(!strcmp(rx.end(t + 31000).status, "409"), "30 seconds later: no update going");
  FakeSink s2 = fresh(); OtaReceiver rx2(s2, "2.3.0");
  rx2.begin("x", EPOCH, true, 1000); t = 1000;
  sendAll(rx2, file("new.bin"), 1000, t, &e);
  CHECK(!strcmp(rx2.end(t + 100).status, "403"), "a refusal is repeated too");
}

static void stalled() {
  FakeSink s = fresh(); OtaReceiver rx(s, "2.3.0");
  rx.begin("x", EPOCH, true, 1000);
  rx.piece(piece(0, "abcdefgh"), 2000);
  CHECK(rx.busy(2000 + 29999) && !rx.stalled(2000 + 30000), "30 seconds with nothing: not yet");
  CHECK(!rx.stopIfStalled(2000 + 30000) && rx.going(), "and not stopped");
  CHECK(rx.stalled(2000 + 30001) && !rx.busy(2000 + 30001), "over 30 seconds: stalled");
  s.calls.clear();
  CHECK(rx.stopIfStalled(2000 + 30001) && !rx.going() && s.calls == "abort radio- " && s.logged("nothing came for 30 s"), "stopped: dropped, radio back to sleeping");
  CHECK(!strcmp(rx.piece(piece(8, "x"), 33000).status, "409"), "a piece after that: no update going");
  FakeSink s2 = fresh(); OtaReceiver rx2(s2, "2.3.0");
  rx2.begin("x", 0xFFFFF000u, true, 0xFFFFF000u);                 // millis wraps around while it waits
  CHECK(!rx2.stalled(0xFFFFF000u + 20000) && rx2.stalled(0xFFFFF000u + 30001), "the stall is timed across millis wrapping");
}

// Trial: the rule with its memory, ticked once a second as webTick does. A refused rollback is asked once, not every second.
struct TrialRun { int rollbacks = 0; uint32_t firstBack = 0, keptAt = 0; bool waitAfterBack = true; };
static TrialRun runTrial(uint32_t untilMs, uint32_t linkUpAt, bool refuse, bool hubJoined = true) {
  Trial t; TrialRun r;
  for (uint32_t now = 1000; now <= untilMs && !r.keptAt; now += 1000) {
    TrialVerdict v = t.tick(now, linkUpAt && now >= linkUpAt, hubJoined);
    if (v == TRIAL_ROLLBACK) { if (!r.rollbacks++) r.firstBack = now; if (refuse) t.rollbackRefused(); }
    else if (v == TRIAL_KEEP) r.keptAt = now;
    else if (r.rollbacks && v != TRIAL_WAIT) r.waitAfterBack = false;
  }
  return r;
}
static void trialWithMemory() {
  TrialRun a = runTrial(3600000, 0, true);
  CHECK(a.rollbacks == 1 && a.firstBack == 301000 && a.waitAfterBack && !a.keptAt, "a refused rollback: asked once, then wait for good");
  TrialRun b = runTrial(3600000, 600000, true);
  CHECK(b.rollbacks == 1 && b.firstBack == 301000 && b.keptAt == 661000, "refused, then the link comes up at 10 minutes: kept a minute later");
  TrialRun c = runTrial(3600000, 0, false);
  CHECK(c.rollbacks == 3300 && c.firstBack == 301000 && !c.keptAt, "not refused: the rule still answers go back on every tick after 5 minutes");
  // The link comes up at 20 s, drops at 50 s, is back at 100 s: the same answer as the free functions.
  Trial t; uint32_t keptAt = 0, backAt = 0;
  for (uint32_t now = 1000; now < 400000 && !keptAt && !backAt; now += 1000) {
    TrialVerdict v = t.tick(now, (now >= 20000 && now < 50000) || now >= 100000, true);
    if (v == TRIAL_KEEP) keptAt = now;
    if (v == TRIAL_ROLLBACK) backAt = now;
  }
  CHECK(keptAt == 161000 && !backAt, "Trial: a dropped link starts the minute again");
  TrialRun d = runTrial(900000, 0, true, false);
  CHECK(!d.rollbacks && !d.keptAt, "Trial: not set up with a hub yet: wait for 15 minutes");
}

static void trial() {
  CHECK(trialVerdict(1000, 0, true) == TRIAL_WAIT, "just started: wait");
  CHECK(trialVerdict(300000, 0, true) == TRIAL_WAIT && trialVerdict(300001, 0, true) == TRIAL_ROLLBACK, "no hub for 5 minutes: back to the one before");
  CHECK(trialVerdict(900000, 0, false) == TRIAL_WAIT, "not set up with a hub yet: never rolled back");
  CHECK(trialVerdict(70000, 10000, true) == TRIAL_WAIT && trialVerdict(70001, 10000, true) == TRIAL_KEEP, "the link up for a minute: kept");
  CHECK(trialVerdict(900000, 899000, true) == TRIAL_WAIT, "the link just came up late: wait, no roll back");
  CHECK(trialLinkUp(true, 0, 5000) && trialLinkUp(false, 1000, 120999) && !trialLinkUp(false, 1000, 121000) && !trialLinkUp(false, 0, 5000), "the link: the hub, or Thread to it in the last 2 minutes");
  // Second by second, as webTick runs it: the link comes up at 20 s, drops at 50 s, is back at 100 s.
  uint32_t since = 0, keptAt = 0, backAt = 0;
  for (uint32_t now = 1000; now < 400000 && !keptAt && !backAt; now += 1000) {
    bool up = (now >= 20000 && now < 50000) || now >= 100000;
    since = trialLinkSince(since, up, now);
    TrialVerdict v = trialVerdict(now, since, true);
    if (v == TRIAL_KEEP) keptAt = now;
    if (v == TRIAL_ROLLBACK) backAt = now;
  }
  CHECK(keptAt == 161000 && !backAt, "a dropped link starts the minute again");
  since = 0; keptAt = backAt = 0;
  for (uint32_t now = 1000; now < 400000 && !keptAt && !backAt; now += 1000) {
    since = trialLinkSince(since, false, now);
    TrialVerdict v = trialVerdict(now, since, true);
    if (v == TRIAL_KEEP) keptAt = now;
    if (v == TRIAL_ROLLBACK) backAt = now;
  }
  CHECK(backAt == 301000 && !keptAt, "never reached the hub: back at 5 minutes");
  CHECK(trialLinkSince(0, true, 0) == 1, "up at millis 0 still counts as up");
  trialWithMemory();
}

int main(int argc, char **argv) {
  if (argc < 2) { printf("usage: ota_test DIR (made by make_ota_files.py)\n"); return 2; }
  dir = argv[1];
  if (file("signed.txt").empty()) { printf("no test files in %s\n", dir.c_str()); return 2; }
  fullFile();
  missedPiece();
  refused();
  patches();
  beginRules();
  repeatedEnd();
  stalled();
  trial();
  printf("ota: %d passed, %d failed\n", passed, failed);
  return failed ? 1 : 0;
}
