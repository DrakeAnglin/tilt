// The app as a person sees it, in a test run (-testrun): the demo room on the Blinds tab, nothing in front of it, and
// nothing kept from one launch to the next.
import XCTest

final class DemoRoomUITests: XCTestCase {
    override func setUp() { continueAfterFailure = false }

    private func launch() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-testrun"]
        app.launch()
        return app
    }
    /// The demo room's card on the Blinds tab.
    private func room(_ app: XCUIApplication) -> XCUIElement { app.staticTexts["Living Room (Demo)"] }
    /// The room's one-line summary under its name, starting with these words.
    private func says(_ app: XCUIApplication, _ words: String) -> XCUIElement {
        app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH %@", words)).firstMatch
    }

    func testTheDemoRoomShowsWithNothingInFrontAndMoves() {
        let app = launch()
        XCTAssertTrue(room(app).waitForExistence(timeout: 20), "the demo room is on the Blinds tab")
        XCTAssertFalse(app.staticTexts["Welcome to Tilt"].exists, "no name sheet")
        app.buttons["Close"].firstMatch.tap()
        XCTAssertTrue(says(app, "Closed").waitForExistence(timeout: 20), "the room says Closed")
        app.buttons["Open"].firstMatch.tap()
        XCTAssertTrue(says(app, "Open").waitForExistence(timeout: 20), "the room says Open")
    }

    func testDeveloperModeIsOfferedInADeveloperBuild() {
        let app = launch()
        XCTAssertTrue(room(app).waitForExistence(timeout: 20))
        app.tabBars.buttons["Settings"].tap()
        XCTAssertTrue(app.switches["Developer Mode"].waitForExistence(timeout: 10), "hidden only with -demo")
    }

    func testNothingIsKeptFromTheLastRun() {
        var app = launch()
        XCTAssertTrue(room(app).waitForExistence(timeout: 20))
        app.buttons["Close"].firstMatch.tap()
        XCTAssertTrue(says(app, "Closed").waitForExistence(timeout: 20))
        app.terminate()
        app = launch()
        XCTAssertTrue(room(app).waitForExistence(timeout: 20))
        XCTAssertEqual(app.staticTexts.matching(identifier: "Living Room (Demo)").count, 1, "the demo room is there once")
        XCTAssertTrue(says(app, "Mixed tilts").waitForExistence(timeout: 20), "the demo room as it starts, not as it was left")
    }
}
