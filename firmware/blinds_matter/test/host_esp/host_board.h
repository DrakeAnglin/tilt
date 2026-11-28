// The host board: a stand-in for the ESP32-C6 the controller runs on, behind the stand-in SDK headers in this folder
// (freertos/, driver/, esp_adc/, nvs.h, esp_timer.h, ...), the way test/host_mbedtls stands in for mbedtls. The real
// files in main/ include those headers by their SDK names and run unchanged; the include path picks these instead.
// Tests only, and one test program per board: it defines functions (time, settimeofday) and keeps its state here.
//
// What a test can do (namespace host):
//   the clock      advanceMs / advanceUs move it; vTaskDelay and esp_rom_delay_us move it too. onClock(hook): a hook
//                  that runs whenever it moves (what is plugged into the board moves with it: host_tilter.h); the
//                  hook gets the time it moves to and may stop at times on the way (setUs), never back
//   another task   duringDelay(fn): fn runs inside the next vTaskDelay (what another task does while the code waits)
//   the wall clock setWallClock(epoch) or settimeofday(); 0 = not set (the Mac's clock is never read or set)
//   flash          kept in memory by namespace and key; survives restart(), wipeFlash() clears it
//                  (putFlashStr / flashStr: a string as nvs_set_str keeps it)
//   pins           the mode and level last written (pinTrace: the history; onLevel(hook): a hook that runs at each
//                  level written), the millivolts on an ADC pin, LEDC duty.
//                  An ADC read asks the pin's source first (adcSource: what is plugged into it), then the readings
//                  queued on the pin (queueMilliVolts, one per read), then the millivolts set (setMilliVolts)
//   reset reason   setResetReason: what esp_reset_reason() says after the next start
//   mutexes        know if they are held; a give with no take or a second take is a fault
//   restart()      clears the board (clock to 0, pins, LEDC, mutexes, wall clock), keeps flash, and runs every
//                  onRestart hook: the test program's, which put the firmware's globals back to their start values
//   faults         takeFaults(): how many faults since the last call (the test program counts them as failures)
#pragma once
#include <sys/time.h>
#include <time.h>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <deque>
#include <functional>
#include <map>
#include <string>
#include <vector>

