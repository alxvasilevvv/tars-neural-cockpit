# Phase 3 (L5 close, v10.2) — Mobile begin/accept protocol flows

**Status:** PLANNING-SURFACE — implementer brief
**Target release:** v10.2 (after v10.1 ships desktop pairing UX from #196)
**Lane:** L5 — pairing + secure sync
**Effort estimate:** ~2 weeks impl, ~1.8k LoC (~700 Swift + ~700 Kotlin + ~400 Python contract test + ~300 LoC mobile UX deltas) + ~600 LoC tests
**Authored:** 2026-05-18 (W310-z continuation, autonomous orchestrator)
**Depends on:** #196 (desktop pairing UX), #208 (iOS companion), #209 (Android companion)
**Coordinates with:** `ph3-pair-ttl` brother-side task (meeet.world relay)

---

## 1. Motivation

The L5 pairing backend has been **host-only complete since W250** (10 REST
endpoints, X25519 + XChaCha20-Poly1305, BIP-39 recovery). Mobile companion
apps have **client-side pairing libraries already shipped**:

| Layer | iOS | Android |
|---|---|---|
| HTTP client | `mobile/ios/TARSCompanion/Sources/TARSCompanion/PairingClient.swift` (~190 LoC) | `mobile/android/TARSCompanion/app/src/main/java/world/meeet/tars/net/PairingClient.kt` (~160 LoC) |
| X25519 + AEAD | `PairingCrypto.swift` (Apple CryptoKit) | `PairingCrypto.kt` (BouncyCastle) |
| Envelope codec | `PairingEnvelope.swift` | `PairingEnvelopeParser.kt` |
| Keychain / Keystore persist | `PairingKeychain.swift` | inline (Android Keystore via Crypto) |
| Onboarding UI | `PairingView.swift` (SwiftUI) + `QRScannerView.swift` | `PairingScreen.kt` (Compose) + `PairingActivity.kt` |
| MVVM glue | `PairingViewModel.swift` | `PairingViewModel.kt` |
| Wire-parity contract tests (JVM-only / XCTest) | `Tests/TARSCompanionTests/` 11 cases | `app/src/test/java/.../PairingDecodersTest.kt` |

The iOS client header explicitly states *"mirrors the iOS PairingClient
surface 1:1 so contract tests can compare both sides against a single
source of truth"* — wire parity is already a design invariant. What is
**not yet specified** is the **end-to-end happy-path + edge-case flow**
across all three sides (host + iOS + Android + meeet.world relay), and
the **operational layer** the mobile user needs once paired (audit
visibility, revoke-from-mobile, recovery flow, push notification on new
device, `pair_id` TTL on the relay).

This brief defines those flows and the cross-platform contract test that
asserts they all agree on the wire.

---

## 2. Goals / non-goals

### Goals

1. **End-to-end happy-path documentation** — desktop-initiated AND
   mobile-initiated pair flows with state-transition diagrams that map
   to the existing `PairingState` enum (`pending → linked | expired |
   rejected`).
2. **Cross-platform contract test** — a single Python test that drives a
   live host, an iOS XCTest fixture, and an Android JVM fixture against
   the same wire fixtures, asserting byte-for-byte decoder parity (same
   approach as PR #210's `test_mobile_voice_contract.py` for native
   speech).
3. **Mobile UX deltas** — three new mobile screens that surface what
   the user needs post-pair: **My Paired Devices** (this phone shows
   the desktop and any other phones in the operator's device set),
   **Audit Log** (per-device pairing history), **Revoke** (one-tap
   remove-this-phone from another paired device).
4. **Recovery flow** — if user wipes phone, the BIP-39 recovery seed
   on the host re-mints the mobile keypair from a derived path
   (`m/44'/0'/0'/<device_kind>/<device_id>`); brief specifies the
   mnemonic mode + UX for both iOS and Android.
5. **`pair_id` TTL on meeet.world relay** — brother-side coordination
   for the relay's TTL semantics (currently no TTL → orphan QR codes
   accumulate; need 30-min auto-expiry matching host-side `expires_at`).
6. **Push notification on new device pair** — APNs (iOS) and FCM
   (Android) registration so the operator's other paired devices get
   a system notification when a new device joins their identity.

### Non-goals

- ❌ **Desktop pairing UX rebuild** — already specified in PR #196.
- ❌ **New cryptographic primitives** — X25519/XChaCha20 are shipped,
   not touching them.
- ❌ **Mobile pack execution** — the marketplace v1 (#207) ships first.
- ❌ **Voice/STT on mobile** — separate brief in PR #210.
- ❌ **Encrypted sync envelope** — that's a v10.1 host-only deliverable;
   mobile will inherit it transparently in v10.2 without a new brief.
- ❌ **Web cockpit pairing UI** — the cockpit pairing UX (PR #196) is the
   canonical surface; web showcase has no pairing.
- ❌ **TLS cert pinning** — TARS pairing rides on `https://` end-to-end;
   cert pinning is a v11 hardening pass.

---

## 3. Target architecture

### 3.1 State machine (unchanged from host-only, formalized here)

```
                  ┌─────────────┐
                  │  pending    │  (host minted pair_id, mobile fetched envelope)
                  └──────┬──────┘
                         │
                ┌────────┼──────────────────┐
                │        │                  │
                │     (timeout              │
                │      ≥ expires_at         │
                │      from host)           │
                │        │                  │
                ▼        ▼                  ▼
        ┌──────────┐ ┌────────┐    ┌─────────────┐
        │  linked  │ │expired │    │  rejected   │
        └────┬─────┘ └────────┘    └─────────────┘
             │  (operator approved
             │   on desktop)
             ▼
   [device added; can now
    sync, audit appears]
```

All four states **already exist** in the host store
(`backend/core/pairing/store.py` line 95) and in both mobile clients
(`PairingState` enum, both .swift and .kt). The brief doesn't add
states; it formalizes which actor mutates which transition:

| Transition | Actor | Endpoint | Rate-limit |
|---|---|---|---|
| `(none) → pending` | **mobile** (`begin`) | `POST /api/pairing/begin` | 3/min/IP (already shipped) |
| `pending → linked` | **desktop** (`accept`) | `POST /api/pairing/accept` | 1/30s/host (already shipped) |
| `pending → rejected` | **desktop** (`reject`) | `POST /api/pairing/reject` | 5/min/host |
| `pending → expired` | **host** (background sweeper, no API) | n/a | TTL = 30 min (matches `PairingRecord.expires_at`) |
| `linked → revoked` | **desktop or mobile** (`revoke`) | `POST /api/pairing/revoke` | 5/min/host |

### 3.2 Flow 1: desktop-initiated ("Add device" from cockpit security panel)

```
[Desktop]                              [Mobile]                       [Host]              [meeet.world relay]
   │                                      │                              │                        │
1. Click "Add device" in security panel   │                              │                        │
   │                                      │                              │                        │
2. POST /api/pairing/begin (kind=desktop) ────────────────────────────► (mints pair_id +          │
   │                                      │                              accept_token, sets       │
   │                                      │                              expires_at = now+30min)  │
   │ ◄──────── (returns envelope with pair_id, accept_token, host_pubkey, fingerprint) ──────────┘
   │                                      │                              │                        │
3. Render QR with envelope                │                              │                        │
   │                                      │                              │                        │
4.   ────────── (operator scans QR with phone camera) ────────────────► │                        │
   │                                      │                              │                        │
   │                                      5. QRScannerView decodes envelope                       │
   │                                      │                              │                        │
   │                                      6. PairingClient.begin(epk)   ─►(host validates + links)│
   │                                      │ ◄────── (returns hostInfo) ──┤                        │
   │                                      │                              │                        │
   │                                      7. Polls /pairing/status      ─►(returns linked)        │
   │                                      │                              │                        │
   │ ◄─────────── (SSE event /api/pairing/events: device_added) ────────┤                        │
   │                                      │                              │                        │
8. UI flips "pending" → "linked"; shows new device in list              │                        │
```

**Mobile UX:** `PairingView.swift` and `PairingScreen.kt` already
implement steps 4-7 end-to-end. Operator just needs the cockpit side
(PR #196) to surface step 1 + step 3.

### 3.3 Flow 2: mobile-initiated ("Pair this phone with my TARS" from app)

```
[Mobile]                            [Desktop]                       [Host]              [meeet.world relay]
   │                                   │                              │                        │
1. Tap "Pair with TARS" in app         │                              │                        │
   │                                   │                              │                        │
2. Mobile generates ephemeral X25519 keypair                          │                        │
   │                                   │                              │                        │
3. POST /api/pairing/begin (kind=ios|android) ──────────────────────►│ (mints pair_id +        │
   │                                   │                              accept_token)            │
   │ ◄──────────────────── (returns hostInfo + pair_id) ─────────────┤                        │
   │                                   │                              │                        │
4. Render 6-digit pair code from accept_token (`base32(token)[:6]`)   │                        │
   │ + show host fingerprint for user to compare against desktop      │                        │
   │                                   │                              │                        │
5.   ──────────── (operator types 6-digit code on desktop) ─────────►│                        │
   │                                   │                              │                        │
   │                                   6. Desktop POST /api/pairing/accept (token=…)            │
   │                                   │                              │ (validates, transitions │
   │                                   │                              │  pending→linked)        │
   │                                   │ ◄── (returns device record) ─┤                        │
   │                                   │                              │                        │
7. Polls /pairing/status ──────────────────────────────────────────►│ (returns linked + device_id)
   │ ◄──────────────────── (returns linked) ────────────────────────┤                        │
   │                                   │                              │                        │
8. Mobile saves device_id; pair complete; navigates to /Settings/Devices                       │
```

**Why two flows?** Real-world dynamic: most users open the *desktop* app
first (because TARS *is* the desktop product) and only later install
the mobile companion. Desktop-initiated is the dominant path. But the
operator may want to add a phone *while away from the desktop* (e.g. set
up Android tablet in a different room), so mobile-initiated must also
work — gives 24/7 self-service without needing both screens at once.

### 3.4 Mobile UX new surfaces

Three new mobile screens (both iOS + Android, ~150 LoC per platform per
screen):

#### Screen A — "My Paired Devices" (`/Settings/Devices`)

| Element | iOS (SwiftUI) | Android (Compose) |
|---|---|---|
| List of paired devices | `List(devices)` with `NavigationLink` | `LazyColumn { items(devices) }` |
| Per-device row | name, kind icon, last-seen relative timestamp | same |
| Tap row → device detail | navigation stack push | `Navigator.push` |
| Pull to refresh | `.refreshable { vm.reload() }` | `SwipeRefresh` |
| Empty state | "No other devices paired yet — visit your desktop to add one" | same |

#### Screen B — "Pairing Audit Log" (`/Settings/Devices/Audit`)

Shows the last 50 entries from `GET /api/pairing/audit` filtered to
events involving devices in the operator's identity:

| Element | Common |
|---|---|
| Reverse-chronological list | one row per audit event |
| Row content | `[icon] verb · device_kind · relative_ts` (e.g. "🔓 Linked · macOS desktop · 3 days ago") |
| Tap row → modal with full details | event kind, actor device, IP/UA hash, raw timestamp |
| Filter chip | "All" / "Pairs" / "Revokes" / "Rotations" |

#### Screen C — Revoke Confirmation (`/Settings/Devices/<id>` → "Remove device")

Modal sheet:

```
┌──────────────────────────────────────┐
│ Remove "iPhone 15 Pro"?              │
│                                      │
│ This device will lose access to your │
│ TARS identity immediately.           │
│                                      │
│ Last seen: 3 hours ago               │
│ Paired: 12 days ago                  │
│                                      │
│ This action cannot be undone.        │
│                                      │
│ [Cancel]  [Remove device]            │
└──────────────────────────────────────┘
```

Calls `POST /api/pairing/revoke` with the device_id. On success, the
device disappears from Screen A and an audit event appears in Screen B.

---

## 4. Cross-platform wire-parity contract test (single source of truth)

The brief's central deliverable. **One Python test, three target runtimes.**

### 4.1 Test file

`tests/test_mobile_pairing_contract.py` (~280 LoC) drives a live host
and asserts that **the JSON bytes** returned by the three pairing
endpoints can be **decoded byte-for-byte identically** by:

- the Python host (via the actual `pairing.py` router responses)
- the iOS Swift decoder (via shelled-out `swift test`)
- the Android Kotlin decoder (via shelled-out `./gradlew :app:test`)

```python
@pytest.mark.parametrize("fixture", [
    "begin_normal", "begin_with_unicode_kind",
    "status_pending", "status_linked", "status_expired", "status_rejected",
    "identity_normal",
])
def test_mobile_pairing_contract_parity(fixture, tmp_path, live_host):
    raw = live_host.get_fixture_response(fixture)   # bytes, exact wire
    py = decode_python(raw, fixture)                # host decoder
    ios = decode_ios_via_xctest(raw, fixture)       # shells xcrun swift test
    android = decode_android_via_gradle(raw, fixture)  # shells gradle test
    assert py == ios == android, (
        f"contract drift on {fixture}:\n"
        f"  python:  {py}\n"
        f"  ios:     {ios}\n"
        f"  android: {android}"
    )
```

### 4.2 CI integration

`.github/workflows/mobile-contract.yml` (new) runs the contract test on:
- macos-latest (has both `swift` + `gradle` + Python)
- Schedule: nightly + on PR to `mobile/**` or `web_extras/routers/pairing.py`

A wire-format drift on any side (e.g. host adds a field, mobile decoder
ignores it silently) fails the test loudly, before either platform can
ship a release that's silently misreading the host.

### 4.3 Fixtures

`tests/fixtures/pairing_wire/*.json` — 7 captured wire responses from
the live host on a known seed. Regeneration script:
`tests/fixtures/pairing_wire/regenerate.py` (when host endpoints
intentionally change, operator regenerates + commits the new fixtures
in the same PR as the host change).

---

## 5. Recovery flow (BIP-39 seed → mobile device re-mint)

If the operator wipes their phone, the mobile pairing keypair is lost
with the OS keychain. Two paths:

### Path A (default, v10.2) — Re-pair from scratch

User opens the freshly-installed app, taps "Pair with TARS", and runs
Flow 2 (§3.3) end-to-end. The host registers a **new** device_id with a
**new** keypair. The old device record stays linked (= still appears in
audit log under its old device_id) but its keys are dead — any push
notification or sync attempt with the old key returns 401.

**Pros:** zero new code; works today.
**Cons:** clutters the device list; user has to manually revoke the old
device entry from Screen C; if the phone was lost (not wiped), the old
keypair is still in unrecovered Keychain bytes and could theoretically
be used by an attacker until manually revoked.

### Path B (opt-in, v10.2) — Deterministic re-mint from recovery seed

When the operator does the initial Flow 2 pair, the mobile client
displays the host's BIP-39 mnemonic (already shipped on host side per
`backend/core/pairing/store.py:recovery_fingerprint`). User writes it
down. On phone-wipe recovery:

1. New phone, fresh install
2. Tap "Recover from seed" instead of "Pair with TARS"
3. Enter 24-word BIP-39 phrase
4. Mobile derives keypair from `m/44'/0'/0'/<device_kind>/<device_id>`
   using the seed (matches host's derivation in `store.py`)
5. Mobile POSTs to `/api/pairing/begin` with the derived public key
6. Host recognizes the public key → matches existing device record →
   transitions directly to `linked` (no operator desktop confirmation
   needed)

**Pros:** zero device-list clutter; old keypair on lost phone becomes
useless immediately because the new phone takes over the same device_id;
"backup → restore" UX matches what mobile users expect from password
managers.

**Cons:** user has to actually keep the BIP-39 phrase; if they don't,
they fall back to Path A; mobile app has to ship a UI for typing 24
words (annoying); the deterministic derivation has to match host code
exactly (one test asserts this).

**Recommendation:** Ship both paths. Path A is the default; Path B is a
single button on the recovery screen, with a one-line explanation
("Have your 24-word backup phrase? Recover instantly without touching
your desktop").

---

## 6. meeet.world relay coordination (`ph3-pair-ttl`)

Currently the meeet.world relay forwards `/api/pairing/begin` envelopes
to the host as a pass-through — no TTL, no rate-limit, no replay
detection. This is fine for the host-side because the host enforces
TTL via `PairingRecord.expires_at`, but the **relay** accumulates
orphaned envelope records indefinitely:

- A user starts pairing on their phone, gets the envelope, then closes
  the app and never finishes
- The relay still has the envelope blob in memory / Redis
- 6 months later, the same user looks at relay storage and sees ~2000
  orphan envelopes

Plus a security gap: an attacker who briefly compromises the relay
could replay an orphan envelope to a stale-but-still-pending host
(rare, but possible — 30-min window).

### Brother-side fix (small, no protocol change)

The relay should:

1. Apply a **30-minute TTL** to every envelope record (matches host's
   `expires_at`) — auto-delete after 30 min from cache.
2. Detect **replay**: if the same `pair_id` is GET'd more than 60 times
   within 5 minutes, log a `pairing.relay.replay_suspected` event and
   start returning 429.
3. Emit **metrics**: `relay.pairing.envelopes_active` gauge,
   `relay.pairing.envelopes_expired_total` counter.

**Filed as** `ph3-pair-ttl` brother coord task in
`docs/handoff/PH11_BROTHER_HANDOFF_BRIEF.md` §6 (already surfaced;
this brief just provides the spec).

---

## 7. Push notification on new pair (APNs + FCM)

**Why:** when a new device pairs with the operator's identity, every
*already-paired* device should get a system notification. Without this,
an attacker who manages to pair their own device (e.g. by social-
engineering the operator into scanning a malicious QR) goes undetected.

### Architecture

- Host stores APNs device tokens (iOS) and FCM tokens (Android) for
  each paired mobile device (`PairedDevice.push_token` field, already
  exists per `store.py:108`)
- On `pending → linked` transition, host iterates over all
  *other* linked devices in the same identity and sends a push:

  ```json
  {
    "kind": "tars.security.new_device_paired",
    "title": "New device joined your TARS",
    "body": "iPhone 15 Pro paired 12s ago. If this wasn't you, tap to revoke.",
    "deep_link": "tars://settings/devices?highlight=<new_device_id>"
  }
  ```

- Tapping the notification opens the mobile app on Screen A with the
  new device highlighted, with a prominent "Not me — revoke immediately"
  button that triggers Screen C against the *new* device.

### Implementation cost

| Component | LoC | Where |
|---|---|---|
| Host APNs sender | ~120 LoC | new `backend/core/pairing/push.py` |
| Host FCM sender | ~110 LoC | same file |
| iOS APNs registration | ~60 LoC | `TARSCompanionRoot.swift` (already has `UNUserNotificationCenter` hook) |
| Android FCM registration | ~80 LoC | `TARSCompanion.kt` (needs `FirebaseMessagingService`) |
| Tests | ~150 LoC | `tests/test_pairing_push.py` |
| **Total** | **~520 LoC** | |

### Operator config

| Env var | What it sets | Default |
|---|---|---|
| `TARS_APNS_KEY_ID` | APNs auth key ID (from Apple Developer portal) | empty (push disabled) |
| `TARS_APNS_TEAM_ID` | Apple Team ID | empty |
| `TARS_APNS_KEY_PATH` | Path to `.p8` auth key | empty |
| `TARS_FCM_PROJECT_ID` | Firebase project ID | empty |
| `TARS_FCM_SERVICE_ACCOUNT_PATH` | Path to FCM service account JSON | empty |

Graceful degrade: if any of these are empty, push silently no-ops (logs
once at startup); the rest of the pairing flow still works. v10.2 GA
ships with push **optional**; v10.3 promotes it to **default ON**.

---

## 8. Implementation steps (mechanical, parallel-safe)

Each step ships as an independent PR. Order matters only for ergonomics
(some steps make others easier to test).

| # | PR | Scope | LoC | Effort |
|---|---|---|---|---|
| **1** | `feat(mobile): contract test scaffolding + 7 wire fixtures` | `tests/test_mobile_pairing_contract.py` + `tests/fixtures/pairing_wire/*.json` + regenerate script + CI workflow | ~400 | 1 day |
| **2** | `feat(mobile): My Paired Devices screen (iOS + Android)` | both `PairingDevicesView.swift` + `PairingDevicesScreen.kt` + ViewModels + tests | ~320 | 2 days |
| **3** | `feat(mobile): Pairing Audit Log screen (iOS + Android)` | `PairingAuditView.swift` + `PairingAuditScreen.kt` + tests | ~280 | 2 days |
| **4** | `feat(mobile): Revoke device confirmation modal (iOS + Android)` | sheets + `PairingClient.revoke()` on both sides + tests | ~220 | 1 day |
| **5** | `feat(host+mobile): BIP-39 recovery re-mint flow (Path B)` | host derivation match + mobile UI + tests | ~340 | 3 days |
| **6** | `feat(host+mobile): APNs+FCM push on new device pair` | `backend/core/pairing/push.py` + iOS + Android registration + tests | ~520 | 4 days |
| **7** | `docs: PH3 mobile pairing brief executed; spec → reality reconciliation` | this brief moves to `docs/SHIPPED/PH3_MOBILE_PAIRING.md`, with per-step "✅ shipped via #PR" marks | ~50 | 0.5 day |
| **Total** | 7 PRs | | **~2,130 LoC** | **~13.5 days** (~2.7 weeks for one implementer) |

Steps 1-4 are **safe to ship without** the brother-side `ph3-pair-ttl`
fix; they only use endpoints that already exist on the host. Steps 5-6
benefit from the relay TTL being in place but don't *require* it (they
gracefully degrade if relay TTL is missing).

---

## 9. Test plan

### Unit tests (per platform)

- iOS: `Tests/TARSCompanionTests/Pairing*Tests.swift` — extend existing
  11 cases to ~25 cases covering revoke, audit, recovery, push
- Android: `app/src/test/java/world/meeet/tars/Pairing*Test.kt` — extend
  existing 4 cases to ~18 cases covering same surface

### Contract tests (cross-platform)

- `tests/test_mobile_pairing_contract.py` (Step 1 deliverable) — 7
  fixtures, asserts byte-for-byte parity Python ↔ Swift ↔ Kotlin

### Integration test (live host)

- `tests/integration/test_mobile_pairing_e2e.py` — spins up actual host,
  drives both flows (§3.2 desktop-initiated, §3.3 mobile-initiated) with
  Python pretending to be each mobile, asserts state transitions match
  the diagram in §3.1

### Manual smoke test (operator wall-clock: ~10 min)

1. Spin up host on `localhost:8000`
2. Install fresh iOS build on iPhone (via TestFlight)
3. Open cockpit, click "Add device" → QR appears
4. Open iPhone app → tap "Pair from QR" → scan
5. Confirm device appears on iPhone Screen A
6. Confirm cockpit Devices list shows iPhone
7. Repeat with Android (Internal Testing build)
8. From iPhone Screen C, revoke Android device
9. Confirm Android app gets a system notification on revoke
10. Confirm cockpit audit log shows the revoke event

**Acceptance:** all 10 steps pass; latency from Step 3 QR scan to Step 5
device-appears-in-list is < 5 seconds.

---

## 10. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Apple bans the app** for requiring deep-link to system settings | low | medium | Use universal links instead of `tars://` scheme; no Apple-private API |
| **FCM rate-limits silent push** in production | medium | low | Push is non-critical (UX nicety); fallback to next-app-open polling |
| **BIP-39 derivation drift** between Python `store.py` and Swift/Kotlin | medium | high | Step 1 contract test asserts byte-for-byte parity; CI fails on drift |
| **`pair_id` TTL not implemented on relay before mobile recovery ships** | high | low | Mobile gracefully degrades — recovery flow works against the host directly without relay TTL; brother item is independent |
| **Operator scans malicious QR** intended for a different host | medium | high | Mobile UI shows host fingerprint *before* completing pair; user can compare against the fingerprint on their desktop |
| **Push notification leaks "iPhone 15 Pro" device names** to Apple/Google servers | low | low | Push payload uses opaque device_id only; device name resolution happens client-side |
| **Cross-platform contract test flakes** under CI runner load | medium | low | Use deterministic fixtures (no network mocking); CI retries 3× on shell-out failure |

---

## 11. Open questions for the operator

1. **Path A vs Path B recovery default**: should v10.2 ship with BIP-39
   recovery (Path B) as the default, or as an opt-in second button?
   Recommend opt-in for v10.2; promote to default in v10.3 after the
   UX flow has telemetry to argue from.
2. **Push notification opt-in or opt-out**: should new-device-paired
   pushes be enabled by default (good security UX) or opt-in (less
   noise for power-users who pair frequently)? Recommend enabled
   by default with a Settings toggle.
3. **Revoke from mobile self-revoke**: should "remove this phone"
   appear in Screen C, allowing a phone to revoke itself? Useful for
   "I sold this phone" workflow. Recommend yes, with a 10-second
   countdown timer and "Cancel" button to prevent fat-finger.
4. **Brother-side TTL implementation timing**: when do we want the
   meeet.world `pair_id` TTL fix? Brother brief (#198) surfaces it as
   `ph3-pair-ttl` v10.2 task; mobile recovery (Step 5) is fully
   functional without it, so no hard dependency.
5. **Mobile audit log retention**: how many entries should
   `GET /api/pairing/audit` return for mobile? Recommend last 50,
   matching desktop (PR #196 §4); add `?since=<iso8601>` query param
   for infinite scroll.
6. **iOS native pull-to-refresh vs notification-driven update**: with
   APNs push, do we even need pull-to-refresh on Screen A? Recommend
   keep both — push is best-effort, pull is always-reliable.

---

## 12. Cross-references

- **PR #196** — desktop pairing/recovery UX (parent v10.1 brief);
  Screens A-C in this brief mirror the desktop panels there.
- **PR #198** — `PH11_BROTHER_HANDOFF_BRIEF.md` §6 — surfaces
  `ph3-pair-ttl` for v10.2 brother slot.
- **PR #208** — iOS companion brief; this brief extends the SwiftUI
  scaffold there with 3 new screens.
- **PR #209** — Android companion brief; same for Compose.
- **PR #210** — native mobile speech brief; uses the same
  cross-platform contract test pattern this brief adopts.
- **`backend/core/pairing/store.py`** — host pairing store (no changes
  needed; brief consumes existing surface).
- **`docs/contracts/L5_PAIRING_DRAFT.md`** — wire contract; brief adds
  no new fields, only documents the existing surface.

---

## 13. Sign-off checklist

When all of these are true, `ph3-mobile-pairing` is clear:

- [ ] Step 1 contract test green on CI (7 fixtures × 3 runtimes)
- [ ] Step 2-4 Screens A/B/C live on iOS + Android Internal Testing
- [ ] Manual smoke test (§9) passes end-to-end on both platforms
- [ ] Step 5 BIP-39 recovery flow tested with real seed → fresh-install
      device → re-pair without desktop interaction
- [ ] Step 6 APNs + FCM push fires on `pending → linked` transition,
      delivered to *other* paired devices within 10 seconds
- [ ] `ph3-pair-ttl` brother-side fix confirmed live OR explicitly
      deferred to v10.3 with operator sign-off
- [ ] This brief moved to `docs/SHIPPED/` with per-step "✅ shipped"
      annotations (Step 7)

---

*Brief authored by the autonomous orchestrator on 2026-05-18 during the
v10.0.0 GA dock-down (W310-z continuation). No code touched in this PR —
pure planning surface for v10.2 mobile pairing closeout. After this lands,
**the only planning-surface gap left in W310 is the Phase 10 Claude
design polish backlog** (continuous, 1-2/week ongoing implementation
work). The W310 wave will then have specified every implementer
question from v10.0.0-rc.1 through v11 on a single planning surface.*
