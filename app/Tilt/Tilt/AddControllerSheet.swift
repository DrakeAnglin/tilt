// Adding a controller: a brand-new one over Bluetooth, or one already on your Tilt Hub. A controller that has an owner
// is asked to let this phone join; the owner approves it in their Tilt app.
import SwiftUI

struct AddControllerSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(Discovery.self) private var discovery
    @Environment(HubWatch.self) private var hub
    @Environment(\.dismiss) private var dismiss
    @State private var busy = false
    @State private var problem: String?
    @State private var ble = BleSetup()

    var body: some View {
        NavigationStack {
            Form {
            Group {
                // Not yours yet. A controller announced through the hub counts only if the hub has heard from it (a phone
                // remembers announcements for a while after a reset).
                let live = Set((hub.info?.c ?? []).filter { $0.seenS >= 0 && !$0.notResponding }.map(\.id))
                let fresh = discovery.found.filter { f in !(model.controllers + model.waiting).contains { $0.id == f.id } && (!f.host.contains(ControllerRecord.hubPath) || live.contains(f.id)) }
                Section {
                    switch hub.status {
                    case .connected where hub.isOwner:
                        if hub.answering == false { Label("Your Tilt Hub is unreachable", systemImage: "exclamationmark.triangle").foregroundStyle(Palette.warning) }
                        else { Label("Connected to your Tilt Hub", systemImage: "checkmark.circle.fill").foregroundStyle(Palette.good) }
                    case .connected: Label("Only the hub's owner can add controllers", systemImage: "lock")
                    case .waiting: Label("Waiting for the hub's owner to let you in", systemImage: "hourglass")
                    case .newHub, .someoneElses: Label("Connect to the Tilt Hub first, on the Blinds page", systemImage: "point.3.connected.trianglepath.dotted")
                    case .none: Label("Looking for a Tilt Hub…", systemImage: "point.3.connected.trianglepath.dotted").foregroundStyle(.secondary)
                    }
                } header: { Text("Tilt Hub") } footer: {
                    Text(hub.isOwner ? "New controllers join through it: pick one below." : "Controllers connect through a Tilt Hub. Plug it in, keep this iPhone on the same Wi-Fi, and connect to it from the Blinds page.")
                }
                Section {
                    if let p = ble.problem { Label(p, systemImage: "exclamationmark.triangle").foregroundStyle(Palette.warning) }
                    else if ble.found.isEmpty { Label("Looking for new controllers…", systemImage: "dot.radiowaves.left.and.right").foregroundStyle(.secondary) }
                    ForEach(ble.found) { d in
                        NavigationLink(value: d) { Label("Blinds Controller", systemImage: "blinds.horizontal.closed") }
                    }
                } header: { Text("New, over Bluetooth") } footer: {
                    Text("A new controller can be set up in its first 15 minutes after it is plugged in. If yours is not listed, unplug it and plug it back in.")
                }
                Section {
                    if fresh.isEmpty { Label(hub.answering == true ? "None waiting to be added" : "Looking on your Tilt Hub…", systemImage: "dot.radiowaves.left.and.right").foregroundStyle(.secondary) }
                    ForEach(fresh) { f in
                        Button { add(f) } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(f.name).foregroundStyle(.primary)
                                    Text(f.owned ? "Tap to ask its owner to let you in" : "New: tap to add").font(.footnote).foregroundStyle(.secondary)
                                }
                                Spacer()
                                if busy { SlatLoader(size: 20) } else { Text(f.owned ? "Ask to Join" : "Add").fontWeight(.medium) }
                            }
                        }
                        .disabled(busy)
                    }
                } header: { Text("Already on your Tilt Hub") }
                if !model.hasDemo && hub.record == nil {           // with a Tilt Hub there is real hardware to set up
                    Section {
                        Button("Try the Demo", systemImage: "play.rectangle") { model.addDemo(); dismiss() }
                    } footer: { Text("A pretend room with three blinds, to see how Tilt works before you have a controller. Remove it in Settings.") }
                }
                if busy { Section { HStack(spacing: 12) { SlatLoader(size: 20); ProgressWords(steps: ["Reaching it through the Tilt Hub…", "Making a key for this iPhone…", "It checks in about once a second: one moment…", "Almost there…"]) } } }
                if let problem { Section { Label(problem, systemImage: "exclamationmark.triangle").foregroundStyle(Palette.warning) } }
            }
        }
            .navigationDestination(for: BleSetup.Found.self) { d in BluetoothSetupView(ble: ble, device: d) { dismiss() } }
            .onAppear { ble.start(); hub.start() }
            .navigationTitle("Add a New Device")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
        }
        .onDisappear { ble.stop() }                      // when the whole sheet closes
    }

    private func add(_ f: FoundController) {
        busy = true; problem = nil
        Task {
            defer { busy = false }
            do { try await model.add(host: f.host); hub.justAdded(); dismiss() } catch { problem = error.localizedDescription }
        }
    }
}
