// WalletClient — read-only wallet surface for the iOS companion.
//
// Mirrors the Cockpit's `lib/wallet.ts` shape but constrained to the
// endpoints the phone actually needs:
//
//   GET  /api/wallet                         → list wallets (no secrets).
//   GET  /api/wallet/{id}                    → single wallet record.
//   GET  /api/wallet/{id}/balance            → live JSON-RPC balance.
//   POST /api/wallet/{id}/sign               → prove ownership (signs
//                                              an ephemeral message; the
//                                              private key never leaves
//                                              the host).
//
// Everything destructive (send / delete / mint) stays on the host —
// the mobile surface is intentionally a viewer + audit lens, not a
// hot wallet.

import Foundation

public struct CompanionWallet: Equatable, Sendable {
    public let id: String
    public let label: String
    public let chain: String
    public let address: String
    public let signingSupported: Bool
    public let derivationScheme: String?
    public let createdAt: Double
}

public struct CompanionBalance: Equatable, Sendable {
    public let chain: String
    public let address: String
    public let raw: String
    public let decimals: Int
    public let symbol: String
    public let display: String
    public let rpcURL: String
}

public enum WalletClientError: Error, Equatable, Sendable {
    case invalidURL
    case http(Int, String)
    case malformed(String)
    case network(String)
}

public actor WalletClient {
    public let baseURL: URL
    private let session: URLSession

    public init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    // MARK: – list

    public func listWallets() async throws -> [CompanionWallet] {
        let data = try await getJSON(path: "/api/wallet")
        return try Self.decodeList(data)
    }

    public func getWallet(id: String) async throws -> CompanionWallet {
        let data = try await getJSON(path: "/api/wallet/\(percentEscape(id))")
        return try Self.decodeSingle(data)
    }

    public func fetchBalance(walletID: String) async throws -> CompanionBalance? {
        let data = try await getJSON(
            path: "/api/wallet/\(percentEscape(walletID))/balance"
        )
        return try Self.decodeBalance(data)
    }

    // MARK: – prove ownership (signs a free-form message; non-destructive)

    public func signOwnershipProof(
        walletID: String,
        timestamp: Date = Date()
    ) async throws -> String {
        let iso = ISO8601DateFormatter().string(from: timestamp)
        let proof = "tars-companion://ownership-proof@\(iso)"
        let body: [String: Any] = ["message": proof]
        let data = try await postJSON(
            path: "/api/wallet/\(percentEscape(walletID))/sign",
            body: body
        )
        return try Self.decodeSignature(data)
    }

    // MARK: – decoders

    static func decodeList(_ data: Data) throws -> [CompanionWallet] {
        let json = try parseObject(data)
        guard let arr = json["wallets"] as? [[String: Any]] else {
            throw WalletClientError.malformed("missing 'wallets' array")
        }
        return arr.compactMap(Self.decodeWalletRow)
    }

    static func decodeSingle(_ data: Data) throws -> CompanionWallet {
        let json = try parseObject(data)
        guard let dict = json["wallet"] as? [String: Any],
              let w = decodeWalletRow(dict) else {
            throw WalletClientError.malformed("missing 'wallet' object")
        }
        return w
    }

    static func decodeBalance(_ data: Data) throws -> CompanionBalance? {
        let json = try parseObject(data)
        // Server can return ok:false when the RPC was unreachable — we
        // surface that as nil rather than an error so the UI can render
        // a "balance unavailable" pill without breaking.
        guard let dict = json["balance"] as? [String: Any] else {
            return nil
        }
        guard let chain = dict["chain"] as? String,
              let address = dict["address"] as? String,
              let raw = dict["raw"] as? String,
              let decimals = dict["decimals"] as? Int,
              let symbol = dict["symbol"] as? String,
              let display = dict["display"] as? String,
              let rpc = dict["rpc_url"] as? String else {
            throw WalletClientError.malformed("balance shape unexpected")
        }
        return CompanionBalance(
            chain: chain,
            address: address,
            raw: raw,
            decimals: decimals,
            symbol: symbol,
            display: display,
            rpcURL: rpc
        )
    }

    static func decodeSignature(_ data: Data) throws -> String {
        let json = try parseObject(data)
        guard let sig = json["signature_b64"] as? String, !sig.isEmpty else {
            throw WalletClientError.malformed("missing 'signature_b64'")
        }
        return sig
    }

    static func decodeWalletRow(_ dict: [String: Any]) -> CompanionWallet? {
        guard let id = dict["id"] as? String,
              let label = dict["label"] as? String,
              let chain = dict["chain"] as? String,
              let address = dict["address"] as? String,
              let signing = dict["signing_supported"] as? Bool,
              let createdAt = dict["created_at"] as? Double else {
            return nil
        }
        return CompanionWallet(
            id: id,
            label: label,
            chain: chain,
            address: address,
            signingSupported: signing,
            derivationScheme: dict["derivation_scheme"] as? String,
            createdAt: createdAt
        )
    }

    // MARK: – HTTP plumbing

    private func getJSON(path: String) async throws -> Data {
        var request = URLRequest(url: try resolve(path))
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        return try await perform(request: request)
    }

    private func postJSON(path: String, body: [String: Any]) async throws -> Data {
        var request = URLRequest(url: try resolve(path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return try await perform(request: request)
    }

    private func perform(request: URLRequest) async throws -> Data {
        do {
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse else {
                throw WalletClientError.malformed("non-HTTP response")
            }
            guard (200..<300).contains(http.statusCode) else {
                let body = String(data: data, encoding: .utf8) ?? ""
                throw WalletClientError.http(http.statusCode, body)
            }
            return data
        } catch let err as WalletClientError {
            throw err
        } catch {
            throw WalletClientError.network(error.localizedDescription)
        }
    }

    private func resolve(_ path: String) throws -> URL {
        guard let url = URL(string: path, relativeTo: baseURL)?.absoluteURL else {
            throw WalletClientError.invalidURL
        }
        return url
    }

    private func percentEscape(_ raw: String) -> String {
        raw.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? raw
    }

    private static func parseObject(_ data: Data) throws -> [String: Any] {
        do {
            guard let any = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                throw WalletClientError.malformed("response is not a JSON object")
            }
            return any
        } catch let err as WalletClientError {
            throw err
        } catch {
            throw WalletClientError.malformed("invalid JSON: \(error.localizedDescription)")
        }
    }
}

public extension CompanionWallet {
    /// "AB12…CD34" for confident, glanceable rendering on small screens.
    var shortenedAddress: String {
        let s = address
        guard s.count > 12 else { return s }
        let prefix = s.prefix(6)
        let suffix = s.suffix(4)
        return "\(prefix)…\(suffix)"
    }
}
