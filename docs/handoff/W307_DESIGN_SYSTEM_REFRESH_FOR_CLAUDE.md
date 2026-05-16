# W307 — Design system refresh (handoff for Claude Code)

> **Owner.** Claude Code (`claude` CLI, Opus 4.x).
> **Why Claude and not Cursor.** Anthropic's `frontend-design` plugin is
> the strongest "anti-slop" rendering pass in our stack, and it ships
> exclusively for Claude Code. Cursor is keeping the engineering loop
> (code, tests, migrations); Claude is owning *taste*.
> **Boundary.** **Do not touch production component code.** This wave
> ships *system artefacts only*: a refreshed `DESIGN.md`, two reference
> HTML pages (hero + cockpit shell), a token-mapping diff against the
> current `design-system/tars/MASTER.md`, and a written verdict. The
> migration into React/Tauri lands in W308 under Cursor.

---

## 0. Mission in one paragraph

We already have a mature `design-system/tars/MASTER.md` (OLED black +
gold-accent + HUD wireframes), but operator feedback after listening to
the W294/W295 voice pass was: *"design still feels broken in places"*.
Run our full design-orchestration stack — **`ui-ux-pro-max` →
`frontend-design` → `web-design-guidelines`** — *with MASTER.md as the
starting point*, not as something to replace. Output: a written verdict
on what's strong, what's brittle, what to upgrade in tokens / typography
/ motion, plus two reference HTML pages we can A/B against the live
cockpit (`apps/showcase` once the React showcase is re-enabled, or
desktop windows in the meantime).

The deliverable Cursor will pick up next is `docs/design/W307_VERDICT.md`
plus the two reference HTMLs under `docs/design/W307_refs/`.

---

## 1. Context you need before you start

Read in order — **do not skip**:

1. `CLAUDE.md` (root) — product direction, "premium SaaS/AI experience,
   not generic admin UI".
2. `design-system/tars/MASTER.md` — the current source of truth
   (Real-Time Monitoring + HUD + OLED, gold-accent `#CA8A04`,
   typography pair, motion contract). **This is the baseline — your
   job is critique + evolution, not replacement.**
3. `design-system/tars/pages/*.md` — page-level overrides for hero,
   cockpit, settings.
4. `docs/AGENT_HANDOFF.md` — top SYNC block (W306) for what just
   landed.
5. `docs/VIDEO_TRANSCRIPTS.md` — operator's spoken intent. Especially
   the W294/W295 cockpit review where "design felt broken" originated.
6. `apps/showcase/src/` (if still present in your checkout) and
   `desktop/src/` for representative screens — at minimum *look at*
   the Hero, the Cockpit grid, and one Settings panel before you form
   an opinion.

Also relevant:

- `.claude/skills/ui-ux-pro-max/SKILL.md` — the visual skill we're
  using (v2.5+, supports `search.py --design-system -p "<project>"`).
- The Anthropic `frontend-design` plugin must be loaded
  (`claude plugin install frontend-design@claude-plugins-official` if
  missing). Verify with `claude plugin list | grep frontend-design`.
- `.claude/skills/web-design-guidelines/SKILL.md` and
  `.claude/skills/vercel-react-best-practices/SKILL.md` for the audit
  pass.

---

## 2. Why we *do not* want a brand-new system

The skill is great at generating fresh systems, but for TARS that
would erase a year of operator taste:

- Gold (`#CA8A04`) + cyan HUD (`#00FFFF`) is already in user-facing
  copy, marketing, app icon, voice persona names.
- `Space Grotesk + JetBrains Mono` is in the brand pages and the
  showcase. Changing it changes the *recognisable* surface.
- OLED black + 1px hairlines is the operator's stated preference.

So the cap is: **MASTER.md stays. We propose evolutions, not
replacements.** If you genuinely believe a primary token must change
(e.g. accent contrast fails WCAG in a real context), say so loudly in
the verdict with screenshots and the failing measurement, and let the
operator decide.

---

## 3. Execution plan — exact commands

Run these from the TARS repo root
(`/Users/alien/Documents/Claude/Projects/Jarvis/jarvis`).

### Step A — fresh `ui-ux-pro-max` pull, tuned for TARS

```bash
python3 .claude/skills/ui-ux-pro-max/scripts/search.py \
  "premium local-first AI neural cockpit operator console dark HUD sci-fi futurism real-time monitoring" \
  --design-system -p "TARS" \
  > docs/design/W307_uipro_dump.md
```

Read the dump. Compare against MASTER.md section-by-section. Build a
table in your scratch buffer: `Aspect | MASTER (current) | uipro (new)
| Verdict (keep/evolve/replace)`. Don't write the public verdict yet.

### Step B — `frontend-design` reference HTML (×2)

