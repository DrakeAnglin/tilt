// Teaching a blind its three marks, as rules without a screen: when the wand is holding still, what each mark's answer
// means, and how the first move to Open checks the motor's wiring. SetupWizard.swift only shows it.
import Foundation

struct BlindSetup: Equatable {
    enum Mark: String { case up, open, down }
    static let marks: [Mark] = [.up, .open, .down]
    /// The reading must not have moved for this long before a mark can be saved.
    static let holdStill: TimeInterval = 1.2
    /// A change of the angle smaller than this (degrees) is sensor noise, not a turn.
    static let noise = 0.6

    /// 0…2: which mark is being set; 3: all three are saved.
    private(set) var step = 0
    private var lastAngle: Double?
    private var movedAt = Date.distantPast

    var done: Bool { step >= Self.marks.count }
    var mark: Mark? { done ? nil : Self.marks[step] }

    /// A new sensor reading (degrees, 0…360; nil when the sensor gives none). 359.9 to 0.1 is a small turn, not a big one.
    mutating func reading(angle: Double?, at now: Date) {
        if let a = angle, let l = lastAngle {
            let d = abs(a - l).truncatingRemainder(dividingBy: 360)
            if min(d, 360 - d) > Self.noise { movedAt = now }
        }
        lastAngle = angle
    }
    /// Holding still: there is a reading, and it has not moved for a moment.
    func steady(at now: Date) -> Bool { lastAngle != nil && now.timeIntervalSince(movedAt) > Self.holdStill }

    mutating func back() { if step > 0 { step -= 1 } }
    mutating func restart() { step = 0 }

    enum Outcome: Equatable {
        /// Saved: on to this step (3: all done, check the wiring).
        case next(step: Int)
        /// The three marks do not make sense together: clear them and start again from step 1.
        case restart(reason: String)
        /// Not saved; stay on this step.
        case failed(reason: String)
    }
    /// The controller's answer to saving the current mark.
    mutating func marked(_ a: CommandAnswer) -> Outcome {
        if a.ok != 1 { return .failed(reason: (a.err ?? "That did not work.").capitalizedFirst) }
        if mark == .down, let p = a.prob {
            step = 0
            return .restart(reason: p.capitalizedFirst + ". Start again from step 1.")
        }
        step += 1
        return .next(step: step)
    }

    /// The first move after setup, to Open: wait for it to start and stop, then say whether it got there.
    struct WiringCheck: Equatable {
        /// How long to wait for the move to start before reading the result anyway.
        static let startWithin: TimeInterval = 4
        /// How long to wait in all.
        static let giveUpAfter: TimeInterval = 30
        private var seenMoving = false

        enum Poll: Equatable { case wait, reached, failed(reason: String) }
        /// One look at the blind, `elapsed` seconds after the move was sent (nil: no answer this time).
        mutating func poll(_ b: BlindState?, elapsed: TimeInterval) -> Poll {
            guard let b else { return .wait }
            if b.moving { seenMoving = true; return .wait }
            guard seenMoving || elapsed > Self.startWithin else { return .wait }
            return b.reachedTarget ? .reached : .failed(reason: "The blind did not reach Open (\(b.last)). Check it turns freely, then tap Open.")
        }
        /// What the wiring check found, from the controller's motor sign for the port (-1: wires the other way round).
        static func words(sign: Int?) -> String {
            (sign ?? 0) < 0 ? "Motor checked: its wires are the other way round. The controller has learned that, nothing to rewire."
                            : "Motor checked: it turns the right way."
        }
    }
}

extension BlindState {
    /// Plugged in (or not yet checked) and shown, but its marks are not set.
    var needsSetup: Bool { listed && cal == 0 }
    /// The last move ended at its target (the controller says "reached …" or "already …").
    var reachedTarget: Bool { last.localizedCaseInsensitiveContains("reached") || last.localizedCaseInsensitiveContains("already") }
}
