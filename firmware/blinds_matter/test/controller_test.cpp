// Tests for the controller's own code on the host board (test/host_esp/host_board.h): main/store.h, main/power.h,
// main/lock.h, main/motion.h (with main/pwmin.h, main/request.h, main/handwatch.h and main/tilter.h), and with them
// main/ardu.h and main/config.h, run on the Mac: tools/firmware_tests.sh. The real files run unchanged; the include
// path picks the stand-in SDK headers in test/host_esp, and a stand-in tilter sits on each port behind the pins
// (test/host_esp/host_tilter.h). Built with TILT_DEVLOG, so the dev build's power log and light log are tested too.
#include "../main/store.h"
#include "../main/power.h"
#include "../main/lock.h"
#include "../main/motion.h"
#include "host_tilter.h"
#include <cstdio>
#include <cstdlib>
#include <string>

static int passed = 0, failed = 0;
#define CHECK(cond, what) do { if (cond) passed++; else { failed++; printf("FAIL line %d: %s\n", __LINE__, what); } } while (0)
static bool near(double a, double b, double tol) { return fabs(a - b) <= tol; }

// app_main.cpp's: someone has the app open. Its real body comes under test with app_main.cpp (#267).
static bool uiOn = false;
bool uiActive() { return uiOn; }

// motion.h and pwmin.h: every global back to its start value.
static void motionStartValues() {
  for (auto &b : bs) b = BlindState();
  for (auto &m : mvs) m = Move();
  cur = &mvs[0];
  for (bool &m : motOn) m = false;
  motorsHeld = false;
  for (int p = 0; p < PORTS; p++) { capLast[p] = 0; capLastMs[p] = 0; }
  pwmSaved = 0;
  hand = HandWatch();
  sensorPort = -1;
  traceN = 0;
  traceT0 = traceLast = 0;
  traceTgt = NAN;
  tracePort = -1;
  for (auto &r : ramp) r = Ramp{};
  tickTimes = TickTimes();
  capTimer = nullptr;
  capRunning = false;
  capRes = 80000000;
  capMux.held = 0;
  for (int k = 0; k < CAP_N; k++) {
    capChan[k] = nullptr;
    capRise[k] = capFall[k] = capHigh[k] = capPeriod[k] = capFrames[k] = capNom[k] = capBad[k] = 0;
    capHaveRise[k] = capHaveFall[k] = false;
    capAt[k] = 0;
  }
  uiOn = false;
}

// A restart puts every global of the firmware back to its start value, as the chip does; flash stays.
static void firmwareStartValues() {
  motionStartValues();
  memset(&cfg, 0, sizeof cfg);
  memset(&stats, 0, sizeof stats);
  memset(movesStalled, 0, sizeof movesStalled);
  tune = {TUNE_MAGIC, 8000, 2500, 10, 180};
  leadMax10 = 80;
  syncMode = 1;
  parMode = 1;
  hkSeparate = 0;
  memset(battHist, 0, sizeof battHist);
  nvs = Preferences();
  memset(plog, 0, sizeof plog);
  plogAcc = {0, 0, 0, 1, 0, 0, 0};
  memset(llog, 0, sizeof llog);
  memset(&llCur, 0, sizeof llCur);
  for (auto &l : logLines) l.clear();
  logSeq = 0;
  logMx = nullptr;
  eventHook = nullptr;
  vbat = vbatRest = vin = 0;
  powered = motorOn = false;
  keepAwakeUntil = 0;
  vdd = 3.3f;
  lastVddProbe = 0;
  mx = nullptr;
  adcUnit() = nullptr;
  adcCali() = nullptr;
  ledcCount() = 0;
  memset(ledcPins(), 0, 8 * sizeof(int));
}
// A start of the controller as app_main.cpp does it, as far as these files go.
static void start(esp_reset_reason_t why = ESP_RST_POWERON) {
  host::setResetReason(why);
  host::restart();
  logBegin();
  storeBegin();
}
static void firstStart() { host::wipeFlash(); start(); }

// ---- storage (store.h)
static void testFirstStart() {
  firstStart();
  CHECK(!strcmp(cfg.name, "Blinds") && cfg.magic == CFG_MAGIC, "first start: the controller is called Blinds");
  CHECK(!strcmp(cfg.b[0].name, "Blind 1") && !strcmp(cfg.b[1].name, "Blind 2") && !strcmp(cfg.b[2].name, "Blind 3"),
        "first start: Blind 1 to Blind 3");
  bool noMarks = true, plain = true, unused = true;
  for (int i = 0; i < PORTS; i++) {
    noMarks = noMarks && isnan(cfg.b[i].up) && isnan(cfg.b[i].open) && isnan(cfg.b[i].down);
    plain = plain && cfg.b[i].speed == 100 && cfg.b[i].fav == 50;
  }
  for (int i = 0; i < SCHEDS; i++) unused = unused && cfg.sched[i].mask == 0;
  CHECK(noMarks, "first start: no Marks");
  CHECK(plain, "first start: speed 100, favorite 50");
  CHECK(unused, "first start: eight unused Schedule slots");
  CHECK(host::flashBlob("blinds", "cfg").size() == sizeof cfg, "first start: the defaults are saved");
  CHECK(stats.boots == 1 && stats.magic == STAT_MAGIC, "first start: the start counter is at 1");
  CHECK(syncMode == 1 && parMode == 1 && hkSeparate == 0 && leadMax10 == 80,
        "first start: follow, together, one covering for all, lead limit 80");
  CHECK(tune.graceMs == 8000 && tune.stallMs == 2500 && tune.stallDeg10 == 10 && tune.moveMaxS == 180,
        "first start: the stall tune is 8000 / 2500 / 10 / 180");
}

static void testSettingsKept() {
  firstStart();
  strlcpy(cfg.name, "Den", sizeof cfg.name);
  cfg.b[1].speed = 70;
  cfgSave();
  start();
  CHECK(!strcmp(cfg.name, "Den") && cfg.b[1].speed == 70, "a saved setting is kept across a restart");
  CHECK(stats.boots == 2, "the start counter is at 2 after a restart");
}

static void testSettingsOfAnotherKind() {
  Settings other;
  cfgDefaultsOf(other);
  strlcpy(other.name, "Old", sizeof other.name);
  other.magic = CFG_MAGIC - 1;
  host::wipeFlash();
  host::putFlashBlob("blinds", "cfg", &other, sizeof other);
  start();
  CHECK(!strcmp(cfg.name, "Blinds"), "settings with another magic: the defaults");
  other.magic = CFG_MAGIC;
  host::wipeFlash();
  host::putFlashBlob("blinds", "cfg", &other, sizeof other - 4);
  start();
  CHECK(!strcmp(cfg.name, "Blinds"), "settings of a smaller size: the defaults");
  std::string bigger((const char *)&other, sizeof other);
  bigger += "more";
  host::wipeFlash();
  host::putFlashBlob("blinds", "cfg", bigger.data(), bigger.size());
  start();
  CHECK(!strcmp(cfg.name, "Blinds"), "settings of a larger size: the defaults");
  CHECK(host::flashBlob("blinds", "cfg").size() == sizeof cfg, "the defaults are saved over them");
}

static void testCountersOfAnotherKind() {
  Stats other = {};
  other.magic = STAT_MAGIC + 1;
  other.boots = 40;
  other.crashes = 3;
  other.motorMs = 99999;
  host::wipeFlash();
  host::putFlashBlob("blinds", "stat", &other, sizeof other);
  start();
  CHECK(stats.magic == STAT_MAGIC && stats.boots == 1 && stats.crashes == 0 && stats.motorMs == 0,
        "counters with another magic: all zero with the right magic (this start counted)");
}

static void testResetReasons() {
  firstStart();
  struct { esp_reset_reason_t why; const char *name; int which; } cases[] = {
      {ESP_RST_BROWNOUT, "a brownout", 0}, {ESP_RST_PANIC, "a crash", 1}, {ESP_RST_INT_WDT, "an interrupt watchdog", 2},
      {ESP_RST_TASK_WDT, "a task watchdog", 2}, {ESP_RST_WDT, "another watchdog", 2}, {ESP_RST_POWERON, "a power-on", -1}};
  for (auto &c : cases) {
    uint32_t before[3] = {stats.brownouts, stats.crashes, stats.wdt}, boots = stats.boots;
    start(c.why);
    uint32_t after[3] = {stats.brownouts, stats.crashes, stats.wdt};
    bool ok = stats.boots == boots + 1;
    for (int k = 0; k < 3; k++) ok = ok && after[k] == before[k] + (k == c.which ? 1 : 0);
    char what[80];
    snprintf(what, sizeof what, "restart after %s: only its counter goes up", c.name);
    CHECK(ok, what);
  }
}

static void testMarksRescale() {
  Settings old;
  cfgDefaultsOf(old);
  old.b[0].up = 100;
  old.b[0].open = 200;
  old.b[0].down = 350;
  old.b[2].open = 0;
  host::wipeFlash();
  host::putFlashBlob("blinds", "cfg", &old, sizeof old);   // and no "angv": Marks of the first angle scale
  start();
  CHECK(near(cfg.b[0].up, 105.7, 0.01) && near(cfg.b[0].open, 211.4, 0.01) && near(cfg.b[0].down, 9.95, 0.01),
        "Marks of the first angle scale: times 1.057, wrapped to 360");
  CHECK(isnan(cfg.b[1].up) && isnan(cfg.b[1].open) && isnan(cfg.b[1].down), "a blind with no Marks is left alone");
  CHECK(isnan(cfg.b[2].up) && cfg.b[2].open == 0, "a blind with one Mark: only that one");
  start();
  CHECK(near(cfg.b[0].up, 105.7, 0.01) && near(cfg.b[0].down, 9.95, 0.01), "no second rescale on the next start");
}

