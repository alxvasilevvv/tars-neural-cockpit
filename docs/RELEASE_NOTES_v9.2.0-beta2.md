# TARS v9.2.0-beta2 — Release notes

Released: 2026-05-14. Beta channel.

A focused launch-readiness push for the thousands of users waiting in
the queue. The headline: the new desktop cockpit is no longer just a
dashboard — it greets you, briefs you, schedules itself, and explains
what every panel does.

## What's new (since beta1)

### Desktop cockpit
- **Welcome onboarding** (W205) — first launch shows a 6-pack picker.
  Pick a domain → starter agent created automatically → straight into
  the AGENTS tab. Footer has a `↺ Restart tour` link to replay it.
- **Today briefing card** (W206) — STATUS tab now leads with a one-line
  headline ("All N checks green. X receipts in last 24h.") plus a 3-row
  KV that pulls from `/api/briefing/today`. Refreshes alongside doctor
  every 30s.
- **Tier-aware visual gating** (W210) — tabs requiring Pro/Business
  dim with a hover tooltip explaining the requirement. Never hides —
  discovery first, upgrade prompt second.
- **Footer links** (W208) — Docs / Report bug / Restart tour, all
  opening via Tauri shell.open to external browser.

### Backend endpoints
- `GET /api/briefing/today` (W206) — one-shot snapshot across health,
  activity, reflection, agents. Always returns 200; each section is
  independently fault-tolerant.
- `POST /api/digest/run` & `GET /api/digest/latest` (W209) — weekly
  digest generator that aggregates the last 7 days, produces a
  human-readable text summary, persists to `~/.tars/reflection_latest.json`,
  and best-effort fanouts via iMessage/Telegram/Email when configured.
- `POST /api/vision/analyze` & `POST /api/vision/ocr` & `GET /api/vision/health`
  (from W203, now with tests) — Claude/OpenAI vision API + local
  pytesseract OCR. Falls back to `getDisplayMedia` if the Tauri
  `vision_capture_screen` command isn't available.
- `POST /api/auth/meeet/exchange` + `/status` + `/disconnect` (W203) —
  1-click meeet.world token paste flow. Persists to
  `~/.tars/meeet_token` with 0o600.
- `GET /api/public/proof/anchor/{root}` + `POST /api/public/proof/verify`
  + `/health` (W204) — anyone can verify a TARS receipt without a key
  or account. Pure-function Merkle replay; no DB access needed.

### Domain packs
- **Civic** (W204) — 7th pack, free for every tier. Three keyless
  actions over public APIs: `lookup_legislator` (OpenStates),
  `recent_votes` (OpenStates), `court_case_search` (CourtListener).
  No partisan opinions; sources cited; private-citizen data never
  gathered.

### Operations
- **`scripts/backend-watchdog.command`** (W207) — polls the backend
  every 30s, restarts via existing `backend_tars_up.sh` if it goes
  down. Pidfile-guarded so it can't double-run. Logs to
  `~/.tars/backend-watchdog.log`.
- **Tauri screen capture** (W203) — new `#[tauri::command] vision_capture_screen`
  on macOS uses `screencapture -x -t png` + base64 encode → data URL.
  Cockpit's "📸 Capture & analyze" button now works end-to-end after
  rebuild.

### Tests
27 new pytest cases lock the W203/W204/W206/W209 behavior:
- `tests/test_vision_router.py` (7)
- `tests/test_auth_meeet_router.py` (6)
- `tests/test_civic_pack.py` (8)
- `tests/test_public_proof_router.py` (6)
- `tests/test_briefing_digest.py` (7)

All env-isolated (temp HOME), all monkey-patch external HTTP, none
require real keys.

## Commits in this release

```
c08a4c7  W203  TARS Control Center upgrade: monolith + Agents/Vision tabs + 1-click meeet
f5acdfc  W203  backend — /api/vision and /api/auth/meeet
e28d80a  W203  handoff doc
dea33b7  W203  tests + Tauri vision_capture_screen
817a32a  W204  Civic domain pack
91da17b  W204  Public verifiable-proof endpoints
ff11eb8  W205  Welcome onboarding modal
5d1f042  W206  Daily briefing endpoint + Today card
81026e0  W207  backend-watchdog.command
00474db  W208  Footer: Docs / Report / Restart tour
99e5d79  W210  Tier-aware visual gating
af9ba69  W211  pytest coverage for briefing/digest
```

## Upgrade path

Existing v9.2.0-beta1 users:

```bash
git pull origin main
bash scripts/build-tars-app.command      # ~5-15 min first time, ~30s incremental
bash scripts/install-tars-app.command    # replaces /Applications/TARS.app
bash scripts/backend-up.command          # restart backend
bash scripts/backend-watchdog.command &  # NEW — keeps backend alive
```

After install, click `↺ Restart tour` in the footer to see the new
Welcome modal.

## What's not in this release (next up)

- Signed installer (DMG/MSI/AppImage) — Apple Developer cert is the
  remaining bottleneck; documented in `docs/HANDOFF_brother_apple_cert.md`
- Real meeet.world magic-link redeem — TARS side is ready; meeet.world
  side ships `/api/magic-link/redeem` next
- Background daemon LaunchAgent for backend-watchdog (currently must
  be started manually or via login items)

## Credits

Built with Claude (Sonnet) in a single 3-hour autonomous push.
All code committed locally; push to `origin/main` via
`scripts/auto-push.command`.
