# Phase 4 (L9 close) — Updater channel bootstrap brief

**Status:** PLANNING-SURFACE — dock-down for backend bootstrap + small frontend implementation
**Owner (planning):** assistant
**Owner (execution):** alien (operator: key push + first tag) + implementer agent (cockpit UI hook)
**Target release:** v10.0.0 GA (key push) + v10.1 (frontend UI surface)
**Estimated effort:** ~30 min operator (T0 alongside Apple sign) + ~4 hours implementer (cockpit UI)
**Depends on:**
- Apple sign brief #199 must complete first (`.dmg` must be properly notarized before updater can ship a signed update)
- `desktop/scripts/generate-release-keys.sh` already exists (146 LoC, complete)
**Risk surface:** Minisign key loss = no future auto-updates possible until UI prompt for manual reinstall ships; first-release-to-release auto-update never tested end-to-end.

---

## 1. Motivation

The Tauri updater channel is **half-wired** today:

| Layer | Status |
|---|---|
| Rust dep `tauri-plugin-updater = "2.0"` in `Cargo.toml` | ✅ shipped |
| Updater config in `tauri.conf.json` (active, endpoint, pubkey) | ✅ shipped — pubkey is REAL (`1B29F3A6…`) |
| CI `latest.json` publishing via `includeUpdaterJson: true` | ✅ shipped, gracefully degrades when secret absent |
| Local key-mint script `desktop/scripts/generate-release-keys.sh` (146 LoC) | ✅ shipped W253 |
| Local pubkey-status check `desktop/scripts/updater-pubkey-status.sh` (23 LoC) | ✅ shipped |
| GH secrets `TAURI_SIGNING_PRIVATE_KEY` + `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | ⚠️ never pushed |
| Frontend `checkForUpdate()` call in cockpit | ❌ NOT WIRED |
| First-release-to-release auto-update smoke-tested | ❌ NEVER |

The "REAL minisign pubkey" commit (`f79ec2b`) pinned a valid pubkey to
`tauri.conf.json`, but the matching **private** key was never pushed to
GitHub Secrets, so every release ships **without** the `latest.json`
channel manifest. Updater code runs on every TARS launch, fails to find
`latest.json`, silently no-ops. Users never see an "update available"
prompt because there is no UI plumbing for it either.

**Net effect:** every TARS update today requires the user to re-download
the `.dmg`, replace `/Applications/TARS.app`, and re-launch — which is
exactly the experience the updater was built to eliminate.

---

## 2. Goals / non-goals

### Goals

- **G1.** GitHub Secrets `TAURI_SIGNING_PRIVATE_KEY` + `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`
  are pushed once before v10.0.0 tag cut.
- **G2.** v10.0.0 tag-cut release publishes `latest.json` with valid
  minisign signature inside (Tauri 2.x embedded format).
- **G3.** A cockpit "Check for updates" UI surface exists by v10.1 and
  triggers Tauri's `check()` + `downloadAndInstall()` plugin APIs.
- **G4.** First real auto-update path (v10.0.0 → v10.0.1) is smoke-tested
  end-to-end on a clean Mac, with rollback-to-manual-install fallback if
  the updater fails.
- **G5.** Pubkey rotation is mechanically possible (private key
  compromise scenario) without losing the user base — covered by
  documented runbook.

### Non-goals (explicit)

- **N1.** Differential update binaries (Tauri 2.x doesn't support; full
  `.app.tar.gz` re-download is acceptable at our size).
- **N2.** Delta cohort rollout via `latest.json` `pub_date` filtering
  (deferred to v11; v10.x ships full-population rollouts).
- **N3.** Code-signing the `latest.json` HTTPS endpoint with a separate
  cert (Tauri 2.x trusts the minisign signature embedded in the JSON
  itself; HTTPS provides transport security only).
- **N4.** In-app rollback to a previous version (Tauri updater is
  forward-only; users on broken release re-download last good `.dmg`
  manually).
- **N5.** Update notifications via push (no server-side push channel;
  cockpit polls `latest.json` on launch + on user demand).
- **N6.** Windows / Linux updater bootstrap (same minisign key works
  cross-platform; coverage extends naturally when those platforms ship
  signed installers — see `PH4_WINDOWS_SIGN_BRIEF.md`).

---

## 3. Pre-flight (5 min operator)

```bash
cd ~/Documents/Claude/Projects/Jarvis/jarvis

# 3.1 Confirm pubkey in tauri.conf is REAL (not TODO_PUBLIC_KEY placeholder)
bash desktop/scripts/updater-pubkey-status.sh
# Expected: "updater_pubkey: patched (minisign pubkey present)"
# FAIL: "TODO_PUBLIC_KEY" → operator hasn't run generate-release-keys.sh,
#                          STOP — do that first

