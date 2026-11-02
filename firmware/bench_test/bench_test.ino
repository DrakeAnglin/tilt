// Bench test for one tilter (docs/bench-test.md). ESP32-C6, Arduino-ESP32 core 3.x.
// Commands, over USB serial (115200) or over Wi-Fi (telnet / nc to blinds-bench.local port 23):
//   e = EN on   x = EN off   f = forward   r = reverse   s = stop (brake)
//   0..9 = duty 0..100 %     a = print angle continuously on/off
// Updates over Wi-Fi after the first USB flash: Arduino IDE -> Port -> "blinds-bench at <ip>" (network port).
// Wi-Fi name / password / update password go in secrets.h (copy secrets.h.example; secrets.h is not committed).
#include <Arduino.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <ArduinoOTA.h>
#include "secrets.h"

const int PIN_IN1 = 19, PIN_IN2 = 20, PIN_EN = 1, PIN_ANGLE = 0;   // bench rig (fixed; see docs/bench-test.md)
const int PWM_HZ = 20000, PWM_BITS = 8;
const char *HOSTNAME = "blinds-bench";

int duty = 255;            // 0..255
int dir = 0;               // 1 forward, -1 reverse, 0 stopped
bool streaming = false;
WiFiServer server(23);
WiFiClient client;

// print to USB serial and, if someone is connected over Wi-Fi, to them too
void say(const char *fmt, ...) {
  char buf[128];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(buf, sizeof buf, fmt, ap);
  va_end(ap);
  if (Serial) Serial.print(buf);                // only when a USB host is listening (no stalls on battery)
  if (client && client.connected()) client.print(buf);
}

void drive() {
  // DRV8833 slow decay: one input high, PWM the other inverted (high = brake)
  if (dir > 0) { ledcWrite(PIN_IN1, 255); ledcWrite(PIN_IN2, 255 - duty); }
  else if (dir < 0) { ledcWrite(PIN_IN1, 255 - duty); ledcWrite(PIN_IN2, 255); }
  else { ledcWrite(PIN_IN1, 255); ledcWrite(PIN_IN2, 255); }      // brake
}

float angleDeg() {
  // AS5600 analog OUT: 0..VCC over 0..360°, VCC = the EN pin (~3.3 V). Average a few reads.
  uint32_t mv = 0;
  for (int i = 0; i < 16; i++) mv += analogReadMilliVolts(PIN_ANGLE);
  return (mv / 16.0f) / 3300.0f * 360.0f;
}

void command(char c) {
  if (c == 'e') { digitalWrite(PIN_EN, HIGH); say("EN on\n"); }
  else if (c == 'x') { dir = 0; drive(); digitalWrite(PIN_EN, LOW); say("EN off\n"); }
  else if (c == 'f') { dir = 1; drive(); say("forward\n"); }
  else if (c == 'r') { dir = -1; drive(); say("reverse\n"); }
  else if (c == 's') { dir = 0; drive(); say("stop\n"); }
  else if (c == 'a') { streaming = !streaming; }
  else if (c >= '0' && c <= '9') { duty = (c - '0') * 255 / 9; drive(); say("duty %d %%\n", duty * 100 / 255); }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_EN, OUTPUT);
  digitalWrite(PIN_EN, LOW);
  ledcAttach(PIN_IN1, PWM_HZ, PWM_BITS);
  ledcAttach(PIN_IN2, PWM_HZ, PWM_BITS);
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_ANGLE, ADC_11db);
  drive();

  WiFi.mode(WIFI_STA);
  WiFi.setHostname(HOSTNAME);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(250);   // up to 10 s; keeps trying after
  MDNS.begin(HOSTNAME);
  ArduinoOTA.setHostname(HOSTNAME);
  ArduinoOTA.setPassword(OTA_PASSWORD);
  ArduinoOTA.onStart([]() { dir = 0; drive(); digitalWrite(PIN_EN, LOW); });   // motor off while updating
  ArduinoOTA.begin();
  server.begin();

  say("bench_test: e/x EN, f/r/s motor, 0-9 duty, a angle stream\n");
  if (WiFi.status() == WL_CONNECTED) say("Wi-Fi %s, telnet %s.local port 23\n", WiFi.localIP().toString().c_str(), HOSTNAME);
  else say("Wi-Fi not connected yet (check secrets.h)\n");
}

void loop() {
  ArduinoOTA.handle();
  if (server.hasClient()) {                      // one Wi-Fi client at a time; a new one replaces the old
    if (client) client.stop();
    client = server.accept();
    client.print("bench_test over Wi-Fi: e/x EN, f/r/s motor, 0-9 duty, a angle stream\n");
  }
  while (Serial.available()) command(Serial.read());
  while (client && client.connected() && client.available()) command(client.read());

  static uint32_t last = 0;
  if (streaming && millis() - last > 200) {
    last = millis();
    say("angle %.1f deg  %s\n", angleDeg(), digitalRead(PIN_EN) ? "" : "(EN off: not valid)");
  }
}
