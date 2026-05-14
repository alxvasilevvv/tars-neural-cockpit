# WHAT WORKS — TARS v9.2.0-beta2

Last updated: 2026-05-14. Honest, exhaustive, per-feature inventory.
Format: ✅ works · ⚠ partial · 🚧 planned · 🚫 deferred.

## Cockpit (TARS.app desktop)

| Feature | State | Notes |
|---|---|---|
| Embedded SVG monolith logo | ✅ | Animated LED rail + pulse + cursor |
| 9-tab nav (Status/Agents/Chat/Activity/Connectors/Cowork/Vision/Plugins/Settings) | ✅ | All tabs render |
| Tier-pill (FREE/PRO/BUSINESS) | ✅ | Live from `/api/entitlements`, refreshes 60s |
| Welcome onboarding modal (W205) | ✅ | First-launch, localStorage gated |
| Today briefing card (W206) | ✅ | Pulls `/api/briefing/today` |
| Doctor health checks panel | ✅ | 11 checks, color-coded counters |
| Quick actions (Reload / fix vault / test alert / full doctor) | ✅ | |
| Chat tab — thread list | ✅ | From `/api/chat/threads` |
| Chat tab — send + receive messages | ⚠ | Needs LLM key configured; streaming via Anthropic/OpenAI/OpenRouter |
| Agents tab — pack catalog | ✅ | 7 packs from `/api/domains/manifest` |
| Agents tab — user agents list + create | ✅ | `POST /api/agents` |
| Activity tab — receipt ledger | ✅ | From `/api/receipts/recent` |
| Connectors tab — health badges | ✅ | Slack/Gmail/Calendar/GitHub/Telegram/meeet probed |
| Cowork tab — sessions list | ⚠ | List works; multiplayer Pro+ gated |
| Vision tab — Capture & analyze | ⚠ | Tauri command needs rebuild + LLM key |
| Vision tab — OCR a file | ⚠ | Works if pytesseract installed locally |
| Plugins tab — marketplace browse | ✅ | Read-only browse; install gated Pro+ |
| Settings → API keys badges | ✅ | Anthropic/OpenAI/OpenRouter live |
| Settings → meeet.world 1-click connect | ⚠ | Token-paste works; full magic-link awaiting brother's `/api/magic-link/redeem` |
| Settings → Billing block | ✅ | source/authority/tier |
| Settings → System (version/daemon/scheduler/disk) | ✅ | |
| Footer Docs / Report / Restart tour links | ✅ | Tauri shell.open external |
| Tier-aware visual gating | ✅ | Dims Pro+ tabs for FREE users |

## Backend HTTP endpoints

### W203 / W204 / W206 / W209 (new in this push)

| Endpoint | State | Notes |
|---|---|---|
| `GET /api/vision/health` | ✅ | Capability probe |
| `POST /api/vision/ocr` | ✅ | Local pytesseract |
| `POST /api/vision/analyze` | ✅ | Anthropic/OpenAI vision, falls back if no key |
| `POST /api/auth/meeet/exchange` | ✅ | Token persist to `~/.tars/meeet_token` |
| `GET /api/auth/meeet/status` | ✅ | |
| `DELETE /api/auth/meeet/disconnect` | ✅ | |
| `GET /api/public/proof/anchor/{root}` | ✅ | Returns Solana explorer URL |
| `POST /api/public/proof/verify` | ✅ | Pure Merkle replay, no DB |
| `GET /api/public/proof/health` | ✅ | |
| `GET /api/briefing/today` | ✅ | 4-section snapshot |
| `POST /api/digest/run` | ✅ | Generates weekly digest |
| `GET /api/digest/latest` | ✅ | Reads persisted reflection |

### Pre-existing (confirmed still working)

