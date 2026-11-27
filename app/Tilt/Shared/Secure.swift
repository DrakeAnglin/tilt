// The secured connection to one controller: pairing (once) and sealed commands.
// It mirrors firmware/blinds_matter/main/sec.h: P-256 key agreement, HKDF-SHA256, AES-256-GCM.
import CryptoKit
import Foundation

struct TiltError: LocalizedError {
    let message: String
    init(_ m: String) { message = m }
    var errorDescription: String? { message }
}

struct Hello: Decodable {
    let id: String, name: String, fw: String, boot: String
    /// The running firmware's SHA-256 (newer controllers), so an update can be a patch made from exactly it.
    let img: String?
    let owned: Int
    let home: Int?
    /// "thread" (every controller now; older firmware said "wifi"), and whether it heard from its hub lately.
    let net: String?, hub: Int?
}

struct Paired {
    let cid: Data, key: SymmetricKey, owner: Bool
    /// Asked to join: the key works once an owner approves it.
    var waiting = false
    /// The controller's name in iCloud notices.
    var topic = ""
    /// Recovery: the blind whose wand has to be turned.
    var blindName = ""
    /// The 4 digits both phones show for a request to join.
    var code: String { String(format: "%04d", Data(HMAC<SHA256>.authenticationCode(for: Data("code".utf8), using: key)).prefix(2).reduce(0) { $0 << 8 | Int($1) } % 10000) }
    /// This key's request to join, nil when it is in.
    var request: JoinRequest? { waiting ? JoinRequest(code: code) : nil }
}

/// A phone's ask to be let in that an owner has not answered yet; `code` is the 4 digits both phones show.
/// Not Codable: the record that holds it decides how it is saved (HubRecord, Shared/Store.swift).
struct JoinRequest: Equatable { var code: String }

/// Why a sealed command was turned away.
enum LinkProblem: LocalizedError {
    case waiting, notPaired
    var errorDescription: String? { self == .waiting ? "Waiting for an owner to approve this phone." : "This phone is no longer paired with the controller." }
}

enum Secure {
    private static let session: URLSession = {
        let c = URLSessionConfiguration.ephemeral
        c.timeoutIntervalForRequest = 6
        c.waitsForConnectivity = false
        return URLSession(configuration: c)
    }()

    /// Carries one request to "http://<host><path>" (a POST when there is a body) and brings back (status, answer).
    typealias Send = @Sendable (_ host: String, _ path: String, _ body: Data?) async throws -> (Int, Data)
    /// The real way: `http` on this app's own session. Tests give Link, hello, recovery and pair a fake instead.
    static let send: Send = { try await http($0, $1, body: $2) }

    static func http(_ host: String, _ path: String, body: Data? = nil, session: URLSession = Secure.session) async throws -> (Int, Data) {
        guard let url = URL(string: "http://\(host)\(path)") else { throw TiltError("That address is not valid.") }
        var r = URLRequest(url: url)
        if let body { r.httpMethod = "POST"; r.httpBody = body; r.setValue("application/octet-stream", forHTTPHeaderField: "Content-Type") }
        let (d, resp) = try await session.data(for: r)
        return ((resp as? HTTPURLResponse)?.statusCode ?? 0, d)
    }

    static func hello(_ host: String, via send: Send = Secure.send) async throws -> Hello {
        let (st, d) = try await send(host, "/x/hello", nil)
        guard st == 200, let h = try? JSONDecoder().decode(Hello.self, from: d) else { throw TiltError("That is not a Tilt controller.") }
        return h
    }

