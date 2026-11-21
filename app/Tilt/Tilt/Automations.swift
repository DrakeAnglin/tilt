// Schedules (run by the controllers, so they work with the phone away) and scenes (one tap from the phone).
import CoreLocation
import SwiftUI

struct BlindTarget: Hashable, Codable { var controller: String; var blind: Int }

struct SchedSlot: Decodable { var on: Int, days: Int, mask: Int, min: Int, tilt: Int, kind: Int, off: Int, ramp: Int; var gid: UInt32 }
struct SchedConfig: Decodable { var sched: [SchedSlot]; var lat: Double?; var lon: Double?; var sun: [Double]? }

/// One schedule as the app shows it. It may live on several controllers (one slot on each, tagged with `id`).
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
    var actionText: String { tilt == 0 ? "Open" : tilt == 100 ? "Close up" : tilt == -100 ? "Close down" : TiltWords.long(Double(tilt)) }
    var daysText: String {
        switch days { case 127: return "Every day"; case 62: return "Weekdays"; case 65: return "Weekends"; case 0: return "Never"
        default: return ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].enumerated().filter { days >> $0.offset & 1 == 1 }.map(\.element).joined(separator: " ") }
    }
    static func clock(_ m: Int) -> String {
        var c = DateComponents(); c.hour = m / 60; c.minute = m % 60
        return Calendar.current.date(from: c).map { $0.formatted(date: .omitted, time: .shortened) } ?? ""
    }
}

struct BlindScene: Identifiable, Codable, Equatable {
    var id = UUID()
    var name = "New Scene"
    var symbol = "sun.max"
    var tilts: [BlindTarget: Int] = [:]
}

@MainActor @Observable
final class AutomationStore {
    var schedules: [Schedule] = []
    var scenes: [BlindScene] = []
    var sun: (rise: Date, set: Date)?
    var hasPlace = false
    var loading = false
    private var slots: [String: [SchedSlot]] = [:]          // per controller, as last read

    init() { scenes = (UserDefaults.standard.data(forKey: "scenes.v1")).flatMap { try? JSONDecoder().decode([BlindScene].self, from: $0) } ?? [] }
    func saveScenes() { UserDefaults.standard.set(try? JSONEncoder().encode(scenes), forKey: "scenes.v1") }

    func load(_ controllers: [Controller]) async {
        loading = true; defer { loading = false }
        var found: [UInt32: Schedule] = [:]
        for c in controllers {
            guard let cfg: SchedConfig = try? await c.link.json("/api/cfg") else { continue }
            slots[c.id] = cfg.sched
            if let s = cfg.sun, s.count == 2, s[0] > 0 { sun = (Date(timeIntervalSince1970: s[0]), Date(timeIntervalSince1970: s[1])); hasPlace = true; Sky.remember(rise: sun!.rise, set: sun!.set) }
            for (i, sl) in cfg.sched.enumerated() where sl.mask != 0 {
                let gid = sl.gid != 0 ? sl.gid : UInt32(truncatingIfNeeded: c.id.hashValue &+ i &+ 1)
                var sc = found[gid] ?? Schedule(id: gid, on: sl.on == 1, days: sl.days, kind: sl.kind, minute: sl.min, offset: sl.off, tilt: sl.tilt, ramp: sl.ramp)
                for b in 0..<3 where sl.mask >> b & 1 == 1 { sc.targets.insert(BlindTarget(controller: c.id, blind: b)) }
                found[gid] = sc
            }
        }
        schedules = found.values.sorted { ($0.kind, $0.minute, $0.id) < ($1.kind, $1.minute, $1.id) }
    }

    /// Write a schedule to every controller it covers, and clear it from the ones it no longer covers.
    func save(_ s: Schedule, delete: Bool = false, controllers: [Controller]) async throws {
        for c in controllers {
            let mine = slots[c.id] ?? []
            var mask = 0
            if !delete { for t in s.targets where t.controller == c.id { mask |= 1 << t.blind } }
            let existing = mine.firstIndex { $0.gid == s.id && $0.mask != 0 }
            guard let i = existing ?? (mask != 0 ? mine.firstIndex { $0.mask == 0 } : nil) else {
                if mask != 0 { throw TiltError("\(c.state?.name ?? "A controller") already has 8 schedules.") }
                continue
            }
            try await c.link.send("/api/sched?i=\(i)&on=\(s.on && mask != 0 ? 1 : 0)&days=\(s.days)&mask=\(mask)&min=\(s.minute)&tilt=\(s.tilt)&kind=\(s.kind)&off=\(s.offset)&ramp=\(s.ramp)&gid=\(mask != 0 ? s.id : 0)")
        }
        await load(controllers)
    }

