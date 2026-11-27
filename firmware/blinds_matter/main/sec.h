// The secured connection for the phone app. No accounts, no server: each phone that is paired holds its own 256-bit
// key, and every command is encrypted and authenticated with it (AES-256-GCM). Nothing else on the network can read
// the blinds' state or move them.
//
// The requests, over Bluetooth (ble.h: the letter) and through the Tilt Hub (hub_link.h: the letter; the app sends the
// hub the path, which the hub turns into the letter):
//   H  GET  /x/hello     who am I: id, name, firmware, this start's number ("boot"), is there an owner yet
//   P                    make a key. JSON {"pub": base64 P-256 public key, "name": "..."}. Bluetooth only: only for
//                        the first phone (it becomes an owner). Both sides do ECDH; the key is HKDF-SHA256 of the result
//                        (tilt_pair.h, shared with the Tilt Hub).
//   A  POST /x/ask       ask to join a controller that has an owner. Same JSON as P. The key is made but does nothing
//                        until an owner approves it in the app (/api/approve). Both phones show the same 4-digit code,
//                        made from the key, so the owner can tell it is the right phone.
//   R  POST /x/recover   no owner left: ask to join, then turn a blind's wand to become an owner (people.h)
//   Q  GET  /x/recstate  how far that recovery has got
//   X  POST /x           a command. Bytes: client id (8) | nonce (12) | ciphertext | tag (16)
//                        nonce = boot (4) | counter (8, must rise). Plain text inside: "/api/go?b=0&t=50".
//                        The answer comes back the same way: nonce (12) | ciphertext | tag. Who may send which
//                        command: routes.h.
//
// A captured command cannot be replayed: the counter must rise, and after a restart the boot number is new.
#pragma once
#include <mbedtls/gcm.h>
#include <mbedtls/md.h>
#include <esp_random.h>
#include <esp_http_server.h>
#include "ardu.h"
#include "logic.h"                               // nonceFresh, permitRule
#include "store.h"                               // nvs, event
#include "wire.h"                                // keptName: a phone's name as typed
#include "lock.h"                                // mx
#include "tilt_crypto.h"                         // hexOf, unhex, hmac256, gcm (shared with the Tilt Hub)
#include "tilt_link.h"                           // linkKey, proofs, the hub link's layouts (shared with the Tilt Hub)
#include "tilt_pair.h"                           // the key exchange in Pairing, the 4-digit code, the answer (shared with the Tilt Hub)

const int MAX_KEYS = 8;
struct ClientKey { uint8_t used, role; uint8_t id[8]; uint8_t key[32]; char name[20]; };   // used 1 = paired, 2 = asked to join, waiting for an owner; role 1 = owner
ClientKey keys[MAX_KEYS];
uint64_t lastCtr[MAX_KEYS];
uint8_t bootId[4];
// A random name for this controller in the iCloud notices the phones send each other (a request to join, a removal).
// Only phones that have talked to the controller know it, so nobody else can send its owners a notice.
uint8_t cloudTopic[16];
// The command being handled. Only set and read while secMx is held: one secured command runs at a time, whether it
// came over Bluetooth or through the hub, so these never belong to two requests at once.
int secClient = -1;                            // which key the command came with (-1: not a secured one)
const char *secQuery = nullptr;                // its "a=b&c=d" part, for arg()
std::string *secOut = nullptr;                 // where its answer goes, for sendJson()
SemaphoreHandle_t secMx = nullptr;             // one secured command at a time (Bluetooth and the hub share the handlers)
// keys[] and lastCtr[] are guarded by the controller lock (mx, lock.h), the one every handler and the main loop
// already hold when they touch shared state. Lock order: secMx, then mx; nothing holding mx may take secMx.
struct KeysLock { KeysLock() { xSemaphoreTake(mx, portMAX_DELAY); } ~KeysLock() { xSemaphoreGive(mx); } };

