// The rules the app applies to each answer from a controller: who is in, who is Owner, what to watch, when it is
// Unreachable, how soon to ask again. Pure: the poll loop in Controller.start (Tilt/Model.swift) asks, applies the
// effects and sleeps.
import Foundation

enum ControllerPoll {
    /// What one ask for the state came back with.
    enum Answer { case state(ControllerState), waiting, notPaired, failed }
    /// What the loop remembers between asks.
    struct Memory: Equatable { var misses = 0; var hubKeyTold = false }
    enum Effect: Equatable {
        case saveRecord                    // the saved record changed
        case clearJoin(cid: String)        // this phone's Join request was answered: take the iCloud note away
        case watch(topic: String)          // Owner: push when someone asks to join
        case unwatch(topic: String)        // Guest: no push
        case loadRequests                  // the count of open Join requests changed
        case admitHub                      // tell the controller which key is the Tilt Hub's
        case batteryNotice(name: String, reading: BatteryReading)   // not on a hub: the phone judges the battery itself
    }
    enum Next: Equatable { case after(Duration), denied, removed }   // ask again, or stop for good
    struct Outcome: Equatable {
        var record: ControllerRecord
        var memory: Memory
        var online: Bool?                  // nil: leave as it is
        var answered: Bool                 // the controller answered with its state (for Last seen)
        var effects: [Effect]
        var next: Next
    }

    static let fastGap = Duration.milliseconds(350), slowGap = Duration.milliseconds(1200)
    /// Extra wait while this phone's Join request is open.
    static let waitingGap = Duration.seconds(2)
    /// Unreachable from this many misses in a row.
    static let missesToUnreachable = 3

    /// `asked`: the count of Join requests the last loadRequests saw. `moving`: the last known state has a move under way
    /// (for `.state` the new state's own `mv` is used). `boost`: a setup screen is watching, ask often.
    static func reconcile(_ answer: Answer, record: ControllerRecord, memory: Memory,
                          asked: Int, moving: Bool, boost: Bool) -> Outcome {
        func gap(_ fast: Bool) -> Duration { fast || boost ? fastGap : slowGap }
        switch answer {
        case .state(let s):
            var r = record, m = memory, effects: [Effect] = [], changed = false
            m.misses = 0
            if r.waiting == true {                                  // an Owner let this phone in
                r.waiting = nil; r.code = nil; changed = true
                effects.append(.clearJoin(cid: r.cid))
            }
            if let t = s.topic, !t.isEmpty, t != r.topic { r.topic = t; changed = true }
            if let me = s.me, (me == 1) != r.owner { r.owner = me == 1; changed = true }
            if changed { effects.insert(.saveRecord, at: 0) }
            if let t = r.topic { effects.append(r.owner ? .watch(topic: t) : .unwatch(topic: t)) }   // Owners get a push when someone asks to join
            if r.owner, (s.asks ?? 0) != asked { effects.append(.loadRequests) }
            // Set up before the controller knew which key is the hub's: tell it (once per start of the app).
            if r.owner, r.onHub, s.hkey == 0, !m.hubKeyTold { m.hubKeyTold = true; effects.append(.admitHub) }
            if !r.onHub { effects.append(.batteryNotice(name: s.name, reading: s.batt.reading)) }   // on a hub: the hub's push alerts
            return Outcome(record: r, memory: m, online: true, answered: true, effects: effects, next: .after(gap(s.mv >= 0)))
        case .waiting:
            return Outcome(record: record, memory: memory, online: true, answered: false, effects: [],
                           next: .after(waitingGap + gap(moving)))
        case .notPaired:
            // The controller answered and no longer knows this phone: turned down while waiting, else an Owner removed it.
            return Outcome(record: record, memory: memory, online: nil, answered: false, effects: [],
                           next: record.waiting == true ? .denied : .removed)
        case .failed:
            var m = memory
            m.misses += 1
            return Outcome(record: record, memory: m, online: m.misses >= missesToUnreachable ? false : nil, answered: false,
                           effects: [], next: .after(gap(moving)))
        }
    }
}
