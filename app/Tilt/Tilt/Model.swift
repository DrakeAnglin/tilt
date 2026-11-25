// What the app knows: the paired controllers, their live state, and where the keys are kept (the Keychain).
import CryptoKit
import Foundation
import Observation
import Security
import UIKit


@MainActor @Observable
final class Controller: Identifiable {
    var record: ControllerRecord
    var state: ControllerState?
    var online = false
    /// When the controller last answered. Kept on the phone, so the app can say "last seen 2 hours ago".
    var lastSeen: Date?
    private var seenSaved = Date.distantPast
    enum Reach: Equatable { case online, asleep, unreachable }
    /// Online: answering. Asleep: not answering, but on battery and seen in the last 15 minutes, so most likely dozing.
    /// Unreachable: this iPhone is not on the home Wi-Fi, or the hub has not heard from it.
    var reach: Reach {
        if online { return .online }
        guard let t = lastSeen, state?.batt.charging == false, Date().timeIntervalSince(t) < 15 * 60 else { return .unreachable }
        return .asleep
    }
    /// One line for the room when it is not answering.
    var awayLine: String { TiltWords.away(lastSeen: lastSeen) }
    var lastError: String?
    /// Read the controller more often (a setup screen is watching the sensor).
    var boost = false
    /// Phones that asked to join this controller (this phone is an owner).
    var requests: [PhoneKey] = []
    /// This phone asked to join and an owner said no.
    var denied = false
    /// An owner removed this phone from the controller.
    var removed = false
    /// The saved record changed (approved): the model saves it.
    var changed: (() -> Void)?
    let client: ControllerClient
    private var task: Task<Void, Never>?
    nonisolated var id: String { _id }
    private let _id: String

    init(record: ControllerRecord, key: SymmetricKey) {
        self.record = record
        _id = record.id
        client = .make(record: record, key: key)
        lastSeen = UserDefaults.standard.object(forKey: Prefs.lastSeen(record.id)) as? Date
    }

    func start() {
        guard task == nil else { return }
        task = Task { [weak self] in
            var misses = 0
            while !Task.isCancelled {
                guard let self else { return }
                do {
                    let s = try await self.client.state()
                    if s != self.state { self.state = s }
                    BatteryAlerts.check(id: self.id, name: s.name, battery: s.batt)
                    self.online = true
                    misses = 0
                    self.noteSeen()
                    if self.record.waiting == true { self.record.waiting = nil; self.record.code = nil; self.changed?(); Task { await Cloud.clearJoin(cid: self.record.cid) } }      // an owner let this phone in
                    if let t = s.topic, !t.isEmpty, t != self.record.topic { self.record.topic = t; self.changed?() }
                    if let t = self.record.topic { if self.record.owner { await Cloud.watch(topic: t) } else { await Cloud.unwatch(topic: t) } }      // owners get a push when someone asks to join
                    if let m = s.me, (m == 1) != self.record.owner { self.record.owner = m == 1; self.changed?() }
                    if self.record.owner, (s.asks ?? 0) != self.asked { await self.loadRequests() }
                    // Set up before the controller knew which key is the hub's: tell it (once per start of the app).
                    if self.record.owner, self.record.onHub, s.hkey == 0, !self.hubKeyTold {
                        self.hubKeyTold = true
                        if let hc = await HubWatch.shared.hubCid(for: self.id) { try? await self.client.markHubKey(cid: hc) }
                    }
                } catch LinkProblem.waiting {
                    self.online = true
                    try? await Task.sleep(for: .seconds(2))
                } catch LinkProblem.notPaired {
                    if self.record.waiting == true { self.denied = true; return }
                    self.removed = true          // the controller answered and no longer knows this phone: an owner removed it
                    self.changed?()
                    return
                } catch {
                    misses += 1
                    if misses >= 3 { self.online = false }
                }
                let fast = (self.state?.mv ?? -1) >= 0 || self.boost
                try? await Task.sleep(for: .milliseconds(fast ? 350 : 1200))
            }
        }
    }
    func stop() { task?.cancel(); task = nil }
    private func noteSeen() {
        lastSeen = Date()
        if Date().timeIntervalSince(seenSaved) > 60 { seenSaved = Date(); UserDefaults.standard.set(lastSeen, forKey: Prefs.lastSeen(id)) }
    }

