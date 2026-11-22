// Tilt's colors, in one place. Screens use these names, never raw colors, so the app looks the same everywhere and a
// change of look is made here once. (The sky and the blind pictures draw their own scenery in Theme.swift and
// SlatView.swift: those are illustrations, not interface colors.)
//
// The look, decided here and nowhere else:
//   Light mode is stock iOS: Apple's grouped background, white rows, and only a faint wash of today's sky at the top.
//   Dark mode is the sky outside right now, with see-through panels over it.
// In both, every surface is Apple's Liquid Glass: cards, list rows, buttons, bars (Theme.swift: card(), RowGlass).
// `surface` is only for small flat things (a badge, a panel inside a sheet).
import SwiftUI
import UIKit

enum Palette {
    // ---- meaning
    /// Buttons, links, selected things (the app's teal, from the asset catalog).
    static let accent = Color.accentColor
    /// Text and icons on an accent-colored background.
    static let onAccent = Color.white
    /// Done, charging, connected.
    static let good = Color.green
    /// Needs attention: low battery, not reachable, a step that failed.
    static let warning = Color.orange
    /// Stop, remove, delete.
    static let danger = Color.red

    // ---- pages and surfaces. Light mode: stock iOS. Dark mode: see-through over the night sky.
    /// Behind every page (light mode; in dark mode the sky is drawn instead).
    static let page = Color(uiColor: .systemGroupedBackground)
    /// List rows, small cards and panels: white like stock iOS in light mode, see-through over the sky in dark mode.
    static let surface = Color(light: .secondarySystemGroupedBackground, dark: UIColor(white: 1, alpha: 0.09))
    /// Something you can pick that is not picked: day buttons, icon choices, a hold-to-turn pad at rest.
    static let fill = Color(light: .tertiarySystemFill, dark: UIColor(white: 1, alpha: 0.12))
    /// The same, picked.
    static let fillSelected = Color.accentColor.opacity(0.25)
    /// Light mode: the tint on glass rows, so they stand out from the light grey page.
    static let glassTint = Color.white.opacity(0.75)
    /// Behind a QR code: always solid white, or cameras cannot read it.
    static let codeBackground = Color.white
}

extension Color {
    /// A color that differs between light and dark mode.
    init(light: UIColor, dark: UIColor) {
        self.init(uiColor: UIColor { $0.userInterfaceStyle == .dark ? dark : light })
    }
}
