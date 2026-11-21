// Bench tool: switch an AS5600 angle sensor from analog output to PWM output, and make that permanent.
// Runs on a spare ESP32-C6 board, talked to over USB serial (115200). Datasheet: ams AS5600, v1-06.
//
// Wiring (sensor board -> ESP board):   VCC -> 3V3    GND -> GND    SDA -> GPIO6    SCL -> GPIO7    OUT -> GPIO5
// A magnet must sit over the chip (use a tilter with its magnet gear in, or hold the 4 x 2 mm magnet over it).
//
// Keys:  i = show the sensor's state        t = try PWM (not permanent: lost when power is removed)
//        a = back to analog (not permanent) w = watch the angle, both ways of reading it, until a key is pressed
//        B = burn: make the present output setting permanent. Can be done ONCE per sensor. Asks you to type YES.
//
// What the burn needs (datasheet): supply 3.3 V or more at the sensor, a 10 uF capacitor from the sensor's VCC to GND
// during the burn, and a stiff supply (short wires). Check the 3V3 pin with a meter first: 3.30 V or a little more.
#include <Arduino.h>
#include <Wire.h>

const int PIN_SDA = 6, PIN_SCL = 7, PIN_OUT = 5;
const uint8_t ADDR = 0x36;                       // the AS5600's I2C address
const uint8_t R_ZMCO = 0x00, R_MANG = 0x05, R_CONF = 0x07, R_STATUS = 0x0B, R_RAW = 0x0C, R_AGC = 0x1A, R_BURN = 0xFF;
const uint16_t OUTS_MASK = 0x0030, OUTS_PWM = 0x0020, PWMF_MASK = 0x00C0;   // CONF bits 5:4 output stage, 7:6 PWM frequency
// PWMF = 00: 115 Hz, the slowest. Its shortest pulse (0.26 ms) is the easiest one for a filtered input to see.

bool rd1(uint8_t reg, uint8_t *buf, int n, bool rep) {
  Wire.beginTransmission(ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(!rep) != 0) return false;
  if (Wire.requestFrom((int)ADDR, n) != n) return false;
  for (int i = 0; i < n; i++) buf[i] = Wire.read();
  return true;
}
bool rd(uint8_t reg, uint8_t *buf, int n) {       // a few tries, and a fresh start of the bus in between
  for (int k = 0; k < 4; k++) {
    if (rd1(reg, buf, n, k % 2 == 0)) return true;
    Wire.end(); delay(5); Wire.begin(PIN_SDA, PIN_SCL, 50000); delay(5);
  }
  return false;
}
bool wr(uint8_t reg, const uint8_t *buf, int n) {
  Wire.beginTransmission(ADDR);
  Wire.write(reg);
  for (int i = 0; i < n; i++) Wire.write(buf[i]);
  return Wire.endTransmission() == 0;
}
bool rd16(uint8_t reg, uint16_t &v) { uint8_t b[2]; if (!rd(reg, b, 2)) return false; v = (b[0] << 8) | b[1]; return true; }
bool wr16(uint8_t reg, uint16_t v) { uint8_t b[2] = {(uint8_t)(v >> 8), (uint8_t)v}; return wr(reg, b, 2); }

// ---- PWM reading: time every edge on the OUT pin
volatile uint32_t tRise = 0, hiUs = 0, perUs = 0, frames = 0;
void IRAM_ATTR onEdge() {
  uint32_t now = micros();
  if (digitalRead(PIN_OUT)) { if (tRise) perUs = now - tRise; tRise = now; frames++; }
  else if (tRise) hiUs = now - tRise;
}
// One frame = 4351 clock periods: 128 high, 4095 for the angle, 128 low. Angle = (high share x 4351 - 128) / 4095.
float pwmAngle() {
  noInterrupts();
  uint32_t h = hiUs, p = perUs;
  interrupts();
  if (!p || h >= p) return NAN;
  return constrain(((float)h / p * 4351.0f - 128.0f) / 4095.0f, 0.0f, 1.0f) * 360.0f;
}

