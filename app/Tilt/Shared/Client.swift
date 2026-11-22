// Talking to a controller, in one place. Screens call typed methods here; they never build commands or decode answers
// themselves. Underneath is a transport: the real secured link (Secure.swift) or the demo room (Demo.swift), and tests
// can use a fake one.
import CryptoKit
import Foundation

/// Carries one command to a controller and brings back its JSON answer.
protocol ControllerTransport: Sendable {
    func call(_ command: String) async throws -> Data
    /// The controller has a new address on the network.
    func move(to host: String) async
    var host: String { get async }
}

// ---- answers (the controller's JSON, see firmware web.h / people.h)
struct ControllerConfig: Decodable {
    struct Blind: Decodable { var name: String; var hid: Int; var speed: Int; var fav: Int }
    var name: String
    var closeUp: Int, sync: Int
    var par: Int?                 // move at the same time (firmware 2.2 and later)
    var tzn: String
    var hksep: Int?
    var b: [Blind]
}
struct SchedSlot: Decodable { var on: Int, days: Int, mask: Int, min: Int, tilt: Int, kind: Int, off: Int, ramp: Int; var gid: UInt32 }
struct SchedConfig: Decodable { var sched: [SchedSlot]; var lat: Double?; var lon: Double?; var sun: [Double]? }
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
    func go(blind: Int, tilt: Int, solo: Bool = false) async throws { try await send(Api.go(blind: blind, tilt: tilt, solo: solo)) }
    func go(blind: Int, to word: String) async throws { try await send(Api.go(blind: blind, to: word)) }
    func goAll(to word: String, gently minutes: Int = 0) async throws { try await send(Api.goAll(to: word, gently: minutes)) }
    func stop() async throws { try await send(Api.stop) }
    /// Hold-to-turn: one short push.
    func jog(blind: Int, dir: Int, percent: Int) async { _ = try? await transport.call(Api.jog(blind: blind, dir: dir, percent: percent)) }
    func restart() async throws { try await send(Api.reboot) }

    // ---- setting up a blind
    /// Keep a blind's sensor reading live while its setup screen is open.
    func watch(blind: Int) async { _ = try? await transport.call(Api.watch(blind: blind)) }
    /// Save one of the three marks ("up", "open", "down", or "clear"). The answer says if the marks make sense together.
    func mark(blind: Int, _ which: String) async throws -> CommandAnswer { try await json(Api.mark(blind: blind, which)) }

    // ---- settings and schedules
    func set(_ key: String, _ value: String) async throws { try await send(Api.set(key, value)) }
    func set(blind: Int, _ field: String, _ value: String) async throws { try await send(Api.set("b\(blind).\(field)", value)) }
    func setLocation(latitude: Double, longitude: Double) async throws { try await set("loc", String(format: "%.3f,%.3f", latitude, longitude)) }
    func setSchedule(slot: Int, on: Bool, days: Int, mask: Int, minute: Int, tilt: Int, kind: Int, offset: Int, ramp: Int, id: UInt32) async throws {
        try await send(Api.schedule(slot: slot) + "on=\(on ? 1 : 0)&days=\(days)&mask=\(mask)&min=\(minute)&tilt=\(tilt)&kind=\(kind)&off=\(offset)&ramp=\(ramp)&gid=\(id)")
    }

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
    func allowUpdate() async throws { try await send(Api.otaOpen) }
    func keepFirmware() async throws { try await send(Api.keep) }
}
