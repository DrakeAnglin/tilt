// Where a request to join a controller stands, read from the model's lists. The Add a New Device sheet shows it after
// Ask to Join, so the person sees the code and what happens next.
import Foundation

enum JoinProgress: Equatable {
    /// Asked, no answer yet. `code` is what both phones show.
    case waiting(code: String)
    /// An owner let this phone in.
    case approved
    /// An owner said no.
    case declined
    /// The request was taken back (Cancel Request), or never made.
    case gone

    /// `joined`: the controllers this phone is in. `waiting`: the ones it asked to join. `denied`: ids an owner declined.
    static func of(id: String, joined: [ControllerRecord], waiting: [ControllerRecord], denied: Set<String>) -> JoinProgress {
        if joined.contains(where: { $0.id == id }) { return .approved }
        guard let asked = waiting.first(where: { $0.id == id }) else { return .gone }
        return denied.contains(id) ? .declined : .waiting(code: asked.code ?? "")
    }
}
