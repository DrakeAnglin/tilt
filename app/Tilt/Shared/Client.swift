// Talking to a controller, in one place. Screens call typed methods here; they never build commands or decode answers
// themselves. Underneath is a transport: the real secured link (Secure.swift), the same sealed commands over Bluetooth
// during first setup (Bluetooth.swift), or the demo room (Demo.swift), and tests can use a fake one.
import CryptoKit
import Foundation

/// Carries one command to a controller and brings back its JSON answer.
protocol ControllerTransport: Sendable {
    func call(_ command: String) async throws -> Data
    /// The controller has a new address on the network.
    func move(to host: String) async
    var host: String { get async }
}

// ---- answers (the controller's JSON, see firmware web.h / wire.h / people.h). The shared fixture in
// firmware/blinds_matter/test/wire/ is checked against these types by the app's tests and against the firmware by its own.
/// How many Ports and Schedule slots a controller has. Firmware 2.2.1 and later says so in /api/cfg; older ones have 3 and 8.
struct ControllerLimits: Equatable, Sendable {
    var ports: Int, slots: Int
    static let fallback = ControllerLimits(ports: 3, slots: 8)
    /// What a controller reported; anything it leaves out is the fallback.
    static func reported(ports: Int?, slots: Int?) -> ControllerLimits { ControllerLimits(ports: ports ?? fallback.ports, slots: slots ?? fallback.slots) }
}
struct ControllerConfig: Decodable {
    struct Blind: Decodable { var name: String; var hid: Int; var speed: Int; var fav: Int }
    var name: String
    var ports: Int?, slots: Int?  // the controller's limits (firmware 2.2.1 and later): read them as `limits`
    var closeUp: Int, sync: Int
    var par: Int?                 // move at the same time (firmware 2.2 and later)
    var tzn: String
    var hksep: Int?
    var b: [Blind]
    var limits: ControllerLimits { .reported(ports: ports, slots: slots) }
}
struct SchedSlot: Decodable, Equatable { var on: Int, days: Int, mask: Int, min: Int, tilt: Int, kind: Int, off: Int, ramp: Int; var gid: UInt32 }
struct SchedConfig: Decodable {
    var ports: Int?, slots: Int?
    var sched: [SchedSlot]; var lat: Double?; var lon: Double?; var sun: [Double]?
    var limits: ControllerLimits { .reported(ports: ports, slots: slots) }
}
struct PhoneKey: Decodable, Identifiable, Equatable { let cid: String; let name: String; let owner: Int; let me: Int; let wait: Int?; let code: String?; var id: String { cid } }
/// {"ok":1} or {"ok":0,"err":"…"}, sometimes with more.
struct CommandAnswer: Decodable { let ok: Int; let err: String?; let proof: String?; let prob: String? }

struct ControllerClient: Sendable {
    let transport: any ControllerTransport

    /// The client for a saved controller: the demo room answers inside the app; anything else is the secured link.
    static func make(record: ControllerRecord, key: SymmetricKey) -> ControllerClient {
        record.host == Demo.host ? ControllerClient(transport: Demo.shared)
                                 : ControllerClient(transport: Link(host: record.host, cid: Data(hex: record.cid) ?? Data(), key: key))
    }

    private func json<T: Decodable>(_ command: String, as: T.Type = T.self) async throws -> T {
        try JSONDecoder().decode(T.self, from: try await transport.call(command))
    }
    /// A command that answers {"ok":…}: throws the controller's reason when it says no.
    @discardableResult private func send(_ command: String) async throws -> CommandAnswer {
        let a: CommandAnswer = try await json(command)
        if a.ok != 1 { throw TiltError((a.err ?? "That did not work.").capitalizedFirst) }
        return a
    }

