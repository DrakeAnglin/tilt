// The ESP side of updates (the file checks are hub_file.h): a controller's firmware through the hub over Thread,
// and the hub's own firmware over Wi-Fi. Part of hub.cpp.
#pragma once
// ---- a controller's firmware through the hub: the app uploads the signed file here (fast, Wi-Fi), the hub keeps it
// in its staging area and feeds it to the controller over Thread (protocol: blinds_matter/main/hub_link.h).
// The hub's spare firmware slot: a controller's file is kept here while it is sent, and the hub's own next firmware
// is written here. (So nothing else uses it while the hub tries new firmware: then it is the way back.)
static const esp_partition_t *stage;
static uint32_t stageSize;
static bool stageDelta;                           // the staged file is a patch (blinds_matter/main/hub_link.h)
static uint32_t pieceBytes = 480, piecesInFlight = 6;   // piece size and pieces in flight (?ch=&win= on the upload, for tuning). Measured: 480 x 6 is about 4 KB/s; 960 x 8 lost most pieces
static uint32_t uploadUntil[MAX_CTRL];           // an owner allowed an upload for this controller (sealed /api/upload)
static void otaFail(Ctrl &k, const char *why) { k.otaSt = OTA_FAILED; cleanName(k.otaErr, sizeof k.otaErr, why); ESP_LOGW(TAG, "%s: update failed: %s", k.s.id, why); alertUpdateFailed((int)(&k - ctrls), why); }
static void otaTask(void *arg) {
  int c = (int)(intptr_t)arg;
  Ctrl &k = ctrls[c];
  uint32_t CH = pieceBytes, WIN = piecesInFlight;               // a controller that keeps its radio on takes big pieces
  std::string ans;
  if (ctrlCommand(c, "/api/s").empty()) { otaFail(k, "the controller did not answer"); otaFor = -1; vTaskDelete(nullptr); return; }   // fresh boot id
  uint8_t link[32];
  std::string sz = std::to_string(stageSize) + (stageDelta ? ",d" : "") + "@" + std::to_string((long)time(nullptr)), mac = linkOf(c, link) ? links[c].proofNow(link, Proof::HubOta, sz) : "";
  if (mac.empty()) { otaFail(k, "the hub has no key on this controller yet"); otaFor = -1; vTaskDelete(nullptr); return; }
  int st = ask(c, 'B', sz + "." + mac, ans, 45000);   // an older controller erases its whole slot first
  if (st != 200) { otaFail(k, st == 403 ? "updates are locked (allow them first)" : st ? "the controller refused to start" : "no answer"); otaFor = -1; vTaskDelete(nullptr); return; }
  xQueueReset(otaAcks);
  uint32_t acked = 0, next = 0, misses = 0, t0 = ms(), moved = ms();
  static uint8_t pkt[3 + 4 + 1200];
  while (acked < stageSize && misses < 25 && ms() - moved < 120000) {
    while (next < stageSize && next < acked + WIN * CH) {
      uint32_t n = stageSize - next < CH ? stageSize - next : CH;
      pkt[0] = 'W'; pkt[1] = 0; pkt[2] = 0;
      pkt[3] = next >> 24; pkt[4] = next >> 16; pkt[5] = next >> 8; pkt[6] = next;
      esp_partition_read(stage, next, pkt + 7, n);
      sendto(sock, pkt, 7 + n, 0, (sockaddr *)&k.addr, sizeof k.addr);
      next += n;
    }
    OtaAck a;
    if (xQueueReceive(otaAcks, &a, pdMS_TO_TICKS(2500)) != pdTRUE) {
      if (acked == 0 && misses >= 1 && CH > 80) { CH = 80; WIN = 8; ESP_LOGW(TAG, "%s: small pieces (older controller)", k.s.id); }
      misses++; ESP_LOGW(TAG, "%s: no answer to pieces (%lu)", k.s.id, (unsigned long)misses); next = acked; continue; }   // nothing back: again from the last good place
    misses = 0;
    static uint32_t logged = 0;
    if (a.next / 50000 != logged / 50000 || !a.ok) ESP_LOGI(TAG, "%s: piece answer %s at %lu", k.s.id, a.ok ? "ok" : "MISSED", (unsigned long)a.next);
    logged = a.next;
    if (!a.num) { otaFail(k, "the controller dropped the update"); otaFor = -1; vTaskDelete(nullptr); return; }
    if (a.next > acked) { acked = a.next; moved = ms(); }
    if (!a.ok) {                                 // it missed a piece: go back to where it is
      next = a.next;
      static uint32_t lost = 0;
      if (++lost >= 12 && CH > 240) { lost = 0; CH /= 2; ESP_LOGW(TAG, "%s: many pieces lost, smaller pieces (%lu bytes)", k.s.id, (unsigned long)CH); }
    }
    k.otaPct = (int)(100ULL * acked / stageSize);
  }
  if (acked < stageSize) { otaFail(k, "the controller stopped answering"); otaFor = -1; vTaskDelete(nullptr); return; }
  k.otaSt = OTA_CHECKING;
  ESP_LOGI(TAG, "%s: %lu bytes sent in %lu s, checking", k.s.id, (unsigned long)stageSize, (unsigned long)((ms() - t0) / 1000));
  st = ask(c, 'E', "", ans, 15000);
  if (st != 200) { cJSON *j = cJSON_Parse(ans.c_str()); const char *e = j ? cJSON_GetStringValue(cJSON_GetObjectItem(j, "err")) : nullptr; otaFail(k, e ? e : "the controller did not take it"); if (j) cJSON_Delete(j); }
  else { k.otaSt = OTA_DONE; k.otaPct = 100; links[c].forgetBoot(); ESP_LOGI(TAG, "%s: update accepted, it restarts", k.s.id); }
  otaFor = -1;
  vTaskDelete(nullptr);
}
// The update-file checks (hub_file.h) read the staging partition as it was written.
struct PartReader : ByteReader {
  const esp_partition_t *p;
  explicit PartReader(const esp_partition_t *part) : p(part) {}
  void read(uint32_t off, void *buf, uint32_t n) override { esp_partition_read(p, off, buf, n); }
};
static_assert(offsetof(esp_app_desc_t, magic_word) == 0 && offsetof(esp_app_desc_t, version) == 16 && offsetof(esp_app_desc_t, project_name) == 48 &&
              sizeof(((esp_app_desc_t *)0)->version) == 32 && sizeof(((esp_app_desc_t *)0)->project_name) == 32 && ESP_APP_DESC_MAGIC_WORD == APP_DESC_MAGIC,
              "hub_file.h reads the app description at these places");
