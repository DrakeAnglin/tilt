// Stand-in for ESP-IDF's esp_image_format.h on the host board: the running firmware's image length, as a test sets it
// (host_board.h slots). Tests only.
#pragma once
#include "esp_err.h"
#include "host_board.h"
typedef struct { uint32_t offset; uint32_t size; } esp_partition_pos_t;
typedef struct { uint32_t start_addr; uint32_t image_len; } esp_image_metadata_t;
inline esp_err_t esp_image_get_metadata(const esp_partition_pos_t *, esp_image_metadata_t *md) {
  if (host::slots().imageLen < 0) return ESP_FAIL;
  md->image_len = (uint32_t)host::slots().imageLen;
  return ESP_OK;
}
