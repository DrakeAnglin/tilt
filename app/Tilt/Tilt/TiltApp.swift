import AuthenticationServices
import SwiftUI
import UserNotifications

/// iCloud's notices arrive as push notifications: the app has to register for them.
final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        application.registerForRemoteNotifications()
        return true
    }
    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {}
    /// Info.plist allows every orientation (Apple requires that for iPad multitasking). A screen with room turns
    /// freely (iPad, a Duo opened flat); an ordinary iPhone screen is too short for the app in landscape, so it stays
    /// upright.
    func application(_ application: UIApplication, supportedInterfaceOrientationsFor window: UIWindow?) -> UIInterfaceOrientationMask {
        let screen = window?.windowScene?.screen.bounds.size ?? .zero
        return min(screen.width, screen.height) >= 600 ? .all : .portrait
    }
}

@main
struct TiltApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @State private var model = AppModel()
    @State private var discovery = Discovery()
    @State private var hub = HubWatch.shared
    @Environment(\.scenePhase) private var phase
    init() { UNUserNotificationCenter.current().delegate = NoticePresenter.shared }

    var body: some Scene {
        WindowGroup {
            if developerBuild && ProcessInfo.processInfo.arguments.contains("-slatdemo") {
                HStack { SlatView(tilt: -100); SlatView(tilt: -55); SlatView(tilt: 55); SlatView(tilt: 100) }.frame(height: 260).padding(8).frame(maxHeight: .infinity).background(AppBackground())
            } else {
            RootView()
                .environment(model)
                .environment(discovery)
                .environment(hub)
                .onChange(of: phase, initial: true) { _, p in
                    if p == .active { model.startAll(); discovery.start(); hub.start() } else if p == .background { model.stopAll(); discovery.stop(); hub.stop(); BatteryAlerts.scheduleRefresh() }
                }
                .onChange(of: discovery.found) { _, f in model.noteFound(f) }
                .alert("Tilt Hub", isPresented: Binding(get: { hub.notice != nil }, set: { if !$0 { hub.notice = nil } })) { Button("OK") {} } message: { Text(hub.notice ?? "") }
            }
        }
        .backgroundTask(.appRefresh(BatteryAlerts.refreshId)) { await BatteryAlerts.backgroundCheck() }
    }
}

struct RootView: View {
    @Environment(AppModel.self) private var model
    @AppStorage(Prefs.appearance) private var appearance = 0
    @State private var splash = true
    @State private var later: Set<String> = []
    /// Developer builds, for screenshots: "-tab 1" starts on Automations, "-demo" adds the demo room.
    @State private var tab = developerBuild ? UserDefaults.standard.integer(forKey: "tab") : 0
    @State private var join: JoinAsk?
    @State private var needName = AppModel.savedName == nil
    /// Requests to join the controllers this phone owns.
    private var pending: [JoinAsk] { model.controllers.flatMap { c in c.requests.map { JoinAsk(controller: c, phone: $0) } } }
    /// Show the next request that has not been answered or swiped away.
    private func showNext() {
        if let j = join { if pending.contains(where: { $0.id == j.id }) { return }; join = nil }
        if !splash, !needName { join = pending.first { !later.contains($0.id) }; if let j = join { later.insert(j.id) } }
    }
    @State private var wizardDemo = developerBuild && ProcessInfo.processInfo.arguments.contains("-wizarddemo")

    var body: some View {
        // Tapping the Blinds tab while already on it goes back to the home page (all rooms).
        TabView(selection: Binding(get: { tab }, set: { if $0 == 0 && tab == 0 { NotificationCenter.default.post(name: .tiltBlindsHome, object: nil) }; tab = $0 })) {
            Tab("Blinds", systemImage: "blinds.horizontal.closed", value: 0) { BlindsTab() }
            Tab("Automations", systemImage: "clock", value: 1) { AutomationsTab() }
            Tab("Settings", systemImage: "gearshape", value: 2) { SettingsTab() }
        }
        .background(AppBackground().ignoresSafeArea())      // the sky behind the status bar too, not a white strip
        .overlay { if splash { SplashView { splash = false } } }
        // For mock-ups: launch with "-wizarddemo" to open the blind setup screen straight away.
        .sheet(isPresented: Binding(get: { !splash && wizardDemo && model.controllers.first != nil }, set: { if !$0 { wizardDemo = false } })) {
            if let c = model.controllers.first { SetupWizard(controller: c, index: 0, name: c.state?.b.first?.name ?? "Blind 1") }
        }
        .onAppear { if developerBuild && ProcessInfo.processInfo.arguments.contains("-demo") { model.addDemo() } }
        .preferredColorScheme(appearance == 1 ? .light : appearance == 2 ? .dark : nil)
        // First time: who is this? (So other people see a name, not "iPhone".)
        .sheet(isPresented: Binding(get: { !splash && needName }, set: { if !$0 { needName = false } })) { WelcomeSheet { needName = false }.presentationDetents([.height(400)]).interactiveDismissDisabled() }
        // A phone asked to join a controller this phone owns: a page to approve or decline it.
        .sheet(item: $join, onDismiss: { showNext() }) { a in JoinSheet(ask: a) { join = nil }.presentationDetents([.height(480)]) }
        .onChange(of: pending.map(\.id), initial: true) { _, _ in showNext() }
        .onChange(of: splash) { _, _ in showNext() }
        .onChange(of: needName) { _, _ in showNext() }
        .alert("Tilt", isPresented: Binding(get: { !splash && model.notice != nil }, set: { if !$0 { model.notice = nil } })) { Button("OK") {} } message: { Text(model.notice ?? "") }
        .onReceive(NotificationCenter.default.publisher(for: .tiltJoinTapped)) { _ in later = []; showNext() }
    }
}

