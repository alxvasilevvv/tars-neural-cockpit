# WHAT_WORKS — TARS v9.1.0 honest capability ledger

> **Source of truth** for what actually works in v9.1.0.
> Maintained for the operator (brother / Cursor) and for investor
> conversations where over-claiming is worse than under-claiming.
> Updated by **Wave 109 (2026-05-10)** after the B2B production
> suite (Waves 94-108) shipped on top of the Workshop suite (Waves 80-92).
>
> **What just shipped:** see [`RELEASE_NOTES_v9.1.0.md`](RELEASE_NOTES_v9.1.0.md).
> **What's coming:** see [`ROADMAP.md`](ROADMAP.md).
> **Wake-up handoff (operator):** see [`HANDOFF_WAKE_UP.md`](HANDOFF_WAKE_UP.md).

Legend:
- **FULLY IMPLEMENTED** — code path exists, ships in v9.1.0, has tests
  or live smoke verification, end-user can hit it.
- **PARTIAL / STUB** — wired in, returns deterministic responses, but
  the underlying integration is mocked / OAuth-only / behind a feature flag.
- **NOT IMPLEMENTED** — referenced in marketing or older docs but no
  shipping code path; do **not** demo this.

---

## FULLY IMPLEMENTED (real, in-product, tested)

### Core platform

| Capability | Files |
| --- | --- |
| Wallet / SOL+SPL balance + spend | `backend/core/wallet/service.py`, `web_extras/routers/wallet.py` |
| Council agents (6 packs + router) | `backend/core/council/`, `backend/agents/`, `backend/core/router/` |
| Planner (chain agents → run) | `backend/core/planner/`, `backend/core/planner/store.py` |
| Playbooks (deterministic recipes, recursive loader) | `playbooks/`, `backend/core/playbooks/` |
| Chat (multi-thread, SQLite-backed) | `backend/core/chat/store.py`, `web_extras/routers/chat.py` |
| Memory KV (per-pack, TTL, SQLite) | `backend/core/memory/store.py` |
| TTS (XTTS-v2 + system fallback) | `backend/core/voice/synthesis.py`, `web_extras/routers/voice.py` |
| STT (Whisper API; 503 when no key) *(Wave 73)* | `backend/core/voice/transcribe.py`, `web_extras/routers/voice.py` |
| Voice intents (parse + dispatch) | `backend/core/speech/intents.py`, `backend/core/agents/router.py` |
| Pairing (host identity + QR) | `backend/core/pairing/store.py` *(SQLite-backed in Wave 72)*, `backend/core/crypto/` |
| Recovery (passphrase → vault) | `backend/core/vault/`, `backend/core/crypto/recovery.py` |
| Meeet bridge (relayer + economy) | `backend/core/meeet/`, `web_extras/routers/meeet*.py` |
| Entitlements (tier gating) | `backend/core/entitlements/`, `web_extras/routers/entitlements.py` |
| 6 domain packs | `backend/core/domains/packs/{wealth,health,family,product,brand,entrepreneur}/` |
| Tauri desktop sidecar | `desktop/src-tauri/src/{main.rs,sidecar.rs}` |
| Sidecar crash watcher (Wave 61) | `desktop/src-tauri/src/sidecar.rs` (watcher thread) |
| Updater channel (live JSON) | `backend/core/product/updater.py`, `web_extras/routers/product.py` |
| Receipt ledger (signed events) | `backend/core/receipts/` |
| Watch-me-work (real WS events) | `backend/core/orchestrator/`, `web_extras/routers/search.py` (`timeline_router`) |
| Health endpoint + cockpit indicator | `web_extras/app.py` (`@app.get("/health")`), frontend Status page |
| OAuth bridge protocol | `backend/core/oauth_bridge/`, `web_extras/routers/oauth_consent.py` |
| GitHub connector (token-based read; 60s LRU) *(Wave 73)* | `web_extras/routers/github.py` |
| Memory reflection (weekly ISO-week summary) *(Wave 73)* | `backend/core/memory/reflection.py`, `playbooks/_global/memory_reflection.json` |
| AI Clone v0.1 (style traits skeleton — *style hint, not full clone*) *(Wave 73)* | `backend/core/clone/style.py`, `web_extras/routers/clone.py` |
| AI Clone v0.2 — style persistence (export/import envelope + debounced webhook sync) *(Wave 151)* | `backend/core/clone/sync.py`, `web_extras/routers/clone.py` (`/api/clone/export`, `/api/clone/import`), `tests/test_clone_sync.py` |
| Background TARS daemon — macOS LaunchAgent + Linux systemd user-unit + heartbeat *(Waves 152 + 153)* | `backend/core/daemon/{__init__,runner,launchd,systemd,__main__}.py`, `scripts/tars-daemon`, `tests/test_daemon.py`, `docs/contracts/BACKGROUND_DAEMON.md` |
| `tars-doctor` — single-command health check across MCP / Clone sync / daemon / scheduler / webhooks / cowork / receipts / vault *(Wave 154)* + HTTP `/api/doctor` *(Wave 155)* + self-contained HTML dashboard at `/api/doctor/page` *(Wave 156)* | `backend/core/doctor/`, `web_extras/routers/doctor.py`, `scripts/tars-doctor`, `tests/test_doctor*.py`, `docs/contracts/DOCTOR.md` |
| iMessage bridge — macOS send (AppleScript) + read (chat.db) *(Wave 160)* | `backend/core/notifications/{__init__,imessage}.py`, `tests/test_imessage.py`, `docs/contracts/IMESSAGE.md` |
| Telegram notifier — cross-platform Bot-API send + doctor fan-out helper *(Wave 161)* | `backend/core/notifications/telegram.py`, `tests/test_telegram_notify.py`, `docs/contracts/IMESSAGE.md` (Telegram section) |
| Smart Agent Router (LLM intent routing; opt-in `TARS_SMART_ROUTER=1`) *(Wave 73)* | `backend/core/agents/router.py`, `web_extras/routers/agents.py` |
| OpenTelemetry exporter wrapper (no-op unless OTLP endpoint set) *(Wave 73)* | `backend/core/observability/otel.py` |
| /dl proxy → GitHub Releases | `experiments/neural-showcase-v3/functions/dl/[file].ts` |
| Marketing landing + cockpit shell | `experiments/neural-showcase-v3/src/` |

