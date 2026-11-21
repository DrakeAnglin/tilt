// App settings: how Tilt looks and behaves on this phone, plus a way into each room's own settings.
import SwiftUI

struct SettingsTab: View {
    @Environment(AppModel.self) private var model
    @State private var adding = false
    @AppStorage("appearance") private var appearance = 0
    @AppStorage("devMode") private var devMode = false

    var body: some View {
        NavigationStack {
            List {
                Section {
                    ForEach(model.controllers) { c in
                        NavigationLink {
                            ControllerSettingsView(controller: c)
                        } label: {
                            HStack(spacing: 12) {
                                SlatView(tilt: c.state?.b.first(where: \.ready)?.tilt ?? 0, known: c.state != nil, slats: 5).frame(width: 44, height: 44)
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(c.state?.name ?? c.record.name).font(.body.weight(.medium))
                                    Text("\(c.record.owner ? "Owner" : "Shared with you")\(c.state == nil ? " · not reachable" : "")").font(.footnote).foregroundStyle(.secondary)
                                }
                            }
                            .padding(.vertical, 2)
                        }
                    }
                    Button("Add a Controller", systemImage: "plus") { adding = true }
                } header: { Text("Rooms") } footer: {
                    Text("Blind names, positions, sharing and Apple Home live in each room's settings.")
                }
                Section("This Phone") {
                    Picker(selection: $appearance) {
                        Text("Automatic").tag(0); Text("Light").tag(1); Text("Dark").tag(2)
                    } label: { Label("Appearance", systemImage: "circle.lefthalf.filled") }
                    Button { open(UIApplication.openNotificationSettingsURLString) } label: { Label("Notifications", systemImage: "bell.badge") }
                }
                Section {
                    Toggle(isOn: $devMode) { Label("Developer Mode", systemImage: "chevron.left.forwardslash.chevron.right") }
                } footer: {
                    Text("Shows sensor readings, motor tuning and logs in each room's settings.")
                }
                Section("About") {
                    LabeledContent("Version", value: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "")
                    ForEach(model.controllers) { c in
                        if let s = c.state { LabeledContent("\(s.name) firmware", value: s.v) }
                    }
                }
            }
            .skyPage()
            .navigationTitle("Settings")
            .sheet(isPresented: $adding) { AddControllerSheet() }
        }
    }
    private func open(_ s: String) { if let u = URL(string: s) { UIApplication.shared.open(u) } }
}
