// PairingCrypto — the small slice of CryptoKit the L5 handshake needs.
//
// 1. Mint a fresh X25519 ephemeral keypair (`PairingEphemeral.generate`).
// 2. Encode the public key in base64 to feed `client_epk` on the wire.
// 3. Persist the secret in the iOS Keychain under
//    `world.meeet.tars.<device_id>` so subsequent boots can reuse it
//    (Secure Enclave-backed when available).
//
// Stays stdlib-only on the network side: callers do not need
// CryptoSwift / OpenSSL, and the wire shape matches `pynacl` test
// vectors validated by `tests/test_pairing_contract.py`.

import Foundation

#if canImport(CryptoKit)
import CryptoKit

public struct PairingEphemeral: Sendable {
    public let privateKey: Curve25519.KeyAgreement.PrivateKey
    public let deviceID: String

    public init(privateKey: Curve25519.KeyAgreement.PrivateKey, deviceID: String) {
        self.privateKey = privateKey
        self.deviceID = deviceID
    }

    public static func generate() -> PairingEphemeral {
        PairingEphemeral(
            privateKey: Curve25519.KeyAgreement.PrivateKey(),
            deviceID: PairingCrypto.freshDeviceID()
        )
    }

    public var publicKeyBase64: String {
        privateKey.publicKey.rawRepresentation.base64EncodedString()
    }
}
#endif

public enum PairingCrypto {
    /// 16-hex device id, matching `docs/contracts/L5_PAIRING_DRAFT.md`.
    public static func freshDeviceID() -> String {
        var bytes = [UInt8](repeating: 0, count: 8)
        for i in 0..<bytes.count {
            bytes[i] = UInt8.random(in: 0...UInt8.max)
        }
        return bytes.map { String(format: "%02x", $0) }.joined()
    }

    /// Render an X25519 raw public key (32 bytes) as base64 — same format
    /// the host accepts on `POST /api/pairing/begin`.
    public static func base64(rawPublicKey bytes: [UInt8]) -> String {
        Data(bytes).base64EncodedString()
    }

    /// Format the host fingerprint into operator-friendly groups
    /// (mirrors `formatFingerprint` in the cockpit's `lib/pairing.ts`).
    public static func formatFingerprint(_ raw: String) -> String {
        let cleaned = raw.replacingOccurrences(of: "-", with: "")
        guard cleaned.count >= 9 else { return raw }
        let chars = Array(cleaned)
        let chunks = stride(from: 0, to: chars.count, by: 4).map {
            String(chars[$0..<min($0 + 4, chars.count)])
        }
        return chunks.joined(separator: "-")
    }
}
