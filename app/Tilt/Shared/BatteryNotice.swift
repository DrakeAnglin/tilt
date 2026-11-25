// The one battery rule for notices: when a reading is worth a "battery low" notice, what it says, and the once-a-day
// limit. Used for readings from the controller itself and for readings a Tilt Hub reports, so the two always agree.
// (Issue #70 moves hub alerts to iCloud push; it can reuse `decide` and the wording here.)
import Foundation

/// One battery reading, from wherever it came.
struct BatteryReading: Equatable {
    let pct: Int
    /// On the charging cable (charging or full). Never low then, unless it is too low to move.
    let charging: Bool
    /// Below the motor cut-off: no blind moves until it is charged.
    let tooLowToMove: Bool

    /// Worth a warning: too low to move, or on battery and under lowPercent.
    var isLow: Bool { tooLowToMove || (!charging && pct < ControllerState.Battery.lowPercent) }

    /// What a Tilt Hub reports for a controller: `pct` -1 when it has not heard one yet; `chg` 1 on the cable, 0 not,
    /// nil from a hub or controller too old to say (then taken as not charging, as before).
    static func fromHub(pct: Int, low: Int?, chg: Int?) -> BatteryReading? {
        pct < 0 ? nil : BatteryReading(pct: pct, charging: chg == 1, tooLowToMove: low == 1)
    }
}

extension ControllerState.Battery {
    var reading: BatteryReading { BatteryReading(pct: pct, charging: charging, tooLowToMove: tooLowToMove) }
}

enum BatteryNotice: Equatable {
    case low(pct: Int)
    case tooLowToMove

    /// At most one battery notice a day per controller.
    static let gap: TimeInterval = 86400

    /// The notice to send now, or nil: on the cable (it is being charged, so there is nothing to ask), not low, or one
    /// was sent less than a day ago.
    static func decide(_ r: BatteryReading, lastSent: Date?, now: Date) -> BatteryNotice? {
        guard !r.charging, r.isLow else { return nil }
        if let lastSent, now.timeIntervalSince(lastSent) <= gap { return nil }
        return r.tooLowToMove ? .tooLowToMove : .low(pct: r.pct)
    }

    func title(name: String) -> String { "\(name): battery low" }
    var body: String {
        switch self {
        case .tooLowToMove: "The battery is too low to move the blinds. Plug in the charging cable."
        case .low(let pct): "The battery is at \(pct)%. Plug in the charging cable soon."
        }
    }
}

/// Where notices go and when each kind was last sent: the phone's notifications and UserDefaults in the app, a fake in
/// the tests.
protocol Notifier {
    func lastSent(_ key: String) -> Date?
    func send(_ key: String, title: String, body: String, at: Date)
}

enum BatteryNotices {
    static func key(id: String) -> String { "lowbatt.\(id)" }
    /// Sends the battery notice for this controller if `decide` says so. Returns what was sent.
    @discardableResult
    static func check(id: String, name: String, reading: BatteryReading, via n: Notifier, now: Date = .now) -> BatteryNotice? {
        let k = key(id: id)
        guard let notice = BatteryNotice.decide(reading, lastSent: n.lastSent(k), now: now) else { return nil }
        n.send(k, title: notice.title(name: name), body: notice.body, at: now)
        return notice
    }
}
