# Agent changelog

Per-batch log of edits made by autonomous agents. Read top-down; latest entry
first. Every entry: who, when, summary, files. Keep entries short and
factual; prose belongs in `AGENT_HANDOFF.md`.

## 2026-04-29 — Claude · Wave 47: pre-launch handoff verified, all gates green

**Summary**

Verified Cursor closed all 5 handoff TODOs from Wave 46 promt. Backend
`to_dict()` + manifest both expose `deprecated` flag — frontend
`KNOWN_DEPRECATED_SLUGS` defensive set already removed by Cursor in same
batch. `.env.production` sets `VITE_TARS_API=https://tars.meeet.world`.
CORS middleware accepts the prod origin (+ `TARS_CORS_ORIGINS` env override).
All 7 pairing routes shipped. Bonus: `audit:lighthouse` / `audit:axe` npm
scripts ready for staging probe. `npx tsc --noEmit` clean, no further
frontend cleanup needed. Green light for `tars.meeet.world` launch.

**Files** — none modified by Claude in Wave 47 (verification-only). All
changes already landed by Cursor in the entry below.

## 2026-04-29 — Cursor · Wave 46 gate: deprecated on wire, prod Vite env, CORS, pairing doc

**Summary**

Pre-launch **`tars.meeet.world`** gate: `DomainPack.to_dict()` and
`GET /api/domains/manifest` now expose ``deprecated`` /
``deprecated_in_favor_of``. Showcase `listDomains` / ``getDomainManifest`` filter
without `KNOWN_DEPRECATED_SLUGS`. ``.env.production`` sets
``VITE_TARS_API=https://tars.meeet.world``. CORS allows
``https://tars.meeet.world`` (+ ``TARS_CORS_ORIGINS``). Pairing router docstring
lists ``GET /identity``. Tests: manifest + list JSON, CORS OPTIONS.

**Files**

- ``backend/core/domains/base.py``, ``web_extras/routers/domains.py``,
  ``web_extras/app.py``, ``web_extras/routers/pairing.py``
- ``experiments/neural-showcase-v3/src/lib/api.ts``,
  ``experiments/neural-showcase-v3/.env.production``, ``.gitignore``,
  ``experiments/neural-showcase-v3/package.json`` (``audit:lighthouse`` /
  ``audit:axe``), ``.env.example`` (VITE base URL fix: no ``/api`` suffix)
- ``tests/test_domains.py``, ``tests/test_usage_router_and_manifest.py``,
  ``tests/test_cors_middleware.py`` (new)

## 2026-04-29 — Cursor · Docs: второй компьютер + шаблоны `.env` (миграция GitHub / meeet.world)

**Summary**

Подготовлен переносимый пакет для Claude Code на другой машине: чеклист
`docs/SECOND_MACHINE_HANDOFF.md`, корневой `.env.example`, пример переменных
для Showcase (`experiments/neural-showcase-v3/.env.example`), поправлен
`.gitignore` (`!**/.env.example`). `docs/AGENT_HANDOFF.md` — ссылка на новый документ.

## 2026-04-29 — Cursor · Showcase: GitHub Pages deploy + SPA subpath (`VITE_BASE_PATH`)

**Summary**

Automated deployment of `experiments/neural-showcase-v3` as a GitHub Actions
artifact to Pages, with correct asset paths and router `basename` for project
sites at `/<repo>/`. Added optional local tunnel script for ephemeral public
URLs when `cloudflared` is installed.

**Delivered**

- `.github/workflows/cockpit-github-pages.yml` — build, copy `dist/404.html`
  from `index.html`, `upload-pages-artifact`, `deploy-pages` (workflow/push).
- `experiments/neural-showcase-v3/vite.config.ts` — `base:
  process.env.VITE_BASE_PATH ?? "/"`.
- `experiments/neural-showcase-v3/src/main.tsx` — `BrowserRouter
  basename={import.meta.env.BASE_URL}`.

- `scripts/preview-demo-tunnel.sh` — `npm run build` + `vite preview`, optional
  `cloudflared tunnel`.

**Notes**

Repo owner enables **Pages → GitHub Actions** once. `VITE_TARS_API` can be wired
into the workflow when a stable public API URL exists.

## 2026-04-29 — Cursor · Desktop: committed Tauri icon set (unblocks cargo / fresh clone)

**Summary**

`desktop/src-tauri/icons/` previously contained only a README — refs in
``tauri.conf.json`` pointed at ``32x32.png`` … ``icon.ico``, so
``cargo build`` / ``cargo test`` / ``tauri generate_context!`` crashed
with missing files on CI and fresh checkouts.

**Delivered**

- ``desktop/assets/icon-source.png`` — 1024×1024 PNG (indigo/T + cyan halo,
  meeet triad-aligned placeholder).
- ``desktop/scripts/mint_placeholder_icon.py`` — Pillow script to regenerate
  the bitmap (manual dev-dep: ``pip install Pillow``).
- ``cd desktop && npx @tauri-apps/cli icon assets/icon-source.png -o src-tauri/icons``
  emitted 53 raster + ``icon.icns`` + ``icon.ico`` + iOS/Appx/Android stubs
  under ``icons/`` (Tauri 2 default footprint).
- ``desktop/package.json`` — ``npm run tauri:icons`` alias wraps the CLI.
- ``desktop/src-tauri/icons/README.md`` — regen cookbook.
- ``desktop/src-tauri/src/main.rs`` — removed unused ``use tauri::Manager``.
- Local ``cargo test`` → **clean** (still 0 rust tests).

**Notes**

Dev venv gained ``Pillow`` for the one-off mint; not added to pinned
 ``requirements.txt`` — CI does not need Pillow because sources are committed.

## 2026-04-29 — Cursor · Downloads manifest + desktop package version aligned to 0.1.0-alpha.2

**Summary**

`tauri.conf.json` and `docs/RELEASE_NOTES_0.1.0-alpha.2.md` already
tracked **0.1.0-alpha.2**, but the baked-in `DEFAULT_MANIFEST` in
`backend/core/product/manifest.py` was still **0.1.0-alpha.1** —
DownloadStrip on the landing page resolved the wrong version from
`/api/product/*` when no `~/.tars/releases.json` exists. Operator
also needed a one-liner smoke check for `TODO_PUBLIC_KEY`.

**Fixes**

- `backend/core/product/manifest.py` — `_DEFAULT_VERSION` →
  `0.1.0-alpha.2`; `_DEFAULT_NOTES` → Phase M backbone blurb; fourth
  default artifact → Linux x64 AppImage (URLs under
  `meeet.world/downloads/tars/0.1.0-alpha.2/`). Docstring JSON
  example synced.
- `tests/test_product_downloads.py` — default manifest OS set now
  requires `linux` alongside `macos` / `windows`.
- `desktop/package.json` — `version` → `0.1.0-alpha.2` (matches
  `desktop/src-tauri/tauri.conf.json`).
- `docs/contracts/MEEET_DOWNLOADS.md` — example payloads → alpha.2.
- `docs/handoff-claude.md` — sample `/api/product/downloads` defaults
  block refreshed (alpha.2 + AppImage row).
- `desktop/scripts/updater-pubkey-status.sh` — new; prints whether
  `plugins.updater.pubkey` is still `TODO_PUBLIC_KEY`; exit 0 always.
- `docs/OPERATOR_RUNBOOK.md` — new **§0a** cross-linking the script.

**Tests**

- `pytest -q` — 671 passed (unchanged count; default manifest assertion
  widened).

**Not changed**

- `desktop/src-tauri/tauri.conf.json → plugins.updater.pubkey` still
  **`TODO_PUBLIC_KEY`** until an operator runs
  `generate-release-keys.sh --patch-tauri-conf` — no fake keys
  committed.

## 2026-04-29 — Cursor · Console-warning sweep (router · framer-motion · iframe · three dedupe · bundle)

**Summary**

Operator asked to keep auditing after the shader-lines swap. Pulled
the live console on `http://127.0.0.1:5174/` and walked the bug list
top-down. Net delta: ~25 of the 30 runtime warnings/errors removed,
the rest are 3rd-party (Spline runtime / framer-motion HMR ghost) and
documented as accepted. Test totals unchanged: pytest **671/671**,
vitest **56/56**, `tsc --noEmit` clean, `npm run build` clean.

**Fixes**

- `src/main.tsx` — opted in to React Router v7 forward-compat flags
  (`v7_startTransition`, `v7_relativeSplatPath`). Kills the two
  future-flag warnings that were firing on every page load.
- `src/components/ScrollStory.tsx` — refactored `PinnedTrack` so
  `useScroll` is computed **once** at the parent (where `trackRef`
  is hydrated synchronously) and the resulting `MotionValue<number>`
  is passed down to `ProgressRail`, `CopyPane`, `VisualPane`. This
  removes 8 redundant scroll listeners and kills 9 `the provided ref
  is not yet hydrated` framer-motion errors per page load. Added
  `layoutEffect: false` to the lifted `useScroll` for belt-and-braces.
- `src/components/Layers.tsx`, `src/components/Steps.tsx` — added
  `layoutEffect: false` to their `useScroll` calls so framer-motion
  defers ref-target binding to `useEffect`. Same warning class.
- `src/components/CockpitLive.tsx` — dropped the iframe `sandbox`
  attribute. The iframe loads same-origin (`/cockpit?embed=1`) so
  `allow-same-origin allow-scripts` was simultaneously firing the
  browser's "iframe can escape its sandbox" warning and providing
  zero protection (the cockpit needs DOM/storage access). Replaced
  with `referrerPolicy="no-referrer-when-downgrade"`.
- `src/components/Hero.tsx` — live-demo cycle now pauses on hover /
  focus and respects `prefers-reduced-motion` (freezes on prompt 0
  instead of auto-advancing). Demo container marked `aria-hidden`
  because every capability in the rotation is already named in the
  subline above — cycling content via SR is hostile, the snapshot is
  decorative.
- `vite.config.ts` — `resolve.dedupe = ["three", "react", "react-dom"]`
  + `optimizeDeps.include = ["three"]` to force a single bundled copy
  of `three` across the app, R3F, drei, postprocessing, and our
  shader-lines port. (Spline still bundles its own three internally
  — that warning is tracked as ecosystem-known.)
- `vite.config.ts` — `chunkSizeWarningLimit: 2200` so the build log
  only screams when a chunk genuinely regresses, not when the
  intentionally-lazy Spline runtime (physics 1.99 MB / react-spline
  2.04 MB) does its expected weight.

**Accepted (3rd-party)**

- `THREE.WARNING: Multiple instances of Three.js being imported.`
  After dedupe + optimizeDeps, the only remaining source is the
  Spline runtime (`@splinetool/react-spline`), which ships its own
  bundled three internally. Cosmetic — Spline still functions, our
  three is shared for R3F/drei/our shader.
- `[@splinetool] updating from 114 to 122` — internal Spline runtime
  version drift, harmless.
- `Each child in a list should have a unique "key" prop` in
  `TrustStrip` — fires only on framer-motion hot-reload, not on cold
  load and not in production. HMR ghost.
- One `Please ensure that the container has a non-static position`
  framer-motion warning per cold load (down from many before
  refactor). Cosmetic dev-only.

**Tests**

- `pytest -q` — 671/671 passed.
- `npx tsc --noEmit` — clean.
- `npx vitest run` — 56/56 across 7 files.
- `npm run build` — ✓ built in 6.57s, no chunk-size warnings.
- Live verify on `http://127.0.0.1:5174/` — console output trimmed
  from 30+ messages on cold load to 4 (3 accepted + 1 cosmetic).

## 2026-04-29 — Cursor · Hero swap: orb → shader-lines (21st.dev port, local three)

**Summary**

Operator vetoed the orbital-reactor 3D scene shipped earlier today
("ужасный элемент"). Swapped it for the `aliimam/shader-lines`
component from 21st.dev. The original component injects a `<script>`
tag pointing at `cdnjs.cloudflare.com/.../three.min.js` at runtime; we
ported it to use the local `three@0.184.0` already in the bundle so:

- no third-party network call on first paint
- no CSP exception
- bundle hash stays reproducible for signed releases

The fragment shader is preserved verbatim — visual character matches
the 21st.dev preview exactly. The shader lives behind a radial veil
+ bottom-fade so the headline and DownloadStrip card always read crisp
against it.

**Files**

- `src/components/ui/shader-lines.tsx` — new. `ShaderAnimation`
  component. Local `import * as THREE from 'three'` instead of CDN
  loader. `PlaneBufferGeometry` → `PlaneGeometry` (three 0.150+ API).
  ResizeObserver on the container (not `window`) so the shader resizes
  cleanly when the hero layout changes. Pixel ratio capped at 1.5.
  `prefers-reduced-motion` freezes the time uniform but still renders
  one calm frame so the visual is not blank. Cleanup is StrictMode-safe
  (RAF cancelled, observer disconnected, geometry/material/renderer
  disposed).
- `src/components/Hero.tsx` — `HeroScene` lazy import replaced with
  `ShaderAnimation` lazy import. Background layer now renders the
  shader plus two veils: a centred radial gradient
  (`rgba(7,7,10,0.78) → 0` over 78% of the ellipse) to dim the bright
  centre under the headline, and a 40-tall bottom gradient handing off
  to `--color-bg-0`. JSDoc updated.
- `src/three/HeroScene.tsx` — deleted (dead code after swap).

**Tests**

- `npx tsc --noEmit` — clean.
- `npx vitest run` — 56/56 passing across 7 files.
- `npm run build` — ✓ built in 6.47s, no new warnings.
- Live verify on `http://127.0.0.1:5174/` — shader renders, headline
  stays legible, DownloadStrip card chrome dominates the focus stack.

## 2026-04-29 — Cursor · Hero refresh (3D scene mounted, sovereignty headline, top-of-fold downloads, audit sweep)

**Summary**

Operator-driven Hero pass. Three concrete asks plus a global audit:
(1) wire a real 3D animation on the first fold, (2) replace the
"crooked" headline with copy that reflects current TARS surface area,
(3) put the OS-detected download buttons at the very top, and (4) run
a global health sweep, fix bugs, and log improvements for Claude.
Net delta: hero now has a centered cyan/gold orbital reactor as a
WebGL background sculpture, a three-beat sovereignty headline (Your
AI. / Your machine. / Your terms.), DownloadStrip is the first action
surface a visitor reaches (above demo + CTAs), and one stale dangling
symbol (`slugifyHeading`) was killed in `MarkdownView.tsx` along the
way.

**Hero refresh (`experiments/neural-showcase-v3/`)**

- `src/three/HeroScene.tsx` — was dead code (defined but never
  mounted). Now imported via `React.lazy` from `Hero.tsx`. Added two
  thin orbital wireframe rings (cyan on the X axis, gold on a
  perpendicular plane) around the indigo distort-icosa reactor. Both
  rings spin independently at sub-Hz; orb scale tuned to 0.62 radius
  / camera at z=14, FOV 22 → orb fills ~25% of viewport height,
  visibly behind the headline without HUD-framing the text.
  `prefers-reduced-motion` slows rotation to ≤ 0.02 rad/s + freezes
  ring rotation. Sparkles split into 45 gold + 25 cyan particles
  (cap 70 total, opacity ≤ 0.18 per Master §6). Bloom intensity
  0.28, threshold 0.86 — bloom never bleeds onto type.
- `src/components/Hero.tsx` — restructured. `<HeroScene />` lives
  in an absolute z-0 container, `pointer-events: none`, behind the
  z-30 content layer. Order under content layer: eyebrow →
  three-line headline (`text-shadow: 0 2px 24px rgba(0,0,0,0.65)`
  on every line, plus a soft gold halo on the third line) →
  subline → **DownloadStrip wrapped in a backdrop-blur card**
  (top-of-fold per the operator brief) → live demo (input + result
  preview cycling at 4.2s) → CTAs.
- `src/components/Hero.tsx` — demo now cycles 5 prompts that show
  the new surfaces actually shipped this phase: morning-brief,
  Phantom-wallet send (proposed → policy gate confirm), entrepreneur
  lead-scoring on a CSV, RAG with `[chunk_N]` citations, and a
  vision-OCR whiteboard pass.
