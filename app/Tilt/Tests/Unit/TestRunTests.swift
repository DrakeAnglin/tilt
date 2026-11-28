// The app in a test run (-testrun, from the scheme's Test action): nothing from an earlier run, no iCloud.
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
}
