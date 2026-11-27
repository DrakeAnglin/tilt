// Schedules as the app shows them, and how they map onto the controllers' slots.
// A Schedule may cover blinds on several controllers: it then lives in one slot on each, tagged with the same id (gid).
// SchedulePlan turns slots into Schedules and a Schedule edit into slot writes. It is pure: no network, no UI.
import Foundation

struct BlindTarget: Hashable, Codable { var controller: String; var blind: Int }

/// When a light Schedule last ran on one controller, and why (SchedSlot.fwhy: 1 by light, 2 no steady reading,
/// 3 sun time, no solar panel seen).
struct LastRun: Equatable { var at: Date; var why: Int }

/// One Schedule as the app shows it.
struct Schedule: Identifiable, Equatable {
    var id: UInt32 = UInt32.random(in: 1...UInt32.max)
    var on = true
    var days = 127                  // bit 0 = Sunday
    var kind = 3                    // 0 clock time, 1 sunrise, 2 sunset, 3 when it gets light (a new one: ADR 0007), 4 when it gets dark
    var minute = 8 * 60
    var offset = 0                  // minutes after (+) or before (-) sunrise / sunset
    var tilt = 0
    var ramp = 0                    // gentle: minutes to take
    var targets: Set<BlindTarget> = []
    /// Light Schedules: when each controller last ran it (read from the controllers, never written).
    var lastRun: [String: LastRun] = [:]

    /// The Light trigger: read from the controller's solar panel, around sunrise (3) or sunset (4).
    static func isLight(_ kind: Int) -> Bool { kind == 3 || kind == 4 }
    static func onSunrise(_ kind: Int) -> Bool { kind == 1 || kind == 3 }
    var isLight: Bool { Self.isLight(kind) }

    var whenText: String {
        if kind == 0 { return Self.clock(minute) }
        let base = Self.onSunrise(kind) ? "Sunrise" : "Sunset"
        let off = "\(abs(offset)) min \(offset > 0 ? "after" : "before") \(base.lowercased())"
        if isLight {
            let name = kind == 3 ? "When it gets light" : "When it gets dark"
            return offset == 0 ? name : "\(name) (\(off))"
        }
        return offset == 0 ? base : off
    }
    var actionText: String { TiltWords.action(tilt) }
    var daysText: String {
        switch days { case 127: return "Every day"; case 62: return "Weekdays"; case 65: return "Weekends"; case 0: return "Never"
        default: return ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].enumerated().filter { days >> $0.offset & 1 == 1 }.map(\.element).joined(separator: " ") }
    }
    /// Every Port of these controllers: a Schedule for "all blinds" also covers a blind that is plugged in later.
    static func everyPort(_ controllers: [(id: String, ports: Int)]) -> Set<BlindTarget> {
        Set(controllers.flatMap { c in (0..<c.ports).map { BlindTarget(controller: c.id, blind: $0) } })
    }
    static func clock(_ m: Int) -> String {
        var c = DateComponents(); c.hour = m / 60; c.minute = m % 60
        return Calendar.current.date(from: c).map { $0.formatted(date: .omitted, time: .shortened) } ?? ""
    }
}

/// One slot write on one controller.
struct SlotWrite: Equatable { var controller: String; var slot: Int; var value: SchedSlot }

/// Why a Schedule edit cannot be written. Nothing is written when there is a problem.
enum PlanProblem: Error, Equatable {
    case full(controller: String)          // every slot on it is taken
    case notRead(controller: String)       // its slots are not known (it did not answer)
    case noLight(controller: String)       // a light Schedule on firmware that does not know it (it would run at sunset)
    case noPlace(controller: String)       // a sun or light Schedule on a controller with no location (it would never run)
}

enum SchedulePlan {
    /// ADR 0007: clock, sunrise and sunset automations are made in the home app (Apple Home, Alexa); Tilt makes only
    /// Light Schedules. An old clock or sun Schedule still shows, runs, and can be turned off or deleted.
    static func isOld(_ kind: Int) -> Bool { !Schedule.isLight(kind) }
    /// The kinds the Starts picker offers: the light kinds when `light` (offersLight), and an old Schedule's own kind,
    /// so editing it does not change what it is. Empty: there is nothing to pick (the screen says why).
    static func kindsOffered(current: Int, isNew: Bool, light: Bool) -> [Int] {
        (!isNew && isOld(current) ? [current] : []) + (light ? [3, 4] : [])
    }
    /// The controllers this Schedule covers that have no location, when it needs one (every kind but a clock time):
    /// sunrise and sunset, and so the Light trigger's window, are worked out from it. Sorted.
    static func missingPlace(_ s: Schedule, noPlace: Set<String>) -> [String] {
        guard s.kind != 0 else { return [] }
        return Set(s.targets.map(\.controller)).intersection(noPlace).sorted()
    }
    /// Offer "When it gets light / dark" for a Schedule: every controller it covers knows the Light trigger and one of
    /// them has seen a solar panel, or it already is one, so it can be changed back. `panels`: what each controller
    /// reported as "panel" (SchedConfig.panel); one missing from it runs older firmware, which would turn the kind into
    /// sunset (`writes` refuses that too).
    static func offersLight(kind: Int, targets: Set<BlindTarget>, panels: [String: Int]) -> Bool {
        if Schedule.isLight(kind) { return true }
        return !targets.isEmpty && targets.allSatisfy { panels[$0.controller] != nil } && targets.contains { panels[$0.controller] == 1 }
    }
    /// The id for a slot written before Schedules had ids (gid 0). The same on every launch.
    static func legacyId(controller: String, slot: Int) -> UInt32 {
        var h: UInt32 = 2166136261                       // FNV-1a, 32 bits
        for b in "\(controller)#\(slot)".utf8 { h = (h ^ UInt32(b)) &* 16777619 }
        return h == 0 ? 1 : h
    }
    static func id(of slot: SchedSlot, controller: String, index: Int) -> UInt32 {
        slot.gid != 0 ? slot.gid : legacyId(controller: controller, slot: index)
    }