### Workshop suite (Waves 80-92)

8 routes + tutorial overlay + 20+ playbooks + 8 markdown templates.
Frontend pages render today; backend hooks are explicit-stub-on-fallback
where the real backend isn't wired yet (cohort live SSE is mock — see
"Honesty caveats" below).

| Capability | Files |
| --- | --- |
| `/workshop` — generic 4-phase wizard (Intake → Design → Test → Deploy) *(Wave 80)* | `experiments/neural-showcase-v3/src/pages/Workshop.tsx`, `src/components/workshop/{AgentDesigner,Backtest}.tsx` |
| `/workshop/enterprise` — branded B2B workshop landing *(Wave 81 → genericized Wave 87)* | `experiments/neural-showcase-v3/src/pages/EnterpriseWorkshop.tsx` |
| `/workshop/roi` — interactive ROI calculator *(Wave 84)* | `experiments/neural-showcase-v3/src/pages/WorkshopROI.tsx` |
| `/workshop/materials` — handouts + recipe library + video placeholders *(Wave 85)* | `experiments/neural-showcase-v3/src/pages/WorkshopMaterials.tsx` |
| `/workshop/assess` — pre-workshop self-assessment quiz (12 Q × 4 categories) *(Wave 88)* | `experiments/neural-showcase-v3/src/pages/WorkshopAssess.tsx` |
| `/workshop/cohort` — facilitator dashboard with **real SSE + attendee tracking** *(Wave 89 → Wave 94 backend)* | `experiments/neural-showcase-v3/src/pages/WorkshopCohort.tsx`, `backend/core/cohort/`, `web_extras/routers/cohort.py` |
| `/compliance` — receipts feed + filters + CSV export + ReceiptVerifier *(Wave 80-D)* | `experiments/neural-showcase-v3/src/pages/Compliance.tsx`, `src/components/compliance/ReceiptVerifier.tsx` |
| In-app tutorial overlay across all workshop pages *(Wave 92)* | tutorial overlay component used by Workshop / EnterpriseWorkshop / ROI / Materials / Assess / Cohort |
| 20+ starter playbooks across 5 verticals + quant pack | `playbooks/_workshop/{fund,saas,dao,family-office,algotrade,quant}/` |
| 8 enterprise-template markdown handouts (5 emails + facilitator runbook + feedback survey + README) | `docs/workshop/enterprise-template/` |
| Workshop content contracts | `docs/B2B_WORKSHOP.md`, `docs/contracts/WORKSPACES.md`, `docs/contracts/SKILL_SDK.md` |

