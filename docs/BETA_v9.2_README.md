# TARS v9.2.0-beta1 — Early Access for Power Users

**Status:** alpha-grade infrastructure, partial business layer
**Audience:** technical power-users who want to try TARS and provide feedback
**Date:** 2026-05-14

---

## What this is

TARS is a local-first AI operator that runs on your Mac. The v9.2.0-beta1
release ships the **operational infrastructure layer** — working backend,
health monitoring, notifications, marketplace, cowork sessions, voice
synthesis — wrapped in a clean operator cockpit.

## What works (verified by 323 passing tests)

- ✅ **FastAPI backend** on `:8765` — entitlements, health, doctor,
  notifications, voice synthesis, cowork sessions, MCP tools, receipts
  ledger, marketplace registry
- ✅ **Background daemon** via LaunchAgent — heartbeat, drift detection,
  auto-fanout on health change
- ✅ **TARS doctor** — 11 health checks with auto-fixers (vault, daemon,
  scheduler), HTTP routes, HTML dashboard, `--watch` mode
- ✅ **Notifications fanout** — iMessage + Telegram + Email (per-channel
  config via env)
- ✅ **Voice** — STT (Whisper), TTS (ElevenLabs + OpenAI + macOS say),
  6 personas, cost ledger, budget gate
- ✅ **AI Clone v0.2** — style profile, portable export/import,
  cross-machine sync via webhook
- ✅ **Cowork sessions** — multiplayer agent sessions with handoff
- ✅ **MCP server** — 5 tools, JSON-RPC bridge for Claude/Cursor
- ✅ **Marketplace v0** — 12 seed plugin listings, install pipeline,
  local ratings, HIL gate
- ✅ **Receipts ledger** — hash-chained signed action receipts (Solana
  anchor coming v9.3)

## What's broken / partial (honest framing)

- ⚠️ **Bundled Tauri /cockpit route** — known v9.1.0-preview localStorage
  bug causes "operation is insecure" error on app load. **Workaround:**
  use `scripts/tars-start.command` which loads the working cockpit
  HTML in a chromeless Chrome window. Native .app cockpit will be fixed
  in v9.2.0.
- ⚠️ **Voice loop incomplete** — wake-word detection, narration auto-loop,
  VAD pause detection are roadmap items for v9.2.
- ⚠️ **Supervisor not implemented** — budget cap, HIL gate, kill switch
  exist on roadmap but no code yet. **Implication:** do NOT install
  untrusted third-party plugins until v9.3.
- ⚠️ **meeet.world OAuth broker** — Slack/Gmail/Calendar connectors use
  direct OAuth, not via meeet. Magic-link sign-in is on v9.2 roadmap.
- ⚠️ **Native skills** (Quest/Stake/Arena/Discovery) — vapor in v9.1
  docs, real implementation lands v9.3.

## Quick start

### Prerequisites

- macOS 13+ (Ventura or later)
- Apple Silicon or Intel Mac
- Python 3.10+ (3.12 recommended)
- Google Chrome (for cockpit window)
- ~500 MB free disk space

### Install

```bash
git clone https://github.com/alxvasilevvv/tars-neural-cockpit.git ~/tars
cd ~/tars/jarvis
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY (or OPENROUTER_API_KEY or OPENAI_API_KEY)
```

### Start

Double-click `scripts/tars-start.command` in Finder. This:

1. Starts backend on `:8765`
2. Installs LaunchAgent for background daemon
3. Opens chromeless cockpit window

That's it. The cockpit lives at `http://127.0.0.1:8765/api/doctor/cockpit`.

### Optional: notifications

To receive health alerts when something drifts, set in `.env`:

```bash
TARS_DAEMON_FANOUT_CHANNELS=imessage,telegram,email

# iMessage (macOS only, no setup needed)
TARS_IMESSAGE_RECIPIENT=+1234567890

# Telegram
TARS_TELEGRAM_BOT_TOKEN=<from @BotFather>
TARS_TELEGRAM_CHAT_ID=<your chat id>

# Email (SMTP)
TARS_EMAIL_SMTP_HOST=smtp.gmail.com
TARS_EMAIL_SMTP_PORT=587
TARS_EMAIL_SMTP_USER=you@example.com
TARS_EMAIL_SMTP_PASS=<app password>
TARS_EMAIL_TO=you@example.com
```

Restart backend after editing `.env`.

## Operator launchers (Finder double-click)

| Script | What it does |
|---|---|
| `scripts/tars-start.command` | **Start TARS (backend + daemon + cockpit)** |
| `scripts/backend-up.command` | Backend only on `:8765` |
| `scripts/open-doctor.command` | Open doctor + cockpit in Chrome |
| `scripts/fix-all-warns.command` | Auto-close all WARN rows (vault, daemon, scheduler) |
| `scripts/verify-doctor.command` | Snapshot 11 doctor checks to file |
| `scripts/relaunch-cockpit.command` | Restart backend + open cockpit |
| `scripts/test-categories.command` | Run pytest by category (diagnostic) |
| `scripts/probe-meeet-billing.command` | Test meeet billing endpoint reachability |

## Feedback

- **Issues:** https://github.com/alxvasilevvv/tars-neural-cockpit/issues
- **Roadmap:** [docs/ROADMAP_v9.2_v10.md](./ROADMAP_v9.2_v10.md)
- **Architecture:** [docs/](./)

## What's NOT in this release (will be in v9.2.0 stable)

- Fixed Tauri /cockpit (real .dmg install experience)
- Wake-word + voice loop
- Real supervisor (budget cap + HIL gate)
- Magic-link sign-in via meeet.world
- Solana memo dispatch for receipt anchoring

## What's NOT in any release yet (v9.3+)

- Native skills (Quest/Stake/Arena/Discovery)
- T2T (agent-to-agent contracts)
- Plugin payments (70/30 split, Stripe live mode)
- iOS/Android apps
- Multi-tenant SaaS

See full roadmap for the 22-26 week trajectory to v10.

## Known caveats

1. **Single-user.** Backend is local-first SQLite. Multi-tenant rebuild is
   v10.0 work.
2. **No signed .dmg yet.** Install is via `git clone` + Python virtualenv.
   Signed installer is coming v9.2.0 stable.
3. **No Stripe.** Subscription/marketplace payments are stubbed. Power
   users in beta get unlimited free access.
4. **Sandbox required for untrusted plugins.** Until Supervisor is real
   (v9.2 roadmap), do NOT install third-party plugins.

---

*This is a real piece of working software with real gaps. We're shipping
the beta so you can see for yourself, give feedback, and help us figure
out the right v10. Thanks for trying it.*
