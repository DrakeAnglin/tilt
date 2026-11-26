// The ESP side of the link to the controllers (ctrl_link.h, tilt_link.h): the UDP socket on Thread, the hub's own
// key on each controller, and the task that takes their pushes and answers. Part of hub.cpp.
#pragma once
static void alertsFromPush(int c, cJSON *j);                      // hub_alerts.h
// ---- UDP to the controllers: send one request, wait for its answer
static int sock = -1;
struct Pending { uint16_t seq; bool used, done; std::string ans; SemaphoreHandle_t sem; in6_addr to;   // to: only its answer counts
                 PieceJoin join; };                                                                 // a long answer, in pieces
static Pending pend[8];
static SemaphoreHandle_t pendMx;
static uint16_t nextSeq = 1;
// Returns the 3-digit status (0 = no answer) and the answer.
static int ask(int c, char type, const std::string &payload, std::string &ans, uint32_t waitMs = 2500) {
  Ctrl &k = ctrls[c];
  if (!k.addrOk) return 0;
  xSemaphoreTake(k.mx, portMAX_DELAY);
  int st = 0;
  for (int attempt = 0; attempt < 2 && !st; attempt++) {
    xSemaphoreTake(pendMx, portMAX_DELAY);
    int slot = -1;
    for (int i = 0; i < 8; i++) if (!pend[i].used) { slot = i; break; }
    uint16_t seq = nextSeq++;
    if (!nextSeq) nextSeq = 1;
    if (slot >= 0) {
      Pending &p = pend[slot];
      p.used = true; p.done = false; p.seq = seq; p.ans.clear(); p.to = k.addr.sin6_addr; p.join.reset();
      xSemaphoreTake(p.sem, 0);
    }
    xSemaphoreGive(pendMx);
    if (slot < 0) break;
    std::string m = dgEncode(type, seq, payload);
    sendto(sock, m.data(), m.size(), 0, (sockaddr *)&k.addr, sizeof k.addr);
    if (xSemaphoreTake(pend[slot].sem, pdMS_TO_TICKS(waitMs)) == pdTRUE) st = dgStatus(pend[slot].ans, ans);
    xSemaphoreTake(pendMx, portMAX_DELAY);
    pend[slot].used = false;
    xSemaphoreGive(pendMx);
  }
  xSemaphoreGive(k.mx);
  return st;
}

