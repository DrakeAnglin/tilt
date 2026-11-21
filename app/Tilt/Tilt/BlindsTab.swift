// Home: one card per room (controller). Tap a room to see and move its blinds.
import SwiftUI

struct BlindsTab: View {
    @Environment(AppModel.self) private var model
    @State private var adding = false
    @State private var path = NavigationPath()

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(Date.now.formatted(.dateTime.weekday(.wide).month().day()).uppercased()).font(.caption.weight(.semibold)).foregroundStyle(.secondary).kerning(0.6)
                        Text(Greeting.text()).font(.system(size: 34, weight: .bold, design: .rounded))
                    }
                    .padding(.top, 6)
                    if model.controllers.isEmpty {
                        VStack(spacing: 16) {
                            SlatView(tilt: 30).frame(width: 150, height: 170)
                            Text("Bring your blinds to life").font(.title2.weight(.semibold))
                            Text("Add your first controller to open, close and schedule your blinds from here.").font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                            Button { adding = true } label: { Label("Add a Controller", systemImage: "plus").padding(.horizontal, 8) }.buttonStyle(.glassProminent).controlSize(.large)
                        }
                        .frame(maxWidth: .infinity).padding(28).card()
                    }
                    ForEach(model.controllers) { c in
                        RoomCard(controller: c)
                    }
                }
                .padding(.horizontal, 18).padding(.bottom, 30)
            }
            .background(AppBackground())
            .onChange(of: model.controllers.count) { was, now in if now < was { path = NavigationPath() } }     // a room was removed: back to the rooms
            .navigationDestination(for: String.self) { id in
                if let c = model.controllers.first(where: { $0.id == id }) { RoomView(controller: c) }
            }
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Add", systemImage: "plus") { adding = true } } }
            .sheet(isPresented: $adding) { AddControllerSheet() }
        }
    }
}

/// A room on the home page.
struct RoomCard: View {
    let controller: Controller
    var body: some View {
        let s = controller.state
        let shown = (s?.b ?? []).filter { $0.hid == 0 && !($0.seen == 1 && $0.pres == 0) }
        VStack(alignment: .leading, spacing: 14) {
          NavigationLink(value: controller.id) {
           VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 10) {
                ForEach(Array(shown.prefix(3).enumerated()), id: \.offset) { k, b in
                    SlatView(tilt: b.tilt ?? 0, known: b.tilt != nil, slats: 7, pane: k, panes: min(shown.count, 3)).frame(height: 118)
                        .animation(.easeInOut(duration: 0.4), value: b.tilt)
                }
                if shown.isEmpty { SlatView(tilt: 0, known: false, slats: 7).frame(height: 118) }
            }
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 3) {
                    Text(s?.name ?? controller.record.name).font(.title3.weight(.semibold))
                    Text(controller.online ? (s.map(TiltWords.room) ?? "Connecting…") : "Not reachable").font(.subheadline).foregroundStyle(controller.online ? .secondary : Color.orange)
                }
                Spacer()
                if let s { BatteryPill(battery: s.batt) }
                Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(.tertiary)
            }
           }
           .contentShape(Rectangle())
          }
          .buttonStyle(.plain)
            if let s, s.b.contains(where: \.ready) {
                HStack(spacing: 10) {
                    QuickButton(title: "Open", systemImage: "sun.max.fill") { controller.goAll(to: "open") }
                    QuickButton(title: "Close", systemImage: "moon.fill") { controller.goAll(to: "close") }
                    if s.mv >= 0 { QuickButton(title: "Stop", systemImage: "stop.fill", tint: .red) { controller.stopAll() } }
                }
            }
        }
        .padding(16)
        .card()
        .opacity(controller.online || controller.state == nil ? 1 : 0.75)
    }
}

struct QuickButton: View {
    let title: String, systemImage: String
    var tint: Color? = nil
    let action: () -> Void
    @State private var taps = 0
    var body: some View {
        Button { taps += 1; action() } label: { Label(title, systemImage: systemImage).font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity).padding(.vertical, 4) }
            .buttonStyle(.glass).tint(tint)
            .sensoryFeedback(.impact(weight: .light), trigger: taps)
    }
}

struct BatteryPill: View {
    let battery: ControllerState.Battery
    var body: some View {
        let charging = battery.st != "battery"
        HStack(spacing: 5) {
            Image(systemName: charging ? "bolt.fill" : battery.pct < 20 ? "battery.25percent" : "battery.75percent").font(.caption2)
            Text("\(battery.pct)%").font(.caption.weight(.semibold)).monospacedDigit()
        }
        .foregroundStyle(battery.low == 1 || (!charging && battery.pct < 20) ? Color.red : charging ? Color.green : Color.secondary)
        .padding(.horizontal, 9).padding(.vertical, 5)
        .background(.thinMaterial, in: Capsule())
        .accessibilityLabel("Battery \(battery.pct) percent\(charging ? ", charging" : "")")
    }
}

