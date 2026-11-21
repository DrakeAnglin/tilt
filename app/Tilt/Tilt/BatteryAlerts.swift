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
}

enum BatteryAlerts {
    static let refreshId = "app.tilt.blinds.refresh"

    /// A removed controller starts fresh if it is added again.
    static func forget(id: String) { UserDefaults.standard.removeObject(forKey: "lowbatt.\(id)") }
    static func askPermission() { UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { _, _ in } }

    static func check(id: String, name: String, battery: ControllerState.Battery) {
        guard battery.st == "battery", battery.low == 1 || battery.pct < 20 else { return }
        let key = "lowbatt.\(id)", last = UserDefaults.standard.double(forKey: key), now = Date().timeIntervalSince1970
        guard now - last > 86400 else { return }
        UserDefaults.standard.set(now, forKey: key)
        let c = UNMutableNotificationContent()
        c.title = "\(name): battery low"
        c.body = battery.low == 1 ? "The battery is too low to move the blinds. Plug in the charging cable." : "The battery is at \(battery.pct)%. Plug in the charging cable soon."
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
        BGTaskScheduler.shared.submitTaskRequest(r) { _ in }
    }
    /// Run by iOS now and then while the app is closed.
    static func backgroundCheck() async {
        scheduleRefresh()
        for (rec, link) in TiltActions.links() {
            if let s: ControllerState = try? await link.json("/api/s") { check(id: rec.id, name: s.name, battery: s.batt) }
        }
    }
}