# 3.2 Confirm matching private key lives at expected path
test -f ~/.tars-release-keys/tars-desktop.key && echo "✓ private key present" \
  || echo "✗ private key missing — re-mint via generate-release-keys.sh"

# 3.3 Confirm tauri-plugin-updater is in Cargo.toml at version 2.0
grep "tauri-plugin-updater" desktop/src-tauri/Cargo.toml
# Expected: tauri-plugin-updater = "2.0"
```

If any check fails → see `desktop/scripts/generate-release-keys.sh` and
re-mint. The mint script is idempotent for the operator — only the FIRST
mint matters for users (rotation later requires UI prompt — see §6).

---

## 4. Bootstrap (one-time, T0 — alongside Apple sign)

### 4.1 Push 2 secrets

```bash
# private key (base64-wrapped)
base64 < ~/.tars-release-keys/tars-desktop.key \
  | gh secret set TAURI_SIGNING_PRIVATE_KEY \
      --repo alxvasilevvv/tars-neural-cockpit

# passphrase (interactive prompt)
gh secret set TAURI_SIGNING_PRIVATE_KEY_PASSWORD \
  --repo alxvasilevvv/tars-neural-cockpit
# Paste the passphrase chosen during generate-release-keys.sh
```

### 4.2 Manual workflow dispatch dry-run (same as Apple sign §4)

`Actions → release-desktop → Run workflow → main`

Wait ~12 min for the macos-arm64 build. Verify in the log:

- ✅ `Tauri updater signing: enabled (private key found)` (line emitted by tauri-action)
- ✅ `Bundling updater artifacts: TARS.app.tar.gz + TARS.app.tar.gz.sig`
- ✅ Final upload step lists `latest.json` as one of the published assets

If `latest.json` is missing from the published assets → the secret round-trip
failed. Re-add, re-dispatch. **Do NOT tag.**

### 4.3 Tag cut (couples to `scripts/RELEASE-v10.0.command`)

After dry-run confirms `latest.json` is produced, the live tag cut for
v10.0.0 will publish a valid signed channel manifest as a side effect. No
separate operator action.

---

## 5. Frontend UI surface (v10.1 — ~4h implementer)

### 5.1 Why this is a separate ticket

The bootstrap (§4) ships the signed `latest.json` to GitHub, but **no TARS
user will ever see an update prompt** because the cockpit doesn't call the
updater API. v10.0.0 GA can ship without this — `latest.json` accumulates
on each release, ready to serve once the frontend lights up. v10.1 wires
the UI.

### 5.2 Target architecture

```
apps/cockpit/src/modules/updater/
├── updater-button.ts          (~60 LoC) — toolbar button "Check for updates"
├── updater-modal.ts           (~120 LoC) — modal with status, download progress, install button
└── updater-client.ts          (~80 LoC) — wraps @tauri-apps/plugin-updater
```

Slot in `apps/cockpit/cockpit.html`:

```html
<button id="updater-button" class="toolbar-button" hidden aria-label="Check for updates">
  ⬆ <span data-i18n="updater.check">Check for updates</span>
</button>
```

`hidden` by default — `updater-button.ts` removes the attribute on mount
when running inside Tauri (detected via `window.__TAURI__`). Vanilla web
serving (e.g. `tars.meeet.world`) keeps the button hidden so the web cockpit
doesn't pretend to update itself.

### 5.3 Client wrapper contract (`updater-client.ts`)

```typescript
import { check, type Update } from '@tauri-apps/plugin-updater'

export type UpdaterState =
  | { kind: 'idle' }
  | { kind: 'checking' }
  | { kind: 'available'; update: Update }
  | { kind: 'downloading'; progress: number }  // 0..1
  | { kind: 'installing' }
  | { kind: 'ready_to_restart' }
  | { kind: 'no_update'; current: string }
  | { kind: 'error'; message: string }

