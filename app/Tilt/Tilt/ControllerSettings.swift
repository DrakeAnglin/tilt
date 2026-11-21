// One controller's settings: its blinds, general options, Apple Home, sharing, developer.
import CoreImage.CIFilterBuiltins
import SwiftUI

struct ControllerConfig: Decodable {
    struct Blind: Decodable { var name: String; var hid: Int; var speed: Int; var fav: Int }
    var name: String
    var closeUp: Int, sync: Int
    var par: Int?                 // move at the same time (firmware 2.2 and later)
    var tzn: String
    var hksep: Int?
    var b: [Blind]
}
struct PhoneKey: Decodable, Identifiable { let cid: String; let name: String; let owner: Int; let me: Int; var id: String { cid } }

struct ControllerSettingsView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let controller: Controller
    @State private var cfg: ControllerConfig?
    @State private var phones: [PhoneKey] = []
    @State private var name = ""
    @State private var share: ShareInfo?
    @State private var home: HomeInfo?
    @State private var problem: String?
    @State private var confirmRemove = false
    @AppStorage("devMode") private var devMode = false

    struct ShareInfo: Identifiable { let link: String; var id: String { link } }
    struct HomeInfo: Identifiable { let code: String; let qr: String; var id: String { qr } }

    var body: some View {
        List {
            if let cfg {
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
                    TextField("Name", text: $name).onSubmit { set("name", name) }.submitLabel(.done)
                    Picker("\u{201C}Close\u{201D} tilts the slats", selection: Binding(get: { cfg.closeUp }, set: { set("closeUp", "\($0)") })) {
                        Text("Up").tag(1); Text("Down").tag(0)
                    }
                    Toggle("Blinds Follow Each Other", isOn: Binding(get: { cfg.sync == 1 }, set: { set("sync", $0 ? "1" : "0") }))
                    if let par = cfg.par {
                        Toggle("Move at the Same Time", isOn: Binding(get: { par == 1 }, set: { set("par", $0 ? "1" : "0") }))
                    }
                } header: { Text("General") } footer: {
                    Text("Follow Each Other: when one blind is moved, from here, from Apple Home or by turning its wand, the others go to the same position.\n\nMove at the Same Time: off moves them one after another, which is quieter and easier on the battery.")
                }
                Section {
                    Button("Add to Apple Home", systemImage: "homekit") { openHome() }
                    Toggle("Show each blind separately", isOn: Binding(get: { cfg.hksep == 1 }, set: { set("hksep", $0 ? "1" : "0") }))
                } header: { Text("Apple Home") } footer: {
                    Text((controller.state?.hk ?? 0) > 0 ? "Added to Apple Home. Changing how blinds are shown restarts the controller." : "Not added to Apple Home yet.")
                }
                Section {
                    ForEach(phones) { p in
                        LabeledContent(p.name + (p.me == 1 ? " (this phone)" : ""), value: p.owner == 1 ? "Owner" : "Shared")
                            .swipeActions { if controller.record.owner && p.me == 0 { Button("Remove", role: .destructive) { revoke(p) } } }
                    }
                    if controller.record.owner { Button("Share with Someone", systemImage: "qrcode") { invite() } }
                } header: { Text("People") } footer: {
                    Text(controller.record.owner ? "Sharing shows a code that works once, for 10 minutes." : "Only the owner can share or remove phones.")
                }
                if devMode { Section {
                    NavigationLink { DeveloperView(controller: controller) } label: { Label("Developer", systemImage: "chevron.left.forwardslash.chevron.right") }
                } }
            } else if problem == nil {
                ProgressView()
            }
            if let problem { Section { Label(problem, systemImage: "exclamationmark.triangle").foregroundStyle(.orange) } }
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
        .skyPage()
        .navigationTitle(controller.state?.name ?? controller.record.name)
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .refreshable { await load() }
        .sheet(item: $share) { ShareSheet(info: $0).presentationDetents([.medium, .large]) }
        .sheet(item: $home) { HomeSheet(info: $0).presentationDetents([.medium, .large]) }
    }

    private func remove(reset: Bool) {
        Task {
            if reset { try? await controller.link.send("/api/revoke?cid=all") }
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
            let c: ControllerConfig = try await controller.link.json("/api/cfg")
            cfg = c; name = c.name; problem = nil
            struct K: Decodable { let keys: [PhoneKey] }
            phones = (try? await controller.link.json("/api/keys", as: K.self).keys) ?? []
            if let me = phones.first(where: { $0.me == 1 }) { model.setOwner(controller, me.owner == 1) }      // the owner may have changed
        } catch { problem = error.localizedDescription }
    }
    private func set(_ key: String, _ value: String) {
        Task {
            do { try await controller.link.send("/api/set?k=\(key)&v=\(value.urlQuery)"); await load() } catch { problem = error.localizedDescription }
        }
    }
    private func invite() {
        Task {
            struct I: Decodable { let inv: String; let secret: String; let id: String }
            do {
                let i: I = try await controller.link.json("/api/invite")
                share = ShareInfo(link: "tilt://join?host=\(controller.record.host)&id=\(i.id)&inv=\(i.inv)&secret=\(i.secret)")
            } catch { problem = error.localizedDescription }
        }
    }
    private func revoke(_ p: PhoneKey) {
        Task { do { try await controller.link.send("/api/revoke?cid=\(p.cid)"); await load() } catch { problem = error.localizedDescription } }
    }
    private func openHome() {
        Task {
            struct H: Decodable { let code: String; let qr: String }
            do { let h: H = try await controller.link.json("/api/homeopen"); home = HomeInfo(code: h.code, qr: h.qr) } catch { problem = error.localizedDescription }
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
        .background(.white, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}

struct ShareSheet: View {
    let info: ControllerSettingsView.ShareInfo
    var body: some View {
        NavigationStack {
            VStack(spacing: 18) {
                QRCode(text: info.link).frame(maxWidth: 240)
                Text("On the other phone, open the Camera and point it at this code. It works once, for the next 10 minutes.")
                    .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                ShareLink("Send the Link Instead", item: info.link)
                Spacer(minLength: 0)
            }
            .padding()
            .skyPage()
            .navigationTitle("Share These Blinds").navigationBarTitleDisplayMode(.inline)
        }
    }
}

struct HomeSheet: View {
    let info: ControllerSettingsView.HomeInfo
    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                QRCode(text: info.qr).frame(maxWidth: 220)
                Text(info.code).font(.title2.monospacedDigit().weight(.semibold))
                Text("In the Home app tap +, then Add Accessory, and scan this code. When it says \u{201C}Uncertified Accessory\u{201D}, choose Add Anyway. The controller accepts this for the next 10 minutes.")
                    .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                Spacer(minLength: 0)
            }
            .padding()
            .skyPage()
            .navigationTitle("Add to Apple Home").navigationBarTitleDisplayMode(.inline)
        }
    }
}

