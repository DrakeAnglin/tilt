// Tests for the Tilt Hub's people rules (main/hub_people.h), update-file checks (main/hub_file.h) and its rule for new
// firmware on trial (blinds_matter/main/trial.h, as main/hub_care.h runs it), run on the Mac:
// tools/firmware_tests.sh. No hardware, no ESP-IDF. The update files in files/ were made by tools/release_firmware.py
// with a test key (make_files.sh).
#include "../main/hub_people.h"
#include "../main/hub_file.h"
#include "trial.h"                               // the trial rule both firmwares share (blinds_matter/main)
#include "../../blinds_matter/main/fwkey.h"     // FW_SIGN_PUB: the release key, here only as "another key"
#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

static int passed = 0, failed = 0;
#define CHECK(cond, what) do { if (cond) passed++; else { failed++; printf("FAIL line %d: %s\n", __LINE__, what); } } while (0)
static bool same(const char *a, const char *b) { return (!a && !b) || (a && b && !strcmp(a, b)); }

// ---- people
static uint32_t fakeNow = 1000;
static uint32_t fakeClock() { return fakeNow; }
static int saves = 0;
static void countSave(const HubPeople &) { saves++; }

static HubPeople fresh() { HubPeople p; p.clock = fakeClock; p.save = countSave; return p; }
static void idOf(uint8_t n, uint8_t id[8]) { memset(id, 0, 8); id[0] = n; }
// A phone that is in (role 1: an owner), as the hub keeps it.
static int addIn(HubPeople &p, uint8_t n, bool owner) {
  uint8_t id[8], key[32] = {0};
  idOf(n, id);
  int s = -1, st = 0; const char *err = nullptr;
  s = p.pairPlace(false, st, err);
  p.pairTake(s, false, owner, id, key, "phone");
  p.keys[s].used = HK_IN;
  return s;
}
// A phone that asked to join and waits.
static int addAsked(HubPeople &p, uint8_t n) {
  uint8_t id[8], key[32] = {0};
  idOf(n, id);
  int st = 0; const char *err = nullptr;
  int s = p.pairPlace(true, st, err);
  if (s >= 0) p.pairTake(s, true, false, id, key, "asker");
  return s;
}
static int owners(const HubPeople &p) { int n = 0; for (auto &k : p.keys) if (k.used == HK_IN && k.role == 1) n++; return n; }

static void permitTests() {
  CHECK(!hubPermit("/api/net", HUB_OWNER) && !hubPermit("/api/resetpeople", HUB_OWNER), "owner: anything");
  for (const char *ok : {"/api/info", "/api/keys", "/api/leave"}) CHECK(!hubPermit(ok, HUB_USER), "user: see the hub and its people, leave");
  for (const char *no : {"/api/approve", "/api/revoke", "/api/makeowner", "/api/resetpeople", "/api/net", "/api/hubupdate", "/api/upload", "/api/homecode", "/api/backup", "/nope"})
    CHECK(same(hubPermit(no, HUB_USER), "only the hub's owner can do that"), "user: not the owner's commands");
  CHECK(!hubPermit("/api/leave", HUB_WAITING), "waiting: may leave");
  for (const char *no : {"/api/info", "/api/keys", "/api/net", "/api/leave?x=1"}) CHECK(same(hubPermit(no, HUB_WAITING), "waiting"), "waiting: nothing but leave");
  CHECK(!hubPermit("/api/keyname", HUB_OWNER) && !hubPermit("/api/keyname", HUB_USER), "owner and Guest: may rename their own phone");
  CHECK(same(hubPermit("/api/keyname", HUB_WAITING), "waiting"), "waiting: may not rename");
}

