// The opening moment, on a cold start only: a closed blind fills the screen, tilts open and shows the name, and the
// app takes over as soon as the first controller has answered (never less than 1.1 s on screen, never more than 2 s).
// Also here: SlatLoader, the icon's three slats tilting, used wherever the app is waiting for something.
import SwiftUI

/// A whole-screen blind: head rail, slats, two ladder cords, bottom rail.
struct SplashSlats: View, Animatable {
    var closed: Double                                   // 1 shut … 0 open
    var animatableData: Double { get { closed } set { closed = newValue } }
    var body: some View {
        Canvas { ctx, size in
            let w = size.width, h = size.height
            let face = Color(red: 0.98, green: 0.97, blue: 0.95), shade = Color(red: 0.83, green: 0.82, blue: 0.79)
            let rail: CGFloat = 26, n = 13
            let top = rail + 6, bottom = h - 20
            let pitch = (bottom - top) / CGFloat(n)
            let thick = pitch * (0.07 + 1.0 * closed)
            // ladder cords behind the slats (they show between open slats)
            for x in [w * 0.22, w * 0.78] {
                ctx.stroke(Path { $0.move(to: CGPoint(x: x, y: rail)); $0.addLine(to: CGPoint(x: x, y: bottom)) }, with: .color(.white.opacity(0.75)), lineWidth: 2)
                ctx.stroke(Path { $0.move(to: CGPoint(x: x + 9, y: rail)); $0.addLine(to: CGPoint(x: x + 9, y: bottom)) }, with: .color(.white.opacity(0.45)), lineWidth: 1.2)
            }
            for i in 0..<n {
                let cy = top + pitch * (CGFloat(i) + 0.5)
                let r = CGRect(x: 6, y: cy - thick / 2, width: w - 12, height: thick)
                let p = Path(roundedRect: r, cornerRadius: min(5, thick / 2))
                ctx.fill(p.offsetBy(dx: 0, dy: -(2 + 3 * closed)), with: .color(.black.opacity(0.13 + 0.1 * closed)))
                ctx.fill(p, with: .linearGradient(Gradient(colors: [shade, face]), startPoint: CGPoint(x: 0, y: r.minY), endPoint: CGPoint(x: 0, y: r.maxY)))
                if closed > 0.3 {                          // the cords' rungs cross each slat's face when it is turned toward us
                    for x in [w * 0.22, w * 0.78] {
                        ctx.fill(Path(CGRect(x: x - 1, y: r.minY, width: 2, height: r.height)), with: .color(.black.opacity(0.07 * closed)))
                    }
                }
            }
            // head rail and bottom rail
            ctx.fill(Path(CGRect(x: 0, y: 0, width: w, height: rail)), with: .linearGradient(Gradient(colors: [face, shade]), startPoint: .zero, endPoint: CGPoint(x: 0, y: rail)))
            ctx.fill(Path(CGRect(x: 0, y: rail, width: w, height: 3)), with: .color(.black.opacity(0.12)))
            ctx.fill(Path(roundedRect: CGRect(x: 4, y: bottom, width: w - 8, height: 12), cornerRadius: 4), with: .linearGradient(Gradient(colors: [face, shade]), startPoint: CGPoint(x: 0, y: bottom), endPoint: CGPoint(x: 0, y: bottom + 12)))
        }
        .ignoresSafeArea()
    }
}

struct SplashView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.accessibilityReduceMotion) private var calm
    let done: () -> Void
    @State private var closed = 1.0
    @State private var leaving = false

    private var loaded: Bool { model.controllers.isEmpty || model.controllers.contains { $0.state != nil } }

    var body: some View {
        ZStack {
            AppBackground()
            VStack(spacing: 10) {
                Text("Tilt").font(.system(size: 76, weight: .heavy, design: .rounded)).kerning(-1)
                Text("Let the light in").font(.title3.weight(.medium)).foregroundStyle(.secondary)
            }
            .scaleEffect(0.82 + 0.18 * (1 - closed))          // the name comes toward you as the blind opens
            .scaleEffect(leaving ? 1.1 : 1)
            SplashSlats(closed: closed).opacity(0.22 + 0.78 * closed)
        }
        .opacity(leaving ? 0 : 1)
        .task {
            let start = Date()
            if calm { closed = 0 } else {
                try? await Task.sleep(for: .milliseconds(150))
                withAnimation(.spring(response: 0.62, dampingFraction: 0.86)) { closed = 0 }
            }
            while Date().timeIntervalSince(start) < 1.1 || (!loaded && Date().timeIntervalSince(start) < 2.0) {
                try? await Task.sleep(for: .milliseconds(50))
            }
            withAnimation(.easeIn(duration: 0.24)) { leaving = true }
            try? await Task.sleep(for: .milliseconds(250))
            done()
        }
        .accessibilityHidden(true)
    }
}

/// The icon's three slats, tilting open and shut: the app's one "working on it" sign. Use it everywhere instead of a
/// spinner.
/// Each slat turns about its long side, toward and away from you, like a real blind (never a seesaw or a slide in the
/// plane of the screen). The angle comes from the clock in a TimelineView, not from a repeating animation: a
/// repeating animation also catches the row's own layout as a list or form loads, which made the slats slide left and
/// right.
struct SlatLoader: View {
    var size: CGFloat = 44
    var label: String? = nil
    @Environment(\.accessibilityReduceMotion) private var calm
    var body: some View {
        VStack(spacing: size * 0.32) {
            TimelineView(.animation(paused: calm)) { tl in
                let t = tl.date.timeIntervalSinceReferenceDate
                VStack(spacing: size * 0.15) {
                    ForEach(0..<3, id: \.self) { i in
                        RoundedRectangle(cornerRadius: size * 0.04).fill(.tint)
                            .frame(width: size, height: size * 0.2)
                            .rotation3DEffect(.degrees(calm ? 40 : Self.tilt(t - 0.12 * Double(i))), axis: (x: 1, y: 0, z: 0), perspective: 0.4)
                    }
                }
            }
            .frame(width: size, height: size * 0.95)
            if let label { Text(label).font(.subheadline).foregroundStyle(.secondary) }
        }
        .accessibilityElement().accessibilityLabel(label ?? "Loading")
    }
    /// 8 degrees (nearly flat to you) to 72 (nearly edge-on) and back, every 1.4 s, eased at both ends.
    private static func tilt(_ t: Double) -> Double { 8 + 64 * (0.5 - 0.5 * cos(2 * .pi * t / 1.4)) }
}
