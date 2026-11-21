// Home: one card per room (controller). Tap a room to see and move its blinds.
import SwiftUI

struct BlindsTab: View {
    @Environment(AppModel.self) private var model
    @State private var adding = false
    @State private var path: [String] = []
    @State private var width: CGFloat = 400
    /// Wide screens: the room that is open beside the rooms.
    @State private var opened: String?
    /// Wide screens, with a room open: the rooms column is tucked away.
    @State private var sideHidden = false
    /// The room that was open last, so a swipe on the home page can go back to it.
    @State private var lastOpened: String?

    var body: some View {
        let wide = width >= 600
        let room = wide ? model.controllers.first(where: { $0.id == opened }) : nil
        let split = room != nil                                  // rooms on the left, the open room on the right
        let side = min(340, width * 0.4)
        let cols = split ? 1 : Layout.count(width, phone: 1, medium: 2, large: 3)
        let cardW = max(120, ((split ? side : width) - 36 - 18 * CGFloat(cols - 1)) / CGFloat(cols))      // each room card, exactly
        // One page for every size. On a phone a room pushes its own page. On a wide screen the rooms stay put and
        // narrow into a column on the left while the room comes in from the right.
        NavigationStack(path: $path) {
            HStack(alignment: .top, spacing: 0) {
                if !(split && sideHidden) {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 18) {
                            HStack(alignment: .top) {
                                GreetingHeader()
                                Spacer(minLength: 0)
                                if split { Button("Hide Rooms", systemImage: "sidebar.left") { withAnimation(.smooth(duration: 0.3)) { sideHidden = true } }.labelStyle(.iconOnly).buttonStyle(.glass).padding(.top, 6) }
                            }
                            if model.controllers.isEmpty && model.waiting.isEmpty {
                                VStack(spacing: 16) {
                                    SlatView(tilt: 30).frame(width: 150, height: 170)
                                    Text("Bring your blinds to life").font(.title2.weight(.semibold))
                                    Text("Add your first blinds controller to open, close and schedule your blinds from here.").font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                                    Button { adding = true } label: { Label("Add a New Device", systemImage: "plus").padding(.horizontal, 8) }.buttonStyle(.glassProminent).controlSize(.large)
                                }
                                .frame(maxWidth: .infinity).padding(28).card()
                            }
                            // One room across on a phone or in the side column, two on a folded-open or small tablet screen, three on a big one.
                            CardFlow(columns: cols, spacing: 18) {
                                ForEach(model.controllers) { c in
                                    RoomCard(controller: c, compact: split, width: cardW, onOpen: wide ? { withAnimation(.smooth(duration: 0.35)) { opened = c.id; sideHidden = false } } : nil)
                                        .overlay { RoundedRectangle(cornerRadius: 26, style: .continuous).strokeBorder(.tint, lineWidth: 2).opacity(split && c.id == opened ? 1 : 0) }
                                }
                                ForEach(model.waiting) { c in WaitingCard(controller: c) }
                            }
                            // Scenes live under the rooms on the home page: scroll down to them.
                            if !split, !model.controllers.isEmpty {
                                VStack(alignment: .leading, spacing: 10) {
                                    Text("Scenes").font(.title3.weight(.semibold))
                                    ScrollView(.horizontal, showsIndicators: false) { ScenesRow().padding(.horizontal, 18) }.padding(.horizontal, -18)
                                }
                                .padding(.top, 8)
                                .transition(.opacity)
                            }
                        }
                        .padding(.horizontal, 18).padding(.bottom, 30)
                    }
                    // Every room at once, from the home page.
                    .safeAreaInset(edge: .bottom) {
                        if !split, model.controllers.contains(where: { $0.state?.b.contains(where: \.ready) == true }) {
                          VStack(spacing: 10) {
                            HomeMoveBar(controllers: model.controllers).controlSize(.large).frame(maxWidth: 520).padding(.horizontal, 18).padding(.bottom, wide ? 6 : 16)
                                // gone at once when a room opens: its own bar slides in over the same spot, and two sets of buttons would overlap
                          }
                                .transition(.asymmetric(insertion: .opacity, removal: .opacity.animation(.linear(duration: 0.06))))
                        }
                    }
                    .frame(width: split ? side : width)
                    .transition(.move(edge: .leading).combined(with: .opacity))
                }
                if let room {
                    RoomView(controller: room, embedded: true, fitWidth: width - (sideHidden ? 0 : side)).id(room.id)
                        .frame(maxWidth: .infinity)
                        .transition(.move(edge: .trailing).combined(with: .opacity))
                }
            }
            .background(AppBackground())
            .navigationDestination(for: String.self) { id in
                if let c = model.controllers.first(where: { $0.id == id }) { RoomView(controller: c) }
            }
            .toolbar {
                if split, sideHidden {
                    ToolbarItem(placement: .topBarLeading) { Button("Show Rooms", systemImage: "sidebar.left") { withAnimation(.smooth(duration: 0.3)) { sideHidden = false } } }
                }
                // Adding a device belongs to the home page (and Settings), not to a room that is open.
                if !split { ToolbarItem(placement: .topBarTrailing) { Button("Add a New Device", systemImage: "plus") { adding = true } } }
            }
            // Swipes on a wide screen with a room open. To the right brings back what is on the left: first the rooms
            // column, then the home page (a long swipe goes straight home). To the left gives the room the whole screen.
            .simultaneousGesture(DragGesture(minimumDistance: 30).onEnded { g in
                let dx = g.translation.width
                guard abs(dx) > 70, abs(dx) > abs(g.translation.height) * 1.6 else { return }
                if !split {                               // on the home page: a swipe to the left reopens the room you were last in
                    guard dx < 0, path.isEmpty, let last = lastOpened, model.controllers.contains(where: { $0.id == last }) else { return }
                    if wide { withAnimation(.smooth(duration: 0.35)) { opened = last; sideHidden = false } } else { path = [last] }
                    return
                }
                withAnimation(.smooth(duration: 0.35)) {
                    if dx < 0 { sideHidden = true }
                    else if sideHidden && dx < width * 0.5 { sideHidden = false }
                    else { opened = nil; sideHidden = false }
                }
            })
        }
        .onReceive(NotificationCenter.default.publisher(for: .tiltBlindsHome)) { _ in withAnimation(.smooth(duration: 0.35)) { opened = nil; sideHidden = false; path = [] } }
        .onGeometryChange(for: CGFloat.self) { $0.size.width } action: { width = $0 }
        .onChange(of: model.controllers.count) { was, now in if now < was { path = []; opened = nil } }     // a room was removed: back to the rooms
        // Folding or unfolding keeps you where you were: the home page stays the home page, an open room stays open.
        .onChange(of: width >= 600) { _, wide in
            // No animation of our own here: the system is already animating the change of screen, and a page sliding
            // off or on at the same moment looks like a glitch.
            var quiet = Transaction(); quiet.disablesAnimations = true
            withTransaction(quiet) {
                if wide { if let last = path.last { opened = last; sideHidden = false; path = [] } }
                else if let o = opened { opened = nil; path = [o] }
            }
        }
        .onChange(of: opened) { _, o in if let o { lastOpened = o } }
        .onChange(of: path) { _, p in if let l = p.last { lastOpened = l } }
        .sheet(isPresented: $adding) { AddControllerSheet() }
    }
}

