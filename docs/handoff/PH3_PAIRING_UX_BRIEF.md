# Phase 3 — Cockpit pairing / recovery UX + audit timeline (v10.1)

**Authoring agent:** Cursor agent (Claude Opus 4.7), W310-k
**Authoring date:** 2026-05-18
**Implementer:** TBD (next L5-lane Cursor/Claude session, UI track)
**Target release:** `v10.1.0` (post-GA security polish)
**Depends on:** v10.0.0 GA tag (no hard dep on `ph3-keyring` — orthogonal lane)
**Phase ID in master plan:** `ph3-pairing-ux` (companion to `ph3-keyring`; same v10.1 slot)

---

## 1. Why this brief exists

`v10.0.0-rc.1` ships a **complete L5 pairing + recovery backend** —
10 REST endpoints, full crypto (real X25519 + XChaCha20-Poly1305,
`REAL_CRYPTO_SHIPPED` per W310-a), audit event stream, and a 24-word
BIP-39 recovery seed with 3-of-24 challenge-based identity rotation.
Every endpoint has test coverage in `tests/test_pairing_*.py` /
`tests/test_recovery_*.py`.

**What's missing:** the operator-facing UI. `apps/cockpit/src/pages/
cockpit-entry.ts` is a 12-line stub ("no imperative behaviour yet"),
and `apps/cockpit/cockpit.html` has no panel, modal, or toast for
**any** L5 flow:

- First-launch recovery seed (24 words, shown exactly once)
- "Add device" QR code + status polling
- Paired devices list + per-device revoke
- Pairing + recovery audit timeline
- Host identity rotation (3-of-24 challenge)

Operators today can only drive L5 via curl. Phase 3 UX closes this
gap with **one cockpit panel** (`<aside class="security">` slot in
`cockpit.html`) that owns all 5 flows above, plus optional toast +
modal overlays. Pure frontend work — backend contracts are frozen.

---

## 2. Goals / non-goals

### Goals

| ID | Goal | Acceptance |
| -- | ---- | ---------- |
| G1 | First-launch recovery seed flow with verification gate | Fresh install → cockpit detects `identity.vault.freshly_minted=true` → modal shows 24-word seed once, then requires operator to retype 3 random words before the modal closes |
| G2 | "Add device" pairing flow with QR code | Operator clicks "Add device" → `POST /api/pairing/begin` → QR code rendered (pair_id + host fingerprint + accept_token) → status polls every 2 s until accept/reject/expire |
| G3 | Paired devices list with revoke | Panel section shows all `GET /api/pairing/devices` rows (kind, fingerprint, paired_at, last_seen) → per-row revoke button → confirm modal → `POST /api/pairing/revoke` |
| G4 | Audit timeline | Gold-pill timeline lane renders `GET /api/pairing/audit` (combined `pair.*` + `recovery.*`) — newest first, time-grouped, with kind-color coding |
| G5 | Identity rotation flow | "Rotate host identity" CTA → 3-of-24 challenge wizard (start → answer → verify → rotate) → success toast + identity refresh |
| G6 | Zero new third-party deps | Vanilla TS + Web APIs only (QR via `qrcode-generator` already in tree, or inline canvas) |
| G7 | Accessible (WCAG AA) | All modals trap focus, ESC closes, `aria-live` announces toast/timeline updates, keyboard nav works end-to-end |

### Non-goals

- **New crypto / backend changes.** Backend contracts are frozen at `v10.0.0-rc.1`. This brief is UI-only.
- **Persistent OS keyring.** That's `ph3-keyring` (separate brief, PR #195). Both can land in either order.
- **Mobile companion app UI.** That's `ph3-mobile-pairing` (v10.2). This brief is desktop cockpit only.
- **`pair_id` TTL on `meeet.world` relay.** Brother-coord slot `ph3-pair-ttl` (v10.2). Out of scope here.
- **Disaster recovery automation.** `docs/DISASTER_RECOVERY.md` covers the manual playbook — this brief doesn't change that.
- **Multi-host federation.** L5_PAIRING_DRAFT calls it out as deferred; not in v10.1.

---

## 3. Current state baseline

### Backend (frozen, no changes)

`web_extras/routers/pairing.py` ships 10 endpoints:

| Endpoint | Purpose | Auth |
| -------- | ------- | ---- |
| `POST /api/pairing/begin` | Start pairing — returns `pair_id`, `accept_token`, `host_id`, `host_fingerprint`, `host_public_key`, `expires_at` | Rate-limited |
| `POST /api/pairing/accept/{token}` | Client accepts (mobile / second desktop) | Token-bound |
| `POST /api/pairing/reject/{token}` | Client rejects | Token-bound |
| `GET /api/pairing/status?pair_id=...` | Poll pairing state (`pending` / `accepted` / `rejected` / `expired`) | Open |
| `POST /api/pairing/revoke` | Revoke a paired device | Operator |
| `GET /api/pairing/devices` | List paired devices | Operator |
| `GET /api/pairing/identity` | Host identity + vault state + recovery_fingerprint | Operator |
| `GET /api/pairing/audit?limit=N&since=ts` | Combined `pair.*` + `recovery.*` event feed | Operator |
| `POST /api/pairing/rotate-identity` | Rotate after 3-of-24 challenge | Operator |

Plus `web_extras/routers/vault.py`:

| Endpoint | Purpose |
| -------- | ------- |
| `GET /api/vault/status` | API-key vault key availability |

Plus existing recovery surface (referenced from rotate-identity flow):

| Endpoint | Purpose |
| -------- | ------- |
| `POST /api/recovery/generate` | Generate 24-word seed (first-install only — server enforces idempotency) |
| `POST /api/recovery/challenge/start` | Start 3-of-24 challenge against current seed |
| `POST /api/recovery/challenge/verify` | Submit answer, returns `passed` / `failed` |

### Frontend (this brief's surface)

- `apps/cockpit/cockpit.html` — operator shell. Has `<main class="stage">` (briefing + chat) and `<aside class="gate">` (policy gate). **New slot needed:** `<aside class="security">` for L5 flows.
- `apps/cockpit/src/pages/cockpit-entry.ts` — 12 lines of stub. **New modules needed** (see §4).
- `apps/cockpit/src/styles/global.css` — design tokens. **Additions only**, no overrides.

### Tests (frontend)

- `tests/cockpit/` — vitest unit test suite (created in W309 step 1 PR #187).
- `apps/cockpit/tests/e2e/` — Playwright scaffold (PR #189 draft, scaffolds 7 `test.skip()` scenarios). **This brief adds 6 more scenarios** to that scaffold.

---

## 4. Target architecture

```
apps/cockpit/src/pages/cockpit-entry.ts
  imports:
  └── modules/security/security-panel.ts         NEW · main orchestrator
       ├── modules/security/recovery-modal.ts    NEW · first-launch seed
       ├── modules/security/add-device-modal.ts  NEW · QR + status poll
       ├── modules/security/devices-list.ts      NEW · list + revoke
       ├── modules/security/audit-timeline.ts    NEW · pair.* + recovery.* feed
       ├── modules/security/rotate-wizard.ts     NEW · 3-of-24 + rotate
       └── modules/security/api-client.ts        NEW · fetch wrappers, no logic
