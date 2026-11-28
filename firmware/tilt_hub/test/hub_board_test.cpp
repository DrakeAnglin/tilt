// Tests for the Tilt Hub's own code on the host board (firmware/blinds_matter/test/host_esp/host_board.h, with the
// hub's own stand-ins in test/host_esp): main/hub_store.h and main/hub_pair.h, run on the Mac with real mbedtls and the
// real cJSON (tools/host_cjson.py): tools/firmware_tests.sh. The real files run unchanged; the include path picks the
// stand-in SDK headers. The hub's parts are included in hub.cpp's order; later parts add theirs here.
//   hub_board_test <link.json>   (firmware/blinds_matter/test/wire/link.json: the sealed-command vector)
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

static const char *TAG = "hub";
static const char *buildPin = "24681357";       // the setup code the build would carry (hub.cpp: setup_pin.h)
#define HUB_SETUP_PIN buildPin
#include "../main/hub_store.h"
#include "../main/hub_pair.h"
#include <nvs_flash.h>
#include "../../blinds_matter/test/sim_phone.h"

static int passed = 0, failed = 0;
#define CHECK(cond, what) do { if (cond) passed++; else { failed++; printf("FAIL line %d: %s\n", __LINE__, what); } } while (0)

// hub_api.h's hubCommand, until that file joins (#277): it records the command and gives a set answer.
static int cmdCalls = 0, cmdSlot = -1;
static std::string cmdGot, cmdAnswer = "{\"ok\":1}";
static std::string hubCommand(int slot, const std::string &cmd) {
  cmdCalls++;
  cmdSlot = slot;
  cmdGot = cmd;
  return cmdAnswer;
}

// A restart puts every global of the hub's parts back to its start value, as the chip does; flash stays.
static void hubStartValues() {
  for (auto &c : ctrls) c = Ctrl();
  memset(proofs, 0, sizeof proofs);
  otaAcks = nullptr;
  hubTrial = false;
  homeWindowUntil = 0;
  otaFor = -1;
  homeManual.clear(); homeQr.clear(); shareManual.clear(); shareQr.clear();
  shareUntil = 0;
  inHome = false;
  stateMx = nullptr;
  nv = 0;
  people = HubPeople();
  memset(hboot, 0, sizeof hboot);
  memset(htopic, 0, sizeof htopic);
  keyMx = nullptr;
  memset(setupPin, 0, sizeof setupPin);
  hubIdKept.clear();
  cmdCalls = 0; cmdSlot = -1; cmdGot.clear(); cmdAnswer = "{\"ok\":1}";
}
// A start of the hub as app_main does it, as far as these parts go.
static void start() {
  host::restart();
  nvs_flash_init();
  nvs_open("hub", NVS_READWRITE, &nv);
  hubId();
  stateMx = xSemaphoreCreateMutex();
  keysBegin();
  otaAcks = xQueueCreate(16, sizeof(OtaAck));
  loadCtrls();
}
static void firstStart() { host::wipeFlash(); start(); }

static std::vector<uint8_t> bytesOf(const std::string &hex) {
  std::vector<uint8_t> b(hex.size() / 2);
  unhex(hex, b.data(), b.size());
  return b;
}
static std::string strOf(const std::string &hex) { std::vector<uint8_t> b = bytesOf(hex); return std::string(b.begin(), b.end()); }
static std::string field(const std::string &json, const char *key) { return jsonStr(json, key); }
static int numField(const std::string &json, const char *key) {
  cJSON *o = cJSON_Parse(json.c_str());
  cJSON *v = o ? cJSON_GetObjectItem(o, key) : nullptr;
  int n = cJSON_IsNumber(v) ? v->valueint : -1;
  if (o) cJSON_Delete(o);
  return n;
}

// ---- a phone: the test phone both firmwares' tests share (blinds_matter/test/sim_phone.h)