struct JoinAsk: Identifiable {
    let controller: Controller, phone: PhoneKey
    var id: String { phone.cid }
}
extension Notification.Name {
    static let tiltJoinTapped = Notification.Name("tilt.join.tapped")
    static let tiltBlindsHome = Notification.Name("tilt.blinds.home")
}

/// Approve or decline a phone that asked to join.
struct JoinSheet: View {
    let ask: JoinAsk
    let done: () -> Void
    @State private var busy = false
    @State private var owner = false
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "person.crop.circle.badge.questionmark").font(.system(size: 44)).foregroundStyle(.tint)
            Text("\(ask.phone.name) wants to join").font(.title2.weight(.semibold))
            Text(ask.controller.state?.name ?? ask.controller.record.name).foregroundStyle(.secondary)
            Text(ask.phone.code ?? "").font(.system(size: 46, weight: .bold, design: .rounded).monospacedDigit()).kerning(6).padding(.vertical, 4)
            Text("Their phone must show this same code. If it does not match, decline.")
                .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
            Picker("Role", selection: $owner) { Text("Guest").tag(false); Text("Owner").tag(true) }.pickerStyle(.segmented)
            Text(owner ? "An owner can also change settings, set up blinds, make schedules, and approve or remove people." : "A guest can open and close the blinds. Nothing else.")
                .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center).frame(minHeight: 34)
            HStack(spacing: 12) {
                Button(role: .destructive) { answer(false) } label: { Text("Decline").frame(maxWidth: .infinity) }.buttonStyle(.bordered)
                Button { answer(true) } label: { Text("Approve").frame(maxWidth: .infinity) }.buttonStyle(.borderedProminent)
            }
            .controlSize(.large).disabled(busy)
        }
        .padding(24)
    }
    private func answer(_ ok: Bool) {
        busy = true
        Task { await ask.controller.answer(ask.phone, approve: ok, owner: owner); done() }
    }
}

/// Asked once: the person's name, from their Apple Account with one tap.
struct WelcomeSheet: View {
    @Environment(AppModel.self) private var model
    let done: () -> Void
    @State private var name = ""
    @State private var note: String?
    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: "person.crop.circle").font(.system(size: 44)).foregroundStyle(.tint)
            Text("Welcome to Tilt").font(.title2.weight(.semibold))
            Text("People you share blinds with see your name. Tilt keeps nothing else about you.")
                .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
            SignInWithAppleButton(.continue) { $0.requestedScopes = [.fullName] } onCompletion: { result in
                guard case .success(let auth) = result, let c = auth.credential as? ASAuthorizationAppleIDCredential else { return }
                let n = c.fullName.map { PersonNameComponentsFormatter.localizedString(from: $0, style: .default) } ?? ""
                if n.trimmingCharacters(in: .whitespaces).isEmpty { note = "Apple did not share your name this time. Enter it once here." } else { save(n) }
            }
            .frame(height: 50)
            if let note {                       // only if Apple gave no name (it shares it the first time only)
                Text(note).font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
                HStack {
                    TextField("First and last name", text: $name).textInputAutocapitalization(.words).autocorrectionDisabled().textFieldStyle(.roundedBorder).onSubmit { save(name) }
                    Button("Save") { save(name) }.buttonStyle(.bordered).disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
        }
        .padding(24)
    }
    private func save(_ n: String) {
        guard !n.trimmingCharacters(in: .whitespaces).isEmpty else { return }
        model.rename(to: n)
        done()
    }
}