    /// Requests the controller listed last, the hub's own included (so a hub request still open does not reload every poll).
    private var asked = 0
    private var hubKeyTold = false
    func loadRequests() async {
        guard let people = try? await client.people() else { return }
        var asks = people.filter { $0.wait == 1 }
        asked = asks.count
        // The Tilt Hub asks to join each of its controllers (to move the blinds for Apple Home). The hub tells this
        // app which request is its own (by its key, not its name): an owner lets exactly that one in, unseen.
        if record.onHub, !asks.isEmpty, let hubCid = await HubWatch.shared.hubCid(for: id), let own = asks.first(where: { $0.cid == hubCid }) {
            if record.owner, (try? await client.approve(cid: own.cid, true, owner: false)) != nil { try? await client.markHubKey(cid: hubCid) }
            asks.removeAll { $0.cid == hubCid }
        }
        requests = asks
    }
    /// The people on this controller as the person sees them (People.shown: the hub's own key left out, this phone
    /// first). Notes when this phone's role changed (an owner made it a user, or the other way round).
    func people() async throws -> [PhoneKey] {
        let hubCid = record.onHub ? await HubWatch.shared.hubCid(for: id) : nil
        let list = People.shown(try await client.people(), hubCid: hubCid)
        if let me = list.first(where: { $0.me == 1 }), (me.owner == 1) != record.owner { record.owner = me.owner == 1; changed?() }
        return list
    }
    /// Let a phone that asked to join in (as an owner or a user), or turn it down.
    func answer(_ r: PhoneKey, approve: Bool, owner: Bool = false) async {
        do { try await client.approve(cid: r.cid, approve, owner: owner) } catch { lastError = error.localizedDescription }
        await loadRequests()
    }

    /// The controller's firmware is older than this version of the app needs.
    var needsUpdate: Bool { state.map { Api.tooOld($0.v) } ?? false }

    /// Do something on the controller; on failure remember the reason so the screen can show it.
    func run(_ action: @escaping @Sendable (ControllerClient) async throws -> Void) {
        let client = client
        Task {
            do { try await action(client) } catch { lastError = error.localizedDescription }
        }
    }
    func go(blind: Int, tilt: Int) { run { try await $0.go(blind: blind, tilt: tilt) } }
    func go(blind: Int, to word: String) { run { try await $0.go(blind: blind, to: word) } }
    /// `gently`: take this many minutes instead of going straight there.
    func goAll(to word: String, gently minutes: Int = 0) { run { try await $0.goAll(to: word, gently: minutes) } }
    /// Every blind that is set up, to one position.
    func goAll(tilt: Int) { for (i, b) in (state?.b ?? []).enumerated() where b.ready { go(blind: i, tilt: tilt) } }
    func stopAll() { run { try await $0.stop() } }
    /// Hold-to-turn: one short push; send again within half a second to keep turning.
    func jog(blind: Int, dir: Int, percent: Int) { let client = client; Task { await client.jog(blind: blind, dir: dir, percent: percent) } }
}

@MainActor @Observable
final class AppModel {
    var controllers: [Controller] = []
    /// Controllers this phone asked to join, until an owner answers.
    var waiting: [Controller] = []
    /// Something the person should be told once.
    var notice: String?
    private let defaultsKey = Prefs.controllers

    /// The name other people see for this person. It comes from Sign in with Apple or is typed once (iOS does not tell
    /// apps who owns the phone), and follows the person to their other devices through iCloud.
    static var savedName: String? {
        let n = UserDefaults.standard.string(forKey: Prefs.myName) ?? NSUbiquitousKeyValueStore.default.string(forKey: Prefs.myName)
        return n.flatMap { $0.isEmpty || $0 == UIDevice.current.name || $0 == "iPhone" ? nil : $0 }      // a device name is not a person's name
    }
    static var myName: String {
        get { savedName ?? UIDevice.current.name }
        set {
            let n = newValue.trimmingCharacters(in: .whitespaces)
            UserDefaults.standard.set(n, forKey: Prefs.myName)
            NSUbiquitousKeyValueStore.default.set(n, forKey: Prefs.myName)
        }
    }
    /// Change the name, here and on every controller this phone is on.
    func rename(to name: String) {
        let n = name.trimmingCharacters(in: .whitespaces)
        guard !n.isEmpty else { return }
        AppModel.myName = n
        for c in controllers { Task { try? await c.client.rename(cid: c.record.cid, to: n) } }
    }

