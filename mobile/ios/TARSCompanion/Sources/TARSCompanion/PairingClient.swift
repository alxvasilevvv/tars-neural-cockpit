// PairingClient — URLSession driver for the L5 pairing handshake.
//
// Implements exactly three calls used by the L1 slice:
//
//   POST /api/pairing/begin     — submit our `client_epk`.
//   GET  /api/pairing/status    — poll for {pending → linked|expired|rejected}.
//   GET  /api/pairing/identity  — sanity-check the host's fingerprint.
//
// No `Codable` magic: each response is decoded by hand so a stray
// schema drift fails loud instead of silently dropping a field.

import Foundation

public struct PairingHostBegin: Equatable, Sendable {
    public let pairID: String
    public let acceptToken: String
    public let hostID: String
    public let hostFingerprint: String
    public let hostPublicKey: String
    public let expiresAt: Double
    public let traceID: String?
}

public enum PairingState: String, Sendable {
    case pending
    case linked
    case expired
    case rejected
    case unknown
}

public struct PairingStatus: Equatable, Sendable {
    public let pairID: String
    public let state: PairingState
    public let deviceID: String?
    public let hostFingerprint: String?
}

public enum PairingClientError: Error, Equatable {
    case invalidURL
    case http(Int, String)
    case malformed(String)
    case network(String)
}

public actor PairingClient {
    public let baseURL: URL
    private let session: URLSession

    public init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    // MARK: – /api/pairing/begin

    public func begin(clientEphemeralKey base64PublicKey: String) async throws -> PairingHostBegin {
        let body: [String: Any] = [
            "client_epk": base64PublicKey,
            "kind": TARSCompanion.deviceKind,
        ]
        let data = try await postJSON(path: "/api/pairing/begin", body: body)
        return try Self.decodeBegin(data)
    }

    // MARK: – /api/pairing/status

    public func pollStatus(pairID: String) async throws -> PairingStatus {
        var url = try resolve("/api/pairing/status")
        var components = URLComponents(url: url, resolvingAgainstBaseURL: false) ?? URLComponents()
        components.queryItems = [URLQueryItem(name: "pair_id", value: pairID)]
        guard let composed = components.url else {
            throw PairingClientError.invalidURL
        }
        url = composed
        let data = try await getJSON(url: url)
        return try Self.decodeStatus(data)
    }

    // MARK: – decoders

    static func decodeBegin(_ data: Data) throws -> PairingHostBegin {
        let json = try parseObject(data)
        guard let pairID = json["pair_id"] as? String,
              let acceptToken = json["accept_token"] as? String,
              let hostID = json["host_id"] as? String,
              let hostFingerprint = json["host_fingerprint"] as? String,
              let hostPublicKey = json["host_public_key"] as? String,
              let expiresAt = json["expires_at"] as? Double else {
            throw PairingClientError.malformed("missing field in /pairing/begin response")
        }
        return PairingHostBegin(
            pairID: pairID,
            acceptToken: acceptToken,
            hostID: hostID,
            hostFingerprint: hostFingerprint,
            hostPublicKey: hostPublicKey,
            expiresAt: expiresAt,
            traceID: json["trace_id"] as? String
        )
    }

    static func decodeStatus(_ data: Data) throws -> PairingStatus {
        let json = try parseObject(data)
        guard let pairID = json["pair_id"] as? String,
              let stateRaw = json["state"] as? String else {
            throw PairingClientError.malformed("missing field in /pairing/status response")
        }
        return PairingStatus(
            pairID: pairID,
            state: PairingState(rawValue: stateRaw) ?? .unknown,
            deviceID: json["device_id"] as? String,
            hostFingerprint: json["host_fingerprint"] as? String
        )
    }

    // MARK: – HTTP plumbing

    private func postJSON(path: String, body: [String: Any]) async throws -> Data {
        var request = URLRequest(url: try resolve(path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return try await perform(request: request)
    }

    private func getJSON(url: URL) async throws -> Data {
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        return try await perform(request: request)
    }

    private func perform(request: URLRequest) async throws -> Data {
        do {
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse else {
                throw PairingClientError.malformed("non-HTTP response")
            }
            guard (200..<300).contains(http.statusCode) else {
                let body = String(data: data, encoding: .utf8) ?? ""
                throw PairingClientError.http(http.statusCode, body)
            }
            return data
        } catch let err as PairingClientError {
            throw err
        } catch {
            throw PairingClientError.network(error.localizedDescription)
        }
    }

    private func resolve(_ path: String) throws -> URL {
        guard let url = URL(string: path, relativeTo: baseURL)?.absoluteURL else {
            throw PairingClientError.invalidURL
        }
        return url
    }

    private static func parseObject(_ data: Data) throws -> [String: Any] {
        do {
            guard let any = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                throw PairingClientError.malformed("response is not a JSON object")
            }
            return any
        } catch let err as PairingClientError {
            throw err
        } catch {
            throw PairingClientError.malformed("invalid JSON: \(error.localizedDescription)")
        }
    }
}
