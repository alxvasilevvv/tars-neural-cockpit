# Phase 4 (L9 close) — Apple `.dmg` v10 sign dock-down

**Status:** PLANNING-SURFACE — operator unblock + verification brief
**Owner (planning):** assistant
**Owner (execution):** alien (operator) + Cursor session on Andrey's Mac (per
existing `APPLE_SIGNING_FOR_CURSOR.md` handoff)
**Target release:** v10.0.0 GA (drops `-rc.1`)
**Estimated effort:** 30–45 min wall-clock on the day the `.p12` lands
**Depends on:** none (all code/CI/docs already shipped — this is verification-only)
**Risk surface:** Apple Developer portal latency, GH Secrets typo, Notary
service throttling. All recoverable inside 1 retry.

---

## 1. Why this brief (and what it is NOT)

### What's already done

Apple signing is fully scaffolded on `main` as of `v10.0.0-rc.1`:

| Layer | Artifact | Status |
|---|---|---|
| Local pipeline | `scripts/SIGN-AND-NOTARIZE.command` (231 LoC) | ✅ shipped W250 |
| One-time setup runbook | `docs/APPLE_SIGNING_SETUP.md` (341 LoC) | ✅ shipped W250 |
| Quick reference | `docs/APPLE_SIGNING_NEXT_TIME.md` (226 LoC) | ✅ shipped W253 |
| CI workflow | `.github/workflows/release-desktop-tagged.yml` | ✅ accepts 6 Apple secrets, graceful degrade |
| Tauri bundle config | `desktop/src-tauri/tauri.conf.json` | ✅ `dmg`+`app` targets, macOS section |
| Entitlements plist | `desktop/src-tauri/entitlements.plist` | ✅ shipped W250 |
| Per-Cursor handoff | `docs/handoff/APPLE_SIGNING_FOR_CURSOR.md` (v9.1.0 vintage) | ⚠️ outdated tag references |

What's NOT done: the `.p12` certificate has never been pushed to GitHub
Secrets, so every release built so far has used the ad-hoc codesign fallback
(usable but triggers Gatekeeper warning).

### What this brief is

A **v10-targeted dock-down** that:

1. Patches the v9.1.0 quirks in `APPLE_SIGNING_FOR_CURSOR.md` (obsolete
   `INSTALLERS_READY` flip, wrong tag).
2. Adds **verification gates** that did not exist in the v9.1.0 path:
   `spctl --assess`, `codesign --verify --deep --strict`, `stapler validate`,
   ad-hoc-vs-real signature diff.
3. Couples the flow to `scripts/RELEASE-v10.0.command` (the GA tag-cut script)
   so signing is observed live during release, not after.
4. Defines a **rollback gate** so a broken `.p12` cannot brick the GA cut.

### What this brief is NOT

