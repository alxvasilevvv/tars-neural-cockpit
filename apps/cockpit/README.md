# apps/cockpit — TARS cockpit source of truth (W308 step 0)

This is the new minimal cockpit shell scaffolded in W308. It exists
because the original SPA (`experiments/neural-showcase-v3`) was
deleted in commit `e5f1911`, leaving the desktop build to ship a
frozen, minified bundle under `desktop/src-tauri/web/`. That bundle
has no source of truth for design tokens, so any taste change is
either a one-off hex patch or impossible.

`apps/cockpit/` fixes that. **Stack: Vite + vanilla TypeScript, no
framework.** Deliberately minimal — the cost of choosing a framework
before knowing what the cockpit needs is higher than the cost of
adding one later.

---

## What lives here

```
apps/cockpit/
├── README.md             ← you are here
├── package.json          ← Vite + TypeScript, no runtime deps
├── tsconfig.json
├── vite.config.ts        ← outputs to dist/, base "/"
├── index.html            ← shell + font preconnects
├── public/
│   └── favicon.svg
└── src/
    ├── main.ts                  ← entry; mounts tokens-preview by default
    ├── styles/
    │   ├── reset.css            ← modern CSS reset (Andy Bell flavour)
    │   ├── tokens.css           ← **synced from design-system/tars/MASTER.md**
    │   ├── typography.css       ← font setup, scale, line-height contract
    │   └── global.css           ← composes the above + body baseline
    └── pages/
        └── tokens-preview.ts    ← live preview of the full token system
```

---

## Why no React

1. The MASTER design contract is plain CSS variables + semantic
   HTML. None of it needs React state.
2. Vanilla TS keeps the cockpit bundle ≤ 30KB raw (target). React
   alone is ~45KB minified.
3. If we need reactivity later, Lit / Preact / Svelte / Solid can
   plug in *per surface*. We are not locked in.
4. The previous SPA used Vanilla JS + Three.js and worked. Three.js
   will rejoin when the hero scene needs it.

---

## What this is *not* yet

- **Not a replacement** for the production cockpit. The Tauri shell
  still serves `desktop/src-tauri/web/`. Migration happens in W308
  step 2, surface by surface, behind verification.
- **Not the visual design.** Tokens here are the *current* MASTER
  values. W307 (Claude's pass) may diff them. Edit `tokens.css` then;
  do not re-architect the shell.
- **Not the place for HUD scenes / Three.js / WebGL.** Those are
  hero-tier additions that come after the token system is verified
  in plain HTML/CSS.

---

## Workflow

### Local dev

```bash
cd apps/cockpit
pnpm install
pnpm dev          # vite dev server on http://localhost:5174
```

Open `http://localhost:5174` — you see the tokens preview page (every
colour swatch + type scale + interactive sample).

### Build for inspection

```bash
pnpm build        # → apps/cockpit/dist/
pnpm preview      # serve the production build
```

### Sync token changes from MASTER

`tokens.css` is **not** auto-generated. After the operator approves a
W307 token diff:

1. Edit the hex / font values in `tokens.css`.
2. Mirror the same change into `design-system/tars/MASTER.md` (so the
   markdown stays the source of truth for prose).
3. Run the drift smoke test (`pytest tests/test_cockpit_tokens_sync.py`)
   to confirm both files agree.

### Wire into the desktop release pipeline (W308 step 2 — not yet)

When the new cockpit is ready to replace the frozen bundle:

```bash
# In desktop/scripts/package-cockpit.sh, replace the "just check it
# exists" stub with:
pnpm --filter cockpit build
cp -R apps/cockpit/dist/* desktop/src-tauri/web/
```

Until then, the production cockpit is the bundle under
`desktop/src-tauri/web/`. This scaffold is a *parallel* surface for
iteration only.

---

## See also

- `design-system/tars/MASTER.md` — the design contract.
- `docs/handoff/W307_DESIGN_SYSTEM_REFRESH_FOR_CLAUDE.md` — taste pass
  (Claude Code).
- `docs/handoff/W308_PRE_FLIGHT_FINDINGS.md` — why Path C was picked.
- `tests/test_cockpit_tokens_sync.py` — guards MASTER ↔ tokens.css
  drift.
