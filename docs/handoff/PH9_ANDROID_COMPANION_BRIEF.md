# Phase 9 — L10 Android companion app (Jetpack Compose) implementer brief

> **Wave:** W310-x  
> **Release target:** **v11** (Google Play Internal Testing track)  
> **Owner:** mobile implementer (next L10-lane session)  
> **Effort:** ~3 weeks impl (~2.6k Kotlin LoC + ~700 LoC tests)  
> **Lane:** Mobile companion — Android side, paired with PH9 iOS brief (#208)  
> **Status:** spec'd; awaiting operator review + sub-task slotting

## 0. TL;DR

Pairing-first Android module is **shipped** under
`mobile/android/TARSCompanion/` — Gradle `:app` module with Compose UI
(`PairingScreen.kt`, `WalletScreen.kt`), OkHttp networking, ZXing QR
scanning, java.security XDH X25519, and 16 JVM-only unit tests (8
pairing decoders + 8 wallet decoders) green via `./gradlew :app:test`.
The pairing handshake is **contract-tested against the backend** via
`tests/test_mobile_pairing_contract.py`, so iOS L1 and Android L2
cannot drift on field names, state values, or envelope formats.

This brief takes the existing pairing-first slice and turns it into the
**first shippable end-user Android app** (Internal Testing track):

- New `:companion` Gradle module wrapping the existing pairing surface
  in a `MainScaffold` (Material 3 NavigationBar with 4 destinations:
  Chat / Plans / Inbox / Settings)
- Streaming chat composable backed by OkHttp's `EventSource` with a
  line-buffered Flow that survives recomposition and process death
- File picker → multipart upload via Storage Access Framework
- Read-only Plans + Inbox tabs (writes deferred to v11.1)
- Internal Testing build pipeline via Gradle Play Publisher (GPP)
- Foreground-service stub for the future push-to-talk voice loop
  (PH9 native speech brief) with notification channel + mic permission
  manifest entry pre-declared

**Distribution:**
- **v11:** Google Play Internal Testing track (~100 testers cap)
- **v11.1:** Closed Beta (~10k testers) once UX is dialed
- **v11.2:** Open Beta + Production rollout
- **Not** F-Droid in v11 (sanitised non-meeet build can come post-GA;
  meeet ingest SDK has non-free crash reporting on optional)

Two native codebases preserved (Swift + Kotlin). No React Native /
Flutter / Cordova wrappers. Visual parity with iOS via shared design
tokens but native idioms throughout (Material 3, not iOS-on-Android).

## 1. Background

### 1.1 What already exists

```
mobile/android/TARSCompanion/
├── settings.gradle.kts         (6 LoC, single module)
├── build.gradle.kts            (root, 14 LoC)
└── app/
    ├── build.gradle.kts        (57 LoC, Compose BOM 2024.06.00)
    └── src/
        ├── main/java/world/meeet/tars/
        │   ├── TARSCompanion.kt              (14 LoC — Application class)
        │   ├── PairingActivity.kt            (35 LoC)
        │   ├── PairingEnvelopeParser.kt      (89 LoC — mirrors iOS)
        │   ├── PairingViewModel.kt           (126 LoC — state machine)
        │   ├── WalletActivity.kt             (38 LoC)
        │   ├── WalletViewModel.kt            (112 LoC)
        │   ├── crypto/PairingCrypto.kt       (86 LoC — X25519 via XDH)
        │   ├── net/PairingClient.kt          (155 LoC — OkHttp + org.json)
        │   ├── net/WalletClient.kt           (234 LoC)
        │   └── ui/
        │       ├── PairingScreen.kt          (185 LoC — Compose)
        │       └── WalletScreen.kt           (232 LoC — Compose)
        └── test/java/world/meeet/tars/
            ├── PairingDecodersTest.kt        (102 LoC, 8 cases)
            └── WalletDecodersTest.kt         (114 LoC, 8 cases)
```

**Total today:** ~1.5k Kotlin LoC + ~216 LoC tests.

**Backend contract pin:** `tests/test_mobile_pairing_contract.py`
asserts wire formats. Any change to envelope field names or state
machine values breaks both iOS and Android in the same CI run.

### 1.2 What is missing for v11

| Layer | iOS shipped | Android shipped | v11 gap |
| ----- | ----------- | ---------------- | ------- |
| Pairing crypto | ✅ | ✅ | — |
| QR scanning | ✅ (AVFoundation) | ✅ (CameraX + ZXing) | — |
| Wallet read | ✅ | ✅ | — |
| Storage | ✅ (Keychain) | ⚠️ partial (StrongBox not wired) | Wire Android Keystore StrongBox where available |
| **Chat (SSE)** | ❌ | ❌ | **THIS BRIEF** |
| **File picker → upload** | ❌ | ❌ | **THIS BRIEF** |
| **Plans inbox (read-only)** | ❌ | ❌ | **THIS BRIEF** |
| **Policy inbox (read-only)** | ❌ | ❌ | **THIS BRIEF** |
| **App-target build pipeline** | ❌ | ❌ | **THIS BRIEF** |
| **Foreground-service push-to-talk** | n/a | ❌ | **THIS BRIEF (stub only)** |
| Native voice (TTS + STT) | n/a | n/a | PH9 native speech brief |

### 1.3 Why Compose + native Kotlin (not RN / Flutter)

Same reasoning as iOS brief §1.3:
- L4/L4.2 voice loop pre-emption budget needs native APIs (Android
  `SpeechRecognizer`, `TextToSpeech`, `MediaSession`)
- L5 device key in Android Keystore (StrongBox where available) means
  zero plain-text key at any frame
- Play review predictability — a native Kotlin app maps 1:1 to the
  review patterns Google expects; "AI assistant that uses Web APIs"
  triggers manual review and longer queues
- Compose UI is the modern Android idiom; Material 3 with dynamic
  color matches the user's home screen palette, which is a quiet
  premium signal
- Zero RN/Flutter footprint avoids the 12-15 MB JS runtime overhead
  and the fragmented native-module ecosystem

## 2. Scope

### 2.1 In scope

1. **`:companion` Gradle module** wrapping existing pairing as
   `MainScaffold` with 4-destination `NavigationBar`
2. **Streaming chat composable** w/ OkHttp `EventSource` line buffer
3. **File picker upload** via Storage Access Framework + multipart
4. **Read-only Plans tab** (HTTP poll + WebSocket subscription)
5. **Read-only Policy Inbox tab** (HTTP poll + SSE subscription)
6. **Settings tab** (paired devices list, identity rotation entry
   point, mic permission toggle, telemetry opt-in toggle)
7. **Internal Testing build pipeline** via Gradle Play Publisher
   (GPP), with bumpVersionCode + buildBundle + publishBundle Gradle
   tasks
8. **Foreground-service stub** for push-to-talk (notification channel
   pre-declared, mic permission in manifest, but actual STT/TTS
   deferred to PH9 native speech)
9. **JVM-only unit tests** for all new pure-Kotlin code paths
10. **Macrobenchmark suite** for cold start + scroll perf (Jetpack
    Macrobenchmark, runs on CI emulator)

### 2.2 Out of scope (deferred)

| Feature | Defer to |
| ------- | -------- |
| Push notifications via FCM | v11.1 |
| Wear OS companion | v11.2+ |
| Foldable / large-screen layout overrides | v11.2+ (default scaffold works) |
| On-device LLM | v12+ |
| F-Droid build flavor | post-v11 |
| Sandboxed code execution UI | not on mobile in v11 (#205 is desktop-only) |
| Marketplace pack installer | not on mobile in v11 (#207 is desktop-only) |
| Write actions on Plans / Inbox tabs | v11.1 |

### 2.3 Why parallel with iOS (not sequential)

The two briefs are **structurally identical** with platform-specific
adapters. Splitting them lets two implementers work in parallel without
shared state. The cross-platform contract (`test_mobile_pairing_contract.py`,
plus a new `test_mobile_chat_contract.py` to be added in step 1) is
the convergence point; any wire-format change fails both CIs in the
same PR, forcing convergence-by-construction.

## 3. Mechanical implementation plan (6 steps, ~3 weeks)

### Step 1: `:companion` module + app target + Internal CI smoke

**Files (~340 LoC Kotlin + ~80 LoC test):**
- `mobile/android/TARSCompanion/companion/build.gradle.kts` (~70 LoC)
  — separate module so the pairing-only `:app` keeps shipping as a
  pure SDK target for the desktop emulator harness
- `mobile/android/TARSCompanion/companion/src/main/AndroidManifest.xml`
  (~50 LoC) — declares `RECORD_AUDIO`, `CAMERA`, `INTERNET`,
  `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_MICROPHONE`, notification
  channel for push-to-talk
- `mobile/android/TARSCompanion/companion/src/main/java/world/meeet/tars/companion/CompanionApplication.kt`
  (~40 LoC) — Application subclass, init OkHttp singleton + notification
  channels
- `mobile/android/TARSCompanion/companion/src/main/java/world/meeet/tars/companion/MainActivity.kt`
  (~60 LoC) — `@AndroidEntryPoint` (or manual DI), `setContent {
  MainScaffold() }`
- `mobile/android/TARSCompanion/companion/src/main/java/world/meeet/tars/companion/ui/MainScaffold.kt`
  (~120 LoC) — `NavHost` with 4 destinations + `NavigationBar`
- `tests/test_mobile_chat_contract.py` (~80 LoC, Python) — contract
  test for new `POST /api/chat` + SSE response shape; runs in pytest
  CI on backend changes, forces both mobile clients to converge

**Tests:**
- `companion/src/test/java/world/meeet/tars/companion/ScaffoldTest.kt`
  (~80 LoC, Robolectric) — assert all 4 nav destinations resolve

**CI:**
- `.github/workflows/android-build.yml` (~60 LoC) — runs on
  `ubuntu-22.04`, installs Java 17 + Android SDK 34 via
  `android-actions/setup-android@v3`, runs `./gradlew :companion:assembleRelease :companion:test`
- Target build time: <12 min for full assemble + test (cold cache);
  <4 min for incremental

**Acceptance:**
- [ ] `./gradlew :companion:assembleRelease` produces signed-debug AAB
- [ ] `./gradlew :app:test :companion:test` — 24 tests pass (16
      existing + 8 new ScaffoldTest)
- [ ] `tests/test_mobile_chat_contract.py` passes via `pytest` (uses
      `respx` to stub backend response)
- [ ] CI green on PR

### Step 2: `ChatClient` + `SseLineBuffer` + `ThreadStore`

**Files (~520 LoC Kotlin + ~200 LoC test):**
- `mobile/android/TARSCompanion/app/src/main/java/world/meeet/tars/net/SseLineBuffer.kt`
  (~120 LoC) — pure Kotlin line buffer; consumes `ByteString` chunks
  from OkHttp's `EventSource.Listener.onEvent`, emits complete
  `event:` / `data:` / blank-line-terminated frames as `Flow<SseFrame>`
- `mobile/android/TARSCompanion/app/src/main/java/world/meeet/tars/net/ChatClient.kt`
  (~250 LoC) — opens `POST /api/chat` with SSE Accept header, parses
  `chunk.delta` / `chunk.tool_use` / `chunk.done` / `chunk.error`
  frames into `Flow<ChatEvent>`; auto-retries with exponential
  backoff on `IOException` + 503; cancellation via `CoroutineScope`
- `mobile/android/TARSCompanion/app/src/main/java/world/meeet/tars/data/ThreadStore.kt`
  (~150 LoC) — `Room` database for chat history persistence;
  `@Dao` with `messagesByThreadId` (Flow), `appendMessage`,
  `markAcked`; survives process death so a backgrounded chat can
  resume mid-stream after foreground

**Tests:**
- `app/src/test/java/world/meeet/tars/net/SseLineBufferTest.kt`
  (~100 LoC, JUnit 4) — 8 scenarios: complete frame, frame split
  across chunks, blank lines, comment lines (`:` prefix), Unicode in
  data, very long lines, mid-frame disconnect, malformed input
- `app/src/test/java/world/meeet/tars/net/ChatClientContractTest.kt`
  (~100 LoC, JUnit 4 + MockWebServer) — fakes backend, asserts
  exponential backoff schedule (100ms / 400ms / 1.6s / 6.4s + jitter),
  asserts `chunk.error` frames terminate the flow with
  `ChatException`

**Dependencies added to `app/build.gradle.kts`:**
- `androidx.room:room-runtime:2.6.1` + `room-ktx` + `room-compiler`
  (ksp)
- `org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.0`

**Acceptance:**
- [ ] 18 unit tests green via `./gradlew :app:test`
- [ ] Manual: send 50 messages in a row, verify all 50 land in Room +
      survive process kill / relaunch
- [ ] Backpressure: stream a 5k-line response, verify the Compose UI
      stays responsive (no jank in Macrobenchmark cold-start scenario)

### Step 3: `MainScaffold` + Chat tab Compose surface

**Files (~680 LoC Kotlin):**
- `companion/src/main/java/world/meeet/tars/companion/ui/chat/ChatTab.kt`
  (~80 LoC) — `Scaffold` w/ `TopAppBar` + thread list pane + chat pane
  (two-pane on tablet, single-pane on phone via
  `WindowSizeClass.compact`)
- `companion/src/main/java/world/meeet/tars/companion/ui/chat/ThreadList.kt`
  (~140 LoC) — `LazyColumn` of `ThreadRow` composables with timestamps
  + unread badges, swipe-to-archive
- `companion/src/main/java/world/meeet/tars/companion/ui/chat/MessageList.kt`
  (~220 LoC) — `LazyColumn` of `MessageBubble` composables; auto-
  scroll to bottom on new message; smooth append animation via
  `animateItemPlacement()`
- `companion/src/main/java/world/meeet/tars/companion/ui/chat/Composer.kt`
  (~180 LoC) — `TextField` + send button + attach button (opens SAF
  picker via `ActivityResultContracts.OpenDocument`)
- `companion/src/main/java/world/meeet/tars/companion/ui/chat/ChatViewModel.kt`
  (~60 LoC) — observes `ThreadStore.messagesByThreadId(threadId)`,
  exposes `send(text: String, attachments: List<Uri>)`

**Material 3 design tokens:**
- Use `MaterialTheme.colorScheme` with `dynamicLightColorScheme(context)` /
  `dynamicDarkColorScheme(context)` on Android 12+ for true dynamic
  color (matches user's home screen palette); fallback to seed color
  `Color(0xFF6750A4)` on older
- Typography from `Typography()` w/ `headlineSmall` for thread title,
  `bodyMedium` for message body, `labelSmall` for timestamps
- Shape: `RoundedCornerShape(16.dp)` for message bubbles (slightly
  more rounded than Material default to feel more "AI assistant")

**Tests:**
- Compose UI tests are platform-emulator only (skipped on CI in v11;
  re-enable in v11.2 when we have macOS-runner Android emulator
  budget). Manual smoke checklist in `mobile/QA_PROTOCOL.md` (new).

**Acceptance:**
- [ ] Visual parity with iOS Chat tab (side-by-side screenshot review)
- [ ] 60 fps scroll on Pixel 6 (Macrobenchmark P95 frame time <16ms)
- [ ] Streaming text renders char-by-char without layout shift jank
- [ ] Attach picker round-trips through SAF correctly (manual test)

### Step 4: Plans + Inbox + Settings tabs (read-only)

**Files (~570 LoC Kotlin):**
- `companion/src/main/java/world/meeet/tars/companion/ui/plans/PlansTab.kt`
  (~180 LoC) — mirrors PH7 PlanInbox UI from desktop (#206), read-only
  in v11; tap row → `PlanTimelineBottomSheet` (Material 3
  `ModalBottomSheet` with timeline of steps + status pills)
- `companion/src/main/java/world/meeet/tars/companion/ui/inbox/InboxTab.kt`
  (~190 LoC) — mirrors PH5 Policy UI from desktop (#203), read-only
  in v11; tap row → `PolicyDetailBottomSheet` w/ category chip,
  $-impact, thread back-link
- `companion/src/main/java/world/meeet/tars/companion/ui/settings/SettingsTab.kt`
  (~200 LoC) — sections for Paired devices (list + revoke), Identity
  (rotation entry, defers to web cockpit for actual rotation in v11),
  Mic permission toggle (delegates to PH9 native speech), Telemetry
  opt-in toggle (always-off default in v11, see PH5 telemetry brief
  #204)

**Backend (zero new endpoints — reuses):**
- `GET /api/plans` (already shipped via PH7 planner backend)
- `GET /api/policy/queue` (already shipped via Wave 101)
- `GET /api/pairing/devices` (already shipped via L5)
- `GET /api/privacy/state` (already shipped)
- WebSocket subscriptions over the existing `/ws/cockpit` channel for
  live updates (read-only on mobile)

**Acceptance:**
- [ ] All three tabs render real data from a live TARS host
- [ ] No write actions exposed (approve/reject buttons disabled w/
      tooltip "Approve from desktop cockpit in v11")
- [ ] Pull-to-refresh on each tab triggers re-fetch

### Step 5: Internal Testing build pipeline via Gradle Play Publisher

**Files (~400 LoC + 1 fastlane folder):**
- `mobile/android/TARSCompanion/build.gradle.kts` (~30 LoC delta) —
  add `id("com.github.triplet.play") version "3.10.1"` plugin
- `mobile/android/TARSCompanion/companion/build.gradle.kts` (~80 LoC
  delta) — configure `play {}` block (track="internal",
  serviceAccountCredentials, releaseStatus="draft" until manual promote)
- `mobile/android/TARSCompanion/keystore/release.keystore.gpg` — GPG-
  encrypted upload keystore (decrypt in CI via `KEYSTORE_PASSWORD`
  secret); add `*.keystore` + `*.keystore.gpg.unenc` to .gitignore
- `.github/workflows/android-internal.yml` (~120 LoC) — manual-
  dispatch workflow; decrypt keystore, set `versionCode` to
  `github.run_number + 1000` for monotonicity, run `./gradlew
  publishCompanionInternalBundle`
- `mobile/android/TARSCompanion/fastlane/metadata/android/en-US/` (~150
  LoC across `title.txt`, `short_description.txt`, `full_description.txt`,
  `release_notes/default.txt`) — Play Store listing copy seed (Internal
  track uses minimal metadata, but seed the full copy now for v11.1
  Closed Beta promotion)

**Play Console prerequisites (operator step, ~30 min):**
- Create Play Developer account (~$25 one-time)
- Create new app `TARS Companion` (package: `world.meeet.tars.companion`)
- Create service account in GCP w/ Play Developer Console role
- Generate JSON key, upload as `PLAY_SERVICE_ACCOUNT_JSON` GitHub
  secret
- Upload keystore via Play Console Upload Key dance (App Signing by
  Google Play)
- Manual app-content forms (target audience age 17+ given the LLM
  disclosure, data safety form, etc.)

**Acceptance:**
- [ ] `./gradlew publishCompanionInternalBundle` succeeds with stub
      service account creds in dry-run mode
- [ ] CI workflow `android-internal.yml` produces signed AAB in <10 min
- [ ] First real Play Internal Testing release lands w/ 5 test users

### Step 6: Push-to-talk foreground service stub + documentation

**Files (~140 LoC Kotlin + ~170 LoC doc):**
- `companion/src/main/java/world/meeet/tars/companion/service/PushToTalkService.kt`
  (~140 LoC) — `Service` subclass with `START_STICKY`,
  `notification` channel "push_to_talk_active" (low-priority + on-
  going), `startForegroundService` triggered by long-press on a
  voice button in the Chat tab Composer; **records nothing in v11**
  — only manages the foreground state + notification, so the
  PH9 native speech brief can plug actual STT (e.g. Whisper.cpp via
  JNI) into `onStartCommand` / `onAudioFrame` callbacks
- `mobile/QA_PROTOCOL.md` (~170 LoC) — manual smoke checklist for
  each release: pair → send msg → see SSE render → attach photo →
  open Plans → open Inbox → toggle settings; explicit pass/fail
  thresholds per step

**Tests:**
- `companion/src/test/java/world/meeet/tars/companion/service/PushToTalkServiceTest.kt`
  (~80 LoC, Robolectric) — assert notification channel is registered,
  assert foreground service binds + unbinds correctly under app
  backgrounding

**Acceptance:**
- [ ] Long-press voice button → notification appears → release →
      notification clears within 500ms
- [ ] Backgrounding the app does not kill the recording service
      (manual: long-press, swipe to home, hold for 30s, see
      notification still active)
- [ ] `mobile/QA_PROTOCOL.md` checklist runs to completion in <5 min
      on Pixel 6

## 4. Wire contracts

### 4.1 Existing (untouched)

- `/api/pairing/begin` — already shipped, contract-tested
- `/api/pairing/accept` — already shipped
- `/api/pairing/devices` — already shipped (read-only in v11)
- `/ws/cockpit` — existing WebSocket channel (subscribe-only on
  mobile in v11)

### 4.2 New for v11

| Endpoint | Method | Purpose | Contract test |
| -------- | ------ | ------- | ------------- |
| `/api/chat` | POST | streaming chat completion via SSE | new `test_mobile_chat_contract.py` |
| `/api/chat/threads` | GET | list user's threads | covered by chat contract test |
| `/api/chat/threads/{id}/messages` | GET | paginated message history | covered |
| `/api/upload` | POST (multipart) | attachment upload, returns `attachment_id` | new test fixture |

### 4.3 Backend changes implied

These already exist in HTTP form for the desktop cockpit. The brief
only requires:
- `/api/upload` may need a 10 MB request body limit lifted to 50 MB
  (mobile photos are ~5-8 MB) — check `web_extras/app.py`
  `MAX_UPLOAD_BYTES` constant
- SSE keepalive should send a `: keepalive\n\n` comment every 15s to
  prevent OkHttp's default 60s read timeout from terminating the
  connection idle-mid-stream

## 5. Coupling matrix

| Brief | Coupling | Why |
| ----- | -------- | --- |
| **PH9 iOS companion (#208)** | **SOFT (visual)** | Same tab structure (Chat / Plans / Inbox / Settings), same wire contract; design tokens shared via `design-system/tars/MASTER.md` but native idioms preserved (Material 3 vs Liquid Glass) |
| **PH9 native speech** | **HARD (forward)** | `PushToTalkService` stub + `RECORD_AUDIO` manifest + notification channel pre-declared so native-speech can plug in via `onAudioFrame` callback w/o app re-architecture |
| **#203 policy UI** | **SOFT** | Mobile mirrors policy queue read-only; same `GET /api/policy/queue` endpoint; v11.1 adds write actions |
| **#206 planner UI** | **SOFT** | Mobile mirrors plans list read-only; same `GET /api/plans` endpoint; v11.1 adds approve/abort buttons |
| **#202 vault** | **NONE** | Vault is host-side only; mobile holds L5 device key in Android Keystore (StrongBox where available), which is a separate secure enclave on the phone, not the desktop vault |
| **#205 sandbox** | **NONE** | No on-device code execution in v11; sandboxed runtime is desktop-only |
| **#207 marketplace** | **NONE** | No mobile pack install in v11; marketplace v1 is desktop-only |
| **#204 telemetry** | **SOFT (defer)** | Mobile is privacy-by-default in v11: telemetry opt-in defaults to OFF, schema bucket families `mobile.action.*` reserved but not emitted in v11; v11.1 implementer can wire if Play Console privacy review allows |

## 6. Distribution

### 6.1 v11 (Google Play Internal Testing)

- ~100 testers cap (Google's limit on Internal track)
- Manual invite via Play Console
- Recipients are pre-screened (we know who they are; reduces support
  burden)
- No data safety form required for Internal track
- Crash reporting via Play Console crashes panel (no Firebase Crashlytics
  in v11; vendor lock-in risk + meeet ingest already handles it)
- Release cadence: weekly while we iterate

### 6.2 v11.1 (Closed Beta)

- ~10k testers via Play Console-controlled email list or Google Group
- Requires:
  - Data safety form (TARS collects: pairing key (encrypted), chat
    history (on-device only by default), no analytics in v11
    default-off)
  - Content rating (likely 17+ given LLM-generated content)
  - Privacy policy URL (`https://meeet.world/privacy/tars-mobile`)
- Release cadence: bi-weekly

### 6.3 v11.2 (Open Beta + Production)

- Defer 4-6 weeks after v11.1 GA to bake feedback
- Production rollout w/ 5% → 25% → 100% staged rollout via Play Console
- F-Droid build flavor reconsideration here (sanitised, no
  Crashlytics, no Play Services)

## 7. Open questions for operator

1. **Play Developer account ownership.** The Apple Developer account
   is on the user. Should the Play Developer account be the user
   personally ($25 one-time, individual track) or the meeet.world
   organization (still $25, but requires DUNS lookup and email-
   verifiable domain). **Recommend organization track** for v11+
   to set up brand-account-binding before App Store submission gets
   complicated.
2. **`minSdk = 26` (Android 8.0) drops Android 7.x and below.**
   Current `:app` module already does this. ~3% of Android install
   base in 2026. OK to keep at 26?
3. **Dynamic color (Material You) on Android 12+ default ON, fallback
   to seed color on older.** Confirm this is the desired aesthetic
   (alternative: lock to brand palette always for consistency).
4. **Pair-by-typing fallback alongside QR.** iOS brief recommended
   yes; consistency suggests same on Android. Pair-key is a 6-digit
   numeric code + 4-word checksum (already in the iOS brief). Confirm.
5. **FCM push notifications deferred to v11.1.** Recommend yes —
   adds a Google Play Services dependency that complicates F-Droid
   path and Play data-safety form. v11 polls every 30s when foregrounded.
6. **Mobile telemetry default-off in v11.** Recommend yes — matches
   PH5 telemetry default; user explicit opt-in flow can be added in
   v11.1 once the schema is bedded down.
7. **L5 device cap on the host side.** iOS brief flagged this; same
   question for Android. Recommend soft cap at 4 (warning, allow
   override) per host identity.
8. **Robolectric vs full instrumented tests in CI.** Recommend
   Robolectric for v11 (runs on JVM, no emulator needed, ~80% of test
   surface coverable). Full instrumented tests via Firebase Test Lab
   in v11.2 if budget allows.

## 8. Risk register

| # | Risk | Likelihood | Severity | Mitigation |
| - | ---- | ---------- | -------- | ---------- |
| 1 | Compose recomposition jank under SSE stream | Medium | High | Use `derivedStateOf` for message list; benchmark in step 2 |
| 2 | OkHttp `EventSource` silent reconnect loops on bad networks | Medium | Medium | Exponential backoff in `ChatClient` step 2; UI shows "Reconnecting…" pill after 3s |
| 3 | Play Console Internal Testing flake during CI publish | Low | Low | Manual fallback via Play Console upload; CI workflow can re-run idempotently |
| 4 | Foreground service notification on long-press feels heavy for chat-only users | Low | Medium | Notification channel set to `IMPORTANCE_MIN`; only appears during active record |
| 5 | Android Keystore StrongBox availability varies by device | Medium | Low | Fall back to TEE-backed keystore (still hardware-isolated) when StrongBox unavailable; log capability per device |
| 6 | `MaxUploadBytes` backend constant bites first photo upload | High | Low | Step 1 backend grep + bump to 50 MB; test fixture with 8 MB image |
| 7 | Material 3 dynamic color clashes with brand palette on user's OS | Low | Low | Settings toggle "Use brand palette" → falls back to seed color |
| 8 | Two-codebase drift between iOS + Android | Medium | Medium | `test_mobile_chat_contract.py` + design-token shared MD; PR template requires "if iOS changed, did Android sync?" check |

## 9. Test plan

### 9.1 Unit (JVM-only, runs on CI)

- 8 existing pairing decoder tests (`PairingDecodersTest.kt`)
- 8 existing wallet decoder tests (`WalletDecodersTest.kt`)
- 8 new `SseLineBufferTest.kt` scenarios (step 2)
- ~5 `ChatClientContractTest.kt` MockWebServer scenarios (step 2)
- ~8 `ScaffoldTest.kt` Robolectric scenarios (step 1)
- ~5 `PushToTalkServiceTest.kt` Robolectric scenarios (step 6)

**Total:** 42 JVM tests via `./gradlew :app:test :companion:test`,
target <2 min cold cache.

### 9.2 Contract (Python pytest, runs on backend CI)

- Existing `test_mobile_pairing_contract.py` untouched
- New `test_mobile_chat_contract.py` covers `POST /api/chat` SSE shape
  (event names, frame ordering, error envelope), `POST /api/upload`
  multipart shape, `GET /api/chat/threads` response schema

### 9.3 Macrobenchmark (instrumented, runs on Firebase Test Lab nightly)

- Cold start time (target P95 <1500ms on Pixel 6)
- Scroll perf on 200-message thread (target P95 frame time <16ms)
- Memory after 30 min chat session (target <120 MB heap)

### 9.4 Manual smoke (per release, `mobile/QA_PROTOCOL.md`)

- Pair → send msg → SSE render → attach photo → open Plans → open
  Inbox → toggle settings → revoke device → re-pair
- Pass criteria: full flow <3 min on Pixel 6 + Pixel 8 + Samsung S23
  + 5-year-old Pixel 4a (minSdk floor)

## 10. Deliverables checklist

- [ ] `:companion` Gradle module shipped with all 4 nav destinations
- [ ] `ChatClient` + `SseLineBuffer` shipped + tested
- [ ] `MainScaffold` Chat tab matches iOS visual parity
- [ ] Plans / Inbox / Settings tabs render real backend data (read-only)
- [ ] Internal Testing build pipeline succeeds in CI
- [ ] First Internal Testing release lands w/ ≥5 testers
- [ ] `PushToTalkService` stub validated (foreground state + notification)
- [ ] 42 JVM tests green via `./gradlew test`
- [ ] `tests/test_mobile_chat_contract.py` green via `pytest`
- [ ] Macrobenchmark suite added + baseline captured
- [ ] `mobile/QA_PROTOCOL.md` checklist drafted
- [ ] Update `mobile/android/TARSCompanion/README.md` to point at v11
      acceptance criteria
- [ ] Update `mobile/README.md` to flip Android status from "L2
      shipped" → "v11 first release"
- [ ] Mark `ph9-android` complete in `docs/PRODUCT_MASTER_PLAN.md §3.9`

## 11. Forward dependencies (post-merge)

Once this brief lands and the implementer ships:

- **PH9 native speech brief** can plug Whisper.cpp (or `SpeechRecognizer`
  as a v0 fallback) into `PushToTalkService.onAudioFrame()` without
  Service or NotificationChannel re-architecture.
- **v11.1 Plans/Inbox write actions brief** can add approve/reject
  buttons that enqueue policy confirmations via the existing
  `/api/policy/confirm` endpoint (no UI architecture changes).
- **v11.1 FCM push notifications brief** can wire device-token
  registration on top of the existing pairing flow; backend already
  emits the event kinds, just need a `push.dispatch` adapter.
- **v11.2 Open Beta + Production rollout brief** consolidates Play
  data safety form, content rating, privacy policy URL, and staged
  rollout sequencing.

---

**End of Phase 9 L10 Android companion brief (W310-x).**

> Companion to PH9 iOS (#208). Together they open the v11 mobile
> planning surface. Next mobile briefs incoming: PH9 native mobile
> speech (Whisper.cpp + native TTS, replaces Web Speech API on both
> iOS + Android), followed by mobile-specific UX polish briefs as the
> Internal Testing feedback comes in.