// ---- phone names: kept as typed (wire.h keptName), 19 bytes at most
static std::string fakeCode(const uint8_t key[32]) { return std::string("c") + std::to_string(key[0]); }
static void nameTests() {
  const char *mom = "Mom\xE2\x80\x99s \"caf\xC3\xA9\"";
  // A rename as the app sends it (HubApi.rename: percent-encoded), read the way hubCommand reads it (wire.h queryValue).
  { HubPeople p = fresh(); int a = addIn(p, 1, true);
    for (auto c : {std::make_pair("name=O%E2%80%99Brien", "O\xE2\x80\x99" "Brien"), std::make_pair("name=John%20Smith", "John Smith"),
                   std::make_pair("name=Mom%E2%80%99s%20%22caf%C3%A9%22", "Mom\xE2\x80\x99s \"caf\xC3\xA9\"")}) {
      CHECK(!p.rename(a, queryValue(c.first, "name").c_str()) && !strcmp(p.keys[a].name, c.second), "a rename from the app's command is kept decoded");
      if (strcmp(p.keys[a].name, c.second)) printf("  got: %s\n", p.keys[a].name);
    } }
  { HubPeople p = fresh(); uint8_t id[8], key[32] = {0}; idOf(1, id);
    p.pairTake(0, false, true, id, key, mom);
    CHECK(!strcmp(p.keys[0].name, mom), "a name with a curly apostrophe, quotes and an accent is kept byte for byte");
    // 15 letters and a 4-byte emoji, then more: 30 bytes in all
    p.pairTake(1, true, false, id, key, "aaaaaaaaaaaaaaa\xF0\x9F\x8E\xAC" "bbbbbbbbbbb");
    CHECK(!strcmp(p.keys[1].name, "aaaaaaaaaaaaaaa\xF0\x9F\x8E\xAC"), "a long name: 19 bytes, the emoji whole");
    p.pairTake(2, true, false, id, key, "aaaaaaaaaaaaaaaaa\xF0\x9F\x8E\xAC");
    CHECK(!strcmp(p.keys[2].name, "aaaaaaaaaaaaaaaaa"), "a name one emoji too long: cut before the emoji, never inside it");
    p.pairTake(3, true, false, id, key, "");
    CHECK(!strcmp(p.keys[3].name, "iPhone"), "no name: iPhone");
    p.pairTake(3, true, false, id, key, "\x01\x02");
    CHECK(!strcmp(p.keys[3].name, "iPhone"), "only control characters: iPhone"); }

  { HubPeople p = fresh(); int a = addIn(p, 1, true), b = addIn(p, 2, false);
    saves = 0;
    CHECK(!p.rename(b, "O\xE2\x80\x99" "Brien") && !strcmp(p.keys[b].name, "O\xE2\x80\x99" "Brien"), "a Guest renames itself, as typed");
    CHECK(!strcmp(p.keys[a].name, "phone") && saves == 1, "only the caller's name changes, saved once");
    saves = 0;
    CHECK(same(p.rename(b, "\x01\n\t"), "a name is needed") && !strcmp(p.keys[b].name, "O\xE2\x80\x99" "Brien") && saves == 0,
          "a name of only control characters: refused, nothing changed"); }

  { HubPeople p = fresh(); int a = addIn(p, 1, true);
    p.rename(a, mom);
    uint8_t wid[8], wkey[32] = {7}; idOf(2, wid);
    int st = 0; const char *err = nullptr;
    int w = p.pairPlace(true, st, err);
    p.pairTake(w, true, false, wid, wkey, "Den\\Kid");          // a Join request
    std::string want = "{\"ok\":1,\"keys\":[{\"cid\":\"0100000000000000\",\"name\":\"Mom\xE2\x80\x99s \\\"caf\xC3\xA9\\\"\",\"owner\":1,\"me\":1,\"wait\":0,\"code\":\"\"},"
                       "{\"cid\":\"0200000000000000\",\"name\":\"Den\\\\Kid\",\"owner\":0,\"me\":0,\"wait\":1,\"code\":\"c7\"}]}";
    std::string got = p.listJson(a, true, fakeCode);
    CHECK(got == want, "the people list: quotes and \\ escaped, me marked, the join code for an owner");
    if (got != want) printf("  got: %s\n", got.c_str());
    int g = addIn(p, 3, false);
    std::string guest = p.listJson(g, false, fakeCode);
    CHECK(guest.find("\"code\":\"\"},{\"cid\":\"0300000000000000\",\"name\":\"phone\",\"owner\":0,\"me\":1") != std::string::npos &&
          guest.find("c7") == std::string::npos, "a Guest: no join code; its own row marked me");
    memcpy(p.keys[a].name, "Lin\xC3\xA9" "aaaaaaaaaaaaaa", 19);   // an old hub name, cut at 19 bytes inside a character
    p.keys[a].name[18] = '\xC3';
    CHECK(p.listJson(a, true, fakeCode).find("\"name\":\"Lin\xC3\xA9" "aaaaaaaaaaaaa\"") != std::string::npos, "a name cut inside a character: the broken byte is not written"); }
}

