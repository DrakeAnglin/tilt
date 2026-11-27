// What every command handler uses to read its command and answer it: a secured command (sec.h secDo) that came
// over Bluetooth or through the Tilt Hub. (There is no web server: httpd_req_t is only the handlers' signature.)
// Also the handlers' lock (Lock) and the request bookkeeping beside it.
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
std::string arg(httpd_req_t *r, const char *key) {       // a value from the address's ?a=b&c=d part, decoded (wire.h)
  return secQuery ? queryValue(secQuery, key) : std::string();
}
int argi(httpd_req_t *r, const char *key) { return atoi(arg(r, key).c_str()); }
esp_err_t sendJson(httpd_req_t *r, const std::string &j) {
  if (!secOut) return ESP_FAIL;                  // not inside a secured command: nobody to answer
  *secOut = j;                                   // secDo seals it
  return ESP_OK;
}
esp_err_t ok(httpd_req_t *r) { return sendJson(r, "{\"ok\":1}"); }
esp_err_t fail(httpd_req_t *r, const char *e) { return sendJson(r, std::string("{\"ok\":0,\"err\":") + jq(e) + "}"); }
esp_err_t done(httpd_req_t *r, const char *e) { return e ? fail(r, e) : ok(r); }
struct QuietLock {                        // mx for a moment, from a task that is not handling a request (it does not count as use)
  QuietLock() { xSemaphoreTake(mx, portMAX_DELAY); }
  ~QuietLock() { xSemaphoreGive(mx); }
};
struct Lock {                             // every handler holds this (mx, lock.h) while it touches the blinds
  Lock() { xSemaphoreTake(mx, portMAX_DELAY); lastWeb = millis() ? millis() : 1; }
  ~Lock() { xSemaphoreGive(mx); pokeBlinds(); }
};
