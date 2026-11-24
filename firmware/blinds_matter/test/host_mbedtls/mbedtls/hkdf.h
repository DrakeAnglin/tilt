// Host stand-in for mbedtls_hkdf (RFC 5869, SHA-256 only). Tests only: see md.h.
#pragma once
#include "md.h"

inline int mbedtls_hkdf(const mbedtls_md_info_t *md, const unsigned char *salt, size_t sn, const unsigned char *ikm, size_t in,
                        const unsigned char *info, size_t fn, unsigned char *okm, size_t on) {
  if (!md || md->type != MBEDTLS_MD_SHA256 || on > 255 * 32) return -1;
  uint8_t zero[32] = {0}, prk[32], t[32];
  if (!salt || !sn) { salt = zero; sn = 32; }
  if (mbedtls_md_hmac(md, salt, sn, ikm, in, prk)) return -1;
  size_t done = 0, tn = 0;
  uint8_t buf[32 + 256 + 1];
  if (fn > 256) return -1;
  for (uint8_t i = 1; done < on; i++) {
    memcpy(buf, t, tn);
    memcpy(buf + tn, info, fn);
    buf[tn + fn] = i;
    if (mbedtls_md_hmac(md, prk, 32, buf, tn + fn + 1, t)) return -1;
    tn = 32;
    size_t k = on - done < 32 ? on - done : 32;
    memcpy(okm + done, t, k);
    done += k;
  }
  return 0;
}
