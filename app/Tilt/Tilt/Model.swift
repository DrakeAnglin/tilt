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
    let link: Link
    private var task: Task<Void, Never>?
    nonisolated var id: String { _id }
    private let _id: String

    init(record: ControllerRecord, key: SymmetricKey) {
        self.record = record
        _id = record.id
        link = Link(host: record.host, cid: Data(hex: record.cid) ?? Data(), key: key)
    }

    func start() {
        guard task == nil else { return }
        task = Task { [weak self] in
            var misses = 0
            while !Task.isCancelled {
                guard let self else { return }
                do {
                    let s: ControllerState = try await self.link.json("/api/s")
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
        struct K: Decodable { let keys: [PhoneKey] }
        guard let k = try? await link.json("/api/keys", as: K.self) else { return }
        requests = k.keys.filter { $0.wait == 1 }
    }
    /// Let a phone that asked to join in (as an owner or a user), or turn it down.
    func answer(_ r: PhoneKey, approve: Bool, owner: Bool = false) async {
        do { try await link.send("/api/approve?cid=\(r.cid)&ok=\(approve ? 1 : 0)&owner=\(owner ? 1 : 0)") } catch { lastError = error.localizedDescription }
        await loadRequests()
    }

    /// Run a command; on failure remember the reason so the screen can show it.
    func run(_ command: String) {
        Task {
            do { try await link.send(command) } catch { lastError = error.localizedDescription }
        }
    }
    func go(blind: Int, tilt: Int) { run("/api/go?b=\(blind)&t=\(tilt)") }
    func go(blind: Int, to word: String) { run("/api/go?b=\(blind)&to=\(word)") }
    /// `gently`: take this many minutes instead of going straight there.
    func goAll(to word: String, gently minutes: Int = 0) { run("/api/go?b=all&to=\(word)" + (minutes > 0 ? "&ramp=\(minutes)" : "")) }
    /// Every blind that is set up, to one position.
    func goAll(tilt: Int) { for (i, b) in (state?.b ?? []).enumerated() where b.ready { run("/api/go?b=\(i)&t=\(tilt)&solo=1") } }
    func stopAll() { run("/api/stop") }
    /// Hold-to-turn: one short push; send again within half a second to keep turning.
    func jog(blind: Int, dir: Int, percent: Int) { Task { _ = try? await link.call("/api/jog?b=\(blind)&d=\(dir)&p=\(percent)&ms=450") } }
}

@MainActor @Observable
final class AppModel {
    var controllers: [Controller] = []
    /// Controllers this phone asked to join, until an owner answers.
    var waiting: [Controller] = []
    /// Something the person should be told once.
    var notice: String?
    private let defaultsKey = "controllers.v1"

    /// The name other people see for this person. It comes from Sign in with Apple or is typed once (iOS does not tell
    /// apps who owns the phone), and follows the person to their other devices through iCloud.
    static var savedName: String? {
        let n = UserDefaults.standard.string(forKey: "myName") ?? NSUbiquitousKeyValueStore.default.string(forKey: "myName")
        return n.flatMap { $0.isEmpty || $0 == UIDevice.current.name || $0 == "iPhone" ? nil : $0 }      // a device name is not a person's name
    }
    static var myName: String {
        get { savedName ?? UIDevice.current.name }
        set {
            let n = newValue.trimmingCharacters(in: .whitespaces)
            UserDefaults.standard.set(n, forKey: "myName")
            NSUbiquitousKeyValueStore.default.set(n, forKey: "myName")
        }
    }
    /// Change the name, here and on every controller this phone is on.
    func rename(to name: String) {
        let n = name.trimmingCharacters(in: .whitespaces)
        guard !n.isEmpty else { return }
        AppModel.myName = n
        for c in controllers { Task { try? await c.link.send("/api/keyname?cid=\(c.record.cid)&name=\(n.urlQuery)") } }
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
        // Away from home too: did an owner remove this phone? (The owner's phone leaves a note in iCloud.)
        for c in controllers {
            guard let k = Keychain.load(c.id) else { continue }
            Task { if await Cloud.gone(cid: c.record.cid, key: SymmetricKey(data: k)) { c.removed = true; c.changed?() } }
        }
    }
    func stopAll() { (controllers + waiting).forEach { $0.stop() } }

    /// Add the controller at `host`: a new one makes this phone its owner; one that has an owner is asked to let this phone join.
    func add(host: String) async throws {
        let h = try await Secure.hello(host)
        if let old = (controllers + waiting).first(where: { $0.id == h.id }) { remove(old) }
        adopt(h, host: host, paired: try await Secure.pair(host: host, phoneName: AppModel.myName, ask: h.owned == 1))
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
            Task { await c.link.move(to: f.host) }
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
        if c.record.waiting == true, !c.denied { Task { _ = try? await c.link.call("/api/leave") } }      // take the request back
        if c.record.waiting == true { Task { await Cloud.clearJoin(cid: c.record.cid) } }
        if let t = c.record.topic { Task { await Cloud.unwatch(topic: t) } }
        Keychain.delete(c.id)
        BatteryAlerts.forget(id: c.id)
        controllers.removeAll { $0.id == c.id }
        waiting.removeAll { $0.id == c.id }
        save()
    }
}

