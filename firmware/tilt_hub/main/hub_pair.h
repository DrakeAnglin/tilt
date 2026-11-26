// The ESP side of the hub's people (the rules are hub_people.h): keys and setup code from flash, the hub's id, the
// key exchange for a new phone, and opening a phone's sealed command. Part of hub.cpp.
#pragma once
static std::string hubCommand(int slot, const std::string &cmd);  // hub_api.h
// ---- the hub's people (hub_people.h: the rules, tested on the Mac). keyMx guards people.
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
static bool hubOwned() { return people.owned(); }
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
static std::string askCode(const HubKey &k) {
  uint8_t h[32]; char c[6];
  mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), k.key, 32, (const uint8_t *)"code", 4, h);
  snprintf(c, sizeof c, "%04u", (unsigned)(((h[0] << 8) | h[1]) % 10000));
  return c;
}
static std::string jsonStr(const std::string &j, const char *key) {
  cJSON *o = cJSON_Parse(j.c_str());
  const char *v = o ? cJSON_GetStringValue(cJSON_GetObjectItem(o, key)) : nullptr;
  std::string r = v ? v : "";
  if (o) cJSON_Delete(o);
  return r;
}
static void cleanName(char *out, size_t n, const std::string &in) {
  size_t k = 0;
  for (char ch : in) if (k + 1 < n && (unsigned char)ch >= 32 && ch != '"' && ch != '\\') out[k++] = ch;
  out[k] = 0;
}
// pair (first phone, becomes the owner) or ask (later phones; waits for an owner)
static int pairDo(const std::string &b, std::string &out, bool ask) {
  std::string pubB64 = jsonStr(b, "pub");
  uint8_t cpub[65];
  size_t n = 0;
  if (mbedtls_base64_decode(cpub, sizeof cpub, &n, (const uint8_t *)pubB64.c_str(), pubB64.length()) != 0 || n != 65) { out = "{\"err\":\"bad key\"}"; return 400; }
  bool first = false;
  const char *why = nullptr;
  xSemaphoreTake(keyMx, portMAX_DELAY);
  int st = people.pairGate(ask, first, why);
  xSemaphoreGive(keyMx);
  if (st) { out = std::string("{\"err\":\"") + why + "\"}"; return st; }
  mbedtls_ecp_group grp; mbedtls_mpi d, z; mbedtls_ecp_point Q, Qp;
  mbedtls_ecp_group_init(&grp); mbedtls_mpi_init(&d); mbedtls_mpi_init(&z); mbedtls_ecp_point_init(&Q); mbedtls_ecp_point_init(&Qp);
  uint8_t dpub[65], shared[32], okm[32], okm0[32], info[9 + 130];   // okm0: the same without the setup code (for the check)
  size_t dn = 0;
  bool ok = mbedtls_ecp_group_load(&grp, MBEDTLS_ECP_DP_SECP256R1) == 0 && mbedtls_ecdh_gen_public(&grp, &d, &Q, rng, nullptr) == 0 &&
            mbedtls_ecp_point_read_binary(&grp, &Qp, cpub, 65) == 0 && mbedtls_ecp_check_pubkey(&grp, &Qp) == 0 &&
            mbedtls_ecdh_compute_shared(&grp, &z, &Qp, &d, rng, nullptr) == 0 && mbedtls_mpi_write_binary(&z, shared, 32) == 0 &&
            mbedtls_ecp_point_write_binary(&grp, &Q, MBEDTLS_ECP_PF_UNCOMPRESSED, &dn, dpub, sizeof dpub) == 0 && dn == 65;
  if (ok) {
    memcpy(info, "blinds-v1", 9); memcpy(info + 9, cpub, 65); memcpy(info + 74, dpub, 65);
    // The first owner's key also takes the setup code (as the HKDF salt): the phone must know it.
    const char *salt = first ? setupPin : "";
    ok = mbedtls_hkdf(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), (const uint8_t *)salt, strlen(salt), shared, 32, info, sizeof info, okm, 32) == 0 &&
         mbedtls_hkdf(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), nullptr, 0, shared, 32, info, sizeof info, okm0, 32) == 0;
  }
  mbedtls_ecp_group_free(&grp); mbedtls_mpi_free(&d); mbedtls_mpi_free(&z); mbedtls_ecp_point_free(&Q); mbedtls_ecp_point_free(&Qp);
  if (!ok) { out = "{\"err\":\"key exchange failed\"}"; return 400; }
  xSemaphoreTake(keyMx, portMAX_DELAY);
  int slot = people.pairPlace(ask, st, why);
  if (slot < 0) { xSemaphoreGive(keyMx); out = std::string("{\"err\":\"") + why + "\"}"; return st; }
  uint8_t id[8];
  char name[sizeof(HubKey::name)];
  esp_fill_random(id, 8);
  cleanName(name, sizeof name, jsonStr(b, "name"));
  people.pairTake(slot, ask, first, id, okm, name);
  HubKey &k = people.keys[slot];
  if (ask) ESP_LOGI(TAG, "%s asked to join the hub", k.name); else ESP_LOGI(TAG, "%s is connecting (owner, once its code is right)", k.name);
  uint8_t chk[32], pb[100];
  mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), okm0, 32, (const uint8_t *)"confirm", 7, chk);   // never from the code
  size_t pn = 0;
  mbedtls_base64_encode(pb, sizeof pb, &pn, dpub, 65);
  out = std::string("{\"pub\":\"") + std::string((char *)pb, pn) + "\",\"cid\":\"" + hexOf(k.id, 8) + "\",\"check\":\"" + hexOf(chk, 8) + "\",\"owner\":" + (first ? "1" : "0") +
        ",\"wait\":" + (ask ? "1" : "0") + ",\"topic\":\"" + hexOf(htopic, 16) + "\",\"code\":\"" + (ask ? askCode(k) : std::string()) + "\"}";
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
