// Firmware updates without the App Store: the release list (firmware.json) and the signed files sit on the public
// site repo's GitHub releases (DrakeAnglin/tilt-site; the code repo is private). Releases there are firmware only. The app reads the list, downloads the file and hands it to the controller over the home Wi-Fi.
// The controller only takes a file signed with the release key (firmware/blinds_matter/main/fwkey.h), so a file from
// anywhere else is refused, and an owner has to allow the upload first.
import CryptoKit
import Foundation
import Observation
import SwiftUI
import UniformTypeIdentifiers

struct FirmwareRelease: Decodable, Equatable {
    let version: String, file: String, size: Int, sha256: String
    let notes: String?
}

@MainActor @Observable
final class FirmwareUpdates {
    static let shared = FirmwareUpdates()
    /// Where the release list lives. tools/release_firmware.py writes it; it is uploaded with each release.
    static let defaultSource = "https://github.com/DrakeAnglin/tilt-site/releases/latest/download/firmware.json"

    private(set) var stable: FirmwareRelease?
    private(set) var beta: FirmwareRelease?
    private var checkedAt: Date?

    var source: URL? {
        let custom = developerBuild ? UserDefaults.standard.string(forKey: Prefs.firmwareSource) : nil
        return URL(string: (custom?.isEmpty == false ? custom : nil) ?? Self.defaultSource)
    }
    /// The newest release this phone follows (beta only in a developer build).
    var latest: FirmwareRelease? { developerBuild && UserDefaults.standard.bool(forKey: Prefs.firmwareBeta) ? (beta ?? stable) : stable }

    /// Is there something newer than `current` to install?
    func newer(than current: String) -> FirmwareRelease? {
        guard let l = latest, Api.version(current).lexicographicallyPrecedes(Api.version(l.version)) else { return nil }
        return l
    }

    /// Read the release list (at most once an hour unless `force`).
    func check(force: Bool = false) async {
        if !force, let t = checkedAt, Date().timeIntervalSince(t) < 3600 { return }
        guard let url = source else { return }
        struct Listing: Decodable { let stable: FirmwareRelease?; let beta: FirmwareRelease? }
        guard let (d, r) = try? await URLSession.shared.data(from: url), (r as? HTTPURLResponse)?.statusCode == 200,
              let l = try? JSONDecoder().decode(Listing.self, from: d) else { return }
        stable = l.stable; beta = l.beta; checkedAt = Date()
    }

    /// Download a release and check it is the file the list describes.
    func download(_ r: FirmwareRelease) async throws -> Data {
        guard let base = source, let url = URL(string: r.file, relativeTo: base) else { throw TiltError("The update address is not valid.") }
        let (d, resp) = try await URLSession.shared.data(from: url)
        guard (resp as? HTTPURLResponse)?.statusCode == 200 else { throw TiltError("The update could not be downloaded.") }
        guard Data(SHA256.hash(data: d)).hex == r.sha256 else { throw TiltError("The downloaded update was damaged. Try again.") }
        return d
    }

    enum Step: Equatable { case downloading, sending, restarting, confirming, done(String) }

    /// Put a firmware file on a controller: allow the upload, send it, wait for the restart, then keep the new firmware.
    static func install(_ file: Data, on c: Controller, step: @escaping (Step) -> Void) async throws {
        step(.sending)
        try await c.client.allowUpdate()
        let host = await c.client.transport.host
        guard let url = URL(string: "http://\(host)/api/update") else { throw TiltError("The controller's address is not valid.") }
        var req = URLRequest(url: url, timeoutInterval: 240)
        req.httpMethod = "POST"
        req.setValue("application/octet-stream", forHTTPHeaderField: "Content-Type")
        let (d, _) = try await URLSession.shared.upload(for: req, from: file)
        struct R: Decodable { let ok: Int; let err: String? }
        let r = try? JSONDecoder().decode(R.self, from: d)
        guard r?.ok == 1 else { throw TiltError((r?.err ?? "The controller did not take the update.").capitalizedFirst) }

        step(.restarting)
        try await Task.sleep(for: .seconds(20))
        step(.confirming)
        for _ in 0..<20 {                         // up to about a minute more for it to come back
            if let h = try? await Secure.hello(host), (try? await c.client.keepFirmware()) != nil { step(.done(h.fw)); return }
            try await Task.sleep(for: .seconds(3))
        }
        throw TiltError("The controller did not come back. If it restarts later it goes back to the old firmware by itself.")
    }
}

