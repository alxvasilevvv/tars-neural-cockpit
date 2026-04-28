# TARS — Neural Showcase v3

React + Vite + TypeScript + Tailwind v4 + framer-motion. Built per the
`ui-ux-pro-max-skill` MASTER (`design-system/tars/MASTER.md`) and ready
for one-line component drops from [21st.dev](https://21st.dev).

## Stack

- React 18 + TypeScript
- Vite 5 (port 5174)
- Tailwind CSS v4 (`@tailwindcss/vite`)
- framer-motion 11 (page motion)
- lucide-react (icons)
- shadcn-style component config (`components.json`) with `@/*` alias

## Run

```bash
npm install
npm run dev   # http://127.0.0.1:5174
npm run build
```

## Adding a 21st.dev component

1. Browse https://21st.dev and pick a block (e.g. `https://21st.dev/<author>/<id>`).
2. Click "Install" — copy the `npx shadcn add ...` command from the page.
3. Paste it inside this folder:

   ```bash
   cd experiments/neural-showcase-v3
   npx shadcn@latest add "https://21st.dev/r/<author>/<id>"
   ```

4. The component lands in `src/components/ui/` (per `components.json`).
   Use it in `src/App.tsx` or in any of the page sections.

The `components.json` is already configured with:

- `tsx: true`, `rsc: false` (Vite-React, not Next.js)
- aliases: `@/components`, `@/components/ui`, `@/lib/utils`, `@/hooks`
- baseColor: `neutral`, cssVariables: `true`
- icon library: `lucide`

## Design tokens

Defined in `src/index.css` via Tailwind v4's `@theme` directive — pulled
straight from `design-system/tars/MASTER.md`. Key tokens:

| Token | Value | Use |
|-------|-------|-----|
| `bg-bg-0` | `#06070d` | Page bg |
| `bg-bg-1` | `#0a0d18` | Card bg |
| `text-ink` | `#f4f6fb` | Primary ink |
| `text-ink-2` | `#9aa3b5` | Secondary ink |
| `text-accent` / `bg-accent` | `#67e8f9` | The one accent |
| `text-alert` | `#fbbf24` | LIVE / integrity only |
| `font-display` | Space Grotesk | Display |
| `font-mono-tech` | Space Mono | HUD labels |

Style blend (per MASTER): HUD/Sci-Fi FUI + Exaggerated Minimalism + Dark
Mode (OLED) + AI-Native UI.
