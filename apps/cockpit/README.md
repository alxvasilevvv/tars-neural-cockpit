# apps/cockpit — TARS cockpit source of truth (W308)

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
├── vite.config.ts        ← multi-page build (index/cockpit/hero/preview)
│
├── index.html            ← dev index / page picker
├── cockpit.html          ← operator shell (W308 step 2 — port of W307 ref)
├── hero.html             ← marketing hero (W308 step 2 — port of W307 ref)
├── preview.html          ← tokens diagnostic surface
│
├── public/
│   └── favicon.svg
└── src/
    ├── pages/
    │   ├── index-entry.ts       ← landing entry (imports CSS only)
    │   ├── cockpit-entry.ts     ← cockpit entry (imports CSS only)
    │   ├── hero-entry.ts        ← hero entry (imports CSS only)
    │   ├── preview-entry.ts     ← preview entry (mounts tokens preview)
    │   └── tokens-preview.ts    ← render module — drift diagnostic
    └── styles/
        ├── reset.css            ← modern CSS reset (Andy Bell flavour)
        ├── tokens.css           ← **synced from design-system/tars/MASTER.md**
        ├── typography.css       ← font setup, scale, line-height contract
        └── global.css           ← composes the above + body baseline
```

### Page contract

| Page              | Route             | Purpose                                                          |
|-------------------|-------------------|------------------------------------------------------------------|
| Landing           | `/`               | Dev index — links to the three real surfaces below.              |
| Cockpit           | `/cockpit.html`   | Operator shell. Briefing card, phase bar, policy gate, mic input.|
| Hero              | `/hero.html`      | Marketing hero. Headline + CTAs + SVG core scene + live rail.    |
| Tokens preview    | `/preview.html`   | Diagnostic — every MASTER token (palette · type · motion · CTAs).|

`cockpit.html` and `hero.html` ship hand-written HTML on top of the
shared `tokens.css` / `typography.css` / `global.css`. Page-specific
chrome (HUD bar, briefing card, scene, policy gate) lives inline in
each `<style>` block so a designer can diff the entire surface in
one file. Shared visual contract (palette, type scale, motion,
CTA contracts, glyph contracts) lives in `src/styles/`.

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

- **Not wired into the desktop release yet.** Until W308 step 3
  flips the switch, the Tauri shell still serves
  `desktop/src-tauri/web/`. `apps/cockpit/dist/` is the candidate.
- **Not the final visual design.** Tokens here are MASTER values
  *after* the W307 verdict (greeting bumped, ink-3 promoted,
  motion budget codified, CTA-text-on-accent enforced). Future
  taste changes edit `tokens.css` + `MASTER.md` in the same commit.
- **No JS behaviour on cockpit/hero yet.** They are static markup
  honouring the design contract. Behaviour (phase bar updates,
  policy gate stream, mic toggle) lands when the desktop bridge
  exposes the matching events.

---

## Workflow

### Local dev

```bash
cd apps/cockpit
pnpm install
pnpm dev          # vite dev server on http://localhost:5174
```

Open `http://localhost:5174` — you see the landing page with three
cards: Cockpit, Hero, Tokens preview. All four pages live-reload on
edits.

### Build for inspection

```bash
pnpm build        # → apps/cockpit/dist/ (multi-page output)
pnpm preview      # serve the production build on :5174
```

Production output (gzip, latest build):

| File              | Size       |
|-------------------|------------|
| `index.html`      | ~1.9 kB    |
| `cockpit.html`    | ~5.5 kB    |
| `hero.html`       | ~5.0 kB    |
| `preview.html`    | ~0.8 kB    |
| shared CSS        | ~1.9 kB    |
| shared JS         | ~3.8 kB    |
| **total**         | **~19 kB** |

### Sync token changes from MASTER

`tokens.css` is **not** auto-generated. After the operator approves a
taste change:

1. Edit the hex / font / motion values in `tokens.css`.
2. Mirror the same change into `design-system/tars/MASTER.md` (so the
   markdown stays the source of truth for prose).
3. Run the drift smoke test (`pytest tests/test_cockpit_tokens_sync.py`)
   to confirm both files agree.

### Compare against W307 reference (visual parity)

Claude's W307 reference HTMLs live at
`docs/design/W307_refs/{cockpit,hero}.html`. To compare side-by-side:

```bash
# Terminal 1: Vite dev (the port)
cd apps/cockpit && pnpm dev

# Terminal 2: static server (the reference)
cd docs/design/W307_refs && python3 -m http.server 5175 --bind 127.0.0.1

# Then open:
#   http://127.0.0.1:5174/cockpit.html  (port)
#   http://127.0.0.1:5175/cockpit.html  (reference)
```

Intentional deltas vs reference (per W307 verdict):

- Greeting is bigger (uses `--type-greeting`, reference uses an
  older clamp).
- All accent fills enforce `var(--cta-text-on-accent)` (black on
  gold, AAA contrast).
- Ambient pulses use `--motion-pulse` (3.6s); alert pulses use
  `--motion-alert-pulse` (1.6s) — reference used 1.6s for everything.

### Wire into the desktop release pipeline (W308 step 3 — next)

When the new cockpit is signed off:

```bash
# In desktop/scripts/package-cockpit.sh, replace the "just check it
# exists" stub with:
pnpm --filter cockpit build
rm -rf desktop/src-tauri/web/*
cp -R apps/cockpit/dist/* desktop/src-tauri/web/
```

---

## See also

- `design-system/tars/MASTER.md` — the design contract (source of truth).
- `docs/design/W307_VERDICT.md` — Claude's taste verdict applied here.
- `docs/design/W307_refs/{cockpit,hero}.html` — visual references.
- `docs/handoff/W308_PRE_FLIGHT_FINDINGS.md` — why Path C was picked.
- `tests/test_cockpit_tokens_sync.py` — guards MASTER ↔ tokens.css drift.
