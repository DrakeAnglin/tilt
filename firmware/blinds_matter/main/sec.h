// The secured connection for the phone app. No accounts, no server: each phone that is paired holds its own 256-bit
// key, and every command is encrypted and authenticated with it (AES-256-GCM). Nothing else on the network can read
// the blinds' state or move them.
//
//   GET  /x/hello   who am I: id, name, firmware, this start's number ("boot"), is there an owner yet
//   POST /x/pair    make a key. JSON {"pub": base64 P-256 public key, "name": "..."}
//                   Only for the first phone (it becomes an owner). Both sides do ECDH; the key is HKDF-SHA256 of the result.
//   POST /x/ask     ask to join a controller that has an owner. Same JSON as /x/pair. The key is made
//                   but does nothing until an owner approves it in the app (/api/approve). Both phones show the
//                   same 4-digit code, made from the key, so the owner can tell it is the right phone.
//   POST /x         a command. Bytes: client id (8) | nonce (12) | ciphertext | tag (16)
//                   nonce = boot (4) | counter (8, must rise). Plain text inside: "/api/go?b=0&t=50".
//                   The answer comes back the same way: nonce (12) | ciphertext | tag.
//
// A captured command cannot be replayed: the counter must rise, and after a restart the boot number is new.
#pragma once
#include <mbedtls/ecdh.h>
#include <mbedtls/ecp.h>
#include <mbedtls/gcm.h>
#include <mbedtls/hkdf.h>
#include <mbedtls/md.h>
#include <mbedtls/base64.h>
#include <esp_random.h>
#include <esp_http_server.h>
#include "ardu.h"
#include "logic.h"                               // nonceFresh, permitRule
#include "store.h"                               // nvs, event, cleanText
#include "lock.h"                                // mx

const int MAX_KEYS = 8;
struct ClientKey { uint8_t used, role; uint8_t id[8]; uint8_t key[32]; char name[20]; };   // used 1 = paired, 2 = asked to join, waiting for an owner; role 1 = owner
ClientKey keys[MAX_KEYS];
uint64_t lastCtr[MAX_KEYS];
uint8_t bootId[4];
// A random name for this controller in the iCloud notices the phones send each other (a request to join, a removal).
// Only phones that have talked to the controller know it, so nobody else can send its owners a notice.
uint8_t cloudTopic[16];
// The command being handled. Only set and read while secMx is held: one secured command runs at a time, whether it
// came over Wi-Fi or Bluetooth, so these never belong to two requests at once.
int secClient = -1;                            // which key the command came with (-1: not a secured one)
const char *secQuery = nullptr;                // its "a=b&c=d" part, for arg()
std::string *secOut = nullptr;                 // where its answer goes, for sendJson()
SemaphoreHandle_t secMx = nullptr;             // one secured command at a time (Wi-Fi and Bluetooth share the handlers)
// keys[] and lastCtr[] are guarded by the controller lock (mx, lock.h), the one every handler and the main loop
// already hold when they touch shared state. Lock order: secMx, then mx; nothing holding mx may take secMx.
struct KeysLock { KeysLock() { xSemaphoreTake(mx, portMAX_DELAY); } ~KeysLock() { xSemaphoreGive(mx); } };

