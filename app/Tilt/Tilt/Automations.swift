// Schedules (run by the controllers, so they work with the phone away) and Scenes (kept on the controllers, run
// with one tap from any phone in the home).
import CoreLocation
import SwiftUI

// Schedule and BlindTarget live in Shared/SchedulePlan.swift.

// BlindScene and ScenePlan live in Shared/ScenePlan.swift.

/// The Scenes, kept on the controllers and shared by every phone with a key. The phone keeps a copy (for Siri,
/// Shortcuts, and controllers it cannot reach right now). One store for every page that shows them.
@MainActor @Observable
final class SceneStore {
    static let shared = SceneStore()
    var scenes: [BlindScene] = (UserDefaults.standard.data(forKey: Prefs.scenes)).flatMap { try? JSONDecoder().decode([BlindScene].self, from: $0) } ?? []
    private var read: [String: [SceneSlot]] = [:]       // per controller, as last read
    private var localOnly: Set<String> = []             // controllers whose firmware does not keep Scenes: their part stays on this phone
    private var lastLoad = Date.distantPast

    /// Keep the copy on this phone.
    func save() { UserDefaults.standard.set(try? JSONEncoder().encode(scenes), forKey: Prefs.scenes) }
    func run(_ scene: BlindScene, controllers: [Controller]) {
        for (t, tilt) in scene.tilts { controllers.first { $0.id == t.controller }?.go(blind: t.blind, tilt: tilt) }
    }

    /// Read the Scenes from the controllers. `soon`: skip it if they were read a moment ago.
    func load(_ controllers: [Controller], soon: Bool = false) async {
        if soon, Date().timeIntervalSince(lastLoad) < 15 { return }
        lastLoad = Date()
        var got: [String: [SceneSlot]] = [:], old: Set<String> = []
        await withTaskGroup(of: (String, [SceneSlot]?, Bool).self) { g in
            for c in controllers {
                let client = c.client, id = c.id
                g.addTask {
                    do { let l = try await client.scenes(); return (id, l, l == nil) } catch { return (id, nil, false) }
                }
            }
            for await (id, l, isOld) in g { if let l { got[id] = l } else if isOld { old.insert(id) } }
        }
        read = got; localOnly = old
        let known = Set(controllers.map(\.id))           // a controller taken off this phone takes its blinds out of the Scenes here
        scenes = ScenePlan.scenes(read: got, kept: scenes.map { var s = $0; s.tilts = s.tilts.filter { known.contains($0.key.controller) }; return s })
        save()
        // Scenes made before the controllers kept them: put them on the controllers now, so the other phones see them.
        for s in scenes where s.gid == 0 { try? await save(s, controllers: controllers) }
    }

    /// Save (or delete) a Scene on every controller it covers, and keep the copy here.
    func save(_ scene: BlindScene, delete: Bool = false, controllers: [Controller]) async throws {
        var s = scene
        s.tilts = s.tilts.filter { t in controllers.contains { $0.id == t.key.controller } }
        if s.gid == 0 { s.gid = UInt32.random(in: 1...UInt32.max) }
        s.ver = UInt32(Date().timeIntervalSince1970)
        let name = { (id: String) in controllers.first { $0.id == id }?.state?.name ?? "A controller" }
        let ports = Dictionary(uniqueKeysWithValues: controllers.compactMap { c in c.state.map { (c.id, $0.b.count) } })
        let writes: [SceneWrite]
        do { writes = try ScenePlan.writes(s, delete: delete, read: read, localOnly: localOnly, ports: ports) }
        catch .full(let c) { throw TiltError("\(name(c)) already has \(ScenePlan.perController) scenes.") }
        catch .notRead(let c) { throw TiltError("\(name(c)) did not answer. Try again when it is reachable.") }
        do {
            for w in writes {
                try await controllers.first { $0.id == w.controller }?.client.setScene(w.value)
                if let i = read[w.controller]?.firstIndex(where: { $0.gid == s.gid }) { read[w.controller]!.remove(at: i) }
                if w.value.mask != 0 { read[w.controller]!.append(w.value) }
            }
        } catch {
            await load(controllers)                         // some were written: show what the controllers have now
            throw error
        }
        if delete { scenes.removeAll { $0.id == s.id } }
        else if let i = scenes.firstIndex(where: { $0.id == s.id }) { scenes[i] = s } else { scenes.append(s) }
        save()
    }
}

