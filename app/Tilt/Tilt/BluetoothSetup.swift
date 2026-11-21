// First setup of a brand-new controller over Bluetooth: find it, become its owner, put it on Wi-Fi.
// It mirrors firmware/blinds_matter/main/ble.h. The Wi-Fi password is sealed with this phone's new key before it is sent.
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
        guard let p = fresh else { throw TiltError("The controller is not in setup mode any more. Unplug it, plug it back in, and try again.") }
        peripheral = p; p.delegate = self; stage = "connecting"
        let timeout = Task { do { try await Task.sleep(for: .seconds(15)) } catch { return }; self.fail(TiltError("Bluetooth got stuck while \(self.stage). [\(self.trace.joined(separator: ", "))]")) }
        defer { timeout.cancel() }
        do { try await withCheckedThrowingContinuation { ready = $0; central.connect(p) } }
        catch { central.cancelPeripheralConnection(p); throw error }
    }
    /// One request and its answer: (status, body). Status is 200, 400 or 500 (only the first digit travels).
    func request(_ data: Data) async throws -> (Int, Data) {
        guard let p = peripheral, let rx, let tx else { throw TiltError("Bluetooth is not connected.") }
        let timeout = Task { do { try await Task.sleep(for: .seconds(10)) } catch { return }; self.fail(TiltError("The controller stopped answering over Bluetooth.")) }
        defer { timeout.cancel() }
        try await withCheckedThrowingContinuation { wrote = $0; p.writeValue(data, for: rx, type: .withResponse) }
        let d = try await withCheckedThrowingContinuation { readBack = $0; p.readValue(for: tx) }
        guard let first = d.first, first >= 0x30, first <= 0x39 else { throw TiltError("The controller gave a bad answer.") }
        return (Int(first - 0x30) * 100, d.dropFirst())
    }
    func hello() async throws -> Hello {
        let (st, d) = try await request(Data("H".utf8))
        guard st == 200, let h = try? JSONDecoder().decode(Hello.self, from: d) else { throw TiltError("That is not a Tilt controller.") }
        return h
    }
    func pair() async throws -> Paired {
        try await Secure.pair(phoneName: UIDevice.current.name, invite: nil) { try await self.request(Data("P".utf8) + $0) }
    }
    /// A sealed command, as in Link.call, carried over Bluetooth.
    func sealed(_ command: String, as p: Paired, boot: Data) async throws -> [String: Any] {
        let counter = UInt64(Date().timeIntervalSince1970 * 1000)
        let nonce = boot + withUnsafeBytes(of: counter.bigEndian) { Data($0) }
        let box = try AES.GCM.seal(Data(command.utf8), using: p.key, nonce: AES.GCM.Nonce(data: nonce), authenticating: Data("blinds-v1".utf8) + p.cid)
        let (st, d) = try await request(Data("X".utf8) + p.cid + nonce + box.ciphertext + box.tag)
        guard st == 200, d.count >= 28 else { throw TiltError("The controller refused the command.") }
        let back = try AES.GCM.SealedBox(nonce: AES.GCM.Nonce(data: d.prefix(12)), ciphertext: d.dropFirst(12).dropLast(16), tag: d.suffix(16))
        let plain = try AES.GCM.open(back, using: p.key, authenticating: Data("blinds-v1r".utf8) + p.cid + nonce)
        return (try? JSONSerialization.jsonObject(with: plain)) as? [String: Any] ?? [:]
    }
    struct Net: Identifiable, Hashable { let ssid: String; let rssi: Int; let locked: Bool; var id: String { ssid } }
    /// The Wi-Fi networks the controller can see (it looks around for a few seconds).
    func networks(as p: Paired, boot: Data, again: Bool) async throws -> [Net] {
        var first = again
        for _ in 0..<10 {
            let r = try await sealed("/api/scan" + (first ? "?new=1" : ""), as: p, boot: boot)
            first = false
            if (r["busy"] as? Int) == 0, let list = r["nets"] as? [[String: Any]] {
                return list.compactMap { n in (n["s"] as? String).map { Net(ssid: $0, rssi: n["r"] as? Int ?? -90, locked: (n["l"] as? Int ?? 1) == 1) } }
            }
            try await Task.sleep(for: .milliseconds(1200))
        }
        return []
    }
    /// Give the controller the network, then wait until it is on it. Returns its address.
    func joinWifi(ssid: String, password: String, as p: Paired, boot: Data) async throws -> String {
        let r = try await sealed("/api/setwifi?ssid=\(ssid.urlQuery)&pass=\(password.urlQuery)", as: p, boot: boot)
        if (r["ok"] as? Int) != 1 { throw TiltError(((r["err"] as? String) ?? "The controller did not accept that network.").capitalizedFirst) }
        for _ in 0..<20 {
            try await Task.sleep(for: .seconds(2))
            guard let s = try? await sealed("/api/wifistate", as: p, boot: boot) else { continue }
            if (s["up"] as? Int) == 1, let ip = s["ip"] as? String, !ip.isEmpty, (s["ssid"] as? String) == ssid { return ip }
        }
        throw TiltError("The controller could not join “\(ssid)”. Check the name and password. It needs a 2.4 GHz network.")
    }

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

