// Tests for the parts of Tilt that must agree with the controller's firmware: the version check, the codes and proofs
// derived from a key, the sealed-command format, and the demo room's answers. Run with tools/app_tests.sh.
// Reference values come from the firmware's own formulas (sec.h, web.h), computed in Python.
import CryptoKit
import Foundation

var failures = 0, passed = 0
func check(_ ok: Bool, _ what: String, file: String = #file, line: Int = #line) {
    if ok { passed += 1 } else { failures += 1; print("FAIL line \(line): \(what)") }
}

// ---- firmware versions
check(Api.tooOld("2.2.0-dev8"), "dev8 is older than the app needs")
check(!Api.tooOld(Api.minFirmware), "the minimum itself is fine")
check(!Api.tooOld("2.2.0-dev11"), "dev11 is newer than dev9")
check(!Api.tooOld("2.2.0"), "a release is newer than its dev builds")
check(Api.tooOld("2.1.9"), "2.1.9 is older")
check(!Api.tooOld("3.0.0-dev1"), "3.0 dev is newer")
check(Api.version("2.2.0-dev10").lexicographicallyPrecedes(Api.version("2.2.0-dev11")), "dev10 before dev11 (not as text)")

// ---- values derived from a pairing key must match the firmware
let key = SymmetricKey(data: Data(0..<32))
let paired = Paired(cid: Data(repeating: 1, count: 8), key: key, owner: false, waiting: true)
check(paired.code == "1585", "the 4-digit join code matches the firmware's askCode (got \(paired.code))")
check(Data(HMAC<SHA256>.authenticationCode(for: Data("removed".utf8), using: key)).prefix(16).hex == "4dfa3acdc02eec5dcd9abb405f387e13", "the removal proof matches the firmware")
check(Data(HMAC<SHA256>.authenticationCode(for: Data("confirm".utf8), using: key)).prefix(8).hex == "ae667c53b3e30bd2", "the pairing check matches the firmware")

// ---- the secured message format, byte for byte against the firmware's way (reference made in Python with
// tools/blinds_client.py's seal / open_reply, which mirror sec.h)
let fkey = SymmetricKey(data: Data(0..<32)), fcid = Data(hex: "0102030405060708")!, fboot = Data(hex: "a1b2c3d4")!
let (fpkt, fnonce) = try Frame.seal("/api/go?b=0&t=50", key: fkey, cid: fcid, boot: fboot, counter: 1795319000123)
check(fpkt.hex == "0102030405060708a1b2c3d4000001a20159ec3b391748e3cd237a453de6fee48b5584e189703cda3269ec699a6a459b137d5402", "a sealed command matches the firmware's format byte for byte")
check(fnonce.hex == "a1b2c3d4000001a20159ec3b", "nonce = boot id + big-endian counter")
let freply = Data(hex: "0f0e0d0c0b0a090807060504df12de3779ed9ed30c4b2482c14b48f05e05612769ee60b3")!
check((try? Frame.open(freply, key: fkey, cid: fcid, nonce: fnonce)).map { String(decoding: $0, as: UTF8.self) } == "{\"ok\":1}", "a controller reply opens")
var tampered = freply; tampered[20] ^= 1
check((try? Frame.open(tampered, key: fkey, cid: fcid, nonce: fnonce)) == nil, "a changed reply is refused")
check((try? Frame.open(freply, key: fkey, cid: fcid, nonce: Data(hex: "a1b2c3d4000001a20159ec3c")!)) == nil, "a reply to another command is refused")

