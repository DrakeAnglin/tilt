// First setup of a brand-new controller over Bluetooth: find it, become its owner, then put it on the Tilt Hub (it
// hands over the hub's Thread network, sealed with this phone's new key).
// This file is the Bluetooth radio and the screens; the protocol (firmware ble.h) is BluetoothWire in Shared/Bluetooth.swift.
@preconcurrency import CoreBluetooth
import CryptoKit
import SwiftUI

@MainActor @Observable
final class BleSetup: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    struct Found: Identifiable, Hashable { let id: UUID; let name: String }
    nonisolated static let svc = CBUUID(string: "B11D0001-7A3C-4F52-9E0D-6C2A91D4E5F0")
    nonisolated static let rxId = CBUUID(string: "B11D0002-7A3C-4F52-9E0D-6C2A91D4E5F0")
    nonisolated static let txId = CBUUID(string: "B11D0003-7A3C-4F52-9E0D-6C2A91D4E5F0")

    var found: [Found] = []
    var problem: String?                              // Bluetooth is off or not allowed
    private var central: CBCentralManager?
    private var seen: [UUID: CBPeripheral] = [:]
    private var peripheral: CBPeripheral?
    private var fresh: CBPeripheral?
    private var stage = "" { didSet { trace.append(String(format: "%.1fs %@", Date().timeIntervalSince(t0), stage)) } }
    @ObservationIgnored private var trace: [String] = []
    @ObservationIgnored private var t0 = Date()
    private var rx: CBCharacteristic?
    private var tx: CBCharacteristic?
    private var ready: CheckedContinuation<Void, Error>?
    private var wrote: CheckedContinuation<Void, Error>?
    private var readBack: CheckedContinuation<Data, Error>?

    func start() {
        if let central { if central.state == .poweredOn { central.scanForPeripherals(withServices: [Self.svc]) } }
        else { central = CBCentralManager(delegate: self, queue: .main) }
    }
    func stop() {
        central?.stopScan()
        if let peripheral { central?.cancelPeripheralConnection(peripheral) }
        peripheral = nil; rx = nil; tx = nil
    }

    // ---- the steps
    func connect(_ f: Found) async throws {
        guard let central, central.state == .poweredOn else { throw TiltError("Bluetooth is not ready.") }
        if let old = peripheral { central.cancelPeripheralConnection(old); peripheral = nil; rx = nil; tx = nil }
        // Look again first: a controller that restarted comes back under a new Bluetooth address.
        fresh = nil; trace = []; t0 = Date(); stage = "looking"
        central.scanForPeripherals(withServices: [Self.svc], options: [CBCentralManagerScanOptionAllowDuplicatesKey: true])
        for _ in 0..<40 where fresh == nil { try? await Task.sleep(for: .milliseconds(200)) }
        central.stopScan()
        guard let p = fresh else { throw TiltError("The controller is not in setup mode anymore. Unplug it, plug it back in, and try again.") }
        peripheral = p; p.delegate = self; stage = "connecting"
        let timeout = Task { do { try await Task.sleep(for: .seconds(15)) } catch { return }; self.fail(TiltError("Bluetooth got stuck while \(self.stage). [\(self.trace.joined(separator: ", "))]")) }
        defer { timeout.cancel() }
        do { try await withCheckedThrowingContinuation { ready = $0; central.connect(p) } }
        catch { central.cancelPeripheralConnection(p); throw error }
    }
    /// Write one request and read back the answer (raw bytes). The protocol on top is BluetoothWire (Shared/Bluetooth.swift).
    func exchange(_ data: Data) async throws -> Data {
        guard let p = peripheral, let rx, let tx else { throw TiltError("Bluetooth is not connected.") }
        let timeout = Task { do { try await Task.sleep(for: .seconds(10)) } catch { return }; self.fail(TiltError("The controller stopped answering over Bluetooth.")) }
        defer { timeout.cancel() }
        try await withCheckedThrowingContinuation { wrote = $0; p.writeValue(data, for: rx, type: .withResponse) }
        return try await withCheckedThrowingContinuation { readBack = $0; p.readValue(for: tx) }
    }
    var wire: BluetoothWire { BluetoothWire { try await self.exchange($0) } }

    private func fail(_ e: Error) {
        ready?.resume(throwing: e); ready = nil
        wrote?.resume(throwing: e); wrote = nil
        readBack?.resume(throwing: e); readBack = nil
    }

    // ---- Bluetooth callbacks (all on the main queue)
    nonisolated func centralManagerDidUpdateState(_ c: CBCentralManager) {
        MainActor.assumeIsolated {
            switch c.state {
            case .poweredOn: problem = nil; c.scanForPeripherals(withServices: [Self.svc])
            case .poweredOff: problem = "Bluetooth is off. Turn it on in Control Center."
            case .unauthorized: problem = "Tilt is not allowed to use Bluetooth. Allow it in Settings > Tilt."
            case .unsupported: problem = "This device has no Bluetooth."
            default: break
            }
        }
    }
    nonisolated func centralManager(_ c: CBCentralManager, didDiscover p: CBPeripheral, advertisementData: [String: Any], rssi: NSNumber) {
        let name = (advertisementData[CBAdvertisementDataLocalNameKey] as? String) ?? p.name ?? "Blinds"
        MainActor.assumeIsolated {
            seen[p.identifier] = p
            fresh = p
            if !found.contains(where: { $0.id == p.identifier }) { found.append(Found(id: p.identifier, name: name)) }
        }
    }
    nonisolated func centralManager(_ c: CBCentralManager, didConnect p: CBPeripheral) {
        MainActor.assumeIsolated { stage = "reading its services" }
        p.discoverServices([Self.svc])
    }
    nonisolated func centralManager(_ c: CBCentralManager, didFailToConnect p: CBPeripheral, error: Error?) {
        MainActor.assumeIsolated { fail(TiltError("Could not connect over Bluetooth.")) }
    }
    nonisolated func centralManager(_ c: CBCentralManager, didDisconnectPeripheral p: CBPeripheral, error: Error?) {
        MainActor.assumeIsolated { rx = nil; tx = nil; fail(TiltError("The Bluetooth connection dropped.")) }
    }
    nonisolated func peripheral(_ p: CBPeripheral, didDiscoverServices error: Error?) {
        let note = "services \(p.services?.count ?? -1) err \(error?.localizedDescription ?? "none")"
        MainActor.assumeIsolated { stage = note }
        guard let s = p.services?.first(where: { $0.uuid == Self.svc }) else { MainActor.assumeIsolated { fail(TiltError("That is not a Tilt controller.")) }; return }
        MainActor.assumeIsolated { stage = "reading its setup service" }
        p.discoverCharacteristics(nil, for: s)
        Task { @MainActor in
            try? await Task.sleep(for: .seconds(4))
            if self.ready != nil, self.rx == nil { self.stage = "asking again"; p.discoverServices(nil) }
        }
    }
    /// The controller announced that its services changed: what was found is void, so look again.
    nonisolated func peripheral(_ p: CBPeripheral, didModifyServices invalidated: [CBService]) {
        MainActor.assumeIsolated { stage = "services changed, reading again" }
        p.discoverServices([Self.svc])
    }
    nonisolated func peripheral(_ p: CBPeripheral, didDiscoverCharacteristicsFor s: CBService, error: Error?) {
        MainActor.assumeIsolated {
            rx = s.characteristics?.first { $0.uuid == Self.rxId }
            tx = s.characteristics?.first { $0.uuid == Self.txId }
            if rx != nil && tx != nil { ready?.resume(); ready = nil } else { fail(TiltError("That is not a Tilt controller.")) }
        }
    }
    nonisolated func peripheral(_ p: CBPeripheral, didWriteValueFor ch: CBCharacteristic, error: Error?) {
        MainActor.assumeIsolated {
            if error != nil { wrote?.resume(throwing: TiltError("The controller did not take the request.")) } else { wrote?.resume() }
            wrote = nil
        }
    }
    nonisolated func peripheral(_ p: CBPeripheral, didUpdateValueFor ch: CBCharacteristic, error: Error?) {
        let v = ch.value
        MainActor.assumeIsolated {
            if let v, error == nil { readBack?.resume(returning: v) } else { readBack?.resume(throwing: TiltError("The controller's answer could not be read.")) }
            readBack = nil
        }
    }
}