```

**Module size budget:** each module ≤ 200 LoC. The orchestrator
`security-panel.ts` is the only one that touches the DOM directly;
the sub-modules render into pre-allocated `<section>` placeholders
and emit `CustomEvent`s back up. Keeps the visual contract auditable.

---

## 5. UX contract (per flow)

### Flow A — First-launch recovery seed

**Trigger:** Cockpit mount → `GET /api/pairing/identity` → if
`vault.freshly_minted === true && recovery_fingerprint === null`,
show the modal.

**Steps:**

1. `POST /api/recovery/generate` → returns `mnemonic: "word1 word2 ..."` (24 words).
2. Modal renders 24 words in a 4x6 grid with copy-to-clipboard.
3. "I've written this down" CTA → switches to verification screen.
4. Verification: server picks 3 random indices (e.g., 5, 12, 19) → modal shows 3 empty inputs labeled `word #5`, `word #12`, `word #19`.
5. Operator fills → submit → client-side check (no server roundtrip; we already have the mnemonic).
6. On match → modal closes, success toast: "Recovery seed secured. Store it somewhere safe."
7. On mismatch → inline error, retry allowed (no lockout — seed is shown again above).

**Failure modes:**

- Operator closes browser before step 6 → on next mount, `identity.vault.freshly_minted === false` (seed was already generated server-side) BUT `recovery_fingerprint !== null` (server bound it on generate). So the modal **doesn't re-show**, but a persistent yellow banner appears: "Recovery seed verification incomplete. [Verify now]" → reopens the verification step (server re-derives, no new seed minted).
- `POST /api/recovery/generate` returns 409 (already generated) → show banner above instead of modal.