/// The About section of a room's settings: the firmware it runs, and an update when there is one (owners only).
struct FirmwareSection: View {
    let controller: Controller
    @AppStorage(Prefs.devMode) private var devMode = false
    @State private var job: FirmwareJob?
    @State private var importing = false
    @State private var problem: String?
    private var updates: FirmwareUpdates { .shared }
    var body: some View {
        let v = controller.state?.v ?? ""
        let next = controller.record.owner ? updates.newer(than: v) : nil
        Section {
            LabeledContent("Firmware", value: v)
                // Presented from a row: a sheet on a whole list section does not reliably appear.
                .fileImporter(isPresented: $importing, allowedContentTypes: [.data]) { result in
                    guard case .success(let url) = result else { return }
                    let open = url.startAccessingSecurityScopedResource()
                    defer { if open { url.stopAccessingSecurityScopedResource() } }
                    if let d = try? Data(contentsOf: url) { job = .file(d, url.lastPathComponent) } else { problem = "That file could not be read." }
                }
                .sheet(item: $job) { FirmwareInstallSheet(job: $0, controller: controller).presentationDetents([.height(380)]).interactiveDismissDisabled() }
            if let next {
                Button("Update to \(next.version)", systemImage: "arrow.down.circle") { job = .release(next) }
                if let n = next.notes, !n.isEmpty { Text(n).font(.footnote).foregroundStyle(.secondary) }
            }
            if controller.record.owner && devMode && developerBuild {
                Button("Install from File\u{2026}", systemImage: "doc.badge.arrow.up") { importing = true }
            }
            if let problem { Label(problem, systemImage: "exclamationmark.triangle").font(.footnote).foregroundStyle(Palette.warning) }
        } header: { Text("About") } footer: {
            if controller.record.owner && next == nil && updates.latest != nil { Text("The newest firmware.") }
        }
        .task { await updates.check() }
    }
}

enum FirmwareJob: Identifiable {
    case release(FirmwareRelease), file(Data, String)
    var id: String { switch self { case .release(let r): r.version; case .file(_, let n): n } }
    var title: String { switch self { case .release(let r): "Firmware \(r.version)"; case .file(_, let n): n } }
}

/// Runs one update and shows where it has got to.
struct FirmwareInstallSheet: View {
    @Environment(\.dismiss) private var dismiss
    let job: FirmwareJob
    let controller: Controller
    @State private var step: FirmwareUpdates.Step = .downloading
    @State private var problem: String?
    private var finished: Bool { if case .done = step { return true }; return problem != nil }
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Updating \(controller.state?.name ?? controller.record.name)").font(.title3.weight(.semibold))
            Text(job.title).font(.subheadline).foregroundStyle(.secondary)
            row(.downloading, "Download", order: 0)
            row(.sending, "Send to the controller", order: 1)
            row(.restarting, "Restart", order: 2)
            row(.confirming, "Check it runs", order: 3)
            if case .done(let v) = step { Label("Now running \(v).", systemImage: "checkmark.circle.fill").foregroundStyle(Palette.good) }
            if let problem { Label(problem, systemImage: "exclamationmark.triangle").font(.footnote).foregroundStyle(Palette.warning) }
            else if !finished { Text("Keep Tilt open and stay on your home Wi-Fi. The blinds will not move until it is done.").font(.footnote).foregroundStyle(.secondary) }
            Spacer(minLength: 0)
            if finished { Button { dismiss() } label: { Text("Done").frame(maxWidth: .infinity) }.buttonStyle(.borderedProminent).controlSize(.large) }
        }
        .padding(24)
        .task { await run() }
    }
    private func order(_ s: FirmwareUpdates.Step) -> Int {
        switch s { case .downloading: 0; case .sending: 1; case .restarting: 2; case .confirming: 3; case .done: 4 }
    }
    private func row(_ s: FirmwareUpdates.Step, _ text: String, order n: Int) -> some View {
        let now = order(step)
        return HStack(spacing: 10) {
            if now == n && problem == nil { SlatLoader(size: 18) } else { Image(systemName: now > n ? "checkmark.circle.fill" : "circle").foregroundStyle(now > n ? Palette.good : Color.secondary) }
            Text(text).foregroundStyle(now >= n ? Color.primary : Color.secondary)
        }
    }
    private func run() async {
        do {
            let file: Data
            switch job {
            case .release(let r): step = .downloading; file = try await FirmwareUpdates.shared.download(r)
            case .file(let d, _): file = d
            }
            try await FirmwareUpdates.install(file, on: controller) { s in Task { @MainActor in step = s } }
        } catch { problem = error.localizedDescription }
    }
}
