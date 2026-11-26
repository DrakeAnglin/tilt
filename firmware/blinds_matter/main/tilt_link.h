// The link between the Tilt Hub and a controller, as pure functions both firmwares share (the hub, tilt_hub/main/hub_ctrl.h,
// and the controller, hub_link.h and sec.h): the link key and its proofs, the push anti-replay rule, the datagram
// types and layouts, the status codes, and the sealed frame the app, the hub and the controller all speak. No ESP-IDF
// and no shared state: test/link_test.cpp runs it on the Mac, against test/wire/link.json, which the app's tests and
// tools/test_tools.py check too. Change a layout here and every side sees it.
#pragma once
#include <cctype>
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <mbedtls/hkdf.h>
#include "tilt_crypto.h"                         // hexOf, unhex, hmac256, gcm

// The link's version, in the hello and the hub's /api/info. 1: this layout. A peer that does not say is older (0).
const int LINK_PROTO = 1;

// ---- datagrams (UDP port 49100 over Thread; the layouts are in hub_link.h's header)
enum Dg : char {
  DG_HELLO = 'H', DG_COMMAND = 'X', DG_ASK = 'A', DG_PAIR = 'P',      // hub -> controller, answered in lower case
  DG_RECOVER = 'R', DG_RECOVER_STATE = 'Q',                           //   getting back in with no owner left (people.h)
  DG_BEGIN = 'B', DG_PIECE = 'W', DG_END = 'E',                       //   a firmware file: begin, pieces, end
  DG_TIME = 's',                                                      // hub -> controller: the answer to a push
  DG_PUSH = 'S', DG_LOG = 'L', DG_BYE = 'G',                          // controller -> hub, seq "00"
  DG_PIECES = '#',                                                    // controller -> hub: one piece of a long answer
};
inline char dgReply(char type) { return (char)tolower((unsigned char)type); }
// type (1) | seq (2, big-endian) | payload
inline std::string dgEncode(char type, uint16_t seq, const std::string &payload) {
  std::string m(1, type);
  m += (char)(seq >> 8); m += (char)(seq & 0xFF);
  return m + payload;
}
struct Datagram { char type; uint16_t seq; std::string payload; };
inline bool dgParse(const char *b, size_t n, Datagram &d) {
  if (n < 3) return false;
  d.type = b[0];
  d.seq = (uint16_t)((uint8_t)b[1] << 8 | (uint8_t)b[2]);
  d.payload.assign(b + 3, n - 3);
  return true;
}
// An answer's payload: status (3 digits) | answer. The status, or 0 when it does not start with 3 digits.
inline int dgStatus(const std::string &payload, std::string &ans) {
  if (payload.size() < 3 || !isdigit((unsigned char)payload[0]) || !isdigit((unsigned char)payload[1]) || !isdigit((unsigned char)payload[2])) return 0;
  ans = payload.substr(3);
  return atoi(payload.substr(0, 3).c_str());
}
inline std::string dgAnswer(int status, const std::string &ans) {
  char st[4];
  snprintf(st, sizeof st, "%03d", status % 1000);
  return st + ans;
}

// ---- long answers: '#' | seq | piece (1) | count (1) | part, in up to 16 pieces
const size_t LINK_PIECE = 1000;
const int LINK_PIECES_MAX = 16;
// The datagrams for one answer body (status and answer): one plain answer when it fits, else pieces. Empty when it
// would take more than LINK_PIECES_MAX pieces.
inline std::vector<std::string> dgAnswerDatagrams(char type, uint16_t seq, const std::string &body, size_t piece = LINK_PIECE) {
  std::vector<std::string> out;
  if (body.size() <= piece) { out.push_back(dgEncode(dgReply(type), seq, body)); return out; }
  size_t count = (body.size() + piece - 1) / piece;
  if (count > (size_t)LINK_PIECES_MAX) return out;
  for (size_t i = 0; i < count; i++) out.push_back(dgEncode(DG_PIECES, seq, std::string(1, (char)i) + (char)count + body.substr(i * piece, piece)));
  return out;
}
// Joins the pieces of one answer, in any order.
struct PieceJoin {
  uint8_t count = 0;
  uint16_t have = 0;
  std::string part[LINK_PIECES_MAX];
  void reset() { count = 0; have = 0; for (auto &p : part) p.clear(); }
  enum Got { BAD, MORE, DONE };
  // payload: piece | count | part. DONE: `joined` is the whole answer (status and answer) and the join is reset.
  Got add(const std::string &payload, std::string &joined) {
    if (payload.size() < 3) return BAD;
    int i = (uint8_t)payload[0], n = (uint8_t)payload[1];
    if (n < 2 || n > LINK_PIECES_MAX || i >= n || (count && count != n)) return BAD;
    count = (uint8_t)n;
    part[i] = payload.substr(2);
    have |= 1 << i;
    if (have != (1 << n) - 1) return MORE;
    joined.clear();
    for (int k = 0; k < n; k++) joined += part[k];
    reset();
    return DONE;
  }
};

