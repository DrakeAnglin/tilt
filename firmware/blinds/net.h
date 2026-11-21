// Wi-Fi, the setup network (when the home Wi-Fi can't be joined), updates over Wi-Fi with automatic rollback, time.
#pragma once
#include <WiFi.h>
#include <ESPmDNS.h>
#include <ArduinoOTA.h>
#include <DNSServer.h>
#include <esp_ota_ops.h>
#include <esp_sntp.h>
#include "secrets.h"
#include "motion.h"

DNSServer dns;
bool apOn = false, wifiStarted = false, otaBusy = false, otaPending = false, mdnsUp = false;
uint32_t wifiT0 = 0, lastNtp = 0;

// A new firmware is only kept once it has joined Wi-Fi and served a page. Until then a reset rolls back to the old one.
extern "C" bool verifyRollbackLater() { return true; }
bool otaIsPending() {
  esp_ota_img_states_t st;
  return esp_ota_get_state_partition(esp_ota_get_running_partition(), &st) == ESP_OK && st == ESP_OTA_IMG_PENDING_VERIFY;
}

bool uiActive() { return lastActivity && millis() - lastActivity < 8000; }
bool timeValid() { return time(nullptr) > 1700000000; }
const char *wifiSsid() { return cfg.ssid[0] ? cfg.ssid : WIFI_SSID; }
const char *wifiPass() { return cfg.ssid[0] ? cfg.pass : WIFI_PASSWORD; }

void applyTz() { setenv("TZ", cfg.tz, 1); tzset(); }

void allOff() {                                  // before an update or a sleep: every motor braked, every driver asleep
  stopAll("stopped");
  for (int i = 0; i < PORTS; i++) { ledcWrite(P_IN1[i], 255); ledcWrite(P_IN2[i], 255); digitalWrite(P_EN[i], LOW); }
  motorOn = false;
}

void startAp() {
  if (apOn) return;
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP(AP_NAME);
  dns.start(53, "*", WiFi.softAPIP());           // any address opens the setup page
  apOn = true;
  event("setup network '%s' open (http://192.168.4.1)", AP_NAME);
}
void stopAp() {
  if (!apOn) return;
  dns.stop();
  WiFi.softAPdisconnect(true);
  WiFi.mode(WIFI_STA);
  apOn = false;
  event("setup network closed");
}

void netBegin() {
  applyTz();
  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(DEFAULT_HOSTNAME);
  WiFi.setAutoReconnect(true);
  WiFi.begin(wifiSsid(), wifiPass());
  WiFi.setTxPower((wifi_power_t)(constrain((int)cfg.txPower, 8, 20) * 4));   // units of 0.25 dBm
  wifiStarted = true;
  wifiT0 = millis();
  otaPending = otaIsPending();

  ArduinoOTA.setHostname(DEFAULT_HOSTNAME);
  ArduinoOTA.setPassword(OTA_PASSWORD);
  ArduinoOTA.onStart([]() { otaBusy = true; allOff(); });
  ArduinoOTA.onEnd([]() { statsSave(); });
  ArduinoOTA.onError([](ota_error_t) { otaBusy = false; });
}

void netTick() {
  static bool was = false, servicesUp = false;
  bool up = WiFi.status() == WL_CONNECTED;
  uint32_t now = millis();
  if (up && !was) {
    event("Wi-Fi joined: %s, %s, %d dBm", WiFi.SSID().c_str(), WiFi.localIP().toString().c_str(), WiFi.RSSI());
    if (!servicesUp) {
      mdnsUp = MDNS.begin(DEFAULT_HOSTNAME);
      ArduinoOTA.begin();
      MDNS.addService("http", "tcp", 80);
      servicesUp = true;
    }
    configTzTime(cfg.tz, "pool.ntp.org", "time.apple.com");
    if (apOn) stopAp();
  }
  if (!up && was) event("Wi-Fi lost");
  was = up;
  if (servicesUp) ArduinoOTA.handle();
  if (apOn) dns.processNextRequest();
  if (!up && !apOn && !otaPending && now - wifiT0 > WIFI_FALLBACK_AP_MS && (powered || now < 600000)) startAp();

  // new firmware: keep it once it is on Wi-Fi and has answered a browser (or 30 s on Wi-Fi); give up after 2 minutes
  if (otaPending) {
    static uint32_t upSince = 0;
    if (up && !upSince) upSince = now;
    if (up && (lastActivity || now - upSince > 30000)) {
      esp_ota_mark_app_valid_cancel_rollback();
      otaPending = false;
      stats.otaOk++;
      statsSave();
      event("new firmware %s confirmed", FW_VERSION);
    } else if (!up && now > OTA_VERIFY_MS) {
      event("new firmware could not join Wi-Fi: rolling back");
      delay(100);
      esp_ota_mark_app_invalid_rollback_and_reboot();
    }
  }
}