### Webhooks (Wave 90)

| Capability | Files |
| --- | --- |
| Webhooks module — outgoing dispatcher + signed delivery + inbound playbook trigger | `backend/core/webhooks/{models,store,signing,dispatcher,dispatcher_loop,inbox}.py`, `web_extras/routers/webhooks.py` |
| Webhook contract v1.0 (HMAC signing, retry, dead-letter, inbox queue) | same |

### Connectors — real OAuth + bridges (Waves 91, 108)

| Capability | Files |
| --- | --- |
| Slack connector (real OAuth + channels/DMs read) | `backend/core/connectors/slack.py`, `web_extras/routers/connectors.py` |
| Gmail connector (real OAuth + thread read) | `backend/core/connectors/gmail.py`, `web_extras/routers/connectors.py` |
| Google Calendar connector (real OAuth + events read) | `backend/core/connectors/calendar.py`, `web_extras/routers/connectors.py` |
| Telegram connector (bot bridge — long-poll + webhook + outbound message) *(Wave 108)* | `backend/core/connectors/telegram.py`, `web_extras/routers/connectors.py` |

> Slack/Gmail/Calendar require `OAUTH_BRIDGE_*` env wired to brother's
> meeet.world bridge. URL-based OAuth flow ships; **Quick Connect
> Chrome flow is not yet wired** (URL-redirect only). Telegram requires
> `TELEGRAM_BOT_TOKEN`. See "Honesty caveats" below.

### B2B operational suite (Waves 94-108)

The post-launch B2B production sprint — full operational stack for
funds / SaaS / DAO / family-office / agency-style customers.

