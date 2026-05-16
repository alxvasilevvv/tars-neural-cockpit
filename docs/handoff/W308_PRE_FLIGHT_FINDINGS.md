# W308 — pre-flight findings (read before starting migration)

> **Status.** Step 0 shipped. Path **C** picked (see below). Cursor
> built the new minimal cockpit shell under `apps/cockpit/`; live
> tokens now live in `apps/cockpit/src/styles/tokens.css` and are
> guarded against MASTER.md drift by `tests/test_cockpit_tokens_sync.py`.
> Step 1 (apply W307 verdict) and step 2 (replace the frozen Tauri
> bundle) are queued.
> **Owner of W308.** Cursor (this agent).
> **Why this doc exists.** While Claude was running the design pass I
> mapped where the current MASTER tokens *actually live in shipping
> code* — and the answer is "not in a place you can edit in 5 min".
> Surfacing this now so W308 doesn't start by assuming a clean
> `tokens.css` exists.

---

## Decision log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-17 | **Path C selected** (new minimal cockpit at `apps/cockpit/`) | Path A breaks on next bundle rebuild; Path B re-litigates the W292 deletion. C gives a real source of truth that absorbs *any* W307 verdict cheaply. |
| 2026-05-17 | Path C **staged** | Step 0 (scaffold + tokens.css mirroring current MASTER) shipped *before* the W307 verdict lands. When verdict arrives, only `tokens.css` + MASTER.md change — no shell rework. |
| 2026-05-17 | Stack: Vite + vanilla TypeScript, no framework | MASTER contract is plain CSS variables + semantic HTML. React/Vue would add ~45KB minified for zero benefit at this stage. Step 0 bundle is 13KB raw / 5KB gzipped. |

---

## TL;DR

- **There is no React/Vue source tree in this repo.** The desktop
  cockpit ships a *committed, pre-built* static bundle under
  `desktop/src-tauri/web/`. `desktop/scripts/package-cockpit.sh`
  literally just checks the bundle exists; it does not build anything.
- The original SPA (`experiments/neural-showcase-v2` and `v3`,
  Vanilla JS + Vite + Three.js) was **deleted in commit `e5f1911`** —
  `chore: remove neural showcase SPA`. The shipping bundle was built
  from one of its descendants and is now frozen.
- The MASTER tokens (`--color-bg-0`, `--color-accent`, `--color-hud`,
  Space Grotesk, JetBrains Mono) currently exist in **two** places:
  - `design-system/tars/MASTER.md` — the design source of truth.
  - `desktop/src-tauri/web/assets/index-x27x8g94.css` — the
    *minified* shipping CSS in the frozen bundle. Hex values are
    inline; no CSS custom properties pass-through.

So W308 cannot be "edit `tokens.css`, redeploy". W308 starts with a
*strategy decision* before any token actually moves.

---

## The strategy decision (operator-facing)

Pick one path. Each has a different cost / risk profile:

### Path A — patch the bundle (cheapest, ugliest)

Edit `desktop/src-tauri/web/assets/index-*.css` directly. Replace
the literal hex values that map to MASTER tokens. Ship.

- **Pro.** ~1 hour total. No re-bundling. No new tooling.
- **Con.** Minified CSS is fragile; every future bundle rebuild blows
  the patch away. No source of truth. Operator cannot iterate.
- **When acceptable.** If the token diff from W307 is tiny (e.g.
  "warm gold to `#D49915` and call it done").

### Path B — restore the SPA source and rebuild (correct, ~1 day)

```bash
# Restore the last committed source tree.
git show e5f1911~1 -- experiments/neural-showcase-v3/ \
  | git apply --reverse --3way  # or rebase-style restore
# Then point package-cockpit.sh at it and re-add the Vite build to
# the desktop release pipeline.
```

- **Pro.** Real source of truth. Tokens become a proper `tokens.css`.
  Future iterations are fast.
- **Con.** That tree was deleted *deliberately* in `e5f1911`
  ("align API-first docs and tooling"). Restoring it reopens the
  decision the operator already made.

### Path C — minimal new shell (clean slate, ~2 days)

Build a new minimal SPA (Vite + vanilla TS, no React) under
`apps/cockpit/` with just enough surface to host the shipping
screens. Move tokens into `apps/cockpit/src/styles/tokens.css`.
Wire `package-cockpit.sh` to build it.

- **Pro.** Clean, owns the entire chain. No legacy SPA baggage.
- **Con.** ~2 days, and Tauri must accept the new bundle path.

---

## What I recommend (Cursor's take)

**Path C, but staged.** Step 1 of W308 ships only the *system* —
a new `apps/cockpit/src/styles/tokens.css` + a single demo page
proving the tokens render. Step 2 ports the cockpit shell screen by
screen. The frozen bundle stays the production cockpit until the new
one is verified.

This matches the W307 / W308 boundary: taste (Claude) + system
(Cursor step 1) + migration (Cursor step 2). Each step ships
independently.

But the operator owns this call — Path A might be enough depending on
the W307 verdict.

---

## Token-location inventory (for reference)

| File | What lives there | Editable? |
|------|------------------|-----------|
| `design-system/tars/MASTER.md` | All MASTER tokens, full design contract | Yes, by hand |
| `design-system/tars/pages/*.md` | Page-level overrides | Yes, by hand |
| `desktop/src-tauri/web/assets/index-x27x8g94.css` | Shipping cockpit CSS (minified) | Technically yes (Path A); strategically no |
| `desktop/src-tauri/web/index.html` | Shipping cockpit HTML shell | Same as above |
| `docs/design/W307_refs/*.html` | Claude's W307 references (created in this wave) | Yes, by Claude; treated as artefact, not source |

**No `tokens.css` exists yet in any shipping form.**

---

## Pre-flight checklist for W308

- [x] Read Claude's verdict (W307 still in flight at time of step 0;
      revisit when it lands).
- [x] Operator picked Path A / B / C — **Path C, staged**.
- [x] Decision note added above and mirrored in `docs/AGENT_HANDOFF.md`.
- [x] `desktop/scripts/package-cockpit.sh` left untouched (step 0 does
      not replace the frozen bundle; step 2 will).
- [x] Cockpit drift smoke test added: `tests/test_cockpit_tokens_sync.py`
      (3 passing). Full pytest collection still resolves cleanly.
- [ ] **Step 1 (queued):** when Claude's `docs/design/W307_VERDICT.md`
      lands, operator marks each row approve/change/skip → Cursor
      updates `apps/cockpit/src/styles/tokens.css` + MASTER.md in the
      same commit; smoke test enforces sync.
- [ ] **Step 2 (queued):** wire `apps/cockpit/` into
      `desktop/scripts/package-cockpit.sh`; replace
      `desktop/src-tauri/web/` once parity is verified.

---

## Untouched in this wave

- `docs/handoff/W292_PROMPT_FOR_CURSOR.md` — older handoff, left
  in place; not part of W307/W308.
- `docs/design/W292_REFERENCES.md` — older design references,
  left in place; not part of W307/W308.

Both are untracked in git — I did not stage or delete them. If
they are stale, the operator can `git clean` them; if they are still
useful, they live where they are.
