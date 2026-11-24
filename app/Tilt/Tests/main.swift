// Tests for the parts of Tilt that must agree with the controller's firmware: the version check, the codes and proofs
// derived from a key, the sealed-command format, and the demo room's answers. Run with tools/app_tests.sh.
// Reference values come from the firmware's own formulas (sec.h, web.h), computed in Python.
import CryptoKit
import Foundation
import Matter

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
check(Api.go(blind: 1, tilt: -100) == "/api/go?b=1&t=-100", "one blind")
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
try await fc.go(blind: 2, tilt: -40)
check(await fake.sent.last == "/api/go?b=2&t=-40", "the client builds the command")

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

// ---- Apple Home in one tap (issue #50): the code goes to Apple's add screen as a Matter payload
// The Matter spec's example device: passcode 20202021, discriminator 3840.
let specQR = "MT:-24J0AFN00KA0648G00", specCode = "34970112332"
let sp = HomeSetup.payload(qr: specQR, code: specCode)
check(sp?.setupPasscode == 20202021 && sp?.discriminator == 3840, "the Matter spec's example QR reads as passcode 20202021, discriminator 3840")
check(HomeSetup.payload(qr: specQR, code: "3497-011-2332") != nil, "the typed code may have dashes and spaces")
check(HomeSetup.payload(qr: specQR, code: "") != nil, "no typed code: the QR alone is enough")
// A code made by Apple's own Matter library, as the hub makes its own.
let made = MTRSetupPayload(setupPasscode: 31415926, discriminator: 1234)
if let q = made.qrCodeString(), let m = made.manualEntryCode() {
    check(HomeSetup.payload(qr: q, code: m)?.setupPasscode == 31415926, "a QR and typed code made together are accepted")
    check(HomeSetup.payload(qr: q, code: specCode) == nil, "a typed code with another passcode: refused (the app shows the code instead)")
} else { check(false, "Apple's Matter library made a QR and a typed code") }
check(HomeSetup.payload(qr: "", code: specCode) == nil, "no QR: no request")
check(HomeSetup.payload(qr: "MT:not-a-code", code: "") == nil, "a broken QR: no request")
check(HomeSetup.payload(qr: "X-HM://0024ABCDE1234", code: "") == nil, "a HomeKit (not Matter) code: no request")
// "Added to Apple Home": the hub's own word is not enough (Apple leaves its iCloud Keychain connection behind when the
// hub is removed in the Home app, 2026-11-23), so it is checked against Apple Home's accessories.
let keychain = HomeSetup.HubHome(node: "00000000A1B2C3D4", vendor: 4996), home = HomeSetup.HubHome(node: "0000000012345678", vendor: 4937)
check(!HomeSetup.inHome(hubSays: true, hubHomes: [keychain], appleNodes: [0x99, 0x42]), "removed in the Home app, only the Keychain connection left: not added")
check(HomeSetup.inHome(hubSays: true, hubHomes: [keychain, home], appleNodes: [0x12345678]), "Apple Home has an accessory with the hub's ID: added")
check(HomeSetup.inHome(hubSays: true, hubHomes: [keychain, home], appleNodes: [0x77]), "both of Apple's connections there (Apple 4937 and Keychain 4996), IDs not matching: still added")
check(HomeSetup.inHome(hubSays: true, hubHomes: [keychain, .init(node: "0000000012345678", vendor: 4996)], appleNodes: [0x77]), "two Apple Keychain-numbered connections: still added")
check(!HomeSetup.inHome(hubSays: true, hubHomes: [keychain, .init(node: "00000000000000AA", vendor: 4447)], appleNodes: [0x77]), "the Keychain leftover plus another maker's home (Alexa): not in Apple Home")
check(!HomeSetup.inHome(hubSays: false, hubHomes: [], appleNodes: [0x12345678]) && HomeSetup.inHome(hubSays: true, hubHomes: [], appleNodes: []), "a hub too old to give its IDs: its own word")
check(HomeSetup.inHome(hubSays: true, hubHomes: [home], appleNodes: nil) && !HomeSetup.inHome(hubSays: false, hubHomes: [home], appleNodes: nil), "no Home access: the hub's own word")
check(HomeSetup.inHome(hubSays: true, hubHomes: [.init(node: "not hex", vendor: 4996)], appleNodes: [0x12345678]), "an ID that can't be read is skipped (then the hub's own word)")
check(!HomeSetup.inHome(hubSays: true, hubHomes: [home], appleNodes: []), "no accessories in Apple Home: not added")