static void testTune() {
  host::wipeFlash();
  Tune t = {TUNE_MAGIC, 3000, 1500, 20, 90};
  host::putFlashBlob("blinds", "tune", &t, sizeof t);
  start();
  CHECK(tune.graceMs == 3000 && tune.stallMs == 1500 && tune.stallDeg10 == 20 && tune.moveMaxS == 90, "a saved stall tune wins");
  t.magic = TUNE_MAGIC + 1;
  host::wipeFlash();
  host::putFlashBlob("blinds", "tune", &t, sizeof t);
  start();
  CHECK(tune.graceMs == 8000 && tune.stallMs == 2500 && tune.stallDeg10 == 10 && tune.moveMaxS == 180,
        "a stall tune with the wrong magic: 8000 / 2500 / 10 / 180");
  tune.graceMs = 4000;
  tuneSave();
  start();
  CHECK(tune.graceMs == 4000, "tuneSave: the tune comes back after a restart");
}

static void testFollowModes() {
  firstStart();
  syncMode = 0;
  parMode = 0;
  syncSave();
  start();
  CHECK(syncMode == 0 && parMode == 0, "syncSave: follow and together come back after a restart");
  host::putFlashU8("blinds", "hksep", 1);
  host::putFlashU8("blinds", "lmax", 40);
  start();
  CHECK(hkSeparate == 1 && leadMax10 == 40, "separate coverings and the lead limit come from flash");
}

static void testBatteryHistory() {
  firstStart();
  bool zeros = true;
  for (int i = 0; i < BATT_HIST; i++) zeros = zeros && battHist[i] == 0;
  CHECK(zeros, "empty flash: the battery history is all zeros");
  histPush(3.70f);
  CHECK(battHist[BATT_HIST - 1] == 120, "3.70 V is stored as 120");
  histPush(2.0f);
  CHECK(battHist[BATT_HIST - 1] == 1 && battHist[BATT_HIST - 2] == 120, "2.0 V is stored as 1, the hour before moves up");
  histPush(6.0f);
  CHECK(battHist[BATT_HIST - 1] == 255, "6 V is stored as 255");
  for (int i = 0; i < BATT_HIST - 3; i++) histPush(3.0f);
  CHECK(battHist[0] == 120, "a week later the first hour is the oldest");
  histPush(3.0f);
  CHECK(battHist[0] == 1, "one more hour: the oldest drops off");
  start();
  CHECK(battHist[0] == 1 && battHist[1] == 255 && battHist[BATT_HIST - 1] == 50, "the week comes back after a restart");
}

static void testCleanText() {
  char out[40];
  cleanText(out, sizeof out, "America/New_York !@$%  ");
  CHECK(!strcmp(out, "America/New_York"), "cleanText: drops what is not allowed, trims spaces at the end");
  cleanText(out, sizeof out, "Etc/GMT+5 (a-b), c.d'e:f#g&h");
  CHECK(!strcmp(out, "Etc/GMT+5 (a-b), c.d'e:f#g&h"), "cleanText: keeps letters, digits and the allowed signs");
  char small[6];
  memset(small, 'X', sizeof small);
  cleanText(small, 5, "abcdefgh");
  CHECK(!strcmp(small, "abcd") && small[5] == 'X', "cleanText: never writes past the buffer");
  cleanText(out, sizeof out, "   ");
  CHECK(out[0] == 0, "cleanText: only spaces gives an empty text");
}

static const std::string &lastLine() { return logLines[(logSeq + LOG_N - 1) % LOG_N]; }
static int hookCalls = 0;
static std::string hookLine;
static void hook(const char *line) { hookCalls++; hookLine = line; }

static void testEventLog() {
  host::restart();
  event("before logBegin %d", 1);                    // only one task yet: no lock, no crash
  CHECK(logSeq == 1, "an event before logBegin is kept");
  firstStart();
  host::advanceMs(12500);
  event("moved %s", "Blind 1");
  CHECK(lastLine() == "+12s  moved Blind 1", "before the clock is set: seconds since the start");
  CHECK(host::lastLog() == "I blinds: +12s  moved Blind 1", "the line also goes to the chip's log");
  host::setWallClock(1800000000);                    // 2027-01-15 08:00:00 UTC: 02:00:00 in Chicago (CST)
  host::advanceMs(3000);
  event("stall");
  CHECK(lastLine() == "02:00:03  stall", "after the clock is set: the time of day in the time zone");
  event("a\"b\\c\td");
  CHECK(lastLine() == "02:00:03  a'b'c'd", "a quote, a backslash and a control character each become '");
  firstStart();
  hookCalls = 0;
  eventHook = hook;
  for (int i = 1; i <= 61; i++) event("e%d", i);
  CHECK(logSeq == 61, "61 events: logSeq is 61");
  CHECK(lastLine() == "+0s  e61" && logLines[1] == "+0s  e2", "the log holds the last 60");
  CHECK(hookCalls == 61 && hookLine == "+0s  e61", "the hook gets every line");
  CHECK(!host::held(logMx), "the log's lock is free after an event");
}

// ---- the dev build's power log and light log (TILT_DEVLOG, store.h)
static void testPowerLog() {
  firstStart();
  CHECK(plog[0].at == 0 && plog[PLOG_N - 1].at == 0, "empty flash: an empty power log");
  for (int m = 0; m < 30; m++) plogTick(4.3f, true, 60000);
  for (int m = 0; m < 30; m++) plogTick(0.5f, false, 60000);
  stats.motorMs += 12000;
  plogPush(1800003600, 3.9f, 25.4f);
  const PowerHour &h = plog[PLOG_N - 1];
  CHECK(h.at == 1800003600 && h.rest == 140, "resting volts: (3.9 - 2.5) * 100");
  CHECK(h.vinMax == 172 && h.vinAvg == 96, "highest input 4.3 V and average 2.4 V, times 40");
  CHECK(h.poweredMin == 30 && h.litMin == 30, "30 minutes on input power, 30 minutes of light");
  CHECK(h.motorS == 12 && h.tempC == 25, "motor seconds and the chip temperature");
  CHECK(h.flags == 1, "the first hour after a start is flagged");
  CHECK(host::flashBlob("blinds", "plog").size() == sizeof plog, "each hour is saved");
  plogTick(0, false, 60000);
  plogPush(1800007200, 3.9f, 25);
  CHECK(plog[PLOG_N - 1].flags == 0 && plog[PLOG_N - 2].at == 1800003600, "the next hour: no flag, the hour before moves up");
  plogPush(1800010800, 2.0f, -150);
  CHECK(plog[PLOG_N - 1].rest == 1 && plog[PLOG_N - 1].tempC == -100 && plog[PLOG_N - 1].vinAvg == 0,
        "the low ends: resting 1, -100 degrees, no ticks gives average 0");
  for (int m = 0; m < 300; m++) plogTick(10, true, 60000);
  stats.motorMs += 70000000;
  plogPush(1800014400, 6, 150);
  const PowerHour &hi = plog[PLOG_N - 1];
  CHECK(hi.rest == 255 && hi.vinMax == 255 && hi.vinAvg == 255 && hi.tempC == 100, "the high ends: 255 and 100 degrees");
  CHECK(hi.poweredMin == 255 && hi.litMin == 255 && hi.motorS == 65535, "minutes stop at 255, motor seconds at 65535");
  for (int i = 1; i <= 169; i++) plogPush(i, 3.7f, 20);
  CHECK(plog[0].at == 2 && plog[PLOG_N - 1].at == 169, "169 hours keep the newest 168");
  start();
  CHECK(plog[0].at == 2 && plog[PLOG_N - 1].at == 169 && plog[PLOG_N - 1].rest == 120, "the power log comes back after a restart");
}

static void testLightLog() {
  const uint32_t RISE = 1800000000, SET = 1800036000;
  firstStart();
  llogMinute(RISE - 7300, 2, RISE, SET);
  llogMinute(RISE, 2, 0, 0);
  CHECK(llCur.start == 0 && !host::flashHas("blinds", "llog"), "outside both windows, or no sun times: nothing stored");
  for (int k = 0; k < LLOG_MIN; k++) llogMinute(RISE - 7200 + 60 * k, k * 0.01f, RISE, SET);
  CHECK(llCur.start == RISE - 7200 && llog[LLOG_N - 1].start == 0, "inside the sunrise window: it fills, not stored yet");
  llogMinute(RISE + 7260, 3, RISE, SET);
  const LightWin &w = llog[LLOG_N - 1];
  CHECK(w.start == RISE - 7200 && w.rise == 1, "the first minute after it stores the sunrise window");
  CHECK(w.v[0] == 1 && w.v[100] == 40 && w.v[240] == 96, "the input by the minute, volts times 40; 0 V is stored as 1");
  CHECK(host::flashBlob("blinds", "llog").size() == sizeof llog && llCur.start == 0, "and saves it");
  for (int k = 0; k < LLOG_MIN; k++) llogMinute(SET - 7200 + 60 * k, 1, RISE, SET);
  llogMinute(SET + 7300, 1, RISE, SET);
  CHECK(llog[LLOG_N - 1].start == SET - 7200 && llog[LLOG_N - 1].rise == 0 && llog[LLOG_N - 2].start == RISE - 7200,
        "the same for sunset");
  for (uint32_t d = 1; d <= 6; d++) {
    uint32_t r = RISE + d * 86400;
    llogMinute(r, 1, r, 0);
    llogMinute(r + 7300, 1, r, 0);
  }
  CHECK(llog[0].start == RISE + 86400 - 7200 && llog[LLOG_N - 1].start == RISE + 6 * 86400 - 7200, "seven windows keep the newest six");
  start();
  CHECK(llog[LLOG_N - 1].start == RISE + 6 * 86400 - 7200 && llCur.start == 0, "the light log comes back after a restart");
}

