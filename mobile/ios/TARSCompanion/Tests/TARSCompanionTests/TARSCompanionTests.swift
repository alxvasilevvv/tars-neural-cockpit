// Unit tests for the pure-Swift slice of the L1 pairing flow.
//
// We don't stand up a real URLSession against a backend here — the
// `PairingClient` decoders are exercised against fixed JSON fixtures
// matching `tests/test_pairing_contract.py` on the host side.

import XCTest
@testable import TARSCompanion

final class TARSCompanionTests: XCTestCase {
    func testVersionMetadataIsStable() {
        XCTAssertFalse(TARSCompanion.version.isEmpty)
        XCTAssertEqual(TARSCompanion.contractVersion, "1.0.0")
        XCTAssertEqual(TARSCompanion.deviceKind, "mobile_ios")
    }

    func testFreshDeviceIDShape() {
        for _ in 0..<32 {
            let id = PairingCrypto.freshDeviceID()
            XCTAssertEqual(id.count, 16)
            XCTAssertTrue(id.allSatisfy { c in
                c.isHexDigit && c.isLowercase || c.isNumber
            }, "device_id must be lowercase hex: got \(id)")
        }
    }

    func testFingerprintFormatting() {
        XCTAssertEqual(PairingCrypto.formatFingerprint("QXr78mB9nJ2L"), "QXr7-8mB9-nJ2L")
        XCTAssertEqual(PairingCrypto.formatFingerprint("QXr7-8mB9-nJ2L"), "QXr7-8mB9-nJ2L")
        XCTAssertEqual(PairingCrypto.formatFingerprint("ABCD"), "ABCD")
    }

    func testEnvelopeJSONParse() throws {
        let raw = """
        {"v":"1","host_id":"a1b2c3d4e5f60718","pair_id":"9988aa77ccd00ff1",
         "expires_at":1745798400,"lan_url":"http://192.168.1.42:8765",
         "fingerprint":"QXr7-8mB9-nJ2L"}
        """
        let env = try PairingEnvelopeParser.parse(raw)
        XCTAssertEqual(env.version, "1")
        XCTAssertEqual(env.hostID, "a1b2c3d4e5f60718")
        XCTAssertEqual(env.pairID, "9988aa77ccd00ff1")
        XCTAssertEqual(env.fingerprint, "QXr7-8mB9-nJ2L")
        XCTAssertEqual(env.lanURL?.absoluteString, "http://192.168.1.42:8765")
    }

    func testEnvelopeURLParse() throws {
        let raw = "tars-pair://a1b2c3d4e5f60718/9988aa77ccd00ff1?fp=QXr7-8mB9-nJ2L&port=9000"
        let env = try PairingEnvelopeParser.parse(raw)
        XCTAssertEqual(env.hostID, "a1b2c3d4e5f60718")
        XCTAssertEqual(env.pairID, "9988aa77ccd00ff1")
        XCTAssertEqual(env.fingerprint, "QXr7-8mB9-nJ2L")
        XCTAssertEqual(env.lanURL?.absoluteString, "http://a1b2c3d4e5f60718:9000")
    }

    func testEnvelopeRejectsEmptyAndUnknown() {
        XCTAssertThrowsError(try PairingEnvelopeParser.parse("")) { err in
            XCTAssertEqual(err as? PairingEnvelopeError, .empty)
        }
        XCTAssertThrowsError(try PairingEnvelopeParser.parse("garbage"))
    }

    func testBeginResponseDecoder() throws {
        let raw = """
        {"ok":true,"trace_id":"trace-9","pair_id":"9988aa77ccd00ff1",
         "accept_token":"tok-123","host_id":"a1b2c3d4e5f60718",
         "host_fingerprint":"QXr7-8mB9-nJ2L",
         "host_public_key":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
         "expires_at":1745798400.0}
        """
        let data = raw.data(using: .utf8)!
        let begin = try PairingClient.decodeBegin(data)
        XCTAssertEqual(begin.pairID, "9988aa77ccd00ff1")
        XCTAssertEqual(begin.acceptToken, "tok-123")
        XCTAssertEqual(begin.hostFingerprint, "QXr7-8mB9-nJ2L")
        XCTAssertEqual(begin.expiresAt, 1745798400.0)
        XCTAssertEqual(begin.traceID, "trace-9")
    }

    func testBeginResponseDecoderRejectsMissingFields() {
        let raw = #"{"ok":true,"pair_id":"x"}"#
        let data = raw.data(using: .utf8)!
        XCTAssertThrowsError(try PairingClient.decodeBegin(data))
    }