    // ---- reading
    func state() async throws -> ControllerState { try await json(Api.state) }
    func config() async throws -> ControllerConfig { try await json(Api.config) }
    func schedules() async throws -> SchedConfig { try await json(Api.config) }
    func people() async throws -> [PhoneKey] {
        struct K: Decodable { let keys: [PhoneKey] }
        return try await json(Api.keys, as: K.self).keys
    }
    /// Developer view: everything the controller reports about itself.
    func developerInfo() async -> [String: Any] {
        guard let d = try? await transport.call(Api.dev) else { return [:] }
        return (try? JSONSerialization.jsonObject(with: d)) as? [String: Any] ?? [:]
    }
    func log() async -> [String] {
        guard let d = try? await transport.call(Api.log), let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { return [] }
        return j["lines"] as? [String] ?? []
    }

    // ---- moving
    func go(blind: Int, tilt: Int) async throws { try await send(Api.go(blind: blind, tilt: tilt)) }
    func go(blind: Int, to word: String) async throws { try await send(Api.go(blind: blind, to: word)) }
    func goAll(to word: String, gently minutes: Int = 0) async throws { try await send(Api.goAll(to: word, gently: minutes)) }
    func stop() async throws { try await send(Api.stop) }
    /// Hold-to-turn: one short push.
    func jog(blind: Int, dir: Int, percent: Int, ms: Int = 450) async { _ = try? await transport.call(Api.jog(blind: blind, dir: dir, percent: percent, ms: ms)) }
    func restart() async throws { try await send(Api.reboot) }

    // ---- setting up a blind
    /// Keep a blind's sensor reading live while its setup screen is open.
    func watch(blind: Int) async { _ = try? await transport.call(Api.watch(blind: blind)) }
    /// Save one of the three marks ("up", "open", "down", or "clear"). The answer says if the marks make sense together.
    func mark(blind: Int, _ which: String) async throws -> CommandAnswer { try await json(Api.mark(blind: blind, which)) }

    // ---- settings (the setting names are firmware web.h hSet's; in the app they live only here)
    private func set(_ key: String, _ value: String, extra: String = "") async throws { try await send(Api.set(key, value) + extra) }
    private func set(blind: Int, _ field: String, _ value: String) async throws { try await set("b\(blind).\(field)", value) }
    private func flag(_ on: Bool) -> String { on ? "1" : "0" }
    func setName(_ name: String) async throws { try await set("name", name) }
    /// "Close" tilts the slats up (true) or down.
    func setCloseUp(_ up: Bool) async throws { try await set("closeUp", flag(up)) }
    /// Blinds follow each other: moving one moves the others.
    func setFollow(_ on: Bool) async throws { try await set("sync", flag(on)) }
    /// Move at the same time (off: one after another).
    func setSameTime(_ on: Bool) async throws { try await set("par", flag(on)) }
    /// Apple Home shows each blind separately. The controller restarts.
    func setHomeSeparate(_ on: Bool) async throws { try await set("hksep", flag(on)) }
    func setLocation(latitude: Double, longitude: Double) async throws { try await set("loc", String(format: "%.3f,%.3f", latitude, longitude)) }
    /// The time zone: a POSIX rule ("CST6CDT,M3.2.0,M11.1.0") and its name ("America/Chicago").
    func setTimeZone(_ rule: String, name: String) async throws { try await set("tz", rule, extra: "&n=\(name.urlQuery)") }
    /// Stall sensing (developer).
    enum Tuning: String { case grace = "tune.grace", stall = "tune.stall", deg10 = "tune.deg10", max = "tune.max" }
    func setTuning(_ t: Tuning, _ value: Int) async throws { try await set(t.rawValue, "\(value)") }
    func setBlindName(blind: Int, _ name: String) async throws { try await set(blind: blind, "name", name) }
    func setHidden(blind: Int, _ hidden: Bool) async throws { try await set(blind: blind, "hid", flag(hidden)) }
    /// Motor speed, percent (50…100).
    func setSpeed(blind: Int, _ percent: Int) async throws { try await set(blind: blind, "speed", "\(percent)") }
    /// The favorite tilt (-100…100).
    func setFavorite(blind: Int, _ tilt: Int) async throws { try await set(blind: blind, "fav", "\(tilt)") }
    /// Which way the motor turns: 1 or -1.
    func setMotorSign(blind: Int, _ sign: Int) async throws { try await set(blind: blind, "sign", "\(sign)") }