// ---- status codes: the one table for the link, the hub's HTTP answers and the app
inline const char *statusLine(int st) {
  switch (st) {
    case 200: return "200 OK";
    case 400: return "400 Bad Request";
    case 401: return "401 Unauthorized";          // not paired, or a bad key: the key is gone
    case 403: return "403 Forbidden";             // not allowed (or "waiting": a request to join an owner has not let in)
    case 409: return "409 Conflict";              // stale: the controller restarted (new boot id), say hello again
    case 410: return "410 Gone";
    case 429: return "429 Too Many Requests";
    case 500: return "500 Internal Server Error";
    default: return "504 Gateway Timeout";        // 0: no answer
  }
}

// ---- proofs: the link key and the four labels
// The link key: HMAC-SHA256 of the hub's own key on the controller, over "tilt-hub-link".
inline bool linkKey(const uint8_t hubKey[32], uint8_t link[32]) { return hmac256(hubKey, 32, (const uint8_t *)"tilt-hub-link", 13, link); }
enum class Proof { CtlPush, CtlBye, HubTime, HubOta };
inline const char *proofLabel(Proof p) {
  switch (p) {
    case Proof::CtlPush: return "ctl-push";      // controller -> hub: a status push (msg: the JSON, then its count)
    case Proof::CtlBye: return "ctl-bye";        // controller -> hub: leaving (msg: empty)
    case Proof::HubTime: return "hub-time";      // hub -> controller: the time (msg: epoch seconds)
    case Proof::HubOta: return "hub-ota";        // hub -> controller: begin a firmware file (msg: size[,d]@epoch)
  }
  return "";
}
// What a proof covers: label | the controller's boot id (4) | msg.
inline std::string proofText(Proof p, const uint8_t boot[4], const std::string &msg) { return proofLabel(p) + std::string((const char *)boot, 4) + msg; }
// The proof: the first 16 bytes of HMAC-SHA256 with the link key over proofText, in hex.
inline std::string proofOfText(const uint8_t link[32], const std::string &text) {
  uint8_t m[32];
  if (!hmac256(link, 32, (const uint8_t *)text.data(), text.size(), m)) return "";
  return hexOf(m, 16);
}
inline std::string proof(const uint8_t link[32], Proof p, const uint8_t boot[4], const std::string &msg) { return proofOfText(link, proofText(p, boot, msg)); }
inline bool sameText(const std::string &a, const std::string &b) {   // in constant time (for proofs)
  if (a.empty() || a.size() != b.size()) return false;
  uint8_t d = 0;
  for (size_t i = 0; i < a.size(); i++) d |= a[i] ^ b[i];
  return d == 0;
}
inline bool proofOk(const uint8_t link[32], Proof p, const uint8_t boot[4], const std::string &msg, const std::string &mac) {
  return sameText(proof(link, p, boot, msg), mac);
}

