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
check(TiltWords.away(lastSeen: seenAt.addingTimeInterval(-30), now: seenAt) == "Unreachable · last seen just now", "unreachable, seen moments ago")
check(TiltWords.away(lastSeen: nil) == "Unreachable", "never seen")
check(TiltWords.away(lastSeen: seenAt.addingTimeInterval(-7200), now: seenAt).hasPrefix("Unreachable · last seen 2"), "unreachable, with when it was last seen")

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
do { try await fc.setName("Den"); check(false, "a refusal throws") } catch { check(error.localizedDescription == "Only the owner can do that", "the controller's reason is passed on") }
try await fc.go(blind: 2, tilt: -40, solo: true)
check(await fake.sent.last == "/api/go?b=2&t=-40&solo=1", "the client builds the command")

// ---- typed settings: the names firmware web.h hSet knows
func sentBy(_ what: (ControllerClient) async throws -> Void) async -> String? { try? await what(fc); return await fake.sent.last }
check(await sentBy { try await $0.setName("Den") } == "/api/set?k=name&v=Den", "name")
check(await sentBy { try await $0.setCloseUp(false) } == "/api/set?k=closeUp&v=0", "close up")
check(await sentBy { try await $0.setFollow(true) } == "/api/set?k=sync&v=1", "follow each other")
check(await sentBy { try await $0.setSameTime(false) } == "/api/set?k=par&v=0", "same time")
check(await sentBy { try await $0.setHomeSeparate(true) } == "/api/set?k=hksep&v=1", "Home separate")
check(await sentBy { try await $0.setLocation(latitude: 41.88, longitude: -87.63) } == "/api/set?k=loc&v=41%2E880%2C%2D87%2E630", "location")
check(await sentBy { try await $0.setTimeZone("CST6CDT,M3.2.0,M11.1.0", name: "America/Chicago") } == "/api/set?k=tz&v=CST6CDT%2CM3%2E2%2E0%2CM11%2E1%2E0&n=America%2FChicago", "time zone")
check(await sentBy { try await $0.setTuning(.stall, 900) } == "/api/set?k=tune.stall&v=900", "stall tuning")
check(await sentBy { try await $0.setBlindName(blind: 1, "Left") } == "/api/set?k=b1.name&v=Left", "a blind's name")
check(await sentBy { try await $0.setHidden(blind: 2, true) } == "/api/set?k=b2.hid&v=1", "hide a blind")
check(await sentBy { try await $0.setSpeed(blind: 0, 80) } == "/api/set?k=b0.speed&v=80", "a blind's speed")
check(await sentBy { try await $0.setFavorite(blind: 1, -50) } == "/api/set?k=b1.fav&v=%2D50", "a blind's favorite")
check(await sentBy { try await $0.setMotorSign(blind: 0, -1) } == "/api/set?k=b0.sign&v=%2D1", "a motor's direction")

