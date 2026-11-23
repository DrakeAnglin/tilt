// Open / Close / Stop buttons: the bar for one room or every room, the hold menu, and the position picker.
import SwiftUI

/// Open and Close for one room or for every room. A tap moves the blinds now; press and hold for a gentle move that
/// takes minutes, or to pick a position. While anything is moving, the two make way for one Stop button.
struct MoveBar: View {
    let controllers: [Controller]
    /// The words on the buttons ("Open" on a room's card, "Open All" on a page).
    var open = "Open All", close = "Close All"
    /// What the position picker is headed with.
    var title = "All Blinds"
    @State private var positioning = false
    var body: some View {
        let moving = controllers.contains { ($0.state?.mv ?? -1) >= 0 }
        let busy = moving || controllers.contains { $0.state?.gentle == 1 }
        HStack(spacing: 10) {
            if busy {
                QuickButton(title: moving ? (controllers.count > 1 ? "Stop All" : "Stop") : "Stop Gentle Move", systemImage: "stop.fill", tint: Palette.danger) { controllers.forEach { $0.stopAll() } }
                    .transition(.opacity)
            } else {
                GentleButton(title: open, systemImage: "sun.max.fill", verb: "Open", position: { positioning = true }) { m in controllers.forEach { $0.goAll(to: "open", gently: m) } }
                GentleButton(title: close, systemImage: "moon.fill", verb: "Close", position: { positioning = true }) { m in controllers.forEach { $0.goAll(to: "close", gently: m) } }
            }
        }
        .animation(.easeInOut(duration: 0.2), value: busy)
        .sheet(isPresented: $positioning) {
            let start = controllers.count == 1 ? controllers[0].state?.b.first(where: \.ready)?.tilt ?? 0 : 0
            PositionSheet(title: title, start: start) { t in controllers.forEach { $0.goAll(tilt: t) } }.presentationDetents([.height(420)])
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
            Button("Set Tilt…", systemImage: "slider.horizontal.3") { position() }
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
