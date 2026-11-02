// Bench test for one tilter (docs/bench-test.md). ESP32-C6, Arduino-ESP32 core 3.x.
// Serial 115200. Commands:  e = EN on   x = EN off   f = forward   r = reverse   s = stop (brake)
//                           0..9 = duty 0..100 %     a = print angle continuously on/off
#include <Arduino.h>

const int PIN_IN1 = 19, PIN_IN2 = 20, PIN_EN = 1, PIN_ANGLE = 0;   // bench rig (fixed; see docs/bench-test.md)
const int PWM_HZ = 20000, PWM_BITS = 8;

int duty = 255;            // 0..255
int dir = 0;               // 1 forward, -1 reverse, 0 stopped
bool streaming = false;

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

void setup() {
  Serial.begin(115200);
  pinMode(PIN_EN, OUTPUT);
  digitalWrite(PIN_EN, LOW);
  ledcAttach(PIN_IN1, PWM_HZ, PWM_BITS);
  ledcAttach(PIN_IN2, PWM_HZ, PWM_BITS);
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_ANGLE, ADC_11db);
  drive();
  Serial.println("bench_test: e/x EN, f/r/s motor, 0-9 duty, a angle stream");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'e') { digitalWrite(PIN_EN, HIGH); Serial.println("EN on"); }
    else if (c == 'x') { dir = 0; drive(); digitalWrite(PIN_EN, LOW); Serial.println("EN off"); }
    else if (c == 'f') { dir = 1; drive(); Serial.println("forward"); }
    else if (c == 'r') { dir = -1; drive(); Serial.println("reverse"); }
    else if (c == 's') { dir = 0; drive(); Serial.println("stop"); }
    else if (c == 'a') { streaming = !streaming; }
    else if (c >= '0' && c <= '9') {
      duty = (c - '0') * 255 / 9; drive();
      Serial.printf("duty %d %%\n", duty * 100 / 255);
    }
  }
  static uint32_t last = 0;
  if (streaming && millis() - last > 200) {
    last = millis();
    Serial.printf("angle %.1f deg  %s\n", angleDeg(), digitalRead(PIN_EN) ? "" : "(EN off: not valid)");
  }
}