// pairDo and secDo, each followed by the check that keyMx is free again (a held keyMx would hang the hub's next call).
static int pair(const std::string &b, std::string &out, bool ask, const char *what) {
  int st = pairDo(b, out, ask);
  CHECK(!host::held(keyMx), what);
  return st;
}
static int sec(const std::string &b, std::string &resp, const char *what) {
  int st = secDo(b, resp);
  CHECK(!host::held(keyMx), what);
  return st;
}
// A first phone that pairs with the setup code it typed and sends its first command: the status of that command.
static int claim(SimPhone &p, const std::string &typed, std::string &resp) {
  std::string out;
  if (pair(p.body(), out, false, "pairDo (first phone): the lock is free") != 200 || !p.finish(out, typed)) return -1;
  return sec(p.seal("/api/info", hboot), resp, "secDo (first command): the lock is free");
}
static int slotOf(const SimPhone &p) { return people.find(p.cid); }

// ---- storage (hub_store.h)
static void testEmptyFlash() {
  firstStart();
  bool none = true, zero = true;
  for (auto &c : ctrls) none = none && !c.used;
  for (auto &p : proofs) zero = zero && !p.on && !p.bn;
  CHECK(none, "empty flash: no controller in use");
  CHECK(zero, "empty flash: every proof record is zero");
}

static Saved savedOf(const char *id, uint8_t ks, uint8_t fill, uint16_t ep0, uint8_t sep) {
  Saved s = {};
  strlcpy(s.id, id, sizeof s.id);
  s.keyState = ks;
  memset(s.cid, fill, sizeof s.cid);
  memset(s.key, fill + 1, sizeof s.key);
  for (int p = 0; p < PORTS; p++) s.ep[p] = ep0 ? ep0 + p : 0;
  s.sep = sep;
  return s;
}
static void testControllersKept() {
  firstStart();
  ctrls[0].used = true; ctrls[0].s = savedOf("a0b1c2d3e4f5", KEY_IN, 0x11, 3, 1);
  ctrls[2].used = true; ctrls[2].s = savedOf("0011223344ff", KEY_ASKED, 0x22, 7, 0);
  strlcpy(ctrls[0].name, "Den", sizeof ctrls[0].name);
  saveCtrls();
  start();
  Saved a = savedOf("a0b1c2d3e4f5", KEY_IN, 0x11, 3, 1), b = savedOf("0011223344ff", KEY_ASKED, 0x22, 7, 0);
  CHECK(ctrls[0].used && !memcmp(&ctrls[0].s, &a, sizeof a), "two controllers saved: the first is back in its place");
  CHECK(ctrls[2].used && !memcmp(&ctrls[2].s, &b, sizeof b), "two controllers saved: the second is back in its place");
  CHECK(!ctrls[1].used && !ctrls[3].used, "two controllers saved: the other places stay free");
  CHECK(!strcmp(ctrls[0].name, "Blinds") && !strcmp(ctrls[2].name, "Blinds"), "after a restart: named Blinds until heard");
}

static void testFirstLayout() {
  SavedV1 v1[MAX_CTRL] = {};
  strlcpy(v1[1].id, "a0b1c2d3e4f5", sizeof v1[1].id);
  v1[1].keyState = KEY_IN;
  memset(v1[1].cid, 0x33, 8);
  memset(v1[1].key, 0x44, 32);
  for (int p = 0; p < PORTS; p++) v1[1].ep[p] = 10 + p;
  host::wipeFlash();
  host::putFlashBlob("hub", "ctrls", v1, sizeof v1);
  start();
  bool eps = true;
  for (int p = 0; p < PORTS; p++) eps = eps && ctrls[1].s.ep[p] == 10 + p;
  CHECK(ctrls[1].used && !strcmp(ctrls[1].s.id, "a0b1c2d3e4f5") && ctrls[1].s.keyState == KEY_IN, "first layout: the controller is kept");
  CHECK(ctrls[1].s.cid[0] == 0x33 && ctrls[1].s.key[31] == 0x44, "first layout: the hub's key is kept");
  CHECK(eps, "first layout: the Window covering endpoints are kept");
  CHECK(ctrls[1].s.sep == 1, "first layout: one per blind is on");
  CHECK(!ctrls[0].used, "first layout: an empty place stays free");
}

