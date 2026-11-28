// What the Tilt Hub adds to the host board (firmware/blinds_matter/test/host_esp/host_board.h): the headers in this
// folder are the SDK ones only the hub includes (lwip/sockets.h, and app/server/Server.h for the one Matter call
// hub_store.h makes), and their state is here. Random bytes and the MAC are the shared board's (host::queueRandom,
// host::setMac).
// This folder comes first on the include path of firmware/tilt_hub/test/hub_board_test.cpp. Tests only.
//
// What a test can do (namespace hubhost):
//   Matter         setFailSafe: a home app is adding the hub right now (off after a restart)
#pragma once
#include "host_board.h"

namespace hubhost {

struct HubBoard {
  bool failSafeArmed = false;
};
inline HubBoard &hubBoard() { static HubBoard b; return b; }

inline void setFailSafe(bool armed) { hubBoard().failSafeArmed = armed; }

inline void hubRestart() { hubBoard().failSafeArmed = false; }
// Put back by the shared board's restart(), before the test program's own hook (this one is added first).
inline const bool hooked = (host::onRestart(hubRestart), true);

}  // namespace hubhost