// ---- the hub's own key for each controller (it moves blinds like a phone would)
static int rng(void *, unsigned char *b, size_t n) { esp_fill_random(b, n); return 0; }
#include "cloud.h"                               // alertRaise: push alerts through iCloud
#include "alert_rules.h"                         // when to send them
// The link key for the proofs on messages between the hub and a controller that has let the hub in (and been told
// which key is the hub's). False when there is none. Protocol: blinds_matter/main/tilt_link.h.
static bool linkOf(int c, uint8_t link[32]) { return ctrls[c].s.keyState == KEY_IN && linkKey(ctrls[c].s.key, link); }
static void cleanName(char *out, size_t n, const std::string &in);
// Ask to join, as "Tilt Hub" (the controller's /x/ask). The owner lets it in from the app.
static void askToJoin(int c) {
  mbedtls_ecp_group grp; mbedtls_mpi d, z; mbedtls_ecp_point Q, Qp;
  mbedtls_ecp_group_init(&grp); mbedtls_mpi_init(&d); mbedtls_mpi_init(&z); mbedtls_ecp_point_init(&Q); mbedtls_ecp_point_init(&Qp);
  uint8_t cpub[65], dpub[65], shared[32], okm[32];
  size_t cn = 0, n = 0;
  bool ok = mbedtls_ecp_group_load(&grp, MBEDTLS_ECP_DP_SECP256R1) == 0 && mbedtls_ecdh_gen_public(&grp, &d, &Q, rng, nullptr) == 0 &&
            mbedtls_ecp_point_write_binary(&grp, &Q, MBEDTLS_ECP_PF_UNCOMPRESSED, &cn, cpub, sizeof cpub) == 0 && cn == 65;
  std::string ans;
  if (ok) {
    uint8_t b64[100];
    size_t bn = 0;
    mbedtls_base64_encode(b64, sizeof b64, &bn, cpub, 65);
    std::string body = "{\"pub\":\"" + std::string((char *)b64, bn) + "\",\"name\":\"Tilt Hub\"}";
    int st = ask(c, 'A', body, ans, 4000);
    ok = st == 200;
    if (!ok) ESP_LOGW(TAG, "%s: ask to join refused (%d) %s", ctrls[c].s.id, st, ans.c_str());
  }
  cJSON *j = ok ? cJSON_Parse(ans.c_str()) : nullptr;
  const char *pub = j ? cJSON_GetStringValue(cJSON_GetObjectItem(j, "pub")) : nullptr, *cid = j ? cJSON_GetStringValue(cJSON_GetObjectItem(j, "cid")) : nullptr;
  ok = pub && cid && mbedtls_base64_decode(dpub, sizeof dpub, &n, (const uint8_t *)pub, strlen(pub)) == 0 && n == 65 &&
       mbedtls_ecp_point_read_binary(&grp, &Qp, dpub, 65) == 0 && mbedtls_ecdh_compute_shared(&grp, &z, &Qp, &d, rng, nullptr) == 0 &&
       mbedtls_mpi_write_binary(&z, shared, 32) == 0;
  if (ok) {
    ok = deriveKey(shared, "", cpub, dpub, okm) && unhex(cid, ctrls[c].s.cid, 8);
  }
  if (ok) {
    xSemaphoreTake(stateMx, portMAX_DELAY);
    memcpy(ctrls[c].s.key, okm, 32);
    ctrls[c].s.keyState = KEY_ASKED;
    saveCtrls();
    xSemaphoreGive(stateMx);
    ESP_LOGI(TAG, "%s: asked to join as Tilt Hub (the owner's Tilt app lets it in by itself).", ctrls[c].s.id);
  }
  if (j) cJSON_Delete(j);
  mbedtls_ecp_group_free(&grp); mbedtls_mpi_free(&d); mbedtls_mpi_free(&z); mbedtls_ecp_point_free(&Q); mbedtls_ecp_point_free(&Qp);
}
// ctrlCommand's way to the network and to the hub's saved key for one controller (ctrl_link.h).
struct HubSeam : LinkSeam {
  int c;
  explicit HubSeam(int c) : c(c) {}
  int ask(char type, const std::string &payload, std::string &ans) override { return ::ask(c, type, payload, ans); }
  KeyState hubKey(uint8_t key[32], uint8_t cid[8]) override {
    xSemaphoreTake(stateMx, portMAX_DELAY);
    KeyState ks = (KeyState)ctrls[c].s.keyState;
    if (ks != KEY_NONE) { memcpy(key, ctrls[c].s.key, 32); memcpy(cid, ctrls[c].s.cid, 8); }
    xSemaphoreGive(stateMx);
    return ks;
  }
  void dropped() override {
    xSemaphoreTake(stateMx, portMAX_DELAY);
    ctrls[c].s.keyState = KEY_NONE; proofs[c] = {};
    saveCtrls(); proofsSave();
    xSemaphoreGive(stateMx);
  }
  void letIn() override {
    xSemaphoreTake(stateMx, portMAX_DELAY);
    bool now = ctrls[c].s.keyState == KEY_ASKED;
    if (now) { ctrls[c].s.keyState = KEY_IN; saveCtrls(); }
    xSemaphoreGive(stateMx);
    if (now) ESP_LOGI(TAG, "%s: Tilt Hub let in", ctrls[c].s.id);
  }
  uint64_t clockMs() override { return (uint64_t)time(nullptr) * 1000ULL + ms() % 1000; }
};
// A command with the hub's key: "/api/home?b=0&lift=5000". Returns the controller's JSON answer, or "" on failure.
// Any task may call it (moves, care, updates): the link keeps one command at a time and one counter (ctrl_link.h).
static std::string ctrlCommand(int c, const std::string &cmd) {
  HubSeam seam(c);
  CallResult r = links[c].call(seam, cmd);
  const char *id = ctrls[c].s.id;
  switch (r.why) {
    case CallResult::OK: return r.out;
    case CallResult::NO_KEY: case CallResult::NO_HELLO: break;
    case CallResult::WAITING: ESP_LOGW(TAG, "%s: Tilt Hub is waiting to be let in (open the owner's Tilt app)", id); break;
    case CallResult::SEAL: ESP_LOGW(TAG, "%s: command %s could not be sealed", id, cmd.c_str()); break;
    case CallResult::BAD_REPLY: ESP_LOGW(TAG, "%s: command %s: the answer did not open", id, cmd.c_str()); break;
    default: ESP_LOGW(TAG, "%s: command %s failed (%d) %s", id, cmd.c_str(), r.st, r.out.c_str()); break;
  }
  return "";
}

