# TARS iOS companion (`TARSCompanion`)

Native SwiftUI client for **L10**. **Phase L10 L1 — pairing-first
slice — shipped.** This package compiles + tests on macOS today
(`swift test` from this folder runs 11 unit tests). The wrapping
Xcode app target is generated on the first UI-shipping slice, but the
networking + crypto + state-machine layer is already validated.

## Planned layout (Xcode will materialise this)

```
TARSCompanion/
├── TARSCompanion.xcodeproj
├── TARSCompanion/
│   ├── TARSCompanionApp.swift
│   ├── Models/
│   │   ├── Thread.swift
│   │   ├── Message.swift
│   │   └── Attachment.swift
│   ├── Networking/
│   │   ├── APIClient.swift          # URLSession + bearer/session id
│   │   └── SSE/
│   │       └── EventStream.swift    # async-sequence over text/event-stream
│   ├── Crypto/
│   │   ├── Pairing.swift            # QR / bech32 envelope (L5)
│   │   └── SyncEnvelope.swift       # XChaCha20-Poly1305 + X25519
│   ├── Voice/
│   │   ├── SpeechRecogniser.swift   # Speech.framework
│   │   └── Synthesiser.swift        # AVSpeechSynthesizer
│   ├── Views/
│   │   ├── ThreadListView.swift
│   │   ├── ThreadView.swift         # streaming SSE
│   │   ├── ComposeView.swift        # text + voice + photo picker
│   │   └── SettingsView.swift
│   └── Resources/
└── Tests/
    └── TARSCompanionTests/
```

## L1 (shipped) — pairing surface

Files:

- `PairingClient.swift` — async URLSession driver for
  `POST /api/pairing/begin` and `GET /api/pairing/status`.
- `PairingCrypto.swift` — Curve25519 ephemeral keypair via CryptoKit
  + base64 packing + fingerprint formatter that matches the cockpit's
  `formatFingerprint` in `lib/pairing.ts`.
- `PairingEnvelope.swift` — JSON / `tars-pair://` URL envelope parser
  for the host's QR payload (matches `docs/contracts/L5_PAIRING_DRAFT.md` § 3.1).
- `PairingKeychain.swift` — `PairingSecretStore` protocol with both
  in-memory and Security.framework-backed implementations under
  `world.meeet.tars.<device_id>`.
- `PairingViewModel.swift` — `idle → scanning → awaitingHostAccept
  → linked|failed` state machine, polls `/status` with backoff.
- `PairingView.swift` — SwiftUI shell (paste envelope, big fingerprint,
  big "Paired ✓").
- `QRScannerView.swift` — AVFoundation QR scanner (UIKit-bridged).

Run the tests on macOS without Xcode:

```bash
cd mobile/ios/TARSCompanion
swift test
# 11 passes — decoders, envelope parser, fingerprint formatting,
# in-memory secret store, etc.
```

## Acceptance for L10 iOS v1

1. App boots, scans the host QR code, completes the L5 pairing
   handshake, persists the device key in Secure Enclave.
2. Renders threads + streaming chat with token-by-token deltas.
3. Voice push-to-talk works offline (Speech.framework); response
   plays via AVSpeechSynthesizer with the persona voice picked up
   from the host (Phase L4.1 metadata).
4. Files: photo / file picker → multipart upload to
   `/api/chat/threads/{id}/attachments`.
5. ⌘K parity: server-side search exposed in a sheet.

## Not in scope for v1

- Apple Watch companion. (Track separately if requested.)
- iPad-specific layout polish (the SwiftUI views adapt by default).
- On-device LLM. The phone is a **window** into the host backend.
