// Adding a controller: a brand-new one over Bluetooth, one already on Wi-Fi, or with a sharing link from the owner.
import SwiftUI

struct AddControllerSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(Discovery.self) private var discovery
    @Environment(\.dismiss) private var dismiss
    @State private var host = ""
    @State private var link = ""
    @State private var busy = false
    @State private var problem: String?
    @State private var ble = BleSetup()

    var body: some View {
        NavigationStack {
            Form {
                let fresh = discovery.found.filter { f in !model.controllers.contains { $0.id == f.id } }
                Section {
                    if let p = ble.problem { Label(p, systemImage: "exclamationmark.triangle").foregroundStyle(.orange) }
                    else if ble.found.isEmpty { Label("Looking for new controllers…", systemImage: "dot.radiowaves.left.and.right").foregroundStyle(.secondary) }
                    ForEach(ble.found) { d in
                        NavigationLink(value: d) { Label("New controller", systemImage: "blinds.horizontal.closed") }
                    }
                } header: { Text("New, over Bluetooth") } footer: {
                    Text("A new controller shows up here for 15 minutes after it is powered on. If yours is not listed, unplug it and plug it back in.")
                }
                Section {
                    if fresh.isEmpty { Label("Looking on your Wi-Fi…", systemImage: "dot.radiowaves.left.and.right").foregroundStyle(.secondary) }
                    ForEach(fresh) { f in
                        Button { if !f.owned { host = f.host; link = ""; add() } } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(f.name).foregroundStyle(.primary)
                                    Text(f.owned ? "Has an owner: ask them to share it with you" : "New: tap to add").font(.footnote).foregroundStyle(.secondary)
                                }
                                Spacer()
                                Image(systemName: f.owned ? "lock" : "plus.circle.fill")
                            }
                        }
                        .disabled(f.owned || busy)
                    }
                } header: { Text("Already on your Wi-Fi") }
                Section {
                    TextField("192.168.1.50", text: $host).keyboardType(.numbersAndPunctuation).textInputAutocapitalization(.never).autocorrectionDisabled()
                } header: { Text("Controller address") } footer: { Text("For a controller nobody has paired yet. This phone becomes its owner.") }
                Section {
                    TextField("tilt://join?…", text: $link, axis: .vertical).textInputAutocapitalization(.never).autocorrectionDisabled()
                } header: { Text("Or a sharing link") } footer: { Text("Paste the link the owner shared with you.") }
                if let problem { Section { Label(problem, systemImage: "exclamationmark.triangle").foregroundStyle(.orange) } }
            }
            .skyPage()
            .navigationDestination(for: BleSetup.Found.self) { d in BluetoothSetupView(ble: ble, device: d) { dismiss() } }
            .onAppear { ble.start() }
            .navigationTitle("Add a Controller")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    if busy { SlatLoader(size: 20) } else { Button("Add") { add() }.disabled(host.isEmpty && link.isEmpty) }
                }
            }
        }
        .onDisappear { ble.stop() }                      // when the whole sheet closes
    }

    private func add() {
        busy = true; problem = nil
        Task {
            defer { busy = false }
            do {
                if !link.isEmpty {
                    guard let inv = Invite(link: link) else { throw TiltError("That sharing link is not valid.") }
                    try await model.add(host: inv.host, invite: inv)
                } else {
                    try await model.add(host: host.trimmingCharacters(in: .whitespaces), invite: nil)
                }
                dismiss()
            } catch { problem = error.localizedDescription }
        }
    }
}
