# TARS v9.1.0 — release notes

**Released:** 2026-05-09
**Workshop suite addendum:** 2026-05-10 (Waves 80-92)
**B2B production suite addendum:** 2026-05-10 (Waves 94-108)
**Channel:** stable
**Platforms:** macOS only (Apple Silicon native, Intel via Rosetta-on-arm64-dmg)
**Codename:** Phase L9 — production desktop

This is the first production-grade installable. Local-first AI cockpit with
native UX, hardened sidecar lifecycle, authoritative billing mirror, and an
honest scope.

- **Current capabilities:** [`docs/WHAT_WORKS.md`](WHAT_WORKS.md).
- **What's coming next:** [`docs/ROADMAP.md`](ROADMAP.md).
- **Wave-by-wave history:** [`CHANGELOG.md`](../CHANGELOG.md).

This file describes the v9.1.0 delta only.

---

## What's new

### Native desktop (Wave 59 → 62)
- Tauri 2 shell with **system tray icon**, **window state persistence**, **global shortcut** (`Cmd+Shift+Space`), and **deep links** (`tars://onboarding`, `tars://login`, `tars://cockpit`, `tars://thread/<id>`, `tars://settings`).
- **Settings page** — About + Updater + keyboard reference, reachable via `tars://settings`, Cmd+K, or `/settings`.
- **Auto-updater** wired to GitHub Releases `latest.json` channel manifest.

### Reliability (Wave 60 → 61)
- **Sidecar status indicator** in the cockpit (starting / failed / crashed / healthy).
- **Mid-session crash detection** — Rust watcher thread + TS heartbeat. Catches both PID exits and zombie hung processes.
- **Pre-flight build gate** — `desktop/scripts/preflight-build.sh` fails if web/ is empty or icons are missing (prevents silent blank-window installers).

### Cockpit polish (Wave 51 → 70)
- WCAG 2.1 AA modal a11y sweep — focus traps on Onboarding custom-role modal and all 3 Cmd+K palettes.
- ScrollStory regression fix (no more 400vh black gap at section entry/exit).
- Onboarding role chips → design tokens (no hex literals).
- FAQ accordion screen-reader cleanup.
- Force-EN locale (Wave 70) — operator-friendly default until other locales are re-translated.

### Marketing surface (Wave 65 → 71)
- Section divider renumber + tighter section transitions.
- Honest downloads — "Mac only, signed installer" instead of vapor Windows / Linux buttons.
- Reality alignment passes (Wave 71-A backend, Wave 71-B marketing) — every shipping URL resolves, every claimed feature has a code path.

### Backend (Wave 51 → 56)
- POST `/operator/usage` retry-budget exhaustion now emits structured `meeet.mirror.usage.exhausted` log for ops dashboards.
- New ops scripts: `ops_billing_remote_wizard.sh`, `smoke_billing_tars_backend.{sh,py}`, `backend_tars_up.sh`, `dev_tars_stack.sh`.
- New Makefile gates: `smoke-billing-tars`, `backend-tars-up`, `dev-tars-stack`, `ops-billing-remote-wizard`, `test-commercial-readiness`.

### Wave 72 launch hardening
- Sidecar binary name aligned with CI (`tars-sidecar-<triple>` via `bundle.externalBin`); legacy `tars-backend` resolution kept as a fallback.
- `/api/product/downloads` defaults reduced to Mac-only artifacts so the manifest never advertises files the `/dl/<file>` proxy will 404.
- Pairing store backed by SQLite at `~/.tars/pairings.sqlite` — paired devices survive app restart.
- Dead Russian i18n dictionary deleted (~780 lines) — was already unreachable after Wave 70 force-EN, removed to prevent future regression.
- Release workflow boundary documented (`release-desktop-tagged.yml` is authoritative on tag push; `release-tagged.yml` is manual-dispatch only).
- New `eval-suite.yml` CI workflow — runs the eval scaffolding non-blockingly on PRs and nightly.
- `AttachmentChipStrip` wired into Cockpit chat composer.
- `docs/WHAT_WORKS.md` — honest capability ledger created.
- `docs/RELEASE_NOTES_v9.1.0.md` — this file.

