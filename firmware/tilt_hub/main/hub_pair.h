// The ESP side of the hub's people (the rules are hub_people.h): keys and setup code from flash, the hub's id, the
// key exchange for a new phone (tilt_pair.h, shared with the controller), and opening a phone's sealed command. Part of hub.cpp.
// It includes what it uses; TAG and HUB_SETUP_PIN come from whoever includes it (hub.cpp, or the Mac test program).
#pragma once
#include <cJSON.h>
#include <esp_log.h>
#include <esp_mac.h>
#include "hub_store.h"                           // nv, ms, rng
#include "hub_people.h"                          // the rules
#include "tilt_pair.h"                           // the key exchange in Pairing
#include "tilt_link.h"                           // sealed frames
#include "wire.h"                                // keptName
static std::string hubCommand(int slot, const std::string &cmd);  // hub_api.h
// ---- the hub's people (hub_people.h: the rules, tested on the Mac). keyMx guards people.
// keyMx is a leaf lock: nothing that holds it takes another lock (the Matter stack lock, stateMx), because the Matter
// task takes keyMx (hubOwned() in announceHub()) while it holds the Matter stack lock.
static HubPeople people;
static uint8_t hboot[4];
static SemaphoreHandle_t keyMx;
static void keysSave(const HubPeople &p) { nvs_set_blob(nv, "hkeys", p.keys, sizeof p.keys); nvs_commit(nv); }
static void pinBegin();
static void keysBegin() {
  keyMx = xSemaphoreCreateMutex();
  people.clock = ms;
  people.save = keysSave;
  size_t n = sizeof people.keys;
  if (nvs_get_blob(nv, "hkeys", people.keys, &n) != ESP_OK || n != sizeof people.keys) memset(people.keys, 0, sizeof people.keys);
  n = sizeof htopic;
  if (nvs_get_blob(nv, "htopic", htopic, &n) != ESP_OK || n != sizeof htopic) { esp_fill_random(htopic, sizeof htopic); nvs_set_blob(nv, "htopic", htopic, sizeof htopic); nvs_commit(nv); }
  esp_fill_random(hboot, sizeof hboot);
  pinBegin();
}
static char setupPin[12];                        // the code on the label (flash "pin")
static void pinBegin() {
  size_t n = sizeof setupPin;
  if (nvs_get_str(nv, "pin", setupPin, &n) == ESP_OK && setupPin[0]) return;
  strlcpy(setupPin, HUB_SETUP_PIN, sizeof setupPin);
  if (setupPin[0]) { nvs_set_str(nv, "pin", setupPin); nvs_commit(nv); }
  else ESP_LOGE(TAG, "no setup code: build once over USB with main/setup_pin.h");
}
// Whether the hub has an owner. It takes keyMx itself, so never call it (or announceHub(), helloJson()) while
// holding keyMx: the mutex is not recursive, and that would hang the hub.
static bool hubOwned() {
  xSemaphoreTake(keyMx, portMAX_DELAY);
  bool owned = people.owned();
  xSemaphoreGive(keyMx);
  return owned;
}
// The hub's id: made from its chip's MAC the first time, then kept in its saved data. So a new hub that takes over an
// old one's saved data (copied from the old chip) is the same hub to the app. A factory reset forgets it too.
static std::string hubIdKept;
static std::string hubId() {
  if (!hubIdKept.empty()) return hubIdKept;      // set once at start (app_main), before any other task asks
  char b[24] = {0};
  size_t n = sizeof b;
  if (nvs_get_str(nv, "hubid", b, &n) == ESP_OK && b[0]) return hubIdKept = b;
  uint8_t m[6];
  esp_read_mac(m, ESP_MAC_WIFI_STA);
  hubIdKept = "hub" + hexOf(m, 6);
  nvs_set_str(nv, "hubid", hubIdKept.c_str());
  nvs_commit(nv);
  return hubIdKept;
}
static std::string jsonStr(const std::string &j, const char *key) {
  cJSON *o = cJSON_Parse(j.c_str());
  const char *v = o ? cJSON_GetStringValue(cJSON_GetObjectItem(o, key)) : nullptr;
  std::string r = v ? v : "";
  if (o) cJSON_Delete(o);
  return r;
}
// For text no person types (the firmware version, an update error): no quotes, backslashes or control characters.
// A phone's name is kept as typed instead (hub_people.h pairTake, wire.h keptName).
static void cleanName(char *out, size_t n, const std::string &in) {
  size_t k = 0;
  for (char ch : in) if (k + 1 < n && (unsigned char)ch >= 32 && ch != '"' && ch != '\\') out[k++] = ch;
  out[k] = 0;
}
// pair (first phone, becomes the owner) or ask (later phones; waits for an owner)
static int pairDo(const std::string &b, std::string &out, bool ask) {
  uint8_t cpub[65];
  if (!pairPub(jsonStr(b, "pub"), cpub)) { out = "{\"err\":\"bad key\"}"; return 400; }
  bool first = false;
  const char *why = nullptr;
  xSemaphoreTake(keyMx, portMAX_DELAY);
  int st = people.pairGate(ask, first, why);
  xSemaphoreGive(keyMx);
  if (st) { out = std::string("{\"err\":\"") + why + "\"}"; return st; }
  // The first owner's key also takes the setup code (as the HKDF salt): the phone must know it. The check never does.
  PairKeys pk;
  if (!pairExchange(cpub, first ? setupPin : "", rng, pk)) { out = "{\"err\":\"key exchange failed\"}"; return 400; }
  xSemaphoreTake(keyMx, portMAX_DELAY);
  int slot = people.pairPlace(ask, st, why);
  if (slot < 0) { xSemaphoreGive(keyMx); out = std::string("{\"err\":\"") + why + "\"}"; return st; }
  uint8_t id[8];
  esp_fill_random(id, 8);
  people.pairTake(slot, ask, first, id, pk.key, jsonStr(b, "name").c_str());   // the name as it came: pairTake keeps it (wire.h)
  HubKey &k = people.keys[slot];
  if (ask) ESP_LOGI(TAG, "%s asked to join the hub", k.name); else ESP_LOGI(TAG, "%s is connecting (owner, once its code is right)", k.name);
  std::string code = ask ? askCode(k.key) : std::string();
  out = pairAnswer(pk, k.id, first, ask, htopic, code.c_str());
  xSemaphoreGive(keyMx);
  return 200;
}

