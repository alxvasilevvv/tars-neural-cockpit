# W308 — step 2 brief (for Cursor)

> **Author.** Claude (Opus 4), W307 design-pass owner.
> **Audience.** Cursor — owns the W308 implementation lane.
> **Purpose.** Pre-write step 2 so it lands in one bounded session
> instead of being re-deliberated. Builds on `1e7dcab` (step 1) and
> respects all constraints from `W308_PRE_FLIGHT_FINDINGS.md`.

---

## 0. State as of writing

- `apps/cockpit/` scaffold + tokens + `.cta`/`.glyph`/`.t-greeting`
  utilities — shipped in step 0 + step 1.
- `tests/test_cockpit_tokens_sync.py` — 6 passing.
- `docs/design/W307_refs/{hero,cockpit}.html` — visual ground truth
  (built by Claude with the *current* MASTER tokens; will need a
  one-time refresh after step 1 so they reflect the W307 verdict).
- `desktop/src-tauri/web/` — frozen Tauri bundle, still production.
- `desktop/scripts/package-cockpit.sh` — checks bundle exists, does
  not build.
- **Open deferred item:** `.surface-marketing` motion override
  (decided in `6231b34`, not yet applied).

---

## 1. Goal of step 2 (in one sentence)

Replace `desktop/src-tauri/web/` with a Vite-built artefact from
`apps/cockpit/` that visually matches the W307 reference HTMLs
(re-rendered against step-1 tokens) and ships the marketing motion
override — without changing the operator's runtime experience.

---

## 2. Sub-tasks (do in this order)

### 2.1. Refresh reference HTMLs against step-1 tokens

The two HTMLs at `docs/design/W307_refs/{hero,cockpit}.html` inline
the *pre-verdict* token values. They are the visual ground truth, so
they must be updated to:

- `--color-ink-3: #8A867B` (was `#5C5A52`)
- `--type-greeting: clamp(2.4rem, 5vw, 3.4rem)` (was implicit
  `clamp(2rem, 4.2vw, 2.6rem)`)
- `--motion-pulse: 3.6s` ambient + new `--motion-alert-pulse: 1.6s`
  (the hero's `<animate>` on `.ring-inner` and `.core` should retarget
  to `--motion-pulse` so they read as ambient, not alert)
- All other tokens unchanged (accent, hud, bg-* — verified by step-1
  drift smoke test).

Add a one-paragraph note at the top of each HTML: *"Re-rendered W308
step 2 against step-1 tokens. Source of truth = `apps/cockpit/src/styles/tokens.css`."*

### 2.2. Port hero + cockpit screens into `apps/cockpit/src/pages/`

Create two new pages alongside `tokens-preview`:

```
apps/cockpit/src/pages/
  tokens-preview.ts   # existing
  hero.ts             # new — port hero.html structure
  cockpit-shell.ts    # new — port cockpit.html structure
```

Each page composes from the existing `apps/cockpit/src/styles/` and
uses `.cta`, `.t-greeting`, `.t-num`, `.glyph` utilities. No new
tokens, no inline hex — if you need a value that isn't in tokens.css,
stop and ask why.

Add a router or hash-based selector to the existing
`apps/cockpit/index.html` so all three pages can be reached for visual
QA without changing the page-1 entrypoint.

### 2.3. Add the marketing motion override

In `apps/cockpit/src/styles/tokens.css`, append after the cockpit
default:

```css
/*
 * Marketing-class surface override. Apply class `surface-marketing`
 * to the root element of any landing / hero / share-card page.
 * Per W307 verdict resolution (6231b34): cockpit caps at 2 infinite
 * animations; marketing hero may use up to 4 because the rotating-
 * core scene IS the value prop.
 */
.surface-marketing {
  --motion-budget-max: 4;
}
```

And document in MASTER §7:

> Surfaces with `.surface-marketing` class lift `--motion-budget-max`
> to `4` to permit the hero's rotating-core scene. All other surfaces
> stay at `2`. Both still honour `prefers-reduced-motion`.

Extend the drift smoke test with:

```python
def test_marketing_motion_override_declared() -> None:
    css = _read(TOKENS_CSS_PATH)
    assert ".surface-marketing" in css and "--motion-budget-max: 4" in css
    md = _read(MASTER_PATH)
    assert "surface-marketing" in md
```

### 2.4. Wire `package-cockpit.sh` to build from `apps/cockpit/`

Replace the existence-check with an actual build step:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Build the new minimal cockpit.
pnpm --filter @tars/cockpit build

