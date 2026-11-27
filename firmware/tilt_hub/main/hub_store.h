// What the Tilt Hub keeps about each controller, in memory and in flash: Saved, Ctrl, the link state (ctrl_link.h),
// the NVS handle and the state lock, save and load. Part of hub.cpp: included once, in order (one compiled file).
// The first part: it includes what it uses by its SDK name, so it compiles with nothing before it (on the Mac too).
#pragma once
#include <cstring>
#include <string>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include <freertos/queue.h>
#include <nvs.h>
#include <esp_timer.h>
#include <esp_random.h>
#include <lwip/sockets.h>
#include <app/server/Server.h>                   // homeBeingAdded: the Matter fail-safe
#include "logic.h"                               // PORTS (the controller's own rules)
#include "ctrl_link.h"                           // CtrlLink, KeyState
const uint16_t HUB_PORT = 49100;
const int MAX_CTRL = 4;                          // PORTS: logic.h
static uint32_t ms() { return (uint32_t)(esp_timer_get_time() / 1000); }
static int rng(void *, unsigned char *b, size_t n) { esp_fill_random(b, n); return 0; }
static uint8_t htopic[16];                       // the hub's own alert topic: made and kept by keysBegin (hub_pair.h)

// ---- what the hub knows about each controller (the part in flash: Saved)
struct Saved {
  char id[13];
  uint8_t keyState;                              // KeyState: the hub's own key on this controller
  uint8_t cid[8], key[32];
  uint16_t ep[PORTS];                            // Home tiles (Matter endpoints, 0 = none): ep[0] alone = all the blinds,
  uint8_t sep;                                   //   or with sep = 1 one tile per blind (the controller's "hksep")
};
// KeyState (ctrl_link.h): no key / asked to join, waiting / let in
enum OtaState { OTA_NONE = 0, OTA_SENDING = 1, OTA_CHECKING = 2, OTA_DONE = 3, OTA_FAILED = 4 };   // the app reads these numbers
struct SavedV1 { char id[13]; uint8_t keyState; uint8_t cid[8], key[32]; uint16_t ep[PORTS]; };
struct Ctrl {
  Saved s;
  bool used;
  char name[33];
  char fw[24];                                   // its firmware version (from its pushes)
  sockaddr_in6 addr;
  bool addrOk;
  uint32_t seen;                                 // ms of the last message from it
  int closeUp, pct, low;
  int chg;                                       // on the charging cable: 1 yes, 0 no, -1 not said (older controller)
  int src;                                       // Power source, passed on as sent (0 battery, 1 solar, 2 USB, 3 unknown); -1 not said
  struct B { char name[33]; int hid, ok, tilt, tgt, mov; } b[PORTS];
  int sep;                                       // what the controller says now (-1 = not heard yet)
  int tileLift[PORTS], tileOp[PORTS];            // what each tile last showed Home (-1 = nothing yet)
  char tileLabel[PORTS][33];
  char pushBoot[9];                              // the controller's boot id from its last push
  std::string hello;                             // its last hello answer, given to the app straight from the hub
  char helloBoot[9];
  bool announced;
  uint32_t cv;                                   // checksum of its settings (from its pushes)
  int own;                                       // it has an owner (from its pushes; -1 not known yet)
  uint32_t firstSeen;                            // ms when the hub first heard from it since this start
  int otaSt;                                     // OtaState: firmware through the hub
  int otaPct;
  char otaErr[64];
  uint16_t rloc;                                 // its Thread short address, while known
  uint32_t pushN;                                // the count on its last proven push (this boot)
  SemaphoreHandle_t mx;                          // one request to this controller at a time
};
static Ctrl ctrls[MAX_CTRL];
// The link to each controller (its boot id, the hub's counter): apart from ctrls[] so a new controller in a place gets
// a clean Ctrl while its link keeps its locks.
static CtrlLink links[MAX_CTRL];
// Per controller (flash "proof"): it has sent a proven push (from then on only proven ones count), and the boot count
// of the newest one (an older boot's push is never taken again).
struct PushProof { uint8_t on; uint32_t bn; };
static PushProof proofs[MAX_CTRL];
static void proofsSave();
static uint32_t constrain_u(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }
struct OtaAck { bool ok, num; uint32_t next; };   // a controller's answer to a firmware piece (num: it gave an offset)
static QueueHandle_t otaAcks;
static bool hubTrial = false;                    // the hub runs new firmware it has not kept yet
static volatile uint32_t homeWindowUntil = 0;    // the owner asked to add the hub to Apple Home: pairing open until then
static volatile int otaFor = -1;                 // the controller being updated (one at a time)
static std::string homeManual, homeQr;           // the code to type and the QR text (USB log, and to the controllers)
static std::string shareManual, shareQr;         // the one-time code for another home app (shareCodeJson)
static volatile uint32_t shareUntil = 0;          // that code's pairing window is open until then (0: none)
static volatile bool inHome = false;             // added to Apple Home (or another Matter home)
static std::string homesJson();                  // the homes it is in, read fresh (below)
static std::string shareCodeJson();              // a one-time code for another home app (below)
// A home app is adding the hub right now (Matter fail-safe armed): its pairing window must not be closed. Call with
// the CHIP stack lock held.
static bool homeBeingAdded() { return chip::Server::GetInstance().GetFailSafeContext().IsFailSafeArmed(); }
static const char *BUSY_JSON = "{\"ok\":0,\"err\":\"a home app is adding the Tilt Hub right now: try again in a minute\"}";
static SemaphoreHandle_t stateMx;              // ctrls[] (not the per-controller request lock)
static nvs_handle_t nv;
static void proofsSave() { nvs_set_blob(nv, "proof", proofs, sizeof proofs); nvs_commit(nv); }
static void saveCtrls() {
  Saved all[MAX_CTRL] = {};
  for (int i = 0; i < MAX_CTRL; i++) if (ctrls[i].used) all[i] = ctrls[i].s;
  nvs_set_blob(nv, "ctrls", all, sizeof all);
  nvs_commit(nv);
}
static void loadCtrls() {
  { size_t pn = sizeof proofs; if (nvs_get_blob(nv, "proof", proofs, &pn) != ESP_OK || pn != sizeof proofs) memset(proofs, 0, sizeof proofs); }
  Saved all[MAX_CTRL] = {};
  size_t n = sizeof all;
  if (nvs_get_blob(nv, "ctrls", all, &n) != ESP_OK || n != sizeof all) {   // the first layout (no sep): keep the keys
    SavedV1 v1[MAX_CTRL];
    n = sizeof v1;
    if (nvs_get_blob(nv, "ctrls", v1, &n) != ESP_OK || n != sizeof v1) return;
    for (int i = 0; i < MAX_CTRL; i++) { memcpy(&all[i], &v1[i], sizeof v1[i]); all[i].sep = 1; }
  }
  for (int i = 0; i < MAX_CTRL; i++) if (all[i].id[0]) { ctrls[i].used = true; ctrls[i].s = all[i]; strlcpy(ctrls[i].name, "Blinds", sizeof ctrls[i].name); }
}
static int findCtrl(const char *id) { for (int i = 0; i < MAX_CTRL; i++) if (ctrls[i].used && !strcmp(ctrls[i].s.id, id)) return i; return -1; }