/// The screens: connect, the Tilt Hub (and an optional restore), joining, done.
struct BluetoothSetupView: View {
    @Environment(AppModel.self) private var model
    @Environment(HubWatch.self) private var hub
    let ble: BleSetup
    let device: BleSetup.Found
    let finished: () -> Void
    enum Step { case connecting, choose, hubJoining, done }
    @State private var step = Step.connecting
    @State private var hello: Hello?
    @State private var paired: Paired?
    @State private var problem: String?
    @State private var moved = false                        // it took the hub's network and left Bluetooth
    @State private var client: ControllerClient?            // sealed commands over Bluetooth, once paired
    @State private var hubStatus = ""
    @State private var backups: [HubWatch.Backup] = []
    @State private var restoreFrom = ""                       // "" = start fresh

    var body: some View {
        Form {
            Group {
            switch step {
            case .connecting:
                Section { if problem == nil { HStack(spacing: 12) { SlatLoader(size: 22); Text("Connecting over Bluetooth…") } } }
            case .choose:
                if !hub.isOwner {
                    Section {
                        Label(hub.record == nil ? "Connect to your Tilt Hub first" : "Only the hub's owner can add controllers", systemImage: "point.3.connected.trianglepath.dotted").font(.headline)
                        Text(hub.record == nil ? "Blinds controllers connect through a Tilt Hub. On the Blinds page, connect to your hub (it shows up there when it is plugged in and this iPhone is on the same Wi-Fi), then come back here." : "Ask the hub's owner to add this controller, or to make you an owner of the hub.").font(.subheadline).foregroundStyle(.secondary)
                        Button("Check Again", systemImage: "arrow.clockwise") { Task { await lookForHub() } }
                    }
                } else {
                    if !backups.isEmpty {
                        Section {
                            Picker("Settings", selection: $restoreFrom) {
                                Text("Start fresh").tag("")
                                ForEach(backups) { b in Text("Restore \(b.name)").tag(b.id) }
                            }
                        } header: { Text("Replacing a controller?") } footer: {
                            Text("Your Tilt Hub kept the settings of these controllers: blind names, open and closed positions, schedules. A restored controller also takes over the old one's place in Apple Home.")
                        }
                    }
                    Section {
                        Button { joinHub() } label: { Label("Connect to the Tilt Hub", systemImage: "point.3.connected.trianglepath.dotted").font(.body.weight(.semibold)) }
                    } footer: { Text("It joins the hub over Thread and shows up in Apple Home through the hub, with no extra setup.") }
                }
            case .hubJoining:
                Section {
                    HStack(spacing: 12) { SlatLoader(size: 22); Text(hubStatus) }
                } footer: { ProgressWords(steps: ["This can take a minute.", "Still working: the controller checks in with the hub about once a second.", "Hang on, nearly there…"]) }
            case .done:
                Section {
                    Label("\(hello?.name ?? "Your controller") is ready", systemImage: "checkmark.circle.fill").foregroundStyle(Palette.good).font(.headline)
                    Text(hub.inHome ? "It is on your Tilt Hub. It shows up in Apple Home by itself in a moment." : "It is on your Tilt Hub. Add the hub to Apple Home once (in the controller's settings) and all its blinds show up.").font(.subheadline).foregroundStyle(.secondary)
                    if restoreFrom.isEmpty { Text("Next, open its room and use the gear to set each blind's open and closed positions.").font(.subheadline).foregroundStyle(.secondary) }
                }
                Section { Button("Done") { finished() } }
            }
            if let problem {
                Section {
                    Label(problem, systemImage: "exclamationmark.triangle").foregroundStyle(Palette.warning)
                    if step == .connecting { Button("Try Again") { Task { await begin() } } }
                }
            }
        }
        }
        .navigationTitle("New Controller").navigationBarTitleDisplayMode(.inline)
        .task { await begin() }
    }

