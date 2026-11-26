// Notices made on the phone itself. Everything a Tilt Hub knows comes as a push from the hub instead (Cloud.swift,
// firmware/tilt_hub/main/cloud.h), so these are only:
//   - low battery of a controller that is NOT on a Tilt Hub (whenever Tilt hears from it, at most once a day), and
//   - "Tilt Hub is offline": on the home Wi-Fi, the hub can't be reached (the hub can't send that one itself).
import BackgroundTasks
import Foundation
import Network
import UserNotifications

/// Shows Tilt's notices as a banner even while the app is open.
final class NoticePresenter: NSObject, UNUserNotificationCenterDelegate {
    static let shared = NoticePresenter()
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification) async -> UNNotificationPresentationOptions { [.banner, .list, .sound] }
    /// A notice was tapped: a request to join opens its page. (The completion-handler form: iOS wants it finished on the main thread.)
    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse, withCompletionHandler done: @escaping () -> Void) {
        let r = response.notification.request
        let join = r.identifier.hasPrefix("ask.") || r.content.userInfo["ck"] != nil
        DispatchQueue.main.async {
            if join { NotificationCenter.default.post(name: .tiltJoinTapped, object: nil) }
            done()
        }
    }
}

/// The phone's notifications, and when each was last sent (UserDefaults).
struct PhoneNotifier: Notifier {
    func lastSent(_ key: String) -> Date? {
        let t = UserDefaults.standard.double(forKey: key)
        return t > 0 ? Date(timeIntervalSince1970: t) : nil
    }
    func send(_ key: String, title: String, body: String, at: Date) {
        UserDefaults.standard.set(at.timeIntervalSince1970, forKey: key)
        let c = UNMutableNotificationContent()
        c.title = title
        c.body = body
        c.sound = .default
        UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: key, content: c, trigger: nil))
    }
}

enum BatteryAlerts {
    static let refreshId = "app.tilt.blinds.refresh"

    /// A removed controller starts fresh if it is added again.
    static func forget(id: String) { UserDefaults.standard.removeObject(forKey: BatteryNotices.key(id: id)) }
    static func askPermission() { UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { _, _ in } }

    static func check(id: String, name: String, reading: BatteryReading) {
        BatteryNotices.check(id: id, name: name, reading: reading, via: PhoneNotifier())
    }

    /// For trying it out: the same notice, 5 seconds from now (leave the app to see it).
    static func test(name: String) {
        askPermission()
        let c = UNMutableNotificationContent(), n = BatteryNotice.low(pct: 15)
        c.title = n.title(name: name)
        c.body = n.body + " (This is a test.)"
        c.sound = .default
        UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: "lowbatt.test", content: c, trigger: UNTimeIntervalNotificationTrigger(timeInterval: 5, repeats: false)))
    }

    static func scheduleRefresh() {
        let r = BGAppRefreshTaskRequest(identifier: refreshId)
        r.earliestBeginDate = Date(timeIntervalSinceNow: 4 * 3600)
        try? BGTaskScheduler.shared.submit(r)
    }
    /// Run by iOS now and then while the app is closed. Controllers on a Tilt Hub are left alone (the hub sends their
    /// alerts itself, and none of them is woken); the others are asked directly. And: is the hub still there?
    static func backgroundCheck() async {
        scheduleRefresh()
        if let r = HubWatch.loadRecord(), r.request == nil {
            var info = await HubWatch.fetchInfo()
            if info == nil { try? await Task.sleep(for: .seconds(20)); info = await HubWatch.fetchInfo() }   // not a restart of a moment
            if info != nil { await HubOffline.answered() } else if r.owner { await HubOffline.missed(since: nil) }
        }
        for (rec, client) in TiltActions.clients() where !rec.onHub {
            guard let s = try? await client.state() else { continue }
            check(id: rec.id, name: s.name, reading: s.batt.reading)
            if rec.owner, (s.asks ?? 0) > 0 { JoinAlerts.notify(cid: "any.\(rec.id)", who: "Someone", room: s.name) }
        }
    }
}

/// "Tilt Hub is offline": the hub can't tell anyone that itself, so an owner's phone does, once per outage, and only on
/// the home Wi-Fi (away from home a hub out of reach is normal). Home = the same Wi-Fi router as when the hub last
/// answered. Not for a moment's restart (an update): only after it has been out of reach for a few minutes.
enum HubOffline {
    private static let sentKey = "huboff.sent", routerKey = "huboff.router", firstKey = "huboff.first"
    static let after: TimeInterval = 180

    static func answered() async {
        UserDefaults.standard.removeObject(forKey: sentKey)
        UserDefaults.standard.removeObject(forKey: firstKey)
        if let r = await wifiRouter() { UserDefaults.standard.set(r, forKey: routerKey) }
    }
    /// since: when the app first missed it in a row (nil: from the background check, which keeps its own first miss,
    /// so it too tells only once the hub has been out of reach for `after`).
    static func missed(since: Date?) async {
        let d = UserDefaults.standard
        var first = since
        if first == nil {
            let t = d.double(forKey: firstKey)
            if t > 0 { first = Date(timeIntervalSince1970: t) } else { d.set(Date().timeIntervalSince1970, forKey: firstKey); return }
        }
        if let first, Date().timeIntervalSince(first) < after { return }
        guard !UserDefaults.standard.bool(forKey: sentKey), let home = UserDefaults.standard.string(forKey: routerKey),
              let now = await wifiRouter(), now == home else { return }
        UserDefaults.standard.set(true, forKey: sentKey)
        let c = UNMutableNotificationContent()
        c.title = AlertWords.title(kind: "hub-offline", room: "Tilt Hub", detail: "")
        c.body = AlertWords.body(kind: "hub-offline", room: "Tilt Hub", detail: "")
        c.sound = .default
        try? await UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: "huboff", content: c, trigger: nil))
    }
    /// The Wi-Fi router this iPhone is on now (nil: not on Wi-Fi).
    static func wifiRouter() async -> String? {
        await withCheckedContinuation { (done: CheckedContinuation<String?, Never>) in
            let m = NWPathMonitor(requiredInterfaceType: .wifi)
            m.pathUpdateHandler = { p in
                m.cancel()
                done.resume(returning: p.status == .satisfied ? p.gateways.first.map { "\($0)" } : nil)
            }
            m.start(queue: .global())
        }
    }
}

/// A phone asked to join a controller this phone owns: one notice per request.
enum JoinAlerts {
    static func notify(cid: String, who: String, room: String) {
        let key = "ask.\(cid)"
        guard !UserDefaults.standard.bool(forKey: key) else { return }
        UserDefaults.standard.set(true, forKey: key)
        let c = UNMutableNotificationContent()
        c.title = "\(who) wants to join \(room)"
        c.body = "Open Tilt to approve or decline."
        c.sound = .default
        UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: key, content: c, trigger: nil))
    }
}
