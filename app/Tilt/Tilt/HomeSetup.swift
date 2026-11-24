// Adding the Tilt Hub (or a controller with no hub) to Apple Home from the app, in one tap: Apple's own add screen
// opens with the code already filled in (issue #50). The code goes in as a Matter setup payload, which needs the
// unrestricted entitlement com.apple.developer.matter.allow-setup-payload. HomeKit's own `payload` field is only for
// makers in Apple's MFi program: for anyone else it fails, so it is never used.
// App only (not the widget). The Mac tests build it too: HomeKit is not in the Mac's SDK, so there they check only
// `payload`; the request itself is checked in the iPhone simulator (tools/app_tests.sh).
import Foundation
import Matter
#if canImport(HomeKit)
import HomeKit
#endif

enum HomeSetup {
    /// A device's code for Apple Home: the typed code and the QR text. Shown when Apple's own add screen could not open
    /// (`note` says why) or when asked for.
    struct Code: Identifiable { let code: String; let qr: String; var hub = false; var inHome = false; var note: String? = nil; var id: String { qr } }

    /// The Matter setup payload from the QR text ("MT:…"). Nil if it is not a good Matter code, or if its passcode is
    /// not the one in the typed code (the backup the app shows): then the app shows the code to add by hand instead.
    static func payload(qr: String, code: String) -> MTRSetupPayload? {
        guard qr.hasPrefix("MT:"), let p = MTRSetupPayload(payload: qr) else { return nil }
        let typed = code.filter(\.isNumber)
        if !typed.isEmpty {
            guard let m = MTRSetupPayload(payload: typed), m.setupPasscode == p.setupPasscode else { return nil }
        }
        return p
    }

    /// One of the hub's Matter home connections: the hub's own ID in it (hex) and the maker's number.
    struct HubHome: Sendable { let node: String?; let vendor: Int? }
    /// Apple's two Matter maker numbers: Apple (4937, 0x1349) and Apple Keychain (4996, 0x1384).
    static let appleVendors: Set<Int> = [4937, 4996]
    /// Amazon's Matter maker number (4631, 0x1217): an Alexa home.
    static let alexaVendors: Set<Int> = [4631]
    /// Is the Tilt Hub in Alexa? One of its Matter home connections was made by Amazon. (Alexa removes its connection
    /// when the hub is removed in the Alexa app.)
    static func inAlexa(hubHomes: [HubHome]) -> Bool { hubHomes.contains { $0.vendor.map(alexaVendors.contains) ?? false } }

    /// Is the Tilt Hub in Apple Home? The hub counts a home for each Matter home connection it has, but Apple adds two
    /// (the home and the iPhone's iCloud Keychain) and leaves the Keychain one when the hub is removed in the Home app.
    /// So when Apple Home's accessories can be seen (`appleNodes`: their Matter node IDs), the hub is in Home if one of
    /// them has the hub's ID in one of its connections, or if both of Apple's connections are still there (in case
    /// Apple's ID is not the one the hub has: Apple does not say). Otherwise (no Home access, or a hub too old to give
    /// its IDs) the hub's own word.
    static func inHome(hubSays: Bool, hubHomes: [HubHome], appleNodes: Set<UInt64>?) -> Bool {
        let ids = hubHomes.compactMap { $0.node.flatMap { UInt64($0, radix: 16) } }
        guard let apple = appleNodes, !ids.isEmpty else { return hubSays }
        if ids.contains(where: apple.contains) { return true }
        return hubHomes.filter { $0.vendor.map(appleVendors.contains) ?? false }.count >= 2
    }

    #if canImport(HomeKit)
    /// Apple's add-accessory request, the code in it as a Matter payload. Nil: see `payload`.
    static func request(qr: String, code: String, name: String?) -> HMAccessorySetupRequest? {
        guard let p = payload(qr: qr, code: code) else { return nil }
        let r = HMAccessorySetupRequest()
        r.matterPayload = p
        r.suggestedAccessoryName = name
        return r
    }

    /// Shown with the code when Apple's add screen could not open: the code was not a good Matter code, or Apple Home
    /// refused (Apple's own words go to the console, for a developer).
    static let badCode = "Apple Home could not use the code from the device."
    static let notOpened = "Apple Home could not open from here."

    /// A tap on "Add to Apple Home": Apple's own add screen, the code filled in. Returns the code to show instead when
    /// that screen could not open (`note` says why), or right away when `showCode`; nil when it is done (added, or
    /// closed by the person). `code` asks the hub or controller, which opens it to Apple Home for a few minutes. If
    /// the page that asked is closed meanwhile (its task canceled), Apple's screen does not open over another page.
    @MainActor
    static func start(name: String, showCode: Bool, code: () async throws -> HomeSetup.Code) async throws -> HomeSetup.Code? {
        var info = try await code()
        if showCode { return info }
        try Task.checkCancellation()
        guard let why = await add(qr: info.qr, code: info.code, name: name) else { return nil }
        info.note = why
        return info
    }

    /// Open Apple's add screen with the code filled in, and wait until the person is done with it. Nil when it is
    /// done (added, or closed by the person); otherwise why it could not open, to show with the code.
    @MainActor
    static func add(qr: String, code: String, name: String?) async -> String? {
        guard let r = request(qr: qr, code: code, name: name) else { return badCode }
        do {
            _ = try await HMAccessorySetupManager().performAccessorySetup(using: r)
            return nil
        } catch {
            if wasClosed(error) { return nil }
            NSLog("Tilt: Apple Home add failed: %@", String(describing: error))
            return notOpened
        }
    }

    /// The person closed Apple's add screen: nothing more to show.
    static func wasClosed(_ error: Error) -> Bool { (error as? HMError)?.code == .operationCancelled }
    #endif
}

#if canImport(HomeKit)
/// The accessories in the person's Apple homes, to see whether the Tilt Hub is really there (`HomeSetup.inHome`).
/// iOS asks for Home access the first time `start()` runs, which is when the Tilt Hub page opens, not before.
@MainActor
final class AppleHomes: NSObject, HMHomeManagerDelegate {
    static let shared = AppleHomes()
    private var manager: HMHomeManager?
    private var loaded = false                    // Apple Home answered (with its homes, or with no access)

    func start() {
        guard manager == nil else { return }
        let m = HMHomeManager()
        m.delegate = self
        manager = m
    }
    /// Wait (up to 3 s) for Apple Home's first answer after `start()`.
    func ready() async {
        var waited = 0
        while manager != nil && !loaded && waited < 30 { try? await Task.sleep(for: .milliseconds(100)); waited += 1 }
    }
    /// The Matter node IDs of every accessory in every home. Nil: not started, no Home access, or no answer yet.
    var nodeIDs: Set<UInt64>? {
        guard let m = manager, loaded, m.authorizationStatus.contains(.authorized) else { return nil }
        return Set(m.homes.flatMap(\.accessories).compactMap(\.matterNodeID))
    }
    nonisolated func homeManagerDidUpdateHomes(_ manager: HMHomeManager) {
        Task { @MainActor in self.loaded = true }
    }
    /// The person answered the Home access question (or had before): with no access there are no homes to wait for.
    nonisolated func homeManager(_ manager: HMHomeManager, didUpdate status: HMHomeManagerAuthorizationStatus) {
        Task { @MainActor in if status.contains(.determined) && !status.contains(.authorized) { self.loaded = true } }
    }
}
#endif
