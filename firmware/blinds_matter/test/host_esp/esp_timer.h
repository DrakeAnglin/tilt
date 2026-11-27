// Stand-in for ESP-IDF's esp_timer.h on the host board (host_board.h): the board's clock. Tests only.
#pragma once
#include "host_board.h"
inline int64_t esp_timer_get_time() { return host::nowUs(); }