// "Added to Alexa": a home connection made by Amazon (4631), seen on the owner's hub as "Alexa-4" (2026-11-24).
let alexa = HomeSetup.HubHome(node: "07C60AA8A4CB54F0", vendor: 4631)
check(HomeSetup.inAlexa(hubHomes: [keychain, home, alexa]), "Apple Home and Alexa both: in Alexa")
check(!HomeSetup.inAlexa(hubHomes: [keychain, home]), "Apple's two connections only: not in Alexa")
check(!HomeSetup.inAlexa(hubHomes: []) && !HomeSetup.inAlexa(hubHomes: [.init(node: nil, vendor: nil)]), "no homes, or a hub too old to give makers: not in Alexa")
check(!HomeSetup.inAlexa(hubHomes: [.init(node: "00000000000000AA", vendor: 4447)]), "another maker's home: not Alexa")
check(!HomeSetup.inHome(hubSays: true, hubHomes: [alexa], appleNodes: [0x77]), "in Alexa only: not in Apple Home")
// ---- the Tilt Hub client (Shared/HubClient.swift, issue #82): commands, answers, the demo hub
/// What a fake device was sent, in order, across devices (to check the order of a flow).
final class Recorder: @unchecked Sendable {
    private let lock = NSLock(); private var items: [String] = []
    func add(_ s: String) { lock.lock(); items.append(s); lock.unlock() }
    var all: [String] { lock.lock(); defer { lock.unlock() }; return items }
    func count(_ prefix: String) -> Int { all.filter { $0.hasPrefix(prefix) }.count }
}
final class Cell<T>: @unchecked Sendable {
    private let lock = NSLock(); private var v: T
    init(_ v: T) { self.v = v }
    var value: T { get { lock.lock(); defer { lock.unlock() }; return v } set { lock.lock(); v = newValue; lock.unlock() } }
}
/// A hub or controller that answers from a script and writes what it was sent to a Recorder.
struct ScriptedDevice: ControllerTransport {
    let name: String, log: Recorder, address: String
    let answer: @Sendable (String) -> String
    var host: String { address }
    func move(to host: String) async {}
    func call(_ c: String) async throws -> Data { log.add("\(name) \(c)"); return Data(answer(c).utf8) }
}
func cmdPath(_ c: String) -> String { String(c.split(separator: "?").first ?? "") }

check(HubApi.info == "/api/info" && HubApi.network == "/api/net" && HubApi.homeCode == "/api/homecode" && HubApi.shareCode == "/api/sharecode", "hub reading commands")
check(HubApi.backup(id: "a1") == "/api/backup?id=a1" && HubApi.replace(old: "a1", new: "b2") == "/api/replace?old=a1&new=b2", "backup and replace")
check(HubApi.allowUpload(controller: "a1") == "/api/upload?id=a1" && HubApi.allowHubUpdate == "/api/hubupdate" && HubApi.resetPeople == "/api/resetpeople", "updates and people")
check(HubApi.base("10.0.0.2") == "10.0.0.2/hub" && HubApi.controller("a1", hubHost: "10.0.0.2") == "10.0.0.2/c/a1", "the hub's addresses")
check(Api.hubKey(cid: "0011") == "/api/hubkey?cid=0011", "tell a controller the hub's key")

// /api/info, from the shared fixture (in the shape of the hub's builder, firmware/tilt_hub/main/hub.cpp infoJson)
let hubInfoData = try Data(contentsOf: wireDir.appendingPathComponent("hub_info.json"))
let hi = try? JSONDecoder().decode(HubInfo.self, from: hubInfoData)
check(hi?.fw == "0.3.5" && hi?.ip == "192.168.1.40" && hi?.ch == 15 && hi?.home == 1 && hi?.homes?.first?.vendor == 4937, "hub_info.json: the hub's own fields")
check(hi?.c.count == 2 && hi?.c[0].hubCid == "0011223344556677" && hi?.c[0].own == 1 && hi?.c[0].signal == -61, "hub_info.json: a controller on the hub")
check(hi?.c[1].notResponding == true && hi?.c[1].signal == nil && hi?.c[1].ota == 4 && hi?.c[1].otaErr == "the controller stopped answering", "hub_info.json: a silent controller whose update failed")
check(hi?.new.first?.ble == "aa:bb:cc:dd:ee:ff", "hub_info.json: a new controller nearby")
let renamed = Data(String(decoding: hubInfoData, as: UTF8.self).replacingOccurrences(of: "\"seenS\"", with: "\"seen\"").utf8)
check((try? JSONDecoder().decode(HubInfo.self, from: renamed)) == nil, "a renamed key in /api/info fails to decode (not silently nil)")
let noHomes = #"{"ok":1,"fw":"0.2.3","up":1,"ip":"x","wifi":0,"ch":11,"c":[],"new":[]}"#
check((try? JSONDecoder().decode(HubInfo.self, from: Data(noHomes.utf8)))?.homes == nil, "a hub from before homes (0.2.6) still decodes")

