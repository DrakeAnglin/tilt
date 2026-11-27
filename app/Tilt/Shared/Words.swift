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
    /// The Power source next to the Battery level: "Solar", "Plugged in", "Charging" (on input power, source not sure),
    /// or nil on battery. Never a named source the charging flag does not back up, or a value it does not know.
    static func powerSource(charging: Bool, src: Int?) -> String? {
        guard charging else { return nil }
        switch src {
        case 1: return "Solar"
        case 2: return "Plugged in"
        default: return "Charging"
        }
    }
    /// When a light Schedule last ran and why (SchedSlot.fwhy), `time` already formatted. nil: it has not run.
    static func lastRun(why: Int, kind: Int, time: String) -> String? {
        switch why {
        case 1: return "Last ran by light at \(time)"
        case 2: return "Last ran at \(time) (no steady reading)"
        case 3: return "Last ran at \(Schedule.onSunrise(kind) ? "sunrise" : "sunset") (no solar panel seen)"
        default: return nil
        }
    }
    /// What a light trigger does, under the Starts picker.
    static func lightTrigger(_ kind: Int) -> String {
        let (what, when) = kind == 3 ? ("light", "sunrise") : ("dark", "sunset")
        return "Runs when the controller's solar panel sees it get \(what), within 90 minutes of \(when), once a day. With no steady reading by then, it runs at the end of that time; with no solar panel, at \(when)."
    }
    /// What a schedule or button does: "Open", "Close up", "Close down", or a position.
    static func action(_ tilt: Int) -> String {
        tilt == 0 ? "Open" : tilt == 100 ? "Close up" : tilt == -100 ? "Close down" : long(Double(tilt))
    }
    /// What the chosen role can do, under the Guest/Owner picker on the join sheet.
    static func role(owner: Bool) -> String {
        owner
            ? "An owner can also change settings, run blind setup, make schedules, and approve or remove people."
            : "A guest can open and close the blinds and make or change scenes."
    }
    static func status(_ b: BlindState) -> String {
        if b.seen == 1 && b.pres == 0 { return "Not connected" }
        if b.cal == 0 { return "Setup required" }
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
        return tilts.allSatisfy({ abs($0 - first) < sameWithin }) ? long(first) : "Mixed tilts"
    }
    /// A controller that has not answered (Unreachable), and when it was last seen. (Asleep is never shown: it is normal.)
    static func away(lastSeen: Date?, now: Date = .now) -> String {
        guard let t = lastSeen else { return "Unreachable" }
        let f = RelativeDateTimeFormatter(); f.unitsStyle = .short
        let ago = now.timeIntervalSince(t) < 60 ? "just now" : f.localizedString(for: t, relativeTo: now)
        return "Unreachable · last seen \(ago)"
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

/// The words of Tilt's push alerts (the Tilt Hub sends what happened; the alerts extension turns it into these).
/// kind: what happened (the hub's names, firmware/tilt_hub/main/hub_alerts.h); room: the controller's name;
/// detail: the blind's name (stall), the battery percent, or why an update failed.
enum AlertWords {
    static func title(kind: String, room: String, detail: String) -> String {
        switch kind {
        case "stall": return detail.isEmpty ? "\(room): a blind got stuck" : "\(room): \(detail) got stuck"
        case "silent": return "\(room) is not responding"
        case "batt-low": return "\(room): battery low"
        case "batt-crit": return "\(room): battery almost empty"
        case "batt-dead": return "\(room): battery empty"
        case "update": return "\(room): update failed"
        case "hub-update": return "Tilt Hub: update failed"
        case "hub-offline": return "Tilt Hub is offline"
        case "test": return "\(room): test alert"
        default: return "\(room) needs a look"
        }
    }
    static func body(kind: String, room: String, detail: String) -> String {
        let pct = Int(detail).map { "The battery is at \($0)%. " } ?? ""
        switch kind {
        case "stall": return "It stopped before it got where it was going. Check that nothing is in its way, then try again."
        case "silent": return "Your Tilt Hub has not heard from it for a while. Check that its battery is charged and that it is within reach of the hub."
        case "batt-low": return pct + "Plug in the charging cable soon."
        case "batt-crit": return pct + "Plug in the charging cable: the blinds will stop moving soon."
        case "batt-dead": return "The battery is too low to move the blinds. Plug in the charging cable."
        case "update": return detail.isEmpty ? "The new firmware did not go on. It still runs the old one: try again from the Tilt Hub page." : "\(detail.capitalizedFirst). It still runs the old firmware: try again from the Tilt Hub page."
        case "hub-update": return "The new firmware \(detail) did not start, so the hub went back to the one it had. Everything still works."
        case "test": return "Push alerts from your Tilt Hub work."
        case "hub-offline": return "Your iPhone is on your home Wi-Fi but can't reach the hub. Check that it is plugged in."
        default: return "Open Tilt to see what happened."
        }
    }
}

extension ControllerState.Battery {
    /// Below this, on battery, Tilt warns that the battery is low; below criticalPercent, that it is almost empty.
    /// The hub's alerts use the same lines (alert_rules.h ALERT_LOW_PCT).
    static let lowPercent = 20, criticalPercent = 10
    var charging: Bool { st != "battery" }
    /// Below the motor cut-off: the controller won't move any blind until it is charged.
    var tooLowToMove: Bool { low == 1 }
    /// Worth a warning (the rule is BatteryReading.isLow, Shared/BatteryNotice.swift).
    var isLow: Bool { reading.isLow }
}