namespace host {

struct Mutex { bool held = false; };
struct Entry { bool blob = false; std::vector<uint8_t> bytes; };    // an NVS value: a blob, or one byte (u8)

struct Board {
  int64_t us = 0;                                      // esp_timer: microseconds since this start
  time_t wallAt = 0;                                   // the wall clock when it was set (0: not set) ...
  int64_t wallSetUs = 0;                               // ... and the board clock then
  std::map<std::string, std::map<std::string, Entry>> flash;   // namespace -> key -> value
  std::map<std::string, std::map<std::string, char>> kind;    // a value that is not a blob: 's' a string, 'u' a u32 (none: a u8)
  std::vector<std::string> handles;                    // nvs_handle_t n is the namespace handles[n - 1]
  std::map<int, int> mode, level, mv;                  // per pin: GPIO mode (0 off, 1 out), level, millivolts on it
  std::map<int, std::deque<int>> mvQueue;              // per pin: readings for the next ADC reads, one each
  std::function<bool(int pin, int *mv)> adcSource;     // asked first on every ADC read: true = it answered
  std::function<void(int64_t toUs)> clockHook;         // runs when the clock moves (onClock)
  std::function<void(int pin)> levelHook;              // runs when a pin's level is written (onLevel)
  bool inClock = false;
  std::function<void()> delayHook;                     // runs inside the next vTaskDelay (duringDelay)
  std::map<int, std::string> trace;                    // per pin: "O" made an output, "I" let go, "1"/"0" a level
  std::map<int, int> chanPin, duty, pendingDuty;       // LEDC: channel -> pin, channel -> duty (applied, set)
  bool ledcTimer = false;
  int resetReason = 1;                                 // ESP_RST_POWERON
  std::deque<Mutex> mutexes;
  std::vector<void (*)()> hooks;
  std::string lastLog;                                 // the last ESP_LOG line: "I blinds: text"
  int faults = 0;
};
inline Board &board() { static Board b; return b; }

inline void fault(const char *fmt, ...) {
  char buf[200];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(buf, sizeof buf, fmt, ap);
  va_end(ap);
  printf("BOARD FAULT: %s\n", buf);
  board().faults++;
}
inline int takeFaults() { int n = board().faults; board().faults = 0; return n; }

// ---- clock
inline int64_t nowUs() { return board().us; }
inline void clockTo(int64_t to) {
  Board &b = board();
  if (b.clockHook && !b.inClock) { b.inClock = true; b.clockHook(to); b.inClock = false; }
  if (b.us < to) b.us = to;
}
inline void advanceUs(int64_t us) { clockTo(board().us + us); }
inline void advanceMs(int64_t ms) { clockTo(board().us + ms * 1000); }
inline void setUs(int64_t us) { if (us > board().us) board().us = us; }   // for a clock hook: a stop on the way
inline void onClock(std::function<void(int64_t)> hook) { board().clockHook = hook; }
inline void onLevel(std::function<void(int)> hook) { board().levelHook = hook; }
inline void duringDelay(std::function<void()> fn) { board().delayHook = fn; }
inline void setWallClock(time_t t) { board().wallAt = t; board().wallSetUs = board().us; }
inline time_t wallClock() { Board &b = board(); return b.wallAt ? b.wallAt + (time_t)((b.us - b.wallSetUs) / 1000000) : 0; }

// ---- flash
inline void wipeFlash() { board().flash.clear(); }
inline bool flashHas(const char *ns, const char *key) {
  auto n = board().flash.find(ns);
  return n != board().flash.end() && n->second.count(key);
}
inline std::vector<uint8_t> flashBlob(const char *ns, const char *key) {
  return flashHas(ns, key) ? board().flash[ns][key].bytes : std::vector<uint8_t>();
}
inline void putFlashBlob(const char *ns, const char *key, const void *p, size_t n) {
  Entry &e = board().flash[ns][key];
  e.blob = true;
  e.bytes.assign((const uint8_t *)p, (const uint8_t *)p + n);
}
inline void putFlashU8(const char *ns, const char *key, uint8_t v) {
  Entry &e = board().flash[ns][key];
  e.blob = false;
  e.bytes.assign(1, v);
}
inline void putFlashStr(const char *ns, const char *key, const std::string &v) {   // as nvs_set_str keeps it
  Entry &e = board().flash[ns][key];
  e.blob = false;
  e.bytes.assign(v.c_str(), v.c_str() + v.size() + 1);
  board().kind[ns][key] = 's';
}
inline std::string flashStr(const char *ns, const char *key) {   // "" when there is no string under the key
  if (!flashHas(ns, key) || board().flash[ns][key].blob || board().kind[ns][key] != 's') return "";
  return (const char *)board().flash[ns][key].bytes.data();
}

// ---- pins
inline void setMilliVolts(int pin, int mv) { board().mv[pin] = mv; }
inline void queueMilliVolts(int pin, std::vector<int> mvs) { for (int v : mvs) board().mvQueue[pin].push_back(v); }
inline void adcSource(std::function<bool(int, int *)> src) { board().adcSource = src; }
inline int adcRead(int pin) {                          // what an ADC read of the pin gives, in millivolts
  Board &b = board();
  int v = 0;
  if (b.adcSource && b.adcSource(pin, &v)) return v;
  auto q = b.mvQueue.find(pin);
  if (q != b.mvQueue.end() && !q->second.empty()) { v = q->second.front(); q->second.pop_front(); return v; }
  return b.mv.count(pin) ? b.mv[pin] : 0;
}
inline int pinModeOf(int pin) { return board().mode.count(pin) ? board().mode[pin] : -1; }   // -1: never set
inline int pinLevel(int pin) { return board().level.count(pin) ? board().level[pin] : -1; }
inline std::string pinTrace(int pin) { return board().trace[pin]; }
inline void clearTrace() { board().trace.clear(); }
inline int dutyOf(int pin) {                           // the LEDC duty on a pin, -1 if no channel drives it
  for (auto &c : board().chanPin)
    if (c.second == pin) return board().duty.count(c.first) ? board().duty[c.first] : -1;
  return -1;
}

// ---- reset reason, restart
inline void setResetReason(int r) { board().resetReason = r; }
inline void onRestart(void (*hook)()) { board().hooks.push_back(hook); }
inline void restart() {
  Board &b = board();
  b.us = 0;
  b.wallAt = 0;
  b.wallSetUs = 0;
  b.handles.clear();
  b.mode.clear();
  b.level.clear();
  b.trace.clear();
  b.mvQueue.clear();
  b.delayHook = nullptr;
  b.chanPin.clear();
  b.duty.clear();
  b.pendingDuty.clear();
  b.ledcTimer = false;
  b.mutexes.clear();
  b.lastLog.clear();
  for (auto h : b.hooks) h();
}

// ---- mutexes
inline bool held(void *m) { return m && ((Mutex *)m)->held; }

inline const std::string &lastLog() { return board().lastLog; }
inline void espLog(char level, const char *tag, const char *fmt, ...) {
  char buf[256];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(buf, sizeof buf, fmt, ap);
  va_end(ap);
  board().lastLog = std::string(1, level) + " " + tag + ": " + buf;
}

}  // namespace host

// The wall clock: the program's own time() and settimeofday(), on the board's clock. glibc declares them noexcept
// (__THROW); the Mac's libc declares them plain.
#ifndef __THROW
#define __THROW
#endif
extern "C" time_t time(time_t *t) __THROW {
  time_t now = host::wallClock();
  if (t) *t = now;
  return now;
}
extern "C" int settimeofday(const struct timeval *tv, const struct timezone *) __THROW {
  if (tv) host::setWallClock(tv->tv_sec);
  return 0;
}