export async function checkForUpdate(): Promise<UpdaterState> { /* … */ }
export async function downloadAndInstall(
  update: Update,
  onProgress: (p: number) => void
): Promise<UpdaterState> { /* … */ }
```

### 5.4 Modal states

| State | UI shape |
|---|---|
| `idle` | Hidden |
| `checking` | "Checking for updates…" + spinner |
| `available` | "TARS x.y.z is available. Notes:\n[changelog excerpt]\n[Download & Install] [Skip]" |
| `downloading` | Progress bar 0..100% + "Downloading TARS x.y.z…" |
| `installing` | "Installing… do not close TARS" + spinner |
| `ready_to_restart` | "Update installed. [Restart now] [Restart later]" |
| `no_update` | "TARS x.y.z is up to date." (auto-dismiss after 2s) |
| `error` | "Update failed: [message]. [Try again] [Download manually]" with link to GH Releases |

### 5.5 Auto-check policy

- On TARS launch: silent `check()` after 10s delay (avoids competing with
  cockpit boot). If `available` AND last-prompted version is different from
  current available, surface a small toolbar dot indicator (no modal).
- User-initiated: clicking `Check for updates` button always shows the
  modal (even if `no_update`).
- Throttle: at most one `check()` per hour (cached in localStorage as
  `tars:updater:last_check_at`).

---

## 6. Pubkey rotation runbook (defensive — no implementation in v10)

Scenario: private key leaks, OR operator rotates as preventive hygiene.

The current public key is hard-coded in `tauri.conf.json`. To rotate:

1. Mint a new keypair: `bash desktop/scripts/generate-release-keys.sh`
2. Update `tauri.conf.json` pubkey field, commit, push.
3. Replace `TAURI_SIGNING_PRIVATE_KEY` + `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` secrets in GH.
4. Tag a new release.

**Problem:** users on the OLD key cannot verify the new `latest.json`
(`pubkey` mismatch). The updater will silently fail. Users won't auto-update
to anything ever again on the broken key.

**Mitigation for v10.x:** the runbook is **documentation-only** until the
cockpit UI surface §5 ships. With UI:
- Add explicit pubkey-rotation flow that shows "TARS needs a manual update
  to continue receiving auto-updates" modal with download link to
  GH Releases.
- Triggered by `check()` returning an error with substring "invalid
  signature" → updater client recognizes this as the rotation case.

**Mitigation for v11:** publish a `keys-history.json` alongside `latest.json`
that lists current + previous N pubkeys. Updater accepts any signature
matching any pubkey in the history file (signature on each pubkey by the
current key, chain of trust). This is real cryptographic infrastructure —
out of scope for v10.x.

For v10.0.0 GA: **mint the key once, don't rotate.** Treat the private key
as a "do not lose" asset (separate Phase 5 vault work eventually owns this).

---

## 7. Implementation steps (3 mechanical, 2 PRs)

### Step 1 — Operator bootstrap (T0, 30 min, no PR)

- Run §3 pre-flight checks
- Push 2 secrets (§4.1)
- Manual workflow dispatch dry-run (§4.2)
- (no commit — secrets-only operation)

### Step 2 — Cockpit updater UI (v10.1, ~4h, 1 PR)

- New module `apps/cockpit/src/modules/updater/` (3 files, ~260 LoC)
- Slot in `cockpit.html`
- Import + initialize in `apps/cockpit/src/pages/cockpit-entry.ts`
- Vitest unit tests for `updater-client.ts` state machine (~8 cases, ~120 LoC)
- Playwright scenario in `apps/cockpit/tests/e2e/updater.spec.ts` mocking
  Tauri's `__TAURI__` global (~80 LoC)

**Files touched:**
- New: 3 module files + 1 test file + 1 playwright spec
- Modified: `cockpit.html` (+3 lines), `cockpit-entry.ts` (+3 lines)
- Total: ~470 LoC

### Step 3 — Pubkey rotation runbook (v10.1, ~1h, 1 PR)

- New doc `docs/UPDATER_KEY_ROTATION.md` (~120 LoC)
- Operator scenarios + UI mitigation references
- Doc-only

---

## 8. Effort summary

| Step | Implementer hours | Operator hours | LoC |
|---|---|---|---|
| 1. Bootstrap secrets | 0 | 0.5 | 0 |
| 2. Cockpit UI | 4.0 | 0 | 470 |
| 3. Rotation runbook | 1.0 | 0 | 120 |
| **Total** | **5.0** | **0.5** | **590** |

---

## 9. Test plan

### Unit (new, ~120 LoC)

- `updater-client.test.ts`: 8 state-machine transition cases (idle→checking→available→downloading→ready→idle, error paths)

### Playwright (new, ~80 LoC)

- `apps/cockpit/tests/e2e/updater.spec.ts`: 3 scenarios using mocked `window.__TAURI__`:
  1. `Check for updates` button hidden when not in Tauri
  2. Manual check → "no update" path → modal auto-dismiss
  3. Manual check → "available" path → download progress → restart prompt

### CI smoke (no real cert)

- §4.2 manual dispatch on a branch without secrets → CI logs "Tauri updater signing: skipped (private key not provided)" and produces release without `latest.json`. **Current behaviour preserved.**

### Real auto-update validation (operator, v10.0.0 → v10.0.1 path)

1. Install v10.0.0 `.dmg` on clean Mac.
2. Launch, observe no update prompt (latest = current).
3. Operator cuts v10.0.1 tag with trivial change.
4. Wait ~15 min for release-desktop CI.
5. On same Mac: relaunch TARS, wait 10s.
6. **PASS:** Toolbar dot indicator appears, clicking opens modal with v10.0.1 changelog.
7. Click `Download & Install` → progress bar 0→100% → `Restart now`.
8. TARS relaunches as v10.0.1. Verify version string in About modal.

---

## 10. Open questions (4)

1. **Q1.** Should v10.0.0 GA push the bootstrap secrets even though
   no UI exists yet, OR defer to v10.1?
   _Lean: **push at GA**. Cost is zero, and accumulating signed
   `latest.json` for v10.0.0, v10.0.1, v10.0.2 etc. means when the UI
   ships in v10.1, users who upgrade to v10.1 immediately see auto-update
   for v10.1.1+. Skipping bootstrap means the first auto-update opportunity
   is v10.1→v10.2, several months later._

2. **Q2.** "Skip this version" persistence: store in localStorage or in
   backend settings DB?
   _Lean: localStorage. Cockpit is local-first; backend DB sync is
   overhead. Per-machine skip is fine UX._

3. **Q3.** Should the modal block cockpit interaction (modal-dialog), or
   be inline (drawer)?
   _Lean: modal-dialog for `available` (forces decision), inline drawer for
   `downloading`/`installing` (doesn't block work in flight)._

4. **Q4.** What error states warrant the "fall back to manual download"
   link prominently?
   _Lean: all `error` states. The link is always cheap to render; users
   can ignore it if the inline `Try again` works. Reduces support load._

---

## 11. Coupling to v10 GA arc

| Phase | What happens |
|---|---|
| T-7d | Operator confirms minisign keys are present (`updater-pubkey-status.sh`) |
| T0 | §4 bootstrap (30 min) runs alongside Apple sign push |
| T0+15min | First `latest.json` published as side-effect of v10.0.0 tag cut |
| T+72h | Soak (per `PH11_QA_SWEEP_BRIEF.md`) NOT testing updater UI (it doesn't exist yet) |
| v10.1 | Implementer ships §5 cockpit UI + §6 rotation runbook |
| v10.1.1 | First real auto-update path tested end-to-end (§9 manual validation) |

**Critical:** bootstrap (§4) is a **GA-time prerequisite** (cost: 30 min,
risk: zero, payoff: enables future auto-update for the entire v10.x line).
Frontend UI (§5) is **NOT** a GA blocker — it ships v10.1.

---

## 12. Files touched (summary)

**New (5 files for v10.1):**
- `docs/handoff/PH4_UPDATER_BOOTSTRAP_BRIEF.md` (this file)
- `apps/cockpit/src/modules/updater/updater-button.ts`
- `apps/cockpit/src/modules/updater/updater-modal.ts`
- `apps/cockpit/src/modules/updater/updater-client.ts`
- `apps/cockpit/tests/unit/updater-client.test.ts`
- `apps/cockpit/tests/e2e/updater.spec.ts`
- `docs/UPDATER_KEY_ROTATION.md`

**Modified (2 files for v10.1):**
- `apps/cockpit/cockpit.html` (+3 lines)
- `apps/cockpit/src/pages/cockpit-entry.ts` (+3 lines)

**v10.0.0 GA: zero code changes.** Bootstrap is secrets-push only.

---

## 13. References

- `desktop/src-tauri/tauri.conf.json` — updater config (active, pubkey, endpoint)
- `desktop/src-tauri/Cargo.toml` — `tauri-plugin-updater = "2.0"` already wired
- `desktop/scripts/generate-release-keys.sh` (146 LoC) — key mint
- `desktop/scripts/updater-pubkey-status.sh` (23 LoC) — pubkey health check
- `.github/workflows/release-desktop-tagged.yml` — CI `includeUpdaterJson` config
- `docs/SYSTEM_AUDIT_2026-05-03.md` — original updater shipping audit
- `docs/security/AUDIT_2026-05-09.md` — pubkey provenance audit
- `docs/handoff/PH4_APPLE_SIGN_V10_BRIEF.md` — sister brief (PR #199), bootstrap runs T0 alongside
- `docs/handoff/PH4_WINDOWS_SIGN_BRIEF.md` — sister brief (PR #200), Windows updater path extends naturally

---

*Brief authored as part of the W310 wave (sub-wave `W310-p`). Companion
briefs: `PH4_APPLE_SIGN_V10_BRIEF.md` (PR #199), `PH4_WINDOWS_SIGN_BRIEF.md` (PR #200).
Closes the Phase 4 / L9 release-signing planning surface.*
