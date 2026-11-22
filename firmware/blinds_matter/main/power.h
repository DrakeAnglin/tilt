// Voltages: battery, input power (USB / solar). Battery percent and charging state.
#pragma once
#include "store.h"

float vbat = 0, vbatRest = 0, vin = 0;   // vbatRest: only updated while no motor runs (the motor pulls it down)
bool powered = false;                    // input power present
bool motorOn = false;                    // set by motion.h
uint32_t keepAwakeUntil = 0;             // developer override (millis)

float readMv(int pin) {
  uint32_t mv = 0;
  for (int i = 0; i < 16; i++) mv += analogReadMilliVolts(pin);
  return mv / 16.0f;
}

// The 3.3 V rail is not always 3.3 V (it sags when the battery is low), and the angle sensor's output is a fraction of
// its supply. So the rail is measured: push the input-sense pin high for a moment (its 100 nF capacitor charges to the
// rail), let go, and read it at once. The pin needs ~0.4 s afterwards before it shows the input voltage again.
float vdd = 3.3f;
uint32_t lastVddProbe = 0;
float probeVdd() {                              // one raw measurement, volts
  pinMode(PIN_VIN, OUTPUT);
  digitalWrite(PIN_VIN, HIGH);
  delayMicroseconds(200);
  pinMode(PIN_VIN, INPUT);
  uint32_t mv = 0;
  for (int i = 0; i < 4; i++) mv += analogReadMilliVolts(PIN_VIN);
  lastVddProbe = millis();
  if (!lastVddProbe) lastVddProbe = 1;
  return mv / 4000.0f;
}

void powerSample(bool first = false) {
  float b = readMv(PIN_VBAT) * 2.0f / 1000.0f;
  if (first) vbat = vbatRest = b;
  else { vbat += (b - vbat) * 0.3f; if (!motorOn) vbatRest += (vbat - vbatRest) * 0.1f; }
  if (first || !lastVddProbe || millis() - lastVddProbe > 400) {
    float i = readMv(PIN_VIN) * 2.0f / 1000.0f;
    if (first) vin = i; else vin += (i - vin) * 0.3f;
  }
  if (!powered && vin >= VIN_ON) powered = true;
  else if (powered && vin < VIN_OFF) powered = false;
}

void powerBegin() {                             // the dividers' ADC range, then the first readings
  analogSetPinAttenuation(PIN_VBAT, ADC_11db);
  analogSetPinAttenuation(PIN_VIN, ADC_11db);
  powerSample(true);
}

// battPercent(): logic.h
const char *chargeState() {
  if (!powered) return "battery";
  return vbatRest >= 4.12f ? "full" : "charging";
}
bool battCritical() { return battLevel(battPercent(vbatRest), powered) == BATT_CRITICAL; }   // logic.h: Schedules pause
