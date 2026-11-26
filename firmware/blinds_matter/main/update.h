// Firmware updates: the file comes through the Tilt Hub (hub_link.h hubOta). The new firmware runs on trial: it is
// kept once it has heard from the hub for a minute; if it cannot reach the hub it goes back to this one.
// If there is no firmware to go back to, it stays on this one, still on trial.
// A firmware file may carry a signature at its end: image | signature (64 bytes, r then s) | "TILTSIG1".
// Only a signed file is taken: the signature proves it came from whoever holds the release key. And an owner must have
// allowed updates first (/api/otaopen, 5 minutes).
#pragma once
#include <esp_ota_ops.h>
#include <esp_image_format.h>
#include <mbedtls/sha256.h>
#include <mbedtls/ecdsa.h>
#include "fwkey.h"                               // FW_SIGN_PUB
#include "motion.h"                              // stopAll, event, stats
#include "sec.h"                                 // owned
#include "api.h"                                 // Lock, ok, fail, restartSoon

uint32_t otaWindow = 0;                          // millis until which a firmware upload is accepted
bool otaPending = false;                         // this firmware is on trial (kept or dropped by webTick, /api/keep)
static uint32_t appSize = 0;                     // this firmware's size, for the developer page
void updateBegin() {                             // is this firmware on trial? how big is it?
  const esp_partition_t *part = esp_ota_get_running_partition();
  esp_image_metadata_t md = {};
  esp_partition_pos_t pos = {part->address, part->size};
  if (esp_image_get_metadata(&pos, &md) == ESP_OK) appSize = md.image_len;
  esp_ota_img_states_t st;
  otaPending = esp_ota_get_state_partition(part, &st) == ESP_OK && st == ESP_OTA_IMG_PENDING_VERIFY;
}

static const char SIG_MAGIC[8] = {'T', 'I', 'L', 'T', 'S', 'I', 'G', '1'};
bool fwSignatureOk(const uint8_t hash[32], const uint8_t sig[64]) {
  mbedtls_ecp_group grp; mbedtls_ecp_point q; mbedtls_mpi r, s;
  mbedtls_ecp_group_init(&grp); mbedtls_ecp_point_init(&q); mbedtls_mpi_init(&r); mbedtls_mpi_init(&s);
  bool ok = mbedtls_ecp_group_load(&grp, MBEDTLS_ECP_DP_SECP256R1) == 0 && mbedtls_ecp_point_read_binary(&grp, &q, FW_SIGN_PUB, 65) == 0 &&
            mbedtls_mpi_read_binary(&r, sig, 32) == 0 && mbedtls_mpi_read_binary(&s, sig + 32, 32) == 0 &&
            mbedtls_ecdsa_verify(&grp, hash, 32, &q, &r, &s) == 0;
  mbedtls_ecp_group_free(&grp); mbedtls_ecp_point_free(&q); mbedtls_mpi_free(&r); mbedtls_mpi_free(&s);
  return ok;
}
