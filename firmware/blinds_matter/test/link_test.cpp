// Tests for main/tilt_link.h (the hub link both firmwares share), run on the Mac: tools/firmware_tests.sh. No hardware,
// no ESP-IDF: the crypto is test/host_mbedtls (a stand-in for mbedtls), checked here against test/wire/link.json, which
// tools/link_vectors.py made with Python's 'cryptography' (and the app's tests read too).
#include "../main/tilt_link.h"
#include <cstdio>
#include <fstream>
#include <map>
#include <sstream>

static int passed = 0, failed = 0;
#define CHECK(cond, what) do { if (cond) passed++; else { failed++; printf("FAIL line %d: %s\n", __LINE__, what); } } while (0)

// A flat JSON object of strings (wire/link.json), with \" and \\ undone.
static std::map<std::string, std::string> readVectors(const char *path) {
  std::ifstream f(path);
  std::stringstream ss;
  ss << f.rdbuf();
  std::string j = ss.str();
  std::map<std::string, std::string> v;
  size_t i = 0;
  auto str = [&](std::string &out) {
    i = j.find('"', i);
    if (i == std::string::npos) return false;
    out.clear();
    for (i++; i < j.size() && j[i] != '"'; i++) {
      if (j[i] == '\\' && i + 1 < j.size()) { i++; out += j[i] == 'n' ? '\n' : j[i]; }
      else out += j[i];
    }
    i++;
    return i <= j.size();
  };
  std::string k, x;
  while (str(k) && str(x)) v[k] = x;
  return v;
}
static std::string bytes(const std::string &hex) {
  std::string b(hex.size() / 2, 0);
  if (!unhex(hex, (uint8_t *)&b[0], b.size())) return "";
  return b;
}
static const uint8_t *u8(const std::string &s) { return (const uint8_t *)s.data(); }

static void proofTests(std::map<std::string, std::string> &v) {
  std::string hubKey = bytes(v["hubKey"]), boot = bytes(v["boot"]);
  uint8_t link[32];
  CHECK(linkKey(u8(hubKey), link) && hexOf(link, 32) == v["linkKey"], "the link key");
  CHECK(proof(link, Proof::CtlPush, u8(boot), v["pushJson"] + v["pushN"]) == v["proofPush"], "a push's proof");
  CHECK(proof(link, Proof::CtlBye, u8(boot), "") == v["proofBye"], "a goodbye's proof");
  CHECK(proof(link, Proof::HubTime, u8(boot), v["timeMsg"]) == v["proofTime"], "the time's proof");
  CHECK(proof(link, Proof::HubOta, u8(boot), v["otaMsg"]) == v["proofOta"], "an update begin's proof");
  CHECK(proofOk(link, Proof::HubTime, u8(boot), v["timeMsg"], v["proofTime"]), "a good proof checks out");
  CHECK(!proofOk(link, Proof::HubOta, u8(boot), v["timeMsg"], v["proofTime"]), "another label's proof does not");
  std::string bad = v["proofTime"];
  bad[0] = bad[0] == '0' ? '1' : '0';
  CHECK(!proofOk(link, Proof::HubTime, u8(boot), v["timeMsg"], bad) && !proofOk(link, Proof::HubTime, u8(boot), v["timeMsg"], ""), "a changed or empty proof does not");
  uint8_t other[4] = {1, 2, 3, 4};
  CHECK(!proofOk(link, Proof::HubTime, other, v["timeMsg"], v["proofTime"]), "another boot id's proof does not");
  // the push as it goes on the air, and back
  std::string dg = dgEncode(DG_PUSH, 0x3030, pushPayload(v["pushJson"], (uint32_t)atoi(v["pushN"].c_str()), v["proofPush"]));
  CHECK(hexOf(u8(dg), (int)dg.size()) == v["pushDatagram"], "the push datagram");
  Datagram d;
  CHECK(dgParse(dg.data(), dg.size(), d) && d.type == DG_PUSH, "a push parses");
  PushIn p = pushParse(d.payload);
  CHECK(p.json == v["pushJson"] && p.n == 12 && p.mac == v["proofPush"], "a push's JSON, count and proof");
  PushIn plain = pushParse(v["pushJson"]);
  CHECK(plain.json == v["pushJson"] && plain.n == 0 && plain.mac.empty(), "a push without a proof (setup)");
  CHECK(pushPayload("{}", 3, "") == "{}", "no key, no proof");
}

