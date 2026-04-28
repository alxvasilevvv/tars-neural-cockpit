# Agent changelog

Per-batch log of edits made by autonomous agents. Read top-down; latest entry
first. Every entry: who, when, summary, files. Keep entries short and
factual; prose belongs in `AGENT_HANDOFF.md`.

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
