// Scenes, kept on the controller so every phone with a key sees the same ones (the app puts them together across
// controllers by gid, wire.h). The controller only stores them: a phone runs a Scene by moving each blind.
// Anyone paired may read and write them (a Guest too); the state is under the controller lock (lock.h).
#pragma once
#include <vector>
#include "store.h"                               // nvs
#include "wire.h"
#include "api.h"                                 // arg, sendJson, ok, fail, Lock

const int SCENES = 16;
struct SceneSlot { uint32_t gid, ver; char name[48]; char sym[20]; uint8_t mask; int8_t tilt[PORTS]; };   // gid 0 = unused
struct SceneTable { uint32_t magic; SceneSlot s[SCENES]; } scn;
const uint32_t SCN_MAGIC = 0x53434E02;            // 02: names are 48 bytes of UTF-8
void scenesSave() { nvs.putBytes("scn", &scn, sizeof scn); }
void scenesBegin() {
  if (nvs.getBytes("scn", &scn, sizeof scn) != sizeof scn || scn.magic != SCN_MAGIC) { memset(&scn, 0, sizeof scn); scn.magic = SCN_MAGIC; }
}

esp_err_t hScenes(httpd_req_t *r) {
  Lock l;
  std::vector<WireScene> w;                      // on the heap: the task that answers has a small stack
  w.reserve(SCENES);
  for (const SceneSlot &s : scn.s) {
    if (!s.gid) continue;
    WireScene &o = w.emplace_back();
    o.gid = s.gid; o.ver = s.ver; o.mask = s.mask;
    o.name.assign(s.name, strnlen(s.name, sizeof s.name));
    o.sym.assign(s.sym, strnlen(s.sym, sizeof s.sym));
    for (int p = 0; p < PORTS; p++) o.t[p] = s.tilt[p];
  }
  return sendJson(r, scenesJson(w.data(), (int)w.size(), SCENES, PORTS));
}
// Save a Scene's part here (in the slot that has its gid, or a free one), or delete it (mask 0).
esp_err_t hScene(httpd_req_t *r) {
  Lock l;
  WireScene w = sceneOfArgs([&](const char *k) { return arg(r, k); }, PORTS);
  if (!w.gid) return fail(r, "no scene id");
  int at = -1, spare = -1;
  for (int i = 0; i < SCENES; i++) {
    if (scn.s[i].gid == w.gid) at = i;
    else if (!scn.s[i].gid && spare < 0) spare = i;
  }
  if (!w.mask) {
    if (at >= 0) { memset(&scn.s[at], 0, sizeof scn.s[at]); scenesSave(); }
    return ok(r);
  }
  if (at < 0) at = spare;
  if (at < 0) return fail(r, "this controller already has 16 scenes");
  SceneSlot &s = scn.s[at];
  memset(&s, 0, sizeof s);
  s.gid = w.gid; s.ver = w.ver; s.mask = w.mask;
  std::string nm = sceneName(w.name, sizeof s.name - 1);          // as typed (UTF-8), not cleanText: see wire.h
  strlcpy(s.name, nm.empty() ? "Scene" : nm.c_str(), sizeof s.name);
  strlcpy(s.sym, w.sym.c_str(), sizeof s.sym);
  for (int p = 0; p < PORTS; p++) s.tilt[p] = w.t[p];
  scenesSave();
  return ok(r);
}