void info() {
  uint8_t zmco, st, agc;
  uint16_t conf, mang, raw;
  if (!rd(R_ZMCO, &zmco, 1) || !rd16(R_CONF, conf) || !rd16(R_MANG, mang) || !rd(R_STATUS, &st, 1) || !rd16(R_RAW, raw) || !rd(R_AGC, &agc, 1)) {
    Serial.println("No answer from the sensor. Check the four wires (VCC, GND, SDA, SCL).");
    return;
  }
  int outs = (conf >> 4) & 3;
  Serial.printf("Output: %s   (CONF = 0x%04X)\n", outs == 2 ? "PWM" : outs == 1 ? "analog, 10-90 %" : "analog", conf & 0x3FFF);
  Serial.printf("Magnet: %s%s%s   strength setting (AGC) %d\n", (st & 0x20) ? "found" : "NOT found", (st & 0x08) ? ", too strong" : "", (st & 0x10) ? ", too weak" : "", agc);
  Serial.printf("Angle (read over I2C): %.1f deg\n", (raw & 0x0FFF) * 360.0f / 4096.0f);
  Serial.printf("Zero position burned %d time(s). Range setting (MANG) %d.\n", zmco & 3, mang & 0x0FFF);
}
bool setOut(bool pwm) {
  uint16_t conf;
  if (!rd16(R_CONF, conf)) return false;
  conf = (conf & ~(OUTS_MASK | PWMF_MASK)) | (pwm ? OUTS_PWM : 0);
  return wr16(R_CONF, conf);
}
void watch() {
  Serial.println("Turn the magnet. Any key stops.");
  while (Serial.available()) Serial.read();
  while (!Serial.available()) {
    uint16_t raw = 0;
    uint8_t st = 0;
    bool okI2c = rd16(R_RAW, raw) && rd(R_STATUS, &st, 1);
    uint32_t f0 = frames;
    delay(250);
    if (!okI2c) { Serial.printf("I2C: NO ANSWER (loose wire?)   OUT wire reads %d mV\n", (int)analogReadMilliVolts(PIN_OUT)); continue; }
    if (!(st & 0x20)) Serial.print("(no magnet) ");
    float pa = pwmAngle();
    uint16_t conf = 0;
    rd16(R_CONF, conf);
    float deg = (raw & 0x0FFF) * 360.0f / 4096.0f;
    if (((conf >> 4) & 3) == 2) {                 // PWM mode: count pulses. (Reading the pin as a voltage would switch its pulse input off.)
      if (frames - f0 >= 5) Serial.printf("I2C %6.1f deg   PWM %6.1f deg   (%lu pulses a second)\n", deg, pa, (unsigned long)(frames - f0) * 4);
      else Serial.printf("I2C %6.1f deg   NO pulses on the OUT wire (pin is %s)\n", deg, digitalRead(PIN_OUT) ? "high" : "low");
    } else {                                      // analog mode: the voltage should be angle / 360 of the supply
      int mv = analogReadMilliVolts(PIN_OUT);
      Serial.printf("I2C %6.1f deg   OUT %4d mV (expect about %d mV)\n", deg, mv, (int)(deg / 360.0f * 3280));
      pinMode(PIN_OUT, INPUT);                    // back to a digital input for the pulse counter
      attachInterrupt(digitalPinToInterrupt(PIN_OUT), onEdge, CHANGE);
    }
  }
  while (Serial.available()) Serial.read();
}
String line() {
  String s;
  for (;;) {
    while (!Serial.available()) delay(5);
    char c = Serial.read();
    if (c == '\n' || c == '\r') { if (s.length()) return s; } else s += c;
  }
}
void burn() {
  uint16_t conf, mang;
  if (!rd16(R_CONF, conf) || !rd16(R_MANG, mang)) { Serial.println("No answer from the sensor."); return; }
  if (((conf >> 4) & 3) != 2) { Serial.println("The output is not set to PWM. Press t first, check it with w, then burn."); return; }
  Serial.println("This makes PWM output PERMANENT on this sensor. It can be done once and cannot be undone.");
  Serial.println("Needed now: 3.30 V or more on the sensor's VCC, and a 10 uF capacitor from its VCC to GND.");
  Serial.println("Type YES and press Enter to burn. Anything else cancels.");
  while (Serial.available()) Serial.read();
  if (line() != "YES") { Serial.println("Cancelled. Nothing was burned."); return; }
  uint8_t cmd = 0x40;                              // Burn_Setting: writes MANG and CONF for good
  if (!wr(R_BURN, &cmd, 1)) { Serial.println("The burn command was not accepted (no answer)."); return; }
  delay(10);
  const uint8_t reload[3] = {0x01, 0x11, 0x10};    // load what is really in the permanent memory back into the registers
  for (int i = 0; i < 3; i++) { wr(R_BURN, &reload[i], 1); delay(2); }
  uint16_t c2 = 0, m2 = 0;
  if (rd16(R_CONF, c2) && rd16(R_MANG, m2) && ((c2 >> 4) & 3) == 2 && (c2 & 0x3FFF) == (conf & 0x3FFF) && m2 == mang)
    Serial.println("Burned and checked: PWM is now this sensor's output for good. Unplug it, plug it in again and press i to see.");
  else
    Serial.printf("NOT confirmed. Permanent memory reads CONF 0x%04X (wanted 0x%04X). Supply too low or no capacitor? Unplug, replug, press i.\n", c2 & 0x3FFF, conf & 0x3FFF);
}

