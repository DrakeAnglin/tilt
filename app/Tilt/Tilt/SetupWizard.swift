// Teaching a blind its three marks. First the motor turns a little each way, so the controller learns which way it is
// wired; then you turn the blind by hand to each mark and save it.
import SwiftUI

struct SetupWizard: View {
    @Environment(\.dismiss) private var dismiss
    let controller: Controller
    let index: Int
    let name: String
    @State private var step = -1                // -1: check the motor first
    @State private var problem: String?
    @State private var busy = false
    @State private var lastAngle: Double?
    @State private var movedAt = Date.distantPast
    @State private var steady = false

    private let steps: [(mark: String, title: String, detail: String, save: String, tilt: Double)] = [
        ("up", "Close the slats up", "Turn the wand until the slats are shut tight, with the room-side edge pointing up.", "Save Closed Up", 100),
        ("open", "Level the slats", "Turn the wand until the slats are flat and you can see straight through.", "Save Open", 0),
        ("down", "Close the slats down", "Turn the wand until the slats are shut tight, with the room-side edge pointing down.", "Save Closed Down", -100),
    ]

    var body: some View {
        let blind = controller.state?.b[safe: index]
        NavigationStack {
            VStack(spacing: 0) {
                if step < 0 {
                    Text("FIRST").font(.caption.weight(.semibold)).kerning(0.8).foregroundStyle(.secondary)
                    Text("Check the motor").font(.system(size: 30, weight: .bold, design: .rounded)).padding(.top, 2)
                    SlatView(tilt: 50, slats: 11).frame(maxWidth: 300).frame(height: 300).padding(.vertical, 20)
                    Text("Turn the wand so the slats are about halfway, not shut. Then tap Check Motor: the blind turns a little one way and back, so the controller learns which way its motor is wired.")
                        .font(.body).multilineTextAlignment(.center).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                    if let problem { Label(problem, systemImage: "exclamationmark.triangle.fill").font(.subheadline).foregroundStyle(Palette.warning).multilineTextAlignment(.center).padding(.top, 12) }
                    Spacer(minLength: 12)
                    Button { checkMotor() } label: {
                        HStack { if busy { ProgressView().tint(Palette.onAccent) }; Text(busy ? "Turning…" : "Check Motor").font(.headline) }.frame(maxWidth: .infinity).padding(.vertical, 6)
                    }
                    .buttonStyle(.glassProminent).controlSize(.large).disabled(busy || blind?.pres == 0)
                } else if step < 3 {
                    let s = steps[step]
                    HStack(spacing: 6) {
                        ForEach(0..<3, id: \.self) { i in Capsule().fill(i <= step ? Palette.accent : Color.primary.opacity(0.15)).frame(height: 5) }
                    }
                    .padding(.bottom, 18)
                    Text("STEP \(step + 1) OF 3").font(.caption.weight(.semibold)).kerning(0.8).foregroundStyle(.secondary)
                    Text(s.title).font(.system(size: 30, weight: .bold, design: .rounded)).padding(.top, 2)
                    SlatView(tilt: s.tilt, slats: 11)
                        .frame(maxWidth: 300).frame(height: 300)
                        .padding(.vertical, 20)
                        .animation(.easeInOut(duration: 0.6), value: step)
                    Text(s.detail).font(.body).multilineTextAlignment(.center).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                    Label(blind?.pres == 0 ? "No blind on this port" : steady ? "Holding still. Ready to save." : "Turning…",
                          systemImage: blind?.pres == 0 ? "cable.connector.slash" : steady ? "checkmark.circle.fill" : "arrow.triangle.2.circlepath")
                        .font(.subheadline.weight(.medium)).foregroundStyle(steady && blind?.pres != 0 ? Palette.good : Color.secondary)
                        .padding(.horizontal, 14).padding(.vertical, 8).card(radius: 20).padding(.top, 16)
                        .animation(.default, value: steady)
                    if let problem { Label(problem, systemImage: "exclamationmark.triangle.fill").font(.subheadline).foregroundStyle(Palette.warning).multilineTextAlignment(.center).padding(.top, 12) }
                    Spacer(minLength: 12)
                    Button { mark(s.mark) } label: {
                        HStack { if busy { ProgressView().tint(Palette.onAccent) }; Text(busy ? "Saving…" : s.save).font(.headline) }.frame(maxWidth: .infinity).padding(.vertical, 6)
                    }
                    .buttonStyle(.glassProminent).controlSize(.large).disabled(busy || blind?.pres == 0)
                    .sensoryFeedback(.success, trigger: step)
                    Button("Back") { step -= 1; problem = nil }.padding(.top, 10).opacity(step > 0 ? 1 : 0).disabled(step == 0)
                } else {
                    Spacer()
                    Image(systemName: "checkmark.circle.fill").font(.system(size: 64)).foregroundStyle(Palette.good)
                    Text("\(name) is set up").font(.system(size: 28, weight: .bold, design: .rounded)).padding(.top, 10)
                    Text("Try each position. The blind moves by itself now.").font(.body).foregroundStyle(.secondary).padding(.top, 2)
                    HStack(spacing: 10) {
                        PositionButton(title: "Close Down", systemImage: "chevron.down") { controller.go(blind: index, tilt: -100, solo: true) }
                        PositionButton(title: "Open", systemImage: "sun.max.fill") { controller.go(blind: index, tilt: 0, solo: true) }
                        PositionButton(title: "Close Up", systemImage: "chevron.up") { controller.go(blind: index, tilt: 100, solo: true) }
                    }
                    .padding(.top, 24)
                    Text(blind.map(TiltWords.status) ?? "").font(.subheadline).foregroundStyle(.secondary).padding(.top, 12)
                    Spacer()
                    Button { dismiss() } label: { Text("Done").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 6) }.buttonStyle(.glassProminent).controlSize(.large)
                    Button("Set Up Again") { step = 0; problem = nil }.padding(.top, 10)
                }
            }
            .padding(.horizontal, 24).padding(.vertical, 16)
            .background(AppBackground())
            .navigationTitle(name).navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
            // Keep the sensor on and read it often while a step is open.
            .task(id: step) {
                controller.boost = true
                defer { controller.boost = false }
                while !Task.isCancelled && step < 3 {
                    if blind?.mov != 1 { await controller.client.watch(blind: index) }
                    try? await Task.sleep(for: .milliseconds(900))
                }
            }
            .onChange(of: blind?.ang) { _, a in
                if let a, let l = lastAngle, abs(a - l) > 0.6, abs(a - l) < 359.4 { movedAt = .now }
                lastAngle = a
            }
            .task {                                                  // "holding still" once the reading has not moved for a moment
                while !Task.isCancelled {
                    steady = lastAngle != nil && Date.now.timeIntervalSince(movedAt) > 1.2
                    try? await Task.sleep(for: .milliseconds(300))
                }
            }
        }
        .interactiveDismissDisabled()
    }

    private func checkMotor() {
        busy = true; problem = nil
        Task {
            defer { busy = false }
            if let p = await MotorCheck.run(controller, blind: index) { problem = p } else { step = 0 }
        }
    }
    private func mark(_ which: String) {
        busy = true; problem = nil
        Task {
            defer { busy = false }
            do {
                let m = try await controller.client.mark(blind: index, which)
                if m.ok != 1 { problem = (m.err ?? "That did not work.").capitalizedFirst; return }
                if which == "down", let p = m.prob {            // the three marks do not make sense together: start over
                    _ = try? await controller.client.mark(blind: index, "clear")
                    problem = p.capitalizedFirst + ". Start again from step 1."
                    step = 0
                    return
                }
                step += 1
            } catch { problem = error.localizedDescription }
        }
    }
}

