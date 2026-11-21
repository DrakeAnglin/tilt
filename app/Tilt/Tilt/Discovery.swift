// Finding controllers on the Wi-Fi network. Each one announces itself with Bonjour as _tilt._tcp, with its id,
// address and whether it already has an owner.
import Foundation
import Network
import Observation

struct FoundController: Identifiable, Equatable {
    let id: String, name: String, host: String
    let owned: Bool
}

@MainActor @Observable
final class Discovery {
    var found: [FoundController] = []
    private var browser: NWBrowser?

    func start() {
        guard browser == nil else { return }
        let b = NWBrowser(for: .bonjourWithTXTRecord(type: "_tilt._tcp", domain: nil), using: .tcp)
        b.browseResultsChangedHandler = { [weak self] results, _ in
            var list: [FoundController] = []
            for r in results {
                guard case let .bonjour(txt) = r.metadata, let id = txt["id"], let ip = txt["ip"], !ip.isEmpty, ip != "0.0.0.0" else { continue }
                list.append(FoundController(id: id, name: txt["name"] ?? "Blinds", host: ip, owned: txt["owned"] == "1"))
            }
            Task { @MainActor in self?.found = list.sorted { $0.name < $1.name } }
        }
        b.start(queue: .main)
        browser = b
    }
    func stop() { browser?.cancel(); browser = nil }
}
