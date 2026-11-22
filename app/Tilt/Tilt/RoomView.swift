// One room's page: its blinds as cards.
import SwiftUI

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
                        Text(controller.reach == .online ? (s.map(TiltWords.room) ?? "Connecting…") : controller.awayLine + (controller.reach == .unreachable ? ". Is this phone on your home Wi-Fi?" : "")).font(.subheadline).foregroundStyle(.secondary)
                    }
                    Spacer()
                    if let s { BatteryPill(battery: s.batt) }
                }
                if controller.needsUpdate { FirmwareNotice(controller: controller).padding(12).frame(maxWidth: .infinity, alignment: .leading).card(radius: 16) }
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
                    Label(e, systemImage: "exclamationmark.triangle.fill").font(.footnote).foregroundStyle(Palette.warning).padding(12).frame(maxWidth: .infinity, alignment: .leading).card(radius: 16)
                        .task(id: e) { try? await Task.sleep(for: .seconds(4)); controller.lastError = nil }
                }
            }
            .padding(.horizontal, 18).padding(.bottom, 10)
        }
        .onGeometryChange(for: CGFloat.self) { $0.size.width } action: { measured = $0 }
        .background { if !embedded { AppBackground() } }
        // Open All / Close All sit at the bottom, in reach of a thumb.
        .safeAreaInset(edge: .bottom) {
            if let s, s.b.contains(where: \.ready) {
                MoveBar(controllers: [controller], title: s.name)
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
            BlindSheet(controller: controller, index: i.id).presentationDetents([.fraction(0.72), .large]).presentationDragIndicator(.visible)
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
                    if blind.stuck { Image(systemName: "exclamationmark.triangle.fill").font(.footnote).foregroundStyle(Palette.warning) }
                    Text(TiltWords.status(blind)).font(.subheadline).foregroundStyle(blind.stuck ? Palette.warning : Color.secondary).lineLimit(1)
                }
            }
            .padding(12).frame(maxWidth: .infinity, alignment: .leading).card(radius: 24)
            .geometryGroup()
        }
        .buttonStyle(.plain)
    }
}
