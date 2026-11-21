// The look of the app: a sky that follows the real sunrise and sunset, and glass cards on top of it.
import SwiftUI

typealias RGB = SIMD3<Double>
extension Color { init(_ c: RGB) { self.init(red: c.x, green: c.y, blue: c.z) } }

/// How the sky looks at one moment: three colors top to bottom, where the sun is, and how many stars show.
struct SkyLook {
    var top: RGB, mid: RGB, low: RGB
    var stars: Double                 // 0 day … 1 full night
    var sun: CGPoint?                 // unit point inside the window, nil when it is below the horizon
    var sunWarm: Double               // 0 white (midday) … 1 orange (at the horizon)

    static func mix(_ a: SkyLook, _ b: SkyLook, _ t: Double) -> SkyLook {
        SkyLook(top: a.top + (b.top - a.top) * t, mid: a.mid + (b.mid - a.mid) * t, low: a.low + (b.low - a.low) * t,
                stars: a.stars + (b.stars - a.stars) * t, sun: nil, sunWarm: 0)
    }
}

enum Sky {
    private static func k(_ top: RGB, _ mid: RGB, _ low: RGB, _ stars: Double) -> SkyLook { SkyLook(top: top, mid: mid, low: low, stars: stars, sun: nil, sunWarm: 0) }
    static let night = k(RGB(0.03, 0.06, 0.18), RGB(0.05, 0.11, 0.27), RGB(0.10, 0.19, 0.36), 1)
    static let firstLight = k(RGB(0.09, 0.17, 0.38), RGB(0.30, 0.42, 0.58), RGB(0.98, 0.62, 0.36), 0.35)
    static let sunrise = k(RGB(0.42, 0.68, 0.92), RGB(0.99, 0.82, 0.58), RGB(1.00, 0.66, 0.32), 0)
    static let day = k(RGB(0.28, 0.61, 0.96), RGB(0.56, 0.80, 0.98), RGB(0.86, 0.94, 0.99), 0)
    static let sunset = k(RGB(0.30, 0.52, 0.82), RGB(0.99, 0.70, 0.40), RGB(0.98, 0.44, 0.22), 0)
    static let dusk = k(RGB(0.07, 0.13, 0.33), RGB(0.20, 0.31, 0.48), RGB(0.86, 0.42, 0.24), 0.4)

    /// For mock-ups: launch with "-skyminute 400" to pin the time (minutes after midnight).
    static let pinned: Double? = { let v = UserDefaults.standard.double(forKey: "skyminute"); return v > 0 ? v : nil }()

    /// Today's sunrise and sunset in minutes after midnight. Comes from the controller once a location is set; otherwise a plain guess.
    static var sunTimes: (rise: Double, set: Double) {
        let r = UserDefaults.standard.double(forKey: "sun.rise"), s = UserDefaults.standard.double(forKey: "sun.set")
        return r > 0 && s > r ? (r, s) : (390, 1110)
    }
    static func remember(rise: Date, set: Date) {
        func m(_ d: Date) -> Double { let c = Calendar.current.dateComponents([.hour, .minute], from: d); return Double((c.hour ?? 0) * 60 + (c.minute ?? 0)) }
        UserDefaults.standard.set(m(rise), forKey: "sun.rise"); UserDefaults.standard.set(m(set), forKey: "sun.set")
    }

    static func look(at date: Date = .now) -> SkyLook {
        let c = Calendar.current.dateComponents([.hour, .minute], from: date)
        let m = pinned ?? Double((c.hour ?? 0) * 60 + (c.minute ?? 0))
        let (rise, set) = sunTimes
        let keys: [(Double, SkyLook)] = [(rise - 75, night), (rise - 30, firstLight), (rise + 12, sunrise), (rise + 80, day),
                                         (set - 85, day), (set - 10, sunset), (set + 30, dusk), (set + 75, night)]
        var look = night
        if m > keys[0].0 && m < keys[keys.count - 1].0 {
            for i in 1..<keys.count where m <= keys[i].0 {
                look = SkyLook.mix(keys[i - 1].1, keys[i].1, (m - keys[i - 1].0) / (keys[i].0 - keys[i - 1].0)); break
            }
        }
        let f = (m - rise) / (set - rise)                       // 0 at sunrise … 1 at sunset
        if f > -0.03 && f < 1.03 {
            let up = sin(.pi * min(max(f, 0), 1))
            look.sun = CGPoint(x: 0.14 + 0.72 * f, y: 0.90 - 0.68 * up)
            look.sunWarm = 1 - min(1, up * 2.2)
        }
        return look
    }

    /// The same stars every time.
    static let starField: [(x: Double, y: Double, r: Double, a: Double)] = {
        var seed: UInt64 = 42
        func next() -> Double { seed = seed &* 6364136223846793005 &+ 1442695040888963407; return Double((seed >> 33) % 10000) / 10000 }
        return (0..<70).map { _ in (next(), next() * 0.8, 0.4 + next() * 1.0, 0.45 + next() * 0.55) }
    }()