Generate **two** standalone HTML pages with the *current* MASTER
tokens (don't change them). The point is to see how the tokens behave
in a real composition — not to discover them.

1. `docs/design/W307_refs/hero.html` — the showcase hero (large title,
   eyebrow, dual CTA, the rotating-core scene as an inline SVG, live
   integrity meter in the live rail).
2. `docs/design/W307_refs/cockpit.html` — the cockpit shell (left
   awareness stream, central thread timeline, right policy gate panel,
   bottom status bar). Static content; no React.

Both pages must:

- Inline all CSS, no external CDN.
- Use the exact MASTER tokens — copy them as `:root` CSS variables.
- Load `Space Grotesk` + `JetBrains Mono` via `<link
  rel="preconnect">` + `<link rel="stylesheet">` from `fonts.bunny.net`
  (privacy-safer than Google Fonts CDN).
- Be ≤ 30KB raw.

Open both in a browser. Take screenshots. Save them next to the HTML
as `hero.png` / `cockpit.png` (use `screencapture -R` on macOS or
`magick screen:0 -crop ...` if you have ImageMagick).

### Step C — design review (`/plan-design-review`)

Invoke the skill on the two reference pages and the matching live
screens (if available). Rate each dimension 0–10, list the deltas,
write specific fix recommendations. **Do not auto-fix** — the goal of
this wave is *diagnosis*, not surgery.

### Step D — quality audit (`/web-design-guidelines`,
`/vercel-react-best-practices`)

Run both against the two reference pages. Capture every flag you find:
- Contrast pairs (text vs surface) — actual measurements, not vibes.
- Heading hierarchy / semantic structure.
- Motion respecting `prefers-reduced-motion`.
- Focus states visible at 7:1 against the surface.
- Tap targets ≥ 44×44.

(`vercel-react-best-practices` will mostly flag "n/a for static HTML"
— that's fine; we run it to set the bar for W308 when this lands in
React.)

### Step E — write the verdict

Compose `docs/design/W307_VERDICT.md` with this structure:

```
# W307 — Design system refresh verdict

## TL;DR
- Keep: [bulleted list of what's working]
- Evolve: [bulleted list of soft tweaks — same family, sharper numbers]
- Replace: [bulleted list of hard changes — with operator-decision flag]

## Token diff (proposed)
| Token | Current | Proposed | Why |

## Typography
- [analysis + recommendation]

## Motion
- [analysis + recommendation]

## Open questions for operator
- [things that need explicit "yes/no" before W308 migration]

## Files in this delivery
- docs/design/W307_uipro_dump.md
- docs/design/W307_refs/hero.html  + hero.png
- docs/design/W307_refs/cockpit.html + cockpit.png
- docs/design/W307_VERDICT.md (this file)
```

---

## 4. Acceptance criteria

The handoff back to Cursor is acceptable only if **all** of these hold:

- [ ] `docs/design/W307_VERDICT.md` exists and reads like an opinion,
      not a feature list. It must say "do X" or "don't do X", with
      reasoning. No fence-sitting.
- [ ] Token diff table has *concrete* hex values, not "make gold
      warmer".
- [ ] Both reference HTML pages open in Chromium/Safari and render
      without console errors.
- [ ] Both contrast measurements (body text on `--color-bg-1`,
      secondary text on `--color-bg-1`) are computed and reported.
- [ ] At least one motion concern is addressed (HUD pulse cadence,
      data-stream tick, reveal duration).
- [ ] `prefers-reduced-motion: reduce` is verified in both reference
      pages.
- [ ] No changes to `design-system/tars/MASTER.md` or any production
      component. *Verdict only.*
- [ ] One commit: `docs(design): W307 design-system refresh verdict
      (Claude)`. Push to a branch named `claude/w307-design-refresh`.

---

## 5. What Cursor will do next (W308)

Once the verdict lands and the operator marks an "approve / change X /
skip Y" against each row of the token diff, Cursor takes over:

- Migrates approved tokens into `design-system/tars/MASTER.md`.
- Updates the React tokens module (`apps/showcase/src/styles/tokens.css`
  or equivalent) — single commit per token group.
- Re-renders each cockpit surface against the new tokens, with
  screenshots in the PR.
- Runs `pytest` (must stay green from W306 baseline) and
  `frontend-design` audit per page.
- Lands behind a feature flag if any change is operator-divisive.

This split keeps taste and engineering on separate clocks.

---

## 6. Quick start (copy-paste into Claude Code)

```
Read docs/handoff/W307_DESIGN_SYSTEM_REFRESH_FOR_CLAUDE.md and execute
it end-to-end. Start with Step A. Do not touch any production code —
verdict and reference HTMLs only. When done, commit on branch
claude/w307-design-refresh and tell me what changed.
```

That's it. Branch + PR title, no chat back-and-forth.
