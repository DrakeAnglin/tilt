// Host stand-in for the mbedtls AES-256-GCM calls tilt_crypto.h makes (12-byte nonce, 16-byte tag). Tests only: see
// md.h. Slow and simple on purpose: a byte-wise AES and a bit-wise GHASH.
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>

typedef enum { MBEDTLS_CIPHER_ID_AES = 2 } mbedtls_cipher_id_t;
#define MBEDTLS_GCM_ENCRYPT 1
#define MBEDTLS_GCM_DECRYPT 0
typedef struct { uint8_t rk[240]; int ok; } mbedtls_gcm_context;

struct HostAes {
  static const uint8_t *sbox() {
    static uint8_t s[256];
    static bool made = false;
    if (made) return s;
    uint8_t p = 1, q = 1;                       // p walks the field by 3, q by its inverse (1/3)
    do {
      p = p ^ (uint8_t)(p << 1) ^ (p & 0x80 ? 0x1B : 0);
      q ^= q << 1; q ^= q << 2; q ^= q << 4; if (q & 0x80) q ^= 0x09;
      uint8_t x = q ^ (uint8_t)(q << 1 | q >> 7) ^ (uint8_t)(q << 2 | q >> 6) ^ (uint8_t)(q << 3 | q >> 5) ^ (uint8_t)(q << 4 | q >> 4);
      s[p] = x ^ 0x63;
    } while (p != 1);
    s[0] = 0x63;
    made = true;
    return s;
  }
  static uint8_t xt(uint8_t x) { return (uint8_t)(x << 1) ^ (x & 0x80 ? 0x1B : 0); }
  static void expand(const uint8_t key[32], uint8_t rk[240]) {
    const uint8_t *s = sbox();
    memcpy(rk, key, 32);
    uint8_t rc = 1;
    for (int i = 8; i < 60; i++) {
      uint8_t t[4];
      memcpy(t, rk + 4 * (i - 1), 4);
      if (i % 8 == 0) { uint8_t a = t[0]; t[0] = s[t[1]] ^ rc; t[1] = s[t[2]]; t[2] = s[t[3]]; t[3] = s[a]; rc = xt(rc); }
      else if (i % 8 == 4) for (auto &b : t) b = s[b];
      for (int j = 0; j < 4; j++) rk[4 * i + j] = rk[4 * (i - 8) + j] ^ t[j];
    }
  }
  static void block(const uint8_t rk[240], const uint8_t in[16], uint8_t out[16]) {
    const uint8_t *s = sbox();
    uint8_t st[16];
    for (int i = 0; i < 16; i++) st[i] = in[i] ^ rk[i];
    for (int r = 1; r <= 14; r++) {
      uint8_t t[16];
      for (int c = 0; c < 4; c++) for (int row = 0; row < 4; row++) t[4 * c + row] = s[st[4 * ((c + row) % 4) + row]];   // sub bytes, shift rows
      if (r < 14) for (int c = 0; c < 4; c++) {                                                                       // mix columns
        uint8_t *a = t + 4 * c, a0 = a[0], a1 = a[1], a2 = a[2], a3 = a[3], all = a0 ^ a1 ^ a2 ^ a3;
        a[0] ^= all ^ xt(a0 ^ a1); a[1] ^= all ^ xt(a1 ^ a2); a[2] ^= all ^ xt(a2 ^ a3); a[3] ^= all ^ xt(a3 ^ a0);
      }
      for (int i = 0; i < 16; i++) st[i] = t[i] ^ rk[16 * r + i];
    }
    memcpy(out, st, 16);
  }
};
struct HostGhash {
  uint8_t h[16], y[16] = {0};
  static void mul(uint8_t x[16], const uint8_t hh[16]) {
    uint8_t z[16] = {0}, v[16];
    memcpy(v, hh, 16);
    for (int i = 0; i < 128; i++) {
      if (x[i / 8] & (0x80 >> (i % 8))) for (int j = 0; j < 16; j++) z[j] ^= v[j];
      bool lsb = v[15] & 1;
      for (int j = 15; j > 0; j--) v[j] = (uint8_t)(v[j] >> 1 | v[j - 1] << 7);
      v[0] >>= 1;
      if (lsb) v[0] ^= 0xE1;
    }
    memcpy(x, z, 16);
  }
  void add(const uint8_t *p, size_t n) {          // padded with zeros to a whole block
    for (size_t i = 0; i < n; i += 16) {
      for (size_t j = 0; j < 16 && i + j < n; j++) y[j] ^= p[i + j];
      mul(y, h);
    }
  }
};
inline void hostGcm(const uint8_t rk[240], const uint8_t iv[12], const uint8_t *aad, size_t an, const uint8_t *ct, size_t n,
                    const uint8_t *in, uint8_t *out, uint8_t tag[16]) {
  // ct: the ciphertext the tag covers (out when sealing, in when opening)
  HostGhash g;
  uint8_t zero[16] = {0}, j0[16], ctr[16], ks[16];
  HostAes::block(rk, zero, g.h);
  memcpy(j0, iv, 12); j0[12] = 0; j0[13] = 0; j0[14] = 0; j0[15] = 1;
  memcpy(ctr, j0, 16);
  for (size_t i = 0; i < n; i += 16) {
    for (int k = 15; k >= 12 && !++ctr[k]; k--) {}
    HostAes::block(rk, ctr, ks);
    for (size_t j = 0; j < 16 && i + j < n; j++) out[i + j] = in[i + j] ^ ks[j];
  }
  g.add(aad, an);
  g.add(ct, n);
  uint8_t len[16];
  uint64_t ab = (uint64_t)an * 8, cb = (uint64_t)n * 8;
  for (int i = 0; i < 8; i++) { len[i] = (uint8_t)(ab >> (56 - 8 * i)); len[8 + i] = (uint8_t)(cb >> (56 - 8 * i)); }
  g.add(len, 16);
  HostAes::block(rk, j0, ks);
  for (int i = 0; i < 16; i++) tag[i] = g.y[i] ^ ks[i];
}

