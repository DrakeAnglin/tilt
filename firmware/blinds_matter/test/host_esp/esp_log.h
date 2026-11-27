// Stand-in for ESP-IDF's esp_log.h on the host board (host_board.h): the board keeps the last line
// (host::lastLog()) and prints nothing. Tests only.
#pragma once
#include "host_board.h"
#define ESP_LOGE(tag, ...) host::espLog('E', tag, __VA_ARGS__)
#define ESP_LOGW(tag, ...) host::espLog('W', tag, __VA_ARGS__)
#define ESP_LOGI(tag, ...) host::espLog('I', tag, __VA_ARGS__)
#define ESP_LOGD(tag, ...) host::espLog('D', tag, __VA_ARGS__)
#define ESP_LOGV(tag, ...) host::espLog('V', tag, __VA_ARGS__)