static void frameTests(std::map<std::string, std::string> &v) {
  std::string shared = bytes(v["shared"]), cpub = bytes(v["cpub"]), dpub = bytes(v["dpub"]), cid = bytes(v["cid"]), boot = bytes(v["boot"]);
  uint8_t key[32], salted[32];
  CHECK(deriveKey(u8(shared), "", u8(cpub), u8(dpub), key) && hexOf(key, 32) == v["key"], "the pairing key");
  CHECK(deriveKey(u8(shared), v["salt"], u8(cpub), u8(dpub), salted) && hexOf(salted, 32) == v["keySalted"], "the pairing key with the setup code");
  uint64_t ctr = strtoull(v["ctr"].c_str(), nullptr, 10);
  std::string f1 = frameSeal(key, u8(cid), u8(boot), ctr, v["cmd"]), f2 = frameSeal(salted, u8(cid), u8(boot), ctr, v["cmd"]);
  CHECK(hexOf(u8(f1), (int)f1.size()) == v["frame"], "a sealed command");
  CHECK(hexOf(u8(f2), (int)f2.size()) == v["frameSalted"], "a sealed command with the salted key");
  // opening, as a controller does: look the client id up, check the counter, then decrypt
  uint64_t last = 0;
  auto find = [&](const Frame &f, uint8_t k[32]) {
    if (memcmp(f.cid, cid.data(), 8)) return FrameErr::NotPaired;
    if (memcmp(f.nonce, boot.data(), 4) || f.ctr <= last) return FrameErr::Stale;
    memcpy(k, key, 32);
    return FrameErr::Ok;
  };
  Frame fr;
  std::string cmd;
  CHECK(frameOpen(f1, find, fr, cmd) == FrameErr::Ok && cmd == v["cmd"] && fr.ctr == ctr, "a command opens, with its counter");
  last = ctr;
  CHECK(frameOpen(f1, find, fr, cmd) == FrameErr::Stale, "the same command again is stale");
  last = 0;
  CHECK(frameOpen(f2, find, fr, cmd) == FrameErr::BadKey && cmd.empty(), "the other key's command does not open");
  std::string bent = f1;
  bent[25] ^= 1;
  CHECK(frameOpen(bent, find, fr, cmd) == FrameErr::BadKey, "a changed command does not open");
  CHECK(frameOpen(f1.substr(0, FRAME_MIN - 1), find, fr, cmd) == FrameErr::Short, "too short");
  std::string other = f1;
  other[0] ^= 1;
  CHECK(frameOpen(other, find, fr, cmd) == FrameErr::NotPaired, "an unknown client id");
  // the reply
  std::string rnd = bytes(v["replyRnd"]), r = replySeal(key, u8(cid), u8(f1) + 8, u8(rnd), v["replyOut"]), out;
  CHECK(hexOf(u8(r), (int)r.size()) == v["reply"], "a sealed reply");
  CHECK(replyOpen(key, u8(cid), u8(f1) + 8, r, out) && out == v["replyOut"], "the reply opens");
  std::string otherNonce = f1.substr(8, 12);
  otherNonce[11] ^= 1;
  CHECK(!replyOpen(key, u8(cid), u8(otherNonce), r, out) && out.empty(), "a reply to another command's nonce does not");
  CHECK(!replyOpen(key, u8(cid), u8(f1) + 8, r.substr(0, 27), out), "a reply too short");
}

static void pushTests() {
  PushState s;                                    // a controller that has let the hub in, before its first proven push
  PushResult r = pushAccept(s, false, 3, "aaaa0001", 0);
  CHECK(r.verdict == PushVerdict::TakeUnproven && !r.save && !r.state.on, "before the first proven push: one without a proof is taken");
  r = pushAccept(r.state, true, 3, "aaaa0001", 1);
  CHECK(r.verdict == PushVerdict::Take && r.save && r.state.on && r.state.bn == 3 && r.state.n == 1, "the first proven push is taken and saved");
  s = r.state;
  CHECK(pushAccept(s, false, 3, "aaaa0001", 0).verdict == PushVerdict::Refuse, "after it: one without a proof is refused");
  CHECK(pushAccept(s, true, 3, "aaaa0001", 1).verdict == PushVerdict::Refuse, "a replayed push is refused");
  r = pushAccept(s, true, 3, "aaaa0001", 2);
  CHECK(r.verdict == PushVerdict::Take && !r.save && r.state.n == 2, "the next count is taken (no flash write)");
  s = r.state;
  CHECK(pushAccept(s, true, 2, "bbbb0002", 50).verdict == PushVerdict::Refuse, "an older boot count is refused");
  r = pushAccept(s, true, 3, "cccc0003", 1);
  CHECK(r.verdict == PushVerdict::Take && r.state.boot == "cccc0003" && r.state.n == 1, "a new boot id with the same boot count is taken");
  r = pushAccept(r.state, true, 4, "dddd0004", 1);
  CHECK(r.verdict == PushVerdict::Take && r.save && r.state.bn == 4, "a newer boot count is taken and saved");
  CHECK(pushAccept(PushState{}, true, 0, "", 0).verdict == PushVerdict::Refuse, "a proven push that is not fresh is refused, even before");
}

