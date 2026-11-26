// The Tilt Hub's Matter side: one bridged Window covering per blind (what Home sees: home_view.h), the hub's own
// Apple Home setup code, and the homes it is in. Part of hub.cpp.
#pragma once
static std::string ctrlCommand(int c, const std::string &cmd);   // hub_ctrl.h
static std::string hubIp();                                       // hub_api.h
static void announce(int c);                                      // hub_api.h
// ---- Matter: one bridged Window covering per blind
static node_t *gNode;
static endpoint_t *aggregator;
static bool matterUp = false;
static uint16_t epOf(int c, int p) { return ctrls[c].s.ep[p]; }
static bool epFind(uint16_t ep, int &c, int &p) {
  for (c = 0; c < MAX_CTRL; c++) if (ctrls[c].used) for (p = 0; p < PORTS; p++) if (ctrls[c].s.ep[p] == ep) return true;
  return false;
}
static endpoint_t *makeTile(int c, int p, uint16_t resumeId, const char *name) {
  endpoint::bridged_node::config_t bc;
  endpoint_t *ep = resumeId ? endpoint::bridged_node::resume(gNode, &bc, ENDPOINT_FLAG_DESTROYABLE | ENDPOINT_FLAG_BRIDGE, resumeId, nullptr)
                            : endpoint::bridged_node::create(gNode, &bc, ENDPOINT_FLAG_DESTROYABLE | ENDPOINT_FLAG_BRIDGE, nullptr);
  if (!ep) return nullptr;
  endpoint::window_covering::config_t wc((uint8_t)WindowCovering::EndProductType::kInteriorBlind);
  wc.window_covering.type = (uint8_t)WindowCovering::Type::kTiltBlindLiftAndTilt;
  wc.window_covering.feature_flags = cluster::window_covering::feature::lift::get_id() | cluster::window_covering::feature::position_aware_lift::get_id();
  wc.window_covering.features.position_aware_lift.current_position_lift_percent_100ths = (uint16_t)0;
  wc.window_covering.features.position_aware_lift.target_position_lift_percent_100ths = (uint16_t)0;
  endpoint::window_covering::add(ep, &wc);
  endpoint::power_source::config_t ps;
  ps.power_source.status = 1;
  strlcpy(ps.power_source.description, "Battery", sizeof ps.power_source.description);
  ps.power_source.feature_flags = cluster::power_source::feature::battery::get_id();
  if (endpoint::power_source::add(ep, &ps) == ESP_OK) {
    cluster_t *pc = cluster::get(ep, PowerSource::Id);
    if (pc) cluster::power_source::attribute::create_bat_percent_remaining(pc, nullable<uint8_t>(200), nullable<uint8_t>((uint8_t)0), nullable<uint8_t>((uint8_t)200));
  }
  cluster_t *bi = cluster::get(ep, BridgedDeviceBasicInformation::Id);
  if (bi) {
    char label[33];
    strlcpy(label, name && name[0] ? name : "Blinds", sizeof label);
    cluster::bridged_device_basic_information::attribute::create_node_label(bi, label, strlen(label));
    char vn[] = "Tilt";
    cluster::bridged_device_basic_information::attribute::create_vendor_name(bi, vn, strlen(vn));
    char pn[] = "Tilt blind";
    cluster::bridged_device_basic_information::attribute::create_product_name(bi, pn, strlen(pn));
    char uid[24];
    snprintf(uid, sizeof uid, "%s-%d", ctrls[c].s.id, ctrls[c].s.sep ? p + 1 : 0);
    cluster::bridged_device_basic_information::attribute::create_unique_id(bi, uid, strlen(uid));
  }
  endpoint::set_parent_endpoint(ep, aggregator);
  return ep;
}
// Called with the CHIP stack lock held (ScheduleWork).
static void setU16(uint16_t ep, uint32_t cl, uint32_t at, uint16_t v) { esp_matter_attr_val_t x = esp_matter_nullable_uint16(nullable<uint16_t>(v)); attribute::update(ep, cl, at, &x); }
static bool selfUpd = false;
static void dropTile(Ctrl &k, int p) {
  endpoint_t *e = endpoint::get(gNode, k.s.ep[p]);
  if (e) endpoint::destroy(gNode, e);
  ESP_LOGI(TAG, "%s: Home tile %d removed", k.s.id, k.s.ep[p]);
  k.s.ep[p] = 0;
  k.tileLift[p] = k.tileOp[p] = -1;
  k.tileLabel[p][0] = 0;
}
// The blinds tile t stands for: all the shown ones (one tile), or blind t (one tile per blind).
static int tileBlinds(const Ctrl &k, int t, BlindNow *out) {
  int n = 0;
  for (int p = 0; p < PORTS; p++) {
    const Ctrl::B &b = k.b[p];
    if (b.hid || !b.ok || (k.s.sep && p != t)) continue;
    out[n++] = {b.tilt == INT32_MIN ? NAN : (float)b.tilt, b.mov != 0, b.tgt == INT32_MIN ? NAN : (float)b.tgt};
  }
  return n;
}
static void applyStatus(intptr_t ci) {
  int c = (int)ci;
  xSemaphoreTake(stateMx, portMAX_DELAY);
  Ctrl &k = ctrls[c];
  bool saved = false;
  if (k.sep >= 0 && k.sep != k.s.sep) {          // the controller's tile setting changed: start the tiles again
    for (int p = 0; p < PORTS; p++) if (k.s.ep[p]) dropTile(k, p);
    k.s.sep = k.sep;
    saved = true;
  }
  for (int t = 0; t < PORTS; t++) {
    BlindNow bl[PORTS];
    int n = tileBlinds(k, t, bl);
    // A tile is made for a blind that is set up; it stays when the blind is unplugged or not set up for a while
    // (Home keeps its room and automations). It goes only when the blind is hidden, or the tile setting changes.
    bool anyShown = false;
    for (int p = 0; p < PORTS; p++) anyShown = anyShown || (!k.b[p].hid && (!k.s.sep || p == t));
    bool want = k.sep >= 0 && (k.s.sep || t == 0) && (k.s.ep[t] ? anyShown : n > 0);
    const char *label = k.s.sep ? k.b[t].name : k.name;
    if (!want) { if (k.s.ep[t] && k.sep >= 0) { dropTile(k, t); saved = true; } continue; }
    if (!k.s.ep[t]) {                            // a tile Home has not seen
      endpoint_t *ep = makeTile(c, t, 0, label);
      if (ep) { k.s.ep[t] = endpoint::get_id(ep); endpoint::enable(ep); saved = true; strlcpy(k.tileLabel[t], label, 33); ESP_LOGI(TAG, "%s: new Home tile '%s' (endpoint %d)", k.s.id, label, k.s.ep[t]); }
    }
    uint16_t ep = k.s.ep[t];
    if (!ep) continue;
    selfUpd = true;
    if (strcmp(k.tileLabel[t], label)) {         // renamed in the app
      strlcpy(k.tileLabel[t], label, 33);
      esp_matter_attr_val_t nl = esp_matter_char_str(k.tileLabel[t], strlen(k.tileLabel[t]));
      attribute::update(ep, BridgedDeviceBasicInformation::Id, BridgedDeviceBasicInformation::Attributes::NodeLabel::Id, &nl);
    }
    esp_matter_attr_val_t r = esp_matter_bool(k.seen && ms() - k.seen < 1500000);   // not heard for 25 minutes: not responding
    attribute::update(ep, BridgedDeviceBasicInformation::Id, BridgedDeviceBasicInformation::Attributes::Reachable::Id, &r);
    HomeView v = homeViewOf(bl, n);
    HomeSend s = homeSendOf(v, k.tileLift[t] < 0, k.tileLift[t], k.tileOp[t]);
    if (s.lift) {
      k.tileLift[t] = v.lift;
      setU16(ep, WindowCovering::Id, WindowCovering::Attributes::CurrentPositionLiftPercent100ths::Id, (uint16_t)v.lift);
      if (s.target) setU16(ep, WindowCovering::Id, WindowCovering::Attributes::TargetPositionLiftPercent100ths::Id, (uint16_t)v.lift);
    }
    if (s.op) { k.tileOp[t] = v.op; esp_matter_attr_val_t o = esp_matter_bitmap8(s.opBits); attribute::update(ep, WindowCovering::Id, WindowCovering::Attributes::OperationalStatus::Id, &o); }
    if (k.pct >= 0) {
      esp_matter_attr_val_t bp = esp_matter_nullable_uint8(nullable<uint8_t>(homeBatPercent(k.pct)));
      attribute::update(ep, PowerSource::Id, PowerSource::Attributes::BatPercentRemaining::Id, &bp);
      esp_matter_attr_val_t bl2 = esp_matter_enum8(homeChargeLevel(k.pct));
      attribute::update(ep, PowerSource::Id, PowerSource::Attributes::BatChargeLevel::Id, &bl2);
    }
    selfUpd = false;
  }
  if (saved) saveCtrls();
  xSemaphoreGive(stateMx);
}
// Home asked a tile to move. Done on a worker task (it waits for the controller).
struct Move { int c, t, lift; };
static QueueHandle_t moves;
static esp_err_t attr_cb(attribute::callback_type_t type, uint16_t ep, uint32_t cl, uint32_t at, esp_matter_attr_val_t *val, void *) {
  if (type != PRE_UPDATE || selfUpd || cl != WindowCovering::Id || at != WindowCovering::Attributes::TargetPositionLiftPercent100ths::Id) return ESP_OK;
  int c, t;
  if (!homeLiftValid(val->val.u16) || !epFind(ep, c, t)) return ESP_OK;
  Move m = {c, t, val->val.u16};
  xQueueSend(moves, &m, 0);
  return ESP_OK;
}
static void moveTask(void *) {
  for (;;) {
    Move m;
    if (xQueueReceive(moves, &m, portMAX_DELAY) != pdTRUE) continue;
    Ctrl &k = ctrls[m.c];
    BlindNow bl[PORTS];
    int n = tileBlinds(k, m.t, bl);
    bool moving = false;
    for (int i = 0; i < n; i++) moving = moving || bl[i].busy;
    bool stop = homeAskIsStop(moving, m.lift, k.tileLift[m.t]);    // Home's "stop": go to where you are
    char cmd[60];
    if (stop) strlcpy(cmd, "/api/stop", sizeof cmd);
    else if (k.s.sep) snprintf(cmd, sizeof cmd, "/api/home?b=%d&lift=%d", m.t, m.lift);
    else snprintf(cmd, sizeof cmd, "/api/home?b=all&lift=%d", m.lift);
    uint32_t t0 = ms();
    std::string r = ctrlCommand(m.c, cmd);
    ESP_LOGI(TAG, "Home: %s %s -> %s (%lu ms)", k.s.id, cmd, r.empty() ? "no answer" : r.c_str(), (unsigned long)(ms() - t0));
  }
}

