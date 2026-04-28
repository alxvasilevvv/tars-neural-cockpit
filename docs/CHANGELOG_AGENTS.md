# Agent changelog

Per-batch log of edits made by autonomous agents. Read top-down; latest entry
first. Every entry: who, when, summary, files. Keep entries short and
factual; prose belongs in `AGENT_HANDOFF.md`.

## 2026-04-29 — Cursor agent · adapters + per-pack auth + code-split

**Summary**

Per-pack ``auth`` keys on ``GET /api/domains/<slug>``; RSS-aware
``traders.news_feed`` when ``TRADERS_NEWS_RSS_URL`` set; OpenAlex
enrichment on ``science.summarize_paper`` for new-style arXiv ids;
HubSpot/Pipedrive pushes on ``business.log_deal`` when keys exist;
``mlm.recruitment_round`` playbook; frontend lazy routes + chunk
splitting + ``sampler.decision`` poll in OperatorStrip. **122 pytest.**

## 2026-04-28 — Cursor agent · Phase F-J (LLM voice → cockpit hooks)

**Summary**

Five more sub-phases shipped on top of Phase K. Each its own commit;
117 pytest tests passing.

- **Phase F — Real LLM voice + Keychain vault.**
  `backend/core/vault/` (env > Keychain > missing). Six known keys:
  `TARS_ANTHROPIC_API_KEY`, `TARS_OPENAI_API_KEY`, `MEEET_API_KEY`,
  `HUBSPOT_API_KEY`, `PIPEDRIVE_API_KEY`, `OPENALEX_EMAIL`.
  `backend/core/council/llm.py` — `AnthropicVoice` (default
  claude-3-5-sonnet) and `OpenAIVoice` (gpt-4o-mini); stdlib HTTP via
  `urllib`. Provider failures collapse to `stance='unavailable'`
  proposals; the orchestrator filters them out of the vote and the
  agreement count. Default panel grows to 3 voices when a key is
  configured. New endpoint `GET /api/vault/status` (sources only —
  values never echoed). 8 new tests.
  Files: `backend/core/vault/{__init__,keychain}.py`,
  `backend/core/council/{llm,__init__,orchestrator}.py`,
  `web_extras/{app,routers/vault}.py`,
  `tests/test_vault_and_llm_voice.py`.

- **Phase G — Parallel playbook steps.** `PlaybookStep.parallel`
  flag groups consecutive parallel-flagged steps; runner executes
  the batch via `asyncio.gather`. Step results are emitted in the
  declared order regardless of completion order. `traders.morning_check`
  runs `news` + `portfolio` concurrently (≈ 50 % wall-clock saving).
  5 new tests. Files:
  `backend/core/playbooks/{loader,runner}.py`,
  `playbooks/traders/morning_check.json`, `tests/test_playbooks.py`.

- **Phase H — SQLite MLM downline DB.**
  `backend/core/domains/packs/mlm/db.py` — `DownlineDB` class with
  WAL SQLite at `~/.tars/downline.sqlite` (override `MLM_DB_PATH`).
  `ensure_seeded()` is idempotent: imports `data/mlm_network.csv`
  on first read; later calls are no-ops. Two new destructive
  actions: `mlm.add_member` (validates sponsor exists) and
  `mlm.log_activity` (timestamps + volume delta). Both gated by the
  policy queue. `_parse_date` extended to accept full ISO timestamps
  with microseconds and offsets. 14 new tests. Files:
  `backend/core/domains/packs/mlm/{db,actions,awareness}.py`,
  `tests/test_mlm_db.py`, `tests/test_policy.py`.

- **Phase I — Background replay loop + meeet health.**
  `web_extras/app.py` lifespan starts a periodic task that calls
  `MeeetClient.replay_unpushed()` every `MEEET_REPLAY_INTERVAL_S`
  (default 60s, `0` disables). `MeeetClient.last_replay` caches
  `{enabled, pushed, failed, scanned, remaining, ran_at}`. New
  endpoint `GET /api/meeet/health` returns client config + store
  stats + last_replay. 5 new tests. Files:
  `backend/core/meeet/client.py`, `web_extras/app.py`,
  `web_extras/routers/meeet.py`,
  `tests/test_meeet_health_and_replay_loop.py`.

