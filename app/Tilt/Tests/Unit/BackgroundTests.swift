// The page background (Tilt/Theme.swift): it draws in both modes.
import SwiftUI
import XCTest
@testable import Tilt

@MainActor
final class BackgroundTests: XCTestCase {
    private func drawn(_ scheme: ColorScheme) -> UIImage? {
        ImageRenderer(content: AppBackground().environment(\.colorScheme, scheme).frame(width: 60, height: 120)).uiImage
    }
    func testTheBackgroundDrawsInLightAndDarkMode() {
        let light = drawn(.light), dark = drawn(.dark)
        XCTAssertNotNil(light)
        XCTAssertNotNil(dark)
        XCTAssertNotEqual(light?.pngData(), dark?.pngData(), "dark mode is the sky, light mode stock iOS")
    }
}
