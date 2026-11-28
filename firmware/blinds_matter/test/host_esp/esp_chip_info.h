// Stand-in for ESP-IDF's esp_chip_info.h on the host board: the chip revision from the board (host_board.h), the rest
// fixed, enough for main/web.h. Tests only.
#pragma once
#include <cstdint>
#include "host_board.h"
typedef struct { int model; uint32_t features; uint16_t revision; uint8_t cores; } esp_chip_info_t;
inline void esp_chip_info(esp_chip_info_t *ci) { ci->model = 23; ci->features = 0; ci->revision = host::board().chipRev; ci->cores = 1; }
