// Stand-in for ESP-IDF's esp_rom_sys.h on the host board (host_board.h): a busy wait moves the board's clock. Tests only.
#pragma once
#include "host_board.h"
inline void esp_rom_delay_us(uint32_t us) { host::advanceUs(us); }
