// Teaching a blind its three marks: you turn the wand to each mark and save it. Then the blind moves to Open by
// itself, and that first move checks the motor's wiring: if it starts the wrong way, the controller turns it round and
// remembers it (firmware tilter.h), so swapped motor wires need no rewiring.
import SwiftUI

struct SetupWizard: View {
    @Environment(\.dismiss) private var dismiss
    let controller: Controller
    let index: Int
    let name: String
    @State private var step = 0
    @State private var wiring: String?            // what the first move found out about the motor's wiring
    @State private var checking = false
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
                if step < 3 {
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
                    if let problem { Label(problem, systemImage: "exclamationmark.triangle.fill").font(.subheadline).foregroundStyle(Palette.warning).multilineTextAlignment(.center).fixedSize(horizontal: false, vertical: true).padding(.top, 12) }
                    Spacer(minLength: 12)
                    // One button says it all: it saves once the blind holds still, and says why it can't before that.
                    let absent = blind?.pres == 0
                    Button { mark(s.mark) } label: {
                        HStack {
                            if busy { SlatLoader(size: 18).tint(Palette.onAccent) }
                            Text(busy ? "Saving…" : absent ? "No Blind on This Port" : steady ? s.save : "Turning…").font(.headline)
                        }
                        .frame(maxWidth: .infinity).padding(.vertical, 6)
                    }
                    .buttonStyle(.glassProminent).controlSize(.large).disabled(busy || absent || !steady)
                    .animation(.default, value: steady)
                    .sensoryFeedback(.success, trigger: step)
                    Button("Back") { step -= 1; problem = nil }.padding(.top, 10).opacity(step > 0 ? 1 : 0).disabled(step == 0)
                } else {
                    Spacer()
                    Image(systemName: "checkmark.circle.fill").font(.system(size: 64)).foregroundStyle(Palette.good)
                    Text("\(name) is ready").font(.system(size: 28, weight: .bold, design: .rounded)).padding(.top, 10)
                    Group {
                        if checking {
                            HStack(spacing: 8) { SlatLoader(size: 16); Text("Moving to Open to check the motor wiring…") }
                        } else if let wiring {
                            Label(wiring, systemImage: "checkmark.circle").foregroundStyle(Palette.good)
                        }
                    }
                    .font(.subheadline).multilineTextAlignment(.center).fixedSize(horizontal: false, vertical: true).padding(.top, 8)
                    if let problem { Label(problem, systemImage: "exclamationmark.triangle.fill").font(.subheadline).foregroundStyle(Palette.warning).multilineTextAlignment(.center).fixedSize(horizontal: false, vertical: true).padding(.top, 8) }
                    Text("Try each one. The blind moves by itself now.").font(.body).foregroundStyle(.secondary).padding(.top, 8)
                    HStack(spacing: 10) {
                        PositionButton(title: "Close Down", systemImage: "chevron.down") { controller.go(blind: index, tilt: -100) }
                        PositionButton(title: "Open", systemImage: "sun.max.fill") { controller.go(blind: index, tilt: 0) }
                        PositionButton(title: "Close Up", systemImage: "chevron.up") { controller.go(blind: index, tilt: 100) }
                    }
                    .padding(.top, 24).disabled(checking)
                    Text(blind.map(TiltWords.status) ?? "").font(.subheadline).foregroundStyle(.secondary).padding(.top, 12)
                    Spacer()
                    Button { dismiss() } label: { Text("Done").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 6) }.buttonStyle(.glassProminent).controlSize(.large)
                    Button("Redo Setup") { step = 0; problem = nil; wiring = nil }.padding(.top, 10)
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

    /// The first move after setup: to Open. The controller watches which way the angle goes; if the motor's wires are
    /// swapped it turns round and keeps that. Reported from the controller's developer view ("sign": -1 = swapped).
    private func checkWiring() {
        checking = true; problem = nil; wiring = nil
        Task {
            defer { checking = false }
            do {
                try await controller.client.go(blind: index, tilt: 0)
                let t0 = Date()
                var seenMoving = false
                while Date().timeIntervalSince(t0) < 30 {
                    try await Task.sleep(for: .milliseconds(700))
                    guard let b = try? await controller.client.state().b[safe: index] else { continue }
                    if b.moving { seenMoving = true; continue }
                    if seenMoving || Date().timeIntervalSince(t0) > 4 {
                        if !b.last.localizedCaseInsensitiveContains("reached") && !b.last.localizedCaseInsensitiveContains("already") {
                            problem = "The blind did not reach Open (\(b.last)). Check it turns freely, then tap Open."
                            return
                        }
                        break
                    }
                }
                let dev = await controller.client.developerInfo()
                let sign = ((dev["p"] as? [[String: Any]])?[safe: index]?["sign"] as? Int) ?? 0
                wiring = sign < 0 ? "Motor checked: its wires are the other way round. The controller has learned that, nothing to rewire."
                                  : "Motor checked: it turns the right way."
            } catch { problem = error.localizedDescription }
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
                if step == 3 { checkWiring() }
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