/// Runs `press` again and again while held (the controller stops by itself if the calls stop coming).
struct HoldButton: View {
    let title: String
    let systemImage: String
    let press: () -> Void
    let release: () -> Void
    @State private var held = false

    var body: some View {
        Label(title, systemImage: systemImage)
            .font(.headline).frame(maxWidth: .infinity).padding(.vertical, 26)
            .background(held ? Palette.fillSelected : Palette.fill, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            .onLongPressGesture(minimumDuration: 600, maximumDistance: 80, perform: {}, onPressingChanged: { held = $0; if !$0 { release() } })
            .task(id: held) {
                while held && !Task.isCancelled { press(); try? await Task.sleep(for: .milliseconds(180)) }
            }
            .sensoryFeedback(.impact, trigger: held)
            .accessibilityAddTraits(.isButton)
    }
}

/// Which way a blind's motor is wired: it turns a little one way and back, and the controller learns the direction
/// from how its angle moved (it keeps it, so swapped motor wires never send a blind the wrong way).
enum MotorCheck {
    /// nil when it worked, else what to tell the user.
    static func run(_ c: Controller, blind i: Int) async -> String? {
        // One way until the angle has clearly moved; if that way is against an end stop, the other way.
        for dir in [1, -1] {
            guard let moved = await turn(c, blind: i, dir: dir) else { return "The controller did not answer. Try again." }
            if abs(moved) >= 6 {
                _ = await turn(c, blind: i, dir: -dir)        // back to where it was
                return nil
            }
        }
        return "The blind did not turn. Turn the wand so the slats are about halfway, check the cable, and try again."
    }
    /// Holds the motor one way (up to 5 s) until the angle has moved 8 degrees. Returns how far it moved, nil if no answer.
    private static func turn(_ c: Controller, blind i: Int, dir: Int) async -> Double? {
        guard let a0 = try? await c.client.state().b[safe: i]?.ang else { return nil }
        let start = Date()
        while Date().timeIntervalSince(start) < 5 {
            await c.client.jog(blind: i, dir: dir, percent: 80, ms: 700)
            if let a = try? await c.client.state().b[safe: i]?.ang, abs(diff(a0, a)) >= 8 { break }
        }
        try? await Task.sleep(for: .seconds(1.5))           // stops and settles; the controller learns the direction now
        guard let a1 = try? await c.client.state().b[safe: i]?.ang else { return nil }
        return diff(a0, a1)
    }
    private static func diff(_ a: Double, _ b: Double) -> Double {
        var d = (b - a).truncatingRemainder(dividingBy: 360)
        if d > 180 { d -= 360 } else if d < -180 { d += 360 }
        return d
    }
}