// ---- the controllers' pushes and answers
static void announce(int c);
static bool sameAddr(const sockaddr_in6 &a, const sockaddr_in6 &b) { return !memcmp(&a.sin6_addr, &b.sin6_addr, 16); }
static void udpTask(void *) {
  static char buf[2400];
  for (;;) {
    sockaddr_in6 from;
    socklen_t fl = sizeof from;
    int n = recvfrom(sock, buf, sizeof buf - 1, 0, (sockaddr *)&from, &fl);   // room for the end mark
    if (n < 3) continue;
    char t = buf[0];
    uint16_t seq = ((uint8_t)buf[1] << 8) | (uint8_t)buf[2];
    { char ip[48]; inet6_ntoa_r(from.sin6_addr, ip, sizeof ip); ESP_LOGD(TAG, "udp '%c' %d bytes from %s", t, n, ip); if (t == 'S') ESP_LOGI(TAG, "push from %s", ip); }
    if (t == 'G') {                             // a controller leaving (factory reset): stop pointing the app here
      xSemaphoreTake(stateMx, portMAX_DELAY);
      for (int i = 0; i < MAX_CTRL; i++) if (ctrls[i].used && ctrls[i].addrOk && sameAddr(ctrls[i].addr, from)) {
        // One that let the hub in proves it is really leaving (anyone else could say it for it).
        uint8_t link[32];
        if (ctrls[i].s.keyState == KEY_IN && (!linkOf(i, link) || !links[i].proofOkNow(link, Proof::CtlBye, "", std::string(buf + 3, n - 3)))) continue;
        std::string inst = ctrls[i].s.id;
        for (auto &ch : inst) ch = toupper(ch);
        mdns_service_remove_for_host((inst + " via Tilt Hub").c_str(), "_tilt", "_tcp", nullptr);
        ctrls[i].announced = false;
        ctrls[i].seen = 0;
        ctrls[i].hello.clear();
        // It forgot everything: the hub's key there is gone too. Ask to join again once it is set up anew.
        ctrls[i].s.keyState = KEY_NONE; proofs[i] = {};
        saveCtrls(); proofsSave();
        ESP_LOGI(TAG, "%s was reset: it is new again", ctrls[i].s.id);
      }
      xSemaphoreGive(stateMx);
      continue;
    }
    if (t == 'L') {                             // a line of a controller's event log
      buf[n] = 0;
      int c = -1;
      xSemaphoreTake(stateMx, portMAX_DELAY);
      for (int i = 0; i < MAX_CTRL; i++) if (ctrls[i].used && ctrls[i].addrOk && !memcmp(&ctrls[i].addr.sin6_addr, &from.sin6_addr, 16)) c = i;
      xSemaphoreGive(stateMx);
      ESP_LOGI(TAG, "[%s] %s", c >= 0 ? ctrls[c].s.id : "?", buf + 3);
      continue;
    }
    if (t == 'h' && seq == 0 && n > 6) {       // the answer to a hello the hub sent an attached device
      buf[n] = 0;
      cJSON *j = cJSON_Parse(buf + 6);
      const char *id = j ? cJSON_GetStringValue(cJSON_GetObjectItem(j, "id")) : nullptr;
      if (id && strlen(id) == 12) {
        xSemaphoreTake(stateMx, portMAX_DELAY);
        int c = findCtrl(id);
        if (c < 0) for (int i = 0; i < MAX_CTRL; i++) if (!ctrls[i].used) { c = i; memset(&ctrls[i].s, 0, sizeof ctrls[i].s); strlcpy(ctrls[i].s.id, id, 13); ctrls[i].used = true; saveCtrls(); break; }
        if (c >= 0) {
          // A hello answer carries no proof. It points the hub at a controller it has no key for yet, or at one that
          // has gone quiet for a minute (it restarted and its address changed); otherwise only proven pushes move it.
          if (ctrls[c].s.keyState != KEY_IN || !ctrls[c].addrOk || (ms() - ctrls[c].seen > 60000 && otaFor != c)) {
            ctrls[c].addr = from; ctrls[c].addrOk = true; ctrls[c].seen = ms() ? ms() : 1;
            const uint8_t *a = (const uint8_t *)&from.sin6_addr;
            ctrls[c].rloc = (a[11] == 0xff && a[12] == 0xfe) ? (a[14] << 8 | a[15]) : 0;
            const char *nm = cJSON_GetStringValue(cJSON_GetObjectItem(j, "name"));
            if (nm) strlcpy(ctrls[c].name, keptName(nm, sizeof ctrls[c].name - 1).c_str(), sizeof ctrls[c].name);   // as typed (wire.h)
            ESP_LOGI(TAG, "controller %s (%s) answered on Thread", id, ctrls[c].name);
            ctrls[c].announced = false;
          }
        }
        xSemaphoreGive(stateMx);
      }
      if (j) cJSON_Delete(j);
      continue;
    }
    if (t == 'h' && n > 6 && !memcmp(buf + 3, "200", 3)) {   // keep the controller's hello for the app
      buf[n] = 0;
      cJSON *hj = cJSON_Parse(buf + 6);
      const char *hid = hj ? cJSON_GetStringValue(cJSON_GetObjectItem(hj, "id")) : nullptr, *hb = hj ? cJSON_GetStringValue(cJSON_GetObjectItem(hj, "boot")) : nullptr;
      xSemaphoreTake(stateMx, portMAX_DELAY);
      int hc = hid ? findCtrl(hid) : -1;
      if (hc >= 0 && hb && strlen(hb) == 8) { ctrls[hc].hello.assign(buf + 6, n - 6); strlcpy(ctrls[hc].helloBoot, hb, 9); }
      xSemaphoreGive(stateMx);
      if (hj) cJSON_Delete(hj);
    }
    if (t == 'w' && n >= 6) {                   // a firmware piece arrived: the next offset it wants
      int f = otaFor;
      if (f < 0 || !sameAddr(ctrls[f].addr, from)) continue;   // only from the controller being updated
      ctrls[f].seen = ms() ? ms() : 1;
      buf[n] = 0;
      OtaAck a = {!memcmp(buf + 3, "200", 3), buf[6] >= '0' && buf[6] <= '9', (uint32_t)strtoul(buf + 6, nullptr, 10)};   // 3-digit status, then the offset
      if (!a.ok) { static int shown = 0; if (shown++ < 3) ESP_LOGW(TAG, "piece answer: '%.40s'", buf + 3); }
      if (otaAcks) xQueueSend(otaAcks, &a, 0);
      continue;
    }
    if (t == DG_PIECES && n > 5) {             // a piece of a long answer: '#' seq, piece, count, part
      std::string piece(buf + 3, n - 3);
      xSemaphoreTake(pendMx, portMAX_DELAY);
      for (auto &p : pend) {
        if (!p.used || p.done || p.seq != seq || memcmp(&p.to, &from.sin6_addr, 16)) continue;
        if (p.join.add(piece, p.ans) == PieceJoin::DONE) {
          p.done = true;
          xSemaphoreGive(p.sem);
          for (auto &k : ctrls) if (k.used && k.addrOk && sameAddr(k.addr, from)) k.seen = ms() ? ms() : 1;
        }
        break;
      }
      xSemaphoreGive(pendMx);
      continue;
    }
    if (t != 'S') {                             // an answer to one of our requests
      xSemaphoreTake(pendMx, portMAX_DELAY);
      bool matched = false;
      for (auto &p : pend) if (p.used && !p.done && p.seq == seq && !memcmp(&p.to, &from.sin6_addr, 16)) { p.ans.assign(buf + 3, n - 3); p.done = true; matched = true; xSemaphoreGive(p.sem); }
      if (matched) for (auto &k : ctrls) if (k.used && k.addrOk && sameAddr(k.addr, from)) k.seen = ms() ? ms() : 1;   // it answered: heard from
      xSemaphoreGive(pendMx);
      continue;
    }
    // A status push: JSON, then (from a controller that has let the hub in) "\n" count "." proof.
    buf[n] = 0;
    PushIn push = pushParse(std::string(buf + 3, n - 3));
    const std::string &json = push.json;
    cJSON *j = cJSON_Parse(json.c_str());
    const char *id = j ? cJSON_GetStringValue(cJSON_GetObjectItem(j, "id")) : nullptr;
    const char *pb = j ? cJSON_GetStringValue(cJSON_GetObjectItem(j, "boot")) : nullptr;
    uint8_t boot[4];
    if (!id || strlen(id) != 12 || !pb || !unhex(pb, boot, 4)) { if (j) cJSON_Delete(j); continue; }
    xSemaphoreTake(stateMx, portMAX_DELAY);
    int c = findCtrl(id);
    bool isNew = c < 0;
    if (c >= 0 && ctrls[c].s.keyState == KEY_IN) {    // let the hub in: a proven push, never an old one (tilt_link.h pushAccept)
      cJSON *bnj = cJSON_GetObjectItem(j, "bn");
      uint32_t bn = cJSON_IsNumber(bnj) ? (uint32_t)bnj->valuedouble : 0;
      uint8_t link[32];
      bool proven = push.n && linkOf(c, link) && proofOk(link, Proof::CtlPush, boot, json + std::to_string(push.n), push.mac);
      PushState was;
      was.on = proofs[c].on; was.bn = proofs[c].bn; was.boot = ctrls[c].pushBoot; was.n = ctrls[c].pushN;
      PushResult pr = pushAccept(was, proven, bn, pb, push.n);
      if (pr.verdict == PushVerdict::Take) {
        ctrls[c].pushN = pr.state.n;
        if (pr.save) { proofs[c].on = 1; proofs[c].bn = pr.state.bn; proofsSave(); }
      } else if (pr.verdict == PushVerdict::Refuse) {   // once it proves its pushes, nothing else counts (nor an old one)
        static uint32_t told = 0;
        if (ms() - told > 60000) { told = ms(); ESP_LOGW(TAG, "%s: a push without a good proof was ignored", id); }
        xSemaphoreGive(stateMx); cJSON_Delete(j); continue;
      }
      // (not proven yet: it has not been told which key is the hub's; taken as before setup)
    }
    if (isNew) {
      for (int i = 0; i < MAX_CTRL && c < 0; i++) if (!ctrls[i].used) c = i;
      // Full: a place held by one that never let the hub in and has been quiet for 10 minutes is taken over (so made-up
      // ids cannot fill the hub for good).
      for (int i = 0; i < MAX_CTRL && c < 0; i++) {
        bool tiles = false;
        for (int p = 0; p < PORTS; p++) tiles = tiles || ctrls[i].s.ep[p];
        if (ctrls[i].s.keyState == KEY_NONE && !tiles && !ctrls[i].announced && ms() - ctrls[i].seen > 600000) c = i;
      }
      if (c >= 0) {                              // a clean place (the request lock stays)
        SemaphoreHandle_t m = ctrls[c].mx;
        ctrls[c] = Ctrl{};
        links[c].reset();
        Ctrl &f = ctrls[c];
        f.mx = m; f.pct = -1; f.chg = -1; f.src = -1; f.sep = -1; f.own = -1;
        for (auto &b : f.b) b.tilt = b.tgt = INT32_MIN;
        for (int t = 0; t < PORTS; t++) f.tileLift[t] = f.tileOp[t] = -1;
        strlcpy(f.s.id, id, 13); f.used = true;
        saveCtrls();
      }
    }
    if (c < 0) { xSemaphoreGive(stateMx); cJSON_Delete(j); continue; }
    Ctrl &k = ctrls[c];
    // Answer with the time (the controller's Schedules need it), with the proof so it can trust it.
    {
      uint8_t link[32];
      std::string ts = std::to_string((long)time(nullptr)), mac = linkOf(c, link) ? proof(link, Proof::HubTime, boot, ts) : "";
      if (!mac.empty() && time(nullptr) > 1700000000) {
        std::string ack = dgEncode(DG_TIME, seq, dgAnswer(200, ts + "." + mac));
        sendto(sock, ack.data(), ack.size(), 0, (sockaddr *)&from, fl);
      }
    }
    bool moved = !k.addrOk || memcmp(&k.addr.sin6_addr, &from.sin6_addr, 16);
    k.addr = from; k.addrOk = true; k.seen = ms() ? ms() : 1;
    const char *nm = cJSON_GetStringValue(cJSON_GetObjectItem(j, "name"));
    char clean[33];                              // the name as typed (wire.h keptName), quotes too
    if (nm) strlcpy(clean, keptName(nm, sizeof clean - 1).c_str(), sizeof clean);
    if (nm && strcmp(clean, k.name)) { strlcpy(k.name, clean, sizeof k.name); k.announced = false; }
    k.pct = cJSON_GetNumberValue(cJSON_GetObjectItem(j, "pct"));
    k.low = cJSON_GetNumberValue(cJSON_GetObjectItem(j, "low"));
    cJSON *chgj = cJSON_GetObjectItem(j, "chg");
    k.chg = cJSON_IsNumber(chgj) ? chgj->valueint : -1;
    cJSON *srcj = cJSON_GetObjectItem(j, "src");
    k.src = cJSON_IsNumber(srcj) ? srcj->valueint : -1;
    cJSON *ownj = cJSON_GetObjectItem(j, "own");
    if (cJSON_IsNumber(ownj) && ownj->valueint != k.own) { k.own = ownj->valueint; k.announced = false; k.hello.clear(); }   // its hello says "owned": ask it again
    cJSON *cvj = cJSON_GetObjectItem(j, "cv");
    if (cJSON_IsNumber(cvj)) k.cv = (uint32_t)cvj->valuedouble;
    if (!k.firstSeen) k.firstSeen = ms() ? ms() : 1;
    const char *fwv = cJSON_GetStringValue(cJSON_GetObjectItem(j, "fw"));
    if (fwv) cleanName(k.fw, sizeof k.fw, fwv);
    k.closeUp = cJSON_GetNumberValue(cJSON_GetObjectItem(j, "closeUp"));
    cJSON *sp = cJSON_GetObjectItem(j, "sep");
    k.sep = cJSON_IsNumber(sp) ? (sp->valueint ? 1 : 0) : 0;
    const char *bt = cJSON_GetStringValue(cJSON_GetObjectItem(j, "boot"));
    if (bt && strlen(bt) == 8 && strcmp(bt, k.pushBoot)) {   // it restarted: its new boot id (for the hub's own commands too)
      strlcpy(k.pushBoot, bt, sizeof k.pushBoot);
      uint8_t nb[4];
      if (unhex(bt, nb, 4)) links[c].setBoot(nb); else links[c].forgetBoot();
    }
    cJSON *bl = cJSON_GetObjectItem(j, "b");
    for (int p = 0; p < PORTS && bl; p++) {
      cJSON *b = cJSON_GetArrayItem(bl, p);
      if (!b) break;
      Ctrl::B &x = k.b[p];
      const char *bn = cJSON_GetStringValue(cJSON_GetObjectItem(b, "n"));
      strlcpy(x.name, keptName(bn ? bn : "", sizeof x.name - 1).c_str(), sizeof x.name);
      x.hid = cJSON_GetNumberValue(cJSON_GetObjectItem(b, "h"));
      x.ok = cJSON_GetNumberValue(cJSON_GetObjectItem(b, "ok"));
      cJSON *tv = cJSON_GetObjectItem(b, "t"), *gv = cJSON_GetObjectItem(b, "g");
      x.tilt = cJSON_IsNumber(tv) ? (int)tv->valuedouble : INT32_MIN;
      x.tgt = cJSON_IsNumber(gv) ? (int)gv->valuedouble : INT32_MIN;
      x.mov = cJSON_GetNumberValue(cJSON_GetObjectItem(b, "m"));
    }
    alertsFromPush(c, j);
    xSemaphoreGive(stateMx);
    cJSON_Delete(j);
    if (isNew || moved) ESP_LOGI(TAG, "controller %s (%s) on Thread", k.s.id, k.name);
    if (matterUp) chip::DeviceLayer::PlatformMgr().ScheduleWork(applyStatus, (intptr_t)c);
    if (!k.announced) announce(c);
  }
}