    // ---- Schedule slots
    /// The command that writes one Schedule slot (see SchedulePlan for which slot holds what).
    static func scheduleCommand(slot: Int, _ v: SchedSlot) -> String {
        Api.schedule(slot: slot) + "on=\(v.on)&days=\(v.days)&mask=\(v.mask)&min=\(v.min)&tilt=\(v.tilt)&kind=\(v.kind)&off=\(v.off)&ramp=\(v.ramp)&gid=\(v.gid)"
    }
    func setSchedule(slot: Int, _ v: SchedSlot) async throws { try await send(Self.scheduleCommand(slot: slot, v)) }

    // ---- Scenes (see ScenePlan)
    /// The Scenes' parts this controller keeps; nil when its firmware is older than Scenes on the controller.
    func scenes() async throws -> [SceneSlot]? {
        let d = try await transport.call(Api.scenes)
        if let l = try? JSONDecoder().decode(SceneList.self, from: d) { return l.sc }
        if let a = try? JSONDecoder().decode(CommandAnswer.self, from: d), a.err == "unknown command" { return nil }
        throw TiltError("That did not work.")
    }
    static func sceneCommand(_ v: SceneSlot) -> String { Api.scene(gid: v.gid, ver: v.ver, name: v.name, symbol: v.sym, mask: v.mask, tilts: v.t) }
    func setScene(_ v: SceneSlot) async throws { try await send(Self.sceneCommand(v)) }


    // ---- people
    func approve(cid: String, _ ok: Bool, owner: Bool) async throws { try await send(Api.approve(cid: cid, ok, owner: owner)) }
    /// Remove a phone. Returns the proof that phone checks to know it was really removed (see Cloud.swift).
    func revoke(cid: String) async throws -> String { try await send(Api.revoke(cid: cid)).proof ?? "" }
    func revokeAll() async throws { try await send(Api.revokeAll) }
    func makeOwner(cid: String, _ on: Bool) async throws { try await send(Api.makeOwner(cid: cid, on)) }
    func rename(cid: String, to name: String) async throws { try await send(Api.rename(cid: cid, to: name)) }
    /// Take back this phone's request to join.
    func leave() async { _ = try? await transport.call(Api.leave) }

    // ---- Apple Home and firmware
    func homeSetupCode() async throws -> (code: String, qr: String) {
        struct H: Decodable { let code: String; let qr: String }
        let h: H = try await json(Api.homeOpen)
        return (h.code, h.qr)
    }
    /// Tell the controller which key is the Tilt Hub's (owner): from then on it trusts only messages proven with it.
    func markHubKey(cid: String) async throws { try await send("/api/hubkey?cid=\(cid)") }
    /// Give a new controller the hub's network, then switch it to its Thread firmware (it restarts and joins the hub).
    /// A controller that already runs its Thread firmware joins at once (no restart needed).
    func moveToHub(network: String, onThread: Bool = false) async throws {
        try await send(Api.hubJoin(network: network))
        if !onThread { try await send(Api.swapFirmware) }
    }
    /// Put a backup (hex, from a Tilt Hub) on this controller. It takes effect at its next start.
    func restore(backup hex: String) async throws {
        let piece = 256
        var i = hex.startIndex
        repeat {
            let j = hex.index(i, offsetBy: piece, limitedBy: hex.endIndex) ?? hex.endIndex
            try await send(Api.restore(offset: hex.distance(from: hex.startIndex, to: i) / 2, hex: String(hex[i..<j]), last: j == hex.endIndex))
            i = j
        } while i < hex.endIndex
    }
    func allowUpdate() async throws { try await send(Api.otaOpen) }
    func keepFirmware() async throws { try await send(Api.keep) }
}
