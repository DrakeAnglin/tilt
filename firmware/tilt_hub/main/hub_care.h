// The Tilt Hub's slow housekeeping: settings backups of each controller, the care task (every few seconds), and new
// controllers nearby on Bluetooth. Part of hub.cpp.
#pragma once
// Every few seconds: ask to join any controller the hub has no key for, and mark quiet ones not responding.
static std::string hubIp();
static void bleScan();
static std::string ctrlCommand(int c, const std::string &cmd);
// ---- settings backups: one per controller id (also after it is gone: that is when it is needed). In flash:
// "bm<n>" = BackupMeta, "bk<n>" = the controller's backup blob (blinds_matter/main/hub_link.h backupBlob).
struct BackupMeta { char id[13]; char name[33]; uint32_t cv, when; };
const int MAX_BACKUPS = 8;
static int backupSlot(const char *id, bool make) {
  int freeSlot = -1;
  for (int i = 0; i < MAX_BACKUPS; i++) {
    char key[16]; snprintf(key, sizeof key, "bm%d", i);
    BackupMeta m; size_t n = sizeof m;
    if (nvs_get_blob(nv, key, &m, &n) == ESP_OK && n == sizeof m) { if (!strcmp(m.id, id)) return i; }
    else if (freeSlot < 0) freeSlot = i;
  }
  return make ? (freeSlot >= 0 ? freeSlot : 0) : -1;
}
static uint32_t backupCv(const char *id) {
  int i = backupSlot(id, false);
  if (i < 0) return 0;
  char key[16]; snprintf(key, sizeof key, "bm%d", i);
  BackupMeta m; size_t n = sizeof m;
  return nvs_get_blob(nv, key, &m, &n) == ESP_OK ? m.cv : 0;
}
static void takeBackup(int c) {                  // with the hub's own key (a Guest may read the backup)
  std::string r = ctrlCommand(c, "/api/backup");
  cJSON *j = r.empty() ? nullptr : cJSON_Parse(r.c_str());
  const char *d = j ? cJSON_GetStringValue(cJSON_GetObjectItem(j, "d")) : nullptr;
  cJSON *cvj = j ? cJSON_GetObjectItem(j, "cv") : nullptr;
  if (d && cJSON_IsNumber(cvj) && strlen(d) % 2 == 0 && strlen(d) / 2 <= 2048) {
    std::string blob(strlen(d) / 2, 0);
    if (unhex(d, (uint8_t *)&blob[0], blob.size())) {
      int i = backupSlot(ctrls[c].s.id, true);
      BackupMeta m = {};
      strlcpy(m.id, ctrls[c].s.id, sizeof m.id); strlcpy(m.name, ctrls[c].name, sizeof m.name);
      m.cv = (uint32_t)cvj->valuedouble; m.when = time(nullptr) > 1700000000 ? (uint32_t)time(nullptr) : 0;   // 0: the clock was not set yet
      char key[16];
      snprintf(key, sizeof key, "bk%d", i); nvs_set_blob(nv, key, blob.data(), blob.size());
      snprintf(key, sizeof key, "bm%d", i); nvs_set_blob(nv, key, &m, sizeof m);
      nvs_commit(nv);
      ESP_LOGI(TAG, "%s: settings backed up (%u bytes)", m.id, (unsigned)blob.size());
    }
  }
  if (j) cJSON_Delete(j);
}
static void careTask(void *) {
  vTaskDelay(pdMS_TO_TICKS(20000));
  if (hubIp() == "0.0.0.0") {                      // no Wi-Fi after 20 s: show what the hub can see (USB log)
    esp_wifi_disconnect();
    wifi_scan_config_t sc = {};
    sc.show_hidden = true;
    if (esp_wifi_scan_start(&sc, true) == ESP_OK) {
      uint16_t n = 20;
      static wifi_ap_record_t aps[20];
      esp_wifi_scan_get_ap_records(&n, aps);
      ESP_LOGW(TAG, "no Wi-Fi: %d networks in range", n);
      for (int i = 0; i < n; i++) ESP_LOGW(TAG, "  '%s' channel %d %d dBm", (const char *)aps[i].ssid, aps[i].primary, aps[i].rssi);
    } else ESP_LOGW(TAG, "no Wi-Fi, and the scan did not start");
    esp_wifi_connect();
  }
  for (;;) {
    vTaskDelay(pdMS_TO_TICKS(ms() < 90000 ? 5000 : 15000));   // quicker just after a start: find the controllers again
    // New hub firmware: kept once Wi-Fi and Apple Home are up for a minute; back to the one before when they are not
    // up 5 minutes after the start (trial.h). Going back refused (no valid firmware in the other slot): it asks once,
    // logs it once and stays on this firmware, still on trial, still kept the normal way if both come up later.
    if (hubTrial) {
      static Trial trial;
      TrialVerdict v = trial.tick(ms(), hubIp() != "0.0.0.0" && matterUp, true);
      if (v == TRIAL_KEEP) { esp_ota_mark_app_valid_cancel_rollback(); hubTrial = false; ESP_LOGI(TAG, "new hub firmware %s kept", esp_app_get_description()->version); }
      else if (v == TRIAL_ROLLBACK) {
        ESP_LOGE(TAG, "new hub firmware did not get Wi-Fi and Apple Home up: going back");
        vTaskDelay(pdMS_TO_TICKS(200));
        esp_err_t e = esp_ota_mark_app_invalid_rollback_and_reboot();   // returns only when refused
        trial.rollbackRefused();
        ESP_LOGE(TAG, "cannot go back (%s): staying on this firmware", esp_err_to_name(e));
      }
    }
    static uint32_t lastScan = 0;
    if (ms() - lastScan > 30000) { lastScan = ms(); bleScan(); }
    // Not in a home yet: Apple Home can add the hub in its first 15 minutes after power-on, and for 15 minutes after the
    // owner opens "Add Tilt Hub to Apple Home" in the app (sealed /api/homecode). Not open all the time.
    if (matterUp && (ms() < 900000 || (int32_t)(homeWindowUntil - ms()) > 0)) chip::DeviceLayer::PlatformMgr().ScheduleWork([](intptr_t) {
      auto &mgr = chip::Server::GetInstance().GetCommissioningWindowManager();
      if (chip::Server::GetInstance().GetFabricTable().FabricCount() == 0 && !mgr.IsCommissioningWindowOpen()) {
        mgr.OpenBasicCommissioningWindow(chip::System::Clock::Seconds16(900), chip::CommissioningWindowAdvertisement::kAllSupported);
        ESP_LOGI(TAG, "pairing window open again (not in a home yet)");
      }
    }, 0);
    {                                            // who is on the Thread network (USB log)
      esp_openthread_lock_acquire(portMAX_DELAY);
      otInstance *ot = esp_openthread_get_instance();
      int role = otThreadGetDeviceRole(ot), kids = 0;
      otChildInfo ci;
      for (uint16_t i = 0; i < otThreadGetMaxAllowedChildren(ot); i++) if (otThreadGetChildInfoByIndex(ot, i, &ci) == OT_ERROR_NONE) {
        kids++;
        ESP_LOGI(TAG, "  child %04x ext %02x%02x%02x%02x age %lu s timeout %lu s rx-on %d state %d", ci.mRloc16, ci.mExtAddress.m8[0], ci.mExtAddress.m8[1], ci.mExtAddress.m8[2],
                 ci.mExtAddress.m8[3], (unsigned long)ci.mAge, (unsigned long)ci.mTimeout, ci.mRxOnWhenIdle, ci.mIsStateRestoring);
      }
      uint8_t ch = otLinkGetChannel(ot);
      otExtAddress kidAddr[8];
      int kidN = 0;
      for (uint16_t i = 0; i < otThreadGetMaxAllowedChildren(ot) && kidN < 8; i++) if (otThreadGetChildInfoByIndex(ot, i, &ci) == OT_ERROR_NONE) kidAddr[kidN++] = ci.mExtAddress;
      esp_openthread_lock_release();
      static int lastKids = -1, lastRole = -1;
      // A device is attached that the hub has not heard from lately: say hello to it, at its own link-local address
      // (fe80:: + its Thread address with the local bit flipped). Thread keeps the message until the device checks in
      // (a multicast would be missed by a sleeping one). A controller answers with its id and learns where the hub is.
      bool quiet = true;
      for (int c = 0; c < MAX_CTRL; c++) if (ctrls[c].used && ctrls[c].addrOk && ms() - ctrls[c].seen < 60000) quiet = false;
      for (int i = 0; quiet && i < kidN; i++) {
        sockaddr_in6 d = {};
        d.sin6_family = AF_INET6;
        d.sin6_port = htons(HUB_PORT);
        uint8_t *a = (uint8_t *)&d.sin6_addr;
        a[0] = 0xfe; a[1] = 0x80;
        memcpy(a + 8, kidAddr[i].m8, 8);
        a[8] ^= 0x02;
        d.sin6_scope_id = esp_netif_get_netif_impl_index(esp_openthread_get_netif());
        const char h[] = {'H', 0, 0};
        if (sendto(sock, h, 3, 0, (sockaddr *)&d, sizeof d) != 3) ESP_LOGW(TAG, "hello not sent (errno %d)", errno);
      }
      if (kids != lastKids || role != lastRole) { ESP_LOGI(TAG, "Thread: role %d, channel %d, %d child%s", role, ch, kids, kids == 1 ? "" : "ren"); lastKids = kids; lastRole = role; }
    }
    for (int c = 0; c < MAX_CTRL; c++) {
      if (!ctrls[c].used || !ctrls[c].addrOk) continue;
      if (!ctrls[c].announced && ctrls[c].seen && ms() - ctrls[c].seen < 1200000) announce(c);
      if (ctrls[c].announced && ms() - ctrls[c].seen > 1500000) {   // quiet for 25 minutes (on Wi-Fi again?): stop pointing the app here
        std::string inst = ctrls[c].s.id;
        for (auto &ch : inst) ch = toupper(ch);
        mdns_service_remove_for_host((inst + " via Tilt Hub").c_str(), "_tilt", "_tcp", nullptr);
        ctrls[c].announced = false;
        ESP_LOGI(TAG, "%s quiet: no longer announced", ctrls[c].s.id);
      }
      if (ctrls[c].s.keyState == KEY_IN && ctrls[c].cv && ctrls[c].cv != backupCv(ctrls[c].s.id)) takeBackup(c);
      if (ctrls[c].s.keyState == KEY_NONE) askToJoin(c);
      else if (ctrls[c].s.keyState == KEY_ASKED) ctrlCommand(c, "/api/s");   // let in yet? (also tells us at once)
      if (matterUp) chip::DeviceLayer::PlatformMgr().ScheduleWork(applyStatus, (intptr_t)c);
    }
    alertsCare();
  }
}

