// The hub's link to one controller: the controller's boot id as the hub last heard it, and the hub's counter for its
// own sealed commands, behind one lock, with one way to send a command (call). Pure: the network and the hub's saved
// key come in through a seam, so test/ctrl_link_test.cpp runs it on the Mac with a fake controller.
//
// Two locks, each with one job, never held the other way round:
//   one   one command at a time (held for the whole call): counters reach the controller in the order they were made
//   mx    the boot id and the counter (held only to read or change them, never across a send or a seam call), so the
//         hub's message task can note a new boot id while a command waits for its answer
#pragma once
#include <mutex>
#include <string>
#include "tilt_link.h"

enum KeyState : uint8_t { KEY_NONE = 0, KEY_ASKED = 1, KEY_IN = 2 };   // no key / asked to join, waiting / let in

struct LinkSeam {
  // Send one request and wait for its answer: the 3-digit status (0 = no answer) and the answer.
  virtual int ask(char type, const std::string &payload, std::string &ans) = 0;
  // The hub's own key on this controller (KEY_NONE: none; key and cid are then not set).
  virtual KeyState hubKey(uint8_t key[32], uint8_t cid[8]) = 0;
  virtual void dropped() = 0;                    // the controller said 401: the hub's key there is gone
  virtual void letIn() = 0;                      // the first answer to a key that was waiting: it is let in now
  virtual uint64_t clockMs() = 0;                // the time in ms (the counter follows it, and always rises)
  virtual ~LinkSeam() {}
};

struct CallResult {
  enum Why { OK, NO_KEY, NO_HELLO, SEAL, WAITING, DROPPED, FAILED, BAD_REPLY } why;
  int st;                                        // the controller's last status (0: no answer)
  std::string out;                               // OK: its answer, opened; else what it said (for the log)
};

class CtrlLink {
 public:
  // A command with the hub's key: "/api/home?b=0&lift=5000". A stale answer (409, the controller restarted) gets one
  // more try with its new boot id.
  CallResult call(LinkSeam &s, const std::string &cmd) {
    std::lock_guard<std::mutex> one(one_);
    CallResult r{CallResult::FAILED, 0, ""};
    for (int attempt = 0; attempt < 2; attempt++) {
      uint8_t key[32], cid[8];
      KeyState ks = s.hubKey(key, cid);
      if (ks == KEY_NONE) return {CallResult::NO_KEY, 0, ""};
      uint8_t b[4];
      if (!boot(b)) {
        std::string h;
        int st = s.ask(DG_HELLO, "", h);
        if (st != 200 || !unhex(linkJsonStr(h, "boot"), b, 4)) return {CallResult::NO_HELLO, st, h};
        setBoot(b);
      }
      uint64_t ctr;
      {
        std::lock_guard<std::mutex> l(mx_);
        if (!bootOk_) continue;                  // forgotten meanwhile (a new start, an update): hello again
        memcpy(b, boot_, 4);
        uint64_t now = s.clockMs();
        ctr_ = now > ctr_ ? now : ctr_ + 1;
        ctr = ctr_;
      }
      std::string pkt = frameSeal(key, cid, b, ctr, cmd);
      if (pkt.empty()) return {CallResult::SEAL, 0, ""};
      std::string ans;
      int st = s.ask(DG_COMMAND, pkt, ans);
      r = {CallResult::FAILED, st, ans};
      if (st == 409) { forgetBootIf(b); continue; }   // the controller restarted (new boot id): once more
      if (st == 403 && ans.find("waiting") != std::string::npos) return {CallResult::WAITING, st, ans};
      if (st == 401) { s.dropped(); return {CallResult::DROPPED, st, ans}; }
      if (st != 200) return r;
      std::string out;
      if (!replyOpen(key, cid, (const uint8_t *)pkt.data() + 8, ans, out)) return {CallResult::BAD_REPLY, st, ""};
      if (ks != KEY_IN) s.letIn();
      return {CallResult::OK, st, out};
    }
    return r;
  }
  // The controller's boot id as the hub knows it (false: not known, say hello first).
  bool boot(uint8_t b[4]) {
    std::lock_guard<std::mutex> l(mx_);
    if (bootOk_) memcpy(b, boot_, 4);
    return bootOk_;
  }
  void setBoot(const uint8_t b[4]) { std::lock_guard<std::mutex> l(mx_); memcpy(boot_, b, 4); bootOk_ = true; }
  void forgetBoot() { std::lock_guard<std::mutex> l(mx_); bootOk_ = false; }
  // A new controller in this place: nothing of the old one stays (the counter keeps rising: it is only ever larger).
  void reset() { forgetBoot(); }
  // A proof with the link key over this controller's boot id ("" when the boot id is not known).
  std::string proofNow(const uint8_t link[32], Proof p, const std::string &msg) {
    uint8_t b[4];
    return boot(b) ? proof(link, p, b, msg) : "";
  }
  bool proofOkNow(const uint8_t link[32], Proof p, const std::string &msg, const std::string &mac) {
    uint8_t b[4];
    return boot(b) && proofOk(link, p, b, msg, mac);
  }

 private:
  void forgetBootIf(const uint8_t b[4]) {        // only the boot id that was refused: a newer one heard meanwhile stays
    std::lock_guard<std::mutex> l(mx_);
    if (bootOk_ && !memcmp(boot_, b, 4)) bootOk_ = false;
  }
  std::mutex one_, mx_;
  uint8_t boot_[4] = {0};
  bool bootOk_ = false;
  uint64_t ctr_ = 0;
};
