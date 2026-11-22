// One controller's settings: its blinds, general options, Apple Home, sharing, developer.
import CoreImage.CIFilterBuiltins
import HomeKit
import SwiftUI

struct ControllerSettingsView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let controller: Controller
    @State private var cfg: ControllerConfig?
    @State private var phones: [PhoneKey] = []
    @State private var name = ""
    @State private var removing: PhoneKey?
    @State private var review: JoinAsk?
    @State private var renaming: PhoneKey?
    @State private var newName = ""
    @State private var home: HomeInfo?
    @State private var problem: String?
    @State private var confirmRemove = false
    @State private var retried = false
    @AppStorage(Prefs.devMode) private var devMode = false

    struct HomeInfo: Identifiable { let code: String; let qr: String; var id: String { qr } }

    var body: some View {
        List {
            Group {
            if !controller.record.owner { Section { Label("You can open and close these blinds. Only an owner can change settings.", systemImage: "lock") } }
            if controller.needsUpdate { Section { FirmwareNotice(controller: controller) } }
            if let cfg {
              if controller.record.owner {       // settings, setup and Apple Home are the owners'
                Section("Blinds") {
                    ForEach(Array(cfg.b.enumerated()), id: \.offset) { i, b in
                        NavigationLink {
                            BlindSettingsView(controller: controller, index: i, blind: b) { await load() }
                        } label: {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(b.name)
                                Text(blindNote(i, b)).font(.footnote).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
                Section {
                    TextField("Name", text: $name).onSubmit { let n = name; change { try await $0.setName(n) } }.submitLabel(.done)
                    Picker("\u{201C}Close\u{201D} tilts the slats", selection: Binding(get: { cfg.closeUp }, set: { v in change { try await $0.setCloseUp(v == 1) } })) {
                        Text("Up").tag(1); Text("Down").tag(0)
                    }
                    Toggle("Blinds Follow Each Other", isOn: Binding(get: { cfg.sync == 1 }, set: { on in change { try await $0.setFollow(on) } }))
                    if let par = cfg.par {
                        Toggle("Move at the Same Time", isOn: Binding(get: { par == 1 }, set: { on in change { try await $0.setSameTime(on) } }))
                    }
                } header: { Text("General") } footer: {
                    Text("Follow Each Other: when one blind is moved, from here, from Apple Home or by turning its wand, the others go to the same position.\n\nMove at the Same Time: off moves them one after another, which is quieter and easier on the battery.")
                }
                Section {
                    Button("Add to Apple Home", systemImage: "homekit") { openHome() }
                    Toggle("Show each blind separately", isOn: Binding(get: { cfg.hksep == 1 }, set: { on in change { try await $0.setHomeSeparate(on) } }))
                } header: { Text("Apple Home") } footer: {
                    Text((controller.state?.hk ?? 0) > 0 ? "Added to Apple Home. Changing how blinds are shown restarts the controller." : "Not added to Apple Home yet.")
                }
              }
                Section {
                    ForEach(phones) { p in
                        if p.wait == 1 {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("\(p.name) wants to join").font(.body.weight(.medium))
                                Text("Their phone shows the code \(p.code ?? "").").font(.footnote).foregroundStyle(.secondary)
                                if controller.record.owner { Button("Review") { review = JoinAsk(controller: controller, phone: p) }.buttonStyle(.borderedProminent) }
                            }
                        } else {
                            Button { if p.me == 1 || controller.record.owner { newName = p.name; renaming = p } } label: {
                                LabeledContent(p.name + (p.me == 1 ? " (this phone)" : ""), value: p.owner == 1 ? "Owner" : "User").contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)                // names in the normal text color, not as links
                            .swipeActions {
                                if controller.record.owner && p.me == 0 {
                                    Button("Remove") { removing = p }.tint(Palette.danger)
                                    Button(p.owner == 1 ? "Make User" : "Make Owner") { setRole(p, owner: p.owner != 1) }.tint(Palette.accent)
                                }
                            }
                            .confirmationDialog("Remove \(p.name)?", isPresented: Binding(get: { removing?.cid == p.cid }, set: { if !$0 { removing = nil } }), titleVisibility: .visible) {
                                Button("Remove", role: .destructive) { revoke(p) }
                            } message: { Text("That phone will no longer control these blinds. It can ask to join again.") }
                        }
                    }
                } header: { Text("People") } footer: {
                    Text("Tap a name to change it. To add someone: on your Wi-Fi, they open Tilt, tap Add, and ask to join. You approve it here." + (controller.record.owner ? " Swipe left on someone to remove them or change their role." : ""))
                }
                if devMode && developerBuild { Section {
                    NavigationLink { DeveloperView(controller: controller) } label: { Label("Developer", systemImage: "chevron.left.forwardslash.chevron.right") }
                } }
            } else if problem == nil {
                SlatLoader(label: "Loading settings…").frame(maxWidth: .infinity).padding(.vertical, 24).listRowBackground(Color.clear)
            }
            if controller.state != nil { FirmwareSection(controller: controller) }
            if cfg == nil, problem == nil { Section { HStack(spacing: 10) { SlatLoader(size: 20); Text("Loading…").foregroundStyle(.secondary) } } }
            if let problem { Section { Label(problem, systemImage: "exclamationmark.triangle").foregroundStyle(Palette.warning) } }
            Section {
                Button("Remove from This Phone", role: .destructive) { confirmRemove = true }
                    .confirmationDialog("Remove this controller from this phone?", isPresented: $confirmRemove, titleVisibility: .visible) {
                        if controller.record.owner {
                            Button("Remove and Reset Controller", role: .destructive) { remove(reset: true) }
                            Button("Remove from This Phone Only", role: .destructive) { remove(reset: false) }
                        } else {
                            Button("Remove", role: .destructive) { remove(reset: false) }
                        }
                    } message: {
                        Text(controller.record.owner ? "Reset makes the controller forget every phone, so it can be set up again as new. Schedules and blind positions are kept."
                                                     : "The blinds keep working. To use them here again you will need a new sharing code.")
                    }
            }
        }
            .listRowBackground(RowGlass())      // rows are glass over the sky, not solid white
        }
        .skyPage()
        .navigationTitle(controller.state?.name ?? controller.record.name)
        .navigationBarTitleDisplayMode(.inline)
        // Not `.task`: that is cancelled whenever the page is rebuilt (picking a room in the side-by-side layout does
        // that), and the cancelled request used to be shown as an error with nothing else on the page.
        .onAppear { Task { await load() } }
        // Someone asked to join, or a request was answered (here or on the approve page): show it in People right away.
        .onChange(of: controller.requests) { _, _ in Task { await load() } }
        .onChange(of: controller.state?.asks) { _, _ in Task { await load() } }
        .refreshable { await load() }
        .sheet(item: $review, onDismiss: { Task { await load() } }) { a in JoinSheet(ask: a) { review = nil }.presentationDetents([.height(480)]) }
        .alert("Name", isPresented: Binding(get: { renaming != nil }, set: { if !$0 { renaming = nil } }), presenting: renaming) { p in
            TextField("Name", text: $newName)
            Button("Save") { rename(p) }
            Button("Cancel", role: .cancel) {}
        } message: { p in Text(p.me == 1 ? "What other people see for this phone." : "What this phone is called in the list.") }
        .sheet(item: $home) { HomeSheet(info: $0, roomName: controller.state?.name ?? controller.record.name).presentationDetents([.large]) }
    }

    private func remove(reset: Bool) {
        Task {
            if reset { try? await controller.client.revokeAll() }
            model.remove(controller)                 // the Blinds tab goes back to the rooms by itself
            dismiss()
        }
    }

    private func blindNote(_ i: Int, _ b: ControllerConfig.Blind) -> String {
        let s = controller.state?.b[safe: i]
        if b.hid == 1 { return "Port \(i + 1) · hidden" }
        if let s, s.seen == 1, s.pres == 0 { return "Port \(i + 1) · nothing plugged in" }
        if let s, s.cal == 0 { return "Port \(i + 1) · not set up" }
        return "Port \(i + 1)"
    }
    private func load() async {
        do {
            let c = try await controller.client.config()
            cfg = c; name = c.name; problem = nil
            let list = ((try? await controller.client.people()) ?? []).sorted { ($0.me, $0.wait ?? 0) > ($1.me, $1.wait ?? 0) }      // this phone first, then requests
            withAnimation { phones = list }
            if let me = phones.first(where: { $0.me == 1 }) { model.setOwner(controller, me.owner == 1) }      // the owner may have changed
        } catch {
            // A request that was cancelled is not a fault: try once more instead of showing "cancelled".
            let cancelled = error is CancellationError || (error as? URLError)?.code == .cancelled
            if cancelled { if !retried { retried = true; try? await Task.sleep(for: .milliseconds(300)); await load() } }
            else { problem = error.localizedDescription }
        }
        retried = false
    }
    /// Change a setting on the controller, then read the settings again.
    private func change(_ what: @escaping (ControllerClient) async throws -> Void) {
        Task {
            do { try await what(controller.client); await load() } catch { problem = error.localizedDescription }
        }
    }
    private func setRole(_ p: PhoneKey, owner: Bool) {
        Task { do { try await controller.client.makeOwner(cid: p.cid, owner); await load() } catch { problem = error.localizedDescription } }
    }
    private func rename(_ p: PhoneKey) {
        let n = newName.trimmingCharacters(in: .whitespaces)
        guard !n.isEmpty else { return }
        if p.me == 1 { AppModel.myName = n }
        Task { do { try await controller.client.rename(cid: p.cid, to: n); await load() } catch { problem = error.localizedDescription } }
    }
    private func revoke(_ p: PhoneKey) {
        Task {
            do {
                let proof = try await controller.client.revoke(cid: p.cid)
                await Cloud.postGone(cid: p.cid, proof: proof)        // so that phone drops these blinds even away from home
                await load()
            } catch { problem = error.localizedDescription }
        }
    }
    private func openHome() {
        Task {
            do { let h = try await controller.client.homeSetupCode(); home = HomeInfo(code: h.code, qr: h.qr) } catch { problem = error.localizedDescription }
        }
    }
}

struct QRCode: View {
    let text: String
    var body: some View {
        let f = CIFilter.qrCodeGenerator()
        f.message = Data(text.utf8)
        f.correctionLevel = "M"
        let img = f.outputImage.flatMap { CIContext().createCGImage($0.transformed(by: CGAffineTransform(scaleX: 12, y: 12)), from: $0.extent.applying(CGAffineTransform(scaleX: 12, y: 12))) }
        return Group {
            if let img { Image(decorative: img, scale: 1).interpolation(.none).resizable().scaledToFit() } else { Image(systemName: "qrcode") }
        }
        .padding(14)
        .background(Palette.codeBackground, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}

struct HomeSheet: View {
    let info: ControllerSettingsView.HomeInfo
    var roomName = "Blinds"
    @Environment(\.openURL) private var openURL
    @State private var copied = false
    @State private var note: String?
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 18) {
                    // The quick way: Apple's own add-accessory page, opened here with the code already filled in.
                    Button { addHere() } label: { Label("Add to Apple Home", systemImage: "homekit").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 4) }
                        .buttonStyle(.borderedProminent).controlSize(.large)
                    Text("When it says \u{201C}Uncertified Accessory\u{201D}, choose Add Anyway. The controller accepts this for the next 10 minutes.")
                        .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    if let note { Label(note, systemImage: "exclamationmark.triangle").font(.footnote).foregroundStyle(Palette.warning) }

                    VStack(spacing: 12) {
                        Text("Or add it by hand").font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity, alignment: .leading)
                        Text(info.code).font(.title2.monospacedDigit().weight(.semibold)).textSelection(.enabled)
                        HStack(spacing: 10) {
                            Button { UIPasteboard.general.string = info.code.filter(\.isNumber); copied = true } label: { Label(copied ? "Copied" : "Copy Code", systemImage: copied ? "checkmark" : "doc.on.doc").frame(maxWidth: .infinity) }
                            Button { if let u = URL(string: "com.apple.home://") { openURL(u) } } label: { Label("Open Home", systemImage: "arrow.up.forward.app").frame(maxWidth: .infinity) }
                        }
                        .buttonStyle(.bordered)
                        Text("In Home tap +, Add Accessory, More Options. Pick this controller, or tap \u{201C}My Accessory Isn\u{2019}t Shown Here\u{201D} and paste the code.")
                            .font(.footnote).foregroundStyle(.secondary).frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .padding(16).background(Palette.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))

                    VStack(spacing: 10) {
                        Text("From another iPhone or iPad").font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity, alignment: .leading)
                        QRCode(text: info.qr).frame(maxWidth: 170)
                        Text("Point its camera at this code.").font(.footnote).foregroundStyle(.secondary)
                    }
                    .padding(16).frame(maxWidth: .infinity).background(Palette.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                }
                .padding()
            }
            .skyPage()
            .navigationTitle("Add to Apple Home").navigationBarTitleDisplayMode(.inline)
            .sensoryFeedback(.success, trigger: copied)
        }
    }
    private func addHere() {
        note = nil
        Task {
            let request = HMAccessorySetupRequest()
            request.payload = URL(string: info.qr).flatMap { HMAccessorySetupPayload(url: $0) }
            request.suggestedAccessoryName = roomName
            guard request.payload != nil else { note = "Use the code below instead."; return }
            do { try await HMAccessorySetupManager().performAccessorySetup(using: request) }
            catch { if (error as? HMError)?.code != .operationCancelled { note = "Apple Home could not start from here. Use the code below instead." } }
        }
    }
}

