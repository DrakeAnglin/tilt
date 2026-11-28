// Stand-in for ESP-IDF's esp_random.h on the host board (host_board.h): a counted stream or the exact bytes a test
// queues. Tests only.
#pragma once
#include <cstddef>
#include "host_board.h"
inline void esp_fill_random(void *buf, size_t len) { host::fillRandom(buf, len); }
inline uint32_t esp_random() { uint32_t v; host::fillRandom(&v, sizeof v); return v; }