    init() {
        let saved = (UserDefaults.standard.data(forKey: defaultsKey)).flatMap { try? JSONDecoder().decode([ControllerRecord].self, from: $0) } ?? []
        for r in saved { if let k = Keychain.load(r.id) { keep(Controller(record: r, key: SymmetricKey(data: k))) } }
        TiltActions.publish(controllers.map(\.record))
    }
    private func keep(_ c: Controller) {
        if c.record.waiting == true { waiting.append(c) } else { controllers.append(c) }
        c.changed = { [weak self, weak c] in
            guard let self, let c else { return }
            if c.removed { self.notice = "\(c.record.name) is no longer on this iPhone: it was reset, or an owner removed you. To use it again, add it from Add."; self.remove(c); return }
            if c.record.waiting != true, let i = self.waiting.firstIndex(where: { $0.id == c.id }) { self.waiting.remove(at: i); self.controllers.append(c) }
            self.save()
        }
    }
    private func save() {
        UserDefaults.standard.set(try? JSONEncoder().encode((controllers + waiting).map(\.record)), forKey: defaultsKey)
        TiltActions.publish(controllers.map(\.record))          // for the widget and Siri
    }
    func startAll() {
        (controllers + waiting).forEach { $0.start() }
        Task { await FirmwareUpdates.shared.check() }
        // Away from home too: did an owner remove this phone? (The owner's phone leaves a note in iCloud.)
        for c in controllers where c.record.host != Demo.host {
            guard let k = Keychain.load(c.id) else { continue }
            Task { if await Cloud.gone(cid: c.record.cid, key: SymmetricKey(data: k)) { c.removed = true; c.changed?() } }
        }
    }
    func stopAll() { (controllers + waiting).forEach { $0.stop() } }

    /// Add the controller at `host`: a new one makes this phone its owner; one that has an owner is asked to let this phone join.
    func add(host: String) async throws {
        let h = try await Secure.hello(host)
        adopt(h, host: host, paired: try await Secure.pair(host: host, phoneName: AppModel.myName, how: h.owned == 1 ? .ask : .first))
    }
    /// Add the demo room: a pretend controller for trying the app without one.
    func addDemo() {
        guard !controllers.contains(where: { $0.id == Demo.id }) else { return }
        let key = Data(repeating: 7, count: 32)                 // never sent anywhere: the demo answers inside the app
        let rec = ControllerRecord(id: Demo.id, name: "Living Room (Demo)", host: Demo.host, cid: "demo", owner: true)
        Keychain.save(Demo.id, key)
        let c = Controller(record: rec, key: SymmetricKey(data: key))
        keep(c)
        save()
        c.start()
        Task { await SceneStore.shared.load(controllers) }      // the demo room keeps two sample Scenes, like a controller would
    }
    var hasDemo: Bool { controllers.contains { $0.id == Demo.id } }
    /// No owner is left to approve: start getting in by turning a blind's wand. Returns the blind to turn.
    func recover(host: String) async throws -> String {
        let h = try await Secure.hello(host)
        let p = try await Secure.pair(host: host, phoneName: AppModel.myName, how: .recover)
        adopt(h, host: host, paired: p)
        return p.blindName
    }
    /// Keep a controller this phone just paired with (through the hub or Bluetooth setup).
    func adopt(_ h: Hello, host: String, paired p: Paired) {
        if let old = (controllers + waiting).first(where: { $0.id == h.id }) { remove(old) }
        let rec = ControllerRecord(id: h.id, name: h.name, host: host, cid: p.cid.hex, owner: p.owner, waiting: p.waiting ? true : nil, code: p.waiting ? p.code : nil, topic: p.topic.isEmpty ? nil : p.topic)
        if p.waiting { Task { await Cloud.postJoin(topic: p.topic, cid: rec.cid, who: AppModel.myName, room: h.name) } }
        Keychain.save(h.id, p.key.withUnsafeBytes { Data($0) })
        let c = Controller(record: rec, key: p.key)
        keep(c)
        save()
        c.start()
        BatteryAlerts.askPermission()
    }
    /// Controllers move when the router hands out a new address: follow them by their id.
    func noteFound(_ list: [FoundController]) {
        var changed = false
        for f in list {
            guard let c = (controllers + waiting).first(where: { $0.id == f.id }), c.record.host != f.host else { continue }
            c.record.host = f.host
            Task { await c.client.transport.move(to: f.host) }
            changed = true
        }
        if changed { save() }
    }
    /// Start over on this iPhone: every room, its key and any unfinished setup is removed (the controllers and the hub
    /// are not touched; set them up again from Add).
    func eraseAll() {
        for c in controllers + waiting { remove(c) }
        let d = UserDefaults.standard
        for k in d.dictionaryRepresentation().keys where k.hasPrefix("pending.cid.") { Pending.clear(String(k.dropFirst("pending.cid.".count))) }
        save()
    }
    func remove(_ c: Controller) {
        c.stop()
        if c.record.waiting == true, !c.denied { let client = c.client; Task { await client.leave() } }      // take the request back
        if c.record.waiting == true { Task { await Cloud.clearJoin(cid: c.record.cid) } }
        if let t = c.record.topic { Task { await Cloud.unwatch(topic: t) } }
        Keychain.delete(c.id)
        BatteryAlerts.forget(id: c.id)
        UserDefaults.standard.removeObject(forKey: Prefs.lastSeen(c.id))
        controllers.removeAll { $0.id == c.id }
        SceneStore.shared.prune(controller: c.id)          // scenes that only moved this controller's blinds go with it
        waiting.removeAll { $0.id == c.id }
        save()
    }
}

