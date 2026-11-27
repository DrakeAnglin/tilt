// Stand-in for ESP-IDF's nvs_flash.h on the host board (host_board.h): the flash is always ready; erasing it is
// host::wipeFlash(). Tests only.
#pragma once
#include "nvs.h"
inline esp_err_t nvs_flash_init() { return ESP_OK; }
inline esp_err_t nvs_flash_erase() { host::wipeFlash(); return ESP_OK; }
