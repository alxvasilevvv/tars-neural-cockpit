# TARS — Master Project Doc (v9.2.0-beta2 → v10.0 GA)

> **Status:** single source of truth. Written W236 (2026-05-15) by TARS strategy desk.
> **Audience:** the founder (Alien), every future contributor, the brother on
> `meeet.world`, any agent doing pickup work in this repo.
> **Rule of the doc:** if a feature is not in here, it is not the plan.
> Deep-dives still live in `docs/`; this file points at them.
> **Companions:** `PROJECT_INDEX.md` (every doc, one line each), `README.md` (the front door).

This is the one document Alien refers to forever. Re-read §1 (North Star)
and §11 (anti-patterns) before saying yes to any new feature.

---

## Table of contents

- [§1. North Star](#1-north-star)
- [§2. What's shipped (v9.2.0-beta2)](#2-whats-shipped-v920-beta2)
- [§3. Architecture overview](#3-architecture-overview)
- [§4. Cursor parity scorecard](#4-cursor-parity-scorecard)
- [§5. The meeet.world integration story — end-to-end](#5-the-meeetworld-integration-story--end-to-end)
- [§6. Roadmap — beta2 to v10.0 GA](#6-roadmap--beta2-to-v100-ga)
- [§7. Pricing and metering economics](#7-pricing-and-metering-economics)
- [§8. Operating manual](#8-operating-manual)
- [§9. Development workflow](#9-development-workflow)
- [§10. Brother sync brief](#10-brother-sync-brief)
- [§11. North Star anti-patterns](#11-north-star-anti-patterns)
- [§12. Appendix](#12-appendix)

---

## §1. North Star

**Vision.** TARS is **Cursor for everything not just code** — a voice-first,
local-first, receipt-anchored AI cockpit that runs on the operator's Mac.
It is the surface between a human and every model, agent, and cloud service
that human uses. It is the one tool that lasts.

**Positioning (1 sentence).**

> Cursor-grade polish + on-chain transparency + 7 life-domains + voice-native +
> sovereign data, billed through `meeet.world`.

**The 5 truths we build on.**

1. **Local-first.** Data on disk, keys in the OS Keychain, agents on `127.0.0.1`.
   The user can air-gap the laptop and TARS still does everything that does not
   strictly need a cloud LLM call.
2. **Voice-first.** Wake-word -> STT -> router -> action -> TTS -> receipt. The
   cockpit is a cinematic visual surface (W230), not a chat window with a
   microphone strapped on.
3. **Receipt-anchored.** Every consequential action emits a signed receipt.
   Receipts hash-chain. Daily Merkle root anchors on `Solana` as a memo. A
   third party can verify "did this agent really do that?" with no auth and
   no access to our database.
4. **Domain packs over generality.** Seven life-ops surfaces (wealth, health,
   family, product, brand, entrepreneur, civic) where the agent already knows
   the vocabulary and the obvious next move. Not a chat field that says
   "ask me anything."
5. **All roads through `meeet.world`.** Identity, billing, balance, entitlements,
   marketplace payouts, $MEEET economy, compliance telemetry — every cross-machine
   action passes through the brother's domain. TARS is the cockpit; `meeet.world`
   is the ledger and the bank.

**Non-goals (what TARS is NOT).**

- Not a Slack clone. We don't own team chat.
- Not a Notion clone. We don't own the doc/wiki surface.
- Not a code IDE. We don't fork VS Code. (We wrap one later as a VS Code
  extension — `tars-tab` in Wave B — so the dev's editor habit transfers.)
- Not a SaaS. The backend is a Python sidecar on the user's machine, not a
  cloud tenant.
- Not a feature factory. If a capability isn't routed through `meeet.world`,
  doesn't emit a receipt, and isn't pinned to one of the 7 domain packs, it
  does not ship.

The only fork-point that matters: TARS sells *trust + breadth + proof* into
audiences `Cursor` cannot serve (life-ops, regulated industries, on-chain
transparency), while closing the friction gap on the dev-overlap surface
through Wave A.

---

## §2. What's shipped (v9.2.0-beta2)

The honest inventory as of W235. Files / routers / paths in code-blocks
so any of this is one grep away from the source.

### Core runtime

- `FastAPI` backend on `127.0.0.1:8765`. Source: `web_extras/app.py`.
- `Tauri 2` desktop wrapper at `desktop/src-tauri/`. Native window state,
  global shortcut `Cmd+Shift+Space`, system tray menu, `tars://` deep-link
  handler (W245).
- ~50 routers under `web_extras/routers/` (see `web_extras/routers/__init__.py`).
- ~24 core modules under `backend/core/` (`agents`, `chat`, `meeet`,
  `meeet_billing`, `metering`, `usage`, `receipts`, ...).

### Domain packs (7)

| Pack | Actions | Source |
|---|---|---|
| Business | `kpi_snapshot`, `daily_brief`, `log_deal`, `draft_email` | `backend/core/domains/business.py` |
| Entrepreneur | `outreach`, `pipeline`, `fundraise_stack` | `backend/core/domains/entrepreneur.py` |
| Science | `arxiv_search`, `citation_graph`, `research_notes` | `backend/core/domains/science.py` |
| Algotrade | `backtest`, `signal_ir`, `paper_trade` | `backend/core/algotrade/` |
| Traders | `live_awareness`, `position_monitor`, `risk_gate` | `backend/core/domains/traders.py` |
| Wallet | `balances`, `$MEEET`, `anchor` | `backend/core/wallet/` |
| Civic (W204) | `lookup_legislator`, `recent_votes`, `court_case_search` | `backend/core/domains/civic.py` — free for every tier |

Pack catalog: `GET /api/domains/manifest`.

### Voice cockpit (W220 + W229 + W230 + W232)

- Cinematic monolith + concentric rings + audio-reactive HUD —
  see `docs/STORYBOARD_VOICE_COCKPIT.md` (8 frames).
- Wake-word: web Picovoice WASM in PWA path (W36).
- STT: `MediaRecorder` -> `POST /api/voice/transcribe` (W229), whisper.cpp local
  or OpenAI Whisper fallback.
- `POST /api/voice/command` (W220) — full-screen cockpit command intake.
- Text-input fallback (W232) under the mic so the cockpit is usable when no
  STT backend is configured.
- TTS: XTTS-v2 voice cloning (W39) + per-persona SSML prosody (W43).

### Auth (`meeet.world`)

- Auth gate at boot (W219). Magic-link + Google/Apple OAuth.
- Deep-link `tars://auth?token=...` -> Tauri handler -> `POST /api/auth/meeet/exchange`.
- Token persists at `~/.tars/meeet_token` mode `0o600`.
- TARS-side router: `web_extras/routers/auth_meeet.py`. Five endpoints
  fully wired waiting on brother's 4 cloud endpoints (see §5, §10).
- Mode switch: `MEEET_MODE=mock` (offline, FREE tier forever) vs
  `MEEET_MODE=live` (production). `scripts/CHECK-MEEET-LIVE.command` flips it.

### Connectors (real OAuth where marked)

- Slack — real OAuth + read (W91).
- Gmail — real OAuth + read (W91).
- Google Calendar — real OAuth + read (W91); `.ics` reader for Daily Briefing.
- GitHub — token-based, not mock (W136 / Iter F).
- Telegram — bridge connector (W108).
- iMessage — real bridge via `AppleScript` + Messages.app DB (W160).
- Email/SMTP — third notification sibling (W163).
- Web search — `Brave`, `SearXNG`, `DuckDuckGo` (web search pack).

### Receipts and on-chain anchoring

- Receipt-ledger (W67): every consequential action emits a signed receipt.
- Hash-chained + Solana memo anchor (W89, W95) — batched Merkle root daily.
- Public verifier endpoints (W204) — no-auth Merkle replay:
  `GET /api/receipts/recent`, `GET /api/receipts/merkle/{day}`,
  `GET /api/public/proof/anchor/{root}`, `POST /api/public/proof/verify`.
- Storage: `~/.tars/receipts/*.ndjson` (one file per UTC day) +
  `~/.tars/receipts.sqlite` mirror. Source: `backend/core/receipts/`.

### Billing and metering (W235)

- `UsageEvent` schema in `backend/core/usage/schema.py`.
- Metering middleware wraps every consequential router (`backend/core/metering/`).
- Consumption console: `GET /api/usage/console` aggregates last-30d by
  action/model/day. Source: `web_extras/routers/usage.py`.
- HMAC-signed POST to `meeet.world` billing event endpoint (awaiting brother
  ingress — see §10).

### Compliance / B2B Workshop

- Compliance export bundle (W104): `POST /api/compliance_export/run` produces
  a signed bundle (JSON + CSV + PDF) of all usage events with Merkle proofs.
- Workshop pack (W80-W89): companies/funds onboard via TARS workshops.
  ROI calculator, self-assessment quiz, cohort facilitator dashboard,
  attendee tracking. Source: `backend/core/cohort/`, `web_extras/routers/cohort.py`.
- Reports: PDF/PPTX/XLSX export from data (W103). Source: `backend/core/reports/`.

### Cowork (multiplayer)

- `backend/core/cowork/` — sessions, presence, stream, handoff.
- HTTP router `web_extras/routers/cowork.py` (W149).
- Orchestrator emits `agent_frame` to cowork on real run path (W131).

### Background daemon

- `backend/core/daemon/` — headless agent triggers.
- macOS `LaunchAgent` plist (W152), Linux `systemd` user-unit (W153),
  Windows `schtasks.exe` parity (W171).
- `tars-doctor` CLI: 11+ health checks with `--fix`, `--watch`,
  `--test-notify` (W154-W173).
- HTTP `/api/doctor/*` (W155, W167, W168).
- Backend-watchdog autostart via `scripts/install-tars-watchdog.command` (W216).

### Notification bridges

- iMessage (W160), Telegram (W161), Email/SMTP (W163).
- Auto-fanout from `doctor_watch` on health drift (W162).
- Unified contract: `docs/NOTIFICATIONS.md` (W164).

### Marketplace + $MEEET economy

- Skill SDK (W95), Marketplace 70/30 revenue share on Solana (W96),
  REST + browse page (W97).
- Native skills: Quest / Stake / Arena / Discovery / Wallet (W75).
- Balance, spend, earn, quests v2 (W48). Source: `backend/core/marketplace/`,
  `backend/core/meeet/`.

### AI Clone

- v0.2: per-user style learning + draft suggestions (W104, W151).
- Webhook sync to `meeet.world` on every `record_message` (W195).
- Source: `backend/core/clone/`, `web_extras/routers/clone.py`.

### Vision

- `POST /api/vision/ocr` (local `pytesseract`), `POST /api/vision/analyze`
  (Anthropic/OpenAI vision), `GET /api/vision/health`. (W203).
- Tauri command `vision_capture_screen` on macOS via `screencapture`.

### Accessibility (W217 + W218)

- `/api/a11y/ocr-to-speech` — turn any image region into spoken output.
- Pytest coverage of 5 cases.

### Agent runtime (the multi-agent layer)

- Workflow engine (W45) — chain agents, schedule, branching, replay.
  Source: `backend/core/workflow/` (wraps planner + orchestrator).
- Smart Agent Router (W116) — LLM-based intent routing across packs.
  Source: `backend/core/agents/router.py`.
- Supervisor (W76) — per-action budget cap, rate limit, kill switch,
  HIL gate. Source: `backend/core/agents/supervisor.py`.
- Council (W56) — two-voice or multi-LLM dissent before consequential
  actions. Source: `backend/core/council/`.
- 7 killer agents (W47): research, analyst, meeting, doc, scraper,
  translator, image. Source: `backend/core/agents/builtin/`.
- Watch-me-work timeline (W77) — real WS events from orchestrator,
  replayable via `GET /api/orchestrator/replay/{run_id}`.
- Memory reflection (W72) — weekly digest with user confirmation;
  endpoint `POST /api/digest/run` (W209).

### Knowledge / RAG

- Knowledge Brain (W46) — universal RAG ingestion: PDF, URL, Office,
  code. Source: `backend/core/memory/`.
- Code RAG (W135 / Iter E) — `sqlite-vec` embeddings over the project
  tree; powers `@codebase` (Wave A) and code-aware actions.
- Universal File Drop (W117) — single drop-zone, auto-typed ingestion.
- Memory UI (W133 / Iter C) — cockpit reads `~/.tars/memory.sqlite`,
  not JSON; CRUD via `/api/memory/*`.

### Cockpit (TARS.app)

- 9-tab nav: Status / Agents / Chat / Activity / Connectors / Cowork /
  Vision / Plugins / Settings (W200, W203, W210).
- Tier pill — live from `/api/entitlements`, 60s refresh.
- Welcome onboarding modal (W205) — first-launch starter-pack picker.
- Today briefing card (W206) — `/api/briefing/today` 4-section snapshot
  (calendar, recent receipts, agenda, top headline).
- Weekly digest (W209) — `/api/digest/latest`.
- Doctor panel embedded — 11 checks color-coded.
- Tier-aware visual gating (W210) — dims Pro+ tabs for FREE users.
- Tray icon + global shortcut `Cmd+Shift+Space` (W242-W245).

### T2T (TARS-to-TARS) protocol

- Agent A on TARS instance #1 negotiates a deal with agent B on TARS
  instance #2. Escrow via `meeet.world` relayer (W86).
- Handshake protocol + mock escrow (W81), MCP server reference (W85),
  T2T frontend page (W88).
- Substrate for the future agent economy (Wave C C4).

### Wallets

- Self-custodial Solana, EVM, TON. BIP-39 seeds generated locally,
  encrypted at rest with XChaCha20-Poly1305.
- Phantom-compatible derivation. Transactions signed on-device with
  `eth-account`, `solders`, `tonsdk`.
- Source: `backend/core/wallet/`, router: `web_extras/routers/wallet.py`.
- Phone pairing — X25519 handshake with iOS/Android companions (W129);
  read-only wallet state streams over the encrypted channel.

### Stats (as of W235)

- 235+ commits since v9.0 cut.
- 21 SQLite stores under `~/.tars/` (see `docs/DB_AUDIT_v9.2.md`).
- ~50 HTTP endpoints (see `web_extras/routers/`).
- ~30 backend core modules.
- ~70K LoC across backend + cockpit + landing.
- ~350+ pytest cases; ~50+ vitest cases.

---

## §3. Architecture overview

### 3.1 The big picture

```
                         +-------------------------------+
                         |  TARS.app (Tauri 2, macOS)    |
                         |  desktop/src-tauri/web/...    |
                         |  - voice cockpit (W220)       |
                         |  - 9-tab control center       |
                         |  - deep-link tars://          |
                         +---------------+---------------+
                                         |  loopback HTTP, no auth
                                         v
                         +-------------------------------+
                         |  FastAPI backend :8765        |
                         |  web_extras/app.py            |
                         |  ~50 routers (auth, voice,    |
                         |  agents, chat, receipts,      |
                         |  usage, cowork, vision, ...)  |
                         +---+----------+---------+------+
                             |          |         |
              +--------------+          |         +-----------------+
              |                         |                           |
              v                         v                           v
   +---------------------+   +-----------------------+   +----------------------+
   | ~/.tars/  (local)   |   |  meeet.world (cloud)  |   |  LLM providers       |
   | 21 SQLite stores    |   |  api.meeet.world      |   |  Anthropic / OpenAI  |
   | receipts NDJSON     |   |  - auth (4 endpoints) |   |  / OpenRouter / local|
   | meeet_token (0o600) |   |  - billing (4 ep.)    |   |  whisper.cpp         |
   | host-key.json       |   |  - marketplace        |   +----------------------+
   +---------------------+   |  - $MEEET economy     |
                             +-----------+-----------+
                                         |
                                         v
                              +----------------------+
                              | Solana (mainnet)     |
                              | Memo program — daily |
                              | Merkle root anchor   |
                              +----------------------+
```

### 3.2 Data plane

- **21 SQLite databases** at `~/.tars/*.sqlite`. Full inventory:
  `docs/DB_AUDIT_v9.2.md`. Each store owns its own `CREATE TABLE IF NOT EXISTS`
  schema (no Alembic). Auto-created on first boot via
  `backend.core.storage.bootstrap.init_all_databases()` (W231).
- **Receipt ledger:** NDJSON, one file per UTC day at `~/.tars/receipts/`.
  Hash-chained, replayable via `ReceiptStore.replay_chain_for_day`. The
  `~/.tars/receipts.sqlite` SQLite mirror is rebuildable from NDJSON for
  cross-version durability.
- **Secrets:** `~/.tars/meeet_token` (mode `0o600`), `~/.tars/wallet_secrets.json`
  (XChaCha20-Poly1305 encrypted), `~/.tars/host-key.json` (Ed25519 receipt-signing).
- **No cross-process sharing.** Single backend process per user.

### 3.3 Auth plane

- User opens TARS.app -> auth gate (W219) appears.
- Magic-link path: email -> TARS backend -> brother's `/api/magic-link/start`
  -> user clicks email -> `https://meeet.world/auth/magic?code=...` ->
  302 to `tars://auth?code=...&email=...` -> Tauri deep-link handler ->
  TARS `/api/auth/meeet/exchange` -> brother's `/api/magic-link/redeem` ->
  Ed25519 JWT persisted to `~/.tars/meeet_token`.
- OAuth path: same idea, browser bounces through Google/Apple, lands on
  `tars://auth?token=...`.
- JWT alg: `EdDSA` (Ed25519); public key fetched once from
  `https://meeet.world/.well-known/jwks.json` and cached 24h.
- Mock vs live: `MEEET_MODE=mock` (default for first-boot, FREE tier,
  no cloud calls) or `MEEET_MODE=live` (production). The
  `scripts/CHECK-MEEET-LIVE.command` script verifies brother's endpoints
  and prompts via dialog to flip the mode.
- Full handshake spec: `docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md`.

### 3.4 Money plane

- Every consequential action goes through metering middleware
  (`backend/core/metering/`).
- Middleware emits a `UsageEvent` (schema in `backend/core/usage/schema.py`):
  `ts, trace_id, action, provider, model, tokens_in, tokens_out, cost_usd,
   cost_meeet, tier, user_id, outcome, receipt_id, merkle_root_anticipated`.
- Event is recorded locally (ledger) AND posted via HMAC-signed POST to
  `meeet.world`'s `/api/billing/usage_event` (brother dep).
- Local mirror polls `/api/billing/balance` for cap math (W246).
- Reconciliation: `scripts/reconcile-meeet-billing.py` (W249) — daily
  drift check; alerts via doctor notification fanout if drift > $0.50.

### 3.5 Trust plane

- Every action emits a signed `Receipt` (Ed25519 with key at `~/.tars/host-key.json`).
- Receipts hash-chain: each receipt's `prev_hash` points at the previous
  receipt of that day. Tampering breaks the chain.
- Daily Merkle root is computed at UTC rollover and anchored as a Solana
  memo by `backend/core/receipts/anchor.py` (W89, W95).
- Public verifier: `POST /api/public/proof/verify` accepts a receipt + proof
  + claimed root, replays the Merkle path, returns yes/no. No auth, no DB
  call. Third parties can verify offline.
- `GET /api/public/proof/anchor/{root}` returns the Solana explorer URL
  for that day's memo.

### 3.6 Models plane

- `Anthropic` (Claude Sonnet/Haiku/Opus 4.6) — default for consequential.
- `OpenAI` (GPT-5, GPT-5-mini, GPT-4o-mini) — Cursor parity + cheap completions.
- `OpenRouter` (any) — provider-of-last-resort, 5% TARS markup over their cut.
- Local: `whisper.cpp`, `pytesseract`, `llama-3.2-3b` on M-series silicon,
  `tars-local-chat-v1` for clone responses. Cost = $0.
- BYO key vs TARS-managed key — see §7.

---

## §4. Cursor parity scorecard

Source of truth: `docs/COMPETITIVE_ANALYSIS_CURSOR.md` §3, condensed here.
Legend: Y = shipped, P = partial/beta, N = absent.

### 4.1 Where Cursor leads today (gaps we close)

| #  | Capability                              | Cursor | TARS today | Wave A target | Wave B target | Wave C target |
|----|-----------------------------------------|--------|------------|---------------|---------------|---------------|
| 1  | Inline Tab completion                   | Y      | N          | N             | `tars-tab` VS Code ext | Y (extension) |
| 2  | Composer (multi-file edit + diff)       | Y      | N          | N             | voice-driven Composer | Y |
| 3  | `@file` / `@folder` / `@symbol` mentions| Y      | N          | Y             | Y             | Y |
| 4  | `@recent-changes` (git diff)            | Y      | N          | Y             | Y             | Y |
| 5  | `@web` live search                      | Y      | P          | Y             | Y             | Y |
| 6  | Codebase index at scale                 | Y      | P          | P             | Y (500K LoC)  | Y |
| 7  | Rules for AI (`.cursor/rules/`)         | Y      | N          | `.tars/rules.yml` | Y         | Y |
| 8  | Notepads (saved chat templates)         | Y      | P          | P             | Y             | Y |
| 9  | MCP servers settings panel              | Y      | P          | Y             | Y             | Y |
| 10 | Models switcher + cost labels           | Y      | P          | Y             | Y             | Y |
| 11 | Per-request usage meter                 | Y      | P (ledger only) | Y (console) | Y         | Y |
| 12 | Soft cap warning at 80%                 | Y      | N          | Y             | Y             | Y |
| 13 | Hard block at 100%                      | Y      | P          | Y             | Y             | Y |
| 14 | Background agents tray                  | Y      | P (daemon, no UI) | Y     | Y             | Y |
| 15 | SOC2 compliance UI                      | Y      | P          | P             | Y             | Y |
| 16 | Magic-link auth                         | Y      | P (waiting brother) | Y     | Y             | Y |
| 17 | OAuth (Google / Apple / GitHub)         | Y      | Y          | Y             | Y             | Y |
| 18 | Tauri auto-update                       | P      | P          | Y             | Y             | Y |

### 4.2 Where TARS already leads Cursor

| #  | Capability                              | Cursor | TARS today |
|----|-----------------------------------------|--------|------------|
| 19 | Local-first by default                  | P (Privacy Mode opt-in) | Y |
| 20 | Hash-chained receipt ledger             | N      | Y |
| 21 | Solana anchor of agent actions          | N      | Y |
| 22 | Public Merkle verifier (no-auth)        | N      | Y |
| 23 | 7 domain packs (life-ops surface)       | N      | Y |
| 24 | Voice-first cockpit + wake-word + TTS   | N      | Y |
| 25 | Multi-agent council / dissent           | N      | Y |
| 26 | T2T agent handshake protocol            | N      | Y |
| 27 | Cowork multiplayer sessions             | N      | Y |
| 28 | $MEEET token economy                    | N      | Y |
| 29 | Marketplace 70/30 on Solana             | N      | Y |
| 30 | B2B Workshop mode                       | N      | Y |
| 31 | iMessage / Telegram / Email bridges     | N      | Y |
| 32 | Real OAuth across 8 connectors          | P (via MCP) | Y |
| 33 | Vision + OCR + accessibility helpers    | N      | Y |
| 34 | Watchdog + auto-restart daemon          | N      | Y |
| 35 | `tars-doctor` CLI                       | N      | Y |

**Tally.** Cursor leads on 18 dev-overlap capabilities (rows 1-18).
TARS leads on 17 trust-and-breadth capabilities (rows 19-35). Wave A
closes the must-have half of Cursor's lead; Wave B+C extends TARS into
space Cursor cannot follow without abandoning its IDE thesis.

**The asymmetric edge** (what Cursor cannot copy without rebuilding):
local-first, receipt-on-chain, voice-cockpit, domain packs, $MEEET economy,
on-chain audit. Defend it.

---

## §5. The meeet.world integration story — end-to-end

Everything cross-machine that TARS does passes through `meeet.world`. This
is the strategic spine of the whole product. Brother's side hosts identity,
billing, balance, entitlements, marketplace payouts, $MEEET treasury,
telemetry, and the compliance backplane. TARS' side hosts the cockpit, the
agents, and the receipts.

### 5.1 Why every road goes through `meeet.world`

| Plane            | What `meeet.world` provides                                       |
|------------------|-------------------------------------------------------------------|
| Identity         | Magic-link email + OAuth (Google/Apple) — issues Ed25519 JWT.     |
| Billing          | Usage event ingest, balance mirror, top-up payment flow.          |
| Entitlements     | Tier sync (FREE/PRO/BUSINESS) + feature flags via `/api/me`.      |
| Compliance       | Cross-instance receipt anchoring backstop + audit-export packaging.|
| Marketplace      | Skill registry + 70/30 publisher payouts on Solana.               |
| Payments         | $MEEET token swaps + USD card processor.                          |
| Telemetry        | `MEEET_TELEMETRY` opt-in structured-event ingest.                 |

If a feature does not have a hook in one of these planes, it is either
local-only-forever (allowed) or it is in the wrong place (re-route through
`meeet.world` or do not ship).

### 5.2 Mode switch

| `MEEET_MODE` | Behaviour                                                          |
|--------------|--------------------------------------------------------------------|
| `mock`       | Offline. No cloud calls. FREE tier forever. Watermarked receipts. Default first-boot. |
| `live`       | Production. Brother's endpoints live. Tier sync, billing, marketplace all real. |

Flip via `scripts/CHECK-MEEET-LIVE.command`: probes the 4 auth endpoints,
prints a 4/4 verdict, and pops a macOS dialog "switch `.env` to live?" Yes
-> edit `.env`, restart backend, you're live.

### 5.3 The 4 auth endpoints brother ships (waiting on him)

Full spec: `docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md`. Summary:

| # | Endpoint                          | Purpose                                          |
|---|-----------------------------------|--------------------------------------------------|
| 1 | `POST /api/magic-link/start`      | Mail a one-time 8-char code to the user.         |
| 2 | `POST /api/magic-link/redeem`     | Swap code for 30-day Ed25519 session JWT.        |
| 3 | `GET /api/oauth/{provider}/start` | Issue OAuth redirect URL (`google`, `apple`).    |
| 4 | `GET /api/me`                     | Tier + feature flags + expiry; polled every 24h. |

TARS-side is already done — see `web_extras/routers/auth_meeet.py`. Brother
ships, runs `CHECK-MEEET-LIVE.command`, flips the mode, magic-link works
end-to-end.

### 5.4 The 4 billing endpoints brother ships (Wave A coordination)

Full spec: `docs/ROADMAP_W234_to_v10.md` §4 and `docs/PRICING_ECONOMICS_v9.2.md` §9.
Summary:

| # | Endpoint                       | Purpose                                                 |
|---|--------------------------------|---------------------------------------------------------|
| 5 | `POST /api/billing/usage_event`| Receives HMAC-signed `UsageEvent`; debits balance.      |
| 6 | `GET /api/billing/balance`     | Returns tier, USD remaining, $MEEET remaining, period.  |
| 7 | `POST /api/billing/topup`      | Initiates Solana ($MEEET) or card top-up flow.          |
| 8 | reconciliation handshake       | Daily drift check; alerts on >$0.50 mismatch.           |

`BRIDGE_SHARED_SECRET` already distributed (W194). Schema: §3.4 above.
Idempotency key: `trace_id`.

### 5.5 Telemetry

- `MEEET_TELEMETRY=1` env opts in.
- Cock-pit emits structured events (route render, command issued, tier change)
  via `web_extras/routers/awareness.py` to `meeet.world`'s ingest.
- Receipts never get sent here — receipts are local + Solana anchor only.
- Off by default. The user has to opt in. (See §11 anti-patterns.)

### 5.6 Brother readiness check

`scripts/CHECK-MEEET-LIVE.command` (W233) is the one-click verification.
Output looks like:

```
meeet.world live readiness:
  POST /api/magic-link/start   -> OK (200) live
  POST /api/magic-link/redeem  -> OK (4xx) endpoint deployed
  GET  /api/oauth/google/start -> OK (200) live
  GET  /api/oauth/apple/start  -> OK (200) live
  GET  /api/me                 -> OK (401) endpoint deployed

Verdict: 4/4 auth endpoints live, /api/me live=yes
  can switch MEEET_MODE=live? yes (all green)
```

4xx and 401 with no token both count as "endpoint deployed and routed."
Only 404 or connection-refused count as "not deployed."

### 5.7 Fallbacks while brother is shipping

The desktop app stays usable. Two paths:

1. **"Skip — local-only mode"** on the auth screen. No cloud sync, no T2T,
   no marketplace install. FREE tier forever. The user can connect later
   from Settings -> Connections.
2. **Text-input fallback (W232)** under the voice cockpit mic. If STT
   isn't configured (no `OPENAI_API_KEY`, no `whisper.cpp`), the user
   types the command and presses Enter; it hits `/api/voice/command`
   directly.

Frontend also shows a specific toast when it detects brother's endpoint
isn't deployed (looks for `error: "not_deployed"`, `error: "meeet_unreachable"`,
or 404/503 from the backend):

> meeet.world cloud not deployed yet. Use "Skip — local-only mode" for now.
> Brother is wiring it up.

This keeps the user calm and tells them whose turn it is.

---

## §6. Roadmap — beta2 to v10.0 GA

Source of truth: `docs/ROADMAP_W234_to_v10.md` (Wave A in commit-sized detail)
and `docs/COMPETITIVE_ANALYSIS_CURSOR.md` §6 (Waves B and C scope). Three waves;
each compounds on the previous; no wave gold-plates the wave before.

### 6.1 Wave A — Cursor parity must-haves (0-4 weeks, W234-W260)

**Goal:** a Cursor-refugee opens TARS and says nothing's missing.

| Wave | Item                              | Effort | Dep                              |
|------|-----------------------------------|--------|----------------------------------|
| W235 (done) | Consumption console + metering middleware | M | `backend/core/usage/`        |
| W237 | `/api/usage/console` aggregator   | S      | usage schema                     |
| W238 | `/api/usage/budget` + entitlement gate | S | entitlements/tiers.py            |
| W239 | Cockpit Usage tab scaffold        | S      | W236-W238                        |
| W240 | Live SSE stream component         | S      | W236                             |
| W241 | Today breakdown table             | S      | W237                             |
| W242 | Monthly cap progress bar          | S      | W238                             |
| W243 | Toast at 80% soft cap             | S      | W242                             |
| W244 | Hard-block 402 modal              | S      | W238 + W242                      |
| W245-W249 | Brother billing endpoints + reconciliation | M | BRIDGE_SHARED_SECRET (W194)  |
| W250 | Cost-label data plumb             | S      | ledger.py                        |
| W251 | Cockpit Models switcher UI        | S      | W250                             |
| W252 | Pre-send cost estimator           | S      | W250                             |
| W253 | `.tars/rules.yml` schema + loader | M      | none                             |
| W254 | Rules injection into agent prompt | M      | W253                             |
| W255 | Cockpit Rules editor              | S      | W253                             |
| W256 | `@-mention` resolver backend      | M      | code-RAG, search pack            |
| W257 | Chat mention autocomplete         | M      | W256                             |
| W258 | Mention persistence across messages| S     | W257                             |
| W259 | MCP servers panel                 | S      | W150 registry                    |
| W260 | Background agents tray            | M      | W77 Watch-me-work, W152 daemon   |
| W260b | Marketing copy update (landing + cockpit) | S | brother numbers locked     |

**Success metrics:**

- Usage tab shows a live cost line within 1s of a request.
- 100% of last-30d requests retrievable with a `cost_usd` field.
- Toast fires deterministically at 80%; modal blocks deterministically at 100%.
- `@file auth.py` pins the file; subsequent messages in the thread re-inject it.
- `.tars/rules.yml` with `deny_edit` for `migrations/` actually blocks an agent.
- Operator starts an agent, closes the cockpit, reopens next morning, sees
  status in the Tasks tab.

**Target ship:** 2026-06-12, tag `v9.3.0`.

**Blocker risk:** brother on W245-W247. Mitigation: TARS-side mock at
`/api/_meeet_mock` so the cockpit doesn't block on his ship.

**Wave A weekly milestones.**

| Week    | Goal                                                                  | Tag candidate |
|---------|-----------------------------------------------------------------------|---------------|
| Week 1 (W235-W240) | Usage event bus shipped + Usage tab scaffold + Live SSE stream | `v9.2.0-beta3` |
| Week 2 (W241-W244) | Today breakdown + Monthly cap bar + soft-cap toast + hard-block modal | `v9.2.0-rc1`   |
| Week 3 (W245-W252) | Brother billing endpoints live + Models switcher + cost estimator | `v9.2.0-rc2`   |
| Week 4 (W253-W260) | `.tars/rules.yml` + `@-mentions` + MCP panel + Background agents tray | `v9.3.0`       |

**Execution discipline (Wave A).**

- One commit per Wxxx number. Each is independently revertable.
- No commit lands without an entry in `CHANGELOG_PUBLIC.md` if it's
  user-facing.
- Backend changes that need brother's side are tagged `[brother dep]`
  in the commit body.
- Cursor lane and Claude lane work concurrently; both reference the
  same `ROADMAP_W234_to_v10.md` for sequencing.

### 6.2 Wave B — TARS-unique edge (4-12 weeks, W261-W320)

**Goal:** features Cursor cannot copy without redesigning its core.

| # | Item                                         | Effort | Why it matters |
|---|----------------------------------------------|--------|----------------|
| B1 | Voice-driven Composer ("hey TARS, refactor auth.py") -> diff preview | L | The killer voice demo |
| B2 | Multi-file refactor + receipt-anchored diffs | M | Every accepted hunk emits a receipt |
| B3 | On-chain audit trail for code changes        | M | `tars audit <repo>` returns N receipts with Solana proofs |
| B4 | Domain-pack-aware code suggestions           | M | Wealth pack pins `tax.py`; product pack pins `roadmap.md` |
| B5 | SOC2-style audit log UI                      | M | Cockpit tab renders W104 compliance export |
| B6 | Privacy Mode branding                        | S | "Private" badge when no cloud LLM keys set |
| B7 | Notepad templates                            | M | Saved prompts + pinned context, runnable from Cmd+K |
| B8 | `tars-tab` VS Code extension                 | L | The wedge into Cursor's audience without forking VS Code |
| B9 | Codebase index scale-up (500K LoC, <200ms)   | L | Incremental rebuild + warm cache + local model fallback |
| B10 | Update channel — Tauri updater JSON published| S | First auto-update lands without operator action |

**Target ship:** 2026-09-01, tag `v9.5.0`.

### 6.3 Wave C — beyond Cursor (12+ weeks, W321+)

**Goal:** the surface area Cursor structurally cannot serve.

| # | Item                                          | Effort | Why it matters |
|---|-----------------------------------------------|--------|----------------|
| C1 | TARS-to-TARS handoff for code review          | XL | My agent hands the diff to your agent; both sign the receipt |
| C2 | B2B compliance export for code changes        | L  | Sellable to regulated finance / healthcare / legal |
| C3 | Voice-first pair programming (20 min, zero clicks) | XL | The flagship demo |
| C4 | Agent economy marketplace (3rd-party agents)  | L  | 10 third-party agents earning $MEEET in 90 days |
| C5 | On-prem TARS for funds/enterprises            | XL | First on-prem deployment to a regulated org |
| C6 | Domain-pack federation (wealth pack calls health pack) | M | Federated receipts across packs under user consent |

**Target ship:** 2026-12-15, tag `v10.0.0` GA.

### 6.4 Risks to watch

| Risk | Severity | Mitigation |
|------|----------|------------|
| Brother slow on billing endpoints | High | Mock endpoint at `/api/_meeet_mock` so cockpit doesn't block |
| Tokenizer cost estimate off >15% | Med  | Calibrate against first 100 prompts; auto-adjust price table |
| SSE stream chokes >100 ev/s    | Low  | Per-client rate limit; batch into 100ms windows |
| `.tars/rules.yml` becomes a footgun (deny everything) | Med | First rule-fail surfaces banner; doctor catches empty allow-set |
| `@web` resolver costs runaway on FREE | Med | Cache results 24h per query; FREE capped 5/day |
| Models switcher overwhelms non-tech users | Low | Hide behind "Advanced" by default |

---

## §7. Pricing and metering economics

Locked numbers from `docs/PRICING_ECONOMICS_v9.2.md`. Brother wires
`/api/billing/usage_event` against these.

### 7.1 Tier matrix

| Tier      | USD            | $MEEET         | Req/mo       | Soft cap | Hard cap | Models               | Receipts        |
|-----------|----------------|----------------|--------------|----------|----------|----------------------|-----------------|
| FREE      | $0             | n/a            | 50           | $1.50    | $3.00    | Basic only (haiku/mini/local) | Watermarked  |
| PRO       | $20/mo         | 200 $MEEET/mo  | 1 000        | $18      | $25      | All providers        | Clean           |
| BUSINESS  | $40/seat/mo    | 400 $MEEET/seat/mo | 5 000 soft cap | $38  | $60      | All + BYO key        | Clean + branded |

`$MEEET` peg: `$0.10` (operator-controllable). Cockpit always shows both
$MEEET *and* USD-equivalent at current rate; receipts record both.

### 7.2 Provider cost table (USD per million tokens)

| Model                          | Input $/Mtok | Output $/Mtok | Default for       |
|--------------------------------|-------------:|--------------:|-------------------|
| `anthropic-claude-haiku-4.6`   | 1.00         | 5.00          | Routine actions   |
| `anthropic-claude-sonnet-4.6`  | 15.00        | 75.00         | Consequential     |
| `anthropic-claude-opus-4.6`    | 30.00        | 150.00        | Council dissent   |
| `openai-gpt-4o-mini`           | 0.15         | 0.60          | FREE-tier default |
| `openai-gpt-5-mini`            | 1.50         | 6.00          | Cheap completion  |
| `openai-gpt-5`                 | 12.00        | 60.00         | Cursor parity     |
| `openrouter-*`                 | provider + 5%| provider + 5% | Fallback          |
| local `whisper.cpp` / llama-3.2-3b | 0       | 0             | Voice + clone     |

**Markup:** BYO key 0%, TARS-managed key 15%, OpenRouter 5%.

### 7.3 Anti-abuse rules

| Tier      | /hour /IP | /hour /token | /day /token |
|-----------|----------:|-------------:|------------:|
| FREE      | 10        | 5            | 50          |
| PRO       | 200       | 100          | 1 000       |
| BUSINESS  | 1 000     | 500          | 5 000       |

- FREE daily USD cap: `$0.05` (covers ~50 cheap haiku prompts).
- FREE daily compute: 30 daemon minutes; beyond that, daemon pauses with
  upgrade toast.
- FREE storage: 100 MB RAG; beyond fails 402.
- FREE connectors: max 2 OAuth connections.
- IP-shared-FREE detection: 5+ distinct FREE tokens on one IP -> all rate-limit
  to 1 req/hour.
- Failure outcome counts: `tars_error` and `provider_error` do **not** debit
  balance (the user did not consume value).

### 7.4 Refund and credit logic

- FREE: no refunds (no charge).
- PRO: pro-rated refund within 14 days of subscription start.
- BUSINESS: annual non-refundable; monthly pro-rated within 30 days.
- $MEEET-paid: refunded in $MEEET at the same paid ratio.
- Beta tester credit: $25 USD auto-applied on first PRO subscription (W198 cohort).
- Workshop attendee credit: $40 USD per workshop.
- AI Clone training contribution: 10 $MEEET per 100 ingested messages
  (cap 500 $MEEET/month/user on FREE).

### 7.5 Receipt-ledger guarantee

Every `usage_event` emits a receipt with:
`ts, trace_id, user_id, tier, action, provider, model, tokens_in, tokens_out,
 cost_usd, cost_meeet, markup_pct, outcome, receipt_id, merkle_root_anticipated`.

Receipts hash-chain. The daily Merkle root anchors on Solana. A user can
prove their consumption to any third party (compliance officer, fund auditor,
court) by handing them the receipt + the Merkle proof + the Solana memo URL,
and that party can verify offline without any cooperation from us.

This is the audit-grade transparency that opens the regulated-industry door
Cursor cannot reach.

---

## §8. Operating manual

### 8.1 The daily user flow

1. **Launch.** Double-click TARS.app (or use `Cmd+Shift+Space` global
   shortcut to toggle window). Backend boots if not already running (the
   watchdog LaunchAgent restarts within 30s of any crash).
2. **Auth.** First launch shows the auth gate (W219). Magic-link or OAuth
   through `meeet.world`, or "Skip — local-only mode" for FREE forever.
3. **Voice cockpit.** Post-auth, the cinematic monolith appears. Wake-word
   or click-to-listen, dictate the command, hear the TTS response. If no
   STT is configured, type into the text fallback (W232).
4. **USAGE tab.** Live cost feed (W240), today breakdown (W241), monthly
   cap progress (W242). Toast at 80%, modal at 100%.
5. **Drawer for old tabs.** The 9 control-center tabs (Status / Agents /
   Chat / Activity / Connectors / Cowork / Vision / Plugins / Settings)
   live in the cockpit drawer behind the voice surface.

### 8.2 `scripts/` cheat sheet

All `.command` files are double-clickable on macOS. One-liner each:

| Script                                | What it does                                                       | When to use |
|---------------------------------------|--------------------------------------------------------------------|-------------|
| `LAUNCH-NOW.command`                  | One-click finish-the-launch: `backend_tars_up` + install watchdog LaunchAgent. | First boot or after pulling main. |
| `REBUILD-TARS-APP.command`            | `npm/pnpm install` + `tauri build` + install to `/Applications` + clear quarantine + launch. | After UI changes. |
| `BYPASS-AUTH.command`                 | Hard `pkill` Tauri + drop a `~/.tars/auth_bypass` flag + restart. | Auth screen hangs and you need to get into cockpit. |
| `CHECK-STATUS.command`                | Curl 10 health endpoints, print red/green table. | Sanity check at any time. |
| `CHECK-MEEET-LIVE.command`            | Probe the 4 brother endpoints; if 4/4 live, dialog to flip `MEEET_MODE`. | After brother says he's deployed. |
| `WALK-THROUGH.command`                | E2E narrated tour: boot DB, list packs, send chat, emit receipt, fetch Merkle proof. | Demo or post-deploy smoke. |
| `SMOKE-TEST.command`                  | Curl all ~22 known endpoints, return non-zero on any 5xx. | CI-style local pre-flight. |
| `install-tars-watchdog.command`       | Install `~/Library/LaunchAgents/com.tars.backend-watchdog.plist`. | One time, post-install. |
| `backend_tars_up.sh`                  | Launch uvicorn on `:8765` with .env loaded; logs to `/tmp/tars-backend-8765.log`. | Manual restart. |
| `probe-meeet-billing.command`         | E2E verify usage event delta against `meeet.world`. | After brother ships billing endpoints. |
| `auto-push.command` / `auto-push-tag.command` | `git push` + tag push. | After landing a commit. |
| `tars-doctor` (CLI)                   | 11+ health checks; `--fix`, `--watch`, `--test-notify`. | Anytime something feels off. |

### 8.3 Troubleshooting

| Symptom                                    | Fix                                                              |
|--------------------------------------------|------------------------------------------------------------------|
| Backend unreachable                        | `LAUNCH-NOW.command`. If it keeps dying, `install-tars-watchdog`. |
| Auth screen stuck                          | `BYPASS-AUTH.command`.                                           |
| Keyboard shortcuts not firing in cockpit   | CSP fix shipped W228 — pull main and `REBUILD-TARS-APP.command`. |
| Voice mic not heard                        | macOS System Settings -> Privacy & Security -> Microphone -> TARS. |
| No STT configured                          | Set `OPENAI_API_KEY` in `.env`, or use text input fallback (W232). |
| Welcome modal shows every launch           | localStorage write denied; click `Restart tour` in footer.       |
| Vision Capture fails on Linux/Windows      | Expected — macOS `screencapture` path only; fallback to browser `getDisplayMedia()`. |
| meeet.world doesn't connect                | Expected until brother ships; "Skip — local-only mode" works.    |
| Backend won't boot — `address already in use` | `lsof -ti :8765 \| xargs kill -9`, then `backend_tars_up.sh`.  |

### 8.4 Where data lives

| Path                                                   | Contents |
|--------------------------------------------------------|----------|
| `~/.tars/` (mode `0o700`)                              | All user-local state. |
| `~/.tars/*.sqlite` (21 stores)                         | See `docs/DB_AUDIT_v9.2.md`. |
| `~/.tars/receipts/*.ndjson`                            | Hash-chained receipt ledger. |
| `~/.tars/meeet_token` (`0o600`)                        | `meeet.world` session JWT. |
| `~/.tars/host-key.json`                                | Ed25519 receipt-signing key. |
| `~/.tars/wallet_secrets.json` (`0o600`)                | XChaCha20-Poly1305 wallet keys. |
| `~/.tars/daemon.{out,err}.log` + `daemon.heartbeat`    | Background daemon. |
| `~/.tars/connectors/`                                  | Per-connector OAuth blobs. |
| `~/.tars/vault/`                                       | Encrypted vault entries. |
| `~/.tars/exports/`                                     | Compliance / GDPR export bundles. |
| `/Applications/TARS.app`                               | Installed Tauri bundle. |
| `/tmp/tars-backend-8765.log`                           | Backend stdout/stderr. |
| `~/Library/LaunchAgents/com.tars.backend-watchdog.plist` | Watchdog autostart. |
| `~/Library/LaunchAgents/com.tars.background.plist`     | Daemon autostart. |

---

## §9. Development workflow

### 9.1 Git

- Single branch: `main`. No PR review (solo + AI agents).
- Commit prefix: `Wxxx: <imperative subject>` where `xxx` is the wave number.
- Tag releases: `v9.X.Y` (annotated tags, pushed via `scripts/auto-push-tag.command`).
- Author: `TARS <tars@local>` for agent commits, `Alien <alienram@icloud.com>`
  for operator commits.
- Every commit is independently revertable (no merge commits, fast-forward only).

### 9.2 Build

- `scripts/REBUILD-TARS-APP.command` is the one true build:
  1. `npm install` (or `pnpm install`) in `desktop/`.
  2. `npm run tauri build` -> produces `.app` under
     `desktop/src-tauri/target/release/bundle/macos/`.
  3. Copies `.app` to `/Applications/TARS.app`.
  4. `xattr -dr com.apple.quarantine /Applications/TARS.app` to clear Gatekeeper.
  5. Launches the rebuilt app.
- Backend: pure Python, `pip install -r requirements.txt`, no build step.

### 9.3 Test

- `pytest tests/` — ~350+ pytest cases.
- `scripts/SMOKE-TEST.command` — curl all ~22 known endpoints, exit non-zero
  on any 5xx.
- `scripts/test-all.command` — full pytest + tsc + smoke in sequence.
- `cd experiments/neural-showcase-v3 && npx vitest run` — frontend logic
  (~50 vitest cases).
- `cd experiments/neural-showcase-v3 && npx tsc --noEmit` — type-check.

### 9.4 Brother sync

- Handoff docs live in `docs/HANDOFF_*_FOR_BROTHER.md`. Each one is
  scoped to a window of waves.
- Latest is `docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md` (W214 + W233 final).
- Weekly sync expected; both sides reference `docs/SYNC.md` for the
  cross-instance state.
- Acceptance test: when `scripts/CHECK-MEEET-LIVE.command` prints 4/4 and
  `scripts/CHECK-STATUS.command` is green, the handshake works.

---

## §10. Brother sync brief

The shortest possible actionable list for the brother on `api.meeet.world`,
in priority order. Everything else can wait.

### 10.1 Next 14 days — the 4 auth endpoints

Already specified in full at `docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md`.
Recap:

1. `POST /api/magic-link/start` — mail a one-time code.
2. `POST /api/magic-link/redeem` — swap code for 30-day Ed25519 JWT.
3. `GET /api/oauth/{google|apple}/start` — issue OAuth redirect URL.
4. `GET /api/me` — return tier + features + expiry.

JWT alg `EdDSA`. JWKS at `https://meeet.world/.well-known/jwks.json`.
Tier values: `free | pro | business | lifetime`.

### 10.2 Next 30 days — the 4 billing endpoints

5. `POST /api/billing/usage_event` — HMAC-signed `UsageEvent` ingest;
   idempotency key = `trace_id`. Schema in §3.4 and §7.5.
6. `GET /api/billing/balance` — `{tier, balance_usd, balance_meeet, period_start, period_end}`.
7. `POST /api/billing/topup` — Solana ($MEEET) and card processor routes.
8. Reconciliation handshake — daily script `scripts/reconcile-meeet-billing.py`
   compares TARS local ledger vs `/api/billing/balance`; alert on drift > $0.50.

### 10.3 Next 60 days — telemetry + marketplace

9. `POST /api/telemetry/event` — opt-in structured event ingest.
10. `POST /api/marketplace/install` and `POST /api/marketplace/payout` —
    enforce the 70/30 split on Solana.

### 10.4 Acceptance criteria

- `scripts/CHECK-MEEET-LIVE.command` prints 4/4 auth.
- `scripts/probe-meeet-billing.command` prints E2E billing OK.
- `scripts/CHECK-STATUS.command` is fully green.
- `MEEET_MODE=live` in `.env`; cockpit tier pill flips from FREE to live tier
  after magic-link.

### 10.5 What brother needs from TARS-side

| Need                                | Where                                                            |
|-------------------------------------|------------------------------------------------------------------|
| `BRIDGE_SHARED_SECRET`              | Already distributed W194 (in shared `.env`).                     |
| Schema for `UsageEvent`             | `backend/core/usage/schema.py` (W235).                           |
| Schema for `Receipt`                | `backend/core/receipts/schema.py`.                               |
| Tier caps (the numbers)             | `docs/PRICING_ECONOMICS_v9.2.md` §9.                             |
| `tars://` return URL allowlist      | `tars://auth` only for now; configure as `MEEET_TARS_RETURN_HOSTS`. |

---

## §11. North Star anti-patterns

The 4 ways this project breaks if we stop paying attention. Read once a week.

**1. DO NOT ship a Cursor-clone code editor.**
We do not own the buffer. We wrap a code mode later via the `tars-tab`
VS Code extension (Wave B). The editor surface is one of Cursor's deepest
moats; trying to clone it is a year of work and we end up with a worse
Cursor. The TARS-shape advantage is *life-ops breadth*, not IDE depth.

**2. DO NOT add features that aren't routed through `meeet.world`.**
Every payment, every cross-machine identity action, every cloud sync,
every marketplace install — all roads lead through `meeet.world`. If a
proposed feature has its own auth, its own billing, its own cloud sync,
it's misplaced. Either re-route through brother, or it's local-only-forever.
Anything else creates a fork in the user's mental model and a fork in the
ops surface.

**3. DO NOT break the receipt chain.**
Every consequential action emits a signed receipt, or it's a bug. Failure
modes emit `outcome=tars_error` / `outcome=provider_error` receipts so the
chain stays intact. A user must be able to point at a Solana memo and say
"that's everything my agent did that day." If the chain breaks, the trust
moat breaks; if the trust moat breaks, the regulated-industry sale dies.

**4. DO NOT leak data.**
Local-first means data lives on the user's disk by default. Anything that
touches the cloud needs (a) explicit user consent at config time, (b) a
visible badge in the cockpit, and (c) a Solana-anchored receipt of the
transit. `MEEET_TELEMETRY` is opt-in only. Receipts never ship to anyone
without consent. The on-device guarantee is the entire reason private
funds, lawyers, and healthcare ops will install TARS — burn that and we
become another SaaS.

---

## §11b. Security and threat model

The threat model the system defends against, codified.

### Trust boundaries

1. **Operator <-> TARS backend** — same machine, loopback only. No network
   path. The TARS backend never opens a public port; the Tauri WebView
   reaches `127.0.0.1:8765` directly.
2. **TARS backend <-> `meeet.world`** — outbound HTTPS over TLS. Auth
   via Ed25519 JWT (`meeet_token`); billing events HMAC-signed with
   `BRIDGE_SHARED_SECRET`. Brother's side never initiates a connection to
   TARS.
3. **TARS backend <-> LLM provider** — outbound HTTPS. API keys live in
   `.env` or macOS Keychain. Never serialized into receipts.
4. **TARS backend <-> Solana** — outbound HTTPS (or `solana-py` RPC).
   Anchor transactions signed locally with the host's signing key.
5. **TARS instance <-> other TARS instance (T2T)** — relay-mediated.
   Both sides authenticate via meeet identity; payload is end-to-end
   encrypted; receipts on both sides.

### Hardening defaults

- `~/.tars/` mode `0o700`.
- `~/.tars/meeet_token`, `~/.tars/wallet_secrets.json` mode `0o600`.
- Wallet secrets encrypted with XChaCha20-Poly1305 (passphrase-derived key).
- `TARS_REQUIRE_OPERATOR_CONFIRM=1` adds HMAC confirm token requirement
  on every destructive endpoint.
- `TARS_AUDIT_RAW_TX=0` (default off) — raw signed bytes are *not* persisted
  in the meeet event log.
- `TARS_HIDE_TRACEBACKS=1` in production hides stack traces in HTTP errors.
- Rate limiting at FastAPI middleware level (see §7.3 anti-abuse).

### Privacy guarantees

- Receipts never leave the machine unless user explicitly exports
  (`POST /api/compliance_export/run`).
- `MEEET_TELEMETRY=0` by default. Opt-in only.
- The Solana anchor publishes only the Merkle root hash — *not* receipt
  contents. The chain proves *that* the user did N things, not *what*.
- Public verifier replays Merkle proofs without DB or auth — no leak of
  other users' data.

### Compliance posture

- GDPR / CCPA: `GET /api/usage/export?user=me` exports the user's events.
  Deletion request -> brother wipes balance + spend history; TARS-side
  anonymises receipts (replaces `user_id` with `deleted-<sha256>`) but
  keeps chain integrity intact.
- 7-year default retention on usage events (configurable per BUSINESS
  account).
- Quarterly compliance bundle (`backend/core/compliance_export/`) packages
  all events + Merkle proofs + Solana memo URLs. Sellable to regulated
  industries.

### Known gaps (honest)

- No SOC2 Type II certification yet (Wave B brand work; the underlying
  controls are already in place).
- No formal BAA template (Wave C, when first healthcare customer signs).
- Apple Developer ID signing pending — installer is unsigned and requires
  `xattr -dr com.apple.quarantine` until cert lands.
- Backend autorestart watchdog needs manual install of the LaunchAgent
  first time (`scripts/install-tars-watchdog.command`).

See `docs/THREAT_MODEL.md` and `docs/SECURITY_BASELINE.md` for the deep
detail.

---

## §11c. FAQ (operator quick-answers)

**Q: Why not just ship a code editor like Cursor?**
A: The IDE surface is Cursor's deepest moat — millions of dev-hours of
extension ecosystem inheritance from VS Code. Cloning that is a year of
work for a worse Cursor. We extend into Cursor's audience via the
`tars-tab` VS Code extension (Wave B) and keep the cockpit focused on
life-ops where we are the only player. See §11 anti-pattern #1.

**Q: Why `meeet.world` and not just our own backend?**
A: `meeet.world` is the brother's domain — separately operated identity,
billing, marketplace, token treasury. Coupling all cross-machine concerns
through one external surface keeps TARS deployable as a single-process
desktop binary and lets `meeet.world` handle cross-tenant concerns
(payments, marketplace listings, compliance) at internet scale. See §11
anti-pattern #2.

**Q: What happens to the user if `meeet.world` goes down?**
A: TARS keeps running. FREE-tier features keep working. Receipts keep
emitting locally. The user can `MEEET_MODE=mock` and continue indefinitely.
Cross-machine features (T2T, marketplace, balance polling) pause until
brother comes back.

**Q: Do receipts get sent to the cloud?**
A: No. Receipts live in `~/.tars/receipts/` only. The daily Merkle *root*
(a single hash, no content) anchors on Solana. A user can export receipts
manually for audit, but the system never auto-uploads them.

**Q: What's the model I should use by default?**
A: Cockpit routes routine actions to `haiku-4.6` (cheap, fast),
consequential actions to `sonnet-4.6` (default), Council dissent to
`opus-4.6`. FREE-tier users get `gpt-4o-mini` or local models. Override
in Settings -> Models (Wave A W251).

**Q: How is the $MEEET token different from a security?**
A: $MEEET is a utility token — earnable by quests, marketplace
contributions, AI Clone training. The user never has to touch the token
to use TARS; USD is always an accepted alternative. Pricing page leads
with USD; token is "advanced settings."

**Q: What's the difference between v9.2 beta2 and v10.0 GA?**
A: beta2 = Cursor parity gaps still open (Wave A scoped). v9.3 closes
those. v9.5 ships the TARS-unique edge (voice Composer, receipt-anchored
diffs, SOC2 UI, VS Code extension). v10.0 = T2T code review + on-prem
TARS + voice pair programming + agent economy marketplace. See §6.

**Q: Can a third party install TARS on their own infra (on-prem)?**
A: Not yet. Wave C item C5. First on-prem customer is forecast 2026 Q4.
Today every TARS install requires the operator's own machine, but
`meeet.world` can be self-hosted by the brother if needed.

**Q: How do I know what an agent did?**
A: ACTIVITY tab in cockpit (receipt ledger). Every action: a row with
timestamp, action name, model, cost, outcome, receipt ID. Click the row
-> see the Merkle proof. Compare against the day's Solana memo via
`GET /api/public/proof/anchor/{root}`.

**Q: What if I want to forget a receipt (GDPR)?**
A: Anonymisation is supported (replaces `user_id` with `deleted-<sha256>`)
while preserving chain integrity. Full deletion would break the chain, so
TARS opts for anonymisation by default. See `docs/PRICING_ECONOMICS_v9.2.md`
§8.3.

**Q: Is there a CLI?**
A: Yes. `tars-doctor` (health, fix, watch) and forthcoming
`tars-cli` (Wave B). Most users live in the cockpit; the CLI exists for
remote pickup, scripting, and CI.

---

## §12. Appendix

### 12.1 Doc index

The complete inventory is in `PROJECT_INDEX.md`. Most-cited deep-dives:

- `docs/WHAT_WORKS_v9.2.0-beta2.md` — honest per-feature ship state.
- `docs/OPERATOR_v9.2.md` — 5-minute path from install to first action.
- `docs/COMPETITIVE_ANALYSIS_CURSOR.md` — 705-line gap matrix vs Cursor.
- `docs/ROADMAP_W234_to_v10.md` — Wave A in commit-sized detail.
- `docs/PRICING_ECONOMICS_v9.2.md` — every number brother needs.
- `docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md` — the 4 auth endpoints brother ships.
- `docs/DB_AUDIT_v9.2.md` — every SQLite store TARS touches.
- `docs/STORYBOARD_VOICE_COCKPIT.md` — 8 frames of voice UX.
- `docs/NOTIFICATIONS.md` — iMessage / Telegram / Email contract.
- `docs/RELEASE_NOTES_v9.2.0-beta2.md` — full v9.2.0-beta2 changelog.

### 12.2 Key file paths

| Path                                                  | What's there |
|-------------------------------------------------------|--------------|
| `web_extras/app.py`                                   | FastAPI app entry. |
| `web_extras/routers/`                                 | All ~50 HTTP routers. |
| `web_extras/routers/auth_meeet.py`                    | The auth surface (5 endpoints, TARS-side). |
| `web_extras/routers/usage.py`                         | Consumption console (W235). |
| `web_extras/routers/voice_command.py`                 | `/api/voice/command` for the cockpit (W220). |
| `web_extras/routers/public_proof.py`                  | No-auth Merkle verifier (W204). |
| `backend/core/`                                       | ~30 backend domain modules. |
| `backend/core/usage/schema.py`                        | `UsageEvent` Pydantic schema. |
| `backend/core/metering/`                              | Metering middleware. |
| `backend/core/receipts/`                              | Hash-chained ledger + Solana anchor. |
| `backend/core/storage/bootstrap.py`                   | `init_all_databases()` — boot-time DB init (W231). |
| `backend/core/meeet/`                                 | `meeet.world` HTTP client. |
| `backend/core/meeet_billing/`                         | Billing event sender + balance mirror. |
| `desktop/src-tauri/`                                  | Tauri 2 wrapper. |
| `desktop/src-tauri/web/index.html`                    | The cockpit shell (auth gate + voice cockpit). |
| `scripts/`                                            | All `.command` operator scripts. |
| `.env` / `.env.example`                               | All config. Search `MEEET_` for the cloud knobs. |

### 12.3 Useful curl commands

```bash
# Backend health
curl -s http://127.0.0.1:8765/api/health | jq

# Doctor (all checks)
curl -s http://127.0.0.1:8765/api/doctor | jq

# Tier + entitlements
curl -s http://127.0.0.1:8765/api/entitlements | jq

# Domain pack catalog (7 packs)
curl -s http://127.0.0.1:8765/api/domains/manifest | jq

# Recent receipts (last 50)
curl -s http://127.0.0.1:8765/api/receipts/recent | jq

# Today's Merkle root
curl -s http://127.0.0.1:8765/api/receipts/merkle/$(date -u +%Y-%m-%d) | jq

# Public proof verifier (no auth)
curl -s http://127.0.0.1:8765/api/public/proof/health | jq

# Auth status
curl -s http://127.0.0.1:8765/api/auth/meeet/status | jq

# meeet.world readiness probe (uses scripts/CHECK-MEEET-LIVE.command logic)
bash scripts/CHECK-MEEET-LIVE.command

# Force a voice command (text-input fallback path)
curl -s -X POST http://127.0.0.1:8765/api/voice/command \
  -H 'content-type: application/json' \
  -d '{"text":"what is my tier?"}' | jq

# Trigger a usage event (manual)
curl -s -X POST http://127.0.0.1:8765/api/usage/console?from=today | jq
```

### 12.4 Version history (one line each)

| Version              | Theme                                                                |
|----------------------|----------------------------------------------------------------------|
| `v9.0.0`             | Truthful baseline — JSON->SQLite migration, real Watch-me-work events, OAuth bridge, health endpoint, signed installer prep. |
| `v9.1.0`             | Cowork + MCP + doctor + signed builds attempt + B2B Workshop + Apple cert effort. |
| `v9.1.1`             | `tars-doctor` CLI + `/api/doctor` HTTP + cockpit Status page live. |
| `v9.1.2`             | iMessage + Telegram + Email notification bridges + auto-fanout. |
| `v9.1.3`             | `tars-doctor --fix` mode + `POST /api/doctor/fix` + test-notify. |
| `v9.1.4`             | Windows schtasks daemon parity + `--watch` mode + 3 new doctor checks. |
| `v9.2.0-beta1`       | Control Center cockpit + AI Clone webhook sync + first `usage.tokens` event + early-access install line. |
| `v9.2.0-beta2`       | Auth gate (W219) + voice cockpit (W220) + REBUILD-TARS-APP + CSP fix + boot-time DB init + meeet handshake + text-input fallback + consumption console (W235). |
| `v9.3.0` *(target)*  | Wave A: usage tab, models switcher, `.tars/rules.yml`, `@-mentions`, MCP panel, background agents tray. |
| `v9.5.0` *(target)*  | Wave B: voice-driven Composer, receipt-anchored diffs, SOC2 audit UI, `tars-tab` VS Code extension. |
| `v10.0.0 GA` *(target)* | Wave C: T2T code review, on-prem TARS, voice pair-programming, agent economy marketplace. |

---

**End of master doc.** When in doubt, re-read §1 (North Star) and §11
(anti-patterns). Everything else is mechanical execution.