// ---- pushes: 'S' "00" JSON, then (once the controller knows the hub's key) "\n" count "." proof
inline std::string pushPayload(const std::string &json, uint32_t n, const std::string &mac) {
  return mac.empty() ? json : json + "\n" + std::to_string(n) + "." + mac;
}
struct PushIn { std::string json; uint32_t n = 0; std::string mac; };   // n 0: no proof
inline PushIn pushParse(const std::string &payload) {
  PushIn p;
  size_t nl = payload.find('\n');
  p.json = payload.substr(0, nl);
  if (nl == std::string::npos) return p;
  std::string tail = payload.substr(nl + 1);
  size_t dot = tail.find('.');
  if (dot == std::string::npos) return p;
  p.n = (uint32_t)strtoul(tail.c_str(), nullptr, 10);
  p.mac = tail.substr(dot + 1);
  return p;
}
// What the hub keeps per controller to refuse an old push: `on` and `bn` are in flash, `boot` and `n` for this start.
struct PushState {
  bool on = false;                               // it has sent a proven push: from then on only proven ones count
  uint32_t bn = 0;                               // the boot count of the newest proven push (an older boot's is never taken)
  std::string boot;                              // the boot id (hex) of its last push taken
  uint32_t n = 0;                                // the count on its last proven push taken
};
enum class PushVerdict { Take, TakeUnproven, Refuse };
struct PushResult { PushVerdict verdict; PushState state; bool save; };   // save: `on` or `bn` changed (write flash)
// The anti-replay rule, for a controller that has let the hub in: a proven push is taken when its boot count is newer,
// or the same boot count with another boot id, or the same boot with a higher count. Before the first proven push
// one without a proof is taken (it has not been told which key is the hub's); after it, never.
inline PushResult pushAccept(const PushState &s, bool proven, uint32_t bn, const std::string &boot, uint32_t n) {
  PushResult r{PushVerdict::Refuse, s, false};
  bool fresh = bn > s.bn || (bn == s.bn && (boot != s.boot || n > s.n));
  if (proven && fresh) {
    r.verdict = PushVerdict::Take;
    r.state.n = n;
    r.state.boot = boot;
    if (!s.on || bn != s.bn) { r.state.on = true; r.state.bn = bn; r.save = true; }
  } else if (!s.on && !proven) {
    r.verdict = PushVerdict::TakeUnproven;
    r.state.boot = boot;
  }
  return r;
}

// ---- the sealed frame (sec.h secDo, the hub's own /hub/x, Secure.swift Frame, tools/blinds_client.py)
//   command: client id (8) | nonce = boot id (4) + counter (8, big-endian) | AES-256-GCM ciphertext | tag (16),
//            authenticated with "blinds-v1" + client id
//   reply:   nonce (12) | ciphertext | tag (16), authenticated with "blinds-v1r" + client id + the command's nonce
// The pairing key: HKDF-SHA256 of the ECDH secret, salt (the hub's setup code for its first owner, else none), info
// "blinds-v1" + the phone's public key (65) + the device's (65).
inline bool deriveKey(const uint8_t shared[32], const std::string &salt, const uint8_t cpub[65], const uint8_t dpub[65], uint8_t key[32]) {
  uint8_t info[9 + 130];
  memcpy(info, "blinds-v1", 9); memcpy(info + 9, cpub, 65); memcpy(info + 74, dpub, 65);
  return mbedtls_hkdf(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), (const uint8_t *)salt.data(), salt.size(), shared, 32, info, sizeof info, key, 32) == 0;
}
const size_t FRAME_MIN = 8 + 12 + 16 + 1;
// "" when sealing failed.
inline std::string frameSeal(const uint8_t key[32], const uint8_t cid[8], const uint8_t boot[4], uint64_t ctr, const std::string &cmd) {
  std::string pkt(20 + cmd.size() + 16, 0);
  uint8_t *p = (uint8_t *)&pkt[0], aad[17];
  memcpy(p, cid, 8);
  memcpy(p + 8, boot, 4);
  for (int i = 0; i < 8; i++) p[12 + i] = (uint8_t)(ctr >> (56 - 8 * i));
  memcpy(aad, "blinds-v1", 9); memcpy(aad + 9, cid, 8);
  if (!gcm(true, key, p + 8, aad, 17, (const uint8_t *)cmd.data(), cmd.size(), p + 20, p + 20 + cmd.size())) return "";
  return pkt;
}
enum class FrameErr { Ok, Short, NotPaired, Stale, BadKey };
struct Frame { const uint8_t *cid, *nonce, *ct; size_t n; uint64_t ctr; };   // points into the packet
inline bool frameSplit(const std::string &b, Frame &f) {
  if (b.size() < FRAME_MIN) return false;
  const uint8_t *p = (const uint8_t *)b.data();
  f.cid = p; f.nonce = p + 8; f.ct = p + 20; f.n = b.size() - 36; f.ctr = 0;
  for (int i = 4; i < 12; i++) f.ctr = (f.ctr << 8) | f.nonce[i];
  return true;
}
// Opens a command. `find(frame, key)` looks up the client id: Ok with its key copied out, NotPaired, or Stale (the
// boot id or counter is old). It runs before anything is decrypted.
template <class Find> FrameErr frameOpen(const std::string &b, Find find, Frame &f, std::string &cmd) {
  if (!frameSplit(b, f)) return FrameErr::Short;
  uint8_t key[32];
  FrameErr e = find(f, key);
  if (e != FrameErr::Ok) return e;
  uint8_t aad[17];
  memcpy(aad, "blinds-v1", 9); memcpy(aad + 9, f.cid, 8);
  cmd.assign(f.n, 0);
  if (!gcm(false, key, f.nonce, aad, 17, f.ct, f.n, (uint8_t *)&cmd[0], (uint8_t *)(f.ct + f.n))) { cmd.clear(); return FrameErr::BadKey; }
  return FrameErr::Ok;
}
// The reply to the command with this client id and nonce. `rnd`: its own 12 random bytes. "" when sealing failed.
inline std::string replySeal(const uint8_t key[32], const uint8_t cid[8], const uint8_t nonce[12], const uint8_t rnd[12], const std::string &out) {
  std::string r(12 + out.size() + 16, 0);
  uint8_t *o = (uint8_t *)&r[0], aad[30];
  memcpy(o, rnd, 12);
  memcpy(aad, "blinds-v1r", 10); memcpy(aad + 10, cid, 8); memcpy(aad + 18, nonce, 12);
  if (!gcm(true, key, o, aad, 30, (const uint8_t *)out.data(), out.size(), o + 12, o + 12 + out.size())) return "";
  return r;
}
inline bool replyOpen(const uint8_t key[32], const uint8_t cid[8], const uint8_t nonce[12], const std::string &reply, std::string &out) {
  if (reply.size() < 28) return false;
  const uint8_t *a = (const uint8_t *)reply.data();
  uint8_t aad[30];
  memcpy(aad, "blinds-v1r", 10); memcpy(aad + 10, cid, 8); memcpy(aad + 18, nonce, 12);
  out.assign(reply.size() - 28, 0);
  if (!gcm(false, key, a, aad, 30, a + 12, out.size(), (uint8_t *)&out[0], (uint8_t *)(a + 12 + out.size()))) { out.clear(); return false; }
  return true;
}

