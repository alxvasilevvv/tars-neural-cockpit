# W310 — Post-rc1 PR triage wave · summary

**Owner:** Cursor agent (Claude Opus 4.7) — autonomous orchestration window
**Window:** 2026-05-17 → 2026-05-18
**Lane:** PR hygiene + cross-cutting closeouts on top of `v10.0.0-rc.1`
**Branch home:** `cursor/post-rc1-master-plan` (PR #188), plus per-extraction branches
**Status:** ✅ All planning sub-waves landed; **37 PRs open awaiting operator merge** (27 planning + 10 implementer follow-ups, see W310-ad / W310-ae / W310-af / W310-ag / W310-ah / W310-ai / W310-aj / W310-ak / W310-al / W310-am). Planning surface fully closed — every implementer question from `v10.0.0-rc.1` through `v11` is spec'd; implementer execution surface opened with PR #214 + extended with PR #215 + extended with PR #216 (Apple pre-flight) + extended with PR #217 (Brother pre-flight) + **consolidated with PR #218** (GA-COOKBOOK single-decision pre-tag wrapper) + **extended with PR #219** (DOWNLOAD-AND-VERIFY-RELEASE single-decision post-tag wrapper) + **extended with PR #220** (BROTHER-POSTFLIGHT single-decision post-launch coord-health wrapper) + **extended with PR #221** (RELEASE-TAG-GUARD single-decision read-only tag-safety gate that sits between SOAK-REPORT and RELEASE-v10.0) + **extended with PR #222** (POST-INSTALL-SMOKE single-decision installed-binary health verdict that bridges Step 8a drag-install → Step 8b soak-cron-start) + **closed with PR #223** (FINAL-QA-VERDICT cookbook-uniform wrapper around the existing `FINAL-QA-GATE.command` W267 — normalises its 0/1 `GO`/`NO-GO` output to the 0/1/2 PROCEED/BLOCK/PARTIAL contract symmetric with every other GA helper, demotes any skipped step to AMBER so the codesign-skipped-because-TARS-app-not-installed false-green case surfaces as PARTIAL, adds per-step remediation pointers). The **five pre-tag-plus-post-tag ritual surfaces** of the GA tag (Apple pre-flight / Brother pre-flight / release / download+verify / soak) are now all single-command executable with spec-pinned tests; the **post-launch brother-coord health surface** (T+24-72 h) is now a single-command regression sweep; the **tag-cut decision point** (soak verdict + git state + CI freshness) is now a single read-only safety gate that refuses to let the operator type the destructive `RELEASE-v10.0` command until all 5 gates pass; the **post-install installed-binary health surface** (between drag-install + soak-cron-start) is now a single-command 4-gate verdict that refuses to let the operator start the 72 h soak cron until the install + backend + meeet bridge are all confirmed alive; and the **pre-tag QA mechanical-checks surface** (pytest + smoke + perf + codesign + bash -n + doc render + json/yaml + version consistency) is now a single-command verdict that catches the false-green case where `FINAL-QA-GATE.command` returns `GO` despite one or more steps having silently skipped. **All five ritual surfaces + the destructive op itself + the post-install bridge + the QA gate** are now symmetric single-decision wrappers: QA-verdict (#223) → pre-tag verify (#218) → tag-safety (#221) → pre-tag release → post-tag verify (#219) → post-install health (#222) → post-launch coord (#220), each producing one PROCEED/BLOCK/PARTIAL verdict. **No "remembered probes" AND no "remembered sequencing" AND no "remembered command typing" AND no "false-green skipped step" left on the v10.0.0 GA path before, at, or after the tag cut, or after the drag-install** — the operator's mental model reduces to *"did FINAL-QA-VERDICT exit 0? if yes, did Gate A exit 0? if yes, soak; did SOAK-REPORT verdict green AND Tag-Guard exit 0? if yes, RELEASE; did Gate B exit 0? if yes, drag-install; did POST-INSTALL-SMOKE exit 0? if yes, start SOAK-HOURLY cron + announce; did POSTFLIGHT exit 0 at T+24 h? if yes, close dock-down arc."*

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
| **W310-ai** | **Sixth implementer follow-up** — symmetric counterpart to W310-ah on the **post-tag** side. Collapses the **7-step manual chore** between *"CI signs+notarizes the `.dmg`"* and *"I trust this build"* into a single wrapper that produces a single PROCEED / BLOCK / PARTIAL verdict for Gate B. `scripts/DOWNLOAD-AND-VERIFY-RELEASE.command` (303 lines bash, +x) auto-detects arch (`arm64→aarch64` / `x86_64`) and canonical GH-Release tag (default `v10.0.0`, `RELEASE_TAG=v10.0.1` overrides), resolves owner/repo via `gh repo view`, confirms the release + arch-matched `.dmg` asset exist (refuses with remediation pointer if either missing — does not silently download nothing), downloads the `.dmg` into a per-pid `/tmp/tars-ga-download-<pid>/` via `gh release download`, computes + prints SHA-256 so the operator can cross-reference `.RELEASE-v10.0.txt` from the build machine, then **invokes `scripts/VERIFY-APPLE-SIGNATURE.command` (PR #215)** on the downloaded `.dmg` and passes through its 0/1/2 exit code verbatim. PROCEED path cleans up the tmp dir (or retains via `DOWNLOAD_VERIFY_KEEP=1` for drag-install). BLOCK path **force-keeps the `.dmg` for forensics** + points at PR #199 §7 rollback brief. PARTIAL path keeps the `.dmg` for retry. Env knobs `RELEASE_TAG` + `GH_REPO` + `RELEASE_ARCH` + `DOWNLOAD_VERIFY_KEEP` + `DOWNLOAD_VERIFY_DRY_RUN` + `DOWNLOAD_VERIFY_REPO` + `DOWNLOAD_VERIFY_NO_COLOR` + `DOWNLOAD_VERIFY_TMP_DIR` + `DOWNLOAD_VERIFY_SKIP_PLATFORM` + `DOWNLOAD_VERIFY_SKIP_TOOLS` — the last two are CI-smoke-only escape hatches that let Linux runners exercise the wrapper without macOS / without `gh` installed. **17/17 green spec tests in ~0.10 s + 2 platform-gated skips** — pins meta (exists+executable, shebang, `bash -n`), pins spec contract (the **7-step manual flow** is enumerated verbatim in the "Why this exists" block AND the **7-step wrapper collapse** is enumerated verbatim — so the manual-vs-automated diff is obvious in source AND the brief and script can't drift; sibling composition explicit (names PR #215); 0/1/2 exit contract documented; all 10 env knobs documented; default `RELEASE_TAG` matches GA target), pins composition (missing-sibling path exits 2 with PR #215 remediation pointer — fails safely, not silently — useful when this script is merged ahead of #215), pins runtime in fully-mocked mode (`DRY_RUN=1 SKIP_PLATFORM=1 SKIP_TOOLS=1` + stub sibling on disk → exit 0 + emits PROCEED verdict + dry-run trace; Linux CI can exercise this on every commit), pins arch detection (uname → canonical asset suffix; `RELEASE_ARCH` override wins; `RELEASE_TAG` override propagates into header banner + assumed asset name `TARS_<ver>_<arch>.dmg`), pins platform guard (structure present, `exit 2` before any real work, bypassable via `SKIP_PLATFORM` for CI), pins tool-dep loop (skippable via `SKIP_TOOLS`; missing-`gh` path exits 2 with `brew install gh` remediation when `gh` is absent), pins cleanup (`KEEP=1` short-circuits cleanup with retained-path note for drag-install), pins red-path (force-keeps `.dmg` + names PR #199 for rollback). Stub-sibling pattern: tests lay a minimal stub `VERIFY-APPLE-SIGNATURE.command` in a tmp dir and point `DOWNLOAD_VERIFY_REPO` at it, so tests don't need #215 already on main. Smoke verified pre-push: post-edit dry-run on macOS without sibling → exit 2 with PR #215 pointer (expected safe-failure state). **Together with PR #218 (Gate A wrapper) this closes the structural symmetry of the GA cookbook**: pre-tag verification is ONE wrapper command + ONE verdict; post-tag verification is ONE wrapper command + ONE verdict. The operator never types `codesign` / `spctl` / `stapler` / `gh release download` / `shasum` manually — every gate is a single bash command surfacing color-coded PROCEED / BLOCK / PARTIAL. Wrapper is purely additive: zero new deps (composes existing `#215` verify), zero changes to sub-gate scripts, zero changes to release pipeline. Hard dep: PR #215 must be on main before the wrapper resolves the sibling (if missing, wrapper exits 2 BLOCK with remediation pointer — fails safely, not silently). Lands cleanly with or without sub-gate already merged | PR #219; `scripts/DOWNLOAD-AND-VERIFY-RELEASE.command` + `tests/test_download_and_verify_release_script.py` |
| **W310-aj** | **Seventh implementer follow-up** — symmetric counterpart to W310-ag on the **post-tag** side. Where #217 BROTHER-PREFLIGHT runs **before** the tag to catch missing-prereqs at Gate A, this script runs **24-72 h after** the tag to detect real-world drift / silent regressions in the brother-coord surface. `scripts/BROTHER-POSTFLIGHT.command` (303 lines bash, +x) wraps the same 4 primitive scripts as #217 in regression-tag mode (Sync 1 A1 ingest re-verify, Sync 2 A2 balance re-verify, Sync 3 A5 auth e2e re-verify, Sync 6 acceptance suite re-run), runs `curl https://meeet.world/billing/tars` for A3 checkout liveness regression (Sync 4), and **elevates Sync 5 from existence-check to execution**: actually invokes `python3 scripts/reconcile-meeet-billing.py` (or `curl --max-time 30 -fsSI "${BROTHER_RECONCILE_URL}"` if the URL knob is set) so silent runtime errors in the daily reconcile pipeline surface as visible BLOCK instead of latent ledger-drift bugs. **6 syncs total, not 7** — drops PREFLIGHT Sync 6 (`BROTHER_PAIR_TTL_ACK`) because ph3-pair-ttl is a v10.2 backlog item whose ack only matters pre-tag (script enforces this drift-guard: any future re-addition of the env knob fires a test). All probes regression-tagged (header banner reads "post-tag regression check"); remediation pointers name brief §6 (post-launch playbook) so red verdicts route to the rollback A/B/C decision tree (A hotfix v10.0.1 / B partial rollback un-publish binaries / C full revert re-tag v10.0.0-rc.1). PROCEED next-steps explicitly **do NOT call `RELEASE-v10.0.command`** (differential vs preflight — tag is already cut by the time this runs); instead prints "post '✓ brother postflight green (T+24h)' comment on v10 GA tag PR" + "schedule T+72h re-run via cron" suggestion (with literal crontab one-liner appending to `.postflight/daily.log`). Exit contract: 0 = all 6 green → brother coord side of v10 GA healthy post-launch; 1 = ≥1 sync red → **BLOCK launch comms** (don't tweet "v10 is live") + decide rollback per brief §6; 2 = prereq missing OR partial verdict (SKIP_LIVE=1 left ≥1 sync unverified). Env knobs `BROTHER_POSTFLIGHT_DRY_RUN=1` + `BROTHER_POSTFLIGHT_SKIP_LIVE=1` + `BROTHER_POSTFLIGHT_REPO=<path>` + `BROTHER_RECONCILE_URL=<url>` + `BROTHER_POSTFLIGHT_NO_COLOR=1`. **21/21 green tests in ~0.07 s** — pins meta (executable + shebang + `bash -n`), pins spec contract (header enumerates all 6 syncs verbatim + 5 deltas from PREFLIGHT verbatim + 0/1/2 exit contract + all 5 env knobs + hard deps list + "fails safely not silently"), pins structural sync count (exact 6 `hdr "Sync N — …"` lines + `/ 6` summary denominator + no `BROTHER_PAIR_TTL_ACK` honored in runtime — silent re-addition guard), pins runtime under three dry-run variants (SKIP_LIVE + no reconcile resolution → rc=1 BLOCK with "no owner" Sync 5 red; SKIP_LIVE + URL set → rc=2 PARTIAL Sync 5 green via brother URL; pure dry-run + URL set + stubs → rc=0 PROCEED all 6 green), pins URL precedence over local `.py` (operator-set knob wins over silent file presence), pins differential check (PROCEED next-steps must NOT name `RELEASE-v10.0.command`; must include "Schedule a T+72h re-run via cron" pointer), pins platform guard (`REPO` override structure + curl-on-PATH gated by dry-run). Stub-sibling pattern (same isolation as preflight tests): tests lay minimal bash stubs for the 4 primitives in tmp dir + point `BROTHER_POSTFLIGHT_REPO` at it, so tests don't need real meeet.world infrastructure / real reconcile script. Smoke verified pre-push: 3 variants on real script (SKIP_LIVE no extras → rc=1 BLOCK; SKIP_LIVE+URL → rc=2 PARTIAL; full dry-run+URL → rc=0 PROCEED) all match expected contract. **Closes the post-launch brother-coord health gap** — together with #218 (Gate A) + #219 (Gate B) + this PR, the v10 GA tag-cut surface is now symmetric across **all four ritual corners**: pre-tag verify (Gate A wrapper) → pre-tag release → post-tag verify (Gate B wrapper) → post-tag health (this wrapper). The operator never re-runs probe-meeet-billing / CHECK-MEEET-LIVE / smoke / acceptance manually 24 h after launch — one bash command surfaces the full coord-health verdict with rollback guidance per-sync. Wrapper is purely additive: zero new deps, zero changes to sibling scripts, zero changes to release pipeline. Hard dep: 4 wrapped primitive scripts must exist on main (already do); reconcile resolution (TARS-side .py OR brother-side URL) — neither hard-required at script-land time; runtime fails safely with both-path remediation if both missing post-tag. Lands cleanly with or without PR #198 already merged | PR #220; `scripts/BROTHER-POSTFLIGHT.command` + `tests/test_brother_postflight_script.py` |
| **W310-al** | **Ninth implementer follow-up** — bridges Step 8a (operator drag-installs the verified `.dmg` into `/Applications/`) → Step 8b (operator starts the 72 h `SOAK-HOURLY` cron) with a single PROCEED / BLOCK / PARTIAL verdict for *"is the installed cockpit alive + serving the expected version + talking to the meeet bridge?"*. `scripts/POST-INSTALL-SMOKE.command` (380 lines bash, +x) runs 4 worst-of gates: Gate 1 = `/Applications/TARS.app` exists AND `defaults read .../Info CFBundleShortVersionString` matches `POST_INSTALL_SMOKE_EXPECTED_VERSION` (default `10.0.0`, override for patch tags); Gate 2 = `curl -sS --connect-timeout 3 --max-time 5 http://127.0.0.1:8765/api/health` succeeds within 5 retries × 2 s (retries cover post-launch warm-up); Gate 3 = health payload contains `"ok": true` AND `"service": "tars"` AND (unless `REQUIRE_MEEET=0`) `"meeet_ingest": true`; Gate 4 = `scripts/SMOKE-TEST.command` sibling reports `SMOKE TEST PASSED` with summary line (graceful AMBER fallback if sibling missing or output unrecognised; explicit `SMOKE TEST FAILED` / `ABORTED (backend down)` → RED). Verdict aggregation: any RED → rc=1 BLOCK (uninstall + re-download via #219 + investigate); any AMBER (skip-flag / dry-run / sibling-missing / `REQUIRE_MEEET=0`) with no RED → rc=2 PARTIAL (operator decides whether partial confidence is acceptable for dev / offline-mode installs; v10.0.0 GA tag requires all 4 GREEN); all GREEN → rc=0 PROCEED (prints exact `crontab -l ... | crontab -` one-liner for hourly soak schedule + lists 4 next steps SOAK-REPORT → RELEASE-TAG-GUARD → publish announce → BROTHER-POSTFLIGHT at T+24 h). **Critical invariant: destructively HARMLESS** — script does NOT uninstall `TARS.app`, does NOT kill the backend process, does NOT modify `/Applications/`, does NOT call `RELEASE-v10.0.command` or any other destructive sibling, does NOT call `defaults write` (only `defaults read` for version lookup), never invokes `rm -rf` / `launchctl unload` / `killall` / `pkill` / `mv /Applications/TARS.app` / `codesign --remove`. Two structural tests pin this with a regex deny-list: `test_runtime_does_not_call_destructive_operations` scans the runtime body for the full forbidden-operations list; `test_runtime_uses_defaults_read_not_write` requires read-only `defaults read` and forbids mutating `defaults write`. Env knobs `POST_INSTALL_SMOKE_DRY_RUN=1` (stub Gates 2-4 green for CI + smoke) + `POST_INSTALL_SMOKE_HOST=127.0.0.1:8765` (backend host:port override) + `POST_INSTALL_SMOKE_EXPECTED_VERSION=10.0.0` (override for patch tags) + `POST_INSTALL_SMOKE_SKIP_VERSION=1` (dev-build override → AMBER) + `POST_INSTALL_SMOKE_SKIP_FULL=1` (skip full SMOKE-TEST when LLM/meeet tokens absent → AMBER, refusing to silently let a partial install look like a full green) + `POST_INSTALL_SMOKE_REQUIRE_MEEET=1` (assert `meeet_ingest` true; set 0 for intentionally offline-only) + `POST_INSTALL_SMOKE_HEALTH_RETRIES=5` + `POST_INSTALL_SMOKE_HEALTH_INTERVAL=2` (Gate 2 retry tuning) + `POST_INSTALL_SMOKE_APP_PATH=/Applications/TARS.app` (test hook) + `POST_INSTALL_SMOKE_REPO=<path>` (test hook for sibling lookup) + `POST_INSTALL_SMOKE_SKIP_PLATFORM=1` (bypass Darwin guard for Linux CI smoke) + `POST_INSTALL_SMOKE_NO_COLOR=1`. **24/25 green tests in ~21.5 s + 1 platform-skipped on Darwin** — pins meta (exec + shebang + `bash -n`), pins spec contract (W310-al sub-wave marker + NINTH marker + all 4 gates verbatim + 0/1/2 exit contract + destructively-harmless framing with 3 NOT-invariants + all 12 env knobs + back-references to siblings #214 #218 #219 #220 #221 + SMOKE-TEST.command), pins structural sync count (exactly 4 `hdr "Gate N — ..."` runtime headers + no destructive operations in runtime + `defaults read` present + `defaults write` absent), pins runtime under dry-run baseline (all-AMBER → rc=2 PARTIAL), pins Gate 1 variants (missing app → rc=1 BLOCK with `DOWNLOAD-AND-VERIFY-RELEASE` remediation pointer; SKIP_VERSION → rc=2 PARTIAL), pins Gate 4 variants (sibling missing source-level branch verification → AMBER not RED; SKIP_FULL → PARTIAL; sibling FAILED via stub → BLOCK; sibling unknown output → AMBER), pins verdict-block semantics (PROCEED block names `SOAK-HOURLY` + `SOAK-REPORT` + `RELEASE-TAG-GUARD` + `BROTHER-POSTFLIGHT` + `crontab`; BLOCK block names `DOWNLOAD-AND-VERIFY-RELEASE` + `backend_tars_up.sh` + `MEEET_INGEST_URL` + PH4 §7 + PH11 §6 rollback decision tree; PARTIAL block explains all 4 skip causes), pins custom host + custom expected version appear in banner. Stub-sibling pattern: tests lay a minimal stub `scripts/SMOKE-TEST.command` in tmp dir that emits one of 4 verdict signatures (PASSED / FAILED / ABORTED / UNKNOWN) + point `POST_INSTALL_SMOKE_REPO` at it, so tests don't need real macOS app / real backend / real curl — `POST_INSTALL_SMOKE_DRY_RUN=1` stubs Gates 2-4 and `POST_INSTALL_SMOKE_SKIP_PLATFORM=1` lets Linux CI exercise the wrapper end-to-end. Smoke verified pre-push: 2 variants on real script (pure dry-run → rc=2 PARTIAL with full verdict block; missing app + closed port → rc=1 BLOCK with per-gate ✗ + remediation pointers + PH4/PH11 decision tree) all match expected contract. **Closes the ninth ritual gap on the v10.0.0 GA path** — the silent stretch between *"operator drag-installs the .dmg"* and *"operator starts the 72 h SOAK-HOURLY cron"* (currently bridged by eyeballing Activity Monitor, double-clicking SMOKE-TEST.command and reading 50+ rows looking for ✗ marks, or skipping smoke entirely and discovering 3 h later the cockpit was dead) reduces to *"did POST-INSTALL-SMOKE.command exit 0?"*. The full GA verification motion is now FIVE bash commands, FIVE exit codes, FIVE color-coded verdicts: `bash scripts/GA-COOKBOOK.command` (Gate A pre-tag) → `bash scripts/RELEASE-TAG-GUARD.command` (tag-cut decision) → `bash scripts/RELEASE-v10.0.command` (destructive) → `bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command` (Gate B post-tag artifact) → `bash scripts/POST-INSTALL-SMOKE.command` (post-install health) → `bash scripts/SOAK-HOURLY.command` cron 72 h → `bash scripts/SOAK-REPORT.command` (soak verdict) → `bash scripts/BROTHER-POSTFLIGHT.command` at T+24 h (post-launch coord health). Wrapper is purely additive: zero new deps, zero changes to sibling scripts (`SMOKE-TEST.command` unchanged — wrapped via output-parsing only), zero changes to release pipeline. Hard dep: `scripts/SMOKE-TEST.command` for Gate 4 (gracefully degrades to AMBER if missing — script lands cleanly with or without sibling present, with or without `TARS.app` installed). Lands cleanly with or without PR #197 / #214 / #218 / #219 / #220 / #221 already merged | PR #222; `scripts/POST-INSTALL-SMOKE.command` + `tests/test_post_install_smoke_script.py` |
| **W310-am** | **Tenth implementer follow-up** — closes the **last non-uniform verdict surface** on the GA tag-cut path. The existing `scripts/FINAL-QA-GATE.command` (W267, runs 8 mechanical pre-tag checks) returns 0/1 `GO`/`NO-GO` which loses the "all 8 green" vs "some skipped, none failed" distinction — `codesign_check` returns 0 AND simultaneously pushes a record into the SKIPPED array when `/Applications/TARS.app` is absent, so the operator can read `GO` without actually verifying signing (false-green on tag-cut). `scripts/FINAL-QA-VERDICT.command` (272 lines bash, +x) is a thin wrapper that invokes the sibling unchanged (backwards-compat preserved — `RELEASE-v10.0.command` keeps calling `FINAL-QA-GATE.command` directly today), parses the sibling's `Passed:/Skipped:/Failed:` block out of `.FINAL-QA-GATE.txt` (last run only — regression-tested with stale-PROCEED + fresh-BLOCK in same log), and re-emits the verdict in the cookbook-uniform 0/1/2 PROCEED/BLOCK/PARTIAL contract symmetric with #214 / #215 / #216 / #217 / #218 / #219 / #220 / #221 / #222. KEY value-add: **demotes any SKIPPED step → AMBER → PARTIAL (rc=2) even when the sibling exited 0** — catches the codesign-skipped-because-TARS-app-not-installed false-green case and any future skip. BLOCK block names every failed step verbatim + 8 per-step remediation pointers (e.g. "4/8 codesign → if not installed: drag /Applications/TARS.app, re-run #222 POST-INSTALL-SMOKE"). PROCEED block enumerates the full 8-step cookbook chain with PR-ref labels (#218, #221, #219, #222, #214, #220). Destructively HARMLESS invariant pinned by `test_runtime_does_not_call_destructive_operations` (strips echo-string content first so operator-informational hints don't false-trigger, then regex-scans for forbidden ops). 5 env knobs (`FINAL_QA_VERDICT_DRY_RUN` + `_REPO` + `_GATE_SCRIPT` + `_LOG` + `_NO_COLOR`). **28/28 green tests in ~0.31 s** — pins meta (exec + shebang + `bash -n`), pins spec contract (W310-am marker + TENTH marker + all 9 cookbook PR back-refs verbatim + W267 sibling reference + 0/1/2 exit contract + AMBER demotion semantics + per-step remediation docs + all 5 env knobs), pins structural drift guards (env overrides honored + Skipped: parsing wired + AMBER demotion code present + no destructive ops + no sibling mutation), pins runtime matrix (dry-run → PARTIAL; sibling-missing → BLOCK with W267 pointer; stub 8/0/0 → PROCEED with full cookbook chain echoed; stub 7/1/0 codesign-skipped → **PARTIAL** ← false-green fix; stub 6/0/2 → BLOCK with named failed steps + all 8 remediation pointers; worst-of: failure beats skipped; custom GATE_SCRIPT/LOG overrides honored; stale log: last go/no-go block only — regression guard), pins verdict-block UX (PROCEED enumerates 6 cookbook PRs; BLOCK back-references W267 brief; PARTIAL enumerates 5 skip-cause categories), pins banner sanity (echoes resolved repo/gate/log paths). Stub-sibling pattern: tests lay a minimal stub `FINAL-QA-GATE.command` in tmp dir + point `FINAL_QA_VERDICT_REPO` at it, so Linux CI exercises wrapper end-to-end without real pipeline. Smoke verified pre-push: 4 matrix variants all match expected contract. **Closes the tenth ritual gap on the v10.0.0 GA path** — the silent false-green in the mechanical-checks gate (currently bridged by operator squinting at sibling per-step bullets and counting `⚠` marks before deciding whether `GO` actually means GO) reduces to *"did FINAL-QA-VERDICT exit 0?"*. The full GA verification motion is now SIX single-command verdict gates. Wrapper is purely additive: zero new deps, zero changes to `FINAL-QA-GATE.command`, zero changes to release pipeline. Hard dep: W267 sibling (on main since W267); fails safely with rc=1 BLOCK if sibling missing (differs from #222's graceful AMBER because here the wrapped script IS the gate). Lands cleanly with or without PR #197 / #214 / #218 / #219 / #220 / #221 / #222 already merged | PR #223; `scripts/FINAL-QA-VERDICT.command` + `tests/test_final_qa_verdict_script.py` |
| **W310-ak** | **Eighth implementer follow-up** — closes the destructive-tag-cut decision point with a purely READ-ONLY safety gate that sits between `SOAK-REPORT.command` (which always exits 0 because the markdown IS the source of truth) and `RELEASE-v10.0.command` (which actually cuts + pushes the v10.0.0 GA tag). `scripts/RELEASE-TAG-GUARD.command` (425 lines bash, +x) runs 5 gates worst-of-5: Gate 1 = SOAK-REPORT verdict (greps `docs/qa/SOAK_v10.0.0.md` for one of the 4 known signatures emitted by SOAK-REPORT.command's `## 1. Verdict` section — authorised / blocked-incomplete / blocked-hardfail / no-data — and routes each to a distinct remediation hint); Gate 2 = `git symbolic-ref --short HEAD` must equal `main` (or whatever `TAG_GUARD_BRANCH` is set to); Gate 3 = `git status --porcelain` must be empty (catches the same condition `RELEASE-v10.0` catches in Step 2, but BEFORE `FINAL-QA-GATE` has to run); Gate 4 = `git rev-parse --verify --quiet refs/tags/v10.0.0` AND `git ls-remote --tags origin v10.0.0` must both be empty (local + remote freshness); Gate 5 = `gh run list --branch main --limit 1 --json status,conclusion,headSha` must return status=completed, conclusion=success, headSha matching local HEAD. Verdict aggregation: any RED → rc=1 BLOCK; any AMBER (gh missing / dry-run) with no RED → rc=2 PARTIAL; all GREEN → rc=0 PROCEED. **Critical invariant: destructively HARMLESS** — the script does NOT push a tag, does NOT modify git state, does NOT call `RELEASE-v10.0.command`. The whole point is to **refuse to let the operator type the tag command** until all 5 gates pass. Two structural tests pin this invariant: `test_runtime_does_not_call_git_tag` regex-scans the runtime body for forbidden `git tag v...` / `git push origin v...` patterns; `test_runtime_uses_ls_remote_not_fetch` forbids mutating `git fetch --tags` and requires read-only `git ls-remote --tags origin`. Env knobs `TAG_GUARD_DRY_RUN=1` (stub Gate 5 green) + `TAG_GUARD_SKIP_GH=1` (downgrades to PARTIAL) + `TAG_GUARD_REPO=<abs path>` (test hook + worktree) + `TARS_TAG_GUARD_REPORT=<path>` (override soak report path) + `TAG_GUARD_TAG=v10.0.0` (re-use for v10.0.1 / v10.1.0) + `TAG_GUARD_BRANCH=main` (override expected branch) + `TAG_GUARD_NO_COLOR=1`. **25/25 green tests in ~1.69 s** — pins meta (executable + shebang + `bash -n`), pins spec contract (W310-ak EIGHTH marker + all 5 gates named verbatim + 0/1/2 exit contract + destructively-harmless framing with 3 invariants + all 4 soak signatures named verbatim with line-wrap-tolerant anchors + all 7 env knobs + back-references to siblings #218 #219 #220), pins structural sync count (exactly 5 `hdr "Gate N — ..."` runtime headers + no mutating `git tag v...` / `git push origin v...` in runtime body + uses `git ls-remote` not `git fetch`), pins runtime Gate 1 variants (no report → BLOCK; blocked-incomplete → BLOCK with "72 samples" pointer; blocked-hardfail → BLOCK with "cursor/soak-v10-fix" pointer; no-data → BLOCK with "SOAK-HOURLY" pointer; unrecognised → BLOCK with "re-render" pointer), pins runtime Gates 2-4 variants (authorised + clean + skip-gh → PARTIAL; authorised + dirty tree → BLOCK with stash pointer; authorised + wrong branch → BLOCK with checkout pointer; authorised + tag exists → BLOCK with `git tag -d` pointer), pins verdict-block semantics (PROCEED prints `bash scripts/RELEASE-v10.0.command` for copy-paste + mentions DOWNLOAD-AND-VERIFY-RELEASE downstream + mentions BROTHER-POSTFLIGHT downstream; BLOCK says "do NOT run RELEASE-v10.0.command yet"; PARTIAL says "do NOT auto-run RELEASE-v10.0"), pins custom tag override (`TAG_GUARD_TAG=v10.0.1` routes through Gate 4 with the custom name). Stub-sibling pattern (real `git init -b main` in tmp dir + minimal soak report written to `docs/qa/SOAK_v10.0.0.md` matching one of the 4 canonical signatures + automatic `git add docs && git commit` so working tree stays clean unless test explicitly dirties it) — tests don't need real GA infrastructure. Smoke verified pre-push: PARTIAL path on real script in /tmp stub repo exits rc=2 with 4/5 gates green + Gate 5 amber, matching expected contract. **Closes the eighth ritual gap on the v10.0.0 GA path** — the destructive `RELEASE-v10.0.command` now sits behind two layers of read-only verification (#218 Gate A pre-tag + #221 tag-cut readiness). After this lands "may I cut v10.0.0 right now?" reduces to "did `RELEASE-TAG-GUARD.command` exit 0?". The full GA tag-cut motion is now THREE bash commands, THREE exit codes, THREE color-coded verdicts: `bash scripts/GA-COOKBOOK.command` (Gate A pre-tag readiness) → `bash scripts/RELEASE-TAG-GUARD.command` (tag-cut decision gate) → `bash scripts/RELEASE-v10.0.command` (destructive tag cut + push + build) → `bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command` (Gate B post-tag signature) → `bash scripts/BROTHER-POSTFLIGHT.command` (post-launch coord health). Wrapper is purely additive: zero new deps (uses only git + gh, both already required by existing GA scripts), zero changes to sibling scripts (#218 / #219 / #220 / RELEASE-v10.0 / SOAK-REPORT all unchanged), zero changes to release pipeline. Hard dep: SOAK-REPORT must have written `docs/qa/SOAK_v10.0.0.md` already (otherwise rc=1 BLOCK with "soak not yet run" pointer); `gh` on PATH for Gate 5 (otherwise rc=2 PARTIAL, NOT rc=1 — refusing to silently let a missing `gh` look like a green Gate 5). Lands cleanly with or without PR #197 / #214 / #218 / #219 / #220 already merged | PR #221; `scripts/RELEASE-TAG-GUARD.command` + `tests/test_release_tag_guard_script.py` |

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
> **Sub-waves ad+ae+af+ag+ah+ai+aj+ak+al open the implementer surface** — sequential
> follow-ups to planning briefs (PR #197 §5.A → PR #214 soak helper
> scripts; PR #199 §6.2 → PR #215 Apple signature verification helper;
> PR #199 §3+§4 → PR #216 Apple pre-flight gate; PR #198 §7 → PR #217
> Brother coord pre-flight gate; PR #216+#217 → PR #218 GA-COOKBOOK
> single-decision pre-tag wrapper; PR #215 + `gh release download` →
> PR #219 DOWNLOAD-AND-VERIFY-RELEASE single-decision post-tag wrapper;
> PR #198 §7 post-tag regression sweep → PR #220 BROTHER-POSTFLIGHT
> single-decision post-launch coord-health wrapper; SOAK-REPORT verdict +
> git/CI state → PR #221 RELEASE-TAG-GUARD read-only tag-cut decision
> gate; existing `SMOKE-TEST.command` + 4-gate composition → PR #222
> POST-INSTALL-SMOKE installed-binary health verdict bridging Step 8a
> drag-install → Step 8b soak-cron-start).
> Future implementer PRs append here as `W310-am`, `W310-an`, etc.,
> each cross-referenced to the planning brief it executes (or the
> helpers it composes). The W310 implementer pattern is now reproduced
> **nine times in a row**: pick the highest-leverage §X.Y operator-
> action (or the highest-leverage helper-composition opportunity),
> ship the pure-additive helper that turns "remembered ritual" or
> "remembered sequencing" into "single command", pin the spec
> contract in tests so brief and script can't drift. The nine helpers
> together collapse the v10.0.0 GA cookbook to **five single-decision
> verification wrappers** across all four verification axes — Gate A
> (pre-tag), Tag-Guard (tag-cut decision), Gate B (post-tag artifact),
> Post-Install (installed-binary health), and Postflight (post-launch
> coord health at T+24-72 h) — interleaved with one destructive
> operator command and one manual drag-install:
>
> ```bash
> bash scripts/GA-COOKBOOK.command                  # Gate A — pre-tag verdict
>                                                   # (Apple pre-flight + Brother pre-flight)
> bash scripts/FINAL-QA-VERDICT.command             # QA gate — pre-tag mechanical checks
>                                                   # (pytest + smoke + perf + codesign + bash -n
>                                                   #  + doc render + json/yaml + version consistency)
> bash scripts/RELEASE-TAG-GUARD.command            # Tag-Guard — tag-cut decision
>                                                   # (SOAK verdict + git state + CI freshness)
> bash scripts/RELEASE-v10.0.command                # destructive — only if Tag-Guard = 0
> # CI signs + notarizes (auto, no operator action)
> bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command  # Gate B — post-tag verdict
>                                                   # (download + sha256 + signature gates)
> # drag-install (manual Finder, one-time per release)
> bash scripts/POST-INSTALL-SMOKE.command           # Step 8b — installed-binary verdict
>                                                   # (app version + backend health + meeet bridge)
> bash scripts/SOAK-HOURLY.command                  # cron, 72 h — only if Post-Install = 0
> bash scripts/SOAK-REPORT.command                  # SOAK verdict (informs next Tag-Guard run)
> # (T+24-72 h, after public announce)
> bash scripts/BROTHER-POSTFLIGHT.command           # Postflight — brother coord health
>                                                   # (regression sweep on 6 syncs)
> ```
>
> All six verification gates produce **one bash command, one exit
> code, one color-coded PROCEED / BLOCK / PARTIAL verdict** with
> per-failure remediation pointers to the planning briefs. The full
> cookbook is **eleven sequential commands** end-to-end (1 QA-verdict +
> 1 Gate A + 1 Tag-Guard + 1 RELEASE + 1 CI sign+notarize + 1 Gate B +
> 1 drag-install + 1 Post-Install + 1 SOAK-HOURLY cron + 1 SOAK-REPORT
> + 1 Postflight at T+24h) with **six color-coded verdict-checkpoints**,
> every automatable command machine-checkable, every gate red/green
> rendered in color, every failure surfacing the exact remediation
> pointer from the brief. **The v10.0.0 GA path now has zero "remembered
> probes" AND zero "remembered sequencing" AND zero "remembered command
> typing" AND zero "false-green skipped step" left at any of QA-verdict,
> Gate A, Tag-Guard, Gate B, Post-Install, or Postflight** — the
> operator's verification motion is six wrapper commands, six exit
> codes, six color-coded verdicts — covering pre-tag QA mechanical
> checks (with skipped-step demotion), pre-tag readiness, tag-cut
> safety, post-tag artifact authenticity, post-install runtime health,
> and post-launch coord drift.

---

## Active PRs (37 open, all awaiting operator merge)

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
| **#219** | W310-ai DOWNLOAD-AND-VERIFY-RELEASE single-decision post-tag wrapper — `DOWNLOAD-AND-VERIFY-RELEASE.command` + 17 tests (**sixth implementer follow-up**) | W310-ai | green except known CI cache issue + 17/17 new tests pass + 2 platform-skipped in ~0.10 s | symmetric counterpart to #218 on the **post-tag** side; collapses the 7-step manual chore between *"CI signs+notarizes"* and *"I trust this build"* into ONE wrapper producing a single PROCEED / BLOCK / PARTIAL verdict for Gate B; auto-detects arch (uname `arm64→aarch64` / `x86_64`), canonical tag (default `v10.0.0`, `RELEASE_TAG` overrides), owner/repo via `gh repo view`; refuses with remediation pointer if release or arch-matched asset missing (no silent no-op); downloads `.dmg` via `gh release download` into per-pid tmp dir, computes + prints SHA-256 for cross-reference against `.RELEASE-v10.0.txt`, then invokes `scripts/VERIFY-APPLE-SIGNATURE.command` (PR #215) on the downloaded `.dmg` and passes through its 0/1/2 exit code verbatim; PROCEED cleans tmp dir (or retains via `DOWNLOAD_VERIFY_KEEP=1` for drag-install); BLOCK force-keeps `.dmg` for forensics + points at PR #199 §7 rollback; PARTIAL keeps `.dmg` for retry; 10 env knobs (including `DOWNLOAD_VERIFY_SKIP_PLATFORM` + `DOWNLOAD_VERIFY_SKIP_TOOLS` for Linux CI smoke); zero new deps (composes existing #215), zero changes to sibling script, zero changes to release pipeline; hard dep on PR #215 (fails safely with rc=2 + remediation pointer if missing); **closes the structural symmetry of the GA cookbook** — both verification gates (Gate A pre-tag via #218, Gate B post-tag via this PR) are now single-decision wrapper commands |
| **#220** | W310-aj BROTHER-POSTFLIGHT single-decision post-launch wrapper — `BROTHER-POSTFLIGHT.command` + 21 tests (**seventh implementer follow-up**) | W310-aj | green except known CI cache issue + 21/21 new tests pass in ~0.07 s | symmetric counterpart to #217 on the **post-tag** side; runs 24-72 h after the tag to detect real-world drift / silent regressions in the brother-coord surface; 6 syncs (drops PREFLIGHT Sync 6 `BROTHER_PAIR_TTL_ACK` — heads-up-only pre-tag knob, dropped by design; runtime drift-guard test prevents silent re-addition); Sync 5 **elevated from existence-check to execution** (actually invokes `python3 scripts/reconcile-meeet-billing.py` or HEAD-probes `BROTHER_RECONCILE_URL` so silent runtime errors in the daily reconcile pipeline surface as visible BLOCK instead of latent ledger-drift bugs); all probes regression-tagged; remediation pointers name brief §6 (post-launch playbook) so red verdicts route to rollback A/B/C decision tree (A hotfix v10.0.1 / B partial rollback / C full revert); PROCEED next-steps explicitly do NOT call `RELEASE-v10.0.command` (tag is already cut by the time this runs) + suggest cron T+72h re-run with literal one-liner appending to `.postflight/daily.log`; exit contract 0 green = brother coord healthy post-launch / 1 red = BLOCK LAUNCH COMMS + decide rollback / 2 prereq-missing-OR-partial; 5 env knobs (DRY_RUN + SKIP_LIVE + REPO + RECONCILE_URL + NO_COLOR); zero new deps (wraps 4 existing primitive scripts), zero changes to sibling scripts, zero changes to release pipeline; lands cleanly with or without PR #198 already merged; **closes the post-launch brother-coord health gap** — together with #218 (Gate A) + #219 (Gate B) the v10 GA tag-cut surface is now symmetric across **all four ritual corners** (pre-tag verify, pre-tag release, post-tag verify, post-tag health) |
| **#221** | W310-ak RELEASE-TAG-GUARD read-only tag-safety gate — `RELEASE-TAG-GUARD.command` + 25 tests (**eighth implementer follow-up**) | W310-ak | green except known CI cache issue + 25/25 new tests pass in ~1.69 s | closes the destructive-tag-cut decision point with a purely READ-ONLY safety gate that sits between `SOAK-REPORT.command` and `RELEASE-v10.0.command`; 5 gates worst-of (SOAK-REPORT verdict signature / current branch / clean tree / tag freshness local + remote / CI green on HEAD); destructively HARMLESS invariant pinned by 2 structural tests (no `git tag v...` / no `git push origin v...` / uses `git ls-remote` not `git fetch --tags`); routes each of the 4 known SOAK-REPORT signatures (authorised / blocked-incomplete / blocked-hardfail / no-data) to a distinct remediation hint; full env knob surface (DRY_RUN + SKIP_GH + REPO + TARS_TAG_GUARD_REPORT + TAG_GUARD_TAG for v10.0.1 re-use + TAG_GUARD_BRANCH + NO_COLOR); zero new deps (git + gh, both already required by existing GA scripts); zero changes to sibling scripts (#218 / #219 / #220 / RELEASE-v10.0 / SOAK-REPORT unchanged); zero changes to release pipeline; **closes the eighth ritual gap on the v10.0.0 GA path** — the destructive `RELEASE-v10.0.command` now sits behind two layers of read-only verification (#218 Gate A pre-tag + #221 tag-cut readiness); after this lands "may I cut v10.0.0 right now?" reduces to "did `RELEASE-TAG-GUARD.command` exit 0?" |
| **#222** | W310-al POST-INSTALL-SMOKE single-decision installed-binary health verdict — `POST-INSTALL-SMOKE.command` + 25 tests (**ninth implementer follow-up**) | W310-al | green except known CI cache issue + 24/25 new tests pass in ~21.5 s + 1 platform-skipped on Darwin | bridges cookbook Step 8a (operator drag-installs the verified `.dmg` into `/Applications/`) → Step 8b (operator starts the 72 h `SOAK-HOURLY` cron) with a single PROCEED / BLOCK / PARTIAL verdict for *"is the installed cockpit alive + serving the expected version + talking to the meeet bridge?"*; 4 worst-of gates (`/Applications/TARS.app` presence + `CFBundleShortVersionString` version match / `/api/health` reachable on `http://127.0.0.1:8765` with 5 retries × 2 s / health payload sanity `"ok":true` + `"service":"tars"` + optional `"meeet_ingest":true` / full `SMOKE-TEST.command` sibling probe with graceful AMBER fallback); destructively HARMLESS invariant pinned by 2 structural tests (no `rm -rf` / no `defaults write` / no `launchctl unload` / no `killall` / no `pkill` / no `mv /Applications/TARS.app` / no `codesign --remove` in the runtime body; uses `defaults read` only); 12 env knobs (DRY_RUN + HOST + EXPECTED_VERSION + SKIP_VERSION + SKIP_FULL + REQUIRE_MEEET + HEALTH_RETRIES + HEALTH_INTERVAL + APP_PATH + REPO + SKIP_PLATFORM + NO_COLOR); PROCEED block prints exact `crontab -l \| crontab -` one-liner for hourly soak schedule + names downstream `SOAK-REPORT` / `RELEASE-TAG-GUARD` / `BROTHER-POSTFLIGHT`; BLOCK block names `DOWNLOAD-AND-VERIFY-RELEASE` re-download + PH4 §7 + PH11 §6 rollback decision tree; PARTIAL block explains all 4 skip causes; zero new deps (wraps existing `SMOKE-TEST.command` via output-parsing only); zero changes to release pipeline; lands cleanly with or without `SMOKE-TEST.command` sibling or `TARS.app` install present; **closes the ninth ritual gap on the v10.0.0 GA path** — the silent stretch between drag-install + soak-cron-start (currently bridged by eyeballing Activity Monitor, double-clicking `SMOKE-TEST.command` and reading 50+ rows looking for ✗ marks, or skipping smoke entirely and discovering 3 h later the cockpit was dead) reduces to *"did POST-INSTALL-SMOKE.command exit 0?"*; the full GA verification motion is now FIVE single-command verdict gates interleaved with the destructive op + manual drag-install: GA-COOKBOOK (Gate A) → RELEASE-TAG-GUARD (tag decision) → RELEASE-v10.0 (destructive) → DOWNLOAD-AND-VERIFY-RELEASE (Gate B) → drag-install (manual) → POST-INSTALL-SMOKE (Step 8b) → SOAK-HOURLY cron 72 h → SOAK-REPORT → BROTHER-POSTFLIGHT at T+24 h |
| **#223** | W310-am FINAL-QA-VERDICT cookbook-uniform wrapper — `FINAL-QA-VERDICT.command` + 28 tests (**tenth implementer follow-up**) | W310-am | green except known CI cache issue + 28/28 new tests pass in ~0.31 s | closes the **last non-uniform verdict surface** on the GA tag-cut path. The existing `scripts/FINAL-QA-GATE.command` (W267, runs 8 mechanical pre-tag checks: pytest + SMOKE-TEST + perf + codesign + `bash -n` + doc-render + JSON/YAML parse + version consistency) returns 0/1 `GO`/`NO-GO` which loses the "all 8 green" vs "some skipped, none failed" distinction — specifically `codesign_check` returns 0 AND simultaneously pushes a record into the SKIPPED array when `/Applications/TARS.app` is absent, so the operator can read `GO` without actually verifying signing (false-green on tag-cut). This wrapper invokes the sibling unchanged (backwards-compat preserved — `RELEASE-v10.0.command` keeps calling `FINAL-QA-GATE.command` directly today, future patch tag can flip the call site to this wrapper without touching the destructive release script), parses the sibling's `Passed:/Skipped:/Failed:` block out of `.FINAL-QA-GATE.txt` (last run only — pinned by a regression test that lays a stale PROCEED block + fresh BLOCK block in the same log to catch the case where a refactor reads the wrong block), and re-emits the verdict in the cookbook-uniform 0/1/2 PROCEED/BLOCK/PARTIAL contract symmetric with #214 / #215 / #216 / #217 / #218 / #219 / #220 / #221 / #222. The KEY value-add: **demotes any SKIPPED step → AMBER → PARTIAL (rc=2) even when the sibling exited 0**, catching the codesign-skipped-because-TARS-app-not-installed false-green and any future skip. BLOCK block names every failed step verbatim from the sibling log + adds per-step remediation pointers for all 8 known steps (e.g. "4/8 codesign → if not installed: drag /Applications/TARS.app, re-run #222 POST-INSTALL-SMOKE"). PROCEED block enumerates the full 8-step cookbook chain with PR-ref labels (#218, #221, #219, #222, #214, #220) — operator has copy-pasteable next commands without remembering the order. Destructively HARMLESS invariant pinned by `test_runtime_does_not_call_destructive_operations` which strips echo-string content first so operator-informational hints like `echo "...bash RELEASE-v10.0..."` don't false-trigger as actual invocations, then regex-scans for `git tag v` / `git push origin v` / `rm -rf` / `launchctl` / `killall` / `mv /Applications/TARS.app` / `bash...RELEASE-v10.0.command` (actual invocation). 5 env knobs (FINAL_QA_VERDICT_DRY_RUN + FINAL_QA_VERDICT_REPO + FINAL_QA_VERDICT_GATE_SCRIPT + FINAL_QA_VERDICT_LOG + FINAL_QA_VERDICT_NO_COLOR). Stub-sibling pattern: tests lay a minimal stub `FINAL-QA-GATE.command` in a tmp dir + point `FINAL_QA_VERDICT_REPO` at it, so Linux CI can exercise the wrapper end-to-end without a real pytest/SMOKE-TEST/perf/codesign pipeline. Smoke verified pre-push: 4 matrix variants (dry-run → PARTIAL; sibling-missing → BLOCK; stub 8/0/0 → PROCEED; stub 7/1/0 codesign-skipped → **PARTIAL** ← the false-green fix; stub 6/0/2 → BLOCK with per-step remediation) all match expected contract. **Closes the tenth ritual gap on the v10.0.0 GA path** — the silent false-green in the mechanical-checks gate (currently bridged by the operator squinting at the sibling's per-step bullets and counting `⚠` marks before deciding whether `GO` actually means GO) reduces to *"did FINAL-QA-VERDICT exit 0?"*. The full GA verification motion is now SIX single-command verdict gates: FINAL-QA-VERDICT (pre-tag mechanical-checks) → GA-COOKBOOK (Gate A pre-tag readiness) → RELEASE-TAG-GUARD (tag decision) → RELEASE-v10.0 (destructive) → DOWNLOAD-AND-VERIFY-RELEASE (Gate B post-tag) → drag-install (manual) → POST-INSTALL-SMOKE (Step 8b) → SOAK-HOURLY cron 72 h → SOAK-REPORT → BROTHER-POSTFLIGHT at T+24 h. Wrapper is purely additive: zero new deps (composes existing W267 sibling), zero changes to `FINAL-QA-GATE.command`, zero changes to release pipeline. Hard dep: `scripts/FINAL-QA-GATE.command` (W267, on `main` since W267 → satisfied today); fails safely with rc=1 BLOCK + remediation pointer if sibling missing (differs from #222's graceful AMBER fallback because here the wrapped script IS the gate, not one of 4 gates — cannot make a GA decision without it). Lands cleanly with or without PR #197 / #214 / #218 / #219 / #220 / #221 / #222 already merged |

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

**Implementer follow-ups (#214, #215, #216, #217, #218, #219, #220, #221, #222, #223):**
also independent at file level (all ten pure additive — `scripts/*` +
`tests/*` only, zero edits to `RELEASE-v10.0.command` or any other
already-shipped script). All land cleanly with or without their parent
planning brief already merged. Merge any time; landing them early just
means the operator has executable helpers when the GA window opens.
The cookbook collapses to **six single-decision wrapper commands + one
destructive release command + one soak cron pair**, each producing
exactly one `PROCEED`/`BLOCK`/`PARTIAL` verdict (exit `0`/`1`/`2`),
each surfacing exact remediation pointers from the planning briefs:

1. **QA gate (pre-tag mechanical checks)** — `bash scripts/FINAL-QA-VERDICT.command` (#223, wraps existing W267 `FINAL-QA-GATE.command`) — single PROCEED/BLOCK/PARTIAL verdict for *"do all 8 mechanical QA checks pass without silently skipping?"* Demotes any SKIPPED step (e.g. `codesign_check` when `/Applications/TARS.app` is absent) to AMBER → PARTIAL so the false-green case surfaces instead of hiding under the sibling's `GO` exit.
2. **Gate A (pre-tag prereq verify)** — `bash scripts/GA-COOKBOOK.command` (#218, composes #216 + #217) — single PROCEED/BLOCK/PARTIAL verdict for *"are Apple sign + brother coord prereqs all green?"*
3. **Tag-safety gate (read-only decision point)** — `bash scripts/RELEASE-TAG-GUARD.command` (#221) — single PROCEED/BLOCK/PARTIAL verdict for *"is it safe to type `bash scripts/RELEASE-v10.0.command` right now?"* Checks soak verdict + git clean + tag-not-already-pushed + CI freshness. Read-only by design — refuses to let the operator near the destructive op until all 5 gates pass.
4. **Release (the only destructive op)** — `bash scripts/RELEASE-v10.0.command` (already shipped, W264) — cuts the tag + triggers signing + notarization. The single destructive command in the entire cookbook.
5. **Gate B (post-tag artifact verify)** — `bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command` (#219, composes #215 + `gh release download`) — single PROCEED/BLOCK/PARTIAL verdict for *"do I trust this just-cut build?"*
6. **Post-install health (drag-install → soak-cron bridge)** — `bash scripts/POST-INSTALL-SMOKE.command` (#222, wraps W267 `SMOKE-TEST.command` with verdict normalisation + remediation) — single PROCEED/BLOCK/PARTIAL verdict for *"is the installed binary + backend + meeet bridge alive enough to start the 72 h soak cron?"*
7. **Soak (72 h GA window)** — `bash scripts/SOAK-HOURLY.command` (cron) + `bash scripts/SOAK-REPORT.command` (#214) drive the GA soak window with auto-abort on 3-consec-fail and markdown verdict at the end.
8. **Postflight (post-launch coord health at T+24-72 h)** — `bash scripts/BROTHER-POSTFLIGHT.command` (#220) — single PROCEED/BLOCK/PARTIAL verdict for *"is brother coord still healthy 24 h after launch?"* with rollback A/B/C remediation if any sync red.

Steps 1+2+3+4+5+6+7+8 = **six single-decision wrapper commands + one
destructive release command + one soak cron pair**, each spec-pinned
with the matching `tests/test_*_script.py` suite, each machine-checkable
in <30 s (modulo the 72 h soak window itself), each surfacing exact
remediation pointers from the planning briefs on `BLOCK`/`PARTIAL`.
**Zero "remembered probes" AND zero "remembered sequencing" AND zero
"remembered command typing" AND zero "false-green skipped step" remain
across the pre-tag QA mechanical gate, pre-tag prereq verify, tag-safety
decision point, post-tag artifact verify, post-install health bridge,
soak window, AND post-launch coord-health phases.**

### Operator one-shot merge sequence

For the operator who prefers a single shell-script merge of the entire
37-PR fleet (instead of clicking each PR individually in the GitHub
UI), the optimal order — derived from the dependency analysis above —
is the following bash block, copy-paste-ready:

```bash
# Tier 0 (root): unblocks every subsequent merge by fixing the
# qa-agent.yml workflow-cache cache that has been stale since
# 2026-05-13 (see W310-c CI diagnosis). Must merge first.
gh pr merge 188 --squash --delete-branch

# Tier 1 (W309 step 1 runtime restore): unblocks step 2 implementation
# surface. Best landed second so the live cockpit comes back online.
gh pr merge 187 --squash --delete-branch

# Tier 2 (W309 step 2 Playwright scaffold, draft): best landed AFTER
# #187 so the suite opens green instead of skipping. Manually mark
# ready-for-review first via `gh pr ready 189`.
gh pr ready 189 && gh pr merge 189 --squash --delete-branch

# Tier 3 (runtime PR rebuilds from triage): file-level independent
# of each other and of all tier-4/tier-5 PRs; any order.
for pr in 190 191; do gh pr merge "$pr" --squash --delete-branch; done

# Tier 4 (planning-surface briefs g→ad): 22 docs-only PRs, fully
# independent at file level (each touches a distinct
# docs/handoff/<NAME>.md). Order doesn't matter.
for pr in 192 193 194 195 196 197 198 199 200 201 \
          202 203 204 205 206 207 208 209 210 211 \
          212 213; do
  gh pr merge "$pr" --squash --delete-branch
done

# Tier 5 (implementer helpers ae→am): 10 PRs, pure additive
# scripts/* + tests/* — no shared paths with each other or with any
# other PR. Order doesn't matter. Each is a self-contained
# scripts/<NAME>.command + tests/test_<name>_script.py addition.
for pr in 214 215 216 217 218 219 220 221 222 223; do
  gh pr merge "$pr" --squash --delete-branch
done
```

This sequence covers all 37 open PRs in roughly **20-30 min** of
operator wall-clock time (most of which is just waiting for the
GitHub merge queue + CI re-runs after #188 lands). After PR #188
merges, the qa-agent.yml workflow-cache fix propagates to every
subsequent PR run, so every PR in tiers 1-5 will go green on the
next push or merge attempt.

**Dependency reality check:**

- **Only PR #188 has a hard root dependency** — every other merge
  benefits from it landing first (because the workflow-cache fix
  re-enables green CI on subsequent PR runs).
- **PR #187 → step-2 implementation** is a runtime dependency, not a
  merge dependency — #189 (scaffold) and the step-2 implementation
  itself need #187, but #189's merge order vs #187 doesn't matter
  beyond the green-vs-skipping suite cosmetic.
- **All Tier 4 + Tier 5 PRs are file-level independent** — they touch
  distinct paths (`docs/handoff/<BRIEF>.md` for briefs, `scripts/<NAME>.command`
  + `tests/test_<name>_script.py` for helpers). The 32-PR batch can land
  in any order with zero rebase risk and zero shared-file conflict risk.
- **No implementer helper depends on its parent brief landing first** —
  the briefs are pure docs and the helpers are pure scripts; they
  intentionally don't cite each other across tree-state (briefs cite
  helpers by filename only, which exists once the helper PR is merged).

If the operator prefers a one-shot single-screen experience (paste
the whole block above, walk away, come back to a clean queue), the
script above is the optimal sequence. If the operator prefers manual
PR-by-PR review (e.g. to read each implementer brief in the GitHub
UI before merging), the tier ordering above still applies but each
`gh pr merge` becomes a click.

**The planning surface is fully closed after PR #213.** Every
implementer question from v10.0.0-rc.1 through v11 has a brief on
disk:

- v10.0.0 GA: #197 (QA sweep) + #198 (brother handoff) + #199 (Apple sign)
- v10.1: #193 (PH2 STT) + #194 (PH2 voice gallery) + #195 (PH3 keyring) + #196 (PH3 pairing UX) + #200 (PH4 Windows) + #201 (PH4 updater)
- v10.2: #202 (PH5 vault) + #203 (PH5 policy UI) + #204 (PH5 telemetry) + #211 (PH3 mobile pairing) + #212 (PH4 Linux optional)
- v11: #205 (PH6 sandbox) + #206 (PH7 planner UI) + #207 (PH8 marketplace) + #208 (PH9 iOS) + #209 (PH9 Android) + #210 (PH9 native speech)
- Continuous: #213 (PH10 Claude polish backlog, 13 items spread across v10.0 → v11)

---

## Operator one-shot GA cookbook execution sequence

**Audience:** the operator on tag-cut day, **after** all 37 W310 PRs
have been merged via the "Operator one-shot merge sequence" subsection
above. The merge playbook compresses 37 PR decisions into 1 paste
action; **this playbook compresses 11 tag-cut decisions into 1 paste
action with only 2 unavoidable operator-required pause points** (one
for destructive tag-cut confirmation, one for the manual drag-install
step). All 9 other steps are either auto-verifying single-decision
wrapper commands (PROCEED/BLOCK/PARTIAL with exit `0`/`1`/`2`) or
unavoidable CI wait (Step 5: sign + notarize the just-cut tag).

The cookbook below is the runtime parallel to the merge sequence
above: copy-paste-ready, pauses only at unavoidable manual
checkpoints, fails loudly with remediation pointers if any verdict is
`BLOCK`, fails amber if any verdict is `PARTIAL` so the operator can
decide whether to push through partial confidence or fix the
underlying skip cause. Every `BLOCK` exit aborts the playbook with
the `set -e` semantics implicit in each `|| { … ; exit 1; }` arm.

### Phase A — pre-tag verification (read-only, no destructive ops)

```bash
# Step 1/11: QA gate — 8 mechanical checks (pytest + smoke + perf +
#            codesign + bash -n + doc render + json/yaml + version
#            consistency) must all PASS without silent skip. Demotes
#            any SKIPPED step to AMBER → PARTIAL so the false-green
#            case (e.g. codesign skipped because /Applications/TARS.app
#            not installed) surfaces as rc=2 instead of hiding under
#            the sibling FINAL-QA-GATE's GO exit.
bash scripts/FINAL-QA-VERDICT.command || {
  echo "QA gate failed — see remediation pointers above; do NOT"
  echo "proceed to Step 2 until rc=0."
  exit 1
}

# Step 2/11: Pre-tag prereq verify — Apple sign keychain + 6 GH secrets
#            + brother coord (7-sync convergence). Worst-of-two
#            aggregation (Apple x Brother). PARTIAL acceptable on
#            non-Mac host but Mac host MUST exit 0 to cut a signed
#            build.
bash scripts/GA-COOKBOOK.command || {
  echo "Gate A failed — see per-sub-gate remediation pointers; do NOT"
  echo "proceed to Step 3 until rc=0."
  exit 1
}

# Step 3/11: Tag-cut safety gate — soak verdict + branch = main +
#            git working tree clean + tag not already pushed locally
#            or remotely + last CI run on main green at HEAD sha.
#            Read-only by design; refuses to let the operator type
#            the destructive Step 4 command until all 5 gates pass.
bash scripts/RELEASE-TAG-GUARD.command || {
  echo "Tag-Guard failed — do NOT type Step 4 until rc=0."
  exit 1
}
```

### Phase B — destructive tag-cut (operator-confirmed)

```bash
# Step 4/11: ⚠️ DESTRUCTIVE — cuts v10.0.0 tag, pushes to origin,
#            triggers release.yml CI workflow (sign + notarize +
#            upload .dmg asset). Only proceed if Steps 1+2+3 all
#            exited 0. PAUSE POINT 1 of 2: operator must type 'yes'.
read -r -p "All pre-tag gates green. Cut v10.0.0 tag now? Type 'yes' to confirm: " confirm
[[ "$confirm" == "yes" ]] || { echo "aborted by operator"; exit 1; }
bash scripts/RELEASE-v10.0.command

# Step 5/11: Wait for CI sign+notarize (~25-40 min wall-clock).
#            Auto-watch via gh CLI:
gh run watch --exit-status --interval 30 \
  "$(gh run list --branch main --workflow release.yml --limit 1 \
       --json databaseId --jq '.[0].databaseId')"
# … or open https://github.com/alxvasilevvv/tars-neural-cockpit/actions
# and monitor the release.yml run manually if you prefer to use the UI.
```

### Phase C — post-tag verification + install + soak start

```bash
# Step 6/11: Gate B — post-tag artifact verify. Downloads the .dmg
#            from the just-cut release, computes SHA-256 (operator
#            can cross-reference against .RELEASE-v10.0.txt from the
#            build machine), runs the three Apple signature gates
#            (codesign --verify --deep --strict + spctl --assess
#            --type execute + stapler validate). On red exit, force-
#            keeps the .dmg in /tmp/tars-ga-download-<pid>/ for
#            forensics.
bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command || {
  echo "Gate B failed — see PR #199 §7 rollback A/B/C decision tree;"
  echo "do NOT drag-install until rc=0."
  exit 1
}

# Step 7/11: ⚠️ MANUAL — drag the verified .dmg to /Applications/.
#            Path printed by Step 6 (typically
#            /tmp/tars-ga-download-<pid>/TARS_10.0.0_<arch>.dmg).
#            Open Finder, drag the .dmg, double-click to mount, drag
#            TARS.app to /Applications/, eject the mounted volume.
#            PAUSE POINT 2 of 2: operator must type 'installed'.
read -r -p "TARS.app installed in /Applications/? Type 'installed' to continue: " confirm
[[ "$confirm" == "installed" ]] || { echo "aborted by operator"; exit 1; }

# Step 8/11: Post-install health bridge — verifies app version +
#            backend health on 127.0.0.1:8765 + meeet_ingest bridge
#            + full SMOKE-TEST sibling. Refuses to let the operator
#            start the 72 h soak cron until the installed binary is
#            confirmed alive on all four gates.
bash scripts/POST-INSTALL-SMOKE.command || {
  echo "Post-install BLOCK — uninstall TARS.app, re-download via #219,"
  echo "and investigate (most common cause: backend wasn't restarted"
  echo "after install; try open -a TARS.app && sleep 5 && re-run)."
  exit 1
}

# Step 9/11: Schedule 72 h soak window via cron (1 sample/hour, auto-
#            abort after 3 consecutive failures, writes JSON-per-line
#            to .soak/hourly.log). Idempotent — re-running this step
#            does not duplicate the cron entry.
crontab -l 2>/dev/null | grep -qE 'SOAK-HOURLY\.command' || {
  ( crontab -l 2>/dev/null
    echo "0 * * * * cd $PWD && bash scripts/SOAK-HOURLY.command \\"
    echo "  >> .soak/cron.log 2>&1"
  ) | crontab -
}
echo "✓ 72 h soak window started; tail .soak/cron.log periodically."
```

### Phase D — post-launch coord health (T+24-72 h)

```bash
# Step 10/11: At T+72 h, render the soak verdict markdown to
#             docs/qa/SOAK_v10.0.0.md. Re-running RELEASE-TAG-GUARD
#             after this picks up the new verdict via its Gate 1
#             (greps docs/qa/SOAK_v10.0.0.md for the canonical
#             "authorised" / "blocked-*" signatures).
bash scripts/SOAK-REPORT.command

# Step 11/11: Post-launch brother coord regression sweep at T+24 h
#             (and again at T+72 h if T+24 h was green). Confirms
#             billing + balance + auth + checkout + reconcile +
#             acceptance suite all still green against real
#             meeet.world traffic. Red verdict → BLOCK launch comms
#             + decide rollback per PH4 §7 + PH11 §6 (hotfix v10.0.1
#             OR partial rollback un-publish binaries OR full revert
#             re-tag v10.0.0-rc.1).
bash scripts/BROTHER-POSTFLIGHT.command
```

### Phase E — tag promotion (operator decision, no helper wrapper)

If Steps 1-11 all exited 0, the operator may promote `v10.0.0` from
rc to stable: update `https://meeet.world/tars` download links, draft
the announce post (PH10 #213 backlog item #4 + #11), merge any
remaining v10.0.0 PR threads, archive the rc tag. **This is the only
step that intentionally has no single-command wrapper** — the
announce post is a Claude-design lane artefact (PH10 #213, tier-1
batch "v10 landing brand pass"), download-link promotion is a
brother-side ops task (PH11 #198 §6.B), and tag archival is a one-off
`git tag -d` / `git push origin :refs/tags/...` operator decision.
All three are tracked outside the W310 helper fleet for separation-of-
concerns reasons.

### Total runtime budget

| Phase | Operator-active time | Wall-clock |
| ----- | -------------------- | ---------- |
| **A** (read-only verifies) | ~30 s | ~30 s |
| **B** (destructive + CI wait) | ~10 s (one `read`) | ~25-40 min (mostly CI) |
| **C** (Gate B + drag-install + post-install + soak schedule) | ~3-5 min (drag-install dominant) | ~5-7 min |
| **D** (after 72 h soak window) | ~10 s at T+24 h + ~10 s at T+72 h | 72 h passive |
| **E** (tag promotion) | operator-paced (typically same day, parallel to Phase D) | n/a |

**Wall-clock window from Step 1 to Step 9: ~30-50 min active.**
**Wall-clock window from Step 9 to Step 11 completion: 72 h passive.**

### Pause points (the only times the operator types something)

1. **Step 4** — type `yes` to cut the v10.0.0 tag.
2. **Step 7** — type `installed` after dragging `TARS.app` to
   `/Applications/`.

That's it. All other steps either run automatically (Phases A, D, E
if all gates green) or unavoidably wait for CI (Step 5). Compare with
the pre-W310 operator burden: ~11 separate decisions, ~11 separate
commands to type correctly, plus ~30 manual probes that had to be
remembered (codesign + spctl + stapler against the right `.app`;
sha256 cross-check; backend on 127.0.0.1:8765; meeet bridge live; soak
cron registration; soak verdict markdown signature; brother coord
re-verify at T+24 h; …). **W310 compresses the GA tag-cut motion
from ~30 remembered probes + ~11 commands into 2 operator
confirmations** spread across an ~45-minute active window plus the
unavoidable 72 h soak.

### Rollback playbook (if any gate exits BLOCK mid-cookbook)

The `|| { …; exit 1; }` guard on every verdict gate ensures the
cookbook **stops before any further destructive op** if a `BLOCK` is
hit. The rollback decision tree differs by phase:

- **Phase A `BLOCK` (Step 1/2/3)** — pre-tag. **Zero rollback** —
  nothing has shipped yet. Fix the underlying issue (per remediation
  pointer printed by the failing gate), re-run the failed step.
- **Phase B `BLOCK` (Step 4 destructive failed)** — **PR #199 §7
  decision tree path A** (pre-tag): `git tag -d v10.0.0` locally,
  no remote push happened yet, no rollback comms needed.
- **Phase C `BLOCK` (Step 6 Gate B failed)** — **PR #199 §7 decision
  tree path B** (post-tag-pre-publish): `gh release delete v10.0.0
  --yes && git push --delete origin v10.0.0 && git tag -d v10.0.0`.
  CI may have already signed the binary; un-publish before any user
  downloads it.
- **Phase C `BLOCK` (Step 8 Post-install failed)** — **PR #199 §7
  decision tree path C** (Intel-only signing flake) **OR** path D
  (corrupted .p12). Triage cause first; usually fixable without
  re-tag (re-download via #219, re-install). If hard-blocked,
  un-publish per path B and re-tag as `v10.0.0-rc.2`.
- **Phase D `BLOCK` (Step 10 SOAK-REPORT verdict blocked-hardfail
  OR Step 11 BROTHER-POSTFLIGHT red)** — **PR #198 §6 launch decision
  tree**:
    - **A: hotfix v10.0.1** — keep v10.0.0 published, ship the fix
      ASAP. Best path if only 1-2 syncs red and root cause is
      identified.
    - **B: partial rollback** — un-publish binaries but keep tag.
      Best path if any user data integrity risk surfaces during soak.
    - **C: full revert** — un-publish binaries + delete tag + re-tag
      as `v10.0.0-rc.2`. Best path if multiple gates red AND root
      cause is structural (e.g. brother-side endpoint broke our
      contract).

The cookbook above does **not** auto-execute any rollback path. By
design — rollback is operator-decision territory (which of A/B/C
applies depends on the failure mode + downstream impact + comms
timing), not a machine-checkable verdict. The rollback playbook is
docs-only on purpose; future implementer follow-up may revisit if a
single rollback path becomes mechanical enough to wrap.

---

## Operator dry-run rehearsal matrix

**Audience:** the operator one or more days **before** tag day, who
wants to flush orchestration bugs (sibling path drift, env-var name
typos, log file path mismatches, color-output glitches, exit-code
contract drift introduced by a sibling refactor) **at zero cost**
instead of discovering them mid-tag-cut at high cost.

Every helper in the GA cookbook ships with a `*_DRY_RUN=1` env knob
that short-circuits real-world I/O (no `gh release download`, no
`security find-identity`, no `curl https://meeet.world/...`, no
`spctl --assess`) while still exercising the full orchestration
runtime: arg parsing, sibling resolution, env-knob propagation, exit
contract, color-coded output, remediation pointer rendering. A
rehearsal-day operator pasting the block below in ~30 s of wall-clock
gets either:

- **All-green-or-amber matrix** — orchestration is mechanically sound
  on the current state of `main`. Tag day will execute as planned.
- **Any unexpected RED matrix** — drift detected. Read the printed
  reason, fix the underlying issue (rebase, update sibling path, fix
  env name), re-run rehearsal until all-green-or-amber. Costs nothing
  because no destructive op is gated behind the rehearsal verdict.

The matrix below documents per helper: the dry-run env-knob recipe,
the expected exit code in dry-run mode (always `2` PARTIAL because
stubs cannot produce green real-world verdicts), the expected stdout
substring to confirm the helper actually ran end-to-end (not just
exited early on a missing dep), and the drift signal — what's likely
broken if the matrix row doesn't match.

```bash
# Pre-tag dry-run rehearsal — paste this block before tag day.
# Exits 0 if all 6 helpers passed orchestration; 1 if any helper
# regressed (drift detected, fix before tag day).

set +e  # need to inspect each exit code individually
PASSED=0; AMBER=0; FAILED=0

run_rehearsal() {
  local label="$1"; local cmd="$2"; local expected_rc="$3"; local expected_substring="$4"
  local out rc
  out=$(eval "$cmd" 2>&1)
  rc=$?
  if [[ "$rc" == "$expected_rc" ]] && echo "$out" | grep -q "$expected_substring"; then
    echo "  ✓ $label — rc=$rc, found '$expected_substring'"
    PASSED=$((PASSED+1))
  elif [[ "$rc" == "$expected_rc" ]]; then
    echo "  ⚠ $label — rc=$rc but missing '$expected_substring' in output (orchestration drift?)"
    AMBER=$((AMBER+1))
  else
    echo "  ✗ $label — rc=$rc (expected $expected_rc); first 20 lines of output:"
    echo "$out" | head -20 | sed 's/^/    /'
    FAILED=$((FAILED+1))
  fi
}

echo "=== W310 dry-run rehearsal matrix — $(date -u +%FT%TZ) ==="
echo

# 1/6: FINAL-QA-VERDICT — wraps W267 FINAL-QA-GATE.command
run_rehearsal "FINAL-QA-VERDICT (#223)" \
  "FINAL_QA_VERDICT_DRY_RUN=1 bash scripts/FINAL-QA-VERDICT.command" \
  2 "PARTIAL"

# 2/6: GA-COOKBOOK — composes #216 + #217
run_rehearsal "GA-COOKBOOK Gate A (#218)" \
  "GA_COOKBOOK_DRY_RUN=1 GA_COOKBOOK_SKIP_LIVE=1 GA_COOKBOOK_SKIP_APPLE=1 GA_COOKBOOK_SKIP_BROTHER=1 bash scripts/GA-COOKBOOK.command" \
  2 "PARTIAL"

# 3/6: RELEASE-TAG-GUARD — read-only safety gate
run_rehearsal "RELEASE-TAG-GUARD (#221)" \
  "TAG_GUARD_DRY_RUN=1 TAG_GUARD_SKIP_GH=1 bash scripts/RELEASE-TAG-GUARD.command" \
  2 "PARTIAL"

# 4/6: DOWNLOAD-AND-VERIFY-RELEASE — composes gh + #215
run_rehearsal "DOWNLOAD-AND-VERIFY (#219)" \
  "DOWNLOAD_VERIFY_DRY_RUN=1 DOWNLOAD_VERIFY_SKIP_PLATFORM=1 DOWNLOAD_VERIFY_SKIP_TOOLS=1 bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command" \
  2 "PARTIAL"

# 5/6: POST-INSTALL-SMOKE — 4-gate installed-binary health
run_rehearsal "POST-INSTALL-SMOKE (#222)" \
  "POST_INSTALL_SMOKE_DRY_RUN=1 POST_INSTALL_SMOKE_SKIP_PLATFORM=1 POST_INSTALL_SMOKE_SKIP_VERSION=1 POST_INSTALL_SMOKE_SKIP_FULL=1 bash scripts/POST-INSTALL-SMOKE.command" \
  2 "PARTIAL"

# 6/6: BROTHER-POSTFLIGHT — 6-sync coord regression sweep
run_rehearsal "BROTHER-POSTFLIGHT (#220)" \
  "BROTHER_POSTFLIGHT_DRY_RUN=1 BROTHER_POSTFLIGHT_SKIP_LIVE=1 BROTHER_RECONCILE_URL=https://meeet.world/admin/reconcile bash scripts/BROTHER-POSTFLIGHT.command" \
  2 "PARTIAL"

echo
echo "=== Rehearsal summary ==="
echo "  Passed (orchestration sound):     $PASSED / 6"
echo "  Amber  (rc ok, substring drift):  $AMBER / 6"
echo "  Failed (rc drift — fix before tag): $FAILED / 6"
echo
if [[ "$FAILED" -gt 0 ]]; then
  echo "✗ REHEARSAL FAILED — orchestration drift detected. Fix and re-run."
  exit 1
else
  echo "✓ REHEARSAL CLEAN — orchestration sound on current main. OK to proceed to tag day."
  exit 0
fi
```

**Rehearsal cadence recommendation:**

- **T-7 days** — first rehearsal, baseline established.
- **T-1 day** — re-run rehearsal after the last PR merges. Should
  still be all-green; any new RED row means a sibling refactor or
  rebase broke the orchestration since baseline.
- **Tag day morning** — re-run rehearsal one final time as the first
  step of the GA cookbook (effectively Step 0/11 in the executable
  sequence above). Any drift here means the GA cookbook itself is
  not safe to execute today; defer tag cut until rehearsal passes.

**Why this is docs-only (W310-ap discipline note):**

A rehearsal wrapper script (e.g. `scripts/DRY-RUN-REHEARSAL.command`)
would grow the merge queue by one and require its own test suite,
spec-contract pinning, and reviewer attention — all of which compete
with the actual tag-cut work for operator throughput. The rehearsal
matrix above is pure bash inside a docs section, copy-paste-ready,
and re-uses the dry-run knobs that every helper already exposes (no
new env knob is introduced). The matrix runtime is bounded by the
slowest helper's dry-run latency (POST-INSTALL-SMOKE at ~21 s, the
others all <0.5 s); total ~25 s end-to-end, well within "paste once,
read result" attention budget.

**Drift signals (what each unexpected RED row means):**

- **FINAL-QA-VERDICT rc≠2 or missing PARTIAL** — W267 sibling
  `scripts/FINAL-QA-GATE.command` was moved or removed; or the
  `Passed:/Skipped:/Failed:` log block format changed. Fix: re-add
  sibling at expected path or update wrapper's log-parsing regex.
- **GA-COOKBOOK rc≠2 or missing PARTIAL** — sibling `PREFLIGHT-APPLE-
  SIGN.command` (#216) or `BROTHER-PREFLIGHT.command` (#217) was
  moved; or env-knob forwarding (`GA_COOKBOOK_SKIP_APPLE` →
  `PREFLIGHT_APPLE_SKIP_LOCAL`) broke. Fix: re-verify sibling paths
  in `GA_COOKBOOK_REPO` resolution, check env-var passthrough.
- **RELEASE-TAG-GUARD rc≠2 or missing PARTIAL** — `gh` not on PATH,
  OR `git ls-remote --tags origin` rejected (network/credentials);
  OR the docs/qa/SOAK_v10.0.0.md stub couldn't be auto-laid because
  the repo lacks `docs/qa/`. Fix: install `gh`, verify GitHub
  credentials, `mkdir -p docs/qa/` if missing.
- **DOWNLOAD-AND-VERIFY rc≠2 or missing PARTIAL** — sibling
  `VERIFY-APPLE-SIGNATURE.command` (#215) was moved; OR the
  platform-skip env knob name changed; OR `gh` is on PATH but stubbed
  out incorrectly. Fix: re-verify sibling at expected path, check
  env-knob names in script header documentation.
- **POST-INSTALL-SMOKE rc≠2 or missing PARTIAL** — `scripts/SMOKE-
  TEST.command` was moved; OR Gate 1 platform-skip knob name
  changed. Fix: re-verify sibling at expected path, check Gate 1
  Darwin guard env knob spelling.
- **BROTHER-POSTFLIGHT rc≠2 or missing PARTIAL** — one of the 4
  wrapped primitives (`probe-meeet-billing.command`, `CHECK-MEEET-
  LIVE.command`, `smoke_billing_tars_backend.sh`, `acceptance_tars_
  meeet.sh`) was moved; OR `BROTHER_RECONCILE_URL` env-knob name
  changed. Fix: re-verify all 4 primitives present in `scripts/`,
  check env-knob name in script header.

If any drift signal fires, the fix is almost always a single grep-
and-replace away. The point of the rehearsal is to **catch the drift
at rehearsal-day cost (~30 s + one-line fix) instead of tag-day cost
(blocked tag cut, scrambled remediation, lost momentum on launch
comms)**.

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
- **W310-ai** — added PR #219 (DOWNLOAD-AND-VERIFY-RELEASE single-decision
  post-tag wrapper — `DOWNLOAD-AND-VERIFY-RELEASE.command` + 17 spec-contract
  tests, +574 LoC), lifting the active PR count to **33**. **SIXTH
  IMPLEMENTER FOLLOW-UP** to the W310 planning surface, and the **second
  composer** (after #218). Symmetric counterpart to W310-ah on the **post-tag**
  side: where #218 collapses Apple+Brother pre-flight into ONE Gate A
  verdict, #219 collapses the 7-step manual post-release chore (ssh to clean
  Mac → open https://github.com/.../releases → click correct .dmg →
  wait for download → drop somewhere predictable → open Terminal → bash
  VERIFY) into ONE Gate B verdict producing the same PROCEED / BLOCK /
  PARTIAL contract. Detects host arch (`uname -m` → `arm64→aarch64` /
  `x86_64`), resolves owner/repo via `gh repo view --json owner,name`,
  confirms the release + arch-matched `TARS_<version>_<arch>.dmg` asset
  exist via `gh release view --json assets` (refuses with remediation
  pointer if either missing — does NOT silently download nothing),
  downloads the `.dmg` into a per-pid `/tmp/tars-ga-download-<pid>/`
  via `gh release download "${tag}" --pattern "${asset}"`, computes +
  prints SHA-256 (so operator can cross-reference `.RELEASE-v10.0.txt`
  from the build machine), then invokes
  `scripts/VERIFY-APPLE-SIGNATURE.command` (PR #215) and passes through
  its 0/1/2 exit code as the wrapper's own. Green path cleans up tmp
  dir + prints next-step cookbook pointers (drag-install + SOAK-HOURLY
  cron); red path force-keeps `.dmg` for rollback forensics + points
  at PR #199 §7 (A/B/C rollback paths); partial path explains cause
  (skip-platform / skip-tools / dry-run only). Env knobs:
  `RELEASE_TAG=v10.0.0` (default — matches GA target), `GH_REPO=` (auto-
  detected via gh; overridable for fork verification), `RELEASE_ARCH=`
  (auto-detected via uname -m; overridable for cross-arch forensics
  e.g. pulling aarch64 .dmg on Intel mac), `DOWNLOAD_VERIFY_KEEP=1`
  (skip tmp cleanup so operator can drag-install the same `.dmg`),
  `DOWNLOAD_VERIFY_DRY_RUN=1` (skip real `gh` + sibling invocation),
  `DOWNLOAD_VERIFY_REPO=<path>` (override sibling lookup root for
  test stubs), `DOWNLOAD_VERIFY_NO_COLOR=1`, `DOWNLOAD_VERIFY_TMP_DIR=`
  (override default `/tmp/tars-ga-download-<pid>/`),
  `DOWNLOAD_VERIFY_SKIP_PLATFORM=1` (bypass macOS guard for Linux CI
  smoke only), `DOWNLOAD_VERIFY_SKIP_TOOLS=1` (bypass gh+shasum
  presence check for Linux CI smoke only). **17/17 green tests +
  2 platform-correctly-skipped in ~0.21 s** — pins meta (executable
  + shebang + `bash -n`), pins spec contract (header enumerates the
  7-step manual flow it replaces verbatim AND the 7-step wrapper
  collapse verbatim AND back-references PR #215 + the four ritual
  surfaces of GA AND 0/1/2 exit contract AND all 10 env overrides
  AND `RELEASE_TAG="${RELEASE_TAG:-v10.0.0}"` default matches GA
  target), pins composition (missing sibling → exit 2 with PR #215
  remediation pointer), pins dry-run path with all skips + stub
  sibling (rc=0 PROCEED + `[dry-run] download skipped` + `[dry-run]
  would invoke: bash …/VERIFY-APPLE-SIGNATURE.command`), pins arch
  auto-detection (uname -m → expected mapping in stdout), pins
  RELEASE_ARCH override semantics (`RELEASE_ARCH=x86_64` wins over
  uname), pins RELEASE_TAG propagation (`tag v10.0.1` in banner +
  `[dry-run] asset assumed: TARS_10.0.1_<arch>.dmg`), pins platform
  guard structure (line-extracted, not substring-split — survived
  the `verification` / `${KEEP}` false-positive trap by switching to
  line-based block parsing for guard / cleanup / case-arm extraction),
  pins tool-dependency loop skip semantics, pins cleanup discipline
  (`KEEP=1` short-circuit pinned; red-path force-keep + `exit 1` +
  PR #199 pointer pinned). Stub sibling pattern (same isolation as
  `test_brother_preflight_script.py` + `test_ga_cookbook_script.py`)
  — `_make_stub_sibling()` lays a minimal `scripts/VERIFY-APPLE-SIGNATURE.command`
  in tmp dir that just exits 0 + points `DOWNLOAD_VERIFY_REPO` at it,
  so tests don't need real GH releases / Apple keychain / Xcode CLT.
  Smoke verified pre-push on macOS (no skips): correctly exits 2 with
  "sibling helper missing → land PR #215" pointer, confirming safe-
  fail before PR #215 is on `main`. Wrapper is purely additive: zero
  new deps (gh + shasum already required by sibling), zero changes
  to sibling script (#215 remains operator-runnable standalone for
  manual re-verification on any local `.dmg`), zero changes to release
  pipeline. Hard dep: PR #215 must be on main before the wrapper
  resolves the sibling (if missing, wrapper exits 2 with remediation
  pointer — fails safely, not silently). **Closes the last operator-
  mental-model gap on the post-tag side of the v10.0.0 GA path** —
  after this lands, *"do I trust this build?"* reduces to *"did
  `DOWNLOAD-AND-VERIFY-RELEASE.command` exit 0?"*. Symmetric with the
  pre-tag *"may I tag?"* → *"did `GA-COOKBOOK.command` exit 0?"*
  collapse from #218. **The v10.0.0 GA path now has zero "remembered
  probes" AND zero "remembered sequencing" left at either Gate A or
  Gate B** — two wrapper commands, two exit codes, two color-coded
  verdicts. Lands cleanly with or without PR #215 already merged.
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

- **W310-aj** — added PR #220 (BROTHER-POSTFLIGHT single-decision post-
  launch wrapper — `BROTHER-POSTFLIGHT.command` + 21 spec-contract tests,
  +602 LoC), lifting the active PR count to **34**. **SEVENTH IMPLEMENTER
  FOLLOW-UP** to the W310 planning surface, and the **third symmetric
  closer** (after #218 pre-tag and #219 post-tag-artifact). Symmetric
  counterpart to W310-ag (#217 BROTHER-PREFLIGHT) on the **post-tag**
  side: where #217 catches missing prereqs at Gate A (pre-tag, cheap
  rollback), this runs 24-72 h after the tag is live to catch real-world
  drift / silent regressions in the brother-coord surface (e.g. brother
  deploys a config change that breaks `/operator` balance shape; checkout
  URL redirects to maintenance page; reconcile script silently throws
  on a new edge case; acceptance flake masks a true regression). 6 syncs
  total (Sync 1 A1 ingest re-verify via `probe-meeet-billing.command`,
  Sync 2 A2 balance re-verify via `CHECK-MEEET-LIVE.command`, Sync 3 A5
  auth e2e re-verify via `smoke_billing_tars_backend.sh`, Sync 4 A3
  checkout liveness via direct `curl -fsSI https://meeet.world/billing/
  tars` regression, Sync 5 A4 reconciliation **executes** rather than
  existence-checks, Sync 6 acceptance suite re-run via `acceptance_tars_
  meeet.sh`); explicitly drops PREFLIGHT Sync 6 `BROTHER_PAIR_TTL_ACK`
  (heads-up-only pre-tag knob; runtime drift-guard test prevents silent
  re-addition). Sync 5 is the headline elevation: PREFLIGHT only checked
  `test -f scripts/reconcile-meeet-billing.py` so a silent runtime error
  in the daily reconcile pipeline would not surface until ledger drift
  accumulated; POSTFLIGHT actually invokes `python3 scripts/reconcile-
  meeet-billing.py --check` (with graceful fallback to bare invocation
  if `--check` flag not yet wired) OR HEAD-probes `BROTHER_RECONCILE_URL`
  (operator-set knob takes precedence over silent file presence — pinned
  by test). All probes regression-tagged (header banner reads "post-tag
  regression check"); remediation pointers name **PH4 §6 + PH11 §6
  (post-launch playbook)** so red verdicts route to the rollback A/B/C
  decision tree (A hotfix v10.0.1 keeping tag live / B partial rollback
  un-publishing binaries / C full revert re-tagging v10.0.0-rc.1 as
  emergency v10.0.0). PROCEED next-steps explicitly do NOT call
  `RELEASE-v10.0.command` (differential vs preflight — tag is already
  cut by the time this runs); instead prints "post '✓ brother postflight
  green (T+24h)' comment on v10 GA tag PR" + "schedule T+72h re-run via
  cron" suggestion with literal crontab one-liner appending to
  `.postflight/daily.log`. Exit contract: 0 = all 6 green → brother coord
  side of v10 GA healthy post-launch (record sign-off; close v10 GA
  dock-down arc); 1 = ≥1 sync red → **BLOCK launch comms** (don't tweet
  "v10 is live") + decide   rollback per brief §6; 2 = prereq missing OR
  partial verdict (SKIP_LIVE=1 left ≥1 sync unverified). Env knobs:
  `BROTHER_POSTFLIGHT_DRY_RUN=1` + `BROTHER_POSTFLIGHT_SKIP_LIVE=1` +
  `BROTHER_POSTFLIGHT_REPO=<path>` + `BROTHER_RECONCILE_URL=<url>` +
  `BROTHER_POSTFLIGHT_NO_COLOR=1`. **21/21 green tests in ~0.07 s** —
  pins meta (executable + shebang + `bash -n`), pins spec contract
  (header enumerates all 6 syncs verbatim + 5 deltas from PREFLIGHT
  verbatim + 0/1/2 exit contract + all 5 env knobs + hard deps list +
  "Fails safely, not silently" framing), pins structural sync count
  (exact 6 `hdr "Sync N — …"` lines + `/ 6` summary denominator pinned
  in 3 echo lines + `BROTHER_PAIR_TTL_ACK` must NOT appear in runtime
  code section — silent re-addition guard), pins runtime under three
  dry-run variants (variant A: SKIP_LIVE + no reconcile resolution →
  rc=1 BLOCK with "no owner" Sync 5 red + `A. Hotfix` / `B. Partial
  rollback` / `C. Full revert` rollback panel; variant B: SKIP_LIVE +
  URL set → rc=2 PARTIAL with Sync 5 green via brother URL + "Defer
  launch comms"; variant C: pure dry-run + URL set + 4 primitive stubs
  laid → rc=0 PROCEED all 6 green + `Schedule a T+72h re-run via cron`
  + `GA-COOKBOOK (#218)` / `DOWNLOAD-AND-VERIFY-RELEASE (#219)`
  symmetry note), pins URL-takes-precedence-over-local-py (operator-
  set knob wins over silent file presence — stub `.py` that would error
  if invoked confirms URL path chosen), pins differential check
  (PROCEED next-steps must NOT name `RELEASE-v10.0.command` — tag is
  already cut by the time this runs), pins platform guard (`BROTHER_
  POSTFLIGHT_REPO` override structure + curl-on-PATH guard gated by
  dry-run). Stub-sibling pattern (same isolation as `test_brother_
  preflight_script.py`): tests lay minimal bash stubs for the 4
  primitives in tmp dir + point `BROTHER_POSTFLIGHT_REPO` at it, so
  tests don't need real meeet.world infrastructure / real reconcile
  script. Smoke verified pre-push: 3 variants on real script (SKIP_LIVE
  no extras → rc=1 BLOCK; SKIP_LIVE+URL → rc=2 PARTIAL; full dry-run+URL
  → rc=0 PROCEED) all match expected contract. **Closes the post-launch
  brother-coord health gap** — together with #218 (Gate A pre-tag verify)
  + #219 (Gate B post-tag artifact verify) + this PR (Postflight at
  T+24-72h), the v10 GA tag-cut surface is now symmetric across **all
  four ritual corners** (pre-tag verify, pre-tag release, post-tag
  verify, post-tag health). After this lands, *"is brother coord still
  healthy 24 h after launch?"* reduces to *"did `BROTHER-POSTFLIGHT.
  command` exit 0?"*. Wrapper is purely additive: zero new deps, zero
  changes to sibling scripts, zero changes to release pipeline. Hard
  dep: 4 wrapped primitive scripts must exist on main (already do);
  reconcile resolution (TARS-side .py OR brother-side URL) — neither
  hard-required at script-land time; runtime fails safely with both-
  path remediation if both missing post-tag. Lands cleanly with or
  without PR #198 already merged.
- **W310-ak/al/am** — bundled implementer follow-ups 8/9/10, lifting
  active PR count to **37**: PR #221 RELEASE-TAG-GUARD (read-only
  tag-cut safety gate; 5 gates worst-of-5; refuses to let operator
  type destructive `RELEASE-v10.0.command` until soak verdict + git
  branch + git clean + tag-not-already-pushed + CI freshness all
  green; **25/25 green tests in ~1.69 s** with two structural pins
  guaranteeing destructively HARMLESS invariant — no `git tag v...`
  or `git push origin v...` in runtime, uses `git ls-remote` not
  `git fetch`), PR #222 POST-INSTALL-SMOKE (drag-install → soak-cron
  bridge; 4 worst-of gates; bridges Step 8a → Step 8b with single
  verdict for *"is the installed cockpit alive on app + backend +
  meeet bridge + smoke?"*; **24/25 green tests in ~21.5 s + 1 Darwin-
  skip** with destructively HARMLESS invariant guard regex deny-list
  pinned by 2 structural tests), PR #223 FINAL-QA-VERDICT (cookbook-
  uniform wrapper around W267 `FINAL-QA-GATE.command`; **demotes any
  SKIPPED step to AMBER → PARTIAL** so the false-green case where
  codesign gets skipped because `/Applications/TARS.app` is absent
  surfaces as rc=2 instead of hiding under sibling's `GO` exit; **28/28
  green tests in ~0.31 s** with regression-tested stale-PROCEED +
  fresh-BLOCK same-log parsing). All three are pure additive
  (`scripts/*` + `tests/*`), file-level independent of every other PR
  in the fleet, lands cleanly in any order with or without parent
  briefs already merged. Closes the **destructive-tag-cut decision
  point** (Tag-Guard sits between SOAK-REPORT and RELEASE-v10.0), the
  **post-install installed-binary health bridge** (Post-Install sits
  between drag-install and soak-cron-start), and the **last non-
  uniform verdict surface** (QA-verdict normalises FINAL-QA-GATE's
  0/1 GO/NO-GO to cookbook-uniform 0/1/2 PROCEED/BLOCK/PARTIAL with
  per-step remediation pointers). The v10.0.0 GA cookbook now has
  **SIX symmetric single-decision wrapper commands** across all six
  verification axes (QA-verdict + Gate A + Tag-Guard + Gate B +
  Post-Install + Postflight).
- **W310-an/ao/ap** — bundled DOCS-ONLY extensions to PR #192, explicitly
  chose NOT to grow the queue with new PRs but to extract operator
  throughput from what's already shipped. **W310-an** added the
  "Operator one-shot merge sequence" subsection — copy-paste-ready
  5-tier bash playbook that lands all 37 W310 PRs in ~20-30 min of
  wall-clock by rooting tier 0 at PR #188 (qa-agent.yml cache fix
  that unblocks every other CI run on the fleet); tiers 1-2 sequence
  runtime PRs by dependency (#187 unlocks step 2 implementation,
  #189 best landed after #187 for green skipping suite); tiers 4-5
  parallelize 32 file-level-independent PRs (22 planning briefs +
  10 implementer helpers). **W310-ao** added the "Operator one-shot
  GA cookbook execution sequence" — copy-paste-ready 5-phase bash
  playbook that cuts v10.0.0 GA from merged-queue state through
  tagged-shipped-soaking-brother-verified in ~30-50 min active +
  72 h passive, with only TWO operator-required pause points (Step 4
  destructive tag-cut confirmation + Step 7 manual drag-install
  confirmation) and explicit per-phase rollback decision trees
  (Phase A BLOCK = zero rollback; Phase B BLOCK = PR #199 §7 path A
  pre-tag delete; Phase C BLOCK = PR #199 §7 path B post-tag-pre-
  publish unpublish; Phase D BLOCK = PR #198 §6 launch decision tree
  A/B/C hotfix-or-partial-or-full-revert). **W310-ap** added the
  "Operator dry-run rehearsal matrix" subsection — copy-paste-ready
  ~30 s bash block that exercises all 6 verdict wrappers in
  `*_DRY_RUN=1` mode against the current state of `main` to detect
  orchestration drift (sibling path moves, env-knob name typos, exit-
  contract regressions introduced by sibling refactors) at zero cost.
  Per-helper drift-signal taxonomy maps each unexpected RED row onto
  the likely single-line fix (re-add sibling at expected path, update
  log-parsing regex, fix env-var name passthrough). Recommended cadence:
  T-7d baseline, T-1d post-final-merge, tag-day-morning Step 0/11. Any
  RED defers tag-cut until rehearsal passes; rehearsal is purely
  read-only so the defer cost is "one more rehearsal run after the
  fix" not "operator burns a tag attempt". All three playbooks compress
  the W310 backlog landing + v10.0.0 GA cut + tag-day-orchestration-
  drift-detection from ~30 remembered probes + ~50 separate commands
  + zero rehearsal capability (current state: operator discovers drift
  mid-tag-cut) into ~3 paste actions + 2 typed confirmations + 1
  rehearsal paste that runs in 30 s. **None adds a new PR to the
  open queue** — all extend PR #192's wave summary in-place. **Why
  this discipline:** each new helper grows the merge backlog by one
  without unblocking throughput on the already-shipped 10 helpers;
  the docs-only extensions compress operator decisions into paste-
  actions rooted on existing artefacts, which is the only remaining
  lever for reducing wall-clock-to-GA without growing the queue
  further.

**W310 PLANNING SURFACE CLOSED ✅; IMPLEMENTER SURFACE OPENED — TEN
HELPERS SHIPPED + THREE DOCS-ONLY EXTENSIONS.** Pickup pointer for any
agent landing in the meeet workspace now lists all **37 active PRs**
(27 planning + 10 implementer follow-ups), all closed stacks, and
points at this wave summary as the single-page operator-readable W310
retrospective — including THREE copy-paste-ready bash playbooks (merge
sequence + GA cookbook execution sequence + dry-run rehearsal matrix)
added in-place via W310-an + W310-ao + W310-ap docs-only extensions
that explicitly chose NOT to grow the queue with new PRs but to extract
operator throughput from what's already shipped. The next implementer session in any phase (PH2 voice
/ PH3 keyring + UX + mobile / PH4 sign trio / PH5 real-data trio /
PH6 sandbox / PH7 planner / PH8 marketplace / PH9 mobile trio / PH10
Claude polish / PH11 GA dock-down) opens to a fully-specified brief
with operator open questions, risk register, test plan, dep matrix,
and effort estimates.

The ten implementer follow-ups shipped so far (W310-ad soak + W310-ae
Apple sign verify + W310-af Apple pre-flight + W310-ag Brother coord
pre-flight + W310-ah GA-COOKBOOK single-decision pre-tag wrapper +
W310-ai DOWNLOAD-AND-VERIFY-RELEASE single-decision post-tag wrapper +
W310-aj BROTHER-POSTFLIGHT single-decision post-launch coord-health
wrapper + W310-ak RELEASE-TAG-GUARD single-decision tag-cut decision
gate + W310-al POST-INSTALL-SMOKE single-decision installed-binary
health bridge + W310-am FINAL-QA-VERDICT single-decision QA mechanical-
checks wrapper) together close **all five** "remembered ritual" gaps
AND the "remembered sequencing" gap AND the "remembered command typing"
gap AND the "false-green skipped step" gap on the v10.0.0 GA execution
path BEFORE, AT, and AFTER the tag cut, AND after the drag-install —
pre-tag QA mechanical checks → Apple pre-flight → Brother pre-flight,
tag-cut safety, release, post-tag download → verify, post-install
health, soak, post-launch brother coord health regression — into
single executable commands with spec-pinned tests, AND collapse the
six verification surfaces into SIX symmetric single-decision wrapper
commands (QA-verdict for *"do all 8 mechanical checks pass without
silent skip?"*, Gate A for *"may I tag v10.0.0?"*, Tag-Guard for *"is
it safe to type the destructive RELEASE command right now?"*, Gate B
for *"do I trust this build?"*, Post-Install for *"is the drag-installed
binary alive enough to start the 72 h soak cron?"*, Postflight for
*"is brother coord still healthy at T+24-72 h?"*), each producing one
PROCEED / BLOCK / PARTIAL verdict with per-failure remediation pointers
to the planning briefs.

The three docs-only extensions (W310-an operator one-shot merge sequence
+ W310-ao operator one-shot GA cookbook execution sequence + W310-ap
operator dry-run rehearsal matrix) close the "operator orchestration"
gap on top: W310-an gives a copy-paste-ready 5-tier bash playbook that
lands all 37 W310 PRs in ~20-30 min of wall-clock; W310-ao gives a
copy-paste-ready 5-phase bash playbook that cuts v10.0.0 GA from
merged-queue state to tagged-shipped-soaking in ~30-50 min active +
72 h passive, with only TWO operator-required pause points (Step 4
destructive tag-cut confirmation + Step 7 manual drag-install
confirmation) and explicit per-phase rollback decision trees; **W310-ap
gives a copy-paste-ready ~30 s bash matrix that exercises all 6
verdict wrappers in `*_DRY_RUN=1` mode against the current state of
`main` to detect orchestration drift at rehearsal-day cost (one-line
fix) instead of tag-day cost (blocked tag cut), with per-helper drift-
signal taxonomy mapping each unexpected RED row onto the likely
single-line fix**. Together the three playbooks compress the W310
backlog landing + v10.0.0 GA cut + tag-day-orchestration-drift-detection
from ~30 remembered probes + ~50 separate commands + zero rehearsal
capability into ~3 paste actions + 2 typed confirmations + 1 rehearsal
paste.

Only the operator action items (.p12 supply, secret push via GitHub
UI, manual dispatch dry-run click, blog post draft, drag-install on
clean Mac, tag-cut confirmation, public launch comms, rollback
decision A/B/C if any postflight gate red) remain blocking non-script
work. The operator's full v10.0.0 GA cookbook now reduces to:

```bash
# Phase A — pre-tag verification (read-only)
bash scripts/FINAL-QA-VERDICT.command             # QA mechanical-checks verdict
bash scripts/GA-COOKBOOK.command                  # Gate A — pre-tag prereq verify
bash scripts/RELEASE-TAG-GUARD.command            # Tag-Guard — safe to tag now?

# Phase B — destructive tag-cut (operator-confirmed)
# pause-point 1 of 2: type 'yes' to cut tag
bash scripts/RELEASE-v10.0.command                # destructive — only if A all = 0
gh run watch ...                                  # wait for CI sign+notarize

# Phase C — post-tag verification + install + soak start
bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command  # Gate B — post-tag artifact verify
# pause-point 2 of 2: type 'installed' after dragging .dmg to /Applications/
bash scripts/POST-INSTALL-SMOKE.command           # Step 8b — installed-binary verdict
crontab -l | { cat; echo "0 * * * * ... SOAK-HOURLY.command"; } | crontab -

# Phase D — post-launch coord health (T+24-72 h)
bash scripts/SOAK-REPORT.command                  # SOAK verdict
bash scripts/BROTHER-POSTFLIGHT.command           # Postflight — coord-health verdict

# Phase E — tag promotion (operator-paced, no helper wrapper)
# (update meeet.world/tars links, draft announce post, archive rc tag)
```

**All six verification gates (QA-verdict, Gate A, Tag-Guard, Gate B,
Post-Install, Postflight) are spec-pinned executable wrappers shipped
in this wave**, each producing one PROCEED / BLOCK / PARTIAL verdict.
The two destructive ops (`RELEASE-v10.0.command`, `SOAK-HOURLY.command`)
were already scripted. The two unavoidable manual steps (Step 4
operator-confirmed tag cut, Step 7 drag-install) and the unavoidable
CI wait (Step 5 sign+notarize ~25-40 min) remain manual by design.
The operator's full verification mental model is now **six bash
commands, six exit codes, six color-coded verdicts** — perfectly
symmetric across the tag-cut boundary AND across the post-install
health bridge AND across the post-launch drift-detection window —
plus **TWO copy-paste bash playbooks** that orchestrate the entire
flow from "37 PRs merged" through "v10.0.0 tagged + soaking + brother
coord verified" with only 2 operator-typed confirmations.

---

## What this wave does NOT touch

- **Production runtime code on `main`** — all sub-waves operate on PR branches.
- **`v10.0.0-rc.1` artifacts** — no installer rebuild required; rc1 still ships as cut.
- **Phase L semantics** — L0-L9 contracts unchanged; #191's L4.2 work is purely additive.
- **Operator decisions** — D1-D4 captured in W310-a and unchanged here.

W310 is **PR-hygiene and forensic-extraction wave only**. v10.0.0 GA
dock-down begins as soon as #187 + #188 (and ideally #189-#191) land on
`main`.
