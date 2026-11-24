// Scenes: a name and a tilt for some blinds, kept on this phone and run from the app, Siri and Shortcuts. The rules
// live here, once: how they are kept, how one is run, and which go when a controller is removed.
import Foundation

struct BlindScene: Identifiable, Codable, Equatable {
    var id = UUID()
    var name = "New Scene"
    var symbol = "sun.max"
    var tilts: [BlindTarget: Int] = [:]
}

enum Scenes {
    static func load(_ d: UserDefaults = .standard) -> [BlindScene] {
        d.data(forKey: Prefs.scenes).flatMap { try? JSONDecoder().decode([BlindScene].self, from: $0) } ?? []
    }
    static func save(_ scenes: [BlindScene], _ d: UserDefaults = .standard) {
        d.set(try? JSONEncoder().encode(scenes), forKey: Prefs.scenes)
    }

    /// What running a scene did: how many blinds were told to move, and why the others were not (per controller).
    struct Run: Equatable {
        var reached = 0
        var failed: [String: String] = [:]
    }
    /// Move each of the scene's blinds, all at once. A controller with no client (removed, or not on this phone) is
    /// skipped.
    static func run(_ scene: BlindScene, clients: [String: ControllerClient]) async -> Run {
        await withTaskGroup(of: (String, String?).self) { g in
            for (t, tilt) in scene.tilts {
                guard let c = clients[t.controller] else { continue }
                g.addTask {
                    do { try await c.go(blind: t.blind, tilt: tilt); return (t.controller, nil) } catch { return (t.controller, error.localizedDescription) }
                }
            }
            var r = Run()
            for await (id, err) in g { if let err { r.failed[id] = err } else { r.reached += 1 } }
            return r
        }
    }

    /// The scenes left once a controller is removed: those that only moved its blinds go with it.
    static func prune(_ scenes: [BlindScene], controller id: String) -> [BlindScene] {
        scenes.filter { $0.tilts.isEmpty || !$0.tilts.keys.allSatisfy { $0.controller == id } }
    }
}

enum TiltMath {
    /// "Percent open" (Siri, Shortcuts) as a tilt: the controller closes toward its own "Close" side, so ask for the
    /// matching share of the way there. 100% open is level (0); 0% open is fully closed on that side.
    static func tilt(percentOpen: Int, closeUp: Bool) -> Int {
        let p = min(max(percentOpen, 0), 100)
        return (closeUp ? 1 : -1) * (100 - p)
    }
}
