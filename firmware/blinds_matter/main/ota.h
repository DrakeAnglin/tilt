// A firmware file through the Tilt Hub: every decision about it, with no ESP-IDF in it, so it is tested on the Mac
// (test/ota_test.cpp, run with tools/firmware_tests.sh). What happens to the bytes (flash, the patch, the hash, the
// signature check, the radio) is an OtaSink: hub_link.h has the one for the controller, the test a fake.
//
// The messages (hub_link.h passes them in):
//   'B' size[",d"]["@" epoch] "." mac   begin ("d": a patch; the proof is checked before this sees it)
//   'W' offset (4, big end) + bytes      answered with the next offset wanted ("200", or "409" when one was missed)
//   'E'                                  end: check the file, keep it, restart
// Two kinds of file:
//   full    image | signature (64) | "TILTSIG1"
//   patch   header (64: magic, the running image's SHA-256) | detools patch | signature of the new image (64) |
//           signature of the patch file (64, for the hub) | "TILTDLT1"
// The end of the file is the signatures, so the last 72 (or 136) bytes are held back from the sink until the end.
// Either way the signature checked is of the image the sink ended up with, so a patch can never make anything the
// full file could not.
//
// Also here: the rule for keeping a new firmware on trial (trialVerdict).
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include "logic.h"                               // fwIsOlder

struct OtaSink {
  virtual bool open() = 0;                       // start writing the other slot
  virtual bool openPatch() = 0;                  // after open(), for a patch: start applying it to the running firmware
  virtual bool write(const uint8_t *b, size_t n) = 0;   // file bytes: the image, or the patch after its header
  virtual bool finishPatch() = 0;                // the patch is all in: finish what it makes
  virtual void closePatch() = 0;
  virtual void hash(uint8_t out[32]) = 0;        // SHA-256 of the image written (for a patch: what it made)
  virtual bool verify(const uint8_t hash[32], const uint8_t sig[64]) = 0;   // the release key signed this hash
  virtual bool finalize() = 0;                   // the image is complete and valid
  virtual bool newVersion(std::string &v) = 0;   // the version inside the image written
  virtual bool setBoot() = 0;                    // start from it next time
  virtual void abort() = 0;                      // drop what was written (and the patch, if one is open)
  virtual bool runningSha(uint8_t out[32]) = 0;  // the running image's SHA-256, as esptool appends it
  // Around the update: the radio stays on while a file comes in; the blinds stop first; checking in fast on each piece.
  virtual void radio(bool on) = 0;
  virtual void stopBlinds() = 0;
  virtual void fastPoll() = 0;
  virtual void accepted() = 0;                   // save what must survive, then restart soon
  virtual void log(const std::string &line) = 0; // the event log
  virtual ~OtaSink() {}
};

const char OTA_SIG_MAGIC[8] = {'T', 'I', 'L', 'T', 'S', 'I', 'G', '1'};
const char OTA_DLT_MAGIC[8] = {'T', 'I', 'L', 'T', 'D', 'L', 'T', '1'};
const uint32_t OTA_PATCH_MAGIC = 0xfccdde10;
const uint32_t OTA_STALL_MS = 30000;             // nothing for this long: the update is stopped
const int OTA_PIECE_MAX = 1200;

struct OtaReply { const char *status; std::string out; };

class OtaReceiver {
 public:
  // running: this firmware's version (FW_VERSION): a file may not be older.
  OtaReceiver(OtaSink &s, const char *running) : sink(s), runningVersion(running) {}