- **Phase J — Cockpit clients + OperatorStrip.** Five new typed
  modules under `experiments/neural-showcase-v3/src/lib/`:
  `policy.ts`, `council.ts`, `playbooks.ts`, `meeet.ts`, `vault.ts`
  (each exposes a fetch client + a React hook). `lib/api.ts`:
  `invokeAction` accepts `{mode, traceId}` and forwards
  `x-tars-policy-mode` / `x-meeet-trace-id` headers; new
  `snapshotAwareness` helper; `PolicyMode` type exported.
  `<OperatorStrip />` mounted on `/cockpit` — 3 columns: pending
  confirmations (with confirm/cancel inline), playbook runner with
  policy mode selector and step results, bridge panel (meeet store +
  last replay + vault sources + on-demand council deliberation).
  Type-check + production build clean. Files:
  `experiments/neural-showcase-v3/src/{lib/api,lib/policy,lib/council,lib/playbooks,lib/meeet,lib/vault,components/OperatorStrip,pages/Cockpit}.ts(x)`.

**Bookkeeping**

- Tests: **117 passing** (up from 79). New suites:
  `test_vault_and_llm_voice` (8), `test_mlm_db` (14),
  `test_meeet_health_and_replay_loop` (5). Existing suites grew
  with `test_playbooks` parallel cases and `test_policy` updated
  for the two new mlm destructive flags.
- Commits: `f099802 → 03b1eb3 → f18bde1 → e273b86 → 0bbe108`
  (Phase F → G → H → I → J).
- Docs: `AGENT_HANDOFF.md` updated; this changelog refreshed;
  `IDEAS.md` to be re-checked next.

## 2026-04-28 — Cursor agent · Tier-1 functional roadmap (Phase K)

**Summary**

Five sub-phases shipped in one push, each its own commit. End state:
council deliberates, policy gate fires, durable buffer survives
restarts, awareness sources actually return data, playbooks run.

- **Phase A — Awareness wiring.** `AwarenessSource` gained an optional
  async `fetcher` field. New endpoint `GET /api/domains/<slug>/awareness/<id>/snapshot`
  runs the fetcher inside a meeet trace scope and emits
  `awareness.snapshot.{requested,completed,failed}`. Live fetchers
  for calendar (`data/calendar_events.json`), HubSpot deals,
  KPI sheet, traders binance basket (DexScreener poll), traders
  news_feed, traders portfolio (NAV-enriched via live quotes), MLM
  downline (CSV fallback), arXiv (cat:<...> via `search_literature`),
  local-papers and datasets-dir. Path resolver: env > arg path
  if exists > default. `business.daily_brief` integrates calendar
  awareness and surfaces `calendar_today[]`.
- **Phase B — SQLite durable event log.** New `backend/core/meeet/store.py`
  with WAL DB at `~/.tars/meeet.sqlite` (override via
  `MEEET_STORE_PATH`, disable via `MEEET_STORE=disabled`). Schema:
  `events(id, ts, trace_id, kind, source, contract_version, payload,
  pushed, pushed_at, last_error)` + three indices.
  `MeeetClient.emit` writes to the store before any network attempt;
  `MeeetClient.replay_unpushed` flushes pending events on reconnect.
  New endpoints: `GET /api/meeet/stats`, `GET /api/meeet/events`
  (filters: `limit`, `since`, `trace_id`, `kind`, `only_unpushed`),
  `POST /api/meeet/replay`.
- **Phase C — Council orchestrator.** `backend/core/council/`:
  `Voice` ABC + `Proposal` dataclass + two real voices
  (`tars-local-rules-v1`, `tars-mock-cloud-v1`). Modes
  `single | dual_vote | n_vote` with confidence-weighted majority
  arbitration. Emits `council.deliberation.{started,completed}` and
  `sampler.decision` (id, mode, models, winner, winning_stance,
  latency_ms, tokens_in/out, agreement, contradictions). Wired into
  `traders.summarize_market` and `business.daily_brief`. New
  endpoint: `POST /api/council/deliberate`.
