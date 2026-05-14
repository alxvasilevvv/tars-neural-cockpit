# W203 handoff — TARS Control Center upgrade

**Status:** code shipped, .app rebuilt + installed, backend endpoints added. Local pytest+install verified. Push to GitHub blocked from sandbox — needs `scripts/auto-push.command` from your end.

## What landed

### Cockpit (TARS.app)
- Embedded SVG monolith wordmark in header (Interstellar-style: 4 vertical
  panels, animated LED rail on the right, pulsing fill-bar in segment 2,
  blinking terminal cursor next to "TARS"). Source: `desktop/src-tauri/web/assets/tars-{mark,wordmark}.svg` and inlined in `index.html` header.
- Tier-pill in header (FREE / PRO / BUSINESS) live-bound to `/api/entitlements`
  with per-tier color (indigo / cyan / amber).
- 9 tabs total (was 7): **Status · Agents · Chat · Activity · Connectors ·
  Cowork · Vision · Plugins · Settings**.
- **Agents tab** — 2-column layout. Left: 6 real domain packs from
  `/api/domains/manifest` (wealth, health, family, product, brand,
  entrepreneur). Right: user agents from `/api/agents` with "+ Create agent"
  button (`POST /api/agents` with name + pack_slug).
- **Vision tab** — 4 capability cards: capture+analyze, OCR a file,
  selection→speak (planned), agent-driven actions (roadmap). Pulls from new
  `/api/vision/*` endpoints.
- **Settings → MEEET.WORLD · 1-CLICK CONNECT** — purple gradient card with:
  magic-link button (opens `meeet.world/account/tars-connect` in external
  browser via Tauri `shell.open`), account-page button, paste-token button.

### Backend (FastAPI on :8765)
- `web_extras/routers/vision.py` (NEW):
  - `GET  /api/vision/health` — capability probe
  - `POST /api/vision/ocr` — multipart upload → pytesseract local OCR
  - `POST /api/vision/analyze` — JSON {image_data_url, prompt} →
    Anthropic/OpenAI vision API. Picks Anthropic first if key set; else
    OpenAI; else returns honest `no_llm_key_with_vision`.
- `web_extras/routers/auth_meeet.py` (NEW):
  - `POST /api/auth/meeet/exchange` — accept pasted token, persist at
    `~/.tars/meeet_token` with 0o600. Returns optimistic `connected` until
    brother ships `meeet.world/api/magic-link/redeem`.
  - `GET  /api/auth/meeet/status` — is a token stored?
  - `DELETE /api/auth/meeet/disconnect`
- Both wired into `web_extras/app.py` imports + `include_router` list.

### Build pipeline
- Rebuilt TARS.app via `scripts/build-tars-app.command` (rustc + Tauri 2,
  ~16s incremental; full build ~5-15min).
- Reinstalled via `scripts/install-tars-app.command` — old removed,
  quarantine cleared, new launched. New cockpit verified visually:
  monolith logo + 9 tabs + FREE pill all rendering.

## Commits

```
f5acdfc W203 backend — /api/vision and /api/auth/meeet endpoints for new cockpit
c08a4c7 W203 — TARS Control Center upgrade: monolith logo + Agents/Vision tabs + 1-click meeet.world
```

Both clean (`git status` is empty). `git push origin main` 403'd from this
sandbox (proxy block) — run `bash scripts/auto-push.command` from your
machine to sync.

## How to verify end-to-end

```bash
# 1. backend up
bash scripts/backend_tars_up.sh           # or double-click scripts/backend-up.command

# 2. probe new endpoints
curl -s 127.0.0.1:8765/api/vision/health | jq
curl -s 127.0.0.1:8765/api/auth/meeet/status | jq

# 3. open TARS.app — tabs should now include AGENTS + VISION,
#    tier-pill should swap from FREE to whatever your /api/entitlements says.
open -a TARS
```

If cockpit still says "Backend unreachable" after backend is up, the
30-second auto-refresh hasn't fired yet — click `↻ Reload` in the cockpit's
Quick Actions panel.

## Known gaps (W204 candidates)

1. **Magic-link redeem flow** — TARS side accepts + persists tokens, but
   meeet.world's `/api/magic-link` endpoint isn't shipped yet. Currently
   returns optimistic "connected". Brother handoff has the contract.
2. **Vision capture via Tauri** — cockpit JS tries
   `window.__TAURI__.invoke('vision_capture_screen')` first, falls back to
   `getDisplayMedia()`. The Rust-side `vision_capture_screen` command
   isn't registered yet — Tauri 2 screenshot plugin install is the next
   step. Until then, browser API fallback works.
3. **Pytesseract not bundled** — `/api/vision/ocr` returns
   `ocr_unavailable` unless user has `brew install tesseract && pip install
   pytesseract Pillow`. Add to install.sh or document in INSTALL.md.
4. **CORS** — `auth_meeet` and `vision` routes inherit the existing CORS
   policy (`localhost:5173`, `127.0.0.1:5173`, `tars.meeet.world`). Tauri
   webview hits `tauri://localhost` which is already CORS-exempt via the
   custom protocol handler — no extra wiring needed.

## AI-for-humanity ideas worth doing next (from W203 orchestrated audit)

1. Personal weekly health/finance digest — Sunday cron via existing
   playbook scheduler → iMessage/email summary.
2. Civic-data agent pack — 7th domain pack wrapping OpenStates / FEC /
   courtlistener for free public-records queries.
3. Distress detection in iMessage bridge — opt-in crisis-keyword pass on
   `~/Library/Messages/chat.db`, HIL-gated.
4. Receipts → public proof API — `/api/public/proof/{root}` so anyone can
   verify TARS-produced outputs without trusting us.
5. OCR-to-accessibility — global shortcut: select region → OCR → speak via
   existing TTS. Free screen-reader for low-vision users.
6. Cowork "ask the village" — extend existing W129 cowork module with a
   public-help mode (anonymous helpers, receipts make it auditable).
7. Offline LLM fallback — one-click "force edge" toggle + bundled small
   local model so TARS works without network/budget.
