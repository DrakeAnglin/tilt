// The Tilt Hub's checks on an update file: signed with the Tilt release key, the right kind, and not older. They read
// the file through a ByteReader, so the same checks run on the flash partition (hub_update.h) and on a file in memory (the
// Mac tests: firmware/tilt_hub/test/hub_test.cpp). The file format is made by tools/release_firmware.py:
//   full file   image | signature (64: r | s) | "TILTSIG1"
//   patch       header (starts 10 de cd fc) | patch | new image's signature | signature (64) | "TILTDLT1"
// The signature covers everything before it: ECDSA P-256 over its SHA-256.
#pragma once
#include <cstdint>
#include <cstring>
#include <mbedtls/sha256.h>
#include <mbedtls/ecdsa.h>
#include "logic.h"                               // fwIsOlder

struct ByteReader { virtual void read(uint32_t off, void *buf, uint32_t n) = 0; virtual ~ByteReader() {} };
// A file in memory. Past its end it reads zeros (a partition reads what flash holds there).
struct MemReader : ByteReader {
  const uint8_t *p; uint32_t size;
  MemReader(const void *data, uint32_t n) : p((const uint8_t *)data), size(n) {}
  void read(uint32_t off, void *buf, uint32_t n) override {
    uint8_t *o = (uint8_t *)buf;
    for (uint32_t i = 0; i < n; i++) o[i] = off + i < size ? p[off + i] : 0;
  }
};

static const char SIG_MAGIC[8] = {'T', 'I', 'L', 'T', 'S', 'I', 'G', '1'}, DLT_MAGIC[8] = {'T', 'I', 'L', 'T', 'D', 'L', 'T', '1'};

// The file's last 72 bytes: signature (64) and magic (8). Signed with the key pub (65 bytes, uncompressed) over
// everything before the signature.
inline bool checkSignedFile(ByteReader &rd, uint32_t size, const char magic[8], const uint8_t pub[65]) {
  if (size < 1000) return false;
  uint8_t tail[72], hash[32];
  rd.read(size - 72, tail, 72);
  if (memcmp(tail + 64, magic, 8)) return false;
  mbedtls_sha256_context sh;
  mbedtls_sha256_init(&sh); mbedtls_sha256_starts(&sh, 0);
  static uint8_t buf[4096];
  for (uint32_t o = 0, end = size - 72; o < end;) {
    uint32_t n = end - o < sizeof buf ? end - o : sizeof buf;
    rd.read(o, buf, n);
    mbedtls_sha256_update(&sh, buf, n);
    o += n;
  }
  mbedtls_sha256_finish(&sh, hash); mbedtls_sha256_free(&sh);
  mbedtls_ecp_group grp; mbedtls_ecp_point q; mbedtls_mpi r, sv;
  mbedtls_ecp_group_init(&grp); mbedtls_ecp_point_init(&q); mbedtls_mpi_init(&r); mbedtls_mpi_init(&sv);
  bool ok = mbedtls_ecp_group_load(&grp, MBEDTLS_ECP_DP_SECP256R1) == 0 && mbedtls_ecp_point_read_binary(&grp, &q, pub, 65) == 0 &&
            mbedtls_mpi_read_binary(&r, tail, 32) == 0 && mbedtls_mpi_read_binary(&sv, tail + 32, 32) == 0 && mbedtls_ecdsa_verify(&grp, hash, 32, &q, &r, &sv) == 0;
  mbedtls_ecp_group_free(&grp); mbedtls_ecp_point_free(&q); mbedtls_mpi_free(&r); mbedtls_mpi_free(&sv);
  return ok;
}

// The parts of an image's app description (esp_app_desc_t) the checks read. It sits after the image header (24 bytes)
// and the first segment header (8): magic word at +0, version at +16, project name at +48 (hub_update.h checks these
// offsets against ESP-IDF's struct).
const uint32_t APP_DESC_AT = 32, APP_DESC_MAGIC = 0xABCD5432;
struct AppDesc { bool ok; char version[32]; char project[32]; };
inline AppDesc appDescOf(ByteReader &rd) {
  uint8_t d[80];
  rd.read(APP_DESC_AT, d, sizeof d);
  AppDesc a;
  a.ok = (d[0] | d[1] << 8 | d[2] << 16 | (uint32_t)d[3] << 24) == APP_DESC_MAGIC;
  memcpy(a.version, d + 16, 32); a.version[31] = 0;
  memcpy(a.project, d + 48, 32);
  return a;
}
inline bool isPatch(ByteReader &rd) {
  uint8_t head[4];
  rd.read(0, head, 4);
  return head[0] == 0x10 && head[1] == 0xde && head[2] == 0xcd && head[3] == 0xfc;
}

// A file for a controller, in the hub's staging area: signed, and (a full file) not older than runningFw, what the
// controller runs ("" if not known). A patch is signed as a file too; the controller checks the image it makes and its
// version. delta: it is a patch. nullptr: good. Otherwise why not.
inline const char *stageCheck(ByteReader &rd, uint32_t size, const char *runningFw, const uint8_t pub[65], bool &delta) {
  if (size < 1000) return "that is not a firmware file";
  delta = isPatch(rd);
  if (!checkSignedFile(rd, size, delta ? DLT_MAGIC : SIG_MAGIC, pub)) return "the file's signature is not valid";
  if (delta) return nullptr;
  AppDesc d = appDescOf(rd);
  if (!d.ok) return "that is not a firmware file";
  if (runningFw[0] && fwIsOlder(d.version, runningFw)) return "that firmware is older than the one it runs";
  return nullptr;
}

// The hub's own firmware (POST /hub/api/update), once stored: signed, a hub image, not older than runningFw.
// 0: good (version: the new one). Otherwise the HTTP status, and err why not.
inline int hubFileCheck(ByteReader &rd, uint32_t size, const char *runningFw, const uint8_t pub[65], const char *&err, char version[32]) {
  if (!checkSignedFile(rd, size, SIG_MAGIC, pub)) { err = "the file's signature is not valid"; return 403; }
  AppDesc d = appDescOf(rd);
  memcpy(version, d.version, 32);
  if (!d.ok || strncmp(d.project, "tilt_hub", sizeof d.project)) { err = "that is not a hub firmware file"; return 400; }
  if (fwIsOlder(d.version, runningFw)) { err = "that firmware is older than the one the hub runs"; return 403; }
  return 0;
}
