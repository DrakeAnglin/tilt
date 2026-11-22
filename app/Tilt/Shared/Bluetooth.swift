// The first-setup protocol over Bluetooth, without Bluetooth itself (that is Tilt/BluetoothSetup.swift).
// It mirrors firmware/blinds_matter/main/ble.h: the app writes one request, then reads one answer.
//   request: 'H' hello | 'P' + pairing JSON | 'X' + sealed command (the same packet as over Wi-Fi, see Frame)
//   answer:  status digit ('2' good, '4' refused, '5' failed) + body
import Foundation

struct BluetoothWire: Sendable {
    /// Write these bytes and read back the controller's answer, as raw bytes.
    let exchange: @Sendable (Data) async throws -> Data

    /// One request and its answer: (status, body). Status is 200, 400 or 500 (only the first digit travels).
    func request(_ data: Data) async throws -> (Int, Data) {
        let d = try await exchange(data)
        guard let first = d.first, first >= 0x30, first <= 0x39 else { throw TiltError("The controller gave a bad answer.") }
        return (Int(first - 0x30) * 100, d.dropFirst())
    }
    func hello() async throws -> Hello {
        let (st, d) = try await request(Data("H".utf8))
        guard st == 200, let h = try? JSONDecoder().decode(Hello.self, from: d) else { throw TiltError("That is not a Tilt controller.") }
        return h
    }
    func pair(phoneName: String) async throws -> Paired {
        try await Secure.pair(phoneName: phoneName) { try await request(Data("P".utf8) + $0) }
    }
    /// The controller client for a phone paired over Bluetooth. `boot` is from the controller's hello.
    func client(_ p: Paired, boot: Data, clock: (@Sendable () -> UInt64)? = nil) -> ControllerClient {
        ControllerClient(transport: BluetoothLink(wire: self, sealer: clock.map { Sealer(cid: p.cid, key: p.key, clock: $0) } ?? Sealer(cid: p.cid, key: p.key), boot: boot))
    }
}

/// Sealed commands over Bluetooth: the same seam as the Wi-Fi Link and the demo room.
actor BluetoothLink: ControllerTransport {
    nonisolated let host = "bluetooth"
    private let wire: BluetoothWire
    private var sealer: Sealer
    private let boot: Data

    init(wire: BluetoothWire, sealer: Sealer, boot: Data) { self.wire = wire; self.sealer = sealer; self.boot = boot }

    func move(to host: String) {}
    func call(_ command: String) async throws -> Data {
        let (packet, nonce) = try sealer.seal(command, boot: boot)
        let (st, d) = try await wire.request(Data("X".utf8) + packet)
        guard st == 200, d.count >= 28 else { throw TiltError("The controller refused the command.") }
        return try sealer.open(Data(d), nonce: nonce)
    }
}