// ---- power (power.h)
static void setVolts(float battery, float input) {           // at the board's pins, behind the 1 M / 1 M dividers
  host::setMilliVolts(PIN_VBAT, (int)lroundf(battery * 500));
  host::setMilliVolts(PIN_VIN, (int)lroundf(input * 500));
}
static void powerStart() {
  firstStart();
  adcBegin();
}

static void testPowerSamples() {
  powerStart();
  setVolts(3.7f, 4.3f);
  powerBegin();
  CHECK(near(vbat, 3.7, 0.001) && near(vbatRest, 3.7, 0.001) && near(vin, 4.3, 0.001), "first sample: the pin millivolts times 2");
  CHECK(powered, "4.3 V input: input power");
  setVolts(3.2f, 4.3f);
  powerSample();
  CHECK(near(vbat, 3.55, 0.001) && near(vbatRest, 3.685, 0.001), "later samples: smoothing 0.3, resting moves by 0.1");
  motorOn = true;
  powerSample();
  CHECK(near(vbat, 3.445, 0.001) && near(vbatRest, 3.685, 0.001), "while a motor runs the resting value is held");
  motorOn = false;
}

static void testInputPower() {
  powerStart();
  setVolts(3.7f, 3.79f);
  powerBegin();
  CHECK(!powered, "input at 3.79 V: no input power");
  setVolts(3.7f, 3.8f);
  powerSample(true);
  CHECK(powered, "input rising to 3.8 V: input power on");
  setVolts(3.7f, 3.5f);
  powerSample(true);
  CHECK(powered, "input at 3.5 V: stays on");
  setVolts(3.7f, 3.3f);
  powerSample(true);
  CHECK(powered, "input at 3.3 V: still on");
  setVolts(3.7f, 3.28f);
  powerSample(true);
  CHECK(!powered, "input under 3.3 V: off");
}

static void testProbeVdd() {
  powerStart();
  setVolts(3.7f, 0);
  powerBegin();
  host::clearTrace();
  host::setMilliVolts(PIN_VIN, 3100);               // the capacitor charged to the rail
  float v = probeVdd();
  CHECK(near(v, 3.1, 0.001), "probeVdd: the rail in volts");
  CHECK(host::pinTrace(PIN_VIN) == "O1I" && host::pinModeOf(PIN_VIN) == 0, "probeVdd: the input pin driven high, then let go");
  CHECK(lastVddProbe == 1, "a probe at 0 ms counts as 1 ms (0 means never)");
  host::advanceMs(1000);
  probeVdd();
  CHECK(lastVddProbe == 1000, "a probe at 1 s");
  host::setMilliVolts(PIN_VIN, 2000);               // 4 V input
  host::advanceMs(400);
  powerSample();
  CHECK(near(vin, 0, 0.001), "no input sample for 400 ms after a probe");
  host::advanceMs(1);
  powerSample();
  CHECK(near(vin, 1.2, 0.001), "after that, input samples again");
}

static void testChargeAndLimits() {
  powerStart();
  setVolts(4.2f, 0);
  powerBegin();
  CHECK(!strcmp(chargeState(), "battery"), "no input power: battery");
  setVolts(4.11f, 4.3f);
  powerSample(true);
  CHECK(!strcmp(chargeState(), "charging"), "input power, under 4.12 V resting: charging");
  setVolts(4.12f, 4.3f);
  powerSample(true);
  CHECK(!strcmp(chargeState(), "full"), "input power, at 4.12 V resting: full");
  vbatRest = 3.349f;
  powered = true;
  CHECK(!battOkToMove(), "Motor cut-off: no moves just under 3.35 V, even with input power");
  powered = false;
  CHECK(!battOkToMove(), "Motor cut-off: no moves just under 3.35 V on battery");
  vbatRest = 3.35f;
  CHECK(battOkToMove(), "at 3.35 V resting: moves");
  powered = true;
  CHECK(battOkToMove(), "at 3.35 V resting with input power: moves");
  vbatRest = 3.52f;                                  // 9% Battery level
  CHECK(battCritical(), "Critical battery under 10%");
  vbatRest = 3.53f;                                  // 10%
  CHECK(!battCritical(), "not Critical battery at 10%");
}

// ---- the board layer (ardu.h, lock.h)
static void testClock() {
  host::restart();
  CHECK(millis() == 0 && uptimeMs() == 0, "a start: the clock at 0");
  host::advanceMs(5000);
  CHECK(millis() == 5000 && uptimeMs() == 5000, "millis and uptimeMs follow the board's clock");
  delay(250);
  CHECK(millis() == 5250, "delay moves it forward");
  delay(0);
  CHECK(millis() == 5251, "delay(0) still waits one tick");
  delayMicroseconds(2000);
  CHECK(millis() == 5253, "delayMicroseconds moves it forward");
}

static void testPins() {
  host::restart();
  pinMode(P_IN1[0], OUTPUT);
  digitalWrite(P_IN1[0], HIGH);
  CHECK(host::pinModeOf(P_IN1[0]) == 1 && host::pinLevel(P_IN1[0]) == 1, "pinMode and digitalWrite reach the pin");
  digitalWrite(P_IN1[0], LOW);
  pinMode(P_IN1[0], INPUT);
  CHECK(host::pinModeOf(P_IN1[0]) == 0 && host::pinLevel(P_IN1[0]) == 0, "low, then let go");
  host::setMilliVolts(P_ANG[0], 1234);
  CHECK(analogReadMilliVolts(P_ANG[0]) == 0, "no ADC unit yet: the read gives 0");
  adcBegin();
  analogSetPinAttenuation(P_ANG[0], ADC_11db);
  analogSetPinAttenuation(P_IN1[0], ADC_11db);       // no ADC channel: nothing to set up
  CHECK(analogReadMilliVolts(P_ANG[0]) == 1234, "an ADC read in millivolts");
  host::setMilliVolts(P_IN1[0], 1000);
  CHECK(analogReadMilliVolts(P_IN1[0]) == 0, "a pin with no ADC channel reads 0");
  host::setMilliVolts(P_ANG[1], -20);
  CHECK(analogReadMilliVolts(P_ANG[1]) == 0, "a negative calibrated reading gives 0");
}

static void testPwm() {
  host::restart();
  int pins[9] = {7, 5, 1, 14, 18, 19, 20, 16, 17};
  bool ok = true;
  for (int i = 0; i < 8; i++) ok = ok && ledcAttach(pins[i], PWM_HZ, PWM_BITS);
  CHECK(ok, "eight pins: each gets its own channel");
  CHECK(!ledcAttach(pins[8], PWM_HZ, PWM_BITS), "the ninth is refused");
  CHECK(host::dutyOf(7) == 255 && host::dutyOf(17) == -1, "an attached pin starts at 255, a refused one has none");
  ledcWrite(5, 100);
  CHECK(host::dutyOf(5) == 100 && host::dutyOf(7) == 255 && host::dutyOf(1) == 255, "ledcWrite sets only that pin's duty");
  ledcWrite(17, 30);
  CHECK(host::dutyOf(17) == -1 && host::dutyOf(16) == 255, "a pin never attached is ignored");
}

static void testPreferences() {
  host::wipeFlash();
  host::restart();
  Preferences p;
  CHECK(p.begin("test", false), "Preferences open");
  CHECK(p.getUChar("x", 7) == 7, "a missing key gives the default");
  uint8_t buf[4] = {1, 2, 3, 4}, back[4] = {};
  CHECK(p.getBytes("b", back, sizeof back) == 0, "missing bytes: 0");
  CHECK(p.putBytes("b", buf, sizeof buf) == 4 && p.getBytes("b", back, sizeof back) == 4 && !memcmp(buf, back, 4),
        "bytes come back as written");
  p.putUChar("x", 9);
  CHECK(p.getUChar("x", 7) == 9, "a byte value comes back as written");
  CHECK(p.getUChar("b", 7) == 7 && p.getBytes("x", back, sizeof back) == 0, "a key of the other kind is not read");
  CHECK(!Serial, "no computer listens on Serial");
  Serial.println("x");
  Serial.print("x");
  Serial.printf("%d", 1);
  Serial.flush();
}

static void testUnlocked() {
  host::restart();
  lockBegin();
  xSemaphoreTake(mx, portMAX_DELAY);
  {
    Unlocked u;
    CHECK(!host::held(mx), "Unlocked: the controller lock is free inside the scope");
  }
  CHECK(host::held(mx), "and held again after it");
  xSemaphoreGive(mx);
  CHECK(host::takeFaults() == 0, "no fault so far");
  xSemaphoreGive(mx);
  CHECK(host::takeFaults() == 1, "the board: a give with no take is a fault");
  xSemaphoreTake(mx, portMAX_DELAY);
  xSemaphoreTake(mx, portMAX_DELAY);
  CHECK(host::takeFaults() == 1, "the board: a second take is a fault");
}

