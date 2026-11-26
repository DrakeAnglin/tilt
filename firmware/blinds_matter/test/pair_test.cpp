// Tests for main/tilt_pair.h (the key exchange in Pairing, shared by the controller and the Tilt Hub), run on the Mac
// with real mbedtls: tools/firmware_tests.sh. The vectors are test/wire/link.json (its path is the argument) and the
// app's own (app/Tilt/Tests/main.swift).
#include "../main/tilt_pair.h"
#include <cstdio>
#include <fstream>
#include <map>
#include <sstream>

static int passed = 0, failed = 0;
#define CHECK(cond, what) do { if (cond) passed++; else { failed++; printf("FAIL line %d: %s\n", __LINE__, what); } } while (0)

// A flat JSON object of strings (wire/link.json), with \" and \\ undone.
static std::map<std::string, std::string> readVectors(const char *path) {
  std::ifstream f(path);
  std::stringstream ss;
  ss << f.rdbuf();
  std::string j = ss.str();
  std::map<std::string, std::string> v;
  size_t i = 0;
  auto str = [&](std::string &out) {
    i = j.find('"', i);
    if (i == std::string::npos) return false;
    out.clear();
    for (i++; i < j.size() && j[i] != '"'; i++) {
      if (j[i] == '\\' && i + 1 < j.size()) { i++; out += j[i] == 'n' ? '\n' : j[i]; }
      else out += j[i];
    }
    i++;
    return i <= j.size();
  };
  std::string k, x;
  while (str(k) && str(x)) v[k] = x;
  return v;
}
static std::string bytes(const std::string &hex) {
  std::string b(hex.size() / 2, 0);
  if (!unhex(hex, (uint8_t *)&b[0], b.size())) return "";
  return b;
}
static const uint8_t *u8(const std::string &s) { return (const uint8_t *)s.data(); }
// A simple random source: counting bytes, so a run is the same every time.
static int counting(void *, unsigned char *b, size_t n) {
  static uint8_t c = 1;
  for (size_t i = 0; i < n; i++) b[i] = c++;
  return 0;
}

// The phone's side, made here: its own key pair, the shared secret with the device's key, deriveKey.
struct Phone {
  uint8_t pub[65];
  mbedtls_ecp_group grp; mbedtls_mpi d; mbedtls_ecp_point Q;
  Phone() {
    mbedtls_ecp_group_init(&grp); mbedtls_mpi_init(&d); mbedtls_ecp_point_init(&Q);
    size_t n = 0;
    mbedtls_ecp_group_load(&grp, MBEDTLS_ECP_DP_SECP256R1);
    mbedtls_ecdh_gen_public(&grp, &d, &Q, counting, nullptr);
    mbedtls_ecp_point_write_binary(&grp, &Q, MBEDTLS_ECP_PF_UNCOMPRESSED, &n, pub, sizeof pub);
  }
  ~Phone() { mbedtls_ecp_group_free(&grp); mbedtls_mpi_free(&d); mbedtls_ecp_point_free(&Q); }
  bool key(const uint8_t dpub[65], const std::string &salt, uint8_t out[32]) {
    mbedtls_ecp_point P; mbedtls_mpi z;
    mbedtls_ecp_point_init(&P); mbedtls_mpi_init(&z);
    uint8_t shared[32];
    bool ok = mbedtls_ecp_point_read_binary(&grp, &P, dpub, 65) == 0 && mbedtls_ecdh_compute_shared(&grp, &z, &P, &d, counting, nullptr) == 0 &&
              mbedtls_mpi_write_binary(&z, shared, 32) == 0 && deriveKey(shared, salt, pub, dpub, out);
    mbedtls_ecp_point_free(&P); mbedtls_mpi_free(&z);
    return ok;
  }
};

static void exchangeTests() {
  Phone phone;
  PairKeys k, ks;
  uint8_t mine[32], mineSalted[32], unsalted[32];
  CHECK(pairExchange(phone.pub, "", counting, k), "the exchange with a phone's key");
  CHECK(phone.key(k.dpub, "", mine) && !memcmp(mine, k.key, 32), "the phone and the device end with the same key");
  CHECK(pairExchange(phone.pub, "12345678", counting, ks), "the exchange with the setup code");
  CHECK(phone.key(ks.dpub, "12345678", mineSalted) && !memcmp(mineSalted, ks.key, 32), "with the setup code too, the same key");
  CHECK(phone.key(ks.dpub, "", unsalted) && memcmp(unsalted, ks.key, 32), "the setup code changes the key");
}

