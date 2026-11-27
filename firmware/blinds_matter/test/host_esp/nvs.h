// Stand-in for ESP-IDF's nvs.h on the host board (host_board.h): flash in memory, by namespace and key, kept across
// host::restart(). Keys are typed as in NVS (a blob, or a u8). A blob read into a smaller buffer fails with
// ESP_ERR_NVS_INVALID_LENGTH and gives the stored size; a larger buffer gets the stored bytes and their count. Tests only.
// Strings and u32s too: a string's length counts its ending zero, and one read into a buffer too small fails the same
// way (no buffer: only its length).
#pragma once
#include "esp_err.h"
#include "host_board.h"
typedef uint32_t nvs_handle_t;
typedef enum { NVS_READONLY, NVS_READWRITE } nvs_open_mode_t;
inline esp_err_t nvs_open(const char *ns, nvs_open_mode_t, nvs_handle_t *h) {
  host::board().handles.push_back(ns);
  *h = (nvs_handle_t)host::board().handles.size();
  return ESP_OK;
}
// The value under a key of an open handle (made empty when `make`), or nullptr: no such handle, or no such key.
inline host::Entry *host_nvs_entry(nvs_handle_t h, const char *key, bool make) {
  host::Board &b = host::board();
  if (h == 0 || h > b.handles.size()) return nullptr;
  auto &ns = b.flash[b.handles[h - 1]];
  if (!make && !ns.count(key)) return nullptr;
  return &ns[key];
}
inline esp_err_t nvs_get_blob(nvs_handle_t h, const char *key, void *out, size_t *len) {
  host::Entry *e = host_nvs_entry(h, key, false);
  if (!e) return ESP_ERR_NVS_NOT_FOUND;
  if (!e->blob) return ESP_ERR_NVS_TYPE_MISMATCH;
  size_t room = *len;
  *len = e->bytes.size();
  if (room < e->bytes.size()) return ESP_ERR_NVS_INVALID_LENGTH;
  memcpy(out, e->bytes.data(), e->bytes.size());
  return ESP_OK;
}
inline esp_err_t nvs_set_blob(nvs_handle_t h, const char *key, const void *p, size_t len) {
  host::Entry *e = host_nvs_entry(h, key, true);
  if (!e) return ESP_ERR_NVS_INVALID_HANDLE;
  e->blob = true;
  e->bytes.assign((const uint8_t *)p, (const uint8_t *)p + len);
  return ESP_OK;
}
inline esp_err_t nvs_get_u8(nvs_handle_t h, const char *key, uint8_t *v) {
  host::Entry *e = host_nvs_entry(h, key, false);
  if (!e) return ESP_ERR_NVS_NOT_FOUND;
  if (e->blob) return ESP_ERR_NVS_TYPE_MISMATCH;
  *v = e->bytes[0];
  return ESP_OK;
}
inline esp_err_t nvs_set_u8(nvs_handle_t h, const char *key, uint8_t v) {
  host::Entry *e = host_nvs_entry(h, key, true);
  if (!e) return ESP_ERR_NVS_INVALID_HANDLE;
  e->blob = false;
  e->bytes.assign(1, v);
  return ESP_OK;
}
inline esp_err_t nvs_commit(nvs_handle_t h) { return h && h <= host::board().handles.size() ? ESP_OK : ESP_ERR_NVS_INVALID_HANDLE; }
// The kind of a value that is not a blob ('s' a string, 'u' a u32, 0 a u8), kept beside it by the board.
inline char &host_nvs_kind(nvs_handle_t h, const char *key) { return host::board().kind[host::board().handles[h - 1]][key]; }
inline esp_err_t nvs_get_str(nvs_handle_t h, const char *key, char *out, size_t *len) {
  host::Entry *e = host_nvs_entry(h, key, false);
  if (!e) return ESP_ERR_NVS_NOT_FOUND;
  if (e->blob || host_nvs_kind(h, key) != 's') return ESP_ERR_NVS_TYPE_MISMATCH;
  size_t room = *len;
  *len = e->bytes.size();
  if (!out) return ESP_OK;
  if (room < e->bytes.size()) return ESP_ERR_NVS_INVALID_LENGTH;
  memcpy(out, e->bytes.data(), e->bytes.size());
  return ESP_OK;
}
inline esp_err_t nvs_set_str(nvs_handle_t h, const char *key, const char *v) {
  host::Entry *e = host_nvs_entry(h, key, true);
  if (!e) return ESP_ERR_NVS_INVALID_HANDLE;
  e->blob = false;
  e->bytes.assign(v, v + strlen(v) + 1);
  host_nvs_kind(h, key) = 's';
  return ESP_OK;
}
inline esp_err_t nvs_get_u32(nvs_handle_t h, const char *key, uint32_t *v) {
  host::Entry *e = host_nvs_entry(h, key, false);
  if (!e) return ESP_ERR_NVS_NOT_FOUND;
  if (e->blob || host_nvs_kind(h, key) != 'u') return ESP_ERR_NVS_TYPE_MISMATCH;
  memcpy(v, e->bytes.data(), 4);
  return ESP_OK;
}
inline esp_err_t nvs_set_u32(nvs_handle_t h, const char *key, uint32_t v) {
  host::Entry *e = host_nvs_entry(h, key, true);
  if (!e) return ESP_ERR_NVS_INVALID_HANDLE;
  e->blob = false;
  e->bytes.assign((const uint8_t *)&v, (const uint8_t *)&v + 4);
  host_nvs_kind(h, key) = 'u';
  return ESP_OK;
}
inline void nvs_close(nvs_handle_t) {}
