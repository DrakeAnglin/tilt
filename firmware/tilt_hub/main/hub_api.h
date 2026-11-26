// What the app asks the Tilt Hub: the relay to a controller, the hub's info, backups and network, its commands
// (hubCommand), the HTTP handlers, and the one-time code for another home app (last: after hubCommand, its one
// caller, as before the split, so the compiler still folds it in and the binary stays the same). Part of hub.cpp.
#pragma once
// ---- the app: http://<hub>/c/<id>/x...  (the same requests as to a controller on Wi-Fi)
static std::string hubIp() {
  esp_netif_ip_info_t info = {};
  esp_netif_t *nif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
  if (nif) esp_netif_get_ip_info(nif, &info);
  char ip[20];
  snprintf(ip, sizeof ip, IPSTR, IP2STR(&info.ip));
  return ip;
}
static bool netUp() { return hubIp() != "0.0.0.0"; }
static void announce(int c) {
  std::string ip = hubIp();
  if (ip == "0.0.0.0") return;
  Ctrl &k = ctrls[c];
  std::string host = ip + "/c/" + k.s.id, inst = k.s.id;
  for (auto &ch : inst) ch = toupper(ch);
  inst += " via Tilt Hub";                         // not the controller's own name (it uses that on Wi-Fi)
  mdns_txt_item_t txt[] = {{"id", k.s.id}, {"ip", host.c_str()}, {"owned", k.own == 0 ? "0" : "1"}, {"name", k.name}, {"via", "hub"}};
  esp_err_t e = mdns_service_txt_set_for_host(inst.c_str(), "_tilt", "_tcp", nullptr, txt, 5);
  if (e != ESP_OK) e = mdns_service_add_for_host(inst.c_str(), "_tilt", "_tcp", nullptr, 80, txt, 5);
  k.announced = e == ESP_OK;
  ESP_LOGI(TAG, "announced %s as %s: %s", inst.c_str(), host.c_str(), esp_err_to_name(e));
}
static const char *reason(int st) { return statusLine(st); }   // tilt_link.h: one table for the link and the app
static esp_err_t hRelay(httpd_req_t *r) {
  const char *u = r->uri + 3;                    // after "/c/"
  char id[13] = {0};
  strlcpy(id, u, sizeof id);
  const char *rest = u + strlen(id);
  std::string path(rest);
  size_t q = path.find('?');
  if (q != std::string::npos) path.resize(q);
  xSemaphoreTake(stateMx, portMAX_DELAY);
  int c = findCtrl(id);
  xSemaphoreGive(stateMx);
  // Unknown here: gone (reset, or the hub was reset); the app offers to remove it. Known but not heard from since the
  // hub started: not answering yet.
  if (c < 0) { httpd_resp_set_status(r, "410 Gone"); return httpd_resp_sendstr(r, "{\"err\":\"not on this hub\"}"); }
  if (!ctrls[c].addrOk) { httpd_resp_set_status(r, "504 Gateway Timeout"); return httpd_resp_sendstr(r, "{\"err\":\"the controller has not checked in yet\"}"); }
  if (r->method == HTTP_POST && path == "/api/update") return hUpload(r, c);
  char type = 0;
  if (r->method == HTTP_GET && path == "/x/hello") type = 'H';
  else if (r->method == HTTP_POST && path == "/x") type = 'X';
  else if (r->method == HTTP_POST && path == "/x/ask") type = 'A';
  else if (r->method == HTTP_POST && path == "/x/recover") type = 'R';      // no owner left: turn a blind to get in
  else if (r->method == HTTP_GET && path == "/x/recstate") type = 'Q';
  // No /x/pair: a controller takes its first owner over Bluetooth only (blinds_matter/main/hub_link.h).
  if (!type) { httpd_resp_set_status(r, "404 Not Found"); return httpd_resp_sendstr(r, "{\"err\":\"not through the hub\"}"); }
  std::string body;
  if (r->method == HTTP_POST) {
    if (r->content_len > 2200) { httpd_resp_set_status(r, "400 Bad Request"); return httpd_resp_sendstr(r, "{\"err\":\"too big\"}"); }
    body.resize(r->content_len);
    size_t got = 0;
    while (got < body.size()) { int n = httpd_req_recv(r, &body[got], body.size() - got); if (n == HTTPD_SOCK_ERR_TIMEOUT) continue; if (n <= 0) return ESP_FAIL; got += n; }
  }
  if (type == 'H') {                             // the hello from memory, while it is still the same start of the controller
    xSemaphoreTake(stateMx, portMAX_DELAY);
    Ctrl &k = ctrls[c];
    std::string h = (!k.hello.empty() && !strcmp(k.helloBoot, k.pushBoot) && ms() - k.seen < 1200000) ? k.hello : "";
    xSemaphoreGive(stateMx);
    if (!h.empty()) { httpd_resp_set_type(r, "application/json"); httpd_resp_set_hdr(r, "Cache-Control", "no-store"); return httpd_resp_send(r, h.data(), h.size()); }
  }
  std::string ans;
  int st = ask(c, type, body, ans, type == 'A' || type == 'R' ? 4000 : 2500);
  httpd_resp_set_status(r, reason(st));
  if (!st) return httpd_resp_sendstr(r, "{\"err\":\"the controller did not answer through the hub\"}");
  httpd_resp_set_type(r, st == 200 && type == 'X' ? "application/octet-stream" : "application/json");
  httpd_resp_set_hdr(r, "Cache-Control", "no-store");
  return httpd_resp_send(r, ans.data(), ans.size());
}
// What the hub knows, for whoever is looking (no keys, no network key).
// The Thread signal of an attached controller, from the hub's list of attached devices (its link-local address is
// fe80:: + its Thread address with the local bit flipped). rssi 127: not attached right now.
static void childSignal(const Ctrl &k, int &rssi, int &lqi) {
  rssi = 127; lqi = 0;
  if (!k.addrOk) return;
  const uint8_t *a = (const uint8_t *)&k.addr.sin6_addr;
  uint8_t ext[8];
  memcpy(ext, a + 8, 8);
  ext[0] ^= 0x02;
  esp_openthread_lock_acquire(portMAX_DELAY);
  otInstance *ot = esp_openthread_get_instance();
  otChildInfo ci;
  for (uint16_t i = 0; i < otThreadGetMaxAllowedChildren(ot); i++)
    if (otThreadGetChildInfoByIndex(ot, i, &ci) == OT_ERROR_NONE && !memcmp(ci.mExtAddress.m8, ext, 8)) { rssi = ci.mAverageRssi; lqi = ci.mLinkQualityIn; }
  esp_openthread_lock_release();
}
static void announceHub();
// ---- what the hub tells its people (inside the secured channel; the public /hub only says "a Tilt Hub, owned or not")
static std::string infoJson() {
  wifi_ap_record_t ap = {};
  int wifiRssi = esp_wifi_sta_get_ap_info(&ap) == ESP_OK ? ap.rssi : 0;
  esp_openthread_lock_acquire(portMAX_DELAY);
  int channel = otLinkGetChannel(esp_openthread_get_instance());
  esp_openthread_lock_release();
  std::string j = "{\"ok\":1,\"hub\":\"tilt\",\"proto\":" + std::to_string(LINK_PROTO) + ",\"fw\":\"" + std::string(esp_app_get_description()->version) + "\",\"up\":" + std::to_string(ms() / 1000) +
                  ",\"ip\":\"" + hubIp() + "\",\"wifi\":" + std::to_string(wifiRssi) + ",\"ch\":" + std::to_string(channel) + ",\"c\":[";
  xSemaphoreTake(stateMx, portMAX_DELAY);
  bool first = true;
  for (int c = 0; c < MAX_CTRL; c++) {
    if (!ctrls[c].used) continue;
    Ctrl &k = ctrls[c];
    int rssi, lqi;
    childSignal(k, rssi, lqi);
    char nums[200];
    snprintf(nums, sizeof nums, ",\"key\":%d,\"seenS\":%ld,\"pct\":%d,\"low\":%d,\"rssi\":%d,\"lqi\":%d,\"ota\":%d,\"otaPct\":%d,\"ep\":[%d,%d,%d]", k.s.keyState, k.seen ? (long)((ms() - k.seen) / 1000) : -1L,
             k.pct, k.low, rssi, lqi, k.otaSt, k.otaPct, k.s.ep[0], k.s.ep[1], k.s.ep[2]);
    std::string tailj = std::string(nums) + (k.otaErr[0] ? ",\"otaErr\":\"" + std::string(k.otaErr) + "\"" : std::string()) +
                        (k.s.keyState ? ",\"hubCid\":\"" + hexOf(k.s.cid, 8) + "\"" : std::string()) +   // the hub's own key on it (its join request)
                        (k.chg >= 0 ? ",\"chg\":" + std::to_string(k.chg) : std::string()) +   // on the charging cable (not said by an older controller)
                        ",\"own\":" + std::to_string(k.own) + "}";                                            // it has an owner (-1 not known)
    j += std::string(first ? "" : ",") + "{\"id\":\"" + std::string(k.s.id, strnlen(k.s.id, 12)) + "\",\"name\":\"" + std::string(k.name, strnlen(k.name, 32)) +
         "\",\"fw\":\"" + std::string(k.fw, strnlen(k.fw, 23)) + "\"" + tailj;
    first = false;
  }
  xSemaphoreGive(stateMx);
  j += "]," + homesJson() + "," + cloudJson() + ",\"heap\":" + std::to_string(esp_get_free_heap_size()) + ",\"heapMin\":" + std::to_string(esp_get_minimum_free_heap_size()) + ",\"new\":[";
  xSemaphoreTake(newMx, portMAX_DELAY);
  first = true;
  for (auto &n : newOnes) {
    if (!n.seen || ms() - n.seen > 300000) continue;
    char line[100];
    snprintf(line, sizeof line, "%s{\"ble\":\"%02x:%02x:%02x:%02x:%02x:%02x\",\"rssi\":%d,\"ageS\":%lu}", first ? "" : ",", n.addr[5], n.addr[4], n.addr[3], n.addr[2], n.addr[1], n.addr[0],
             n.rssi, (unsigned long)((ms() - n.seen) / 1000));
    j += line;
    first = false;
  }
  xSemaphoreGive(newMx);
  return j + "]}";
}
static std::string backupsJson() {
  std::string j = "{\"ok\":1,\"b\":[";
  bool first = true;
  for (int i = 0; i < MAX_BACKUPS; i++) {
    char key[16]; snprintf(key, sizeof key, "bm%d", i);
    BackupMeta m; size_t n = sizeof m;
    if (nvs_get_blob(nv, key, &m, &n) != ESP_OK || n != sizeof m) continue;
    m.name[32] = 0;
    for (char *p = m.name; *p; p++) if (*p == '"' || *p == '\\') *p = '\'';
    j += std::string(first ? "" : ",") + "{\"id\":\"" + m.id + "\",\"name\":\"" + m.name + "\",\"when\":" + std::to_string(m.when) + "}";
    first = false;
  }
  return j + "]}";
}
static std::string backupJson(const char *id) {
  int i = backupSlot(id, false);
  if (i < 0) return "{\"ok\":0,\"err\":\"no backup of that controller\"}";
  char key[16]; snprintf(key, sizeof key, "bk%d", i);
  static uint8_t blob[2048];
  size_t n = sizeof blob;
  if (nvs_get_blob(nv, key, blob, &n) != ESP_OK) return "{\"ok\":0,\"err\":\"no backup\"}";
  return "{\"ok\":1,\"d\":\"" + hexOf(blob, n) + "\"}";
}
// A new controller takes the place of an old one: its Apple Home tiles move over (Home keeps the same blinds, rooms
// and automations). Only for a controller the hub met in the last 15 minutes.
static std::string replaceJson(const char *o, const char *n2) {
  xSemaphoreTake(stateMx, portMAX_DELAY);
  int a = findCtrl(o), b = findCtrl(n2);
  const char *why = a < 0 || b < 0 || a == b ? "unknown controller" : !ctrls[b].firstSeen || ms() - ctrls[b].firstSeen > 900000 ? "only just after setup" : nullptr;
  if (!why) {
    for (int p = 0; p < PORTS; p++) {
      if (ctrls[b].s.ep[p]) { endpoint_t *e = endpoint::get(gNode, ctrls[b].s.ep[p]); if (e) endpoint::destroy(gNode, e); }
      ctrls[b].s.ep[p] = ctrls[a].s.ep[p]; ctrls[b].tileLift[p] = ctrls[b].tileOp[p] = -1; ctrls[b].tileLabel[p][0] = 0;
    }
    ctrls[b].s.sep = ctrls[a].s.sep;
    memset(&ctrls[a].s, 0, sizeof ctrls[a].s);
    ctrls[a].used = false; ctrls[a].addrOk = false;
    saveCtrls();
    ESP_LOGI(TAG, "%s replaces %s (Home tiles moved)", n2, o);
  }
  xSemaphoreGive(stateMx);
  if (why) return std::string("{\"ok\":0,\"err\":\"") + why + "\"}";
  if (matterUp) chip::DeviceLayer::PlatformMgr().ScheduleWork(applyStatus, (intptr_t)b);
  return "{\"ok\":1}";
}
static std::string netJson() {
  esp_openthread_lock_acquire(portMAX_DELAY);
  otOperationalDatasetTlvs tlv;
  bool ok = otDatasetGetActiveTlvs(esp_openthread_get_instance(), &tlv) == OT_ERROR_NONE;
  esp_openthread_lock_release();
  if (!ok) return "{\"ok\":0,\"err\":\"no Thread network\"}";
  return "{\"ok\":1,\"ds\":\"" + hexOf(tlv.mTlvs, tlv.mLength) + "\"}";
}

