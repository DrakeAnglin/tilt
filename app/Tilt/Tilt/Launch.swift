// The launch switches, in one place. Each is off in an App Store build; a test run is also off on a real iPhone.
//   -demo        adds the demo room (for screenshots)
//   -slatdemo    shows four blind pictures and nothing else (for mock-ups)
//   -wizarddemo  opens the blind setup screen straight away (for mock-ups)
//   -testrun     the Xcode tests (TiltTests, TiltUITests): the app's saved settings are cleared at launch, the keys
//                stay in memory, and nothing is asked of the network, iCloud, Bonjour or Bluetooth. The demo room is
//                added, with no splash and no name sheet in front.
// Values such as "-tab 1" and "-skyminute" are read through UserDefaults (see RootView and Sky).
import Foundation

struct Launch: Equatable {
    var demo = false, slatDemo = false, wizardDemo = false, testRun = false

    init(arguments: [String], developerBuild: Bool, simulator: Bool) {
        guard developerBuild else { return }
        demo = arguments.contains("-demo")
        slatDemo = arguments.contains("-slatdemo")
        wizardDemo = arguments.contains("-wizarddemo")
        testRun = simulator && arguments.contains("-testrun")     // it clears saved settings: never a person's iPhone
    }

    /// A test run starts from nothing: the app's saved settings are cleared and the keys stay in memory. Values given
    /// as launch arguments ("-tab 1") are not saved settings and are still read. Does nothing in any other launch.
    func startFresh() {
        guard testRun else { return }
        if let id = Bundle.main.bundleIdentifier { UserDefaults.standard.removePersistentDomain(forName: id) }
        Keychain.store = MemoryKeychain.self
    }

    /// This launch.
    static let current = Launch(arguments: ProcessInfo.processInfo.arguments, developerBuild: developerBuild, simulator: isSimulator)
    static let isSimulator: Bool = {
        #if targetEnvironment(simulator)
        return true
        #else
        return false
        #endif
    }()
}
