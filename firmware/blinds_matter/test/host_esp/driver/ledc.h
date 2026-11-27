// Stand-in for ESP-IDF's driver/ledc.h on the host board (host_board.h): the board keeps each channel's pin and duty
// (host::dutyOf). A duty takes effect at ledc_update_duty, as on the chip. Tests only.
#pragma once
#include "../esp_err.h"
#include "../host_board.h"
typedef enum { LEDC_LOW_SPEED_MODE = 0 } ledc_mode_t;
typedef enum { LEDC_TIMER_0 = 0, LEDC_TIMER_1, LEDC_TIMER_2, LEDC_TIMER_3 } ledc_timer_t;
typedef int ledc_timer_bit_t;
typedef int ledc_channel_t;
typedef enum { LEDC_AUTO_CLK = 0 } ledc_clk_cfg_t;
typedef struct {
  ledc_mode_t speed_mode; ledc_timer_bit_t duty_resolution; ledc_timer_t timer_num; uint32_t freq_hz; ledc_clk_cfg_t clk_cfg;
} ledc_timer_config_t;
typedef struct {
  int gpio_num; ledc_mode_t speed_mode; ledc_channel_t channel; int intr_type; ledc_timer_t timer_sel; uint32_t duty; int hpoint;
} ledc_channel_config_t;
inline esp_err_t ledc_timer_config(const ledc_timer_config_t *) { host::board().ledcTimer = true; return ESP_OK; }
inline esp_err_t ledc_channel_config(const ledc_channel_config_t *c) {
  if (!host::board().ledcTimer) host::fault("ledc_channel_config before ledc_timer_config");
  host::board().chanPin[c->channel] = c->gpio_num;
  host::board().duty[c->channel] = host::board().pendingDuty[c->channel] = (int)c->duty;
  return ESP_OK;
}
inline esp_err_t ledc_set_duty(ledc_mode_t, ledc_channel_t ch, uint32_t duty) {
  host::board().pendingDuty[ch] = (int)duty;
  return ESP_OK;
}
inline esp_err_t ledc_update_duty(ledc_mode_t, ledc_channel_t ch) {
  host::board().duty[ch] = host::board().pendingDuty[ch];
  return ESP_OK;
}
