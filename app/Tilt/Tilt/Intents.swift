// Siri and Shortcuts: "Open the blinds with Tilt", "Close the blinds with Tilt", set a position, run a scene.
import AppIntents
import CryptoKit
import Foundation

extension TiltActions {
    static func scenes() -> [BlindScene] {
        UserDefaults.standard.data(forKey: Prefs.scenes).flatMap { try? JSONDecoder().decode([BlindScene].self, from: $0) } ?? []
    }
}

struct SetBlindsIntent: AppIntent {
    static var title: LocalizedStringResource = "Set Blinds"
    static var description = IntentDescription("Sets how far open all your blinds are.")
    @Parameter(title: "Percent open", inclusiveRange: (0, 100)) var percent: Int
    static var parameterSummary: some ParameterSummary { Summary("Set the blinds to \(\.$percent)% open") }
    func perform() async throws -> some IntentResult {
        // The controller closes toward its own "Close" side: ask for the matching share of the way there.
        var reached = 0
        for (_, client) in TiltActions.clients() {
            guard let s = try? await client.state() else { continue }
            let t = (s.closeUp == 1 ? 1 : -1) * (100 - percent)
            for (i, b) in s.b.enumerated() where b.ready { if (try? await client.go(blind: i, tilt: t, solo: true)) != nil { reached += 1 } }
        }
        if reached == 0 { throw TiltError("Tilt could not reach your blinds. Is this iPhone on your home Wi-Fi?") }
        return .result()
    }
}

struct SceneEntity: AppEntity {
    static var typeDisplayRepresentation: TypeDisplayRepresentation = "Scene"
    static var defaultQuery = SceneQuery()
    let id: UUID
    let name: String
    var displayRepresentation: DisplayRepresentation { DisplayRepresentation(title: LocalizedStringResource(stringLiteral: name)) }
}
struct SceneQuery: EntityQuery {
    func entities(for ids: [UUID]) async throws -> [SceneEntity] { TiltActions.scenes().filter { ids.contains($0.id) }.map { SceneEntity(id: $0.id, name: $0.name) } }
    func suggestedEntities() async throws -> [SceneEntity] { TiltActions.scenes().map { SceneEntity(id: $0.id, name: $0.name) } }
}
struct RunSceneIntent: AppIntent {
    static var title: LocalizedStringResource = "Run Scene"
    static var description = IntentDescription("Sets your blinds to one of your Tilt scenes.")
    @Parameter(title: "Scene") var scene: SceneEntity
    static var parameterSummary: some ParameterSummary { Summary("Run \(\.$scene)") }
    func perform() async throws -> some IntentResult {
        guard let sc = TiltActions.scenes().first(where: { $0.id == scene.id }) else { throw TiltError("That scene no longer exists.") }
        let clients = Dictionary(uniqueKeysWithValues: TiltActions.clients().map { ($0.0.id, $0.1) })
        var reached = 0
        for (t, tilt) in sc.tilts { if let c = clients[t.controller], (try? await c.go(blind: t.blind, tilt: tilt, solo: true)) != nil { reached += 1 } }
        if reached == 0 { throw TiltError("Tilt could not reach your blinds. Is this iPhone on your home Wi-Fi?") }
        return .result()
    }
}

struct TiltShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(intent: OpenBlindsIntent(), phrases: ["Open the blinds with \(.applicationName)", "\(.applicationName) open the blinds"], shortTitle: "Open Blinds", systemImageName: "sun.max")
        AppShortcut(intent: CloseBlindsIntent(), phrases: ["Close the blinds with \(.applicationName)", "\(.applicationName) close the blinds"], shortTitle: "Close Blinds", systemImageName: "moon")
        AppShortcut(intent: RunSceneIntent(), phrases: ["Run \(\.$scene) with \(.applicationName)", "\(.applicationName) \(\.$scene)"], shortTitle: "Run Scene", systemImageName: "sparkles")
    }
}
