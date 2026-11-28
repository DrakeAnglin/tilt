// The system Keychain, as the app uses it (Shared/Store.swift).
import XCTest
@testable import Tilt

final class KeychainTests: XCTestCase {
    private let account = "tests-\(UUID().uuidString)"
    override func tearDown() { SystemKeychain.delete(account) }

    func testWhatIsSavedLoadsBack() {
        SystemKeychain.save(account, Data([1, 2, 3]))
        XCTAssertEqual(SystemKeychain.load(account), Data([1, 2, 3]))
    }
    func testASecondSaveReplacesTheFirst() {
        SystemKeychain.save(account, Data([1, 2, 3]))
        SystemKeychain.save(account, Data([9]))
        XCTAssertEqual(SystemKeychain.load(account), Data([9]))
    }
    func testDeleteLeavesNothing() {
        SystemKeychain.save(account, Data([1]))
        SystemKeychain.delete(account)
        XCTAssertNil(SystemKeychain.load(account))
    }
}
