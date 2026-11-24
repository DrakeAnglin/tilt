// The wire contract for config and Schedule slots, as pure functions: no ESP-IDF, no shared state. web.h's hCfg and
// hSched call these. The shared fixture (test/wire/) is checked against them on the Mac (test/logic_test.cpp) and
// against the app's client (app/Tilt/Tests), so both sides read and write the same fields.
#pragma once
#include <cmath>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>

// ---- small JSON helpers
inline void ap(std::string &j, const char *fmt, ...) {
  char b[256];
  va_list a;
  va_start(a, fmt);
  vsnprintf(b, sizeof b, fmt, a);
  va_end(a);
  j += b;
}
inline std::string jq(const char *s) {
  std::string o = "\"";
  for (; *s; s++) {
    if (*s == '"' || *s == '\\') { o += '\\'; o += *s; }
    else if ((unsigned char)*s >= 32) o += *s;
  }
  return o + "\"";
}
inline std::string jn(float v, int dp) {
  if (std::isnan(v)) return "null";
  char b[24];
  snprintf(b, sizeof b, "%.*f", dp, v);
  return b;
}
inline int wireClamp(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }

// ---- what /api/cfg reports
struct WireBlind { const char *name; int hid, speed, fav; };
struct WireSlot { int on, days, mask, min, tilt, kind, off, ramp; uint32_t gid; };
struct WireCfg {
  const char *name; int closeUp, sync, par, tx; const char *tz, *tzn; int hksep;
  const WireBlind *b; int ports;              // one per Port
  const WireSlot *s; int slots;               // one per Schedule slot
  float lat, lon; uint32_t rise, set;
};
// "ports" and "slots" are the controller's limits (added in 2.2.1; an app that does not know them ignores them).
inline std::string cfgJson(const WireCfg &c) {
  std::string j;
  j.reserve(1400);
  ap(j, "{\"name\":%s,\"ports\":%d,\"slots\":%d,\"closeUp\":%d,\"sync\":%d,\"par\":%d,\"battMode\":1,\"checkin\":0,\"tx\":%d",
     jq(c.name).c_str(), c.ports, c.slots, c.closeUp, c.sync, c.par, c.tx);
  ap(j, ",\"tz\":%s,\"tzn\":%s,\"hksep\":%d,\"b\":[", jq(c.tz).c_str(), jq(c.tzn).c_str(), c.hksep);      // two parts: each must fit ap's buffer
  for (int i = 0; i < c.ports; i++) ap(j, "%s{\"name\":%s,\"hid\":%d,\"speed\":%d,\"fav\":%d}", i ? "," : "", jq(c.b[i].name).c_str(), c.b[i].hid, c.b[i].speed, c.b[i].fav);
  j += "],\"sched\":[";
  for (int i = 0; i < c.slots; i++) {
    const WireSlot &s = c.s[i];
    ap(j, "%s{\"on\":%d,\"days\":%d,\"mask\":%d,\"min\":%d,\"tilt\":%d,\"kind\":%d,\"off\":%d,\"ramp\":%d,\"gid\":%lu}", i ? "," : "", s.on, s.days, s.mask, s.min, s.tilt, s.kind, s.off, s.ramp, (unsigned long)s.gid);
  }
  ap(j, "],\"lat\":%s,\"lon\":%s,\"sun\":[%lu,%lu]}", jn(c.lat, 3).c_str(), jn(c.lon, 3).c_str(), (unsigned long)c.rise, (unsigned long)c.set);
  return j;
}

// ---- a Schedule slot write: /api/sched?i=N&on=&days=&mask=&min=&tilt=&kind=&off=&ramp=&gid=
// `arg(key)` gives one value of the query ("" when missing). Out-of-range values are brought into range.
template <class Arg> WireSlot slotOfArgs(Arg arg, int ports) {
  auto n = [&](const char *k) { return atoi(arg(k).c_str()); };
  WireSlot s;
  s.on = n("on") ? 1 : 0;
  s.days = n("days") & 0x7F;
  s.mask = n("mask") & ((1 << ports) - 1);
  s.min = wireClamp(n("min"), 0, 1439);
  s.tilt = wireClamp(n("tilt"), -100, 100);
  s.kind = wireClamp(n("kind"), 0, 2);
  s.off = wireClamp(n("off"), -180, 180);
  s.ramp = wireClamp(n("ramp"), 0, 60);
  s.gid = strtoul(arg("gid").c_str(), nullptr, 10);
  return s;
}

// ---- Scenes: /api/scenes lists them, /api/scene?gid=&ver=&name=&sym=&mask=&t=a,b,c writes one (mask 0 deletes it)
// A Scene may cover blinds on several controllers: each keeps its own part (its Ports' tilts), under the same gid, with
// the name, icon and edit time (ver, seconds) beside it, so any phone with a key can put the whole Scene back together.
struct WireScene { uint32_t gid, ver; std::string name, sym; int mask; int t[8]; };
inline std::string scenesJson(const WireScene *s, int n, int max, int ports) {
  std::string j;
  j.reserve(120 * n + 24);
  ap(j, "{\"max\":%d,\"sc\":[", max);
  for (int i = 0; i < n; i++) {
    ap(j, "%s{\"gid\":%lu,\"ver\":%lu,\"name\":%s,\"sym\":%s,\"mask\":%d,\"t\":[", i ? "," : "", (unsigned long)s[i].gid, (unsigned long)s[i].ver,
       jq(s[i].name.c_str()).c_str(), jq(s[i].sym.c_str()).c_str(), s[i].mask);
    for (int p = 0; p < ports; p++) ap(j, "%s%d", p ? "," : "", s[i].t[p]);
    j += "]}";
  }
  j += "]}";
  return j;
}
// A Scene write, from the query. Out-of-range values are brought into range; the icon keeps only a-z, 0-9 and dots
// (an SF Symbol name). The name is cleaned by the caller (cleanText), as every name typed in the app.
template <class Arg> WireScene sceneOfArgs(Arg arg, int ports) {
  WireScene s{};
  s.gid = strtoul(arg("gid").c_str(), nullptr, 10);
  s.ver = strtoul(arg("ver").c_str(), nullptr, 10);
  s.name = arg("name");
  for (char c : arg("sym")) if ((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '.') s.sym += c;
  s.mask = atoi(arg("mask").c_str()) & ((1 << ports) - 1);
  std::string t = arg("t");
  const char *p = t.c_str();
  for (int i = 0; i < ports; i++) {
    char *end;
    long v = strtol(p, &end, 10);
    s.t[i] = end == p ? 0 : wireClamp((int)v, -100, 100);
    p = *end == ',' ? end + 1 : end;
  }
  for (int i = 0; i < ports; i++) if (!((s.mask >> i) & 1)) s.t[i] = 0;
  return s;
}
