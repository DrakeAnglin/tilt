// The Tilt Hub page's Integrations section (Apple Home and Alexa), and adding the Tilt Hub to Alexa (issue #18), so an
// Echo can open and close the blinds by voice. Alexa talks Matter to the hub, like Apple Home, with no Tilt cloud.
// Matter lets one hub be in several homes: the hub makes a fresh one-time code (/api/sharecode, 15 minutes, one home)
// and the person types it in the Alexa app. iOS has no way for another app to open Alexa's add screen with the code
// filled in (as Apple Home's can), so Tilt copies the code and opens Alexa.
// The sheets live on the page (HubView), not in a row: a sheet on a List row closes itself when the list redraws.
import SwiftUI

/// Alexa's color on its row (a teal; never Amazon's logo).
let alexaTint = Color(red: 0.0, green: 0.62, blue: 0.78)

/// One home app in the Integrations section: icon, name and a short line; on the right a check when the hub is in it,
/// or an Add button (owners).
struct IntegrationRow: View {
    let icon: String, tint: Color, name: String, detail: String
    let added: Bool, busy: Bool, canAdd: Bool
    let add: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 16, weight: .semibold)).foregroundStyle(.white)
                .frame(width: 32, height: 32)
                .background(tint.gradient, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(name).font(.body.weight(.semibold))
                Text(detail).font(.footnote).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 8)
            if busy {
                SlatLoader(size: 20)
            } else if added {
                Image(systemName: "checkmark.circle.fill").font(.title3).foregroundStyle(Palette.good).accessibilityLabel("Added")
            } else if canAdd {
                Button("Add", action: add).buttonStyle(.borderedProminent).buttonBorderShape(.capsule).controlSize(.small)
                    .accessibilityLabel("Add Tilt Hub to \(name)")
            } else {
                Text("Not added").font(.footnote).foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 4)
    }
}

struct AlexaCode: Identifiable { let code: String; let mins: Int; let first: Bool; var id: String { code } }

/// The code and the few steps in the Alexa app.
struct AlexaSheet: View {
    let info: AlexaCode
    @Environment(\.openURL) private var openURL
    @Environment(\.dismiss) private var dismiss
    @State private var copied = false

    /// The Alexa app, or its App Store page when it is not on this iPhone.
    static let alexaApp = URL(string: "alexa://")!
    static let alexaStore = URL(string: "https://apps.apple.com/app/amazon-alexa/id944011620")!

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 18) {
                    VStack(spacing: 12) {
                        Text("Setup code for Alexa").font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity, alignment: .leading)
                        Text(info.code).font(.title.monospacedDigit().weight(.semibold)).textSelection(.enabled)
                            .accessibilityLabel(info.code.filter(\.isNumber).map(String.init).joined(separator: " "))
                        Text(info.first ? "The hub's own setup code. It takes it for the next \(info.mins) minutes."
                                        : "Good for \(info.mins) minutes, for one Alexa home.").font(.footnote).foregroundStyle(.secondary)
                        HStack(spacing: 10) {
                            Button { copy() } label: { Label(copied ? "Copied" : "Copy Code", systemImage: copied ? "checkmark" : "doc.on.doc").frame(maxWidth: .infinity) }
                                .buttonStyle(.bordered)
                            Button { copy(); openAlexa() } label: { Label("Open Alexa", systemImage: "arrow.up.forward.app").frame(maxWidth: .infinity) }
                                .buttonStyle(.borderedProminent)
                        }
                    }
                    .padding(16).background(Palette.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))

                    VStack(alignment: .leading, spacing: 10) {
                        Text("In the Alexa app").font(.subheadline.weight(.semibold))
                        ForEach(Array(Self.steps(first: info.first).enumerated()), id: \.offset) { n, step in
                            HStack(alignment: .firstTextBaseline, spacing: 10) {
                                Text("\(n + 1)").font(.footnote.weight(.bold)).frame(width: 22, height: 22).background(Palette.accent.opacity(0.2), in: Circle())
                                Text(step).font(.subheadline)
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(16).background(Palette.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))

                    Text("Alexa needs an Echo with Matter in your home, on the same Wi-Fi as the hub. Open and close work by voice and in the Alexa app.")
                        .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
                }
                .padding()
            }
            .navigationTitle("Add to Alexa").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
            .sensoryFeedback(.success, trigger: copied)
        }
    }

    static func steps(first: Bool) -> [String] {
        ["Tap Devices, then +, then Add Device.",
         "Choose Other, then Matter. Say Yes when it asks about a Matter logo.",
         "Choose \u{201C}Try numeric code\u{201D} (or skip the QR code) and paste the code.",
         "If it says the device is not Matter certified, continue.",
         first ? "Pick your home Wi-Fi when Alexa asks, and wait for it to find the blinds."
               : "Wait for Alexa to find the blinds, then put each one in a room."]
    }

    private func copy() { UIPasteboard.general.string = info.code.filter(\.isNumber); copied = true }
    private func openAlexa() {
        openURL(Self.alexaApp) { opened in if !opened { openURL(Self.alexaStore) } }
    }
}