static void pairTests() {
  { HubPeople p = fresh(); bool first; const char *err;
    CHECK(p.pairGate(true, first, err) == 403 && first && same(err, "this hub has no owner yet: connect to it"), "no owner: no asking to join");
    CHECK(p.pairGate(false, first, err) == 0 && first, "no owner: the first phone may connect"); }
  { HubPeople p = fresh(); addIn(p, 1, true); bool first; const char *err;
    CHECK(p.pairGate(false, first, err) == 403 && !first && same(err, "this hub has an owner. Ask to join from the app."), "an owner: nobody else claims it");
    CHECK(p.pairGate(true, first, err) == 0, "an owner: others may ask");
    fakeNow += 5000;
    CHECK(p.pairGate(true, first, err) == 429 && same(err, "try again in a few seconds"), "asks: one per 10 s");
    fakeNow += 6000;
    CHECK(p.pairGate(true, first, err) == 0, "asks: again after 10 s"); }
  // A claim (the first owner, until its setup code proves right) holds the hub for 60 s.
  { HubPeople p = fresh(); bool first; const char *err; int st;
    uint8_t id[8], key[32] = {0}; idOf(7, id);
    int s = p.pairPlace(false, st, err);
    p.pairTake(s, false, true, id, key, "");
    CHECK(p.keys[s].used == HK_CLAIM && p.keys[s].role == 1 && !strcmp(p.keys[s].name, "iPhone") && !p.owned(), "claim: held, named iPhone, not the owner yet");
    fakeNow += 59999;
    CHECK(p.pairGate(false, first, err) == 409 && same(err, "someone else is connecting to this hub: try again in a minute"), "claim: others wait within 60 s");
    fakeNow += 1;
    CHECK(p.pairGate(false, first, err) == 0 && !p.keys[s].used, "claim: expires after 60 s, the place goes"); }
  // The right code: the owner. Saved.
  { HubPeople p = fresh(); int st; const char *err; uint8_t id[8], key[32] = {0}; idOf(7, id);
    int s = p.pairPlace(false, st, err); p.pairTake(s, false, true, id, key, "Ann");
    p.pinFails = 3; saves = 0;
    CHECK(p.opened(s, 42) && p.owned() && p.last[s] == 42 && p.pinFails == 0 && saves == 1, "claim: the right code makes the owner");
    CHECK(!p.opened(s, 43) && p.last[s] == 43, "in: a command just moves the counter on");
    CHECK(p.find(id) == s, "find: by id"); }
}

