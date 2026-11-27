// The Tilt Hub's people: who is in, who waits, who owns it, and what each may do. Plain state with an injected clock
// and a save hook, so the rules run on the Mac (firmware/tilt_hub/test/hub_test.cpp). hub_pair.h holds the lock, does the
// crypto and the logging, keeps the flash copy (the save hook) and asks these rules.
//
// The same scheme as a controller's (blinds_matter/main/sec.h), so the app pairs with the hub the same way (its address
// "<hub>/hub"). The first phone is the owner; others ask to join and an owner lets them in. Owners can add controllers
// (the network), add the hub to Apple Home (its code), use backups and invite people.
//
// The first owner (a new hub, or after its people were reset) must know the setup code on the hub's label: it is
// mixed into the key, so a phone with the wrong code makes a key the hub does not share, and its first command fails.
// Until then the place is held for a minute; five wrong codes close connecting for five minutes.
#pragma once
#include <cstdint>
#include <cstring>
#include <string>
#include "wire.h"                                // keptName, keyJson: a phone's name as typed (blinds_matter/main)

const int HUB_KEYS = 8;
struct HubKey { uint8_t used, role; uint8_t id[8]; uint8_t key[32]; char name[20]; };   // used 1 in, 2 asked, 3 first owner not yet proven; role 1 owner
enum HubKeyUse : uint8_t { HK_FREE = 0, HK_IN = 1, HK_ASKED = 2, HK_CLAIM = 3 };

// Who the caller is, for hubPermit.
enum HubRole { HUB_WAITING, HUB_USER, HUB_OWNER };
// What a phone may ask the hub. nullptr: allowed. Otherwise the reason it is refused. A phone that waits for an owner
// may only leave (the whole command, as it came); one that is in may see the hub and its people, rename itself and
// leave; an owner may do anything.
inline const char *hubPermit(const std::string &cmd, HubRole role) {
  if (role == HUB_OWNER) return nullptr;
  if (role == HUB_WAITING) return cmd == "/api/leave" ? nullptr : "waiting";
  for (const char *ok : {"/api/info", "/api/keys", "/api/keyname", "/api/leave"}) if (cmd == ok) return nullptr;
  return "only the hub's owner can do that";
}

// What the people commands do (hubCommand).
enum PeopleOp { PO_LEAVE, PO_RESET, PO_APPROVE, PO_DENY, PO_REVOKE, PO_MAKEOWNER, PO_UNOWNER };
struct PeopleResult {
  const char *err;                               // nullptr: done. Otherwise why not (as the app shows it)
  char name[20];                                 // the phone it was about (for the log)
};

struct HubPeople {
  HubKey keys[HUB_KEYS];
  uint32_t claimAt[HUB_KEYS], askAt[HUB_KEYS], pinLockUntil = 0, lastAsk = 0;
  int pinFails = 0;
  uint64_t last[HUB_KEYS];                       // the newest counter taken from each phone (this start)
  uint32_t (*clock)() = nullptr;                 // ms since start
  void (*save)(const HubPeople &) = nullptr;     // write keys to flash

  HubPeople() { memset(keys, 0, sizeof keys); memset(claimAt, 0, sizeof claimAt); memset(askAt, 0, sizeof askAt); memset(last, 0, sizeof last); }
  uint32_t now() const { return clock(); }
  void saved() { if (save) save(*this); }
  bool owned() const { for (auto &k : keys) if (k.used == HK_IN && k.role == 1) return true; return false; }
  int find(const uint8_t id[8]) const { int s = -1; for (int i = 0; i < HUB_KEYS; i++) if (keys[i].used && !memcmp(keys[i].id, id, 8)) s = i; return s; }
  HubRole role(int slot) const { return keys[slot].used != HK_IN ? HUB_WAITING : keys[slot].role == 1 ? HUB_OWNER : HUB_USER; }

