// The launch switches (Tilt/Launch.swift): on only in a developer build, and a test run only in a simulator.
import XCTest
@testable import Tilt

final class LaunchTests: XCTestCase {
    private func launch(_ args: [String], developer: Bool = true, simulator: Bool = true) -> Launch {
        Launch(arguments: ["Tilt"] + args, developerBuild: developer, simulator: simulator)
    }

    func testATestRunIsOnInADeveloperBuildInASimulator() {
        XCTAssertTrue(launch(["-testrun"]).testRun)
    }
    func testATestRunIsOffInAnAppStoreBuildAndOnARealIPhone() {
        XCTAssertFalse(launch(["-testrun"], developer: false).testRun)
        XCTAssertFalse(launch(["-testrun"], simulator: false).testRun)
    }
    func testEachSwitchTurnsOnlyItselfOn() {
        let demo = launch(["-demo"]), slats = launch(["-slatdemo"]), wizard = launch(["-wizarddemo"])
        XCTAssertEqual([demo.demo, demo.slatDemo, demo.wizardDemo, demo.testRun], [true, false, false, false])
        XCTAssertEqual([slats.demo, slats.slatDemo, slats.wizardDemo, slats.testRun], [false, true, false, false])
        XCTAssertEqual([wizard.demo, wizard.slatDemo, wizard.wizardDemo, wizard.testRun], [false, false, true, false])
    }
    func testNoArgumentsNoSwitch() {
        let l = launch([])
        XCTAssertEqual([l.demo, l.slatDemo, l.wizardDemo, l.testRun], [false, false, false, false])
    }
    func testNoSwitchInAnAppStoreBuild() {
        let l = launch(["-demo", "-slatdemo", "-wizarddemo", "-testrun"], developer: false)
        XCTAssertEqual([l.demo, l.slatDemo, l.wizardDemo, l.testRun], [false, false, false, false])
    }
    func testThisRunIsATestRun() {
        XCTAssertTrue(Launch.current.testRun, "the scheme's Test action starts the app with -testrun")
    }
}
