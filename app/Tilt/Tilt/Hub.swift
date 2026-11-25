// The Tilt Hub. It announces itself with Bonjour as _tilthub._tcp (its address, id, and whether it has an owner).
// A phone connects to it like to a controller (the same pairing, Shared/Secure.swift, at "<hub>/hub"): the first phone
// becomes its owner; later phones ask to join and an owner lets them in. Until this iPhone is connected, the hub is only
// "found" (the Blinds page offers Connect or Ask to Join); Settings shows it once connected.
// HubWatch keeps what the app knows about the hub (found, record, status); the commands are HubClient's (Shared/HubClient.swift).
import CryptoKit
import Foundation
import Network
import Observation

/// This iPhone's link to a hub (saved; its key is in the Keychain as "hub-<id>").
struct HubRecord: Codable, Equatable {
    var id: String, host: String, cid: String, owner: Bool
    var waiting: Bool = false, code: String? = nil, topic: String? = nil
}

@MainActor @Observable
final class HubWatch {
    static let shared = HubWatch()
    enum Status { case none, newHub, someoneElses, waiting, connected }

    /// A hub seen on the Wi-Fi: its address, id and whether it has an owner.
    var found: FoundHub?
    struct FoundHub: Equatable { var host: String, id: String, owned: Bool }
    /// This iPhone's connection to a hub.
    private(set) var record: HubRecord? = HubWatch.loadRecord()
    var status: Status {
        if let r = record { return r.waiting ? .waiting : .connected }
        guard let f = found else { return .none }
        return f.owned ? .someoneElses : .newHub
    }
    var isOwner: Bool { record?.owner == true && record?.waiting == false }
    /// Where the hub is: the connected one's address, else the one found.
    var host: String? { record?.host ?? found?.host }
    /// In Apple Home: checked against Apple Home's own accessories once the Tilt Hub page has opened (HomeSetup.inHome).
    var inHome = false
    /// The connected hub answered lately. nil: not asked yet.
    var answering: Bool?
    var statusWord: String {
        guard let r = record else { return "Not connected" }
        if r.waiting { return "Waiting for its owner" }
        return answering == nil ? "Checking…" : answering! ? "Connected" : "Unreachable"
    }
    /// New controllers advertising near the hub (shown to an owner).
    var newNearby = 0
    /// People asking to join the hub (shown to an owner).
    var asks: [PhoneKey] = []
    /// The hub's people, nil until the hub has listed them (the Remove choices depend on it).
    private(set) var everyone: [PhoneKey]?
    /// Everything the hub reported last (the hub page).
    var info: HubInfo?
    var quietUntil = Date.distantPast
    /// New controllers: advertising near the hub, or already on it with nobody owning them yet, that this app has not
    /// added (quiet for a few minutes after a setup: the hub remembers a controller's Bluetooth call for a while).
    func showBanner(added: Set<String>) -> Bool {
        guard isOwner, Date() > quietUntil else { return false }
        return newNearby > 0 || (info?.c.contains { $0.own == 0 && !added.contains($0.id) } ?? false)
    }
    /// Called after a controller was set up or added.
    func justAdded() { quietUntil = Date().addingTimeInterval(300); Task { await refresh() } }
    /// Something the app should tell once (the hub forgot this iPhone, or an owner said no).
    var notice: String?

    private var browser: NWBrowser?
    private var poll: Task<Void, Never>?
    private var misses = 0
    private var firstMiss: Date?
    private var conn: HubClient?

    func start() {
        if browser == nil {
            let b = NWBrowser(for: .bonjourWithTXTRecord(type: "_tilthub._tcp", domain: nil), using: .tcp)
            b.browseResultsChangedHandler = { [weak self] results, _ in
                var f: FoundHub?
                for r in results { if case let .bonjour(txt) = r.metadata, let a = txt["ip"], !a.isEmpty, a != "0.0.0.0" { f = FoundHub(host: a, id: txt["id"] ?? "", owned: txt["owned"] == "1") } }
                Task { @MainActor in self?.noteFound(f) }
            }
            b.start(queue: .main)
            browser = b
        }
        if poll == nil {
            poll = Task { [weak self] in
                while !Task.isCancelled {
                    await self?.refresh()
                    try? await Task.sleep(for: .seconds(6))
                }
            }
        }
    }
    func stop() { browser?.cancel(); browser = nil; poll?.cancel(); poll = nil; answering = nil; misses = 0; firstMiss = nil }   // ask afresh when the app comes back