# Replace the frozen bundle.
rm -rf desktop/src-tauri/web
mkdir -p desktop/src-tauri/web
cp -R apps/cockpit/dist/* desktop/src-tauri/web/

echo "✓ desktop/src-tauri/web rebuilt from apps/cockpit/dist"
```

If Tauri's config (`desktop/src-tauri/tauri.conf.json`) hardcodes a
`distDir` of `web`, leave it — the path stays the same, only the
*producer* of the bundle changes. Verify with `cargo tauri build
--debug` locally that the desktop app still opens to the same shell.

### 2.5. Add a regression test for `package-cockpit.sh`

```python
# tests/test_package_cockpit_uses_apps_cockpit.py
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "desktop" / "scripts" / "package-cockpit.sh"

def test_script_invokes_apps_cockpit_build() -> None:
    text = SCRIPT.read_text()
    assert "pnpm --filter @tars/cockpit build" in text
    assert "apps/cockpit/dist" in text
```

### 2.6. Lint rule for the motion budget (lightweight)

Add a CSS-grep test that counts `animation-iteration-count: infinite`
declarations per scoped block in `apps/cockpit/src/pages/cockpit-shell.css`
(or wherever the cockpit shell CSS lives). Fail if > 2 within the
cockpit root selector. Marketing surfaces (`.surface-marketing`) are
excluded.

This is the closest thing to enforcement that doesn't require a real
CSS AST parser. If we want stricter, that's W309.

---

## 3. Visual-parity protocol (manual, ~15 min)

After 2.1–2.4 are done, before committing:

1. `pnpm --filter @tars/cockpit dev` — open `http://localhost:5173`.
2. Open `apps/cockpit/index.html` (router) → hero page.
3. Side-by-side: `open docs/design/W307_refs/hero.html` (the refreshed
   one from step 2.1).
4. Confirm visual parity on:
   - **Hierarchy**: greeting size, eyebrow weight, CTA pair spacing.
   - **Color**: accent fill, ink-3 on bg-1, hud cyan opacity.
   - **Motion**: ambient pulses cadence (3.6s) read as "all good",
     not "warning".
   - **Layout**: container max-width, hairline placement, corner
     bracket positioning.
   - **Typography**: Share Tech Mono on display, Fira Code on body,
     `.t-num` on the integrity meter.
5. Repeat for cockpit-shell.

**If any of these diverge by more than "intentional refinement", stop
and ask the operator before committing.** Step 2 must not silently
change the visual contract.

---

## 4. Rollback criteria

Revert step 2 if any of:

- `pnpm --filter @tars/cockpit build` fails on a clean checkout.
- Tauri dev/build cannot load `desktop/src-tauri/web/` produced by
  the new script (smoke: `cargo tauri build --debug` and visually
  open the .app).
- Bundle size grows past 80 KB raw / 25 KB gzipped without explicit
  operator approval (current step-1 baseline: 18 KB / 6 KB).
- Drift smoke tests fail.
- Visual-parity check (§3) shows a regression on hero, briefing
  greeting, ambient health pulse cadence, or accent CTA contrast.

Revert is one `git revert <step2 sha>` — keep the commit bounded.

---

## 5. Out of scope for step 2 (queue for W309)

- Migration of `experiments/*` deleted content. The W307 references
  are the new ground truth.
- React/framework migration. Vanilla TS stays.
- Real CSS lint with PostCSS AST. The grep test in §2.6 is enough
  for now.
- `desktop/scripts/package-cockpit.sh` cross-platform parity
  (Windows / Linux). macOS-first.
- New screens (settings, status, conversation strand). Step 2 only
  ports the two screens that have W307 reference HTMLs.
- The mono-glyph icon library — sanctioned set is in MASTER §4
  already; expand only when a real surface demands a new glyph.

---

## 6. Commit message (suggested)

```
feat(cockpit): W308 step 2 — port hero + cockpit shell to apps/cockpit/, swap frozen bundle

- Ports docs/design/W307_refs/{hero,cockpit}.html into apps/cockpit/src/pages/
  using step-1 tokens + .cta/.glyph/.t-greeting/.t-num utilities.
- Refreshes the reference HTMLs against step-1 tokens (ink-3 #8A867B,
  greeting clamp(2.4,5vw,3.4), motion-pulse 3.6s, motion-alert-pulse 1.6s).
- Adds .surface-marketing { --motion-budget-max: 4 } override (W307
  resolution addendum, 6231b34).
- Rewires desktop/scripts/package-cockpit.sh to pnpm-build apps/cockpit/
  and replace desktop/src-tauri/web/ contents.
- Drift smoke test grows from 6 → 8 tests (marketing override + script
  regression).
- Bundle: 18 KB → ~28 KB raw (estimated; hero scene SVG is the bulk).
- Visual-parity check passed against refreshed W307 references.

Production cockpit risk: medium (replaces frozen bundle). Rollback via
single git revert; package-cockpit.sh writes a new bundle each run.

Co-authored-by: Claude <claude@anthropic.com>  # for the step-2 brief
```

---

## 7. After step 2 — what's left in the W307 lineage

- **W307_VERDICT.md** § "Resolution" → fully applied.
- **W307_refs/*.html** → updated to step-1 tokens, serve as artefacts
  for future taste passes.
- **W308 step 0 + step 1 + step 2** → frozen-bundle problem
  permanently solved.
- **W309** could pick up: real CSS AST lint, settings / status /
  conversation-strand screens, Windows/Linux package-cockpit parity.

This brief is intentionally bounded. If new scope surfaces during
step 2, stop and write a new W309 brief — don't expand step 2.
