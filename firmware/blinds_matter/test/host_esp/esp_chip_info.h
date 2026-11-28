// Stand-in for ESP-IDF's esp_chip_info.h on the host board: fixed values, enough for main/web.h. Tests only.
#pragma once
#include <cstdint>
typedef struct { int model; uint32_t features; uint16_t revision; uint8_t cores; } esp_chip_info_t;
inline void esp_chip_info(esp_chip_info_t *ci) { ci->model = 23; ci->features = 0; ci->revision = 1; ci->cores = 1; }