uint8_t openApi = 0;                           // 1: the plain /api answers even once a phone is paired (owner's choice, off by default)
static int secRng(void *, unsigned char *b, size_t n) { esp_fill_random(b, n); return 0; }
void keysSave() { nvs.putBytes("keys", keys, sizeof keys); }
void secBegin() {
  if (nvs.getBytes("keys", keys, sizeof keys) != sizeof keys) memset(keys, 0, sizeof keys);
  esp_fill_random(bootId, sizeof bootId);
  if (nvs.getBytes("topic", cloudTopic, sizeof cloudTopic) != sizeof cloudTopic) { esp_fill_random(cloudTopic, sizeof cloudTopic); nvs.putBytes("topic", cloudTopic, sizeof cloudTopic); }
  memset(lastCtr, 0, sizeof lastCtr);
  openApi = nvs.getUChar("plainopen", 0);     // new key: the old "openapi" defaulted to open, so it is ignored
  secMx = xSemaphoreCreateMutex();
}
bool owned() { for (auto &k : keys) if (k.used == 1) return true; return false; }
int asksWaiting() { int n = 0; for (auto &k : keys) if (k.used == 2) n++; return n; }
std::string hexOf(const uint8_t *b, int n) { static const char *H = "0123456789abcdef"; std::string s; for (int i = 0; i < n; i++) { s += H[b[i] >> 4]; s += H[b[i] & 15]; } return s; }
bool unhex(const std::string &s, uint8_t *out, size_t n) {
  if (s.length() != n * 2) return false;
  for (size_t i = 0; i < n; i++) { char h[3] = {s[2 * i], s[2 * i + 1], 0}; char *e; out[i] = strtol(h, &e, 16); if (*e) return false; }
  return true;
}
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
bool hmac256(const uint8_t *key, size_t kn, const uint8_t *d, size_t dn, uint8_t out[32]) {
  return mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), key, kn, d, dn, out) == 0;
}
bool gcm(bool enc, const uint8_t key[32], const uint8_t nonce[12], const uint8_t *aad, size_t an, const uint8_t *in, size_t n, uint8_t *out, uint8_t tag[16]) {
  mbedtls_gcm_context g;
  mbedtls_gcm_init(&g);
  bool ok = mbedtls_gcm_setkey(&g, MBEDTLS_CIPHER_ID_AES, key, 256) == 0;
  if (ok) ok = enc ? mbedtls_gcm_crypt_and_tag(&g, MBEDTLS_GCM_ENCRYPT, n, nonce, 12, aad, an, in, out, 16, tag) == 0
                   : mbedtls_gcm_auth_decrypt(&g, n, nonce, 12, aad, an, tag, 16, in, out) == 0;
  mbedtls_gcm_free(&g);
  return ok;
}
std::string body(httpd_req_t *r, size_t maxLen) {
  std::string b;
  if (r->content_len > maxLen) return b;
  b.resize(r->content_len);
  size_t got = 0;
  while (got < b.size()) {
    int n = httpd_req_recv(r, &b[got], b.size() - got);
    if (n == HTTPD_SOCK_ERR_TIMEOUT) continue;
    if (n <= 0) return "";
    got += n;
  }
  return b;
}
esp_err_t plain(httpd_req_t *r, const char *status, const std::string &j) {
  httpd_resp_set_status(r, status);
  httpd_resp_set_type(r, "application/json");
  return httpd_resp_send(r, j.c_str(), j.size());
}

// ---- pairing
// Returns the HTTP-style status ("200 OK", ...) and fills out with the JSON answer. Used over Wi-Fi and Bluetooth.
const char *pairDo(const std::string &b, std::string &out, bool ask = false) {
  std::string pubB64 = jsonStr(b, "pub");
  uint8_t cpub[65];
  size_t n = 0;
  if (mbedtls_base64_decode(cpub, sizeof cpub, &n, (const uint8_t *)pubB64.c_str(), pubB64.length()) != 0 || n != 65) { out = "{\"err\":\"bad key\"}"; return "400 Bad Request"; }
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
  }

  mbedtls_ecp_group grp; mbedtls_mpi d, z; mbedtls_ecp_point Q, Qp;
  mbedtls_ecp_group_init(&grp); mbedtls_mpi_init(&d); mbedtls_mpi_init(&z); mbedtls_ecp_point_init(&Q); mbedtls_ecp_point_init(&Qp);
  uint8_t dpub[65], shared[32], okm[32], info[9 + 130];
  size_t dn = 0;
  bool ok = mbedtls_ecp_group_load(&grp, MBEDTLS_ECP_DP_SECP256R1) == 0 && mbedtls_ecdh_gen_public(&grp, &d, &Q, secRng, nullptr) == 0 &&
            mbedtls_ecp_point_read_binary(&grp, &Qp, cpub, 65) == 0 && mbedtls_ecp_check_pubkey(&grp, &Qp) == 0 &&
            mbedtls_ecdh_compute_shared(&grp, &z, &Qp, &d, secRng, nullptr) == 0 && mbedtls_mpi_write_binary(&z, shared, 32) == 0 &&
            mbedtls_ecp_point_write_binary(&grp, &Q, MBEDTLS_ECP_PF_UNCOMPRESSED, &dn, dpub, sizeof dpub) == 0 && dn == 65;
  if (ok) {
    memcpy(info, "blinds-v1", 9); memcpy(info + 9, cpub, 65); memcpy(info + 74, dpub, 65);
    ok = mbedtls_hkdf(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), nullptr, 0, shared, 32, info, sizeof info, okm, 32) == 0;
  }
  mbedtls_ecp_group_free(&grp); mbedtls_mpi_free(&d); mbedtls_mpi_free(&z); mbedtls_ecp_point_free(&Q); mbedtls_ecp_point_free(&Qp);
  if (!ok) { out = "{\"err\":\"key exchange failed\"}"; return "400 Bad Request"; }

  KeysLock kl;                                 // the key is ready: claim a slot now (the slow part ran unlocked)
  if (!first != owned()) { out = "{\"err\":\"another phone paired at the same moment. Try again.\"}"; return "409 Conflict"; }
  int slot = -1;
  if (ask && asksWaiting() >= 2) { for (int i = 0; i < MAX_KEYS; i++) if (keys[i].used == 2) { slot = i; break; } }   // at most two waiting: a new ask takes the place of an old one
  else for (int i = 0; i < MAX_KEYS; i++) if (!keys[i].used) { slot = i; break; }
  if (slot < 0) { out = "{\"err\":\"no room for another phone\"}"; return "403 Forbidden"; }
  ClientKey &k = keys[slot];
  memset(&k, 0, sizeof k);
  k.used = ask ? 2 : 1; k.role = first ? 1 : 0;
  esp_fill_random(k.id, 8);
  memcpy(k.key, okm, 32);
  cleanText(k.name, sizeof k.name, jsonStr(b, "name"));
  if (!k.name[0]) strlcpy(k.name, "iPhone", sizeof k.name);
  keysSave();
  lastCtr[slot] = 0;
  event(ask ? "%s asked to join%s" : "%s paired%s", k.name, first ? " (owner)" : "");
  uint8_t chk[32], pb[100];
  hmac256(okm, 32, (const uint8_t *)"confirm", 7, chk);
  size_t pn = 0;
  mbedtls_base64_encode(pb, sizeof pb, &pn, dpub, 65);
  out = std::string("{\"pub\":\"") + std::string((char *)pb, pn) + "\",\"cid\":\"" + hexOf(k.id, 8) + "\",\"check\":\"" + hexOf(chk, 8) + "\",\"owner\":" + (first ? "1" : "0") + ",\"wait\":" + (ask ? "1" : "0") + ",\"topic\":\"" + hexOf(cloudTopic, 16) + "\"}";
  return "200 OK";
}
esp_err_t hPair(httpd_req_t *r) { std::string out; const char *st = pairDo(body(r, 600), out); return plain(r, st, out); }
esp_err_t hAsk(httpd_req_t *r) { std::string out; const char *st = pairDo(body(r, 600), out, true); return plain(r, st, out); }
// The 4 digits both phones show for a request to join.
std::string askCode(const ClientKey &k) {
  uint8_t h[32]; char c[6];
  hmac256(k.key, 32, (const uint8_t *)"code", 4, h);
  snprintf(c, sizeof c, "%04u", (unsigned)(((h[0] << 8) | h[1]) % 10000));
  return c;
}


