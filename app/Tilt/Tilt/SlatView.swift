// The picture of a blind, seen from the front: a head rail, the slats, the cords, and daylight behind.
// Open: thin slats with the sky between them. Closing: the slats turn and fill the window.
import SwiftUI

struct SlatView: View, Animatable {
    /// -100 closed (slats down) … 0 open … +100 closed (slats up).
    var tilt: Double
    var known = true
    var slats = 9
    /// Which window of how many this is: blinds side by side in a room look out on ONE view (the sun is in one of them).
    var pane = 0
    var panes = 1

    var animatableData: Double {
        get { tilt }
        set { tilt = newValue }
    }

    var body: some View {
        Canvas { ctx, size in
            let w = size.width, h = size.height
            let frame = CGRect(origin: .zero, size: size)
            let closed = known ? min(abs(tilt), 100) / 100 : 0.0
            let look = Sky.look()
            let view = CGRect(x: -CGFloat(pane) * w, y: 0, width: w * CGFloat(max(panes, 1)), height: h)
            Sky.draw(look, in: &ctx, rect: view, starScale: max(0.6, w / 260), unit: w)
            if !known { ctx.fill(Path(frame), with: .color(.gray.opacity(0.45))) }

            // slats
            let rail = max(6, h * 0.055)
            let top = rail, bottom = h - rail * 0.7
            let pitch = (bottom - top) / CGFloat(slats)
            let thick = pitch * (0.16 + 0.92 * closed)                 // how much of each slat faces us
            let up = tilt >= 0
            let dim = 1 - 0.2 * look.stars                                 // a little dimmer at night
            let face = Color(red: 0.97 * dim, green: 0.96 * dim, blue: 0.93 * dim), shade = Color(red: 0.80 * dim, green: 0.79 * dim, blue: 0.76 * dim)
            // Closed down: each slat laps over the one below it, so draw from the bottom up.
            // Closed up: each slat laps over the one above it, so draw from the top down.
            let order = up ? Array(0..<slats) : Array((0..<slats).reversed())
            let lap: CGFloat = up ? -1 : 1                              // which way the front edge's shadow falls
            for i in order {
                let cy = top + pitch * (CGFloat(i) + 0.5)
                let r = CGRect(x: 2.5, y: cy - thick / 2, width: w - 5, height: thick)
                let p = Path(roundedRect: r, cornerRadius: min(3, thick / 2))
                ctx.fill(p.offsetBy(dx: 0, dy: lap * (1.5 + 1.5 * closed)), with: .color(.black.opacity(0.16 + 0.10 * closed)))   // shadow of the front edge on the next slat
                ctx.fill(p, with: .linearGradient(Gradient(colors: up ? [shade, face] : [face, shade]),
                                                  startPoint: CGPoint(x: 0, y: r.minY), endPoint: CGPoint(x: 0, y: r.maxY)))
                let edge = up ? r.minY + 0.6 : r.maxY - 0.6             // bright line on the front edge
                ctx.stroke(Path { $0.move(to: CGPoint(x: r.minX + 2, y: edge)); $0.addLine(to: CGPoint(x: r.maxX - 2, y: edge)) },
                           with: .color(.white.opacity(0.75)), lineWidth: 0.8)
            }
            // cords, head rail, bottom rail
            for x in [w * 0.24, w * 0.76] {
                ctx.stroke(Path { $0.move(to: CGPoint(x: x, y: rail)); $0.addLine(to: CGPoint(x: x, y: bottom)) }, with: .color(.black.opacity(0.12)), lineWidth: 1)
            }
            ctx.fill(Path(CGRect(x: 0, y: 0, width: w, height: rail)), with: .linearGradient(Gradient(colors: [face, shade]), startPoint: .zero, endPoint: CGPoint(x: 0, y: rail)))
            ctx.fill(Path(roundedRect: CGRect(x: 2.5, y: bottom, width: w - 5, height: rail * 0.55), cornerRadius: 2), with: .color(shade))
            if !known { ctx.fill(Path(frame), with: .color(Color(.systemBackground).opacity(0.35))) }
        }
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(.white.opacity(0.55), lineWidth: 1))
        .shadow(color: .black.opacity(0.14), radius: 10, y: 6)
        .accessibilityHidden(true)
    }
}

#Preview {
    HStack { SlatView(tilt: 0); SlatView(tilt: 55); SlatView(tilt: -100) }.frame(height: 160).padding().background(AppBackground())
}