    private func noteFound(_ f: FoundHub?) {
        found = f                                   // nil: the hub is gone from the Wi-Fi (unplugged, or this iPhone left home)
        guard let f else { return }
        if var r = record, r.id == f.id, r.host != f.host { r.host = f.host; save(r); conn = nil }      // the hub got a new address
    }

    func refresh() async {
        guard record != nil else {                 // not connected: is the hub that was found new, or someone's?
            guard let h = found?.host, let (st, d) = try? await Secure.http(h, "/hub"), st == 200,
                  let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { return }
            found?.owned = (j["owned"] as? Int) == 1
            return
        }
        // Several refreshes can overlap (the poll, the hub page, after a change): an answer for a record that has since
        // been removed or replaced is dropped.
        let asked = record
        func current() -> Bool { record?.id == asked?.id && record?.cid == asked?.cid }
        do {
            let i = try await client().info()
            guard current() else { return }
            misses = 0; answering = true; info = i; firstMiss = nil
            Task { await HubOffline.answered() }
            inHome = HomeSetup.inHome(hubSays: (i.home ?? 0) == 1, hubHomes: (i.homes ?? []).map { .init(node: $0.node, vendor: $0.vendor) },
                                      appleNodes: AppleHomes.shared.nodeIDs)
            newNearby = i.new.count
            if var r = record, r.waiting { r.waiting = false; r.code = nil; save(r) }     // the owner let this iPhone in
            if isOwner, var r = record {                                                     // the hub's push alerts: watched on every check, so a
                if let t = i.topic, !t.isEmpty, t != r.topic { r.topic = t; save(r) }      // phone that joined before them gets them too
                if let t = r.topic { Task { await Cloud.watch(topic: t) } }
            }
            if let ps = try? await client().people(), current() {
                everyone = ps
                if let me = ps.first(where: { $0.me == 1 }), var r = record, r.owner != (me.owner == 1) {     // made owner, or user
                    r.owner = me.owner == 1; save(r)
                    if let t = r.topic { Task { r.owner ? await Cloud.watch(topic: t) : await Cloud.unwatch(topic: t) } }
                }
                asks = isOwner ? ps.filter { $0.wait == 1 } : []
            }
        } catch LinkProblem.waiting {
            guard current() else { return }
            answering = true
        } catch LinkProblem.notPaired {
            guard current() else { return }
            // A request that no longer exists (the hub was reset) just goes; the Blinds page offers Connect or Ask again.
            if record?.waiting != true { notice = "The Tilt Hub does not know this iPhone anymore: it was reset, or an owner removed you. Connect to it again from the Blinds page." }
            forgetLocally()
        } catch {
            guard current() else { return }
            misses += 1
            if firstMiss == nil { firstMiss = Date() }
            if misses >= 2 || answering == nil { answering = false; newNearby = 0 }
            if misses >= 2, isOwner, let since = firstMiss { Task { await HubOffline.missed(since: since) } }
        }
    }