### Flow B — Add device (QR pairing)

**Trigger:** "Add device" button on the security panel.

**Steps:**

1. Modal opens with kind selector (`mobile` / `desktop` / `web`). Default: `mobile`.
2. Operator generates ephemeral X25519 client keypair **on-device** (mobile companion app). **Desktop cockpit DOES NOT generate the client_epk** — the QR sent to the device contains the host's part; the device returns its `client_epk` via `accept`. This brief's UI just shows the QR + polls.
3. `POST /api/pairing/begin` with `client_epk: ""` placeholder (mobile sets it via accept) → returns `pair_id`, `accept_token`, `host_fingerprint`, `expires_at`.
4. QR code rendered with payload: `{ pair_id, host_fingerprint, host_public_key, accept_token, kind }` (JSON, base64url).
5. Below QR: text "Scan with TARS Mobile" + countdown timer until `expires_at`.
6. Modal polls `GET /api/pairing/status?pair_id=...` every 2 s.
7. On `state === "accepted"`: success toast, modal closes, devices list refreshes.
8. On `state === "rejected"`: error toast "Device rejected pairing", modal closes.
9. On `state === "expired"`: error toast "Pairing expired (5 min)", modal closes.

**Edge cases:**

- Rate limited (429) → modal shows `Retry-After` countdown, "Try again in Ns" button.
- Network error during poll → silently retry with exponential backoff (max 30 s); show a "Connection lost — retrying" subtitle.

### Flow C — Paired devices list

**Trigger:** Always visible on the security panel after first launch.

**Render:** Sortable table — `kind` icon, fingerprint (truncated to 8 chars, click to copy full), `paired_at` ("3 days ago"), `last_seen` ("12 minutes ago"), revoke button.

**Revoke flow:**

1. Click revoke → confirm modal: "Revoke {kind} ({fingerprint})? This device will lose access immediately."
2. Confirm → `POST /api/pairing/revoke` with `device_id` body.
3. On 200 → table row fades out + removed.
4. On error → toast "Revoke failed: {error}".

### Flow D — Audit timeline

**Trigger:** Always visible on the security panel, below devices list.

**Render:** Vertical timeline, newest first, paginated (load more on scroll). Each entry:

- Time pill (relative: "2 min ago" / "3 hours ago" / "May 17")
- Color-coded kind chip:
  - `pair.attempted` / `pair.accepted` / `pair.rejected` / `pair.revoked` → blue / green / amber / red
  - `pair.host_rotated` → purple
  - `pair.rate_limited` → orange
  - `recovery.generated` / `recovery.challenge.passed` → indigo / teal
  - `recovery.challenge.failed` → orange
- One-line description with key fields: device kind, fingerprint, IP (for `rate_limited`)
- Expand on click → JSON payload pretty-printed

**Polling:** Every 30 s (or trigger refetch on cockpit focus event).
Use `since=ts` for incremental fetches after the initial load.

### Flow E — Rotate host identity

**Trigger:** "Rotate identity" CTA in security panel header.

**Why operator would do this:** Suspected compromise, scheduled key rotation, key-rollover before mobile re-pair.

**Steps (4-screen wizard in modal):**

