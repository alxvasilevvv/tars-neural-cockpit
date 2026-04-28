# Claude Code — TARS context

Auto-loaded by Claude Code in every session. Cursor reads the same context via
`.cursorrules` and `.cursor/rules/tars-architecture.mdc`. Keep all three in sync.

> **Naming**: the product is **TARS**. Older artefacts may say "Jarvis" — when
> editing, change copy to TARS. The folder name `Jarvis/jarvis` stays as-is so
> existing paths don't break.

## Project

- **TARS** — local-first neural cockpit. Released under the `meeet.world` brand
  with end-to-end logging through the meeet bridge.
- Backend: Python (FastAPI-style routers under `web_extras/routers/`), MCP entry
  points in `backend/mcp/`, agents in `backend/agents/`.
- Frontend canon: dependency-free vanilla HTML/CSS/JS in `frontend/` (no React,
  no Tailwind, no bundler).
- Premium marketing surfaces:
  - `experiments/neural-showcase-v2/` — vanilla JS + Vite + Three.js + GSAP +
    Lenis + postprocessing. WebGL-heavy, custom GLSL. Dev port `5173`.
  - `experiments/neural-showcase-v3/` — React 18 + TypeScript + Vite +
    Tailwind v4 + framer-motion + lucide. shadcn-style `components.json`
    pre-wired so any [21st.dev](https://21st.dev) block installs with
    `npx shadcn@latest add "<url>"`. Dev port `5174`.
  These are the only places where heavier frontend deps live. Do not bleed
  those deps into `frontend/`.

## Awareness modules (load-bearing)

`backend/core/awareness/` contains calendar, memory, code_index, mac_actions.
Treat as load-bearing — do not refactor without explicit scope.

## Domain packs (Phase 9)

`backend/core/domains/` is a plugin system that adapts the neural core to
specific audiences. Built-in packs: `traders`, `business`, `mlm`, `science`.

- Base types: `backend/core/domains/base.py`
  (`DomainPack`, `DomainManifest`, `ActionSpec`, `AwarenessSource`).
- Registry: `backend/core/domains/registry.py` (`register`, `get_pack`,
  `all_packs`).
- Built-in packs: `backend/core/domains/packs/{traders,business,mlm,science}/`
  with `pack.py`, `actions.py`, `awareness.py`, `prompts.py`, `manifest.json`.
- Router: `web_extras/routers/domains.py` exposes
  `GET /api/domains`, `GET /api/domains/{slug}`,
  `GET /api/domains/{slug}/awareness`, `GET /api/domains/{slug}/prompt`,
  `POST /api/domains/{slug}/actions/{action_id}`. The POST endpoint runs inside
  a meeet trace scope and emits `domain.action.invoked|completed|failed`.
- Tests: `tests/test_domains.py`, `tests/test_meeet.py`,
  `tests/test_meeet_store.py`, `tests/test_real_adapters.py`,
  `tests/test_awareness_fetchers.py`, `tests/test_awareness_stream.py`,
  `tests/test_council.py`, `tests/test_policy.py`,
  `tests/test_playbooks.py`. **79 tests, all green.**
- Spec: `docs/DOMAIN_PACKS.md`.

### Real adapters shipped (action contracts stay stable)

- `traders.fetch_quote` — DexScreener public search, prefers
  highest-liquidity pair with populated 24h change.
- `traders.summarize_market` — basket aggregation: bias
  (risk-on/off/neutral), top gainers/losers, dispersion contradictions.
- `science.search_literature` — arXiv Atom feed.
- `science.summarize_paper` — arXiv abstract by id / `arxiv:<id>` /
  full URL; returns title/authors/tldr/abstract.
- `business.kpi_snapshot`, `business.daily_brief` — local
  JSON-backed (`data/business_kpi.json`, `data/business_deals.json`,
  override via `BUSINESS_KPI_PATH` / `BUSINESS_DEALS_PATH` or the
  `path` arg).
- `mlm.downline_snapshot`, `mlm.retention_alert` — local
  CSV-backed (`data/mlm_network.csv`, override via
  `MLM_NETWORK_PATH`); `score_recruit`, `generate_post` are
  deterministic heuristics with model labels.

### SSE awareness stream (Phase 9.2)

`GET /api/awareness/stream` (`web_extras/routers/awareness.py`) emits
`hello`, `system.pulse`, `domain.heartbeat`, `bye` frames. Tunable via
`AWARENESS_PULSE_S` and `AWARENESS_TICK_LIMIT`. Frontend consumer:
`experiments/neural-showcase-v3/src/lib/awareness.ts` +
`<AwarenessTicker/>` mounted at the top of `/cockpit`.

### Awareness snapshots (Phase K-A)

Every `AwarenessSource` may carry an async `fetcher`. The HTTP surface
`GET /api/domains/<slug>/awareness/<source_id>/snapshot` materialises
the source on demand inside a meeet trace scope and emits
`awareness.snapshot.{requested,completed,failed}`. Live fetchers
ship for calendar / hubspot / kpi / traders binance basket / news /
portfolio (NAV-enriched) / mlm downline (CSV) / arxiv / local-papers /
datasets-dir.

### Council (Phase K-C)

`backend/core/council/` runs two voices (`tars-local-rules-v1` +
`tars-mock-cloud-v1`). Modes `single | dual_vote | n_vote`. Emits
`sampler.decision` for every deliberation. Hooked into
`traders.summarize_market` and `business.daily_brief` — responses
carry a `council` block with voices, agreement, contradictions and
the chosen stance. New endpoint: `POST /api/council/deliberate`.
Drop a third concrete `Voice` for the real LLM adapter.

### Policy gate (Phase K-D)

`backend/core/policy/` gates destructive actions. `ActionSpec.destructive`
opts an action in. Modes `autopilot | confirm | dry_run`, default
`confirm` (env `TARS_POLICY_MODE`, header `x-tars-policy-mode`).
Pending tokens persist in the SQLite store. Endpoints:
`GET /api/policy/{pending,recent}`,
`POST /api/policy/{confirm,cancel}/{token}`,
`POST /api/policy/expire`.

### Playbooks (Phase K-E)

JSON files under `playbooks/<pack>/<name>.json`. Steps support
`<slug>.<action_id>` and `<slug>.awareness.<source_id>.snapshot`,
`${steps.<id>...}` / `${context.<key>}` templating, `when` clauses,
`store_as`, `on_error`, and `on_block`. Sample playbooks:
`traders.morning_check`, `business.morning_brief`,
`mlm.retention_round`. Endpoints: `GET /api/playbooks`,
`GET /api/playbooks/{id}`, `POST /api/playbooks/{id}/run`,
`POST /api/playbooks/_reload`. Override discovery root with
`TARS_PLAYBOOKS_DIR`.

Action handlers MUST:

- be `async`, accept a `Mapping[str, Any]`, return a `dict` with an `ok` boolean,
- never raise on bad user input — return `{"ok": False, "error": "..."}` instead,
- never perform live trades, sends, or destructive actions without an
  explicit confirmation flow. Tag them with `destructive=True` on the
  `ActionSpec` so the policy gate routes them through the confirmation
  queue automatically.

## meeet.world bridge (Phase 9.1 + Phase K-B)

`backend/core/meeet/` provides end-to-end logging and trace propagation. The
bridge is stdlib-only (no httpx) and is a no-op when `MEEET_INGEST_URL` is not
set, so it is safe in tests and offline envs.

- `tracing.py` — `start_trace`, `current_trace`, `trace_scope`, `new_trace_id`.
- `events.py` — `TARSEvent` (trace_id, kind, payload, source, contract_version, ts).
- `client.py` — `MeeetClient.emit(kind, payload)` (async), local jsonl fallback,
  durable buffer.
- `store.py` — SQLite WAL durable buffer at `~/.tars/meeet.sqlite`
  (override `MEEET_STORE_PATH`; disable `MEEET_STORE=disabled`). Every
  event is inserted before any network attempt; offline events stay
  `pushed=0` until `MeeetClient.replay_unpushed()` (or
  `POST /api/meeet/replay`) flushes them. `PolicyStore` shares the
  same DB.
- `config.py` — env-driven (`MEEET_INGEST_URL`, `MEEET_CONTRACT_VERSION`,
  `MEEET_API_KEY`, `MEEET_SOURCE`, `MEEET_LOCAL_LOG`). Default contract pin
  `1.0.0`.
- HTTP entry: domain router accepts `x-meeet-trace-id` header to continue a
  parent trace from meeet.world or any other surface. New trace viewer
  endpoints: `GET /api/meeet/{stats,events}` + `POST /api/meeet/replay`.

Every meaningful TARS request that crosses a service boundary must run inside
`trace_scope` and emit at least one `*.invoked` and one `*.completed` event.

## Frontend conventions

- The main `frontend/` stays dependency-free. Reuse existing CSS variables and
  animation keyframes from `frontend/jarvis-ui.css`,
  `frontend/jarvis-hud-pro.css`, `frontend/brand-meeet.css`.
- Cockpit/operator pages (`cockpit.html`, `tars.html`, `tars-dashboard.html`)
  keep their dark HUD aesthetic.
- Marketing/landing surfaces evolve toward a premium AI-product feel: cinematic
  hero, big confident type, glass cards, restrained gradients, purposeful
  motion. **Aesthetic = minimalism + futurism**, never neon/gaudy.
- Always provide empty / loading / error / success states for async UI.
- Maintain accessibility: semantic structure, visible focus, `aria-live`.

## Premium showcase (`experiments/neural-showcase-v2/`)

- Stack: Vite + Three.js + GSAP + ScrollTrigger + Lenis + postprocessing.
- WebGL: Stark / Interstellar inspired core (`src/scene/Core.js`) — reactor +
  cage + monolith slabs + two thin concentric rings — and `Galaxy.js` particle
  field with custom GLSL.
- Palette: deep ink (#04060d) + soft pastel cyan (#9ec3d4) + warm amber
  (#e6c97a) accents only. No rainbow gradients.
- Postprocessing: tame bloom + faint chromatic aberration + vignette + film
  noise + SMAA.
- DOM HUD: a single subtle panel `aside.hud` top-left.
- GLB hook: drop `public/models/brain.glb` to override the procedural reactor.
- Motion: word stagger reveal, magnetic cursor, scroll-driven camera, animated
  counter, ScrollTrigger reveals.
- Respect `prefers-reduced-motion`. Hide HUD on small screens.

## Backend conventions

- New endpoints in `web_extras/routers/`, follow existing patterns. Register
  packs / awareness sources via the existing registries; do not invent parallel
  ones.
- Don't change response shapes silently — but additive keys (e.g. `trace_id`,
  `took_ms`) are fine.
- Long-running work: `backend/core/background` and observability hooks.

## Engineering guardrails

- Keep changes scoped to the requested surface.
- Don't add npm tooling or heavy frontend frameworks for one-off polish; only
  `experiments/neural-showcase-v2/` owns its own `node_modules`.
- Don't commit `.env`.
- Flag any change that crosses frontend/backend.
- For "make it innovative" requests: produce a plan (sections, motion, states)
  before large refactors.

## Design system & skill

- **Source of truth** for visual decisions: `design-system/tars/MASTER.md`.
  Page-specific overrides live under `design-system/tars/pages/`.
- **Skill** `nextlevelbuilder/ui-ux-pro-max-skill` (v2.5+) is installed in
  the canonical locations for every AI assistant on this machine:
  - `~/.cursor/skills-cursor/ui-ux-pro-max/` — **Cursor agent global**
    (registered in `~/.cursor/skills-cursor/.sync-manifest.json`). This
    is what makes the skill appear in the agent's system prompt under
    `<available_skills>`.
  - `.cursor/skills/ui-ux-pro-max/` — Cursor (this project, fallback).
  - `~/.claude/skills/ui-ux-pro-max/` — **Claude Code global**.
  - `.claude/skills/ui-ux-pro-max/` — Claude Code (this project,
    project-pinned data + scripts).
  Auto-activates on UI/UX requests (build, design, create, implement,
  fix, improve).
- **Workflow** when touching any UI surface:
  1. Read `design-system/tars/MASTER.md`.
  2. Check `design-system/tars/pages/<slug>.md` for the page being built.
  3. If unsure, run a targeted skill query, e.g.
     `python3 .cursor/skills/ui-ux-pro-max/scripts/search.py "<keywords>"
     --domain style|landing|typography|ux|color`.
  4. Synthesize, then implement. Never reach for AI-purple/pink rainbow
     gradients — banking AI anti-pattern carried over.
- **Aesthetic baseline** (per MASTER): HUD/Sci-Fi FUI + Exaggerated
  Minimalism + Dark Mode (OLED) + AI-Native UI. One cyan accent
  (`#67E8F9`). Amber (`#FBBF24`) is reserved for live/alert telemetry.

## Tooling installed

- **Claude Code** v2.1.121 (`npm i -g @anthropic-ai/claude-code`). Reads
  this `CLAUDE.md` automatically when launched from the project root.
- **uipro-cli** v2.2.3 (`npm i -g uipro-cli`). Use to reinstall or update
  the skill: `uipro init --ai cursor --force` or `--ai claude --force`.
- **Local transcription**: `imageio-ffmpeg` + `faster-whisper` in
  `.venv/`. Helper: `python /tmp/tars-transcribe/run.py <wav> small`.
  See `docs/VIDEO_TRANSCRIPTS.md` for usage and existing transcripts.

## 21st.dev workflow

The 4-step recipe from the design instruction video
(`docs/VIDEO_TRANSCRIPTS.md`) lives entirely inside
`experiments/neural-showcase-v3/`. To drop a new block:

```bash
cd experiments/neural-showcase-v3
npx shadcn@latest add "https://21st.dev/r/<author>/<id>"
```

The component lands in `src/components/ui/<name>.tsx` and inherits TARS
tokens (cyan accent, deep-ink BG) via the shadcn CSS variables defined
in `src/index.css`.

## Sync with the agent transcript

Every meaningful agent edit is logged in `docs/CHANGELOG_AGENTS.md` with a
short note and file paths. The current open work and conventions live in
`docs/AGENT_HANDOFF.md`. New ideas / proposals live in `docs/IDEAS.md`. Read
all four (including `design-system/tars/MASTER.md`) when picking up a new
chat.