// ---- commands
struct Route { const char *uri; httpd_method_t m; esp_err_t (*fn)(httpd_req_t *); };
extern const Route routes[];
extern const int routeCount;
// ---- who may do what: the one place every request is decided (plain HTTP, and secured over Wi-Fi or Bluetooth)
struct Caller {
  bool secure;                                   // came over the secured connection (else: plain HTTP)
  bool owner;                                    // secured: the phone is an owner (else a user)
  const uint8_t *id;                             // secured: the phone's 8-byte id
};
esp_err_t hUpdate(httpd_req_t *r);
std::string qarg(const std::string &query, const char *key) {
  char v[80] = "";
  return httpd_query_key_value(query.c_str(), key, v, sizeof v) == ESP_OK ? std::string(v) : std::string();
}
// nullptr: allowed. Otherwise the reason it is refused. Rules about the target (you cannot remove yourself, the last
// owner stays) live in the handlers; who the caller is and what that lets them do is decided only here.
const char *permit(const Route *rt, const std::string &path, const std::string &query, const Caller &c) {
  return permitRule(c.secure, c.owner, !owned() || openApi, rt->fn == hUpdate, path,
                    c.secure ? qarg(query, "cid") : std::string(), c.secure ? hexOf(c.id, 8) : std::string());
}
// The answer is sealed bytes when the status is "200 OK", plain JSON otherwise.
const char *secDo(const std::string &b, std::string &resp, httpd_req_t *r) {
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
    if (keys[slot].used != 1) {                  // still waiting for an owner: the only thing it may do is take its request back
      if (cmd == "/api/leave") { event("%s took the request back", keys[slot].name); memset(&keys[slot], 0, sizeof keys[slot]); keysSave(); resp = "{\"err\":\"not paired\"}"; return "401 Unauthorized"; }
      resp = "{\"err\":\"waiting\"}"; return "403 Forbidden";
    }
    owner = keys[slot].role;
  }

  size_t q = cmd.find('?');
  std::string path = cmd.substr(0, q), query = q == std::string::npos ? "" : cmd.substr(q + 1), out;
  const Route *rt = nullptr;
  for (int i = 0; i < routeCount; i++) if (path == routes[i].uri && routes[i].m == HTTP_GET && !path.compare(0, 5, "/api/")) rt = &routes[i];
  if (!rt) out = "{\"ok\":0,\"err\":\"unknown command\"}";
  else if (const char *why = permit(rt, path, query, Caller{true, owner, p})) out = std::string("{\"ok\":0,\"err\":\"") + why + "\"}";
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
esp_err_t hSecure(httpd_req_t *r) {
  std::string resp;
  const char *st = secDo(body(r, 2200), resp, r);
  if (strcmp(st, "200 OK")) return plain(r, st, resp);
  httpd_resp_set_type(r, "application/octet-stream");
  return httpd_resp_send(r, resp.data(), resp.size());
}