/// The screens: connect, Wi-Fi name and password, joining, done.
struct BluetoothSetupView: View {
    @Environment(AppModel.self) private var model
    let ble: BleSetup
    let device: BleSetup.Found
    let finished: () -> Void
    enum Step { case connecting, wifi, joining, done }
    @State private var step = Step.connecting
    @State private var hello: Hello?
    @State private var paired: Paired?
    @State private var ssid = ""
    @State private var password = ""
    @State private var problem: String?
    @State private var nets: [BleSetup.Net] = []
    @State private var scanning = false
    @State private var chosen: String?
    @State private var asking = false
    @State private var typed = ""
    @FocusState private var typing: Bool

    var body: some View {
        Form {
            switch step {
            case .connecting:
                Section { if problem == nil { HStack(spacing: 12) { ProgressView(); Text("Connecting over Bluetooth…") } } }
            case .wifi:
                if let net = chosen {
                    Section {
                        LabeledContent("Network", value: net)
                        SecureField("Password", text: $password).focused($typing)
                    } footer: { Text("The password is sent sealed, over Bluetooth, to the controller only.") }
                    Section {
                        Button("Join Wi-Fi") { join() }
                        Button("Choose Another Network") { chosen = nil; password = "" }
                    }
                } else {
                    Section {
                        if scanning { HStack(spacing: 12) { ProgressView(); Text("Looking for networks…").foregroundStyle(.secondary) } }
                        ForEach(nets) { n in
                            Button { pick(n.ssid, locked: n.locked) } label: {
                                HStack {
                                    Text(n.ssid).foregroundStyle(.primary)
                                    Spacer()
                                    if n.locked { Image(systemName: "lock.fill").font(.footnote).foregroundStyle(.secondary) }
                                    Image(systemName: "wifi", variableValue: n.rssi > -60 ? 1 : n.rssi > -72 ? 0.6 : 0.3).foregroundStyle(.secondary)
                                }
                            }
                        }
                        if !scanning && nets.isEmpty { Text("No networks found.").foregroundStyle(.secondary) }
                    } header: { Text("Choose your Wi-Fi") } footer: {
                        Text("These are the networks the controller can see. It only uses 2.4 GHz, so a 5 GHz-only network will not be listed.")
                    }
                    Section {
                        if !scanning { Button("Look Again", systemImage: "arrow.clockwise") { Task { await scan(again: true) } } }
                        Button("Other Network…", systemImage: "ellipsis") { asking = true }
                    }
                }
            case .joining:
                Section { HStack(spacing: 12) { ProgressView(); Text("Joining “\(ssid)”… This can take half a minute.") } }
            case .done:
                Section {
                    Label("\(hello?.name ?? "Your controller") is ready", systemImage: "checkmark.circle.fill").foregroundStyle(.green).font(.headline)
                    Text("Next, open its room and use the gear to set each blind's open and closed positions.").font(.subheadline).foregroundStyle(.secondary)
                }
                Section { Button("Done") { finished() } }
            }
            if let problem {
                Section {
                    Label(problem, systemImage: "exclamationmark.triangle").foregroundStyle(.orange)
                    if step == .connecting { Button("Try Again") { Task { await begin() } } }
                }
            }
        }
        .skyPage()
        .navigationTitle("New Controller").navigationBarTitleDisplayMode(.inline)
        .task { await begin() }
        .alert("Network Name", isPresented: $asking) {
            TextField("Name", text: $typed).textInputAutocapitalization(.never).autocorrectionDisabled()
            Button("Cancel", role: .cancel) {}
            Button("OK") { if !typed.isEmpty { pick(typed, locked: true) } }
        }
    }

    private func begin() async {
        problem = nil
        do {
            try await ble.connect(device)
            let h = try await ble.hello()
            let p: Paired
            if h.owned == 1 {
                guard let mine = Pending.load(h.id) else { throw TiltError("This controller already has an owner. Ask them to share it with you.") }
                p = mine                                               // this phone started setting it up earlier
            } else {
                p = try await ble.pair()
                Pending.save(h.id, p)
            }
            hello = h; paired = p
            if h.wifi == 1, let ip = h.ip, !ip.isEmpty { finish(ip) } else { step = .wifi; await scan(again: false) }
        } catch { problem = error.localizedDescription }
    }
    private func scan(again: Bool) async {
        guard let h = hello, let p = paired, let boot = Data(hex: h.boot) else { return }
        scanning = true; defer { scanning = false }
        nets = (try? await ble.networks(as: p, boot: boot, again: again)) ?? nets
    }
    private func pick(_ name: String, locked: Bool) {
        ssid = name; chosen = name; password = ""
        if locked { typing = true } else { join() }
    }
    private func join() {
        guard let h = hello, let p = paired, let boot = Data(hex: h.boot) else { return }
        problem = nil; step = .joining
        Task {
            do {
                let ip = try await ble.joinWifi(ssid: ssid, password: password, as: p, boot: boot)
                finish(ip)
            } catch { problem = error.localizedDescription; step = .wifi }
        }
    }
    private func finish(_ ip: String) {
        guard let h = hello, let p = paired else { return }
        model.adopt(h, host: ip, paired: p)
        Pending.clear(h.id)
        ble.stop()
        step = .done
    }
}

/// A pairing made over Bluetooth whose setup is not finished yet (the controller is not on Wi-Fi).
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
