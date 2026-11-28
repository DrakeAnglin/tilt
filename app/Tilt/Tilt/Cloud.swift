// Notices between phones, through iCloud (CloudKit's public database). Tilt has no server of its own, and a controller
// only talks on its own Wi-Fi, so the phones tell each other two things this way:
//   Join   a phone asked to join a controller: its owners get a push notification, wherever they are.
//   Gone   an owner removed a phone: that phone drops the blinds the next time it opens, even away from home.
// And the Tilt Hub tells owners when something is wrong (Alert records, written by the hub: firmware/tilt_hub/main/cloud.h):
//   Alert  one per topic, kind and blind, replaced each time; an owner's subscription turns each save into a push, and
//          the alerts extension (TiltAlerts) words it with AlertWords.
// What is stored: a random name for the controller ("topic", known only to phones that have talked to it), the name the
// asking person typed, the room's name, and a proof only the removed phone can check. No keys, no addresses.
import CloudKit
import CryptoKit
import Foundation
import os

enum Cloud {
    private static let log = Logger(subsystem: "app.tilt.blinds", category: "cloud")
    @MainActor private static var lastTry: [String: Date] = [:]
    private static let db = CKContainer(identifier: "iCloud.app.tilt.blinds").publicCloudDatabase
    /// A test run (Launch.swift) has no iCloud: an unsigned build may not make a container at all, so every call
    /// returns before it touches one.
    private static var off: Bool { Launch.current.testRun }

    /// Is this phone signed in to iCloud? (Needed to send and get these notices.)
    static func signedIn() async -> Bool {
        guard !off else { return false }
        return (try? await CKContainer(identifier: "iCloud.app.tilt.blinds").accountStatus()) == .available
    }

    /// The asking phone: tell the owners.
    static func postJoin(topic: String, cid: String, who: String, room: String) async {
        guard !off, !topic.isEmpty else { return }
        let r = CKRecord(recordType: "Join", recordID: CKRecord.ID(recordName: "join-\(cid)"))
        r["topic"] = topic; r["who"] = who; r["room"] = room
        do { _ = try await db.save(r) } catch { log.error("join not sent: \(error.localizedDescription)") }
    }
    /// The request was answered or taken back.
    static func clearJoin(cid: String) async { guard !off else { return }; _ = try? await db.deleteRecord(withID: CKRecord.ID(recordName: "join-\(cid)")) }

    /// An owner's phone: get a push when someone asks to join this controller. Done once per controller.
    @MainActor static func watch(topic: String) async {
        guard !off else { return }
        await watchAlerts(topic: topic)
        let key = "cloud.watch.\(topic)"
        guard !topic.isEmpty, !UserDefaults.standard.bool(forKey: key) else { return }
        if let t = lastTry[topic], Date().timeIntervalSince(t) < 300 { return }      // it failed a moment ago (no iCloud account, no internet): try again in 5 minutes
        lastTry[topic] = Date()
        let sub = CKQuerySubscription(recordType: "Join", predicate: NSPredicate(format: "topic == %@", topic), subscriptionID: "join-\(topic)", options: [.firesOnRecordCreation])
        let info = CKSubscription.NotificationInfo()
        info.titleLocalizationKey = "JOIN_TITLE"; info.titleLocalizationArgs = ["who", "room"]
        info.alertLocalizationKey = "JOIN_BODY"
        info.soundName = "default"
        sub.notificationInfo = info
        for attempt in 0..<2 {
            do { _ = try await db.save(sub); UserDefaults.standard.set(true, forKey: key); return }
            catch {
                log.error("watch failed: \(error.localizedDescription)")
                guard attempt == 0 else { return }
                // The very first time, iCloud does not know what a "Join" is yet: save one and take it away again.
                let r = CKRecord(recordType: "Join", recordID: CKRecord.ID(recordName: "join-setup-\(UUID().uuidString)"))
                r["topic"] = "setup"; r["who"] = ""; r["room"] = ""
                if let saved = try? await db.save(r) { _ = try? await db.deleteRecord(withID: saved.recordID) }
            }
        }
    }
    /// No longer an owner (or the controller was removed from this phone).
    static func unwatch(topic: String) async {
        guard !off else { return }
        let key = "cloud.watch.\(topic)", akey = "cloud.alerts.\(topic)"
        if UserDefaults.standard.bool(forKey: akey) {
            _ = try? await db.deleteSubscription(withID: "alert-\(topic)")
            UserDefaults.standard.removeObject(forKey: akey)
        }
        guard UserDefaults.standard.bool(forKey: key) else { return }
        _ = try? await db.deleteSubscription(withID: "join-\(topic)")
        UserDefaults.standard.removeObject(forKey: key)
    }

    /// An owner's phone: the hub's alerts for this controller (or for the hub itself) come as a push. Done once per topic.
    @MainActor static func watchAlerts(topic: String) async {
        let key = "cloud.alerts.\(topic)"
        guard !off, !topic.isEmpty, !UserDefaults.standard.bool(forKey: key) else { return }
        if let t = lastTry["a" + topic], Date().timeIntervalSince(t) < 300 { return }
        lastTry["a" + topic] = Date()
        // Each record is replaced by the next alert of its kind, so a save fires both ways.
        let sub = CKQuerySubscription(recordType: "Alert", predicate: NSPredicate(format: "topic == %@", topic), subscriptionID: "alert-\(topic)",
                                      options: [.firesOnRecordCreation, .firesOnRecordUpdate])
        let info = CKSubscription.NotificationInfo()
        info.titleLocalizationKey = "ALERT_TITLE"; info.titleLocalizationArgs = ["name"]   // if the extension can't run
        info.alertLocalizationKey = "ALERT_BODY"
        info.desiredKeys = ["kind", "name", "detail", "port"]
        info.shouldSendMutableContent = true                                                 // TiltAlerts words it
        info.soundName = "default"
        sub.notificationInfo = info
        do { _ = try await db.save(sub); UserDefaults.standard.set(true, forKey: key) }
        catch { log.error("alerts not watched: \(error.localizedDescription)") }
    }

    /// An owner removed the phone `cid`. `proof` came from the controller, made with that phone's own key.
    static func postGone(cid: String, proof: String) async {
        guard !off, !proof.isEmpty else { return }
        let r = CKRecord(recordType: "Gone", recordID: CKRecord.ID(recordName: "gone-\(cid)"))
        r["proof"] = proof
        do { _ = try await db.save(r) } catch { log.error("removal not sent: \(error.localizedDescription)") }
    }
    /// Was this phone removed from the controller? True only with the controller's proof.
    static func gone(cid: String, key: SymmetricKey) async -> Bool {
        guard !off else { return false }
        let id = CKRecord.ID(recordName: "gone-\(cid)")
        guard let r = try? await db.record(for: id), let proof = r["proof"] as? String else { return false }
        let mine = Data(HMAC<SHA256>.authenticationCode(for: Data("removed".utf8), using: key)).prefix(16).hex
        return proof == mine
    }
}
