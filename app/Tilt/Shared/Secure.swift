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
    let owned: Int
    let wifi: Int?, ip: String?, home: Int?
}

/// What an invite (the sharing QR code) carries.
struct Invite {
    let host: String, id: String, inv: String, secret: Data
    /// tilt://join?host=…&id=…&inv=…&secret=…
    init?(link: String) {
        guard let c = URLComponents(string: link.trimmingCharacters(in: .whitespacesAndNewlines)), c.scheme == "tilt", c.host == "join" else { return nil }
        func q(_ n: String) -> String? { c.queryItems?.first { $0.name == n }?.value }
        guard let h = q("host"), let i = q("id"), let v = q("inv"), let s = q("secret").flatMap(Data.init(hex:)), s.count == 16 else { return nil }
        host = h; id = i; inv = v; secret = s
    }
}

struct Paired {
    let cid: Data, key: SymmetricKey, owner: Bool
}

enum Secure {
    private static let session: URLSession = {
        let c = URLSessionConfiguration.ephemeral
        c.timeoutIntervalForRequest = 6
        c.waitsForConnectivity = false
        return URLSession(configuration: c)
    }()

    static func http(_ host: String, _ path: String, body: Data? = nil) async throws -> (Int, Data) {
        guard let url = URL(string: "http://\(host)\(path)") else { throw TiltError("That address is not valid.") }
        var r = URLRequest(url: url)
        if let body { r.httpMethod = "POST"; r.httpBody = body; r.setValue("application/octet-stream", forHTTPHeaderField: "Content-Type") }
        let (d, resp) = try await session.data(for: r)
        return ((resp as? HTTPURLResponse)?.statusCode ?? 0, d)
    }

    static func hello(_ host: String) async throws -> Hello {
        let (st, d) = try await http(host, "/x/hello")
        guard st == 200, let h = try? JSONDecoder().decode(Hello.self, from: d) else { throw TiltError("That is not a Tilt controller.") }
        return h
    }

    /// Make this phone's key on a controller. The first phone becomes the owner; later ones need an invite.
    static func pair(host: String, phoneName: String, invite: Invite?) async throws -> Paired {
        try await pair(phoneName: phoneName, invite: invite) { try await http(host, "/x/pair", body: $0) }
    }
    /// The same, through any channel that carries the request and brings back (status, answer).
    static func pair(phoneName: String, invite: Invite?, via: (Data) async throws -> (Int, Data)) async throws -> Paired {
        let priv = P256.KeyAgreement.PrivateKey()
        let cpub = priv.publicKey.x963Representation
        var body: [String: String] = ["pub": cpub.base64EncodedString(), "name": phoneName]
        if let invite {
            body["inv"] = invite.inv
            body["mac"] = Data(HMAC<SHA256>.authenticationCode(for: cpub, using: SymmetricKey(data: invite.secret))).hex
        }
        let (st, d) = try await via(try JSONSerialization.data(withJSONObject: body, options: [.withoutEscapingSlashes]))
        let j = (try? JSONSerialization.jsonObject(with: d)) as? [String: Any] ?? [:]
        guard st == 200, let pub = (j["pub"] as? String).flatMap({ Data(base64Encoded: $0) }), let cid = (j["cid"] as? String).flatMap(Data.init(hex:)),
              let check = j["check"] as? String else { throw TiltError((j["err"] as? String) ?? "Pairing was refused.") }
        let shared = try priv.sharedSecretFromKeyAgreement(with: P256.KeyAgreement.PublicKey(x963Representation: pub))
        let key = shared.hkdfDerivedSymmetricKey(using: SHA256.self, salt: invite?.secret ?? Data(), sharedInfo: Data("blinds-v1".utf8) + cpub + pub, outputByteCount: 32)
        let mine = Data(HMAC<SHA256>.authenticationCode(for: Data("confirm".utf8), using: key)).prefix(8).hex
        guard mine == check else { throw TiltError("The controller's key did not match. Pairing was cancelled.") }
        return Paired(cid: cid, key: key, owner: (j["owner"] as? Int) == 1)
    }
}

/// Sealed commands to one paired controller.
actor Link {
    private(set) var host: String
    private let cid: Data
    private let key: SymmetricKey
    private var boot: Data?
    private var counter: UInt64 = 0

    init(host: String, cid: Data, key: SymmetricKey) { self.host = host; self.cid = cid; self.key = key }

    /// The controller's address changed (found again on the network).
    func move(to newHost: String) { if newHost != host { host = newHost; boot = nil } }

    /// Send "/api/…?…" and return the controller's JSON answer.
    func call(_ command: String) async throws -> Data {
        for attempt in 0..<2 {
            if boot == nil { boot = Data(hex: try await Secure.hello(host).boot) }
            guard let boot, boot.count == 4 else { throw TiltError("The controller gave a bad answer.") }
            counter = max(counter + 1, UInt64(Date().timeIntervalSince1970 * 1000))
            let nonce = boot + withUnsafeBytes(of: counter.bigEndian) { Data($0) }
            let box = try AES.GCM.seal(Data(command.utf8), using: key, nonce: AES.GCM.Nonce(data: nonce), authenticating: Data("blinds-v1".utf8) + cid)
            let (st, d) = try await Secure.http(host, "/x", body: cid + nonce + box.ciphertext + box.tag)
            if st == 200, d.count >= 28 {
                let back = try AES.GCM.SealedBox(nonce: AES.GCM.Nonce(data: d.prefix(12)), ciphertext: d.dropFirst(12).dropLast(16), tag: d.suffix(16))
                return try AES.GCM.open(back, using: key, authenticating: Data("blinds-v1r".utf8) + cid + nonce)
            }
            if st == 409, attempt == 0 { self.boot = nil; continue }          // the controller restarted: get its new number
            if st == 401 { throw TiltError("This phone is no longer paired with the controller.") }
            throw TiltError("The controller refused the command.")
        }
        throw TiltError("The controller did not answer.")
    }

    func json<T: Decodable>(_ command: String, as: T.Type = T.self) async throws -> T {
        try JSONDecoder().decode(T.self, from: try await call(command))
    }

    /// A command whose answer is {"ok":1} or {"ok":0,"err":"…"}.
    func send(_ command: String) async throws {
        struct R: Decodable { let ok: Int; let err: String? }
        let r: R = try await json(command)
        if r.ok != 1 { throw TiltError((r.err ?? "That did not work.").capitalizedFirst) }
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