1. **Warning screen:** "Rotating the host identity will invalidate all currently paired devices. You'll need to re-pair each one." Confirm + Cancel.
2. **Challenge screen:** `POST /api/recovery/challenge/start` → server returns `challenge_id` + 3 word indices. Modal shows 3 input fields.
3. **Verification screen:** operator submits → `POST /api/recovery/challenge/verify` → on `status: failed` show "Wrong word — try again ({attempts_left} left)". On `status: exhausted` → cancel flow with error.
4. **Confirmation screen:** "Identity verified. Proceed with rotation?" Confirm → `POST /api/pairing/rotate-identity` with `challenge_id`.
5. On 200 → success toast: "Host identity rotated. All paired devices have been invalidated." Auto-refetch identity + devices.

**Errors:** Map the 4 `_ROTATE_ERROR_HTTP` codes to inline error states in the wizard (back to step 2 with explanation).

---

## 6. Implementation steps (mechanical)

### Step 1 — API client wrapper + types

**Branch:** `cursor/ph3-pairing-ux-step1-api`
**Files:**
- `apps/cockpit/src/modules/security/api-client.ts` (NEW): thin fetch wrappers for all 10 + 3 endpoints (pairing / recovery / vault). Each returns typed `Result<T, ApiError>`. No JSX, no DOM.
- `apps/cockpit/src/modules/security/types.ts` (NEW): TypeScript interfaces matching backend response shapes.

**Tests:**
- `tests/cockpit/security/api-client.test.ts` (NEW, 14 cases): one happy + one error per endpoint, using `vi.fn()`-mocked `fetch`.

**Acceptance:** Type-check passes; all 14 tests green.

---

### Step 2 — Security panel scaffold + slot

**Branch:** `cursor/ph3-pairing-ux-step2-panel`
**Files:**
- `apps/cockpit/cockpit.html`: add `<aside class="security" aria-labelledby="security-head">` slot next to `<aside class="gate">`. Empty `<section>` placeholders for each sub-module.
- `apps/cockpit/src/styles/global.css`: additive tokens — panel background, timeline colors, modal overlay.
- `apps/cockpit/src/modules/security/security-panel.ts` (NEW, ≤200 LoC): orchestrator that mounts sub-modules into placeholders, subscribes to refresh events.
- `apps/cockpit/src/pages/cockpit-entry.ts`: import + initialize `SecurityPanel`.

**Tests:**
- `tests/cockpit/security/security-panel.test.ts` (NEW, 5 cases): mounts into DOM, lazy-loads sub-modules, dispatches refresh events.

**Acceptance:** Cockpit renders new `<aside class="security">` block with 5 empty placeholders. No regression on existing W309 panes.

---

### Step 3 — Recovery seed modal (Flow A)

