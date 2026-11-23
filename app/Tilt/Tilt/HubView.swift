// The Tilt Hub page (Settings): the hub itself and every controller on it, from what the hub knows. Looking at it
// wakes no controller.
import SwiftUI

struct HubView: View {
    @Environment(HubWatch.self) private var hub
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State private var home: ControllerSettingsView.HomeInfo?
    @State private var problem: String?
    @State private var confirmLeave = false
    @State private var removing: PhoneKey?

    var body: some View {
        List {
            Group {
                if let i = hub.info {
                    Section {
                        LabeledContent("Status", value: hub.statusWord)
                        LabeledContent("Address", value: i.ip ?? hub.host ?? "")
                        if let w = i.wifi, w != 0 { LabeledContent("Wi-Fi signal", value: Self.signal(w)) }
                        if let ch = i.ch { LabeledContent("Thread channel", value: "\(ch)") }
                        if let fw = i.fw { LabeledContent("Firmware", value: fw) }
                        if let up = i.up { LabeledContent("Running for", value: Self.span(up)) }
                    } header: { Text("Tilt Hub") }
                    Section {
                        LabeledContent("Status", value: (i.home ?? 0) == 1 ? "Added" : "Not added yet")
                        if hub.isOwner && (i.home ?? 0) != 1 {
                            Button("Add Tilt Hub to Apple Home", systemImage: "homekit") { openHome() }
                        }
                    } header: { Text("Apple Home") } footer: {
                        Text("Add the hub once: every controller on it shows up in Apple Home by itself.")
                    }
                    Section {
                        if let n = i.new, !n.isEmpty {
                            Label("\(n.count) new controller\(n.count == 1 ? "" : "s") nearby, waiting to be set up", systemImage: "sparkles")
                        }
                        if i.c.isEmpty { Text("No controllers yet.").foregroundStyle(.secondary) }
                        ForEach(i.c) { m in
                            if let c = model.controllers.first(where: { $0.id == m.id }) {
                                NavigationLink { ControllerSettingsView(controller: c) } label: { MemberRow(m: m) }
                            } else { MemberRow(m: m) }
                        }
                    } header: { Text("Controllers") } footer: {
                        Text("What each controller last told the hub. Tap one for its settings.")
                    }
                    Section {
                        ForEach(people) { p in
                            VStack(alignment: .leading, spacing: 6) {
                                LabeledContent(p.name + (p.me == 1 ? " (this iPhone)" : ""), value: p.wait == 1 ? "Asks to join" : p.owner == 1 ? "Owner" : "User")
                                if p.wait == 1, hub.isOwner {
                                    Text("Their iPhone shows the code \(p.code ?? ""). Let them in if it matches.").font(.footnote).foregroundStyle(.secondary)
                                    HStack {
                                        Button("Let In") { act { try await hub.approve(cid: p.cid, true) } }.buttonStyle(.borderedProminent)
                                        Button("Decline") { act { try await hub.approve(cid: p.cid, false) } }.buttonStyle(.bordered)
                                    }
                                }
                            }
                            .swipeActions {
                                if hub.isOwner && p.me == 0 && p.wait != 1 {
                                    Button("Remove") { removing = p }.tint(Palette.danger)
                                    Button(p.owner == 1 ? "Make User" : "Make Owner") { act { try await hub.makeOwner(cid: p.cid, p.owner != 1) } }.tint(Palette.accent)
                                }
                            }
                            .confirmationDialog("Remove \(p.name) from the Tilt Hub?", isPresented: Binding(get: { removing?.cid == p.cid }, set: { if !$0 { removing = nil } }), titleVisibility: .visible) {
                                Button("Remove", role: .destructive) { act { try await hub.revoke(cid: p.cid) } }
                            }
                        }
                    } header: { Text("People") } footer: {
                        Text("To add someone: on your home Wi-Fi, they open Tilt and tap Ask to Join on the Tilt Hub. You let them in here." + (hub.isOwner ? " Swipe left on someone to remove them." : ""))
                    }
                    if let problem { Section { Label(problem, systemImage: "exclamationmark.triangle").foregroundStyle(Palette.warning) } }
                    Section {
                        Button("Remove Tilt Hub", role: .destructive) { confirmLeave = true }
                            .disabled(hub.everyone == nil)          // the choices depend on who else is in
                            .confirmationDialog("Remove the Tilt Hub?", isPresented: $confirmLeave, titleVisibility: .visible) {
                                if soleOwner {
                                    Button("Remove and Reset the Hub's People", role: .destructive) { act { try await hub.resetPeople(); dismiss() } }
                                    Button("Remove from This iPhone Only", role: .destructive) { hub.forgetHere(); dismiss() }
                                } else {
                                    Button("Leave the Tilt Hub", role: .destructive) { act { try await hub.leave(); dismiss() } }
                                }
                            } message: {
                                Text(soleOwner ? "You are the hub's only owner. Reset its people: it forgets every phone and the next one to connect becomes its owner (its controllers, blinds and Apple Home stay). Or remove it from this iPhone only: the hub still counts you as its owner, and nobody can get in without resetting it."
                                               : "The hub forgets this iPhone. Its other people keep it. You can ask to join again.")
                            }
                    }
                    Section {
                        Text("Hold the hub's BOOT button (only that one, not RST) for 10 seconds: its light blinks slowly, then fast when it resets. It forgets Apple Home, its Thread network, its controllers and their backups, and starts again. Then remove the old Tilt Hub in the Home app, add it again (Apple Home, above), and set up each controller again.")
                            .font(.footnote).foregroundStyle(.secondary)
                    } header: { Text("Reset the Tilt Hub") }

                } else {
                    Section { HStack(spacing: 12) { SlatLoader(size: 22); Text("Asking the Tilt Hub…") } }
                }
            }
            .listRowBackground(RowGlass())
        }
        .skyPage()
        .navigationTitle("Tilt Hub")
        .refreshable { await load() }
        .task { await load() }
        .sheet(item: $home) { HomeSheet(info: $0, roomName: "Tilt Hub").presentationDetents([.large]) }
    }
    /// This iPhone is the hub's only owner (leaving would leave the hub with nobody to let people in).
    private var soleOwner: Bool { hub.isOwner && !people.contains { $0.me == 0 && $0.owner == 1 && $0.wait != 1 } }
    private var people: [PhoneKey] { hub.everyone ?? [] }
    private func load() async { await hub.refresh() }
    private func act(_ f: @escaping () async throws -> Void) {
        problem = nil
        Task { do { try await f(); await load() } catch { problem = error.localizedDescription } }
    }
    private func openHome() {
        Task {
            do { let h = try await hub.homeCode(); home = .init(code: h.code, qr: h.qr, hub: true, inHome: h.home == 1) } catch { problem = error.localizedDescription }
        }
    }
    static func signal(_ dbm: Int) -> String { "\(dbm) dBm (\(dbm > -60 ? "strong" : dbm > -75 ? "good" : dbm > -85 ? "weak" : "very weak"))" }
    static func span(_ s: Int) -> String { s < 3600 ? "\(s / 60) min" : s < 86400 ? "\(s / 3600) h" : "\(s / 86400) d" }
}

/// One controller on the hub: name, battery and last check-in; signal only when it is worth knowing about.
private struct MemberRow: View {
    let m: HubInfo.Member
    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack {
                Text(m.name).font(.body.weight(.medium))
                Spacer()
                if m.notResponding { Label("Not responding", systemImage: "exclamationmark.triangle.fill").font(.footnote).foregroundStyle(Palette.warning) }
            }
            Text(line).font(.footnote).foregroundStyle(.secondary)
            if let r = m.rssi, r != 127, r <= -85 { Text("Weak signal: move the hub closer.").font(.footnote).foregroundStyle(Palette.warning) }
            if m.key == 1 { Text("Connecting the hub to this controller…").font(.footnote).foregroundStyle(.secondary) }
        }
        .padding(.vertical, 2)
    }
    private var line: String {
        var parts: [String] = []
        if m.pct >= 0 { parts.append("Battery \(m.pct)%") }
        if m.seenS >= 0 { parts.append(m.seenS < 90 ? "checked in just now" : "checked in \(HubView.span(m.seenS)) ago") }
        if m.rssi == nil || m.rssi == 127 { parts.append("not on the hub's network") }
        return parts.joined(separator: " · ")
    }
}