/// One room: its blinds, and the gear for this controller's settings.
struct RoomView: View {
    let controller: Controller
    @State private var open: Int?
    private let columns = [GridItem(.adaptive(minimum: 158), spacing: 14)]

    var body: some View {
        let s = controller.state
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(s?.name ?? controller.record.name).font(.system(size: 30, weight: .bold, design: .rounded))
                        Text(controller.online ? (s.map(TiltWords.room) ?? "Connecting…") : "Not reachable. Is this phone on your home Wi-Fi?").font(.subheadline).foregroundStyle(.secondary)
                    }
                    Spacer()
                    if let s { BatteryPill(battery: s.batt) }
                }
                if let s {
                    let all = Array(s.b.enumerated()).filter { $0.element.hid == 0 }
                    let shown = all.filter { !($0.element.seen == 1 && $0.element.pres == 0) }
                    let empty = all.count - shown.count
                    if shown.contains(where: { $0.element.ready }) {
                        HStack(spacing: 10) {
                            QuickButton(title: "Open All", systemImage: "sun.max.fill") { controller.goAll(to: "open") }
                            QuickButton(title: "Close All", systemImage: "moon.fill") { controller.goAll(to: "close") }
                            if s.mv >= 0 { QuickButton(title: "Stop", systemImage: "stop.fill", tint: .red) { controller.stopAll() } }
                        }
                    }
                    LazyVGrid(columns: columns, spacing: 14) {
                        ForEach(Array(shown.enumerated()), id: \.element.offset) { k, e in BlindCard(blind: e.element, pane: k, panes: shown.count) { open = e.offset } }
                    }
                    if empty > 0 {
                        Label("\(empty) empty port\(empty == 1 ? "" : "s"). Plug in a blind and it shows up here.", systemImage: "cable.connector")
                            .font(.footnote).foregroundStyle(.secondary).frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 4)
                    }
                } else {
                    SlatLoader(size: 52, label: "Connecting…").frame(maxWidth: .infinity).padding(40)
                }
                if let e = controller.lastError {
                    Label(e, systemImage: "exclamationmark.triangle.fill").font(.footnote).foregroundStyle(.orange).padding(12).frame(maxWidth: .infinity, alignment: .leading).card(radius: 16)
                        .task(id: e) { try? await Task.sleep(for: .seconds(4)); controller.lastError = nil }
                }
            }
            .padding(.horizontal, 18).padding(.bottom, 30)
        }
        .background(AppBackground())
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                NavigationLink { ControllerSettingsView(controller: controller) } label: { Label("Room Settings", systemImage: "gearshape") }
            }
        }
        .sheet(item: Binding(get: { open.map(Idx.init) }, set: { open = $0?.id })) { i in
            BlindSheet(controller: controller, index: i.id).presentationDetents([.fraction(0.72), .large]).presentationDragIndicator(.visible).presentationBackground(.thinMaterial)
        }
    }
    struct Idx: Identifiable { let id: Int }
}

struct BlindCard: View {
    let blind: BlindState
    var pane = 0
    var panes = 1
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 10) {
                SlatView(tilt: blind.tilt ?? 0, known: blind.tilt != nil, pane: pane, panes: panes).frame(height: 150).animation(.easeInOut(duration: 0.4), value: blind.tilt)
                Text(blind.name).font(.headline).lineLimit(1)
                HStack(spacing: 5) {
                    if blind.moving { SlatLoader(size: 13) }
                    if blind.stuck { Image(systemName: "exclamationmark.triangle.fill").font(.footnote).foregroundStyle(.orange) }
                    Text(TiltWords.status(blind)).font(.subheadline).foregroundStyle(blind.stuck ? Color.orange : Color.secondary).lineLimit(1)
                }
            }
            .padding(12).frame(maxWidth: .infinity, alignment: .leading).card(radius: 24)
        }
        .buttonStyle(.plain)
    }
}

/// The bottom drawer for one blind. Drag on the picture, or use the slider and buttons.
struct BlindSheet: View {
    let controller: Controller
    let index: Int
    @State private var drag: Double?
    @State private var dragStart: Double?
    @State private var settingUp = false

