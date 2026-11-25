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

    static func check(id: String, name: String, battery: ControllerState.Battery) {
        BatteryNotices.check(id: id, name: name, reading: battery.reading, via: PhoneNotifier())
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
    /// From what a Tilt Hub reports (no controller is woken for it): the same rule as a reading from the controller.
    static func check(member m: HubInfo.Member) {
        guard let r = BatteryReading.fromHub(pct: m.pct, low: m.low, chg: m.chg) else { return }
        BatteryNotices.check(id: m.id, name: m.name, reading: r, via: PhoneNotifier())
    }
    /// The hub has not heard from a controller for 25 minutes (unplugged, flat, or out of range of the hub).
    static func notResponding(id: String, name: String, now: Date = .now) {
        let key = "noresp.\(id)", n = PhoneNotifier()
        if let last = n.lastSent(key), now.timeIntervalSince(last) <= 43200 { return }
        n.send(key, title: "\(name) is not responding", body: "Your Tilt Hub has not heard from it for a while. Check that its battery is charged and that it is within reach of the hub.", at: now)
    }

    /// Run by iOS now and then while the app is closed. Controllers on a Tilt Hub are checked through the hub (it
    /// knows their battery and when each last checked in), so none of them is woken; the others are asked directly.
    static func backgroundCheck() async {
        scheduleRefresh()
        var onHub: Set<String> = []
        if let info = await HubWatch.fetchInfo() {
            for m in info.c {
                onHub.insert(m.id)
                check(member: m)
                if m.seenS > HubInfo.Member.silentAfter { notResponding(id: m.id, name: m.name) }
            }
        }
        for (rec, client) in TiltActions.clients() where !onHub.contains(rec.id) {
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