static void testControllersOfAnotherSize() {
  Saved all[MAX_CTRL] = {};
  all[0] = savedOf("a0b1c2d3e4f5", KEY_IN, 0x11, 3, 1);
  std::string bigger((const char *)all, sizeof all);
  bigger += "more";
  host::wipeFlash();
  host::putFlashBlob("hub", "ctrls", bigger.data(), bigger.size());
  start();
  CHECK(!ctrls[0].used, "a ctrls record larger than either layout: no controller in use");
  host::wipeFlash();
  host::putFlashBlob("hub", "ctrls", all, sizeof all - 1);
  start();
  CHECK(!ctrls[0].used, "a ctrls record smaller than this layout: no controller in use");
}

static void testProofs() {
  PushProof other[MAX_CTRL];
  memset(other, 0x5a, sizeof other);
  host::wipeFlash();
  host::putFlashBlob("hub", "proof", other, sizeof other - 1);
  start();
  bool zero = true;
  for (auto &p : proofs) zero = zero && !p.on && !p.bn;
  CHECK(zero, "a proof record of another size: zeros");
  proofs[1] = {1, 42};
  proofs[3] = {1, 7};
  proofsSave();
  start();
  CHECK(proofs[1].on == 1 && proofs[1].bn == 42 && proofs[3].on == 1 && proofs[3].bn == 7, "proofs saved: back after a restart");
  CHECK(!proofs[0].on && !proofs[2].on, "proofs saved: the others stay zero");
}

static void testFindCtrl() {
  firstStart();
  ctrls[0].used = true; strlcpy(ctrls[0].s.id, "a0b1c2d3e4f5", 13);
  ctrls[2].used = true; strlcpy(ctrls[2].s.id, "0011223344ff", 13);
  ctrls[1].used = false; strlcpy(ctrls[1].s.id, "deadbeef0000", 13);
  CHECK(findCtrl("0011223344ff") == 2 && findCtrl("a0b1c2d3e4f5") == 0, "findCtrl: the place of a known id");
  CHECK(findCtrl("ffffffffffff") == -1, "findCtrl: -1 for an unknown id");
  CHECK(findCtrl("deadbeef0000") == -1, "findCtrl: -1 for an id left in a place no longer in use");
}

static void testHomeBeingAdded() {
  start();
  CHECK(!homeBeingAdded(), "homeBeingAdded: no home app adding the hub");
  hubhost::setFailSafe(true);
  CHECK(homeBeingAdded(), "homeBeingAdded: a home app is adding the hub (the fail-safe is armed)");
  start();
  CHECK(!homeBeingAdded(), "homeBeingAdded: off after a restart");
}

static void testHelpers() {
  CHECK(constrain_u(5, 0, 10) == 5 && constrain_u(0, 0, 10) == 0 && constrain_u(10, 0, 10) == 10, "constrain_u: in range and at its ends");
  CHECK(constrain_u(-3, 0, 10) == 0 && constrain_u(12, 0, 10) == 10, "constrain_u: under and over its ends");
  start();
  CHECK(ms() == 0, "ms: 0 at a start");
  host::advanceMs(1234);
  CHECK(ms() == 1234, "ms: follows the board's clock");
  host::advanceUs(999);
  CHECK(ms() == 1234, "ms: whole milliseconds");
}

// ---- the hub's people from flash (hub_pair.h)
static void testPeopleFromFlash() {
  std::vector<uint8_t> rnd;
  for (int i = 0; i < 20; i++) rnd.push_back((uint8_t)(0xa0 + i));
  host::wipeFlash();
  // start() restarts the board, which clears queued bytes: do its steps here with the bytes queued after the restart.
  host::restart();
  host::queueRandom(rnd);
  nvs_open("hub", NVS_READWRITE, &nv);
  hubId();
  stateMx = xSemaphoreCreateMutex();
  keysBegin();
  bool none = true;
  for (auto &k : people.keys) none = none && !k.used;
  CHECK(none, "empty flash: no people");
  CHECK(!memcmp(htopic, rnd.data(), 16), "empty flash: a new random alert topic");
  CHECK(host::flashBlob("hub", "htopic") == std::vector<uint8_t>(rnd.begin(), rnd.begin() + 16), "empty flash: the alert topic is saved");
  CHECK(!memcmp(hboot, rnd.data() + 16, 4), "empty flash: the boot id comes from the board's random bytes");
  uint8_t topic[16], boot[4];
  memcpy(topic, htopic, 16);
  memcpy(boot, hboot, 4);
  start();
  CHECK(!memcmp(htopic, topic, 16), "a second start: the same alert topic");
  CHECK(memcmp(hboot, boot, 4) != 0, "a second start: a new boot id");

  HubKey keys[HUB_KEYS] = {};
  keys[0].used = HK_IN; keys[0].role = 1;
  host::putFlashBlob("hub", "hkeys", keys, sizeof keys - 1);
  start();
  CHECK(!people.keys[0].used, "saved people of another size: no people");
}