| Capability | Files |
| --- | --- |
| Cohort backend — real attendee tracking + live SSE *(Wave 94)* | `backend/core/cohort/{models,store,events}.py`, `web_extras/routers/cohort.py`, `experiments/neural-showcase-v3/src/pages/WorkshopCohort.tsx` |
| Receipt ledger unified — hash chain + Merkle root + Solana memo anchor *(Wave 95)* | `backend/core/receipts/{ledger,chain,merkle,anchor}.py`, `web_extras/routers/receipts.py`, `docs/contracts/RECEIPTS.md` |
| Reporting dashboard — `/dashboard` with 10 widgets, 5 default layouts, drag-resize *(Wave 96)* | `experiments/neural-showcase-v3/src/pages/Dashboard.tsx`, `src/components/dashboard/widgets/*` |
| Playbook scheduler — cron-based, persisted, restart-safe *(Wave 97)* | `backend/core/scheduler/{cron,store,runner}.py`, `web_extras/routers/scheduler.py`, `docs/contracts/SCHEDULER.md` |
| Email outreach — Gmail send + AI Clone drafting + HIL gate + 5 starter templates *(Wave 98)* | `backend/core/outreach/{templates,sender,drafts}.py`, `web_extras/routers/outreach.py`, `experiments/neural-showcase-v3/src/pages/Outreach.tsx`, `docs/contracts/OUTREACH.md` |
| Org onboarding — `/onboard/org` 5-step wizard (org type / size / pillars / connectors / first playbook) *(Wave 99)* | `experiments/neural-showcase-v3/src/pages/OrgOnboarding.tsx`, `backend/core/org/{models,store}.py`, `web_extras/routers/org.py` |
| HIL inbox — `/inbox` approval queue + bulk approve + policy thresholds *(Wave 101)* | `experiments/neural-showcase-v3/src/pages/Inbox.tsx`, `backend/core/policy/`, `web_extras/routers/policy.py` |
| Files management — `/files` document UI + bulk ops + 8 categories + tagging *(Wave 102)* | `experiments/neural-showcase-v3/src/pages/Files.tsx`, `backend/core/files/{store,categories}.py`, `web_extras/routers/files.py`, `docs/contracts/FILES.md` |
| Reports — `/reports` 6 templates (LP, board, weekly digest, compliance, KPI, postmortem) + scheduling + delivery *(Wave 103)* | `experiments/neural-showcase-v3/src/pages/Reports.tsx`, `backend/core/reports/{templates,renderers,scheduler}.py`, `web_extras/routers/reports.py`, `docs/contracts/REPORTS.md` |
| Compliance export — audit-grade bundle (receipts + ledger + Merkle proofs + verifier script + GDPR + PII redaction) *(Wave 104)* | `backend/core/compliance_export/{bundler,gdpr}.py`, `web_extras/routers/compliance_export.py`, `docs/contracts/COMPLIANCE_EXPORT.md` |
| E2E test suite — 10 cross-module scenarios (12 pass + 1 skip) *(Wave 105)* | `tests/e2e/`, `docs/testing/E2E_SUITE.md` |
| Marketplace v0 — in-process registry + `/marketplace` browse + install + local ratings + 12 seed listings *(Wave 106)* | `backend/core/marketplace/{registry,store,ratings}.py`, `web_extras/routers/marketplace.py`, `experiments/neural-showcase-v3/src/pages/Marketplace.tsx`, `docs/contracts/MARKETPLACE.md` |
| Vertical bundles — 7 org-type ready-to-demo packs (fund / saas / dao / family-office / agency / enterprise / nonprofit) at `/bundles` *(Wave 107)* | `backend/core/bundles/{fund,saas,dao,family_office,agency,enterprise,nonprofit}.py`, `web_extras/routers/bundles.py`, `experiments/neural-showcase-v3/src/pages/Bundles.tsx`, `docs/contracts/BUNDLES.md` |
| Performance dashboard — `/admin/perf` ops monitoring (latency p50/p95/p99 + throughput + error rate + active sessions) *(Wave 108)* | `experiments/neural-showcase-v3/src/pages/PerfDashboard.tsx`, `backend/core/observability/{otel,latency}.py`, `web_extras/routers/perf.py`, `docs/contracts/PERF_DASHBOARD.md` |
| **Cowork — multiplayer agent sessions** (shared sessions + presence + cursors over shared paths + one-click ownership handoff via short-TTL token). Closes W122 audit gaps on tasks #99 + #100 which had historically been marked complete but had no live backend code. *(Waves 129-132)* | `backend/core/cowork/{models,store,presence,stream,handoff}.py`, `experiments/neural-showcase-v3/src/pages/Cowork.tsx`, `experiments/neural-showcase-v3/src/lib/cowork.ts`, `experiments/neural-showcase-v3/src/components/cowork/{PresenceBar,SessionViewer,HandoffDialog}.tsx`, `experiments/neural-showcase-v3/src/components/CoworkPreview.tsx`, `tests/test_cowork_{store,presence}.py`, `docs/contracts/COWORK.md`. Backend module ships in this release; the 10 `/api/cowork/*` HTTP routes land in v9.1.1 (brother handoff at `docs/handoff/COWORK_WIRING_FOR_CURSOR.md`). Frontend transparently mocks until then. |
| **Orchestrator → Cowork fan-out** (agents pass `cowork_session_id` in task metadata → runner emits `task.started`/`completed`/`failed` frames onto the live session) *(Wave 131)* | `backend/core/agents/runner.py` |
| **Cowork HTTP routes** (FastAPI router, 10 endpoints per `docs/contracts/COWORK.md` v1.0 — `/api/cowork/*` callable on `make backend-tars-up`) *(Wave 149)* | `web_extras/routers/cowork.py`, `web_extras/app.py`, `tests/test_cowork_router.py` (12 cases) |
| **MCP server bridge** (stdio JSON-RPC 2.0, 5 built-in tools: `tars.{version,list_playbooks,run_playbook,recent_events,cowork_session}`, conforms to MCP spec 2024-11-05) *(Wave 150)* | `backend/core/mcp/{__init__,protocol,tools,server,__main__}.py`, `tests/test_mcp_server.py` (21 cases), `docs/contracts/MCP.md`. Closes historic task #17 + #85 dishonest-done drift. |