    func testStatusResponseDecoder() throws {
        let raw = """
        {"ok":true,"pair_id":"9988aa77ccd00ff1","state":"linked",
         "device_id":"feedface00112233","host_fingerprint":"QXr7-8mB9-nJ2L"}
        """
        let data = raw.data(using: .utf8)!
        let status = try PairingClient.decodeStatus(data)
        XCTAssertEqual(status.state, .linked)
        XCTAssertEqual(status.deviceID, "feedface00112233")
    }

    func testStatusResponseDecoderUnknownState() throws {
        let raw = #"{"ok":true,"pair_id":"x","state":"weird"}"#
        let data = raw.data(using: .utf8)!
        let status = try PairingClient.decodeStatus(data)
        XCTAssertEqual(status.state, .unknown)
    }

    func testInMemorySecretStoreRoundTrip() throws {
        let store = InMemorySecretStore()
        try store.save(deviceID: "dev1", secret: Data([1, 2, 3]))
        XCTAssertEqual(try store.load(deviceID: "dev1"), Data([1, 2, 3]))
        try store.clear(deviceID: "dev1")
        XCTAssertNil(try store.load(deviceID: "dev1"))
    }

    // MARK: – wallet client decoder fixtures

    func testWalletListDecoder() throws {
        let raw = """
        {"ok":true,"count":2,"wallets":[
          {"id":"wlt_1","label":"sol-main","chain":"solana",
           "address":"AbCDEF1234567890zZyYxXwWvVuUtT","public_key_hex":"00",
           "derivation_path":"m/tars/v1/solana/0","seed_fingerprint":"abcd",
           "signing_supported":true,"created_at":100.0,"updated_at":100.0,
           "derivation_scheme":"tars-v1"},
          {"id":"wlt_2","label":"evm-main","chain":"evm",
           "address":"0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
           "public_key_hex":"00","derivation_path":"m/44'/60'/0'/0/0",
           "seed_fingerprint":"efgh","signing_supported":true,
           "created_at":200.0,"updated_at":200.0}
        ]}
        """
        let data = raw.data(using: .utf8)!
        let wallets = try WalletClient.decodeList(data)
        XCTAssertEqual(wallets.count, 2)
        XCTAssertEqual(wallets[0].chain, "solana")
        XCTAssertEqual(wallets[0].derivationScheme, "tars-v1")
        XCTAssertNil(wallets[1].derivationScheme)  // omitted on this row
        XCTAssertTrue(wallets[1].signingSupported)
    }

    func testWalletListRejectsMissingArray() {
        let raw = #"{"ok":true,"count":0}"#
        XCTAssertThrowsError(
            try WalletClient.decodeList(raw.data(using: .utf8)!)
        )
    }

    func testBalanceDecoder() throws {
        let raw = """
        {"ok":true,"trace_id":"t","balance":{
            "chain":"solana",
            "address":"AbCDEF","raw":"500000000","decimals":9,
            "symbol":"SOL","display":"0.5","rpc_url":"https://x"
        }}
        """
        let data = raw.data(using: .utf8)!
        let bal = try WalletClient.decodeBalance(data)
        XCTAssertEqual(bal?.chain, "solana")
        XCTAssertEqual(bal?.display, "0.5")
        XCTAssertEqual(bal?.decimals, 9)
    }

    func testBalanceDecoderReturnsNilWhenAbsent() throws {
        // RPC failure path: server returns ok:false with no balance.
        let raw = #"{"ok":false,"error":"rpc unreachable"}"#
        let data = raw.data(using: .utf8)!
        XCTAssertNil(try WalletClient.decodeBalance(data))
    }

    func testSignatureDecoder() throws {
        let raw = #"{"ok":true,"signature_b64":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="}"#
        let sig = try WalletClient.decodeSignature(raw.data(using: .utf8)!)
        XCTAssertEqual(sig.count, 32)
    }

    func testSignatureDecoderRejectsEmpty() {
        let raw = #"{"ok":true,"signature_b64":""}"#
        XCTAssertThrowsError(
            try WalletClient.decodeSignature(raw.data(using: .utf8)!)
        )
    }

    func testShortenedAddress() {
        let w = CompanionWallet(
            id: "x", label: "y", chain: "evm",
            address: "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
            signingSupported: true, derivationScheme: nil, createdAt: 0
        )
        XCTAssertEqual(w.shortenedAddress, "0x7099…79C8")
    }
}
