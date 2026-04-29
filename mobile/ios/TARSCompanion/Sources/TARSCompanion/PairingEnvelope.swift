// PairingEnvelope — decode the QR / pasteable text payload printed by
// the host's pairing UI (Phase L5 contract § 3.1).
//
// Two formats:
//
//   1. JSON (preferred):
//        { "v": "1", "host_id": "...", "lan_url": "...",
//          "pair_id": "...", "fingerprint": "...", ... }
//
//   2. URL-style fallback (`tars-pair://<host>/<pair_id>?fp=...`)
//      kept for terminals that can't show JSON cleanly.

import Foundation

public struct PairingEnvelope: Equatable, Sendable {
    public let version: String
    public let hostID: String
    public let pairID: String?
    public let lanURL: URL?
    public let relayURL: URL?
    public let fingerprint: String?
    public let expiresAt: Double?

    public init(
        version: String,
        hostID: String,
        pairID: String?,
        lanURL: URL?,
        relayURL: URL?,
        fingerprint: String?,
        expiresAt: Double?
    ) {
        self.version = version
        self.hostID = hostID
        self.pairID = pairID
        self.lanURL = lanURL
        self.relayURL = relayURL
        self.fingerprint = fingerprint
        self.expiresAt = expiresAt
    }
}

public enum PairingEnvelopeError: Error, Equatable {
    case empty
    case unknownFormat
    case missingField(String)
    case malformedJSON(String)
}

public enum PairingEnvelopeParser {
    public static func parse(_ raw: String) throws -> PairingEnvelope {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { throw PairingEnvelopeError.empty }
        if trimmed.hasPrefix("{") {
            return try parseJSON(trimmed)
        }
        if trimmed.hasPrefix("tars-pair://") || trimmed.hasPrefix("tars1") {
            return try parseURL(trimmed)
        }
        throw PairingEnvelopeError.unknownFormat
    }

    static func parseJSON(_ trimmed: String) throws -> PairingEnvelope {
        guard let data = trimmed.data(using: .utf8) else {
            throw PairingEnvelopeError.malformedJSON("non-utf8")
        }
        let object: Any
        do {
            object = try JSONSerialization.jsonObject(with: data)
        } catch {
            throw PairingEnvelopeError.malformedJSON(error.localizedDescription)
        }
        guard let dict = object as? [String: Any] else {
            throw PairingEnvelopeError.malformedJSON("not an object")
        }
        guard let version = dict["v"] as? String else {
            throw PairingEnvelopeError.missingField("v")
        }
        guard let hostID = dict["host_id"] as? String else {
            throw PairingEnvelopeError.missingField("host_id")
        }
        let pairID = dict["pair_id"] as? String
        let lanURL = (dict["lan_url"] as? String).flatMap(URL.init(string:))
        let relayURL = (dict["relay_url"] as? String).flatMap(URL.init(string:))
        let fingerprint = dict["fingerprint"] as? String
        let expiresAt = dict["expires_at"] as? Double
        return PairingEnvelope(
            version: version,
            hostID: hostID,
            pairID: pairID,
            lanURL: lanURL,
            relayURL: relayURL,
            fingerprint: fingerprint,
            expiresAt: expiresAt
        )
    }

    static func parseURL(_ trimmed: String) throws -> PairingEnvelope {
        guard let url = URL(string: trimmed),
              let scheme = url.scheme,
              scheme == "tars-pair" else {
            throw PairingEnvelopeError.unknownFormat
        }
        guard let host = url.host else {
            throw PairingEnvelopeError.missingField("host_id")
        }
        let pairID = url.pathComponents.last { !$0.isEmpty && $0 != "/" }
        let components = URLComponents(url: url, resolvingAgainstBaseURL: false)
        let queryItems = components?.queryItems ?? []
        let fp = queryItems.first { $0.name == "fp" }?.value
        let port = queryItems.first { $0.name == "port" }?.value ?? "8765"
        let lanURL = URL(string: "http://\(host):\(port)")
        return PairingEnvelope(
            version: queryItems.first { $0.name == "v" }?.value ?? "1",
            hostID: queryItems.first { $0.name == "host_id" }?.value ?? host,
            pairID: pairID,
            lanURL: lanURL,
            relayURL: nil,
            fingerprint: fp,
            expiresAt: queryItems.first { $0.name == "expires_at" }?.value.flatMap(Double.init)
        )
    }
}