// POST /hub/x: id (8) | nonce (12: boot 4 | counter 8) | ciphertext | tag (16); the answer: nonce | ciphertext | tag.
static int secDo(const std::string &b, std::string &resp) {
  Frame f;
  std::string cmd;
  uint8_t key[32];                               // a copy: the reply is sealed with it even if the phone is removed meanwhile
  int slot = -1;
  xSemaphoreTake(keyMx, portMAX_DELAY);
  FrameErr e = frameOpen(b, [&](const Frame &fr, uint8_t k[32]) {
    slot = people.find(fr.cid);
    if (slot < 0) return FrameErr::NotPaired;
    if (memcmp(fr.nonce, hboot, 4) || fr.ctr <= people.last[slot]) return FrameErr::Stale;
    memcpy(k, people.keys[slot].key, 32);
    memcpy(key, people.keys[slot].key, 32);
    return FrameErr::Ok;
  }, f, cmd);
  if (e == FrameErr::Short) { xSemaphoreGive(keyMx); resp = "{\"err\":\"short\"}"; return 400; }
  if (e == FrameErr::NotPaired) { xSemaphoreGive(keyMx); resp = "{\"err\":\"not paired\"}"; return 401; }
  if (e == FrameErr::Stale) { xSemaphoreGive(keyMx); resp = "{\"err\":\"stale\",\"boot\":\"" + hexOf(hboot, 4) + "\"}"; return 409; }
  if (e == FrameErr::BadKey) {
    bool claim = people.openFailed(slot);       // a first owner with the wrong setup code: the place goes
    if (claim && people.pinFails == 0) ESP_LOGW(TAG, "five wrong setup codes: connecting closed for 5 minutes");
    xSemaphoreGive(keyMx);
    resp = claim ? "{\"err\":\"wrong setup code\"}" : "{\"err\":\"bad key\"}";
    return 401;
  }
  if (people.opened(slot, f.ctr)) ESP_LOGI(TAG, "%s connected (owner)", people.keys[slot].name);   // the right code: the owner now
  bool waiting = people.role(slot) == HUB_WAITING;
  if (waiting && !hubPermit(cmd, HUB_WAITING)) { people.forget(slot); xSemaphoreGive(keyMx); resp = "{\"err\":\"not paired\"}"; return 401; }
  xSemaphoreGive(keyMx);
  if (waiting) { resp = "{\"err\":\"waiting\"}"; return 403; }
  std::string out = hubCommand(slot, cmd);
  uint8_t rnd[12];
  esp_fill_random(rnd, sizeof rnd);
  resp = replySeal(key, f.cid, f.nonce, rnd, out);
  if (resp.empty()) { resp = "{\"err\":\"seal\"}"; return 500; }   // never an empty "200" (it was not checked before)
  return 200;
}
