// Low-battery notices, made on the phone (there is no server to push them): whenever Tilt hears from a controller,
// in the app or during iOS's background refresh, and its battery is low, the phone shows a notification.
// At most one a day per controller.
import BackgroundTasks
import Foundation
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

enum BatteryAlerts {
    static let refreshId = "app.tilt.blinds.refresh"

    /// A removed controller starts fresh if it is added again.
    static func forget(id: String) { UserDefaults.standard.removeObject(forKey: "lowbatt.\(id)") }
    static func askPermission() { UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { _, _ in } }

    static func check(id: String, name: String, battery: ControllerState.Battery) {
        guard !battery.charging, battery.isLow else { return }
        let key = "lowbatt.\(id)", last = UserDefaults.standard.double(forKey: key), now = Date().timeIntervalSince1970
        guard now - last > 86400 else { return }
        UserDefaults.standard.set(now, forKey: key)
        let c = UNMutableNotificationContent()
        c.title = "\(name): battery low"
        c.body = battery.isCritical ? "The battery is almost empty, so Schedules are paused. Plug in the charging cable." : "The battery is at \(battery.pct)%. Plug in the charging cable soon."
        c.sound = .default
        UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: key, content: c, trigger: nil))
    }

    /// For trying it out: the same notice, 5 seconds from now (leave the app to see it).
    static func test(name: String) {
        askPermission()
        let c = UNMutableNotificationContent()
        c.title = "\(name): battery low"
        c.body = "The battery is at 15%. Plug in the charging cable soon. (This is a test.)"
        c.sound = .default
        UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: "lowbatt.test", content: c, trigger: UNTimeIntervalNotificationTrigger(timeInterval: 5, repeats: false)))
    }

    static func scheduleRefresh() {
        let r = BGAppRefreshTaskRequest(identifier: refreshId)
        r.earliestBeginDate = Date(timeIntervalSinceNow: 4 * 3600)
        try? BGTaskScheduler.shared.submit(r)
    }
    /// Run by iOS now and then while the app is closed.
    static func backgroundCheck() async {
        scheduleRefresh()
        for (rec, client) in TiltActions.clients() {
            guard let s = try? await client.state() else { continue }
            check(id: rec.id, name: s.name, battery: s.batt)
            if rec.owner, (s.asks ?? 0) > 0 { JoinAlerts.notify(cid: "any.\(rec.id)", who: "Someone", room: s.name) }
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