// The file in the staging area, for controller k (hub_file.h).
static const char *stageCheck(const Ctrl &k) {
  PartReader rd(stage);
  return stageCheck(rd, stageSize, k.fw, FW_SIGN_PUB, stageDelta);
}
// ---- the hub's own firmware, over Wi-Fi: POST /hub/api/update, in the 5 minutes after its owner allowed it (sealed
// /api/hubupdate). The signed file goes into the spare slot; the hub checks the signature and that it is not older,
// then starts it on trial. Kept once Wi-Fi and Apple Home have worked for a minute; otherwise it goes back by itself.
// With no firmware to go back to, it stays on the new one, still on trial.
static uint32_t hubUpdUntil = 0;
static bool cloudBusy() {                        // a firmware file is coming in or going out: no TLS meanwhile (memory)
  if (otaFor >= 0 || (hubUpdUntil && (int32_t)(hubUpdUntil - ms()) > 0)) return true;
  for (auto u : uploadUntil) if (u && (int32_t)(u - ms()) > 0) return true;
  return false;
}
static esp_err_t hHubUpdate(httpd_req_t *r) {
  auto no = [&](const char *st, const char *why) { httpd_resp_set_status(r, st); return httpd_resp_sendstr(r, (std::string("{\"ok\":0,\"err\":\"") + why + "\"}").c_str()); };
  if (!hubUpdUntil || (int32_t)(ms() - hubUpdUntil) > 0) return no("403 Forbidden", "the Tilt Hub's owner has to allow this update first");
  if (hubTrial) return no("409 Conflict", "the hub is still trying the last update");
  if (otaFor >= 0) return no("409 Conflict", "the hub is updating a controller");
  if (!stage || r->content_len < 100000 || r->content_len > stage->size) return no("400 Bad Request", "that is not a hub firmware file");
  hubUpdUntil = 0;
  otaFor = MAX_CTRL;                             // nothing else writes the spare slot meanwhile
  esp_partition_erase_range(stage, 0, (r->content_len + 4095) & ~4095u);
  static char buf[4096];
  uint32_t got = 0;
  while (got < r->content_len) {
    int n = httpd_req_recv(r, buf, sizeof buf);
    if (n == HTTPD_SOCK_ERR_TIMEOUT) continue;
    if (n <= 0) { otaFor = -1; return ESP_FAIL; }
    esp_partition_write(stage, got, buf, n);
    got += n;
  }
  otaFor = -1;
  PartReader rd(stage);
  const char *why = nullptr;
  char version[32];
  if (int st = hubFileCheck(rd, got, esp_app_get_description()->version, FW_SIGN_PUB, why, version)) return no(st == 400 ? "400 Bad Request" : "403 Forbidden", why);
  if (esp_ota_set_boot_partition(stage) != ESP_OK) return no("500 Internal Server Error", "the file was not accepted");
  ESP_LOGW(TAG, "hub firmware %s accepted: restarting", version);
  httpd_resp_set_type(r, "application/json");
  httpd_resp_sendstr(r, (std::string("{\"ok\":1,\"fw\":\"") + version + "\"}").c_str());
  xTaskCreate([](void *) { vTaskDelay(pdMS_TO_TICKS(1500)); esp_restart(); }, "restart", 2048, nullptr, 3, nullptr);
  return ESP_OK;
}
// POST /c/<id>/api/update: the signed file. Only just after the hub's owner allowed it (sealed /api/upload?id=), so
// nobody else on the Wi-Fi can fill the hub or keep a controller busy. Answers once it is stored and checked; the
// progress is in /hub ("ota").
static esp_err_t hUpload(httpd_req_t *r, int c) {
  if (hubTrial) { httpd_resp_set_status(r, "409 Conflict"); return httpd_resp_sendstr(r, "{\"ok\":0,\"err\":\"the Tilt Hub is trying its own new firmware: try again in a few minutes\"}"); }
  if (!uploadUntil[c] || (int32_t)(ms() - uploadUntil[c]) > 0) { httpd_resp_set_status(r, "403 Forbidden"); return httpd_resp_sendstr(r, "{\"ok\":0,\"err\":\"the Tilt Hub's owner has to allow this update first\"}"); }
  if (!stage) { httpd_resp_set_status(r, "500 Internal Server Error"); return httpd_resp_sendstr(r, "{\"ok\":0,\"err\":\"the hub has no room for firmware\"}"); }
  if (otaFor >= 0) { httpd_resp_set_status(r, "409 Conflict"); return httpd_resp_sendstr(r, "{\"ok\":0,\"err\":\"the hub is updating another controller\"}"); }
  if (r->content_len < 1000 || r->content_len > stage->size) { httpd_resp_set_status(r, "400 Bad Request"); return httpd_resp_sendstr(r, "{\"ok\":0,\"err\":\"that is not a firmware file\"}"); }
  char q[64], v[12];
  pieceBytes = 480; piecesInFlight = 6;
  if (httpd_req_get_url_query_str(r, q, sizeof q) == ESP_OK) {
    if (httpd_query_key_value(q, "ch", v, sizeof v) == ESP_OK) pieceBytes = constrain_u(atoi(v), 32, 1200);
    if (httpd_query_key_value(q, "win", v, sizeof v) == ESP_OK) piecesInFlight = constrain_u(atoi(v), 1, 16);
  }
  otaFor = c;
  uploadUntil[c] = 0;                              // one upload per allowance
  esp_partition_erase_range(stage, 0, (r->content_len + 4095) & ~4095u);
  static char buf[4096];
  uint32_t got = 0;
  while (got < r->content_len) {
    int n = httpd_req_recv(r, buf, sizeof buf);
    if (n == HTTPD_SOCK_ERR_TIMEOUT) continue;
    if (n <= 0) { otaFor = -1; return ESP_FAIL; }
    esp_partition_write(stage, got, buf, n);
    got += n;
  }
  stageSize = got;
  Ctrl &k = ctrls[c];
  if (const char *why = stageCheck(k)) {
    otaFor = -1;
    ESP_LOGW(TAG, "%s: upload refused: %s", k.s.id, why);
    httpd_resp_set_status(r, "403 Forbidden");
    return httpd_resp_sendstr(r, (std::string("{\"ok\":0,\"err\":\"") + why + "\"}").c_str());
  }
  k.otaSt = OTA_SENDING; k.otaPct = 0; k.otaErr[0] = 0;
  xTaskCreate(otaTask, "ota", 6144, (void *)(intptr_t)c, 5, nullptr);
  ESP_LOGI(TAG, "%s: firmware stored (%lu bytes), sending it over Thread", k.s.id, (unsigned long)got);
  httpd_resp_set_type(r, "application/json");
  return httpd_resp_sendstr(r, "{\"ok\":1,\"hub\":1}");
}
