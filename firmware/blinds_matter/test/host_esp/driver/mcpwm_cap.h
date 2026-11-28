// Stand-in for ESP-IDF's driver/mcpwm_cap.h on the host board (host_board.h): the capture timer (80 MHz) and its
// channels, each with its pin, callback and on/off state. It counts the timers made and the timer's starts and stops.
// Edges reach a channel's callback through host::capEdge: a PWM tilter that is on feeds them as the clock moves
// (host_tilter.h), and a test can feed one raw edge (noise). host::failNext("mcpwm_new_capture_timer" or
// "mcpwm_new_capture_channel") makes the next such call fail. A restart clears it all, as on the chip. Tests only.
#pragma once
#include <set>
#include <string>
#include <vector>
#include "../esp_err.h"
#include "../host_board.h"

typedef enum { MCPWM_CAP_EDGE_POS = 0, MCPWM_CAP_EDGE_NEG = 1 } mcpwm_capture_edge_t;
typedef enum { MCPWM_CAPTURE_CLK_SRC_DEFAULT = 0 } mcpwm_capture_clock_source_t;
struct host_cap_timer { bool enabled = false, running = false; };
struct host_cap_channel;
typedef host_cap_timer *mcpwm_cap_timer_handle_t;
typedef host_cap_channel *mcpwm_cap_channel_handle_t;
typedef struct { uint32_t cap_value; mcpwm_capture_edge_t cap_edge; } mcpwm_capture_event_data_t;
typedef bool (*mcpwm_capture_event_cb_t)(mcpwm_cap_channel_handle_t, const mcpwm_capture_event_data_t *, void *);
struct host_cap_channel { host_cap_timer *timer; int pin; mcpwm_capture_event_cb_t cb; void *arg; bool enabled; };
typedef struct { int group_id; mcpwm_capture_clock_source_t clk_src; uint32_t resolution_hz; } mcpwm_capture_timer_config_t;
typedef struct {
  int gpio_num;
  uint32_t prescale;
  struct { uint32_t pos_edge : 1, neg_edge : 1, pull_up : 1, pull_down : 1, invert_cap_signal : 1; } flags;
} mcpwm_capture_channel_config_t;
typedef struct { mcpwm_capture_event_cb_t on_cap; } mcpwm_capture_event_callbacks_t;

namespace host {
const uint32_t CAP_HZ = 80000000;                      // the capture timer's clock
struct Capture {
  std::vector<host_cap_timer *> timers;
  std::vector<host_cap_channel *> channels;
  int starts = 0, stops = 0;
  std::set<std::string> fail;
};
inline Capture &capture() { static Capture c; return c; }
inline void failNext(const char *call) { capture().fail.insert(call); }
inline bool failing(const char *call) { return capture().fail.erase(call) > 0; }
inline int capTimers() { return (int)capture().timers.size(); }
inline int capTimerStarts() { return capture().starts; }
inline int capTimerStops() { return capture().stops; }
inline bool capTimerRunning() { for (auto *t : capture().timers) if (t->running) return true; return false; }
inline bool capListening(int pin) {                    // a channel on the pin that is on, its timer running
  for (auto *c : capture().channels) if (c->pin == pin && c->enabled && c->timer->running) return true;
  return false;
}
// One edge on a pin, stamped with the timer's count: each channel on the pin that is on and whose timer runs gets it.
inline void capEdge(int pin, bool rising, uint32_t ticks) {
  std::vector<host_cap_channel *> on;
  for (auto *c : capture().channels) if (c->pin == pin && c->enabled && c->timer->running && c->cb) on.push_back(c);
  for (auto *c : on) {
    mcpwm_capture_event_data_t e = {ticks, rising ? MCPWM_CAP_EDGE_POS : MCPWM_CAP_EDGE_NEG};
    c->cb(c, &e, c->arg);
  }
}
inline void captureRestart() {
  Capture &c = capture();
  for (auto *t : c.timers) delete t;
  for (auto *ch : c.channels) delete ch;
  c = Capture();
}
inline const bool captureHooked = (onRestart(captureRestart), true);
}  // namespace host

inline esp_err_t mcpwm_new_capture_timer(const mcpwm_capture_timer_config_t *, mcpwm_cap_timer_handle_t *t) {
  if (host::failing("mcpwm_new_capture_timer")) return ESP_FAIL;
  *t = new host_cap_timer();
  host::capture().timers.push_back(*t);
  return ESP_OK;
}
inline esp_err_t mcpwm_capture_timer_get_resolution(mcpwm_cap_timer_handle_t, uint32_t *hz) { *hz = host::CAP_HZ; return ESP_OK; }
inline esp_err_t mcpwm_capture_timer_enable(mcpwm_cap_timer_handle_t t) {
  if (t->enabled) host::fault("mcpwm_capture_timer_enable on a timer already on");
  t->enabled = true;
  return ESP_OK;
}
inline esp_err_t mcpwm_capture_timer_disable(mcpwm_cap_timer_handle_t t) {
  if (t->running) host::fault("mcpwm_capture_timer_disable on a running timer");
  t->enabled = false;
  return ESP_OK;
}
inline esp_err_t mcpwm_capture_timer_start(mcpwm_cap_timer_handle_t t) {
  if (!t->enabled) host::fault("mcpwm_capture_timer_start on a timer not enabled");
  t->running = true;
  host::capture().starts++;
  return ESP_OK;
}
inline esp_err_t mcpwm_capture_timer_stop(mcpwm_cap_timer_handle_t t) {
  t->running = false;
  host::capture().stops++;
  return ESP_OK;
}
inline esp_err_t mcpwm_new_capture_channel(mcpwm_cap_timer_handle_t t, const mcpwm_capture_channel_config_t *c,
                                           mcpwm_cap_channel_handle_t *ch) {
  if (host::failing("mcpwm_new_capture_channel")) return ESP_FAIL;
  *ch = new host_cap_channel{t, c->gpio_num, nullptr, nullptr, false};
  host::capture().channels.push_back(*ch);
  return ESP_OK;
}
inline esp_err_t mcpwm_capture_channel_register_event_callbacks(mcpwm_cap_channel_handle_t ch, const mcpwm_capture_event_callbacks_t *cbs,
                                                                void *arg) {
  ch->cb = cbs->on_cap;
  ch->arg = arg;
  return ESP_OK;
}
inline esp_err_t mcpwm_capture_channel_enable(mcpwm_cap_channel_handle_t ch) { ch->enabled = true; return ESP_OK; }
inline esp_err_t mcpwm_capture_channel_disable(mcpwm_cap_channel_handle_t ch) { ch->enabled = false; return ESP_OK; }
inline esp_err_t mcpwm_del_capture_channel(mcpwm_cap_channel_handle_t ch) {
  auto &v = host::capture().channels;
  for (size_t i = 0; i < v.size(); i++)
    if (v[i] == ch) { v.erase(v.begin() + i); delete ch; return ESP_OK; }
  host::fault("mcpwm_del_capture_channel on a channel not made");
  return ESP_ERR_INVALID_ARG;
}