// ---- motion (motion.h, with pwmin.h, tilter.h, handwatch.h, request.h), on the stand-in tilters (host_tilter.h)
// "Blind 1" is port 0 with a tilter plugged in and Marks set: up 200, open 290, down 20 (so tilt 50 is 245 degrees).
static void lockedDo(const std::function<void()> &fn) { xSemaphoreTake(mx, portMAX_DELAY); fn(); xSemaphoreGive(mx); }
// What the motors did while the tests ran (run): per port, the first direction and duty, when the motor first ran and
// first stopped after that, the most motors on at once.
struct Seen {
  int firstDir[PORTS], firstDuty[PORTS], maxDuty[PORTS];
  uint32_t onAt[PORTS], offAt[PORTS];
  bool on[PORTS];
  int maxOn;
};
static Seen seen;
static void seenReset() {
  seen = Seen();
  for (int p = 0; p < PORTS; p++) seen.onAt[p] = seen.offAt[p] = 0;
}
static void look() {
  int n = 0;
  for (int p = 0; p < PORTS; p++) {
    int duty, d = host::motorDir(p, &duty);
    if (d && host::enHigh(p)) {
      n++;
      if (!seen.on[p]) { seen.on[p] = true; seen.firstDir[p] = d; seen.firstDuty[p] = duty; seen.onAt[p] = millis(); }
      seen.maxDuty[p] = std::max(seen.maxDuty[p], duty);
    } else if (seen.on[p] && !seen.offAt[p]) seen.offAt[p] = millis();
  }
  seen.maxOn = std::max(seen.maxOn, n);
}
// The blinds task's pass, for ms milliseconds of the board's clock: the lock held, motionTick once a millisecond, the
// clock moved 1 ms each time (and more while a pass waits: a sensor read takes tens of milliseconds).
static void run(uint32_t ms) {
  uint32_t end = millis() + ms;
  while ((int32_t)(millis() - end) < 0) { lockedDo(motionTick); look(); host::advanceMs(1); }
}
static bool runUntil(const std::function<bool()> &done, uint32_t maxMs) {
  for (uint32_t i = 0; i < maxMs; i++) { if (done()) return true; run(1); }
  return done();
}
static bool settled() { return !moving() && !bs[0].queued && !bs[1].queued && !bs[2].queued; }
static void unplugAll() { for (int p = 0; p < PORTS; p++) host::unplug(p); }
// A start of the controller with the motion code, and every port empty.
static void motionStart() {
  unplugAll();
  firstStart();
  adcBegin();
  lockBegin();
  host::setMilliVolts(PIN_VIN, 3300);            // the rail, as probeVdd measures it
  vbatRest = vbat = 3.9f;
  syncMode = 0;
  motionBegin();
}
static void setMarks(int p, float up = 200, float open = 290, float down = 20) {
  cfg.b[p].up = up; cfg.b[p].open = open; cfg.b[p].down = down;
}
// Blind p: a tilter plugged in with its rod at deg, a quick motor, Marks set, and read once.
static host::HostTilter &blind(int p, float deg, bool pwm = false) {
  host::HostTilter &t = pwm ? host::plugPwm(p, deg) : host::plugAnalog(p, deg);
  t.degPerS = 15;
  setMarks(p);
  pulseRead(p);
  return t;
}
static std::string logFrom(uint32_t seq) {          // the event log's lines since logSeq was seq
  std::string s;
  for (uint32_t i = seq; i < logSeq; i++) { s += logLines[i % LOG_N]; s += "\n"; }
  return s;
}
static bool has(const std::string &s, const char *what) { return s.find(what) != std::string::npos; }
static int count(const std::string &s, const char *what) {
  int n = 0;
  for (size_t at = s.find(what); at != std::string::npos; at = s.find(what, at + 1)) n++;
  return n;
}

// The bug: a stop in the same millisecond a move started read a sensor only just switched on, never woken.
static void testStopAtStart() {
  motionStart();
  blind(0, 260);
  float before = bs[0].tilt;
  uint32_t seq = logSeq;
  lockedDo([] { startTilt(0, 50); });
  int reads = host::tilter(0).angleReads;
  lockedDo(moveStop);
  CHECK(host::tilter(0).angleReads == reads, "a stop as the move starts: the sensor is not read");  CHECK(!has(logFrom(seq), "gave no reading"), "a stop as the move starts: no \"gave no reading\" line");
  CHECK(bs[0].tilt == before, "a stop as the move starts: the Current tilt is as before");
  CHECK(!strcmp(bs[0].last, "stopped") && !moving(), "a stop as the move starts: it ends \"stopped\"");
}

// A restart with the motion code; the tilters stay plugged in, flash stays.
static void motionRestart() {
  start();
  adcBegin();
  lockBegin();
  vbatRest = vbat = 3.9f;
  syncMode = 0;
  motionBegin();
}

// ---- start and sensors (motion.h)
static void testMotionBegin() {
  host::wipeFlash();
  host::putFlashU8("blinds", "pwm", 0x05);
  unplugAll();
  start();
  motionBegin();
  bool enLow = true, braked = true;
  for (int p = 0; p < PORTS; p++) {
    enLow = enLow && host::pinLevel(P_EN[p]) == 0 && host::pinModeOf(P_EN[p]) == 1;
    braked = braked && host::dutyOf(P_IN1[p]) == 255 && host::dutyOf(P_IN2[p]) == 255;
  }
  CHECK(enLow, "motionBegin: every EN pin an output, low (drivers and sensors asleep)");
  CHECK(braked, "motionBegin: both motor pins of every port at 255 (braked)");
  CHECK(pwmSaved == 0x05, "motionBegin: the PWM ports are read back from flash");
}

static void testEmptyPort() {
  motionStart();
  setMarks(0);
  pulseRead(0);
  CHECK(!bs[0].present && bs[0].seen && isnan(bs[0].tilt), "an empty port is read: not present, seen, tilt unknown");
  const char *e = startTilt(0, 50);
  CHECK(e && !strcmp(e, "no tilter plugged in"), "an empty port: a move to a tilt is refused, no tilter plugged in");
}

static void testAnalogRead() {
  motionStart();
  host::plugAnalog(0, 120);
  setMarks(0, 30, 120, 210);
  pulseRead(0);
  CHECK(bs[0].present && !bs[0].pwm && near(bs[0].ang, 120, 1), "an analog tilter at 120 degrees: present, Angle 120");
  CHECK(near(bs[0].tilt, tiltOfMarks(marksOf(0), 120), 1), "an analog tilter: the tilt worked out from the Marks");
  CHECK(host::pinLevel(P_EN[0]) == 0, "after a read: EN low");
}

static void testPwmRead() {
  motionStart();
  uint32_t seq = logSeq;
  blind(0, 100, true);
  CHECK(bs[0].present && bs[0].pwm && (pwmSaved & 1), "a PWM tilter: found as PWM");
  CHECK(host::flashBlob("blinds", "pwm") == std::vector<uint8_t>{1}, "a PWM tilter: the bit saved in flash");
  CHECK(count(logFrom(seq), "sensor signal is PWM") == 1, "a PWM tilter: one \"sensor signal is PWM\" line");
  CHECK(near(bs[0].ang, 100, 1), "a PWM tilter: the Angle within 1 degree");
  CHECK(!host::capTimerRunning(), "after a read: the capture timer stopped");
  motionRestart();
  pulseRead(0);
  CHECK(bs[0].pwm && near(bs[0].ang, 100, 1), "after a restart: still PWM");
  CHECK(!has(logFrom(0), "sensor signal"), "after a restart: no second line");
}

static void testPwmResting() {
  motionStart();
  blind(0, 5, true);
  cfgSave();
  host::rest(0);
  pulseRead(0);
  CHECK(bs[0].present && bs[0].pwm, "a PWM tilter resting at its zero: still PWM");
  CHECK(near(bs[0].ang, 5, 1) && bs[0].blind && !bs[0].lost, "resting at its zero: the last good Angle kept, no reading, not a dropout");
  motionRestart();
  pulseRead(0);
  CHECK(bs[0].pwm && bs[0].seen && isnan(bs[0].tilt) && isnan(bs[0].ang), "resting at its zero just after a restart: the tilt unknown, not 0 (#135)");
  host::rest(0, true);
  pulseRead(0);
  CHECK(bs[0].present && bs[0].pwm, "resting at the rail: still the PWM sensor");
}

static void testPwmBackToAnalog() {
  motionStart();
  blind(0, 100, true);
  uint32_t seq = logSeq;
  host::plugAnalog(0, 150);
  pulseRead(0);
  CHECK(!bs[0].pwm && !(pwmSaved & 1) && host::flashBlob("blinds", "pwm") == std::vector<uint8_t>{0},
        "a port that was PWM gets an analog tilter in mid-range: back to analog, saved");
  CHECK(count(logFrom(seq), "sensor signal is analog") == 1 && near(bs[0].ang, 150, 1), "one \"sensor signal is analog\" line");
}

static void testOddResults() {
  motionStart();
  blind(0, 260);
  host::unplug(0);
  pulseRead(0);
  pulseRead(0);
  CHECK(bs[0].present, "two odd plugged-in results in a row: still present");
  pulseRead(0);
  CHECK(!bs[0].present && isnan(bs[0].ang) && isnan(bs[0].judge.good), "a third: gone, its Angle unknown, its last good reading forgotten");
}

static void testAnalogDropout() {
  motionStart();
  blind(0, 260);
  uint32_t seq = logSeq;
  host::dropout(0, 1000);
  pulseRead(0);
  CHECK(bs[0].present && near(bs[0].ang, 260, 1) && bs[0].lost, "an analog dropout away from zero: the last Angle kept, lost");
  CHECK(count(logFrom(seq), "gave no reading (1 time)") == 1, "a dropout: one log line");
  host::advanceMs(1000);
  pulseRead(0);
  CHECK(!bs[0].lost, "the sensor gives readings again");
  host::dropout(0, 1000);
  pulseRead(0);
  CHECK(count(logFrom(seq), "gave no reading") == 1, "a second dropout inside 10 minutes: no line");
  host::advanceMs(601000);
  pulseRead(0);
  host::dropout(0, 1000);
  pulseRead(0);
  CHECK(count(logFrom(seq), "gave no reading (2 times)") == 1, "one after 10 minutes: logged with the count");
}