- **Phase D — Policy gate.** `ActionSpec.destructive` flag.
  Destructive actions (`traders.place_alert`, `business.draft_email`,
  `business.log_deal`, `mlm.generate_post`) flow through
  `backend/core/policy/gate.py`. Modes: `autopilot | confirm | dry_run`,
  default `confirm`. Confirmations persist in the same SQLite DB
  (`PolicyStore`); resolve is idempotent; expiration baked in
  (default 5 min TTL). New endpoints: `GET /api/policy/{pending,recent}`,
  `POST /api/policy/{confirm,cancel}/{token}`, `POST /api/policy/expire`.
  Header `x-tars-policy-mode` switches mode per request. Emits
  `policy.{queued,allowed,blocked,confirm,cancelled}`.
- **Phase E — Playbook runner.** `backend/core/playbooks/` with
  loader + runner + JSON files under `playbooks/<pack>/<name>.json`.
  Steps support `<slug>.<action_id>` and
  `<slug>.awareness.<source_id>.snapshot`, arg templating
  (`${steps.<id>.<json.path>}` and `${context.<key>}`, single-token
  references survive native types), `when` clauses, `store_as`,
  `on_error`. Sample playbooks shipped:
  `traders.morning_check`, `business.morning_brief`, `mlm.retention_round`.
  New endpoints: `GET /api/playbooks`, `GET /api/playbooks/{id}`,
  `POST /api/playbooks/{id}/run`, `POST /api/playbooks/_reload`.

**End-to-end smoke**

- `business.daily_brief` returns council-arbitrated "EXPANDING — MRR up 4.6%."
  with `calendar_today` populated.
- `traders.summarize_market` BTC/ETH/SOL/ARB on 2026-04-28: council
  splits — local says neutral/hold, mock-cloud says risk_off/tighten_stops,
  arbiter picks neutral on confidence; full disagreement is logged.
- `traders.morning_check` playbook: market + news + portfolio
  (NAV $146,425) all green in <500 ms.
- `mlm.retention_round` playbook in confirm mode: 2 read-only steps run,
  destructive `generate_post` step blocks with `cfm_*` token; confirming
  via `/api/policy/confirm/<token>` flushes the post.
- Event trail across one demo run: 11 unique kinds in
  `/api/meeet/events`, all trace-correlated, all persisted.

**Tests**: 79 passing total (was 34 in the previous batch). New suites:
`tests/test_awareness_fetchers.py`, `tests/test_meeet_store.py`,
`tests/test_council.py`, `tests/test_policy.py`,
`tests/test_playbooks.py`.

**Files**

- `backend/core/domains/base.py` — `AwarenessSource.fetcher`,
  `ActionSpec.destructive`, `DomainPack.find_awareness`,
  `to_dict` extends with `live` and `destructive` flags.
- `backend/core/domains/packs/{business,traders,mlm,science}/awareness.py`
  — fetchers added.
- `backend/core/domains/packs/business/actions.py` — calendar
  integration in `daily_brief`, council hook.
- `backend/core/domains/packs/traders/actions.py` — council hook in
  `summarize_market`, `destructive=True` on `place_alert`.
- `backend/core/domains/packs/mlm/actions.py` — `destructive=True`
  on `generate_post`.
- `backend/core/meeet/{store,client,__init__}.py` — durable buffer.
- `backend/core/council/{__init__,voices,orchestrator}.py` — new package.
- `backend/core/policy/{__init__,gate,store}.py` — new package.
- `backend/core/playbooks/{__init__,loader,runner}.py` — new package.
- `web_extras/app.py` — registers four new routers + extends CORS
  allow-headers.
- `web_extras/routers/{domains,meeet,council,policy,playbooks}.py`
  — new endpoints + policy-aware action invoke pipeline.
- `data/{calendar_events,traders_news,traders_portfolio}.json`
  — sample data files.