// ---- the hub's own Apple Home setup code: made at random on the first start and kept (never the public test code)
static HomeCode homeCode;
struct HomeCodeProvider : chip::DeviceLayer::CommissionableDataProvider {
  CHIP_ERROR GetSetupDiscriminator(uint16_t &d) override { d = homeCode.disc; return CHIP_NO_ERROR; }
  CHIP_ERROR SetSetupDiscriminator(uint16_t) override { return CHIP_ERROR_NOT_IMPLEMENTED; }
  CHIP_ERROR GetSpake2pIterationCount(uint32_t &n) override { n = homeCode.iter; return CHIP_NO_ERROR; }
  CHIP_ERROR GetSpake2pSalt(chip::MutableByteSpan &b) override { return chip::CopySpanToMutableSpan(chip::ByteSpan(homeCode.salt), b); }
  CHIP_ERROR GetSpake2pVerifier(chip::MutableByteSpan &b, size_t &n) override { n = sizeof homeCode.verifier; return chip::CopySpanToMutableSpan(chip::ByteSpan(homeCode.verifier), b); }
  CHIP_ERROR GetSetupPasscode(uint32_t &p) override { p = homeCode.pin; return CHIP_NO_ERROR; }
  CHIP_ERROR SetSetupPasscode(uint32_t) override { return CHIP_ERROR_NOT_IMPLEMENTED; }
};
static HomeCodeProvider homeCodeProvider;
// The maker and product names Apple Home and Alexa show (Basic Information): Tilt's own, not the SDK's "TEST_VENDOR".
// Everything else (serial, dates, versions) as the SDK keeps it.
struct TiltInfo : chip::DeviceLayer::Internal::GenericDeviceInstanceInfoProvider<chip::DeviceLayer::Internal::ESP32Config> {
  TiltInfo() : GenericDeviceInstanceInfoProvider(chip::DeviceLayer::ConfigurationManagerImpl::GetDefaultInstance()) {}
  static CHIP_ERROR put(const char *s, char *buf, size_t n) { if (strlen(s) >= n) return CHIP_ERROR_BUFFER_TOO_SMALL; strcpy(buf, s); return CHIP_NO_ERROR; }
  CHIP_ERROR GetVendorName(char *buf, size_t n) override { return put("Tilt", buf, n); }
  CHIP_ERROR GetProductName(char *buf, size_t n) override { return put("Tilt Hub", buf, n); }
};
static TiltInfo tiltInfo;
static void homeCodeBegin() {                      // before Bluetooth and Matter start (the random source needs the radio off)
  size_t n = sizeof homeCode;
  if (nvs_get_blob(nv, "homecode", &homeCode, &n) != ESP_OK || !homeCodeKeep(homeCode, n)) {
    HomeCode c = {HOME_CODE_MAGIC, 0, 1000, 0, {}, {}};
    bootloader_random_enable();
    do esp_fill_random(&c.pin, sizeof c.pin); while (!setupPinValid(c.pin %= 100000000));
    esp_fill_random(&c.disc, sizeof c.disc);
    c.disc &= 0xFFF;
    esp_fill_random(c.salt, sizeof c.salt);
    bootloader_random_disable();
    chip::Crypto::Spake2pVerifier v;
    chip::MutableByteSpan out(c.verifier);
    if (v.Generate(c.iter, chip::ByteSpan(c.salt), c.pin) == CHIP_NO_ERROR && v.Serialize(out) == CHIP_NO_ERROR) {
      homeCode = c;
      nvs_set_blob(nv, "homecode", &homeCode, sizeof homeCode);
      nvs_commit(nv);
    }
  }
  esp_matter::set_custom_commissionable_data_provider(&homeCodeProvider);
  esp_matter::set_custom_device_instance_info_provider(&tiltInfo);
  chip::PayloadContents p;
  p.vendorID = CONFIG_DEVICE_VENDOR_ID;
  p.productID = CONFIG_DEVICE_PRODUCT_ID;
  p.rendezvousInformation.Emplace(chip::RendezvousInformationFlag::kBLE);
  p.discriminator.SetLongValue(homeCode.disc);
  p.setUpPINCode = homeCode.pin;
  char manual[chip::kManualSetupLongCodeCharLength + 1], qr[chip::QRCodeBasicSetupPayloadGenerator::kMaxQRCodeBase38RepresentationLength + 1];
  chip::MutableCharSpan m(manual), q(qr);
  if (chip::ManualSetupPayloadGenerator(p).payloadDecimalStringRepresentation(m) == CHIP_NO_ERROR &&
      chip::QRCodeBasicSetupPayloadGenerator(p).payloadBase38Representation(q) == CHIP_NO_ERROR)
  {
    homeManual = manualCodeDashed(std::string(m.data(), m.size()));
    homeQr.assign(q.data(), q.size());
    printf("HUB SETUP CODE %s  QR %s\n", homeManual.c_str(), homeQr.c_str());   // USB log
  }
}