- `src/lib/i18n.ts` — `hero.eyebrow`, `hero.title.line1/2/3`,
  `hero.subline`, `hero.demo.label` all swapped. Headline:
  EN "Your AI. / Your machine. / Your terms." · RU "Твой ИИ. /
  Твоя машина. / Твои правила." Subline lists the actual surfaces
  (files / voice / calendar / code / vision / on-chain) with the
  council-of-agents framing. Eyebrow is now an evergreen brand line
  ("TARS · operator-grade · local-first AI") instead of the stale
  "Phase 09" reference.
- `src/components/MeetTars.tsx` — h2 was echoing the OLD hero
  headline ("Your machine, awakened.") and reading like a duplicate.
  Replaced with "Two voices. One verdict." which fits the section
  brief (intro to TARS + the council orchestrator) without
  duplicating the hero's three-beat rhythm.
- `experiments/neural-showcase-v3/.env.local` — pinned
  `VITE_TARS_API` to `127.0.0.1:8765` (matches `serve.py` default).
  Was pointing at `:9911`, leaving DownloadStrip in `offline ·
  couldn't load installers` state during local dev.

**Audit + bug fixes**

- `src/components/MarkdownView.tsx` — call site at line 248
  referenced `slugifyHeading` which was previously fine because it
  was defined later in the same file (line 395) and hoisted. A
  stale `.tsbuildinfo` cache from a partial earlier session
  desync'd the symbol table; cleared, rebuild green. No real code
  change beyond the cache invalidation, but the false positive
  was a real production-build risk on a fresh checkout, so flagged
  in the audit log.