- `playbooks/{traders/morning_check,business/morning_brief,mlm/retention_round}.json`
  — sample playbooks.
- `tests/{test_awareness_fetchers,test_meeet_store,test_council,test_policy,test_playbooks}.py`
  — 5 new suites; `tests/test_meeet.py` updated to use an explicit tmp store.

**Commits** (from oldest to newest):

- `5c8bdd5` feat(awareness): live fetchers + GET /api/domains/<slug>/awareness/<id>/snapshot
- `b68ad4a` feat(meeet): SQLite durable buffer + replay + /api/meeet/{stats,events,replay}
- `5bafd0c` feat(council): two-voice orchestrator + sampler.decision events + action wiring
- `5540bb4` feat(policy): destructive-action gate (dry_run | confirm | autopilot)
- `df120cb` feat(playbooks): JSON-defined multi-step action chains + runner + /api/playbooks

## 2026-04-28 — Cursor agent · real adapters + SSE awareness + cockpit live wiring

**Summary**

- Replaced the four heaviest stubs with real, deterministic adapters:
  - `business.kpi_snapshot` reads `data/business_kpi.json` (path
    overridable via `BUSINESS_KPI_PATH` or per-call `path` arg) and
    returns `metrics`, ranked `summary`, `as_of`, `sources`.
  - `business.daily_brief` composes a deterministic operator brief
    from KPI + `data/business_deals.json`: deltas, top next-step
    actions, headline summary. Council can drop in without changing
    the surface contract.
  - `mlm.downline_snapshot` reads `data/mlm_network.csv`, walks
    sponsor → handle ancestry, computes `total/active/dormant/ranks/
    by_depth/volume_usd`, returns flat `members[]`.
  - `mlm.retention_alert` filters by configurable `threshold_days`.
  - `mlm.score_recruit`, `mlm.generate_post` upgraded to deterministic
    heuristics with model labels + hints (still stubs but useful).
  - `science.summarize_paper` accepts arxiv id / `arxiv:<id>` / full
    URL via `_normalize_arxiv_ref`, fetches the Atom entry, returns
    title/authors/published/primary_category/categories/tldr (first
    two sentences)/abstract.
  - `traders.summarize_market` aggregates a basket of tickers via
    `fetch_quote`, computes `avg_change_24h`, surfaces `bias`
    (risk-on/off/neutral/uncertain), `top_gainers`, `top_losers`,
    and a dispersion `contradictions[]`. Sample run BTC/ETH/SOL/ARB
    on 2026-04-28: RISK-OFF, basket -1.55%/24h.
  - `traders.fetch_quote` picker upgraded to prefer the highest-liquidity
    pair *with* `priceChange.h24` populated; falls back otherwise.
- New SSE endpoint `GET /api/awareness/stream` in
  `web_extras/routers/awareness.py` emits `hello`, `system.pulse`,
  `domain.heartbeat`, `bye` frames. Tunable via env
  `AWARENESS_PULSE_S`, `AWARENESS_TICK_LIMIT`. Trace-scoped.
- Frontend Cockpit gains `<AwarenessTicker/>` (`src/components/
  AwarenessTicker.tsx`) — connects via EventSource, animates CPU/RAM
  bars, lists last 6 domain heartbeats, shows trace_id and live
  status pill. SSE client at `src/lib/awareness.ts`.
- Tests: `tests/test_real_adapters.py` (KPI, daily brief, downline
  snapshot, retention alert, score recruit, arxiv ref normaliser),
  `tests/test_awareness_stream.py` (hello + N pulses + bye, bounded
  cpu/ram). Full suite: 34 passing.
- Smoke verified end-to-end against `:9911`:
  - `business.daily_brief` → "MRR_USD is up 4.6% — focus on Pelagic
    Energy.", 4 next steps.
  - `mlm.downline_snapshot` → 15 members, 11 active, $47,200 volume,
    ranks `{starter:10, silver:2, bronze:2, gold:1}`.
  - `mlm.retention_alert(40)` → @sasha (134d), @rin (103d), @iris (79d).
  - `science.summarize_paper(2305.13245)` → "GQA: Training
    Generalized Multi-Query Transformer Models from Multi-Head
    Checkpoints" with two-sentence tldr.
  - `traders.summarize_market` → BTC $76k, ETH $2.26k, RISK-OFF.
  - SSE first frame: `hello{trace_id, domains: [business, mlm,
    science, traders], interval_s: 1.2}`.

