// Why a Scene could not be saved, as the person reads it (Shared/ScenePlan.swift).
import XCTest
@testable import Tilt

final class ScenePlanTests: XCTestCase {
    private func words(_ p: PlanProblem) -> String {
        let e = ScenePlan.problem(p, name: { $0 == "k" ? "Kitchen" : "?" })
        return (e as? LocalizedError)?.errorDescription ?? "\(e)"
    }
    func testAFullControllerSaysHowManyScenesItHolds() {
        XCTAssertEqual(words(.full(controller: "k")), "Kitchen already has 16 scenes.")
    }
    func testAControllerThatDidNotAnswerSaysSo() {
        XCTAssertEqual(words(.notRead(controller: "k")), "Kitchen did not answer. Try again when it is reachable.")
    }
    func testAnyOtherProblemIsPassedOn() {
        XCTAssertEqual(ScenePlan.problem(.noLight(controller: "k"), name: { $0 }) as? PlanProblem, .noLight(controller: "k"))
    }
}
