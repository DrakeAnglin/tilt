// Tilt's colors (Shared/Design.swift): the two-mode ones differ between light and dark mode, and every name resolves.
import SwiftUI
import XCTest
@testable import Tilt

final class PaletteTests: XCTestCase {
    private func resolved(_ c: Color, _ style: UIUserInterfaceStyle) -> UIColor {
        UIColor(c).resolvedColor(with: UITraitCollection(userInterfaceStyle: style))
    }

    func testSurfaceAndFillDifferBetweenLightAndDark() {
        for c in [Palette.surface, Palette.fill] {
            XCTAssertNotEqual(resolved(c, .light), resolved(c, .dark))
        }
    }
    func testAColorMadeForBothModesGivesEachItsOwn() {
        let c = Color(light: .red, dark: .blue)
        XCTAssertEqual(resolved(c, .light), UIColor.red.resolvedColor(with: UITraitCollection(userInterfaceStyle: .light)))
        XCTAssertEqual(resolved(c, .dark), UIColor.blue.resolvedColor(with: UITraitCollection(userInterfaceStyle: .dark)))
    }
    func testEveryNameResolves() {
        let all = [Palette.accent, Palette.onAccent, Palette.good, Palette.warning, Palette.danger, Palette.page,
                   Palette.surface, Palette.fill, Palette.fillSelected, Palette.glassTint, Palette.codeBackground]
        for c in all {
            var a: CGFloat = -1
            XCTAssertTrue(resolved(c, .light).getRed(nil, green: nil, blue: nil, alpha: &a))
            XCTAssertGreaterThan(a, 0)
        }
    }
}
