# TARS mobile companions (iOS + Android)

Phase **L10** of `docs/PHASE_L_ROADMAP.md`. Two thin clients that pair
with the desktop **TARS** host (Phase L9) over the LAN (Bonjour / NSD)
and remotely via `meeet.world` (Phase L5). Same HTTP/SSE contract,
two codebases.

## Status

- [x] `mobile/ios/TARSCompanion/` — pairing-first SPM library
      (CryptoKit + URLSession + AVFoundation QR + SwiftUI). Builds
      and ships **11** unit tests today (`swift test`). The Xcode app
      target lands on the next UI-shipping slice.
- [x] `mobile/android/TARSCompanion/` — pairing-first Compose + OkHttp
      module. Gradle config in place; JVM-only unit tests live at
      `app/src/test/java/world/meeet/tars/PairingDecodersTest.kt`.
- [x] Pairing handshake — both clients consume
      `POST /api/pairing/begin` + `GET /api/pairing/status`. iOS↔Android
      symmetry pinned by `tests/test_mobile_pairing_contract.py`.
- [ ] Streaming chat (`/api/chat/threads/{id}/messages`).
- [ ] File picker → attachment upload
      (`POST /api/chat/threads/{id}/attachments`).
- [ ] Native voice loop (Speech / SpeechRecognizer + AVSpeechSynthesizer / TextToSpeech).
- [ ] Push-to-talk foreground service (Android).

## Why two codebases (not React Native / Flutter)

Same reasoning we already documented in `PHASE_L_ROADMAP § L10`:

- **Latency.** The voice loop (L4) needs OS-level audio APIs.
- **Privacy.** Secure Enclave (iOS) / Keystore + StrongBox (Android)
  hold the L5 sync key — no JS bridge, no leaks.
- **App review.** Two clean native apps win store review faster than
  one cross-platform shell talking to a sidecar.

Optional later: a shared Rust crypto core (so both clients use the
same L5 envelope code) — out of scope for L10 v1.

## Distribution

- **iOS:** TestFlight first, App Store submission once L4 + L5 are
  green and the LLM-handling disclosures are dialled in.
- **Android:** Play internal testing → closed track → production.
  Optional F-Droid track is out of scope for v1 unless requested.

## Shared contract

Both clients consume:

- `GET /api/product/version` — version probe (already shipped).
- `POST /api/pairing/begin` … (Phase L5, see
  `docs/contracts/L5_PAIRING_DRAFT.md`).
- `GET /api/chat/threads` + `POST /api/chat/threads/{id}/messages` (SSE).
- `POST /api/chat/threads/{id}/attachments` (multipart).
- `POST /api/search` (⌘K parity on mobile).

No backend on-device for v1.
