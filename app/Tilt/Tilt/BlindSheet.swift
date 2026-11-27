// The drawer for one blind: its picture, slider and buttons.
import SwiftUI

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
        let row = (controller.state?.b ?? []).enumerated().filter { $0.element.listed }.map(\.offset)
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
            if let blind { ForEach(BlindWarning.all(blind)) { w in Group { if let url = w.link { SwiftUI.Link(destination: url) { Label(w.text, systemImage: "exclamationmark.triangle.fill") } } else { Label(w.text, systemImage: "exclamationmark.triangle.fill") } }.font(.footnote).foregroundStyle(Palette.warning).frame(maxWidth: .infinity, alignment: .leading) } }
            if let blind, blind.ready {
                HStack(spacing: 12) {
                    Image(systemName: "arrow.down.to.line").foregroundStyle(.secondary)
                    Slider(value: Binding(get: { shownTilt }, set: { drag = $0.rounded() }), in: -100...100, onEditingChanged: { if !$0 { commit() } }).accessibilityLabel("Tilt")
                    Image(systemName: "arrow.up.to.line").foregroundStyle(.secondary)
                }
                // While it moves, one Stop button takes the three buttons' place: same spot, same height, nothing shifts.
                HStack(spacing: 10) {
                    PositionButton(title: "Close Down", systemImage: "chevron.down") { controller.go(blind: index, tilt: -100) }
                    PositionButton(title: "Open", systemImage: "sun.max.fill") { controller.go(blind: index, tilt: 0) }
                    PositionButton(title: "Close Up", systemImage: "chevron.up") { controller.go(blind: index, tilt: 100) }
                }
                .opacity(blind.moving ? 0 : 1).disabled(blind.moving)
                .overlay {
                    if blind.moving {
                        Button(role: .destructive) { controller.stopAll() } label: {
                            VStack(spacing: 6) { Image(systemName: "stop.fill").font(.title3).frame(height: 24); Text("Stop").font(.footnote.weight(.semibold)) }
                                .frame(maxWidth: .infinity, maxHeight: .infinity)
                        }
                        .buttonStyle(.glassProminent).tint(Palette.danger)
                    }
                }
                .animation(.default, value: blind.moving)
            } else if let blind {
                if blind.cal == 0 && !(blind.seen == 1 && blind.pres == 0) {
                    Text("This blind needs setup. It takes about a minute: you turn the blind by hand to three spots.")
                        .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    if controller.record.owner {
                        Button { settingUp = true } label: { Text("Start Setup").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 6) }
                            .buttonStyle(.glassProminent).controlSize(.large)
                    } else {
                        Text("Ask an owner to set it up.").font(.subheadline.weight(.semibold))      // setup is an owner's job
                    }
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
