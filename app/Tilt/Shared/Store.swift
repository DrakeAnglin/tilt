// What the app, Siri and the widget all need: the saved controllers, their keys, and the open / close actions.
import AppIntents
import CryptoKit
import Foundation
import Security
import WidgetKit

struct BlindState: Decodable, Equatable {
    let name: String
    let hid: Int, pres: Int, seen: Int, cal: Int
    let tilt: Double?, tgt: Double?
    let mov: Int, q: Int, fav: Int
    let ang: Double?
    let last: String
    /// Shown in the app: not hidden, and not an empty port.
    var listed: Bool { hid == 0 && !(seen == 1 && pres == 0) }
    var ready: Bool { listed && cal == 1 }
    /// The last move ran the motor but the sensor saw no turn.
    var stuck: Bool { last.hasPrefix("blocked") && mov == 0 && q == 0 }
    var moving: Bool { mov == 1 || q == 1 }
}
struct ControllerState: Decodable, Equatable {
    struct Battery: Decodable, Equatable { let v: Double; let pct: Int; let st: String; let low: Int }
    let v: String, name: String
    let batt: Battery
    let closeUp: Int, sync: Int, mv: Int
    let hk: Int?
    /// Phones that asked to join and wait for an owner.
    let asks: Int?
    /// 1 if this phone is an owner of the controller, 0 if a user.
    let me: Int?
    /// 1 while a gentle (slow, over minutes) move is under way.
    let gentle: Int?
    /// The controller's name in iCloud notices (see Cloud.swift).
    let topic: String?
    let b: [BlindState]
}

/// Saved on the phone (not secret). The key itself is in the Keychain under `id`.
struct ControllerRecord: Codable, Identifiable, Equatable {
    var id: String          // the controller's own id
    var name: String
    var host: String
    var cid: String         // this phone's id on that controller
    var owner: Bool
    /// Asked to join, not approved yet; `code` is what both phones show.
    var waiting: Bool?
    var code: String?
    var topic: String?
}

enum Keychain {
    private static let service = "app.tilt.blinds.keys"
    static func save(_ account: String, _ data: Data) {
        delete(account)
        SecItemAdd([kSecClass: kSecClassGenericPassword, kSecAttrService: service, kSecAttrAccount: account, kSecValueData: data,
                    kSecAttrAccessible: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly] as CFDictionary, nil)
    }
    static func load(_ account: String) -> Data? {
        var out: CFTypeRef?
        let q = [kSecClass: kSecClassGenericPassword, kSecAttrService: service, kSecAttrAccount: account, kSecReturnData: true, kSecMatchLimit: kSecMatchLimitOne] as CFDictionary
        return SecItemCopyMatching(q, &out) == errSecSuccess ? out as? Data : nil
    }
    static func delete(_ account: String) {
        SecItemDelete([kSecClass: kSecClassGenericPassword, kSecAttrService: service, kSecAttrAccount: account] as CFDictionary)
    }
}

/// Talks to the paired controllers without the app's screens (Siri and the widget run these in the background).
enum TiltActions {
    /// The app keeps a copy of its controller list in the Keychain, where the widget can read it.
    static func publish(_ records: [ControllerRecord]) {
        if let d = try? JSONEncoder().encode(records) { Keychain.save("records", d) }
    }
    static func records() -> [ControllerRecord] {
        let d = Keychain.load("records") ?? UserDefaults.standard.data(forKey: Prefs.controllers)
        return d.flatMap { try? JSONDecoder().decode([ControllerRecord].self, from: $0) } ?? []
    }
    /// A client for every controller this phone may use (for Siri, the widget and background checks).
    static func clients() -> [(ControllerRecord, ControllerClient)] {
        records().filter { $0.waiting != true }.compactMap { r in Keychain.load(r.id).map { (r, ControllerClient.make(record: r, key: SymmetricKey(data: $0))) } }
    }
    /// Do one thing on every controller. Throws if none could be reached.
    static func all(_ action: (ControllerClient) async throws -> Void) async throws {
        var reached = 0
        for (_, client) in clients() { if (try? await action(client)) != nil { reached += 1 } }
        if reached == 0 { throw TiltError("Tilt could not reach your blinds. Is this iPhone on your home Wi-Fi?") }
        WidgetCenter.shared.reloadAllTimelines()
    }
    /// One line for a room, for the widget.
    static func words(_ s: ControllerState) -> String { TiltWords.short(s) }
}

struct OpenBlindsIntent: AppIntent {
    static var title: LocalizedStringResource = "Open Blinds"
    static var description = IntentDescription("Opens all your blinds (slats level).")
    func perform() async throws -> some IntentResult { try await TiltActions.all { try await $0.goAll(to: "open") }; return .result() }
}
struct CloseBlindsIntent: AppIntent {
    static var title: LocalizedStringResource = "Close Blinds"
    static var description = IntentDescription("Closes all your blinds.")
    func perform() async throws -> some IntentResult { try await TiltActions.all { try await $0.goAll(to: "close") }; return .result() }
}