**Files**

- `backend/core/domains/packs/business/actions.py` — full rewrite.
- `backend/core/domains/packs/mlm/actions.py` — full rewrite.
- `backend/core/domains/packs/science/actions.py` — `summarize_paper`
  + `_normalize_arxiv_ref`.
- `backend/core/domains/packs/traders/actions.py` — real
  `summarize_market`, `fetch_quote` picker upgrade.
- `web_extras/routers/awareness.py` — new SSE router.
- `web_extras/app.py` — mount awareness router.
- `data/business_kpi.json`, `data/business_deals.json`,
  `data/mlm_network.csv` — sample data.
- `experiments/neural-showcase-v3/src/lib/awareness.ts`,
  `experiments/neural-showcase-v3/src/components/AwarenessTicker.tsx`,
  `experiments/neural-showcase-v3/src/pages/Cockpit.tsx` — frontend
  consumer.
- `tests/test_real_adapters.py`, `tests/test_awareness_stream.py`
  — new suites.
- `docs/AGENT_HANDOFF.md`, `docs/IDEAS.md` — sync.

## 2026-04-28 — Cursor agent · transcript + showcase v3 (React) + Claude Code

**Summary**

- Transcribed `433d7195d4f34e84b8a52cfe28924a62.MP4` (40s, RU) locally with
  `faster-whisper small` over `imageio-ffmpeg`. Saved to
  `docs/VIDEO_TRANSCRIPTS.md`. The video specifies a 4-step recipe:
  1. Install Claude Code.
  2. Install Framer Motion.
  3. Install ui-ux-pro-max-skill.
  4. Drop a 21st.dev component into the codebase.
- Step 1: `npm i -g @anthropic-ai/claude-code` (v2.1.121 installed).
- Step 2 + 3 + 4: bootstrapped a new React project at
  `experiments/neural-showcase-v3/` with React 18 + TypeScript + Vite +
  Tailwind v4 (`@tailwindcss/vite`) + framer-motion + lucide-react +
  shadcn-style `components.json`. Path alias `@/*`, `cn()` helper at
  `src/lib/utils.ts`, design tokens piped via Tailwind v4 `@theme` from
  `design-system/tars/MASTER.md`.
- Built every section as a framer-motion component: `Hero` (word stagger
  + spotlight gradient), `Rail` (live awareness strip with animated
  integrity counter via `useMotionValue`), `Layers`, `Domains`, `Steps`,
  `Footer`, plus decorative `Brackets` (HUD corner SVGs).
- v3 is configured so any 21st.dev block installs with a single line:
  `npx shadcn@latest add "https://21st.dev/r/<author>/<id>"` from inside
  the project. Components land in `src/components/ui/`.
- Skill installed in three locations now:
  - `Jarvis/jarvis/.cursor/skills/ui-ux-pro-max/`
  - `meeet-browser-agent/.cursor/skills/ui-ux-pro-max/`
  - `~/.claude/skills/ui-ux-pro-max/` (Claude Code, global)
- Build verified: `npm run build` clean, 277 KB JS gzipped 89 KB.
- Dev server: `http://127.0.0.1:5174/` (v2 still on 5173).

**Files**

- `experiments/neural-showcase-v3/` — full project
  - `package.json`, `vite.config.ts`, `tsconfig.{,app,node}.json`
  - `components.json` (shadcn / 21st.dev config)
  - `index.html`, `.gitignore`, `README.md`
  - `src/{main,App,index.css}.{tsx,css}`
  - `src/lib/utils.ts`
  - `src/components/{Brackets,Nav,Hero,Rail,SectionHead,Layers,Domains,Steps,Footer}.tsx`
