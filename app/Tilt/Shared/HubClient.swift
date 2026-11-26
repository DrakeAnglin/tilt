// Talking to the Tilt Hub, in one place, like ControllerClient is for a controller. Screens and HubWatch call typed
// methods here; they never build hub commands or decode its answers themselves. The hub's side is
// firmware/tilt_hub/main/hub_api.h (hubCommand): a change to a command there is a change here, and nowhere else in the app.
// Underneath is a transport: the real secured link (Link, at "<hub>/hub"), the demo hub (DemoHub.swift), or a test's fake.
import CryptoKit
import Foundation

/// Every command the app sends the Tilt Hub. The people commands are the same as a controller's (Api).
enum HubApi {
    static let info = "/api/info"
    static let keys = Api.keys
    static let leave = Api.leave
    static let resetPeople = "/api/resetpeople"
    static func approve(cid: String, _ ok: Bool, owner: Bool) -> String { Api.approve(cid: cid, ok, owner: owner) }
    static func revoke(cid: String) -> String { Api.revoke(cid: cid) }
    static func makeOwner(cid: String, _ on: Bool) -> String { Api.makeOwner(cid: cid, on) }
    /// The hub's Thread network, for a new controller.
    static let network = "/api/net"
    /// Apple Home's setup code (it opens Apple Home's pairing window).
    static let homeCode = "/api/homecode"
    /// A one-time code for another home app (Alexa).
    static let shareCode = "/api/sharecode"
    static let backups = "/api/backups"
    static func backup(id: String) -> String { "/api/backup?id=\(id)" }
    /// A new controller takes an old one's place in Apple Home.
    static func replace(old: String, new: String) -> String { "/api/replace?old=\(old)&new=\(new)" }
    /// Let one firmware file through to this controller, for 5 minutes.
    static func allowUpload(controller: String) -> String { "/api/upload?id=\(controller)" }
    /// Let one update of the hub's own firmware in, for 5 minutes.
    static let allowHubUpdate = "/api/hubupdate"

    // ---- plain HTTP, not sealed commands
    /// Where the hub answers sealed commands and pairing: "<hub address>/hub".
    static func base(_ hubHost: String) -> String { "\(hubHost)/hub" }
    /// A controller on the hub, by its id: "<hub address>/c/<id>" (see ControllerRecord.hubPath).
    static func controller(_ id: String, hubHost: String) -> String { "\(hubHost)\(ControllerRecord.hubPath)\(id)" }
    /// Where a firmware file is posted: the hub's own ("<hub>/hub" + this) or a controller's on it ("<hub>/c/<id>" + this).
    static let upload = "/api/update"
}

/// What the hub says about itself and its controllers (/api/info). Every key the hub has always sent is required, so a
/// renamed key fails loudly (in the tests, against firmware/blinds_matter/test/wire/hub_info.json). Optional: keys the
/// hub sends only sometimes, or added after its first release (homes and home: hub 0.2.6; chg: after 0.3.5, and only when the controller says).
struct HubInfo: Decodable, Sendable {
    let fw: String, up: Int, ip: String, wifi: Int, ch: Int
    let home: Int?
    /// The hub's own alert name (owners only): its push alerts (iCloud) are filed under it.
    let topic: String?
    /// Its Matter home connections: `node` is the hub's own ID in each (hex), to find it among Apple Home's accessories.
    let homes: [Home]?
    struct Home: Decodable, Sendable { let node: String?; let vendor: Int? }
    let c: [Member]
    let new: [New]
    struct New: Decodable, Sendable { let ble: String; let rssi: Int }
    /// One controller on the hub. seenS: seconds since it last checked in (-1: not since the hub started).
    /// key: the hub's own key on it (2 let in, 1 waiting for an owner, 0 none). rssi: Thread signal (127: not attached).
    struct Member: Decodable, Sendable, Identifiable {
        let id: String, name: String, fw: String, key: Int, seenS: Int, pct: Int, low: Int, rssi: Int, lqi: Int
        /// On the charging cable: 1 yes, 0 no (nil: a hub or controller too old to say).
        let chg: Int?
        /// A firmware update through the hub: 1 sending (otaPct), 2 checking, 3 done, 4 failed (otaErr).
        let ota: Int, otaPct: Int, otaErr: String?
        /// The hub's own key on this controller (only once it asked): its request to join is let in by the app, never shown.
        let hubCid: String?
        /// It has an owner (0: nobody set it up yet, so it can be added from Add a New Device; -1: not known).
        let own: Int
        /// Not heard from for 25 minutes (it checks in at least every 10).
        static let silentAfter = 1500
        var notResponding: Bool { seenS < 0 || seenS > Self.silentAfter }
        /// Its Thread signal, nil when it is not attached to the hub's network (the hub says 127 then).
        var signal: Int? { rssi == 127 ? nil : rssi }
        /// The hub asked to join this controller and the owner's app has not let it in yet.
        var hubWaiting: Bool { key == 1 }
    }
}
/// A controller's settings the hub kept (to restore on a new or reset controller).
struct HubBackup: Decodable, Identifiable, Hashable, Sendable { let id: String; let name: String; let when: Int }

