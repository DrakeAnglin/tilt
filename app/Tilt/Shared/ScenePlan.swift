// Scenes as the app shows them, and how they map onto the controllers. Scenes are kept on the controllers, so every
// phone with a key sees the same ones (a Guest on another Apple account too). A Scene may cover blinds on several
// controllers: each keeps its own part (its Ports' tilts) under the same id (gid), with the name, icon and the time of
// the last edit (ver). The newest edit's name and icon win; when two phones edit at once, the last save wins.
// ScenePlan is pure: no network, no UI. The phone keeps a copy (SceneStore) for Siri, Shortcuts and controllers it
// cannot reach right now.
import Foundation

struct BlindScene: Identifiable, Codable, Equatable {
    var id = UUID()
    var name = "New Scene"
    var symbol = "sun.max"
    var tilts: [BlindTarget: Int] = [:]
    /// The id the controllers know it by (0: not on any controller yet, a Scene made before they kept them).
    var gid: UInt32 = UInt32.random(in: 1...UInt32.max)
    /// When it was last edited, seconds since 1970.
    var ver: UInt32 = 0

    init(id: UUID = UUID(), name: String = "New Scene", symbol: String = "sun.max", tilts: [BlindTarget: Int] = [:],
         gid: UInt32 = UInt32.random(in: 1...UInt32.max), ver: UInt32 = 0) {
        self.id = id; self.name = name; self.symbol = symbol; self.tilts = tilts; self.gid = gid; self.ver = ver
    }
    // A copy saved by an older app has no gid or ver: it is then not on any controller yet.
    init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        name = try c.decode(String.self, forKey: .name)
        symbol = try c.decode(String.self, forKey: .symbol)
        tilts = try c.decode([BlindTarget: Int].self, forKey: .tilts)
        gid = try c.decodeIfPresent(UInt32.self, forKey: .gid) ?? 0
        ver = try c.decodeIfPresent(UInt32.self, forKey: .ver) ?? 0
    }
    /// The same id on every phone for a Scene first seen on a controller (Shortcuts keep pointing at it).
    static func id(for gid: UInt32) -> UUID {
        var b = [UInt8](repeating: 0, count: 16)
        b[0] = 0x54; b[1] = 0x49; b[2] = 0x4C; b[3] = 0x54          // "TILT"
        withUnsafeBytes(of: gid.bigEndian) { for (i, x) in $0.enumerated() { b[12 + i] = x } }
        b[6] = 0x80; b[8] = 0x80                                     // version 8 (custom), RFC 4122 variant
        return UUID(uuid: (b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7], b[8], b[9], b[10], b[11], b[12], b[13], b[14], b[15]))
    }
}

/// One Scene's part on one controller, as /api/scenes reports it (firmware scenes.h, wire.h).
struct SceneSlot: Decodable, Equatable { var gid: UInt32, ver: UInt32; var name: String, sym: String; var mask: Int; var t: [Int] }
struct SceneList: Decodable { var max: Int; var sc: [SceneSlot] }

/// One Scene write on one controller (mask 0 deletes its part there).
struct SceneWrite: Equatable { var controller: String; var value: SceneSlot }

enum ScenePlan {
    /// How many Scenes one controller keeps (firmware scenes.h SCENES).
    static let perController = 16
    /// The Scenes, put together from the controllers that answered (`read`), with the phone's copy (`kept`) for the
    /// controllers that did not. A kept Scene that no answering controller has any more was deleted on another phone:
    /// only its part on controllers that did not answer is left, or nothing. Kept order first, new ones after.
    static func scenes(read: [String: [SceneSlot]], kept: [BlindScene]) -> [BlindScene] {
        var found: [UInt32: BlindScene] = [:]
        var order: [UInt32] = []
        for c in read.keys.sorted() {
            for sl in read[c]! where sl.gid != 0 {
                var s = found[sl.gid] ?? BlindScene(id: BlindScene.id(for: sl.gid), name: sl.name, symbol: sl.sym, gid: sl.gid, ver: sl.ver)
                if found[sl.gid] == nil { order.append(sl.gid) }
                if sl.ver > s.ver { s.name = sl.name; s.symbol = sl.sym; s.ver = sl.ver }
                for (p, t) in sl.t.enumerated() where sl.mask >> p & 1 == 1 { s.tilts[BlindTarget(controller: c, blind: p)] = t }
                found[sl.gid] = s
            }
        }
        var out: [BlindScene] = []
        for k in kept {
            let away = k.tilts.filter { read[$0.key.controller] == nil }           // its part on controllers that did not answer
            if k.gid == 0 { out.append(k); continue }                               // not shared yet: SceneStore puts it on the controllers
            if var s = found.removeValue(forKey: k.gid) {
                s.id = k.id                                                         // the id this phone's Shortcuts know
                if k.ver > s.ver { s.name = k.name; s.symbol = k.symbol; s.ver = k.ver }
                s.tilts.merge(away) { now, _ in now }
                out.append(s)
            } else if !away.isEmpty {
                var s = k; s.tilts = away; out.append(s)
            }
        }
        out += order.compactMap { found[$0] }
        return out
    }

    /// The writes that save (or delete) a Scene: its part on each controller it covers, and a delete on each other
    /// controller that has it. Only controllers in `read` are written; a Scene with blinds on a controller not in `read`
    /// and not `localOnly` (firmware without Scenes, whose part stays on the phone) cannot be saved now.
    static func writes(_ s: BlindScene, delete: Bool = false, read: [String: [SceneSlot]], localOnly: Set<String> = [], ports: [String: Int] = [:]) throws(PlanProblem) -> [SceneWrite] {
        for t in s.tilts.keys where read[t.controller] == nil && !localOnly.contains(t.controller) { throw .notRead(controller: t.controller) }
        var out: [SceneWrite] = []
        for c in read.keys.sorted() {
            let n = ports[c] ?? ControllerLimits.fallback.ports
            var mask = 0
            var t = Array(repeating: 0, count: n)
            if !delete { for (b, v) in s.tilts where b.controller == c && b.blind < n { mask |= 1 << b.blind; t[b.blind] = v } }
            let has = read[c]!.contains { $0.gid == s.gid }
            if mask == 0 && !has { continue }
            if mask != 0 && !has && read[c]!.count >= perController { throw .full(controller: c) }
            out.append(SceneWrite(controller: c, value: SceneSlot(gid: s.gid, ver: s.ver, name: s.name, sym: s.symbol, mask: mask, t: mask == 0 ? [] : t)))
        }
        return out
    }
}
