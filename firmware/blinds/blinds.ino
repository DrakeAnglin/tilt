// Blinds controller, V1: web app for the phone (user space + developer space), three-mark calibration, schedules,
// battery plan (Wi-Fi only on input power, or in short check-ins), updates over Wi-Fi with automatic rollback.
//
//   Web app:  http://blinds-pcb.local   (or the IP it prints)
//   Update:   bin/arduino-cli compile --upload --fqbn esp32:esp32:esp32c6:CDCOnBoot=cdc -p blinds-pcb.local blinds
//   Files:    config.h pins and limits   store.h settings   power.h voltages   motion.h moves   net.h Wi-Fi + updates
//             sleep.h schedules + sleep  api.h web interface  ui.h the app (made from ui/index.html by tools/build_ui.py)
//   Wi-Fi name / password / update password: secrets.h (copy secrets.h.example; never committed).
#include "api.h"

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_VBAT, ADC_11db);
  analogSetPinAttenuation(PIN_VIN, ADC_11db);
  motionBegin();
  storeBegin();
  applyTz();
  powerSample(true);
  quickWake();                                   // on a timer wake on battery this usually goes straight back to sleep

  if (!wokeFromSleep) {
    stats.boots++;
    esp_reset_reason_t r = esp_reset_reason();
    if (r == ESP_RST_BROWNOUT) stats.brownouts++;
    else if (r == ESP_RST_PANIC) stats.crashes++;
    else if (r == ESP_RST_INT_WDT || r == ESP_RST_TASK_WDT || r == ESP_RST_WDT) stats.wdt++;
  }
  stats.wakes += rtc.wakes;
  stats.battWakes += rtc.wakes;
  rtc.wakes = 0;
  if (checkinBoot) stats.checkins++;
  statsSave();

  netBegin();
  apiBegin();
  event("start %s (%s), battery %.2f V, input %.2f V", FW_VERSION, resetReason(), vbatRest, vin);
  if (otaPending) event("new firmware on trial: it is kept once Wi-Fi works");
}

void loop() {
  static uint32_t lastP = 0;
  uint32_t now = millis();
  if (now - lastP >= 200) { lastP = now; powerSample(); }
  netTick();
  web.handleClient();
  if (!otaBusy) {
    motionTick();
    sleepTick();
  }
  if (Serial.available()) {                      // USB serial: s = stop, i = info
    char c = Serial.read();
    if (c == 's') stopAll("stopped");
    else if (c == 'i') Serial.printf("%s  %s  battery %.2f V  input %.2f V  Wi-Fi %s\n", FW_VERSION, FW_BUILD, vbatRest, vin, WiFi.localIP().toString().c_str());
  }
  delay(1);
}
