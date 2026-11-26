// Every secured command the app can send, with its handler and who may send it. The one list: web.h makes the
// handler table from it, logic.h permitRule decides from its roles, and test/logic_test.cpp checks it. No ESP-IDF here.
//
//   OWNER  only an Owner
//   GUEST  an Owner or a Guest (see the blinds and move them, see the people, make and change Scenes)
//   SELF   an Owner, or a Guest when the command's "cid" is the Guest's own (renaming themself)
#pragma once
#include <string>

enum Who { OWNER, GUEST, SELF };

#define TILT_ROUTES(R) \
  R("/api/s", hState, GUEST) R("/api/cfg", hCfg, GUEST) R("/api/go", hGo, GUEST) R("/api/stop", hStop, GUEST) \
  R("/api/home", hHome, GUEST) R("/api/backup", hBackup, GUEST) R("/api/keys", hKeys, GUEST) \
  R("/api/scenes", hScenes, GUEST) R("/api/scene", hScene, GUEST) \
  R("/api/keyname", hKeyName, SELF) \
  R("/api/dev", hDev, OWNER) R("/api/log", hLog, OWNER) R("/api/hist", hHist, OWNER) R("/api/set", hSet, OWNER) \
  R("/api/sched", hSched, OWNER) R("/api/jog", hJog, OWNER) R("/api/angle", hAngle, OWNER) R("/api/mark", hMark, OWNER) \
  R("/api/reset", hReset, OWNER) R("/api/reboot", hReboot, OWNER) R("/api/awake", hAwake, OWNER) R("/api/keep", hKeep, OWNER) \
  R("/api/watch", hWatch, OWNER) R("/api/trace", hTrace, OWNER) R("/api/homeopen", hHomeOpen, OWNER) \
  R("/api/revoke", hRevoke, OWNER) R("/api/approve", hApprove, OWNER) R("/api/makeowner", hMakeOwner, OWNER) \
  R("/api/otaopen", hOtaOpen, OWNER) R("/api/hubjoin", hHubJoin, OWNER) \
  R("/api/swapfw", hSwapFw, OWNER) R("/api/hubkey", hHubKey, OWNER) R("/api/hubnet", hHubNet, OWNER) \
  R("/api/factory", hFactory, OWNER) R("/api/restore", hRestore, OWNER) \
  TILT_DEV_ROUTES(R)

#ifdef TILT_DEVLOG
#define TILT_DEV_ROUTES(R) R("/api/powerlog", hPowerLog, OWNER)
#else
#define TILT_DEV_ROUTES(R)
#endif

struct RouteRule { const char *path; Who who; };
#define TILT_RULE(p, fn, w) {p, w},
inline constexpr RouteRule routeRules[] = { TILT_ROUTES(TILT_RULE) };
#undef TILT_RULE
inline constexpr int routeRuleCount = sizeof routeRules / sizeof routeRules[0];
// The rule for a command, or nullptr: not a command.
inline const RouteRule *routeRule(const std::string &path) {
  for (const RouteRule &r : routeRules) if (path == r.path) return &r;
  return nullptr;
}