static std::string qv(const std::string &q, const char *key) {
  char v[300] = "";
  return httpd_query_key_value(q.c_str(), key, v, sizeof v) == ESP_OK ? std::string(v) : std::string();
}
// One command from a phone that is in. Owner-only unless said otherwise.
static std::string hubCommand(int slot, const std::string &cmd) {
  size_t qi = cmd.find('?');
  std::string path = cmd.substr(0, qi), q = qi == std::string::npos ? "" : cmd.substr(qi + 1);
  bool owner = people.keys[slot].role == 1;
  if (const char *why = hubPermit(path, owner ? HUB_OWNER : HUB_USER)) return std::string("{\"ok\":0,\"err\":\"") + why + "\"}";
  if (path == "/api/info") {                    // owners also get the hub's alert name (their phones watch it for its pushes)
    std::string j = infoJson();
    return owner ? "{\"topic\":\"" + hexOf(htopic, 16) + "\"," + j.substr(1) : j;
  }
  if (path == "/api/keys") {                     // the hub's people (as a controller lists its phones)
    xSemaphoreTake(keyMx, portMAX_DELAY);
    std::string j = "{\"ok\":1,\"keys\":[";
    bool first = true;
    for (int i = 0; i < HUB_KEYS; i++) {
      HubKey &k = people.keys[i];
      if (!k.used) continue;
      j += std::string(first ? "" : ",") + "{\"cid\":\"" + hexOf(k.id, 8) + "\",\"name\":\"" + k.name + "\",\"owner\":" + (k.role ? "1" : "0") + ",\"me\":" + (i == slot ? "1" : "0") +
           ",\"wait\":" + (k.used == 2 ? "1" : "0") + ",\"code\":\"" + (k.used == 2 && owner ? askCode(k.key) : std::string()) + "\"}";   // the code: owners only
      first = false;
    }
    xSemaphoreGive(keyMx);
    return j + "]}";
  }
  if (path == "/api/leave") {                    // this phone leaves the hub (everywhere, not just on the phone)
    xSemaphoreTake(keyMx, portMAX_DELAY);
    PeopleResult res = people.apply(PO_LEAVE, slot);
    xSemaphoreGive(keyMx);
    if (res.err) return std::string("{\"ok\":0,\"err\":\"") + res.err + "\"}";
    ESP_LOGI(TAG, "%s left the hub", res.name);
    announceHub();                               // no owner left: it says so (a new person can connect)
    return "{\"ok\":1}";
  }
  if (path == "/api/light") {                    // test: which light is which on this board (lights.h). For a minute.
    lightTestUntil = (ms() + 60000) | 1;
    std::string l = qv(q, "l");
    if (l == "15") { gpio_set_level(GPIO_NUM_15, qv(q, "v") == "1" ? 1 : 0); return "{\"ok\":1}"; }
    if (l == "8") { rgbSet(atoi(qv(q, "r").c_str()), atoi(qv(q, "g").c_str()), atoi(qv(q, "b").c_str())); return "{\"ok\":1}"; }
    return "{\"ok\":0,\"err\":\"l=15&v=0|1 or l=8&r=&g=&b=\"}";
  }
  if (path == "/api/resetpeople") {              // forget every phone: the next one to connect becomes the owner.
    xSemaphoreTake(keyMx, portMAX_DELAY);        // (Its controllers, their Home tiles and Apple Home stay.)
    people.apply(PO_RESET, slot);
    xSemaphoreGive(keyMx);
    ESP_LOGW(TAG, "people reset: waiting for a new owner");
    announceHub();
    return "{\"ok\":1}";
  }
  if (path == "/api/approve" || path == "/api/revoke" || path == "/api/makeowner") {
    uint8_t id[8];
    if (!unhex(qv(q, "cid").c_str(), id, 8)) return "{\"ok\":0,\"err\":\"bad id\"}";
    PeopleOp op = path == "/api/approve" ? (qv(q, "ok") == "1" ? PO_APPROVE : PO_DENY)
                : path == "/api/makeowner" ? (qv(q, "on") == "1" ? PO_MAKEOWNER : PO_UNOWNER) : PO_REVOKE;
    xSemaphoreTake(keyMx, portMAX_DELAY);
    PeopleResult res = people.apply(op, slot, id, qv(q, "owner") == "1");
    xSemaphoreGive(keyMx);
    if (res.err) return std::string("{\"ok\":0,\"err\":\"") + res.err + "\"}";
    if (op == PO_APPROVE) ESP_LOGI(TAG, "%s let into the hub", res.name);
    return "{\"ok\":1}";
  }
  if (path == "/api/net") return netJson();
  if (path == "/api/mem" && owner) {             // where the memory goes: free, biggest block, and each task's stack low point
    multi_heap_info_t h; heap_caps_get_info(&h, MALLOC_CAP_INTERNAL);
    std::string j = "{\"ok\":1,\"free\":" + std::to_string(h.total_free_bytes) + ",\"big\":" + std::to_string(h.largest_free_block) +
                    ",\"used\":" + std::to_string(h.total_allocated_bytes) + ",\"min\":" + std::to_string(h.minimum_free_bytes) +
                    ",\"blocks\":" + std::to_string(h.allocated_blocks) + ",\"tasks\":{";
    UBaseType_t n = uxTaskGetNumberOfTasks() + 4;
    TaskStatus_t *t = (TaskStatus_t *)malloc(n * sizeof(TaskStatus_t));
    if (t) {
      n = uxTaskGetSystemState(t, n, nullptr);
      for (UBaseType_t i = 0; i < n; i++)
        j += std::string(i ? "," : "") + "\"" + t[i].pcTaskName + "\":" + std::to_string(t[i].usStackHighWaterMark);
      free(t);
    }
    return j + "}}";
  }
  if (path == "/api/testalert") { alertRaise(htopic, "test", 9, "Tilt Hub"); return "{\"ok\":1}"; }   // a push to the hub's owners, to try the path
  if (path == "/api/hubupdate") { hubUpdUntil = (ms() + 300000) | 1; return "{\"ok\":1}"; }   // one hub update, 5 minutes
  if (path == "/api/upload") {                   // allow one firmware upload for this controller, for 5 minutes
    xSemaphoreTake(stateMx, portMAX_DELAY);
    int c = findCtrl(qv(q, "id").c_str());
    if (c >= 0) uploadUntil[c] = (ms() + 300000) | 1;
    xSemaphoreGive(stateMx);
    return c >= 0 ? "{\"ok\":1}" : "{\"ok\":0,\"err\":\"no such controller\"}";
  }
  if (path == "/api/homecode" && matterUp) {      // open Apple Home's pairing now (Apple's add screen comes next)
    // Also when the hub still counts a home: the owner asked, and that home may be gone (removed in its own app
    // without the hub hearing of it). Matter allows a hub in several homes. The automatic window (above) stays for a
    // hub in no home only. The check and the window change happen in one go (under the lock), so the code given is
    // always the one the window takes.
    chip::DeviceLayer::PlatformMgr().LockChipStack();
    auto &mgr = chip::Server::GetInstance().GetCommissioningWindowManager();
    bool busy = homeBeingAdded();
    if (!busy) {
      // A window open for an Alexa code takes only that code: swap it for one that takes the hub's own code.
      if (mgr.IsCommissioningWindowOpen() && shareUntil && (int32_t)(shareUntil - ms()) > 0) { mgr.CloseCommissioningWindow(); shareUntil = 0; }
      if (!mgr.IsCommissioningWindowOpen())
        mgr.OpenBasicCommissioningWindow(chip::System::Clock::Seconds16(900), chip::CommissioningWindowAdvertisement::kAllSupported);
    }
    chip::DeviceLayer::PlatformMgr().UnlockChipStack();
    if (busy) return BUSY_JSON;
    homeWindowUntil = (ms() + 900000) | 1;
  }
  if (path == "/api/homecode") return "{\"ok\":1,\"code\":\"" + homeManual + "\",\"qr\":\"" + homeQr + "\"," + homesJson() + "}";
  if (path == "/api/sharecode") return shareCodeJson();   // a one-time code for a second home app (Alexa)
  if (path == "/api/backups") return backupsJson();
  if (path == "/api/backup") return backupJson(qv(q, "id").c_str());
  if (path == "/api/replace") return replaceJson(qv(q, "old").c_str(), qv(q, "new").c_str());
  return "{\"ok\":0,\"err\":\"unknown command\"}";
}

