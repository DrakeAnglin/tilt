/// A name as the controller keeps it: a Scene, a blind or the controller. UTF-8 as typed (quotes, the curly apostrophe,
/// accents, emoji), without control characters, at most so many bytes, never cut inside a character. The firmware's twin
/// is wire.h keptName, so what was typed is what every phone, the Tilt Hub and Apple Home read back.
enum NameRule {
    /// The longest blind name a controller keeps, in UTF-8 bytes (firmware store.h BlindCfg name[20]).
    static let blindBytes = 19
    /// The longest controller name, in UTF-8 bytes (firmware store.h Settings name[24]).
    static let controllerBytes = 23

    /// A name as it can be typed: no control characters, at most `bytes` bytes, never cut inside a character.
    static func limit(_ s: String, bytes: Int) -> String {
        var out = ""
        for ch in s where !ch.unicodeScalars.contains(where: { $0.value < 32 || $0.value == 127 }) {
            if out.utf8.count + String(ch).utf8.count > bytes { break }
            out.append(ch)
        }
        return out
    }
    /// A name as the controller keeps it: limited, without trailing spaces.
    static func fit(_ s: String, bytes: Int) -> String {
        var n = limit(s, bytes: bytes)
        while n.hasSuffix(" ") { n.removeLast() }
        return n
    }
}