/// The date and the greeting at the top of the rooms.
struct GreetingHeader: View {
    var compact = false
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(Date.now.formatted(.dateTime.weekday(.wide).month().day()).uppercased()).font(.caption.weight(.semibold)).foregroundStyle(.secondary).kerning(0.6)
            Text(Greeting.text()).font(.system(size: compact ? 26 : 34, weight: .bold, design: .rounded))
        }
        .padding(.top, 6)
    }
}

/// How many cards go side by side for the width at hand.
enum Layout {
    static func count(_ width: CGFloat, phone: Int, medium: Int, large: Int, from: CGFloat = 600, to: CGFloat = 1000) -> Int {
        width < from ? phone : width < to ? medium : large
    }
}

/// Cards in equal columns. Unlike a lazy grid, every card keeps its identity when the number of columns or the width
/// changes, so a change of layout slides the cards to their new places instead of popping them in and out.
struct CardFlow: SwiftUI.Layout {
    var columns: Int
    var spacing: CGFloat
    private func cell(_ width: CGFloat) -> CGFloat { max(0, (width - spacing * CGFloat(columns - 1)) / CGFloat(max(columns, 1))) }
    private func rows(_ subviews: Subviews, _ w: CGFloat) -> [CGFloat] {
        stride(from: 0, to: subviews.count, by: max(columns, 1)).map { i in
            subviews[i..<min(i + columns, subviews.count)].map { $0.sizeThatFits(ProposedViewSize(width: w, height: nil)).height }.max() ?? 0
        }
    }
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? 0, h = rows(subviews, cell(width))
        return CGSize(width: width, height: h.reduce(0, +) + spacing * CGFloat(max(h.count - 1, 0)))
    }
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let w = cell(bounds.width), h = rows(subviews, w)
        var y = bounds.minY
        for (i, v) in subviews.enumerated() {
            let c = i % max(columns, 1), r = i / max(columns, 1)
            if c == 0, r > 0 { y += h[r - 1] + spacing }
            v.place(at: CGPoint(x: bounds.minX + CGFloat(c) * (w + spacing), y: y), anchor: .topLeading, proposal: ProposedViewSize(width: w, height: nil))
        }
    }
}