    /// Make this phone's key on a controller. The first phone becomes an owner; later ones ask to join and wait.
    /// salt: the Tilt Hub's setup code (from its label) when connecting as its first owner; empty otherwise.
    static func pair(host: String, phoneName: String, how: Joining, salt: Data = Data(), via send: Send = Secure.send) async throws -> Paired {
        try await pair(phoneName: phoneName, salt: salt) { try await send(host, how.rawValue, $0) }
    }
    /// The three ways in: the first phone (of a Tilt Hub; a new controller's first phone pairs over Bluetooth), asking an
    /// owner, or proving you are at the window.
    enum Joining: String { case first = "/x/pair", ask = "/x/ask", recover = "/x/recover" }
    /// How far a recovery has got: steps done (0…3) and seconds left; nil when none is running. Throws when no answer
    /// came (through the hub one can be lost: see RecoveryPoll).
    static func recovery(_ host: String, via send: Send = Secure.send) async throws -> (step: Int, left: Int)? {
        struct R: Decodable { let on: Int, step: Int, left: Int }
        let (st, d) = try await send(host, "/x/recstate", nil)
        guard st == 200, let r = try? JSONDecoder().decode(R.self, from: d) else { throw TiltError("No answer about the recovery.") }
        return r.on == 1 ? (r.step, r.left) : nil
    }
    /// The same, through any channel that carries the request and brings back (status, answer).
    static func pair(phoneName: String, salt: Data = Data(), via: (Data) async throws -> (Int, Data)) async throws -> Paired {
        let priv = P256.KeyAgreement.PrivateKey()
        let cpub = priv.publicKey.x963Representation
        let body: [String: String] = ["pub": cpub.base64EncodedString(), "name": phoneName]
        let (st, d) = try await via(try JSONSerialization.data(withJSONObject: body, options: [.withoutEscapingSlashes]))
        let j = (try? JSONSerialization.jsonObject(with: d)) as? [String: Any] ?? [:]
        guard st == 200, let pub = (j["pub"] as? String).flatMap({ Data(base64Encoded: $0) }), let cid = (j["cid"] as? String).flatMap(Data.init(hex:)),
              let check = j["check"] as? String else { throw TiltError((j["err"] as? String) ?? "Pairing was refused.") }
        let shared = try priv.sharedSecretFromKeyAgreement(with: P256.KeyAgreement.PublicKey(x963Representation: pub))
        let (key, checkKey) = pairingKey(shared: shared.withUnsafeBytes { Data($0) }, phone: cpub, controller: pub, salt: salt)
        let mine = Data(HMAC<SHA256>.authenticationCode(for: Data("confirm".utf8), using: checkKey)).prefix(8).hex
        guard mine == check else { throw TiltError("The controller's key did not match. Pairing was cancelled.") }
        return Paired(cid: cid, key: key, owner: (j["owner"] as? Int) == 1, waiting: (j["wait"] as? Int) == 1, topic: (j["topic"] as? String) ?? "", blindName: (j["blindName"] as? String) ?? "")
    }
    /// The Pairing key as sec.h makes it: HKDF-SHA256 of the key agreement's shared secret, salted with the Setup code
    /// (empty when there is none), over "blinds-v1" + the phone's public key + the controller's. `check` is the key the
    /// Pairing check is made with: always without the Setup code (so the answer to one Pairing says nothing about the
    /// code); a wrong code shows up at the first command instead.
    static func pairingKey(shared: Data, phone: Data, controller: Data, salt: Data) -> (key: SymmetricKey, check: SymmetricKey) {
        let secret = SymmetricKey(data: shared), info = Data("blinds-v1".utf8) + phone + controller
        let key = HKDF<SHA256>.deriveKey(inputKeyMaterial: secret, salt: salt, info: info, outputByteCount: 32)
        return (key, salt.isEmpty ? key : HKDF<SHA256>.deriveKey(inputKeyMaterial: secret, salt: Data(), info: info, outputByteCount: 32))
    }
}

/// Watching a recovery's progress: one lost answer through the hub is not the end of it. Only `limit` in a row are.
struct RecoveryPoll {
    let limit = 3
    private(set) var missedInARow = 0
    mutating func answered() { missedInARow = 0 }
    /// One poll got no answer. True: give up.
    mutating func missed() -> Bool { missedInARow += 1; return missedInARow >= limit }
}