    private func begin() async {
        problem = nil
        do {
            try await ble.connect(device)
            let wire = ble.wire
            let h = try await wire.hello()
            let p: Paired
            if h.owned == 1 {
                guard let mine = Pending.load(h.id) else { throw TiltError("This controller already has an owner. Ask them to share it with you.") }
                p = mine                                               // this phone started setting it up earlier
            } else {
                p = try await wire.pair(phoneName: AppModel.myName)
                Pending.save(h.id, p)
            }
            guard let boot = Data(hex: h.boot), boot.count == 4 else { throw TiltError("The controller gave a bad answer.") }
            hello = h; paired = p; client = wire.client(p, boot: boot)
            await lookForHub()
            step = .choose
        } catch { problem = error.localizedDescription }
    }
    private func lookForHub() async {
        hub.start()
        await hub.refresh()
        guard hub.isOwner, let h = hello else { return }
        let mine = Set(model.controllers.map(\.id))
        // This controller's own backup (it was reset), or one of a controller that is gone (it is replaced).
        backups = await hub.backups().filter { $0.id == h.id || !mine.contains($0.id) }
        if backups.contains(where: { $0.id == h.id }) { restoreFrom = h.id }
    }
    /// Onto the Tilt Hub: give the controller the hub's network (and, if asked, an old controller's settings), wait for
    /// it on the hub, then let the hub in (it asks to join the controller as "Tilt Hub", like a phone would).
    private func joinHub() {
        guard let h = hello, let p = paired, hub.isOwner, let hubHost = hub.host else {
            problem = hub.isOwner ? "The Tilt Hub is not on your Wi-Fi right now. Check it is plugged in, then try again." : "Only the Tilt Hub's owner can add controllers to it."
            return
        }
        problem = nil; step = .hubJoining
        Task {
            do {
                let onThread = h.net == "thread"           // older controllers started on Wi-Fi firmware and switch over
                if !moved {                                 // a second try after it left Bluetooth only waits for it again
                    guard let client else { throw TiltError("The Bluetooth link to the controller was lost. Start the setup again.") }
                    hubStatus = "Getting the hub's network…"
                    let network = try await hub.network()
                    if !restoreFrom.isEmpty {
                        hubStatus = "Restoring its settings…"
                        try await client.restore(backup: try await hub.backup(restoreFrom))
                    }
                    hubStatus = "Joining the hub…"
                    try await client.moveToHub(network: network, onThread: onThread)
                    if onThread && !restoreFrom.isEmpty { try? await client.restart() }   // the restored settings take effect
                    ble.stop()
                    moved = true
                }
                hubStatus = "Waiting for it on the hub…"
                let host = "\(hubHost)/c/\(h.id)"
                var there = false
                for _ in 0..<60 where !there {
                    try? await Task.sleep(for: .seconds(2))
                    if let n = try? await Secure.hello(host), n.net == "thread", n.boot != h.boot || onThread { there = true }
                }
                guard there else { throw TiltError("It did not reach the hub. Check that it is within reach of the hub, unplug it and plug it back in, and try again.") }
                model.adopt(h, host: host, paired: p)
                Pending.clear(h.id)
                hubStatus = "Letting the hub in…"
                if let c = model.controllers.first(where: { $0.id == h.id }) {
                    for _ in 0..<30 {                     // the hub asks within a few seconds; it says which request is its own
                        if let hubCid = await hub.hubCid(for: h.id), let ask = try? await c.client.people().first(where: { $0.wait == 1 && $0.cid == hubCid }) {
                            try? await c.client.approve(cid: ask.cid, true, owner: false)
                            try? await c.client.markHubKey(cid: hubCid)
                            break
                        }
                        try? await Task.sleep(for: .seconds(2))
                    }
                }
                if !restoreFrom.isEmpty && restoreFrom != h.id { await hub.replace(old: restoreFrom, new: h.id) }
                hub.justAdded()
                step = .done
            } catch { problem = error.localizedDescription; step = .choose }
        }
    }
}