/// A controller this phone asked to join, until an owner answers.
struct WaitingCard: View {
    @Environment(AppModel.self) private var model
    let controller: Controller
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(controller.record.name).font(.title3.weight(.semibold))
            if controller.denied {
                Label("The owner declined your request.", systemImage: "xmark.circle").foregroundStyle(.orange)
                Button("Remove") { model.remove(controller) }.buttonStyle(.bordered)
            } else {
                HStack(spacing: 10) { SlatLoader(size: 20); Text("Waiting for an owner to approve").foregroundStyle(.secondary) }
                Text("Your code: \(controller.record.code ?? "")").font(.title2.weight(.semibold).monospacedDigit())
                Text("The owner opens Tilt and approves you. Their phone shows the same code.").font(.footnote).foregroundStyle(.secondary)
                Button("Cancel Request", role: .destructive) { model.remove(controller) }.buttonStyle(.bordered)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading).padding(20).card()
    }
}

/// A room on the home page.
struct RoomCard: View {
    let controller: Controller
    /// In the side column on a wide screen: smaller pictures.
    var compact = false
    /// The card's width, so the pictures inside get an exact size and change size in step with the card.
    var width: CGFloat? = nil
    /// Wide screens: open the room beside the list. Without it the card pushes the room's page.
    var onOpen: (() -> Void)? = nil
    var body: some View {
        let s = controller.state
        let shown = (s?.b ?? []).filter { $0.hid == 0 && !($0.seen == 1 && $0.pres == 0) }
        VStack(alignment: .leading, spacing: 14) {
          Group {
            if let onOpen { Button(action: onOpen) { top(s, shown) } } else { NavigationLink(value: controller.id) { top(s, shown) } }
          }
          .buttonStyle(.plain)
            // In the side column the buttons fold away inside the card (taken out, they would hang below it as it shrinks).
            if let s, s.b.contains(where: \.ready) {
                MoveBar(controller: controller, state: s, open: "Open", close: "Close")
                    .frame(height: compact ? 0 : nil, alignment: .top).opacity(compact ? 0 : 1).clipped()
                    .padding(.top, compact ? -14 : 0)
                    .allowsHitTesting(!compact)
            }
        }
        .padding(16)
        .frame(width: width, alignment: .leading)       // an exact width, so the card and what is in it change size on the same curve
        .clipShape(RoundedRectangle(cornerRadius: 26, style: .continuous))      // nothing pokes past the edge mid-move
        .card()
        .geometryGroup()                // the inside moves with the card as it changes size, not each piece by itself
        .opacity(controller.online || controller.state == nil ? 1 : 0.75)
    }
    private func top(_ s: ControllerState?, _ shown: [BlindState]) -> some View {
           VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 3) {
                    Text(s?.name ?? controller.record.name).font(.title3.weight(.semibold)).lineLimit(1).fixedSize()      // never cut short mid-move
                    Text(controller.online ? (s.map(TiltWords.room) ?? "Connecting…") : "Not reachable").font(.subheadline).foregroundStyle(controller.online ? .secondary : Color.orange).lineLimit(1).fixedSize()
                }
                .layoutPriority(1)
                Spacer(minLength: 6)
                if let s { BatteryPill(battery: s.batt).opacity(compact ? 0 : 1) }      // the side column is narrow: the open room shows the battery
            }
            HStack(spacing: 10) {
                let n = CGFloat(max(min(shown.count, 3), 1))
                let pw = width.map { max(20, ($0 - 32 - 10 * (n - 1)) / n) }
                ForEach(Array(shown.prefix(3).enumerated()), id: \.offset) { k, b in
                    SlatView(tilt: b.tilt ?? 0, known: b.tilt != nil, slats: 7, pane: k, panes: min(shown.count, 3)).frame(width: pw, height: compact ? 64 : 118)
                }
                if shown.isEmpty { SlatView(tilt: 0, known: false, slats: 7).frame(width: pw, height: compact ? 64 : 118) }
            }
           }
           .contentShape(Rectangle())
    }
}

