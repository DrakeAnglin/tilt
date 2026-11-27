// Putting a new controller on the Tilt Hub, once it is paired over Bluetooth: one flow that returns its steps, so the
// screen (Tilt/BluetoothSetup.swift) only shows them, and the tests run it against fakes. Also the one rule for
// letting the hub in on a controller (admitHub), which the app's model uses too.
import Foundation

enum OnboardingStep: Equatable, Sendable { case gettingNetwork, restoring, joining, waitingOnHub, lettingHubIn, done }

/// Where an onboarded controller is kept: the app's model, or a test's list.
protocol ControllerStore: Sendable {
    /// Keep a controller this phone paired with, now reachable at `host` (on the hub). Returns its client there.
    func adopt(_ h: Hello, host: String, paired: Paired) async -> ControllerClient
}

actor ControllerOnboarding {
    private let controller: ControllerClient
    private let store: any ControllerStore
    private let hello: Hello, paired: Paired
    private let look: @Sendable (String) async -> Hello?
    private let sleep: @Sendable (Duration) async throws -> Void
    private let leftBluetooth: @Sendable () async -> Void
    /// It took the hub's network and left Bluetooth: a second try only waits for it on the hub again.
    private var moved = false

    /// `transport`: sealed commands to the new controller over Bluetooth.
    /// `look`: the controller's hello at an address (nil when it does not answer). `leftBluetooth`: it is off Bluetooth now.
    init(transport: any ControllerTransport, store: any ControllerStore, hello: Hello, paired: Paired,
         look: @escaping @Sendable (String) async -> Hello? = { try? await Secure.hello($0) },
         sleep: @escaping @Sendable (Duration) async throws -> Void = { try await Task.sleep(for: $0) },
         leftBluetooth: @escaping @Sendable () async -> Void = {}) {
        controller = ControllerClient(transport: transport)
        self.store = store; self.hello = hello; self.paired = paired
        self.look = look; self.sleep = sleep; self.leftBluetooth = leftBluetooth
    }

    /// Give the controller the hub's network (and, with `restore`, a backup the hub kept: its own, or a replaced
    /// controller's), wait for it on the hub, keep it, then let the hub in (it asks to join the controller like a phone).
    /// `hub` and `hubHost` (its address on the Wi-Fi) are read fresh for each try: the hub may have a new address by then.
    nonisolated func run(restore: String?, hub: HubClient, hubHost: String) -> AsyncThrowingStream<OnboardingStep, Error> {
        AsyncThrowingStream { c in
            let t = Task {
                do { try await self.steps(restore: restore, hub: hub, hubHost: hubHost) { c.yield($0) }; c.finish() } catch { c.finish(throwing: error) }
            }
            c.onTermination = { _ in t.cancel() }
        }
    }

    private func steps(restore: String?, hub: HubClient, hubHost: String, _ step: (OnboardingStep) -> Void) async throws {
        let onThread = hello.net == "thread"           // older controllers started on Wi-Fi firmware and switch over
        if !moved {
            step(.gettingNetwork)
            let network = try await hub.network()
            if let restore {
                step(.restoring)
                try await controller.restore(backup: try await hub.backup(restore))
            }
            step(.joining)
            try await controller.moveToHub(network: network, onThread: onThread)
            // The restored Home layout takes effect only at a start. A controller already on its Thread firmware does
            // not restart by itself when it joins (one on Wi-Fi firmware restarts anyway, in swapFirmware).
            if onThread && restore != nil { try? await controller.restart() }
            await leftBluetooth()
            moved = true
        }
        step(.waitingOnHub)
        let host = HubApi.controller(hello.id, hubHost: hubHost)
        var there = false
        for _ in 0..<60 where !there {
            try await sleep(.seconds(2))
            if let n = await look(host), n.net == "thread", n.boot != hello.boot || onThread { there = true }
        }
        guard there else { throw TiltError("It did not reach the hub. Check that it is within reach of the hub, unplug it and plug it back in, and try again.") }
        let client = await store.adopt(hello, host: host, paired: paired)
        step(.lettingHubIn)
        for _ in 0..<30 {                              // the hub asks within a few seconds; it says which request is its own
            if await hub.admitHub(on: client, controllerId: hello.id).done { break }
            try await sleep(.seconds(2))
        }
        if let restore, restore != hello.id { await hub.replace(old: restore, new: hello.id) }
        step(.done)
    }
}

/// How letting the hub in on a controller went. `hubCid`: the hub's own key on it, once the hub has asked (its
/// request is never shown to people). `done`: the hub is in and the controller knows that key is the hub's.
struct HubAdmission: Equatable, Sendable { var hubCid: String?; var done: Bool }

extension HubClient {
    /// The Tilt Hub asks to join each of its controllers (to move the blinds for Apple Home) and tells this app which
    /// request is its own, by its key (not its name). An owner lets exactly that one in, once, and tells the controller
    /// it is the hub's key. A hub let in before the controller knew which key is the hub's: only that is told.
    func admitHub(on controller: ControllerClient, controllerId: String) async -> HubAdmission {
        guard let cid = await hubCid(for: controllerId) else { return HubAdmission(hubCid: nil, done: false) }
        guard let people = try? await controller.people(), let hub = people.first(where: { $0.cid == cid }) else { return HubAdmission(hubCid: cid, done: false) }
        if hub.wait == 1 {
            guard (try? await controller.approve(cid: cid, true, owner: false)) != nil,
                  (try? await controller.markHubKey(cid: cid)) != nil else { return HubAdmission(hubCid: cid, done: false) }
            return HubAdmission(hubCid: cid, done: true)
        }
        guard let s = try? await controller.state() else { return HubAdmission(hubCid: cid, done: false) }     // ask again later
        if s.hkey == 0 {
            guard (try? await controller.markHubKey(cid: cid)) != nil else { return HubAdmission(hubCid: cid, done: false) }
        }
        return HubAdmission(hubCid: cid, done: true)
    }
}
