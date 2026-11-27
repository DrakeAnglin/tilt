// What the Tilt Hub adds to the host board (firmware/blinds_matter/test/host_esp/host_board.h): the headers in this
// folder are the SDK ones only the hub includes (esp_random.h, esp_mac.h, lwip/sockets.h), and their state is here.
// This folder comes first on the include path of firmware/tilt_hub/test/hub_board_test.cpp. Tests only.
//
// What a test can do (namespace hubhost):
//   random bytes   by default a counted stream (never the same bytes twice, also across restarts); queueRandom puts
//                  the exact bytes the next esp_fill_random calls give (a test vector's), then the stream goes on
//   the MAC        setMac: what esp_read_mac gives (a restart puts back the default 02:00:00:00:00:01)
//   restart        host::restart() clears the queued bytes and puts back the MAC
#pragma once
#include <cstdint>
#include <cstring>
#include <deque>
#include <vector>
#include "host_board.h"

namespace hubhost {

struct HubBoard {
  uint64_t counted = 0;                                // bytes of the stream given so far
  std::deque<uint8_t> queued;                          // given first, in order
  uint8_t mac[6] = {0x02, 0, 0, 0, 0, 0x01};
};
inline HubBoard &hubBoard() { static HubBoard b; return b; }

inline void queueRandom(const std::vector<uint8_t> &bytes) { for (uint8_t b : bytes) hubBoard().queued.push_back(b); }
inline size_t randomQueued() { return hubBoard().queued.size(); }
inline void setMac(const uint8_t m[6]) { memcpy(hubBoard().mac, m, 6); }

// One byte of the stream: a mix of its count (splitmix64), so the bytes look random but repeat from run to run.
inline uint8_t streamByte() {
  uint64_t z = ++hubBoard().counted * 0x9e3779b97f4a7c15ULL;
  z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
  z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
  return (uint8_t)((z ^ (z >> 31)) >> 56);
}
inline void fillRandom(void *p, size_t n) {
  uint8_t *b = (uint8_t *)p;
  for (size_t i = 0; i < n; i++) {
    if (!hubBoard().queued.empty()) { b[i] = hubBoard().queued.front(); hubBoard().queued.pop_front(); }
    else b[i] = streamByte();
  }
}

inline void hubRestart() {
  HubBoard &b = hubBoard();
  b.queued.clear();
  const uint8_t def[6] = {0x02, 0, 0, 0, 0, 0x01};
  memcpy(b.mac, def, 6);
}
// Put back by the shared board's restart(), before the test program's own hook (this one is added first).
inline const bool hooked = (host::onRestart(hubRestart), true);

}  // namespace hubhost