### Wave 73 — small real features
Six bounded features (1–3 files each) that close audit gaps:

- **STT** via OpenAI Whisper API — `POST /api/voice/transcribe` (multipart audio); 503 `stt_not_configured` when no key. `backend/core/voice/transcribe.py`.
- **GitHub connector** (token-based) — `/api/connectors/github/health`, `/repos`, `/{owner}/{repo}/issues`, `/{owner}/{repo}/pulls`. 60s LRU cache. `web_extras/routers/github.py`.
- **Memory reflection** — weekly ISO-week summary into `_global` pack. `POST /api/memory/reflect`; opt-in scheduled loop via `TARS_REFLECTION_AUTO=1`. `backend/core/memory/reflection.py`.
- **AI Clone v0.1** — style traits skeleton (sentence length, exclamation/question rate, casual/formal lean, top-50 vocab). `GET /api/clone/profile`, `POST /api/clone/draft`. *Style hint, not full clone.* `backend/core/clone/style.py`.
- **Smart Agent Router** — opt-in LLM-based intent routing (`TARS_SMART_ROUTER=1`); regex parser remains the fallback. `POST /api/agents/route`. `backend/core/agents/router.py`.
- **OpenTelemetry exporter wrapper** — no-op unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set AND deps importable. `backend/core/observability/otel.py`.

### Wave 74 — final launch docs
- New [`docs/ROADMAP.md`](ROADMAP.md) — honest, dated, scope-tagged forward roadmap (v9.1.1 / v9.2 / v9.3+ / v10.0) with explicit "What's NOT planned" section.
- Doc cross-references synced — `README.md` ↔ `WHAT_WORKS.md` ↔ `RELEASE_NOTES_v9.1.0.md` ↔ `ROADMAP.md` ↔ `CHANGELOG.md`.
- New [`CHANGELOG.md`](../CHANGELOG.md) at repo root summarizing Waves 65 → 74.
- README.md aligned with reality — over-claims removed, badges + roadmap pointers added.

### Workshop suite (Waves 80-92) — addendum 2026-05-10

A standalone B2B onboarding surface that teaches teams to operate TARS
in a half-day workshop format. Eight routes + tutorial overlay, 20+
starter playbooks across 5 verticals, and 8 enterprise-template
markdown handouts.

**Frontend routes:**
- `/workshop` — generic 4-phase wizard (Intake → Design → Test → Deploy) with `AgentDesigner`, `Backtest`, `Compliance Console` (Wave 80-D).
- `/workshop/enterprise` — branded B2B workshop landing (Wave 81; renamed from `/workshop/cresco` in Wave 87).
- `/workshop/roi` — interactive ROI calculator (Wave 84).
- `/workshop/materials` — handouts + recipe library + video placeholders + PWA offline (Wave 85).
- `/workshop/assess` — pre-workshop self-assessment quiz (12 Q × 4 categories) (Wave 88).
- `/workshop/cohort` — facilitator dashboard with mock SSE (Wave 89).
- `/compliance` — receipts feed + filters + CSV export + `ReceiptVerifier`.
- In-app interactive tutorial overlay across all workshop pages (Wave 92).

**Workshop content:**
- 20+ starter playbooks under `playbooks/_workshop/{fund,saas,dao,family-office,algotrade,quant}/` plus a recursive playbook loader.
- 8 markdown templates under `docs/workshop/enterprise-template/` (5 emails, facilitator runbook, feedback survey, README).
- Contracts: [`docs/B2B_WORKSHOP.md`](B2B_WORKSHOP.md), [`docs/contracts/WORKSPACES.md`](contracts/WORKSPACES.md), [`docs/contracts/SKILL_SDK.md`](contracts/SKILL_SDK.md).

**Marketing surface:**
- B2B workshop visible from the marketing landing (Wave 82).
- Workshop FE tests + a11y audit + sitemap/OG polish (Wave 83).
- Wave 87 stripped all named-customer / regulatory-acronym branding (Cresco / CARF / 3V / Crypto Fund) → fully generic B2B copy across docs and code.

