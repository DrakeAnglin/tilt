// Stand-in for ESP-IDF's esp_adc/adc_cali_scheme.h on the host board (host_board.h): the curve-fitting scheme. Tests only.
#pragma once
#include "adc_oneshot.h"
#include "adc_cali.h"
typedef struct { adc_unit_t unit_id; adc_channel_t chan; adc_atten_t atten; adc_bitwidth_t bitwidth; } adc_cali_curve_fitting_config_t;
inline esp_err_t adc_cali_create_scheme_curve_fitting(const adc_cali_curve_fitting_config_t *c, adc_cali_handle_t *h) {
  static host_adc_cali schemes[2];
  schemes[c->unit_id].unit = c->unit_id;
  *h = &schemes[c->unit_id];
  return ESP_OK;
}