static std::string helloJson() {
  return "{\"id\":\"" + hubId() + "\",\"name\":\"Tilt Hub\",\"fw\":\"" + std::string(esp_app_get_description()->version) + "\",\"boot\":\"" + hexOf(hboot, 4) +
         "\",\"owned\":" + (hubOwned() ? "1" : "0") + ",\"kind\":\"hub\",\"proto\":" + std::to_string(LINK_PROTO) + "}";
}
static esp_err_t sendStatus(httpd_req_t *r, int st, const std::string &body, bool binary = false) {
  httpd_resp_set_status(r, reason(st));
  httpd_resp_set_type(r, binary ? "application/octet-stream" : "application/json");
  httpd_resp_set_hdr(r, "Cache-Control", "no-store");
  return httpd_resp_send(r, body.data(), body.size());
}
static bool readBody(httpd_req_t *r, std::string &b, size_t max) {
  if (r->content_len > max) return false;
  b.resize(r->content_len);
  size_t got = 0;
  while (got < b.size()) { int n = httpd_req_recv(r, &b[got], b.size() - got); if (n == HTTPD_SOCK_ERR_TIMEOUT) continue; if (n <= 0) return false; got += n; }
  return true;
}
static esp_err_t hHello(httpd_req_t *r) { return sendStatus(r, 200, helloJson()); }
static esp_err_t hPair(httpd_req_t *r) { std::string b, out; if (!readBody(r, b, 600)) return sendStatus(r, 400, "{\"err\":\"bad request\"}"); return sendStatus(r, pairDo(b, out, false), out); }
static esp_err_t hAsk(httpd_req_t *r) { std::string b, out; if (!readBody(r, b, 600)) return sendStatus(r, 400, "{\"err\":\"bad request\"}"); return sendStatus(r, pairDo(b, out, true), out); }
static esp_err_t hSecure(httpd_req_t *r) { std::string b, out; if (!readBody(r, b, 2200)) return sendStatus(r, 400, "{\"err\":\"bad request\"}"); int st = secDo(b, out); return sendStatus(r, st, out, st == 200); }
// GET /hub: public, so a phone can tell a new hub from one that has an owner. Nothing more.
static esp_err_t hInfo(httpd_req_t *r) { return sendStatus(r, 200, "{\"hub\":\"tilt\",\"id\":\"" + hubId() + "\",\"owned\":" + (hubOwned() ? "1" : "0") + "}"); }
static void httpBegin() {
  httpd_config_t hc = HTTPD_DEFAULT_CONFIG();
  hc.uri_match_fn = httpd_uri_match_wildcard;
  hc.stack_size = 6144;                         // uses about 2 KB (/api/mem)
  hc.lru_purge_enable = true;
  hc.max_open_sockets = 5;
  hc.max_uri_handlers = 12;
  hc.recv_wait_timeout = 30;                     // a firmware file can be slow to arrive
  httpd_handle_t srv = nullptr;
  if (httpd_start(&srv, &hc) != ESP_OK) { ESP_LOGE(TAG, "web server did not start"); return; }
  httpd_uri_t u[] = {{"/c/*", HTTP_GET, hRelay, nullptr}, {"/c/*", HTTP_POST, hRelay, nullptr}, {"/hub", HTTP_GET, hInfo, nullptr},
                     {"/hub/x/hello", HTTP_GET, hHello, nullptr}, {"/hub/x/pair", HTTP_POST, hPair, nullptr}, {"/hub/x/ask", HTTP_POST, hAsk, nullptr},
                     {"/hub/x", HTTP_POST, hSecure, nullptr}, {"/hub/api/update", HTTP_POST, hHubUpdate, nullptr}};
  for (auto &x : u) httpd_register_uri_handler(srv, &x);
}

