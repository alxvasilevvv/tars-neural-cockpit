# W310 — Post-rc1 PR triage wave · summary

**Owner:** Cursor agent (Claude Opus 4.7) — autonomous orchestration window
**Window:** 2026-05-17 → 2026-05-18
**Lane:** PR hygiene + cross-cutting closeouts on top of `v10.0.0-rc.1`
**Branch home:** `cursor/post-rc1-master-plan` (PR #188), plus per-extraction branches
**Status:** ✅ All sub-waves landed; **27 PRs open awaiting operator merge**. Planning surface fully closed — every implementer question from `v10.0.0-rc.1` through `v11` is spec'd.

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

---

## Active PRs (27 open, all awaiting operator merge)

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

**W310 PLANNING SURFACE CLOSED ✅.** Pickup pointer for any agent
landing in the meeet workspace now lists all **27 active PRs**, all
closed stacks, and points at this wave summary as the single-page
operator-readable W310 retrospective. The next implementer session
in any phase (PH2 voice / PH3 keyring + UX + mobile / PH4 sign trio /
PH5 real-data trio / PH6 sandbox / PH7 planner / PH8 marketplace /
PH9 mobile trio / PH10 Claude polish / PH11 GA dock-down) opens to
a fully-specified brief with operator open questions, risk register,
test plan, dep matrix, and effort estimates.

---

## What this wave does NOT touch

- **Production runtime code on `main`** — all sub-waves operate on PR branches.
- **`v10.0.0-rc.1` artifacts** — no installer rebuild required; rc1 still ships as cut.
- **Phase L semantics** — L0-L9 contracts unchanged; #191's L4.2 work is purely additive.
- **Operator decisions** — D1-D4 captured in W310-a and unchanged here.

W310 is **PR-hygiene and forensic-extraction wave only**. v10.0.0 GA
dock-down begins as soon as #187 + #188 (and ideally #189-#191) land on
`main`.
