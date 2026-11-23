// What every web handler uses to read a request and answer it, whether it came as plain HTTP or as a secured
// command (sec.h) over Bluetooth or through the Tilt Hub. Also the handlers' lock (Lock) and the request bookkeeping beside it.
#pragma once
#include <esp_http_server.h>
#include "ardu.h"
#include "lock.h"                                // mx
#include "sec.h"                                 // secQuery, secOut: the secured command being handled
#include "wire.h"                                // ap, jq, jn

uint32_t lastWeb = 0;                    // millis of the last request (0 = none yet)
bool restartSoon = false;                // restart once the answer has gone out (webTick)
void pokeBlinds();                       // app_main.cpp: wake the blinds task

// ---- small helpers (ap, jq, jn: wire.h)
std::string arg(httpd_req_t *r, const char *key) {       // a value from the address's ?a=b&c=d part, decoded
  char q[600], v[300];
  if (secQuery) { if (httpd_query_key_value(secQuery, key, v, sizeof v) != ESP_OK) return ""; }      // a secured command
  else if (httpd_req_get_url_query_str(r, q, sizeof q) != ESP_OK || httpd_query_key_value(q, key, v, sizeof v) != ESP_OK) return "";
  std::string o;
  for (char *p = v; *p; p++) {
    if (*p == '+') o += ' ';
    else if (*p == '%' && isxdigit((unsigned char)p[1]) && isxdigit((unsigned char)p[2])) { char h[3] = {p[1], p[2], 0}; o += (char)strtol(h, nullptr, 16); p += 2; }
    else o += *p;
  }
  return o;
}
int argi(httpd_req_t *r, const char *key) { return atoi(arg(r, key).c_str()); }
esp_err_t sendJson(httpd_req_t *r, const std::string &j) {
  if (secOut) { *secOut = j; return ESP_OK; }    // a secured command: the answer is sealed by hSecure
  httpd_resp_set_type(r, "application/json");
  httpd_resp_set_hdr(r, "Cache-Control", "no-store");
  return httpd_resp_send(r, j.c_str(), j.size());
}
esp_err_t ok(httpd_req_t *r) { return sendJson(r, "{\"ok\":1}"); }
esp_err_t fail(httpd_req_t *r, const char *e) { return sendJson(r, std::string("{\"ok\":0,\"err\":") + jq(e) + "}"); }
esp_err_t done(httpd_req_t *r, const char *e) { return e ? fail(r, e) : ok(r); }
struct Lock {                             // every handler holds this (mx, lock.h) while it touches the blinds
  Lock() { xSemaphoreTake(mx, portMAX_DELAY); lastWeb = millis() ? millis() : 1; }
  ~Lock() { xSemaphoreGive(mx); pokeBlinds(); }
};