/// A pairing made over Bluetooth whose setup is not finished yet (the controller is not on the hub).
enum Pending {
    static func save(_ id: String, _ p: Paired) {
        Keychain.save("pending-" + id, p.key.withUnsafeBytes { Data($0) })
        UserDefaults.standard.set(p.cid.hex, forKey: "pending.cid." + id)
    }
    static func load(_ id: String) -> Paired? {
        guard let k = Keychain.load("pending-" + id), let cid = UserDefaults.standard.string(forKey: "pending.cid." + id).flatMap(Data.init(hex:)) else { return nil }
        return Paired(cid: cid, key: SymmetricKey(data: k), owner: true)
    }
    static func clear(_ id: String) { Keychain.delete("pending-" + id); UserDefaults.standard.removeObject(forKey: "pending.cid." + id) }
}

/// A line under a long wait that changes every few seconds, so it is clear the app is still working.
struct ProgressWords: View {
    let steps: [String]
    @State private var i = 0
    var body: some View {
        Text(steps[min(i, steps.count - 1)])
            .foregroundStyle(.secondary)
            .contentTransition(.opacity)
            .animation(.easeInOut, value: i)
            .task { while !Task.isCancelled { try? await Task.sleep(for: .seconds(4)); if i < steps.count - 1 { i += 1 } } }
    }
}