// The Tilt Hub's own key here (its id; set by an owner, /api/hubkey). Messages from the hub prove themselves with a key
// made from it, so another device on the Thread network cannot pose as the hub.
uint8_t hubKeyId[8];
bool hubKeySet = false;
int hubSlot() { if (!hubKeySet) return -1; for (int i = 0; i < MAX_KEYS; i++) if (keys[i].used == 1 && !memcmp(keys[i].id, hubKeyId, 8)) return i; return -1; }
// When each request to join was made (this start): a new request may only take the place of one older than 10 minutes.
uint32_t askAt[MAX_KEYS];
// A controller nobody owns takes its first owner only in its first 15 minutes after power-on (unplug it to pair again).
const uint32_t FIRST_PAIR_MS = 15 * 60 * 1000;
bool firstPairOpen() { return esp_timer_get_time() / 1000 < FIRST_PAIR_MS; }
static int secRng(void *, unsigned char *b, size_t n) { esp_fill_random(b, n); return 0; }
void hubLinkRefresh();
void keysSave() { nvs.putBytes("keys", keys, sizeof keys); hubLinkRefresh(); }
void secBegin() {
  if (nvs.getBytes("keys", keys, sizeof keys) != sizeof keys) memset(keys, 0, sizeof keys);
  esp_fill_random(bootId, sizeof bootId);
  if (nvs.getBytes("topic", cloudTopic, sizeof cloudTopic) != sizeof cloudTopic) { esp_fill_random(cloudTopic, sizeof cloudTopic); nvs.putBytes("topic", cloudTopic, sizeof cloudTopic); }
  memset(lastCtr, 0, sizeof lastCtr);
  memset(askAt, 0, sizeof askAt);
  hubKeySet = nvs.getBytes("hubkey", hubKeyId, sizeof hubKeyId) == sizeof hubKeyId;
  hubLinkRefresh();
  secMx = xSemaphoreCreateMutex();
}
bool owned() { for (auto &k : keys) if (k.used == 1) return true; return false; }
int asksWaiting() { int n = 0; for (auto &k : keys) if (k.used == 2) n++; return n; }
std::string jsonStr(const std::string &j, const char *key) {      // the string value of "key" in a flat JSON object
  std::string k = std::string("\"") + key + "\"";
  size_t i = j.find(k);
  if (i == std::string::npos) return "";
  i = j.find(':', i + k.length());
  if (i == std::string::npos) return "";
  i = j.find('"', i);
  if (i == std::string::npos) return "";
  std::string out;                               // up to the closing quote, undoing backslash escapes
  for (size_t p = i + 1; p < j.length(); p++) {
    if (j[p] == '"') return out;
    if (j[p] == '\\' && p + 1 < j.length()) p++;
    out += j[p];
  }
  return "";
}
// The proof on a message between the hub and this controller: the first 16 bytes of HMAC-SHA256 with the link key
// (HMAC of the hub's key with "tilt-hub-link"), over a label and the message, in hex. "" when there is no hub key.
// The link key is kept ready (remade whenever the keys change, which happens under the controller lock), so making a
// proof never needs the lock: it is made from the blinds task, which already holds it.
static uint8_t hubLink[32];
static volatile bool hubLinkOk = false;
void hubLinkRefresh() {
  int s = hubSlot();
  if (s >= 0) linkKey(keys[s].key, hubLink);
  hubLinkOk = s >= 0;
}
std::string hubMac(const std::string &what) {
  if (!hubLinkOk) return "";
  uint8_t link[32], m[32];
  memcpy(link, hubLink, 32);
  hmac256(link, 32, (const uint8_t *)what.data(), what.size(), m);
  return hexOf(m, 16);
}
bool hubMacOk(const std::string &what, const std::string &mac) {
  std::string want = hubMac(what);
  if (want.empty() || mac.size() != want.size()) return false;
  uint8_t d = 0;
  for (size_t i = 0; i < want.size(); i++) d |= want[i] ^ mac[i];
  return d == 0;
}
// ---- pairing
// Returns the HTTP-style status ("200 OK", ...) and fills out with the JSON answer. Over Bluetooth ('P', 'A') and through
// the hub ('A'); recoverDo (people.h) starts with an ask too.
const char *pairDo(const std::string &b, std::string &out, bool ask = false, bool recovering = false) {
  uint8_t cpub[65];
  if (!pairPub(jsonStr(b, "pub"), cpub)) { out = "{\"err\":\"bad key\"}"; return "400 Bad Request"; }
  bool first;
  {
  KeysLock kl;
  first = !owned();
  if (ask) {
    static uint32_t lastAsk = 0;               // each ask is written to flash: no more than one every 10 seconds
    if (first) { out = "{\"err\":\"this controller has no owner yet\"}"; return "403 Forbidden"; }
    if (lastAsk && millis() - lastAsk < 10000) { out = "{\"err\":\"try again in a few seconds\"}"; return "429 Too Many Requests"; }
    lastAsk = millis();
  } else if (!first) { out = "{\"err\":\"this controller has an owner. Ask to join from the app.\"}"; return "403 Forbidden"; }
  else if (!firstPairOpen()) { out = "{\"err\":\"setup is closed: unplug the controller, plug it back in, and set it up within 15 minutes\"}"; return "403 Forbidden"; }
  }

  PairKeys pk;                                   // the slow part, with no lock held
  if (!pairExchange(cpub, "", secRng, pk)) { out = "{\"err\":\"key exchange failed\"}"; return "400 Bad Request"; }

  KeysLock kl;                                 // the key is ready: claim a slot now (the slow part ran unlocked)
  if (!first != owned()) { out = "{\"err\":\"another phone paired at the same moment. Try again.\"}"; return "409 Conflict"; }
  uint8_t used[MAX_KEYS];                        // the slot rule (logic.h keySlot): at most two asks wait, a recovery always gets in
  uint32_t waited[MAX_KEYS];
  for (int i = 0; i < MAX_KEYS; i++) { used[i] = keys[i].used; waited[i] = askAt[i] ? millis() - askAt[i] : UINT32_MAX; }
  int slot = keySlot(used, waited, MAX_KEYS, ask, recovering);
  if (slot == KEY_TWO_WAITING) { out = "{\"err\":\"two requests are waiting already. Try again later.\"}"; return "429 Too Many Requests"; }
  if (slot < 0) { out = "{\"err\":\"no room for another phone\"}"; return "403 Forbidden"; }
  if (keys[slot].used == 2) event("%s's request to join was replaced by a newer one", keys[slot].name);
  ClientKey &k = keys[slot];
  memset(&k, 0, sizeof k);
  k.used = ask ? 2 : 1; k.role = first ? 1 : 0;
  esp_fill_random(k.id, 8);
  memcpy(k.key, pk.key, 32);
  strlcpy(k.name, keptName(jsonStr(b, "name"), sizeof k.name - 1).c_str(), sizeof k.name);   // as typed (UTF-8): wire.h
  if (!k.name[0]) strlcpy(k.name, "iPhone", sizeof k.name);
  keysSave();
  lastCtr[slot] = 0;
  askAt[slot] = ask ? (millis() ? millis() : 1) : 0;
  event(ask ? "%s asked to join%s" : "%s paired%s", k.name, first ? " (owner)" : "");
  out = pairAnswer(pk, k.id, first, ask, cloudTopic, nullptr);
  return "200 OK";
}