- `docs/VIDEO_TRANSCRIPTS.md`
- `docs/AGENT_HANDOFF.md` (where-things-live updated)
- `~/.claude/skills/ui-ux-pro-max/` (Claude Code global skill)
- Global: `npm i -g @anthropic-ai/claude-code` (Claude Code 2.1.121)

## 2026-04-28 — Cursor agent · ui-ux-pro-max skill + showcase v3

**Summary**

- Installed `nextlevelbuilder/ui-ux-pro-max-skill` v2.5 via `uipro-cli`
  in two locations: `Jarvis/jarvis/.cursor/skills/ui-ux-pro-max/` (TARS
  project) and `meeet-browser-agent/.cursor/skills/ui-ux-pro-max/`
  (active Cursor workspace). Skill auto-activates on UI/UX requests.
- Used the skill workflow strictly per its `SKILL.md`: domain searches in
  `style`, `landing`, `typography`, `ux`, plus stack guidelines for
  `html-tailwind`. Synthesized a custom design system because the
  engine's auto-pick (`--design-system`) matched the wrong product
  category. Persisted as `design-system/tars/MASTER.md` (the engine's
  initial output was overwritten with the manual synthesis).
- Aesthetic blend chosen by skill data: **HUD / Sci-Fi FUI** (1px lines,
  decorative corner brackets, mono labels, sparing accent glow) +
  **Exaggerated Minimalism** (massive typography, single accent,
  whitespace) + **Dark Mode (OLED)** (deep ink BG, no white BG) +
  **AI-Native UI** (context-card border-left accents).
- Single accent: cyan `#67E8F9`. Single functional alert: amber
  `#FBBF24` (only LIVE dot + integrity ticker).
- Rewrote `experiments/neural-showcase-v2/index.html` from scratch:
  decorative SVG corner brackets, hero with split title and one accent
  word, live awareness rail (HUD strip with streams + integrity +
  latency), monolithic card grids with hairline borders, footer with a
  big "Open cockpit" deep-link.
- Rewrote `src/style.css` from scratch under the MASTER tokens. Z-index
  scale 10/20/30/40/50 (no `9999`). All transitions 150–220ms.
  `prefers-reduced-motion` blanket override at the bottom kills all
  animations in 0.001ms.
- Tightened WebGL composer to MASTER (bloom intensity 0.55 → 0.38,
  threshold 0.78 → 0.92, kernel SMALL, no mipmap blur). 3D scene is now
  a background sculpture, not the focus.
- Synced `CLAUDE.md`, `.cursorrules`, `.cursor/rules/tars-architecture.mdc`
  with skill location and workflow rules so Claude and future agents
  always reach for the skill before touching UI.

**Files**

- `experiments/neural-showcase-v2/index.html` (full rewrite)
- `experiments/neural-showcase-v2/src/style.css` (full rewrite)
- `experiments/neural-showcase-v2/src/scene/Composer.js` (bloom tighten)
- `design-system/tars/MASTER.md` (manual synthesis from skill data)
- `design-system/tars/pages/` (created)
- `.cursor/skills/ui-ux-pro-max/` (installed via uipro init)
- `CLAUDE.md`, `.cursorrules`, `.cursor/rules/tars-architecture.mdc`

## 2026-04-28 — Cursor agent · Phase 9 polish + meeet bridge

**Summary**