  // 'B'. spec: what came before the proof ("size", ",d", "@epoch"). epochNow: this controller's clock (seconds);
  // allowed: an owner opened the window.
  OtaReply begin(const std::string &spec, long epochNow, bool allowed, uint32_t nowMs) {
    // The begin carries the hub's time ("@epoch"): each one must be newer than the last, so a recorded one does nothing.
    // (A hub from before this sends none: still accepted, owner-allowed window only.)
    size_t at = spec.find('@');
    if (at != std::string::npos) {
      long tb = atol(spec.c_str() + at + 1);
      if (tb <= lastB || (epochNow > 1700000000 && labs(tb - epochNow) > 600)) return {"403", "{\"err\":\"an old update request\"}"};
      lastB = tb;
    }
    if (!allowed) return {"403", "{\"err\":\"updates are locked: the owner must allow them from the app\"}"};
    if (active) stopNow();
    active = false;
    last = nowMs;
    sink.stopBlinds();
    delta = spec.find(",d") != std::string::npos;
    // The sink erases as the pieces come in, not all at once: erasing 1.9 MB stops the radio for many seconds.
    if (!sink.open()) return {"500", "{\"err\":\"could not start the update\"}"};
    if (delta && !sink.openPatch()) { sink.abort(); return {"500", "{\"err\":\"could not start the patch\"}"}; }
    hdrN = 0; got = 0; tailN = 0; good = true; active = true;
    size_t c = spec.find(',');
    sink.log("update through the hub: " + spec.substr(0, c < spec.size() ? c : spec.size()) + " bytes" + (delta ? " (a patch)" : ""));
    sink.fastPoll();
    sink.radio(true);
    return {"200", "0"};
  }

  // 'W': offset (4, big end) + bytes.
  OtaReply piece(const std::string &in, uint32_t nowMs) {
    if (!active) return noUpdate();
    last = nowMs;
    sink.fastPoll();
    if (in.size() < 5) return {"400", std::to_string(got)};
    const uint8_t *b = (const uint8_t *)in.data();
    uint32_t off = (uint32_t)b[0] << 24 | b[1] << 16 | b[2] << 8 | b[3];
    if (off != got) return {"409", std::to_string(got)};   // missed one: send from here again
    int n = (int)in.size() - 4, T = tailLen();
    if (n > OTA_PIECE_MAX) return {"400", std::to_string(got)};
    memcpy(buf, tail, tailN);
    memcpy(buf + tailN, b + 4, n);
    int have = tailN + n, wr = have > T ? have - T : 0;
    if (wr && good) good = delta ? feedPatch(buf, wr) : sink.write(buf, wr);
    tailN = have - wr;
    memcpy(tail, buf + wr, tailN);
    got += n;
    return {good ? "200" : "500", std::to_string(got)};
  }

  // 'E'. An 'E' after the update is over gets the answer the last one got, for 30 seconds (its answer was lost).
  OtaReply end(uint32_t nowMs) {
    if (!active) {
      if (lastEnd.status && nowMs - lastEndAt < 30000) return lastEnd;
      return noUpdate();
    }
    last = nowMs;
    lastEnd = check();
    lastEndAt = nowMs ? nowMs : 1;
    return lastEnd;
  }

  // Nothing came for 30 seconds while a file was coming in. stalled() is for the blinds task (it only asks);
  // stopIfStalled() is for the task that runs the update.
  bool stalled(uint32_t nowMs) const { return active && (int32_t)(nowMs - last) > (int32_t)OTA_STALL_MS; }
  bool stopIfStalled(uint32_t nowMs) {
    if (!stalled(nowMs)) return false;
    active = false;
    stopNow();
    sink.log("update through the hub stopped (nothing came for 30 s)");
    return true;
  }
  bool busy(uint32_t nowMs) const { return active && (int32_t)(nowMs - last) < (int32_t)OTA_STALL_MS; }
  bool going() const { return active; }

 private:
  OtaSink &sink;
  const char *runningVersion;
  volatile bool active = false;                  // set by the update's task, read by the blinds task
  volatile uint32_t last = 0;
  bool delta = false, good = false;
  uint32_t got = 0;
  uint8_t tail[136];
  int tailN = 0;
  uint8_t hdr[64];
  uint8_t buf[OTA_PIECE_MAX + 136];              // the tail held back, then this piece
  int hdrN = 0;
  long lastB = 0;
  OtaReply lastEnd = {nullptr, ""};
  uint32_t lastEndAt = 0;

