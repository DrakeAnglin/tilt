// The app in a test run (-testrun, from the scheme's Test action): nothing from an earlier run, no iCloud.
import CryptoKit
import XCTest
@testable import Tilt

@MainActor
final class TestRunTests: XCTestCase {
    func testAFreshStartForgetsTheRoomsOfTheRunBefore() {
        Launch.current.startFresh()
        let before = AppModel()
        before.addDemo()
        XCTAssertEqual(AppModel().controllers.count, 1, "a room is saved")
        Launch.current.startFresh()
        XCTAssertTrue(AppModel().controllers.isEmpty)
        before.remove(before.controllers[0])
    }
    func testAnAppStoreLaunchKeepsTheSavedRooms() {
        Launch.current.startFresh()
        let model = AppModel()
        model.addDemo()
        Launch(arguments: ["Tilt", "-testrun"], developerBuild: false, simulator: true).startFresh()
        XCTAssertEqual(AppModel().controllers.count, 1)
        model.remove(model.controllers[0])
    }
    func testTheModelStartsWithNoControllerAndTakesTheDemoRoomOnce() {
        Launch.current.startFresh()
        let model = AppModel()
        XCTAssertTrue(model.controllers.isEmpty)
        XCTAssertFalse(model.hasDemo)
        model.addDemo()
        XCTAssertEqual(model.controllers.map(\.record.name), ["Living Room (Demo)"])
        XCTAssertTrue(model.hasDemo)
        model.addDemo()
        XCTAssertEqual(model.controllers.count, 1)
        model.remove(model.controllers[0])
    }
    func testNotSignedInToICloud() async {
        let signedIn = await Cloud.signedIn()
        XCTAssertFalse(signedIn)
    }
    /// Each call returns at once: making a CloudKit container in an unsigned or account-less run would crash.
    func testEveryICloudCallReturnsWithoutAContainer() async {
        await Cloud.postJoin(topic: "t", cid: "c", who: "w", room: "r")
        await Cloud.clearJoin(cid: "c")
        await Cloud.watch(topic: "t")
        await Cloud.watchAlerts(topic: "t")
        UserDefaults.standard.set(true, forKey: "cloud.watch.t")
        await Cloud.unwatch(topic: "t")
        XCTAssertTrue(UserDefaults.standard.bool(forKey: "cloud.watch.t"), "nothing was asked of iCloud")
        UserDefaults.standard.removeObject(forKey: "cloud.watch.t")
        await Cloud.postGone(cid: "c", proof: "p")
        let gone = await Cloud.gone(cid: "c", key: .init(size: .bits256))
        XCTAssertFalse(gone)
    }
    func testNoNameIsReadFromICloud() {
        Launch.current.startFresh()
        XCTAssertNil(AppModel.savedName)
    }
    func testBluetoothSetupAsksNothingOfBluetooth() {
        let ble = BleSetup()
        ble.start()
        RunLoop.main.run(until: Date().addingTimeInterval(1))      // time for the radio to answer, if it were asked
        XCTAssertNil(ble.problem, "no Bluetooth manager was made, so none said the simulator has no Bluetooth")
        ble.stop()
    }
}