    func run(_ scene: BlindScene, controllers: [Controller]) {
        for (t, tilt) in scene.tilts { controllers.first { $0.id == t.controller }?.run("/api/go?b=\(t.blind)&t=\(tilt)&solo=1") }
    }
}

struct AutomationsTab: View {
    @Environment(AppModel.self) private var model
    @State private var store = AutomationStore()
    @State private var editing: Schedule?
    @State private var editingScene: BlindScene?
    @State private var problem: String?
    @State private var locator = Locator()

    var body: some View {
        NavigationStack {
            List {
                Section("Scenes") {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 10) {
                            ForEach(store.scenes) { sc in
                                Button { store.run(sc, controllers: model.controllers) } label: {
                                    VStack(spacing: 8) { Image(systemName: sc.symbol).font(.title2); Text(sc.name).font(.footnote.weight(.semibold)).lineLimit(1) }
                                        .frame(width: 104, height: 84)
                                        .card(radius: 20)
                                }
                                .buttonStyle(.plain)
                                .contextMenu {
                                    Button("Edit", systemImage: "pencil") { editingScene = sc }
                                    Button("Delete", systemImage: "trash", role: .destructive) { store.scenes.removeAll { $0.id == sc.id }; store.saveScenes() }
                                }
                                .sensoryFeedback(.impact, trigger: sc.id)
                            }
                            Button { editingScene = BlindScene() } label: {
                                VStack(spacing: 8) { Image(systemName: "plus").font(.title2); Text("New").font(.footnote.weight(.semibold)) }
                                    .frame(width: 104, height: 84).foregroundStyle(.tint)
                                    .background(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(.tint.opacity(0.4), style: StrokeStyle(lineWidth: 1.5, dash: [5])))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .listRowInsets(EdgeInsets(top: 6, leading: 2, bottom: 6, trailing: 0))
                    .listRowBackground(Color.clear)
                }
                Section {
                    ForEach(store.schedules) { s in
                        HStack {
                            Button { editing = s } label: {
                                VStack(alignment: .leading, spacing: 3) {
                                    HStack(spacing: 6) {
                                        Text(s.whenText).font(.headline)
                                        if s.ramp > 0 { Image(systemName: "sunrise").font(.footnote).foregroundStyle(.orange) }
                                    }
                                    Text("\(s.actionText) · \(s.daysText) · \(blindNames(s))").font(.footnote).foregroundStyle(.secondary).lineLimit(2)
                                }
                            }
                            .buttonStyle(.plain)
                            Spacer()
                            Toggle("On", isOn: Binding(get: { s.on }, set: { on in var c = s; c.on = on; save(c) })).labelsHidden()
                        }
                    }
                    Button("New Schedule", systemImage: "plus") { editing = Schedule(targets: allTargets()) }.disabled(model.controllers.isEmpty)
                } header: { Text("Schedules") } footer: {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Schedules are kept on the controllers, so they run even when this phone is away.")
                        if let sun = store.sun { Text("Today: sunrise \(sun.rise.formatted(date: .omitted, time: .shortened)), sunset \(sun.set.formatted(date: .omitted, time: .shortened)).") }
                        Button(store.hasPlace ? "Update Location for Sunrise and Sunset" : "Set Location for Sunrise and Sunset") { setPlace() }.font(.footnote)
                    }
                }
                if let problem { Section { Label(problem, systemImage: "exclamationmark.triangle").foregroundStyle(.orange) } }
            }
            .skyPage()
            .navigationTitle("Automations")
            .task { await store.load(model.controllers) }
            .refreshable { await store.load(model.controllers) }
            .sheet(item: $editing) { item in ScheduleEditor(schedule: item, isNew: !store.schedules.contains { $0.id == item.id }) { s, del in save(s, delete: del) } }
            .sheet(item: $editingScene) { sc in
                SceneEditor(scene: sc) { new in
                    if let i = store.scenes.firstIndex(where: { $0.id == new.id }) { store.scenes[i] = new } else { store.scenes.append(new) }
                    store.saveScenes()
                }
            }
        }
    }