// The hub itself on Bonjour (_tilthub._tcp): its address and whether it has an owner (a new hub says owned=0).
static bool hubOwned();
static std::string hubId();
static void announceHub() {
  std::string ip = hubIp(), id = hubId();
  if (ip == "0.0.0.0") return;
  mdns_txt_item_t t[] = {{"ip", ip.c_str()}, {"id", id.c_str()}, {"owned", hubOwned() ? "1" : "0"}};
  if (mdns_service_txt_set_for_host("Tilt Hub", "_tilthub", "_tcp", nullptr, t, 3) != ESP_OK) mdns_service_add_for_host("Tilt Hub", "_tilthub", "_tcp", nullptr, 80, t, 3);
}
// The homes the hub is in (Matter fabrics), read fresh: `home` is 1 if there is any. Each one with its maker's
// number (Apple's is 4996), the hub's node ID in it, and its label. Apple adds two (the home and the iPhone's iCloud
// Keychain) and leaves the Keychain one when the hub is removed from Home, so `home` alone can't say "in Apple Home":
// the app compares the node IDs with the accessories Apple Home has (HomeSetup.inHome).
static std::string homesJson() {
  if (!matterUp) return std::string("\"homes\":[],\"home\":") + (inHome ? "1" : "0");   // Matter not running: nothing to lock or read
  std::string j = "\"homes\":[";
  int n = 0;
  chip::DeviceLayer::PlatformMgr().LockChipStack();
  for (const auto &f : chip::Server::GetInstance().GetFabricTable()) {
    chip::CharSpan l = f.GetFabricLabel();
    std::string label;
    for (size_t i = 0; i < l.size(); i++) { char c = l.data()[i]; if (c != '"' && c != '\\' && (unsigned char)c >= 32 && (unsigned char)c < 127) label += c; }   // plain ASCII: always good JSON
    char one[128];                               // node: the hub's own ID in that home (Apple Home shows it per accessory)
    snprintf(one, sizeof one, "%s{\"i\":%u,\"vendor\":%u,\"node\":\"%016llX\",\"label\":\"%s\"}", n ? "," : "", (unsigned)f.GetFabricIndex(),
             (unsigned)f.GetVendorId(), (unsigned long long)f.GetNodeId(), label.c_str());
    j += one;
    n++;
  }
  chip::DeviceLayer::PlatformMgr().UnlockChipStack();
  inHome = n > 0;
  return j + "],\"home\":" + (n ? "1" : "0");
}
static void event_cb(const ChipDeviceEvent *ev, intptr_t) {
  if (ev->Type == chip::DeviceLayer::DeviceEventType::kCommissioningComplete) { inHome = true; ESP_LOGI(TAG, "added to a home"); }
  if (ev->Type == chip::DeviceLayer::DeviceEventType::kFabricRemoved) inHome = chip::Server::GetInstance().GetFabricTable().FabricCount() > 0;
  if (ev->Type == chip::DeviceLayer::DeviceEventType::kESPSystemEvent && ev->Platform.ESPSystemEvent.Base == IP_EVENT &&
      ev->Platform.ESPSystemEvent.Id == IP_EVENT_STA_GOT_IP) {
    for (int c = 0; c < MAX_CTRL; c++) ctrls[c].announced = false;
    announceHub();
    for (int c = 0; c < MAX_CTRL; c++) if (ctrls[c].used && ctrls[c].addrOk) announce(c);
    ESP_LOGI(TAG, "on Wi-Fi at %s", hubIp().c_str());
  }
}