**Branch:** `cursor/ph3-pairing-ux-step3-recovery-modal`
**Files:**
- `apps/cockpit/src/modules/security/recovery-modal.ts` (NEW, ≤200 LoC).
- Modal CSS additions (additive to step 2's panel CSS).

**Tests:**
- `tests/cockpit/security/recovery-modal.test.ts` (NEW, 8 cases): freshly-minted shows modal, partial-completion shows banner, verification flow, retry on mismatch, copy-to-clipboard, ESC closes (but only if verification complete), focus trap.
- `apps/cockpit/tests/e2e/recovery-modal.spec.ts` (NEW): full Playwright flow against a stubbed backend with `freshly_minted=true`.

**Acceptance:** All 8 unit tests + 1 Playwright scenario green. WCAG AA spot-check (axe-core).

---

### Step 4 — Add device modal + QR (Flow B)

**Branch:** `cursor/ph3-pairing-ux-step4-add-device`
**Files:**
- `apps/cockpit/src/modules/security/add-device-modal.ts` (NEW, ≤200 LoC).
- QR rendering: prefer existing `qrcode-generator` dep if already in tree; else inline 100-LoC pure-TS QR (BSD-licensed) — **no new npm dep**.

**Tests:**
- `tests/cockpit/security/add-device-modal.test.ts` (NEW, 10 cases): begin happy path, accepted, rejected, expired, rate-limited (with Retry-After), network error → backoff, QR payload shape, focus trap, ESC, kind selector.
- `apps/cockpit/tests/e2e/add-device.spec.ts` (NEW): Playwright full happy-path with backend stub.

**Acceptance:** 10 unit + 1 Playwright scenario green.

---

### Step 5 — Paired devices list + revoke (Flow C)

**Branch:** `cursor/ph3-pairing-ux-step5-devices`
**Files:**
- `apps/cockpit/src/modules/security/devices-list.ts` (NEW, ≤200 LoC).

**Tests:**
- `tests/cockpit/security/devices-list.test.ts` (NEW, 7 cases): empty state, populated render, sort by paired_at, sort by kind, revoke success, revoke failure with toast, fingerprint copy.
- `apps/cockpit/tests/e2e/revoke-device.spec.ts` (NEW): Playwright revoke flow with confirm modal.

**Acceptance:** 7 unit + 1 Playwright scenario green.

---

### Step 6 — Audit timeline (Flow D)

**Branch:** `cursor/ph3-pairing-ux-step6-audit`
**Files:**
- `apps/cockpit/src/modules/security/audit-timeline.ts` (NEW, ≤200 LoC).

**Tests:**
- `tests/cockpit/security/audit-timeline.test.ts` (NEW, 9 cases): initial load, color-coding per kind, time grouping, expand JSON, pagination (load more on scroll), incremental fetch with `since=ts`, refresh on focus, empty state, `aria-live` announces new events.
- `apps/cockpit/tests/e2e/audit-timeline.spec.ts` (NEW): Playwright scenario seeded with mixed `pair.*` + `recovery.*` events.

**Acceptance:** 9 unit + 1 Playwright scenario green.

---

### Step 7 — Rotate identity wizard (Flow E)

**Branch:** `cursor/ph3-pairing-ux-step7-rotate`
**Files:**
- `apps/cockpit/src/modules/security/rotate-wizard.ts` (NEW, ≤200 LoC).

**Tests:**
- `tests/cockpit/security/rotate-wizard.test.ts` (NEW, 11 cases): 4 screens render, warning gate, challenge start, verify pass, verify fail with retry, verify exhausted, rotate success, each `_ROTATE_ERROR_HTTP` code mapped, focus trap, ESC cancels (except mid-rotate).
- `apps/cockpit/tests/e2e/rotate-identity.spec.ts` (NEW): Playwright full 4-screen wizard happy path.

**Acceptance:** 11 unit + 1 Playwright scenario green. Operator can rotate identity end-to-end without leaving the cockpit.

---

## 7. Acceptance criteria (Phase 3 pairing UX done = all of these)

- [ ] Fresh install shows the 24-word recovery seed modal exactly once, with 3-of-24 verification gate
- [ ] Operator can pair a mobile device via QR without touching curl
- [ ] Paired devices list updates within 2 s of accept/revoke
- [ ] Audit timeline shows all `pair.*` + `recovery.*` events with color-coded chips, time-grouped
- [ ] Operator can rotate host identity from cockpit end-to-end (3-of-24 → rotate → identity refresh)
- [ ] All modals trap focus, ESC closes (when safe), `aria-live` announces async results
- [ ] Zero new npm deps
- [ ] All existing W309 panes regression-free (briefing, gate, chat, TTS, vault status)
- [ ] No backend changes (all 13 endpoints frozen)
- [ ] axe-core a11y scan: zero violations on security panel

---

## 8. Test plan summary

| Layer | New tests | Modified tests | Coverage |
| ----- | --------- | -------------- | -------- |
| Unit (api-client) | 14 cases | none | each endpoint happy + error |
| Unit (security-panel) | 5 cases | none | mount + sub-module dispatch |
| Unit (recovery-modal) | 8 cases | none | freshly-minted / partial / verify / retry / copy / a11y |
| Unit (add-device-modal) | 10 cases | none | begin / accept / reject / expire / rate-limit / network / QR / a11y |
| Unit (devices-list) | 7 cases | none | empty / sort / revoke success/fail / fingerprint copy |
| Unit (audit-timeline) | 9 cases | none | load / colors / grouping / expand / pagination / since / focus / empty / a11y |
| Unit (rotate-wizard) | 11 cases | none | 4 screens + 4 error codes + a11y |
| Playwright e2e | 5 scenarios | none | one per flow (A/B/C/D/E) |

**Total:** 64 new unit tests + 5 new Playwright scenarios. 0 modified.

Playwright scenarios slot into the e2e scaffold from PR #189 — those
`test.skip()` markers turn into real tests as each step lands.

---

## 9. Rollback strategy

| Step | Rollback |
| ---- | -------- |
| 1 | Revert PR. No UI consumer yet — safe. |
| 2 | Revert PR. Cockpit loses the empty security panel slot; existing panes unaffected. |
| 3 | Revert PR. First-launch operator falls back to manual `curl POST /api/recovery/generate` (rare path; pre-rc1 baseline). |
| 4 | Revert PR. Operators pair via `phase1-lab` script or curl (pre-rc1 baseline). |
| 5 | Revert PR. Devices list disappears; revoke still works via curl. |
| 6 | Revert PR. Audit log only accessible via `GET /api/pairing/audit` JSON (pre-rc1 baseline). |
| 7 | Revert PR. Rotation still works via curl + 3-of-24 challenge sequence. |

Every step is independently revertable. Backend semantics never change.

---

## 10. Open questions for operator (defaults apply if silent through step 1)

| # | Question | Default if operator silent |
| - | -------- | -------------------------- |
| Q1 | Show recovery seed modal as full-screen overlay or as a side-sheet? | Full-screen overlay — security-critical, deserves the focus |
| Q2 | QR encoding format: JSON-base64url, or compact protobuf? | JSON-base64url — easier to debug in field, mobile companion already parses JSON |
| Q3 | Audit timeline default page size? | 20 events; "load more" reveals 20 more |
| Q4 | Auto-refresh interval for devices + audit? | 30 s — matches the QA Agent cadence; avoids hammering the host |
| Q5 | Should rotate-identity require an additional "type the word ROTATE to confirm" gate beyond the 3-of-24? | No — 3-of-24 + warning screen is enough friction; additional gate is busywork |

---

## 11. Estimated effort

- Step 1 (api-client + types): ~2 h, 1 PR, low risk
- Step 2 (panel scaffold + CSS): ~3 h, 1 PR, low risk (mostly markup)
- Step 3 (recovery modal): ~4 h, 1 PR, medium risk (security-critical UX)
- Step 4 (add-device + QR): ~5 h, 1 PR, medium risk (QR + polling state machine)
- Step 5 (devices list): ~3 h, 1 PR, low risk
- Step 6 (audit timeline): ~4 h, 1 PR, low risk (rendering-only)
- Step 7 (rotate wizard): ~5 h, 1 PR, medium risk (4-screen state machine + error mapping)

**Total:** ~26 h, 7 PRs, distributable across 1-1.5 weeks at
one-step-per-day cadence.

Comparable to `ph3-keyring` (~23 h, 6 PRs). Together the two L5
closeout briefs land in ~50 h, ~13 PRs — that's the entire v10.1
Phase 3 surface.

---

## 12. Pointers / references

- Backend canonical: `web_extras/routers/pairing.py` (10 endpoints), `web_extras/routers/vault.py` (1 endpoint), `web_extras/routers/recovery.py` (3 endpoints — invoked from rotate-wizard)
- Pairing store: `backend/core/pairing/store.py` (PairingStore, PairingRecord, PairedDevice)
- L5 crypto canon: `backend/core/crypto/envelope.py`, `backend/core/crypto/recovery.py`
- Contract spec: `docs/contracts/L5_PAIRING_DRAFT.md` (status: SHIPPED v1 host-only)
- Disaster recovery playbook (not changed by this brief): `docs/DISASTER_RECOVERY.md`
- Cockpit shell baseline (W309 step 1): `apps/cockpit/cockpit.html`, `apps/cockpit/src/pages/cockpit-entry.ts`
- E2E scaffold to extend: PR #189 (`cursor/w309-step2-e2e-prep`)
- Companion brief: `docs/handoff/PH3_KEYRING_BRIEF.md` (PR #195) — backend-only
- Master plan slot: `docs/PRODUCT_MASTER_PLAN.md` — Phase 3 (`ph3-pairing-ux`)
- Wave summary: `docs/W310_WAVE_SUMMARY.md` (will be extended with W310-k)

---

**End of brief.**