static void testSetupCode() {
  host::wipeFlash();
  host::putFlashStr("hub", "pin", "11112222");
  start();
  CHECK(!strcmp(setupPin, "11112222"), "setup code: the one in flash wins over the build's");
  host::wipeFlash();
  start();
  CHECK(!strcmp(setupPin, "24681357"), "setup code: none in flash, the build's");
  CHECK(host::flashStr("hub", "pin") == "24681357", "setup code: the build's is copied to flash");
  buildPin = "";
  host::wipeFlash();
  start();
  CHECK(setupPin[0] == 0 && !host::flashHas("hub", "pin"), "setup code: neither, it stays empty");
  CHECK(host::lastLog().rfind("E hub: no setup code", 0) == 0, "setup code: neither, an error is logged");
  buildPin = "24681357";
}

static void testHubId() {
  host::wipeFlash();
  host::restart();
  const uint8_t mac[6] = {0x40, 0x4c, 0xca, 0x01, 0x02, 0xab};
  host::setMac(mac);
  nvs_open("hub", NVS_READWRITE, &nv);
  CHECK(hubId() == "hub404cca0102ab", "the hub's id: hub and the MAC in hex the first time");
  CHECK(host::flashStr("hub", "hubid") == "hub404cca0102ab", "the hub's id: saved");
  host::restart();                               // another chip (the MAC is put back to the board's default)
  nvs_open("hub", NVS_READWRITE, &nv);
  CHECK(hubId() == "hub404cca0102ab", "the hub's id: the same after a restart on a board with another MAC");
}

static void testHubOwned() {
  firstStart();
  CHECK(!hubOwned(), "hubOwned: false on a new hub");
  SimPhone p;
  std::string resp;
  CHECK(claim(p, "24681357", resp) == 200, "a first phone with the right setup code: in");
  CHECK(hubOwned(), "hubOwned: true once an Owner is in");
  CHECK(host::takeFaults() == 0, "no board fault so far");
  xSemaphoreTake(keyMx, portMAX_DELAY);
  hubOwned();
  CHECK(host::takeFaults() == 1, "hubOwned with keyMx held: a board fault (the lock is not recursive)");
}

static void testCleanName() {
  char out[32];
  cleanName(out, sizeof out, std::string("a\"b\\c\x01" "d\te\xc3\xa9", 11));
  CHECK(!strcmp(out, "abcde\xc3\xa9"), "cleanName: no quotes, backslashes or control characters; UTF-8 kept");
  char small[8];
  memset(small, 'X', sizeof small);
  cleanName(small, 5, "abcdefgh");
  CHECK(!strcmp(small, "abcd") && small[5] == 'X' && small[6] == 'X' && small[7] == 'X', "cleanName: never writes past the buffer");
  cleanName(small, 1, "abc");
  CHECK(small[0] == 0, "cleanName: a buffer of one byte gets an empty name");
}

static void testJsonStr() {
  CHECK(jsonStr("{\"a\":\"x y\",\"n\":5}", "a") == "x y", "jsonStr: the value of a key");
  CHECK(jsonStr("{\"a\":\"x\"}", "b") == "", "jsonStr: a missing key");
  CHECK(jsonStr("{\"n\":5,\"o\":{\"a\":\"x\"}}", "n") == "", "jsonStr: a value that is not a string");
  CHECK(jsonStr("not json", "a") == "" && jsonStr("", "a") == "", "jsonStr: text that is not JSON");
}