// Which ESP pin is the sensor's OUT really on? Pull each free pin up, then down, and see what it does.
// A pin nothing is connected to follows the pull. A pin the sensor drives does not.
void scan() {
  const int pins[] = {0, 1, 2, 3, 4, 5, 8, 9, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23};
  detachInterrupt(digitalPinToInterrupt(PIN_OUT));
  for (int p : pins) {
    pinMode(p, INPUT_PULLUP); delay(5); int up = digitalRead(p);
    pinMode(p, INPUT_PULLDOWN); delay(5); int dn = digitalRead(p);
    pinMode(p, INPUT);
    Serial.printf("pin %2d: %s\n", p, up && !dn ? "nothing connected" : up && dn ? "held HIGH by something" : !up && !dn ? "held LOW by something" : "odd");
  }
  attachInterrupt(digitalPinToInterrupt(PIN_OUT), onEdge, CHANGE);
}

// Is the sensor board there at all? Its own pull-up resistors hold SDA and SCL high when it has power and the two
// wires are in. Then every I2C address is tried.
void diag() {
  Wire.end();
  const int pp[2] = {PIN_SDA, PIN_SCL};
  for (int k = 0; k < 2; k++) {
    pinMode(pp[k], INPUT_PULLDOWN); delay(5);
    Serial.printf("%s (pin %d): %s\n", k ? "SCL" : "SDA", pp[k], digitalRead(pp[k]) ? "held high by the sensor board (good)" : "NOT held high: wire out, or the sensor board has no power");
    pinMode(pp[k], INPUT);
  }
  Wire.begin(PIN_SDA, PIN_SCL, 100000);
  int found = 0;
  for (int a = 1; a < 127; a++) { Wire.beginTransmission(a); if (Wire.endTransmission() == 0) { Serial.printf("a device answers at address 0x%02X\n", a); found++; } }
  if (!found) Serial.println("no device answers at any address");
}

void setup() {
  Serial.begin(115200);
  Wire.begin(PIN_SDA, PIN_SCL, 100000);
  pinMode(PIN_OUT, INPUT);
  attachInterrupt(digitalPinToInterrupt(PIN_OUT), onEdge, CHANGE);
  delay(1500);
  Serial.println("\nAS5600 setup tool.  i = state   t = try PWM   a = analog again   w = watch   B = burn (permanent)");
  info();
}
void loop() {
  if (!Serial.available()) { delay(10); return; }
  char c = Serial.read();
  if (c == 'i') info();
  else if (c == 't') { Serial.println(setOut(true) ? "Output set to PWM, 115 Hz (until power is removed). Press w to check it." : "No answer from the sensor."); }
  else if (c == 'a') { Serial.println(setOut(false) ? "Output set to analog (until power is removed)." : "No answer from the sensor."); }
  else if (c == 'w') watch();
  else if (c == 'B') burn();
  else if (c == 's') scan();
  else if (c == 'd') diag();
  else if (c == 'x') {                             // raw I2C trial, with the error numbers
    for (int reg : {0x00, 0x07, 0x08, 0x0B, 0x0C, 0x0E, 0x1A}) {
      Wire.beginTransmission(ADDR); Wire.write((uint8_t)reg);
      int e = Wire.endTransmission(true);
      int n = Wire.requestFrom((int)ADDR, 1);
      int v = n ? Wire.read() : -1;
      Serial.printf("reg 0x%02X: write result %d, bytes back %d, value 0x%02X\n", reg, e, n, v & 0xFF);
      delay(5);
    }
  }
}
