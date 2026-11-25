// Words the Tilt Hub's push alerts. iCloud sends what happened (the Alert record's kind, room name and detail); this
// turns it into Tilt's own words (Shared/Words.swift AlertWords), so the wording lives in one place. If this does not
// run in time, iOS shows the push as it came ("<room> needs a look").
import CloudKit
import UserNotifications

final class NotificationService: UNNotificationServiceExtension {
    override func didReceive(_ request: UNNotificationRequest, withContentHandler done: @escaping (UNNotificationContent) -> Void) {
        guard let c = request.content.mutableCopy() as? UNMutableNotificationContent,
              let note = CKNotification(fromRemoteNotificationDictionary: request.content.userInfo) as? CKQueryNotification,
              let f = note.recordFields, let kind = f["kind"] as? String else { done(request.content); return }
        let room = f["name"] as? String ?? "", detail = f["detail"] as? String ?? ""
        c.title = AlertWords.title(kind: kind, room: room, detail: detail)
        c.body = AlertWords.body(kind: kind, room: room, detail: detail)
        c.threadIdentifier = "alert"
        done(c)
    }
}
