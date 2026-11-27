// Stand-in for ESP-IDF's driver/gpio.h on the host board (host_board.h): the board keeps each pin's mode and level,
// and their history (host::pinTrace). Tests only.
#pragma once
#include "../esp_err.h"
#include "../host_board.h"
typedef int gpio_num_t;
typedef enum { GPIO_MODE_DISABLE = 0, GPIO_MODE_INPUT = 1, GPIO_MODE_OUTPUT = 2 } gpio_mode_t;
typedef struct { uint64_t pin_bit_mask; gpio_mode_t mode; int pull_up_en, pull_down_en, intr_type; } gpio_config_t;
inline esp_err_t gpio_config(const gpio_config_t *c) {
  for (int pin = 0; pin < 64; pin++)
    if (c->pin_bit_mask >> pin & 1) {
      bool out = c->mode == GPIO_MODE_OUTPUT;
      host::board().mode[pin] = out ? 1 : 0;
      host::board().trace[pin] += out ? "O" : "I";
    }
  return ESP_OK;
}
inline esp_err_t gpio_set_level(gpio_num_t pin, uint32_t level) {
  host::board().level[pin] = level ? 1 : 0;
  host::board().trace[pin] += level ? "1" : "0";
  return ESP_OK;
}
