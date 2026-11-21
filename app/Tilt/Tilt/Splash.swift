// The opening moment: a closed blind fills the screen, tilts open, and shows the name.
import SwiftUI

struct SplashSlats: View, Animatable {
    var closed: Double                                   // 1 shut … 0 open
    var animatableData: Double { get { closed } set { closed = newValue } }
    var body: some View {
        Canvas { ctx, size in
            let n = 13, pitch = size.height / CGFloat(n)
            let thick = pitch * (0.07 + 1.0 * closed)
            for i in 0..<n {
                let cy = pitch * (CGFloat(i) + 0.5)
                let r = CGRect(x: 6, y: cy - thick / 2, width: size.width - 12, height: thick)
                let p = Path(roundedRect: r, cornerRadius: min(5, thick / 2))
                ctx.fill(p.offsetBy(dx: 0, dy: -(2 + 3 * closed)), with: .color(.black.opacity(0.14 + 0.1 * closed)))
                ctx.fill(p, with: .linearGradient(Gradient(colors: [Color(red: 0.84, green: 0.83, blue: 0.80), Color(red: 0.98, green: 0.97, blue: 0.95)]),
                                                  startPoint: CGPoint(x: 0, y: r.minY), endPoint: CGPoint(x: 0, y: r.maxY)))
            }
        }
        .ignoresSafeArea()
    }
}

struct SplashView: View {
    let done: () -> Void
    @Environment(\.accessibilityReduceMotion) private var calm
    @State private var closed = 1.0
    @State private var leaving = false

    var body: some View {
        ZStack {
            AppBackground()
            VStack(spacing: 10) {
                Text("Tilt").font(.system(size: 76, weight: .heavy, design: .rounded)).kerning(-1)
                Text("Let the light in").font(.title3.weight(.medium)).foregroundStyle(.secondary)
            }
            .scaleEffect(0.9 + 0.1 * (1 - closed))
            SplashSlats(closed: closed).opacity(0.25 + 0.75 * closed)
        }
        .opacity(leaving ? 0 : 1)
        .task {
            if calm { closed = 0 } else {
                try? await Task.sleep(for: .milliseconds(350))
                withAnimation(.easeInOut(duration: 1.25)) { closed = 0 }
            }
            try? await Task.sleep(for: .milliseconds(calm ? 900 : 2100))
            withAnimation(.easeOut(duration: 0.45)) { leaving = true }
            try? await Task.sleep(for: .milliseconds(460))
            done()
        }
        .accessibilityHidden(true)
    }
}