static void lockoutTests() {
  HubPeople p = fresh(); bool first; const char *err; int st;
  uint8_t key[32] = {0};
  for (int n = 1; n <= 5; n++) {
    CHECK(p.pairGate(false, first, err) == 0, "wrong codes: may try again");
    uint8_t id[8]; idOf(n, id);
    int s = p.pairPlace(false, st, err); p.pairTake(s, false, true, id, key, "x");
    CHECK(p.openFailed(s) && !p.keys[s].used, "wrong code: the place goes");
  }
  CHECK(p.pinLockUntil && p.pinFails == 0, "five wrong codes: locked");
  CHECK(p.pairGate(false, first, err) == 429 && same(err, "too many wrong codes: try again in a few minutes"), "locked: no connecting");
  fakeNow += 299999;
  CHECK(p.pairGate(false, first, err) == 429, "locked: still within 5 minutes");
  fakeNow += 2;                                 // the end is marked odd: 300000 or 300001 ms
  CHECK(p.pairGate(false, first, err) == 0, "locked: open again after 5 minutes");
  // Not a claim: a bad key is just refused.
  HubPeople q = fresh(); int s = addIn(q, 1, true);
  CHECK(!q.openFailed(s) && q.keys[s].used == HK_IN && q.pinFails == 0, "a phone that is in with a bad message stays");
  // Four wrong codes then the right one: the count starts again.
  HubPeople r = fresh();
  for (int n = 1; n <= 4; n++) { uint8_t id[8]; idOf(n, id); int t = r.pairPlace(false, st, err); r.pairTake(t, false, true, id, key, "x"); r.openFailed(t); }
  { uint8_t id[8]; idOf(9, id); int t = r.pairPlace(false, st, err); r.pairTake(t, false, true, id, key, "x"); r.opened(t, 1); }
  CHECK(r.pinFails == 0 && !r.pinLockUntil, "the right code: wrong codes forgotten");
}

static void waitingTests() {
  HubPeople p = fresh(); addIn(p, 1, true);
  int st; const char *err;
  int a = addAsked(p, 2);
  fakeNow += 1000;
  int b = addAsked(p, 3);
  CHECK(a >= 0 && b >= 0 && p.role(a) == HUB_WAITING && p.keys[a].used == HK_ASKED, "two may wait");
  CHECK(p.pairPlace(true, st, err) < 0 && st == 429 && same(err, "two requests are waiting already. Try again later."), "a third waits for room");
  fakeNow += 600001;
  CHECK(p.pairPlace(true, st, err) == a, "after 10 minutes a new ask takes the oldest place");
  saves = 0;
  p.forget(b);
  CHECK(!p.keys[b].used && saves == 1, "a waiting phone that leaves is forgotten");
  // No room: eight places.
  HubPeople f = fresh();
  for (int n = 1; n <= HUB_KEYS; n++) addIn(f, n, n == 1);
  CHECK(f.pairPlace(false, st, err) < 0 && st == 403 && same(err, "no room for another phone"), "no room for a ninth");
}

