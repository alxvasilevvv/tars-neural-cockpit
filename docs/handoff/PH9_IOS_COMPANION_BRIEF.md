# PH9 — Phase 9 / L10 iOS companion app (SwiftUI) implementer brief

**Owner:** next iOS-lane implementer
**Release target:** v11 (TestFlight); App Store after v11.1
**Scope window:** ~3 weeks / ~6 PRs
**Estimated LoC:** ~2.4k Swift + ~600 LoC tests
**Status entering brief:** **pairing-first SPM library shipped (`mobile/ios/TARSCompanion/`, 11 unit tests green); Xcode app target greenfield**

---

## 0. TL;DR for the implementer

This brief delivers the **first shippable iOS companion** — a SwiftUI
app target on top of the already-shipped `TARSCompanion` SPM library.
Today the library has pairing handshake (`POST /api/pairing/begin`)
plus a barebones `WalletView` proof-of-concept. Operators cannot
install the companion because there is no Xcode app target.

What this brief delivers:

1. `TARSCompanion.xcodeproj` Xcode app target (universal binary,
   iOS 17.0+ minimum) consuming the existing SPM library.
2. **Streaming chat** view — SSE over `/api/chat/threads/{id}/messages`
   with native `URLSession` data tasks.
3. **Attachment upload** — `PHPickerViewController` + multipart upload
   to `POST /api/chat/threads/{id}/attachments`.
4. **`<MainTabView />`** with 4 tabs: Chat, Plans, Inbox, Settings —
   parity with cockpit nav (read-only for v11; write actions
   ship in v11.1 after App Store review feedback).
5. **TestFlight build pipeline** — fastlane lane + GH Actions matrix.
6. Stub for **L4 voice loop** (full implementation lives in the
   sibling PH9 native-speech brief).

This is **not** a Cordova/React Native wrapper. Two native codebases
remain the canonical L10 design (see `mobile/README.md §Why two
codebases`).

---

## 1. Why this brief exists

`docs/PHASE_L_ROADMAP.md §L10` calls for two native companion apps.
Today (`main`):

```
mobile/ios/TARSCompanion/
├── Package.swift                 # SPM library only
├── Sources/TARSCompanion/        # 11 files
│   ├── PairingClient.swift       # POST /api/pairing/begin
│   ├── PairingCrypto.swift       # CryptoKit ed25519 + X25519
│   ├── PairingEnvelope.swift     # JSON model
│   ├── PairingKeychain.swift     # Keychain wrapper
│   ├── PairingView.swift         # SwiftUI pairing flow
│   ├── PairingViewModel.swift
│   ├── QRScannerView.swift       # AVFoundation
│   ├── TARSCompanion.swift       # library entry
│   ├── TARSCompanionRoot.swift   # root SwiftUI scene
│   ├── WalletClient.swift        # proof-of-concept HTTP
│   └── WalletView.swift          # PoC view
└── Tests/TARSCompanionTests/     # 11 tests, all green via `swift test`
```

So the **pairing surface** + **basic networking primitives** + **a
SwiftUI host scene** all exist. The pairing handshake is contract-
tested against the backend via `tests/test_mobile_pairing_contract.py`.
What's missing is the actual operator-facing app.

This brief is the closure for the iOS half of L10 v1.

---

## 2. Target architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ TARSCompanion.xcodeproj                                         │
│ ├── TARSCompanion (App target, iOS 17.0+ universal binary)      │
│ │   └── @main TARSCompanionApp.swift                            │
│ │       └── WindowGroup → MainTabView                           │
│ │           ├── ChatTab (NavigationStack → ThreadListView →     │
│ │           │            ChatView + AttachmentSheet)            │
│ │           ├── PlansTab (read-only; calls /api/planner)        │
│ │           ├── InboxTab (read-only; calls /api/policy/queue)   │
│ │           └── SettingsTab (paired device info, theme, logout) │
│ └── TARSCompanion (existing SPM library — Sources/, Tests/)     │
└─────────────────────────────────────────────────────────────────┘

