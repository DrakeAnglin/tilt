// How Tilt words a blind's position and judges a battery, in one place for the app, the widget and the notices.
import Foundation

enum TiltWords {
    /// Within this much of level, a blind counts as open; beyond the closed line, as closed (percent of the way).
    static let openBelow = 8.0, closedAbove = 92.0
    /// Blinds within this much of each other count as "the same position" for a room's one-line summary.
    static let sameWithin = 12.0

    static func long(_ t: Double?) -> String {
        guard let t else { return "" }
        let a = abs(t)
        if a < openBelow { return "Open" }
        if a > closedAbove { return t > 0 ? "Closed, slats up" : "Closed, slats down" }
        return "\(Int(a.rounded()))% toward \(t > 0 ? "up" : "down")"
    }
    /// What a schedule or button does: "Open", "Close up", "Close down", or a position.
    static func action(_ tilt: Int) -> String {
        tilt == 0 ? "Open" : tilt == 100 ? "Close up" : tilt == -100 ? "Close down" : long(Double(tilt))
    }
    static func status(_ b: BlindState) -> String {
        if b.seen == 1 && b.pres == 0 { return "Not connected" }
        if b.cal == 0 { return "Not set up yet" }
        if b.mov == 1 { return "Moving to \(long(b.tgt).lowercased())" }
        if b.q == 1 { return "Waiting its turn" }
        if b.stuck { return "Did not move" }
        return long(b.tilt)
    }
    /// One line for a whole room.
    static func room(_ s: ControllerState) -> String {
        let ready = s.b.filter(\.ready)
        if ready.isEmpty { return "Needs setup" }
        if s.mv >= 0 { return "Moving" }
        let tilts = ready.compactMap(\.tilt)
        guard let first = tilts.first else { return "\(ready.count) blind\(ready.count == 1 ? "" : "s")" }
        return tilts.allSatisfy({ abs($0 - first) < sameWithin }) ? long(first) : "Mixed positions"
    }
    /// A controller that is not answering: asleep (dozing on battery, expected) or not reachable, and when it was last seen.
    static func away(asleep: Bool, lastSeen: Date?, now: Date = .now) -> String {
        guard let t = lastSeen else { return asleep ? "Asleep" : "Not reachable" }
        let f = RelativeDateTimeFormatter(); f.unitsStyle = .short
        let ago = now.timeIntervalSince(t) < 60 ? "just now" : f.localizedString(for: t, relativeTo: now)
        return asleep ? "Asleep · seen \(ago)" : "Not reachable · last seen \(ago)"
    }
    /// The widget's shorter line: Open, Closed, or how far closed on average.
    static func short(_ s: ControllerState) -> String {
        let tilts = s.b.filter(\.ready).compactMap(\.tilt)
        if tilts.isEmpty { return "Needs setup" }
        if s.mv >= 0 { return "Moving" }
        let a = tilts.map { abs($0) }.reduce(0, +) / Double(tilts.count)
        return a < openBelow ? "Open" : a > closedAbove ? "Closed" : "\(Int(a.rounded()))% closed"
    }
}

extension ControllerState.Battery {
    /// Below this, on battery, Tilt warns that the battery is low.
    static let lowPercent = 20
    var charging: Bool { st != "battery" }
    /// The controller says it is too low to move the blinds.
    var tooLowToMove: Bool { low == 1 }
    /// Worth a warning: too low to move, or on battery and under lowPercent.
    var isLow: Bool { tooLowToMove || (!charging && pct < Self.lowPercent) }
}