    // ---- connecting
    /// A new hub: this iPhone becomes its owner, with the setup code on the hub's label. The code goes into the key
    /// (never over the network): the hub only takes this iPhone once its first command shows the code was right.
    func connect(code: String) async throws {
        guard let f = found else { throw TiltError("No Tilt Hub was found on your Wi-Fi.") }
        let digits = code.filter(\.isNumber)
        guard digits.count == 8 else { throw TiltError("The setup code has 8 digits. It is on the hub's label.") }
        let p = try await Secure.pair(host: HubApi.base(f.host), phoneName: AppModel.myName, how: .first, salt: Data(digits.utf8))
        keep(f, p)
        do { _ = try await client().info() }
        catch { forgetLocally(); throw TiltError("That setup code is not right. Check the label on the hub and try again.") }
        await refresh()
    }
    /// A hub with an owner: ask to join; the owner lets this iPhone in from their Tilt app.
    func askToJoin() async throws {
        guard let f = found else { throw TiltError("No Tilt Hub was found on your Wi-Fi.") }
        let p = try await Secure.pair(host: HubApi.base(f.host), phoneName: AppModel.myName, how: .ask)
        keep(f, p)
        if !p.topic.isEmpty { await Cloud.postJoin(topic: p.topic, cid: p.cid.hex, who: AppModel.myName, room: "Tilt Hub") }
    }
    private func keep(_ f: FoundHub, _ p: Paired) {
        Keychain.save("hub-" + f.id, p.key.withUnsafeBytes { Data($0) })
        save(HubRecord(id: f.id, host: f.host, cid: p.cid.hex, owner: p.owner, waiting: p.waiting, code: p.waiting ? p.code : nil, topic: p.topic.isEmpty ? nil : p.topic))
        conn = nil
        if p.owner, !p.topic.isEmpty { Task { await Cloud.watch(topic: p.topic) } }     // told when someone asks to join
    }
    /// This iPhone leaves the hub: the hub forgets it too (a waiting request is taken back). The hub's only owner cannot
    /// leave while others are in (make someone else an owner, or reset its people).
    func leave() async throws {
        if record?.waiting == true { await (try? client())?.takeBackRequest() }
        else { try await client().leave() }
        forgetLocally()
    }
    /// The hub forgets every phone and waits for a new owner (its controllers and Apple Home stay). This iPhone too.
    func resetPeople() async throws {
        try await client().resetPeople()
        forgetLocally()
    }
    /// Only this iPhone forgets the hub (it stays in the hub's people; someone has to let it in again).
    func forgetHere() { forgetLocally() }
    private func forgetLocally() {
        if let r = record { Keychain.delete("hub-" + r.id); if let t = r.topic { Task { await Cloud.unwatch(topic: t) } } }
        record = nil; conn = nil; info = nil; answering = nil; newNearby = 0; asks = []; everyone = nil
        Keychain.delete(Self.recordKey); UserDefaults.standard.removeObject(forKey: Self.recordKey)
    }

    // ---- what a connected iPhone can ask that changes what the app shows (the rest: client(), owner-only on the hub)
    func approve(cid: String, _ ok: Bool, owner: Bool = false) async throws { try await client().approve(cid: cid, ok, owner: owner); await refresh() }
    /// The hub restarted (its own update): ask afresh.
    func restarted() async { conn = nil; await refresh() }
    /// In Alexa: the hub has a Matter home connection made by Amazon.
    var inAlexa: Bool { HomeSetup.inAlexa(hubHomes: (info?.homes ?? []).map { .init(node: $0.node, vendor: $0.vendor) }) }
    /// The hub's own request to join a controller (to move its blinds for Apple Home), if it has made one. From the
    /// last /api/info this watch read, asking again only when it is not there (HubClient.hubCid always asks).
    func hubCid(for controller: String) async -> String? {
        if let c = info?.c.first(where: { $0.id == controller })?.hubCid { return c }
        await refresh()
        return info?.c.first(where: { $0.id == controller })?.hubCid
    }

    // ---- the secured channel to the hub
    /// The client for the connected hub (a waiting request too: it can only take itself back).
    func client() throws -> HubClient {
        if let conn { return conn }
        guard let r = record, let c = Self.client(r) else { throw TiltError("This iPhone is not connected to the Tilt Hub.") }
        conn = c
        return c
    }
    nonisolated private static func client(_ r: HubRecord) -> HubClient? {
        guard let k = Keychain.load("hub-" + r.id), let cid = Data(hex: r.cid) else { return nil }
        return HubClient.make(host: r.host, cid: cid, key: SymmetricKey(data: k))
    }

    // ---- saved
    nonisolated static let recordKey = "hub.record"
    // Kept in the Keychain (it survives deleting and reinstalling the app, like the hub's key next to it), so this
    // iPhone never loses a hub that still counts it as its owner.
    private func save(_ r: HubRecord) { record = r; if let d = try? JSONEncoder().encode(r) { Keychain.save(Self.recordKey, d) } }
    nonisolated static func loadRecord() -> HubRecord? {
        guard let d = Keychain.load(recordKey) ?? UserDefaults.standard.data(forKey: recordKey) else { return nil }
        return try? JSONDecoder().decode(HubRecord.self, from: d)
    }
    /// For the background check: what the connected hub reports, over the secured channel.
    nonisolated static func fetchInfo() async -> HubInfo? {
        guard let r = loadRecord(), !r.waiting, let c = client(r) else { return nil }
        return try? await c.info()
    }
}
