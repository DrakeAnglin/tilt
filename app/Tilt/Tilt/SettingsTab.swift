// App settings: how Tilt looks and behaves on this iPhone, plus a way into each device's own settings.
import SwiftUI

struct SettingsTab: View {
    @Environment(AppModel.self) private var model
    @Environment(HubWatch.self) private var hub
    @State private var confirmErase = false
    @State private var adding = false
    @State private var selected: String?
    @Environment(\.horizontalSizeClass) private var wide
    @AppStorage(Prefs.appearance) private var appearance = 0
    @AppStorage(Prefs.devMode) private var devMode = false
    @AppStorage(Prefs.firmwareBeta) private var firmwareBeta = false
    @AppStorage(Prefs.firmwareSource) private var firmwareSource = ""
    @State private var myName = AppModel.myName
    @State private var cloud: Bool?

    var body: some View {
        // On a wide screen (iPad, a Duo opened flat) the list stays on the left and a room's settings open beside it.
        // On a phone the same list pushes the room's settings as its own page.
        NavigationSplitView {
            List(selection: $selected) {
            Group {
                Section {
                    ForEach(model.controllers) { c in
                        NavigationLink(value: c.id) {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(c.state?.name ?? c.record.name).font(.body.weight(.medium))
                                Text("\(c.record.owner ? "Owner" : "Guest")\(c.reach == .unreachable ? " · unreachable" : "")").font(.footnote).foregroundStyle(.secondary)
                            }
                            .padding(.vertical, 2)
                        }
                        .listRowBackground(rowBackground(c.id))
                    }
                    if hub.status == .connected {       // only once this iPhone is in (a request still waiting shows on the Blinds page)
                        NavigationLink(value: Self.hubTag) {
                            VStack(alignment: .leading, spacing: 3) {
                                Text("Tilt Hub").font(.body.weight(.medium))
                                Text(hub.statusWord).font(.footnote).foregroundStyle(.secondary)
                            }
                            .padding(.vertical, 2)
                        }
                        .listRowBackground(rowBackground(Self.hubTag))
                    }
                    Button("Add a New Device", systemImage: "plus") { adding = true }.listRowBackground(RowGlass()).selectionDisabled()
                } header: { Text("Devices") } footer: {
                    Text("Tap a device for its settings: blind names and marks, people and Apple Home.")
                }
                Section {
                    LabeledContent { TextField("Name", text: $myName).multilineTextAlignment(.trailing).onSubmit { model.rename(to: myName) } } label: { Label("Display Name", systemImage: "person.crop.circle").lineLimit(1).fixedSize(horizontal: true, vertical: false) }.selectionDisabled()
                    LabeledContent { Text(cloud == nil ? "Checking…" : cloud == true ? "On" : "Off") } label: { Label("iCloud Notices", systemImage: "icloud") }.selectionDisabled()
                    Picker(selection: $appearance) {
                        Text("Automatic").tag(0); Text("Light").tag(1); Text("Dark").tag(2)
                    } label: { Label("Appearance", systemImage: "circle.lefthalf.filled") }
                    Button { open(UIApplication.openNotificationSettingsURLString) } label: { Label("Notifications", systemImage: "bell.badge") }
                } header: { Text("This iPhone") } footer: {
                    Text(cloud == false ? "Sign in to iCloud in the Settings app to be told when someone asks to join your blinds, even when Tilt is closed." : "Your display name is what other people see in People and when you ask to join their blinds. iCloud tells you when someone asks to join yours.")
                }
                // Never in an App Store build; also hidden when launched with "-demo" for App Store screenshots.
                if developerBuild && !ProcessInfo.processInfo.arguments.contains("-demo") {
                    Section {
                        Toggle(isOn: $devMode) { Label("Developer Mode", systemImage: "chevron.left.forwardslash.chevron.right") }
                        if devMode {
                            Toggle("Beta Firmware", isOn: $firmwareBeta)
                            TextField("Firmware list address", text: $firmwareSource, prompt: Text("Default (GitHub releases)")).textInputAutocapitalization(.never).autocorrectionDisabled().keyboardType(.URL)
                        }
                    } footer: {
                        Text("Shows sensor readings, motor tuning, logs and Install from File in each controller's settings. Beta Firmware offers beta releases.")
                    }
                }
                Section {
                    Button("Erase Tilt on This iPhone", role: .destructive) { confirmErase = true }
                        .confirmationDialog("Erase Tilt on this iPhone?", isPresented: $confirmErase, titleVisibility: .visible) {
                            Button("Erase", role: .destructive) { model.eraseAll() }
                        } message: { Text("Every device and key on this iPhone is removed. Set the controllers up again from Add.") }
                } footer: { Text("Removes every controller, key and unfinished setup from this iPhone. This iPhone stays connected to the Tilt Hub (remove that on the hub's page). Your controllers and the hub are not touched.") }
                Section("About") {
                    LabeledContent("Version", value: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "").selectionDisabled()
                }
            }
            .listRowBackground(RowGlass())      // the same glass rows on a phone and in the side column
        }
            .listStyle(.insetGrouped)
            .skyPage()
            .navigationTitle("Settings")
            .onAppear { if wide == .regular, selected == nil { selected = model.controllers.first?.id } }
            .task { cloud = await Cloud.signedIn() }
            .onAppear { myName = AppModel.myName }
            .onDisappear { if myName != AppModel.myName { model.rename(to: myName) } }
            .sheet(isPresented: $adding) { AddControllerSheet().presentationDetents([.medium, .large]).presentationDragIndicator(.visible) }
        } detail: {
            NavigationStack {
                if selected == Self.hubTag, hub.status == .connected { HubView() }
                else if let c = model.controllers.first(where: { $0.id == selected }) { ControllerSettingsView(controller: c).id(c.id) }
                else { ContentUnavailableView("Pick a Device", systemImage: "blinds.horizontal.closed", description: Text("Its blinds, people and Apple Home settings show here.")).skyPage() }
            }
        }
        .onChange(of: hub.status == .connected) { _, on in let gone = !on; if gone, selected == Self.hubTag { selected = wide == .regular ? model.controllers.first?.id : nil } }
        .onChange(of: model.controllers.count) { _, _ in if selected != Self.hubTag, !model.controllers.contains(where: { $0.id == selected }) { selected = wide == .regular ? model.controllers.first?.id : nil } }
    }
    /// The Tilt Hub's row in the device list (controllers are picked by their id).
    static let hubTag = "tilt-hub"
    /// The picked device's row is tinted in the side column; on a phone every row is plain glass.
    @ViewBuilder private func rowBackground(_ tag: String) -> some View {
        if wide == .regular, selected == tag { Palette.accent.opacity(0.22) } else { RowGlass() }
    }
    private func open(_ s: String) { if let u = URL(string: s) { UIApplication.shared.open(u) } }
}
