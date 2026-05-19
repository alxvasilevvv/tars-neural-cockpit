# Phase 9 — L10 native mobile speech (iOS + Android) implementer brief

> **Wave:** W310-y  
> **Release target:** **v11** (alongside iOS TestFlight + Android Internal Testing)  
> **Owner:** mobile-speech implementer (cross-platform, after PH9 iOS #208 + Android #209 land)  
> **Effort:** ~2.5 weeks impl (~1.6k Swift + ~1.4k Kotlin + ~800 LoC tests)  
> **Lane:** Mobile companion — native voice loop replacing Web Speech API  
> **Status:** spec'd; **HARD-blocked** on PH9 iOS (#208) + Android (#209) merging first

## 0. TL;DR

The cockpit (desktop) uses `webkitSpeechRecognition` + `speechSynthesis`
(Web Speech API). On mobile WebViews this is unreliable: iOS Safari
falls back to a noisy server, Android Chrome's Web Speech requires
Google account login + network. The PH9 iOS (#208) and Android
(#209) briefs ship `MainTabView` / `MainScaffold` with a voice-button
**stub** in the chat composer and a `PushToTalkService` foreground
stub on Android (mic permission + notification channel pre-declared).

This brief wires the actual voice loop:

- **iOS:** `SFSpeechRecognizer` (on-device since iOS 13) for STT +
  `AVSpeechSynthesizer` for TTS (always on-device, no network)
- **Android:** `SpeechRecognizer` (native, on-device since API 31 for
  most Pixels; degrades to network on older devices) + `TextToSpeech`
  for TTS (always on-device after voice data download)
- **Offline-first fallback (both):** Whisper.cpp ggml model bundled
  (~75 MB `tiny.en` for v11; `base.en` ~140 MB optional download for
  v11.1) via Swift Package + JNI binding
- **PushToTalkService activation:** plugs into iOS `VoiceTab` stub +
  Android `PushToTalkService.onAudioFrame` (foreground-service stub
  already shipped in #209)
- **Wire compat:** unchanged — mobile clients hit the existing
  `POST /api/voice/transcribe` for cloud relay; native engines bypass
  the round-trip entirely when on-device is configured

After this brief lands, the mobile chat composer voice button matches
the desktop cockpit's behavior (hold-to-talk + VAD endpointing + live
partial transcripts) using zero network dependencies in the default
configuration. **On-device by default; cloud relay only as explicit
opt-in.**

## 1. Background

### 1.1 Why Web Speech API doesn't work on mobile WebViews

- **iOS Safari `webkitSpeechRecognition`** silently routes audio to
  Apple's server-side recognition (which Apple sunsetted from
  documentation in iOS 18). On a flaky network it returns garbage
  or `no-speech` events. There is **no offline mode**.
- **Android Chrome `webkitSpeechRecognition`** requires a Google
  account, sends audio to Google servers, requires `INTERNET`
  permission, fails with `network` error on China-firewall devices.
- Neither path gives **partial transcripts** with predictable
  latency or **on-device guarantees** that match TARS's local-first
  positioning.

### 1.2 What ships natively on each platform

| Platform | STT | TTS | On-device guarantee |
| -------- | --- | --- | ------------------- |
| iOS 13+ | `SFSpeechRecognizer` w/ `requiresOnDeviceRecognition = true` | `AVSpeechSynthesizer` (default voices) | STT on-device when device supports the locale (~all iPhone 8+); TTS always |
| Android API 31+ (Pixel, Samsung S20+) | `SpeechRecognizer` w/ `EXTRA_PREFER_OFFLINE = true` | `TextToSpeech` w/ offline voice data | STT on-device when offline voice data installed; TTS always |
| Android API 26-30 | `SpeechRecognizer` (network-only on most OEMs) | `TextToSpeech` (download-and-cache voices) | STT requires network; TTS on-device after voice data download |

### 1.3 Why also ship Whisper.cpp

The native APIs are good but have three soft constraints:

1. **Limited locales offline.** iOS supports ~10 languages on-device;
   Android Pixel supports ~30; older Android OEMs vary widely.
2. **No engine choice.** Apple's STT can hallucinate domain-specific
   names (e.g. "Claude" → "cloud"). Whisper.cpp with `tiny.en` or
   `base.en` gives operator-controllable behavior.
3. **No streaming protocol on iOS.** `SFSpeechRecognizer` does emit
   partial transcripts but framing is per-engine; Whisper.cpp gives
   us the same partial-transcript shape as the desktop cockpit's
   `tars.stt.v1` WS contract (per PH2 STT brief, PR #193).

Bundling Whisper.cpp:
- **iOS:** Swift Package wrapping the existing `whisper.cpp` C++
  library; ggml `tiny.en` model (~75 MB) bundled in app target;
  larger `base.en` (~140 MB) downloadable on-demand in Settings
- **Android:** JNI binding through `external/whisper.cpp` git
  submodule; same ggml models stored in app private storage
  (download-on-demand for `base.en`)

App size impact:
- **iOS v11 IPA:** baseline + ~80 MB Whisper (tiny.en + framework) =
  ~95 MB total (vs ~15 MB baseline). Acceptable for App Store; on-
  demand resource (ODR) tagging considered but rejected as
  complexity-not-worth-it for v11.
- **Android v11 AAB:** baseline + ~80 MB Whisper (per ABI; split AAB
  by ABI keeps per-device download ~95 MB total). Acceptable for
  Play Store; Play Asset Delivery considered for v11.1.

## 2. Scope

### 2.1 In scope

1. **iOS native STT** via `SFSpeechRecognizer` w/ partial transcripts
   and on-device requirement
2. **iOS native TTS** via `AVSpeechSynthesizer` w/ persona-aware voice
   selection (matches desktop L4.2 fallback semantics: persona hint
   first, fallback list second)
3. **iOS Whisper.cpp** Swift Package + bundled `tiny.en` model
4. **Android native STT** via `SpeechRecognizer` w/ `EXTRA_PREFER_OFFLINE`
   and partial-result `Bundle.EXTRA_PARTIAL_RESULTS`
5. **Android native TTS** via `TextToSpeech` w/ persona-aware voice
   selection
6. **Android Whisper.cpp** JNI binding + bundled `tiny.en` model
7. **VAD endpointing** on both platforms (WebRTC VAD lib, auto-stop
   after 800 ms silence — same semantics as PH2 STT brief)
8. **Mode selector** in Settings: "On-device (recommended)" / "Cloud
   relay" / "Auto" (uses on-device when available, falls back to
   cloud over the existing `POST /api/voice/transcribe` if model not
   loaded or locale unsupported)
9. **Push-to-talk integration** w/ PushToTalkService (Android, from
   #209) and `VoiceTab` (iOS, from #208 stub)
10. **Live partial-transcript rendering** in composer (matches PH2
    STT brief WS contract `tars.stt.v1`)

### 2.2 Out of scope (deferred)

| Feature | Defer to |
| ------- | -------- |
| Voice gallery on mobile (latency/token/model picker) | v11.1 (desktop-only in v11 via PH2 voice-gallery brief #194) |
| Whisper.cpp `large-v3` model | v12+ (multi-GB, requires NPU/GPU acceleration) |
| Real-time translation | v12+ |
| Diarization (multi-speaker) | v12+ |
| Multilingual auto-detect | v11.1 (v11 ships explicit locale selector) |
| WS streaming protocol for mobile-to-host audio | v11.1 (v11 uses on-device only, no audio bytes leave phone) |
| Custom wake word | v12+ |
| Voice biometrics / speaker verification | v12+ |

### 2.3 Why batched with iOS + Android (cross-platform brief)

Native voice APIs are by far the platform's most divergent surface,
but the **state machine, persona mapping, and VAD semantics are
identical**. Splitting the brief into iOS + Android variants would
cost a week of duplicate spec'ing without any code-sharing benefit.
The shared `VoiceState` enum + `PersonaVoiceMap` JSON contract
(defined here) ensures both implementers converge on the same UX.

## 3. Mechanical implementation plan (6 steps, ~2.5 weeks)

### Step 1: Shared contracts + cross-platform contract test

**Files (~280 LoC):**
- `mobile/contracts/voice_state.md` (~80 LoC) — defines the 7-state
  `VoiceState` enum (`idle`, `requesting_permission`, `permission_denied`,
  `listening`, `transcribing`, `speaking`, `error`) and 5 transition
  events; both Swift `enum VoiceState` and Kotlin `sealed class
  VoiceState` derive from this
- `mobile/contracts/persona_voice_map.json` (~120 LoC) — per-persona
  voice selector for both engines (`tars-classic` → iOS:
  `com.apple.voice.compact.en-US.Samantha`, Android:
  `en-us-x-sfg-network`; `tars-cinematic` → iOS:
  `com.apple.voice.enhanced.en-US.Evan`, Android:
  `en-us-x-iol-local`); mirrors desktop `MacSayEngine` fallback list
  pattern
- `tests/test_mobile_voice_contract.py` (~80 LoC, Python pytest) —
  asserts both platforms agree on (a) `VoiceState` enum values
  byte-for-byte, (b) `persona_voice_map.json` JSON shape, (c) VAD
  silence threshold defaults (800 ms initial, 300-2000 ms range)

**Tests:**
- `mobile/ios/TARSCompanion/Tests/TARSCompanionTests/VoiceStateContractTests.swift`
  (~50 LoC) — round-trip parse of `persona_voice_map.json`, enum
  exhaustiveness
- `mobile/android/TARSCompanion/companion/src/test/java/world/meeet/tars/companion/voice/VoiceStateContractTest.kt`
  (~50 LoC) — same; parses JSON via `org.json`

**Acceptance:**
- [ ] `pytest tests/test_mobile_voice_contract.py` green
- [ ] Both mobile unit-test suites green
- [ ] Any change to `voice_state.md` or `persona_voice_map.json`
      fails ALL THREE test suites in the same PR (forcing convergence)

### Step 2: iOS — `SFSpeechRecognizer` + `AVSpeechSynthesizer` + VAD

**Files (~620 LoC Swift + ~180 LoC tests):**
- `mobile/ios/TARSCompanion/Sources/TARSCompanion/voice/VoiceCoordinator.swift`
  (~200 LoC) — `@MainActor` actor; owns `VoiceState`; orchestrates
  permission request → audio session → recognizer → synthesizer
  state machine
- `mobile/ios/TARSCompanion/Sources/TARSCompanion/voice/SpeechRecognizerClient.swift`
  (~180 LoC) — wraps `SFSpeechRecognizer` w/ partial transcript
  callback; sets `requiresOnDeviceRecognition = true`; emits
  `[partial String, final String]` tuples on a `AsyncStream`
- `mobile/ios/TARSCompanion/Sources/TARSCompanion/voice/SpeechSynthesizerClient.swift`
  (~140 LoC) — wraps `AVSpeechSynthesizer`; persona → voice
  resolution via `PersonaVoiceMap`; queue + interrupt semantics
  (match desktop L4.2 `MacSayEngine`)
- `mobile/ios/TARSCompanion/Sources/TARSCompanion/voice/VADClient.swift`
  (~100 LoC) — WebRTC VAD wrapper via `WebRTC.framework` (~12 MB);
  configurable silence threshold (800 ms default); emits
  `silenceDetected` after threshold crossed

**Tests:**
- `mobile/ios/TARSCompanion/Tests/TARSCompanionTests/VoiceCoordinatorTests.swift`
  (~120 LoC) — state machine transitions under mocked recognizer
- `mobile/ios/TARSCompanion/Tests/TARSCompanionTests/PersonaVoiceMapTests.swift`
  (~60 LoC) — verify all known personas resolve to a non-nil
  `AVSpeechSynthesisVoice`

**App target integration:**
- `mobile/ios/TARSCompanion/App/TARSCompanion/Tabs/VoiceTab.swift`
  (~80 LoC) — replaces the stub from #208 w/ live waveform +
  partial transcript label + send button
- `Info.plist` already has `NSMicrophoneUsageDescription` +
  `NSSpeechRecognitionUsageDescription` from #208

**Acceptance:**
- [ ] Hold mic button → see partial transcript stream within 400ms
- [ ] Release mic button → final transcript dispatched to chat
- [ ] Speak → silence 800ms → auto-stop (VAD)
- [ ] Persona switch in Settings → TTS voice changes on next utterance
- [ ] Airplane mode → STT still works (on-device guarantee asserted)

### Step 3: iOS — Whisper.cpp Swift Package + offline model

**Files (~340 LoC Swift + ~80 LoC C++ bridge + ~120 LoC tests):**
- `mobile/ios/WhisperKit/Package.swift` (~40 LoC) — new SPM package
  wrapping `whisper.cpp` as a static library; expose `WhisperKit`
  module
- `mobile/ios/WhisperKit/Sources/WhisperKit/WhisperEngine.swift`
  (~200 LoC) — actor-based wrapper around `whisper_init_from_file` +
  `whisper_full` + `whisper_get_segment_text`; emits partial
  transcripts via `AsyncStream`; model load happens lazily on first
  use w/ a warm-up call queue
- `mobile/ios/WhisperKit/Sources/WhisperKit/include/whisper_bridge.h`
  (~30 LoC) — minimal C bridge header
- `mobile/ios/WhisperKit/Sources/WhisperKitCXX/whisper_bridge.cpp`
  (~80 LoC) — C++ shim that exposes `whisper.cpp` symbols Swift
  can call
- `mobile/ios/WhisperKit/Resources/ggml-tiny.en.bin` (~75 MB) —
  vendored model; in `.gitattributes` w/ `binary` + LFS hint, in
  `.gitignore` for non-CI clones; downloaded by `scripts/
  fetch_whisper_models.sh` (~40 LoC, new)
- `mobile/ios/TARSCompanion/App/TARSCompanion/Tabs/VoiceTab.swift`
  (~30 LoC delta) — adds engine picker: "Apple" / "Whisper.cpp"
  (default = Apple; on-device flag enforced for both)

**Tests:**
- `mobile/ios/WhisperKit/Tests/WhisperKitTests/WhisperEngineTests.swift`
  (~120 LoC) — synth WAV input → assert transcript matches expected;
  load + warm-up timing assertion (<2s p95 on M1 simulator)

**CI:**
- `.github/workflows/ios-build.yml` (~20 LoC delta) — `git lfs pull`
  before build; skip Whisper tests on PR builds w/o LFS fetch (cost
  control), run nightly on `macos-14`

**Acceptance:**
- [ ] WhisperKit Swift Package builds for iOS 17.0+
- [ ] `tiny.en` model loads in <2s on iPhone 15 Pro
- [ ] Transcription accuracy: WER ≤ 0.10 on `librispeech-test-clean`
      first 20 utterances (regression budget)
- [ ] Engine picker switches between Apple + Whisper.cpp w/o app
      restart

### Step 4: Android — `SpeechRecognizer` + `TextToSpeech` + VAD

**Files (~580 LoC Kotlin + ~180 LoC tests):**
- `mobile/android/TARSCompanion/companion/src/main/java/world/meeet/tars/companion/voice/VoiceCoordinator.kt`
  (~200 LoC) — `class` w/ `StateFlow<VoiceState>`; orchestrates
  permission → audio session → recognizer → synthesizer
- `mobile/android/TARSCompanion/companion/src/main/java/world/meeet/tars/companion/voice/SpeechRecognizerClient.kt`
  (~160 LoC) — wraps `SpeechRecognizer.createSpeechRecognizer`;
  sets `EXTRA_PREFER_OFFLINE = true` on API 31+; falls back to
  network on older w/ explicit operator warning; emits partial
  results via `Flow`
- `mobile/android/TARSCompanion/companion/src/main/java/world/meeet/tars/companion/voice/SpeechSynthesizerClient.kt`
  (~120 LoC) — wraps `TextToSpeech`; persona → voice resolution
  via `PersonaVoiceMap`; queue + interrupt semantics
- `mobile/android/TARSCompanion/companion/src/main/java/world/meeet/tars/companion/voice/VADClient.kt`
  (~100 LoC) — WebRTC VAD via AAR (`org.webrtc:google-webrtc:1.0.32006`);
  configurable silence threshold

**Tests:**
- `mobile/android/TARSCompanion/companion/src/test/java/world/meeet/tars/companion/voice/VoiceCoordinatorTest.kt`
  (~120 LoC, Robolectric) — state machine transitions
- `mobile/android/TARSCompanion/companion/src/test/java/world/meeet/tars/companion/voice/PersonaVoiceMapTest.kt`
  (~60 LoC) — verify all known personas resolve

**App target integration:**
- `companion/src/main/java/world/meeet/tars/companion/ui/voice/VoiceTab.kt`
  (~80 LoC) — live waveform composable + partial transcript + send
  button
- `companion/src/main/java/world/meeet/tars/companion/service/PushToTalkService.kt`
  (~50 LoC delta) — wires `onStartCommand` to `VoiceCoordinator.beginListening()`,
  `onDestroy` to `VoiceCoordinator.endListening()` (replaces stub from #209)

**Acceptance:**
- [ ] Long-press voice button → foreground service starts → see
      partial transcript stream within 500ms
- [ ] Release → final transcript dispatched to chat → service stops
      → notification clears
- [ ] Speak → silence 800ms → auto-stop (VAD)
- [ ] Airplane mode on Pixel 8 → STT still works (on-device guarantee)
- [ ] Airplane mode on Pixel 4a → falls back to Whisper.cpp (step 5)
      automatically (since native recognizer is network on older)

### Step 5: Android — Whisper.cpp JNI + offline model

**Files (~340 LoC Kotlin + ~120 LoC C++ JNI + ~80 LoC tests):**
- `external/whisper.cpp` — git submodule pinning a known-good
  whisper.cpp commit; build via CMake from
  `companion/src/main/cpp/CMakeLists.txt` (~40 LoC, new)
- `companion/src/main/cpp/whisper_jni.cpp` (~120 LoC) — JNI exports:
  `Java_world_meeet_tars_companion_voice_WhisperEngine_nativeInit`,
  `_nativeTranscribe`, `_nativeRelease`
- `companion/src/main/java/world/meeet/tars/companion/voice/WhisperEngine.kt`
  (~200 LoC) — Kotlin wrapper; `external fun nativeInit(modelPath: String): Long`
  + `external fun nativeTranscribe(handle: Long, audio: FloatArray): String`;
  exposed via `class WhisperEngine(scope: CoroutineScope)`
- `companion/src/main/assets/ggml-tiny.en.bin` (~75 MB) — vendored
  model; same .gitattributes LFS treatment as iOS
- `companion/src/main/java/world/meeet/tars/companion/voice/VoiceCoordinator.kt`
  (~80 LoC delta) — adds engine picker; auto-fallback to Whisper.cpp
  when native recognizer reports `ERROR_NETWORK` on older Android
- `companion/build.gradle.kts` (~30 LoC delta) — adds `externalNativeBuild
  { cmake { path = file("src/main/cpp/CMakeLists.txt"); version = "3.22.1" } }`,
  ABI splits (`arm64-v8a`, `armeabi-v7a`, `x86_64`)

**Tests:**
- `companion/src/test/java/world/meeet/tars/companion/voice/WhisperEngineTest.kt`
  (~80 LoC, Robolectric + JNI-skipped on JVM) — load + warm-up
  timing assertion runs only on instrumented `androidTest/` (Firebase
  Test Lab nightly)

**CI:**
- `.github/workflows/android-build.yml` (~30 LoC delta) — install
  Android NDK r26d; `git lfs pull` before build; ABI split builds
  in parallel matrix

**Acceptance:**
- [ ] CMake build produces `.so` per ABI w/o errors
- [ ] APK size delta per ABI: +~30 MB (Whisper lib + tiny.en model)
- [ ] Engine picker switches between Native + Whisper.cpp w/o app
      restart
- [ ] Auto-fallback fires on `ERROR_NETWORK` from native recognizer
- [ ] Manual test on Pixel 4a (API 26, no offline native STT):
      first utterance after install uses Whisper.cpp transparently

### Step 6: Mode selector UI + telemetry + docs

**Files (~340 LoC Swift/Kotlin + ~180 LoC doc):**
- iOS: `App/TARSCompanion/Tabs/SettingsTab+Voice.swift` (~140 LoC)
  — adds Voice section: STT engine picker (Auto / Apple / Whisper.cpp),
  TTS engine picker (System), VAD threshold slider (300-2000 ms,
  default 800), "Download base.en (140 MB)" button for upgrade
- Android: `companion/src/main/java/world/meeet/tars/companion/ui/settings/VoiceSettingsSection.kt`
  (~140 LoC) — same surface
- Both: persist setting in app preferences (UserDefaults / DataStore)
- `mobile/QA_PROTOCOL.md` (~80 LoC delta) — adds voice-loop section:
  pair → grant mic permission → hold to talk → see partial → release
  → see final → hear TTS reply → switch engine → re-test → toggle
  airplane mode → re-test
- `mobile/README.md` (~50 LoC delta) — Voice loop status flips from
  "stub" → "v11 native"
- `mobile/ios/TARSCompanion/README.md` + `mobile/android/TARSCompanion/README.md`
  (~25 LoC delta each) — voice acceptance criteria updated to v11
  shipped

**Telemetry buckets (deferred to v11.1 per PH5 #204 default-off):**
- `mobile.voice.stt.engine_used` (apple / android_native / whisper_cpp)
- `mobile.voice.stt.partial_ttft_ms`
- `mobile.voice.stt.final_latency_ms`
- `mobile.voice.tts.engine_used`
- `mobile.voice.vad.silence_ms_at_stop`

These are documented in this brief but emitted only when the v11.1
telemetry opt-in lands. Schema reserved in `PH5_TELEMETRY_BRIEF.md`
update needed (separate small PR after this brief lands).

**Acceptance:**
- [ ] All settings persist across app restart
- [ ] Telemetry buckets documented in master plan §3.5 telemetry
      schema appendix
- [ ] `mobile/QA_PROTOCOL.md` voice section runs in <2 min
- [ ] Both READMEs reflect v11 native voice status

## 4. State machine + UX

### 4.1 `VoiceState` enum (shared)

```
idle
  → (button pressed) → requesting_permission
  → (permission granted) → listening
  → (permission denied) → permission_denied → idle (after operator dismisses)

listening
  → (recognizer ready, audio flowing) → listening (stays here, emits partials)
  → (button released OR VAD silence threshold) → transcribing
  → (recognizer error) → error → idle

transcribing
  → (final transcript) → dispatched to chat → idle
  → (timeout 5s) → error → idle

(separately, chat reply arrives):
  idle → speaking → idle
```

### 4.2 Composer voice button states

| State | Visual | Interaction |
| ----- | ------ | ----------- |
| `idle` | Mic icon, neutral color | Tap = no-op (recommends long-press); long-press starts |
| `requesting_permission` | Mic icon, dimmed | Shows system permission dialog |
| `permission_denied` | Mic icon w/ slash | Tap → opens app settings |
| `listening` | Animated waveform, red tint | Release to stop; tap-to-stop also works |
| `transcribing` | Spinner | No interaction (1-3s typically) |
| `speaking` | Speaker icon, animated | Tap = interrupt TTS |
| `error` | Error icon, with toast | Tap = dismiss |

### 4.3 First-launch flow

```
User opens chat for the first time
  → composer shows mic icon w/ tooltip "Long-press to talk"
  → user long-presses
  → system permission dialog (microphone + speech recognition on iOS)
  → on grant: brief 1s "Listening..." pulse, then live waveform
  → on deny: friendly explanation + "Open Settings" button
```

### 4.4 Persona switching

Persona is chat-thread-scoped (matches desktop). On thread open:
- Look up `persona_id` from thread metadata
- Resolve via `PersonaVoiceMap[persona_id]` to `[primary, fallback1, fallback2]`
- TTS uses first available; STT uses default (locale-bound, not
  persona-bound; STT engine doesn't have persona voices)

## 5. Coupling matrix

| Brief | Coupling | Why |
| ----- | -------- | --- |
| **PH9 iOS companion (#208)** | **HARD (blocker)** | Replaces `VoiceTab` stub; depends on `MainTabView` scaffolding + mic permission entry in Info.plist |
| **PH9 Android companion (#209)** | **HARD (blocker)** | Replaces `PushToTalkService` foreground stub; depends on companion module + `RECORD_AUDIO` manifest + notification channel |
| **PH2 STT streaming brief (#193, desktop)** | **SOFT (semantic parity)** | Mobile uses same `tars.stt.v1` partial-transcript semantics as desktop WS contract; persona fallback list mirrors desktop `MacSayEngine` |
| **PH2 voice gallery (#194, desktop)** | **NONE in v11** | Mobile gets a fixed mode selector (Auto/Apple/Whisper.cpp) instead of latency/token/model gallery; v11.1 may add gallery |
| **PH4 voice fallback hardening (#191)** | **SOFT (pattern reuse)** | `PersonaVoiceMap` follows the same fallback-list pattern as `MacSayEngine._pick_fallback_voice` |
| **#202 vault** | **NONE** | Voice has no secrets to vault; mic permission is OS-level |
| **#203 policy UI** | **NONE in v11** | Voice utterances don't go through policy queue; chat messages do (but they were already going through policy before this brief) |
| **#204 telemetry** | **SOFT (forward)** | Telemetry buckets reserved here, emitted v11.1 once mobile telemetry default-off opt-in is in place |
| **#205 sandbox** | **NONE** | n/a (no on-device code exec on mobile in v11) |
| **#206 planner UI / #207 marketplace** | **NONE** | Desktop-only in v11 |

## 6. Open questions for operator

1. **Bundled vs download model.** Recommendation: bundle `tiny.en`
   (75 MB) for offline-first guarantee out-of-the-box; download
   `base.en` (140 MB) on demand. Operator confirm?
2. **iOS Speech Recognition usage description language.** Must
   disclose that on-device speech recognition is used. Recommend:
   "TARS uses on-device speech recognition to convert your voice
   to text. Audio never leaves your device."
3. **Android offline voice data download UX.** On Pixel devices,
   offline voice data isn't always pre-installed. Recommend: on
   first long-press, if `EXTRA_PREFER_OFFLINE` fails, show a
   one-time card: "Download offline voice (~50 MB) for faster
   recognition without internet?" with "Download" / "Use Whisper.cpp"
   buttons.
4. **WebRTC VAD lib for iOS.** Options: (a) `WebRTC.framework`
   (~12 MB, Google-maintained), (b) `silero-vad` ported to Swift
   (~2 MB, MIT, modern), (c) custom (energy + zero-crossing rate,
   ~200 LoC, no dep). Recommend (b) for app size + accuracy. Confirm?
5. **Persona voice mapping coverage.** v11 maps 4 personas
   (tars-classic, tars-cinematic, jarvis, glados). Add more? Punt
   to v11.1 with operator survey results from TestFlight?
6. **Voice loop telemetry — really default off?** Recommend yes —
   matches PH5 telemetry default. Implementer can wire emission
   in v11.1 once Play Console data safety form allows; v11 IPA/AAB
   has zero voice telemetry.
7. **L4 voice loop on desktop — does this brief affect it?** No.
   Desktop uses backend STT/TTS engines (#191/#193); this brief
   is mobile-only. Desktop ↔ mobile audio bridging deferred to
   v11.2+ if ever (significant new wire protocol).
8. **App Store / Play Store review risk.** Recommend a one-line
   note in the App Store / Play submission: "Voice features run
   entirely on-device by default. Cloud relay is an explicit
   opt-in." This sidesteps the "is this an AI app that uses voice
   for surveillance" review prompts.

## 7. Risk register

| # | Risk | Likelihood | Severity | Mitigation |
| - | ---- | ---------- | -------- | ---------- |
| 1 | Whisper.cpp build flake on Android NDK r26d w/ ABI splits | Medium | High | Pin NDK + whisper.cpp commit in `external/`; CI matrix per ABI in step 5 |
| 2 | App Store rejects 95 MB IPA as "too large" | Low | High | On-Demand Resources tagging deferred to v11.1 if rejection; tiny.en (75 MB) is below the 100 MB cellular download cap that triggers WiFi-only |
| 3 | Whisper LFS bandwidth cost in CI | Medium | Low | Skip LFS fetch on PR builds; nightly only |
| 4 | iOS `SFSpeechRecognizer` rate-limit hits operator hard | Medium | Medium | Document the 1000/hr Apple limit in Settings tooltip; Whisper.cpp fallback bypasses it |
| 5 | Android `SpeechRecognizer` `ERROR_NO_MATCH` on quiet input | High | Low | VAD threshold prevents spurious recognizer calls; UX shows "Speak louder?" hint after 2 consecutive no-matches |
| 6 | Persona voice not installed on user's Android device | Medium | Low | Fallback list resolves to first available; explicit toast "Persona voice 'Evan' unavailable, using 'System default'" |
| 7 | WebRTC VAD CPU spike on low-end Android | Medium | Low | Use silero-vad alternative (recommended option 4b) or fallback to energy-only VAD |
| 8 | Locale mismatch — operator's chat lang differs from STT locale | Medium | Medium | v11 ships English-only on-device STT (per non-goal §2.2); explicit locale selector in v11.1 |

## 8. Test plan

### 8.1 Unit (JVM + Swift Package, runs on CI)

- 5 cross-platform contract tests (step 1)
- 6 iOS state machine tests (`VoiceCoordinatorTests`)
- 3 iOS persona resolution tests (`PersonaVoiceMapTests`)
- 5 WhisperKit engine tests (step 3, nightly only due to model load)
- 6 Android state machine tests (`VoiceCoordinatorTest`)
- 3 Android persona resolution tests (`PersonaVoiceMapTest`)
- 5 Android WhisperEngine instrumented tests (nightly only)

**Total CI-blocking tests:** ~28 (excluding nightly Whisper tests).
Target <3 min full cross-platform CI.

### 8.2 Contract (Python pytest, runs on backend CI)

- New `test_mobile_voice_contract.py` — asserts `voice_state.md` +
  `persona_voice_map.json` byte-for-byte parity with both mobile suites

### 8.3 Manual smoke (per release, `mobile/QA_PROTOCOL.md` voice section)

- iOS: pair → grant mic → hold mic → see partial → release → see
  final → TTS reply audible → switch engine to Whisper.cpp → re-test
  → airplane mode → re-test
- Android: same flow, plus long-press triggers foreground notification
  → release dismisses → repeat 10 times to verify no notification
  leakage

### 8.4 Accuracy regression (nightly, Firebase Test Lab / Mac CI)

- Librispeech-test-clean first 20 utterances → WER ≤ 0.10
- Domain-specific test set (10 sentences w/ "Claude", "TARS",
  "meeet", "Anthropic") → exact-match ≥ 8/10 for Whisper.cpp;
  ≥ 6/10 for Apple/Android native

## 9. Deliverables checklist

- [ ] `mobile/contracts/voice_state.md` + `persona_voice_map.json`
- [ ] iOS `VoiceCoordinator` + `SpeechRecognizerClient` +
      `SpeechSynthesizerClient` + `VADClient` shipped + tested
- [ ] iOS `VoiceTab` replaces #208 stub w/ live waveform
- [ ] WhisperKit SPM package + tiny.en model bundled
- [ ] Android `VoiceCoordinator` + clients + VAD shipped + tested
- [ ] Android `VoiceTab` Composable replaces #209 stub
- [ ] Android `PushToTalkService.onStartCommand` wires VoiceCoordinator
- [ ] Android Whisper.cpp JNI binding + tiny.en model bundled
- [ ] Mode selector in Settings on both platforms
- [ ] All test suites green: ~28 CI-blocking tests + 1 contract test
- [ ] `mobile/QA_PROTOCOL.md` voice section drafted + run
- [ ] `mobile/README.md` + per-platform READMEs updated
- [ ] Telemetry buckets reserved in PH5 schema appendix (separate
      small PR)
- [ ] Mark `ph9-native-speech` complete in `docs/PRODUCT_MASTER_PLAN.md
      §3.9`

## 10. Forward dependencies (post-merge)

After this brief lands:

- **v11.1 voice gallery on mobile brief** can add the latency/token/
  model picker UX from desktop (#194) on top of the existing engine
  selector
- **v11.1 telemetry emission brief** can wire the 5 reserved
  `mobile.voice.*` buckets to the `DifferentialAggregator` (#204)
- **v11.2 desktop↔mobile audio bridging brief** (if pursued) can
  introduce a WS audio pipe between paired devices using the existing
  L5 device key for symmetric encryption
- **v12 multilingual auto-detect brief** can add per-thread locale
  detection from chat history + Whisper.cpp `auto` task
- **v12 wake-word brief** can add `"Hey TARS"` detection via the same
  Whisper.cpp engine in a low-power always-listening mode
  (significant battery + privacy review)

---

**End of Phase 9 L10 native mobile speech brief (W310-y).**

> Closes the **L10 mobile companion trio** (iOS #208 + Android #209
> + this). After this lands, the entire L0-L10 contract is shipped
> on planning surface. The remaining sub-wave (W310-z) covers the
> continuous Phase 10 Claude design polish backlog, which is
> implementation-time rather than planning-time work.