// ---- Pairing (pairDo)
static void testBadKey() {
  firstStart();
  std::string out;
  CHECK(pair("{\"pub\":\"bm90IGEga2V5\"}", out, false, "pairDo (bad key): the lock is free") == 400 && field(out, "err") == "bad key",
        "a first phone with a bad public key: 400 bad key");
  CHECK(pair("{}", out, false, "pairDo (no key): the lock is free") == 400, "a first phone with no public key: 400");
  bool free = true;
  for (auto &k : people.keys) free = free && !k.used;
  CHECK(free, "a bad public key: no place taken");
  // 65 bytes that are not a point on the curve: the key exchange fails
  uint8_t bad[65], b64[100];
  memset(bad, 0x04, sizeof bad);
  size_t n = 0;
  mbedtls_base64_encode(b64, sizeof b64, &n, bad, 65);
  CHECK(pair("{\"pub\":\"" + std::string((char *)b64, n) + "\"}", out, false, "pairDo (not on the curve): the lock is free") == 400 &&
        field(out, "err") == "key exchange failed", "a public key not on the curve: 400 key exchange failed");
}

static void testFirstPhone() {
  firstStart();
  SimPhone p;
  std::string out;
  CHECK(pair(p.body(), out, false, "pairDo (first phone): the lock is free") == 200, "a first phone with a good key: 200");
  uint8_t dpub[65];
  CHECK(pairPub(field(out, "pub"), dpub), "the answer: the hub's public key");
  CHECK(field(out, "cid").size() == 16 && numField(out, "owner") == 1 && numField(out, "wait") == 0, "the answer: the phone's id, owner");
  CHECK(field(out, "topic") == hexOf(htopic, 16), "the answer: the hub's alert topic");
  CHECK(p.finish(out, "24681357"), "the phone works out its key with the setup code");
  CHECK(field(out, "check") == p.check, "the check is the same on both sides");
  int slot = slotOf(p);
  CHECK(slot >= 0 && people.keys[slot].used == HK_CLAIM && people.keys[slot].role == 1, "the place is held as a claim");
  CHECK(!strcmp(people.keys[slot].name, "Ann's iPhone"), "the phone's name as typed");
  CHECK(!hubOwned(), "no Owner until its first command opens");
  std::string frame = p.seal("/api/info", hboot), resp;
  cmdAnswer = "{\"ok\":1,\"name\":\"Tilt Hub\"}";
  CHECK(sec(frame, resp, "secDo (first command): the lock is free") == 200, "its first sealed command opens: 200");
  CHECK(cmdCalls == 1 && cmdGot == "/api/info" && cmdSlot == slot, "hubCommand gets the command and the phone's place");
  CHECK(p.open(frame, resp) == "{\"ok\":1,\"name\":\"Tilt Hub\"}", "the answer is sealed with the phone's key");
  CHECK(people.keys[slot].used == HK_IN && hubOwned(), "it is the Owner");
  CHECK(host::lastLog() == "I hub: Ann's iPhone connected (owner)", "the log says so");
  CHECK(host::flashBlob("hub", "hkeys").size() == sizeof people.keys, "the people are saved");
}

static void testWrongSetupCode() {
  firstStart();
  std::string resp;
  for (int i = 1; i <= 5; i++) {
    SimPhone p;
    int st = claim(p, "00000000", resp);
    char what[80];
    snprintf(what, sizeof what, "wrong setup code %d: its first command is refused with 401", i);
    CHECK(st == 401 && field(resp, "err") == "wrong setup code", what);
    CHECK(slotOf(p) < 0 && cmdCalls == 0, "a wrong setup code: the place is gone, no command");
  }
  CHECK(host::lastLog() == "W hub: five wrong setup codes: connecting closed for 5 minutes", "the fifth: the log says connecting is closed");
  SimPhone p;
  std::string out;
  CHECK(pair(p.body(), out, false, "pairDo (closed): the lock is free") == 429, "the sixth /hub/x/pair: 429");
  host::advanceMs(299000);
  CHECK(pair(p.body(), out, false, "pairDo (still closed): the lock is free") == 429, "under 5 minutes later: still 429");
  host::advanceMs(2000);
  CHECK(claim(p, "24681357", resp) == 200 && hubOwned(), "after 5 minutes on the board's clock: taken again");
}

