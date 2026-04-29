# TARS — Neural Showcase v3

The marketing surface for TARS · meeet.world. React + Vite + TypeScript +
Tailwind v4 + framer-motion. Brand triad **indigo / violet / brand cyan**
on OLED black per `design-system/tars/MASTER.md` (overridden globally
in `src/index.css` for the meeet brand).

```bash
cd experiments/neural-showcase-v3
npm install
npm run dev          # http://127.0.0.1:5174
npm run build        # → dist/
```

## Routes

| Path        | Page                  | Notes |
|-------------|-----------------------|-------|
| `/`         | `pages/Landing.tsx`   | Hero · trust · MeetTars · packs · cockpit live · pricing · FAQ |
| `/install`  | `pages/Install.tsx`   | One-curl setup, OS-detected via `lib/downloads.ts` |
| `/onboarding` | `pages/Onboarding.tsx` | 3-step: sign-in → role → first brief (P7 role selector) |
| `/cockpit`  | `pages/Cockpit.tsx`   | Live operator console (Cursor's surface) |
| `/pitch`    | `pages/Pitch.tsx`     | 12-slide investor deck, keyboard nav |
| `/press`    | `pages/Press.tsx`     | Press kit — boilerplate, palette, assets |
| `/docs`     | `pages/Docs.tsx`      | API reference, public HTTP surface |
| `/status`   | `pages/Status.tsx`    | Live system pulses (`/health` + `/api/product/downloads`) |
| `/privacy`  | `pages/Privacy.tsx`   | renders `docs/PRIVACY_POLICY.md?raw` |
| `/terms`    | `pages/Terms.tsx`     | renders `docs/TERMS_OF_SERVICE.md?raw` |
| `/security` | `pages/Security.tsx`  | renders `docs/SECURITY.md?raw` |
| `*`         | `pages/NotFound.tsx`  | proper 404 with deep-links |

## Stack

- React 18 + TypeScript 5.4
- Vite 5 (port 5174)
- Tailwind CSS v4 (`@tailwindcss/vite`)
- framer-motion 11
- @react-three/fiber + drei + postprocessing (HeroGlobe, DomainsScene)
- @splinetool/react-spline (MeetTars character)
- @tsparticles/* (Sparkles)
- lucide-react (icons)
- shadcn/ui via `npx shadcn@latest add <url>` workflow

## Brand tokens

`src/index.css` `@theme` directive:

| Token              | Value                                | Use                                |
|--------------------|--------------------------------------|------------------------------------|
| `--color-bg-0`     | `#000000`                            | Page bg (OLED)                     |
| `--color-bg-1`     | `#0b0b10`                            | Card bg                            |
| `--color-bg-2`     | `#14141b`                            | Hover / nested card                |
| `--color-ink`      | `#f5f5f0`                            | Primary ink                        |
| `--color-ink-2`    | `#b0aea4`                            | Secondary ink                      |
| `--color-ink-3`    | `#7a786f`                            | Muted (passes WCAG AA on bg-0)     |
| `--color-accent`   | `#6366f1`                            | Indigo — brand primary             |
| `--color-hud`      | `#06b6d4`                            | Brand cyan — HUD lines             |
| `--color-meeet-violet` | `#8b5cf6`                        | Violet — secondary accent          |
| `--color-success`  | `#34d399`                            | LIVE / verified                    |
| `--color-alert`    | `#ef4444`                            | Errors / destructive               |
| `--font-display`   | `Share Tech Mono, Fira Code`         | Display                            |
| `--font-mono`      | `Fira Code`                          | HUD labels                         |

Light theme via `:root[data-theme="light"]` — toggleable from Nav
(`<ThemeToggle />`).

## Markdown legal pages

`Privacy / Terms / Security` import the canonical markdown via Vite
`?raw`:

```ts
import source from "@docs/PRIVACY_POLICY.md?raw";
```

Configured in `vite.config.ts` (`@docs` alias + `server.fs.allow` to
include parent `docs/`) and `tsconfig.app.json` (`@docs/*` paths) and
`src/vite-env.d.ts` (declare module `*.md?raw`).

## ⌘K — Global nav palette

`<GlobalCommandPalette />` mounted from `App.tsx` exposes a Vercel/
Linear-style nav from any landing-side route. Doesn't mount inside
`/cockpit` — that surface owns its own ⌘K (chat search). Recent
selections persisted in `localStorage` under `tars-cmdk-recent`.

## Adding a 21st.dev component

1. Browse https://21st.dev and pick a block (e.g. `https://21st.dev/<author>/<id>`).
2. Click "Install" — copy the `npx shadcn add ...` command.
3. Paste it inside this folder:

   ```bash
   npx shadcn@latest add "https://21st.dev/r/<author>/<id>"
   ```

4. Component lands in `src/components/ui/` (per `components.json`).
   Import via `@/components/ui/<name>`.

`components.json`:

- `tsx: true`, `rsc: false` (Vite-React, not Next.js)
- aliases: `@/components`, `@/components/ui`, `@/lib/utils`, `@/hooks`
- baseColor: `neutral`, cssVariables: `true`
- icon library: `lucide`

## Backend coupling

The cockpit reads `VITE_TARS_API` (default `http://127.0.0.1:8765`)
to find the local TARS daemon. Public manifest:

- `GET /api/product/downloads` — `lib/downloads.ts` (contract 1.0.0)
- `GET /health` — daemon liveness
- `GET /api/pairing/*` — L5 device pairing (1.1.0 envelope)
- `POST /api/chat/threads/{id}/messages` — SSE streaming

Full surface: see `/docs` page or `lib/api.ts` / `lib/downloads.ts` /
`lib/pairing.ts` / `lib/search.ts` / `lib/attachments.ts`.

## Build

```bash
npm run build
```

Outputs `dist/` with hashed assets, ~1.4 MB total gzip (Three.js +
postprocessing dominate). Vendor split:

- `three-vendor` — three.js
- `r3f-vendor` — @react-three/* + react-three-rapier
- `react-vendor` — react + react-dom

PWA manifest at `public/manifest.webmanifest` — installable from
modern browsers. Sitemap at `public/sitemap.xml`, robots at
`public/robots.txt`.

## Routing structure

```
src/App.tsx                — Routes + Suspense + AnimatePresence
src/pages/                 — top-level routes
src/components/            — reusable surfaces
src/components/ui/         — shadcn-installed components
src/lib/                   — API clients + hooks
src/three/                 — R3F scenes
public/                    — static assets (favicon, og, manifest, sitemap)
```

## Development checklist

```bash
npm run typecheck   # tsc -b --noEmit
npm run build       # vite build
npm run preview     # preview dist/
```

## Cross-references

- Backend roadmap: `docs/PHASE_L_ROADMAP.md`
- Phase M (monetization + product polish): `docs/PRODUCT_PHASE_M.md`
- Cross-agent handoff: `docs/AGENT_HANDOFF.md`
- Design canon: `design-system/tars/MASTER.md`
- Contracts: `docs/contracts/{MEEET_DOWNLOADS,L5_PAIRING_DRAFT,TARS_SUBDOMAIN}.md`