/// The scenes as a row of tiles: tap to run, hold to edit or delete, and a tile to make a new one.
struct ScenesRow: View {
    @Environment(AppModel.self) private var model
    @Environment(\.scenePhase) private var phase
    @State private var editing: BlindScene?
    @State private var ran: UUID?
    @State private var problem: String?
    var body: some View {
        let store = SceneStore.shared
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 10) {
                ForEach(store.scenes) { sc in
                    Button { ran = sc.id; store.run(sc, controllers: model.controllers) } label: {
                        VStack(spacing: 8) { Image(systemName: sc.symbol).font(.title2); Text(sc.name).font(.footnote.weight(.semibold)).lineLimit(1) }
                            .frame(width: 104, height: 84)
                            .card(radius: 20)
                    }
                    .buttonStyle(.plain)
                    .contextMenu {
                        Button("Edit", systemImage: "pencil") { editing = sc }
                        Button("Delete", systemImage: "trash", role: .destructive) { change(sc, delete: true) }
                    }
                }
                Button { editing = BlindScene() } label: {
                    VStack(spacing: 8) { Image(systemName: "plus").font(.title2); Text("New Scene").font(.footnote.weight(.semibold)) }
                        .frame(width: 104, height: 84).foregroundStyle(.tint)
                        .background(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(.tint.opacity(0.4), style: StrokeStyle(lineWidth: 1.5, dash: [5])))
                }
                .buttonStyle(.plain)
                .disabled(model.controllers.isEmpty)
            }
            .padding(.vertical, 2)
        }
        .sensoryFeedback(.impact, trigger: ran)
        .task(id: model.controllers.map(\.id)) { await store.load(model.controllers, soon: true) }
        .onChange(of: phase) { if phase == .active { Task { await store.load(model.controllers, soon: true) } } }   // another phone may have changed them
        .sheet(item: $editing) { sc in
            SceneEditor(scene: sc) { new in change(new) }
        }
        .alert("Scene not saved", isPresented: Binding(get: { problem != nil }, set: { if !$0 { problem = nil } })) {
            Button("OK", role: .cancel) {}
        } message: { Text(problem ?? "") }
    }
    private func change(_ sc: BlindScene, delete: Bool = false) {
        Task {
            do { try await SceneStore.shared.save(sc, delete: delete, controllers: model.controllers) }
            catch { problem = error.localizedDescription }
        }
    }
}

@MainActor @Observable
final class AutomationStore {
    var schedules: [Schedule] = []
    var sun: (rise: Date, set: Date)?
    var hasPlace = false
    var loading = false
    private var slots: [String: [SchedSlot]] = [:]          // per controller, as last read
    private var limits: [String: ControllerLimits] = [:]    // per controller, as it reported them

    private func limits(_ id: String) -> ControllerLimits { limits[id] ?? .fallback }
    /// Every Port of these controllers (a new Schedule starts with all of them).
    func everyBlind(_ controllers: [Controller]) -> Set<BlindTarget> { Schedule.everyPort(controllers.map { ($0.id, limits($0.id).ports) }) }

    func load(_ controllers: [Controller]) async {
        loading = true; defer { loading = false }
        slots = [:]
        for c in controllers {
            guard let cfg = try? await c.client.schedules() else { continue }
            slots[c.id] = cfg.sched
            limits[c.id] = cfg.limits
            if let s = cfg.sun, s.count == 2, s[0] > 0 { sun = (Date(timeIntervalSince1970: s[0]), Date(timeIntervalSince1970: s[1])); hasPlace = true; Sky.remember(rise: sun!.rise, set: sun!.set) }
        }
        schedules = SchedulePlan.schedules(controllers.compactMap { c in slots[c.id].map { (c.id, $0) } })
    }

    /// Write a Schedule to every controller it covers, and clear it from the ones it no longer covers.
    func save(_ s: Schedule, delete: Bool = false, controllers: [Controller]) async throws {
        let name = { (id: String) in controllers.first { $0.id == id }?.state?.name ?? "A controller" }
        let writes: [SlotWrite]
        do { writes = try SchedulePlan.writes(s, delete: delete, slots: slots, ports: limits.mapValues(\.ports)) }
        catch .full(let c) { throw TiltError("\(name(c)) already has \(limits(c).slots) schedules.") }
        catch .notRead(let c) { throw TiltError("\(name(c)) did not answer. Try again when it is reachable.") }
        for w in writes { try await controllers.first { $0.id == w.controller }?.client.setSchedule(slot: w.slot, w.value) }
        await load(controllers)
    }
}

struct AutomationsTab: View {
    @Environment(AppModel.self) private var model
    @State private var store = AutomationStore()
    @State private var editing: Schedule?
    @State private var problem: String?
    @State private var locator = Locator()
    @State private var ran: UInt32?
    /// Schedules are the owners' to change; anyone can run one.
    private var owner: Bool { model.controllers.contains { $0.record.owner } }