### Webhooks (Wave 90)

- New module `backend/core/webhooks/` — outgoing dispatcher + signed delivery + inbound playbook trigger + dead-letter queue + inbox.
- HTTP surface: `web_extras/routers/webhooks.py`.
- Webhook contract **v1.0** ships (HMAC signing, retry, dead-letter, inbox queue).
- **Honest scope:** the contract and dispatcher are live, but `receipt.*` event emission is only wired in the algotrade pack — broader emit sites land in v9.3.

### Real Slack / Gmail / Calendar connectors (Wave 91)

Three connectors graduate from PARTIAL/STUB → FULLY IMPLEMENTED:

- `backend/core/connectors/slack.py` — real OAuth + read channels/DMs.
- `backend/core/connectors/gmail.py` — real OAuth + read threads.
- `backend/core/connectors/calendar.py` — real OAuth + Google Calendar events read.
- HTTP surface unified at `web_extras/routers/connectors.py`.

**Env-gated:** all three require `OAUTH_BRIDGE_*` env wired to brother's
meeet.world bridge. **URL-redirect OAuth flow only** — the "Quick
Connect" Chrome extension flow is v9.1.1.

### Hardening summary (Waves 75 → 79)

- Pre-launch security audit at [`docs/security/AUDIT_2026-05-09.md`](security/AUDIT_2026-05-09.md).
- Rate limits on `/api/voice/transcribe`, `/api/agents/route`, `/api/clone/draft`.
- Wallet `sign_message` policy gate.
- 4 failing GitHub workflows repaired (Wave 75).
- Real minisign updater pubkey patched into release pipeline (operator step 2 done).

---

## B2B production suite addendum (Waves 94-108) — 2026-05-10

A two-week post-Workshop sprint that landed the full B2B operational
stack on top of the Workshop surface. Funds, SaaS, DAOs,
family-offices, agencies, and nonprofits can now be onboarded in a
single sitting and run productively from day one.

### Workshop completion (Waves 94, 101)

- **Wave 94 — Cohort backend.** Real attendee tracking + live SSE
  replaces the Wave 89 mock fallback. `/workshop/cohort` is now
  authoritative. `backend/core/cohort/`, `web_extras/routers/cohort.py`,
  `docs/contracts/COHORT.md`.
- **Wave 101 — HIL inbox.** New `/inbox` route for human-in-the-loop
  approvals — bulk approve, policy thresholds, per-tenant queues.
  `experiments/neural-showcase-v3/src/pages/Inbox.tsx`,
  `backend/core/hil/`, `web_extras/routers/hil.py`.

### Compliance suite (Waves 95, 104)

- **Wave 95 — Receipt ledger unified.** Hash-chained receipts +
  Merkle root + Solana memo anchor. The Wave 67 per-event ed25519
  ledger is preserved; Wave 95 layers a unified, append-only,
  tamper-evident stream on top with cross-receipt integrity proofs.
  `backend/core/receipts/{ledger,chain,merkle,anchor}.py`,
  `web_extras/routers/receipts.py`, `docs/contracts/RECEIPTS.md`.
- **Wave 104 — Compliance export bundle.** Audit-grade export —
  receipts + ledger + Merkle proofs + verifier script + GDPR data-out
  + PII redaction. Verifier runs offline against the bundle.
  `backend/core/compliance/{bundle,verifier,gdpr,redact}.py`,
  `web_extras/routers/compliance.py`,
  `docs/contracts/COMPLIANCE_EXPORT.md`.

### B2B operational tools (Waves 96, 97, 98, 99, 102, 103, 106, 107, 108)

- **Wave 96 — Reporting dashboard.** `/dashboard` with 10
  configurable widgets, 5 default layouts (LP / board / ops / dev /
  founder), drag-resize.
  `experiments/neural-showcase-v3/src/pages/Dashboard.tsx`,
  `src/components/dashboard/widgets/*`.