static void testPwmFramesLost() {
  motionStart();
  blind(0, 100, true);
  digitalWrite(P_EN[0], HIGH);
  delay(20);
  senseWake(0);
  CHECK(near(readAngle(0), 100, 1), "a PWM sensor that is on: read");
  host::dropout(0, 1000);
  delay(150);
  float a = readAngle(0);
  CHECK(near(a, 100, 1) && !bs[0].blind, "frames lost for under 200 ms: the last good share is used");
  delay(100);
  readAngle(0);
  CHECK(bs[0].blind && bs[0].lost, "frames lost for longer: judged as at a rail (here a dropout)");
  sensorOff(0);
}

static void testRailDips() {
  motionStart();
  blind(0, 260);
  digitalWrite(P_EN[0], HIGH);
  delay(20);
  int reads = host::tilter(0).angleReads;
  host::queueMilliVolts(PIN_VIN, {3300, 3300, 3300, 3300, 3200, 3200, 3200, 3200});
  float a = readAngle(0);
  CHECK(host::tilter(0).angleReads - reads == 16 && near(a, 260, 1), "the rail differs between the two probes: read again");
  CHECK(near(vdd, 3.3, 0.001), "the rail from the probes that agree");
  reads = host::tilter(0).angleReads;
  for (int k = 0; k < 6; k++) host::queueMilliVolts(PIN_VIN, {3300, 3300, 3300, 3300, 3200, 3200, 3200, 3200});
  readAngle(0);
  CHECK(host::tilter(0).angleReads - reads == 32, "four tries at most");
  CHECK(near(vdd, 3.25, 0.001), "both probes in range: vdd is their middle");
  host::board().mvQueue.clear();
  host::queueMilliVolts(PIN_VIN, std::vector<int>(32, 3700));
  readAngle(0);
  CHECK(near(vdd, 3.25, 0.001), "probes over 3.6 V: vdd is not changed");
  host::board().mvQueue.clear();
  host::queueMilliVolts(PIN_VIN, {3300, 3300, 3300, 3300, 2400, 2400, 2400, 2400});
  host::queueMilliVolts(PIN_VIN, std::vector<int>(24, 2400));
  readAngle(0);
  CHECK(near(vdd, 3.25, 0.001), "a probe under 2.5 V: vdd is not changed");
  host::board().mvQueue.clear();
  sensorOff(0);
}

// ---- PWM frames (pwmin.h)
static void testCaptureTimer() {
  motionStart();
  capStop(1);
  CHECK(host::capTimers() == 0, "a stop of a port never started: nothing");
  CHECK(!capStart(-1, P_ANG[0]) && !capStart(3, P_ANG[0]) && host::capTimers() == 0, "a start of port -1 or 3: false, nothing made");
  bool ok = capStart(0, P_ANG[0]) && capStart(1, P_ANG[1]) && capStart(2, P_ANG[2]);
  CHECK(ok && host::capTimers() == 1 && host::capTimerStarts() == 1, "three ports started: one timer, started once");
  CHECK(host::pinModeOf(P_ANG[1]) == 0, "a started port's pin is an input");
  capStop(-1);
  capStop(3);
  capStop(0);
  capStop(1);
  CHECK(host::capTimerStops() == 0 && host::capTimerRunning(), "stopped one by one: the timer runs while one is left");
  capStop(2);
  CHECK(host::capTimerStops() == 1 && !host::capTimerRunning(), "the last port stopped: the timer too");
  capStop(2);
  CHECK(host::capTimerStops() == 1, "a second stop: nothing");
}

static void testCaptureFails() {
  motionStart();
  host::failNext("mcpwm_new_capture_timer");
  CHECK(!capStart(0, P_ANG[0]) && !capTimer, "the timer cannot be made: capStart false");
  host::failNext("mcpwm_new_capture_channel");
  CHECK(!capStart(0, P_ANG[0]) && !capChan[0] && !host::capTimerRunning(), "a channel cannot be made: capStart false");
  CHECK(capShare(0) < 0, "after: the port reads no pulses");
}

static void edge(bool rising, uint32_t ticks) { host::capEdge(P_ANG[0], rising, ticks); }
static void frame(uint32_t at, uint32_t high) { edge(true, at); edge(false, at + high); }   // its rise and fall
static void testCaptureFrames() {
  motionStart();
  const uint32_t P = 80000000 / 115;
  host::advanceMs(1);                               // a frame's stamp of 0 means none
  capStart(0, P_ANG[0]);
  edge(false, 10);
  edge(true, 100);
  edge(true, 100 + P);
  CHECK(capFrames[0] == 0, "a falling edge before any rising edge is ignored");
  uint32_t t = 1000000;
  frame(t, P / 4); frame(t + P, P / 4); edge(true, t + 2 * P);
  CHECK(capFrames[0] == 2 && capShare(0) == as5600Share(P / 4, P), "frames at 115 Hz, a quarter high: the share of that frame");
  host::advanceMs(41);
  CHECK(capShare(0) < 0, "41 ms after the last frame: no reading");
  capStart(0, P_ANG[0]);
  CHECK(capFrames[0] == 0 && capPeriod[0] == 0 && capShare(0) < 0, "capStart on a running port: its frames cleared");
  t = 5000000;
  uint32_t L = P + P / 10;
  frame(t, P / 4); edge(true, t + L);
  CHECK(capFrames[0] == 1 && capNom[0] == L, "before a frame length is learned: a frame a tenth longer is taken");
  edge(false, t + L + P / 4); uint32_t at = t + 2 * L + L / 20; edge(true, at);
  CHECK(capFrames[0] == 1 && capBad[0] == 1, "after: a frame 5% off is dropped");
  for (int k = 0; k < 3; k++) { edge(false, at + P / 4); at += L + L / 20; edge(true, at); }
  CHECK(capNom[0] == 0 && capBad[0] == 0 && capFrames[0] == 1, "four misfits in a row: the length is learned again");
  edge(false, at + P / 4); at += P; edge(true, at);
  CHECK(capFrames[0] == 2 && capNom[0] == P, "the next frame is taken and learned");
  edge(false, at + P + 10); at += P; edge(true, at);
  CHECK(capFrames[0] == 2 && capBad[0] == 1, "a frame with its high time not under its period is dropped");
  capStop(0);
}

// ---- moves
static const char *tiltTo(int p, float t) { const char *e = nullptr; lockedDo([&] { e = startTilt(p, t); }); return e; }
static bool is(const char *a, const char *b) { return a && b && !strcmp(a, b); }
static bool braked(int p) { return host::dutyOf(P_IN1[p]) == 255 && host::dutyOf(P_IN2[p]) == 255; }
static bool endsBy(uint32_t ms) { return runUntil(settled, ms); }

static void testWholeMove() {
  motionStart();
  blind(0, 290);
  powered = false;
  uint32_t moves = stats.moves[0], seq = logSeq;
  seenReset();
  CHECK(!tiltTo(0, 50) && host::pinLevel(P_EN[0]) == 1, "a move to tilt 50: accepted, EN high");
  CHECK(blindNow(0).busy && near(bs[0].target, 50, 0.01), "while it moves: busy, the Target set");
  CHECK(endsBy(60000), "the move ends");
  CHECK(seen.firstDir[0] == -1 && seen.firstDuty[0] < 60 && seen.maxDuty[0] >= 99, "a soft start, the right way (the angle falls toward up)");
  CHECK(is(bs[0].last, "reached") && near(bs[0].tilt, 50, 5), "it ends \"reached\" within 5 of tilt 50");
  CHECK(braked(0) && host::pinLevel(P_EN[0]) == 0, "after: motor braked, EN low");
  CHECK(stats.moves[0] == moves + 1 && stats.motorMs > 0 && stats.battMotorMs == stats.motorMs, "the moves counter up one, motor time added (on battery too)");
  CHECK(isnan(bs[0].target) && !blindNow(0).busy, "the Target cleared");
  CHECK(count(logFrom(seq), "reached at tilt") == 1, "one log line with the tilt");
  powered = true;
  uint32_t batt = stats.battMotorMs, all = stats.motorMs;
  tiltTo(0, -20);
  endsBy(60000);
  CHECK(stats.motorMs > all && stats.battMotorMs == batt, "with input power: motor time added, not to the battery's");
}

static void testAlreadyThere() {
  motionStart();
  blind(0, 245);
  seenReset();
  tiltTo(0, 50);
  endsBy(5000);
  CHECK(is(bs[0].last, "already there") && !seen.on[0], "a move to where it already is: \"already there\", the motor never driven");
}

// The stall rule as the code has it today (F-5 asks for 250 ms: a product question, filed apart): no check while the
// gear play is taken up (tune.graceMs), then the rod has to move within the stall time (tune.stallMs).
static void testStall() {
  motionStart();
  blind(0, 290);
  uint32_t stalls = stats.stalls[0], seq = logSeq;
  host::hold(0);                                   // held from the start, part-way between its Marks
  seenReset();
  tiltTo(0, 50);
  endsBy(60000);
  uint32_t ranFor = seen.offAt[0] - seen.onAt[0];
  CHECK(ranFor >= tune.graceMs && ranFor < tune.graceMs + 100,
        "rod held: the motor braked as the gear play time ends (it has stood still for longer than the stall time)");
  CHECK(count(logFrom(seq), "trying the other direction") == 1, "no progress at all: one try the other way");
  CHECK(is(bs[0].last, "blocked (stalled)") && stats.stalls[0] == stalls + 1 && movesStalled[0] == 1, "it ends \"blocked (stalled)\", the stalls counters up one");
  CHECK(near(blindNow(0).tilt, 0, 2) && cfg.b[0].motSign == 1, "the Current tilt is reported, not the Target; the direction put back");
  host::letGo(0);
  motionStart();
  blind(0, 290);
  seq = logSeq;
  seenReset();
  tiltTo(0, -100);
  run(2000);
  host::hold(0);                                   // held part-way through the move
  endsBy(60000);
  ranFor = seen.offAt[0] - seen.onAt[0];
  CHECK(ranFor >= tune.graceMs + tune.stallMs && ranFor < tune.graceMs + tune.stallMs + 100,
        "rod held part-way: the motor braked once it stood still for the stall time after the gear play");
  CHECK(is(bs[0].last, "blocked (stalled)") && !has(logFrom(seq), "other direction"), "it ends \"blocked (stalled)\", no turn-round after progress");
  host::letGo(0);
}

