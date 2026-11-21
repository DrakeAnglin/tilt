// Reading an AS5600 that has been switched to PWM output (firmware/as5600_setup): the angle is the share of each
// 115 Hz frame that the line is high, so it does not shift with the supply or with motor current in the ground wire.
// One frame = 4351 clock periods: 128 high, 4095 for the angle, 128 low (datasheet v1-06, "PWM Output Mode").
//
// The chip's capture timer stamps every edge in hardware. One timer, one channel per port, so several blinds can be
// read (and moved) at the same time. The timer runs only while at least one port's sensor is on (it keeps the chip
// from dozing).
#pragma once
#include "driver/mcpwm_cap.h"
#include "ardu.h"

#define CAP_N 3                                    // ports
static mcpwm_cap_timer_handle_t capTimer = nullptr;
static mcpwm_cap_channel_handle_t capChan[CAP_N] = {nullptr, nullptr, nullptr};
static bool capRunning = false;
static uint32_t capRes = 80000000;                 // timer ticks a second
static portMUX_TYPE capMux = portMUX_INITIALIZER_UNLOCKED;
static volatile uint32_t capRise[CAP_N], capFall[CAP_N], capHigh[CAP_N], capPeriod[CAP_N], capFrames[CAP_N];
static volatile bool capHaveRise[CAP_N], capHaveFall[CAP_N];
static volatile uint32_t capNom[CAP_N], capBad[CAP_N];   // this sensor's own frame length once known; frames thrown away in a row
static volatile int64_t capAt[CAP_N];              // when the last good frame ended (microseconds since start)

static bool IRAM_ATTR capCb(mcpwm_cap_channel_handle_t, const mcpwm_capture_event_data_t *e, void *arg) {
  int k = (int)(intptr_t)arg;
  uint32_t t = e->cap_value;
  if (e->cap_edge == MCPWM_CAP_EDGE_POS) {
    if (capHaveRise[k] && capHaveFall[k]) {
      // A real frame is 115 Hz give or take (chip to chip). Once this sensor's own frame length is known, a frame
      // must match it within 2 %: a noise edge from a running motor shifts a frame's start and would read as a jump of
      // tens of degrees. Four misfits in a row: learn the length again.
      uint32_t per = t - capRise[k], hi = capFall[k] - capRise[k];
      uint32_t nom = capNom[k] ? capNom[k] : capRes / 115, tol = capNom[k] ? nom / 50 : nom / 6;
      if (per > nom - tol && per < nom + tol && hi < per) {
        capHigh[k] = hi; capPeriod[k] = per; capFrames[k] = capFrames[k] + 1; capAt[k] = esp_timer_get_time();
        capNom[k] = capNom[k] ? (capNom[k] * 7 + per) / 8 : per;
        capBad[k] = 0;
      } else if (capNom[k]) {
        capBad[k] = capBad[k] + 1;
        if (capBad[k] >= 4) { capNom[k] = 0; capBad[k] = 0; }
      }
    }
    capRise[k] = t; capHaveRise[k] = true; capHaveFall[k] = false;
  } else if (capHaveRise[k]) { capFall[k] = t; capHaveFall[k] = true; }
  return false;
}
static bool capAny() { for (int k = 0; k < CAP_N; k++) if (capChan[k]) return true; return false; }
void capStop(int k) {
  if (k < 0 || k >= CAP_N || !capChan[k]) return;
  mcpwm_capture_channel_disable(capChan[k]);
  mcpwm_del_capture_channel(capChan[k]);
  capChan[k] = nullptr;
  if (!capAny() && capRunning) {                   // the last one: stop the timer too
    mcpwm_capture_timer_stop(capTimer);
    mcpwm_capture_timer_disable(capTimer);
    capRunning = false;
  }
}
bool capStart(int k, int pin) {
  if (k < 0 || k >= CAP_N) return false;
  capStop(k);
  if (!capTimer) {
    mcpwm_capture_timer_config_t tc = {};
    tc.group_id = 0;
    tc.clk_src = MCPWM_CAPTURE_CLK_SRC_DEFAULT;
    if (mcpwm_new_capture_timer(&tc, &capTimer) != ESP_OK) { capTimer = nullptr; return false; }
    mcpwm_capture_timer_get_resolution(capTimer, &capRes);
  }
  mcpwm_capture_channel_config_t cc = {};
  cc.gpio_num = pin;
  cc.prescale = 1;
  cc.flags.pos_edge = true;
  cc.flags.neg_edge = true;
  if (mcpwm_new_capture_channel(capTimer, &cc, &capChan[k]) != ESP_OK) { capChan[k] = nullptr; return false; }
  mcpwm_capture_event_callbacks_t cbs = {};
  cbs.on_cap = capCb;
  mcpwm_capture_channel_register_event_callbacks(capChan[k], &cbs, (void *)(intptr_t)k);
  portENTER_CRITICAL(&capMux);
  capHaveRise[k] = capHaveFall[k] = false; capFrames[k] = 0; capAt[k] = 0; capPeriod[k] = 0; capNom[k] = 0; capBad[k] = 0;
  portEXIT_CRITICAL(&capMux);
  mcpwm_capture_channel_enable(capChan[k]);
  if (!capRunning) {
    mcpwm_capture_timer_enable(capTimer);
    mcpwm_capture_timer_start(capTimer);
    capRunning = true;
  }
  gpio_set_direction((gpio_num_t)pin, GPIO_MODE_INPUT);   // the plugged-in test leaves the pin switched off
  return true;
}
// The newest frame as a share of a turn (0..1), or -1 if there has been none for 40 ms (no pulses: the line is
// resting low or high, which is the few degrees either side of the sensor's zero, or no magnet).
float capShare(int k) {
  portENTER_CRITICAL(&capMux);
  uint32_t h = capHigh[k], p = capPeriod[k];
  int64_t at = capAt[k];
  portEXIT_CRITICAL(&capMux);
  if (!p || !at || esp_timer_get_time() - at > 40000) return -1.0f;
  float s = ((float)h / (float)p * 4351.0f - 128.0f) / 4095.0f;
  return s < 0 ? 0 : s > 1 ? 1 : s;
}