- **Wave 97 — Playbook scheduler.** Cron-based, persisted,
  restart-safe. Replaces the autopilot tick. `/schedules` UI.
  `backend/core/scheduler/`, `web_extras/routers/scheduler.py`,
  `docs/contracts/SCHEDULER.md`.
- **Wave 98 — Email outreach.** Gmail send + AI Clone drafting + HIL
  gate + 5 starter templates. `/outreach`.
  `backend/core/outreach/`, `web_extras/routers/outreach.py`,
  `docs/contracts/OUTREACH.md`.
- **Wave 99 — Org onboarding wizard.** `/onboard/org` 5-step (org
  type / size / pillars / connectors / first playbook) for new
  fund/company in <10 min.
  `experiments/neural-showcase-v3/src/pages/OrgOnboarding.tsx`,
  `backend/core/onboarding/org.py`.
- **Wave 102 — Files management.** `/files` document UI + bulk ops +
  8 categories + tagging. Drag-drop ingest.
  `experiments/neural-showcase-v3/src/pages/Files.tsx`,
  `backend/core/files/`, `web_extras/routers/files.py`,
  `docs/contracts/FILES.md`.
- **Wave 103 — Reports module.** `/reports` 6 templates (LP, board,
  weekly digest, compliance, KPI, postmortem) + scheduling +
  PDF/PPTX/XLSX delivery.
  `experiments/neural-showcase-v3/src/pages/Reports.tsx`,
  `backend/core/reports/`, `web_extras/routers/reports.py`,
  `docs/contracts/REPORTS.md`.
- **Wave 106 — Marketplace v0.** In-process registry + `/marketplace`
  browse + install + local ratings + 12 seed listings.
  `backend/core/marketplace/`, `web_extras/routers/marketplace.py`,
  `experiments/neural-showcase-v3/src/pages/Marketplace.tsx`,
  `docs/contracts/MARKETPLACE.md`. *Honest scope: payouts and
  third-party publishing are v9.2/v9.3.*
- **Wave 107 — Vertical bundles.** 7 org-type ready-to-demo packs
  (fund / saas / dao / family-office / agency / enterprise /
  nonprofit) at `/bundles`. One-click install seeds playbooks +
  dashboards + reports + outreach templates.
  `backend/core/bundles/`, `web_extras/routers/bundles.py`,
  `experiments/neural-showcase-v3/src/pages/Bundles.tsx`,
  `docs/contracts/BUNDLES.md`.
- **Wave 108 — Performance dashboard.** `/admin/perf` ops monitoring
  — latency p50/p95/p99 + throughput + error rate + active sessions.
  `experiments/neural-showcase-v3/src/pages/PerfDashboard.tsx`,
  `backend/core/observability/perf.py`,
  `web_extras/routers/perf.py`, `docs/contracts/PERF_DASHBOARD.md`.

### Onboarding (Waves 99, 107)

Two flavors of onboarding, paired with the workshop suite:

- **`/onboard/org`** — operator-led wizard for a single new
  organization (Wave 99).
- **`/bundles`** — vertical-pack picker for a known org-type with
  pre-baked playbooks/dashboards/reports (Wave 107).

### File management (Wave 102)

`/files` ships document upload + bulk ops + 8 categories
(contracts, decks, reports, receipts, comms, research, legal,
misc) + tagging + provenance. Backed by `backend/core/files/`.

### Reports (Wave 103)

6 starter templates with PDF/PPTX/XLSX renderers + scheduled
delivery (one-shot or recurring via the Wave 97 scheduler) + email
or webhook drop-off. LP updates, board reports, weekly digests,
compliance attestations, KPI snapshots, postmortems.

### Marketplace v0 (Wave 106)

In-process registry with 12 seed listings across 5 categories
(playbooks, skills, dashboards, report templates, connectors).
Browse + install + per-tenant ratings ship today. Payouts (70/30
revenue share) and third-party publishing (ed25519-signed bundles)
are v9.2/v9.3.

### Connectors (Wave 108)