static void testEndStop() {
  motionStart();
  host::HostTilter &t = blind(0, 230);
  t.lo = 205;
  tiltTo(0, 100);
  endsBy(60000);
  CHECK(is(bs[0].last, "reached (end stop)"), "against its end stop near the up Mark, Target 100: \"reached (end stop)\"");
}

static void testWiredRound() {
  motionStart();
  host::HostTilter &t = blind(0, 290);
  t.phys = -1;
  t.hi = 320;
  uint32_t seq = logSeq;
  tiltTo(0, 50);
  endsBy(60000);
  Settings saved;
  std::vector<uint8_t> b = host::flashBlob("blinds", "cfg");
  memcpy(&saved, b.data(), std::min(b.size(), sizeof saved));
  CHECK(count(logFrom(seq), "going the wrong way") == 1, "a motor wired the other way round: it turns round once");
  CHECK(is(bs[0].last, "reached") && cfg.b[0].motSign == -2 && saved.b[0].motSign == -2, "it reaches, the direction saved in flash as seen");
}

static void testNoReadingMidMove() {
  motionStart();
  blind(0, 290);
  tiltTo(0, -50);
  run(1500);
  host::dropout(0, 5000);
  endsBy(30000);
  CHECK(is(bs[0].last, "stopped: no reading from the sensor"), "the sensor gives nothing for over a second: it stops and says why");
}

static void testUnpluggedBeforeMove() {
  motionStart();
  blind(0, 290);
  host::unplug(0);
  pulseRead(0);
  pulseRead(0);                                  // two odd results: still present (testOddResults)
  seenReset();
  CHECK(!tiltTo(0, 50), "the move is accepted (the blind was there at its last reads)");
  endsBy(5000);
  CHECK(is(bs[0].last, "no tilter plugged in") && !seen.on[0], "unplugged before a move starts: \"no tilter plugged in\", the motor never driven");
}

static void testTimeLimit() {
  motionStart();
  host::HostTilter &t = blind(0, 290);
  t.degPerS = 2.5f;
  tune.moveMaxS = 2;
  tiltTo(0, 50);
  endsBy(30000);
  CHECK(is(bs[0].last, "stopped: time limit"), "a move past the time limit: \"stopped: time limit\"");
}

static void testOneAtATime() {
  motionStart();
  blind(0, 290);
  blind(1, 290);
  parMode = 0;
  seenReset();
  tiltTo(0, 50);
  tiltTo(1, 50);
  CHECK(bs[1].queued && blindNow(1).busy && near(bs[1].target, 50, 0.01) && !movingPort(1), "one at a time: blind 2 waits, busy, its Target set");
  endsBy(60000);
  CHECK(seen.maxOn == 1 && seen.onAt[1] > seen.offAt[0], "one at a time: only one motor on at any moment, blind 2 after blind 1");
  CHECK(is(bs[0].last, "reached") && is(bs[1].last, "reached"), "one at a time: both reach");
}

static void testTogether() {
  motionStart();
  for (int p = 0; p < PORTS; p++) blind(p, 290);
  parMode = 1;
  seenReset();
  for (int p = 0; p < PORTS; p++) tiltTo(p, 50);
  endsBy(60000);
  CHECK(seen.maxOn == 3, "together: all three motors on at the same time");
  CHECK(is(bs[0].last, "reached") && is(bs[1].last, "reached") && is(bs[2].last, "reached"), "together: all three reach (F-2)");
}

static void testWaitingUnplugged() {
  motionStart();
  blind(0, 290);
  blind(1, 290);
  parMode = 0;
  tiltTo(0, 50);
  tiltTo(1, 50);
  run(500);
  host::unplug(1);
  for (int k = 0; k < 3; k++) pulseRead(1);       // its third odd result: gone
  endsBy(60000);
  CHECK(is(bs[1].last, "no tilter plugged in") && isnan(bs[1].target) && !bs[1].queued, "a waiting blind unplugged before its turn: the reason kept, its Target cleared");
}

static int traced(char c, int pin) { std::string s = host::pinTrace(pin); return (int)std::count(s.begin(), s.end(), c); }
static void testNewTarget() {
  motionStart();
  blind(0, 290);
  tiltTo(0, 50);
  run(1500);
  int wakes = traced('O', P_ANG[0]);
  CHECK(mvs[0].st == MS_RUN && !tiltTo(0, -50), "a new Target during a move: accepted");
  endsBy(60000);
  CHECK(is(bs[0].last, "reached") && near(bs[0].tilt, -50, 5), "it carries on to the new Target");
  CHECK(traced('O', P_ANG[0]) == wakes, "with no second wake");
}

static void testStartAngle() {
  motionStart();
  host::plugAnalog(0, 290).degPerS = 15;
  pulseRead(0);
  const char *e = nullptr;
  lockedDo([&] { e = startAngle(0, 250); });
  endsBy(60000);
  CHECK(!e && near(host::tilter(0).wrapped(), 250, 2), "startAngle with no Marks: the rod within 2 degrees of the Angle asked for");
}

static void testRefusals() {
  motionStart();
  blind(0, 290);
  const char *r[6];
  lockedDo([&] {
    r[0] = startTilt(-1, 0); r[1] = startTilt(3, 0); r[2] = startAngle(-1, 0); r[3] = startAngle(3, 0);
    r[4] = jog(-1, 1, 100, 100, false); r[5] = jog(3, 1, 100, 100, false);
  });
  bool ok = true;
  for (auto *x : r) ok = ok && is(x, "no such blind");
  CHECK(ok, "port -1 and 3: \"no such blind\" (startTilt, startAngle, jog)");
  motorsHeld = true;
  lockedDo([&] { r[0] = startTilt(0, 0); r[1] = startAngle(0, 0); r[2] = jog(0, 1, 100, 100, false); });
  CHECK(is(r[0], "restarting") && is(r[1], "restarting") && is(r[2], "restarting"), "motorsHeld: \"restarting\"");
  motorsHeld = false;
  vbatRest = 3.34f;
  lockedDo([&] { r[0] = startTilt(0, 0); r[1] = startAngle(0, 0); r[2] = jog(0, 1, 100, 100, false); });
  CHECK(is(r[0], "battery too low") && is(r[1], "battery too low") && is(r[2], "battery too low"), "resting cell under 3.35 V: \"battery too low\" (Motor cut-off)");
  vbatRest = 3.9f;
  cfg.b[0].open = NAN;
  CHECK(is(tiltTo(0, 0), "not set up yet"), "no Marks: startTilt \"not set up yet\"");
  CHECK(!moving(), "nothing started");
}

static const char *jogNow(int p, int d, uint32_t ms, bool seek = false) {
  const char *e = nullptr;
  lockedDo([&] { e = jog(p, d, 100, ms, seek); });
  return e;
}
static void testJog() {
  motionStart();
  blind(0, 290);
  seenReset();
  jogNow(0, 1, 500);
  run(300);
  CHECK(host::motorRunning(0), "a jog of 500 ms: the motor on");
  jogNow(0, 1, 500);
  run(400);
  CHECK(host::motorRunning(0), "a second call the same way before the end: the end pushed out");
  run(1000);
  CHECK(!moving() && is(bs[0].last, "jog"), "then it ends \"jog\"");
  jogNow(0, 1, 500);
  run(100);
  jogNow(0, -1, 500);
  CHECK(mvs[0].kind == MV_JOG && mvs[0].jogDir == -1 && mvs[0].st == MS_WAKE, "a call the other way starts a new jog");
  endsBy(5000);
  uint32_t at = millis();
  jogNow(0, 1, 5000);
  CHECK(mvs[0].deadline - at == 2030, "5000 ms asked: cut to 2000");
  endsBy(10000);
}

static void testJogLearns() {
  motionStart();
  blind(0, 290);
  uint32_t seq = logSeq;
  jogNow(0, 1, 1500);
  endsBy(10000);
  Settings saved;
  memcpy(&saved, host::flashBlob("blinds", "cfg").data(), sizeof saved);
  CHECK(cfg.b[0].motSign == 2 && saved.b[0].motSign == 2, "a jog of more than 4 degrees, no direction known: learned and saved");
  CHECK(count(logFrom(seq), "motor direction learned (+1)") == 1, "a log line");
}

static void testSeek() {
  motionStart();
  host::HostTilter &t = blind(0, 290);
  t.lo = 250;
  uint32_t at = millis();
  jogNow(0, -1, 30000, true);
  endsBy(40000);
  CHECK(is(bs[0].last, "jog: stalled") && millis() - at < 20000 && near(t.rod, 250, 0.01), "a seek toward an end stop stops by itself there, well inside 30 s");
}

static void testStopWithWaiting() {
  motionStart();
  blind(0, 290);
  blind(1, 290);
  parMode = 0;
  tiltTo(0, 50);
  tiltTo(1, 50);
  run(1500);
  lockedDo(moveStop);
  CHECK(braked(0) && !bs[1].queued && isnan(bs[1].target) && !blindNow(1).busy, "stop with another waiting: braked, the waiting one no longer busy");
  endsBy(5000);
  CHECK(is(bs[0].last, "stopped") && !movingPort(1), "it ends \"stopped\", the waiting one never starts");
}

