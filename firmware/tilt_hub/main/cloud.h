// Push alerts through iCloud. Tilt has no server: the hub writes an "Alert" record to the app's CloudKit public
// database with CloudKit's server-to-server key, and every owner's phone has a subscription on that controller's
// topic, so iCloud pushes it to the phone, at home or away. Every alert the hub sends goes through alertRaise().
//
// A record holds only: the topic (a random name only phones that talked to the controller know), what happened
// (kind), which blind (port), the room's name, a short detail (a battery percent), a number and a time. No keys, no
// addresses (the same rule as the app's Cloud.swift).
//
// One record per topic, kind and blind ("alert-<topic>-<kind>-<port>"), replaced each time: the database never grows,
// and the phones' subscriptions fire on create and on update. Alerts wait in flash until iCloud has taken them (the
// internet may be down), and a retry after a lost answer first looks whether the record already has this number, so
// one alert never becomes two pushes.
//
// The key: main/cloud_key.h (not in Git; tools/cloudkit_key.py makes it), copied to flash at the first start, like
// the setup code. A public release carries no key: each hub keeps its own in flash.
#pragma once
#include <esp_tls.h>
#include <esp_heap_caps.h>
#include <esp_crt_bundle.h>                      // just the two roots in main/cloud_roots.pem (sdkconfig.defaults)
#include <mbedtls/ecdsa.h>
#include <mbedtls/sha256.h>
#include <mbedtls/base64.h>
#include <time.h>
#if __has_include("cloud_key.h") && !defined(TILT_RELEASE)
#include "cloud_key.h"                           // CLOUD_KEY_ID, CLOUD_KEY_ID_PROD, CLOUD_KEY_HEX
#endif
#ifndef CLOUD_KEY_ID
#define CLOUD_KEY_ID ""
#define CLOUD_KEY_ID_PROD ""
#define CLOUD_KEY_HEX ""
#endif

static const char CK_CONTAINER[] = "iCloud.app.tilt.blinds";
// The app built from Xcode listens in "development", the App Store app in "production": the hub writes to both.
static const char *const CK_ENVS[] = {"development", "production"};
static const int CK_NENV = 2;
static const int ALERT_Q = 10;                   // alerts waiting for iCloud at most (the oldest goes first if full)
static const uint32_t ALERT_KEEP_S = 7 * 86400;  // an alert not sent within a week is dropped

struct Alert {
  uint8_t used;
  uint8_t sent;                                  // a bit per environment: taken there
  uint8_t unsure;                                // a bit per environment: the last try had no answer (look first)
  uint8_t port;                                  // blind 0-2; 9 = the whole controller or the hub
  uint8_t topic[16];
  char kind[12];
  char name[33];
  char detail[24];
  uint32_t n;                                    // its number (flash "alertn")
  uint32_t at;                                   // when it happened (epoch s; 0 = the clock was not set yet)
};
static Alert alertq[ALERT_Q];
static uint32_t alertN = 0;
static SemaphoreHandle_t alertMx;
static TaskHandle_t cloudTaskH;
static char ckKeyId[2][80];                      // a key ID per environment (CloudKit keys are per environment; one key pair)
static uint8_t ckKey[32];
static bool ckKeyOk = false;
// What the app's hub page shows: how the last try went.
static volatile int ckLastStatus = 0;            // HTTP status of the last try (-1 no connection, 0 none yet)
static char ckLastErr[48];
static volatile uint32_t ckLastOkAt = 0;         // epoch s of the last alert iCloud took

static void alertsSave() { nvs_set_blob(nv, "alertq", alertq, sizeof alertq); nvs_set_u32(nv, "alertn", alertN); nvs_commit(nv); }

