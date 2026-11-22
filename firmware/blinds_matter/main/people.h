// The phones on this controller: the list, rename, remove, approve, owner rights, and getting back in by turning a blind.
// Part of the web server (web.h includes it in place): uses its helpers and the blinds' shared state.
#pragma once

esp_err_t hKeys(httpd_req_t *r) {
  Lock l;
  std::string j = "{\"keys\":[";
  bool any = false;
  for (int i = 0; i < MAX_KEYS; i++) if (keys[i].used) {
    ap(j, "%s{\"cid\":\"%s\",\"name\":%s,\"owner\":%d,\"me\":%d,\"wait\":%d,\"code\":\"%s\"}", any ? "," : "", hexOf(keys[i].id, 8).c_str(), jq(keys[i].name).c_str(), keys[i].role,
       i == secClient ? 1 : 0, keys[i].used == 2 ? 1 : 0, keys[i].used == 2 ? askCode(keys[i]).c_str() : "");
    any = true;
  }
  j += "]}";
  return sendJson(r, j);
}
esp_err_t hRevoke(httpd_req_t *r) {              // owner: remove a phone. "all" removes every phone (back to unpaired).
  Lock l;
  std::string c = arg(r, "cid");
  uint8_t id[8];
  int n = 0;
  std::string proof;
  if (c != "all" && !unhex(c, id, 8)) return fail(r, "bad id");
  if (c != "all" && secClient >= 0 && !memcmp(keys[secClient].id, id, 8)) return fail(r, "you cannot remove yourself");
  if (c != "all") {                              // never remove the last owner: nobody could manage the controller
    int others = 0;
    for (int i = 0; i < MAX_KEYS; i++) if (keys[i].used == 1 && keys[i].role && memcmp(keys[i].id, id, 8)) others++;
    if (!others) return fail(r, "that is the only owner");
  }
  for (int i = 0; i < MAX_KEYS; i++) if (keys[i].used && (c == "all" || !memcmp(keys[i].id, id, 8))) {
    uint8_t h[32];                               // proof for the removed phone (made with its own key) that it really was removed here
    hmac256(keys[i].key, 32, (const uint8_t *)"removed", 7, h);
    proof = hexOf(h, 16);
    event("%s removed", keys[i].name); memset(&keys[i], 0, sizeof keys[i]); n++;
  }
  if (!n) return fail(r, "no such phone");
  keysSave();
  return sendJson(r, std::string("{\"ok\":1,\"proof\":\"") + proof + "\"}");
}
esp_err_t hKeyName(httpd_req_t *r) {             // rename a phone in the People list (who may: permit() in sec.h)
  Lock l;
  uint8_t id[8];
  if (!unhex(arg(r, "cid"), id, 8)) return fail(r, "bad id");
  for (int i = 0; i < MAX_KEYS; i++) if (keys[i].used && !memcmp(keys[i].id, id, 8)) {
    char nm[sizeof keys[i].name];
    cleanText(nm, sizeof nm, arg(r, "name"));
    if (!nm[0]) return fail(r, "a name is needed");
    strlcpy(keys[i].name, nm, sizeof keys[i].name);
    keysSave();
    return ok(r);
  }
  return fail(r, "no such phone");
}
esp_err_t hApprove(httpd_req_t *r) {             // owner: answer a phone that asked to join. ok=1 lets it in (owner=1: as an owner), ok=0 removes it.
  Lock l;
  uint8_t id[8];
  if (!unhex(arg(r, "cid"), id, 8)) return fail(r, "bad id");
  for (int i = 0; i < MAX_KEYS; i++) if (keys[i].used == 2 && !memcmp(keys[i].id, id, 8)) {
    if (arg(r, "ok") == "1") { keys[i].used = 1; keys[i].role = arg(r, "owner") == "1" ? 1 : 0; lastCtr[i] = 0; event("%s approved (%s)", keys[i].name, keys[i].role ? "owner" : "user"); }
    else { event("%s turned down", keys[i].name); memset(&keys[i], 0, sizeof keys[i]); }
    keysSave();
    return ok(r);
  }
  return fail(r, "no such request");
}
// ---- getting back in when no owner's phone is left
// Physical proof instead of a reset button: whoever asks must turn one blind's wand fully closed up, then fully closed
// down, then level (open), within two minutes. Only someone at the window can do that. The phone that asked becomes
// an owner; the blinds' settings and the other phones are left as they are.
struct Recover { int slot = -1, port = 0, step = 0; uint32_t until = 0, moves = 0; } recover;
uint32_t movesEver() { uint32_t n = 0; for (int p = 0; p < PORTS; p++) n += stats.moves[p]; return n; }
void recoverTick() {                             // from webTick, once a second
  if (recover.slot < 0) return;
  uint32_t now = millis();
  ClientKey &k = keys[recover.slot];
  if ((int32_t)(recover.until - now) <= 0 || k.used != 2) {
    if (k.used == 2) { memset(&k, 0, sizeof k); keysSave(); event("recovery timed out"); }
    recover.slot = -1;
    return;
  }
  // The turning has to be by hand. If a motor runs at all (a paired phone could send a blind to these positions), the
  // attempt is over: otherwise a user could make themself an owner without touching the blind.
  if (moving() || movesEver() != recover.moves) {
    memset(&k, 0, sizeof k); keysSave(); recover.slot = -1;
    event("recovery stopped: a motor ran");
    return;
  }
  int p = recover.port;
  if (watchPort >= 0 && watchPort != p) watchStop();
  watchPort = p; handBusy = false; watchUntil = now + 3000;      // keep this blind's sensor read, as a setup screen does
  setupSeen = now ? now : 1;                                     // and the other blinds do not follow these twists
  float t = bs[p].tilt;
  if (isnan(t)) return;
  bool hit = recover.step == 0 ? t >= 85 : recover.step == 1 ? t <= -85 : fabsf(t) <= 20;
  if (!hit || ++recover.step < 3) return;
  k.used = 1; k.role = 1; lastCtr[recover.slot] = 0;
  keysSave();
  event("%s recovered access by turning blind %d", k.name, p + 1);
  recover.slot = -1;
}
esp_err_t hRecover(httpd_req_t *r) {             // POST /x/recover: the same JSON as /x/ask
  int p = -1;
  for (int i = 0; i < PORTS && p < 0; i++) if (movable(i)) p = i;
  if (p < 0) return plain(r, "409 Conflict", "{\"err\":\"no blind is set up, so there is nothing to turn\"}");
  if (recover.slot >= 0) return plain(r, "429 Too Many Requests", "{\"err\":\"a recovery is already under way. Try again in two minutes.\"}");
  std::string out;
  const char *st = pairDo(body(r, 600), out, true);
  if (strcmp(st, "200 OK")) return plain(r, st, out);
  uint8_t id[8];
  unhex(jsonStr(out, "cid"), id, 8);
  {
    KeysLock kl;                                 // recover, ramps and keys[] are also used by the main loop (recoverTick)
    for (int i = 0; i < MAX_KEYS; i++) if (keys[i].used == 2 && !memcmp(keys[i].id, id, 8)) recover.slot = i;
    rampCancel();                                // a gentle move would run the motor and end the attempt
    recover.port = p; recover.step = 0; recover.until = millis() + 120000; recover.moves = movesEver();
  }
  event("recovery started: turn blind %d", p + 1);
  out.pop_back();                                // the closing brace
  out += std::string(",\"recover\":1,\"blind\":") + std::to_string(p) + ",\"blindName\":" + jq(cfg.b[p].name) + "}";
  return plain(r, st, out);
}
esp_err_t hRecoverState(httpd_req_t *r) {        // GET /x/recstate: how far the turning has got (0..3), seconds left
  std::string j;
  ap(j, "{\"on\":%d,\"step\":%d,\"left\":%d}", recover.slot >= 0 ? 1 : 0, recover.slot >= 0 ? recover.step : 0, recover.slot >= 0 ? (int)((int32_t)(recover.until - millis()) / 1000) : 0);
  return plain(r, "200 OK", j);
}
esp_err_t hMakeOwner(httpd_req_t *r) {           // owner: give another phone the owner's rights too
  Lock l;
  uint8_t id[8];
  if (!unhex(arg(r, "cid"), id, 8)) return fail(r, "bad id");
  bool on = arg(r, "on") != "0";                 // on=0: back to a user
  for (int i = 0; i < MAX_KEYS; i++) if (keys[i].used == 1 && !memcmp(keys[i].id, id, 8)) {
    if (!on && i == secClient) return fail(r, "you cannot change yourself");
    keys[i].role = on ? 1 : 0; keysSave(); event("%s is now %s", keys[i].name, on ? "an owner" : "a user"); return ok(r);
  }
  return fail(r, "no such phone");
}