inline void mbedtls_gcm_init(mbedtls_gcm_context *g) { memset(g, 0, sizeof *g); }
inline void mbedtls_gcm_free(mbedtls_gcm_context *g) { memset(g, 0, sizeof *g); }
inline int mbedtls_gcm_setkey(mbedtls_gcm_context *g, mbedtls_cipher_id_t id, const unsigned char *key, unsigned bits) {
  if (id != MBEDTLS_CIPHER_ID_AES || bits != 256) return -1;
  HostAes::expand(key, g->rk);
  g->ok = 1;
  return 0;
}
inline int mbedtls_gcm_crypt_and_tag(mbedtls_gcm_context *g, int mode, size_t n, const unsigned char *iv, size_t ivn, const unsigned char *aad,
                                     size_t an, const unsigned char *in, unsigned char *out, size_t tn, unsigned char *tag) {
  if (!g->ok || mode != MBEDTLS_GCM_ENCRYPT || ivn != 12 || tn != 16) return -1;
  hostGcm(g->rk, iv, aad, an, out, n, in, out, tag);
  return 0;
}
inline int mbedtls_gcm_auth_decrypt(mbedtls_gcm_context *g, size_t n, const unsigned char *iv, size_t ivn, const unsigned char *aad, size_t an,
                                    const unsigned char *tag, size_t tn, const unsigned char *in, unsigned char *out) {
  if (!g->ok || ivn != 12 || tn != 16) return -1;
  uint8_t want[16];
  hostGcm(g->rk, iv, aad, an, in, n, in, out, want);
  uint8_t d = 0;
  for (int i = 0; i < 16; i++) d |= want[i] ^ tag[i];
  if (d) { memset(out, 0, n); return -0x12; }
  return 0;
}