URLSession + SSE     →    https://<paired-host>:8001/api/...
                              (via tailnet/LAN/meeet.world relay
                               depending on pairing mode)

KeyStorage:  Keychain (existing PairingKeychain helper from SPM lib)
Crypto:      CryptoKit (existing PairingCrypto from SPM lib)
Background:  None for v11; v11.1 adds BGAppRefreshTask for
             "new chat message" badge
```

---

## 3. Wire contract (shipped, read-only)

The iOS app **does not** alter the backend; it consumes the existing
endpoints. Verified live on `main`:

| Method | Path | Purpose |
| ------ | ---- | ------- |
| `GET`  | `/api/chat/threads` | list threads |
| `GET`  | `/api/chat/threads/{id}` | one thread |
| `POST` | `/api/chat/threads/{id}/messages` | send message (streams SSE on accept-header) |
| `POST` | `/api/chat/threads/{id}/attachments` | multipart upload |
| `GET`  | `/api/planner` | list plans (read-only mobile view) |
| `GET`  | `/api/planner/{id}/full` | plan detail |
| `GET`  | `/api/policy/queue` | inbox view |
| `GET`  | `/api/policy/pending` | unread count for badge |
| `POST` | `/api/policy/{id}/confirm` | (v11.1 only — write action) |
| `GET`  | `/api/search` | parity with cockpit ⌘K (mobile pull-down) |

SSE handling: `URLSession.dataTask` with manual line-buffered parsing.
A small `SSEEvent` model + `SSEDecoder` actor goes in the library
(see step 2).

---

## 4. Mechanical steps

### Step 1 — Xcode project + app target + CI smoke (~290 LoC + project files)

**Files (new):**

- `mobile/ios/TARSCompanion/TARSCompanion.xcodeproj/` (Xcode-managed).
- `mobile/ios/TARSCompanion/App/TARSCompanionApp.swift` (~40 LoC) —
  `@main` entry, hooks `TARSCompanionRoot` from the SPM library.
- `mobile/ios/TARSCompanion/App/AppDependencies.swift` (~80 LoC) —
  DI container; injects `URLSession`, `Keychain`, `PairingClient`,
  the new `ChatClient`, etc.
- `mobile/ios/TARSCompanion/App/Info.plist` (~20 LoC) — `NSCameraUsageDescription`
  (already needed for pairing), `NSPhotoLibraryUsageDescription`
  (attachments), `NSLocalNetworkUsageDescription` (Bonjour
  discovery), `NSMicrophoneUsageDescription` (deferred to native-
  speech brief but pre-declare to dodge a re-review).
- `mobile/ios/TARSCompanion/App/Assets.xcassets/` — app icon set
  + accent color.
- `.github/workflows/ios-build.yml` (~150 LoC) — fastlane lane
  `build_for_testing`, runs `swift test` on the library + `xcodebuild
  test` on the app target with `iPhone 15 Pro` simulator. Triggered
  on every PR touching `mobile/ios/**`.

CI uses `macos-14` runner (Apple Silicon required for SwiftUI Live
Preview on the new Xcode pipeline).

### Step 2 — `ChatClient` + SSE decoder + thread store (~480 LoC)

**Files (new in SPM lib):**

- `mobile/ios/TARSCompanion/Sources/TARSCompanion/ChatClient.swift`
  (~280 LoC) — actor with `listThreads()`, `getThread(id:)`,
  `sendMessage(threadId:text:streaming:)`, `uploadAttachment(threadId:
  fileURL:mime:)`.
- `mobile/ios/TARSCompanion/Sources/TARSCompanion/SSEDecoder.swift`
  (~120 LoC) — line-buffered parser; emits `SSEEvent(kind:data:id:)`
  via `AsyncSequence`.
- `mobile/ios/TARSCompanion/Sources/TARSCompanion/ThreadStore.swift`
  (~80 LoC) — `ObservableObject` cache for active thread; flushes
  to disk via `Codable + FileManager` on background task.

**Files (new tests):**

- `mobile/ios/TARSCompanion/Tests/TARSCompanionTests/ChatClientTests.swift`
  (~80 LoC) — mocked URLSession.
- `mobile/ios/TARSCompanion/Tests/TARSCompanionTests/SSEDecoderTests.swift`
  (~60 LoC) — line-buffered edge cases (CRLF/LF/buffer split mid-frame).

### Step 3 — `MainTabView` + Chat tab (~620 LoC)

**Files (new in App target):**

- `mobile/ios/TARSCompanion/App/Views/MainTabView.swift` (~120 LoC) —
  4-tab `TabView` w/ symbol icons (`bubble.left.fill`, `list.bullet.rectangle`,
  `tray.full.fill`, `gear`).
- `mobile/ios/TARSCompanion/App/Views/Chat/ThreadListView.swift` (~140 LoC) —
  `List` of threads, pull-to-refresh, search bar wired to `/api/search`.
- `mobile/ios/TARSCompanion/App/Views/Chat/ChatView.swift` (~210 LoC) —
  message bubble layout (user-right, assistant-left), `TextField`
  composer w/ multi-line growth, send button, SSE-driven incremental
  text render.
- `mobile/ios/TARSCompanion/App/Views/Chat/MessageBubble.swift` (~90 LoC).
- `mobile/ios/TARSCompanion/App/Views/Chat/AttachmentSheet.swift` (~60 LoC) —
  `PHPickerViewController` wrapper → calls
  `ChatClient.uploadAttachment(...)` then injects the resulting
  attachment markdown into the composer.

iOS 17 Liquid Glass / Material treatment uses native `.background(.ultraThinMaterial)`
modifiers; no third-party libs.

### Step 4 — Plans + Inbox tabs (read-only) + Settings (~510 LoC)

**Files (new in App target):**

- `mobile/ios/TARSCompanion/App/Views/Plans/PlansListView.swift` (~140 LoC) —
  scrollable plan inbox; status pill + step count + cost badge.
  Tap → `PlanDetailView` (read-only).
- `mobile/ios/TARSCompanion/App/Views/Plans/PlanDetailView.swift` (~100 LoC).
- `mobile/ios/TARSCompanion/App/Views/Inbox/InboxListView.swift` (~120 LoC) —
  policy confirmations queue, badge with pending count. Tap →
  `ConfirmationDetailView` (read-only v11; confirm/deny actions
  added in v11.1).
- `mobile/ios/TARSCompanion/App/Views/Inbox/ConfirmationDetailView.swift` (~70 LoC).
- `mobile/ios/TARSCompanion/App/Views/Settings/SettingsView.swift` (~80 LoC) —
  paired device info (host hostname, paired-at timestamp), theme
  toggle, "unpair" button (calls existing `PairingClient.unpair()`).

These tabs share the same `PlannerClient` / `PolicyClient` /
`SettingsClient` actors that the implementer should add to the SPM
lib in step 2-extension (~60 LoC each).

### Step 5 — TestFlight build pipeline + fastlane + provisioning (~330 LoC)

**Files (new):**

- `mobile/ios/TARSCompanion/fastlane/Fastfile` (~120 LoC) — lanes:
  `bump_build`, `build_dev`, `build_testflight`, `submit_testflight`.
- `mobile/ios/TARSCompanion/fastlane/Appfile` (~10 LoC).
- `mobile/ios/TARSCompanion/fastlane/Matchfile` (~10 LoC) —
  certs / profiles via `fastlane match` (private Git repo).
- `.github/workflows/ios-testflight.yml` (~160 LoC) — manual
  dispatch on tag `mobile-ios-v*` → runs `bump_build` →
  `build_testflight` → `submit_testflight`. App-specific password
  + ASC API key are GH secrets.
- `mobile/ios/TARSCompanion/CHANGELOG_TESTFLIGHT.md` (~30 LoC) —
  release notes copy-paste source.

Distribution: TestFlight only for v11. App Store submission
deferred to v11.1 once L4 voice + L5 device list polish ship and
the Apple LLM-handling disclosure language is finalised.

### Step 6 — Documentation + smoke checklist (~170 LoC)

**Files (new):**

- `mobile/ios/TARSCompanion/README.md` — replace stub with v11
  installer + dev setup (~80 LoC).
- `docs/MOBILE_IOS_SETUP.md` (~90 LoC) — operator-facing guide
  (Apple ID + provisioning + pair to host + first chat).

---

## 5. Test plan summary

| Test type | Count | Pass gate |
| --------- | ----- | --------- |
| SPM library `swift test` | 11 existing + 14 new = 25 | 25/25 green |
| Xcode app target `xcodebuild test` | 16 (UI snapshot via `XCTest`) | 16/16 green |
| Backend contract `tests/test_mobile_pairing_contract.py` | unchanged | green |
| Manual TestFlight smoke | 5 scenarios | all pass |
| Accessibility audit (Xcode `Accessibility Inspector`) | App-wide | 0 critical issues |

Smoke test (manual): operator pairs to a TARS host on the local
network, sees thread list populated, opens a thread, sends a
message, observes SSE incremental render, attaches a photo,
verifies it lands in the host's `~/.tars/attachments/`. <3 min
end-to-end on iPhone 15 Pro.

---

## 6. Coupling notes

| Other brief / system | Hard / Soft | Reason |
| -------------------- | ----------- | ------ |
| **PH5 vault (#202)** | Soft | iOS Keychain holds the L5 device key; vault is host-side only. Mobile is unaffected. |
| **PH5 policy UI (#203)** | Soft | Mobile Inbox tab is read-only mirror; v11.1 adds write actions. |
| **PH5 telemetry (#204)** | Soft | Mobile companion does **not** emit telemetry in v11 (privacy-by-default). v11.1 adds opt-in mobile telemetry separately. |
| **PH6 L3 sandbox (#205)** | None | Mobile does not run user code locally; sandboxed runs stay host-side. |
| **PH7 planner UI (#206)** | Soft | Mobile Plans tab is a read-only mirror of the cockpit `/plans` page. v11.1 adds approve/abort actions. |
| **PH8 marketplace (#207)** | None | Mobile does not install packs in v11. v11.1 may add a read-only catalog browse. |
| **PH9 Android sibling (next brief)** | Soft (visual) | Same wire contract, same tab structure, same paired-device guarantees. Code paths are independent (no shared Swift/Kotlin code in v11). |
| **PH9 native speech (next brief)** | Hard (forward) | Native voice loop work lives in a separate brief; this brief leaves a `VoiceTab` stub + microphone permission pre-declared in Info.plist. |
| **Apple App Store** | Hard (deferred) | v11 ships TestFlight only. App Store submission happens after Apple's LLM-disclosure language is dialed in (see open Q §8.1). |

---

## 7. Operator-side checklist (v11 GA)

Add to `docs/V11_GA_CHECKLIST.md`:

- [ ] **E1.** TestFlight build available with the v11 version
      bumped (`mobile/ios/TARSCompanion/build` ≥ 110).
- [ ] **E2.** Pair from iPhone to a TARS host on local Wi-Fi in
      <60 s.
- [ ] **E3.** Send a message; SSE renders the assistant reply
      token-by-token.
- [ ] **E4.** Attach a photo from Photos; verify it lands in the
      host's `~/.tars/attachments/<thread>/`.
- [ ] **E5.** Open Plans tab; observe the same plans as the
      cockpit (read-only).
- [ ] **E6.** Open Inbox tab; observe the same pending count as
      the cockpit pill.
- [ ] **E7.** Unpair from Settings; subsequent app launch returns
      to pairing flow.
- [ ] **E8.** Crash-free session over 30 min mixed-use soak.

---

## 8. Open questions for operator

1. **Apple LLM-disclosure language.** App Store review requires
   explicit disclosure when an LLM is involved. Recommend operator
   draft language with legal counsel before App Store submission;
   v11 stays on TestFlight to side-step this.
2. **Minimum iOS version.** Recommend iOS 17.0 for SwiftUI Liquid
   Glass + native Material treatments; this drops iPhone 8 and
   below. Operator to confirm.
3. **Universal vs iPad-only optimization.** Recommend universal
   (iPhone + iPad) with adaptive layouts; iPad-specific
   optimizations defer to v11.1.
4. **Pairing QR**: should we also support typing the pair_id
   manually? Recommend yes (existing flow allows but UX could be
   smoother).
5. **Push notifications**: v11 does not implement APNs. v11.1
   adds APNs for "new plan", "pending confirmation", and "voice
   relay request" with explicit per-category opt-in.
6. **Mobile telemetry**: confirm v11 is privacy-by-default
   (no events emitted from the mobile client; host-side
   telemetry counts the mobile-originated requests). Recommend yes.
7. **L5 device limit**: how many paired mobiles per host? Backend
   has no enforced limit today; UI should show all paired devices
   in the host cockpit (#196). Recommend soft cap at 4 in v11 with
   warning toast; hard cap deferred.

---

## 9. Effort estimate

| Step | LoC | Hours |
| ---- | --- | ----- |
| 1. Xcode project + app target + CI | 290 | 7 |
| 2. ChatClient + SSEDecoder + ThreadStore | 480 | 10 |
| 3. MainTabView + Chat tab | 620 | 14 |
| 4. Plans + Inbox + Settings tabs | 510 | 11 |
| 5. TestFlight pipeline + fastlane | 330 | 7 |
| 6. Documentation + smoke checklist | 170 | 3 |
| **Total** | **2400** | **52 hrs (~3 weeks)** |

Six PRs recommended; step 1 must land first (project file required
for compile). Steps 2-5 can land in parallel after step 1.

---

## 10. Out of scope (explicit non-goals)

- **App Store submission** — TestFlight only for v11.
- **Push notifications (APNs)** — v11.1.
- **Write actions on Plans/Inbox** — v11 mobile is read-only on
  these surfaces.
- **Local-on-device LLM inference** — v11 hits the host; on-device
  LLM (e.g. Apple Foundation Models) is a separate v12 brief.
- **Native voice loop** — covered by sibling PH9 native-speech
  brief.
- **iPad-specific layouts** — v11 is universal w/ adaptive
  layouts; iPad-specific (split view, multitasking) → v11.1.
- **Shared Rust crypto core** — see `mobile/README.md` "Optional
  later"; v11 keeps Swift CryptoKit + Kotlin BouncyCastle
  independent.

---

## 11. Acceptance criteria (merge gate)

- [ ] All 25 SPM library tests + 16 app target tests green on CI.
- [ ] `xcodebuild build-for-testing` succeeds on `macos-14`
      with Xcode 15.4+ in <8 min.
- [ ] TestFlight build artifact produced by `ios-testflight.yml`
      after merge.
- [ ] Manual smoke checklist (§5) signed off by operator on a
      real iPhone 15 Pro device.
- [ ] No new SPM deps beyond existing Apple frameworks.
- [ ] `mobile/ios/TARSCompanion/README.md` updated with v11
      installer + dev setup.
- [ ] Accessibility Inspector reports 0 critical issues.

---

**End of brief.** Sibling briefs: PH9 Android (next), PH9 native
speech (after Android). PH10 (Claude design polish backlog) closes
the autonomous orchestration window.