/// The secured message format, shared with the firmware (sec.h secDo) and tested against it (Tests/main.swift).
///   command: client id (8) | nonce = boot id (4) + counter (8, big-endian) | AES-256-GCM ciphertext | tag (16),
///            authenticated with "blinds-v1" + client id
///   reply:   nonce (12) | ciphertext | tag (16), authenticated with "blinds-v1r" + client id + the command's nonce
enum Frame {
    static func seal(_ command: String, key: SymmetricKey, cid: Data, boot: Data, counter: UInt64) throws -> (packet: Data, nonce: Data) {
        let nonce = boot + withUnsafeBytes(of: counter.bigEndian) { Data($0) }
        let box = try AES.GCM.seal(Data(command.utf8), using: key, nonce: AES.GCM.Nonce(data: nonce), authenticating: Data("blinds-v1".utf8) + cid)
        return (cid + nonce + box.ciphertext + box.tag, nonce)
    }
    static func open(_ reply: Data, key: SymmetricKey, cid: Data, nonce: Data) throws -> Data {
        let box = try AES.GCM.SealedBox(nonce: AES.GCM.Nonce(data: reply.prefix(12)), ciphertext: reply.dropFirst(12).dropLast(16), tag: reply.suffix(16))
        return try AES.GCM.open(box, using: key, authenticating: Data("blinds-v1r".utf8) + cid + nonce)
    }
}

/// Seals commands for one paired controller, through the Tilt Hub or over Bluetooth. The counter must rise with every command
/// (sec.h nonceFresh): it is the time in milliseconds, or one more than the last one if that is later.
struct Sealer: Sendable {
    let cid: Data, key: SymmetricKey
    private var counter: UInt64 = 0
    private let clock: @Sendable () -> UInt64
    init(cid: Data, key: SymmetricKey, clock: @escaping @Sendable () -> UInt64 = { UInt64(Date().timeIntervalSince1970 * 1000) }) {
        self.cid = cid; self.key = key; self.clock = clock
    }
    mutating func seal(_ command: String, boot: Data) throws -> (packet: Data, nonce: Data) {
        counter = max(counter + 1, clock())
        return try Frame.seal(command, key: key, cid: cid, boot: boot, counter: counter)
    }
    func open(_ reply: Data, nonce: Data) throws -> Data { try Frame.open(reply, key: key, cid: cid, nonce: nonce) }
}

/// Sealed commands to one paired controller.
actor Link: ControllerTransport {
    private(set) var host: String
    private var sealer: Sealer
    private var boot: Data?
    private let send: Secure.Send

    init(host: String, cid: Data, key: SymmetricKey, send: @escaping Secure.Send = Secure.send) {
        self.host = host; sealer = Sealer(cid: cid, key: key); self.send = send
    }

    /// The controller's address changed (found again on the network).
    func move(to newHost: String) { if newHost != host { host = newHost; boot = nil } }

    /// Send "/api/…?…" and return the controller's JSON answer.
    func call(_ command: String) async throws -> Data {
        for attempt in 0..<2 {
            if boot == nil { boot = Data(hex: try await Secure.hello(host, via: send).boot) }
            guard let boot, boot.count == 4 else { throw TiltError("The controller gave a bad answer.") }
            let (packet, nonce) = try sealer.seal(command, boot: boot)
            let (st, d) = try await send(host, "/x", packet)
            if st == 200, d.count >= 28 { return try sealer.open(d, nonce: nonce) }
            if st == 409, attempt == 0 { self.boot = nil; continue }          // the controller restarted: get its new number
            if st == 401 || st == 410 { throw LinkProblem.notPaired }   // 410: the Tilt Hub does not know it (it was reset)
            if st == 403 { throw LinkProblem.waiting }
            throw TiltError("The controller refused the command.")
        }
        throw TiltError("The controller did not answer.")
    }
}

extension Data {
    init?(hex: String) {
        guard hex.count % 2 == 0 else { return nil }
        var d = Data(capacity: hex.count / 2)
        var i = hex.startIndex
        while i < hex.endIndex {
            let j = hex.index(i, offsetBy: 2)
            guard let b = UInt8(hex[i..<j], radix: 16) else { return nil }
            d.append(b)
            i = j
        }
        self = d
    }
    var hex: String { map { String(format: "%02x", $0) }.joined() }
}
extension String {
    var capitalizedFirst: String { prefix(1).uppercased() + dropFirst() }
    var urlQuery: String { addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? self }
}