// After the shared secret, against wire/link.json (its cpub and dpub are not real points, so only this part can be).
static void deriveTests(std::map<std::string, std::string> &v) {
  std::string shared = bytes(v["shared"]), cpub = bytes(v["cpub"]), dpub = bytes(v["dpub"]), key = bytes(v["key"]), keySalted = bytes(v["keySalted"]);
  PairKeys k, ks;
  CHECK(pairDerive(u8(shared), "", u8(cpub), u8(dpub), k) && hexOf(k.key, 32) == v["key"], "the key with no salt");
  CHECK(!memcmp(k.dpub, u8(dpub), 65), "the device's public key is kept");
  CHECK(pairDerive(u8(shared), v["salt"], u8(cpub), u8(dpub), ks) && hexOf(ks.key, 32) == v["keySalted"], "the key with the setup code");
  uint8_t h[32], hs[32];
  hmac256(u8(key), 32, (const uint8_t *)"confirm", 7, h);
  hmac256(u8(keySalted), 32, (const uint8_t *)"confirm", 7, hs);
  CHECK(!memcmp(ks.check, h, 8), "the check is made from the key without the setup code");
  CHECK(memcmp(ks.check, hs, 8), "and not from the key with it");
  CHECK(!memcmp(k.check, h, 8), "with no salt, the same check");
}

static std::string b64(const uint8_t *b, size_t n) {
  uint8_t out[200];
  size_t on = 0;
  mbedtls_base64_encode(out, sizeof out, &on, b, n);
  return std::string((char *)out, on);
}
// What the phone sends is refused unless it is a public key: 65 bytes, and a point on the curve.
static void refuseTests(std::map<std::string, std::string> &v) {
  uint8_t raw[66], cpub[65];
  for (int i = 0; i < 66; i++) raw[i] = (uint8_t)(i + 1);
  CHECK(!pairPub(b64(raw, 64), cpub), "64 bytes are refused");
  CHECK(!pairPub(b64(raw, 66), cpub), "66 bytes are refused");
  CHECK(!pairPub("", cpub), "an empty text is refused");
  CHECK(!pairPub("not base64!", cpub), "text that is not base64 is refused");
  CHECK(pairPub(b64(raw, 65), cpub) && !memcmp(cpub, raw, 65), "65 bytes are taken");
  Phone phone;
  PairKeys k;
  uint8_t bad[65];
  memcpy(bad, phone.pub, 65);
  bad[64] ^= 1;
  CHECK(!pairExchange(bad, "", counting, k), "a good key with its last byte flipped is refused");
  std::string cpubV = bytes(v["cpub"]);
  CHECK(!pairExchange(u8(cpubV), "", counting, k), "link.json's cpub (not a point on the curve) is refused");
}

// The 4 digits and the check for key bytes 0..31: the same vectors as the app's test (app/Tilt/Tests/main.swift).
static void codeTests() {
  uint8_t key[32], h[32];
  for (int i = 0; i < 32; i++) key[i] = (uint8_t)i;
  CHECK(askCode(key) == "1585", "the 4-digit code matches the app's");
  hmac256(key, 32, (const uint8_t *)"confirm", 7, h);
  CHECK(hexOf(h, 8) == "ae667c53b3e30bd2", "the check matches the app's");
}

// The answer, as exact text: the controller (no "code") and the hub (always a "code", empty unless it is an ask).
static void answerTests() {
  PairKeys k;
  uint8_t cid[8], topic[16];
  k.dpub[0] = 4;
  for (int i = 1; i < 65; i++) k.dpub[i] = (uint8_t)i;
  for (int i = 0; i < 8; i++) { cid[i] = (uint8_t)(i + 1); k.check[i] = (uint8_t)(0xa0 + i); }
  for (int i = 0; i < 16; i++) topic[i] = (uint8_t)(0xf0 + i);
  const std::string head = "{\"pub\":\"BAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8gISIjJCUmJygpKissLS4vMDEyMzQ1Njc4OTo7PD0+P0A=\","
                           "\"cid\":\"0102030405060708\",\"check\":\"a0a1a2a3a4a5a6a7\",";
  const std::string topicHex = "f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff";
  CHECK(pairAnswer(k, cid, true, false, topic, nullptr) == head + "\"owner\":1,\"wait\":0,\"topic\":\"" + topicHex + "\"}", "the controller's first owner");
  CHECK(pairAnswer(k, cid, false, true, topic, nullptr) == head + "\"owner\":0,\"wait\":1,\"topic\":\"" + topicHex + "\"}", "the controller, an ask");
  CHECK(pairAnswer(k, cid, true, false, topic, "") == head + "\"owner\":1,\"wait\":0,\"topic\":\"" + topicHex + "\",\"code\":\"\"}", "the hub's first owner");
  CHECK(pairAnswer(k, cid, false, true, topic, "1585") == head + "\"owner\":0,\"wait\":1,\"topic\":\"" + topicHex + "\",\"code\":\"1585\"}", "the hub, an ask");
}

int main(int argc, char **argv) {
  if (argc < 2) { printf("usage: pair_test <path to wire/link.json>\n"); return 2; }
  std::map<std::string, std::string> v = readVectors(argv[1]);
  CHECK(!v["key"].empty(), "the vectors are read");
  exchangeTests();
  deriveTests(v);
  refuseTests(v);
  codeTests();
  answerTests();
  printf("pair_test: %d passed, %d failed\n", passed, failed);
  return failed ? 1 : 0;
}