static void testClaimBusy() {
  firstStart();
  SimPhone a, b;
  std::string out;
  CHECK(pair(a.body(), out, false, "pairDo (claim): the lock is free") == 200, "a first phone holds a claim");
  host::advanceMs(59000);
  CHECK(pair(b.body(), out, false, "pairDo (busy): the lock is free") == 409, "a second first-phone while the claim is under a minute old: 409");
  host::advanceMs(1000);
  CHECK(pair(b.body(), out, false, "pairDo (after a minute): the lock is free") == 200, "after a minute: taken");
  CHECK(b.finish(out, "24681357"), "the second phone works out its key");
  std::string resp;
  CHECK(sec(b.seal("/api/info", hboot), resp, "secDo (second phone): the lock is free") == 200 && hubOwned(), "the second phone is the Owner");
  bool aGone = true;
  for (auto &k : people.keys) aGone = aGone && !(k.used == HK_CLAIM);
  CHECK(aGone, "the old claim is gone");
}

static void testPairOrAskRefused() {
  firstStart();
  SimPhone o, x;
  std::string out, resp;
  CHECK(pair(x.body(), out, true, "pairDo (ask, no Owner): the lock is free") == 403, "/hub/x/ask on a hub with no Owner: 403");
  CHECK(claim(o, "24681357", resp) == 200, "an Owner is in");
  CHECK(pair(x.body(), out, false, "pairDo (pair, Owner): the lock is free") == 403, "/hub/x/pair on a hub with an Owner: 403");
}

static void testJoinRequest() {
  firstStart();
  SimPhone o, a, b, c;
  std::string out, resp;
  host::advanceMs(5000);                         // the hub has been up a while
  CHECK(claim(o, "24681357", resp) == 200, "an Owner is in");
  CHECK(pair(a.body("Bo\"b \xf0\x9f\x93\xb1"), out, true, "pairDo (ask): the lock is free") == 200, "a Join request: 200");
  CHECK(numField(out, "owner") == 0 && numField(out, "wait") == 1, "the answer: not an owner, it waits");
  CHECK(a.finish(out, ""), "the joining phone works out its key (no setup code)");
  int slot = slotOf(a);
  CHECK(slot >= 0 && people.keys[slot].used == HK_ASKED, "a place that waits");
  CHECK(field(out, "code").size() == 4 && field(out, "code") == askCode(a.key), "the 4-digit code is askCode of the new key");
  CHECK(!strcmp(people.keys[slot].name, "Bo\"b \xf0\x9f\x93\xb1"), "a name with a quote and an emoji: kept as typed");
  CHECK(host::lastLog() == "I hub: Bo\"b \xf0\x9f\x93\xb1 asked to join the hub", "the log names it");
  host::advanceMs(9000);
  CHECK(pair(b.body(nullptr), out, true, "pairDo (ask too soon): the lock is free") == 429, "a second one inside 10 seconds: 429");
  host::advanceMs(1000);
  CHECK(pair(b.body(nullptr), out, true, "pairDo (second ask): the lock is free") == 200, "a second one after 10 seconds: 200");
  CHECK(b.finish(out, "") && !strcmp(people.keys[slotOf(b)].name, "iPhone"), "no name: iPhone");
  host::advanceMs(10000);
  CHECK(pair(c.body(), out, true, "pairDo (third ask): the lock is free") == 429 &&
        field(out, "err") == "two requests are waiting already. Try again later.", "a third while two wait: 429");
}

