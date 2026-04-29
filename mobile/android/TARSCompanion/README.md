# TARS Android companion (`TARSCompanion`)

Native Kotlin + Jetpack Compose client for **L10**. **Phase L10 L2 —
pairing-first slice — shipped.** Sources compile with a stock Android
Studio + Android SDK install (`./gradlew :app:test` runs the JVM
unit tests covering the pure-Kotlin slice).

The cross-platform contract is pinned by
`tests/test_mobile_pairing_contract.py` so iOS L1 and Android L2
cannot drift on field names, state values, or envelope formats.

## Planned layout (Android Studio will materialise this)

```
TARSCompanion/
├── settings.gradle.kts
├── build.gradle.kts
├── gradle.properties
├── app/
│   ├── build.gradle.kts
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/world/meeet/tars/
│       │   ├── MainActivity.kt
│       │   ├── ui/
│       │   │   ├── ThreadListScreen.kt
│       │   │   ├── ThreadScreen.kt        # streaming SSE
│       │   │   ├── ComposeBar.kt
│       │   │   └── theme/
│       │   ├── net/
│       │   │   ├── ApiClient.kt           # OkHttp + Sse listener
│       │   │   └── EventStream.kt
│       │   ├── crypto/
│       │   │   ├── Pairing.kt             # QR + bech32 (L5)
│       │   │   └── SyncEnvelope.kt        # XChaCha20-Poly1305 + X25519 via Tink
│       │   ├── voice/
│       │   │   ├── SpeechRecogniser.kt    # SpeechRecognizer
│       │   │   └── Synthesiser.kt         # TextToSpeech
│       │   └── service/
│       │       └── PushToTalkService.kt   # foreground service
│       └── res/
└── gradle/
```

## L2 (shipped) — pairing surface

```
app/src/main/java/world/meeet/tars/
├── TARSCompanion.kt
├── PairingActivity.kt
├── PairingEnvelopeParser.kt   # mirrors iOS PairingEnvelope.swift
├── PairingViewModel.kt        # idle → scanning → linked|failed state machine
├── crypto/PairingCrypto.kt    # X25519 via java.security XDH (API 31+)
├── net/PairingClient.kt       # OkHttp + org.json
└── ui/PairingScreen.kt        # Compose mirror of PairingView.swift
```

JVM-only unit tests live at
`app/src/test/java/world/meeet/tars/PairingDecodersTest.kt` (8 cases:
envelope JSON / URL parser, begin/status decoders, fingerprint
formatter symmetry).

## Acceptance for L10 Android v1

Mirrors the iOS list from `mobile/ios/TARSCompanion/README.md`:

1. Pairing via QR (camera permission), L5 envelope persisted in
   Android Keystore (StrongBox when the device supports it).
2. Streaming chat in a Compose `LazyColumn` with delta-token
   appending.
3. Voice push-to-talk as a **foreground service** (Android background
   execution rules forbid recording from a backgrounded activity).
4. File picker → multipart upload.
5. ⌘K parity in a bottom sheet.

## Tooling

- Min SDK: 26 (Android 8.0).
- Target SDK: latest stable.
- Kotlin 2.0+, Compose Bill-of-Materials.
- OkHttp 4 (SSE plugin).
- Tink for crypto interop with the iOS / desktop side.

## Not in scope for v1

- Wear OS companion.
- F-Droid track (the meeet bridge depends on optional non-free SDKs
  for crash reporting; a sanitised F-Droid build can come later).
- On-device LLM.
