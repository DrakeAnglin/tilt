// Schedules as the app shows them, and how they map onto the controllers' slots.
// A Schedule may cover blinds on several controllers: it then lives in one slot on each, tagged with the same id (gid).
// SchedulePlan turns slots into Schedules and a Schedule edit into slot writes. It is pure: no network, no UI.
import Foundation

struct BlindTarget: Hashable, Codable { var controller: String; var blind: Int }

/// One Schedule as the app shows it.
struct Schedule: Identifiable, Equatable {
    var id: UInt32 = UInt32.random(in: 1...UInt32.max)
    var on = true
    var days = 127                  // bit 0 = Sunday
    var kind = 0                    // 0 clock time, 1 sunrise, 2 sunset
    var minute = 8 * 60
    var offset = 0                  // minutes after (+) or before (-) sunrise / sunset
    var tilt = 0
    var ramp = 0                    // gentle: minutes to take
    var targets: Set<BlindTarget> = []

    var whenText: String {
        if kind == 0 { return Self.clock(minute) }
        let base = kind == 1 ? "Sunrise" : "Sunset"
        return offset == 0 ? base : "\(abs(offset)) min \(offset > 0 ? "after" : "before") \(base.lowercased())"
    }
    var actionText: String { TiltWords.action(tilt) }
    var daysText: String {
        switch days { case 127: return "Every day"; case 62: return "Weekdays"; case 65: return "Weekends"; case 0: return "Never"
        default: return ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].enumerated().filter { days >> $0.offset & 1 == 1 }.map(\.element).joined(separator: " ") }
    }
    /// Every port of these controllers: a Schedule for "all blinds" also covers a blind that is plugged in later.
    static func everyPort(_ controllers: [String]) -> Set<BlindTarget> {
        Set(controllers.flatMap { c in (0..<SchedulePlan.ports).map { BlindTarget(controller: c, blind: $0) } })
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
}

enum SchedulePlan {
    static let ports = 3

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
                for b in 0..<ports where sl.mask >> b & 1 == 1 { s.targets.insert(BlindTarget(controller: c, blind: b)) }
                found[id] = s
            }
        }
        return found.values.sorted { ($0.kind, $0.minute, $0.id) < ($1.kind, $1.minute, $1.id) }
    }

    /// The slot writes that save (or delete) a Schedule: one slot on each controller it covers, the slot that
    /// already holds it if there is one, and clears for any other slot holding it.
    static func writes(_ s: Schedule, delete: Bool = false, slots: [String: [SchedSlot]]) throws(PlanProblem) -> [SlotWrite] {
        for t in s.targets where !delete && slots[t.controller] == nil { throw .notRead(controller: t.controller) }
        var out: [SlotWrite] = []
        for c in slots.keys.sorted() {
            let mine = slots[c]!
            var mask = 0
            if !delete { for t in s.targets where t.controller == c && t.blind < ports { mask |= 1 << t.blind } }
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