static void testNoRoom() {
  HubKey keys[HUB_KEYS] = {};
  for (int i = 0; i < HUB_KEYS; i++) {
    keys[i].used = HK_IN; keys[i].role = i == 0;
    memset(keys[i].id, i + 1, 8);
    strlcpy(keys[i].name, "Phone", sizeof keys[i].name);
  }
  host::wipeFlash();
  host::putFlashBlob("hub", "hkeys", keys, sizeof keys);
  start();
  SimPhone p;
  std::string out;
  CHECK(pair(p.body(), out, true, "pairDo (no room): the lock is free") == 403 && field(out, "err") == "no room for another phone",
        "the hub has no room for another phone: 403");
}

// ---- sealed commands (secDo)
static void testSealedRefused() {
  firstStart();
  SimPhone o;
  std::string resp;
  CHECK(claim(o, "24681357", resp) == 200, "an Owner is in");
  CHECK(sec("abc", resp, "secDo (short): the lock is free") == 400 && field(resp, "err") == "short", "a body shorter than a frame: 400 short");
  SimPhone stranger;
  memset(stranger.cid, 0x77, 8);
  memset(stranger.key, 0x01, 32);
  CHECK(sec(stranger.seal("/api/info", hboot), resp, "secDo (unknown): the lock is free") == 401 && field(resp, "err") == "not paired",
        "an id the hub does not know: 401 not paired");
  uint8_t other[4];
  memcpy(other, hboot, 4);
  other[3] ^= 1;
  CHECK(sec(o.seal("/api/info", other), resp, "secDo (stale): the lock is free") == 409 && field(resp, "err") == "stale" &&
        field(resp, "boot") == hexOf(hboot, 4), "a frame for another boot id: 409 stale, with the hub's boot id");
  std::string frame = o.seal("/api/info", hboot);
  CHECK(sec(frame, resp, "secDo (once): the lock is free") == 200, "a fresh frame: 200");
  CHECK(sec(frame, resp, "secDo (replay): the lock is free") == 409, "the same frame again (a replay): 409");
  o.ctr -= 5;
  CHECK(sec(o.seal("/api/info", hboot), resp, "secDo (older counter): the lock is free") == 409, "a counter under the last one taken: 409");
  o.ctr += 10;
  std::string bent = o.seal("/api/info", hboot);
  bent[22] ^= 0x40;
  int calls = cmdCalls;
  CHECK(sec(bent, resp, "secDo (bad key): the lock is free") == 401 && field(resp, "err") == "bad key", "one byte changed: 401 bad key");
  CHECK(slotOf(o) >= 0 && people.keys[slotOf(o)].used == HK_IN && hubOwned(), "one byte changed: the phone is still in");
  CHECK(cmdCalls == calls, "a refused frame never reaches hubCommand");
  CHECK(sec(o.seal("/api/info", hboot), resp, "secDo (after a bad one): the lock is free") == 200, "its next good frame: 200");
}

static void testLinkVector(const char *path) {
  std::ifstream f(path);
  std::stringstream ss;
  ss << f.rdbuf();
  cJSON *v = cJSON_Parse(ss.str().c_str());
  CHECK(v != nullptr, "the link vector reads");
  if (!v) return;
  auto s = [&](const char *k) { const char *t = cJSON_GetStringValue(cJSON_GetObjectItem(v, k)); return std::string(t ? t : ""); };
  HubKey keys[HUB_KEYS] = {};
  keys[0].used = HK_IN; keys[0].role = 1;
  unhex(s("cid"), keys[0].id, 8);
  unhex(s("key"), keys[0].key, 32);
  strlcpy(keys[0].name, "Vector", sizeof keys[0].name);
  host::wipeFlash();
  host::putFlashBlob("hub", "hkeys", keys, sizeof keys);
  host::putFlashBlob("hub", "htopic", std::vector<uint8_t>(16, 9).data(), 16);
  // the boot id is the next 4 random bytes at the start: the vector's
  host::restart();
  host::queueRandom(bytesOf(s("boot")));
  nvs_open("hub", NVS_READWRITE, &nv);
  stateMx = xSemaphoreCreateMutex();
  keysBegin();
  CHECK(hexOf(hboot, 4) == s("boot"), "the hub's boot id is the vector's");
  cmdAnswer = s("replyOut");
  host::queueRandom(bytesOf(s("replyRnd")));
  std::string resp;
  CHECK(sec(strOf(s("frame")), resp, "secDo (vector): the lock is free") == 200, "the vector's frame: 200");
  CHECK(cmdGot == s("cmd") && cmdSlot == 0, "hubCommand gets the vector's command");
  CHECK(hexOf((const uint8_t *)resp.data(), (int)resp.size()) == s("reply"), "the answer is the vector's reply, byte for byte");
  CHECK(host::randomQueued() == 0, "the reply took the vector's random bytes");
  cJSON_Delete(v);
}

