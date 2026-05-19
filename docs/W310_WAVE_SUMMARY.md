# W310 — Post-rc1 PR triage wave · summary

**Owner:** Cursor agent (Claude Opus 4.7) — autonomous orchestration window
**Window:** 2026-05-17 → 2026-05-18
**Lane:** PR hygiene + cross-cutting closeouts on top of `v10.0.0-rc.1`
**Branch home:** `cursor/post-rc1-master-plan` (PR #188), plus per-extraction branches
**Status:** ✅ All planning sub-waves landed; **32 PRs open awaiting operator merge** (27 planning + 5 implementer follow-ups, see W310-ad / W310-ae / W310-af / W310-ag / W310-ah). Planning surface fully closed — every implementer question from `v10.0.0-rc.1` through `v11` is spec'd; implementer execution surface opened with PR #214 + extended with PR #215 + extended with PR #216 (Apple pre-flight) + extended with PR #217 (Brother pre-flight) + **consolidated with PR #218** (GA-COOKBOOK single-decision wrapper). The **five pre-tag ritual surfaces** of the GA tag (Apple pre-flight / Brother pre-flight / release / verify / soak) are now all single-command executable with spec-pinned tests — and the two pre-tag gates collapse to **ONE wrapper command** that produces a single PROCEED / BLOCK / PARTIAL verdict for *"may I tag v10.0.0?"*. **No "remembered probes" AND no "remembered sequencing" left on the v10.0.0 GA path** — the operator's mental model reduces to `bash scripts/GA-COOKBOOK.command && bash scripts/RELEASE-v10.0.command`.

---

## Why W310 exists

After `v10.0.0-rc.1` was cut (W264, 2026-05-15) the repository carried
**14 open PRs** that had been stacked through Waves 80-95 — long-running
branches built against a `main` that had since absorbed three large
refactors (W264 release axis bump, OpenTelemetry pin, dynamic
`SUPPORTED_VERSIONS`). Several of them no longer rebased cleanly; a few
introduced regressions; one outright conflicted with an endpoint that
had already shipped on `main`.

W310's mandate: **forensic triage of every open PR**, with a per-PR
decision (rebase / close-and-rewrite / close-only / extract), and a
clean repository state heading into the v10.0.0 GA dock-down.

---

## Sub-wave map

| Sub-wave | Scope | Output |
| -------- | ----- | ------ |
| **W310-a** | Master plan composition — operator decision capture, release-axis archaeology, L5 crypto canon verification | `docs/PRODUCT_MASTER_PLAN.md` (PR #188), `docs/handoff/MCP_REWRITE_BRIEF.md` |
| **W310-b** | M-wave MCP stack closeout — 6 stale stacked PRs reviewed and closed with design-intel preservation comments | PR #176, #177, #178, #179, #180, #184 closed; consolidated rewrite scheduled per `MCP_REWRITE_BRIEF.md` |
| **W310-c** | CI infrastructure diagnosis — root cause of `qa-agent.yml` failures traced to GH Actions workflow-registration cache staleness since 2026-05-13 | Header-comment touch baked into PR #188; follow-up PR planned for other affected workflows |
| **W310-d** | W309 step 2 preparation — Playwright e2e scaffold (7 `test.skip()` scenarios mapped to the W309 step 2 brief), independent of PR #187 | PR #189 (draft); `docs/handoff/W309_STEP2_BRIEF.md` updated |
| **W310-e** | Install funnel v10 sync — close PR #175 (rebase impossible due to deep semantic drift), rewrite clean | PR #190; 4 bugs fixed (3 v10-exposed); 30/30 tests green |
| **W310-f** | L4.2 voice fallback hardening — close PR #183 (4 regressions: Jarvis voice ID, ElevenLabs tuning, docstring deletion, endpoint conflict), extract additive value only | PR #191; 164/164 voice+persona tests green; `docs/handoff/L4_2_VOICE_FALLBACK_EXTRACTION_BRIEF.md` |
| **W310-g** | This document — single-page wave summary so operator can orient before the merge sequence | PR #192; this file |
| **W310-h** | Phase 2 STT streaming + push-to-talk implementer brief (v10.1, ~38 h, 7 PRs) — accelerates the next L4-lane session | PR #193; `docs/handoff/PH2_STT_STREAMING_BRIEF.md` |
| **W310-i** | Phase 2 voice gallery UI implementer brief (v10.1, ~17 h, 4 PRs) — companion to W310-h, smaller-scope warm-up | PR #194; `docs/handoff/PH2_VOICE_GALLERY_BRIEF.md` |
| **W310-j** | Phase 3 cross-platform keyring implementer brief (v10.1, ~23 h, 6 PRs) — extends macOS-only secret storage to Windows Credential Manager + Linux Secret Service | PR #195; `docs/handoff/PH3_KEYRING_BRIEF.md` |
| **W310-k** | Phase 3 cockpit pairing/recovery UX implementer brief (v10.1, ~26 h, 7 PRs) — companion to W310-j; new `<aside class="security">` panel covering 5 L5 flows (recovery seed, add-device QR, devices list, audit timeline, identity rotation) | PR #196; `docs/handoff/PH3_PAIRING_UX_BRIEF.md` |
| **W310-l** | Phase 11 v10.0.0 GA dock-down brief (~6-8 h active + 72 h soak) — V10_GA_CHECKLIST reconciliation post-W310 (8 hard blockers vs 21 deferred), 72 h soak protocol (hourly probes, hard-fail thresholds), tag-cut protocol with per-step rollback gates | PR #197; `docs/handoff/PH11_QA_SWEEP_BRIEF.md` |
| **W310-m** | v10.0.0 brother coord handoff brief (~10-12 h cross-stack) — companion to W310-l; 7 concrete syncs convergence-only (no new endpoints), reclassifies 3 of 6 brother-side A-items out of hard-blocker set, surfaces `ph3-pair-ttl` as v10.2 brother slot | PR #198; `docs/handoff/PH11_BROTHER_HANDOFF_BRIEF.md` |
| **W310-n** | Phase 4 Apple `.dmg` v10 sign dock-down (~30-45 min operator) — verification-only brief that patches v9.1.0 quirks in `APPLE_SIGNING_FOR_CURSOR.md`, adds `spctl --assess` + `stapler validate` gates, couples to `RELEASE-v10.0.command`, defines 4 explicit rollback gates (A pre-tag, B post-tag-pre-publish, C Intel-only, D corrupted .p12) | PR #199; `docs/handoff/PH4_APPLE_SIGN_V10_BRIEF.md` |
| **W310-o** | Phase 4 Windows `.exe`/`.msi` Authenticode sign full implementer brief (v10.1, ~12 h impl + ~3 h operator, ~510 LoC) — currently zero scaffold; cert decision matrix (recommend Sectigo OV @ $170/yr), two-pass sign architecture (sidecar BEFORE Tauri bundle, then installer), 6 mechanical steps with graceful degrade, 6-row risk register | PR #200; `docs/handoff/PH4_WINDOWS_SIGN_BRIEF.md` |
| **W310-p** | Phase 4 updater channel bootstrap brief (T0 + v10.1, ~0.5 h operator + ~5 h impl, ~590 LoC) — closes Phase 4 trio; bootstrap pushes 2 `TAURI_SIGNING_*` secrets at v10 GA (zero code), cockpit UI surface deferred to v10.1 (3 modules + tests), pubkey rotation runbook defensive (doc-only for v10.x) | PR #201; `docs/handoff/PH4_UPDATER_BOOTSTRAP_BRIEF.md` |
| **W310-q** | Phase 5 encrypted vault implementer brief (v10.2 gate for real data, ~3 weeks, ~2.5k LoC) — key insight: libsodium ALREADY wired in `file_vault.py`; brief focuses on scope expansion (CRM/OAuth/wallet keys migrate behind vault), master passphrase + unlock UX, SQLCipher at rest for `meeet.sqlite`, single BIP-39 mnemonic recovers both vault + host identity; 6 mechanical steps | PR #202; `docs/handoff/PH5_VAULT_BRIEF.md` |
| **W310-r** | Phase 5 policy confirmations inbox UI brief (v10.2, ~1 week, ~1.5k LoC) — key insight: backend FULLY shipped (Wave 101 policy queue, 499 LoC w/ pending+queue+confirm+deny+bulk-approve+SSE+auto-approve-threshold); brief is PURE UI implementation, zero new endpoints; sortable table + drawer + keyboard-first nav + pending pill | PR #203; `docs/handoff/PH5_POLICY_UI_BRIEF.md` |
| **W310-s** | Phase 5 differential telemetry brief (v10.2 opt-in k-anon, ~1 week, ~1.8k LoC) — closes Phase 5 trio; key insight: privacy module + gating ALREADY shipped; brief adds parallel "counters-only" stream (14 fixed bucket families, k=3, ≤10 KB/15min), vault-gated flush loop, cockpit settings panel with live preview + history + schema link | PR #204; `docs/handoff/PH5_TELEMETRY_BRIEF.md` |
| **W310-t** | Phase 6 L3 sandboxed code execution + ArtifactPanel brief (v11, ~3 weeks, ~5k LoC incl ~5 MB Pyodide vendor bundle) — opens v11 backend planning surface; greenfield `backend/core/runtime/` module; OS sandbox matrix (macOS `sandbox-exec`, Linux `firejail`+rlimit fallback, Windows/Tauri Pyodide WebView); Python+Bash adapters (JS+SQL → v11.1); 7-event WS contract `tars.runtime.v1`; cockpit `<ArtifactPanel />` with 6 MIME bucket views (markdown/html-sandboxed-iframe/json-tree/csv-virtualized/png/x-tars-table); HARD deps on #202 (vault for secrets) + #203 (policy queue for every run); 7 mechanical steps with sandbox profile manual review gate | PR #205; `docs/handoff/PH6_L3_SANDBOX_BRIEF.md` |
| **W310-u** | Phase 7 L6 planner cockpit UI brief (v11, ~1.5 weeks, ~1.8k LoC) — key insight: planner backend FULLY shipped (`backend/core/planner/` ~2.8k LoC + `web_extras/routers/planner.py` 904 LoC w/ plan synthesis, store, runner, history, SSE events); brief is PURE UI, zero new endpoints; `/plans` inbox page (list + filter + status pills), `<PlanTimeline />` drawer with step-by-step trace + diff viewer, approve/reject/abort buttons gated on policy queue (#203), "Create plan from this" affordance in chat composer, planner pill in header (running count); HARD coupling on #203 (policy UI for plan approvals) | PR #206; `docs/handoff/PH7_PLANNER_UI_BRIEF.md` |
| **W310-v** | Phase 8 L7 marketplace v1 implementer brief (v11, ~3 weeks, ~3.5k LoC) — closes the L0-L9 contract on v11 backend planning surface; key insight: marketplace v0 EXISTS (`backend/core/marketplace/` ~1.6k LoC + `web_extras/routers/marketplace.py` 267 LoC, lenient warn-don't-block signature verify); brief defines `.tars-pack` format (manifest.json + recipes/ + adapters/ + signatures/), HARD-FAIL ed25519 signing (trust store + revocation), static-analysis preflight (AST whitelist + import allowlist), remote distribution from `meeet.world/packs/` (signed mirror + CDN), cockpit `<MarketplaceSheet />` modal (browse + install + update + uninstall + ratings), 7 mechanical steps with operator-policy gate for first-time-install of each publisher | PR #207; `docs/handoff/PH8_L7_MARKETPLACE_BRIEF.md` |
| **W310-w** | Phase 9 L10 iOS companion app (SwiftUI) implementer brief (v11 TestFlight, ~3 weeks, ~2.4k Swift + ~600 LoC tests) — opens **v11 mobile planning surface**; key insight: pairing-first SPM library SHIPPED (`mobile/ios/TARSCompanion/`, 11 unit tests green; pairing handshake contract-tested against backend); brief defines the greenfield Xcode app target on top — `MainTabView` (Chat/Plans/Inbox/Settings), streaming chat via SSE-line-buffered `URLSession` actor, `PHPickerViewController` attachment upload, TestFlight pipeline via fastlane, read-only Plans + Inbox in v11 (write actions → v11.1); SOFT coupling on #203 (policy mirror) + #206 (planner mirror); HARD forward-coupling on PH9 native speech (mic perm pre-declared, `VoiceTab` stub) | PR #208; `docs/handoff/PH9_IOS_COMPANION_BRIEF.md` |
| **W310-x** | Phase 9 L10 Android companion app (Kotlin + Jetpack Compose) implementer brief (v11 Internal Testing, ~3 weeks, ~2.6k Kotlin + ~600 LoC tests) — companion to W310-w; key insight: pairing-first Compose module SHIPPED (`mobile/android/TARSCompanion/`, ~1.5k LoC, ZXing QR + OkHttp + X25519 crypto, JVM-only unit tests green); brief defines new `:companion` Gradle module on top — streaming chat via OkHttp `EventSource` + Room persistence, Storage Access Framework attachment picker, read-only Plans + Inbox tabs, Internal Testing pipeline via Gradle Play Publisher (GPP), foreground service stub for push-to-talk; SOFT coupling on #203 (policy mirror) + #206 (planner mirror); HARD forward-coupling on PH9 native speech (`PushToTalkService` stub + RECORD_AUDIO perm pre-declared) | PR #209; `docs/handoff/PH9_ANDROID_COMPANION_BRIEF.md` |
| **W310-y** | Phase 9 L10 native mobile speech implementer brief (v11, ~2.5 weeks, ~3k LoC — ~1.6k Swift + ~1.4k Kotlin — + ~800 LoC tests) — **closes the L10 mobile companion trio**; replaces unreliable Web Speech API with native engines on both platforms (iOS `SFSpeechRecognizer` on-device + `AVSpeechSynthesizer`; Android `SpeechRecognizer` offline-first on API 31+ + `TextToSpeech`) PLUS Whisper.cpp tiny.en (~75 MB bundled) as offline-first fallback; cross-platform `VoiceState` contract (7 states, byte-for-byte parity asserted via `tests/test_mobile_voice_contract.py`); `PersonaVoiceMap` mirrors desktop L4.2 `MacSayEngine` fallback pattern; WebRTC VAD (or silero-vad) endpointing; Settings mode selector (Auto / Native / Whisper.cpp); IPA / AAB grows from ~15 MB → ~95 MB (below 100 MB cellular cap; On-Demand Resources + Play Asset Delivery deferred to v11.1 if rejected); HARD-blocked on #208 + #209 (plugs into `VoiceTab` stub + `PushToTalkService` foreground stub those briefs ship); SOFT coupling on #193 (PH2 STT — same `tars.stt.v1` partial-transcript shape) + #191 (L4.2 fallback pattern reuse) + #204 (PH5 telemetry — 5 `mobile.voice.*` buckets reserved, emission deferred to v11.1) | PR #210; `docs/handoff/PH9_NATIVE_MOBILE_SPEECH_BRIEF.md` |
| **W310-aa** | Phase 3 L5 mobile pairing protocol implementer brief (v10.2, ~2.7 weeks, ~2.1k LoC + tests) — completes Phase 3 / L5 trio (cross-platform host keyring #195 + cockpit pairing UX #196 + this); end-to-end protocol from desktop QR-scan to mobile-initiated 6-digit-code flows; formalized `pending → linked|expired|rejected` state machine; three new mobile UX screens (My Paired Devices / Pairing Audit Log / Revoke Confirmation); BIP-39 recovery seed for lost-phone re-pair; `pair_id` TTL coordination with brother (15 min host-side, 24 h backend with extension); APNs (iOS) / FCM (Android) push for "device added" + "revoke" + "pairing rejected"; cross-platform wire-parity contract test (`tests/test_mobile_pairing_contract.py`) ensures iOS + Android emit byte-identical envelopes; HARD coupling on #195 (mobile reuses host keyring abstraction) + #196 (cockpit "Devices" tab same data) + #208 + #209 (iOS + Android SPM/Compose surface). 7 mechanical steps. **No new endpoints** — wraps existing host pairing surface | PR #211; `docs/handoff/PH3_MOBILE_PAIRING_BRIEF.md` |
| **W310-ab** | Phase 4 L9 Linux `.deb` + AppImage GPG signing brief (v10.2 **optional**, ~6-8 h impl + ~3 h operator, ~280 LoC) — closes the Phase 4 / L9 release-signing trio on planning surface (Apple #199 GA-critical + Windows #200 v10.1 + this Linux v10.2-optional); explicitly framed as deferred-by-design rather than implementation gap (Linux install share < 3 % per W113, Linux trust model tolerates unsigned, per-distro apt-repo overhead competes badly with higher-leverage v10.1 work); GPG-detached `.deb.gpg` + AppImage embedded signature via `appimagetool --sign`; optional `apt.tars.meeet.world` S3 + apt-ftparchive repo (step 4 deferrable to v10.3 / v11); operator GPG-key generation runbook (~5 min one-time setup, ed25519 + cv25519, 5-year expiry); 6-row risk register; **non-goals**: RPM / Snap / Flatpak / AUR / NixOS / Linux ARM / reproducible builds → v11+ if Linux share crosses 10 % | PR #212; `docs/handoff/PH4_LINUX_BRIEF.md` |
| **W310-ac** | Phase 10 Claude design-polish backlog (**continuous lane**, ~23-25 days Claude wall-clock spread at 1-2 items/week → ~3-5 months across v10.0 → v11 arc) — **closes the FINAL planning-surface gap in W310**; inventories the 13 Claude-owned visual-polish items from `docs/AGENT_HANDOFF.md` lines 3326-3394 with per-item GA-visibility tier (1 = first 30s of user life / 2 = first 5 min / 3 = power-user) + dep status + Claude effort (XS/S/M/L) + 4-point done criteria (shipped + HANDOFF row updated + no regression + `gstack-claude review` pass); tier-1 batch (landing copy #4 + brand dressing #5 + download CTAs #11 = "v10 landing brand pass" ~3.5 days, recommended fast-follow within 48 h of v10.0.0 tag); tier-2 batch (GLB asset / micro-interactions / page transitions / sound / ChatPane chrome = v10.1 ~10-12 days, item 12 meeet.world embed blocked on brother PR #198); tier-3 batch (AwarenessTicker rev / attachment polish / ⌘K + ThreadTimeline / pairing visual = v10.2 ~10 days, item 13 now post-engineering polish since PR #195 + #196 shipped functional); Claude lane is purely parallel to engineering (PH2-PH9), no merge-order dependency; append-only design (each item gets `✅ shipped W<wave>` inline when it lands) | PR #213; `docs/handoff/PH10_CLAUDE_POLISH_BACKLOG.md` |
| **W310-ad** | **First implementer follow-up** to the W310 planning surface — ships the two pure-helper scripts PR #197 §5.A asks for so the v10.0.0 soak protocol becomes executable end-to-end the moment the brief lands. `scripts/SOAK-HOURLY.command` (221 lines bash, JSON-per-line `.soak/hourly.log`, 3-consec-fail abort, `TARS_SOAK_REPO` env override for cron with absolute paths) + `scripts/SOAK-REPORT.command` (232 lines bash, markdown render with verdict + hard-fail threshold table + hour-by-hour rows + top-5 sanitized ERROR signatures + optional `--check-meeet`). Zero behaviour change to existing release pipeline. 7 spec'd unit tests + 2 meta tests = **9/9 green** in ~3 s. End-to-end smoke (HOURLY × 3 → ABORT → REPORT renders "GA tag **blocked** — hard-fail criterion hit") verified pre-push. One implement-time correction: brief said `/api/pairing/identity`, real surface is `/api/pairing/status` (flagged in script header). Lands cleanly with or without PR #197 already merged | PR #214; `scripts/SOAK-HOURLY.command` + `scripts/SOAK-REPORT.command` + `tests/test_soak_hourly.py` + `tests/test_soak_report.py` |
| **W310-ae** | **Second implementer follow-up** — automates PR #199 §6.2's three "clean-machine" Apple signature verification commands so the operator runs ONE script post-download instead of pasting three separate commands at GA time. `scripts/VERIFY-APPLE-SIGNATURE.command` (203 lines bash, +x) takes either a `.app` or a `.dmg` (auto-mounts `.dmg` read-only via `hdiutil`, finds the bundle inside, detaches on exit via `trap`), runs the three brief gates (`codesign --verify --deep --strict --verbose=2` → grep `valid on disk` + `satisfies its Designated Requirement`; `spctl --assess --type execute --verbose` → grep `accepted` + `source=Notarized Developer ID`; `stapler validate` → grep `The validate action worked`), surfaces the `Authority=` identity line against `VERIFY_APPLE_EXPECTED_IDENTITY` (default `Developer ID Application`), prints colorized `✓`/`✗` summary with the brief §7 rollback pointer if any gate red. Exit contract: 0 = GA tag verification passed; 1 = block release; 2 = prereq missing. `VERIFY_APPLE_DRY_RUN=1` + `VERIFY_APPLE_NO_DMG_MOUNT=1` env knobs for smoke tests. **9/9 green tests in ~0.09 s** — pins script structure (exec + shebang + `bash -n`), pins spec contract (header documents §6.2's 3 commands verbatim AND the 4 pass-signal substrings AND the 0/1/2 exit contract — so brief and script can't drift silently), pins runtime (missing arg / nonexistent target / wrong extension → exit 2 or 1), pins platform guard (`Darwin` check + `exit 2` present). Cannot exercise the real signing pipeline from pytest — that's covered by the operator's clean-machine run per brief §6. Lands cleanly with or without PR #199 already merged | PR #215; `scripts/VERIFY-APPLE-SIGNATURE.command` + `tests/test_verify_apple_signature_script.py` |
| **W310-af** | **Third implementer follow-up** — automates PR #199 §3 (three local-env checks) + §4 (CI-secrets check) into a single pre-tag gate so the operator catches missing prereqs at Gate A (pre-tag, cheap to roll back) instead of Gate B (post-tag, mid-publish — requires re-tag). `scripts/PREFLIGHT-APPLE-SIGN.command` (262 lines bash, +x) runs four gates verbatim from brief: §3.1 `security find-identity -v -p codesigning \| grep "Developer ID Application"` (≥1 match), §3.2 `xcrun notarytool history --keychain-profile "${APPLE_NOTARY_PROFILE}"` (success message), §3.3 `test -f .env && grep -c "^APPLE_" .env` (≥3 APPLE_* keys), §4 `gh secret list -R alxvasilevvv/tars-neural-cockpit` matched against the 6 hard-required secret names (`APPLE_CERTIFICATE`, `APPLE_CERTIFICATE_PASSWORD`, `APPLE_SIGNING_IDENTITY`, `APPLE_TEAM_ID`, `APPLE_ID`, `APPLE_PASSWORD`). For each red gate prints the exact remediation pointer from `APPLE_SIGNING_SETUP.md` / `APPLE_SIGNING_FOR_CURSOR.md`. Also prints the workflow-dispatch URL for the manual dispatch dry-run (brief §4) but does NOT trigger it (would burn a CI build minute every pre-flight; operator owns the click). Exit contract: 0 = all four green → may proceed; 1 = any red → block tag cut; 2 = prereq missing (not on macOS without `SKIP_LOCAL=1`; missing `security`/`xcrun`/`gh`). `PREFLIGHT_APPLE_DRY_RUN=1` + `PREFLIGHT_APPLE_SKIP_CI=1` + `PREFLIGHT_APPLE_SKIP_LOCAL=1` + `PREFLIGHT_APPLE_REPO=<path>` + `APPLE_NOTARY_PROFILE=<name>` + `GH_REPO=<owner/name>` env knobs for testing, cron, CI-only mode, custom keychain profile, alt-repo. **12/12 green tests in ~0.09 s + 1 skipped** (Darwin-only guard cannot fire on Mac) — pins script structure (exec + shebang + `bash -n`), pins spec contract (header documents §3.1/3.2/3.3 verbatim + §4 gh command verbatim + 6 secret names verbatim + 6 env-override names + 0/1/2 exit contract), pins required-secrets array contract (`REQUIRED_SECRETS=(...)` literally equals brief §4 names in brief's order so secret list cannot silently drift), pins dry-run path (all-skipped → exit 0 + prints next-steps cookbook), pins platform guard (uname check + exit 2 + non-Darwin without skip exits 2). Smoke verified pre-push: dry-run all-skipped → exit 0; skip-local + real `gh secret list` → exit 1, all 6 secrets correctly reported missing (expected pre-v10-GA state). Lands cleanly with or without PR #199 already merged | PR #216; `scripts/PREFLIGHT-APPLE-SIGN.command` + `tests/test_preflight_apple_sign_script.py` |
| **W310-ag** | **Fourth implementer follow-up** — automates PR #198 §7 (7 brother-side coord syncs for v10 GA) into a single pre-tag verification gate so the operator runs ONE bash command instead of 4 separate probe scripts + 1 manual `curl` + 2 env-var sanity checks. `scripts/BROTHER-PREFLIGHT.command` (375 lines bash, +x) wraps the 4 existing primitive scripts (`probe-meeet-billing.command` for A1 idempotent usage event, `CHECK-MEEET-LIVE.command` for A2 `/operator` balance shape, `smoke_billing_tars_backend.sh` for A5 auth + billing e2e, `acceptance_tars_meeet.sh` for end-to-end), runs them in sequence with last-3-lines diag capture per primitive, adds a 4th sync as a direct `curl -fsSI https://meeet.world/billing/tars` (Sync 4 = A3 checkout URL liveness — accepts 200/301/302), a 5th sync as a file-existence-OR-`BROTHER_RECONCILE_URL`-set check (Sync 5 = A4 reconciliation script ownership — two valid resolutions per brief §3.A4: TARS ships `scripts/reconcile-meeet-billing.py` OR brother declares URL via env), a 6th sync as a `BROTHER_PAIR_TTL_ACK=yes` env-var check (Sync 6 = ph3-pair-ttl ownership, framed verbatim from brief as "NOT v10 GA — heads-up only" so `ALLOWED_SKIPS=1` tolerates it). Aggregate verdict: PROCEED / BLOCK / PARTIAL with per-sync `✓`/`✗`/`⊘` rows + brief §<N>.<X> remediation pointer per red. Exit contract: 0 = all 7 green → proceed; 1 = any red → BLOCK GA tag cut; 2 = neither green nor red (prereq missing OR partial verdict from SKIP_LIVE=1 leaving ≥1 sync unverified). `BROTHER_PREFLIGHT_DRY_RUN=1` (CI mock) + `BROTHER_PREFLIGHT_SKIP_LIVE=1` (offline backend mode) + `BROTHER_PREFLIGHT_REPO=<path>` (cron) + `BROTHER_RECONCILE_URL=<url>` (Sync 5 brother-owns path) + `BROTHER_PAIR_TTL_ACK=yes` (record §6 verbal sign-off) + `BROTHER_PREFLIGHT_NO_COLOR=1` env knobs. **17/17 green tests in ~0.16 s** — pins script structure (exec + shebang + `bash -n`), pins spec contract (header enumerates all 7 syncs verbatim + each sync names its primitive script or curl invocation + PR #198 + §7 back-pointers + 0/1/2 exit contract + 6 env-override names + "NOT v10 GA — heads-up only" framing for Sync 6), pins runtime under `BROTHER_PREFLIGHT_DRY_RUN=1` matrix (skip-live + no extras → exit 1 Sync 5 red; skip-live + owners → exit 2 partial; full dry-run + owners → exit 0 PROCEED; full dry-run, no extras → exit 1; green path prints all 5 cookbook ritual pointers; red path surfaces §3.A4 remediation with both resolution paths), pins drift-catch (all 4 wrapped primitive scripts must exist on main + `ALLOWED_SKIPS=1` tolerance present + `record()` helper + `RESULTS` aggregated to stdout). **Closes the last "remembered ritual" gap on the v10 GA path** — together with #216 Apple pre-flight, every prerequisite surface of the tag cut is now machine-checkable: `bash scripts/PREFLIGHT-APPLE-SIGN.command && bash scripts/BROTHER-PREFLIGHT.command && bash scripts/RELEASE-v10.0.command && bash scripts/VERIFY-APPLE-SIGNATURE.command <dmg> && bash scripts/SOAK-HOURLY.command && (72 h later) bash scripts/SOAK-REPORT.command`. Lands cleanly with or without PR #198 already merged | PR #217; `scripts/BROTHER-PREFLIGHT.command` + `tests/test_brother_preflight_script.py` |
| **W310-ah** | **Fifth implementer follow-up** — collapses the two pre-tag gates from W310-af (#216 Apple) and W310-ag (#217 Brother) into ONE wrapper that produces a single PROCEED / BLOCK / PARTIAL verdict for *"may I tag v10.0.0?"*. `scripts/GA-COOKBOOK.command` (288 lines bash, +x) runs Gate 1 (`PREFLIGHT-APPLE-SIGN.command`) then Gate 2 (`BROTHER-PREFLIGHT.command`) — **Gate 2 always runs even if Gate 1 failed** so the operator sees both verdicts on one screen — then applies the worst-of-two aggregation rule (any 1 → 1 BLOCK; any 2 with no 1 → 2 PARTIAL; both 0 → 0 PROCEED). PROCEED path prints the remaining 7 cookbook steps (RELEASE → CI sign+notarize → download → VERIFY → drag-install → SOAK-HOURLY cron 72h → SOAK-REPORT → tag if green); BLOCK path prints per-gate remediation pointers to the relevant brief sections; PARTIAL path explains the cause (skip-live / skip-apple / non-Mac host) and defers tag decision to operator judgment. Env knobs `GA_COOKBOOK_DRY_RUN=1` + `GA_COOKBOOK_SKIP_LIVE=1` + `GA_COOKBOOK_SKIP_APPLE=1` + `GA_COOKBOOK_SKIP_BROTHER=1` + `GA_COOKBOOK_REPO=<path>` + `GA_COOKBOOK_NO_COLOR=1` — all forwarded to sub-gates as their respective `PREFLIGHT_APPLE_*` / `BROTHER_PREFLIGHT_*` knobs. All sub-gate-specific env vars (APPLE_NOTARY_PROFILE, GH_REPO, BROTHER_RECONCILE_URL, BROTHER_PAIR_TTL_ACK, etc.) pass through unchanged because sub-gates run as separate bash processes inheriting parent env. **24/24 green tests in ~0.28 s** — pins meta (exists+executable, shebang, `bash -n`), pins spec contract (names both wrapped gates verbatim, back-references PRs #216 + #217, documents 0/1/2 contract, documents worst-of-two rule, documents all 6 GA_COOKBOOK_* env overrides, lists next-step cookbook 7 commands), pins orchestration runtime (both green → 0; Apple red → 1; Brother red → 1; both red → 1; Apple partial → 2; Brother partial → 2; partial loses to red; **Gate 2 always runs even when Gate 1 red**; SKIP_APPLE → 2; SKIP_BROTHER → 2; missing Apple script → 1), pins UX (PROCEED prints next steps; BLOCK prints remediation pointers; env forwarding propagates; no `set -e` dump on failure). Stub sub-gates pattern (same isolation as test_brother_preflight_script.py) — lays minimal bash scripts in tmp dir + points `GA_COOKBOOK_REPO` at it, so tests don't need real Apple / Brother infrastructure. Smoke verified pre-push: 4 matrix variants (both green dry-run → rc=0 PROCEED; Apple skip + Brother dry-run green → rc=2 PARTIAL; both skipped → rc=2 PARTIAL; both scripts missing → rc=1 BLOCK) all match expected contract. **Closes the last operator-mental-model gap on the v10.0.0 GA path** — after this lands "may I tag v10.0.0?" reduces to "did `GA-COOKBOOK.command` exit 0?". The pre-tag motion is now ONE bash command, ONE exit code, ONE color-coded verdict. Wrapper is purely additive: zero new deps, zero changes to sub-gate scripts (#216 + #217 remain operator-runnable standalone for selective re-verification), zero changes to release pipeline. Hard dep: PR #216 + PR #217 must be on main before the wrapper resolves sub-gates (if either missing, wrapper exits 1 BLOCK with remediation pointer — fails safely, not silently). Lands cleanly with or without sub-gates already merged | PR #218; `scripts/GA-COOKBOOK.command` + `tests/test_ga_cookbook_script.py` |

> **Sub-waves a..f are forensic triage on stacked PRs.** Sub-waves g..ac
> are forward-leaning **planning surface** that reduces the briefing
> load on the next implementer session — Phase 2 voice loop + Phase 3
> security closeout for v10.1, full v10.0.0 GA dock-down arc (Phase 11,
> TARS-side methodology + brother-side convergence), Phase 4 release-
> signing trio (Apple GA + Windows v10.1 + updater + Linux v10.2-optional),
> Phase 5 v10.2 trio (encrypted vault + policy inbox UI + differential
> telemetry — the full "real data" gate), Phase 3 mobile pairing
> protocol completing L5 trio for v10.2, v11 backend trio (L3 sandbox +
> L6 planner UI + L7 marketplace v1), the **full v11 mobile companion
> trio** (PH9 iOS + PH9 Android + PH9 native speech), and the **Phase
> 10 Claude design-polish backlog** (13 items, continuous parallel
> lane). **After W310-ac the planning surface is fully closed** —
> every implementer question from `v10.0.0-rc.1` through `v11` is
> spec'd on disk. The two halves can be reviewed independently.
>
> **Sub-waves ad+ae+af+ag+ah open the implementer surface** — sequential
> follow-ups to planning briefs (PR #197 §5.A → PR #214 soak helper
> scripts; PR #199 §6.2 → PR #215 Apple signature verification helper;
> PR #199 §3+§4 → PR #216 Apple pre-flight gate; PR #198 §7 → PR #217
> Brother coord pre-flight gate; PR #216+#217 → PR #218 GA-COOKBOOK
> single-decision wrapper). Future implementer PRs append here as
> `W310-ai`, `W310-aj`, etc., each cross-referenced to the planning
> brief it executes (or the helpers it composes). The W310 implementer
> pattern is now reproduced **five times in a row**: pick the highest-
> leverage §X.Y operator-action (or the highest-leverage helper-
> composition opportunity), ship the pure-additive helper that turns
> "remembered ritual" or "remembered sequencing" into "single command",
> pin the spec contract in tests so brief and script can't drift. The
> five helpers together collapse the v10.0.0 GA cookbook to **two
> bash commands** for the operator's pre-tag motion:
>
> ```bash
> bash scripts/GA-COOKBOOK.command    # ONE PROCEED/BLOCK/PARTIAL verdict
>                                     # (Apple pre-flight + Brother pre-flight)
> bash scripts/RELEASE-v10.0.command  # destructive — only if GA-COOKBOOK exit 0
> ```
>
> The full cookbook is **nine sequential commands** end-to-end (1 GA-COOKBOOK
> + 1 RELEASE + 1 CI sign+notarize + 1 download + 1 VERIFY + 1 drag-install
> + 1 SOAK-HOURLY cron + 1 SOAK-REPORT + 1 tag-if-green decision) — every
> automatable command machine-checkable, every gate red/green rendered in
> color, every failure surfacing the exact remediation pointer from the
> brief. **The v10.0.0 GA path now has zero "remembered probes" AND zero
> "remembered sequencing" left** — the operator's pre-tag mental model is
> one wrapper command, one exit code, one color-coded verdict.

---

## Active PRs (32 open, all awaiting operator merge)

| # | Title | Wave | Status | Merge unblocks |
| - | ----- | ---- | ------ | -------------- |
| **#187** | W309 cockpit runtime step 1 — voice mode + WS + chat + TTS + vault hook-up | W309 | green except known CI cache issue | W309 step 2 implementation |
| **#188** | Post-rc1 master plan + 8 stale-PR closeouts + `qa-agent.yml` cache-fix header touch | W310-a..c | green except known CI cache issue | MCP consolidated rewrite + landing-report + cache fix on other workflows |
| **#189** *(draft)* | W310-d Playwright e2e scaffold for cockpit | W310-d | green except known CI cache issue | step 2 implementer opens to a green suite (just drop `.skip()` markers) |
| **#190** | W310-e install funnel v10 sync — Win/Linux artifacts, `LATEST_TAG`, pre-release filename regex | W310-e | green except known CI cache issue | cross-target updater channel + funnel for Tauri 2 cross-target builds |
| **#191** | W310-f L4.2 voice fallback hardening — additive extract from closed #183 | W310-f | green except known CI cache issue | L4 voice loop GA-ready |
| **#192** | W310-g wave summary (this doc) | W310-g | green except known CI cache issue | n/a — orientation doc, useful any time |
| **#193** | W310-h Phase 2 STT streaming + push-to-talk implementer brief | W310-h | green except known CI cache issue | next L4-lane session can start ph2-stt without spec work |
| **#194** | W310-i Phase 2 voice gallery UI implementer brief | W310-i | green except known CI cache issue | next L4-lane session can start ph2-voice-gallery without spec work |
| **#195** | W310-j Phase 3 cross-platform keyring implementer brief | W310-j | green except known CI cache issue | next L5-lane session can start ph3-keyring without spec work |
| **#196** | W310-k Phase 3 cockpit pairing/recovery UX implementer brief | W310-k | green except known CI cache issue | next L5-lane session can start ph3-pairing-ux without spec work; together with #195 covers the entire v10.1 Phase 3 surface |
| **#197** | W310-l Phase 11 v10.0.0 GA dock-down brief (reconciliation + soak + tag) | W310-l | green except known CI cache issue | gives operator a single-document GA execution script; ph11-qa-sweep is now spec'd end-to-end |
| **#198** | W310-m v10.0.0 brother coord handoff brief (7-sync convergence) | W310-m | green except known CI cache issue | brother lane for v10 GA is now spec'd; together with #197 closes the full v10.0.0 GA dock-down arc on planning surface |
| **#199** | W310-n Phase 4 Apple `.dmg` v10 sign dock-down (verification) | W310-n | green except known CI cache issue | on the GA critical path; operator can execute end-to-end in 30-45 min when `.p12` lands |
| **#200** | W310-o Phase 4 Windows `.exe`/`.msi` Authenticode sign full implementer brief | W310-o | green except known CI cache issue | NOT GA-blocker (v10.0 ships Windows unsigned/"Preview"); v10.1 implementer can start ph4-windows-sign mechanically; ~12 h impl + 6-step roadmap |
| **#201** | W310-p Phase 4 updater channel bootstrap (bootstrap T0, UI v10.1) | W310-p | green except known CI cache issue | bootstrap is a 30-min T0 op (zero code) alongside Apple sign at v10 GA; future v10.x line auto-publishes signed `latest.json`; UI deferred to v10.1 |
| **#202** | W310-q Phase 5 encrypted vault implementer brief (v10.2 gate for real data) | W310-q | green except known CI cache issue | v10.2 implementer can start ph5-vault mechanically; ~3 weeks, 6 steps; gate for CRM/OAuth/wallet to touch real customer data |
| **#203** | W310-r Phase 5 policy confirmations inbox UI brief (v10.2 cockpit surface) | W310-r | green except known CI cache issue | v10.2 cockpit implementer can start ph5-policy-ui mechanically; ~1 week pure UI work (backend fully shipped Wave 101); surfaces approval inbox + bulk approve + SSE |
| **#204** | W310-s Phase 5 differential telemetry brief (v10.2 opt-in k-anon counters) | W310-s | green except known CI cache issue | v10.2 implementer can start ph5-telemetry mechanically; ~1 week; closes Phase 5 trio; meeet.world side adds `POST /api/telemetry/diff/flush` per brother handoff §6 extension |
| **#205** | W310-t Phase 6 L3 sandboxed code execution + ArtifactPanel brief (v11 greenfield) | W310-t | green except known CI cache issue | opens v11 backend planning surface; v11 implementer can start ph6-sandbox + ph6-artifact-panel mechanically; ~3 weeks total; OS sandbox matrix (macOS sandbox-exec / Linux firejail+rlimit / Windows Pyodide WebView); HARD deps on #202 (vault) + #203 (policy queue) |
| **#206** | W310-u Phase 7 L6 planner cockpit UI brief (v11 pure UI, backend shipped) | W310-u | green except known CI cache issue | v11 cockpit implementer can start ph7-planner mechanically; ~1.5 weeks pure UI; planner backend already fully shipped (`backend/core/planner/` + `web_extras/routers/planner.py`); HARD coupling on #203 (policy UI for plan approvals) |
| **#207** | W310-v Phase 8 L7 marketplace v1 implementer brief (v11 hardening v0) | W310-v | green except known CI cache issue | closes the L0-L9 contract on v11 backend planning surface; v11 implementer can start ph8-marketplace mechanically; ~3 weeks; hardens existing marketplace v0 with `.tars-pack` format + hard-fail ed25519 signing + static-analysis preflight + remote distribution from `meeet.world/packs/` + `<MarketplaceSheet />` modal |
| **#208** | W310-w Phase 9 L10 iOS companion app (SwiftUI) implementer brief (v11 TestFlight) | W310-w | green except known CI cache issue | opens v11 mobile planning surface; v11 mobile implementer can start ph9-ios mechanically; ~3 weeks; greenfield Xcode app target on top of shipped pairing-first SPM library; `MainTabView` + SSE chat + PHPicker attachments + TestFlight pipeline; HARD forward-coupling on PH9 native speech (mic perm + VoiceTab stub) |
| **#209** | W310-x Phase 9 L10 Android companion app (Kotlin + Compose) implementer brief (v11 Internal Testing) | W310-x | green except known CI cache issue | v11 mobile implementer can start ph9-android mechanically (parallel-safe with ph9-ios); ~3 weeks; new `:companion` Gradle module on top of shipped pairing-first module; OkHttp `EventSource` + Room SSE chat + SAF attachments + GPP Internal Testing pipeline; HARD forward-coupling on PH9 native speech (`PushToTalkService` stub + RECORD_AUDIO pre-declared) |
| **#210** | W310-y Phase 9 L10 native mobile speech implementer brief (v11; iOS `SFSpeechRecognizer`+`AVSpeechSynthesizer`, Android `SpeechRecognizer`+`TextToSpeech`, Whisper.cpp tiny.en bundled fallback) | W310-y | green except known CI cache issue | closes the L10 mobile companion trio; **HARD-blocked on #208 + #209** (plugs into `VoiceTab` + `PushToTalkService` stubs those briefs ship); ~2.5 weeks; ~3k LoC (~1.6k Swift + ~1.4k Kotlin); cross-platform `VoiceState` contract w/ byte-for-byte parity; mode selector Auto/Native/Whisper.cpp; replaces Web Speech API everywhere. After this lands, the entire L0-L10 contract is spec'd on planning surface |
| **#211** | W310-aa Phase 3 L5 mobile pairing protocol implementer brief (v10.2, ~2.7 weeks, ~2.1k LoC + tests) | W310-aa | green except known CI cache issue | completes Phase 3 / L5 trio (#195 keyring + #196 cockpit UX + this mobile protocol); end-to-end desktop-QR + mobile-code flows, three new mobile UX screens (Devices / Audit Log / Revoke), BIP-39 lost-phone recovery, `pair_id` TTL coordination with brother (15 min host-side, 24 h backend), APNs+FCM push, cross-platform wire-parity contract test; HARD-coupled on #195 + #196 + #208 + #209; NO new endpoints — wraps existing host pairing surface |
| **#212** | W310-ab Phase 4 L9 Linux `.deb` + AppImage GPG signing brief (v10.2 **optional**, ~6-8 h impl + ~3 h operator, ~280 LoC) | W310-ab | green except known CI cache issue | closes Phase 4 / L9 release-signing trio on planning surface (Apple #199 GA-critical + Windows #200 v10.1 + this Linux v10.2-optional); explicitly framed as deferred-by-design (Linux install share <3%, trust model tolerates unsigned, per-distro overhead); GPG `.deb.gpg` + AppImage embedded signature; optional `apt.tars.meeet.world` repo (step 4 deferrable); operator GPG-key runbook ~5 min one-time; non-goals: RPM/Snap/Flatpak/AUR/NixOS/ARM/reproducible builds for v11+ if Linux share crosses 10% |
| **#213** | W310-ac Phase 10 Claude design-polish backlog (**continuous lane**, ~23-25 days Claude wall-clock spread at 1-2 items/week → ~3-5 months) | W310-ac | green except known CI cache issue | **closes the FINAL planning-surface gap in W310**; inventories the 13 Claude-owned visual-polish items from `HANDOFF.md` lines 3326-3394 with per-item GA-visibility tier + dep status + effort (XS/S/M/L) + 4-point done criteria; tier-1 batch (items 4+5+11 = "v10 landing brand pass" ~3.5d recommended fast-follow ≤48h post v10.0.0 tag); tier-2 batch v10.1 (items 1+2+3+6+8, item 12 blocked on PR #198); tier-3 batch v10.2 (items 7+9+10+13); Claude lane is purely parallel to engineering, no merge-order dependency; append-only design (each item gets `✅ shipped W<wave>` inline). **After this brief, planning surface is fully closed.** |
| **#214** | W310-ad PH11 §5.A soak helper scripts — `SOAK-HOURLY.command` + `SOAK-REPORT.command` + 9 tests (**first implementer follow-up** to the W310 planning surface) | W310-ad | green except known CI cache issue + 9/9 new tests pass in ~3 s | makes the v10.0.0 soak protocol **executable end-to-end** the moment PR #197 lands; zero behaviour change to existing release pipeline; valid JSON-per-line `.soak/hourly.log` ingestable by future dashboards; 3-consec-fail abort with `TARS_SOAK_REPO` env override so the same script works under cron with absolute paths; one implement-time correction to PR #197 (real surface is `/api/pairing/status`, not `/identity`) flagged in the script header |
| **#215** | W310-ae PH4 §6.2 Apple signature verification helper — `VERIFY-APPLE-SIGNATURE.command` + 9 tests (**second implementer follow-up**) | W310-ae | green except known CI cache issue + 9/9 new tests pass in ~0.09 s | automates the GA-blocking 3-gate verification (`codesign` + `spctl` + `stapler`) so the operator runs ONE script post-`.dmg`-download instead of pasting three commands at GA time; auto-mounts `.dmg`, surfaces `Authority=` identity, prints colorized `✓`/`✗` summary with brief §7 rollback pointer; lands cleanly with or without PR #199 already merged; closes the post-download "remembered ritual" gap on the v10.0.0 release path |
| **#216** | W310-af PH4 §3+§4 Apple pre-flight gate — `PREFLIGHT-APPLE-SIGN.command` + 12 tests (**third implementer follow-up**) | W310-af | green except known CI cache issue + 12/12 new tests pass in ~0.09 s (+1 skipped on Darwin) | automates the pre-tag prereq check (3 local-env gates: codesigning identity, notarytool profile, .env APPLE_* keys + 1 CI-secrets gate: 6 hard-required `APPLE_` secrets in repo) so the operator catches missing prereqs at Gate A (pre-tag, cheap rollback) instead of Gate B (post-tag, mid-publish — requires re-tag); prints workflow-dispatch URL for the manual dispatch dry-run but does not trigger it (owner controls build minutes); colorized `✓`/`✗` summary with brief §3/§4 remediation pointer per red gate; lands cleanly with or without PR #199 already merged; **closes the pre-tag Apple ritual gap** — together with #214 + #215 + #217 the five pre-tag surfaces of GA (Apple pre-flight + Brother pre-flight + release + verify + soak) are all single-command executable |
| **#217** | W310-ag PH11 §7 Brother coord pre-flight — `BROTHER-PREFLIGHT.command` + 17 tests (**fourth implementer follow-up**) | W310-ag | green except known CI cache issue + 17/17 new tests pass in ~0.16 s | automates PR #198 §7 (7 brother-side coord syncs for v10 GA) — wraps the 4 existing primitive scripts (`probe-meeet-billing.command` A1 + `CHECK-MEEET-LIVE.command` A2 + `smoke_billing_tars_backend.sh` A5 + `acceptance_tars_meeet.sh` end-to-end), adds direct `curl https://meeet.world/billing/tars` for A3 checkout liveness (Sync 4), file-existence-OR-`BROTHER_RECONCILE_URL`-set check for A4 reconciliation script ownership (Sync 5), `BROTHER_PAIR_TTL_ACK=yes` env-var check for v10.2 ph3-pair-ttl ack (Sync 6, framed as "NOT v10 GA — heads-up only" so `ALLOWED_SKIPS=1` tolerates it without tripping verdict); aggregate verdict PROCEED / BLOCK / PARTIAL with per-sync `✓`/`✗`/`⊘` rows + brief §<N>.<X> remediation pointer per red; exit contract 0 green / 1 red / 2 prereq-missing-OR-partial; full env knob surface (DRY_RUN + SKIP_LIVE + REPO + RECONCILE_URL + PAIR_TTL_ACK + NO_COLOR); closes the pre-tag Brother ritual gap — the brother coord surface is now machine-checkable alongside the Apple surface (#216); lands cleanly with or without PR #198 already merged |
| **#218** | W310-ah GA-COOKBOOK single-decision wrapper — `GA-COOKBOOK.command` + 24 tests (**fifth implementer follow-up**) | W310-ah | green except known CI cache issue + 24/24 new tests pass in ~0.28 s | composes PR #216 (Apple pre-flight) + PR #217 (Brother pre-flight) into ONE wrapper that produces a single PROCEED / BLOCK / PARTIAL verdict for *"may I tag v10.0.0?"*; runs both sub-gates sequentially with **Gate 2 always running even if Gate 1 red** so the operator sees both verdicts on one screen; worst-of-two aggregation (any rc=1 → BLOCK, any rc=2 with no rc=1 → PARTIAL, both rc=0 → PROCEED); PROCEED prints next-step cookbook (RELEASE → CI sign+notarize → download → VERIFY → drag-install → SOAK-HOURLY cron 72h → SOAK-REPORT → tag if green); BLOCK prints per-gate remediation pointer to the relevant brief section; PARTIAL explains cause (skip-live / skip-apple / non-Mac host) and defers to operator judgment; full env-knob pass-through (DRY_RUN / SKIP_LIVE / SKIP_APPLE / SKIP_BROTHER / REPO / NO_COLOR — all forwarded to sub-gates as PREFLIGHT_APPLE_* / BROTHER_PREFLIGHT_*); zero new deps, zero changes to sub-gate scripts (#216 + #217 remain operator-runnable standalone); hard dep on #216 + #217 (fails safely with rc=1 BLOCK + remediation pointer if either missing); **closes the last operator-mental-model gap on the v10.0.0 GA path** — after this lands the pre-tag motion is ONE bash command, ONE exit code, ONE color-coded verdict; lands cleanly with or without sub-gates already merged |

> **Known CI failure (cosmetic, repo-wide).** `TARS B2B E2E suite`,
> `TARS eval suite`, `scan working tree` all fail in 2-3 s on every
> PR cut after 2026-05-13. Root cause is a GH Actions workflow
> registration cache that went stale; PR #188 includes the
> single-character header-comment fix for `qa-agent.yml` and a
> follow-up PR is scheduled to apply the same trick to
> `e2e-suite.yml`, `eval-suite.yml`, `credential-sentinel.yml`,
> `scan-working-tree.yml`. **None of these failures reflect actual
> test results.**

---

## Closed PRs (W310)

### Stale M-wave MCP stack (6 PRs)

Closed in W310-b. All targeted the pre-rc1 cockpit and depended on each
other in a 6-deep stack that no longer rebased. Design intelligence
captured in `docs/handoff/MCP_REWRITE_BRIEF.md`; consolidated rewrite
will follow on a single fresh branch after PR #188 merges.

| # | Rationale |
| - | --------- |
| #176 | Wrong cockpit + stack base no longer rebasable |
| #177 | Stack child of #176; same |
| #178 | Stack child of #177; same |
| #179 | Stack child of #178; same |
| #180 | Stack child of #179; same |
| #184 | Mid-stack repaint; same |

### Algotrade Wave-M (2 PRs)

Closed in W310-a (operator decision D4: out of scope until post-v10 GA).
Re-open candidacy noted in `docs/PRODUCT_MASTER_PLAN.md §3.A`.

| # | Rationale |
| - | --------- |
| #170 | Algotrade E2E suite — out of scope for v10 GA |
| #174 | Algotrade Wave-M continuation — same |

### Other PR triage (W310-b/e/f)

| # | Wave | Outcome | Reason |
| - | ---- | ------- | ------ |
| #175 | W310-e | Close-and-rewrite as #190 | Hardcoded `_DEFAULT_ARTIFACTS` approach obsolete after dynamic `SUPPORTED_VERSIONS` refactor on `main`; 3 newly-discovered v10-exposed bugs found during forensic review |
| #181 | W310-b | Closed | Algotrade demo (same scope as #170/#174) |
| #182 | W310-b | Closed | Frontend targeted outdated `experiments/neural-showcase-v3` cockpit; backend depended on closed M-wave stack — graceful-degradation patterns preserved in `MCP_REWRITE_BRIEF.md §4` |
| #183 | W310-f | Close-and-extract as #191 | 4 regressions (Jarvis voice "George"→default, ElevenLabs cinematic tuning stripped, `PersonaProviderHint` docstring deleted, semantic conflict with already-shipped `/api/voice/personas/effective` endpoint from W295) |

---

## Recommended merge order

**Triage/runtime PRs (#187-#191):**

1. **#188 first** — unlocks the cache-fix follow-up + makes the master plan canonical (it's already referenced by `AGENTS.md` in `meeet-browser-agent`).
2. **#187** — unlocks W309 step 2 implementation.
3. **#189** — can land any time but ideally **after #187** so step 2 implementation opens with a green skipping suite.
4. **#190** — install funnel; landing earlier just means the cross-target funnel works sooner for testing.
5. **#191** — voice fallback hardening; landing earlier just means the L4 voice loop becomes GA-ready sooner.

**Planning-surface PRs (#192-#213):**

These are docs-only and have **no downstream code dependency** — merge
any time, in any order. Optimal time-to-value is to merge them whenever
operator has a 1-minute review window between the runtime merges.

All 27 are **independent** at the file level (no shared paths), so they
can also land in parallel. The order above only reflects which merges
unblock the most downstream work.

**Implementer follow-ups (#214, #215, #216, #217):** also independent
at file level (all four pure additive — `scripts/*` + `tests/*` only).
All four land cleanly with or without their parent planning brief
already merged. Merge any time; landing them early just means the
operator has executable helpers when the GA window opens. Together
they cover all **five pre-tag ritual surfaces** of the v10.0.0
tag-cut sequence:

1. **Apple pre-tag** — `bash scripts/PREFLIGHT-APPLE-SIGN.command` (#216) checks 3 local-env + 1 CI-secrets gates BEFORE invoking the destructive release script
2. **Brother pre-tag** — `bash scripts/BROTHER-PREFLIGHT.command` (#217) checks 7 brother-side coord syncs (A1/A2/A5 ingest + balance + auth + A3 checkout + A4 reconcile + ph3-pair-ttl ack + e2e) BEFORE invoking the destructive release script
3. **Release** — `bash scripts/RELEASE-v10.0.command` (already shipped) cuts the tag + triggers signing + notarization
4. **Post-download** — `bash scripts/VERIFY-APPLE-SIGNATURE.command <path-to-dmg>` (#215) runs 3 brief gates on the downloaded `.dmg` on a clean Mac
5. **Soak** — `bash scripts/SOAK-HOURLY.command` (cron, 72 h) + `bash scripts/SOAK-REPORT.command` (#214) drive the GA soak window with auto-abort on 3-consec-fail and markdown verdict at the end

Steps 1+2+3+4+5 = six bash commands, each spec-pinned, each
machine-checkable, each surfacing exact remediation pointers from
the planning briefs. **Zero "remembered probes" left on the GA path.**

**The planning surface is fully closed after PR #213.** Every
implementer question from v10.0.0-rc.1 through v11 has a brief on
disk:

- v10.0.0 GA: #197 (QA sweep) + #198 (brother handoff) + #199 (Apple sign)
- v10.1: #193 (PH2 STT) + #194 (PH2 voice gallery) + #195 (PH3 keyring) + #196 (PH3 pairing UX) + #200 (PH4 Windows) + #201 (PH4 updater)
- v10.2: #202 (PH5 vault) + #203 (PH5 policy UI) + #204 (PH5 telemetry) + #211 (PH3 mobile pairing) + #212 (PH4 Linux optional)
- v11: #205 (PH6 sandbox) + #206 (PH7 planner UI) + #207 (PH8 marketplace) + #208 (PH9 iOS) + #209 (PH9 Android) + #210 (PH9 native speech)
- Continuous: #213 (PH10 Claude polish backlog, 13 items spread across v10.0 → v11)

---

## Pending W310 follow-ups (post-merge)

- **`ph1-ci-cache-other-workflows`** — after PR #188 lands, apply the same `qa-agent.yml`-style header-comment trick to `e2e-suite.yml`, `eval-suite.yml`, `credential-sentinel.yml`, `scan-working-tree.yml`. **Mix-of-scopes risk** — done as a separate small infra PR, not bundled into anything else.
- **`ph1-mcp-consolidated`** — open `cursor/mcp-rewrite-consolidated` PR per `docs/handoff/MCP_REWRITE_BRIEF.md` after PR #188 merges (master plan needs to be canonical first so the new PR can cite §2.B of it).

Both items are tracked in the active todo list and will be picked up
autonomously once their merge prerequisites are met.

---

## Cross-workspace state

`meeet-browser-agent`'s `AGENTS.md` has been synced through W310 in three
passes:

- **W310-b** — initial #187 + #188 snapshot
- **W310-f** — expanded to full 5-PR fleet (#187-#191) plus known CI cache issue
- **W310-i** — re-expanded to the full 8-PR fleet (#187-#194) including the three
  planning-surface PRs and their per-PR effort estimates
- **W310-j** — added PR #195 (Phase 3 keyring brief) to the planning-surface
  track, lifting the active PR count to 9
- **W310-k** — added PR #196 (Phase 3 pairing/recovery UX brief, companion
  to #195) to the planning-surface track, lifting the active PR count to 10
- **W310-l** — added PR #197 (Phase 11 v10.0.0 GA dock-down brief, the
  release-engineering methodology that bridges existing scripts +
  checklist) to the planning-surface track, lifting the active PR count
  to 11
- **W310-m** — added PR #198 (v10.0.0 brother coord handoff brief,
  companion to W310-l) to the planning-surface track, lifting the
  active PR count to 12. The W310 wave now covers the full v10 → v10.1
  arc on planning surface alone — every implementer + coord question
  for the v10.0.0 GA tag has a spec'd brief.
- **W310-n/o/p** — added PRs #199-#201 (Phase 4 / L9 release-signing
  trio: Apple `.dmg` v10 dock-down, Windows `.exe`/`.msi` Authenticode
  full implementer, updater channel bootstrap), lifting the active PR
  count to 15. The trio closes the entire Phase 4 / L9 planning surface:
  Apple sign is GA-critical (verification-only brief), Windows is v10.1
  (full implementer brief, 12 h impl + 510 LoC roadmap), updater
  bootstrap is a 30-min T0 op coupled to the Apple sign workflow with
  the UI surface deferred to v10.1.
- **W310-q/r/s** — added PRs #202-#204 (Phase 5 v10.2 "real data" trio:
  encrypted vault, policy confirmations inbox UI, differential
  telemetry), lifting the active PR count to 18. The trio closes the
  entire Phase 5 planning surface and unlocks v10.2 as the release that
  lets pack adapters touch real customer data: vault re-keys CRM/OAuth/
  wallet secrets behind a master passphrase + libsodium AEAD (with
  SQLCipher for `meeet.sqlite` at rest), policy UI surfaces the Wave 101
  approval queue in cockpit as a sortable inbox with bulk approve + SSE,
  and telemetry adds a k-anonymized differential counter stream
  (default OFF, vault-gated flush, fixed 14-bucket schema). The full v10
  → v10.2 arc is now spec'd on planning surface — every implementer
  question for the next two releases has a brief.
- **W310-t** — added PR #205 (Phase 6 L3 sandboxed code execution +
  ArtifactPanel brief, v11 greenfield), lifting the active PR count to
  19. Opens the **v11 backend planning surface**: closes the last
  unshipped L0-L9 contract (L10 mobile remains, separate brief). OS
  sandbox matrix (macOS `sandbox-exec`, Linux `firejail`+rlimit
  fallback, Windows/Tauri Pyodide WebView). HARD-coupled to Phase 5
  trio: every `run_code` enqueues a policy confirmation (#203) and
  fetches secrets through VaultGate (#202). Cockpit ArtifactPanel
  renders 6 MIME bucket views (markdown/sandboxed-html/json-tree/
  csv-virtualized/png/x-tars-table). ~3 weeks impl, ~5k LoC incl
  ~1.4k LoC tests and ~5 MB vendored Pyodide bundle for the Windows/
  Tauri path. Next planning briefs: PH7 (L6 planner), PH8 (L7
  marketplace), PH9 (L10 mobile).
- **W310-u** — added PR #206 (Phase 7 L6 planner cockpit UI brief),
  lifting the active PR count to 20. Pure-UI brief: planner backend
  fully shipped (`backend/core/planner/` ~2.8k LoC + `web_extras/
  routers/planner.py` 904 LoC w/ synthesis, store, runner, history,
  SSE events, playbook integration). Brief specs `/plans` inbox page,
  `<PlanTimeline />` drawer with step-by-step trace + diff viewer,
  approve/reject/abort buttons gated on policy queue (#203), "Create
  plan from this" composer affordance, and a planner pill in header.
  HARD coupling on #203 for plan-approval policy enqueue. ~1.5 weeks
  impl.
- **W310-v** — added PR #207 (Phase 8 L7 marketplace v1 implementer
  brief), lifting the active PR count to 21. Closes the **L0-L9
  contract on v11 backend planning surface**. Hardens existing
  marketplace v0 (`backend/core/marketplace/` ~1.6k LoC + 267 LoC
  router, currently lenient warn-don't-block sig verify) into v1:
  defines `.tars-pack` format (manifest.json + recipes/ + adapters/ +
  signatures/), HARD-FAIL ed25519 signing (trust store + revocation),
  static-analysis preflight (AST whitelist + import allowlist), remote
  distribution from `meeet.world/packs/` (signed mirror + CDN), and
  cockpit `<MarketplaceSheet />` modal (browse + install + update +
  uninstall + ratings). Operator-policy gate on first-time-install
  of each publisher. 7 mechanical steps, ~3 weeks impl, ~3.5k LoC.
  After this brief, the full L0-L9 contract is spec'd; only L10
  mobile remains.
- **W310-w** — added PR #208 (Phase 9 L10 iOS companion app SwiftUI
  brief), lifting the active PR count to 22. **Opens the v11 mobile
  planning surface.** Key insight: pairing-first SPM library SHIPPED
  (`mobile/ios/TARSCompanion/`, 11 unit tests green; pairing handshake
  contract-tested against backend). Brief specs the greenfield Xcode
  app target on top: `MainTabView` with Chat/Plans/Inbox/Settings
  tabs, streaming chat via SSE-line-buffered `URLSession` actor,
  `PHPickerViewController` attachment upload, TestFlight pipeline via
  fastlane (`bump_build`, `build_testflight`, `submit_testflight`),
  read-only Plans + Inbox in v11 (write actions deferred to v11.1).
  SOFT coupling on #203 (policy mirror) + #206 (planner mirror).
  HARD forward-coupling on PH9 native speech (mic permission +
  `VoiceTab` stub pre-declared). 6 mechanical steps, ~3 weeks impl,
  ~2.4k Swift LoC + ~600 LoC tests. Distribution: TestFlight v11;
  App Store v11.1 after Apple LLM-disclosure language is dialed in.
  Two native codebases preserved (Swift + Kotlin), no React Native /
  Flutter / Cordova wrappers.
- **W310-x** — added PR #209 (Phase 9 L10 Android companion app
  Kotlin + Jetpack Compose brief), lifting the active PR count to 23.
  Companion to W310-w; parallel-safe with PH9 iOS. Key insight:
  pairing-first Compose module SHIPPED (`mobile/android/TARSCompanion/`,
  ~1.5k Kotlin LoC, 13 files, 2 activities, ZXing for QR, OkHttp for
  net, X25519 for crypto, JVM-only unit tests green). Brief specs new
  `:companion` Gradle module on top: streaming chat via OkHttp
  `EventSource` w/ Room persistence (`ChatMessageEntity`,
  `ChatDao`, `TARSDatabase`), Storage Access Framework attachment
  picker (no READ_EXTERNAL_STORAGE required), read-only Plans +
  Inbox tabs (write actions deferred to v11.1), Internal Testing
  build pipeline via **Gradle Play Publisher (GPP)** (`./gradlew
  :companion:publishBundle --track internal`), foreground service
  stub `PushToTalkService` (no audio capture yet; placeholder
  notification + lifecycle hooks for PH9 native speech to fill in).
  SOFT coupling on #203 (policy mirror) + #206 (planner mirror).
  HARD forward-coupling on PH9 native speech (RECORD_AUDIO
  pre-declared, `PushToTalkService` stub). 6 mechanical steps,
  ~3 weeks impl, ~2.6k Kotlin LoC + ~600 LoC tests. Distribution:
  Internal Testing track v11; Closed/Open Beta v11.1; Production
  v11.2 after one full beta cycle.
- **W310-y** — added PR #210 (Phase 9 L10 native mobile speech
  brief), lifting the active PR count to 24. **Closes the L10
  mobile companion trio.** Replaces the unreliable Web Speech API
  on both platforms with native engines + bundled offline-first
  Whisper.cpp fallback. iOS: `SFSpeechRecognizer` (on-device since
  iOS 13) + `AVSpeechSynthesizer`. Android: `SpeechRecognizer`
  (offline-first on API 31+) + `TextToSpeech`. Both: Whisper.cpp
  tiny.en (~75 MB bundled) as offline-first fallback. VAD
  endpointing via WebRTC VAD (recommend silero-vad: ~2 MB MIT vs
  12 MB Google). Cross-platform `VoiceState` contract (7 states,
  byte-for-byte parity asserted via `tests/test_mobile_voice_contract.py`).
  `PersonaVoiceMap` mirrors desktop L4.2 `MacSayEngine` fallback
  pattern. Mode selector in Settings (Auto / Native / Whisper.cpp).
  App size impact: IPA + AAB grow from ~15 MB → ~95 MB (below 100
  MB cellular download cap; On-Demand Resources + Play Asset
  Delivery deferred to v11.1 if Apple / Google reject). **HARD-blocked
  on #208 + #209** (replaces stubs `VoiceTab` and `PushToTalkService`).
  SOFT coupling on #193 (PH2 STT — same `tars.stt.v1` partial-transcript
  shape) + #191 (L4.2 fallback pattern reuse) + #204 (PH5 telemetry —
  5 `mobile.voice.*` buckets reserved, emission deferred to v11.1).
  6 mechanical steps, ~3k LoC (~1.6k Swift + ~1.4k Kotlin) + ~800
  LoC tests, ~2.5 weeks impl. Nightly WER ≤ 0.10 regression on
  librispeech-test-clean first 20 utterances.
- **W310-aa** — added PR #211 (Phase 3 L5 mobile pairing protocol
  brief, v10.2, ~2.7 weeks, ~2.1k LoC + tests), lifting the active
  PR count to 25. **Completes Phase 3 / L5 trio**: #195 cross-platform
  host keyring + #196 cockpit pairing/recovery UX + this mobile
  protocol. End-to-end protocol from desktop QR-scan to mobile-
  initiated 6-digit-code flows; formalized `pending → linked|
  expired|rejected` state machine; three new mobile UX screens
  ("My Paired Devices" / "Pairing Audit Log" / "Revoke
  Confirmation"); BIP-39 recovery seed flow for lost-phone re-
  pair; `pair_id` TTL coordination with brother (15 min host-side
  short-lived, 24 h backend with extension on accept); APNs (iOS)
  / FCM (Android) push for "device added" + "revoke from elsewhere"
  + "pairing rejected"; cross-platform wire-parity contract test
  (`tests/test_mobile_pairing_contract.py`) asserts iOS + Android
  emit byte-identical envelopes for the same payload. **HARD
  coupling on #195** (mobile reuses host keyring abstraction
  pattern for storing per-account paired identities) + **#196**
  (cockpit "My Paired Devices" tab from #196 displays the same
  data this brief writes from mobile side) + **#208 + #209**
  (iOS SwiftUI + Android Compose surfaces). **NO new endpoints**
  — wraps existing host pairing surface from `backend/core/
  pairing/store.py`. 7 mechanical steps with §5 risk register
  + §6 operator open questions.
- **W310-ab** — added PR #212 (Phase 4 L9 Linux `.deb` + AppImage
  GPG signing brief, v10.2 optional, ~6-8 h impl + ~3 h operator,
  ~280 LoC), lifting the active PR count to 26. **Closes the
  Phase 4 / L9 release-signing trio on planning surface**: Apple
  #199 (GA-critical, hard blocker B1) + Windows #200 (v10.1, full
  implementer) + this Linux v10.2-optional brief. Explicitly framed
  as deferred-by-design rather than implementation gap (Linux
  install share < 3 % per W113 download telemetry, Linux trust
  model tolerates unsigned binaries (apt warns + installs; AppImage
  just chmod+run; no Gatekeeper-equivalent hard-block), per-distro
  apt-repo overhead competes badly with higher-leverage v10.1
  work, natural slot alongside PH5 "real data" trio as the "real
  Linux trust" pass in v10.2). 5 mechanical steps: GPG-detached
  `.deb.gpg` signature + `tars-pubkey.asc` import flow, AppImage
  embedded signature via `appimagetool --sign`, optional
  `apt.tars.meeet.world` S3 + apt-ftparchive repo (step 4 fully
  deferrable to v10.3 / v11 without affecting rest of v10.2 Linux
  signing), updater channel uniformity (Linux-x86_64 entry in
  `latest.json`), brief → SHIPPED reconciliation. Operator GPG-key
  runbook (~5 min one-time setup, ed25519 + cv25519, 5-year
  expiry recommended). 6-row risk register, highest-impact "user
  imports wrong pubkey from MITM" mitigated by HTTPS-only
  distribution + future DNS TXT publication. **Non-goals**: RPM
  (Fedora/RHEL/SUSE), Snap, Flatpak, AUR, NixOS, reproducible
  builds, Linux ARM (`aarch64-unknown-linux-gnu`) — all roadmap
  for v11+ if Linux install share crosses 10 %.
- **W310-ac** — added PR #213 (Phase 10 Claude design-polish
  backlog, continuous lane, ~23-25 days Claude wall-clock spread
  at 1-2 items/week → ~3-5 months across v10.0 → v11 arc), lifting
  the active PR count to **27**. **CLOSES THE FINAL PLANNING-
  SURFACE GAP IN W310.** Inventories the 13 Claude-owned visual-
  polish items from `docs/AGENT_HANDOFF.md` lines 3326-3394 with
  per-item dimensions: GA-visibility tier (1 = first 30s of user
  life, 2 = first 5 min, 3 = power-user), engineering dep status
  (ready vs blocked-on-brother), Claude effort (XS/S/M/L), and
  4-point done criteria (component shipped + HANDOFF row updated
  + no regression + `gstack-claude review` pass). Tier-1 batch
  (items 4 landing copy + 5 brand dressing + 11 download CTAs =
  "v10 landing brand pass", ~3.5 days, recommended fast-follow
  within 48 h of v10.0.0 tag so blog post + OG share images use
  polished brand). Tier-2 batch v10.1 (items 1 GLB asset + 2
  micro-interactions + 3 page transitions + 6 sound design + 8
  ChatPane chrome polish, ~10-12 days; item 12 meeet.world embed
  BLOCKED on brother sync PR #198). Tier-3 batch v10.2 (items 7
  AwarenessTicker rev + 9 attachment/sources visual + 10 ⌘K +
  ThreadTimeline visual (biggest L-effort) + 13 pairing-flow
  visual — NOW post-engineering polish since PR #195+#196 shipped
  functional surface, not pre-code sketch as originally framed in
  HANDOFF). Key framing: Claude lane is purely parallel to
  engineering (PH2-PH9); engineering merge order (PR #187 → #211)
  doesn't gate Claude sequence; none of the 13 items is a v10.0.0
  hard blocker (`V10_GA_CHECKLIST.md` is engineering-driven).
  Append-only design: each item gets `✅ shipped W<wave>` inline
  when it lands; brief STATUS → SHIPPED ✅ only when all 13
  complete + HANDOFF "Phase 10 design polish closed (13/13)" row
  added. **After this brief lands, the planning surface is fully
  closed.** Every implementer question from `v10.0.0-rc.1`
  through `v11` has a brief on disk.
- **W310-ad** — added PR #214 (PH11 §5.A soak helper scripts —
  `SOAK-HOURLY.command` + `SOAK-REPORT.command` + 9 unit/meta tests,
  +827 LoC), lifting the active PR count to **28**. **FIRST
  IMPLEMENTER FOLLOW-UP** to the W310 planning surface. Picks the
  highest-leverage immediate-prep PR from the 27 briefs: PR #197
  (PH11 GA dock-down) explicitly calls in its §5.A for two new
  helper scripts the soak protocol depends on, and the operator
  cannot start the 72 h soak window without them. Hourly probe hits
  the four mandatory health routes (corrected `/api/pairing/status`
  vs brief's `/identity` typo, flagged in script header) + the
  optional QA-Agent probe, records p50/p95/RSS/fd/new-ERRORs/WAL
  size as one JSON line per call in `.soak/hourly.log`, aborts with
  exit 1 after 3 consecutive probe-fail hours per §4.5. Report
  script renders the markdown contract from §4.6 (verdict +
  hard-fail threshold table + hour-by-hour rows + top-5 sanitized
  ERROR signatures + optional `--check-meeet`) with thresholds
  pulled verbatim from §4.5 (p95 drift 20 %, ERR/h 100, RSS 2 GB,
  fd 1024). Hermetic tests (`ThreadingHTTPServer` for fake backend,
  no extra pytest plugins, ~3 s total). `TARS_SOAK_REPO` env
  override lets the same script work under cron with absolute
  paths. Lands cleanly with or without PR #197 already merged —
  pure additive, zero behaviour change to the existing release
  pipeline. **Demonstrates the W310 pattern is now production:
  briefs are review-grade, implementer follow-ups land in single
  PRs with green tests and end-to-end smoke verified pre-push.**
- **W310-ae** — added PR #215 (PH4 §6.2 Apple signature verification
  helper — `VERIFY-APPLE-SIGNATURE.command` + 9 spec-contract tests,
  +388 LoC), lifting the active PR count to **29**. **SECOND
  IMPLEMENTER FOLLOW-UP** to the W310 planning surface. Picks the
  highest-leverage GA-blocker prep from the 27 briefs: PR #199
  (PH4 Apple `.dmg` v10 dock-down) §6.2 lists three "clean-machine"
  verification commands the operator MUST run on a fresh Mac after
  downloading the signed `.dmg` from GH Release — exactly the wrong
  time for manual ritual. Helper takes either `.app` or `.dmg`
  (auto-mounts `.dmg` read-only via `hdiutil`, finds bundle inside,
  detaches via `trap` on exit), runs the three brief gates
  verbatim (`codesign --verify --deep --strict --verbose=2` →
  grep `valid on disk` + `satisfies its Designated Requirement`;
  `spctl --assess --type execute --verbose` → grep `accepted` +
  `source=Notarized Developer ID`; `stapler validate` → grep
  `The validate action worked`), extracts `Authority=` identity
  line and compares against `VERIFY_APPLE_EXPECTED_IDENTITY`
  (default `Developer ID Application`), prints colorized
  `✓`/`✗` summary with brief §7 (A/B/C) rollback pointer if any
  gate red. Exit contract per brief: 0 = GA tag verification
  passed; 1 = block release; 2 = prereq missing. `VERIFY_APPLE_DRY_RUN=1`
  + `VERIFY_APPLE_NO_DMG_MOUNT=1` env knobs for smoke-test
  isolation. Cannot exercise the real signing pipeline from
  pytest (no signed `.app` + Apple keychain in CI) — instead
  pins what IS deterministic and mistake-prone: meta (executable
  + shebang + `bash -n`), spec contract (header documents §6.2's
  three commands verbatim AND the four pass-signal substrings AND
  the 0/1/2 exit contract — so brief and script can't drift
  silently), runtime arg-validation (missing arg / nonexistent
  target / wrong extension), platform guard (`Darwin` check + 
  `exit 2`). **9/9 green in ~0.09 s.** Lands cleanly with or
  without PR #199 already merged — pure additive, two new files,
  zero edits to existing code.
- **W310-ah** — added PR #218 (GA-COOKBOOK single-decision wrapper —
  `GA-COOKBOOK.command` + 24 spec-contract tests, +470 LoC), lifting the
  active PR count to **32**. **FIFTH IMPLEMENTER FOLLOW-UP** to the W310
  planning surface, and the FIRST that composes existing helpers rather
  than wrapping a brief directly. Picks the highest-leverage post-W310-ag
  consolidation opportunity: the operator now has TWO independent pre-tag
  gates (Apple via #216, Brother via #217), and the "remembered sequencing"
  surface of running them in order, capturing both exit codes, and
  deciding *"may I tag?"* still lives in operator head. This wrapper
  collapses that mental model to ONE bash command producing ONE PROCEED /
  BLOCK / PARTIAL verdict. Runs Gate 1 (`PREFLIGHT-APPLE-SIGN.command`)
  then Gate 2 (`BROTHER-PREFLIGHT.command`) sequentially — **Gate 2
  always runs even when Gate 1 returns red** so the operator gets the
  full picture on one screen instead of having to fix Apple, re-run,
  then discover Brother is also red. Worst-of-two aggregation: any rc=1
  → BLOCK, any rc=2 with no rc=1 → PARTIAL, both rc=0 → PROCEED.
  PROCEED prints the remaining 7 cookbook steps verbatim (RELEASE →
  CI sign+notarize → download → VERIFY → drag-install → SOAK-HOURLY
  cron 72h → SOAK-REPORT → tag if green). BLOCK prints per-gate
  remediation pointer to the relevant brief section. PARTIAL explains
  cause (skip-live / skip-apple / non-Mac host) and defers tag decision
  to operator judgment. Env knobs `GA_COOKBOOK_DRY_RUN=1` +
  `GA_COOKBOOK_SKIP_LIVE=1` + `GA_COOKBOOK_SKIP_APPLE=1` +
  `GA_COOKBOOK_SKIP_BROTHER=1` + `GA_COOKBOOK_REPO=<path>` +
  `GA_COOKBOOK_NO_COLOR=1` — all forwarded to sub-gates as their
  respective `PREFLIGHT_APPLE_*` / `BROTHER_PREFLIGHT_*` knobs. All
  sub-gate-specific env vars (APPLE_NOTARY_PROFILE, GH_REPO,
  BROTHER_RECONCILE_URL, BROTHER_PAIR_TTL_ACK, etc.) pass through
  unchanged because sub-gates run as separate bash processes inheriting
  parent env. **24/24 green tests in ~0.28 s** — pins meta (executable
  + shebang + `bash -n`), pins spec contract (names both wrapped gates
  verbatim, back-references PRs #216 + #217, documents 0/1/2 contract,
  documents worst-of-two rule, documents all 6 `GA_COOKBOOK_*` env
  overrides, lists next-step cookbook 7 commands), pins orchestration
  runtime (both green → 0; Apple red → 1; Brother red → 1; both red →
  1; Apple partial → 2; Brother partial → 2; partial loses to red;
  **Gate 2 always runs even when Gate 1 red**; SKIP_APPLE → 2;
  SKIP_BROTHER → 2; missing Apple script → 1), pins UX (PROCEED prints
  next steps; BLOCK prints remediation pointers; env forwarding
  propagates; no `set -e` dump on failure). Stub sub-gates pattern
  (same isolation as `test_brother_preflight_script.py`) — lays minimal
  bash scripts in tmp dir + points `GA_COOKBOOK_REPO` at it, so tests
  don't need real Apple / Brother infrastructure. Smoke verified pre-push:
  4 matrix variants (both green dry-run → rc=0 PROCEED; Apple skip +
  Brother dry-run green → rc=2 PARTIAL; both skipped → rc=2 PARTIAL;
  both scripts missing → rc=1 BLOCK) all match expected contract.
  Wrapper is purely additive: zero new deps, zero changes to sub-gate
  scripts (#216 + #217 remain operator-runnable standalone for selective
  re-verification), zero changes to release pipeline. Hard dep: PR #216 +
  PR #217 must be on main before the wrapper resolves sub-gates (if
  either missing, wrapper exits 1 BLOCK with remediation pointer — fails
  safely, not silently). **Closes the last operator-mental-model gap on
  the v10.0.0 GA path** — after this lands, "may I tag v10.0.0?" reduces
  to "did `GA-COOKBOOK.command` exit 0?". Lands cleanly with or without
  sub-gates already merged.
- **W310-ag** — added PR #217 (PH11 §7 Brother coord pre-flight gate —
  `BROTHER-PREFLIGHT.command` + 17 spec-contract tests, +666 LoC),
  lifting the active PR count to **31**. **FOURTH IMPLEMENTER FOLLOW-UP**
  to the W310 planning surface. Picks the highest-leverage pre-tag
  prep from PR #198: the §7 7-sync convergence checklist (3 hard A1/A2/A5
  blockers + A3 checkout liveness + A4 reconcile ownership + v10.2
  ph3-pair-ttl ack + acceptance). Brief framing carried verbatim into
  script header: ph3-pair-ttl explicitly "NOT v10 GA — heads-up only"
  (so `ALLOWED_SKIPS=1` tolerates it without tripping verdict). Wraps
  4 existing primitive scripts on `main` (`probe-meeet-billing.command`
  Sync 1 → A1, `CHECK-MEEET-LIVE.command` Sync 2 → A2,
  `smoke_billing_tars_backend.sh` Sync 3 → A5,
  `acceptance_tars_meeet.sh` Sync 7 → end-to-end) + adds Sync 4 direct
  `curl -fsSI https://meeet.world/billing/tars` (accepts 200/301/302
  for A3 checkout liveness) + Sync 5 file-exists-OR-`BROTHER_RECONCILE_URL`-set
  (two valid resolutions per §3.A4) + Sync 6 `BROTHER_PAIR_TTL_ACK=yes`
  env-var check. Aggregate verdict PROCEED / BLOCK / PARTIAL with
  per-sync `✓` / `✗` / `⊘` rows and brief §<N>.<X> remediation pointer
  per red sync. Exit contract: 0 = all 7 green → proceed; 1 = any red
  → BLOCK GA tag cut; 2 = neither green nor red (prereq missing OR
  partial verdict from SKIP_LIVE=1). Env knobs: `BROTHER_PREFLIGHT_DRY_RUN=1`
  + `BROTHER_PREFLIGHT_SKIP_LIVE=1` + `BROTHER_PREFLIGHT_REPO=<path>`
  + `BROTHER_RECONCILE_URL=<url>` + `BROTHER_PAIR_TTL_ACK=yes` +
  `BROTHER_PREFLIGHT_NO_COLOR=1`. **17/17 green tests in ~0.16 s** —
  pins spec contract (header enumerates all 7 syncs verbatim, each
  sync names its primitive, PR #198 + §7 back-pointers present, 0/1/2
  exit contract documented, all 6 env overrides documented, Sync 6
  framed as "NOT v10 GA — heads-up only"), pins runtime under the
  full `BROTHER_PREFLIGHT_DRY_RUN=1` matrix (skip-live + no extras
  → exit 1 Sync 5 red; skip-live + owners → exit 2 partial; full
  dry-run + owners → exit 0 PROCEED; full dry-run no extras → exit 1;
  green path prints all 5 cookbook ritual pointers; red path surfaces
  §3.A4 remediation with both resolution paths), pins drift-catch
  (all 4 primitive scripts exist on main + `ALLOWED_SKIPS=1` tolerance
  in body + `record()` helper + `RESULTS` aggregation). Smoke verified
  pre-push: variant-1 (skip-live no extras) → exit 1; variant-2
  (skip-live + owners) → exit 2; variant-3 (pure dry-run + owners)
  → exit 0; variant-4 (pure dry-run no extras) → exit 1. **Closes
  the last "remembered ritual" gap on the v10 GA path.** Together
  with #214 + #215 + #216, the FIVE pre-tag ritual surfaces of GA
  (Apple pre-flight + Brother pre-flight + release + verify + soak)
  are all single-command executable with spec-pinned tests. The
  v10.0.0 GA path now has **zero** remembered probes left. Lands
  cleanly with or without PR #198 already merged.
- **W310-af** — added PR #216 (PH4 §3+§4 Apple pre-flight gate —
  `PREFLIGHT-APPLE-SIGN.command` + 12 spec-contract tests, +482
  LoC), lifting the active PR count to **30**. **THIRD IMPLEMENTER
  FOLLOW-UP** to the W310 planning surface. Picks the highest-
  leverage pre-tag prep from PR #199: the §3 + §4 checklists.
  Brief §4 says verbatim *"Catching a typo at this stage avoids
  a doomed tag cut"* — this script enforces that machine-checkable.
  Four gates verbatim from brief: §3.1 `security find-identity
  -v -p codesigning | grep "Developer ID Application"` (≥1 match,
  else re-import .p12), §3.2 `xcrun notarytool history
  --keychain-profile "${APPLE_NOTARY_PROFILE:-tars-notary}"`
  (success message, else re-run `store-credentials`), §3.3
  `test -f .env && grep -c "^APPLE_" .env` (≥3 APPLE_* keys,
  else re-provision from `.env.example`), §4 `gh secret list
  -R alxvasilevvv/tars-neural-cockpit` against the 6 hard-
  required secret names (`APPLE_CERTIFICATE`,
  `APPLE_CERTIFICATE_PASSWORD`, `APPLE_SIGNING_IDENTITY`,
  `APPLE_TEAM_ID`, `APPLE_ID`, `APPLE_PASSWORD`) in brief's
  order. For each red gate prints the exact remediation pointer
  from `APPLE_SIGNING_SETUP.md` / `APPLE_SIGNING_FOR_CURSOR.md`.
  Also prints the workflow-dispatch URL the operator clicks for
  the brief §4 manual-dispatch dry-run — does NOT trigger it
  itself (would burn a CI build minute on every pre-flight call;
  operator owns the click). Exit contract: 0 = all four green
  → may proceed; 1 = any red → block tag cut; 2 = prereq
  missing (not on macOS without `SKIP_LOCAL=1`; missing
  `security` / `xcrun` / `gh`). Env knobs: `PREFLIGHT_APPLE_DRY_RUN=1`
  + `PREFLIGHT_APPLE_SKIP_CI=1` + `PREFLIGHT_APPLE_SKIP_LOCAL=1`
  + `PREFLIGHT_APPLE_REPO=<path>` + `APPLE_NOTARY_PROFILE=<name>`
  + `GH_REPO=<owner/name>`. **12/12 green tests in ~0.09 s +
  1 skipped** (Darwin-only guard cannot fire on Mac) — pins
  spec contract (header documents §3.1/3.2/3.3 verbatim + §4 gh
  command verbatim + 6 secret names verbatim + 6 env-override
  names + 0/1/2 exit contract), pins required-secrets array
  contract (`REQUIRED_SECRETS=(...)` literally equals brief §4
  names in brief's order — secret list cannot silently drift),
  pins dry-run path (all-skipped → exit 0 + prints next-steps
  cookbook pointers to both sibling scripts), pins platform guard.
  Smoke verified pre-push: dry-run all-skipped → exit 0; skip-
  local + real `gh secret list` → exit 1, all 6 secrets correctly
  reported missing (expected pre-v10-GA state). Lands cleanly
  with or without PR #199 already merged. **Closes the pre-tag
  "remembered ritual" gap.** Together with #214 + #215 the FOUR
  ritual corners of GA (pre-flight + release + verify + soak)
  are all single-command executable with spec-pinned tests.

**W310 PLANNING SURFACE CLOSED ✅; IMPLEMENTER SURFACE OPENED — FIVE
HELPERS SHIPPED.** Pickup pointer for any agent landing in the meeet
workspace now lists all **32 active PRs** (27 planning + 5 implementer
follow-ups), all closed stacks, and points at this wave summary as the
single-page operator-readable W310 retrospective. The next implementer
session in any phase (PH2 voice / PH3 keyring + UX + mobile / PH4 sign
trio / PH5 real-data trio / PH6 sandbox / PH7 planner / PH8 marketplace
/ PH9 mobile trio / PH10 Claude polish / PH11 GA dock-down) opens to a
fully-specified brief with operator open questions, risk register, test
plan, dep matrix, and effort estimates.

The five implementer follow-ups shipped so far (W310-ad soak + W310-ae
Apple sign verify + W310-af Apple pre-flight + W310-ag Brother coord
pre-flight + W310-ah GA-COOKBOOK single-decision wrapper) together close
**all five** "remembered ritual" gaps AND the "remembered sequencing"
gap on the v10.0.0 GA execution path — Apple pre-flight → Brother
pre-flight → release → verify → soak — into single executable commands
with spec-pinned tests, AND collapse the two pre-tag gates into ONE
wrapper command that produces a single PROCEED / BLOCK / PARTIAL
verdict for *"may I tag v10.0.0?"*. Only the operator action items
(.p12 supply, secret push via GitHub UI, manual dispatch dry-run
click, blog post draft, drag-install on clean Mac) remain blocking
non-script work. The operator's GA cookbook now reduces to:

```bash
# Pre-tag decision (ONE wrapper, both gates)
bash scripts/GA-COOKBOOK.command          # → PROCEED / BLOCK / PARTIAL
# (if PROCEED) cut tag + run release pipeline
bash scripts/RELEASE-v10.0.command
# (operator) watch CI sign + notarize
# (operator) download signed .dmg on a clean Mac
bash scripts/VERIFY-APPLE-SIGNATURE.command <path-to-dmg>
# (operator) drag-install
bash scripts/SOAK-HOURLY.command          # cron, 72 h, auto-abort on 3-fail
# (72 h later)
bash scripts/SOAK-REPORT.command          # markdown verdict
# (if verdict green) tag v10.0.0
```

**Steps 1, 5, 7, 8 (now wrapped into step 1 via GA-COOKBOOK)** are
spec-pinned executable helpers shipped in this wave. **Steps 2 and 6**
were already scripted. Only **CI watch, manual download, drag-install,
and tag cut** remain manual ops — all unavoidably so by design. The
operator's pre-tag mental model is now **one bash command, one exit
code, one color-coded verdict**.

---

## What this wave does NOT touch

- **Production runtime code on `main`** — all sub-waves operate on PR branches.
- **`v10.0.0-rc.1` artifacts** — no installer rebuild required; rc1 still ships as cut.
- **Phase L semantics** — L0-L9 contracts unchanged; #191's L4.2 work is purely additive.
- **Operator decisions** — D1-D4 captured in W310-a and unchanged here.

W310 is **PR-hygiene and forensic-extraction wave only**. v10.0.0 GA
dock-down begins as soon as #187 + #188 (and ideally #189-#191) land on
`main`.
