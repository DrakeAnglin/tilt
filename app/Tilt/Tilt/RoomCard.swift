// A room on the home page: its card, the card of a controller that is waiting for approval, and the battery badge.
import SwiftUI

/// A controller this phone asked to join, until an owner answers.
struct WaitingCard: View {
    @Environment(AppModel.self) private var model
    let controller: Controller
    @State private var recovering = false
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(controller.record.name).font(.title3.weight(.semibold))
            if controller.denied {
                Label("The owner declined your request.", systemImage: "xmark.circle").foregroundStyle(Palette.warning)
                Button("Remove") { model.remove(controller) }.buttonStyle(.bordered)
            } else {
                HStack(spacing: 10) { SlatLoader(size: 20); Text("Waiting for an owner to approve").foregroundStyle(.secondary) }
                Text("Your code: \(controller.record.code ?? "")").font(.title2.weight(.semibold).monospacedDigit())
                Text("The owner opens Tilt and approves you. Their phone shows the same code.").font(.footnote).foregroundStyle(.secondary)
                HStack {
                    Button("Cancel Request", role: .destructive) { model.remove(controller) }.buttonStyle(.bordered)
                    Spacer()
                    Button("No owner left?") { recovering = true }.font(.footnote)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading).padding(20).card()
        .sheet(isPresented: $recovering) { RecoverSheet(id: controller.id, host: controller.record.host, name: controller.record.name).presentationDetents([.height(520)]) }
    }
}

/// Shown where a controller's firmware is older than this version of the app needs.
struct FirmwareNotice: View {
    let controller: Controller
    var body: some View {
        Label("This controller runs firmware \(controller.state?.v ?? ""). This version of Tilt needs \(Api.minFirmware) or newer, so some things may not work until it is updated. An owner can update it under About in this room's settings.", systemImage: "arrow.triangle.2.circlepath")
            .font(.footnote).foregroundStyle(Palette.warning)
    }
}

/// Getting back into a controller when no owner's phone is left: prove you are at the window by turning a blind.
struct RecoverSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let id: String, host: String, name: String
    @State private var blind: String?
    @State private var step = 0
    @State private var left = 120
    @State private var problem: String?
    private var done: Bool { model.controllers.contains { $0.id == id } }
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Recover Access").font(.title2.weight(.semibold))
            if done {
                Label("You are in, as an owner of \(name).", systemImage: "checkmark.circle.fill").foregroundStyle(Palette.good)
                Button { dismiss() } label: { Text("Done").frame(maxWidth: .infinity) }.buttonStyle(.borderedProminent).controlSize(.large)
            } else if let blind {
                Text("Turn the wand of \(blind) by hand, in this order. \(max(left, 0)) seconds left.").font(.subheadline).foregroundStyle(.secondary)
                row(0, "Close it all the way, slats up")
                row(1, "Close it all the way, slats down")
                row(2, "Open it, slats level")
            } else {
                Text("If no owner can approve you (a lost or replaced phone), you can still get in by showing you are at the window.")
                    .font(.subheadline).foregroundStyle(.secondary)
                Text("You will turn one blind\u{2019}s wand fully closed up, fully closed down, then level, within two minutes. This phone then becomes an owner. Nothing else is changed.")
                    .font(.subheadline).foregroundStyle(.secondary)
                Button { start() } label: { Text("Start").frame(maxWidth: .infinity) }.buttonStyle(.borderedProminent).controlSize(.large)
            }
            if let problem { Label(problem, systemImage: "exclamationmark.triangle").font(.footnote).foregroundStyle(Palette.warning) }
            Spacer(minLength: 0)
        }
        .padding(24)
    }
    private func row(_ n: Int, _ text: String) -> some View {
        Label(text, systemImage: step > n ? "checkmark.circle.fill" : step == n ? "arrow.right.circle" : "circle")
            .foregroundStyle(step > n ? Palette.good : step == n ? Color.primary : Color.secondary).font(.body.weight(step == n ? .semibold : .regular))
    }
    private func start() {
        problem = nil
        Task {
            do { blind = try await model.recover(host: host) } catch { problem = error.localizedDescription; return }
            while !done {
                guard let r = await Secure.recovery(host) else { break }
                step = r.step; left = r.left
                try? await Task.sleep(for: .seconds(1))
            }
            try? await Task.sleep(for: .seconds(2))          // the app notices it was let in on its next read
            if !done { blind = nil; step = 0; problem = "Time ran out before all three turns were seen. You can try again." }
        }
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
        let shown = (s?.b ?? []).filter { $0.listed }
        VStack(alignment: .leading, spacing: 14) {
          Group {
            if let onOpen { Button(action: onOpen) { top(s, shown) } } else { NavigationLink(value: controller.id) { top(s, shown) } }
          }
          .buttonStyle(.plain)
            // In the side column the buttons fold away inside the card (taken out, they would hang below it as it shrinks).
            if let s, s.b.contains(where: \.ready) {
                MoveBar(controllers: [controller], open: "Open", close: "Close", title: s.name)
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
                    Text(controller.online ? (s.map(TiltWords.room) ?? "Connecting…") : "Not reachable").font(.subheadline).foregroundStyle(controller.online ? .secondary : Palette.warning).lineLimit(1).fixedSize()
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

struct BatteryPill: View {
    let battery: ControllerState.Battery
    var body: some View {
        let charging = battery.st != "battery"
        HStack(spacing: 5) {
            Image(systemName: charging ? "bolt.fill" : battery.pct < 20 ? "battery.25percent" : "battery.75percent").font(.caption2)
            Text("\(battery.pct)%").font(.caption.weight(.semibold)).monospacedDigit()
        }
        .foregroundStyle(battery.low == 1 || (!charging && battery.pct < 20) ? Palette.danger : charging ? Palette.good : Color.secondary)
        .padding(.horizontal, 9).padding(.vertical, 5)
        .background(Palette.surface, in: Capsule())
        .accessibilityLabel("Battery \(battery.pct) percent\(charging ? ", charging" : "")")
    }
}
