// When the Tilt Hub tells a controller's owners: the rules are alert_rules.h, cloud.h sends them. This is the ESP
// side: what was already told (in flash), and the alerts from pushes, care rounds and updates. Part of hub.cpp.
#pragma once
// ---- Alert rules (alert_rules.h): when the hub tells a controller's owners. cloud.h sends them.
struct Memo {                                    // per controller, by id (flash "amemo2"): what was already told
  char id[13];
  char name[33];                                 // its room's name (kept: the hub may restart while it is silent)
  uint8_t topic[16];                             // its iCloud topic (its status, asked once with the hub's key)
  AlertMemo r;
};
static Memo memos[MAX_CTRL];
static void memosSave() { nvs_set_blob(nv, "amemo2", memos, sizeof memos); nvs_commit(nv); }
static void memosLoad() { size_t n = sizeof memos; if (nvs_get_blob(nv, "amemo2", memos, &n) != ESP_OK || n != sizeof memos) memset(memos, 0, sizeof memos); }
static Memo &memoOf(int c) {
  const char *id = ctrls[c].s.id;
  for (auto &m : memos) if (!strcmp(m.id, id)) return m;
  int slot = -1;
  for (int i = 0; i < MAX_CTRL && slot < 0; i++) if (!memos[i].id[0] || findCtrl(memos[i].id) < 0) slot = i;
  if (slot < 0) slot = c;
  memos[slot] = Memo{};
  strlcpy(memos[slot].id, id, sizeof memos[slot].id);
  return memos[slot];
}
static bool topicKnown(const Memo &m) { for (auto b : m.topic) if (b) return true; return false; }
// A status push came in (under stateMx): battery levels, stalls, and it is no longer silent.
static void alertsFromPush(int c, cJSON *j) {
  Ctrl &k = ctrls[c];
  Memo &m = memoOf(c);
  bool save = false, told = topicKnown(m);       // no topic yet: nothing can be sent, so nothing counts as told
  if (strcmp(m.name, k.name)) { strlcpy(m.name, k.name, sizeof m.name); save = true; }
  if (alertHeard(m.r)) { save = true; ESP_LOGI(TAG, "%s heard again", k.s.id); }
  if (told)
    if (const char *kind = alertBattery(m.r, k.pct, k.low, &save)) alertRaise(m.topic, kind, 9, k.name, std::to_string(k.pct).c_str());
  cJSON *bl = cJSON_GetObjectItem(j, "b"), *bnj = cJSON_GetObjectItem(j, "bn");
  if (cJSON_IsNumber(cJSON_GetObjectItem(cJSON_GetArrayItem(bl, 0), "st")) && cJSON_IsNumber(bnj)) {   // a controller that counts stalls
    int st[PORTS];
    for (int p = 0; p < PORTS; p++) { cJSON *sv = cJSON_GetObjectItem(cJSON_GetArrayItem(bl, p), "st"); st[p] = cJSON_IsNumber(sv) ? sv->valueint : -1; }
    int stalled = alertStalls(m.r, (uint32_t)bnj->valuedouble, st, PORTS, &save);
    for (int p = 0; p < PORTS && told; p++) if (stalled & (1 << p)) alertRaise(m.topic, "stall", p, k.name, k.b[p].name);
  }
  if (save) memosSave();
}
// Every care round: silent controllers, and learning each controller's topic (once, with the hub's key).
static void alertsCare() {
  for (int c = 0; c < MAX_CTRL; c++) {
    if (!ctrls[c].used || ctrls[c].s.keyState != KEY_IN) continue;
    xSemaphoreTake(stateMx, portMAX_DELAY);
    Memo &m = memoOf(c);
    uint32_t quiet = ctrls[c].seen ? ms() - ctrls[c].seen : ms();
    if (topicKnown(m) && otaFor != c && alertSilent(m.r, quiet)) {
      alertRaise(m.topic, "silent", 9, m.name[0] ? m.name : ctrls[c].name);
      memosSave();
    }
    bool ask = !topicKnown(m) && ctrls[c].seen && ms() - ctrls[c].seen < 60000;
    xSemaphoreGive(stateMx);
    static uint32_t askedAt[MAX_CTRL];
    if (!ask || (askedAt[c] && ms() - askedAt[c] < 600000)) continue;
    askedAt[c] = ms() | 1;
    std::string r = ctrlCommand(c, "/api/s");
    cJSON *j = cJSON_Parse(r.c_str());
    const char *t = j ? cJSON_GetStringValue(cJSON_GetObjectItem(j, "topic")) : nullptr;
    uint8_t tb[16];
    if (t && unhex(t, tb, 16)) {
      xSemaphoreTake(stateMx, portMAX_DELAY);
      memcpy(memoOf(c).topic, tb, 16); memosSave();
      xSemaphoreGive(stateMx);
      ESP_LOGI(TAG, "%s: alert topic known", ctrls[c].s.id);
    }
    if (j) cJSON_Delete(j);
  }
}
static void alertUpdateFailed(int c, const char *why) {     // from the update task (stateMx not held)
  uint8_t t[16];
  char name[33];
  xSemaphoreTake(stateMx, portMAX_DELAY);
  memcpy(t, memoOf(c).topic, 16);
  strlcpy(name, ctrls[c].name, sizeof name);
  xSemaphoreGive(stateMx);
  alertRaise(t, "update", 9, name, why);
}
// The hub's own new firmware went back to the old one (it did not work): tell its owners once per version.
static uint8_t htopic[16];
static void alertHubUpdate() {
  const esp_partition_t *bad = esp_ota_get_last_invalid_partition();
  esp_app_desc_t d;
  if (!bad || esp_ota_get_partition_description(bad, &d) != ESP_OK) return;
  char seen[32] = {0};
  size_t n = sizeof seen;
  bool first = nvs_get_str(nv, "badver", seen, &n) != ESP_OK;   // an old failure from before alerts existed: no alert
  if (!strcmp(seen, d.version)) return;
  nvs_set_str(nv, "badver", d.version); nvs_commit(nv);
  if (!first) alertRaise(htopic, "hub-update", 9, "Tilt Hub", d.version);
}