/// Open and Close for a whole room. A tap moves the blinds now; press and hold for a gentle move that takes minutes.
/// While anything is moving, the two make way for one Stop button.
struct MoveBar: View {
    let controller: Controller
    let state: ControllerState
    let open: String, close: String
    @State private var positioning = false
    var body: some View {
        let busy = state.mv >= 0 || state.gentle == 1
        HStack(spacing: 10) {
            if busy {
                QuickButton(title: state.mv >= 0 ? "Stop" : "Stop Gentle Move", systemImage: "stop.fill", tint: .red) { controller.stopAll() }
                    .transition(.opacity)
            } else {
                GentleButton(title: open, systemImage: "sun.max.fill", verb: "Open", position: { positioning = true }) { controller.goAll(to: "open", gently: $0) }
                GentleButton(title: close, systemImage: "moon.fill", verb: "Close", position: { positioning = true }) { controller.goAll(to: "close", gently: $0) }
            }
        }
        .animation(.easeInOut(duration: 0.2), value: busy)
        .sheet(isPresented: $positioning) {
            PositionSheet(title: state.name, start: state.b.first(where: \.ready)?.tilt ?? 0) { controller.goAll(tilt: $0) }.presentationDetents([.height(420)])
        }
    }
}

/// Open All and Close All for every room, on the home page. Works like a room's own bar: tap for now, hold for more.
struct HomeMoveBar: View {
    let controllers: [Controller]
    @State private var positioning = false
    var body: some View {
        let moving = controllers.contains { ($0.state?.mv ?? -1) >= 0 }
        let busy = moving || controllers.contains { $0.state?.gentle == 1 }
        HStack(spacing: 10) {
            if busy {
                QuickButton(title: moving ? "Stop All" : "Stop Gentle Move", systemImage: "stop.fill", tint: .red) { controllers.forEach { $0.stopAll() } }
                    .transition(.opacity)
            } else {
                GentleButton(title: "Open All", systemImage: "sun.max.fill", verb: "Open", position: { positioning = true }) { m in controllers.forEach { $0.goAll(to: "open", gently: m) } }
                GentleButton(title: "Close All", systemImage: "moon.fill", verb: "Close", position: { positioning = true }) { m in controllers.forEach { $0.goAll(to: "close", gently: m) } }
            }
        }
        .animation(.easeInOut(duration: 0.2), value: busy)
        .sheet(isPresented: $positioning) {
            PositionSheet(title: "All Blinds", start: 0) { t in controllers.forEach { $0.goAll(tilt: t) } }.presentationDetents([.height(420)])
        }
    }
}

