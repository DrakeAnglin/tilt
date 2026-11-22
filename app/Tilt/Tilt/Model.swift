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
                    if self.record.waiting == true { self.record.waiting = nil; self.record.code = nil; self.changed?(); Task { await Cloud.clearJoin(cid: self.record.cid) } }      // an owner let this phone in
                    if let t = s.topic, !t.isEmpty, t != self.record.topic { self.record.topic = t; self.changed?() }
                    if let t = self.record.topic { if self.record.owner { await Cloud.watch(topic: t) } else { await Cloud.unwatch(topic: t) } }      // owners get a push when someone asks to join
                    if let m = s.me, (m == 1) != self.record.owner { self.record.owner = m == 1; self.changed?() }
                    if self.record.owner, (s.asks ?? 0) != self.requests.count { await self.loadRequests() }
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

    func loadRequests() async {
        guard let people = try? await client.people() else { return }
        requests = people.filter { $0.wait == 1 }
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
    func go(blind: Int, tilt: Int, solo: Bool = false) { run { try await $0.go(blind: blind, tilt: tilt, solo: solo) } }
    func go(blind: Int, to word: String) { run { try await $0.go(blind: blind, to: word) } }
    /// `gently`: take this many minutes instead of going straight there.
    func goAll(to word: String, gently minutes: Int = 0) { run { try await $0.goAll(to: word, gently: minutes) } }
    /// Every blind that is set up, to one position.
    func goAll(tilt: Int) { for (i, b) in (state?.b ?? []).enumerated() where b.ready { go(blind: i, tilt: tilt, solo: true) } }
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
            if c.removed { self.notice = "You no longer have access to \(c.record.name). It was removed from this phone."; self.remove(c); return }
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
        // Two sample scenes, so the demo shows what scenes are for (removed again with the demo room).
        let store = SceneStore.shared
        if store.scenes.isEmpty {
            let all = (0..<3).map { BlindTarget(controller: Demo.id, blind: $0) }
            store.scenes = [BlindScene(name: "Morning", symbol: "sunrise", tilts: Dictionary(uniqueKeysWithValues: all.map { ($0, 0) })),
                            BlindScene(name: "Movie", symbol: "film", tilts: Dictionary(uniqueKeysWithValues: all.map { ($0, -100) }))]
            store.save()
        }
    }
    var hasDemo: Bool { controllers.contains { $0.id == Demo.id } }
    /// No owner is left to approve: start getting in by turning a blind's wand. Returns the blind to turn.
    func recover(host: String) async throws -> String {
        let h = try await Secure.hello(host)
        let p = try await Secure.pair(host: host, phoneName: AppModel.myName, how: .recover)
        adopt(h, host: host, paired: p)
        return p.blindName
    }
    /// Keep a controller this phone just paired with (over Wi-Fi or Bluetooth setup).
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
    func setOwner(_ c: Controller, _ owner: Bool) {
        guard c.record.owner != owner else { return }
        c.record.owner = owner
        save()
    }
    func remove(_ c: Controller) {
        c.stop()
        if c.record.waiting == true, !c.denied { let client = c.client; Task { await client.leave() } }      // take the request back
        if c.record.waiting == true { Task { await Cloud.clearJoin(cid: c.record.cid) } }
        if let t = c.record.topic { Task { await Cloud.unwatch(topic: t) } }
        Keychain.delete(c.id)
        BatteryAlerts.forget(id: c.id)
        controllers.removeAll { $0.id == c.id }
        let store = SceneStore.shared                       // scenes that only moved this controller's blinds go with it
        let before = store.scenes.count
        store.scenes.removeAll { !$0.tilts.isEmpty && $0.tilts.keys.allSatisfy { $0.controller == c.id } }
        if store.scenes.count != before { store.save() }
        waiting.removeAll { $0.id == c.id }
        save()
    }
}