struct BlindSettingsView: View {
    let controller: Controller
    let index: Int
    @State var blind: ControllerConfig.Blind
    let reload: () async -> Void
    @State private var name = ""
    @State private var fav = 0.0
    @State private var settingUp = false

    var body: some View {
        Form {
            Section("Name") {
                TextField("Name", text: $name).onSubmit { set("name", name) }.submitLabel(.done)
            }
            Section("Favorite position") {
                HStack(spacing: 14) {
                    SlatView(tilt: fav).frame(width: 64, height: 80)
                    VStack(alignment: .leading) {
                        Text(TiltWords.long(fav))
                        Slider(value: $fav, in: -100...100, step: 5) { editing in if !editing { set("fav", "\(Int(fav))") } }
                    }
                }
            }
            Section {
                Toggle("Show this blind", isOn: Binding(get: { blind.hid == 0 }, set: { blind.hid = $0 ? 0 : 1; set("hid", $0 ? "0" : "1") }))
            } footer: { Text("Turn off for a port with nothing plugged in.") }
            Section {
                Button("Set Up Positions", systemImage: "slider.horizontal.below.rectangle") { settingUp = true }
            } footer: { Text("Mark where this blind is closed up, open, and closed down.") }
        }
        .skyPage()
        .navigationTitle(blind.name).navigationBarTitleDisplayMode(.inline)
        .onAppear { name = blind.name; fav = Double(blind.fav) }
        .fullScreenCover(isPresented: $settingUp) { SetupWizard(controller: controller, index: index, name: blind.name) }
    }
    private func set(_ field: String, _ value: String) {
        Task { try? await controller.link.send("/api/set?k=b\(index).\(field)&v=\(value.urlQuery)"); await reload() }
    }
}
