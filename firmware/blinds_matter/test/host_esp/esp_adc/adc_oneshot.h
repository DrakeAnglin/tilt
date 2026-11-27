// Stand-in for ESP-IDF's esp_adc/adc_oneshot.h on the host board (host_board.h). ADC1's channels are GPIO 0 to 6, as
// on the ESP32-C6. A raw reading here is the pin's millivolts (host::setMilliVolts); calibration passes it on.
// With no unit (adc_oneshot_new_unit not called) a read fails and leaves the raw value alone, as on the chip. Tests only.
#pragma once
#include "../esp_err.h"
#include "../host_board.h"
typedef enum { ADC_UNIT_1 = 0, ADC_UNIT_2 } adc_unit_t;
typedef int adc_channel_t;
typedef enum { ADC_ATTEN_DB_0 = 0, ADC_ATTEN_DB_2_5, ADC_ATTEN_DB_6, ADC_ATTEN_DB_12 } adc_atten_t;
typedef enum { ADC_BITWIDTH_DEFAULT = 0, ADC_BITWIDTH_12 = 12 } adc_bitwidth_t;
struct host_adc_unit { int unit; };
typedef host_adc_unit *adc_oneshot_unit_handle_t;
typedef struct { adc_unit_t unit_id; int clk_src; int ulp_mode; } adc_oneshot_unit_init_cfg_t;
typedef struct { adc_atten_t atten; adc_bitwidth_t bitwidth; } adc_oneshot_chan_cfg_t;
inline esp_err_t adc_oneshot_new_unit(const adc_oneshot_unit_init_cfg_t *c, adc_oneshot_unit_handle_t *h) {
  static host_adc_unit units[2];
  units[c->unit_id].unit = c->unit_id;
  *h = &units[c->unit_id];
  return ESP_OK;
}
inline esp_err_t adc_oneshot_io_to_channel(int pin, adc_unit_t *unit, adc_channel_t *ch) {
  if (pin < 0 || pin > 6) return ESP_ERR_NOT_FOUND;
  *unit = ADC_UNIT_1;
  *ch = pin;
  return ESP_OK;
}
inline esp_err_t adc_oneshot_config_channel(adc_oneshot_unit_handle_t h, adc_channel_t, const adc_oneshot_chan_cfg_t *) {
  return h ? ESP_OK : ESP_ERR_INVALID_ARG;
}
inline esp_err_t adc_oneshot_read(adc_oneshot_unit_handle_t h, adc_channel_t ch, int *raw) {
  if (!h) return ESP_ERR_INVALID_ARG;
  *raw = host::board().mv.count(ch) ? host::board().mv[ch] : 0;
  return ESP_OK;
}
