# Changelog

All notable changes to TARS at the **release** level. Per-wave detail
lives in [`docs/CHANGELOG_AGENTS.md`](docs/CHANGELOG_AGENTS.md). Honest
capability ledger: [`docs/WHAT_WORKS.md`](docs/WHAT_WORKS.md). Forward
roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md).

The format is loosely based on [Keep a Changelog](https://keepachangelog.com).

---

## v9.1.0 — B2B Production Suite addendum (2026-05-10)

A two-week post-Workshop sprint that landed the full B2B operational
stack on top of the Wave 80-92 workshop surface. 15 waves shipped on
the protected branch `claude/wave-87-onwards`. Funds, SaaS, DAOs,
family-offices, agencies, and nonprofits can now be onboarded in a
single sitting and run productively from day one.

Full release notes: [`docs/RELEASE_NOTES_v9.1.0.md`](docs/RELEASE_NOTES_v9.1.0.md#b2b-production-suite-addendum-waves-94-108--2026-05-10).
Wake-up handoff for operator: [`docs/HANDOFF_WAKE_UP.md`](docs/HANDOFF_WAKE_UP.md).

### Workshop suite completed
- **Wave 94 — Cohort backend.** Real attendee tracking + live SSE; replaces the Wave 89 mock fallback. `/workshop/cohort` is now authoritative. `backend/core/cohort/`, `web_extras/routers/cohort.py`, `docs/contracts/COHORT.md`.
- **Wave 101 — HIL inbox.** New `/inbox` route — bulk approve, policy thresholds, per-tenant queues. `experiments/neural-showcase-v3/src/pages/Inbox.tsx`, `backend/core/hil/`, `web_extras/routers/hil.py`.

### Compliance + audit
- **Wave 95 — Receipt ledger unified.** Hash chain + Merkle root + Solana memo anchor on top of the Wave 67 per-event ed25519 ledger. `backend/core/receipts/{ledger,chain,merkle,anchor}.py`, `docs/contracts/RECEIPTS.md`.
- **Wave 104 — Compliance export bundle.** Audit-grade — receipts + ledger + Merkle proofs + offline verifier script + GDPR data-out + PII redaction. `backend/core/compliance/`, `docs/contracts/COMPLIANCE_EXPORT.md`.

### B2B operational tools
- **Wave 96 — Reporting dashboard.** `/dashboard` with 10 configurable widgets, 5 default layouts, drag-resize. `experiments/neural-showcase-v3/src/pages/Dashboard.tsx`.
- **Wave 97 — Playbook scheduler.** Cron-based, persisted, restart-safe. Replaces the autopilot tick. `/schedules`. `backend/core/scheduler/`, `docs/contracts/SCHEDULER.md`.
- **Wave 98 — Email outreach.** Gmail send + AI Clone drafting + HIL gate + 5 starter templates. `/outreach`. `backend/core/outreach/`, `docs/contracts/OUTREACH.md`.
- **Wave 99 — Org onboarding wizard.** `/onboard/org` 5-step (org type / size / pillars / connectors / first playbook). `experiments/neural-showcase-v3/src/pages/OrgOnboarding.tsx`, `backend/core/onboarding/org.py`.
- **Wave 102 — Files management.** `/files` document UI + bulk ops + 8 categories + tagging. `backend/core/files/`, `docs/contracts/FILES.md`.
- **Wave 103 — Reports module.** `/reports` 6 templates (LP, board, weekly digest, compliance, KPI, postmortem) + scheduling + PDF/PPTX/XLSX delivery. `backend/core/reports/`, `docs/contracts/REPORTS.md`.
- **Wave 106 — Marketplace v0.** In-process registry + `/marketplace` browse + install + local ratings + 12 seed listings. `backend/core/marketplace/`, `docs/contracts/MARKETPLACE.md`. *Honest scope: payouts and third-party publishing are v9.2/v9.3.*
- **Wave 107 — Vertical bundles.** 7 org-type ready-to-demo packs (fund / saas / dao / family-office / agency / enterprise / nonprofit) at `/bundles`. `backend/core/bundles/`, `docs/contracts/BUNDLES.md`.
- **Wave 108 — Performance dashboard.** `/admin/perf` p50/p95/p99 + throughput + error rate + active sessions. `backend/core/observability/perf.py`, `docs/contracts/PERF_DASHBOARD.md`.

### Connectors
- **Wave 108 — Telegram bridge.** Bot bridge with long-poll + webhook + outbound. `TELEGRAM_BOT_TOKEN` env-gated. Promotes the v9.1.1 PARTIAL row to FULLY IMPLEMENTED. `backend/core/connectors/telegram.py`.
- Slack/Gmail/Calendar (Wave 91) and Telegram (Wave 108) are now all real connectors. Quick Connect Chrome extension flow remains v9.1.1.

### Cross-module testing
- **Wave 105 — E2E test suite.** 10 cross-module scenarios (12 pass + 1 skip) covering onboarding → bundle install → cohort → outreach → HIL → reports → compliance export → verifier round-trip. `tests/e2e/`, `docs/testing/E2E_SUITE.md`.

### Cursor parallel — algotrade lane
- W1/W2/W3/W4 algotrade work continued on `cursor/algotrade-w*` branches in parallel. Some of Cursor's W2-W4 stuff merged to `origin/main` while Claude worked on the Workshop + B2B production suite on `claude/wave-87-onwards`. Wave 100 audit verified the integration. The Wave 4-PR1 quant playbooks landed in Claude's branch via cherry-pick.

### Honesty caveats
- Marketplace v0 ships browse + install + local ratings. Payouts (70/30 revenue share) and third-party publishing (ed25519-signed bundles) are v9.2/v9.3.
- Webhooks emit `receipt.*` from the unified ledger (Wave 95); per-feature emit sites (outreach, scheduler, files, reports) wire incrementally — full coverage v9.3.
- AI Clone is still v0.1 (style-hint heuristic). Wave 98 outreach uses it for first-draft generation under HIL gate. Real fine-tuned per-user clone is v9.2.
- Multi-tenant Workspaces backend MVP (Wave 110) is in flight; runtime impl pending v9.2.

### Operator-blocked (still pending after Wave 108)
- Apple Developer .p12 → CI signed .dmg (notarization).
- `GITHUB_RELEASE_TOKEN` in CF Pages env.
- `BRIDGE_SHARED_SECRET` in CF Pages env.
- Tag `v9.1.0` to trigger signed .dmg build.
- Flip `INSTALLERS_READY = true` after .dmg ships.

### Brother-blocked
- Magic-link auth (live token mint) — v9.1.1.
- $MEEET enterprise invoice path — v9.2.

### Credits
- Operator: alienram@icloud.com
- Waves 94-108 + Wave 109 docs sync + wake-up handoff: Claude (assistant)
- Cursor parallel (algotrade W1-W4): Cursor (their lane)

---

## v9.1.0 — Workshop Suite addendum (2026-05-10)

A two-week post-launch sprint that landed the B2B Workshop surface,
the Webhooks module, real OAuth connectors, and a comprehensive
hardening pass. Honest scope: workshop cohort SSE is mock; webhook
`receipt.*` emit-sites land in v9.3; Slack/Gmail/Calendar Quick
Connect Chrome flow lands in v9.1.1.

Full release notes: [`docs/RELEASE_NOTES_v9.1.0.md`](docs/RELEASE_NOTES_v9.1.0.md#workshop-suite-waves-80-92--addendum-2026-05-10).

### Added — Workshop FE
- **Wave 80:** `/workshop` 4-phase wizard + AgentDesigner + Backtest + `/compliance` Console (FE complete).
- **Wave 81:** algotrade workshop pack + branded landing + Cursor SYNC handshake.
- **Wave 82:** B2B workshop visible from marketing landing (Hero CTA + Pricing Business tier + workshop pillar).
- **Wave 83:** workshop FE tests + a11y audit + sitemap/OG polish.
- **Wave 84:** `/workshop/roi` interactive ROI calculator.
- **Wave 85:** `/workshop/materials` hub + PWA offline support for workshop routes.
- **Wave 88:** `/workshop/assess` pre-workshop self-assessment quiz (12 Q × 4 categories).
- **Wave 89:** `/workshop/cohort` facilitator dashboard with mock SSE.
- **Wave 92:** in-app interactive tutorial overlay across all workshop pages.

### Added — Workshop content
- **Phase W1 / W4-PR1:** algotrade foundations (Strategy IR + registry + backtest engine + recipes) + Cursor's quant pack + recursive playbook loader.
- 20+ starter playbooks across 5 verticals under `playbooks/_workshop/{fund,saas,dao,family-office,algotrade,quant}/`.
- **Wave 86:** 8 enterprise-template handouts under `docs/workshop/enterprise-template/` (5 emails + facilitator runbook + feedback survey + README).
- Contracts: [`docs/B2B_WORKSHOP.md`](docs/B2B_WORKSHOP.md), [`docs/contracts/WORKSPACES.md`](docs/contracts/WORKSPACES.md), [`docs/contracts/SKILL_SDK.md`](docs/contracts/SKILL_SDK.md).

### Added — Backend
- **Wave 90:** webhooks module — outgoing dispatcher + signed delivery + inbound playbook trigger + dead-letter queue + inbox. Contract v1.0 (HMAC, retry). `backend/core/webhooks/`, `web_extras/routers/webhooks.py`.
- **Wave 91:** real Slack / Gmail / Google Calendar connectors (OAuth + read). Env-gated on `OAUTH_BRIDGE_*`. `backend/core/connectors/{slack,gmail,calendar}.py`, `web_extras/routers/connectors.py`.

### Added — Hardening
- **Wave 75:** repaired 4 failing GitHub workflows.
- **Wave 76:** release pipeline hardened — verified v9.1.0 tag will build signed dmg.
- **Wave 77:** pre-staged launch flag flip + launch announcement copy.
- **Wave 78:** brother handoff doc (meeet.world side ops).
- **Wave 79:** final security audit + production hardening — rate limits on `/voice/transcribe`, `/agents/route`, `/clone/draft`; wallet `sign_message` policy gate. Audit doc at `docs/security/AUDIT_2026-05-09.md`.
- Real minisign updater pubkey patched into release pipeline.

### Changed — Cleanup
- **Wave 87:** stripped ALL named-customer / regulatory-acronym branding (Cresco / CARF / 3V / Crypto Fund) from docs and code → fully generic B2B. `/workshop/cresco` renamed to `/workshop/enterprise`.
- Workshop content reads as generic enterprise B2B everywhere.

### Honesty caveats
- `/workshop/cohort` SSE is **mock**; no live attendee tracking yet.
- Webhooks contract + dispatcher ship, but `receipt.*` event emission is wired only in algotrade pack today; broader emit-site coverage is v9.3.
- Slack / Gmail / Calendar OAuth is the URL-redirect flow only. The "Quick Connect" Chrome extension flow is v9.1.1.

### Operator-blocked (still pending after Wave 92)
- Apple Developer .p12 → CI signed .dmg (notarization).
- `GITHUB_RELEASE_TOKEN` in CF Pages env.
- `BRIDGE_SHARED_SECRET` in CF Pages env.

### Brother-blocked
- Magic-link auth (live token mint) — v9.1.1.
- $MEEET enterprise invoice path — v9.2.

### Credits
- Operator: alienram@icloud.com
- Waves 80-92 + Wave 93 docs sync: Claude (assistant)

---

## v9.1.0 — 2026-05-09

First production-grade installable. Local-first AI cockpit with native
desktop UX, hardened sidecar lifecycle, and an honest scope. Full release
notes: [`docs/RELEASE_NOTES_v9.1.0.md`](docs/RELEASE_NOTES_v9.1.0.md).

### Added (real features)
- **Wave 73:** STT via Whisper API (`POST /api/voice/transcribe`).
- **Wave 73:** GitHub connector (token-based read of `/user`, `/repos`,
  `/issues`, `/pulls`; 60s LRU cache).
- **Wave 73:** Memory reflection (weekly ISO-week summary into `_global`
  pack; opt-in scheduled loop via `TARS_REFLECTION_AUTO=1`).
- **Wave 73:** AI Clone v0.1 (style traits skeleton — sentence length,
  exclamation/question rate, casual/formal lean, top-50 vocab). Style
  hint, not full clone — see `clone_version` in profile JSON.
- **Wave 73:** Smart Agent Router (opt-in LLM-based intent routing via
  `TARS_SMART_ROUTER=1`; regex parser stays as fallback).
- **Wave 73:** OpenTelemetry exporter wrapper (no-op unless
  `OTEL_EXPORTER_OTLP_ENDPOINT` set).
- **Wave 72:** SQLite-backed pairing store (`~/.tars/pairings.sqlite`) —
  paired devices survive app restart.
- **Wave 72:** `eval-suite.yml` CI workflow (non-blocking on PRs +
  nightly).
- **Wave 72:** `AttachmentChipStrip` wired into Cockpit chat composer.
- **Waves 65–67:** Landing visual + perf audit, Install Instructions
  modal, section divider renumber, tighter section transitions.
- **Wave 64:** Operator launch playbook + auto-precheck + marketing
  templates.
- **Waves 60–62:** Sidecar status indicator, mid-session crash detection
  (Rust watcher + TS heartbeat), `/settings` page + updater UI, Cmd+K
  palette index.
- **Waves 59-1 → 59-9:** ScrollStory empty-space fix, pre-build validator,
  window state persistence, system tray icon (macOS menu bar), global
  shortcut `Cmd+Shift+Space`, deep-link handler `tars://*`.

### Changed
- **Wave 70:** i18n forced to EN-only (RU dictionary removed in Wave 72
  to prevent regression).
- **Wave 71-A:** Backend reality alignment — version bump 9.1.0,
  dl-proxy allowlist, memory copy honest.
- **Wave 71-B:** Marketing copy aligned with shipped code (every
  claimed feature has a code path; every shipping URL resolves).
- **Wave 72:** Pairing store migrated in-memory → `~/.tars/pairings.sqlite`.
- **Wave 72:** Sidecar binary name aligned with CI
  (`tars-sidecar-<triple>` via `bundle.externalBin`); legacy
  `tars-backend` resolution kept as fallback for one minor version.
- **Wave 72:** `/api/product/downloads` defaults reduced to Mac-only
  artifacts so the manifest never advertises files the `/dl/<file>`
  proxy will 404.

### Removed
- **Wave 71-B:** False marketing claims about marketplace, "5 native
  skills", `sqlite-vec` (not yet wired), and live T2T.
- **Wave 72:** Russian i18n dictionary (~780 lines, already unreachable
  after Wave 70 force-EN).
- **Wave 71 (simplify):** 3D neural-brain, quests UI, surplus personas
  removed from main cockpit (kept under `experiments/` for posterity).

### Known limitations
- **macOS only.** Windows / Linux installers scheduled for v9.2.
- **No marketplace.** Third-party skill registry scaffolded (Wave 49,
  96–97) but not live; v9.2 MVP, v9.3 with payouts.
- **No live T2T.** Mock escrow only (Wave 81); live counterparty
  discovery in v9.3.
- **Single-user.** Multi-tenant + JWT auth scheduled for v10.0.
- **Magic-link auth** depends on the meeet.world brother backend
  (token mint endpoint). Onboarding wizard UI ships; live mint pending
  in v9.1.1.
- **AI Clone is v0.1** — style hint, not fine-tuned clone. v9.2 ships
  full style replication via fine-tuned model.
- **No notarization.** Ad-hoc codesigned only. First-run
  `xattr -dr com.apple.quarantine` documented in `install.sh`.
- **No STT on-device** — Whisper API call (Wave 73). On-device pipeline
  not in v9.1.0.

Full breakdown: [`docs/WHAT_WORKS.md`](docs/WHAT_WORKS.md). Forward
plan: [`docs/ROADMAP.md`](docs/ROADMAP.md).

### Migrations
- **Pairing store:** in-memory → `~/.tars/pairings.sqlite` (auto-created
  on first sidecar boot). Set `TARS_PAIRINGS_DB=disabled` to opt back
  into in-memory only (tests / packaged distros).
- **Sidecar binary name:** `tars-backend` → `tars-sidecar-<triple>`.
  Legacy resolution kept as a fallback for v9.1.x; will be removed in
  v9.2.
- **Locale type:** `Locale` in `@/lib/i18n` is now `"en"` only. Code
  that did `setLocale("ru")` no longer type-checks (was a no-op anyway
  after Wave 70).

### Credits
- Operator: alienram@icloud.com
- Backend & desktop: brother-of-meeet.world
- Marketing & cockpit: meeet.world team + Lovable
- Wave 72 launch hardening + Wave 73 + Wave 74 docs: Claude

---

## Earlier history

For releases before v9.1.0, see [`docs/CHANGELOG_AGENTS.md`](docs/CHANGELOG_AGENTS.md)
(per-wave append-only log). Notable milestones:

- **v9.0** (Wave Final-8) — first installable; honest WHAT_WORKS
  baseline; OAuth bridge + health endpoint + connector status badges.
- **v8.x** (Waves 65 → 138) — Background TARS, receipt ledger, native
  skills MVP, T2T mock escrow, MCP server reference, AI Clone v1
  (heuristic), Skill SDK, marketplace REST + browse page,
  multi-tenant scaffolding, edge compute adapter, OpenTelemetry,
  subscription tiers, public skill ratings.
- **v8.0** (Wave 40) — JARVIS → TARS rebrand merged with v7.6
  monorepo.
- **v7.x** — Original 8 agents (browser/code/shell/vision/advisor/
  builder/cursor/local_model), multi-user + JWT, plugin signing,
  Workflow Engine, Knowledge Brain.