- Tone-down pass on `experiments/neural-showcase-v2/` toward minimalism +
  futurism: bloom intensity 1.4 → 0.55, luminance threshold 0.18 → 0.78,
  no mipmap blur. Galaxy reduced from 14k to 8k particles; smaller sizes;
  pastel palette (cyan #9ec3d4 + amber #e6c97a + grayscale only). Reactor
  base color shifted to deep blue #1a3550, halo removed, two thin rings
  instead of four. DOM HUD reduced from four corner panels to a single
  subtle top-left panel. Hero typography stripped of rainbow gradient,
  buttons recoloured to monochrome with a single accent fill.
- Added meeet.world bridge: `backend/core/meeet/` with trace context
  (`start_trace`, `current_trace`, `trace_scope`), event types
  (`TARSEvent`), and a stdlib-only HTTP client (`MeeetClient.emit`).
  No-op when `MEEET_INGEST_URL` is unset; optional jsonl fallback via
  `MEEET_LOCAL_LOG`. Contract version pin defaults to `1.0.0`.
- Wired the bridge into `web_extras/routers/domains.py`: action invocations
  run inside `trace_scope` (continuing an upstream `x-meeet-trace-id` header
  if present) and emit `domain.action.invoked|completed|failed`. Response
  now carries `trace_id` and `took_ms`.
- Replaced "Jarvis" with "TARS" in user-visible copy and AI rules
  (`CLAUDE.md`, `.cursorrules`, `.cursor/rules/tars-architecture.mdc`,
  showcase index, lead text). Folder name `Jarvis/jarvis` left untouched
  for path stability.
- Added `tests/test_meeet.py` (8 tests, all green). Total suite: 17/17.

**Files**

- `experiments/neural-showcase-v2/index.html` (HUD trim, copy update)
- `experiments/neural-showcase-v2/src/style.css` (palette + layout pass)
- `experiments/neural-showcase-v2/src/main.js` (camera 9.5, dpr cap, fog)
- `experiments/neural-showcase-v2/src/scene/{Composer,Galaxy,Core}.js`
- `experiments/neural-showcase-v2/src/scene/shaders/{galaxy,core}.glsl.js`
- `backend/core/meeet/{__init__,config,tracing,events,client}.py`
- `web_extras/routers/domains.py`
- `tests/test_meeet.py`
- `CLAUDE.md`, `.cursorrules`, `.cursor/rules/tars-architecture.mdc`
- `docs/AGENT_HANDOFF.md`, `docs/IDEAS.md`

## 2026-04-28 — Cursor agent · Phase 9 kickoff

**Summary**

- Bootstrapped premium marketing surface in `experiments/neural-showcase-v2/`
  with Vite + Three.js + GSAP + Lenis + postprocessing. Iron-Man / Interstellar
  inspired core (procedural reactor + monolith slabs + concentric rings) with
  custom GLSL shaders, HDR room environment, ACES tone mapping, scroll-driven
  camera, magnetic cursor, animated loader, Stark-style DOM HUD overlays in
  four corners. Optional GLB override hook.
- Added domain packs plugin system in `backend/core/domains/` with
  `traders`, `business`, `mlm`, `science` built-ins, async action handlers,
  awareness sources, system prompts, manifests.
- Added FastAPI router at `web_extras/routers/domains.py` mounting at
  `/api/domains`.
- Added pytest suite `tests/test_domains.py` (9 tests, all green).
- Synced AI context across `CLAUDE.md`, `.cursorrules`,
  `.cursor/rules/tars-architecture.mdc`. Added `docs/AGENT_HANDOFF.md` and
  `docs/DOMAIN_PACKS.md`.

**Files**

- `experiments/neural-showcase-v2/` — full project
  - `package.json`, `vite.config.js`, `index.html`, `README.md`, `.gitignore`
  - `src/main.js`, `src/style.css`
  - `src/scene/{Galaxy,Core,Composer}.js`
  - `src/scene/shaders/{lib,galaxy,core}.glsl.js`
  - `src/ui/{Cursor,Loader,HUD,Reveal}.js`
- `backend/core/domains/{__init__,base,registry}.py`
- `backend/core/domains/packs/__init__.py`
- `backend/core/domains/packs/{traders,business,mlm,science}/{__init__,pack,actions,awareness,prompts}.py`
- `backend/core/domains/packs/{traders,business,mlm,science}/manifest.json`
- `web_extras/routers/{__init__,domains}.py`
- `tests/{__init__,test_domains}.py`
- `CLAUDE.md`, `.cursorrules`, `.cursor/rules/tars-architecture.mdc`
- `docs/AGENT_HANDOFF.md`, `docs/DOMAIN_PACKS.md`, `docs/CHANGELOG_AGENTS.md`