struct BlindSettingsView: View {
    let controller: Controller
    let index: Int
    @State var blind: ControllerConfig.Blind
    let reload: () async -> Void
    @State private var name = ""
    @State private var settingUp = false

    var body: some View {
        Form {
            Group {
            Section("Name") {
                TextField("Name", text: $name).onSubmit { let n = name; change { try await $0.setBlindName(blind: index, n) } }.submitLabel(.done)
            }
            Section {
                Toggle("Show this blind", isOn: Binding(get: { blind.hid == 0 }, set: { shown in blind.hid = shown ? 0 : 1; change { try await $0.setHidden(blind: index, !shown) } }))
            } footer: { Text("Turn off for a port with nothing plugged in.") }
            Section {
                Button("Set Up Positions", systemImage: "slider.horizontal.below.rectangle") { settingUp = true }
            } footer: { Text("Mark where this blind is closed up, open, and closed down.") }
        }
            .listRowBackground(RowGlass())      // rows are glass over the sky, not solid white
        }
        .skyPage()
        .navigationTitle(blind.name).navigationBarTitleDisplayMode(.inline)
        .onAppear { name = blind.name }
        .fullScreenCover(isPresented: $settingUp) { SetupWizard(controller: controller, index: index, name: blind.name) }
    }
    private func change(_ what: @escaping (ControllerClient) async throws -> Void) {
        Task { try? await what(controller.client); await reload() }
    }
}