static void peopleOpTests() {
  uint8_t id[8];
  // The only owner can't leave while others remain.
  { HubPeople p = fresh(); int o = addIn(p, 1, true); int u = addIn(p, 2, false);
    PeopleResult r = p.apply(PO_LEAVE, o);
    CHECK(same(r.err, "you are the hub's only owner: make someone else an owner first, or reset its people") && p.keys[o].used, "the only owner can't leave others behind");
    int w = addAsked(p, 3); (void)w;
    CHECK(!p.apply(PO_LEAVE, u).err && !p.keys[u].used, "a user may leave");
    CHECK(p.apply(PO_LEAVE, o).err, "a waiting phone counts as someone left behind");
    idOf(3, id); p.apply(PO_DENY, o, id);
    saves = 0;
    CHECK(!p.apply(PO_LEAVE, o).err && !p.owned() && saves == 1, "the last phone may leave: no owner, saved"); }
  { HubPeople p = fresh(); int o = addIn(p, 1, true); addIn(p, 2, true);
    CHECK(!p.apply(PO_LEAVE, o).err && p.owned(), "one of two owners may leave"); }
  // Revoke and makeowner never leave zero owners.
  { HubPeople p = fresh(); int o = addIn(p, 1, true); int u = addIn(p, 2, false);
    idOf(1, id);
    CHECK(same(p.apply(PO_UNOWNER, o, id).err, "the hub needs an owner: make someone else an owner first") && p.keys[o].role == 1, "the last owner stays an owner");
    CHECK(same(p.apply(PO_REVOKE, o, id).err, "you cannot remove yourself") && p.keys[o].used, "you cannot remove yourself");
    idOf(2, id);
    CHECK(!p.apply(PO_MAKEOWNER, o, id).err && p.keys[u].role == 1 && owners(p) == 2, "make a second owner");
    idOf(1, id);
    CHECK(!p.apply(PO_REVOKE, u, id).err && !p.keys[o].used && owners(p) == 1, "an owner removes another");
    idOf(2, id);
    CHECK(p.apply(PO_UNOWNER, u, id).err && owners(p) == 1, "still never zero owners");
    idOf(9, id);
    CHECK(same(p.apply(PO_REVOKE, u, id).err, "no such phone"), "revoke: no such phone"); }
  // Approve and deny: only a phone that waits.
  { HubPeople p = fresh(); int o = addIn(p, 1, true); int u = addIn(p, 2, false);
    int a = addAsked(p, 3);
    p.last[a] = 99;
    idOf(2, id);
    CHECK(same(p.apply(PO_APPROVE, o, id).err, "no such phone") && p.keys[u].role == 0, "approve: only one that waits");
    idOf(3, id);
    PeopleResult r = p.apply(PO_APPROVE, o, id, true);
    CHECK(!r.err && !strcmp(r.name, "asker") && p.role(a) == HUB_OWNER && p.last[a] == 0, "approve as an owner");
    fakeNow += 20000;
    int b = addAsked(p, 4); idOf(4, id);
    CHECK(!p.apply(PO_APPROVE, o, id, false).err && p.role(b) == HUB_USER, "approve as a user");
    fakeNow += 20000;
    int c = addAsked(p, 5); idOf(5, id);
    CHECK(!p.apply(PO_DENY, o, id).err && !p.keys[c].used, "deny: the place goes"); }
  // Reset: everyone goes, the next phone becomes the owner.
  { HubPeople p = fresh(); int o = addIn(p, 1, true); addIn(p, 2, false); bool first; const char *err;
    CHECK(!p.apply(PO_RESET, o).err && !p.owned(), "reset: nobody left");
    fakeNow += 70000;
    CHECK(p.pairGate(false, first, err) == 0 && first, "reset: a new first owner may connect"); }
}