- ❌ Not a re-write of the one-time portal setup (that's `APPLE_SIGNING_SETUP.md`).
- ❌ Not a new GitHub Secrets list (same 6 secrets as v9.1.0).
- ❌ Not the Windows or updater story (separate briefs `PH4_WINDOWS_SIGN_BRIEF.md` and `PH4_UPDATER_BOOTSTRAP_BRIEF.md`).
- ❌ Not the operator portal CSR / cert request (also already documented).

---

## 2. Goals / non-goals

### Goals

- **G1.** A signed + notarized + stapled `TARS_10.0.0_aarch64.dmg` is the
  artifact GitHub Releases serves at GA tag.
- **G2.** The same artifact passes `spctl --assess --type execute` on a
  factory-clean Mac (no developer toolchain, no keychain entries).
- **G3.** `gatekeeper-bypass` warnings are zero in
  `console.app` when launching the installed `.app` on a fresh user account.
- **G4.** If any sign step fails, the operator stops at a clear rollback gate
  and can decide whether to ship ad-hoc-signed (acceptable but visible
  Gatekeeper banner) or block the GA cut entirely.
- **G5.** Operator round-trip ≤ 45 min from `.p12` in clipboard to live
  Release artifact verified.

### Non-goals (explicit)

- **N1.** Apple Distribution / App Store signing (we ship outside MAS).
- **N2.** TestFlight or beta channel signing (no separate cert needed).
- **N3.** macOS Catalina (< 10.15) hardened-runtime quirks (we require 12.0+
  per `tauri.conf.json: macOS.minimumSystemVersion`).
- **N4.** Intel-only Mac runners on GitHub Actions (`macos-13` is
  `continue-on-error: true` in the matrix — Apple Silicon `.dmg` runs under
  Rosetta on Intel users, redirect handled by dl-proxy).
- **N5.** Self-signed cert as a "good enough" fallback (Gatekeeper rejects).
- **N6.** Renewing the cert (separate 5-year-out concern, deferred to runbook
  task in `APPLE_SIGNING_SETUP.md` §10).

---

## 3. Pre-flight (operator owns; 5 min)

Run **before** the `.p12` export starts. All read-only.

```bash
cd ~/Documents/Claude/Projects/Jarvis/jarvis

# 3.1 Confirm Apple Developer cert is in keychain
security find-identity -v -p codesigning | grep "Developer ID Application"
# Expected: 1 line, e.g.
#   1) ABCDEF... "Developer ID Application: CSA PROJECT - FZCO (ZGR2C33ZLZ)"

# 3.2 Confirm notarytool credentials profile is stored
xcrun notarytool history --keychain-profile "${APPLE_NOTARY_PROFILE:-tars-notary}" 2>&1 \
  | head -3
# Expected: "Successfully received submission history." (even if empty)

# 3.3 Confirm local SIGN-AND-NOTARIZE.command can read .env
test -f .env && grep -c "^APPLE_" .env
# Expected: 3 (TEAM_ID, DEVELOPER_ID_APPLICATION, NOTARY_PROFILE)
```

If any of 3.1/3.2/3.3 fails → follow `docs/APPLE_SIGNING_SETUP.md` to
re-provision. Do not proceed.

---

## 4. CI secrets push (10 min, owner clicks)

Per `APPLE_SIGNING_FOR_CURSOR.md` steps 4–6 — **unchanged**.

Push exactly 6 secrets to <https://github.com/alxvasilevvv/tars-neural-cockpit/settings/secrets/actions>:

```
APPLE_CERTIFICATE              base64 of .p12 (Step 4 output)
APPLE_CERTIFICATE_PASSWORD     P12_PASS from Step 4
APPLE_SIGNING_IDENTITY         e.g. "Developer ID Application: CSA PROJECT - FZCO (ZGR2C33ZLZ)"
APPLE_TEAM_ID                  ZGR2C33ZLZ
APPLE_ID                       Apple Developer login email
APPLE_PASSWORD                 app-specific password (from appleid.apple.com)
```

**New for v10:** before tagging, dry-run that CI sees all 6 by running
`Actions → release-desktop → Run workflow` with manual dispatch (the
workflow has `workflow_dispatch:` enabled). Pick branch `main`, no inputs.
Look at the "Set up build environment" step — it should log
`APPLE_CERTIFICATE: ***` (masked) for every secret. **If any secret missing,
re-add and re-dispatch BEFORE tagging.** Catching a typo at this stage
avoids a doomed tag cut.

---

## 5. Tag cut + sign observation (15 min)

### 5.1 Coupling to `scripts/RELEASE-v10.0.command`

The GA tag-cut script (per `PH11_QA_SWEEP_BRIEF.md`) runs in this order:

1. `scripts/FINAL-QA-GATE.command` (8 gates, all green)
2. Bump version `10.0.0-rc.1` → `10.0.0` in `desktop/src-tauri/tauri.conf.json`
   and `pyproject.toml`
3. Commit + tag `v10.0.0`
4. `git push origin v10.0.0`
5. Wait for `release-desktop` workflow (~12–15 min on Apple Silicon)
6. Verify `latest.json` + `.dmg` attached to GH Release
7. `INSTALL.command` smoke test against the GH Release artifact

Apple sign hooks at step 5: the workflow's `tauri-action` step calls
`apple/codesign-and-notarize` internally when all 6 secrets are present.

### 5.2 Observe the sign step in CI

While the workflow runs, watch the `Build - macOS-arm64` job. Key
substring matches in the log:

- ✅ `Imported APPLE_CERTIFICATE successfully` — secret round-trip OK
- ✅ `signing identity 'Developer ID Application: CSA PROJECT - FZCO …'` — cert resolved
- ✅ `notarytool submit … status: Accepted` — Apple notary green
- ✅ `Stapled ticket to … TARS_10.0.0_aarch64.dmg` — ticket attached

If the log instead shows:

- ⚠️ `falling back to ad-hoc codesigning` → at least one secret is missing
  or malformed. **STOP — do not consume the tag.** Run the rollback in §7.

---

## 6. Post-release verification (10 min on a clean machine)

The fastest definitive test: a Mac with no Xcode, no developer keychain,
no admin override.

```bash
# 6.1 Download from GH Release (factory-clean machine, fresh user account)
curl -L -o ~/Downloads/TARS_10.0.0_aarch64.dmg \
  https://github.com/alxvasilevvv/tars-neural-cockpit/releases/download/v10.0.0/TARS_10.0.0_aarch64.dmg

# 6.2 Static checks (no install needed)
codesign --verify --deep --strict --verbose=2 \
  /Volumes/TARS/TARS.app 2>&1 | grep -E "valid on disk|satisfies"
# Expected: "valid on disk" + "satisfies its Designated Requirement"

spctl --assess --type execute --verbose /Volumes/TARS/TARS.app 2>&1
# Expected: "accepted" + "source=Notarized Developer ID"
# FAIL signal: "rejected" → block GA cut, rollback

stapler validate /Volumes/TARS/TARS.app 2>&1
# Expected: "The validate action worked!"

# 6.3 Drag-install + first-launch (manual, observed)
# - Drag TARS to /Applications
# - Double-click /Applications/TARS.app
# - MUST launch cleanly with NO "unidentified developer" modal
# - Console.app filter "TARS" — should show ZERO gatekeeper-bypass warnings
```

### 6.4 Soak verification (couples to PH11 brief)

The first hour of the v10.0.0 72h soak (per `PH11_QA_SWEEP_BRIEF.md` §4)
runs against the **installed signed `.app`**, not the dev build. If
sign-related anomalies (sandbox denials, keychain prompts on every launch,
TCC privacy resets) surface in the soak, that's a sign defect — block the
release, do not "let it ride" 72h.

---

## 7. Rollback gates

Three explicit checkpoints where the operator MUST stop and choose:

### Gate A — pre-tag (workflow dispatch failed sign step)

**Symptom:** §4 manual dispatch logs `falling back to ad-hoc codesigning`.
**Action:** Re-export `.p12`, re-add secret(s), re-dispatch. **Do NOT tag.**
**Time cost:** +15 min, no production impact.

### Gate B — post-tag, pre-publish (CI sign green, but verify red)

**Symptom:** `spctl --assess` shows `rejected` on the downloaded `.dmg`.
**Action:**
1. `git push --delete origin v10.0.0` (delete the tag).
2. `git tag -d v10.0.0` (local).
3. Mark the GH Release as **Draft** (do not delete — keep audit trail).
4. Diagnose: most common is Notary returning `Accepted` but staple failing
   (then `spctl` is in offline mode and reports `unsigned`). Re-staple via
   `xcrun stapler staple TARS.app` then re-zip. If that does not work,
   re-cut tag as `v10.0.0` after the fix lands on `main`.
**Time cost:** +30–60 min, no production impact (tag was never live).

### Gate C — post-publish, post-verify (works on Apple Silicon, broken on Intel)

**Symptom:** `macos-13` (Intel) job timed-out or built unsigned variant.
**Action:** This is expected at low frequency per the workflow header
comment. The arm64 `.dmg` runs under Rosetta on Intel macOS — dl-proxy
already redirects `/dl/TARS-x86_64.dmg` → `/dl/TARS-aarch64.dmg`. **Do not
re-cut tag.** File issue for v10.0.1 to fix the Intel matrix.
**Time cost:** zero (defer to dot-release).

### Gate D — `.p12` corrupted / cert expired

**Symptom:** §4 manual dispatch logs `import-cert: pkcs12 password
incorrect` or `Identity not found in keychain`.
**Action:** Stop the v10 sign work. Operator follows
`docs/APPLE_SIGNING_SETUP.md` §6 to re-export a fresh `.p12`. Cert renewal
follows §10.
**Time cost:** +20 min, no production impact.

---

## 8. Files this brief touches

**Read (verify these exist + correct paths):**
- `scripts/SIGN-AND-NOTARIZE.command`
- `scripts/RELEASE-v10.0.command`
- `scripts/FINAL-QA-GATE.command`
- `desktop/src-tauri/tauri.conf.json`
- `desktop/src-tauri/entitlements.plist`
- `.github/workflows/release-desktop-tagged.yml`
- `docs/APPLE_SIGNING_SETUP.md`
- `docs/APPLE_SIGNING_NEXT_TIME.md`
- `docs/handoff/APPLE_SIGNING_FOR_CURSOR.md`

**Write (only this brief — zero net-new code):**
- `docs/handoff/PH4_APPLE_SIGN_V10_BRIEF.md` (this file)

**No code changes proposed.** The pipeline is mechanically complete; this
brief gates execution.

---

## 9. Test plan

Apple sign verification is the test. There is no unit-test layer that
exercises real Notary. The brief contributes 3 verification scripts the
operator runs by hand (§6) and 4 rollback gates (§7). No new pytest /
playwright cases.

---

## 10. Open questions (5)

1. **Q1.** Should `scripts/RELEASE-v10.0.command` automatically run the §6
   verification block on the downloaded artifact, or keep it operator-eyes?
   _Lean: add as an optional step gated by `--verify-sign` flag, default
   off. Adds 90 s but reduces "shipped and didn't notice the warning" risk._

2. **Q2.** Should `APPLE_SIGNING_FOR_CURSOR.md` be **deleted** (superseded
   by this brief + `APPLE_SIGNING_SETUP.md`) or kept as historical handoff?
   _Lean: keep, mark `> SUPERSEDED by PH4_APPLE_SIGN_V10_BRIEF.md` at top._

3. **Q3.** If the Intel `macos-13` runner is reliably queue-starved in 2026,
   should we **drop** that matrix entry entirely and ship arm64-only?
   _Lean: yes for v10.1, keep for v10.0 (already `continue-on-error`)._

4. **Q4.** Should we add a CI step that runs `spctl --assess` against the
   built `.dmg` **before** publishing to Release, as a hard gate?
   _Lean: yes. Add to `release-desktop` workflow as `verify-sign` step that
   fails the job if `rejected`. Separate PR — folded into PH11 prep._

5. **Q5.** Cert expires in ~5 years. Should this brief link to a calendar
   reminder file (`docs/runbook/CERT_RENEWAL_2031.md`)?
   _Lean: out of scope. Folded into v10.0.x docs pass._

---

## 11. Effort summary

- **Operator wall-clock:** 30–45 min on the day `.p12` is exported.
- **Assistant authoring:** ~2 hours (this brief).
- **CI cost:** 1 manual workflow dispatch + 1 real tag run = ~25 min runner
  time on Apple Silicon.
- **No new code, no new tests, zero churn on `main`.**

---

## 12. Coupling to the v10 GA arc

| Step | Brief | Time slot |
|---|---|---|
| QA sweep + soak | `PH11_QA_SWEEP_BRIEF.md` | T-72h |
| Apple sign dry-run | **this brief §4** | T-24h |
| Tag cut + sign live | **this brief §5** + `scripts/RELEASE-v10.0.command` | T0 |
| Verify signed `.dmg` | **this brief §6** | T+30 min |
| Brother handoff sync | `PH11_BROTHER_HANDOFF_BRIEF.md` | T-7d to T+24h |
| Windows sign | `PH4_WINDOWS_SIGN_BRIEF.md` | v10.1 (NOT v10 GA blocker) |
| Updater channel bootstrap | `PH4_UPDATER_BOOTSTRAP_BRIEF.md` | T0 with Apple sign |

Apple sign is **on the GA critical path**. Windows sign is **NOT** —
v10.0.0 ships Mac-first; the `.msi` and `.exe` build (unsigned) and serve
behind a "Windows preview" label on tars.meeet.world. Real Authenticode
signing is v10.1.

---

## 13. References

- `docs/APPLE_SIGNING_SETUP.md` — one-time portal setup (341 LoC)
- `docs/APPLE_SIGNING_NEXT_TIME.md` — 15-min cheat sheet (226 LoC)
- `docs/handoff/APPLE_SIGNING_FOR_CURSOR.md` — v9.1.0 Cursor handoff (214 LoC)
- `docs/V10_GA_CHECKLIST.md` — items B1–B5 (Apple Developer side blockers)
- `docs/LAUNCH_PLAYBOOK_v10_GA.md` — operational script
- `scripts/SIGN-AND-NOTARIZE.command` — local pipeline (231 LoC)
- `scripts/RELEASE-v10.0.command` — GA tag-cut entry point
- `.github/workflows/release-desktop-tagged.yml` — CI release pipeline

---

*Brief authored as part of the W310 wave (sub-wave `W310-n`). Companion
briefs: `PH4_WINDOWS_SIGN_BRIEF.md` (next, full implementer), `PH4_UPDATER_BOOTSTRAP_BRIEF.md` (after).*
