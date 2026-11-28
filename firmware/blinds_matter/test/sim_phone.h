// A test phone for both firmwares' tests on the host board (controller_test.cpp, tilt_hub/test/hub_board_test.cpp):
// its own P-256 key pair, the Pairing request body, its half of the key exchange from the device's answer, sealed
// commands and their answers opened, through the same shared code the devices use (tilt_pair.h, tilt_link.h), and the
// 4-digit code it shows for a Join request. Real mbedtls; no cJSON (the controller's test has none). Tests only.
#pragma once
#include <cstring>
#include <string>
#include <mbedtls/base64.h>
#include <mbedtls/ecdh.h>
#include <mbedtls/ecp.h>
#include "tilt_crypto.h"
#include "tilt_link.h"
#include "tilt_pair.h"

// The phones' own random source: a fixed sequence, so every run makes the same keys.
inline int simPhoneRng(void *, unsigned char *b, size_t n) {
  static uint32_t x = 12345;
  for (size_t i = 0; i < n; i++) { x = x * 1103515245u + 12345u; b[i] = (uint8_t)(x >> 16); }
  return 0;
}

struct SimPhone {
  uint8_t d[32], pub[65], key[32], cid[8];
  uint64_t ctr = 1000;                           // the counter of its last sealed command (the next one is higher)
  std::string check;                             // the check the phone works out (the device's must be the same)
  SimPhone() {
    mbedtls_ecp_group grp; mbedtls_mpi dm; mbedtls_ecp_point Q;
    mbedtls_ecp_group_init(&grp); mbedtls_mpi_init(&dm); mbedtls_ecp_point_init(&Q);
    size_t n = 0;
    mbedtls_ecp_group_load(&grp, MBEDTLS_ECP_DP_SECP256R1);
    mbedtls_ecdh_gen_public(&grp, &dm, &Q, simPhoneRng, nullptr);
    mbedtls_mpi_write_binary(&dm, d, 32);
    mbedtls_ecp_point_write_binary(&grp, &Q, MBEDTLS_ECP_PF_UNCOMPRESSED, &n, pub, sizeof pub);
    mbedtls_ecp_group_free(&grp); mbedtls_mpi_free(&dm); mbedtls_ecp_point_free(&Q);
    memset(key, 0, sizeof key); memset(cid, 0, sizeof cid);
  }
  // The request body: {"pub": base64, "name": ...} (name nullptr: none sent). Quotes and backslashes in the name escaped.
  std::string body(const char *name = "Ann's iPhone") const {
    uint8_t b64[100]; size_t n = 0;
    mbedtls_base64_encode(b64, sizeof b64, &n, pub, 65);
    std::string s = "{\"pub\":\"" + std::string((char *)b64, n) + "\"";
    if (name) {
      s += ",\"name\":\"";
      for (const char *c = name; *c; c++) { if (*c == '"' || *c == '\\') s += '\\'; s += *c; }
      s += "\"";
    }
    return s + "}";
  }
  // The phone's half, from the device's answer: the shared secret, then the key with `salt` (the setup code it typed,
  // the hub's first owner; else "").
  bool finish(const std::string &answer, const std::string &salt = "") {
    uint8_t dpub[65], shared[32];
    if (!pairPub(linkJsonStr(answer, "pub"), dpub) || !unhex(linkJsonStr(answer, "cid"), cid, 8)) return false;
    mbedtls_ecp_group grp; mbedtls_mpi dm, z; mbedtls_ecp_point P;
    mbedtls_ecp_group_init(&grp); mbedtls_mpi_init(&dm); mbedtls_mpi_init(&z); mbedtls_ecp_point_init(&P);
    bool ok = mbedtls_ecp_group_load(&grp, MBEDTLS_ECP_DP_SECP256R1) == 0 && mbedtls_mpi_read_binary(&dm, d, 32) == 0 &&
              mbedtls_ecp_point_read_binary(&grp, &P, dpub, 65) == 0 &&
              mbedtls_ecdh_compute_shared(&grp, &z, &P, &dm, simPhoneRng, nullptr) == 0 && mbedtls_mpi_write_binary(&z, shared, 32) == 0;
    mbedtls_ecp_group_free(&grp); mbedtls_mpi_free(&dm); mbedtls_mpi_free(&z); mbedtls_ecp_point_free(&P);
    PairKeys pk;
    if (!ok || !pairDerive(shared, salt, pub, dpub, pk)) return false;
    memcpy(key, pk.key, 32);
    check = hexOf(pk.check, 8);
    return true;
  }
  // A command sealed for the device's boot id, with the next counter.
  std::string seal(const std::string &cmd, const uint8_t boot[4]) { return frameSeal(key, cid, boot, ++ctr, cmd); }
  // The device's answer opened with this phone's key ("" if it does not open).
  std::string open(const std::string &frame, const std::string &reply) const {
    std::string out;
    return replyOpen(key, cid, (const uint8_t *)frame.data() + 8, reply, out) ? out : "";
  }
  std::string cidHex() const { return hexOf(cid, 8); }
  std::string code() const { return askCode(key); }   // the 4 digits it shows for a Join request
};