static void testStopEndsGentle() {
  motionStart();
  blind(0, 290);
  ramp[0] = {true, 0, 50, millis(), 60000, 0};
  lockedDo(moveStop);
  CHECK(!rampAny(), "moveStop while a gentle move is set: it is ended too");
}

static void testRecording() {
  motionStart();
  host::HostTilter &a = blind(0, 290);
  blind(1, 290);
  a.degPerS = 1;
  tiltTo(0, -100);
  run(100);
  tiltTo(1, 50);
  bool apart = true, motor = false;
  endsBy(200000);
  for (int i = 1; i < traceN; i++) apart = apart && trace[i].t - trace[i - 1].t >= 4;
  for (int i = 0; i < traceN; i++) motor = motor || (trace[i].st & 16);
  CHECK(tracePort == 0, "the move recording: the first move that started");
  CHECK(apart && motor, "points 40 ms or more apart, the motor-on bit set while it ran");
  CHECK(traceN == TRACE_N, "never more than 1500 points");
}

static void testBlindNow() {
  motionStart();
  blind(0, 290);
  blind(1, 290);
  parMode = 0;
  tiltTo(0, 50);
  tiltTo(1, -50);
  run(3000);
  BlindReport r = blindNow(0);
  CHECK(r.busy && r.movable && near(r.target, 50, 0.01) && near(r.tilt, tiltOf(0, mvs[0].live), 0.01) && r.tilt > 5,
        "blindNow during a move: the live tilt, busy, the Target, movable");
  CHECK(blindNow(1).busy, "blindNow for a waiting blind: busy");
  CHECK(firstMoving() == 0 && msign(0) == 1 && near(arcX(0, 245), 45, 0.01) && near(xOfTilt(0, -50), -45, 0.01),
        "the developer page's helpers: the first blind moving, its motor direction, degrees from open");
  endsBy(60000);
  CHECK(firstMoving() == -1, "nothing moving: -1");
}

// ---- move requests through the controller's adapter (EspMoves)
static void testRequests() {
  motionStart();
  blind(0, 290);
  vbatRest = 3.45f;                                 // Critical battery, above the Motor cut-off
  MoveResult r = moveBlinds(moveAsk(FROM_SCHEDULE, -1, 30, 0, 0x01));
  CHECK(r.started == 0 && is(r.why, "battery critical: Schedules paused") && !moving(), "a Schedule at Critical battery: nothing started");
  r = moveBlinds(moveAsk(FROM_APP, 0, 30));
  CHECK(r.started == 1 && movingPort(0), "the same from the app: it starts");
  endsBy(60000);
  vbatRest = 3.9f;
  r = moveBlinds(moveAsk(FROM_APP, 0, -40, 600000));
  CHECK(r.started == 1 && ramp[0].on && near(ramp[0].from, bs[0].tilt, 0.01) && near(ramp[0].to, -40, 0.01) && ramp[0].durMs == 600000 && !moving(),
        "a gentle request from the app: a gentle move from the Current tilt, no motor yet");
  r = moveBlinds(moveAsk(FROM_APP, 0, 10));
  CHECK(!ramp[0].on && movingPort(0), "a plain app command after it ends it");
  endsBy(60000);
}

// ---- settings changes (cfgApply)
static Settings savedCfg() {
  Settings s;
  std::vector<uint8_t> b = host::flashBlob("blinds", "cfg");
  memcpy(&s, b.data(), std::min(b.size(), sizeof s));
  return s;
}
static void apply(const Settings &n) { lockedDo([&] { cfgApply(n); }); }
static void testNewMarksWhileMoving() {
  motionStart();
  blind(0, 290);
  blind(1, 290);
  tiltTo(0, 50);
  tiltTo(1, 50);
  run(1500);
  Settings n = cfg;
  n.b[0].open = 280;
  apply(n);
  CHECK(is(bs[0].last, "stopped: settings changed") && !movingPort(0), "new Marks for a moving blind: stopped, \"settings changed\"");
  CHECK(near(bs[0].tilt, tiltOfMarks(Marks{200, 280, 20}, bs[0].ang), 0.01), "its tilt worked out from the new Marks");
  CHECK(savedCfg().b[0].open == 280, "the settings saved in flash");
  CHECK(movingPort(1), "the other blind still moving");
  endsBy(60000);
}

static void testNewMarksWaitingAndGentle() {
  motionStart();
  for (int p = 0; p < PORTS; p++) blind(p, 290);
  parMode = 0;
  tiltTo(0, 50);
  tiltTo(1, 50);
  moveBlinds(moveAsk(FROM_SCHEDULE, -1, 30, 600000, 0x04));
  CHECK(bs[1].queued && ramp[2].on, "blind 2 waits, blind 3 on a gentle move");
  Settings n = cfg;
  n.b[1].open = n.b[2].open = 280;
  apply(n);
  CHECK(!bs[1].queued && isnan(bs[1].target) && !blindNow(1).busy, "new Marks for a waiting blind: no longer busy, its Target cleared");
  CHECK(!ramp[2].on, "new Marks for a blind on a gentle move: the gentle move off");
  CHECK(movingPort(0), "the blind whose Marks stayed carries on");
  endsBy(60000);
}

static void testNameOnly() {
  motionStart();
  blind(0, 290);
  tiltTo(0, 50);
  run(1500);
  Settings n = cfg;
  strlcpy(n.b[0].name, "Den", sizeof n.b[0].name);
  apply(n);
  CHECK(movingPort(0) && !strcmp(cfg.b[0].name, "Den"), "only a name changes during a move: the move carries on");
  endsBy(60000);
  CHECK(is(bs[0].last, "reached"), "and reaches");
}

static void testDirectionChange() {
  motionStart();
  blind(0, 290);
  tiltTo(0, 50);
  run(1500);
  Settings n = cfg;
  n.b[0].motSign = -1;
  apply(n);
  CHECK(!movingPort(0) && is(bs[0].last, "stopped: settings changed") && cfg.b[0].motSign == -1, "the motor direction flipped: stopped, the asked direction kept");
  motionStart();
  blind(0, 290);
  tiltTo(0, 80);
  run(3000);
  n = cfg;                                         // asked before the move learned anything: +1
  n.b[0].open = 285;
  apply(n);
  CHECK(cfg.b[0].motSign == 2, "a change that does not touch the direction keeps what the stopped move learned");
}

static void testNewZone() {
  motionStart();
  Settings n = cfg;
  strlcpy(n.tz, "EST5EDT,M3.2.0,M11.1.0", sizeof n.tz);
  apply(n);
  CHECK(!strcmp(getenv("TZ"), "EST5EDT,M3.2.0,M11.1.0"), "a new time zone: the running zone changed at once");
  n = cfg;
  strlcpy(n.tz, "CST6CDT,M3.2.0,M11.1.0", sizeof n.tz);
  apply(n);
}

static void testMarksNeverRead() {
  motionStart();
  Settings n = cfg;
  n.b[2].up = 200; n.b[2].open = 290; n.b[2].down = 20;
  apply(n);
  CHECK(!bs[2].seen && isnan(bs[2].tilt), "new Marks for a blind never read: its tilt still unknown");
}

// ---- the watch and Follow (ADR 0004)
static int highs(int p) { return traced('1', P_EN[p]); }   // times EN went high since the last clearTrace
static void testIdleQuiet() {
  motionStart();
  for (int p = 0; p < PORTS; p++) blind(p, 290);
  host::clearTrace();
  run(10000);
  CHECK(highs(0) + highs(1) + highs(2) == 0, "idle, nobody looking, Follow off, every port seen: no sensor switched on in 10 s");
}

static void testIdleLooking() {
  motionStart();
  for (int p = 0; p < PORTS; p++) blind(p, 290);
  uiOn = true;
  run(1000);
  bool turn = true;
  for (int k = 0; k < 6; k++) {
    host::clearTrace();
    run(1000);
    int p = (int)(tickTimes.idlePort + PORTS - 1) % PORTS;   // the port read last
    turn = turn && highs(p) == 1 && highs(0) + highs(1) + highs(2) == 1;
  }
  CHECK(turn, "idle with someone looking: one port read each second, in turn");
}

static void testFollowPace() {
  motionStart();
  blind(0, 290);
  blind(1, 290);
  syncMode = 1;
  run(1000);
  host::clearTrace();
  run(3500);
  int slow = highs(0) + highs(1) + highs(2);
  uiOn = true;
  host::clearTrace();
  run(3500);
  int quick = highs(0) + highs(1) + highs(2);
  CHECK(slow == 3 || slow == 4, "Follow on, two movable blinds, nobody looking: a read each second");
  CHECK(quick == 10 || quick == 9, "someone looking: every 350 ms");
}

static void followSetUp(bool follow) {
  motionStart();
  for (int p = 0; p < PORTS; p++) blind(p, 290);
  syncMode = follow;
  uiOn = true;
  run(3500);                                       // each blind read once: where the controller left it
}
static void testFollowHand() {
  followSetUp(true);
  uint32_t seq = logSeq;
  seenReset();
  host::turnByHand(0, -27);                        // 30 tilt
  CHECK(runUntil([] { return sensorPort == 0; }, 5000), "Follow on, blind 1 turned by hand: its sensor kept on");
  host::clearTrace();
  run(1000);
  CHECK(host::pinLevel(P_EN[0]) == 1 && highs(0) == 0 && near(bs[0].tilt, 30, 2), "read every 100 ms with its sensor on");
  CHECK(runUntil([] { return movingPort(1); }, 3000), "1.5 s after it holds still: the others move");
  endsBy(60000);
  CHECK(near(bs[1].tilt, 30, 5) && near(bs[2].tilt, 30, 5) && !seen.on[0], "blinds 2 and 3 at its tilt, blind 1 not driven");
  CHECK(count(logFrom(seq), "turned by hand") == 1, "one \"turned by hand\" line");
}