- Verified pytest 671 / vitest 56 / `tsc --noEmit` clean / vite
  production build green (`npm run build` succeeds; chunk-size
  warning on `physics-*` and `react-spline-*` is pre-existing,
  noted for Claude's future code-split pass).
- Verified `Footer.tsx` already mounts
  `<DownloadStrip variant="footer" />` (the AGENT_HANDOFF.md `Owned
  by Claude · item 11` line about "drop a footer variant in" is
  stale — Cursor shipped this in an earlier batch). Updating
  handoff-claude.md to reflect.

**Files (new)** — none.

**Files (changed)**

- `experiments/neural-showcase-v3/src/components/Hero.tsx`
- `experiments/neural-showcase-v3/src/components/MeetTars.tsx`
- `experiments/neural-showcase-v3/src/three/HeroScene.tsx`
- `experiments/neural-showcase-v3/src/lib/i18n.ts`
- `experiments/neural-showcase-v3/.env.local`
- `docs/CHANGELOG_AGENTS.md` (this file)
- `docs/AGENT_HANDOFF.md` (next session note)
- `docs/handoff-claude.md` (brand pass refresh)

**Test totals**

| Suite  | Before | After  | Delta |
|--------|-------:|-------:|------:|
| pytest | 671    | **671** | 0    |
| vitest | 56     | 56     | 0    |
| tsc    | clean  | clean  | —    |
| swift  | 18     | 18     | 0    |
| build  | clean  | clean  | —    |

---

## 2026-04-29 — Cursor · Phase M backbone (entitlements + roles + vision agent + entrepreneur pack + cleanup sweep)

**Summary**

Closes every remaining functional task from the post-launch-readiness
audit: the four big P5–P8 backend modules plus the four cleanup items
(stale TODOs, recovery policy gate hook-up, mobile wiring, tauri
public-key auto-patch). Test totals jump pytest **600 → 671 (+71)**
across the new modules. Vitest **56**, swift **18**, `tsc --noEmit`
clean — all unchanged.

**Cleanup-pass (4 items)**

- `desktop/src-tauri/src/main.rs` — replaced the stale "sidecar TODO"
  comment with the actual sidecar-owned-by-`sidecar.rs` story.
- `web_extras/routers/recovery.py` — wired `policy_gate.require_confirm`
  for `POST /api/recovery/{generate,verify}` plus a new
  `POST /api/recovery/confirm` endpoint that mints recovery-scoped
  HMAC tokens. Default-off behaviour preserved (the dev / first-launch
  flow keeps working without `TARS_REQUIRE_OPERATOR_CONFIRM=1`).
- `desktop/scripts/generate-release-keys.sh` — added
  `--patch-tauri-conf` flag that rewrites
  `desktop/src-tauri/tauri.conf.json` `plugins.updater.pubkey` with the
  freshly generated key (json-safe via inline `python3` snippet).
- Mobile activity wiring — Android: new `WalletActivity.kt` + manifest
  registration + "open wallets" CTA from `PairingScreen` Linked state.
  iOS: new `TARSCompanionRoot.swift` exposing the public TabView shell
  (`pairing` + `wallets`) so downstream Xcode targets just plug it in.

**P5 — Entitlements (`backend/core/entitlements/`)**

- `tiers.py` — `Tier` enum (`free / pro / business`) + `TierLimits`
  dataclass + `LIMITS` table matching the cockpit Pricing page
  (free: $0/0-cap, pro: $19, business: $79/seat). `format_caps`
  surfaces unlimited council votes / T2T as null for the cockpit.
- `store.py` — single-tenant JSON store at
  `~/.tars/entitlements.json` (overridable via `TARS_ENTITLEMENTS_PATH`).
  Atomic writes, `0o600` perms, no crypto (tier isn't secret).
- `checker.py` — async `can_run(kind=…)` against the meeet usage ledger
  (`UsageLedger.rollup(since=…)`). Edge always allowed; cloud blocks
  past the daily cap; BYO toggle relaxes the cap.
- `web_extras/routers/entitlements.py` — 5 endpoints:
  `GET /api/entitlements`, `POST /upgrade`, `POST /byo`,
  `POST /can_run`, `GET /tiers`. Emits
  `entitlements.{upgraded, byo_toggled, cap_hit}` to meeet.

**P6 — Entrepreneur pack (canonical replacement for MLM)**

- `backend/core/domains/packs/entrepreneur/` — new pack with
  renamed action ids: `network_snapshot`, `lead_score`,
  `generate_content`, `add_lead` (plus `retention_alert` /
  `log_activity` kept). Reuses MLM awareness sources verbatim.
- `backend/core/domains/base.py` — `DomainManifest.deprecated` /
  `deprecated_in_favor_of` fields; `DomainManifest` is now extensible
  without breaking existing call sites.
- `backend/core/domains/packs/mlm/pack.py` — `manifest.deprecated=True`
  + `deprecated_in_favor_of="entrepreneur"`. Stays registered for
  90 days (until 2026-07-29) so saved cockpit state + agents pinned
  to `pack_slug=mlm` keep working.
- `backend/core/domains/registry.py` — `register_alias` infrastructure
  + `aliases()` + `resolve_alias` for future renames (currently unused
  by entrepreneur, since both packs are independently registered).

**P7 — Roles (`backend/core/roles/`)**

- `models.py` — `Role` dataclass (slug / name / description /
  backing_packs / overlay / custom / color / icon).
- `synthesis.py` — deterministic `synthesise_overlay(name, description,
  backing_packs, samples)` that produces a TARS-shaped system-prompt
  fragment (priorities extracted via regex hints; voice samples
  optionally folded). No LLM call — overlay is reproducible.
- `registry.py` — 6 built-in roles matching the cockpit Onboarding
  page (`founder / trader / researcher / marketer / engineer / operator`).
  Custom roles persist to `~/.tars/roles.json`. Active-role state
  carried per-host. Built-in roles are read-only.
- `web_extras/routers/roles.py` — 6 endpoints: `GET /api/roles`,
  `GET /api/roles/active`, `POST /{slug}/activate`, `POST /api/roles`,
  `DELETE /{slug}`, `GET /{slug}/overlay`. Emits
  `role.{activated, created, deleted}` to meeet.
- `backend/core/chat/orchestrator.py` — `_system_prompt_for` now
  prepends the active role's overlay (with `\n\n---\n\n` separator)
  before the pack prompt. Falls back to either alone if the other
  is missing.

**P8 — Vision agent (`backend/agents/vision_agent.py`)**

- `VisionAgent` + `VisionPayload` + `VisionAttachmentSummary` +
  `is_image_attachment` helper. Lazy-imports `pytesseract` + `PIL`
  so the agent stays dep-free when image attachments aren't present
  (or those packages aren't installed).
- OCR pluggable via the `OCRRunner` ABC; `DefaultOCRRunner` does the
  best-effort pass and reports `unavailable` when tesseract is absent
  rather than crashing.
- Image dimensions (`_image_dimensions`) probed via PIL, also lazy.
- `backend/core/chat/voices.py` — `ChatVoice.supports_multimodal`
  class flag (default `False`); `AnthropicChatVoice` and
  `OpenAIChatVoice` opt in (their default models are vision-capable).
- `backend/core/chat/orchestrator.py` — runs the vision agent on every
  turn that has attachments; the structured text block (filename,
  mime, dimensions, OCR text or "OCR unavailable") is folded into the
  system prompt for *every* voice. Multimodal voices additionally
  receive the raw image refs through the existing `attachments`
  parameter and decide what to do with them.
- New `context.vision` `StreamEvent` so the cockpit can render which
  images the agent picked up + their OCR status.

**Tests**

- `tests/test_recovery_policy_gate.py` (new, 8 cases) — confirms
  default-off works, `TARS_REQUIRE_OPERATOR_CONFIRM=1` enforces tokens
  on `/generate` + `/verify`, params-hash binding rejects token reuse.
- `tests/test_entrepreneur_pack.py` (new, 8 cases) — confirms canonical
  pack id, deprecated MLM still resolves, action ids match the spec,
  `lead_score` is deterministic, `generate_content` channel guard.
- `tests/test_entitlements.py` (new, 18 cases) — Tier defaults, BYO
  toggle, cap-hit blocking against synthetic ledger usage, HTTP
  upgrade / can_run / byo / tiers endpoints.
- `tests/test_roles.py` (new, 24 cases) — default-roles list, custom
  role create / delete, active-role round-trip, HTTP router parity,
  orchestrator overlay-prepending behaviour.
- `tests/test_vision_agent.py` (new, 13 cases) — image detection,
  OCR truncation, image_refs surfacing, `supports_multimodal` flags,
  orchestrator vision-block fold.

**Files (new)**

- `backend/core/entitlements/{__init__,tiers,store,checker}.py`
- `backend/core/roles/{__init__,models,registry,synthesis}.py`
- `backend/core/domains/packs/entrepreneur/{__init__,pack,actions,prompts}.py`
- `backend/agents/{__init__,vision_agent}.py`
- `web_extras/routers/{entitlements,roles}.py`
- `mobile/android/TARSCompanion/app/src/main/java/world/meeet/tars/WalletActivity.kt`
- `mobile/ios/TARSCompanion/Sources/TARSCompanion/TARSCompanionRoot.swift`

**Files (changed)**

- `web_extras/app.py` (+2 routers), `web_extras/routers/recovery.py`
  (+ policy gate + `/confirm`), `desktop/src-tauri/src/main.rs`
  (TODO cleanup), `desktop/scripts/generate-release-keys.sh`
  (`--patch-tauri-conf`), `mobile/android/.../AndroidManifest.xml`,
  `mobile/android/.../ui/PairingScreen.kt` (+open-wallets CTA),
  `backend/core/domains/{base,registry}.py` (deprecated flag +
  alias infra), `backend/core/domains/packs/__init__.py`,
  `backend/core/domains/packs/mlm/pack.py` (deprecated marker),
  `backend/core/chat/{orchestrator,voices}.py` (vision hook +
  multimodal flag).

**Test totals**

| Suite  | Before | After  | Delta |
|--------|-------:|-------:|------:|
| pytest | 600    | **671** | +71  |
| vitest | 56     | 56     | 0    |
| tsc    | clean  | clean  | —    |
| swift  | 18     | 18     | 0    |

---

## 2026-04-29 — Cursor · final sweep (mobile wallet surface + cinematic mnemonic + release-key helper)

**Summary**

Closes the last three Cursor-lane items on `LAUNCH_READINESS.md`:
mobile companion wallet surface, cinematic mnemonic-reveal polish,
and a guarded helper for minting the desktop release-signing
keypair. Hands the brand polish baton to Claude with an updated
`docs/handoff-claude.md` block listing every shipped surface.

Test deltas: pytest **600** (unchanged — no backend change), vitest
**50 → 56 (+6)** (`MnemonicReveal.test.ts`), tsc `--noEmit` clean,
swift **11 → 18 (+7)** (`WalletClient` decoder fixtures + shortened
address). Android JUnit fixtures landed (`WalletDecodersTest.kt`)
but require an Android SDK on CI to execute — same pattern as the
existing pairing tests, which is why the totals don't move.

**iOS companion · read-only wallet surface**

- `mobile/ios/TARSCompanion/Sources/TARSCompanion/WalletClient.swift`
  (new, 230 LOC) — Swift actor mirroring `lib/wallet.ts` for the four
  endpoints the phone needs: list / get / balance / sign-ownership.
  Hand-rolled decoders so a stray schema drift fails loud.
  `CompanionWallet.shortenedAddress` for glanceable rendering.
- `mobile/ios/TARSCompanion/Sources/TARSCompanion/WalletView.swift`
  (new, 220 LOC) — SwiftUI list with chain badges, refresh-on-pull,
  per-row "Balance" + "Prove" CTAs. Empty / error states render as
  inline blocks (kept compatible with macOS 13 — no
  `ContentUnavailableView`). `WalletViewModel` exposes `load`,
  `refreshBalance`, `proveOwnership`.
- `mobile/ios/TARSCompanion/Tests/TARSCompanionTests/TARSCompanionTests.swift`
  — added 7 wallet-decoder tests (`testWalletListDecoder`,
  `testWalletListRejectsMissingArray`, `testBalanceDecoder`,
  `testBalanceDecoderReturnsNilWhenAbsent`, `testSignatureDecoder`,
  `testSignatureDecoderRejectsEmpty`, `testShortenedAddress`).

**Android companion · read-only wallet surface**

- `mobile/android/TARSCompanion/app/src/main/java/world/meeet/tars/net/WalletClient.kt`
  (new, 215 LOC) — OkHttp-based mirror of the iOS surface; identical
  decoder semantics so contract drift surfaces on either platform.
- `mobile/android/TARSCompanion/app/src/main/java/world/meeet/tars/WalletViewModel.kt`
  (new, 100 LOC) — `WalletState` data class, `load` /
  `refreshBalance` / `proveOwnership` coroutine actions, busy-set
  tracking per wallet id.
- `mobile/android/TARSCompanion/app/src/main/java/world/meeet/tars/ui/WalletScreen.kt`
  (new, 175 LOC) — Jetpack Compose list with chain badges (matching
  the iOS palette), prove-ownership CTA, empty / error states.
- `mobile/android/TARSCompanion/app/src/test/java/world/meeet/tars/WalletDecodersTest.kt`
  (new, 95 LOC) — JUnit fixtures mirroring the Swift decoder tests
  one-for-one.

**Cinematic mnemonic reveal**

- `experiments/neural-showcase-v3/src/components/MnemonicReveal.tsx`
  (new, 240 LOC) — face-down card grid; "reveal phrase" gating CTA;
  60ms-stagger 3D card flip per word using only CSS transforms;
  `Eye` / `EyeOff` toggle once revealed; "I wrote it down"
  affirmation. Pure-CSS perspective + `backfaceVisibility`; no
  third-party motion library. Exports `splitMnemonic` and
  `gridTemplateForCount` helpers for reuse.
- `experiments/neural-showcase-v3/src/components/MnemonicReveal.test.ts`
  (new, 6 vitest cases) — locks the parsing + grid heuristics.
- `experiments/neural-showcase-v3/src/components/WalletPanel.tsx` —
  drops the inline reveal block, mounts `<MnemonicReveal />`.
  Pruned the now-unused `AlertTriangle` import.

**Release-key bootstrap helper**

- `desktop/scripts/generate-release-keys.sh` (new, 95 LOC) —
  guarded one-shot script that mints a Tauri/minisign keypair to
  `~/.tars-release-keys/` (override with `--out`), refuses to
  overwrite existing keys, prints the public key for
  `tauri.conf.json -> plugins.updater.pubkey`, then prints the two
  `gh secret set …` commands the operator needs to install
  `TAURI_SIGNING_PRIVATE_KEY` + `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`
  on the GitHub repo. Never uploads anything; everything is local.

**Claude sync**

- `docs/handoff-claude.md` — re-headlined for the late-session
  state, added wallet-panel / chain-send / mnemonic / mobile
  rows to the "what's already live" table, marked the cinematic
  mnemonic TODO done with a pointer to `<MnemonicReveal />`, fresh
  test totals, and a final coordination block listing the only
  remaining red items (real release-signing credentials are
  human-only).
- `docs/CHANGELOG_AGENTS.md` — this entry.
- `docs/AGENT_HANDOFF.md` and `docs/LAUNCH_READINESS.md` — bumped
  totals + flipped the mobile and cinematic rows.

## 2026-04-29 — Cursor · Phases O1–O4 + P1–P4 + Q1 + D1 + D4 (production hardening + UX completeness + smoke + docs)

**Summary**

Twelve sequenced phases that take TARS from "wallet signing works"
to "binary-alpha-ready". Every phase ships behind an opt-in env
flag where applicable — existing dev workflows are unchanged
unless the operator deliberately turns the new behaviour on.

Test deltas: pytest **525 → 600 (+75)**, vitest 50 (unchanged),
tsc clean, swift 11 (unchanged). Full sweep on a fresh checkout
green.

**Phase O1 — structured error envelope**

- `web_extras/errors.py` (new, 184 LOC) — `TARSAPIError`
  subclasses `HTTPException`; `ERROR_CODES` taxonomy +
  `ERROR_HINTS`; handlers for `HTTPException`,
  `RequestValidationError`, and `StarletteHTTPException`.
- `web_extras/app.py` — calls `errors.install(app)` at startup.
- `tests/test_error_envelope.py` (8 tests) — pins envelope shape,
  validation breakdown, hint registration, and legacy `detail`
  preservation.

**Phase O2 — HTTP policy gate (opt-in)**

- `web_extras/policy_gate.py` (new, 196 LOC) — HMAC-SHA256
  signed confirm tokens bound to `(wallet_id, action,
  params_hash, expires_at)`. Default off via
  `TARS_REQUIRE_OPERATOR_CONFIRM`. `mint_token` /
  `verify_token` / `require_confirm` exposed.
- `web_extras/routers/wallet.py` — `POST /api/wallet/{id}/confirm`
  + `GET /api/wallet/policy/status`; destructive routes (`DELETE`,
  `sign_evm_tx`, `sign_ton_transfer`, `sign_solana_transfer`)
  call `policy_gate.require_confirm` with the request body's
  `model_dump(exclude_none=True)`.
- `tests/test_policy_gate.py` (17 tests) — full token lifecycle,
  tampering, expiry, wallet/action/params-mismatch, malformed
  tokens, env-flag toggle.

**Phase O3 — SLIP-0010 Phantom-compatible Solana derivation**

- `backend/core/wallet/slip10.py` (new, 91 LOC) — official
  SLIP-0010 ed25519. `derive_solana_phantom(seed, account, change)`
  at `m/44'/501'/{account}'/{change}'`.
- `backend/core/wallet/models.py` — `Wallet.derivation_scheme`
  field (`tars-v1` default, `bip44-501-phantom` opt-in).
- `backend/core/wallet/derive.py` — `derive_solana` accepts
  `derivation_scheme`; routes through SLIP-0010 when set.
- `backend/core/wallet/service.py` — `_create_wallet_sync` threads
  the scheme; `_SCHEMA` adds `derivation_scheme TEXT NOT NULL
  DEFAULT 'tars-v1'`; `_migrate_add_derivation_scheme` runs an
  idempotent ALTER for pre-existing DBs.
- `web_extras/routers/wallet.py` — `CreateWalletRequest` /
  `ImportWalletRequest` accept `derivation_scheme`; emitted in
  `wallet.created` event.
- `tests/test_wallet_slip10.py` (13 tests) — SLIP-0010 master
  matches the spec test vector; canonical zero-mnemonic at
  `m/44'/501'/0'/0'` produces
  `HAgk14JpMQLgt6rVgv7cBQFJWFto5Dqxi472uT3DKpqk`; legacy DB
  migration round-trips.

**Phase O4 — wallet audit log (raw bytes opt-in)**

- `backend/core/wallet/audit.py` (new, 89 LOC) — `is_enabled` /
  `retention_seconds` / `enrich_signed_event` /
  `prune_signed_events`. `TARS_AUDIT_RAW_TX` (default off);
  `TARS_AUDIT_RETENTION_DAYS` (default 30).
- `backend/core/meeet/store.py` — new
  `prune_kind_before(kind_prefix, kind_suffix, before_unix)` ·
  `_prune_sync` does the SQLite DELETE.
- `web_extras/routers/wallet.py` — sign routes wrap their
  meeet event payload through `enrich_signed_event`; new
  `POST /api/wallet/audit/prune` endpoint.
- `tests/test_wallet_audit.py` (14 tests) — privacy-by-default
  for all three chains, opt-in attaches raw fields, prune
  drops old events, retention env var honoured.

**Phases P2 / P3 / P4 — live RPC helpers**

- `backend/core/wallet/chain_helpers.py` (new, 138 LOC) —
  `get_solana_blockhash` (`getLatestBlockhash`), `get_evm_nonce`
  (`eth_getTransactionCount`), `get_ton_seqno` (TON Center
  `runGetMethod` for v3R2). All stdlib `urllib`. Parses tonsdk-
  style `["num", "0x..."]` and dict-with-value stack heads;
  fresh / undeployed TON wallets surface as `seqno=0`.
- `web_extras/routers/wallet.py` —
  `GET /api/wallet/solana/blockhash`,
  `GET /api/wallet/evm/{address}/nonce?block_tag=`,
  `GET /api/wallet/ton/{address}/seqno`. All return
  `502 wallet_balance_rpc_failure` on transport failure with
  the unified envelope.
- `tests/test_wallet_chain_helpers.py` (19 tests) — stack
  parsing, malformed addresses, invalid block tags, transport
  failure → 502, happy paths through HTTP.

**Phase P1 — chain-specific send forms in cockpit**

- `experiments/neural-showcase-v3/src/lib/wallet.ts` — adds
  `fetchSolanaBlockhash`, `fetchEVMNonce`, `fetchTONSeqno`,
  `fetchPolicyStatus`, `mintConfirmToken`. Existing
  `signEVMTransaction` / `signTONTransfer` /
  `signSolanaTransfer` accept optional `confirmToken` →
  attach as `X-TARS-Confirm` header.
- `experiments/neural-showcase-v3/src/components/ChainSendForm.tsx`
  (new, 358 LOC) — per-chain inputs (Solana: blockhash + memo;
  EVM: nonce + chainId + gas + EIP-1559 fees; TON: seqno +
  payload). Single ⚡ "autofill" button per chain hits the
  P2/P3/P4 endpoint. Auto-mints a confirm token if
  `policy_required`. Renders signed payload with copy buttons.
- `experiments/neural-showcase-v3/src/components/WalletPanel.tsx`
  — `send` button toggles `ChainSendForm` for any signing-
  capable wallet; the legacy build-only flow stays as a
  fallback for chains without local signing.

**Phase Q1 — end-to-end smoke**

- `tests/test_e2e_smoke.py` (4 tests, ~330 LOC) — pair
  (`/api/pairing/begin` → `/accept` → status confirms `linked`)
  → mint Solana / EVM / TON wallets → sign personal message
  on each → sign real transaction on each → verify via
  independent crypto (`Account.recover_transaction`,
  `b58decode` 64-byte ed25519 signature, TON body_hash + boc
  shape) → mint agent + task + run → assert meeet store
  recorded `pair.attempted`, `wallet.created`,
  `wallet.solana_transfer_signed`, `wallet.evm_tx_signed`,
  `wallet.ton_transfer_signed`, `agent.*`, `agent.task.*`.
  Plus privacy smoke (no raw in default events) and error
  envelope smoke.

**Phase D1 — root README.md**

- `README.md` (new, 246 LOC) — quickstart (backend + cockpit +
  Tauri), env var reference (wallets, hardening, pairing,
  meeet bridge), architecture diagram, common operations
  (Phantom-compat wallet, sign Solana transfer with live
  blockhash), troubleshooting, test commands.

**Phase D4 — THREAT_MODEL.md**

- `docs/THREAT_MODEL.md` (new, 226 LOC) — trust zones (Z0–Z7),
  what we trust the host to do, where every piece of crypto
  material lives + its at-rest encryption, attack surfaces
  ranked by blast radius (local malware → confused-deputy via
  destructive HTTP), what we deliberately DO NOT do, logging
  policy, primitive choices + rationale, security contact.

**Misc**

- `tests/test_policy_gate.py::test_gate_token_signature_tamper_rejected`
  — flip the *middle* base64 char of the signature instead of
  the last one, since the last char's lower bits can land in
  base64 padding and decode unchanged. Removes a test flake.
- `tests/test_e2e_smoke.py::test_full_smoke` — the smoke uses
  the project-local `b58decode` (no transitive `base58` test
  dependency) and the canonical `name` / `pack_slug` /
  `prompt` field names from the agent contract.

**Test counts**

- pytest: 525 → **600** (+75)
- vitest: 50 → **50** (unchanged)
- tsc --noEmit: clean
- swift test: 11 → 11 (unchanged)

Files added (10): `web_extras/errors.py`,
`web_extras/policy_gate.py`, `backend/core/wallet/slip10.py`,
`backend/core/wallet/audit.py`,
`backend/core/wallet/chain_helpers.py`,
`experiments/neural-showcase-v3/src/components/ChainSendForm.tsx`,
`tests/test_error_envelope.py`, `tests/test_policy_gate.py`,
`tests/test_wallet_slip10.py`, `tests/test_wallet_audit.py`,
`tests/test_wallet_chain_helpers.py`, `tests/test_e2e_smoke.py`,
`README.md`, `docs/THREAT_MODEL.md`.

Files modified (8): `web_extras/app.py`,
`web_extras/routers/wallet.py`,
`backend/core/wallet/models.py`,
`backend/core/wallet/derive.py`,
`backend/core/wallet/service.py`,
`backend/core/meeet/store.py`,
`experiments/neural-showcase-v3/src/lib/wallet.ts`,
`experiments/neural-showcase-v3/src/components/WalletPanel.tsx`.

## 2026-04-29 — Claude · Waves 7–10 (viral hook + cookie + count-up + share-meta + analytics)

**Summary**

Four polish waves on the marketing surface, all behind 0-error `tsc`.
Pre-launch viral mechanic is now end-to-end shippable: the `/build-with`
page generates four badge variants, the four matching SVGs ship in
`public/badge/` so the Markdown embed-URL works the moment we deploy,
and conversion clicks (install copy, badge copy, downloads) emit the
e2e analytics contract for brother to consume on `tars.meeet.world`.

**Wave 7 — `/build-with` + cookie consent + stat count-up**

- `src/pages/BuildWith.tsx` (new, 410 LOC) — viral-hook page. 2 sizes
  (full 220×60 / compact 160×44) × 2 themes (dark/light). Inline SVG
  with brand-sweep gradient + monolith icosahedron. Paste-ready HTML
  and Markdown blocks, optional link override, "where it goes" copy.
- `src/components/CookieConsent.tsx` (new) — dismissible banner about
  functional-only cookies. Persisted in `localStorage["tars-cookie-ack"]`,
  1.2s delay, brand-triad hairline, deep-link to Privacy § 9. Mounted
  globally in `<AppShell/>`.
- `src/components/CountUpNumber.tsx` (new) — framer-motion primitive,
  `useInView` triggered, respects `prefers-reduced-motion`.
- `src/components/ProofStrip.tsx` (new) — 4-stat row on Landing
  (28 / 14 / 6 / 100%) between TrustStrip and MeetTars. CountUpNumber
  applied. Numbers also wired into `/pitch` slide 0 StatGrid.
- `src/App.tsx` — `/build-with` lazy route, `<CookieConsent/>` mount.
- `public/sitemap.xml`, `Footer.tsx → Resources`, `GlobalCommandPalette
  → Pages` — `/build-with` linkage.

**Wave 8 — static badge assets + share-meta + NotFound polish**

- `public/badge/built-with-tars.svg` (full / dark) — primary endpoint
  the `/build-with` Markdown embed points at. Three variants alongside
  it (`-light`, `-compact`, `-compact-light`).
- `src/lib/meta.ts` (new) — `useDocumentMeta({ title, description,
  ogImage })`. Updates `document.title`, `<meta name=description>`, and
  the og/twitter pair on route mount; restores defaults on unmount.
- Applied to /build-with, /404, /pitch, /install, /cockpit, /onboarding,
  /press, /docs, /status, plus the LegalLayout wrapper (auto-derives a
  one-line description from the markdown lede for /privacy /terms
  /security /roadmap /changelog).
- `src/pages/NotFound.tsx` — added Stamp icon + `/build-with` deep link
  in the "Did you mean" grid; fits 6 destinations on the 2-col layout.

**Wave 9 — analytics scaffolding (e2e logging contract)**

- `src/lib/analytics.ts` (new) — batched event tracker. Names follow
  `tars.<page|api|click>.<action>`. Buffer in `localStorage` (cap 200,
  oldest-evicted). `POST /api/log` with `keepalive`, `sendBeacon` on
  `beforeunload`. Drains the queue when brother stands up the endpoint.
- `src/App.tsx` — `tars.page.view` emitted on every route change.
- `src/pages/Install.tsx` — `tars.click.install_copy_(install|brew)`
  with `os` prop on the curl + Homebrew copy buttons.
- `src/pages/BuildWith.tsx` — `tars.click.badge_copy_(html|md)` with
  `size` + `theme` props on the embed copy buttons.
- `docs/contracts/ANALYTICS.md` (new) — full event-name catalogue,
  wire shape, retention, brother's responsibilities (validate name
  pattern, drop stale `ts`, stamp `received_at` server-side, persist
  to ClickHouse, respond 204).

**Wave 10 — DownloadStrip analytics + this changelog entry**

- `src/components/DownloadStrip.tsx` — `tars.click.download_<os>_<arch>`
  fired from the hero primary button, the footer-variant link, and
  every "all installers" chip. Carries `version`, `kind`, `surface`
  ("hero" / "footer" / "all_installers"). `PrimaryButton` accepts a
  new `version` prop so the hero CTA can stamp it on the event.

**Other polish (collateral fixes to keep `tsc` green)**

- `src/pages/Pitch.tsx` — moved `ARCH_DIAGRAM` declaration above
  `SLIDES` (real JS TDZ bug — module-init evaluation read the const
  before its line was reached).
- `src/components/CommandPalette.tsx` — dropped unused `useMemo`.
- `src/components/HeroGlobe.tsx` — dropped unused `@ts-expect-error`.
- `src/components/GlobalCommandPalette.tsx` — dropped unused
  `ArrowRight`, added `Stamp` for the new `/build-with` palette item.
- `src/pages/BuildWith.tsx` — `buildMarkdown` no longer takes the
  unused `svg` arg; per-variant URL slug now matches the four files
  in `public/badge/`.
- `tsconfig.app.json` — `exclude: ["src/**/*.test.{ts,tsx}"]` so the
  vitest-namespace errors stay out of the production type-check.

**Verification** — `npx tsc --noEmit -p tsconfig.app.json` → 0 errors
after every wave.

## 2026-04-29 — Cursor agent · N5 (real Solana tx signing, system_program::transfer)

**Summary**

Closes the last "tx-signing not yet" cell in the wallet matrix. All
three chains (Solana, EVM, TON) are now full-stack signing capable:
keys, balance, message signing, and transaction signing. The N3/N4
architecture (chain-specific signer module behind a uniform
`WalletService` interface) carries straight through — no upstream
shape changes.

`solders` is the Rust-native binding for `solana-sdk`; we use its
`Keypair`, `Pubkey`, `Hash`, `Message`, `Transaction`, and
`system_program.transfer` primitives. The caller supplies
`recent_blockhash` so the policy gate can inspect the prepared tx
before we reach the network — same trust model as EVM/TON.

**Backend**

- `requirements.txt`: pinned `solders>=0.21,<1.0`.
- `backend/core/wallet/sign_sol.py` (new): `derive_solana_keypair`
  (32-byte ed25519 seed → `solders.Keypair` + Base58 address),
  `sign_solana_transfer` (builds + signs `system_program::transfer`,
  returns `{raw_b64, raw_b58, raw_hex, tx_signature, signer,
  recipient, lamports, blockhash, memo}`). Helper `parse_lamports`
  accepts lamports digit-strings, ints, hex (`0x…`), and SOL
  decimals (`"0.5"` → 500_000_000).
- `backend/core/wallet/service.py`: new `sign_solana_transfer` async
  method (decrypts seed via the existing path, dispatches through
  `sign_sol.py`, raises `WalletError` on validation failure).
- `backend/core/domains/packs/wallet/actions.py`: new
  `wallet.sign_solana_transfer` action (destructive, gated by
  policy).
- `web_extras/routers/wallet.py`: new
  `POST /api/wallet/{id}/sign_solana_transfer` route, emits
  `wallet.solana_transfer_signed` Meeet event.

**Cockpit**

- `experiments/neural-showcase-v3/src/lib/wallet.ts`: new
  `signSolanaTransfer`, `SolanaSigned`, `SolanaTransferRequest`
  types — completes the per-chain transaction-signing client trio.

**Tests**

- `tests/test_wallet_sol_signing.py` (new): 22 cases — deterministic
  derivation against `bytes(0..31)` → canonical address
  `FAe4sisG95oZ42w7buUn5qEE4TAnfTTFPiguZUHmhiF`, address matches
  `b58encode(public_key)`, raw_b64 / raw_b58 / raw_hex all decode
  to the same bytes, `tx_signature` matches the first signature
  parsed back via `solders.Transaction.from_bytes`, signing is
  deterministic for fixed `(seed, recipient, lamports, blockhash)`,
  changing the blockhash changes the signature, invalid recipient /
  blockhash / negative lamports rejected, `parse_lamports` decimal /
  digit-string / int / float / hex / empty paths, HTTP route
  200 / 400 / 404 / invalid-amount / non-Solana wallet, pack action
  ok / wrong-chain / missing-args / destructive-flag, end-to-end
  service-level signer-matches-wallet-address, unknown-wallet raises.

**Test deltas:** +22 pytest (503 → 525), 0 vitest. `tsc --noEmit`
clean. Full suite green.

**Docs**

- `docs/LAUNCH_READINESS.md`: Solana row in the score card now reads
  "keys + sign + transfer + balance"; numbered sequence updated with
  N5; smoke-test hero list mentions Solana transfers explicitly.
- `docs/AGENT_HANDOFF.md`: update banner reflects N5 close-out.

## 2026-04-29 — Cursor agent · N4 (real TON signing, wallet v3R2 + BoC transfers)

**Summary**

Closes launch blocker §3.1' from `docs/LAUNCH_READINESS.md`. TON
wallets now derive canonical wallet **v3R2** contract addresses (the
same shape Tonkeeper / MyTonWallet / OpenMask issue), sign ed25519
messages locally, and build + sign broadcastable BoC transfer
messages. `Wallet.signing_supported = True` for all three chains
(Solana, EVM, TON). The architectural pivot from N3 (chain-specific
sign module behind a uniform `WalletService` interface) carries
through cleanly — no changes to the wallet schema, the secrets file,
the policy gate, or the cockpit shell.

**Backend**

- `requirements.txt`: pinned `tonsdk>=1.0,<2.0`.
- `backend/core/wallet/sign_ton.py` (new): `derive_ton_account`
  (32-byte ed25519 seed → wallet v3R2 contract address), `sign_ton_message`
  (pure ed25519, mirror of Solana primitive), `sign_ton_transfer`
  (build + sign external transfer message; returns
  `{boc, body_hash, address, to, amount_nanoton, seqno, workchain}`).
  Helpers `to_nano` and `parse_amount` (accepts nanoton ints,
  digit-strings, and decimal TON like ``"0.5"``).
- `backend/core/wallet/derive.py`: `derive_ton` now produces a
  canonical v3R2 user-friendly address (48-char base64url, starts
  with `EQ` / `UQ`) instead of the chain-prefixed hex placeholder.
  `sign_message` dispatches TON through ed25519 (PyNaCl).
- `backend/core/wallet/models.py`: `Wallet.signing_supported` returns
  `True` for **all three** chains now (Solana, EVM, TON).
- `backend/core/wallet/service.py`: new `sign_ton_transfer` async
  method (decrypts ed25519 seed, signs via `sign_ton.py`, returns
  the same shape as `sign_evm_transaction`).
- `backend/core/domains/packs/wallet/actions.py`: new
  `wallet.sign_ton_transfer` action (destructive, gated).
- `web_extras/routers/wallet.py`: new
  `POST /api/wallet/{id}/sign_ton_transfer` route + `parse_amount`
  validation; emits `wallet.ton_transfer_signed` Meeet event.

**Cockpit**

- `experiments/neural-showcase-v3/src/lib/wallet.ts`: new
  `signTONTransfer`, `TONSigned`, `TONTransferRequest` types. The
  existing per-row "prove ownership" button now lights up for TON
  wallets too (since `signing_supported` is `True`).

**Tests**

- `tests/test_wallet_ton_signing.py` (new): 23 cases — v3R2 address
  shape and determinism, invalid seed lengths, ed25519 signature
  verification via `nacl.signing.VerifyKey`, signature determinism,
  transfer BoC + body-hash shape, transfer determinism, seqno-changes-
  body-hash, negative-amount rejection, `parse_amount` decimal /
  digit-string / int / float / empty-string paths, HTTP route 200 /
  400 / 404 / invalid-amount, pack action ok / wrong-chain / missing-
  args / destructive-flag, end-to-end service signing, unknown-wallet
  raise.
- `tests/test_wallet_service.py`: `test_ton_address_shape` updated
  (real v3R2 prefix `EQ`/`UQ`, length 48, `signing_supported is
  True`); renamed `test_signing_unsupported_for_ton` →
  `test_ton_sign_message_round_trips` asserting 64-byte ed25519
  detached signature.
- `tests/test_wallet_router.py`: renamed `test_sign_ton_returns_400`
  → `test_sign_ton_round_trips`.
- `tests/test_wallet_pack.py`: renamed
  `test_sign_message_unsupported_chain_returns_error_envelope` →
  `test_sign_message_ton_round_trips`.

**Test deltas:** +23 pytest (480 → 503), 0 vitest. `tsc --noEmit`
clean. Full suite green.

**Docs**

- `docs/LAUNCH_READINESS.md`: §3.1' marked CLOSED; score card now
  shows ✅ across all three chains. Test totals refreshed.
- `docs/AGENT_HANDOFF.md`: update banner reflects N4 close-out;
  remaining blockers are operational signing keys + cinematic
  mnemonic polish (Claude lane).

## 2026-04-29 — Cursor agent · N3 (real EVM signing, secp256k1 + EIP-1559)

**Summary**

Closes launch blocker §3.1 from `docs/LAUNCH_READINESS.md`. EVM wallets
now do real BIP-44 derivation (`m/44'/60'/0'/0/{index}`), EIP-191
personal_sign, and EIP-1559 / legacy transaction signing — using
`eth-account` (canonical Ethereum signer in the Python ecosystem,
pulls in `coincurve` for libsecp256k1, `pycryptodome` for proper
Keccak-256, `rlp`, `eth-keys`). The Anvil canonical mnemonic
`test test … junk` deterministically yields
`0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266` (the same address Hardhat,
Foundry, and every Ethereum tutorial use), so anyone running
`anvil --mnemonic "test ... junk"` can replay the test fixtures
1-to-1 against a local node.

**Backend**

- `requirements.txt`: pinned `eth-account>=0.13,<0.14`.
- `backend/core/wallet/sign_evm.py` (new): `derive_evm_account`,
  `sign_evm_personal_message`, `recover_evm_personal_message`,
  `sign_evm_transaction`. All output hex strings normalised to `0x…`
  via `_ensure_0x` (works around the `hexbytes` version drift).
- `backend/core/wallet/derive.py`: `derive_evm` now takes optional
  `mnemonic`. With it → real BIP-44 path. Without it → legacy
  placeholder kept for old fixtures. `derive(...)` dispatcher updated.
  `sign_message(...)` now dispatches EVM through `sign_evm.py`.
- `backend/core/wallet/models.py`: `Wallet.signing_supported` now
  returns `True` for both Solana and EVM. TON still placeholder-only.
- `backend/core/wallet/service.py`: `_create_wallet_sync` threads the
  mnemonic through to `derive`. New `sign_evm_transaction` async
  method (decrypts wallet secret, signs via `sign_evm.py`, returns
  `{raw, hash, r, s, v}`).
- `backend/core/crypto/recovery.py`: `mnemonic_to_entropy` accepts
  any standard BIP-39 word count (12 / 15 / 18 / 21 / 24) so we can
  import third-party mnemonics like Anvil's 12-word phrase. Host
  identity recovery still mints 24 words.
- `backend/core/domains/packs/wallet/actions.py`: new
  `wallet.sign_evm_tx` action (destructive, gated by policy). Also
  updated `wallet.sign_message` description (EVM now supported).
- `web_extras/routers/wallet.py`: new
  `POST /api/wallet/{id}/sign_evm_tx` route, emits
  `wallet.evm_tx_signed` Meeet event.

**Cockpit**

- `experiments/neural-showcase-v3/src/lib/wallet.ts`: new
  `signEVMTransaction`, `EVMSigned`, `EVMTxRequest` types.
- `experiments/neural-showcase-v3/src/components/WalletPanel.tsx`:
  per-row "prove ownership" button (visible whenever
  `signing_supported`) that signs a timestamped string and shows a
  truncated signature line.

**Tests**

- `tests/test_wallet_evm_signing.py` (new): 17 cases, including:
  Anvil-mnemonic determinism (indices 0..2), EIP-55 checksum,
  personal_sign round-trip via `recover_evm_personal_message`, type-2
  envelope byte (`0x02`), legacy tx round-trip, hex-string coercion,
  invalid-tx ValueError, HTTP route 200 / 400 / 404, pack action
  ok / unsupported chain / destructive flag, end-to-end import of
  the Anvil mnemonic + tx broadcast hex round-trip.
- `tests/test_wallet_service.py`: renamed
  `test_signing_unsupported_for_evm` → `for_ton`. `evm_address_shape`
  now asserts `signing_supported is True` and EIP-55 mixed case.
- `tests/test_wallet_router.py`: renamed `sign_evm_returns_400` →
  `sign_ton_returns_400`. New `test_sign_evm_round_trips`.
- `tests/test_wallet_pack.py`: `sign_message_unsupported_chain_…` now
  uses TON; new `test_sign_message_evm_round_trips` asserting 65-byte
  EIP-191 signature.
- `experiments/neural-showcase-v3/src/lib/wallet.test.ts`: new
  EIP-55 checksum-preservation case for `shortenAddress`.

**Test deltas:** +19 pytest (461 → 480), +1 vitest (49 → 50).
`tsc --noEmit` clean. Full suite green.

**Docs**

- `docs/LAUNCH_READINESS.md`: §3.1 marked CLOSED, score card updated
  (EVM column flipped to ✅), TON now standalone partial entry. Test
  numbers refreshed.

## 2026-04-29 — Cursor agent · N1 + N2 (wallet balance reader + agent autopilot) + LAUNCH_READINESS audit

**Summary**

Two follow-ups on top of M1/M2 to close the most visible UX gaps and
make the wallet panel feel alive instead of skeletal, plus a
structured launch-readiness document so the project lead has a
single-page GO / NO-GO view.

**N1 — Wallet balance reader (live JSON-RPC):**

- `backend/core/wallet/balance.py` (new): stdlib `urllib`-based JSON-RPC
  client. Per-chain readers `fetch_solana_balance`,
  `fetch_evm_balance`, `fetch_ton_balance`. Each returns a `Balance`
  with `raw / decimals / symbol / display`. RPC URLs configurable via
  `TARS_SOLANA_RPC_URL`, `TARS_EVM_RPC_URL`, `TARS_TON_RPC_URL` (sane
  defaults: api.mainnet-beta.solana.com, eth.llamarpc.com,
  toncenter.com). All transport failures surface as `BalanceError`.
- `web_extras/routers/wallet.py`: new `GET /api/wallet/{id}/balance`
  endpoint. Returns `ok=true` with the balance dict on success;
  `ok=false` with a structured error message on RPC failure (never
  500s — the cockpit shows a friendly retry pill).
- `backend/core/domains/packs/wallet/actions.py`: new `wallet.balance`
  action (read, non-destructive). Agents can now call it the same way
  they call `wallet.address`.
- `experiments/neural-showcase-v3/src/lib/wallet.ts` (`fetchBalance`,
  `BalanceReading`, `BalanceResult`) + `WalletPanel.tsx` (per-row
  "balance" button → live `display SYMBOL` line, errors rendered
  inline in alert colour).
- Tests: `tests/test_wallet_balance.py` (15 cases — Solana lamports
  decoding, EVM hex-wei decoding, TON nano decoding, zero balance,
  RPC error path, transport failure path, garbage response, env
  vs override RPC URL precedence, HTTP route round-trip + 404,
  pack action plumbing, destructive flag).

**N2 — Agent autopilot loop:**

- `backend/core/agents/autopilot.py` (new): `tick_once()` lists active
  agents whose `metadata.autopilot=true`, takes the oldest pending
  task per agent, and runs it through the council orchestrator.
  `autopilot_loop()` is a background coroutine that calls `tick_once`
  every `TARS_AGENTS_AUTOPILOT_INTERVAL_S` seconds (default 30,
  setting it to 0 short-circuits cleanly). Per-task crashes are
  isolated — a single broken task can never kill the loop.
- `web_extras/app.py`: lifespan now spawns the autopilot loop next to
  the existing meeet replay loop; both are cancelled cleanly on
  shutdown.
- `web_extras/routers/agents.py`: `POST /api/agents/{id}/autopilot
  ?enabled=true|false` toggles the flag in agent metadata. `POST
  /api/agents/autopilot/tick` forces an immediate tick (useful for
  tests + the cockpit "tick" button). Both emit
  `agent.autopilot.{toggled,dispatch,failed}` to the meeet store.
- `experiments/neural-showcase-v3/src/lib/agents.ts`: `setAutopilot`,
  `autopilotTickNow`, `isAutopilot` helpers. `AgentsPanel.tsx`: per-
  agent autopilot on/off pill (emerald glow when active) + global
  "tick" button next to "refresh".
- Tests: `tests/test_agents_autopilot.py` (8 cases — toggle persists,
  unknown agent 404, tick runs pending task, agents without flag
  skipped, paused agents skipped, only one task per tick per agent
  to avoid sibling starvation, loop short-circuits on interval=0,
  force-tick endpoint).

**LAUNCH_READINESS audit:**

- `docs/LAUNCH_READINESS.md` (new): structured GO/NO-GO scorecard,
  per-surface status, three explicit blockers (real EVM signing,
  operational signing keys, cinematic mnemonic polish), three launch
  tiers (private alpha → public alpha → hosted SaaS), a 5-minute
  smoke test, and a minimum-to-green table. Built from the actual
  test totals — not from intent. Calibrates expectations for the
  project lead and Claude alike.

**Test totals after this session:** 461 pytest · 49 vitest · 11 swift
· `tsc --noEmit` clean.

---

## 2026-04-29 — Cursor agent · M1 + M2 (multi-agent surface + crypto wallets)

**Summary**

Two functional blocks landed in one session — TARS now has a true
multi-agent layer and per-user crypto wallets that agents can
propose/sign through the policy gate. Stdlib + `pynacl` only; no new
dependencies.

**M1 — Multi-agent registry + task queue:**

- `backend/core/agents/__init__.py`, `models.py`, `store.py`,
  `runner.py` (new): `Agent` + `Task` dataclasses, SQLite-backed
  `AgentStore` (WAL, `~/.tars/agents.sqlite` by default), explicit
  state machines (`active|paused|archived`,
  `pending|running|awaiting_confirmation|done|failed|cancelled`)
  with valid-transition checks, async runner that drives every
  task through the council orchestrator (`CouncilOrchestrator`)
  using the agent's `pack_slug` persona + optional system prompt.
- `web_extras/routers/agents.py` (new): `POST /api/agents`,
  `GET /api/agents`, `GET /api/agents/{id}`,
  `PATCH /api/agents/{id}` (status / fields), `POST
  /api/agents/{id}/tasks`, `GET /api/agents/{id}/tasks`,
  `GET /api/tasks/{id}`, `POST /api/tasks/{id}/run`,
  `POST /api/tasks/{id}/cancel`. Emits `agent.created`,
  `agent.patched`, `agent.task.{queued,started,completed,failed,
  cancelled}` to the meeet store with `trace_id`s so paired devices
  replay the per-agent timeline.
- `web_extras/app.py`: `agents_router` registered.
- Cockpit: `experiments/neural-showcase-v3/src/lib/agents.ts`
  (typed CRUD + `useAgents` hook + `statusBadgeClass`),
  `experiments/neural-showcase-v3/src/components/AgentsPanel.tsx`
  (mint, pause/resume/archive, queue + run task with inline
  council-shaped result, cancel pending task). Header gets an
  `agents` link; new `#ops` section sits above the security row.
- Tests: `tests/test_agents_router.py` (15 cases — create/list,
  invalid pack rejection, archive filtering, status transition
  guard, queue → run → done flow, cancel terminal tasks, meeet
  event emission).

**M2 — Per-user crypto wallets + wallet domain pack:**

- `backend/core/wallet/__init__.py`, `models.py`, `encoding.py`
  (Base58 + SHA3-256 placeholder), `derive.py` (Solana via
  ed25519/PyNaCl, EVM + TON deterministic placeholders flagged
  `signing_supported=False`), `service.py` (new): public-only
  `Wallet` rows in SQLite (`~/.tars/wallets.sqlite`), private
  material in `~/.tars/wallet_secrets.json` encrypted with
  XChaCha20-Poly1305 (PBKDF2 over `TARS_WALLETS_PASSPHRASE`).
- `web_extras/routers/wallet.py` (new): `POST /api/wallet`
  (returns the 24-word mnemonic ONCE, never persisted),
  `POST /api/wallet/import`, `GET /api/wallet`, `GET
  /api/wallet/{id}`, `DELETE /api/wallet/{id}`,
  `POST /api/wallet/{id}/sign`, `POST /api/wallet/{id}/build_send`.
  Emits `wallet.created`, `wallet.imported`, `wallet.removed`,
  `wallet.signed`, `wallet.send_built` to the meeet store.
- `backend/core/domains/packs/wallet/` (new pack): `wallet.list`
  (read), `wallet.address` (read), `wallet.propose_send`
  (destructive — gated), `wallet.sign_message` (destructive).
  Awareness source `wallet.summary` exposes a roster of
  addresses by chain (no balances, no secrets). Auto-registered.
- Cockpit: `experiments/neural-showcase-v3/src/lib/wallet.ts`
  (typed client + `useWallets`, `shortenAddress`,
  `chainBadgeClass`),
  `experiments/neural-showcase-v3/src/components/WalletPanel.tsx`
  (mint with mnemonic-reveal, copy address, build send envelope,
  remove). Mounted next to `AgentsPanel` in `#ops`.
- Tests:
  - `tests/test_wallet_service.py` (13 cases — mnemonic
    determinism, base58 round-trip, ed25519 signing verifies
    against the public key, secrets file does not contain plain
    bytes, EVM signing rejected, delete drops the encrypted item).
  - `tests/test_wallet_router.py` (10 cases — mnemonic shown
    once, import round-trips, sign is gated per chain, build-send
    envelope shape, delete cleans up, meeet event emission).
  - `tests/test_wallet_pack.py` (8 cases — pack registered,
    destructive flags pinned, action handlers reach the wallet
    service end-to-end).

**Documentation:**

- `docs/handoff-claude.md` § 6.1 / § 6.2: handoff lanes for
  Claude's parallel design pass (specifically the cinematic
  mnemonic-reveal moment) + an explicit Cursor↔Claude
  coordination contract so contract-bumping changes always go
  through a contract test first.
- `docs/AGENT_HANDOFF.md`: «Next Cursor block» updated with the
  new M1/M2 rows + an updated test totals line (438 pytest, 49
  vitest, 11 swift).

**Test totals after this session:** 438 pytest · 49 vitest ·
11 swift · `tsc --noEmit` clean.

**Open follow-ups (not blocking):**

- Real EVM signing (needs `coincurve` / `eth-account` or libsecp256k1
  via PyNaCl in a follow-up phase).
- Balance reads via configurable RPC (`TARS_EVM_RPC_URL` etc.).
- Agent-to-agent task handoff (one agent files a task into another
  agent's inbox); the storage layer already supports it.
- Visual brand pass on the mnemonic-reveal screen
  (`<WalletPanel />`'s amber alert) — Claude lane.

---

## 2026-04-29 — Cursor agent · A1 + L1 + L2 + L3 (multi-platform release loop)

**Summary**

Four blocks from «Next Cursor block» landed in a single dense session.

**A1 — Tauri pyoxidizer sidecar (desktop):**

- `desktop/pyoxidizer.bzl` (new): CPython 3.12 + repo (`backend`,
  `web_extras`) → `tars-backend(.exe)`. Boots uvicorn against
  `web_extras.app:app` on `127.0.0.1:$PORT` (default 8765).
- `desktop/src-tauri/src/sidecar.rs` (rewritten): real spawn path
  (`TARS_BACKEND_BIN` → bundled binary → `python3 serve.py`),
  TCP+HTTP `/health` poll (250 ms · 15 s ceiling), `SidecarHandle`
  drop with SIGTERM + 5 s grace + SIGKILL. Emits exactly one of
  `desktop.sidecar.{started,failed,exited}` per lifecycle stage.
- `desktop/src-tauri/sidecar-events.schema.json` (new, v1.0.0):
  single source of truth for the event names + payload shapes.
- `tests/test_desktop_sidecar_events_contract.py` (4 cases): pins
  schema set + asserts each event is emitted from the Rust source
  with all required JSON keys present in the `json!{…}` literal.

**L1 — iOS pairing-first slice (`mobile/ios/TARSCompanion/`):**

- `PairingClient.swift` async URLSession driver (`POST /api/pairing/begin`
  + `GET /api/pairing/status`), `PairingCrypto.swift` (CryptoKit X25519
  ephemeral + base64 + fingerprint formatter), `PairingEnvelope.swift`
  parser (JSON + `tars-pair://`), `PairingKeychain.swift` (in-memory
  + Security.framework under `world.meeet.tars.<device_id>`),
  `PairingViewModel.swift` (idle → scanning → awaitingHostAccept →
  linked|failed) and `PairingView.swift` SwiftUI shell. AVFoundation
  QR scanner in `QRScannerView.swift`.
- `Package.swift` upgraded to also build on macOS 13+ for headless CI.
- `swift test` runs **11** unit tests (decoders, envelope parser,
  fingerprint formatter, in-memory secret store).

**L2 — Android pairing-first slice (`mobile/android/TARSCompanion/`):**

- Mirror of L1 in Kotlin/Compose: `crypto/PairingCrypto.kt`
  (java.security XDH X25519, API 31+), `net/PairingClient.kt`
  (OkHttp + org.json), `PairingEnvelopeParser.kt`,
  `PairingViewModel.kt` (StateFlow + viewModelScope coroutines),
  `ui/PairingScreen.kt` Compose, `PairingActivity.kt`.
- Gradle build files (`build.gradle.kts`, `app/build.gradle.kts`,
  `AndroidManifest.xml`). JVM-only `PairingDecodersTest.kt`.
- `tests/test_mobile_pairing_contract.py` (10 cases): pins iOS ↔
  Android symmetry (contract version 1.0.0, begin response field
  set, status state set, envelope parser surfaces, phase machine
  states, fingerprint formatter implementation choice).

**L3 — Tauri desktop release workflow with minisign:**

- `.github/workflows/release-desktop.yml` (new): triggered by
  `desktop-v*.*.*` tag; matrix builds darwin-{aarch64,x86_64},
  windows-x86_64, linux-x86_64; runs `pyoxidizer build`, stages the
  sidecar into `src-tauri/resources`, runs `pnpm tauri:build`, then
  invokes `desktop/scripts/sign-artifacts.sh` with the
  `TAURI_SIGNING_PRIVATE_KEY` secret. Final job calls
  `python -m backend.core.product.publish staged --updater-out
  dist/updates --updater-alias latest` to produce the per-target
  Tauri updater channel JSON files.
- `desktop/scripts/sign-artifacts.sh` (new, executable): walks the
  bundle dir, signs every installer with `tauri signer sign`
  (passes `--private-key` from env, optional `--password`), and
  fails loud if any `<artifact>.sig` sidecar is missing. Skips
  cleanly in dev mode when no key is configured.
- `tests/test_release_desktop_workflow.py` (9 cases): pins tag
  prefix, secret env-var names, full target matrix, the
  `--updater-out`/`--updater-alias latest` invocation, and the sign
  script's safety properties (skip on no secret, fail-loud on
  missing sidecar, executable mode + shebang).

**Tests:**

- pytest **392** (+23: 4 sidecar contract, 10 mobile contract, 9
  release-desktop contract).
- vitest **41**, `tsc --noEmit` clean (no React surface change).
- `swift test` (mobile/ios/TARSCompanion) **11** passing.

---

## 2026-04-29 — Cursor agent · K5 vault secrets panel + merged status API

**Summary**

**K5 — Domain-pack secret / Keychain UX in cockpit:**

- `web_extras/routers/vault.py`: `GET /api/vault/status` merges
  `KNOWN_KEYS` with registered packs' `auth_vault_keys()` via
  `status_for_keys` (e.g. SMTP keys listed with LLM keys).
- `VaultSecretsPanel.tsx`: `useVaultStatus` + env / keychain / missing
  badges; copyable macOS `security add-generic-password` per key; header
  `keys` → `#vault-keys`; `#security` is three columns on xl.
- `vault.ts`: `macOSKeychainAddCommand`, `VAULT_KEYCHAIN_ACCOUNT`;
  `vault.test.ts` pins the shell line.

**Tests:** pytest **369** (+1); vitest **41** (+3); `tsc --noEmit` clean.

---

## 2026-04-29 — Cursor agent · K4 cockpit pairing + recovery UI

**Summary**

Continuation: React surfaces wired to Phase L5 K3 libs:
**`<RecoverySetup />`**, **`PairingPanel />`**, **`/cockpit` integration.**

- `RecoverySetup.tsx`: 3-step flow (generate → 4×6 word grid +
  written-down checkbox → verify typed phrase → `verifySeed`).
  No clipboard. Optional `onSkip`; `recovery.shown` still emitted server-side.
- `PairingPanel.tsx`: `getIdentity` + fingerprint + pubkey copy +
  `accept_token` paste → `acceptPairing`; device list +
  revoke.
- `Cockpit.tsx`: `#security` section (pairing + backup card), overlay
  when `vault.configured && vault.freshly_minted` and no verified
  fingerprint/skip (`localStorage` keys); manual "Open backup wizard";
  toast on verify; header link to `#security`.

**Tests:** vitest 38 unchanged (lib-only); pytest 368 unchanged;
`tsc --noEmit` clean.

---

## 2026-04-29 — Cursor agent · K2 updater + K1 host vault + K3 cockpit clients

**Summary**

Continuation of the same multi-block session. Three more blocks from
the «Next Cursor block» backlog landed: **K2** (Tauri updater channel
publisher), **K1** (persistent host keyring), and **K3** (cockpit
typed clients for pairing + recovery). Test totals are now
**368 pytest + 38 vitest** green; cockpit `tsc --noEmit` clean.

**K2 — Tauri updater channel publisher**

- `backend/core/product/updater.py` (new): pure stdlib module that
  builds a `TauriChannel` from sniffed artifacts and writes the per-
  target `<target>/<version>.json` files Tauri's updater consumes.
  Mapping table covers `darwin-aarch64 / darwin-x86_64 /
  darwin-universal / windows-x86_64 / windows-aarch64 / windows-i686 /
  linux-x86_64 / linux-aarch64`. Reads `<artifact>.sig` sidecar files
  produced by `tauri signer sign`; falls back to an empty signature
  string when no sidecar is present (the safe dev-mode default — the
  Tauri client refuses unsigned updates unless `pubkey` is also empty).
- `backend/core/product/publish.py` extended with `--updater-out` and
  `--updater-alias` flags. `--updater-alias latest` writes
  `<target>/latest.json` next to `<target>/<version>.json` so the
  marketing site can hard-link a stable URL.
- `tests/test_product_updater.py` (8 cases): target-mapping coverage,
  unknown-target drop, sidecar signature pickup, signed-over-unsigned
  preference, file-output shape, CLI dry-run, CLI without `--updater-out`
  must skip the channel.
- `desktop/README.md` updated to mark updater publishing as shipped
  (real minisign signing key still lives in CI).

**K1 — Persistent host keyring**

- `backend/core/vault/file_vault.py` (new): `FileKeyringVault`
  implements the `KeyringVault` ABC, persisting the X25519 host
  identity into a single JSON file (default
  `~/.tars/host_identity.json`). Secret half is **always** encrypted
  at rest with XChaCha20-Poly1305 keyed by PBKDF2-HMAC-SHA512 (200_000
  iterations, 16-byte salt, 24-byte nonce). File is written with
  `0o600` permissions via a temp-file + `os.replace` for crash
  safety; the loader does a strict permission check on POSIX hosts
  and raises `VaultPermissionError` if anything has chmod'd it
  wider. AAD = `device_id` so swapping the secret for another
  vault file's secret breaks the AEAD tag. The decoder also
  re-derives the public key from the decrypted secret and rejects
  mismatches.
- `backend/core/vault/__init__.py` upgraded to expose **both** the
  new host-identity vault types and the existing domain-pack secret
  resolver (`KNOWN_KEYS`, `get_secret`, `list_known`,
  `status_for_keys`, `SecretRef`) — they live behind a single import
  path now.
- `backend/core/pairing/store.py`: `PairingStore` accepts an optional
  `vault=` keyword arg. On init it loads the persisted identity if
  present, or mints + saves a fresh one when a vault is set but
  empty. New helpers expose `identity_was_loaded`,
  `identity_was_freshly_minted`, and `recovery_fingerprint`. New
  `rotate_host_identity()` method writes a new keypair through the
  vault and records the rotation timestamp. `get_pairing_store()`
  picks the default vault from
  `TARS_PAIRING_VAULT={enabled,disabled,…}`,
  `TARS_PAIRING_VAULT_PATH`, `TARS_PAIRING_VAULT_PASSPHRASE` env
  vars.
- `web_extras/routers/pairing.py`: new `GET /api/pairing/identity`
  endpoint surfaces vault status (`configured`, `loaded_from_disk`,
  `freshly_minted`) + `recovery_fingerprint` so the cockpit's
  first-launch flow can decide whether to show the recovery prompt.
- Tests: `tests/test_vault_file.py` (11 cases — round-trip with /
  without passphrase, wrong-passphrase rejection, 0o600 permissions,
  permission-widening rejection, atomic write, rotate semantics,
  ciphertext tamper rejection, public-key tamper rejection, garbage
  file, idempotent clear) and `tests/test_pairing_vault_integration.py`
  (6 cases — identity persists across restarts, no-vault keeps the
  legacy fresh-mint behaviour, rotate semantics, end-to-end pairing
  with a vault, identity endpoint reports vault status). The two
  pre-existing pairing test files now `monkeypatch.setenv("TARS_PAIRING_VAULT", "disabled")`
  so they don't pollute the developer's `~/.tars/`.

**K3 — Cockpit typed clients**

- `experiments/neural-showcase-v3/src/lib/pairing.ts` (new): typed
  wrappers over `POST/GET /api/pairing/*` plus pure helpers for
  fingerprint formatting / matching and base64url-encoded QR
  payloads. Visual-side React components stay Claude-owned;
  this file is framework-free so vitest can exercise it without a
  DOM.
- `experiments/neural-showcase-v3/src/lib/recovery.ts` (new): typed
  wrappers over `POST/GET /api/recovery/*` plus UX helpers
  (`normaliseMnemonic`, `chunkMnemonic` for the 4×6 grid,
  `mnemonicsMatch`, `isCompleteAttempt`).
- Vitest coverage: `pairing.test.ts` (14 cases) covers fingerprint
  helpers, QR round-trip, fetch-stubbed HTTP wrappers, error path;
  `recovery.test.ts` (12 cases) covers normalisation, grid chunking,
  completeness check, fetch-stubbed HTTP wrappers, error path.

**Tests** — full suite green:

- pytest: **368 passed** (+25 from previous: 8 updater + 11 vault +
  6 vault integration). Pre-existing voice-synthesis flake on
  cross-test store pollution went away after the new isolation.
- vitest: **38 passed** (+26 from previous: 14 pairing + 12 recovery).
- `tsc --noEmit`: clean.

**Files**

- `backend/core/product/updater.py` (new)
- `backend/core/product/publish.py` (CLI extended)
- `backend/core/vault/{__init__.py,file_vault.py}` (init merged + new file)
- `backend/core/pairing/store.py` (vault integration)
- `web_extras/routers/pairing.py` (`/identity` endpoint)
- `experiments/neural-showcase-v3/src/lib/{pairing,recovery}.ts` (new)
- `experiments/neural-showcase-v3/src/lib/{pairing,recovery}.test.ts` (new)
- `tests/{test_product_updater,test_vault_file,test_pairing_vault_integration}.py` (new)
- `tests/test_pairing_{contract,envelope_e2e}.py` (env-var isolation fix)
- `desktop/README.md` (K2 status bumped)

**Next pending blocks**

A1 (pyoxidizer sidecar) — still platform-coupled, deferred to
dedicated CI session. L1/L2 (iOS/Android pairing-first slices) —
still need Xcode / Android Studio to validate, deferred. Everything
else from the L5 + L9 K-tier backlog is shipped.

---

## 2026-04-29 — Cursor agent · L5 contract 1.1.0 + real crypto + recovery seed + Claude handoff

**Summary**

Continuation of the same multi-block session. Phase **L5** functionally
complete on the host: meeet contract bumped to **1.1.0** (additive),
real **X25519 + XChaCha20-Poly1305** sync envelope shipped, **BIP-39
24-word recovery seed** flow + endpoints landed, and a structured
hand-off package for Claude was written. Test totals now **343 pytest
+ 12 vitest** green.

**meeet contract → 1.1.0 (`backend/core/meeet/`)**

- `events.py` — `TARSEvent` gains optional `ciphertext` (str) +
  `envelope` (mapping) fields. When both are set, `to_dict()`
  auto-bumps `contract_version` to `1.1.0`; otherwise it stays
  `1.0.0`. Two new module-level constants
  (`BASELINE_CONTRACT_VERSION = "1.0.0"`,
  `ENCRYPTED_CONTRACT_VERSION = "1.1.0"`) are the source of truth.
- `store.py` — schema + migrations gain `ciphertext TEXT` and
  `envelope TEXT` columns. `_insert_sync`, `_row_to_event`, and
  `replay_unpushed` all round-trip the new fields. Existing 1.0.0
  rows stay untouched.
- `client.py` — `emit()` accepts `ciphertext=` and `envelope=` kwargs;
  forwards them to `TARSEvent`.
- 9 new tests (`tests/test_meeet_contract_v11.py`) pin both flows;
  the existing `tests/test_meeet_contract.py` still passes
  unchanged.

**Real L5 crypto (`backend/core/crypto/`)**

- `envelope.py` — XChaCha20-Poly1305 (24-byte nonce, 32-byte key) +
  X25519 long-term identity keys. ``encrypt_event`` seals the
  payload, wraps the per-event content key for every recipient via
  libsodium's `SealedBox`, and binds AAD = ``trace_id|kind`` so
  tampering with metadata invalidates the AEAD tag. ``decrypt_event``
  is the matching primitive; ``decode_envelope`` is a defensive
  parser. `pynacl>=1.5` added to `requirements.txt` (a fresh file —
  pinning the previously-implicit deps).
- `pairing/store.py` — host now mints a long-term X25519 keypair on
  init; `host_public_key_b64` exposed alongside `host_id` /
  `host_fingerprint`; `client_epk` validated on `begin` (32 bytes
  base64) — broken QR codes 400 fast. Linked devices get a
  per-device `DeviceKey` exposed via `device_keys()` so the
  envelope module can encrypt-to-all-devices in one call. `revoke`
  also drops the cached pubkey.
- `tests/test_crypto_envelope.py` (10 cases): single + multi
  recipient round-trip, wrong-key rejection, unknown device
  rejection, AAD-tamper rejection, empty-recipient rejection,
  invalid-length-pubkey rejection, garbage envelope decode,
  base64 wrapped-key shape sanity.
- `tests/test_pairing_envelope_e2e.py` (3 cases): pair → encrypt →
  decrypt with the actual paired key; emit through the meeet client
  and decrypt back from the SQLite store; revoke drops the device
  pubkey.

**Recovery seed (`backend/core/crypto/recovery.py`, `web_extras/routers/recovery.py`)**

- Stdlib-only BIP-39 implementation (256-bit entropy → 24 words →
  PBKDF2-HMAC-SHA512 seed → first 32 bytes → X25519 master key).
- Canonical 2048-word English wordlist bundled at
  `backend/core/crypto/data/bip39_english.txt`. Loader caches it
  via `lru_cache`.
- `RecoverySeed` carries the mnemonic + a 12-char SHA-256
  fingerprint that is **safe to log** (the mnemonic itself never
  hits any audit trail).
- `seed_to_master_key(seed, host_id)` builds an X25519 `DeviceKey`
  from the BIP-39 seed — drop-in input for the same
  `backend.core.crypto.envelope` primitives.
- HTTP endpoints: `POST /api/recovery/generate`,
  `POST /api/recovery/verify`, `GET /api/recovery/wordlist/info`.
  Both POST routes emit `recovery.{shown,verified}` events to the
  meeet store carrying **only the fingerprint** + `word_count` —
  no mnemonic ever lands in storage.
- `tests/test_recovery_seed.py` (15 cases): wordlist sanity, random
  entropy round-trip, all-zero-entropy known vector, exact PBKDF2
  output match (catches silent algo drift), passphrase changes
  seed, master-key derivation length, invalid-word rejection,
  wrong-word-count rejection, tampered-checksum rejection,
  HTTP generate / verify / wordlist endpoints, audit event payload
  pin.

**Claude handoff (`docs/handoff-claude.md`)**

- Captured live API outputs (manifest, latest, version, pairing
  begin, recovery wordlist + generate) for Claude to copy-paste
  during the brand pass.
- Concrete polish task list per surface (`<DownloadStrip />`,
  `<CommandPalette />`, `<ThreadTimeline />`) with priority order.
- Pairing + recovery UX sketches (host fingerprint pulse, 4×6 word
  grid, "I have written this down" gate).
- meeet.world SSR integration recipe + deep-link policy.
- Sensitive-data handling rules (no clipboard for mnemonic, never
  log secrets, MITM-pin the host pubkey).
- Quick-start commands for local dev + the publish CLI.

**Pairing router updates**

- `host_public_key` exposed on the `begin` response.
- `client_epk` validation surfaces a 400 with `invalid_client_epk`
  detail when the client posts a non-32-byte base64 key.
- `tests/test_pairing_contract.py` reworked: real X25519 keys
  generated per test via `_fresh_epk_b64()`, new test for the 400
  on bad keys, asserts the new `host_public_key` field.

**Tests** — full suite **343 pytest + 12 vitest** green:

- New: `test_meeet_contract_v11.py` (9), `test_crypto_envelope.py`
  (10), `test_pairing_envelope_e2e.py` (3), `test_recovery_seed.py`
  (15) = **+37 pytest**.
- Updated: `test_pairing_contract.py` to use real X25519 keys.

**Files**

- `backend/core/meeet/{events.py,store.py,client.py,__init__.py}`
- `backend/core/crypto/{__init__.py,envelope.py,recovery.py}` (new)
- `backend/core/crypto/data/bip39_english.txt` (canonical wordlist)
- `backend/core/pairing/store.py` (real X25519 plumb)
- `web_extras/routers/{pairing.py,recovery.py}` (recovery router new)
- `web_extras/app.py` (mount recovery)
- `requirements.txt` (new — explicit dep pinning incl. `pynacl>=1.5`)
- `tests/{test_meeet_contract_v11,test_crypto_envelope,test_pairing_envelope_e2e,test_recovery_seed}.py` (new)
- `tests/test_pairing_contract.py` (real X25519 keys + new field assertions)
- `docs/handoff-claude.md` (new)
- `docs/contracts/L5_PAIRING_DRAFT.md` (status update — DRAFT → SHIPPED v1)

**Smoke**

- `python -m pytest tests/` → **343 passed** in ~3 s.
- `npx vitest run` (cockpit) → **12 passed**.
- `npx tsc --noEmit` (cockpit) → clean.
- Manual `curl localhost:8765/api/recovery/generate` round-trips a
  fresh 24-word phrase and emits one `recovery.shown` event with
  fingerprint-only payload.

---

## 2026-04-29 — Cursor agent · L5 pairing endpoints + publish CLI + cockpit Vitest

**Summary**

Continuation of the same ~10-h session: turned the L5 *draft* into
**shape-correct, mock-crypto endpoints** so the cockpit, the iOS app,
and the Android app can all build against real wire shapes; landed
the release publishing CLI that produces the `~/.tars/releases.json`
the manifest API serves; added a Vitest suite for the new cockpit
download client. Full suite **305 pytest + 12 vitest** green.

**L5 pairing endpoints (`backend/core/pairing/`, `web_extras/routers/pairing.py`)**

- `backend/core/pairing/store.py` — in-memory `PairingStore` with
  `begin / accept / reject / status / revoke / list_devices` async
  methods. Idempotent `begin` (re-using the same `pair_id` returns
  the same record while it's still pending). Stable
  `host_fingerprint` digest (SHA-256 of `host_id:pair_id`,
  3-group dash format).
- `web_extras/routers/pairing.py` mounts six endpoints — `POST
  /api/pairing/{begin,accept/{token},reject/{token},revoke}`,
  `GET /api/pairing/{status,devices}` — all wrapped in `trace_scope`
  and emitting `pair.attempted / linked / rejected / revoked` events
  into the meeet store so replay on a paired device gives the same
  audit trail as policy actions.
- Mounted in `web_extras/app.py`. Crypto stays mock for now (the
  `client_epk` round-trips but isn't validated as a real X25519 key);
  when real envelope code lands, only the `begin / accept` internals
  change — wire shape stays.

**Release publishing CLI (`backend/core/product/publish.py`)**

- `python -m backend.core.product.publish <build-dir> --version=<v>`
  walks the directory, **sniffs** artifacts (`.dmg → macos`,
  `.exe → windows`, `.apk → android`, …), computes **SHA256**, and
  writes a contract-shaped `releases.json` (default
  `~/.tars/releases.json`, override via `TARS_RELEASES_PATH`).
- Architecture is sniffed from the filename (`arm64`, `x64`,
  `universal`, `x86`, `any`) so Tauri's default
  `TARS_<v>_x64-setup.exe` / `TARS-<v>-arm64.dmg` shapes round-trip
  without manual config.
- Idempotent re-publishing: re-running with the same
  `version + channel` **replaces** the previous release entry
  (other versions are preserved newest-first).
- `--copy-to <dir>` mirrors the artifacts into a staging folder for
  the upload pipeline; `--dry-run` prints the manifest to stdout.
- Loader (`backend/core/product/manifest.py`) immediately picks up
  the resulting file via the same `TARS_RELEASES_PATH` env var so the
  flow is `publish → /api/product/downloads → <DownloadStrip />`
  without a server restart.

**Cockpit Vitest (`experiments/neural-showcase-v3/`)**

- Added `vitest@^2` + `jsdom@^25` as dev deps; wired
  `vite.config.ts` to register the test runner with `jsdom` env;
  package scripts gain `test` / `test:watch`.
- `src/lib/downloads.test.ts` — 12 cases pinning `detectPlatform` UA
  edges (Safari Apple Silicon spoofing Intel, Chrome on M-series,
  Mac Intel, Windows 10, Ubuntu, iPhone, Pixel/Android, unknown
  console UAs) and `pickArtifact` fallbacks (exact arch → universal
  → any → null).
- Fixed an ordering bug in `detectPlatform`: Android UA contains
  "Linux", iPhone UA contains "Mac OS X", so mobile checks now run
  **before** desktop ones.
- `Makefile` gains `cockpit-test` and `test-all` targets.

**Tests** — full suite now **305 pytest + 12 vitest** green:

- `tests/test_pairing_contract.py` (12 cases) — `begin` envelope
  shape, idempotency, kind validation; `accept` linking + 404 on
  unknown token + 409 after reject; `status` pending/linked/404;
  `revoke` + 404 on unknown device; `pair.{attempted,linked}` events
  emitted with the right payload.
- `tests/test_product_publish.py` (9 cases) — sniffer recognises
  `.dmg`/`.exe`, base-URL substitution, missing-dir error, replace
  same-version-channel, keep other versions, CLI writes-and-loader-
  picks-up, `--dry-run` emits without writing, returns 1 when no
  artifacts, `--copy-to` mirrors files.
- `experiments/neural-showcase-v3/src/lib/downloads.test.ts`
  (12 cases) — see above.

**Files**

- `backend/core/pairing/{__init__.py,store.py}` (new module)
- `backend/core/product/publish.py` (new CLI)
- `web_extras/routers/pairing.py` (new)
- `web_extras/app.py` (mount pairing router)
- `tests/test_pairing_contract.py`, `tests/test_product_publish.py`
- `experiments/neural-showcase-v3/{package.json,vite.config.ts}`
- `experiments/neural-showcase-v3/src/lib/{downloads.ts,downloads.test.ts}`
- `Makefile` (cockpit-test, test-all targets)

**Smoke**

- `python -m pytest tests/` → **305 passed**.
- `npx vitest run` (cockpit) → **12 passed**.
- `npx tsc --noEmit` (cockpit) → clean.
- Manual `python -m backend.core.product.publish ./build/release
  --version 1.0.0 --notes "smoke"` writes a valid `releases.json`,
  verified by re-loading via `load_manifest()` and curling
  `/api/product/downloads`.

---

## 2026-04-29 — Cursor agent · L9 desktop scaffold + product manifest API + L5/L10 contracts

**Summary**

Single ~10-h session executing the full **«Next Cursor block»** backlog
from `AGENT_HANDOFF.md` plus two stretch items (Landing download CTAs
wired to the new manifest, mobile companion stubs). Lands the
**website-direct download** distribution channel end-to-end on the
backend + cockpit, and pins the **L5 pairing** + **download manifest**
wire shapes so Claude / mobile / meeet.world can build against them
without inventing payloads.

**Phase L9 desktop scaffold (`desktop/`)**

- New folder `desktop/` with full Tauri 2 layout: `package.json`
  (`pnpm tauri:dev`/`build`/`release`), `src-tauri/Cargo.toml` (deps:
  `tauri-plugin-shell` / `notification` / `updater`),
  `tauri.conf.json` (CSP allows `127.0.0.1:8765` + `meeet.world`,
  `tauri-plugin-updater` endpoint pinned to
  `meeet.world/updates/{target}/{current_version}.json`), `src/main.rs`
  (window + sidecar bring-up hook), `src/sidecar.rs` (TODO: pyoxidizer
  bundle of FastAPI as a child process — non-fatal warn until that
  slice lands). `scripts/package-cockpit.sh` copies the v3 cockpit
  dist into Tauri's web root before `tauri build`.
- `desktop/README.md` documents the v1 acceptance criteria
  (`tauri:dev` opens the cockpit, signed `.dmg`/`.exe` shaped
  artifacts, `tauri-plugin-updater` wired to the production endpoint).
- All paths kept stable in git via small placeholder READMEs in
  `src-tauri/web/` and `src-tauri/icons/`.

**Public download manifest (`backend/core/product/`, `web_extras/routers/product.py`)**

- New `backend/core/product/manifest.py` — stdlib-only loader for
  `~/.tars/releases.json` (override via `TARS_RELEASES_PATH`) with a
  bundled `DEFAULT_MANIFEST` so the API never returns 5xx pre-release.
- `resolve_url()` resolves relative artifact paths against
  `TARS_DOWNLOAD_BASE_URL` at request time so the file on disk stays
  human-friendly while consumers always see absolute URLs.
- Coercers reject unknown `os` / `arch` / `kind` values with a
  `WARNING` (soft-fail — keep the rest of the manifest intact).
- New `web_extras/routers/product.py` with three endpoints:
  - `GET /api/product/downloads` — full manifest (`Cache-Control:
    public, max-age=60`, `X-Tars-Contract: 1.0.0`).
  - `GET /api/product/downloads/latest?os=&channel=` — latest release
    for the filters; **400** on invalid `os`, **404** on no match.
  - `GET /api/product/version` — minimal probe.
- Mounted in `web_extras/app.py` alongside the existing routers.

**Contracts (`docs/contracts/`)**

- `docs/contracts/README.md` — folder convention + index.
- `docs/contracts/MEEET_DOWNLOADS.md` — full prose contract for the
  download manifest, with wire examples, validation rules, and a
  meeet.world SSR integration recipe. Versioned at `1.0.0`.
- `docs/contracts/download_manifest.schema.json` — JSON Schema (Draft
  2020-12) pinning the same shape; runtime test
  (`tests/test_product_schema.py`) validates the loader output
  against it so the prose and the code can't drift.
- `docs/contracts/L5_PAIRING_DRAFT.md` — full draft of the L5 device
  pairing flow + encrypted sync envelope (XChaCha20-Poly1305 + X25519,
  HKDF-SHA-256, bech32m QR transport with HRP `tars1`). Names every
  field the Tauri shell, the iOS app, and the Android app will
  exchange; lists the five `/api/pairing/*` endpoints; locks
  recovery semantics (BIP-39 24-word seed displayed once at install
  time); calls out open questions to lock before code lands.

**Frontend — Landing CTAs (`experiments/neural-showcase-v3/`)**

- New `src/lib/downloads.ts` — typed manifest client + UA-based
  platform detection (`detectPlatform()` handles macOS Apple Silicon
  vs Intel via `userAgentData`, Windows, Linux, iOS, Android), plus a
  `useDownloads()` hook that returns the right primary artifact for
  the visiting browser.
- New `src/components/DownloadStrip.tsx` — functional surface only.
  Auto-targets the visitor's OS, falls back to a "pick your
  installer" panel when detection fails, and exposes
  `data-sha256` / `data-size-bytes` attributes so a future verify-on-
  download UI can read them. Visual treatment is deliberately plain
  — Claude owns the brand pass.
- `src/components/Hero.tsx` mounts `<DownloadStrip variant="hero" />`
  beneath the existing CTA row, immediately before the section
  divider.

**Mobile stubs (`mobile/`)**

- `mobile/README.md` — phase L10 overview: why two codebases, store
  policies, shared HTTP/SSE contract.
- `mobile/ios/TARSCompanion/` — Swift Package skeleton (`Package.swift`,
  `Sources/TARSCompanion/TARSCompanion.swift`, XCTest stub) with the
  full planned Xcode layout documented in `README.md`. Tracks the
  contract version constant.
- `mobile/android/TARSCompanion/` — Gradle settings placeholder, full
  planned Android Studio layout in `README.md` (Compose, OkHttp 4 SSE,
  Tink for crypto interop, `PushToTalkService` foreground service).

**Tests** (+14 new, full suite **284 green**)

- `tests/test_product_downloads.py` — loader returns defaults on
  missing/malformed file, parses real manifests with relative URLs +
  base-URL resolution, skips invalid artifacts, HTTP endpoints emit
  `X-Tars-Contract` / `Cache-Control`, `os` filter rejects unknown
  values.
- `tests/test_product_schema.py` — pins the JSON Schema against both
  the bundled defaults and a real on-disk manifest; explicit negative
  test confirms unknown `os` values fail validation.
- `Makefile` — `make help` / `test` / `test-product` /
  `cockpit{,-build,-tsc}` / `desktop-{dev,build}` / `clean`. No new
  runner deps; everything is `python -m`, `pnpm --dir`, or `bash`.

**Smoke**

- `python -m pytest tests/` → **284 passed**.
- `pnpm tsc --noEmit` (cockpit) → clean.
- Manual `curl http://127.0.0.1:8765/api/product/downloads | jq` returns
  the bundled defaults with `source: "defaults"` and three artifacts
  (macOS arm64/x64, Windows x64); flipping `TARS_RELEASES_PATH` to a
  custom file flips `source` and the URLs absolute-resolve through
  `TARS_DOWNLOAD_BASE_URL`.

**Files**

- `desktop/{README.md,.gitignore,package.json,scripts/package-cockpit.sh}`
- `desktop/src-tauri/{Cargo.toml,build.rs,tauri.conf.json,src/main.rs,src/sidecar.rs,icons/README.md,web/README.md}`
- `backend/core/product/{__init__.py,manifest.py}`
- `web_extras/routers/product.py`
- `web_extras/app.py` (mount)
- `docs/contracts/{README.md,MEEET_DOWNLOADS.md,L5_PAIRING_DRAFT.md,download_manifest.schema.json}`
- `experiments/neural-showcase-v3/src/lib/downloads.ts` (new)
- `experiments/neural-showcase-v3/src/components/DownloadStrip.tsx` (new)
- `experiments/neural-showcase-v3/src/components/Hero.tsx` (mount strip)
- `mobile/README.md`
- `mobile/ios/TARSCompanion/{README.md,Package.swift,.gitignore,Sources/.../TARSCompanion.swift,Tests/.../TARSCompanionTests.swift}`
- `mobile/android/TARSCompanion/{README.md,settings.gradle.kts,.gitignore}`
- `tests/{test_product_downloads.py,test_product_schema.py}`
- `Makefile`
- `docs/{PHASE_L_ROADMAP,AGENT_HANDOFF,CHANGELOG_AGENTS,IDEAS}.md`

---

## 2026-04-29 — Cursor agent · Session planning + Claude handoff cue

**Summary**

Appended **`AGENT_HANDOFF.md`** with a **~5–6 h Cursor functional backlog**
(L9 desktop skeleton, public download manifest API + contract note, L5
pairing draft stub) and a **Handoff → Claude Code** block (design polish,
Landing download CTAs, meeet.world integration guardrails, copy-paste cue).

**Files**

- `docs/AGENT_HANDOFF.md`

---

## 2026-04-29 — Cursor agent · Phase L8 (Search & observability v2)

**Summary**

Cross-thread hybrid search across files, messages, and meeet event
traces, plus a per-thread structured timeline. Three SQLite **FTS5**
virtual tables (`chunks_fts`, `messages_fts`, `events_fts`) give
proper BM25 ranking for the keyword side of L2's hybrid retrieval and
unlock a full ⌘K command palette in the cockpit. Tokeniser is
`unicode61 remove_diacritics 2` so cyrillic and latin queries both
work.

**Backend (`backend/core/search/`, new module)**

- `fts.py` — FTS5 setup / sync / sanitiser. Tables auto-create + back-
  fill from source rows. Public helpers `index_chunk(s)`,
  `index_message`, `index_event`, `remove_chunks_for_attachment`,
  `remove_messages_for_thread`. `sanitise_query()` makes raw operator
  queries safe to drop into a `MATCH` clause (drops FTS5 keywords +
  punctuation, quotes individual tokens). Three `fts_match_*` helpers
  return `(rowid, rank, snippet)` rows with `<mark>` highlights.
- `engine.py` — typed `SearchHit` / `SearchResult`. `search()`
  dispatches across scopes (`all|chunks|messages|traces`).
  `search_chunks()` runs hybrid FTS5 BM25 + vector cosine with
  reciprocal-rank fusion (k=60); falls back to vector-only when FTS5
  misses. Cross-thread by default; supports `thread_id` scope.
  Joins thread titles into hits so the cockpit can render
  "kpi.md · KPI ops" tags.
- `timeline.py` — `get_thread_timeline()` joins messages, tool calls,
  attachments, and relevant `meeet` events
  (`voice.tts`, `usage.tokens`, `chat.context.retrieved`, `council.*`,
  `policy.*`, `playbook.step.*`, `sampler.decision`,
  `attachment.ingested`) into a single chronological feed.

**L2 retrieval moved to FTS5 BM25**

`backend/core/attachments/retrieval.py` now ranks the keyword side
via FTS5 (with the existing TF-overlap kept as a graceful fallback).
Same `RetrievedChunk` contract — orchestrator side untouched.

**HTTP surface (`web_extras/routers/search.py`, new)**

- `POST /api/search` — unified hybrid (`scope`, `top_k`).
- `POST /api/search/chunks` — cross-thread or `thread_id`-scoped.
- `POST /api/search/messages` — keyword search over messages
  (`thread_id`, `role` filters).
- `POST /api/search/traces` — free-text search over meeet events.
- `GET /api/chat/threads/{id}/timeline` — structured per-thread feed
  (limit caps at 1000).

Mounted in `web_extras/app.py` alongside the existing chat / voice /
usage routers.

**Sync hooks**

- `backend/core/chat/store.py · ChatStore.insert_message` mirrors
  writes into `messages_fts` (best-effort, non-fatal).
- `backend/core/attachments/pipeline.py · ingest()` bulk-indexes new
  chunks via `index_chunks_bulk` after embeddings land.
  `delete_attachment()` clears the FTS slice.

**Frontend (`experiments/neural-showcase-v3/`)**

- `src/lib/search.ts` — typed client + 3 hooks (`useDebouncedSearch`,
  `useGlobalShortcut`, `useThreadTimeline`).
- `src/components/CommandPalette.tsx` — ⌘K modal: scope chips,
  arrow-key navigation, BM25 highlights, deep links via the
  `tars:open-thread` custom event.
- `src/components/ThreadTimeline.tsx` — collapsible feed mounted
  under the conversation, auto-refresh every 6 s while open.
- `src/components/ChatPane.tsx` — listens for `tars:open-thread` to
  flip the active thread; mounts `<ThreadTimeline />` under the
  conversation.
- `src/pages/Cockpit.tsx` — mounts `<CommandPalette />` once at the
  page level.

**Tests** (+21 new, full suite **270 green**)

- `tests/test_search_fts.py` — sanitiser, indexing, backfill, delete
  cascade, idempotency.
- `tests/test_search_engine.py` — cross-thread chunk search, scope
  restriction, cyrillic queries, vector fallback.
- `tests/test_search_router.py` — HTTP unified / chunks / messages /
  traces / timeline + scope validation + 400 on empty query.
- `tests/test_voice_synthesis.py` — bumped event-store query limits
  + filter-by-kind so the test isn't sensitive to incidental events
  emitted by other tests.

**Smoke (TestClient)**

Two threads with KPI + trade docs, an SSE chat turn through the
real orchestrator, then:

- `POST /api/search` for "EMEA blocker GDPR" → 2 hits
  (`{chunks:1, messages:1, traces:0}`) with BM25 `<mark>` highlights.
- `POST /api/search` for "NVDA hedge" → cross-thread chunk hit on
  the trade thread.
- `GET /api/chat/threads/{a}/timeline` → 3 chronologically-ordered
  entries (attachment ingest → operator question → TARS reply).

**Files**

- `backend/core/search/__init__.py` (new)
- `backend/core/search/fts.py` (new, ~400 LOC)
- `backend/core/search/engine.py` (new, ~430 LOC)
- `backend/core/search/timeline.py` (new, ~220 LOC)
- `backend/core/attachments/pipeline.py` (FTS sync hook on
  ingest + delete)
- `backend/core/attachments/retrieval.py` (FTS5-first keyword side)
- `backend/core/chat/store.py` (`insert_message` mirrors into FTS)
- `web_extras/routers/search.py` (new, ~145 LOC)
- `web_extras/app.py` (mount the new routers)
- `experiments/neural-showcase-v3/src/lib/search.ts` (new)
- `experiments/neural-showcase-v3/src/components/CommandPalette.tsx`
  (new)
- `experiments/neural-showcase-v3/src/components/ThreadTimeline.tsx`
  (new)
- `experiments/neural-showcase-v3/src/components/ChatPane.tsx`
  (mount timeline + listen for `tars:open-thread`)
- `experiments/neural-showcase-v3/src/pages/Cockpit.tsx` (mount
  `<CommandPalette />`)
- `tests/test_search_fts.py` (new)
- `tests/test_search_engine.py` (new)
- `tests/test_search_router.py` (new)
- `tests/test_voice_synthesis.py` (resilience tweak)
- `docs/PHASE_L_ROADMAP.md`, `docs/AGENT_HANDOFF.md`,
  `docs/CHANGELOG_AGENTS.md`, `docs/IDEAS.md` (post-L8 follow-ups).

---

## 2026-04-29 — Cursor agent · Phase L2 (Attachments + RAG with citations)

**Summary**

End-to-end retrieval-augmented chat: operators drop PDF / Markdown /
CSV / JSON / plain text into a thread, the backend extracts text,
chunks it with overlap, computes real OpenAI embeddings (with a
deterministic offline hash-bigram fallback so nothing breaks without
keys), and stores everything alongside the chat in
`~/.tars/chat.sqlite`. Each operator turn runs hybrid retrieval
(cosine + keyword fused via reciprocal rank), injects the top-K
chunks into the system prompt with stable `[chunk_N]` markers, and
exposes them through a new `context.retrieved` SSE event + persisted
`sources` field on the assistant message. Cockpit grows drag-and-drop
into the composer, an attachment chip strip with deletion, and a
collapsible per-message "Sources" footer.

**Backend**

- `backend/core/attachments/__init__.py` (new) — module entrypoint.
- `backend/core/attachments/extractors.py` (new) — text/json/csv/md/pdf
  extractors. Lazy `pypdf` import (only new dep, MIT). Best-effort:
  errors land in `meta["error"]`.
- `backend/core/attachments/chunking.py` (new) — token-aware chunker
  (paragraph-first, sentence-aware oversized split, overlap, heading
  + page resolution, hash dedup).
- `backend/core/attachments/embeddings.py` (new) — `Embedder` ABC +
  `OpenAIEmbedder` (`text-embedding-3-small` via stdlib `urllib`)
  and `HashEmbedder` (deterministic, offline, normalised cosine
  meaningful). `detect_embedder()` picks best available; pinned
  via `TARS_EMBEDDER`.
- `backend/core/attachments/index.py` (new) — `AttachmentStore`
  singleton on the chat SQLite. Auto-migrates `attachments` with
  `content_hash`, `status`, `error`, `meta_json`, `char_count`. New
  `attachment_chunks` table with raw float32 vector blobs.
- `backend/core/attachments/retrieval.py` (new) — hybrid cosine +
  keyword retrieval fused via reciprocal rank (k=60). Returns
  `RetrievedChunk` rows with `[chunk_N]` citation ids.
- `backend/core/attachments/pipeline.py` (new) — `ingest()` + `delete_attachment()`.
  Idempotent on `(thread_id, content_hash)`, 25 MB cap (env-tunable),
  emits `attachment.ingested` + `usage.tokens` events; bumps
  `meeet` route to `cloud` whenever the OpenAI embedder runs.
- `backend/core/chat/orchestrator.py` (modified) —
  `_maybe_retrieve()` + `_compose_system_prompt()` layer reference
  materials over the pack's prompt. New `context.retrieved` stream
  event; `message.completed` carries `sources`; `Message.extra`
  persists them so reload still shows citations.
- `backend/core/chat/models.py` (modified) — new
  `context.retrieved` `StreamKind`.
- `web_extras/routers/chat.py` (modified) — new endpoints:
  `POST /threads/{id}/attachments` (multipart),
  `GET /threads/{id}/attachments`, `GET /attachments/{id}`,
  `GET /attachments/{id}/download`, `GET /attachments/{id}/extracted`,
  `DELETE /attachments/{id}`, `POST /threads/{id}/retrieve`.

**Frontend**

- `experiments/neural-showcase-v3/src/lib/attachments.ts` (new) —
  typed client + `useThreadAttachments` (list/upload/progress/remove)
  + `useDropZone` (drag-depth-counted to avoid flicker).
- `experiments/neural-showcase-v3/src/lib/chat.ts` (modified) —
  `ChatStreamEventKind` adds `context.retrieved`; new types
  `ChatAttachment`, `ChatSourceCitation`, `RetrievedChunkRef`;
  `ChatTurnState.retrieved` plumbs live RAG through to the bubble.
- `experiments/neural-showcase-v3/src/components/ChatPane.tsx`
  (modified) — drag-and-drop overlay, `<AttachmentChipStrip />`,
  `+ file` composer button, collapsible `<SourcesFooter />` in
  `<MessageBubble />` (live previews during streaming, persisted
  citations on reload).

**Tests**

- `tests/test_attachments_extractors.py` (8) — sniff, plaintext,
  json, csv, image stub, unknown, broken pdf.
- `tests/test_attachments_chunking.py` (6) — empty, short, paragraph
  split + overlap, heading + page resolution, dedup.
- `tests/test_attachments_embeddings.py` (7) — hash availability,
  normalisation, similarity, empty, env pin, fallback, OpenAI mocked
  endpoint.
- `tests/test_attachments_pipeline.py` (7) — record + chunks, dedupe,
  oversize, empty, retrieval ranking, empty-thread retrieval,
  delete.
- `tests/test_attachments_router.py` (8) — multipart upload + dedupe,
  unknown thread, list ordering, describe with previews, extracted
  text, retrieve top-K, retrieve-required-query, delete drop.
- `tests/test_chat_with_rag.py` (3) — orchestrator emits
  `context.retrieved` + persists sources; skips for empty thread /
  short query.

Suite: 210 → **249 passing**. Frontend `npm run build` green.

**Smoke proof**

Live HTTP run on `:8767`:

1. `POST /api/chat/threads` → `thr_…`
2. `POST /api/chat/threads/{id}/attachments` (`kpi.md`) →
   `chunk_count=1`, `embedding_model=tars-hash-bigram-v1-d384`,
   `status=ready`.
3. `POST /api/chat/threads/{id}/retrieve` (`"EMEA conversion blocker"`)
   → `chunk_1` with `score=0.0328`, ranked 1 in both semantic and
   keyword pools.
4. `POST /api/chat/threads/{id}/messages` (SSE) emitted
   `message.started → context.retrieved → token… → usage →
   message.completed → stream.closed`. `message.completed.sources`
   = `[{citation_id: "chunk_1", filename: "kpi.md", …}]`.
5. `GET /api/chat/threads/{id}/attachments` → `count=1`.
6. Chunk count, embed cost, char counts all align with the cost
   ledger (cost `$0` for offline hash embedder, would be ~$0.02/1M
   tokens with `text-embedding-3-small`).

**Files changed**

- backend/core/attachments/{__init__,extractors,chunking,embeddings,index,retrieval,pipeline}.py
- backend/core/chat/{models,orchestrator}.py
- web_extras/routers/chat.py
- experiments/neural-showcase-v3/src/lib/{attachments.ts,chat.ts}
- experiments/neural-showcase-v3/src/components/ChatPane.tsx
- tests/test_attachments_extractors.py
- tests/test_attachments_chunking.py
- tests/test_attachments_embeddings.py
- tests/test_attachments_pipeline.py
- tests/test_attachments_router.py
- tests/test_chat_with_rag.py
- docs/{AGENT_HANDOFF.md,CHANGELOG_AGENTS.md,IDEAS.md,PHASE_L_ROADMAP.md}

## 2026-04-29 — Cursor agent · Phase L4.1 (Voice persona layer + mic dictation)

**Summary**

Operator-facing TTS landed early because L1 chat is now usable and
character voices are the single biggest "feels alive" upgrade.
Six personas ship (J.A.R.V.I.S. · British butler, Tony Stark · Iron
Man, HAL 9000, GLaDOS, Interstellar TARS, Operator default), with
three provider tiers: ElevenLabs (best character voices) → OpenAI
TTS (`gpt-4o-mini-tts` honours per-persona `instructions`) →
macOS `say` (offline fallback, ships free on every Mac). Cockpit
gets a persona picker, provider override, autoplay toggle, mute,
per-message ▶ speak button, and a 🎙 mic button using the
browser's Web Speech API for input dictation. Costs roll into the
existing `/api/usage` ledger as `voice/<provider>` rows.

**Backend**

- `backend/core/voice/__init__.py` (new) — module entrypoint.
- `backend/core/voice/personas.py` (new) — Persona dataclasses +
  registry (env-overridable, plugin-extensible).
- `backend/core/voice/engines.py` (new) — `ElevenLabsEngine`,
  `OpenAITTSEngine`, `MacSayEngine` (TTSEngine ABC). Accent-aware
  fallback when persona's preferred mac voice isn't installed.
- `backend/core/voice/synthesis.py` (new) — orchestrator with
  pinned-provider + auto-order semantics; emits `voice.tts` +
  `usage.tokens` events with char-based USD cost.
- `web_extras/routers/voice.py` (new) — `/api/voice/{personas,
  health,speak}`. Mounted in `web_extras/app.py`.

**Frontend**

- `experiments/neural-showcase-v3/src/lib/voice.ts` (new) — typed
  client + `useVoicePlayback`, `usePersonas`, `useVoiceHealth`,
  `useMicTranscription` hooks. localStorage persistence for
  persona / provider / autoplay / mute.
- `experiments/neural-showcase-v3/src/components/ChatPane.tsx` —
  added `<VoiceControls />` header row, autoplay-on-new-reply,
  per-message speak button, mic button in composer.

**Tests**

- `tests/test_voice_personas.py` (new) — 8 cases.
- `tests/test_voice_engines.py` (new) — 6 cases (mac fallback +
  duration estimator).
- `tests/test_voice_synthesis.py` (new) — 8 cases (provider order,
  fallbacks, event emission).
- `tests/test_voice_router.py` (new) — 6 cases.
- **Total: 210 passing** (was 182, +28).

**Smoke proof**

Live `POST /api/voice/speak` against the running server returned a
real 131 KB WAV for Jarvis (Daniel · British male) and a
148 KB WAV for Stark (Tom · American male, accent-aware fallback
when "Aaron" isn't installed). `/api/usage` now lists
`voice/mac_say` alongside chat models. Frontend `npm run build`
clean.

**Notes on character likeness**

The roster is *inspirational* — every persona maps to a generic
preset voice (ElevenLabs starter library, OpenAI public voices,
macOS shipped voices). No Disney/Marvel/Valve/Paramount asset is
reused. Operators wanting a tighter likeness drop a custom
ElevenLabs voice id into `TARS_PERSONA_<ID>_ELEVENLABS_ID`.

## 2026-04-29 — Cursor agent · Phase L1 (Conversation Layer)

**Summary**

First implementation pass of the Phase L roadmap. Threads, streaming
assistant turns, tool-call routing through the existing policy gate,
and full integration with the K-tier cost ledger and meeet event
bridge — every chat turn now lights up `/api/usage` automatically.

**Backend**

- `backend/core/chat/__init__.py` (new) — module entrypoint.
- `backend/core/chat/models.py` (new) — `Thread`, `Message`,
  `ToolCall`, `Attachment`, `AttachmentRef`, `StreamEvent` plus id
  factories.
- `backend/core/chat/store.py` (new) — SQLite WAL store at
  `~/.tars/chat.sqlite` (env override `TARS_CHAT_DB_PATH`, disable
  via `TARS_CHAT_STORE=disabled`). CRUD + paginated message reads +
  tool-call upsert + attachment table (forward-compatible for L2).
- `backend/core/chat/voices.py` (new) — `ChatVoice` ABC with three
  flavours: `LocalChatVoice` (deterministic, offline), and
  Anthropic / OpenAI streaming voices that talk SSE via stdlib
  `urllib` driven by an `asyncio.Queue` — no httpx, stays
  contract-pure.
- `backend/core/chat/orchestrator.py` (new) — the seam between L
  (chat) and K (cost / policy / meeet). Persists operator turn,
  opens `trace_scope(session=…, route="edge")`, streams chunks,
  parses `<tool name="slug.action_id">{...}</tool>` sentinels on
  the fly, runs them through `PolicyGate.check`, emits per-turn
  `usage.tokens` events, persists assistant message + tool calls.
- `web_extras/routers/chat.py` (new) — full HTTP surface under
  `/api/chat` plus an SSE-streaming POST. Mounted in
  `web_extras/app.py`.
- `backend/core/usage/ledger.py` — added `tars-local-chat-v1` price
  (zero) so the cost ledger doesn't show "n/a" for offline turns.

**Frontend**

- `experiments/neural-showcase-v3/src/lib/chat.ts` (new) — typed
  client + `useChatThread` React hook with a streaming reducer
  (optimistic operator bubble, token-by-token assistant draft,
  tool-call status machine, usage snapshot).
- `experiments/neural-showcase-v3/src/components/ChatPane.tsx` (new)
  — thread list + conversation view + composer with `⌘↵ to send`,
  inline tool-call cards, archive / rename, optimistic UI. Mounted
  on `/cockpit` as the primary panel above the existing JSON
  invocation grid.
- `experiments/neural-showcase-v3/src/pages/Cockpit.tsx` — imports
  `<ChatPane />` and renders it after the awareness ticker, biased
  to the currently-selected pack via `defaultPackSlug`.

**Tests**

- `tests/test_chat_models.py` (new) — 8 cases.
- `tests/test_chat_orchestrator.py` (new) — 8 cases including
  scripted tool-call routing through autopilot + confirm modes.
- `tests/test_chat_router.py` (new) — 7 cases including SSE shape
  and post-stream persistence.
- **Total: 182 passing** (159 → 182, +23).

**Smoke proof**

Live SSE round-trip on a free port: thread created, message streamed
chunk-by-chunk, persisted to SQLite, surfaced under
`/api/usage?session_id=…` as `tars-local-chat-v1` on the `edge`
route. Frontend `npm run build` clean.

## 2026-04-29 — Cursor agent · Phase L roadmap published

**Summary**

Wrote `docs/PHASE_L_ROADMAP.md` — full functional plan for the
Claude-tier evolution of TARS released as the flagship product of
`meeet.world` with native distribution on macOS, Windows and iOS.
Eight functional sub-phases (L1–L8) plus two distribution sub-phases
(L9 desktop, L10 iOS) with explicit contracts, file layouts, event
kinds, HTTP surfaces, tests, and acceptance criteria. AGENT_HANDOFF
and IDEAS now point to the roadmap as the canonical source of
truth. Implementation of **L1 (Conversation Layer)** starts in the
next entry.

Files: `docs/PHASE_L_ROADMAP.md` (new), `docs/AGENT_HANDOFF.md`,
`docs/IDEAS.md`.

## 2026-04-29 — Cursor agent · Phase K observability + extensibility

**Summary**

Six more functional sub-phases shipped. Total **159 pytest tests**
passing (was 122 — added 37 across contract, ledger, composite,
manifest, smtp, replay-cli). Every cross-boundary call now carries
optional `session_id` + `route` tags, the cost of every council
deliberation lands in a USD ledger, composite domain packs ship
(`research_lab`, `ops_room`), and the SMTP outbound for
`business.draft_email` is real when configured.

- **Phase K1 — route + session_id everywhere.** New
  `backend/core/meeet/tracing.py` exports `session_scope`, `set_route`,
  `current_session`, `current_route`. `TARSEvent` and the SQLite store
  carry optional `session_id` + `route`; the store auto-migrates with
  `ALTER TABLE` between table creation and index creation so old
  buffers keep working. `web_extras/routers/domains.py` accepts
  `x-tars-session-id`; `trace_scope` defaults to `route="edge"` and
  the council bumps it to `cloud` when an LLM voice runs.
  Files: `backend/core/meeet/{tracing,events,store,client,__init__}.py`,
  `web_extras/routers/{domains,meeet}.py`,
  `tests/test_meeet_contract.py`.
- **Phase K2 — cost ledger.** `backend/core/usage/{__init__,ledger}.py`
  with a configurable `PriceTable` (defaults for sonnet, haiku, opus,
  gpt-4o, gpt-4o-mini, gpt-4.1; `TARS_PRICE_OVERRIDES_JSON` for
  overrides). The orchestrator emits per-voice `usage.tokens`
  events with `cost_usd`; `sampler.decision` carries the aggregate.
  Files: `backend/core/usage/*`,
  `backend/core/council/orchestrator.py`,
  `tests/test_usage_ledger.py`.
- **Phase K3 — `/api/usage` rollup.** `web_extras/routers/usage.py`
  aggregates `usage.tokens` by `model | route | session`. Frontend
  ships `lib/usage.ts` + `<UsageStrip />` mounted on `/cockpit`.
  CORS now whitelists `x-tars-session-id`.
  Files: `web_extras/routers/usage.py`, `web_extras/app.py`,
  `experiments/neural-showcase-v3/src/lib/usage.ts`,
  `experiments/neural-showcase-v3/src/components/UsageStrip.tsx`,
  `experiments/neural-showcase-v3/src/pages/Cockpit.tsx`,
  `tests/test_usage_router_and_manifest.py`.
- **Phase K4 — composite packs + manifest.**
  `backend/core/domains/composite.py` + `packs/composites.py` register
  `research_lab` (science + business) and `ops_room` (traders + mlm).
  Composite actions surface as `<sub_slug>__<id>`; destructive flags +
  auth keys propagate from leaves. New endpoint
  `GET /api/domains/manifest`.
  Files: `backend/core/domains/composite.py`,
  `backend/core/domains/packs/composites.py`,
  `backend/core/domains/packs/__init__.py`,
  `web_extras/routers/domains.py`,
  `tests/test_composite_packs.py`.
- **Phase K5 — replay CLI + contract test.** New
  `python -m backend.core.meeet.replay_cli` with
  `--stats / --export / --limit / --since / --kind / --session-id`.
  Round-trips session/route through replay; useful for cold-start
  recovery or schema migrations.
  Files: `backend/core/meeet/replay_cli.py`,
  `tests/test_replay_cli.py`, `tests/test_meeet_contract.py`.
- **Phase K6 — SMTP outbound for `business.draft_email`.**
  `backend/core/domains/packs/business/smtp.py` reads SMTP_* config
  from the vault (env or Keychain), supports STARTTLS on 587 and
  implicit TLS on 465. With `send=true` and SMTP configured (and the
  policy gate confirmed), `draft_email` actually delivers; otherwise
  it returns the draft + `delivery.status` hint. Pack adds
  `SMTP_HOST/USER/PASSWORD/FROM` to `auth_vault_keys()`.
  Files: `backend/core/domains/packs/business/{smtp,actions,pack}.py`,
  `tests/test_business_smtp.py`.
- **Frontend (Cursor lane).** `lib/session.ts` (per-tab `ses_<id>` in
  `sessionStorage`); `invokeAction` accepts `sessionId` and stamps
  `x-tars-session-id`. `getDomainManifest()` typed client; new
  `composite` + `composed_of` flags on `DomainPack`. `Domains.tsx`
  unused-import cleanup so build stays green.
  Files: `experiments/neural-showcase-v3/src/lib/{api,session,usage}.ts`,
  `experiments/neural-showcase-v3/src/components/{UsageStrip,Domains}.tsx`,
  `experiments/neural-showcase-v3/src/pages/Cockpit.tsx`.

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