// ---- the shared wire fixture (firmware/blinds_matter/test/wire/, made from known firmware state and checked by the
// firmware's own tests too): the app reads the same /api/cfg and writes the same slot command
let wireDir = URL(fileURLWithPath: CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "../../firmware/blinds_matter/test/wire")
let cfgData = try Data(contentsOf: wireDir.appendingPathComponent("cfg.json"))
let wcfg = try JSONDecoder().decode(ControllerConfig.self, from: cfgData)
let wsched = try JSONDecoder().decode(SchedConfig.self, from: cfgData)
check(wcfg.limits == ControllerLimits(ports: 3, slots: 8) && wsched.limits == wcfg.limits, "the limits are read from /api/cfg")
check(wcfg.name == "Den \"East\"" && wcfg.b.count == wcfg.limits.ports && wcfg.b[2].hid == 1 && wcfg.b[1].fav == -50 && wcfg.par == 0 && wcfg.tzn == "America/Chicago", "the config decodes")
check(wsched.sched.count == wsched.limits.slots && wsched.sched[2].gid == 4_000_000_000 && wsched.sched[2].off == -15 && wsched.lat == 41.88, "the Schedule slots decode")
let slotWrite = try String(contentsOf: wireDir.appendingPathComponent("slot_write.txt"), encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines)
check(ControllerClient.scheduleCommand(slot: 2, wsched.sched[2]) == slotWrite, "writing slot 2 back is the fixture's command")
try await fc.setSchedule(slot: 2, wsched.sched[2])
check(await fake.sent.last == slotWrite, "the client sends that command")
let oldCfg = Data(#"{"name":"Den","closeUp":1,"sync":0,"tzn":"","b":[],"sched":[]}"#.utf8)
check((try? JSONDecoder().decode(ControllerConfig.self, from: oldCfg))?.limits == .fallback && (try? JSONDecoder().decode(SchedConfig.self, from: oldCfg))?.limits == .fallback,
      "older firmware without limits: 3 Ports and 8 slots")
check(Schedule.everyPort([("den", 2), ("hall", 3)]).count == 5, "every Port follows each controller's limits")

// ---- Schedules on the controllers' slots (Shared/SchedulePlan.swift)
func emptySlots() -> [SchedSlot] { Array(repeating: .empty, count: 8) }
func apply(_ ws: [SlotWrite], to slots: inout [String: [SchedSlot]]) { for w in ws { slots[w.controller]![w.slot] = w.value } }
func both(_ slots: [String: [SchedSlot]]) -> [Schedule] { SchedulePlan.schedules(slots.keys.sorted().map { ($0, slots[$0]!) }) }

var rooms: [String: [SchedSlot]] = ["den": emptySlots(), "hall": emptySlots()]
let wake = Schedule(id: 42, days: 62, kind: 1, minute: 0, offset: 15, tilt: -100, ramp: 10,
                    targets: [BlindTarget(controller: "den", blind: 0), BlindTarget(controller: "den", blind: 2), BlindTarget(controller: "hall", blind: 1)])
apply(try SchedulePlan.writes(wake, slots: rooms), to: &rooms)
check(both(rooms) == [wake], "a Schedule saved to two controllers loads back the same")
check(rooms["den"]![0].mask == 0b101 && rooms["hall"]![0].mask == 0b010 && rooms["hall"]![0].gid == 42, "one slot on each, same gid")

// legacy slot (gid 0): stable id, edited in place
var legacy: [String: [SchedSlot]] = ["den": emptySlots()]
legacy["den"]![3] = SchedSlot(on: 1, days: 127, mask: 1, min: 420, tilt: 0, kind: 0, off: 0, ramp: 0, gid: 0)
let first = both(legacy), again = both(legacy)
check(first.count == 1 && first[0].id == again[0].id && first[0].id == SchedulePlan.legacyId(controller: "den", slot: 3), "a gid-0 slot has the same id on every load")
var edited = first[0]; edited.minute = 450
let legacyWrites = try SchedulePlan.writes(edited, slots: legacy)
check(legacyWrites.count == 1 && legacyWrites[0].slot == 3 && legacyWrites[0].value.gid == edited.id, "editing a gid-0 slot rewrites that slot and gives it a gid")
apply(legacyWrites, to: &legacy)
check(both(legacy) == [edited] && legacy["den"]!.filter { $0.mask != 0 }.count == 1, "no duplicate after the edit")

// moving a Schedule's blinds to another controller clears the old slot
var moved = wake; moved.targets = [BlindTarget(controller: "hall", blind: 0)]
apply(try SchedulePlan.writes(moved, slots: rooms), to: &rooms)
check(rooms["den"]!.allSatisfy { $0.mask == 0 } && both(rooms) == [moved], "the old controller's slot is cleared")
apply(try SchedulePlan.writes(moved, delete: true, slots: rooms), to: &rooms)
check(both(rooms).isEmpty, "delete clears every slot")

// a full controller: nothing is written
var full: [String: [SchedSlot]] = ["den": emptySlots(), "hall": (0..<8).map { SchedSlot(on: 1, days: 127, mask: 1, min: $0, tilt: 0, kind: 0, off: 0, ramp: 0, gid: UInt32($0 + 100)) }]
do { _ = try SchedulePlan.writes(wake, slots: full); check(false, "a full controller throws") }
catch { check(error == .full(controller: "hall"), "the full controller is named") }
do { _ = try SchedulePlan.writes(wake, slots: ["den": emptySlots()]); check(false, "an unread controller throws") }
catch { check(error == .notRead(controller: "hall"), "the unread controller is named") }
full["hall"]![5].gid = 42                          // it already holds this Schedule: reuse that slot
check((try? SchedulePlan.writes(wake, slots: full))?.first { $0.controller == "hall" }?.slot == 5, "the slot already holding it is reused")
// a controller with 2 Ports: a target on a third Port is left out of its mask
let twoPorts = try SchedulePlan.writes(wake, slots: ["den": emptySlots(), "hall": emptySlots()], ports: ["den": 2])
check(twoPorts.first { $0.controller == "den" }?.value.mask == 0b001, "the mask follows the controller's Ports")

// ---- Bluetooth setup (Shared/Bluetooth.swift): the same frames as Frame
final class FakeRadio: @unchecked Sendable {      // a controller in setup mode, answering over Bluetooth
    var written: [Data] = []
    let lock = NSLock()
    func exchange(_ d: Data) -> Data {
        lock.lock(); defer { lock.unlock() }
        written.append(d)
        guard d.first == UInt8(ascii: "X") else { return Data("4{}".utf8) }
        let nonce = d.dropFirst(9).prefix(12)
        let command = try! AES.GCM.open(AES.GCM.SealedBox(nonce: AES.GCM.Nonce(data: nonce), ciphertext: d.dropFirst(21).dropLast(16), tag: d.suffix(16)),
                                        using: fkey, authenticating: Data("blinds-v1".utf8) + fcid)
        let c = String(decoding: command, as: UTF8.self)
        let answer = #"{"ok":1}"#
        let rn = Data(repeating: 7, count: 12)
        let box = try! AES.GCM.seal(Data(answer.utf8), using: fkey, nonce: AES.GCM.Nonce(data: rn), authenticating: Data("blinds-v1r".utf8) + fcid + nonce)
        return Data("2".utf8) + rn + box.ciphertext + box.tag
    }
}
let radio = FakeRadio()
let wire = BluetoothWire { radio.exchange($0) }
let bp = Paired(cid: fcid, key: fkey, owner: true)
let ble = wire.client(bp, boot: fboot, clock: { 1795319000123 })
try await ble.go(blind: 0, tilt: 50)
check(radio.written.first == Data("X".utf8) + fpkt, "a Bluetooth command is 'X' + the same frame as Frame.seal")
_ = try? await ble.state()
check(radio.written.last.map { $0.dropFirst(13).prefix(8).hex } == "000001a20159ec3c", "the counter rises when the clock does not")

print("\(passed) passed, \(failures) failed")
exit(failures == 0 ? 0 : 1)