// Something to tell the owners. topic: the controller's (or the hub's own). Returns at once; sent when it can be.
static void alertRaise(const uint8_t topic[16], const char *kind, int port, const char *name, const char *detail = "") {
  if (!alertMx) return;
  bool any = false;
  for (int i = 0; i < 16; i++) any = any || topic[i];
  if (!any) { ESP_LOGW(TAG, "alert %s for %s not sent: no topic known yet", kind, name); return; }
  xSemaphoreTake(alertMx, portMAX_DELAY);
  int slot = -1, oldest = 0;
  for (int i = 0; i < ALERT_Q; i++) {
    if (!alertq[i].used) { if (slot < 0) slot = i; continue; }
    if (alertq[i].n < alertq[oldest].n || !alertq[oldest].used) oldest = i;
  }
  if (slot < 0) { ESP_LOGW(TAG, "alert queue full: dropping %s for %s", alertq[oldest].kind, alertq[oldest].name); slot = oldest; }
  Alert &a = alertq[slot];
  a = Alert{};
  a.used = 1; a.port = port < 0 ? 9 : port;
  memcpy(a.topic, topic, 16);
  strlcpy(a.kind, kind, sizeof a.kind); strlcpy(a.name, name, sizeof a.name); strlcpy(a.detail, detail, sizeof a.detail);
  a.n = ++alertN;
  time_t now = time(nullptr);
  a.at = now > 1700000000 ? (uint32_t)now : 0;
  alertsSave();
  xSemaphoreGive(alertMx);
  ESP_LOGI(TAG, "alert %lu: %s, %s%s%s", (unsigned long)a.n, kind, name, detail[0] ? ", " : "", detail);
  if (cloudTaskH) xTaskNotifyGive(cloudTaskH);
}