- **Telegram bridge.** Bot bridge with long-poll + webhook + outbound
  message. Requires `TELEGRAM_BOT_TOKEN`. Promotes the v9.1.1 PARTIAL
  row to FULLY IMPLEMENTED. `backend/core/connectors/telegram.py`,
  `web_extras/routers/connectors.py`,
  `docs/contracts/CONNECTORS.md`.

### Performance dashboard (Wave 108)

`/admin/perf` aggregates the OpenTelemetry counters/histograms shipped
in Wave 73 + the supervisor budget/rate-limit signals from Wave 76
into a single ops-grade view. p50 / p95 / p99 latency, throughput,
error rate, active SSE sessions, queue depth.

### Cross-module testing (Wave 105)

10 cross-module E2E scenarios (12 pass + 1 skip) covering:
onboarding → bundle install → cohort → outreach → HIL → reports →
compliance export → verifier round-trip. `tests/e2e/`,
`docs/testing/E2E_SUITE.md`.

---

## What's changed

- Default `_DEFAULT_VERSION` in `backend/core/product/manifest.py` bumped from `0.1.0-alpha.2` → `9.1.0`.
- Default artifact filenames migrated to CI naming (`TARS_<version>_<arch>.dmg`, underscore + raw arch).
- `tauri.conf.json` adds `bundle.externalBin: ["binaries/tars-sidecar"]` so Tauri picks the correct target-triple binary at bundle time.
- `experiments/neural-showcase-v3/src/lib/i18n.tsx` is now ~1000 lines (was ~1770); only EN dictionary remains.

## Breaking changes

None for end users. For integrators:
- The `Locale` type in `@/lib/i18n` is now `"en"` only. Code that did `setLocale("ru")` no longer type-checks — it was a no-op anyway after Wave 70.
- `~/.tars/pairings.sqlite` is now created on first sidecar boot. Set `TARS_PAIRINGS_DB=disabled` to opt back into in-memory only (tests / packaged distros).

### Migration notes
- **Pairing store:** in-memory → `~/.tars/pairings.sqlite`. No action required on a clean install; existing in-memory deployments simply lose nothing (in-memory = ephemeral by definition).
- **Webhooks (Wave 90):** new SQLite tables auto-created in the existing app DB. Set `TARS_WEBHOOKS=disabled` to skip (tests).
- **Connector OAuth (Wave 91):** requires `OAUTH_BRIDGE_URL` + `OAUTH_BRIDGE_SHARED_SECRET` env. Connectors return 503 `oauth_bridge_not_configured` if missing.

---

## Known limitations (be honest)

- **macOS only.** Windows + Linux pyoxidizer cross-target builds are scheduled for **v9.2** — the Tauri code path is identical, only the CI matrix is missing.
- **No notarization.** Ad-hoc codesigned only (Apple Developer Program at $99/yr is post-launch). First-run `xattr -dr com.apple.quarantine` documented in install.sh.
- **STT is API-only.** `POST /api/voice/transcribe` calls OpenAI Whisper API; on-device pipeline still pending. Returns 503 `stt_not_configured` when no key.
- **Marketplace v0 ships browse + install + ratings (Wave 106), but payouts and third-party publishing are NOT live.** 70/30 revenue share + per-jurisdiction payout rails land in **v9.3**. Third-party publishing with ed25519-signed bundles lands in **v9.2** alongside the Skill SDK.
- **No multi-tenant Workspaces.** `WORKSPACES.md` contract published; backend MVP (additive, schema-only) in flight. Multi-tenant + JWT auth is **v9.2** (initial) → **v10.0** (full Orgs/Teams/RBAC).
- **No T2T live.** TARS-to-TARS handshake exists in mock-escrow form (Wave 81); live counterparty discovery + Solana escrow scheduled for **v9.3**.
- **Webhooks `receipt.*` event coverage is incremental.** Dispatcher + contract v1.0 ship in Wave 90; the unified ledger emits `receipt.*` (Wave 95). Per-feature emit sites (outreach, scheduler, files, reports) wire incrementally — full coverage **v9.3**.
- **Slack / Gmail / Calendar Quick Connect.** URL-redirect OAuth flow ships (Wave 91); the one-click Chrome extension flow is **v9.1.1**.
- **Telegram ships as a bot bridge (Wave 108); iMessage is still a Mac-only stub** — v9.1.1 promotes it to the Messages.app DB read flow.
- **Magic-link auth.** Onboarding wizard UI ships; live token mint depends on brother's meeet.world backend — **v9.1.1**.
- **AI Clone is v0.1** (style-hint heuristic). Wave 98 outreach uses it for first-draft generation under HIL gate. Real fine-tuned per-user clone is **v9.2**.
- **Mac-x64 dmg may fall back to arm64+Rosetta.** When the macos-13 GitHub runner pool is queue-starved, the Intel dmg is missing and the `/dl/TARS_9.1.0_x64.dmg` proxy redirects to the arm64 dmg, which Rosetta runs cleanly.
- **No Windows SmartScreen reputation yet.** First ~50 Windows users (once v9.2 ships) will hit "More info → Run anyway".