  // A phone asks to pair (ask false: the first phone, it becomes the owner) or to join (ask true: it waits for an
  // owner). Before the key exchange: 0 if it may go on (first: no owner yet), else the HTTP status and why not.
  int pairGate(bool ask, bool &first, const char *&err) {
    first = !owned();
    if (ask && first) { err = "this hub has no owner yet: connect to it"; return 403; }
    if (!ask && !first) { err = "this hub has an owner. Ask to join from the app."; return 403; }
    if (!ask) {
      if (pinLockUntil && (int32_t)(now() - pinLockUntil) < 0) { err = "too many wrong codes: try again in a few minutes"; return 429; }
      bool busy = false;
      for (int i = 0; i < HUB_KEYS; i++) if (keys[i].used == HK_CLAIM) { if (now() - claimAt[i] < 60000) busy = true; else memset(&keys[i], 0, sizeof keys[i]); }
      if (busy) { err = "someone else is connecting to this hub: try again in a minute"; return 409; }
    }
    if (ask && lastAsk && now() - lastAsk < 10000) { err = "try again in a few seconds"; return 429; }
    if (ask) lastAsk = now();
    return 0;
  }
  // After the key exchange: the place for the new phone, or -1 with the HTTP status and why not. At most two wait: a
  // new ask takes the place of one older than 10 minutes.
  int pairPlace(bool ask, int &status, const char *&err) const {
    int slot = -1, waiting = 0;
    for (auto &k : keys) if (k.used == HK_ASKED) waiting++;
    if (ask && waiting >= 2) {
      for (int i = 0; i < HUB_KEYS; i++) if (keys[i].used == HK_ASKED && (!askAt[i] || now() - askAt[i] > 600000)) { slot = i; break; }
      if (slot < 0) { status = 429; err = "two requests are waiting already. Try again later."; return -1; }
    }
    else for (int i = 0; i < HUB_KEYS; i++) if (!keys[i].used) { slot = i; break; }
    if (slot < 0) { status = 403; err = "no room for another phone"; return -1; }
    return slot;
  }
  // The new phone takes the place: waiting (ask), or holding it for a minute until its setup code proves right.
  void pairTake(int slot, bool ask, bool first, const uint8_t id[8], const uint8_t key[32], const char *name) {
    HubKey &k = keys[slot];
    memset(&k, 0, sizeof k);
    k.used = ask ? HK_ASKED : HK_CLAIM; k.role = first ? 1 : 0;
    askAt[slot] = ask ? (now() ? now() : 1) : 0;
    claimAt[slot] = ask ? 0 : now();
    memcpy(k.id, id, 8);
    memcpy(k.key, key, 32);
    std::string nm = keptName(name, sizeof k.name - 1);         // as typed (UTF-8): wire.h
    strncpy(k.name, nm.empty() ? "iPhone" : nm.c_str(), sizeof k.name - 1);
    last[slot] = 0;
    saved();
  }
  // Its first command could not be opened. A phone claiming the hub had the wrong setup code: its place goes, and the
  // fifth wrong code closes connecting for 5 minutes. True if it was a claim.
  bool openFailed(int slot) {
    if (keys[slot].used != HK_CLAIM) return false;
    memset(&keys[slot], 0, sizeof keys[slot]);
    if (++pinFails >= 5) { pinFails = 0; pinLockUntil = (now() + 300000) | 1; }
    return true;
  }
  // Its command opened (counter ctr). A claim with the right code makes the owner: true then.
  bool opened(int slot, uint64_t ctr) {
    last[slot] = ctr;
    if (keys[slot].used != HK_CLAIM) return false;
    keys[slot].used = HK_IN; pinFails = 0;
    saved();
    return true;
  }
  // A phone that waits for an owner gives up (its /api/leave): it is forgotten.
  void forget(int slot) { memset(&keys[slot], 0, sizeof keys[slot]); saved(); }