### Hardening (Waves 72, 79)

| Capability | Files |
| --- | --- |
| Pre-launch security audit (rate limits + wallet policy gate) | `docs/security/AUDIT_2026-05-09.md` |
| Rate limits on `/voice/transcribe`, `/agents/route`, `/clone/draft` | `web_extras/routers/{voice,agents,clone}.py` |
| Wallet `sign_message` policy gate | `backend/core/wallet/service.py` |
| Release pipeline hardened (CI tag → signed dmg + minisign-pubkey-patched updater) | `.github/workflows/release-desktop-tagged.yml` |
| Eval suite in CI (non-blocking) | `.github/workflows/eval-suite.yml`, `web_extras/eval/` |

---

## PARTIAL / STUB (wired but not "real" — set expectations)

| Capability | Status | Files |
| --- | --- | --- |
| Slack/Gmail/Calendar — Quick Connect Chrome flow | URL-based OAuth ships (Wave 91); one-click Chrome extension flow pending. v9.1.1. | `backend/core/connectors/`, `web_extras/routers/connectors.py` |
| GitHub connector — write side | Read shipped Wave 73; PR creation / issue write pending. v9.3 with webhooks. | `web_extras/routers/github.py` |
| Webhooks `receipt.*` event emission (broad) | Contract v1.0 + dispatcher ship Wave 90; `receipt.*` events fire from algotrade + the unified receipt ledger (Wave 95). Other emit sites (outreach, scheduler, files, reports, compliance) wire incrementally. v9.3 for full coverage. | `backend/core/webhooks/`, `backend/core/receipts/` |
| Background TARS daemon (macOS + Linux parity) *(Waves 152 + 153)* | Real `launchd` LaunchAgent **and** `systemd --user` unit, platform-auto via `python -m backend.core.daemon --install`. Heartbeat at `~/.tars/daemon.heartbeat`. Windows still pending (v9.2 target). | `backend/core/daemon/`, `scripts/tars-daemon`, `docs/contracts/BACKGROUND_DAEMON.md` |
| iMessage bridge (macOS-only — send via AppleScript + read chat.db) *(Wave 160)* | Real bridge. `send_imessage(handle, text)` via `osascript`; `recent_messages(limit)` reads `~/Library/Messages/chat.db` (requires Full Disk Access). Telegram + Email modules still v9.1.2. | `backend/core/notifications/{__init__,imessage}.py`, `docs/contracts/IMESSAGE.md` |
| Marketplace v0 — payouts | Browse + install + ratings ship Wave 106; **70/30 payouts NOT live** (still need brother's payout rails + per-jurisdiction legal). v9.3. | `backend/core/marketplace/`, `web_extras/routers/marketplace.py` |
| Marketplace v0 — third-party publishing | In-process registry only (12 seed listings); third-party submit flow + ed25519 signing pending. v9.2 with Skill SDK. | same |

---

## NOT IMPLEMENTED in v9.1.0 (do NOT demo / claim)

| Capability | Status | Roadmap |
| --- | --- | --- |
| AI Clone v1 (real fine-tune) | v0.1 ships Wave 73 (style hint); v0.2 ships Wave 151 (style **persistence** via export/import envelope + debounced webhook sync — *still the same heuristic, just cross-machine portable*); Wave 98 outreach uses style-hint draft. Real fine-tuned per-user clone pending. | v9.2 |
| Wake-word (web variant) | Browser experiment removed; native equivalent missing | v9.1.1 (web wasm Picovoice / PWA) |
| Magic-link auth (real, end-to-end) | Onboarding wizard UI shipped; live token mint depends on brother backend | v9.1.1 |
| Pyoxidizer Win/Linux desktop builds | CI only ships macOS dmg/app for v9.1.0 | v9.2 |
| `sqlite-vec` extension wired | Memory KV does cosine in Python today | v9.2 |
| XTTS-v2 voice cloning (separate sidecar bundle) | TTS ships; voice-cloning bundle not yet | v9.2 |
| Skill SDK (third-party packaging spec + signing) | Scaffolding shipped earlier; public spec + third-party publish flow pending. Marketplace v0 uses in-process registry. | v9.2 |
| T2T (TARS-to-TARS handshake, live) | Mock escrow only (Wave 81); no live counterparty discovery | v9.3 |
| Reputation Graph + leaderboard (public UI) | Wave 80 aggregator shipped; public UI pending | v9.3 |
| ~~MCP server bridge (canonical productized form)~~ | **W150 reality fix:** the historic task #17 + #85 entries claimed a reference shipped — code path was absent. W150 actually ships it: `backend/core/mcp/` (stdio JSON-RPC server, 5 built-in tools, 21 pytest cases). See `docs/contracts/MCP.md`. Moved to FULLY IMPLEMENTED. | shipped v9.1.1-dev |
| Multi-tenant Workspaces + JWT auth | Single-user only today; `WORKSPACES.md` contract published; Wave 110 backend MVP in flight (additive, schema-only) | v9.2 (initial) → v10.0 (full) |
| Webhooks central registry (cross-tenant) | Per-instance webhook registry today; cross-tenant central registry pending. | v9.3 |
| Organizations + Teams + RBAC | Org/team scaffolding exists, role assignment UI does not | v10.0 |
| ~~Shared agent sessions (multiplayer)~~ | **MOVED TO FULLY IMPLEMENTED at Wave 129** — see Cowork row in "B2B operational suite" above | shipped v9.1.0 |
| ~~TARS Handoff (viral hand-off between users)~~ | **MOVED TO FULLY IMPLEMENTED at Wave 129** — see Cowork row in "B2B operational suite" above | shipped v9.1.0 |
| Edge compute adapter for voice latency | Local adapter shipped earlier; edge variant pending | v10.0 |

Full forward-looking detail: [`ROADMAP.md`](ROADMAP.md).

---

## Honesty caveats (Wave 71-B / 74 / 93 / 109 principle)

- **Workshop cohort is real now** — Wave 94 backend ships real
  attendee tracking + SSE; the Wave 89 mock fallback is gone.
- **Workshop tutorial overlay** is a guided tour — it does NOT track
  attendee progression. Progression tracking lives in the cohort
  module proper.
- **Webhooks contract ships + the unified receipt ledger emits
  `receipt.*` events (Wave 95).** Per-feature emit sites (outreach,
  scheduler, files, reports, compliance) are wired incrementally;
  full coverage targets v9.3.
- **Slack / Gmail / Calendar OAuth** is the URL-redirect flow only.
  The "Quick Connect" Chrome extension flow is not in v9.1.0 — that's
  v9.1.1.
- **Telegram connector** ships as a bot bridge (Wave 108). Long-poll
  + webhook + outbound work today; **iMessage bridge is still a
  Mac-only stub** awaiting the FullDiskAccess UX (v9.1.1).
- **Marketplace v0** ships browse + install + local ratings + 12
  seed listings (Wave 106). **Payouts and third-party publishing are
  v9.2/v9.3.** Don't claim "creator economy" yet.
- **Compliance export bundle** (Wave 104) is audit-grade —
  hash-chained receipts + Merkle proofs + verifier script + GDPR
  export + PII redaction. Verifier runs offline.
- **No B2B-customer branding anywhere in code or docs.** Wave 87
  stripped all references to specific named customers / regulatory
  acronyms; everything reads as generic "enterprise B2B" today.

---

## Platform support (v9.1.0)

| Target | Status |
| --- | --- |
| macOS arm64 (Apple Silicon) | shipping (signed ad-hoc, not notarized) |
| macOS x64 (Intel) | best-effort — falls back to arm64 dmg + Rosetta when CI runner is queue-starved |
| Windows | NOT shipping in v9.1.0 (pyoxidizer cross-target pipeline pending) |
| Linux | NOT shipping in v9.1.0 (same reason) |

---

## How this file is maintained

- Wave 72 is the baseline. Wave 93 was the first sync; Wave 109 is
  the second sync (after the B2B production sprint Waves 94-108).
  Every subsequent wave that ships a real capability MUST move its
  row from PARTIAL/STUB or NOT IMPLEMENTED into FULLY IMPLEMENTED,
  with file paths.
- If a capability regresses, demote it. Never delete a row — strike
  it through with the wave number that removed it.
- Marketing copy on `tars.meeet.world` MUST be a strict subset of the
  FULLY IMPLEMENTED column.
