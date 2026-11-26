// The key exchange in Pairing, as pure functions both firmwares share: the controller (sec.h pairDo) and the Tilt Hub
// (tilt_hub/main/hub_pair.h pairDo). The phone's public key, the P-256 exchange, the key (deriveKey, tilt_link.h), the
// check, the 4-digit code and the answer JSON. Who may pair, the lock and the save stay with each device. No ESP-IDF
// and no shared state: test/pair_test.cpp runs it on the Mac with real mbedtls.
#pragma once
#include <string>
#include <mbedtls/base64.h>
#include <mbedtls/ecdh.h>
#include <mbedtls/ecp.h>
#include "tilt_crypto.h"                         // hexOf, hmac256
#include "tilt_link.h"                           // deriveKey

// The phone's public key from its base64 text ("pub" in the request). False unless it is exactly 65 bytes.
inline bool pairPub(const std::string &b64, uint8_t cpub[65]) {
  size_t n = 0;
  return mbedtls_base64_decode(cpub, 65, &n, (const uint8_t *)b64.data(), b64.size()) == 0 && n == 65;
}

// The device's public key, the phone's key, and the check (made from the key without the setup code).
struct PairKeys { uint8_t dpub[65], key[32], check[8]; };

// The part after the shared secret. key: deriveKey with the salt. check: the first 8 bytes of HMAC-SHA256("confirm")
// with the key made without the salt, so it never shows the setup code.
inline bool pairDerive(const uint8_t shared[32], const std::string &salt, const uint8_t cpub[65], const uint8_t dpub[65], PairKeys &out) {
  uint8_t plain[32], h[32];
  if (!deriveKey(shared, salt, cpub, dpub, out.key)) return false;
  if (salt.empty()) memcpy(plain, out.key, 32);
  else if (!deriveKey(shared, "", cpub, dpub, plain)) return false;
  if (!hmac256(plain, 32, (const uint8_t *)"confirm", 7, h)) return false;
  memcpy(out.dpub, dpub, 65);
  memcpy(out.check, h, 8);
  return true;
}

// The P-256 exchange with the phone's public key: a new key pair here, the shared secret, then pairDerive.
// False for a point that is not on the curve.
inline bool pairExchange(const uint8_t cpub[65], const std::string &salt, int (*rng)(void *, unsigned char *, size_t), PairKeys &out) {
  mbedtls_ecp_group grp; mbedtls_mpi d, z; mbedtls_ecp_point Q, Qp;
  mbedtls_ecp_group_init(&grp); mbedtls_mpi_init(&d); mbedtls_mpi_init(&z); mbedtls_ecp_point_init(&Q); mbedtls_ecp_point_init(&Qp);
  uint8_t dpub[65], shared[32];
  size_t dn = 0;
  bool ok = mbedtls_ecp_group_load(&grp, MBEDTLS_ECP_DP_SECP256R1) == 0 && mbedtls_ecdh_gen_public(&grp, &d, &Q, rng, nullptr) == 0 &&
            mbedtls_ecp_point_read_binary(&grp, &Qp, cpub, 65) == 0 && mbedtls_ecp_check_pubkey(&grp, &Qp) == 0 &&
            mbedtls_ecdh_compute_shared(&grp, &z, &Qp, &d, rng, nullptr) == 0 && mbedtls_mpi_write_binary(&z, shared, 32) == 0 &&
            mbedtls_ecp_point_write_binary(&grp, &Q, MBEDTLS_ECP_PF_UNCOMPRESSED, &dn, dpub, sizeof dpub) == 0 && dn == 65;
  mbedtls_ecp_group_free(&grp); mbedtls_mpi_free(&d); mbedtls_mpi_free(&z); mbedtls_ecp_point_free(&Q); mbedtls_ecp_point_free(&Qp);
  return ok && pairDerive(shared, salt, cpub, dpub, out);
}

// The 4 digits both phones show for a request to join, made from the key.
inline std::string askCode(const uint8_t key[32]) {
  uint8_t h[32]; char c[6];
  hmac256(key, 32, (const uint8_t *)"code", 4, h);
  snprintf(c, sizeof c, "%04u", (unsigned)(((h[0] << 8) | h[1]) % 10000));
  return c;
}

// The answer to the phone. code nullptr: no "code" field (the controller); otherwise it is written, also when empty
// (the hub).
inline std::string pairAnswer(const PairKeys &k, const uint8_t cid[8], bool owner, bool wait, const uint8_t topic[16], const char *code) {
  uint8_t pb[100];
  size_t pn = 0;
  mbedtls_base64_encode(pb, sizeof pb, &pn, k.dpub, 65);
  std::string out = std::string("{\"pub\":\"") + std::string((char *)pb, pn) + "\",\"cid\":\"" + hexOf(cid, 8) + "\",\"check\":\"" + hexOf(k.check, 8) +
                    "\",\"owner\":" + (owner ? "1" : "0") + ",\"wait\":" + (wait ? "1" : "0") + ",\"topic\":\"" + hexOf(topic, 16) + "\"";
  if (code) out += std::string(",\"code\":\"") + code + "\"";
  return out + "}";
}