  // The phone in `slot` renames itself (its /api/keyname). nullptr: saved; otherwise why not. On the hub a phone renames
  // only itself.
  const char *rename(int slot, const char *name) {
    std::string nm = keptName(name, sizeof keys[slot].name - 1);
    if (nm.empty()) return "a name is needed";
    memset(keys[slot].name, 0, sizeof keys[slot].name);
    memcpy(keys[slot].name, nm.data(), nm.size());
    saved();
    return nullptr;
  }
  // The hub's people, as /api/keys answers the phone in `me` (owner: it may see the join codes). codeOf: a waiting
  // phone's join code from its key (tilt_pair.h askCode; passed in so the crypto stays in hub_pair.h).
  std::string listJson(int me, bool owner, std::string (*codeOf)(const uint8_t key[32])) const {
    std::string j = "{\"ok\":1,\"keys\":[";
    bool first = true;
    for (int i = 0; i < HUB_KEYS; i++) {
      const HubKey &k = keys[i];
      if (!k.used) continue;
      std::string name(k.name, strnlen(k.name, sizeof k.name));
      j += (first ? "" : ",") + keyJson(hexOf8(k.id), name, k.role ? 1 : 0, i == me ? 1 : 0, k.used == HK_ASKED ? 1 : 0,
                                       k.used == HK_ASKED && owner ? codeOf(k.key) : std::string());
      first = false;
    }
    return j + "]}";
  }
  // tilt_crypto.h hexOf for an id, here without its mbedtls (this file runs on the Mac without it)
  static std::string hexOf8(const uint8_t id[8]) {
    static const char *d = "0123456789abcdef";
    std::string h;
    for (int i = 0; i < 8; i++) { h += d[id[i] >> 4]; h += d[id[i] & 15]; }
    return h;
  }

  // A people command from the phone in `slot` (one that is in). cid: the phone it is about (approve, deny, revoke,
  // makeowner). A change that would leave the hub with no owner is put back.
  PeopleResult apply(PeopleOp op, int slot, const uint8_t *cid = nullptr, bool asOwner = false) {
    PeopleResult r = {"no such phone", ""};
    if (op == PO_LEAVE) {                        // this phone leaves the hub (everywhere, not just on the phone)
      int owners = 0, others = 0;
      for (int i = 0; i < HUB_KEYS; i++) if (i != slot && keys[i].used) { others++; if (keys[i].used == HK_IN && keys[i].role == 1) owners++; }
      if (keys[slot].role == 1 && owners == 0 && others > 0) { r.err = "you are the hub's only owner: make someone else an owner first, or reset its people"; return r; }
      memcpy(r.name, keys[slot].name, sizeof r.name);
      memset(&keys[slot], 0, sizeof keys[slot]);
      saved();
      r.err = nullptr;
      return r;
    }
    if (op == PO_RESET) {                        // forget every phone: the next one to connect becomes the owner
      memset(keys, 0, sizeof keys);
      saved();
      r.err = nullptr;
      return r;
    }
    for (int i = 0; i < HUB_KEYS; i++) {
      HubKey &k = keys[i];
      if (!k.used || memcmp(k.id, cid, 8)) continue;
      HubKey before = k;
      memcpy(r.name, k.name, sizeof r.name);
      if (op == PO_APPROVE || op == PO_DENY) {
        if (k.used != HK_ASKED) break;
        if (op == PO_APPROVE) { k.used = HK_IN; k.role = asOwner; last[i] = 0; }
        else memset(&k, 0, sizeof k);
      } else if (op == PO_MAKEOWNER || op == PO_UNOWNER) k.role = op == PO_MAKEOWNER;
      else { if (i == slot) { r.err = "you cannot remove yourself"; break; } memset(&k, 0, sizeof k); }
      if (!owned()) { k = before; r.err = "the hub needs an owner: make someone else an owner first"; break; }
      saved();
      r.err = nullptr;
      break;
    }
    return r;
  }
};
