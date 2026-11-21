import SwiftUI
import UserNotifications

@main
struct TiltApp: App {
    @State private var model = AppModel()
    @State private var discovery = Discovery()
    @Environment(\.scenePhase) private var phase
    init() { UNUserNotificationCenter.current().delegate = NoticePresenter.shared }

    var body: some Scene {
        WindowGroup {
            if ProcessInfo.processInfo.arguments.contains("-slatdemo") {
                HStack { SlatView(tilt: -100); SlatView(tilt: -55); SlatView(tilt: 55); SlatView(tilt: 100) }.frame(height: 260).padding(8).frame(maxHeight: .infinity).background(AppBackground())
            } else {
            RootView()
                .environment(model)
                .environment(discovery)
                .onChange(of: phase, initial: true) { _, p in
                    if p == .active { model.startAll(); discovery.start() } else if p == .background { model.stopAll(); discovery.stop(); BatteryAlerts.scheduleRefresh() }
                }
                .onChange(of: discovery.found) { _, f in model.noteFound(f) }
            }
        }
        .backgroundTask(.appRefresh(BatteryAlerts.refreshId)) { await BatteryAlerts.backgroundCheck() }
    }
}

struct RootView: View {
    @Environment(AppModel.self) private var model
    @State private var notice: String?
    @AppStorage("appearance") private var appearance = 0
    @State private var splash = true
    @State private var wizardDemo = ProcessInfo.processInfo.arguments.contains("-wizarddemo")

    var body: some View {
        TabView {
            Tab("Blinds", systemImage: "blinds.horizontal.closed") { BlindsTab() }
            Tab("Automations", systemImage: "clock") { AutomationsTab() }
            Tab("Settings", systemImage: "gearshape") { SettingsTab() }
        }
        .overlay { if splash { SplashView { splash = false } } }
        // For mock-ups: launch with "-wizarddemo" to open the blind setup screen straight away.
        .sheet(isPresented: Binding(get: { !splash && wizardDemo && model.controllers.first != nil }, set: { if !$0 { wizardDemo = false } })) {
            if let c = model.controllers.first { SetupWizard(controller: c, index: 0, name: c.state?.b.first?.name ?? "Blind 1") }
        }
        .preferredColorScheme(appearance == 1 ? .light : appearance == 2 ? .dark : nil)
        // A sharing link (from a QR code or a message): tilt://join?…
        .onOpenURL { url in
            guard let invite = Invite(link: url.absoluteString) else { notice = "That sharing link is not valid."; return }
            Task {
                do { try await model.add(host: invite.host, invite: invite); notice = "Added. You can now control these blinds." }
                catch { notice = error.localizedDescription }
            }
        }
        .alert("Tilt", isPresented: Binding(get: { notice != nil }, set: { if !$0 { notice = nil } })) { Button("OK") {} } message: { Text(notice ?? "") }
    }
}