struct HubClient: Sendable {
    let transport: any ControllerTransport

    /// The client for a saved hub: the demo hub answers inside the app; anything else is the secured link.
    static func make(host: String, cid: Data, key: SymmetricKey) -> HubClient {
        host == Demo.host ? HubClient(transport: DemoHub.shared) : HubClient(transport: Link(host: HubApi.base(host), cid: cid, key: key))
    }

    /// Every hub answer has "ok": throw the hub's reason when it says no, else decode the rest.
    private func json<T: Decodable>(_ command: String, as: T.Type = T.self, refused: String = "The Tilt Hub said no.") async throws -> T {
        let d = try await transport.call(command)
        let a = try JSONDecoder().decode(Answer.self, from: d)
        if (a.ok ?? 1) != 1 { throw TiltError((a.err ?? refused).capitalizedFirst) }
        return try JSONDecoder().decode(T.self, from: d)
    }
    private struct Answer: Decodable { let ok: Int?; let err: String? }
    private struct Nothing: Decodable {}
    private func send(_ command: String) async throws { let _: Nothing = try await json(command) }

    // ---- reading
    func info() async throws -> HubInfo { try await json(HubApi.info) }
    func people() async throws -> [PhoneKey] {
        struct K: Decodable { let keys: [PhoneKey] }
        return try await json(HubApi.keys, as: K.self).keys
    }
    /// The hub's own request to join this controller (to move its blinds for Apple Home), if it has made one.
    func hubCid(for controller: String) async -> String? { try? await info().c.first { $0.id == controller }?.hubCid }

    // ---- people (owner-only on the hub, except leaving)
    func approve(cid: String, _ ok: Bool, owner: Bool = false) async throws { try await send(HubApi.approve(cid: cid, ok, owner: owner)) }
    func revoke(cid: String) async throws { try await send(HubApi.revoke(cid: cid)) }
    func makeOwner(cid: String, _ on: Bool) async throws { try await send(HubApi.makeOwner(cid: cid, on)) }
    /// This iPhone leaves the hub (the hub's only owner cannot while others are in).
    func leave() async throws { try await send(HubApi.leave) }
    /// Take back a request to join that is still waiting (the hub answers "not paired" to it).
    func takeBackRequest() async { _ = try? await transport.call(HubApi.leave) }
    /// The hub forgets every phone and waits for a new owner (its controllers and Apple Home stay).
    func resetPeople() async throws { try await send(HubApi.resetPeople) }

    // ---- controllers
    func network() async throws -> String {
        struct N: Decodable { let ds: String }
        return try await json(HubApi.network, as: N.self).ds
    }
    /// The settings backups the hub keeps. None when it cannot say.
    func backups() async -> [HubBackup] {
        struct L: Decodable { let b: [HubBackup] }
        return (try? await json(HubApi.backups, as: L.self).b) ?? []
    }
    /// One backup, as hex (for ControllerClient.restore).
    func backup(_ id: String) async throws -> String {
        struct B: Decodable { let d: String }
        return try await json(HubApi.backup(id: id), as: B.self).d
    }
    func replace(old: String, new: String) async { try? await send(HubApi.replace(old: old, new: new)) }
    func allowUpload(for controller: String) async throws { try await send(HubApi.allowUpload(controller: controller)) }
    func allowHubUpdate() async throws { try await send(HubApi.allowHubUpdate) }

    // ---- home apps
    func homeCode() async throws -> (code: String, qr: String, home: Int) {
        struct H: Decodable { let code: String; let qr: String; let home: Int? }
        let h = try await json(HubApi.homeCode, as: H.self, refused: "The Tilt Hub could not give its code.")
        return (h.code, h.qr, h.home ?? 0)
    }
    /// A one-time code to add the hub to another home app (Alexa): fresh, good for `mins` minutes and one home. A hub
    /// in no home yet gives its own code instead (`first`).
    func shareCode() async throws -> (code: String, qr: String, mins: Int, first: Bool) {
        struct S: Decodable { let code: String; let qr: String; let mins: Int?; let first: Int? }
        let s = try await json(HubApi.shareCode, as: S.self, refused: "The Tilt Hub could not make a code.")
        return (s.code, s.qr, s.mins ?? 15, s.first == 1)
    }
}