  int tailLen() const { return delta ? 136 : 72; }
  static OtaReply noUpdate() { return {"409", "{\"err\":\"no update going\"}"}; }
  void stopNow() {
    sink.abort();
    sink.radio(false);
  }
  // The patch bytes as they come: first its header (made for this exact firmware?), then the patch itself.
  bool feedPatch(const uint8_t *b, int n) {
    if (hdrN < 64) {
      int k = n < 64 - hdrN ? n : 64 - hdrN;
      memcpy(hdr + hdrN, b, k);
      hdrN += k; b += k; n -= k;
      if (hdrN == 64) {
        uint8_t mine[32];
        uint32_t magic = hdr[0] | hdr[1] << 8 | hdr[2] << 16 | (uint32_t)hdr[3] << 24;
        if (magic != OTA_PATCH_MAGIC || !sink.runningSha(mine) || memcmp(mine, hdr + 4, 32)) {
          sink.log("update refused: the patch is for another firmware");
          return false;
        }
      }
    }
    return n <= 0 || sink.write(b, n);
  }
  OtaReply check() {
    active = false;
    sink.radio(false);
    if (delta && good) good = sink.finishPatch();
    if (delta) sink.closePatch();
    int T = tailLen();
    bool signedFile = good && tailN == T && !memcmp(tail + T - 8, delta ? OTA_DLT_MAGIC : OTA_SIG_MAGIC, 8);
    uint8_t h[32];
    sink.hash(h);
    if (!good) { sink.abort(); return {"500", delta ? "{\"err\":\"the patch did not fit this firmware\"}" : "{\"err\":\"the update broke off\"}"}; }
    // The image's signature is the first 64 bytes of the end, for both kinds.
    if (!signedFile || !sink.verify(h, tail)) { sink.abort(); sink.log("update refused: bad signature"); return {"403", "{\"err\":\"the file's signature is not valid\"}"}; }
    if (!sink.finalize()) return {"500", "{\"err\":\"the file was not accepted\"}"};
    std::string v;
    bool haveV = sink.newVersion(v);
    if (!haveV || fwIsOlder(v.c_str(), runningVersion)) {
      sink.log(haveV ? "update refused: " + v + " is older than " + runningVersion : std::string("update refused: its version could not be read"));
      return {"403", "{\"err\":\"that firmware is older than the one it runs\"}"};
    }
    if (!sink.setBoot()) return {"500", "{\"err\":\"the file was not accepted\"}"};
    sink.log("signed update accepted (through the hub)");
    sink.accepted();
    return {"200", "{\"ok\":1}"};
  }
};

// ---- a new firmware on trial: kept once Thread to the Tilt Hub has worked for a minute; dropped (back to the one
// before) if, five minutes after it started, it has a hub to reach and has not reached it.
enum TrialVerdict { TRIAL_WAIT, TRIAL_KEEP, TRIAL_ROLLBACK };
// The link counts as up when the hub was heard (proven) lately, or Thread to it worked in the last 2 minutes.
inline bool trialLinkUp(bool hubOk, uint32_t hubLinkSeen, uint32_t now) { return hubOk || (hubLinkSeen && now - hubLinkSeen < 120000); }
// Since when the link has been up (millis, 0 = it is not).
inline uint32_t trialLinkSince(uint32_t since, bool up, uint32_t now) { return !up ? 0 : since ? since : now ? now : 1; }
inline TrialVerdict trialVerdict(uint32_t now, uint32_t linkUpSince, bool hubJoined) {
  if (linkUpSince && now - linkUpSince > 60000) return TRIAL_KEEP;
  if (!linkUpSince && now > 300000 && hubJoined) return TRIAL_ROLLBACK;   // setup is done, and no hub
  return TRIAL_WAIT;
}