static std::string b64(const uint8_t *d, size_t n) {
  std::string o(((n + 2) / 3) * 4 + 1, 0);
  size_t on = 0;
  mbedtls_base64_encode((uint8_t *)&o[0], o.size(), &on, d, n);
  o.resize(on);
  return o;
}
// CloudKit's server-to-server signature: ECDSA P-256 (DER, base64) over "date:base64(sha256(body)):subpath".
static bool ckSign(const std::string &date, const std::string &body, const std::string &sub, std::string &sig) {
  uint8_t h[32];
  mbedtls_sha256((const uint8_t *)body.data(), body.size(), h, 0);
  std::string msg = date + ":" + b64(h, 32) + ":" + sub;
  mbedtls_sha256((const uint8_t *)msg.data(), msg.size(), h, 0);
  mbedtls_ecdsa_context k;
  mbedtls_ecdsa_init(&k);
  uint8_t der[MBEDTLS_ECDSA_MAX_LEN];
  size_t dn = 0;
  bool ok = mbedtls_ecp_read_key(MBEDTLS_ECP_DP_SECP256R1, &k, ckKey, 32) == 0 &&
            mbedtls_ecdsa_write_signature(&k, MBEDTLS_MD_SHA256, h, 32, der, sizeof der, &dn, rng, nullptr) == 0;
  mbedtls_ecdsa_free(&k);
  if (ok) sig = b64(der, dn);
  return ok;
}
// One signed request, straight over TLS (no HTTP library: the hub has little room). HTTP/1.0, so the answer is
// never in chunks. Returns the HTTP status (-1: no connection), the answer's body in resp.
// A TLS session takes about 30 KB of the hub's memory for a few seconds (measured 2026-11-24: about 50 KB free
// before, 18-25 KB at the lowest; ckPost logs it). With less than CK_NEED_HEAP free, or while a firmware file is
// coming in or going out, Wi-Fi and Matter could run short, so the alert waits (-2) until the hub is calmer.
static const size_t CK_NEED_HEAP = 45000;
static size_t ckMemBefore, ckMemLow, ckMemWorst = SIZE_MAX;   // the last send: free before and at its lowest; the lowest of any send
static bool cloudBusy();                         // hub.cpp: an update is on
static int ckPost(const char *env, const char *op, const std::string &body, std::string &resp) {
  static const char HOST[] = "api.apple-cloudkit.com";
  size_t freeBefore = esp_get_free_heap_size();
  if (cloudBusy() || freeBefore < CK_NEED_HEAP || heap_caps_get_largest_free_block(MALLOC_CAP_8BIT) < 12000) { strlcpy(ckLastErr, "waiting for memory", sizeof ckLastErr); return -2; }
  heap_caps_monitor_local_minimum_free_size_start();
  std::string sub = std::string("/database/1/") + CK_CONTAINER + "/" + env + "/public/records/" + op, sig;
  char date[64];
  time_t now = time(nullptr);
  struct tm g;
  gmtime_r(&now, &g);
  snprintf(date, sizeof date, "%04d-%02d-%02dT%02d:%02d:%02dZ", g.tm_year + 1900, g.tm_mon + 1, g.tm_mday, g.tm_hour, g.tm_min, g.tm_sec);
  resp.clear();
  if (!ckSign(date, body, sub, sig)) { strlcpy(ckLastErr, "could not sign", sizeof ckLastErr); return -1; }
  std::string req = "POST " + sub + " HTTP/1.0\r\nHost: " + HOST + "\r\nContent-Type: application/json\r\nContent-Length: " + std::to_string(body.size()) +
                    "\r\nX-Apple-CloudKit-Request-KeyID: " + ckKeyId[strcmp(env, CK_ENVS[0]) ? 1 : 0] + "\r\nX-Apple-CloudKit-Request-ISO8601Date: " + date +
                    "\r\nX-Apple-CloudKit-Request-SignatureV1: " + sig + "\r\n\r\n" + body;
  esp_tls_cfg_t cfg = {};
  cfg.crt_bundle_attach = esp_crt_bundle_attach;
  cfg.timeout_ms = 15000;
  esp_tls_t *tls = esp_tls_init();
  if (!tls) return -1;
  int st = -1;
  std::string all;
  if (esp_tls_conn_new_sync(HOST, sizeof HOST - 1, 443, &cfg, tls) == 1) {
    size_t off = 0;
    while (off < req.size()) {
      ssize_t w = esp_tls_conn_write(tls, req.data() + off, req.size() - off);
      if (w <= 0 && w != ESP_TLS_ERR_SSL_WANT_WRITE) break;
      if (w > 0) off += w;
    }
    char buf[512];
    for (;;) {
      ssize_t n = esp_tls_conn_read(tls, buf, sizeof buf);
      if (n == ESP_TLS_ERR_SSL_WANT_READ) continue;
      if (n <= 0 || all.size() > 6000) break;
      all.append(buf, n);
    }
    if (off == req.size() && all.compare(0, 5, "HTTP/") == 0 && all.size() > 12) st = atoi(all.c_str() + 9);
  }
  esp_tls_conn_destroy(tls);
  ckMemBefore = freeBefore; ckMemLow = esp_get_minimum_free_heap_size();
  if (ckMemLow < ckMemWorst) ckMemWorst = ckMemLow;
  ESP_LOGI(TAG, "iCloud %s: %d; memory free %u before, %u at the lowest", op, st, (unsigned)freeBefore, (unsigned)ckMemLow);
  heap_caps_monitor_local_minimum_free_size_stop();
  size_t hb = all.find("\r\n\r\n");
  if (hb != std::string::npos) resp = all.substr(hb + 4);
  return st;
}
static std::string jstr(const char *v) {        // a JSON string
  std::string o = "\"";
  for (const char *p = v; *p; p++) {
    unsigned char ch = *p;
    if (ch == '"' || ch == '\\') { o += '\\'; o += ch; }
    else if (ch < 0x20) { char e[8]; snprintf(e, sizeof e, "\\u%04x", ch); o += e; }
    else o += ch;
  }
  return o + "\"";
}
static std::string recordName(const Alert &a) { return "alert-" + hexOf(a.topic, 16) + "-" + a.kind + "-" + std::to_string(a.port); }
// Does iCloud already have this alert (an earlier try went through but its answer was lost)?
static bool ckHas(const char *env, const Alert &a) {
  std::string resp, body = "{\"records\":[{\"recordName\":\"" + recordName(a) + "\"}],\"desiredKeys\":[\"n\"]}";
  if (ckPost(env, "lookup", body, resp) != 200) return false;
  cJSON *j = cJSON_Parse(resp.c_str());
  cJSON *r = j ? cJSON_GetArrayItem(cJSON_GetObjectItem(j, "records"), 0) : nullptr;
  cJSON *n = r ? cJSON_GetObjectItem(cJSON_GetObjectItem(cJSON_GetObjectItem(r, "fields"), "n"), "value") : nullptr;
  bool has = cJSON_IsNumber(n) && (uint32_t)n->valuedouble == a.n;
  if (j) cJSON_Delete(j);
  return has;
}
// Send one alert to one environment. True when iCloud has it.
static bool ckSend(const char *env, Alert &a, bool unsure) {
  if (unsure && ckHas(env, a)) return true;
  auto str = [](const char *k, const std::string &v) { return std::string("\"") + k + "\":{\"value\":" + v + "}"; };
  uint64_t atMs = (uint64_t)(a.at ? a.at : (uint32_t)time(nullptr)) * 1000ULL;
  std::string body = "{\"operations\":[{\"operationType\":\"forceReplace\",\"record\":{\"recordType\":\"Alert\",\"recordName\":\"" + recordName(a) + "\",\"fields\":{" +
                     str("topic", "\"" + hexOf(a.topic, 16) + "\"") + "," + str("kind", jstr(a.kind)) + "," + str("name", jstr(a.name)) + "," +
                     str("detail", jstr(a.detail)) + "," + str("port", std::to_string(a.port)) + "," + str("n", std::to_string(a.n)) +
                     ",\"at\":{\"value\":" + std::to_string(atMs) + ",\"type\":\"TIMESTAMP\"}}}}]}", resp;
  int st = ckPost(env, "modify", body, resp);
  if (st == -2) return false;                    // not tried: too little memory just now
  ckLastStatus = st;
  bool ok = st == 200 && resp.find("serverErrorCode") == std::string::npos;
  if (ok) { ckLastErr[0] = 0; ckLastOkAt = (uint32_t)time(nullptr); return true; }
  // what went wrong, short (the USB log has it all)
  cJSON *j = cJSON_Parse(resp.c_str());
  cJSON *r = j ? cJSON_GetArrayItem(cJSON_GetObjectItem(j, "records"), 0) : nullptr;
  const char *why = cJSON_GetStringValue(cJSON_GetObjectItem(r ? r : j, "serverErrorCode"));
  snprintf(ckLastErr, sizeof ckLastErr, "%s: %s", env, why ? why : st < 0 ? "no connection" : ("HTTP " + std::to_string(st)).c_str());
  if (j) cJSON_Delete(j);
  ESP_LOGW(TAG, "iCloud %s: %d %.300s", env, st, resp.c_str());
  return false;
}
static bool netUp();
// Each environment goes on its own: one that fails (no schema there yet, say) waits longer and longer between tries,
// and never holds the other back.
static void cloudTask(void *) {
  uint32_t fails[CK_NENV] = {}, nextTry[CK_NENV] = {};
  uint32_t waitMs = 5000;
  for (;;) {
    ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(waitMs));
    waitMs = 30000;
    if (!ckKeyOk || !netUp() || time(nullptr) < 1700000000) continue;   // no key, no Wi-Fi or no clock yet: wait
    bool memWait = false;
    for (int e = 0; e < CK_NENV && !memWait; e++) {
      if (nextTry[e] && (int32_t)(nextTry[e] - ms()) > 0) continue;
      nextTry[e] = 0;
      for (;;) {                                 // this environment's waiting alerts, oldest first
        xSemaphoreTake(alertMx, portMAX_DELAY);
        int i = -1;
        uint32_t now = (uint32_t)time(nullptr);
        bool dropped = false;
        for (int k = 0; k < ALERT_Q; k++) {
          Alert &q = alertq[k];
          if (!q.used) continue;
          if (!q.at) q.at = now;                 // happened before the clock was set: about now
          if (now - q.at > ALERT_KEEP_S) { ESP_LOGW(TAG, "alert %lu (%s) too old: dropped", (unsigned long)q.n, q.kind); q.used = 0; dropped = true; continue; }
          if (q.sent & (1 << e)) continue;
          if (i < 0 || q.n < alertq[i].n) i = k;
        }
        if (dropped) alertsSave();
        Alert a = i >= 0 ? alertq[i] : Alert{};
        xSemaphoreGive(alertMx);
        if (i < 0) break;
        bool ok = ckSend(CK_ENVS[e], a, a.unsure & (1 << e));
        if (!ok && !strcmp(ckLastErr, "waiting for memory")) { memWait = true; break; }   // not a failure: again in a minute
        xSemaphoreTake(alertMx, portMAX_DELAY);
        if (alertq[i].used && alertq[i].n == a.n) {
          Alert &q = alertq[i];
          if (ok) { q.sent |= 1 << e; q.unsure &= ~(1 << e); }
          else if (ckLastStatus < 0 || ckLastStatus >= 500) q.unsure |= 1 << e;   // it may have gone through
          if (q.sent == (1 << CK_NENV) - 1) q.used = 0;
          alertsSave();
        }
        xSemaphoreGive(alertMx);
        if (ok) { ESP_LOGI(TAG, "alert %lu (%s, %s) sent to %s", (unsigned long)a.n, a.kind, a.name, CK_ENVS[e]); fails[e] = 0; continue; }
        fails[e]++;
        uint32_t back = fails[e] > 6 ? 900000 : 15000u << fails[e];   // 30 s, 1 min, ... up to 15 minutes
        nextTry[e] = (ms() + back) | 1;
        ESP_LOGW(TAG, "alert %lu not sent to %s yet (%s): again in %lu s", (unsigned long)a.n, CK_ENVS[e], ckLastErr, (unsigned long)(back / 1000));
        break;
      }
    }
    if (memWait) { waitMs = 60000; continue; }
    for (int e = 0; e < CK_NENV; e++)            // wake for the next environment that is backing off
      if (nextTry[e]) { int32_t left = (int32_t)(nextTry[e] - ms()); waitMs = left < 1000 ? 1000 : (uint32_t)left < waitMs ? (uint32_t)left : waitMs; }
  }
}
static int alertsWaiting() {
  int n = 0;
  for (auto &a : alertq) n += a.used ? 1 : 0;
  return n;
}
// For the app's hub page: is there a key, how many wait, how the last try went.
static std::string cloudJson() {
  return std::string("\"cloud\":{\"key\":") + (ckKeyOk ? "1" : "0") + ",\"wait\":" + std::to_string(alertsWaiting()) + ",\"st\":" + std::to_string(ckLastStatus) +
         ",\"okAt\":" + std::to_string(ckLastOkAt) +
         (ckMemBefore ? ",\"mem\":[" + std::to_string(ckMemBefore) + "," + std::to_string(ckMemLow) + "," + std::to_string(ckMemWorst) + "]" : std::string()) + (ckLastErr[0] ? ",\"err\":\"" + std::string(ckLastErr) + "\"" : std::string()) + "}";
}
static void cloudBegin() {
  alertMx = xSemaphoreCreateMutex();
  size_t n = sizeof alertq;
  if (nvs_get_blob(nv, "alertq", alertq, &n) != ESP_OK || n != sizeof alertq) memset(alertq, 0, sizeof alertq);
  nvs_get_u32(nv, "alertn", &alertN);
  // The key from cloud_key.h goes to flash (a newer build may bring a new key); a release build uses what is there.
  if (CLOUD_KEY_ID[0] && strlen(CLOUD_KEY_HEX) == 64) {
    char have[80] = {0}, haveP[80] = {0};
    size_t a = sizeof have, b = sizeof haveP;
    nvs_get_str(nv, "ckid", have, &a);
    nvs_get_str(nv, "ckidp", haveP, &b);
    uint8_t k[32];
    if ((strcmp(have, CLOUD_KEY_ID) || strcmp(haveP, CLOUD_KEY_ID_PROD)) && unhex(CLOUD_KEY_HEX, k, 32)) {
      nvs_set_str(nv, "ckid", CLOUD_KEY_ID); nvs_set_str(nv, "ckidp", CLOUD_KEY_ID_PROD); nvs_set_blob(nv, "ckkey", k, 32); nvs_commit(nv);
      ESP_LOGI(TAG, "iCloud key saved");
    }
  }
  size_t kn = sizeof ckKey;
  for (int e = 0; e < CK_NENV; e++) { n = sizeof ckKeyId[e]; if (nvs_get_str(nv, e ? "ckidp" : "ckid", ckKeyId[e], &n) != ESP_OK) ckKeyId[e][0] = 0; }
  ckKeyOk = ckKeyId[0][0] && nvs_get_blob(nv, "ckkey", ckKey, &kn) == ESP_OK && kn == 32;
  if (!ckKeyOk) ESP_LOGW(TAG, "no iCloud key: alerts wait in flash (tools/cloudkit_key.py)");
  xTaskCreate(cloudTask, "cloud", 8192, nullptr, 3, &cloudTaskH);
}