// ---- wording and battery rules (Shared/Words.swift: one place for the app, the widget and the notices)
check(TiltWords.long(5) == "Open" && TiltWords.long(-7.9) == "Open", "within 8% of level is open")
check(TiltWords.long(93) == "Closed, slats up" && TiltWords.long(-100) == "Closed, slats down", "past 92% is closed")
check(TiltWords.long(50) == "50% toward up", "in between")
check(TiltWords.action(0) == "Open" && TiltWords.action(100) == "Close up" && TiltWords.action(-100) == "Close down", "schedule actions")
let low = ControllerState.Battery(v: 3.6, pct: 15, st: "battery", low: 0), ok = ControllerState.Battery(v: 3.9, pct: 70, st: "battery", low: 0)
let chargingLow = ControllerState.Battery(v: 3.6, pct: 15, st: "charging", low: 0), empty = ControllerState.Battery(v: 3.3, pct: 2, st: "charging", low: 1)
check(low.isLow && !ok.isLow, "under 20% on battery is low")
check(!chargingLow.isLow, "charging is not low")
check(empty.isLow && empty.tooLowToMove, "too low to move is low even while charging")

// ---- asleep / not reachable wording
let seenAt = Date(timeIntervalSince1970: 1_800_000_000)
check(TiltWords.away(asleep: true, lastSeen: seenAt.addingTimeInterval(-30), now: seenAt) == "Asleep · seen just now", "asleep, seen moments ago")
check(TiltWords.away(asleep: false, lastSeen: nil) == "Not reachable", "never seen")
check(TiltWords.away(asleep: false, lastSeen: seenAt.addingTimeInterval(-7200), now: seenAt).hasPrefix("Not reachable · last seen 2"), "unreachable, with when it was last seen")

// ---- command strings
check(Api.go(blind: 1, tilt: -100, solo: true) == "/api/go?b=1&t=-100&solo=1", "one blind, solo")
check(Api.goAll(to: "close", gently: 10) == "/api/go?b=all&to=close&ramp=10", "a gentle move for all")
check(Api.goAll(to: "open") == "/api/go?b=all&to=open", "no ramp when not gentle")
check(Api.set("name", "Den & Hall") == "/api/set?k=name&v=Den%20%26%20Hall", "values are escaped")

// ---- the demo room answers like a controller
let demo = ControllerClient(transport: Demo.shared)
let s = try await demo.state()
check(s.b.count == 3 && s.b.allSatisfy(\.ready), "the demo has three ready blinds")
try await demo.goAll(to: "close")
let moving = try await demo.state()
check(moving.mv >= 0, "after Close the demo blinds are moving")
try await Task.sleep(for: .seconds(3.5))
let done = try await demo.state()
check(done.mv == -1 && done.b.allSatisfy { ($0.tilt ?? 0) == 100 }, "after a few seconds they are closed (slats up)")
check((try? await demo.homeSetupCode()) == nil, "Apple Home says it is not available in the demo")

// ---- the client against a fake controller: no network, no crypto
actor FakeController: ControllerTransport {
    var sent: [String] = []
    var host: String { "fake" }
    func move(to host: String) {}
    func call(_ command: String) async throws -> Data {
        sent.append(command)
        if command.hasPrefix("/api/keys") { return Data(#"{"keys":[{"cid":"aa","name":"Alex","owner":1,"me":1,"wait":0,"code":""},{"cid":"bb","name":"Sam","owner":0,"me":0,"wait":1,"code":"1234"}]}"#.utf8) }
        if command.hasPrefix("/api/revoke") { return Data(#"{"ok":1,"proof":"abc"}"#.utf8) }
        if command.hasPrefix("/api/set") { return Data(#"{"ok":0,"err":"only the owner can do that"}"#.utf8) }
        return Data(#"{"ok":1}"#.utf8)
    }
}
let fake = FakeController(), fc = ControllerClient(transport: fake)
let ppl = try await fc.people()
check(ppl.count == 2 && ppl[1].wait == 1 && ppl[1].code == "1234", "people are decoded")
check((try await fc.revoke(cid: "bb")) == "abc", "remove returns the proof")
do { try await fc.set("name", "Den"); check(false, "a refusal throws") } catch { check(error.localizedDescription == "Only the owner can do that", "the controller's reason is passed on") }
try await fc.go(blind: 2, tilt: -40, solo: true)
check(await fake.sent.last == "/api/go?b=2&t=-40&solo=1", "the client builds the command")

print("\(passed) passed, \(failures) failed")
exit(failures == 0 ? 0 : 1)