| Endpoint | State | Notes |
|---|---|---|
| `GET /api/health` | ✅ | Plus `/health` alias |
| `GET /api/doctor` | ✅ | + `/fix`, `/registry`, `/test/notify` |
| `GET /api/entitlements` | ✅ | + `/tiers` static catalogue |
| `GET /api/domains/manifest` | ✅ | 7 packs |
| `POST /api/agents` | ✅ | Create user agent |
| `GET /api/agents` | ✅ | List user agents |
| `GET /api/chat/threads` | ✅ | |
| `POST /api/chat/messages` | ⚠ | LLM call works if key set |
| `GET /api/receipts/recent` | ✅ | |
| `GET /api/receipts/merkle/{day}` | ✅ | + `/proof/{id}`, `/anchor/{day}` |
| `GET /api/cowork/sessions` | ✅ | |
| `GET /api/connectors/{slack,gmail,calendar,github,telegram,meeet}/health` | ✅ | |
| `GET /api/marketplace/listings` | ✅ | |
| `GET /api/product/version` | ✅ | |

## Domain packs

| Pack | Actions | State |
|---|---|---|
| Business | kpi_snapshot, daily_brief, log_deal, draft_email | ✅ |
| Entrepreneur | outreach, pipeline, fundraise_stack | ✅ |
| Science | arxiv_search, citation_graph, research_notes | ✅ |
| Algotrade | backtest, signal_ir, paper_trade | ✅ |
| Traders | live_awareness, position_monitor, risk_gate | ✅ |
| Wallet | balances, $MEEET, anchor | ✅ |
| Web search | brave, searxng, ddg | ✅ |
| **Civic** (W204, NEW) | lookup_legislator, recent_votes, court_case_search | ✅ |
| MLM (deprecated) | — | 🚫 redirects to Entrepreneur |

## Operations

| Feature | State | Notes |
|---|---|---|
| FastAPI backend on :8765 | ✅ | uvicorn |
| LaunchAgent (com.tars.background) | ✅ | macOS, persistent across reboots |
| Linux systemd unit | ✅ | parity |
| Windows schtasks daemon | ✅ | parity |
| Receipt-chain (hash-chained) | ✅ | |
| Receipt-anchor (Solana memo, batched) | ✅ | Daily Merkle root anchor |
| tars-doctor CLI | ✅ | + `--fix`, `--watch`, `--test-notify` |
| iMessage / Telegram / Email notifications | ✅ | fanout sibling |
| Backend autorestart watchdog (W207) | ✅ | `scripts/backend-watchdog.command` |
| Apple-signed installer | 🚫 | Awaits Apple Developer cert |
| Auto-update via Tauri updater | ⚠ | Plugin loaded; release JSON not yet published |

## meeet.world integration

| Surface | State | Notes |
|---|---|---|
| `MEEET_BASE_URL` config | ✅ | |
| Billing remote read | ⚠ | Returns 401 without account |
| Receipt mirror | ⚠ | Sends; needs his ingest endpoint live |
| Magic-link 1-click connect | 🚧 | TARS side ready; awaits `/api/magic-link/redeem` |
| Cross-device sync | 🚧 | After magic-link lands |

## Test coverage

- **Total pytest cases:** ~350
- **New in W203-W211:** 27
  - `test_vision_router.py` 7
  - `test_auth_meeet_router.py` 6
  - `test_civic_pack.py` 8
  - `test_public_proof_router.py` 6
  - `test_briefing_digest.py` 7
- **Run:** `bash scripts/test-all.command`

## Honest list of "promise vs reality" gaps

1. Welcome modal claims meeet.world cloud sync — fully wires only when
   brother ships `/api/magic-link/redeem`. Until then it's local-only.
2. Vision tab "Capture & analyze" requires `.app` rebuild for the
   new Tauri command (`vision_capture_screen`). Browser fallback works.
3. Daily digest fanout requires `TARS_DIGEST_CHANNELS` env to point at
   configured channel(s). Default state is generate-only.
4. Backend-watchdog must be started manually first time — automatic
   LaunchAgent installation is a planned W217.

## Next 3 commits (priority queue)

- W216 — LaunchAgent install script for the watchdog (autostart)
- W217 — Distress detection in iMessage bridge (AI-for-humanity #3)
- W218 — OCR-to-accessibility shortcut (AI-for-humanity #5)