/// A button that acts on a tap. Press and hold for the choices (slide a finger to pick): the plain move, the same move
/// done gently over some minutes, or a position picked with a slider.
struct GentleButton: View {
    let title: String, systemImage: String, verb: String
    let position: () -> Void
    /// Minutes to take; 0 = now.
    let action: (Int) -> Void
    @State private var taps = 0
    var body: some View {
        Menu {
            Button(verb, systemImage: systemImage) { taps += 1; action(0) }
            Section("Gently") {
                Button("\(verb) Gently", systemImage: "tortoise") { taps += 1; action(5) }
                Button("Over 10 Minutes", systemImage: "tortoise") { taps += 1; action(10) }
                Button("Over 30 Minutes", systemImage: "tortoise") { taps += 1; action(30) }
            }
            Button("Move to Position…", systemImage: "slider.horizontal.3") { position() }
        } label: {
            Label(title, systemImage: systemImage).font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity).padding(.vertical, 4)
        } primaryAction: { taps += 1; action(0) }
        .buttonStyle(.glass)
        .sensoryFeedback(.impact(weight: .light), trigger: taps)
    }
}

/// Pick a position with a slider and send the blinds there.
struct PositionSheet: View {
    @Environment(\.dismiss) private var dismiss
    let title: String
    let start: Double
    let move: (Int) -> Void
    @State private var tilt = 0.0
    var body: some View {
        VStack(spacing: 16) {
            VStack(spacing: 4) {
                Text(title).font(.title3.weight(.semibold))
                Text(TiltWords.long(tilt)).font(.subheadline).foregroundStyle(.secondary).contentTransition(.numericText())
            }
            SlatView(tilt: tilt, slats: 9).frame(width: 170, height: 170)
            HStack(spacing: 12) {
                Image(systemName: "arrow.down.to.line").foregroundStyle(.secondary)
                Slider(value: $tilt, in: -100...100, step: 5).accessibilityLabel("Tilt")
                Image(systemName: "arrow.up.to.line").foregroundStyle(.secondary)
            }
            Button { move(Int(tilt)); dismiss() } label: { Text("Move").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 4) }
                .buttonStyle(.glassProminent).controlSize(.large)
        }
        .padding(.horizontal, 24).padding(.top, 34).padding(.bottom, 16)
        .onAppear { tilt = (start / 5).rounded() * 5 }
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
    /// Shown beside the rooms on a wide screen: the page behind supplies the background.
    var embedded = false
    /// The width it will have, when the page that holds it knows (so the blinds do not re-flow while it slides in).
    var fitWidth: CGFloat? = nil
    @State private var open: Int?
    @State private var measured: CGFloat = 400
    private var width: CGFloat { fitWidth ?? measured }

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
                    // Two blinds across on a phone, three on a folded-open or small tablet screen, four on a big one.
                    CardFlow(columns: Layout.count(width, phone: 2, medium: 3, large: 4, from: 480, to: 860), spacing: 14) {
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
            .padding(.horizontal, 18).padding(.bottom, 10)
        }
        .onGeometryChange(for: CGFloat.self) { $0.size.width } action: { measured = $0 }
        .background { if !embedded { AppBackground() } }
        // Open All / Close All sit at the bottom, in reach of a thumb.
        .safeAreaInset(edge: .bottom) {
            if let s, s.b.contains(where: { $0.ready && $0.hid == 0 }) {
                MoveBar(controller: controller, state: s, open: "Open All", close: "Close All")
                    .controlSize(.large).frame(maxWidth: 520).padding(.horizontal, 18).padding(.bottom, width >= 480 ? 6 : 16)
            }
        }
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
            .geometryGroup()
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
            .padding(.top, 38)                          // clear of the drawer's grab bar
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
                if blind.moving { Button(role: .destructive) { controller.stopAll() } label: { Label("Stop", systemImage: "stop.fill").frame(maxWidth: .infinity) }.buttonStyle(.glassProminent).tint(.red) }
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
