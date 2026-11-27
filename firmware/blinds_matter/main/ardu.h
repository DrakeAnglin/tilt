// The few Arduino calls the blinds code uses, written on ESP-IDF, so config.h / store.h / power.h / motion.h are shared
// with the Wi-Fi firmware nearly unchanged.
#pragma once
#include <stdio.h>
#include <stdarg.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <ctype.h>
#include <time.h>
#include <string>
#include <algorithm>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "esp_rom_sys.h"
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "nvs_flash.h"
#include "nvs.h"

typedef std::string String;
using std::min;
using std::max;
#define constrain(v, lo, hi) ((v) < (lo) ? (lo) : ((v) > (hi) ? (hi) : (v)))
#define HIGH 1
#define LOW 0
#define INPUT 0
#define OUTPUT 1
#define ADC_11db 0
#ifndef PROGMEM
#define PROGMEM
#endif

inline uint32_t millis() { return (uint32_t)(esp_timer_get_time() / 1000); }
inline uint64_t uptimeMs() { return (uint64_t)(esp_timer_get_time() / 1000); }   // never wraps
inline void delay(uint32_t ms) { vTaskDelay(pdMS_TO_TICKS(ms) ? pdMS_TO_TICKS(ms) : 1); }
inline void delayMicroseconds(uint32_t us) { esp_rom_delay_us(us); }

// ---- pins
inline void pinMode(int pin, int mode) {
  gpio_config_t c = {};
  c.pin_bit_mask = 1ULL << pin;
  c.mode = mode == OUTPUT ? GPIO_MODE_OUTPUT : GPIO_MODE_DISABLE;   // "input" here always means: let go, the ADC reads it
  gpio_config(&c);
}
inline void digitalWrite(int pin, int level) { gpio_set_level((gpio_num_t)pin, level); }

// ---- ADC, in millivolts (one unit, calibrated)
inline adc_oneshot_unit_handle_t &adcUnit() { static adc_oneshot_unit_handle_t h = nullptr; return h; }
inline adc_cali_handle_t &adcCali() { static adc_cali_handle_t h = nullptr; return h; }
inline void adcBegin() {
  adc_oneshot_unit_init_cfg_t u = {};
  u.unit_id = ADC_UNIT_1;
  adc_oneshot_new_unit(&u, &adcUnit());
  adc_cali_curve_fitting_config_t cc = {};
  cc.unit_id = ADC_UNIT_1;
  cc.atten = ADC_ATTEN_DB_12;
  cc.bitwidth = ADC_BITWIDTH_DEFAULT;
  adc_cali_create_scheme_curve_fitting(&cc, &adcCali());
}
inline void analogSetPinAttenuation(int pin, int) {            // also: make the pin an ADC input
  adc_unit_t unit;
  adc_channel_t ch;
  if (adc_oneshot_io_to_channel(pin, &unit, &ch) != ESP_OK) return;
  adc_oneshot_chan_cfg_t c = {};
  c.atten = ADC_ATTEN_DB_12;
  c.bitwidth = ADC_BITWIDTH_DEFAULT;
  adc_oneshot_config_channel(adcUnit(), ch, &c);
}
inline uint32_t analogReadMilliVolts(int pin) {
  adc_unit_t unit;
  adc_channel_t ch;
  int raw = 0, mv = 0;
  if (adc_oneshot_io_to_channel(pin, &unit, &ch) != ESP_OK) return 0;
  adc_oneshot_read(adcUnit(), ch, &raw);
  adc_cali_raw_to_voltage(adcCali(), raw, &mv);
  return mv < 0 ? 0 : mv;
}

// ---- PWM: one LEDC channel per pin, in the order they are attached
inline int &ledcCount() { static int n = 0; return n; }
inline int *ledcPins() { static int p[8]; return p; }
inline bool ledcAttach(int pin, int hz, int bits) {
  if (ledcCount() == 0) {
    ledc_timer_config_t t = {};
    t.speed_mode = LEDC_LOW_SPEED_MODE;
    t.timer_num = LEDC_TIMER_0;
    t.duty_resolution = (ledc_timer_bit_t)bits;
    t.freq_hz = hz;
    t.clk_cfg = LEDC_AUTO_CLK;
    ledc_timer_config(&t);
  }
  if (ledcCount() >= 8) return false;
  ledc_channel_config_t c = {};
  c.gpio_num = pin;
  c.speed_mode = LEDC_LOW_SPEED_MODE;
  c.channel = (ledc_channel_t)ledcCount();
  c.timer_sel = LEDC_TIMER_0;
  c.duty = 255;
  ledc_channel_config(&c);
  ledcPins()[ledcCount()++] = pin;
  return true;
}
inline void ledcWrite(int pin, int duty) {
  for (int i = 0; i < ledcCount(); i++)
    if (ledcPins()[i] == pin) {
      ledc_set_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)i, duty);
      ledc_update_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)i);
      return;
    }
}

// ---- settings storage (the part of Arduino's Preferences that is used)
class Preferences {
  nvs_handle_t h = 0;
 public:
  bool begin(const char *ns, bool) { return nvs_open(ns, NVS_READWRITE, &h) == ESP_OK; }
  size_t getBytes(const char *k, void *buf, size_t len) { size_t n = len; return nvs_get_blob(h, k, buf, &n) == ESP_OK ? n : 0; }
  size_t putBytes(const char *k, const void *buf, size_t len) { nvs_set_blob(h, k, buf, len); nvs_commit(h); return len; }
  uint8_t getUChar(const char *k, uint8_t def) { uint8_t v; return nvs_get_u8(h, k, &v) == ESP_OK ? v : def; }
  void putUChar(const char *k, uint8_t v) { nvs_set_u8(h, k, v); nvs_commit(h); }
};

// Serial is only used for "is a computer listening": logs go through ESP_LOG instead.
struct SerialShim { operator bool() const { return false; } void println(const char *) {} void print(const char *) {} void printf(const char *, ...) {} void flush() {} };
static SerialShim Serial;