static void testWaitingPhone() {
  firstStart();
  SimPhone o, w, w2;
  std::string out, resp;
  host::advanceMs(5000);                         // the hub has been up a while
  CHECK(claim(o, "24681357", resp) == 200, "an Owner is in");
  CHECK(pair(w.body("Kid"), out, true, "pairDo (ask): the lock is free") == 200 && w.finish(out, ""), "a phone asks to join");
  int calls = cmdCalls;
  CHECK(sec(w.seal("/api/info", hboot), resp, "secDo (waiting): the lock is free") == 403 && field(resp, "err") == "waiting",
        "a phone that waits sends /api/info: 403 waiting");
  CHECK(cmdCalls == calls, "a phone that waits: hubCommand is not called");
  CHECK(sec(w.seal("/api/leave", hboot), resp, "secDo (leave): the lock is free") == 401 && field(resp, "err") == "not paired",
        "a phone that waits sends /api/leave: 401 not paired");
  CHECK(slotOf(w) < 0 && cmdCalls == calls, "its Join request is gone");

  host::advanceMs(10000);
  CHECK(pair(w2.body("Guest"), out, true, "pairDo (ask again): the lock is free") == 200 && w2.finish(out, ""), "another phone asks");
  xSemaphoreTake(keyMx, portMAX_DELAY);
  PeopleResult r = people.apply(PO_APPROVE, slotOf(o), w2.cid);
  xSemaphoreGive(keyMx);
  CHECK(r.err == nullptr, "an Owner approves the waiting phone");
  std::string frame = w2.seal("/api/info", hboot);
  CHECK(sec(frame, resp, "secDo (approved): the lock is free") == 200 && cmdGot == "/api/info" && cmdSlot == slotOf(w2),
        "the approved phone's command goes through: 200");
  CHECK(w2.open(frame, resp) == "{\"ok\":1}", "the answer opens with its key");

  // a restart: the people back from flash, the old boot id's frames stale
  uint8_t oldBoot[4];
  memcpy(oldBoot, hboot, 4);
  std::string old = w2.seal("/api/info", hboot);
  start();
  CHECK(slotOf(o) >= 0 && people.keys[slotOf(o)].role == 1 && slotOf(w2) >= 0 && people.keys[slotOf(w2)].used == HK_IN,
        "a restart: the people are back from flash");
  CHECK(memcmp(hboot, oldBoot, 4) != 0, "a restart: a new boot id");
  CHECK(sec(old, resp, "secDo (old boot): the lock is free") == 409 && field(resp, "err") == "stale", "a restart: the old boot id's frames are stale");
  CHECK(sec(o.seal("/api/info", hboot), resp, "secDo (new boot): the lock is free") == 200, "a frame for the new boot id: 200");
}

int main(int argc, char **argv) {
  if (argc < 2) { printf("usage: hub_board_test <link.json>\n"); return 2; }
  host::onRestart(hubStartValues);
  testEmptyFlash();
  testControllersKept();
  testFirstLayout();
  testControllersOfAnotherSize();
  testProofs();
  testFindCtrl();
  testHelpers();
  testHomeBeingAdded();
  testPeopleFromFlash();
  testSetupCode();
  testHubId();
  testHubOwned();
  testCleanName();
  testJsonStr();
  testBadKey();
  testFirstPhone();
  testWrongSetupCode();
  testClaimBusy();
  testPairOrAskRefused();
  testJoinRequest();
  testNoRoom();
  testSealedRefused();
  testLinkVector(argv[1]);
  testWaitingPhone();
  failed += host::takeFaults();
  printf("%d passed, %d failed\n", passed, failed);
  return failed ? 1 : 0;
}