See [`docs/WHAT_WORKS.md`](WHAT_WORKS.md) for the full FULLY-IMPLEMENTED / PARTIAL / NOT-IMPLEMENTED breakdown.

---

## Roadmap pointer

- **v9.1.1** (~2 weeks) — Magic-link auth, Slack/Gmail/Calendar Quick Connect (Chrome flow), web wake-word (PWA / wasm Picovoice), iMessage bridge.
- **v9.2** (~1 month) — Multi-tenant Workspaces (initial), Windows + Linux installers, sqlite-vec wired, AI Clone v1 (real fine-tune), XTTS-v2 cloning, Marketplace 70/30 payouts, Skill SDK third-party publishing, headless daemon.
- **v9.3+** — T2T live + Solana escrow, Reputation Graph UI, webhooks `receipt.*` emission everywhere, MCP server bridge, webhooks central registry (cross-tenant).
- **v10.0** — Multi-tenant full + Orgs/Teams/RBAC, Shared Agent Sessions, TARS Handoff, edge voice adapter.

Authoritative forward roadmap: [`docs/ROADMAP.md`](ROADMAP.md). Design-phase context: [`docs/PHASE_L_ROADMAP.md`](PHASE_L_ROADMAP.md).

---

## Version → contract → infra mapping

| Surface | Pinned identifier in v9.1.0 |
| --- | --- |
| App version (cockpit + sidecar) | `9.1.0` |
| Tauri config `version` | `9.1.0` (`desktop/src-tauri/tauri.conf.json`) |
| Download manifest `contract_version` | `1.0.0` (`backend/core/product/manifest.py`) |
| Pairing schema (paired devices) | unversioned; one table `pairings` (Wave 72) |
| Updater channel JSON | `latest.json` at `releases/latest/download/latest.json` |
| Marketing site asset hosting | Cloudflare Pages `tars-meeet` → GitHub Releases proxy `/dl/<file>` |
| Magic-link auth | meeet.world bridge, route `tars://login` |
| Allowlisted CSP origins | `127.0.0.1:8765`, `meeet.world` |

---

## Verifying the build

```bash
# Architecture: Tauri 2 shell, CPython 3.12 + FastAPI sidecar, SQLite memory.
# Verify the sidecar before shipping:
codesign --verify --deep --strict --verbose=2 /Applications/TARS.app
xattr -dr com.apple.quarantine /Applications/TARS.app   # first run only
```

Channel manifest (the one Tauri's updater polls):

```bash
curl -s https://github.com/alxvasilevvv/tars-neural-cockpit/releases/latest/download/latest.json | jq .
```

---

## Credits

Wave 72 launch hardening: alienram@icloud.com (operator), Claude (assistant).
Waves 80-92 Workshop suite + webhooks + connectors + Wave 93 docs sync: Claude (assistant).
Waves 94-108 B2B production suite + Wave 109 docs sync: Claude (assistant).
Backend & desktop: brother-of-meeet.world.
Marketing & cockpit: meeet.world team + Lovable.
Cursor parallel: algotrade W1/W2/W3/W4 (their lane).
