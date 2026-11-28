// Stand-in for ESP-IDF's esp_ota_ops.h (and the partition call with it) on the host board: the firmware slots a test
// sets (host_board.h slots). Keep and go-back change the running slot's state; go-back is refused when the other slot
// holds no firmware (it returns why), and one that works does not return (host::Restarted, as esp_restart). A restart
// of the board keeps the slots. Tests only.
#pragma once
#include "esp_err.h"
#include "host_board.h"
typedef struct { uint32_t address; uint32_t size; char label[17]; } esp_partition_t;
typedef enum {
  ESP_OTA_IMG_NEW = 0, ESP_OTA_IMG_PENDING_VERIFY = 1, ESP_OTA_IMG_VALID = 2, ESP_OTA_IMG_INVALID = 3,
  ESP_OTA_IMG_ABORTED = 4, ESP_OTA_IMG_UNDEFINED = -1,
} esp_ota_img_states_t;
inline const esp_partition_t *esp_ota_get_running_partition() {
  static esp_partition_t p;
  host::Slots &s = host::slots();
  p.address = s.address;
  p.size = s.size;
  memcpy(p.label, s.label, sizeof p.label);
  return &p;
}
inline esp_err_t esp_ota_get_state_partition(const esp_partition_t *, esp_ota_img_states_t *st) {
  if (host::slots().state == host::SLOT_UNREADABLE) return ESP_ERR_NOT_FOUND;
  *st = (esp_ota_img_states_t)host::slots().state;
  return ESP_OK;
}
inline esp_err_t esp_ota_mark_app_valid_cancel_rollback() { host::slots().state = host::SLOT_KEPT; return ESP_OK; }
inline esp_err_t esp_ota_mark_app_invalid_rollback_and_reboot() {   // returns only when refused
  if (!host::slots().otherHasFirmware) return ESP_ERR_OTA_ROLLBACK_FAILED;
  host::slots().state = host::SLOT_GONE_BACK;
  host::restarted();
}
inline esp_err_t esp_partition_get_sha256(const esp_partition_t *, uint8_t *sha) {
  memcpy(sha, host::slots().sha, 32);
  return ESP_OK;
}
