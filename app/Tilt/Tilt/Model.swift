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

    /// Run a command; on failure remember the reason so the screen can show it.
    func run(_ command: String) {
        Task {
            do { try await link.send(command) } catch { lastError = error.localizedDescription }
        }
    }
    func go(blind: Int, tilt: Int) { run("/api/go?b=\(blind)&t=\(tilt)") }
    func go(blind: Int, to word: String) { run("/api/go?b=\(blind)&to=\(word)") }
    func goAll(to word: String) { run("/api/go?b=all&to=\(word)") }
    func stopAll() { run("/api/stop") }
    /// Hold-to-turn: one short push; send again within half a second to keep turning.
    func jog(blind: Int, dir: Int, percent: Int) { Task { _ = try? await link.call("/api/jog?b=\(blind)&d=\(dir)&p=\(percent)&ms=450") } }
}

@MainActor @Observable
final class AppModel {
    var controllers: [Controller] = []
    private let defaultsKey = "controllers.v1"

    init() {
        let saved = (UserDefaults.standard.data(forKey: defaultsKey)).flatMap { try? JSONDecoder().decode([ControllerRecord].self, from: $0) } ?? []
        for r in saved { if let k = Keychain.load(r.id) { controllers.append(Controller(record: r, key: SymmetricKey(data: k))) } }
        TiltActions.publish(controllers.map(\.record))
    }
    private func save() {
        UserDefaults.standard.set(try? JSONEncoder().encode(controllers.map(\.record)), forKey: defaultsKey)
        TiltActions.publish(controllers.map(\.record))          // for the widget and Siri
    }
    func startAll() { controllers.forEach { $0.start() } }
    func stopAll() { controllers.forEach { $0.stop() } }

    /// Pair with the controller at `host` (first phone), or join with an invite.
    func add(host: String, invite: Invite?) async throws {
        let h = try await Secure.hello(host)
        if let old = controllers.first(where: { $0.id == h.id }) { remove(old) }
        if h.owned == 1 && invite == nil { throw TiltError("This controller already has an owner. Ask them to share it with you, then scan their code.") }
        let p = try await Secure.pair(host: host, phoneName: UIDevice.current.name, invite: invite)
        let rec = ControllerRecord(id: h.id, name: h.name, host: host, cid: p.cid.hex, owner: p.owner)
        Keychain.save(h.id, p.key.withUnsafeBytes { Data($0) })
        let c = Controller(record: rec, key: p.key)
        controllers.append(c)
        save()
        c.start()
        BatteryAlerts.askPermission()
    }
    /// Keep a controller this phone just paired with some other way (Bluetooth setup).
    func adopt(_ h: Hello, host: String, paired p: Paired) {
        if let old = controllers.first(where: { $0.id == h.id }) { remove(old) }
        let rec = ControllerRecord(id: h.id, name: h.name, host: host, cid: p.cid.hex, owner: p.owner)
        Keychain.save(h.id, p.key.withUnsafeBytes { Data($0) })
        let c = Controller(record: rec, key: p.key)
        controllers.append(c)
        save()
        c.start()
        BatteryAlerts.askPermission()
    }
    /// Controllers move when the router hands out a new address: follow them by their id.
    func noteFound(_ list: [FoundController]) {
        var changed = false
        for f in list {
            guard let c = controllers.first(where: { $0.id == f.id }), c.record.host != f.host else { continue }
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
        Keychain.delete(c.id)
        BatteryAlerts.forget(id: c.id)
        controllers.removeAll { $0.id == c.id }
        save()
    }
}

