// Stand-in for ESP-IDF's esp_system.h on the host board (host_board.h): the reset reason a test sets, a restart that
// does not return (the board counts it and throws host::Restarted; the test catches it and restarts the board), the
// IDF version (fixed) and the free memory from the board. Tests only.
#pragma once
#include "esp_err.h"
#include "host_board.h"
typedef enum {
  ESP_RST_UNKNOWN, ESP_RST_POWERON, ESP_RST_EXT, ESP_RST_SW, ESP_RST_PANIC, ESP_RST_INT_WDT, ESP_RST_TASK_WDT,
  ESP_RST_WDT, ESP_RST_DEEPSLEEP, ESP_RST_BROWNOUT, ESP_RST_SDIO, ESP_RST_USB,
} esp_reset_reason_t;
inline esp_reset_reason_t esp_reset_reason() { return (esp_reset_reason_t)host::board().resetReason; }
[[noreturn]] inline void esp_restart() { host::restarted(); }
inline const char *esp_get_idf_version() { return "v5.4.1"; }
inline uint32_t esp_get_free_heap_size() { return host::board().heapFree; }
inline uint32_t esp_get_minimum_free_heap_size() { return host::board().heapMin; }
