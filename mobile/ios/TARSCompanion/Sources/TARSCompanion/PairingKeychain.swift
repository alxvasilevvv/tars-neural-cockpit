// PairingKeychain — minimal Security.framework wrapper for storing the
// per-device X25519 secret + device_id under
// `world.meeet.tars.<device_id>` (matches the namespace pinned by
// `docs/contracts/L5_PAIRING_DRAFT.md` § 5).
//
// On simulator without entitlements the store falls back to NSDefaults
// so pairing flows still demo cleanly.

import Foundation

#if canImport(Security)
import Security
#endif

public protocol PairingSecretStore: Sendable {
    func save(deviceID: String, secret: Data) throws
    func load(deviceID: String) throws -> Data?
    func clear(deviceID: String) throws
}

public enum PairingKeychainError: Error, Equatable {
    case unavailable
    case osStatus(Int32)
}

public struct InMemorySecretStore: PairingSecretStore, @unchecked Sendable {
    private final class Box {
        var values: [String: Data] = [:]
        let queue = DispatchQueue(label: "TARSCompanion.InMemorySecretStore")
    }
    private let box = Box()

    public init() {}

    public func save(deviceID: String, secret: Data) throws {
        box.queue.sync { box.values[deviceID] = secret }
    }
    public func load(deviceID: String) throws -> Data? {
        box.queue.sync { box.values[deviceID] }
    }
    public func clear(deviceID: String) throws {
        box.queue.sync {
            _ = box.values.removeValue(forKey: deviceID)
        }
    }
}

#if canImport(Security)
public struct KeychainSecretStore: PairingSecretStore {
    public let serviceNamespace: String

    public init(serviceNamespace: String = "world.meeet.tars") {
        self.serviceNamespace = serviceNamespace
    }

    private func service(for deviceID: String) -> String {
        "\(serviceNamespace).\(deviceID)"
    }

    public func save(deviceID: String, secret: Data) throws {
        let svc = service(for: deviceID)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: svc,
            kSecAttrAccount as String: deviceID,
        ]
        SecItemDelete(query as CFDictionary)

        var attrs = query
        attrs[kSecValueData as String] = secret
        attrs[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(attrs as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw PairingKeychainError.osStatus(status)
        }
    }

    public func load(deviceID: String) throws -> Data? {
        let svc = service(for: deviceID)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: svc,
            kSecAttrAccount as String: deviceID,
            kSecReturnData as String: kCFBooleanTrue as Any,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess else {
            throw PairingKeychainError.osStatus(status)
        }
        return item as? Data
    }

    public func clear(deviceID: String) throws {
        let svc = service(for: deviceID)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: svc,
            kSecAttrAccount as String: deviceID,
        ]
        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw PairingKeychainError.osStatus(status)
        }
    }
}
#endif