// ---- a one-time code for another home app (Alexa, Google Home, SmartThings), issue #18
// Matter lets a device be in several homes. A hub already in one gets the next by an "enhanced" pairing window: a
// fresh random code, good for 15 minutes and one home, over the home Wi-Fi only (Apple Home's "Turn On Pairing Mode"
// does the same). Every Matter home app must take this kind of code. A hub in no home yet gives its own code, opened
// as for Apple Home (Bluetooth too, so the app can give it Wi-Fi). Asking again while a code is still good gives
// the same code, so a second tap does not break the first.
static std::string shareCodeJson() {
  if (!matterUp) return "{\"ok\":0,\"err\":\"the hub's Matter is not running yet: try again in a minute\"}";
  chip::DeviceLayer::PlatformMgr().LockChipStack();
  auto &srv = chip::Server::GetInstance();
  auto &mgr = srv.GetCommissioningWindowManager();
  bool homed = srv.GetFabricTable().FabricCount() > 0;
  bool same = homed && shareUntil && (int32_t)(shareUntil - ms()) > 60000 && mgr.IsCommissioningWindowOpen();
  bool busy = homeBeingAdded();
  chip::DeviceLayer::PlatformMgr().UnlockChipStack();
  if (busy && !same) return BUSY_JSON;            // its window stays; the code still good is given (same) as before
  if (!homed) {                                  // the first home: the hub's own code (like /api/homecode)
    homeWindowUntil = (ms() + 900000) | 1;
    chip::DeviceLayer::PlatformMgr().ScheduleWork([](intptr_t) {
      auto &m = chip::Server::GetInstance().GetCommissioningWindowManager();
      if (!m.IsCommissioningWindowOpen()) m.OpenBasicCommissioningWindow(chip::System::Clock::Seconds16(900), chip::CommissioningWindowAdvertisement::kAllSupported);
    }, 0);
    return "{\"ok\":1,\"code\":\"" + homeManual + "\",\"qr\":\"" + homeQr + "\",\"mins\":15,\"first\":1," + homesJson() + "}";
  }
  if (!same) {
    uint32_t pin;
    uint16_t disc;
    uint8_t salt[32];
    do esp_fill_random(&pin, sizeof pin); while (!setupPinValid(pin %= 100000000));   // the radio is on: true random
    esp_fill_random(&disc, sizeof disc);
    disc &= 0xFFF;
    esp_fill_random(salt, sizeof salt);
    chip::Crypto::Spake2pVerifier v;
    if (v.Generate(1000, chip::ByteSpan(salt), pin) != CHIP_NO_ERROR) return "{\"ok\":0,\"err\":\"could not make a code\"}";
    chip::DeviceLayer::PlatformMgr().LockChipStack();
    chip::FabricIndex fi = chip::kUndefinedFabricIndex;
    chip::VendorId vid = chip::VendorId::Common;
    for (const auto &f : srv.GetFabricTable()) { fi = f.GetFabricIndex(); vid = f.GetVendorId(); break; }   // "opened by": its first home
    if (homeBeingAdded()) { chip::DeviceLayer::PlatformMgr().UnlockChipStack(); return BUSY_JSON; }   // began just now
    mgr.CloseCommissioningWindow();             // a window still open (the start-up one, an older code) goes
    CHIP_ERROR e = mgr.OpenEnhancedCommissioningWindow(chip::System::Clock::Seconds32(900), disc, v, 1000, chip::ByteSpan(salt), fi, vid);
    chip::DeviceLayer::PlatformMgr().UnlockChipStack();
    if (e != CHIP_NO_ERROR) { ESP_LOGE(TAG, "share window: %" CHIP_ERROR_FORMAT, e.Format()); return "{\"ok\":0,\"err\":\"the hub could not open pairing\"}"; }
    chip::PayloadContents p;
    p.vendorID = CONFIG_DEVICE_VENDOR_ID;
    p.productID = CONFIG_DEVICE_PRODUCT_ID;
    p.rendezvousInformation.Emplace(chip::RendezvousInformationFlag::kOnNetwork);
    p.discriminator.SetLongValue(disc);
    p.setUpPINCode = pin;
    char manual[chip::kManualSetupLongCodeCharLength + 1], qr[chip::QRCodeBasicSetupPayloadGenerator::kMaxQRCodeBase38RepresentationLength + 1];
    chip::MutableCharSpan m(manual), q(qr);
    if (chip::ManualSetupPayloadGenerator(p).payloadDecimalStringRepresentation(m) != CHIP_NO_ERROR ||
        chip::QRCodeBasicSetupPayloadGenerator(p).payloadBase38Representation(q) != CHIP_NO_ERROR)
      return "{\"ok\":0,\"err\":\"could not make a code\"}";
    shareManual = manualCodeDashed(std::string(m.data(), m.size()));
    shareQr.assign(q.data(), q.size());
    shareUntil = (ms() + 900000) | 1;
    ESP_LOGI(TAG, "pairing open for another home app for 15 minutes");
  }
  int mins = (int)(((int32_t)(shareUntil - ms())) / 60000);
  return "{\"ok\":1,\"code\":\"" + shareManual + "\",\"qr\":\"" + shareQr + "\",\"mins\":" + std::to_string(mins < 1 ? 1 : mins) + "," + homesJson() + "}";
}