// ---- new controllers nearby: a controller nobody owns yet says "Tilt new" in its Bluetooth scan response (first
// 15 minutes after it is powered on). The app shows them as "New controller found".
struct NewOne { uint8_t addr[6]; int rssi; uint32_t seen; };
static NewOne newOnes[6];
static SemaphoreHandle_t newMx;
static int bleSeen(ble_gap_event *ev, void *) {
  if (ev->type != BLE_GAP_EVENT_DISC) return 0;
  ble_hs_adv_fields f;
  if (ble_hs_adv_parse_fields(&f, ev->disc.data, ev->disc.length_data) || !f.name || f.name_len != 8 || memcmp(f.name, "Tilt new", 8)) return 0;
  xSemaphoreTake(newMx, portMAX_DELAY);
  int slot = -1, oldest = 0;
  for (int i = 0; i < 6; i++) {
    if (newOnes[i].seen && !memcmp(newOnes[i].addr, ev->disc.addr.val, 6)) { slot = i; break; }
    if (newOnes[i].seen < newOnes[oldest].seen) oldest = i;
  }
  if (slot < 0) {
    slot = oldest;
    memcpy(newOnes[slot].addr, ev->disc.addr.val, 6);
    const uint8_t *a = ev->disc.addr.val;
    ESP_LOGI(TAG, "new controller nearby (Bluetooth %02x:%02x:%02x:%02x:%02x:%02x, %d dBm)", a[5], a[4], a[3], a[2], a[1], a[0], ev->disc.rssi);
  }
  newOnes[slot].rssi = ev->disc.rssi;
  newOnes[slot].seen = ms() ? ms() : 1;
  xSemaphoreGive(newMx);
  return 0;
}
static void bleScan() {                          // 4 s, listening 10 % of the time: Wi-Fi and Thread keep the radio
  if (!ble_hs_synced() || ble_gap_disc_active()) return;
  uint8_t own;
  if (ble_hs_id_infer_auto(0, &own)) return;
  ble_gap_disc_params dp = {};
  dp.itvl = 160;                                 // 100 ms
  dp.window = 16;                                // 10 ms
  dp.passive = 0;                                // ask for the scan response (the name is there)
  int e = ble_gap_disc(own, 4000, &dp, bleSeen, nullptr);
  if (e) ESP_LOGW(TAG, "Bluetooth scan did not start (%d)", e);
}
static bool newNearby(uint32_t withinMs = 300000) {
  bool any = false;
  xSemaphoreTake(newMx, portMAX_DELAY);
  for (auto &n : newOnes) any = any || (n.seen && ms() - n.seen < withinMs);
  xSemaphoreGive(newMx);
  return any;
}
