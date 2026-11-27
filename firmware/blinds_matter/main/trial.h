// The rule for keeping a new firmware on trial, shared by both firmwares, with no ESP-IDF in it, so it is tested on the
// Mac (blinds_matter/test/ota_test.cpp, tilt_hub/test/hub_test.cpp). The controller (web.h trialTick) runs it with
// Thread to the Tilt Hub as its link; the Tilt Hub (tilt_hub/main/hub_care.h careTask) with Wi-Fi and Apple Home as its
// link, and always as joined.
#pragma once
#include <cstdint>

// ---- a new firmware on trial: kept once Thread to the Tilt Hub has worked for a minute; dropped (back to the one
// before) if, five minutes after it started, it has a hub to reach and has not reached it.
enum TrialVerdict { TRIAL_WAIT, TRIAL_KEEP, TRIAL_ROLLBACK };
// The link counts as up when the hub was heard (proven) lately, or Thread to it worked in the last 2 minutes.
inline bool trialLinkUp(bool hubOk, uint32_t hubLinkSeen, uint32_t now) { return hubOk || (hubLinkSeen && now - hubLinkSeen < 120000); }
// Since when the link has been up (millis, 0 = it is not).
inline uint32_t trialLinkSince(uint32_t since, bool up, uint32_t now) { return !up ? 0 : since ? since : now ? now : 1; }
inline TrialVerdict trialVerdict(uint32_t now, uint32_t linkUpSince, bool hubJoined) {
  if (linkUpSince && now - linkUpSince > 60000) return TRIAL_KEEP;
  if (!linkUpSince && now > 300000 && hubJoined) return TRIAL_ROLLBACK;   // setup is done, and no hub
  return TRIAL_WAIT;
}
// The rule with its memory, as the controller runs it once a second (web.h trialTick) and the hub every 5 to 15 s: since when the link has been up,
// and whether going back was refused. Refused (no valid firmware in the other slot): it never asks again, since
// waiting cannot make one, and stays on this firmware, still on trial. Being kept still works the normal way.
struct Trial {
  TrialVerdict tick(uint32_t now, bool linkUp, bool hubJoined) {
    linkSince = trialLinkSince(linkSince, linkUp, now);
    TrialVerdict v = trialVerdict(now, linkSince, hubJoined);
    return v == TRIAL_ROLLBACK && refused ? TRIAL_WAIT : v;
  }
  void rollbackRefused() { refused = true; }
 private:
  uint32_t linkSince = 0;
  bool refused = false;
};
