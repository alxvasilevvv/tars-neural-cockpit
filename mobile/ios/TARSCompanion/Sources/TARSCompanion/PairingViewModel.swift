// PairingViewModel — driver for the L1 pairing-first flow.
//
// State machine:
//
//   .idle  → user pastes / scans envelope                        → .scanning
//   .scanning → POST /api/pairing/begin                          → .awaitingHostAccept
//   .awaitingHostAccept → poll /api/pairing/status loop          → .linked | .failed
//   .linked → we keep the secret in PairingSecretStore           → terminal
//
// The view is intentionally dumb — it just renders `state` and the
// last message; this view-model is the only place that talks to the
// network.
//
// MainActor on purpose: everything we publish drives the SwiftUI render.

import Foundation

#if canImport(CryptoKit)
import CryptoKit
#endif

public enum PairingPhase: Equatable, Sendable {
    case idle
    case scanning
    case awaitingHostAccept(PairingHostBegin)
    case linked(PairingStatus, fingerprint: String)
    case failed(message: String)
}

@MainActor
public final class PairingViewModel: ObservableObject {
    @Published public private(set) var phase: PairingPhase = .idle
    @Published public private(set) var statusLog: [String] = []

    private let client: PairingClient
    private let store: PairingSecretStore
    private var pollTask: Task<Void, Never>?

    public init(client: PairingClient, store: PairingSecretStore = InMemorySecretStore()) {
        self.client = client
        self.store = store
    }

    deinit { pollTask?.cancel() }

    public func reset() {
        pollTask?.cancel()
        pollTask = nil
        phase = .idle
        statusLog = []
    }

    public func handleScannedEnvelope(_ raw: String) async {
        do {
            _ = try PairingEnvelopeParser.parse(raw)
        } catch {
            log("Bad QR · \(error)")
            phase = .failed(message: "Bad QR · \(error)")
            return
        }
        await beginPairing()
    }

    public func beginPairing() async {
        phase = .scanning
        log("Generating ephemeral key…")

        #if canImport(CryptoKit)
        let eph = PairingEphemeral.generate()
        let pk = eph.publicKeyBase64
        let sk = eph.privateKey.rawRepresentation
        #else
        let pk = PairingCrypto.base64(rawPublicKey: (0..<32).map { _ in UInt8.random(in: 0...255) })
        let sk = Data(repeating: 0, count: 32)
        let eph = (publicKeyBase64: pk, deviceID: PairingCrypto.freshDeviceID())
        #endif

        log("POST /api/pairing/begin")

        do {
            let begin = try await client.begin(clientEphemeralKey: pk)
            try store.save(deviceID: begin.pairID, secret: sk)
            phase = .awaitingHostAccept(begin)
            log("Host fingerprint · \(PairingCrypto.formatFingerprint(begin.hostFingerprint))")
            startPolling(pairID: begin.pairID, fingerprint: begin.hostFingerprint)
        } catch {
            log("Begin failed · \(error)")
            phase = .failed(message: "begin failed: \(error)")
        }
    }

    private func startPolling(pairID: String, fingerprint: String) {
        pollTask?.cancel()
        let task = Task { [weak self] in
            guard let self else { return }
            let backoffs: [UInt64] = [500, 750, 1_000, 1_500, 2_000, 3_000]
            var attempt = 0
            while !Task.isCancelled {
                let delay = backoffs[min(attempt, backoffs.count - 1)]
                try? await Task.sleep(nanoseconds: delay * 1_000_000)
                attempt += 1
                do {
                    let status = try await self.client.pollStatus(pairID: pairID)
                    await MainActor.run {
                        self.log("status · \(status.state.rawValue)")
                        switch status.state {
                        case .linked:
                            self.phase = .linked(status, fingerprint: fingerprint)
                            self.pollTask = nil
                        case .expired, .rejected:
                            self.phase = .failed(message: status.state.rawValue)
                            self.pollTask = nil
                        case .pending, .unknown:
                            break
                        }
                    }
                    if case .linked = await MainActor.run(body: { self.phase }) { return }
                    if case .failed = await MainActor.run(body: { self.phase }) { return }
                } catch {
                    await MainActor.run {
                        self.log("poll error · \(error)")
                    }
                }
            }
        }
        pollTask = task
    }

    private func log(_ message: String) {
        let now = Date().formatted(.dateTime.hour().minute().second())
        statusLog.insert("\(now) · \(message)", at: 0)
        if statusLog.count > 12 { statusLog.removeLast(statusLog.count - 12) }
    }
}