// ---- the string value of a top-level key of a JSON object (the hello's "boot"): "" when it is not there or not a
// string. It walks the object key by key, so the same text in a value (a controller named "boot") or inside a nested
// object never counts.
inline bool linkJsonReadStr(const std::string &j, size_t &i, std::string &out) {   // j[i] is the opening quote
  out.clear();
  for (i++; i < j.size(); i++) {
    if (j[i] == '"') { i++; return true; }
    if (j[i] == '\\' && i + 1 < j.size()) i++;
    out += j[i];
  }
  return false;
}
inline void linkJsonSkipWs(const std::string &j, size_t &i) { while (i < j.size() && isspace((unsigned char)j[i])) i++; }
inline std::string linkJsonStr(const std::string &j, const char *key) {
  size_t i = 0;
  linkJsonSkipWs(j, i);
  if (i >= j.size() || j[i] != '{') return "";
  i++;
  for (;;) {
    linkJsonSkipWs(j, i);
    std::string k, v;
    if (i >= j.size() || j[i] != '"' || !linkJsonReadStr(j, i, k)) return "";
    linkJsonSkipWs(j, i);
    if (i >= j.size() || j[i] != ':') return "";
    i++;
    linkJsonSkipWs(j, i);
    if (i >= j.size()) return "";
    if (j[i] == '"') {
      if (!linkJsonReadStr(j, i, v)) return "";
      if (k == key) return v;
    } else {                                     // a number, true/false/null, or a nested object or list: skip it
      if (k == key) return "";
      int depth = 0;
      for (; i < j.size(); i++) {
        char ch = j[i];
        if (ch == '"') { std::string skip; if (!linkJsonReadStr(j, i, skip)) return ""; i--; continue; }
        if (ch == '{' || ch == '[') depth++;
        else if (ch == '}' || ch == ']') { if (!depth) break; depth--; }
        else if (ch == ',' && !depth) break;
      }
    }
    linkJsonSkipWs(j, i);
    if (i >= j.size() || j[i] != ',') return "";
    i++;
  }
}