    var body: some View {
        let blind = controller.state?.b[safe: index]
        let shownTilt = drag ?? blind?.tilt ?? 0
        // the same slice of the outside view as on the room's page
        let row = (controller.state?.b ?? []).enumerated().filter { $0.element.hid == 0 && !($0.element.seen == 1 && $0.element.pres == 0) }.map(\.offset)
        let pane = row.firstIndex(of: index) ?? 0
        VStack(spacing: 18) {
            VStack(spacing: 4) {
                Text(blind?.name ?? "Blind").font(.title2.weight(.bold))
                Text(drag.map { TiltWords.long($0) } ?? blind.map(TiltWords.status) ?? "").font(.subheadline).foregroundStyle(.secondary).contentTransition(.numericText()).animation(.default, value: drag)
            }
            .padding(.top, 22)
            SlatView(tilt: shownTilt, known: drag != nil || blind?.tilt != nil, slats: 11, pane: pane, panes: max(row.count, 1))
                .frame(width: 210, height: 250)
                .animation(drag == nil ? .easeInOut(duration: 0.35) : nil, value: shownTilt)
                .gesture(DragGesture(minimumDistance: 4)
                    .onChanged { g in
                        guard blind?.ready == true else { return }
                        if dragStart == nil { dragStart = blind?.tilt ?? 0 }
                        drag = max(-100, min(100, (dragStart ?? 0) - g.translation.height * 0.8)).rounded()
                    }
                    .onEnded { _ in commit(); dragStart = nil })
                .sensoryFeedback(.selection, trigger: drag.map { Int($0 / 10) })
            if let blind, blind.ready {
                if blind.stuck {
                    Label("The motor ran but the sensor saw no movement. Check that the blind's rod is turning.", systemImage: "exclamationmark.triangle.fill")
                        .font(.footnote).foregroundStyle(.orange).frame(maxWidth: .infinity, alignment: .leading)
                }
                HStack(spacing: 12) {
                    Image(systemName: "arrow.down.to.line").foregroundStyle(.secondary)
                    Slider(value: Binding(get: { shownTilt }, set: { drag = $0.rounded() }), in: -100...100, onEditingChanged: { if !$0 { commit() } }).accessibilityLabel("Tilt")
                    Image(systemName: "arrow.up.to.line").foregroundStyle(.secondary)
                }
                HStack(spacing: 10) {
                    PositionButton(title: "Close Down", systemImage: "chevron.down") { controller.go(blind: index, tilt: -100) }
                    PositionButton(title: "Open", systemImage: "sun.max.fill") { controller.go(blind: index, tilt: 0) }
                    PositionButton(title: "Close Up", systemImage: "chevron.up") { controller.go(blind: index, tilt: 100) }
                }
                HStack {
                    Button { controller.go(blind: index, to: "fav") } label: { Label("Favorite", systemImage: "star.fill") }.buttonStyle(.glass)
                    Spacer()
                    if blind.moving { Button(role: .destructive) { controller.stopAll() } label: { Label("Stop", systemImage: "stop.fill") }.buttonStyle(.glassProminent).tint(.red) }
                }
            } else if let blind {
                if blind.cal == 0 && !(blind.seen == 1 && blind.pres == 0) {
                    Text("This blind has not been set up yet. Setup takes a minute: you turn it by hand to three positions.")
                        .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    Button { settingUp = true } label: { Text("Set Up Now").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 6) }
                        .buttonStyle(.glassProminent).controlSize(.large)
                } else {
                    Text("Nothing is plugged into this port.").font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 20)
        .fullScreenCover(isPresented: $settingUp) { SetupWizard(controller: controller, index: index, name: blind?.name ?? "Blind") }
    }
    private func commit() {
        guard let d = drag else { return }
        controller.go(blind: index, tilt: Int(d))
        Task { try? await Task.sleep(for: .seconds(1.5)); drag = nil }
    }
}

struct PositionButton: View {
    let title: String, systemImage: String
    let action: () -> Void
    @State private var taps = 0
    var body: some View {
        Button { taps += 1; action() } label: {
            VStack(spacing: 6) { Image(systemName: systemImage).font(.title3).frame(height: 24); Text(title).font(.footnote.weight(.semibold)).lineLimit(1).minimumScaleFactor(0.8) }
                .frame(maxWidth: .infinity).padding(.vertical, 8)
        }
        .buttonStyle(.glass)
        .sensoryFeedback(.impact(weight: .medium), trigger: taps)
    }
}

extension Array {
    subscript(safe i: Int) -> Element? { indices.contains(i) ? self[i] : nil }
}
