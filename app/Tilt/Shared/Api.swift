// Every command the app sends a controller, in one place. The controller's side is firmware/blinds_matter/main/web.h:
// a change to a command there is a change here, and nowhere else in the app.
import Foundation

enum Api {
    // ---- reading
    static let state = "/api/s"
    static let config = "/api/cfg"
    static let keys = "/api/keys"
    static let dev = "/api/dev"
    static let log = "/api/log"

    // ---- moving
    static let stop = "/api/stop"
    /// One blind to a tilt (-100…100). It moves alone: following is only for a turn of the wand.
    static func go(blind: Int, tilt: Int) -> String { "/api/go?b=\(blind)&t=\(tilt)" }
    /// One blind to a named position: open, close, fav.
    static func go(blind: Int, to word: String) -> String { "/api/go?b=\(blind)&to=\(word)" }
    /// Every blind to a named position. `gently`: take this many minutes.
    static func goAll(to word: String, gently minutes: Int = 0) -> String { "/api/go?b=all&to=\(word)" + (minutes > 0 ? "&ramp=\(minutes)" : "") }
    /// Hold-to-turn: one short push.
    static func jog(blind: Int, dir: Int, percent: Int, ms: Int = 450) -> String { "/api/jog?b=\(blind)&d=\(dir)&p=\(percent)&ms=\(ms)" }

    // ---- setting up a blind
    static func watch(blind: Int) -> String { "/api/watch?b=\(blind)" }
    static func mark(blind: Int, _ which: String) -> String { "/api/mark?b=\(blind)&w=\(which)" }

    // ---- settings and schedules
    static func set(_ key: String, _ value: String) -> String { "/api/set?k=\(key)&v=\(value.urlQuery)" }
    /// The start of a schedule command for one slot; the caller adds the fields.
    static func schedule(slot: Int) -> String { "/api/sched?i=\(slot)&" }
    /// The Scenes this controller keeps its part of (anyone paired may read and write them).
    static let scenes = "/api/scenes"
    /// Save one Scene's part (mask 0 deletes it). `t`: one tilt per Port.
    static func scene(gid: UInt32, ver: UInt32, name: String, symbol: String, mask: Int, tilts: [Int]) -> String {
        "/api/scene?gid=\(gid)&ver=\(ver)&name=\(name.urlQuery)&sym=\(symbol.urlQuery)&mask=\(mask)&t=" + tilts.map(String.init).joined(separator: ",")
    }
    static let homeOpen = "/api/homeopen"
    /// The Tilt Hub's Apple Home setup code, from a controller on that hub (owner).
    /// The Tilt Hub's Thread network that a controller on it keeps (owner), to hand to a new controller.
    static let backup = "/api/backup"
    static func hubJoin(network: String) -> String { "/api/hubjoin?ds=\(network)" }
    /// Go back to the firmware in the other slot, the one before the last update (the controller restarts).
    static let swapFirmware = "/api/swapfw"
    /// Put a settings backup back, one piece at a time (hex; end=1 on the last).
    static func restore(offset: Int, hex: String, last: Bool) -> String { "/api/restore?o=\(offset)&d=\(hex)" + (last ? "&end=1" : "") }
    /// An owner allows a firmware upload for the next 5 minutes.
    static let otaOpen = "/api/otaopen"
    /// Keep the firmware that is on trial after an update (otherwise the next restart goes back to the old one).
    static let keep = "/api/keep"
    static let reboot = "/api/reboot"

    // ---- people
    static func approve(cid: String, _ ok: Bool, owner: Bool) -> String { "/api/approve?cid=\(cid)&ok=\(ok ? 1 : 0)&owner=\(owner ? 1 : 0)" }
    static func revoke(cid: String) -> String { "/api/revoke?cid=\(cid)" }
    static let revokeAll = "/api/revoke?cid=all"
    static func makeOwner(cid: String, _ on: Bool) -> String { "/api/makeowner?cid=\(cid)&on=\(on ? 1 : 0)" }
    static func rename(cid: String, to name: String) -> String { "/api/keyname?cid=\(cid)&name=\(name.urlQuery)" }
    /// Take back a request to join (the only command a waiting phone may send).
    static let leave = "/api/leave"
    /// Tell a controller which key is the Tilt Hub's (owner): from then on it trusts only messages proven with it.
    static func hubKey(cid: String) -> String { "/api/hubkey?cid=\(cid)" }

    // ---- first setup

    // ---- which firmware this version of the app needs
    /// The oldest controller firmware that has every command above.
    static let minFirmware = "2.2.0-dev9"
    /// "2.2.0-dev9" → [2, 2, 0, 9]; a release ("2.2.0") counts as newer than any of its dev builds.
    static func version(_ s: String) -> [Int] {
        let halves = s.split(separator: "-", maxSplits: 1)
        var n = (halves.first ?? "").split(separator: ".").map { Int($0) ?? 0 }
        while n.count < 3 { n.append(0) }
        n.append(halves.count > 1 ? (Int(halves[1].filter(\.isNumber)) ?? 0) : Int.max)
        return n
    }
    static func tooOld(_ firmware: String) -> Bool { version(firmware).lexicographicallyPrecedes(version(minFirmware)) }
}

/// The settings this app keeps on the phone, by name.
enum Prefs {
    static let controllers = "controllers.v1"
    static let scenes = "scenes.v1"
    static let myName = "myName"
    static let devMode = "devMode"
    /// The person tapped Not Now on the first-launch name sheet: do not ask again (Settings still has Display Name).
    static let nameSkipped = "nameSkipped"
    static let appearance = "appearance"
    /// Developer builds only: follow the beta firmware channel, and where to look for firmware.
    static let firmwareBeta = "fwBeta"
    static let firmwareSource = "fwSource"
    /// When a controller last answered, by its id.
    static func lastSeen(_ id: String) -> String { "seen.\(id)" }
}

/// Developer Mode exists only in builds made from Xcode, never in an App Store build.
let developerBuild: Bool = {
    #if DEBUG
    return true
    #else
    return false
    #endif
}()
