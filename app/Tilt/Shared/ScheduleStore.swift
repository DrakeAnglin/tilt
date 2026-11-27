// The Schedules screen's state: read every controller's slots, put them together as Schedules (SchedulePlan), and
// write an edit back. No UI here, so the tests run it against fake controllers.
import Foundation
import Observation

/// A controller as the Schedules screen needs it: who it is, its name for messages, and how to reach it.
@MainActor protocol ScheduleHolder {
    nonisolated var id: String { get }
    var scheduleName: String { get }
    var client: ControllerClient { get }
}

@MainActor @Observable
final class AutomationStore {
    var schedules: [Schedule] = []
    var sun: (rise: Date, set: Date)?
    /// At least one controller has a location (it sent today's sunrise).
    var hasPlace = false
    var loading = false
    /// Per controller: what it reported as "panel" (1 a solar panel seen, 0 none). A controller missing from it runs
    /// firmware without the Light trigger (or did not answer).
    var panels: [String: Int] = [:]
    /// Controllers that answered with no location: sun and light Schedules cannot run there (SchedulePlan.missingPlace).
    var noPlace: Set<String> = []
    private var slots: [String: [SchedSlot]] = [:]          // per controller, as last read
    private var limits: [String: ControllerLimits] = [:]    // per controller, as it reported them
    private var names: [String: String] = [:]               // per controller, for the lines under a Schedule
    /// Told today's sunrise and sunset whenever a controller sends them (the app's sky colors).
    private let remember: (Date, Date) -> Void

    init(remember: @escaping (Date, Date) -> Void = { SunMemory.remember(rise: $0, set: $1) }) { self.remember = remember }

    private func limits(_ id: String) -> ControllerLimits { limits[id] ?? .fallback }
    /// Every Port of these controllers (a new Schedule starts with all of them).
    func everyBlind(_ controllers: [some ScheduleHolder]) -> Set<BlindTarget> { Schedule.everyPort(controllers.map { ($0.id, limits($0.id).ports) }) }
    /// The Set Location button: "Update" only when every controller that answered has a location.
    var placeButton: String { hasPlace && noPlace.isEmpty ? "Update Location for Sunrise and Sunset" : "Set Location for Sunrise and Sunset" }

    func load(_ controllers: [some ScheduleHolder]) async {
        loading = true; defer { loading = false }
        slots = [:]; panels = [:]; noPlace = []; sun = nil; hasPlace = false   // a location taken away shows at once
        for c in controllers {
            names[c.id] = c.scheduleName
            guard let cfg = try? await c.client.schedules() else { continue }
            slots[c.id] = cfg.sched
            limits[c.id] = cfg.limits
            panels[c.id] = cfg.panel
            if cfg.placeMissing { noPlace.insert(c.id) }
            if let s = cfg.sun, s.count == 2, s[0] > 0 {
                let rise = Date(timeIntervalSince1970: s[0]), set = Date(timeIntervalSince1970: s[1])
                sun = (rise, set); hasPlace = true; remember(rise, set)
            }
        }
        schedules = SchedulePlan.schedules(controllers.compactMap { c in slots[c.id].map { (c.id, $0) } })
    }

    /// Write a Schedule to every controller it covers, and clear it from the ones it no longer covers. Nothing is
    /// written when SchedulePlan finds a problem; the error says which controller, in plain words.
    func save(_ s: Schedule, delete: Bool = false, controllers: [some ScheduleHolder]) async throws {
        let name = { (id: String) in controllers.first { $0.id == id }?.scheduleName ?? "A controller" }
        let writes: [SlotWrite]
        do { writes = try SchedulePlan.writes(s, delete: delete, slots: slots, ports: limits.mapValues(\.ports), panels: panels, noPlace: noPlace) }
        catch { throw TiltError(TiltWords.planProblem(error, name: name, slots: { self.limits($0).slots })) }
        for w in writes { try await controllers.first { $0.id == w.controller }?.client.setSchedule(slot: w.slot, w.value) }
        await load(controllers)
    }

    /// The lines under a Schedule: an old clock or sun one says where it belongs now (ADR 0007), and one that is on
    /// but covers a controller with no location says it will not run there.
    func notes(_ s: Schedule) -> [ScheduleNote] {
        var out: [ScheduleNote] = []
        if SchedulePlan.isOld(s.kind) { out.append(ScheduleNote(text: TiltWords.oldSchedule)) }
        let missing = SchedulePlan.missingPlace(s, noPlace: noPlace)
        if s.on && !missing.isEmpty { out.append(ScheduleNote(text: TiltWords.noPlace(missing.map { names[$0] ?? "a controller" }), warn: true)) }
        return out
    }
}

/// Today's sunrise and sunset, kept on the phone for the sky colors (Sky.sunTimes in Theme.swift reads these keys).
enum SunMemory {
    static let riseKey = "sun.rise", setKey = "sun.set"
    /// Stores them as minutes after midnight, in this phone's time zone.
    static func remember(rise: Date, set: Date, in d: UserDefaults = .standard, calendar: Calendar = .current) {
        func m(_ t: Date) -> Double { let c = calendar.dateComponents([.hour, .minute], from: t); return Double((c.hour ?? 0) * 60 + (c.minute ?? 0)) }
        d.set(m(rise), forKey: riseKey); d.set(m(set), forKey: setKey)
    }
}

/// A line under a Schedule in the list. `warn`: it will not run as it is.
struct ScheduleNote: Hashable { var text: String; var warn = false }

/// What the Schedule editor offers and allows, from the Schedule being edited. Pure: the editor only draws it.
struct ScheduleForm {
    var schedule: Schedule, isNew: Bool, all: Bool
    /// Every Port of every controller: what "All blinds" saves.
    var everyBlind: Set<BlindTarget>
    /// Per controller: what it reported as "panel" (AutomationStore.panels).
    var panels: [String: Int]

    /// The blinds a save would cover.
    var targets: Set<BlindTarget> { all ? everyBlind : schedule.targets }
    /// The light triggers are offered when a covered controller has seen a solar panel (SchedulePlan.offersLight).
    /// A new Schedule is judged by its blinds alone: it starts as a light one, which would always count.
    var offersLight: Bool { SchedulePlan.offersLight(kind: isNew ? 0 : schedule.kind, targets: targets, panels: panels) }
    /// ADR 0007: only the light kinds, plus an old Schedule's own kind (SchedulePlan.kindsOffered).
    var kinds: [Int] { SchedulePlan.kindsOffered(current: schedule.kind, isNew: isNew, light: offersLight) }
    /// Save: a kind that can be picked here, a day, and a blind.
    var canSave: Bool { kinds.contains(schedule.kind) && schedule.days != 0 && !targets.isEmpty }
    /// Under the When section.
    var footer: String? {
        if kinds.isEmpty { return TiltWords.noLightYet }      // first: a new Schedule starts as a light one
        if schedule.isLight { return TiltWords.lightTrigger(schedule.kind) }
        return isNew ? nil : TiltWords.oldSchedule + "."
    }
}