    /// Draw the sky into a rectangle: color, sun or moon, stars.
    /// `rect` is the whole view outside (it may be wider than the window drawn: several blinds side by side share it);
    /// `unit` is one window's width, which sizes the sun, the moon and the spread of stars.
    static func draw(_ look: SkyLook, in ctx: inout GraphicsContext, rect: CGRect, starScale: CGFloat = 1, unit: CGFloat? = nil) {
        let w = rect.width, h = rect.height, u = unit ?? rect.width
        ctx.fill(Path(rect), with: .linearGradient(Gradient(stops: [.init(color: Color(look.top), location: 0), .init(color: Color(look.mid), location: 0.55), .init(color: Color(look.low), location: 1)]),
                                                   startPoint: rect.origin, endPoint: CGPoint(x: rect.minX, y: rect.maxY)))
        if look.stars > 0.02 {
            let tiles = max(1, Int((w / u).rounded()))                 // the same star field, shifted, for each window's width
            for t in 0..<tiles {
                let tx = rect.minX + CGFloat(t) * w / CGFloat(tiles), tw = w / CGFloat(tiles)
                for s in starField {
                    let sx = (s.x + 0.37 * Double(t)).truncatingRemainder(dividingBy: 1), sy = (s.y + 0.23 * Double(t)).truncatingRemainder(dividingBy: 0.8)
                    let r = s.r * starScale
                    ctx.fill(Path(ellipseIn: CGRect(x: tx + sx * tw - r, y: rect.minY + sy * h - r, width: 2 * r, height: 2 * r)), with: .color(.white.opacity(s.a * look.stars)))
                }
            }
            let mr = min(u, h) * 0.075, mc = CGPoint(x: rect.minX + w * 0.74, y: rect.minY + h * 0.22)      // crescent moon
            var moon = ctx
            moon.opacity = look.stars
            moon.fill(Path(ellipseIn: CGRect(x: mc.x - mr * 3, y: mc.y - mr * 3, width: mr * 6, height: mr * 6)),
                      with: .radialGradient(Gradient(colors: [.white.opacity(0.22), .white.opacity(0)]), center: mc, startRadius: 0, endRadius: mr * 3))
            moon.clip(to: Path(ellipseIn: CGRect(x: mc.x - mr, y: mc.y - mr, width: 2 * mr, height: 2 * mr)))
            moon.fill(Path(rect), with: .color(Color(red: 0.98, green: 0.96, blue: 0.88)))
            moon.fill(Path(ellipseIn: CGRect(x: mc.x - mr * 0.45, y: mc.y - mr * 1.25, width: 2 * mr, height: 2 * mr)), with: .color(Color(look.top)))
        }
        if let s = look.sun {
            let c = CGPoint(x: rect.minX + s.x * w, y: rect.minY + s.y * h), R = max(u, h) * (0.42 + 0.2 * look.sunWarm)
            let warm = Color(red: 1, green: 1 - 0.22 * look.sunWarm, blue: 1 - 0.55 * look.sunWarm)
            ctx.fill(Path(ellipseIn: CGRect(x: c.x - R, y: c.y - R, width: 2 * R, height: 2 * R)),
                     with: .radialGradient(Gradient(colors: [warm.opacity(0.95), warm.opacity(0.35), warm.opacity(0)]), center: c, startRadius: 0, endRadius: R))
            let d = min(u, h) * 0.07
            ctx.fill(Path(ellipseIn: CGRect(x: c.x - d, y: c.y - d, width: 2 * d, height: 2 * d)), with: .color(.white.opacity(0.95)))
        }
    }
}

/// Fills the screen behind every page: a soft version of the sky outside right now.
struct AppBackground: View {
    @Environment(\.colorScheme) private var scheme
    var body: some View {
        TimelineView(.periodic(from: .now, by: 120)) { t in
            let look = Sky.look(at: t.date), dark = scheme == .dark
            // dark mode: a night-blue top with today's sky glowing low on the screen; at night, the night sky itself
            let deep = Sky.night.top, n = look.stars
            let a = Color(dark ? deep + (look.top * 0.45 - deep) * (0.5 + 0.5 * n) : look.top)
            let b = Color(dark ? look.mid * (0.34 + 0.5 * n) : look.mid)
            let c = Color(dark ? look.low * (0.50 + 0.4 * n) : look.low)
            ZStack {
                MeshGradient(width: 3, height: 3,
                             points: [[0, 0], [0.5, 0], [1, 0], [0, 0.5], [0.6, 0.45], [1, 0.6], [0, 1], [0.5, 1], [1, 1]],
                             colors: [a, a, b, b, a, b, c, c, b])
                if dark && look.stars > 0.02 {
                    Canvas { ctx, size in
                        for s in Sky.starField { ctx.fill(Path(ellipseIn: CGRect(x: s.x * size.width, y: s.y * size.height, width: s.r * 2.4, height: s.r * 2.4)), with: .color(.white.opacity(s.a * look.stars * 0.8))) }
                    }
                }
                // light mode keeps dark text readable, even at night
                (dark ? Color.black.opacity(0.18) : Color.white.opacity(0.36 + 0.26 * look.stars))
            }
        }
        .ignoresSafeArea()
    }
}

extension View {
    /// A glass card.
    func card(radius: CGFloat = 26) -> some View {
        glassEffect(.regular, in: RoundedRectangle(cornerRadius: radius, style: .continuous))
    }
    /// A page with the sky behind it (for lists and forms too).
    func skyPage() -> some View {
        scrollContentBackground(.hidden).background(AppBackground())
    }
}

struct Greeting {
    static func text(_ date: Date = .now) -> String {
        switch Calendar.current.component(.hour, from: date) {
        case 5..<12: return "Good morning"
        case 12..<17: return "Good afternoon"
        case 17..<22: return "Good evening"
        default: return "Good night"
        }
    }
}