    /// Controllers' slots, in the order given, as Schedules (sorted by when they run).
    static func schedules(_ controllers: [(id: String, slots: [SchedSlot])]) -> [Schedule] {
        var found: [UInt32: Schedule] = [:]
        for (c, slots) in controllers {
            for (i, sl) in slots.enumerated() where sl.mask != 0 {
                let id = id(of: sl, controller: c, index: i)
                var s = found[id] ?? Schedule(id: id, on: sl.on == 1, days: sl.days, kind: sl.kind, minute: sl.min, offset: sl.off, tilt: sl.tilt, ramp: sl.ramp)
                var m = sl.mask                          // bit n = Port n (the controller keeps only its own Ports' bits)
                while m != 0 { s.targets.insert(BlindTarget(controller: c, blind: m.trailingZeroBitCount)); m &= m - 1 }
                if let at = sl.fat, at > 0 { s.lastRun[c] = LastRun(at: Date(timeIntervalSince1970: TimeInterval(at)), why: sl.fwhy ?? 0) }
                found[id] = s
            }
        }
        return found.values.sorted { ($0.kind, $0.minute, $0.id) < ($1.kind, $1.minute, $1.id) }
    }

    /// The slot writes that save (or delete) a Schedule: one slot on each controller it covers, the slot that
    /// already holds it if there is one, and clears for any other slot holding it. `ports`: each controller's number of
    /// Ports (ControllerLimits); a controller not in it has the fallback. `panels`: what each controller reported as
    /// "panel"; a light Schedule is never written to one missing from it (older firmware would run it at sunset).
    /// `noPlace`: controllers with no location; a Schedule that is on and needs one (missingPlace) is never written.
    static func writes(_ s: Schedule, delete: Bool = false, slots: [String: [SchedSlot]], ports: [String: Int] = [:],
                       panels: [String: Int] = [:], noPlace: Set<String> = []) throws(PlanProblem) -> [SlotWrite] {
        for t in s.targets where !delete && slots[t.controller] == nil { throw .notRead(controller: t.controller) }
        if !delete && s.on, let c = missingPlace(s, noPlace: noPlace).first { throw .noPlace(controller: c) }
        if s.isLight && !delete {
            for t in s.targets.sorted(by: { ($0.controller, $0.blind) < ($1.controller, $1.blind) })
            where t.blind < (ports[t.controller] ?? ControllerLimits.fallback.ports) && panels[t.controller] == nil {
                throw .noLight(controller: t.controller)
            }
        }
        var out: [SlotWrite] = []
        for c in slots.keys.sorted() {
            let mine = slots[c]!
            var mask = 0
            let n = ports[c] ?? ControllerLimits.fallback.ports
            if !delete { for t in s.targets where t.controller == c && t.blind < n { mask |= 1 << t.blind } }
            let holding = mine.indices.filter { mine[$0].mask != 0 && id(of: mine[$0], controller: c, index: $0) == s.id }
            var clears = holding
            if mask != 0 {
                guard let i = holding.first ?? mine.firstIndex(where: { $0.mask == 0 }) else { throw .full(controller: c) }
                clears.removeAll { $0 == i }
                out.append(SlotWrite(controller: c, slot: i, value: SchedSlot(on: s.on ? 1 : 0, days: s.days, mask: mask, min: s.minute, tilt: s.tilt,
                                                                           kind: s.kind, off: s.offset, ramp: s.ramp, gid: s.id)))
            }
            for i in clears { out.append(SlotWrite(controller: c, slot: i, value: SchedSlot.empty)) }
        }
        return out
    }
}

extension SchedSlot {
    /// An unused slot, as the controller keeps one.
    static let empty = SchedSlot(on: 0, days: 127, mask: 0, min: 8 * 60, tilt: 0, kind: 0, off: 0, ramp: 0, gid: 0)
}
