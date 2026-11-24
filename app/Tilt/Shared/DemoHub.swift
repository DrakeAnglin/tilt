// The demo hub: a pretend Tilt Hub inside the app, the hub's second adapter after the secured link (like Demo is for a
// controller). It answers the same commands as a real hub (HubApi) from memory: the demo room is its one controller,
// this iPhone its one owner. HubClient.make picks it for a hub record whose host is Demo.host.
import Foundation

actor DemoHub: ControllerTransport {
    nonisolated var host: String { Demo.host }
    func move(to host: String) {}
    func call(_ command: String) async throws -> Data { answer(command) }

    static let shared = DemoHub()
    /// The hub's own key on the demo room (its request to join, already let in).
    static let hubCid = "00000000000000d0"

    private var started = Date()
    private var people: [[String: Any]] = [["cid": "demo", "name": "You", "owner": 1, "me": 1, "wait": 0, "code": ""]]

    func answer(_ command: String) -> Data {
        let parts = command.split(separator: "?", maxSplits: 1)
        let path = String(parts.first ?? "")
        var q: [String: String] = [:]
        for kv in (parts.count > 1 ? parts[1] : "").split(separator: "&") {
            let p = kv.split(separator: "=", maxSplits: 1)
            q[String(p[0])] = p.count > 1 ? String(p[1]) : ""
        }
        var out: [String: Any] = ["ok": 1]
        switch path {
        case HubApi.info:
            let room: [String: Any] = ["id": Demo.id, "name": "Living Room (Demo)", "fw": "2.2.0", "key": 2, "seenS": 4, "pct": 82, "low": 0,
                                       "rssi": -48, "lqi": 3, "ota": 0, "otaPct": 0, "hubCid": Self.hubCid, "own": 1]
            out = ["ok": 1, "hub": "tilt", "fw": "0.3.5", "up": Int(Date().timeIntervalSince(started)), "ip": Demo.host, "wifi": -52, "ch": 15,
                   "c": [room], "homes": [], "home": 0, "new": []]
        case HubApi.keys:
            out = ["ok": 1, "keys": people]
        case "/api/approve":
            if let i = people.firstIndex(where: { $0["cid"] as? String == q["cid"] }), people[i]["wait"] as? Int == 1 {
                if q["ok"] == "1" { people[i]["wait"] = 0; people[i]["owner"] = q["owner"] == "1" ? 1 : 0 } else { people.remove(at: i) }
            } else { out = ["ok": 0, "err": "no such phone"] }
        case "/api/revoke":
            if q["cid"] == "demo" { out = ["ok": 0, "err": "you cannot remove yourself"] } else { people.removeAll { $0["cid"] as? String == q["cid"] } }
        case HubApi.network:
            out = ["ok": 1, "ds": "0e080000000000010000"]
        case HubApi.backups:
            out = ["ok": 1, "b": []]
        case "/api/backup":
            out = ["ok": 0, "err": "no backup of that controller"]
        case HubApi.homeCode, HubApi.shareCode:
            out = ["ok": 0, "err": "Apple Home is not available in the demo."]
        case HubApi.leave, HubApi.resetPeople:
            out = ["ok": 0, "err": "the demo hub keeps its owner"]
        default:
            break                                    // everything else just succeeds
        }
        return (try? JSONSerialization.data(withJSONObject: out)) ?? Data("{\"ok\":1}".utf8)
    }
}
