// The demo room: a pretend controller inside the app, for trying Tilt without one (and for App Review, which has no
// hardware). It answers the same commands as a real controller (see Api.swift), and its blinds move over time.
import Foundation

actor Demo: ControllerTransport {
    nonisolated var host: String { Demo.host }
    func move(to host: String) {}
    func call(_ command: String) async throws -> Data { answer(command) }

    static let host = "demo"
    static let id = "demo"
    static let shared = Demo()

    private struct Blind { var name: String; var from: Double; var to: Double; var started: Date?; var hidden = false }
    private var name = "Living Room (Demo)"
    private var blinds = [Blind(name: "Left", from: 0, to: 0), Blind(name: "Middle", from: 0, to: 0), Blind(name: "Right", from: 60, to: 60)]
    private var closeUp = 1, sync = 0, par = 1, hksep = 0
    private var slots: [[String: Any]] = (0..<8).map { i in
        i == 0 ? ["on": 1, "days": 127, "mask": 7, "min": 0, "tilt": -100, "kind": 2, "off": 0, "ramp": 10, "gid": 1]
               : ["on": 0, "days": 0, "mask": 0, "min": 0, "tilt": 0, "kind": 0, "off": 0, "ramp": 0, "gid": 0]
    }
    private let speed = 40.0                         // tilt units a second, about like the real tilter

    private func tilt(_ b: Blind, at now: Date) -> Double {
        guard let s = b.started else { return b.to }
        let gone = now.timeIntervalSince(s) * speed, span = b.to - b.from
        return abs(span) <= gone ? b.to : b.from + (span > 0 ? gone : -gone)
    }
    private func moving(_ b: Blind, at now: Date) -> Bool { b.started != nil && tilt(b, at: now) != b.to }
    private func go(_ i: Int, _ t: Double) {
        let now = Date()
        blinds[i].from = tilt(blinds[i], at: now); blinds[i].to = max(-100, min(100, t)); blinds[i].started = now
    }

    func answer(_ command: String) -> Data {
        let parts = command.split(separator: "?", maxSplits: 1)
        let path = String(parts.first ?? "")
        var q: [String: String] = [:]
        for kv in (parts.count > 1 ? parts[1] : "").split(separator: "&") {
            let p = kv.split(separator: "=", maxSplits: 1)
            q[String(p[0])] = p.count > 1 ? (String(p[1]).removingPercentEncoding ?? String(p[1])) : ""
        }
        let now = Date()
        var out: [String: Any] = ["ok": 1]
        switch path {
        case Api.state:
            let b = blinds.map { bl -> [String: Any] in
                let t = tilt(bl, at: now), m = moving(bl, at: now)
                return ["name": bl.name, "hid": bl.hidden ? 1 : 0, "pres": 1, "seen": 1, "cal": 1, "tilt": t, "tgt": bl.to,
                        "mov": m ? 1 : 0, "q": 0, "fav": 0, "ang": 0, "last": "ok"]
            }
            out = ["v": "2.2.0", "name": name, "batt": ["v": 3.9, "pct": 82, "st": "battery", "low": 0],
                   "closeUp": closeUp, "sync": sync, "mv": blinds.firstIndex { moving($0, at: now) } ?? -1,
                   "hk": 0, "asks": 0, "me": 1, "gentle": 0, "b": b]
        case Api.config:
            let day = Calendar.current.startOfDay(for: now).timeIntervalSince1970
            out = ["name": name, "ports": blinds.count, "slots": slots.count, "closeUp": closeUp, "sync": sync, "par": par, "tzn": TimeZone.current.identifier, "hksep": hksep,
                   "b": blinds.map { ["name": $0.name, "hid": $0.hidden ? 1 : 0, "speed": 100, "fav": 0] },
                   "sched": slots, "sun": [day + 7 * 3600, day + 17.5 * 3600]]
        case Api.keys:
            out = ["keys": [["cid": "demo", "name": UserDefaults.standard.string(forKey: Prefs.myName) ?? "You", "owner": 1, "me": 1, "wait": 0, "code": ""]]]
        case "/api/go":
            let all = q["b"] == "all", one = Int(q["b"] ?? "") ?? 0
            let word = q["to"]
            let target: Double = word == "open" ? 0 : word == "close" ? (closeUp == 1 ? 100 : -100) : Double(q["t"] ?? "") ?? 0
            if all || (sync == 1 && q["solo"] == nil) { for i in blinds.indices where !blinds[i].hidden { go(i, target) } }
            else if blinds.indices.contains(one) { go(one, target) }
        case Api.stop:
            for i in blinds.indices { let t = tilt(blinds[i], at: now); blinds[i].from = t; blinds[i].to = t; blinds[i].started = nil }
        case "/api/jog":
            let i = Int(q["b"] ?? "") ?? 0, d = Double(q["d"] ?? "") ?? 0
            if blinds.indices.contains(i) { go(i, tilt(blinds[i], at: now) + d * 8) }
        case "/api/sched":
            if let i = Int(q["i"] ?? ""), slots.indices.contains(i) {
                for k in ["on", "days", "mask", "min", "tilt", "kind", "off", "ramp", "gid"] { slots[i][k] = Int(q[k] ?? "") ?? 0 }
            }
        case "/api/set":
            let k = q["k"] ?? "", v = q["v"] ?? ""
            switch k {
            case "name": name = v
            case "closeUp": closeUp = Int(v) ?? 1
            case "sync": sync = Int(v) ?? 0
            case "par": par = Int(v) ?? 1
            case "hksep": hksep = Int(v) ?? 0
            default:
                // b0.name, b1.hid …
                let p = k.dropFirst().split(separator: ".")
                if p.count == 2, let i = Int(p[0]), blinds.indices.contains(i) {
                    if p[1] == "name" { blinds[i].name = v } else if p[1] == "hid" { blinds[i].hidden = v == "1" }
                }
            }
        case Api.homeOpen:
            out = ["ok": 0, "err": "Apple Home is not available in the demo."]
        case Api.dev:
            out = [:]
        case Api.log:
            out = ["log": ["demo room started"]]
        default:
            break                                    // everything else just succeeds
        }
        return (try? JSONSerialization.data(withJSONObject: out)) ?? Data("{\"ok\":1}".utf8)
    }
}