// ---- update files
static std::vector<uint8_t> readBin(const std::string &name) {
  std::ifstream f("files/" + name, std::ios::binary);
  return std::vector<uint8_t>((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
}
static uint8_t PUB[65];
static void loadPub() {
  std::ifstream f("files/test-key.pub.hex");
  std::string h; f >> h;
  for (int i = 0; i < 65 && (size_t)i * 2 + 1 < h.size(); i++) PUB[i] = (uint8_t)strtol(h.substr(i * 2, 2).c_str(), nullptr, 16);
}
static const char *stage(const std::vector<uint8_t> &f, const char *running, bool &delta) { MemReader r(f.data(), f.size()); return stageCheck(r, f.size(), running, PUB, delta); }
static int hubFile(const std::vector<uint8_t> &f, const char *running, const char *&err, char *ver) { MemReader r(f.data(), f.size()); return hubFileCheck(r, f.size(), running, PUB, err, ver); }

static void fileTests() {
  loadPub();
  std::vector<uint8_t> full = readBin("tilt-2.3.0.bin.signed"), older = readBin("tilt-2.2.0.bin.signed"), patch = readBin("tilt-2.3.0.bin.patch");
  std::vector<uint8_t> hub = readBin("hub-0.3.5.bin.signed"), hubOld = readBin("hub-0.3.4.bin.signed");
  CHECK(full.size() > 3000 && patch.size() > 1000 && hub.size() > 3000 && PUB[0] == 4, "the test files are there (make_files.sh)");
  bool delta = true;
  { MemReader r(full.data(), full.size()); CHECK(checkSignedFile(r, full.size(), SIG_MAGIC, PUB), "a file release_firmware.py signed checks"); }
  { MemReader r(full.data(), full.size()); CHECK(!checkSignedFile(r, full.size(), SIG_MAGIC, FW_SIGN_PUB), "not with another key"); }
  CHECK(!stage(full, "2.2.0", delta) && !delta, "full file: newer than it runs");
  CHECK(!stage(full, "2.3.0", delta), "full file: the same version");
  CHECK(!stage(full, "", delta), "full file: what it runs is not known");
  CHECK(same(stage(older, "2.3.0", delta), "that firmware is older than the one it runs"), "full file: older");
  CHECK(!stage(patch, "2.2.0", delta) && delta, "patch: signed, taken (the controller checks its version)");
  CHECK(!stage(patch, "9.0.0", delta) && delta, "patch: no version check here");
  // Truncated.
  { std::vector<uint8_t> t(full.begin(), full.end() - 1);
    CHECK(same(stage(t, "2.2.0", delta), "the file's signature is not valid"), "truncated: one byte short");
    std::vector<uint8_t> h(full.begin(), full.begin() + 999);
    CHECK(same(stage(h, "2.2.0", delta), "that is not a firmware file"), "truncated: under 1000 bytes"); }
  // Wrong magic: a full file named a patch, a patch named a full file, a changed magic.
  { std::vector<uint8_t> m = full; m[m.size() - 1] = '2';
    CHECK(same(stage(m, "2.2.0", delta), "the file's signature is not valid"), "wrong magic");
    std::vector<uint8_t> asDelta = full; memcpy(&asDelta[asDelta.size() - 8], DLT_MAGIC, 8);
    CHECK(same(stage(asDelta, "2.2.0", delta), "the file's signature is not valid"), "a full file with the patch magic");
    std::vector<uint8_t> noHead = patch; noHead[0] = 0xE9;
    CHECK(same(stage(noHead, "2.2.0", delta), "the file's signature is not valid") && !delta, "a patch without its header is checked as a full file");
    MemReader r(patch.data(), patch.size()); CHECK(!checkSignedFile(r, patch.size(), SIG_MAGIC, PUB), "a patch is not a full file"); }
  // One bit flipped anywhere: in the image, in the signature.
  for (size_t at : {(size_t)0x40, full.size() / 2, full.size() - 80, full.size() - 72, full.size() - 40}) {
    std::vector<uint8_t> b = full; b[at] ^= 0x01;
    CHECK(same(stage(b, "2.2.0", delta), "the file's signature is not valid"), "one bit flipped: refused");
  }
  { std::vector<uint8_t> b = patch; b[patch.size() / 2] ^= 0x80;
    CHECK(same(stage(b, "2.2.0", delta), "the file's signature is not valid"), "patch: one bit flipped"); }
  // The hub's own update.
  const char *err = nullptr; char ver[32];
  CHECK(hubFile(hub, "0.3.4", err, ver) == 0 && !strcmp(ver, "0.3.5"), "hub file: newer, taken");
  CHECK(hubFile(hub, "0.3.5", err, ver) == 0, "hub file: the same version");
  CHECK(hubFile(hubOld, "0.3.5", err, ver) == 403 && same(err, "that firmware is older than the one the hub runs"), "hub file: older");
  CHECK(hubFile(full, "0.3.4", err, ver) == 400 && same(err, "that is not a hub firmware file"), "hub file: a controller's file");
  CHECK(hubFile(patch, "0.3.4", err, ver) == 403 && same(err, "the file's signature is not valid"), "hub file: a patch");
  { std::vector<uint8_t> b = hub; b[hub.size() / 2] ^= 0x04;
    CHECK(hubFile(b, "0.3.4", err, ver) == 403 && same(err, "the file's signature is not valid"), "hub file: one bit flipped"); }
  { std::vector<uint8_t> t(hub.begin(), hub.begin() + 500);
    CHECK(hubFile(t, "0.3.4", err, ver) == 403 && same(err, "the file's signature is not valid"), "hub file: truncated"); }
}

// ---- new hub firmware on trial, as the care task runs it (hub_care.h): its first pass 20 s after the start, then every
// 5 s until 90 s, then every 15 s; the link is Wi-Fi and Apple Home; a hub always counts as joined.
struct TrialPass { uint32_t t; TrialVerdict v; };
// up(t): whether Wi-Fi and Apple Home are up at t. refuse: the bootloader refuses every rollback asked for. It stops at
// the first TRIAL_KEEP (the hub is then no longer on trial) or after an hour.
template <class Up> static std::vector<TrialPass> trialRun(Up up, bool refuse) {
  std::vector<TrialPass> out;
  Trial tr;
  for (uint32_t t = 20000; t <= 3600000; t += t < 90000 ? 5000 : 15000) {
    TrialVerdict v = tr.tick(t, up(t), true);
    out.push_back({t, v});
    if (v == TRIAL_ROLLBACK && refuse) tr.rollbackRefused();
    if (v == TRIAL_KEEP) break;
  }
  return out;
}
static int countOf(const std::vector<TrialPass> &r, TrialVerdict v) { int n = 0; for (auto &p : r) if (p.v == v) n++; return n; }
static uint32_t firstOf(const std::vector<TrialPass> &r, TrialVerdict v) { for (auto &p : r) if (p.v == v) return p.t; return 0; }

static void hubTrialTests() {
  { auto r = trialRun([](uint32_t) { return false; }, true);
    bool waitAfter = true;
    for (auto &p : r) if (p.t > 315000 && p.v != TRIAL_WAIT) waitAfter = false;
    CHECK(countOf(r, TRIAL_ROLLBACK) == 1 && firstOf(r, TRIAL_ROLLBACK) == 315000 && waitAfter && r.back().t == 3600000,
          "hub trial: never up, rollback refused: asked once, on the first pass after 5 minutes, then wait for good"); }
  { auto r = trialRun([](uint32_t t) { return t >= 600000; }, true);
    CHECK(countOf(r, TRIAL_ROLLBACK) == 1 && firstOf(r, TRIAL_ROLLBACK) == 315000 && countOf(r, TRIAL_KEEP) == 1 && r.back().t == 675000,
          "hub trial: rollback refused, then up from 10 minutes: kept on the first pass more than a minute later"); }
  { auto r = trialRun([](uint32_t) { return false; }, false);
    bool every = true;
    for (auto &p : r) if (p.t > 300000 && p.v != TRIAL_ROLLBACK) every = false;
    CHECK(every && firstOf(r, TRIAL_ROLLBACK) == 315000 && countOf(r, TRIAL_ROLLBACK) == (int)((3600000 - 315000) / 15000 + 1),
          "hub trial: never up, never refused: rollback asked on every pass after 5 minutes"); }
  { auto r = trialRun([](uint32_t t) { return t >= 20000; }, true);
    CHECK(countOf(r, TRIAL_ROLLBACK) == 0 && r.back().v == TRIAL_KEEP && r.back().t == 85000,
          "hub trial: up from 20 s: kept on the first pass after 80 s"); }
  { auto r = trialRun([](uint32_t t) { return t >= 290000; }, true);   // first seen up on the 300 s pass
    CHECK(countOf(r, TRIAL_ROLLBACK) == 0 && r.back().v == TRIAL_KEEP && r.back().t == 375000,
          "hub trial: up late (290 s) and staying up: no rollback, kept once up for a minute"); }
  { auto r = trialRun([](uint32_t t) { return t >= 20000 && t < 50000; }, false);
    CHECK(countOf(r, TRIAL_KEEP) == 0 && firstOf(r, TRIAL_ROLLBACK) == 315000,
          "hub trial: up at 20 s, down at 50 s for good: rollback on the first pass after 5 minutes"); }
}

int main() {
  permitTests();
  pairTests();
  nameTests();
  lockoutTests();
  waitingTests();
  peopleOpTests();
  fileTests();
  hubTrialTests();
  printf("%d passed, %d failed\n", passed, failed);
  return failed ? 1 : 0;
}
