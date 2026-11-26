// When the Tilt Hub tells a controller's owners something (the alerts themselves go out through cloud.h). Plain C++,
// no ESP-IDF, so the rules are tested on the Mac (firmware/blinds_matter/test/logic_test.cpp).
//
// Every alert is sent once:
//   stall       a blind stalled during an ordinary move (the controller counts them since its start: b[].st)
//   silent      not heard for ALERT_SILENT_MS (cleared, without an alert, once it is heard again)
//   batt-low / batt-crit / batt-dead   under ALERT_LOW_PCT, under ALERT_CRIT_PCT, too low to move: each level once.
//               All reset only when the battery is back at ALERT_RESET_PCT or more (a little above the low line, so a
//               reading right at it can't make the alert come and go)
//   update      a firmware update through the hub failed;   hub-update   the hub's own new firmware went back
// The app's words for them: app/Tilt/Shared/Words.swift AlertWords (it uses the same battery lines).
#pragma once
#include <stdint.h>
#include <string.h>

const int ALERT_LOW_PCT = 20, ALERT_CRIT_PCT = 10, ALERT_RESET_PCT = 25;
const uint32_t ALERT_SILENT_MS = 1500000;        // 25 minutes: the app's HubInfo.Member.silentAfter
const int ALERT_PORTS = 3;

// What was already told about one controller (kept in flash).
struct AlertMemo {
  uint8_t silent;                                // "not responding" was sent
  uint8_t batt;                                  // the battery level told: 0 fine, 1 low, 2 critical, 3 too low to move
  uint8_t stBase;                                // the stall counts below are known
  uint32_t bn;                                   // the controller start (boot count) they belong to
  uint16_t st[ALERT_PORTS];
};

// 0 fine, 1 low, 2 critical, 3 too low to move; -1 not known (no reading yet).
inline int alertBattLevel(int pct, int low) { return low == 1 ? 3 : pct < 0 ? -1 : pct < ALERT_CRIT_PCT ? 2 : pct < ALERT_LOW_PCT ? 1 : 0; }
inline const char *alertBattKind(int level) { return level == 1 ? "batt-low" : level == 2 ? "batt-crit" : level == 3 ? "batt-dead" : nullptr; }

// A new battery reading: the alert to send (nullptr: none). A drop straight past a level tells only the lowest.
// Changes m when something changed (*changed = true: save it).
inline const char *alertBattery(AlertMemo &m, int pct, int low, bool *changed) {
  int lv = alertBattLevel(pct, low);
  if (lv > m.batt) { m.batt = (uint8_t)lv; *changed = true; return alertBattKind(lv); }
  if (lv == 0 && m.batt && pct >= ALERT_RESET_PCT) { m.batt = 0; *changed = true; }
  return nullptr;
}

// A status push with stall counts (st[], for n blinds, from start bn): which blinds stalled since the last push (a
// bit per blind). The first push only learns the counts; a new start counts from 0 again.
inline int alertStalls(AlertMemo &m, uint32_t bn, const int *st, int n, bool *changed) {
  bool fresh = !m.stBase;
  int out = 0;
  if (bn != m.bn) { if (!fresh) memset(m.st, 0, sizeof m.st); m.bn = bn; *changed = true; }
  for (int p = 0; p < n && p < ALERT_PORTS; p++) {
    if (st[p] < 0 || st[p] == m.st[p]) continue;
    if (st[p] > m.st[p] && !fresh) out |= 1 << p;
    m.st[p] = (uint16_t)st[p]; *changed = true;
  }
  if (fresh) { m.stBase = 1; *changed = true; }
  return out;
}

// Heard from it (any message): true if it had been told silent (cleared now).
inline bool alertHeard(AlertMemo &m) { if (!m.silent) return false; m.silent = 0; return true; }
// Quiet for quietMs: true once, when "not responding" should be sent.
inline bool alertSilent(AlertMemo &m, uint32_t quietMs) { if (m.silent || quietMs <= ALERT_SILENT_MS) return false; m.silent = 1; return true; }