let hlog = Recorder()
let hc = HubClient(transport: ScriptedDevice(name: "hub", log: hlog, address: "10.0.0.2/hub") { c in
    switch cmdPath(c) {
    case HubApi.homeCode: #"{"ok":0,"err":"a home app is adding the Tilt Hub right now: try again in a minute"}"#
    case HubApi.shareCode: #"{"ok":1,"code":"12345678901","qr":"MT:X","mins":15,"first":1,"homes":[],"home":0}"#
    case HubApi.network: #"{"ok":1,"ds":"0e08"}"#
    case "/api/revoke": #"{"ok":0,"err":"you cannot remove yourself"}"#
    default: #"{"ok":1}"#
    }
})
do { _ = try await hc.homeCode(); check(false, "a refused home code throws") }
catch { check(error.localizedDescription == "A home app is adding the Tilt Hub right now: try again in a minute", "the hub's reason is passed on") }
let share = try? await hc.shareCode()
check(share?.code == "12345678901" && share?.first == true && share?.mins == 15, "a share code is decoded")
check((try? await hc.network()) == "0e08", "the hub's network")
do { try await hc.revoke(cid: "aa"); check(false, "a refused remove throws") } catch { check(error.localizedDescription == "You cannot remove yourself", "a refusal is the hub's words") }
try? await hc.approve(cid: "bb", true); try? await hc.allowUpload(for: "a1")
check(hlog.all.suffix(2) == ["hub /api/approve?cid=bb&ok=1&owner=0", "hub /api/upload?id=a1"], "the hub client builds the commands")

let dh = HubClient.make(host: Demo.host, cid: Data(), key: SymmetricKey(size: .bits256))
let dinfo = try? await dh.info()
check(dinfo?.c.first?.id == Demo.id && dinfo?.c.first?.hubCid == DemoHub.hubCid, "the demo hub decodes as a hub, with the demo room on it")
let dme = (try? await dh.people())?.first?.me, dnet = try? await dh.network()
check(dme == 1 && dnet != nil, "the demo hub answers people and its network")
check((try? await dh.homeCode()) == nil, "the demo hub has no Apple Home")

