# Agent handoff — TARS

Pick this up if you are continuing the work in a fresh chat. Read this file
plus `docs/CHANGELOG_AGENTS.md` and `docs/IDEAS.md` first.

> Naming: product = **TARS**. Older copy may say "Jarvis" — replace in copy
> when editing. Folder name `Jarvis/jarvis` stays for path stability.

## Mental model

TARS is a local-first Neural Cockpit. Frontend and backend are loosely coupled
— `frontend/` is vanilla HTML/CSS/JS, backend is Python FastAPI-style.

The premium marketing surface is the standalone Vite project under
`experiments/neural-showcase-v2/`. Do not let its deps leak into `frontend/`.

The Phase-9 product expansion is **domain packs**: a plugin system that
specialises the neural core for specific audiences (traders, business, MLM,
science).

The Phase-9.1 expansion is the **meeet.world bridge**: every cross-boundary
action runs inside a `trace_scope` and emits events to the meeet ingest, with
a stable contract version pinned at `1.0.0`.

## Where things live

- **Design system source of truth:** `design-system/tars/MASTER.md` (per
  `ui-ux-pro-max-skill`).
- **Skill (UI/UX):** `.cursor/skills/ui-ux-pro-max/` (Cursor),
  `~/.claude/skills/ui-ux-pro-max/` (Claude Code, global).
- **Domain pack core:** `backend/core/domains/{base,registry,__init__}.py`
- **Domain pack implementations:**
  `backend/core/domains/packs/{traders,business,mlm,science}/`
  Each pack has `pack.py`, `actions.py`, `awareness.py`, `prompts.py`,
  `manifest.json`.
- **Domain HTTP router:** `web_extras/routers/domains.py`
- **meeet bridge:** `backend/core/meeet/{config,tracing,events,client,__init__}.py`
- **Tests:** `tests/test_domains.py`, `tests/test_meeet.py`
- **Specs:** `docs/DOMAIN_PACKS.md`, `docs/VIDEO_TRANSCRIPTS.md`.
- **Showcase v2 — vanilla:** `experiments/neural-showcase-v2/` (Three.js +
  GSAP + Lenis + postprocessing + custom GLSL).
- **Showcase v3 — React:** `experiments/neural-showcase-v3/` (React +
  Tailwind v4 + framer-motion + 21st.dev / shadcn-ready). This is the
  surface where new motion / 21st.dev components land first.
- **Project context for AI:** `CLAUDE.md`, `.cursorrules`,
  `.cursor/rules/tars-architecture.mdc` — keep these three in sync.

## Done

- Phase A — Iron-Man / Interstellar core in showcase v2:
  - Replaced the icosahedron brain with a procedural reactor + monolith slabs +
    two concentric rings + cage. Custom GLSL with simplex noise displacement,
    fresnel emissive, ring scanner, ring notches.
  - HDR environment via `RoomEnvironment` + PMREMGenerator; ACES tone mapping.
  - GLB override at `public/models/brain.glb` (procedural is the default).
  - Single subtle DOM HUD panel top-left (replaced the four-corner Stark grid).
- Phase B — domain packs scaffold:
  - `DomainPack` base + registry; 4 built-ins; HTTP router; pytest suite.
- Phase C — sync infra:
  - This handoff, the changelog, the spec, and the unified AI rules.
- Phase D — design tone-down (minimalism + futurism):
  - Calmer bloom (intensity 0.55, threshold 0.78). Pastel palette: deep ink
    + cyan #9ec3d4 + amber #e6c97a only. Particle count and size reduced.
    Hero gradient removed. HUD reduced from four panels to one.
- Phase E — meeet.world bridge:
  - `backend/core/meeet/` (stdlib-only). Trace scope + event emitter + local
    jsonl fallback. Domain router accepts `x-meeet-trace-id` header and emits
    `domain.action.invoked|completed|failed` for every call.
- Phase F — Jarvis → TARS rename in user-visible copy and rules; folder paths
  preserved.

## Pending / next moves

1. **Wire the domains router into the host app.** When the FastAPI app is
   restored, add `app.include_router(domains.router)` and import
   `backend.core.domains.packs` once at startup so the registry populates.
   Mount the meeet bridge as middleware so non-domain endpoints also pick up
   `x-meeet-trace-id`.
2. **Replace stub action handlers** with real adapters as integrations land
   (binance, hubspot, telegram bot, arxiv, etc.). Keep handler return shape
   stable.
3. **Frontend domain switcher**: a UI in the cockpit that reads
   `GET /api/domains`, lets the user choose a pack, and pipes the system
   prompt + action catalogue to the council.
4. **GLB asset.** Source a CC0 brain or stylised core mesh and drop into
   `experiments/neural-showcase-v2/public/models/brain.glb`. Procedural stays
   as the offline-safe fallback.
5. **Sound design pass for showcase v2** (optional): ambient hum + UI clicks
   via WebAudio. Respect `prefers-reduced-motion` and a UI mute toggle.
6. **Page transitions** between marketing surfaces: shared overlay, route-aware
   ScrollTrigger reset.
7. **meeet contract evolution**: align event kinds with the meeet.world ingest
   contract once it lands. Keep the `contract_version` pin updated.

## Conventions to keep

- Aesthetic = minimalism + futurism. No rainbow gradients, no neon flooding.
  Two accent colours max (cyan + amber).
- Action handlers: `async`, return a dict with `ok`, never raise on bad user
  input, never auto-execute destructive ops.
- Every cross-boundary call must run inside `trace_scope` and emit at least
  `*.invoked` and `*.completed` events.
- Manifests: slug is kebab-case-or-lower; color is hex; capabilities are
  short snake_case strings.
- Don't bleed `experiments/neural-showcase-v2/` deps into the canonical
  `frontend/`.
- Update `docs/CHANGELOG_AGENTS.md` after every meaningful edit batch.
