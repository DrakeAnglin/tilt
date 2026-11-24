// Putting firmware on a controller (through the Tilt Hub) or on the hub itself: one flow that returns its steps, so the
// screens (Tilt/FirmwareUpdate.swift, Tilt/HubView.swift) only show them, and the tests run it against fakes.
// The release list and downloads stay in FirmwareUpdates (Tilt/FirmwareUpdate.swift).
import Foundation

struct FirmwareRelease: Decodable, Equatable, Sendable {
    let version: String, file: String, size: Int, sha256: String
    let notes: String?
    /// Only what changed since an earlier firmware ("from": that image's SHA-256): about a minute over Thread
    /// instead of seven. Used when the controller runs exactly that firmware.
    let patches: [Patch]?
    struct Patch: Decodable, Equatable, Sendable { let from: String, file: String, size: Int, sha256: String }
}

enum FirmwareStep: Equatable, Sendable { case downloading, sending, hub(Int), restarting, confirming, done(String) }

/// Posts a firmware file to "http://<address>" and returns the answer. One for a controller (through the hub) and the hub.
protocol FirmwareUploader: Sendable {
    func upload(_ file: Data, to address: String, timeout: TimeInterval) async throws -> Data
}
struct HTTPUploader: FirmwareUploader {
    func upload(_ file: Data, to address: String, timeout: TimeInterval) async throws -> Data {
        guard let url = URL(string: "http://\(address)") else { throw TiltError("The address is not valid.") }
        var req = URLRequest(url: url, timeoutInterval: timeout)
        req.httpMethod = "POST"
        req.setValue("application/octet-stream", forHTTPHeaderField: "Content-Type")
        return try await URLSession.shared.upload(for: req, from: file).0
    }
}

struct FirmwareInstaller: Sendable {
    enum Job: Sendable { case release(FirmwareRelease), file(Data) }

    /// The client for the connected hub, asked for again at each use: the hub may get a new address during an update.
    let hub: @Sendable () async throws -> HubClient
    let uploader: any FirmwareUploader
    let sleep: @Sendable (Duration) async throws -> Void
    /// The hello at an address: a controller's ("<hub>/c/<id>") or the hub's own ("<hub>/hub"). nil when it does not answer.
    var look: @Sendable (String) async -> Hello? = { try? await Secure.hello($0) }
    /// A release file by its name in the release list, checked against its SHA-256.
    var download: @Sendable (_ file: String, _ sha256: String) async throws -> Data

    /// Put firmware on a controller on the hub: allow the upload, send it, follow it through the hub, wait for the
    /// restart, then keep the new firmware. A release goes as a patch when there is one for exactly the firmware the
    /// controller runs, and as the whole file if that does not work.
    func install(_ job: Job, on controller: ControllerClient, id: String) -> AsyncThrowingStream<FirmwareStep, Error> {
        stream { step in
            switch job {
            case .file(let d): try await put(d, on: controller, id: id, step)
            case .release(let r):
                step(.downloading)
                let img = await look(await controller.transport.host)?.img
                if let p = r.patches?.first(where: { $0.from == img }), let d = try? await download(p.file, p.sha256) {
                    do { try await put(d, on: controller, id: id, step); return } catch { step(.downloading) }
                }
                try await put(try await download(r.file, r.sha256), on: controller, id: id, step)
            }
        }
    }

    enum HubStep: Equatable, Sendable { case downloading, sending, restarting, done }
    /// Put new firmware on the hub itself, over Wi-Fi (owner): it restarts on it and keeps it once Wi-Fi and Apple Home
    /// work, otherwise it goes back by itself. Done once the hub answers with the new version.
    func updateHub(to r: FirmwareRelease, hubHost: String) -> AsyncThrowingStream<HubStep, Error> {
        stream { step in
            step(.downloading)
            let file = try await download(r.file, r.sha256)
            step(.sending)
            try await hub().allowHubUpdate()
            try await post(file, to: HubApi.base(hubHost) + HubApi.upload, timeout: 180, refused: "The Tilt Hub did not take the update.")
            step(.restarting)
            for _ in 0..<40 {
                try await sleep(.seconds(3))
                if await look(HubApi.base(hubHost))?.fw == r.version { step(.done); return }
            }
            throw TiltError("The Tilt Hub did not come back with the new firmware. If it cannot start it, it goes back to the old one by itself.")
        }
    }

    // ---- the steps
    private func put(_ file: Data, on c: ControllerClient, id: String, _ step: (FirmwareStep) -> Void) async throws {
        step(.sending)
        try await c.allowUpdate()
        try await hub().allowUpload(for: id)                 // the hub takes a file only when its owner says so
        let host = await c.transport.host
        // The hub takes the file and feeds it over Thread.
        guard host.contains(ControllerRecord.hubPath) else { throw TiltError("This controller is not on a Tilt Hub. Set it up again to put it on the hub.") }
        let before = await look(host)
        try await post(file, to: host + HubApi.upload, timeout: 240, refused: "The controller did not take the update.")
        step(.hub(0))
        var done = false
        for _ in 0..<900 where !done {                     // a few minutes; up to half an hour for an older controller
            try await sleep(.seconds(2))
            guard let m = try? await hub().info().c.first(where: { $0.id == id }) else { continue }
            switch m.ota {
            case 4: throw TiltError((m.otaErr ?? "The update did not go through.").capitalizedFirst)
            case 3: done = true
            case 2: step(.hub(100))
            default: step(.hub(m.otaPct))
            }
        }
        guard done else { throw TiltError("The update through the hub did not finish.") }
        step(.restarting)
        try await sleep(.seconds(10))
        step(.confirming)
        for _ in 0..<40 {                                  // up to a minute or two more for it to come back
            // Kept only once it has restarted (a new boot id): keeping before that would keep the old firmware's trial.
            if let h = await look(host), h.boot != before?.boot, (try? await c.keepFirmware()) != nil { step(.done(h.fw)); return }
            try await sleep(.seconds(3))
        }
        throw TiltError("The controller did not come back. If it restarts later it goes back to the old firmware by itself.")
    }
    /// Send a file and read the {"ok":…} answer.
    private func post(_ file: Data, to address: String, timeout: TimeInterval, refused: String) async throws {
        struct R: Decodable { let ok: Int; let err: String? }
        let r = try? JSONDecoder().decode(R.self, from: try await uploader.upload(file, to: address, timeout: timeout))
        guard r?.ok == 1 else { throw TiltError((r?.err ?? refused).capitalizedFirst) }
    }
    private func stream<S: Sendable>(_ body: @escaping @Sendable (_ step: (S) -> Void) async throws -> Void) -> AsyncThrowingStream<S, Error> {
        AsyncThrowingStream { c in
            let t = Task { do { try await body { c.yield($0) }; c.finish() } catch { c.finish(throwing: error) } }
            c.onTermination = { _ in t.cancel() }
        }
    }
}
