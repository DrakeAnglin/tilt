// Stand-in for ESP-IDF's esp_system.h on the host board (host_board.h): the reset reason a test sets. Tests only.
#pragma once
#include "esp_err.h"
#include "host_board.h"
typedef enum {
  ESP_RST_UNKNOWN, ESP_RST_POWERON, ESP_RST_EXT, ESP_RST_SW, ESP_RST_PANIC, ESP_RST_INT_WDT, ESP_RST_TASK_WDT,
  ESP_RST_WDT, ESP_RST_DEEPSLEEP, ESP_RST_BROWNOUT, ESP_RST_SDIO,
} esp_reset_reason_t;
inline esp_reset_reason_t esp_reset_reason() { return (esp_reset_reason_t)host::board().resetReason; }
