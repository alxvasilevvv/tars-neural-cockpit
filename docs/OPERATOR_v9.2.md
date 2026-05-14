# TARS v9.2 · Operator one-pager

For the thousands of users about to install TARS. One page, one purpose:
**get you from download to first useful action in 5 minutes.**

## 1. Install (60 seconds)

macOS (Apple Silicon or Intel):

```bash
git clone https://github.com/alxvasilevvv/tars-neural-cockpit.git
cd tars-neural-cockpit
bash scripts/install-tars.sh      # one-time setup, ~2 min
```

## 2. First launch (90 seconds)

```bash
bash scripts/tars-start.command
```

What happens:
1. **Backend** boots on `127.0.0.1:8765` (FastAPI, JSON-only)
2. **Daemon** registers as a macOS LaunchAgent (`com.tars.background`)
3. **TARS.app** opens. First time only: a Welcome modal asks you to
   pick one of 6 starter packs. Click one → you get a starter agent
   → cockpit jumps to the AGENTS tab.

The 6 packs you can pick from:
| Pack | What it does | Tier |
|---|---|---|
| **Business** | CRM, daily brief, outreach, KPI graph | Pro+ for full |
| **Entrepreneur** | Cold outreach, deal pipeline, founder ops | Free |
| **Science** | arXiv triage, citation graph, research notes | Free |
| **Civic** | Public records, legislators, court cases | **Always free** |
| **Web search** | Outbound search via Brave / DDG | Free |
| **Algotrade** | Backtest, signal IR, paper-trading | Pro+ |

## 3. Configure your LLM key (45 seconds)

Edit `.env` at the repo root:

```bash
ANTHROPIC_API_KEY=sk-ant-...
# or
OPENAI_API_KEY=sk-...
# or
OPENROUTER_API_KEY=sk-or-...
```

Restart the backend:

```bash
bash scripts/backend-up.command
```

Open TARS.app → STATUS tab → top-right `↻ Reload`. Tier badge in
header should flip from `FREE` to your live tier.

## 4. Your first action (60 seconds)

The 4 fastest ways to feel the system:

- **Daily briefing** — STATUS tab leads with today's headline. No setup.
- **Pick an agent** — AGENTS tab → your starter is already there.
  Click `+ Create agent` for more.
- **Civic lookup** — CHAT tab → type "look up my state senator for CA".
  Free, no key needed, real OpenStates data.
- **Vision** — VISION tab → 📸 Capture & analyze → describes your
  screen via Claude / OpenAI. Uses your configured key.

## 5. Keep it alive (one command, once)

Run the watchdog so the backend self-restarts if it crashes:

```bash
bash scripts/backend-watchdog.command &
disown
```

This polls `/api/health` every 30s and restarts via `backend_tars_up.sh`
if the backend goes down. Logs to `~/.tars/backend-watchdog.log`.

Stop with `kill $(cat ~/.tars/backend-watchdog.pid)`.

## Cockpit quick reference

9 tabs in TARS.app:

- **STATUS** — health checks, today briefing, daemon log, quick actions
- **AGENTS** — domain packs (left) + your agents (right) + create button
- **CHAT** — threaded conversations with your active agent
- **ACTIVITY** — receipt ledger (signed, hash-chained, Solana-anchored)
- **CONNECTORS** — Slack, Gmail, Calendar, GitHub, Telegram, meeet.world
- **COWORK** — multiplayer sessions (Pro+)
- **VISION** — screen capture & analyze, OCR on a file, planned features
- **PLUGINS** — marketplace v0 (browse free, install Pro+)
- **SETTINGS** — API keys, billing, system, 🌐 meeet.world 1-click connect

Header pills:
- Version badge — `v9.2.0-beta2 · local`
- Tier badge — `FREE` / `PRO` / `BUSINESS` (live from /api/entitlements)
- API dot — green = backend alive, red = offline

## Troubleshooting

**"Backend unreachable" persists** → `scripts/backend-up.command`. If
it keeps dying, start `scripts/backend-watchdog.command` (step 5 above).

**Welcome modal shows every launch** → localStorage write was denied
(rare in Tauri). Click `↺ Restart tour` in footer to re-trigger; if
the issue persists, clear app cache via System Settings → Privacy.

**Vision Capture button fails on Linux/Windows** → expected. The macOS
`screencapture` path is the only one wired today; both other OSes fall
back to browser `getDisplayMedia()`.

**Sign in to meeet.world doesn't connect** → expected for beta2. The
meeet.world `/api/magic-link/redeem` endpoint ships next; for now your
token is saved locally and will exchange automatically once the brother
side is live.

## Where to read further

- `docs/HANDOFF_W203.md` — engineering handoff for the W203 series
- `docs/RELEASE_NOTES_v9.2.0-beta2.md` — full commit-level changelog
- `docs/ROADMAP_v9.2_v10.md` — what's next through v10.0
- `docs/NOTIFICATIONS.md` — iMessage/Telegram/Email setup
- `https://tars.meeet.world/docs` — public docs site

## Where to report

GitHub: https://github.com/alxvasilevvv/tars-neural-cockpit/issues
Or click `🐞 Report` in the cockpit footer.
