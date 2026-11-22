// Firmware upload over Wi-Fi: a signed file (or, in a developer build, the update password).
// Part of the web server (web.h includes it in place): uses its helpers and the blinds' shared state.
#pragma once

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
esp_err_t hUpdate(httpd_req_t *r) {
  char pw[80] = "";
  httpd_req_get_hdr_value_str(r, "X-Update-Password", pw, sizeof pw);
  bool pwOk = OTA_PASSWORD[0] && strcmp(pw, OTA_PASSWORD) == 0;      // no password in a release: only signed files
  if (owned() && !openApi && (int32_t)(otaWindow - millis()) <= 0) return fail(r, "updates are locked: the owner must allow them from the app");
  { Lock l; stopAll("stopped"); }
  const esp_partition_t *to = esp_ota_get_next_update_partition(nullptr);
  esp_ota_handle_t h;
  if (!to || esp_ota_begin(to, OTA_SIZE_UNKNOWN, &h) != ESP_OK) return fail(r, "could not start the update");
  event("update over Wi-Fi: %d bytes", (int)r->content_len);
  // The last 72 bytes may be the signature: they are held back until the end, everything before them is written.
  static uint8_t buf[4096 + 72];
  static uint8_t tail[72];
  int tailN = 0;
  mbedtls_sha256_context sha;
  mbedtls_sha256_init(&sha); mbedtls_sha256_starts(&sha, 0);
  int left = r->content_len;
  bool good = left > 100000;
  while (left > 0 && good) {
    memcpy(buf, tail, tailN);
    int n = httpd_req_recv(r, (char *)buf + tailN, min(left, 4096));
    if (n == HTTPD_SOCK_ERR_TIMEOUT) continue;
    if (n <= 0) { good = false; break; }
    left -= n;
    int have = tailN + n, out = have > 72 ? have - 72 : 0;
    if (out && esp_ota_write(h, buf, out) != ESP_OK) { good = false; break; }
    mbedtls_sha256_update(&sha, buf, out);
    tailN = have - out;
    memcpy(tail, buf + out, tailN);
  }
  bool signedFile = good && tailN == 72 && !memcmp(tail + 64, SIG_MAGIC, 8);
  if (good && !signedFile && tailN) {                // no signature: those last bytes are part of the image
    if (esp_ota_write(h, tail, tailN) != ESP_OK) good = false; else mbedtls_sha256_update(&sha, tail, tailN);
  }
  uint8_t hash[32];
  mbedtls_sha256_finish(&sha, hash); mbedtls_sha256_free(&sha);
  if (!good) { esp_ota_abort(h); return fail(r, "the upload broke off"); }
  if (signedFile && !fwSignatureOk(hash, tail)) { esp_ota_abort(h); event("update refused: bad signature"); return fail(r, "the file's signature is not valid"); }
  if (!signedFile && !pwOk) { esp_ota_abort(h); return fail(r, "this file is not signed"); }
  if (esp_ota_end(h) != ESP_OK || esp_ota_set_boot_partition(to) != ESP_OK) return fail(r, "the file was not accepted");
  event(signedFile ? "signed update accepted" : "update accepted (password)");
  statsSave();
  restartSoon = true;
  return ok(r);
}
