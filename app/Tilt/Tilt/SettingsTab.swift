// App settings: how Tilt looks and behaves on this phone, plus a way into each room's own settings.
import SwiftUI

struct SettingsTab: View {
    @Environment(AppModel.self) private var model
    @State private var adding = false
    @State private var selected: String?
    @Environment(\.horizontalSizeClass) private var wide
    @AppStorage("appearance") private var appearance = 0
    @AppStorage("devMode") private var devMode = false
    @State private var myName = AppModel.myName
    @State private var cloud: Bool?

    var body: some View {
        // On a wide screen (iPad, a Duo opened flat) the list stays on the left and a room's settings open beside it.
        // On a phone the same list pushes the room's settings as its own page.
        NavigationSplitView {
            List(selection: $selected) {
                Section {
                    ForEach(model.controllers) { c in
                        NavigationLink(value: c.id) {
                            HStack(spacing: 12) {
                                SlatView(tilt: c.state?.b.first(where: \.ready)?.tilt ?? 0, known: c.state != nil, slats: 5).frame(width: 44, height: 44)
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(c.state?.name ?? c.record.name).font(.body.weight(.medium))
                                    Text("\(c.record.owner ? "Owner" : "User")\(c.state == nil ? " · not reachable" : "")").font(.footnote).foregroundStyle(.secondary)
                                }
                            }
                            .padding(.vertical, 2)
                        }
                    }
                    Button("Add a New Device", systemImage: "plus") { adding = true }
                } header: { Text("Rooms") } footer: {
                    Text("Blind names, positions, sharing and Apple Home live in each room's settings.")
                }
                Section {
                    LabeledContent { TextField("Name", text: $myName).multilineTextAlignment(.trailing).onSubmit { model.rename(to: myName) } } label: { Label("Display Name", systemImage: "person.crop.circle").lineLimit(1).fixedSize(horizontal: true, vertical: false) }
                    LabeledContent { Text(cloud == nil ? "Checking…" : cloud == true ? "On" : "Off") } label: { Label("iCloud Notices", systemImage: "icloud") }
                    Picker(selection: $appearance) {
                        Text("Automatic").tag(0); Text("Light").tag(1); Text("Dark").tag(2)
                    } label: { Label("Appearance", systemImage: "circle.lefthalf.filled") }
                    Button { open(UIApplication.openNotificationSettingsURLString) } label: { Label("Notifications", systemImage: "bell.badge") }
                } header: { Text("This Phone") } footer: {
                    Text(cloud == false ? "Sign in to iCloud in the Settings app to be told when someone asks to join your blinds, even when Tilt is closed." : "Your display name is what other people see in People and when you ask to join their blinds. iCloud tells you when someone asks to join yours.")
                }
                Section {
                    Toggle(isOn: $devMode) { Label("Developer Mode", systemImage: "chevron.left.forwardslash.chevron.right") }
                } footer: {
                    Text("Shows sensor readings, motor tuning and logs in each room's settings.")
                }
                Section("About") {
                    LabeledContent("Version", value: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "")
                }
            }
            .skyPage()
            .navigationTitle("Settings")
            .onAppear { if wide == .regular, selected == nil { selected = model.controllers.first?.id } }
            .task { cloud = await Cloud.signedIn() }
            .onAppear { myName = AppModel.myName }
            .onDisappear { if myName != AppModel.myName { model.rename(to: myName) } }
            .sheet(isPresented: $adding) { AddControllerSheet() }
        } detail: {
            NavigationStack {
                if let c = model.controllers.first(where: { $0.id == selected }) { ControllerSettingsView(controller: c).id(c.id) }
                else { ContentUnavailableView("Pick a Room", systemImage: "blinds.horizontal.closed", description: Text("Its blinds, people and Apple Home settings show here.")).skyPage() }
            }
        }
        .onChange(of: model.controllers.count) { _, _ in if !model.controllers.contains(where: { $0.id == selected }) { selected = wide == .regular ? model.controllers.first?.id : nil } }
    }
    private func open(_ s: String) { if let u = URL(string: s) { UIApplication.shared.open(u) } }
}