// ---- adding a controller to the hub (Shared/ControllerOnboarding.swift)
let hubCidOnNew = "00112233aabbccdd"
func hubInfoJSON(_ id: String, hubCid: String?, ota: Int = 0, pct: Int = 0, err: String? = nil) -> String {
    #"{"ok":1,"fw":"0.3.5","up":9,"ip":"10.0.0.2","wifi":-50,"ch":15,"c":[{"id":"\#(id)","name":"Den","fw":"2.2.1","key":1,"seenS":1,"pct":80,"low":0,"rssi":-60,"lqi":3,"ota":\#(ota),"otaPct":\#(pct)"#
        + (err.map { #","otaErr":"\#($0)""# } ?? "") + (hubCid.map { #","hubCid":"\#($0)""# } ?? "") + #","own":1}],"new":[]}"#
}
func stateJSON(_ hkey: Int) -> String { #"{"v":"2.2.1","name":"Den","batt":{"v":3.9,"pct":80,"st":"battery","low":0},"closeUp":1,"sync":0,"mv":-1,"hkey":\#(hkey),"b":[]}"# }
/// A controller on the hub whose people include the hub's request (waiting until approved).
func controllerOnHub(_ log: Recorder, hubWaiting: Cell<Bool>, hkey: Cell<Int>) -> ControllerClient {
    ControllerClient(transport: ScriptedDevice(name: "ctrl", log: log, address: "10.0.0.2/c/new1") { c in
        switch cmdPath(c) {
        case Api.keys: return #"{"keys":[{"cid":"aa","name":"Me","owner":1,"me":1,"wait":0},{"cid":"\#(hubCidOnNew)","name":"Tilt Hub","owner":0,"me":0,"wait":\#(hubWaiting.value ? 1 : 0)}]}"#
        case "/api/approve": hubWaiting.value = false; return #"{"ok":1}"#
        case "/api/hubkey": hkey.value = 1; return #"{"ok":1}"#
        case Api.state: return stateJSON(hkey.value)
        default: return #"{"ok":1}"#
        }
    })
}
struct TestStore: ControllerStore {
    let log: Recorder, client: ControllerClient
    func adopt(_ h: Hello, host: String, paired: Paired) async -> ControllerClient { log.add("adopt \(host)"); return client }
}
func fakeHello(_ id: String, boot: String, net: String?) -> Hello { Hello(id: id, name: "Den", fw: "2.2.1", boot: boot, img: "aaa", owned: 1, home: nil, net: net, hub: nil) }
func collect<S>(_ stream: AsyncThrowingStream<S, Error>) async -> (steps: [S], error: Error?) {
    var steps: [S] = []
    do { for try await s in stream { steps.append(s) }; return (steps, nil) } catch { return (steps, error) }
}

// A controller that started on Wi-Fi firmware, restored from a replaced controller's backup
let olog = Recorder()
let backupHex = String(repeating: "ab", count: 200)       // two pieces of 128 bytes and 72
let ohub = HubClient(transport: ScriptedDevice(name: "hub", log: olog, address: "10.0.0.2/hub") { c in
    switch cmdPath(c) {
    case HubApi.network: #"{"ok":1,"ds":"0e08"}"#
    case "/api/backup": #"{"ok":1,"d":"\#(backupHex)"}"#
    case HubApi.info: hubInfoJSON("new1", hubCid: hubCidOnNew)
    default: #"{"ok":1}"#
    }
})
let looks = Cell(0)
let onb = ControllerOnboarding(transport: ScriptedDevice(name: "ble", log: olog, address: "bluetooth") { _ in #"{"ok":1}"# }, hub: ohub,
                               store: TestStore(log: olog, client: controllerOnHub(olog, hubWaiting: Cell(true), hkey: Cell(0))),
                               hello: fakeHello("new1", boot: "0a0b0c0d", net: nil), paired: Paired(cid: fcid, key: fkey, owner: true), hubHost: "10.0.0.2",
                               look: { host in looks.value += 1; olog.add("look \(host)"); return looks.value < 3 ? nil : fakeHello("new1", boot: "11223344", net: "thread") },
                               sleep: { _ in }, leftBluetooth: { olog.add("left bluetooth") })
let run1 = await collect(onb.run(restore: "old1"))
check(run1.error == nil && run1.steps == [.gettingNetwork, .restoring, .joining, .waitingOnHub, .lettingHubIn, .done], "onboarding steps, in order (\(run1.steps), \(run1.error?.localizedDescription ?? "-"))")
let onbExpected = ["hub /api/net", "hub /api/backup?id=old1",
                "ble /api/restore?o=0&d=\(String(repeating: "ab", count: 128))", "ble /api/restore?o=128&d=\(String(repeating: "ab", count: 72))&end=1",
                "ble /api/hubjoin?ds=0e08", "ble /api/swapfw", "left bluetooth",
                "look 10.0.0.2/c/new1", "look 10.0.0.2/c/new1", "look 10.0.0.2/c/new1", "adopt 10.0.0.2/c/new1",
                "hub /api/info", "ctrl /api/keys", "ctrl /api/approve?cid=\(hubCidOnNew)&ok=1&owner=0", "ctrl /api/hubkey?cid=\(hubCidOnNew)",
                "hub /api/replace?old=old1&new=new1"]
check(olog.all == onbExpected, "restore before joining, wait for it on the hub, keep it, let the hub in, take over the old one's place\n  got \(olog.all.map { String($0.prefix(60)) })")

// A Thread controller that did not reach the hub: the second try only waits for it again
let rlog = Recorder(), reachable = Cell(false)
let rhub = HubClient(transport: ScriptedDevice(name: "hub", log: rlog, address: "10.0.0.2/hub") { c in
    cmdPath(c) == HubApi.info ? hubInfoJSON("new1", hubCid: hubCidOnNew) : cmdPath(c) == HubApi.network ? #"{"ok":1,"ds":"0e08"}"# : #"{"ok":1}"#
})
let ronb = ControllerOnboarding(transport: ScriptedDevice(name: "ble", log: rlog, address: "bluetooth") { _ in #"{"ok":1}"# }, hub: rhub,
                                store: TestStore(log: rlog, client: controllerOnHub(rlog, hubWaiting: Cell(true), hkey: Cell(0))),
                                hello: fakeHello("new1", boot: "0a0b0c0d", net: "thread"), paired: Paired(cid: fcid, key: fkey, owner: true), hubHost: "10.0.0.2",
                                look: { _ in reachable.value ? fakeHello("new1", boot: "0a0b0c0d", net: "thread") : nil }, sleep: { _ in })
let rFirst = await collect(ronb.run(restore: nil))
check(rFirst.error?.localizedDescription.hasPrefix("It did not reach the hub.") == true && rFirst.steps.last == .waitingOnHub, "not on the hub: the reason is shown")
check(rlog.count("ble /api/hubjoin") == 1 && rlog.count("ble /api/swapfw") == 0 && rlog.count("ble /api/reboot") == 0, "a Thread controller joins without switching firmware or restarting")
reachable.value = true
let rSecond = await collect(ronb.run(restore: nil))
check(rSecond.error == nil && rSecond.steps == [.waitingOnHub, .lettingHubIn, .done], "the second try only waits for it on the hub")
check(rlog.count("hub /api/net") == 1 && rlog.count("ble ") == 1, "the hub's network is not asked for or sent again")

// The hub is let in exactly once (the setup flow and the app's model share admitHub)
let alog = Recorder(), waitingHub = Cell(true), knows = Cell(0)
let actrl = controllerOnHub(alog, hubWaiting: waitingHub, hkey: knows)
let ahub = HubClient(transport: ScriptedDevice(name: "hub", log: alog, address: "10.0.0.2/hub") { _ in hubInfoJSON("new1", hubCid: hubCidOnNew) })
let a1 = await ahub.admitHub(on: actrl, controllerId: "new1"), a2 = await ahub.admitHub(on: actrl, controllerId: "new1")
check(a1 == HubAdmission(hubCid: hubCidOnNew, done: true) && a2 == a1, "the hub's request is let in, and the second time it is already in")
check(alog.count("ctrl /api/approve") == 1 && alog.count("ctrl /api/hubkey") == 1, "approved once and its key told once (approve \(alog.count("ctrl /api/approve")), hubkey \(alog.count("ctrl /api/hubkey")))")
check(!alog.all.contains { $0.hasPrefix("ctrl /api/approve") && !$0.contains(hubCidOnNew) }, "only the hub's own request is let in")
let blog = Recorder()
let bctrl = controllerOnHub(blog, hubWaiting: Cell(false), hkey: Cell(0))      // let in before controllers knew the hub's key
let bhub = HubClient(transport: ScriptedDevice(name: "hub", log: blog, address: "10.0.0.2/hub") { _ in hubInfoJSON("new1", hubCid: hubCidOnNew) })
_ = await bhub.admitHub(on: bctrl, controllerId: "new1")
check(blog.count("ctrl /api/approve") == 0 && blog.count("ctrl /api/hubkey") == 1, "already in, the controller not told: only the key is told")
let slog = Recorder()                                // the controller's state cannot be read: not done, so it is asked again
let sctrl = ControllerClient(transport: ScriptedDevice(name: "ctrl", log: slog, address: "10.0.0.2/c/new1") { c in
    cmdPath(c) == Api.keys ? #"{"keys":[{"cid":"\#(hubCidOnNew)","name":"Tilt Hub","owner":0,"me":0,"wait":0}]}"# : "not json"
})
check(await bhub.admitHub(on: sctrl, controllerId: "new1") == HubAdmission(hubCid: hubCidOnNew, done: false), "a state that cannot be read is not done")
let nhub = HubClient(transport: ScriptedDevice(name: "hub", log: blog, address: "10.0.0.2/hub") { _ in hubInfoJSON("new1", hubCid: nil) })
check(await nhub.admitHub(on: bctrl, controllerId: "new1") == HubAdmission(hubCid: nil, done: false), "the hub has not asked yet: nothing is let in")

// ---- firmware (Shared/FirmwareInstaller.swift)
final class FakeUploader: FirmwareUploader, @unchecked Sendable {
    let log: Recorder, answers: Cell<[String]>
    init(log: Recorder, answers: [String]) { self.log = log; self.answers = Cell(answers) }
    func upload(_ file: Data, to address: String, timeout: TimeInterval) async throws -> Data {
        log.add("upload \(String(decoding: file, as: UTF8.self)) to \(address)")
        var a = answers.value; let first = a.isEmpty ? #"{"ok":1}"# : a.removeFirst(); answers.value = a
        return Data(first.utf8)
    }
}
/// A controller update through a fake hub: `infos` are the hub's /api/info answers in turn (the last one repeats).
func fakeInstaller(_ log: Recorder, infos: [String], uploads: [String] = [], boots: [String]) -> FirmwareInstaller {
    let seen = Cell(0), bootsLeft = Cell(boots)
    let hub = HubClient(transport: ScriptedDevice(name: "hub", log: log, address: "10.0.0.2/hub") { c in
        guard cmdPath(c) == HubApi.info else { return #"{"ok":1}"# }
        let i = infos[min(seen.value, infos.count - 1)]; seen.value += 1; return i
    })
    var f = FirmwareInstaller(hub: hub, uploader: FakeUploader(log: log, answers: uploads), sleep: { _ in }, download: { file, _ in log.add("download \(file)"); return Data(file.utf8) })
    f.look = { host in
        var b = bootsLeft.value; let boot = b.count > 1 ? b.removeFirst() : b[0]; bootsLeft.value = b
        log.add("look \(boot)"); return Hello(id: "den1", name: "Den", fw: boot == "b2" ? "2.3.0" : "2.2.1", boot: boot, img: "aaa", owned: 1, home: nil, net: "thread", hub: 1)
    }
    return f
}
let fwCtrl = { (log: Recorder) in ControllerClient(transport: ScriptedDevice(name: "ctrl", log: log, address: "10.0.0.2/c/den1") { _ in #"{"ok":1}"# }) }
let rel = FirmwareRelease(version: "2.3.0", file: "full.bin", size: 9, sha256: "x", notes: nil,
                              patches: [.init(from: "aaa", file: "patch.bin", size: 1, sha256: "y"), .init(from: "zzz", file: "other.bin", size: 1, sha256: "z")])

// The update fails on the controller: the hub's reason is shown
let elog = Recorder()
let failed = await collect(fakeInstaller(elog, infos: [hubInfoJSON("den1", hubCid: nil, ota: 1, pct: 40), hubInfoJSON("den1", hubCid: nil, ota: 4, err: "the controller stopped answering")],
                                     boots: ["b1"]).install(.file(Data("f.bin".utf8)), on: fwCtrl(elog), id: "den1"))
check(failed.error?.localizedDescription == "The controller stopped answering" && failed.steps == [.sending, .hub(0), .hub(40)], "a failed update shows the hub's reason (\(failed.steps))")
check(elog.all.prefix(3) == ["ctrl /api/otaopen", "hub /api/upload?id=den1", "look b1"] && elog.count("upload f.bin to 10.0.0.2/c/den1/api/update") == 1,
      "allowed on the controller and the hub, then posted to the controller's address on the hub")
check(elog.count("ctrl /api/keep") == 0, "a failed update is never kept")

// The patch is refused: the whole file follows, and it is kept only once the controller restarted (a new boot id)
let plog = Recorder()
let pinst = fakeInstaller(plog, infos: [hubInfoJSON("den1", hubCid: nil, ota: 3)], uploads: [#"{"ok":0,"err":"not a patch for this firmware"}"#], boots: ["b1", "b1", "b1", "b1", "b2"])
let patched = await collect(pinst.install(.release(rel), on: fwCtrl(plog), id: "den1"))
check(patched.error == nil && patched.steps.last == .done("2.3.0"), "the update finishes on the whole file (\(patched.error?.localizedDescription ?? "-"))")
check(plog.all.filter { $0.hasPrefix("download") || $0.hasPrefix("upload") } == ["download patch.bin", "upload patch.bin to 10.0.0.2/c/den1/api/update", "download full.bin", "upload full.bin to 10.0.0.2/c/den1/api/update"],
      "the patch for exactly the running firmware first, then the whole file")
check(patched.steps.prefix(3) == [.downloading, .sending, .downloading], "the steps go back to downloading for the whole file")
let keepAt = plog.all.firstIndex(of: "ctrl /api/keep"), newBootAt = plog.all.firstIndex(of: "look b2")
check(plog.count("ctrl /api/keep") == 1 && keepAt != nil && newBootAt != nil && keepAt! > newBootAt!, "kept once, and only after the boot id changed")
check(patched.steps.suffix(3) == [.restarting, .confirming, .done("2.3.0")], "restart, check it runs, done")

// The hub's own update: allowed, posted to the hub, done once the hub answers with the new version
let ulog = Recorder()
var uinst = fakeInstaller(ulog, infos: [hubInfoJSON("den1", hubCid: nil)], boots: ["b1"])
let hubFw = Cell(["0.3.5", "0.3.5", "0.3.6"])
uinst.look = { host in var v = hubFw.value; let fw = v.count > 1 ? v.removeFirst() : v[0]; hubFw.value = v; ulog.add("look \(host)"); return Hello(id: "hub", name: "Tilt Hub", fw: fw, boot: "h1", img: nil, owned: 1, home: nil, net: nil, hub: nil) }
let hubRelease = FirmwareRelease(version: "0.3.6", file: "hub.bin", size: 1, sha256: "h", notes: nil, patches: nil)
let hubRun = await collect(uinst.updateHub(to: hubRelease, hubHost: "10.0.0.2"))
check(hubRun.error == nil && hubRun.steps == [.downloading, .sending, .restarting, .done], "the hub update steps")
check(ulog.all.prefix(3) == ["download hub.bin", "hub /api/hubupdate", "upload hub.bin to 10.0.0.2/hub/api/update"] && ulog.count("look 10.0.0.2/hub") == 3, "allowed, posted to the hub, then waited for its new version")
let refusedHub = await collect(fakeInstaller(Recorder(), infos: [hubInfoJSON("den1", hubCid: nil)], uploads: [#"{"ok":0}"#], boots: ["b1"]).updateHub(to: hubRelease, hubHost: "10.0.0.2"))
check(refusedHub.error?.localizedDescription == "The Tilt Hub did not take the update.", "a hub that does not take the file says so")
// ---- blind setup (Shared/BlindSetup.swift)
func blind(hid: Int = 0, pres: Int = 1, seen: Int = 1, cal: Int = 1, mov: Int = 0, q: Int = 0, last: String = "") -> BlindState {
    BlindState(name: "B", hid: hid, pres: pres, seen: seen, cal: cal, tilt: 0, tgt: nil, mov: mov, q: q, fav: 0, ang: nil, last: last)
}
let ts = Date(timeIntervalSince1970: 1_800_000_000)
var su = BlindSetup()
check(!su.steady(at: ts), "no reading yet: not steady")
su.reading(angle: 359.8, at: ts); su.reading(angle: 0.1, at: ts.addingTimeInterval(0.2))
check(su.steady(at: ts.addingTimeInterval(1.5)), "359.8 to 0.1 is noise across 0/360, not a turn")
su.reading(angle: 359.0, at: ts.addingTimeInterval(1.6)); su.reading(angle: 1.0, at: ts.addingTimeInterval(1.7))
check(!su.steady(at: ts.addingTimeInterval(2.5)) && su.steady(at: ts.addingTimeInterval(3.0)), "359 to 1 is a 2 degree turn: wait 1.2 s after it")
su.reading(angle: 10, at: ts.addingTimeInterval(4)); su.reading(angle: 200, at: ts.addingTimeInterval(4.1))
check(!su.steady(at: ts.addingTimeInterval(4.5)), "a big turn is a turn")
su.reading(angle: nil, at: ts.addingTimeInterval(9))
check(!su.steady(at: ts.addingTimeInterval(20)), "the sensor gave nothing: not steady")
let okA = CommandAnswer(ok: 1, err: nil, proof: nil, prob: nil)
check(su.mark == .up && su.marked(okA) == .next(step: 1) && su.mark == .open, "a saved mark: on to the next")
check(su.marked(CommandAnswer(ok: 0, err: "no reading", proof: nil, prob: nil)) == .failed(reason: "No reading") && su.step == 1, "a refused mark: stay, with the reason")
_ = su.marked(okA)
check(su.mark == .down && su.marked(CommandAnswer(ok: 1, err: nil, proof: nil, prob: "up and down are too close")) == .restart(reason: "Up and down are too close. Start again from step 1.") && su.step == 0, "bad marks: start again from step 1")
_ = su.marked(okA); _ = su.marked(okA)
check(su.marked(okA) == .next(step: 3) && su.done && su.mark == nil, "three good marks: done")
su.back(); check(su.step == 2, "back one step")
var wc = BlindSetup.WiringCheck()
check(wc.poll(nil, elapsed: 1) == .wait && wc.poll(blind(last: "reached 0"), elapsed: 1) == .wait, "before the move starts: wait")
check(wc.poll(blind(mov: 1), elapsed: 2) == .wait && wc.poll(blind(last: "reached open"), elapsed: 3) == .reached, "moved, then reached")
var wc2 = BlindSetup.WiringCheck()
check(wc2.poll(blind(last: "already there"), elapsed: 5) == .reached, "already at Open: reached")
check(wc2.poll(blind(last: "blocked: no turn"), elapsed: 6) == .failed(reason: "The blind did not reach Open (blocked: no turn). Check it turns freely, then tap Open."), "did not get there: says why")
check(BlindSetup.WiringCheck.words(sign: -1).contains("other way round") && BlindSetup.WiringCheck.words(sign: 1).contains("right way") && BlindSetup.WiringCheck.words(sign: nil).contains("right way"), "the wiring words")
check(blind(cal: 0).needsSetup && !blind(cal: 1).needsSetup, "not marked: needs setup")
check(!blind(hid: 1, cal: 0).needsSetup && !blind(pres: 0, seen: 1, cal: 0).needsSetup, "hidden or an empty port: no setup asked for")
check(blind(pres: 0, seen: 0, cal: 0).needsSetup, "a port not checked yet still asks for setup")

// ---- scenes (Shared/Scenes.swift) and the motor sign, against scripted controllers
actor Scripted: ControllerTransport {
    let answers: [String: String]
    var sent: [String] = []
    init(_ answers: [String: String]) { self.answers = answers }
    var host: String { "fake" }
    func move(to host: String) {}
    func call(_ command: String) async throws -> Data {
        sent.append(command)
        if let a = answers.first(where: { command.hasPrefix($0.key) })?.value { return Data(a.utf8) }
        throw URLError(.timedOut)
    }
}
let den = Scripted(["/api/go": #"{"ok":1}"#, "/api/dev": #"{"fw":"x","p":[{"ang":1,"sign":1},{"ang":2,"sign":-1}]}"#])
let office = Scripted(["/api/go": #"{"ok":0,"err":"too low to move"}"#])
let scene = BlindScene(name: "Movie", tilts: [BlindTarget(controller: "den", blind: 0): -100, BlindTarget(controller: "den", blind: 1): -100,
                                              BlindTarget(controller: "office", blind: 0): 50, BlindTarget(controller: "gone", blind: 0): 0])
let run = await Scenes.run(scene, clients: ["den": ControllerClient(transport: den), "office": ControllerClient(transport: office)])
check(run.reached == 2 && run.failed == ["office": "Too low to move"], "a scene moves what it can, says why not, and skips a missing controller")
check(Set(await den.sent) == ["/api/go?b=0&t=-100", "/api/go?b=1&t=-100"], "a scene sends each blind its tilt")
let signs = [await ControllerClient(transport: den).motorSign(blind: 0), await ControllerClient(transport: den).motorSign(blind: 1),
             await ControllerClient(transport: den).motorSign(blind: 2), await ControllerClient(transport: office).motorSign(blind: 0)]
check(signs == [1, -1, nil, nil], "the motor sign, typed; nil when there is no such port or no answer")
let onlyDen = BlindScene(name: "Den", tilts: [BlindTarget(controller: "den", blind: 0): 0]), empty0 = BlindScene(name: "Empty")
let pruned = Scenes.prune([scene, onlyDen, empty0], controller: "den")
check(pruned.map(\.name) == ["Movie", "Empty"], "removing a controller removes the scenes that only moved its blinds")
let sd = UserDefaults(suiteName: "tilt-tests-\(UUID())")!
Scenes.save([scene, onlyDen], sd)
check(Scenes.load(sd) == [scene, onlyDen] && Scenes.load(UserDefaults(suiteName: "tilt-tests-empty-\(UUID())")!) == [], "scenes are kept and read back")
check(TiltMath.tilt(percentOpen: 100, closeUp: true) == 0 && TiltMath.tilt(percentOpen: 0, closeUp: true) == 100 && TiltMath.tilt(percentOpen: 0, closeUp: false) == -100, "percent open: 100 is level, 0 is closed on the Close side")
check(TiltMath.tilt(percentOpen: 30, closeUp: false) == -70 && TiltMath.tilt(percentOpen: 130, closeUp: true) == 0, "in between, and out of range is held to 0…100")

// ---- people as shown (Shared/Client.swift People)
let pk = { (cid: String, me: Int, wait: Int?) in PhoneKey(cid: cid, name: cid, owner: 0, me: me, wait: wait, code: nil) }
let shown = People.shown([pk("x", 0, 0), pk("hub", 0, 1), pk("w", 0, 1), pk("me", 1, 0)], hubCid: "hub")
check(shown.map(\.cid) == ["me", "w", "x"], "the hub's own key is left out; this phone first, then requests")
check(People.shown([pk("hub", 0, 1)], hubCid: nil).count == 1, "not on a hub: nobody is left out")

print("\(passed) passed, \(failures) failed")
exit(failures == 0 ? 0 : 1)
