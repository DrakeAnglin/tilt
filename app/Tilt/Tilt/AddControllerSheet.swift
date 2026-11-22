// Adding a controller: a brand-new one over Bluetooth, or one already on Wi-Fi. A controller that has an owner is
// asked to let this phone join; the owner approves it in their Tilt app.
import SwiftUI

struct AddControllerSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(Discovery.self) private var discovery
    @Environment(\.dismiss) private var dismiss
    @State private var busy = false
    @State private var problem: String?
    @State private var ble = BleSetup()

    var body: some View {
        NavigationStack {
            Form {
            Group {
                let fresh = discovery.found.filter { f in !(model.controllers + model.waiting).contains { $0.id == f.id } }
                Section {
                    if let p = ble.problem { Label(p, systemImage: "exclamationmark.triangle").foregroundStyle(Palette.warning) }
                    else if ble.found.isEmpty { Label("Looking for new controllers…", systemImage: "dot.radiowaves.left.and.right").foregroundStyle(.secondary) }
                    ForEach(ble.found) { d in
                        NavigationLink(value: d) { Label("Blinds Controller", systemImage: "blinds.horizontal.closed") }
                    }
                } header: { Text("New, over Bluetooth") } footer: {
                    Text("A new controller shows up here for 15 minutes after it is powered on. If yours is not listed, unplug it and plug it back in.")
                }
                Section {
                    if fresh.isEmpty { Label("Looking on your Wi-Fi…", systemImage: "dot.radiowaves.left.and.right").foregroundStyle(.secondary) }
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
                } header: { Text("Already on your Wi-Fi") }
                if !model.hasDemo {
                    Section {
                        Button("Try the Demo", systemImage: "play.rectangle") { model.addDemo(); dismiss() }
                    } footer: { Text("A pretend room with three blinds, to see how Tilt works before you have a controller. Remove it in Settings.") }
                }
                if let problem { Section { Label(problem, systemImage: "exclamationmark.triangle").foregroundStyle(Palette.warning) } }
            }
            .listRowBackground(RowGlass())      // rows are glass over the sky, not solid white
        }
            .skyPage()
            .navigationDestination(for: BleSetup.Found.self) { d in BluetoothSetupView(ble: ble, device: d) { dismiss() } }
            .onAppear { ble.start() }
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
            do { try await model.add(host: f.host); dismiss() } catch { problem = error.localizedDescription }
        }
    }
}