    private func allTargets() -> Set<BlindTarget> {
        var t = Set<BlindTarget>()
        for c in model.controllers { for (i, b) in (c.state?.b ?? []).enumerated() where b.ready { t.insert(BlindTarget(controller: c.id, blind: i)) } }
        return t
    }
    private func blindNames(_ s: Schedule) -> String {
        let all = allTargets()
        if !all.isEmpty && s.targets.isSuperset(of: all) { return "All blinds" }
        let names = s.targets.sorted { ($0.controller, $0.blind) < ($1.controller, $1.blind) }.compactMap { t in model.controllers.first { $0.id == t.controller }?.state?.b[safe: t.blind]?.name }
        return names.isEmpty ? "No blinds" : names.joined(separator: ", ")
    }
    private func save(_ s: Schedule, delete: Bool = false) {
        Task { do { try await store.save(s, delete: delete, controllers: model.controllers); problem = nil } catch { problem = error.localizedDescription } }
    }
    private func setPlace() {
        Task {
            problem = nil
            guard let place = await locator.once() else { problem = "Tilt could not get this phone's location. Allow location for Tilt in Settings."; return }
            for c in model.controllers { try? await c.link.send("/api/set?k=loc&v=" + String(format: "%.3f,%.3f", place.latitude, place.longitude).urlQuery) }
            await store.load(model.controllers)
        }
    }
}

struct ScheduleEditor: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State var schedule: Schedule
    let isNew: Bool
    let done: (Schedule, Bool) -> Void
    @State private var custom = false

    var body: some View {
        NavigationStack {
            Form {
                Section("When") {
                    Picker("Starts", selection: $schedule.kind) { Text("At a time").tag(0); Text("At sunrise").tag(1); Text("At sunset").tag(2) }
                    if schedule.kind == 0 {
                        DatePicker("Time", selection: Binding(get: { Calendar.current.date(bySettingHour: schedule.minute / 60, minute: schedule.minute % 60, second: 0, of: .now) ?? .now },
                                                              set: { let c = Calendar.current.dateComponents([.hour, .minute], from: $0); schedule.minute = (c.hour ?? 0) * 60 + (c.minute ?? 0) }), displayedComponents: .hourAndMinute)
                    } else {
                        Stepper(schedule.offset == 0 ? "Exactly then" : "\(abs(schedule.offset)) min \(schedule.offset > 0 ? "after" : "before")", value: $schedule.offset, in: -120...120, step: 5)
                    }
                    HStack(spacing: 6) {
                        ForEach(0..<7, id: \.self) { d in
                            let on = schedule.days >> d & 1 == 1
                            Text(["S", "M", "T", "W", "T", "F", "S"][d]).font(.subheadline.weight(.semibold))
                                .frame(maxWidth: .infinity, minHeight: 36)
                                .background(on ? Color.accentColor : Color(.tertiarySystemFill), in: Circle())
                                .foregroundStyle(on ? Color.white : Color.primary)
                                .onTapGesture { schedule.days ^= 1 << d }
                                .accessibilityAddTraits(on ? [.isButton, .isSelected] : .isButton)
                        }
                    }
                }
                Section("Do this") {
                    Picker("Position", selection: Binding(get: { custom ? 1 : schedule.tilt }, set: { if $0 == 1 { custom = true; schedule.tilt = 50 } else { custom = false; schedule.tilt = $0 } })) {
                        Text("Open").tag(0); Text("Close up").tag(100); Text("Close down").tag(-100); Text("Other").tag(1)
                    }
                    if custom {
                        HStack(spacing: 14) {
                            SlatView(tilt: Double(schedule.tilt)).frame(width: 56, height: 70)
                            VStack(alignment: .leading) {
                                Text(TiltWords.long(Double(schedule.tilt)))
                                Slider(value: Binding(get: { Double(schedule.tilt) }, set: { schedule.tilt = Int($0) }), in: -100...100, step: 5)
                            }
                        }
                    }
                    Picker("Gently, over", selection: $schedule.ramp) { Text("Off").tag(0); Text("5 min").tag(5); Text("10 min").tag(10); Text("20 min").tag(20); Text("30 min").tag(30) }
                }
                ForEach(model.controllers) { c in
                    Section(c.state?.name ?? c.record.name) {
                        ForEach(Array((c.state?.b ?? []).enumerated()), id: \.offset) { i, b in
                            if b.hid == 0 {
                                let t = BlindTarget(controller: c.id, blind: i)
                                Button { if schedule.targets.contains(t) { schedule.targets.remove(t) } else { schedule.targets.insert(t) } } label: {
                                    HStack { Text(b.name).foregroundStyle(.primary); Spacer(); if schedule.targets.contains(t) { Image(systemName: "checkmark").fontWeight(.semibold) } }
                                }
                            }
                        }
                    }
                }
                if !isNew { Section { Button("Delete Schedule", role: .destructive) { done(schedule, true); dismiss() } } }
            }
            .skyPage().navigationTitle(isNew ? "New Schedule" : "Schedule").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) { Button("Save") { done(schedule, false); dismiss() }.disabled(schedule.days == 0 || schedule.targets.isEmpty) }
            }
            .onAppear { custom = ![0, 100, -100].contains(schedule.tilt) }
        }
    }
}