static void datagramTests() {
  const char types[] = {DG_HELLO, DG_COMMAND, DG_ASK, DG_PAIR, DG_BEGIN, DG_PIECE, DG_END, DG_TIME, DG_PUSH, DG_LOG, DG_BYE, DG_PIECES};
  bool all = true;
  for (char t : types) {
    std::string payload = std::string("x\0y", 3) + t, m = dgEncode(t, 0xBEEF, payload);
    Datagram d;
    all = all && m.size() == 3 + payload.size() && dgParse(m.data(), m.size(), d) && d.type == t && d.seq == 0xBEEF && d.payload == payload;
  }
  CHECK(all, "every datagram type round-trips");
  Datagram d;
  CHECK(!dgParse("H0", 2, d), "too short to be a datagram");
  CHECK(dgReply(DG_HELLO) == 'h' && dgReply(DG_COMMAND) == 'x', "an answer is the type in lower case");
  std::string ans;
  CHECK(dgStatus(dgAnswer(409, "{\"err\":\"stale\"}"), ans) == 409 && ans == "{\"err\":\"stale\"}", "a status and its answer");
  CHECK(dgStatus("20", ans) == 0 && dgStatus("ok!", ans) == 0, "no status");
  // long answers: pieces, joined in any order
  std::string body = "200";
  for (int i = 0; i < 2500; i++) body += (char)('a' + i % 26);
  std::vector<std::string> ds = dgAnswerDatagrams(DG_HELLO, 7, body);
  CHECK(ds.size() == 3 && ds[0][0] == DG_PIECES && (uint8_t)ds[0][4] == 3, "a long answer goes in pieces");
  PieceJoin j;
  std::string joined;
  Datagram p0, p1, p2;
  dgParse(ds[0].data(), ds[0].size(), p0); dgParse(ds[1].data(), ds[1].size(), p1); dgParse(ds[2].data(), ds[2].size(), p2);
  CHECK(j.add(p2.payload, joined) == PieceJoin::MORE && j.add(p0.payload, joined) == PieceJoin::MORE && j.add(p1.payload, joined) == PieceJoin::DONE &&
        joined == body && p0.seq == 7, "the pieces join back, in any order");
  CHECK(j.count == 0 && j.have == 0, "a done join is clean again");
  std::string bad = p0.payload;
  bad[1] = 1;
  CHECK(j.add(bad, joined) == PieceJoin::BAD, "a count of one is not a piece");
  j.add(p0.payload, joined);
  std::string other = p1.payload;
  other[1] = 4;
  CHECK(j.add(other, joined) == PieceJoin::BAD, "a piece of another count is ignored");
  std::vector<std::string> one = dgAnswerDatagrams(DG_COMMAND, 9, "200{}");
  CHECK(one.size() == 1 && one[0] == dgEncode('x', 9, "200{}"), "a short answer is one datagram");
  CHECK(dgAnswerDatagrams(DG_HELLO, 1, std::string(LINK_PIECE * LINK_PIECES_MAX + 1, 'z')).empty(), "too long for the hub");
  CHECK(std::string(statusLine(409)) == "409 Conflict" && std::string(statusLine(410)) == "410 Gone" && std::string(statusLine(0)) == "504 Gateway Timeout",
        "the status lines");
  CHECK(linkJsonStr("{\"id\":\"x\",\"boot\":\"a1b2c3d4\"}", "boot") == "a1b2c3d4" && linkJsonStr("{}", "boot").empty(), "a hello's boot id");
}

int main() {
  std::map<std::string, std::string> v = readVectors("wire/link.json");
  CHECK(v.size() >= 20, "wire/link.json is there");
  proofTests(v);
  frameTests(v);
  pushTests();
  datagramTests();
  printf("link: %d passed, %d failed\n", passed, failed);
  return failed ? 1 : 0;
}
