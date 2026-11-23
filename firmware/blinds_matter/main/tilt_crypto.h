// The small crypto and hex helpers the controller (sec.h) and the Tilt Hub (tilt_hub/main/hub.cpp) both use, in one
// place: a fix here reaches both. AES-256-GCM for sealed commands, HMAC-SHA256 for proofs and checks.
#pragma once
#include <string>
#include <cstdlib>
#include <mbedtls/gcm.h>
#include <mbedtls/md.h>

inline std::string hexOf(const uint8_t *b, int n) {
  static const char *H = "0123456789abcdef";
  std::string s;
  for (int i = 0; i < n; i++) { s += H[b[i] >> 4]; s += H[b[i] & 15]; }
  return s;
}
// Exactly n bytes from 2n hex digits; false on anything else.
inline bool unhex(const std::string &s, uint8_t *out, size_t n) {
  if (s.length() != n * 2) return false;
  for (size_t i = 0; i < n; i++) { char h[3] = {s[2 * i], s[2 * i + 1], 0}; char *e; out[i] = strtol(h, &e, 16); if (*e) return false; }
  return true;
}
inline bool hmac256(const uint8_t *key, size_t kn, const uint8_t *d, size_t dn, uint8_t out[32]) {
  return mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), key, kn, d, dn, out) == 0;
}
// enc: seal `in` into `out` and write the tag; else open `in` into `out` if `tag` checks out.
inline bool gcm(bool enc, const uint8_t key[32], const uint8_t nonce[12], const uint8_t *aad, size_t an, const uint8_t *in, size_t n, uint8_t *out, uint8_t tag[16]) {
  mbedtls_gcm_context g;
  mbedtls_gcm_init(&g);
  bool ok = mbedtls_gcm_setkey(&g, MBEDTLS_CIPHER_ID_AES, key, 256) == 0;
  if (ok) ok = enc ? mbedtls_gcm_crypt_and_tag(&g, MBEDTLS_GCM_ENCRYPT, n, nonce, 12, aad, an, in, out, 16, tag) == 0
                   : mbedtls_gcm_auth_decrypt(&g, n, nonce, 12, aad, an, tag, 16, in, out) == 0;
  mbedtls_gcm_free(&g);
  return ok;
}