struct SceneEditor: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State var scene: BlindScene
    let done: (BlindScene) -> Void
    private let symbols = ["sun.max", "moon", "sunrise", "sunset", "film", "bed.double", "eye.slash", "book", "tv", "sparkles"]

    var body: some View {
        NavigationStack {
            Form {
                Section("Name") { TextField("Name", text: $scene.name) }
                Section("Icon") {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 10) {
                            ForEach(symbols, id: \.self) { s in
                                Image(systemName: s).font(.title3).frame(width: 46, height: 46)
                                    .background(scene.symbol == s ? Color.accentColor.opacity(0.25) : Color(.tertiarySystemFill), in: Circle())
                                    .onTapGesture { scene.symbol = s }
                            }
                        }
                    }
                }
                ForEach(model.controllers) { c in
                    Section(c.state?.name ?? c.record.name) {
                        ForEach(Array((c.state?.b ?? []).enumerated()), id: \.offset) { i, b in
                            if b.hid == 0 {
                                let t = BlindTarget(controller: c.id, blind: i)
                                VStack(alignment: .leading, spacing: 8) {
                                    Toggle(b.name, isOn: Binding(get: { scene.tilts[t] != nil }, set: { scene.tilts[t] = $0 ? Int(b.tilt ?? 0) : nil }))
                                    if let v = scene.tilts[t] {
                                        HStack(spacing: 12) {
                                            SlatView(tilt: Double(v)).frame(width: 44, height: 56)
                                            VStack(alignment: .leading) {
                                                Text(TiltWords.long(Double(v))).font(.footnote).foregroundStyle(.secondary)
                                                Slider(value: Binding(get: { Double(v) }, set: { scene.tilts[t] = Int($0) }), in: -100...100, step: 5)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            .skyPage().navigationTitle("Scene").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) { Button("Save") { done(scene); dismiss() }.disabled(scene.tilts.isEmpty || scene.name.isEmpty) }
            }
        }
    }
}

/// This phone's location, once, for sunrise and sunset. Only sent to the user's own controllers.
@MainActor
final class Locator: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private var waiting: CheckedContinuation<CLLocationCoordinate2D?, Never>?
    override init() { super.init(); manager.delegate = self; manager.desiredAccuracy = kCLLocationAccuracyKilometer }
    private var asking: CheckedContinuation<Void, Never>?
    func once() async -> CLLocationCoordinate2D? {
        if waiting != nil { return nil }
        if manager.authorizationStatus == .notDetermined {              // wait for the answer to the pop-up before asking for a fix
            await withCheckedContinuation { c in asking = c; manager.requestWhenInUseAuthorization() }
        }
        guard manager.authorizationStatus == .authorizedWhenInUse || manager.authorizationStatus == .authorizedAlways else { return nil }
        return await withCheckedContinuation { c in waiting = c; manager.requestLocation() }
    }
    nonisolated func locationManagerDidChangeAuthorization(_ m: CLLocationManager) {
        Task { @MainActor in if manager.authorizationStatus != .notDetermined { asking?.resume(); asking = nil } }
    }
    nonisolated func locationManager(_ m: CLLocationManager, didUpdateLocations l: [CLLocation]) { Task { @MainActor in waiting?.resume(returning: l.last?.coordinate); waiting = nil } }
    nonisolated func locationManager(_ m: CLLocationManager, didFailWithError e: Error) { Task { @MainActor in waiting?.resume(returning: nil); waiting = nil } }
}
