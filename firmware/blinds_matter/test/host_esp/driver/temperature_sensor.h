// Stand-in for ESP-IDF's driver/temperature_sensor.h on the host board: a sensor that installs and reads a fixed
// value, enough for main/web.h. Tests only.
#pragma once
#include "../esp_err.h"
struct temperature_sensor_obj_t { float celsius = 24.5f; };
typedef temperature_sensor_obj_t *temperature_sensor_handle_t;
typedef struct { int range_min; int range_max; } temperature_sensor_config_t;
#define TEMPERATURE_SENSOR_CONFIG_DEFAULT(min, max) {min, max}
inline esp_err_t temperature_sensor_install(const temperature_sensor_config_t *, temperature_sensor_handle_t *h) {
  static temperature_sensor_obj_t sensor;
  *h = &sensor;
  return ESP_OK;
}
inline esp_err_t temperature_sensor_enable(temperature_sensor_handle_t) { return ESP_OK; }
inline esp_err_t temperature_sensor_get_celsius(temperature_sensor_handle_t h, float *c) { *c = h->celsius; return ESP_OK; }
