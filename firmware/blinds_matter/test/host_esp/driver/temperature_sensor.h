// Stand-in for ESP-IDF's driver/temperature_sensor.h on the host board: the chip's temperature from the board
// (host_board.h), and an install that fails when a test says so. Tests only.
#pragma once
#include "../esp_err.h"
#include "../host_board.h"
struct temperature_sensor_obj_t { int unused; };
typedef temperature_sensor_obj_t *temperature_sensor_handle_t;
typedef struct { int range_min; int range_max; } temperature_sensor_config_t;
#define TEMPERATURE_SENSOR_CONFIG_DEFAULT(min, max) {min, max}
inline esp_err_t temperature_sensor_install(const temperature_sensor_config_t *, temperature_sensor_handle_t *h) {
  static temperature_sensor_obj_t sensor;
  if (host::board().noTempSensor) return ESP_FAIL;
  *h = &sensor;
  return ESP_OK;
}
inline esp_err_t temperature_sensor_enable(temperature_sensor_handle_t) { return ESP_OK; }
inline esp_err_t temperature_sensor_get_celsius(temperature_sensor_handle_t, float *c) { *c = host::board().celsius; return ESP_OK; }