static void testHandNoFollow() {
  followSetUp(false);
  seenReset();
  host::turnByHand(0, -27);
  run(8000);
  CHECK(seen.maxOn == 0, "Follow off, blind 1 turned by hand: no blind moves");
  CHECK(near(blindNow(0).tilt, 30, 2), "the app shows blind 1's new tilt at its next read (F-12)");
}

static void testAppMoveNoFollow() {
  followSetUp(true);
  seenReset();
  moveBlinds(moveAsk(FROM_APP, 0, 50));
  endsBy(60000);
  run(8000);
  CHECK(seen.on[0] && !seen.on[1] && !seen.on[2], "Follow on, blind 1 moved from the app: blinds 2 and 3 do not move");
}

static void testSetupQuiet() {
  followSetUp(true);
  seenReset();
  bool kept = true;
  for (int k = 0; k < 3; k++) {
    hand.setupOpen(1, millis());                   // the app asks every second
    run(1000);
    kept = kept && sensorPort == 1 && host::pinLevel(P_EN[1]) == 1;
  }
  host::turnByHand(0, -27);
  run(8000);
  CHECK(kept, "Setup open for blind 2: its sensor kept on");
  CHECK(seen.maxOn == 0, "blind 1 turned by hand within 15 s: nothing followed");
}

static void testWatchMoves() {
  motionStart();
  blind(0, 290);
  blind(1, 290);
  watchSync(0);
  CHECK(sensorPort == 0 && host::pinLevel(P_EN[0]) == 1, "the watch on blind 1: its sensor on");
  watchSync(1);
  CHECK(sensorPort == 1 && host::pinLevel(P_EN[0]) == 0 && host::pinLevel(P_EN[1]) == 1, "the watch moves to blind 2: the first sensor off");
  tiltTo(0, 50);
  CHECK(sensorPort == -1 && host::pinLevel(P_EN[1]) == 0, "a move that starts ends the watch");
  watchSync(1);
  watchSync(0);
  CHECK(sensorPort == 0 && host::pinLevel(P_EN[0]) == 1, "the watch leaves a blind that is moving: its sensor stays on");
  endsBy(60000);
}

// ---- Setup (the Marks)
static const char *mark(int p, const char *w) { const char *e = nullptr; lockedDo([&] { e = setMark(p, w); }); return e; }
static void testWholeSetup() {
  motionStart();
  host::HostTilter &t = host::plugAnalog(0, 250);
  t.degPerS = 15;
  t.lo = 195;
  t.hi = 385;
  pulseRead(0);
  uint32_t seq = logSeq;
  jogNow(0, -1, 30000, true);
  endsBy(30000);
  const char *up = mark(0, "up");
  while (t.wrapped() < 284 && t.wrapped() > 100) { jogNow(0, 1, 500); run(200); }
  endsBy(5000);
  const char *open = mark(0, "open");
  jogNow(0, 1, 30000, true);
  endsBy(30000);
  const char *down = mark(0, "down");
  CHECK(!up && !open && !down, "a whole Setup: each mark taken");
  Settings s = savedCfg();
  CHECK(near(s.b[0].up, 195, 2) && near(s.b[0].open, 290, 5) && near(s.b[0].down, 25, 2), "the three Marks saved in flash");
  CHECK(count(logFrom(seq), ": marked ") == 3, "a \"marked\" line each");
  CHECK(near(tiltOf(0, s.b[0].up), 100, 0.01) && near(tiltOf(0, s.b[0].open), 0, 0.01) && near(bs[0].tilt, -100, 1),
        "tilt 100, 0 and -100 at the three places");
  tiltTo(0, 50);
  endsBy(60000);
  CHECK(is(bs[0].last, "reached"), "then a move to tilt 50 ends \"reached\"");
}

static void testMarkUpResetsDirection() {
  motionStart();
  blind(0, 290);
  cfg.b[0].motSign = -2;
  CHECK(!mark(0, "up") && cfg.b[0].motSign == -1, "mark up on a blind whose direction was seen: back to assumed, same way");
}

static void testMarksClear() {
  motionStart();
  blind(0, 290);
  uint32_t seq = logSeq;
  CHECK(!mark(0, "clear"), "clear: accepted");
  Settings s = savedCfg();
  CHECK(isnan(cfg.b[0].up) && isnan(cfg.b[0].open) && isnan(cfg.b[0].down) && isnan(s.b[0].open), "the three Marks gone, saved");
  CHECK(isnan(bs[0].tilt) && count(logFrom(seq), "marks cleared") == 1, "the tilt unknown, a \"marks cleared\" line");
}

static void testMarkRefusals() {
  motionStart();
  blind(0, 290);
  CHECK(is(mark(3, "up"), "no such blind") && is(mark(-1, "up"), "no such blind"), "port 3: \"no such blind\"");
  tiltTo(0, 50);
  CHECK(is(mark(0, "up"), "wait until it stops"), "during a move: \"wait until it stops\"");
  endsBy(60000);
  CHECK(is(mark(1, "up"), "no tilter plugged in"), "an empty port: \"no tilter plugged in\"");
  Marks before = marksOf(0);
  CHECK(is(mark(0, "sideways"), "unknown mark"), "a word that is not a mark: \"unknown mark\"");
  Marks after = marksOf(0);
  CHECK(after.up == before.up && after.open == before.open && after.down == before.down, "the Marks unchanged");
}

static void testMarkUnsteady() {
  motionStart();
  blind(0, 290);
  host::turnByHand(0, -20, 3000);
  CHECK(is(mark(0, "up"), "the slats are still moving: let them settle, then tap again"), "turned by hand during the steady reading");
  run(3000);
  host::dropout(0, 3000);
  CHECK(is(mark(0, "up"), "the sensor gave no reading: check the tilter's cable, then tap again"), "the sensor gives nothing during it");
}

// fn runs in the first wait of the steady reading (the lock let go), as another task would.
static void inFirstWait(std::function<void()> fn) {
  host::duringDelay([fn] {
    if (host::held(mx)) { inFirstWait(fn); return; }
    lockedDo(fn);
  });
}
static void testMarkInterrupted() {
  motionStart();
  blind(0, 290);
  blind(1, 290);
  inFirstWait([] { startTilt(1, 50); });
  CHECK(is(mark(0, "up"), "wait until it stops"), "a move starts during a wait: \"wait until it stops\"");
  endsBy(60000);
  inFirstWait([] { watchSync(1); });
  CHECK(is(mark(0, "up"), "interrupted: tap again"), "the watch goes to another blind during a wait: \"interrupted: tap again\"");
  host::board().delayHook = nullptr;
}

static int freeWaits = 0;
static void countWaits() {
  host::duringDelay([] { if (!host::held(mx)) freeWaits++; countWaits(); });
}
static void testMarkLock() {
  motionStart();
  blind(0, 290);
  freeWaits = 0;
  bool heldAfter = false;
  countWaits();
  lockedDo([&] { setMark(0, "up"); heldAfter = host::held(mx); });
  host::board().delayHook = nullptr;
  CHECK(freeWaits == 12, "the steady reading: the lock free inside each 50 ms wait");
  CHECK(heldAfter && host::takeFaults() == 0, "and held when setMark returns, with no board fault");
}

int main() {
  host::onRestart(firmwareStartValues);
  setenv("TZ", "CST6CDT,M3.2.0,M11.1.0", 1);
  tzset();
  testFirstStart();
  testSettingsKept();
  testSettingsOfAnotherKind();
  testCountersOfAnotherKind();
  testResetReasons();
  testMarksRescale();
  testTune();
  testFollowModes();
  testBatteryHistory();
  testCleanText();
  testEventLog();
  testPowerLog();
  testLightLog();
  testPowerSamples();
  testInputPower();
  testProbeVdd();
  testChargeAndLimits();
  testClock();
  testPins();
  testPwm();
  testPreferences();
  testUnlocked();
  testStopAtStart();
  testMotionBegin();
  testEmptyPort();
  testAnalogRead();
  testPwmRead();
  testPwmResting();
  testPwmBackToAnalog();
  testOddResults();
  testAnalogDropout();
  testPwmFramesLost();
  testRailDips();
  testCaptureTimer();
  testCaptureFails();
  testCaptureFrames();
  testWholeMove();
  testAlreadyThere();
  testStall();
  testEndStop();
  testWiredRound();
  testNoReadingMidMove();
  testUnpluggedBeforeMove();
  testTimeLimit();
  testOneAtATime();
  testTogether();
  testWaitingUnplugged();
  testNewTarget();
  testStartAngle();
  testRefusals();
  testJog();
  testJogLearns();
  testSeek();
  testStopWithWaiting();
  testStopEndsGentle();
  testRecording();
  testBlindNow();
  testRequests();
  testNewMarksWhileMoving();
  testNewMarksWaitingAndGentle();
  testNameOnly();
  testDirectionChange();
  testNewZone();
  testMarksNeverRead();
  testIdleQuiet();
  testIdleLooking();
  testFollowPace();
  testFollowHand();
  testHandNoFollow();
  testAppMoveNoFollow();
  testSetupQuiet();
  testWatchMoves();
  testWholeSetup();
  testMarkUpResetsDirection();
  testMarksClear();
  testMarkRefusals();
  testMarkUnsteady();
  testMarkInterrupted();
  testMarkLock();
  failed += host::takeFaults();
  printf("%d passed, %d failed\n", passed, failed);
  return failed ? 1 : 0;
}