// ---- commands
struct Route { const char *uri; esp_err_t (*fn)(httpd_req_t *); Who who; };      // made from routes.h (web.h)
extern const Route routes[];
extern const int routeCount;
// ---- who may do what: the one place every command is decided (over Bluetooth or through the hub)
struct Caller {
  bool owner;                                    // the phone is an Owner (else a Guest)
  const uint8_t *id;                             // the phone's 8-byte id
};
std::string qarg(const std::string &query, const char *key) {
  char v[80] = "";
  return httpd_query_key_value(query.c_str(), key, v, sizeof v) == ESP_OK ? std::string(v) : std::string();
}
// nullptr: allowed. Otherwise the reason it is refused. Rules about the target (you cannot remove yourself, the last
// owner stays) live in the handlers; who the caller is and what that lets them do is decided only here.
const char *permit(const Route &rt, const std::string &query, const Caller &c) {
  return permitRule(rt.who, c.owner, qarg(query, "cid"), hexOf(c.id, 8));
}
// The answer is sealed bytes when the status is "200 OK", plain JSON otherwise.
const char *secDo(const std::string &b, std::string &resp, httpd_req_t *r, bool *fromHub = nullptr) {
  if (b.size() < 8 + 12 + 16 + 1) { resp = "{\"err\":\"short\"}"; return "400 Bad Request"; }
  const uint8_t *p = (const uint8_t *)b.data();
  const uint8_t *nonce = p + 8, *ct = p + 20;
  size_t n = b.size() - 36;
  uint64_t ctr = nonceCounter(nonce);
  uint8_t aad[17];
  memcpy(aad, "blinds-v1", 9); memcpy(aad + 9, p, 8);
  std::string cmd(n, 0);
  int slot = -1;
  uint8_t key[32];                               // a copy: the reply is sealed with it even if the phone is removed meanwhile
  bool owner = false;
  {
    // Find the phone, check the counter, decrypt and record the counter in one step under the lock, so two requests
    // carrying the same counter (a replay racing the original) cannot both get through.
    KeysLock kl;
    for (int i = 0; i < MAX_KEYS; i++) if (keys[i].used && !memcmp(keys[i].id, p, 8)) slot = i;
    if (slot < 0) { resp = "{\"err\":\"not paired\"}"; return "401 Unauthorized"; }
    if (!nonceFresh(nonce, bootId, lastCtr[slot])) { resp = std::string("{\"err\":\"stale\",\"boot\":\"") + hexOf(bootId, 4) + "\"}"; return "409 Conflict"; }
    memcpy(key, keys[slot].key, 32);
    if (!gcm(false, key, nonce, aad, 17, ct, n, (uint8_t *)&cmd[0], (uint8_t *)(ct + n))) { resp = "{\"err\":\"bad key\"}"; return "401 Unauthorized"; }
    lastCtr[slot] = ctr;
    if (fromHub) *fromHub = slot == hubSlot();
    if (keys[slot].used != 1) {                  // still waiting for an owner: the only thing it may do is take its request back
      if (cmd == "/api/leave") { event("%s took the request back", keys[slot].name); memset(&keys[slot], 0, sizeof keys[slot]); keysSave(); resp = "{\"err\":\"not paired\"}"; return "401 Unauthorized"; }
      resp = "{\"err\":\"waiting\"}"; return "403 Forbidden";
    }
    owner = keys[slot].role;
  }

  size_t q = cmd.find('?');
  std::string path = cmd.substr(0, q), query = q == std::string::npos ? "" : cmd.substr(q + 1), out;
  const Route *rt = nullptr;
  for (int i = 0; i < routeCount; i++) if (path == routes[i].uri) rt = &routes[i];
  if (!rt) out = "{\"ok\":0,\"err\":\"unknown command\"}";
  else if (const char *why = permit(*rt, query, Caller{owner, p})) out = std::string("{\"ok\":0,\"err\":\"") + why + "\"}";
  else {
    xSemaphoreTake(secMx, portMAX_DELAY);
    bool still;                                  // removed by a command that ran just before this one?
    { KeysLock kl; still = keys[slot].used == 1 && !memcmp(keys[slot].id, p, 8); }
    if (still) {
      secClient = slot; secQuery = query.c_str(); secOut = &out;
      rt->fn(r);
      secClient = -1; secQuery = nullptr; secOut = nullptr;
    } else out = "{\"ok\":0,\"err\":\"not paired\"}";
    xSemaphoreGive(secMx);
  }
  resp.assign(12 + out.size() + 16, 0);
  uint8_t *o = (uint8_t *)&resp[0], aad2[30];
  esp_fill_random(o, 12);
  memcpy(aad2, "blinds-v1r", 10); memcpy(aad2 + 10, p, 8); memcpy(aad2 + 18, nonce, 12);
  if (!gcm(true, key, o, aad2, 30, (const uint8_t *)out.data(), out.size(), o + 12, o + 12 + out.size())) { resp = "{\"err\":\"seal\"}"; return "500 Internal Server Error"; }
  return "200 OK";
}
