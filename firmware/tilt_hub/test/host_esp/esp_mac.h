// Stand-in for ESP-IDF's esp_mac.h on the host board: the MAC a test sets (hub_board.h). Tests only.
#pragma once
#include "esp_err.h"
#include "hub_board.h"
typedef enum { ESP_MAC_WIFI_STA, ESP_MAC_WIFI_SOFTAP, ESP_MAC_BT, ESP_MAC_ETH, ESP_MAC_IEEE802154 } esp_mac_type_t;
inline esp_err_t esp_read_mac(uint8_t *mac, esp_mac_type_t) { memcpy(mac, hubhost::hubBoard().mac, 6); return ESP_OK; }
