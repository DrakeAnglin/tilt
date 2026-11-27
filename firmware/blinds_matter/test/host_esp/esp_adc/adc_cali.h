// Stand-in for ESP-IDF's esp_adc/adc_cali.h on the host board (host_board.h): the raw reading already is millivolts
// (adc_oneshot.h). With no scheme the call fails and leaves the voltage alone, as on the chip. Tests only.
#pragma once
#include "../esp_err.h"
struct host_adc_cali { int unit; };
typedef host_adc_cali *adc_cali_handle_t;
inline esp_err_t adc_cali_raw_to_voltage(adc_cali_handle_t h, int raw, int *mv) {
  if (!h) return ESP_ERR_INVALID_ARG;
  *mv = raw;
  return ESP_OK;
}