    var body: some View {
        NavigationStack {
            List {
            Group {
                Section("Scenes") {
                    ScenesRow().listRowInsets(EdgeInsets(top: 6, leading: 2, bottom: 6, trailing: 0)).listRowBackground(Color.clear)
                }
                Section {
                    ForEach(store.schedules) { s in
                        HStack(spacing: 12) {
                            Button { ran = s.id; runNow(s) } label: { Image(systemName: "play.fill").frame(width: 34, height: 34).background(.tint.opacity(0.15), in: Circle()) }
                                .buttonStyle(.borderless).accessibilityLabel("Run now")
                                .sensoryFeedback(.impact, trigger: ran)
                            Button { if owner { editing = s } } label: {
                                VStack(alignment: .leading, spacing: 3) {
                                    HStack(spacing: 6) {
                                        Text(s.whenText).font(.headline)
                                        if s.ramp > 0 { Image(systemName: s.kind == 2 ? "sunset" : "sunrise").font(.footnote).foregroundStyle(Palette.warning) }
                                    }
                                    Text("\(s.actionText) · \(s.daysText) · \(blindNames(s))").font(.footnote).foregroundStyle(.secondary).lineLimit(2)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle())      // the whole row opens it, not just the words
                            }
                            .buttonStyle(.plain)
                            Toggle("On", isOn: Binding(get: { s.on }, set: { on in var c = s; c.on = on; save(c) })).labelsHidden().disabled(!owner)
                        }
                    }
                    if owner { Button("New Schedule", systemImage: "plus") { editing = Schedule(targets: store.everyBlind(model.controllers)) } }
                } header: { Text("Schedules") } footer: {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Schedules are kept on the controllers, so they run even when this phone is away. The play button runs one right now.")
                        if let sun = store.sun { Text("Today: sunrise \(sun.rise.formatted(date: .omitted, time: .shortened)), sunset \(sun.set.formatted(date: .omitted, time: .shortened)).") }
                        if !owner { Text("Only an owner can add or change schedules.") }
                        if owner { Button(store.hasPlace ? "Update Location for Sunrise and Sunset" : "Set Location for Sunrise and Sunset") { setPlace() }.font(.footnote) }
                    }
                }
                if let problem { Section { Label(problem, systemImage: "exclamationmark.triangle").foregroundStyle(Palette.warning) } }
            }
            .listRowBackground(RowGlass())      // rows are glass over the sky, not solid white
        }
            .skyPage()
            .navigationTitle("Automations")
            .task { await store.load(model.controllers) }
            .refreshable { await store.load(model.controllers) }
            .sheet(item: $editing) { item in ScheduleEditor(schedule: item, isNew: !store.schedules.contains { $0.id == item.id }, everyBlind: store.everyBlind(model.controllers)) { s, del in save(s, delete: del) } }
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
    /// Do what the schedule does, right now.
    private func runNow(_ s: Schedule) {
        for t in s.targets {
            guard let c = model.controllers.first(where: { $0.id == t.controller }), c.state?.b[safe: t.blind]?.ready == true else { continue }
            c.go(blind: t.blind, tilt: s.tilt)
        }
    }
    private func save(_ s: Schedule, delete: Bool = false) {
        Task { do { try await store.save(s, delete: delete, controllers: model.controllers); problem = nil } catch { problem = error.localizedDescription } }
    }
    private func setPlace() {
        Task {
            problem = nil
            guard let place = await locator.once() else { problem = "Tilt could not get this phone's location. Allow location for Tilt in Settings."; return }
            for c in model.controllers { try? await c.client.setLocation(latitude: place.latitude, longitude: place.longitude) }
            await store.load(model.controllers)
        }
    }
}

struct ScheduleEditor: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State var schedule: Schedule
    let isNew: Bool
    /// Every Port of every controller: what "All blinds" saves.
    let everyBlind: Set<BlindTarget>
    let done: (Schedule, Bool) -> Void
    @State private var custom = false
    @State private var all = true

    var body: some View {
        NavigationStack {
            Form {
            Group {
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
                                .background(on ? Palette.accent : Palette.fill, in: Circle())
                                .foregroundStyle(on ? Palette.onAccent : Color.primary)
                                .onTapGesture { schedule.days ^= 1 << d }
                                .accessibilityAddTraits(on ? [.isButton, .isSelected] : .isButton)
                        }
                    }
                }
                Section("Do this") {
                    Picker("Tilt", selection: Binding(get: { custom ? 1 : schedule.tilt }, set: { if $0 == 1 { custom = true; schedule.tilt = 50 } else { custom = false; schedule.tilt = $0 } })) {
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
                Section {
                    Toggle("All Blinds", isOn: $all)
                } header: { Text("Blinds") } footer: { Text(all ? "Every blind moves together, including any you add later." : "Pick the blinds this schedule moves.") }
                if !all {
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
                }
                if !isNew { Section { Button("Delete Schedule", role: .destructive) { done(schedule, true); dismiss() } } }
            }
        }
            .navigationTitle(isNew ? "New Schedule" : "Schedule").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) { Button("Save") { var s = schedule; if all { s.targets = everyBlind }; done(s, false); dismiss() }.disabled(schedule.days == 0 || (!all && schedule.targets.isEmpty)) }
            }
            .onAppear {
                custom = ![0, 100, -100].contains(schedule.tilt)
                // "All" if it already covers every blind that is shown
                let shown = Set(model.controllers.flatMap { c in (c.state?.b ?? []).enumerated().filter { $0.element.listed }.map { BlindTarget(controller: c.id, blind: $0.offset) } })
                all = isNew || schedule.targets.isSuperset(of: shown)
            }
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
            Group {
                Section("Name") { TextField("Name", text: $scene.name) }
                Section("Icon") {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 10) {
                            ForEach(symbols, id: \.self) { s in
                                Image(systemName: s).font(.title3).frame(width: 46, height: 46)
                                    .background(scene.symbol == s ? Palette.fillSelected : Palette.fill, in: Circle())
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
        }
            .navigationTitle("Scene").navigationBarTitleDisplayMode(.inline)
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
