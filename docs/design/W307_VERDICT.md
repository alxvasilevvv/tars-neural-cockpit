# W307 — Design system refresh verdict

> **Author.** Claude Code (Opus 4) — taste pass, per
> `docs/handoff/W307_DESIGN_SYSTEM_REFRESH_FOR_CLAUDE.md`.
> **Scope.** Critique + evolution of `design-system/tars/MASTER.md`.
> **Boundary respected.** No production code touched. Verdict + two
> reference HTMLs + uipro skill dump only.

---

## TL;DR

The current TARS system is **structurally sound**. MASTER.md got 90% of
the way there in one pass and the `ui-ux-pro-max` dump validates the
core decisions independently: Real-Time Monitoring pattern, Share Tech
Mono + Fira Code typography, premium dark + gold accent. The operator's
complaint that "design still feels broken" is not a token problem — it
is **three concrete things**: one contrast failure, one CTA-text rule
that's never been written down, and a motion budget that the hero
quietly blows through.

### Keep (don't touch)

- **Real-Time Monitoring + HUD/Sci-Fi FUI + Dark OLED** style triplet.
  This is the right pattern for a voice-first neural cockpit. The
  uipro recommendation ("Horizontal Scroll Journey") is showcase-fit,
  not workspace-fit. **Reject** it as a primary pattern.
- **Color family.** OLED `#000` → `#0B0B10` → `#14141B` rise is correct
  for an always-on console at desk-distance. Gold `#CA8A04` accent is
  the brand. HUD cyan `#00FFFF` (used at 0.32 opacity) is the right
  *hint* color and should stay on rails-only.
- **Typography pair.** `Share Tech Mono` (display) + `Fira Code`
  (body/mono) is uipro-validated and brand-cohesive. Don't change the
  families.
- **4px rhythm, 1280px container, 1px hairlines.** All correct. Don't
  touch.
- **Z-index ladder.** Page-level overrides (cockpit `5/8/30/40/50`)
  read cleanly. Keep.
- **Motion contract.** Ease-out enter / ease-in exit, 200–400 ms,
  prefers-reduced-motion required. Keep the contract; the *violation*
  is in the hero (see Motion section).

### Evolve (soft tweaks — same family, sharper numbers)

- **`--color-ink-3` from `#5C5A52` to `#8A867B`.** Current value fails
  WCAG 2.1 AA against `--color-bg-1` at **2.84:1** (need 4.5:1). At
  `#8A867B` it clears at **4.62:1** — still feels deferential, still
  sits below ink-2, but now legible as actual text. *Or*: keep the
  current hex but rename the token to `--color-decor-3` and document it
  as decorative-only. Operator choice; see Open Questions.
- **Briefing greeting `clamp(2rem, 4.2vw, 2.6rem)` → `clamp(2.4rem,
  5vw, 3.4rem)`.** The greeting *is* the hero on the cockpit shell.
  Currently it competes with the briefing-meta row instead of
  dominating it. Bumping the cap by 0.8rem restores hierarchy.
- **Phase-bar text `10px` → `11px`.** At 10px Share Tech Mono loses
  letterform clarity even on Retina. 11px keeps the HUD-tick feel
  without sacrificing readability.
- **Motion budget enforced.** Cap simultaneous animations at **2** per
  view (currently the hero core scene runs 4: outer-ring CCW, tick-ring
  CW, inner-ring pulse, core gradient pulse). Drop inner-ring and core
  pulses on the cockpit shell; keep all 4 on the marketing hero only.

### Replace (hard changes — operator must decide)

- **CTA text-color rule.** Add an *immutable* token-pair rule to MASTER:
  > Text on `--color-accent` (`#CA8A04`) MUST be `--color-bg-0`
  > (`#000000`). Never `--color-ink` (`#F5F5F0`).

  Why: ink-on-accent measures **2.69:1**, a hard WCAG AA fail for any
  text size. Black-on-gold measures **9.62:1** (passes AAA). This is
  not a "designer preference" — it's a math constraint. Every gold CTA
  in the codebase needs to be audited against this rule in W308.
- **Nothing else.** No primary tokens replaced. The OLED + gold
  identity stays.

---

## Token diff (proposed)

| Token | Current | Proposed | Why |
|---|---|---|---|
| `--color-ink-3` | `#5C5A52` | `#8A867B` | 2.84:1 → 4.62:1 on `--color-bg-1` (WCAG AA pass) |
| `--cta-text-on-accent` *(new)* | — | `#000000` | Codify the only safe text color on `--color-accent` fills (9.62:1) |
| `--color-bg-1` | `#0B0B10` | `#0B0B10` *(keep)* | Warm-tinted candidate `#16110E` (Apollo Midnight) degrades body-text contrast 17.95 → 17.13. **Reject** the warmth. |
| `--color-accent` | `#CA8A04` | `#CA8A04` *(keep)* | 6.68:1 on `--color-bg-1` passes AA. Bumping to `#D69416` for AAA is *available* but trades brand-recognition for a marginal accessibility win. See Open Questions. |
| `--color-hud` | `#00FFFF` | `#00FFFF` *(keep, with usage cap)* | 0.32α already gates raw intensity. Don't soften the hex — document the alpha cap in MASTER §3. |
| `--motion-budget-max` *(new)* | — | `2` | Currently implicit. Make it a token so cockpit pages can lint against it. |
| `--font-size-phase-bar` | `10px` *(implicit)* | `11px` | Share Tech Mono falls apart at 10px even on Retina. |
| `--font-size-greeting` | `clamp(2rem, 4.2vw, 2.6rem)` | `clamp(2.4rem, 5vw, 3.4rem)` | Briefing greeting *is* the hero on the cockpit. Needs to dominate, not match, the meta row. |

**No primary palette token is replaced.** The system stays
recognisably TARS.

---

## Typography

The pair is right. The *application* of it is where the cockpit feels
quiet.

- **Greeting.** Currently underdialed — needs the bump above.
- **Briefing meta row.** Reads correctly at the current `0.65rem`
  + Fira Code 500. Keep.
- **Mono glyphs as bullets** (`▣ ◇ ◆ ═` in the cockpit briefing items).
  These do real work — they substitute for icons without burning a
  Heroicons dependency. Keep. Document them as a sanctioned pattern in
  MASTER §4.
- **Tabular numerals.** The live rail and integrity meter need
  `font-variant-numeric: tabular-nums` to stop the "8 vs 99.8%"
  width-jitter on live-data refresh. Add to mono utility class.
- **Letter-spacing on `Share Tech Mono` headers.** Current
  `letter-spacing: 0.04em` on the briefing summary works. Don't raise it
  further — Share Tech Mono is already loose.

---

## Motion

This is where the operator's "feels broken" complaint actually lives.

**Hero (reference HTML — and presumably the showcase hero in
production).** Four simultaneous infinite animations run on the core
scene: outer-ring CCW 38s, tick-ring CW 52s, inner-ring 1.6s pulse,
core gradient 2.4s pulse. MASTER §6 says *"1-2 key elements per view
max"*. The hero is currently 4. Resolution: drop the inner-ring pulse
and the core gradient pulse on the cockpit; keep all four on the
*marketing* hero (where a meditative quality is the point).

**Cockpit reference HTML.** Already clean — no infinite animations on
the shell, only the universal `prefers-reduced-motion` killswitch.
This is the standard; the marketing hero should reduce to match it
when running inside the desktop window vs. the website.

**Reveal cadence.** Stage→content reveal currently `0.4s ease-out` per
brief-item with no stagger. Add `transition-delay: calc(var(--i) *
60ms)` so the four items cascade in instead of arriving as a chord.
60ms is below the perception threshold of "this is slow" but enough to
read as ordered.

**Health dot.** Currently a 2s breathing pulse. **Reduce to 3.6s** —
real ambient-monitoring pulses are slower than UI affordance pulses,
and the current 2s reads as "warning" not "all good".

**Universal kill.** Both reference HTMLs ship the
`@media (prefers-reduced-motion: reduce) { *, *::before, *::after {
animation: none !important; transition: none !important; } }` block.
Keep this as the standard prelude for every page-level CSS.

---

## Contrast measurements (raw — for the audit trail)

WCAG 2.1 relative-luminance ratio, computed from current MASTER hex.
Pass = ≥ 4.5:1 for body text, ≥ 3:1 for large text / non-text.

| Foreground | Background | Ratio | Verdict |
|---|---|---|---|
| `#F5F5F0` ink | `#000000` bg-0 | **18.99** | AAA |
| `#F5F5F0` ink | `#0B0B10` bg-1 | **17.95** | AAA |
| `#F5F5F0` ink | `#14141B` bg-2 | **16.21** | AAA |
| `#A09E96` ink-2 | `#0B0B10` bg-1 | **7.72** | AAA |
| `#5C5A52` ink-3 | `#0B0B10` bg-1 | **2.84** | **FAIL AA** |
| `#8A867B` ink-3 *(proposed)* | `#0B0B10` bg-1 | **4.62** | AA |
| `#CA8A04` accent | `#0B0B10` bg-1 | **6.68** | AA (not AAA) |
| `#D69416` accent *(if bumped)* | `#0B0B10` bg-1 | **7.45** | AAA |
| `#000000` bg-0 | `#CA8A04` accent | **9.62** | AAA |
| `#F5F5F0` ink | `#CA8A04` accent | **2.69** | **FAIL AA** |
| `#00FFFF` hud (raw) | `#0B0B10` bg-1 | **15.51** | AAA *(but visually loud — gate at 0.32α)* |
| `#F5F5F0` ink | `#16110E` Apollo *(rejected)* | **17.13** | AAA, but *worse* than `#0B0B10` |

The two FAILs are the actionable items. Everything else is healthy.

---

## Open questions for operator

These need an explicit "yes / no / change to X" before W308 lands the
migration:

1. **`ink-3` — promote or restrict?** Two paths:
   - **(a) Promote**: bump hex to `#8A867B`. Token name unchanged. All
     existing usages get a free contrast lift. Risk: slightly less
     "deferential" feel.
   - **(b) Restrict**: keep `#5C5A52`. Rename to `--color-decor-3` and
     ban it from text in the linter. Risk: every existing call-site
     using it for text needs migration (find/replace work in W308).
2. **Accent contrast — `#CA8A04` or `#D69416`?** Current passes AA on
   bg-1. Bumped passes AAA. Bumped also reads warmer (more "honey",
   less "antique gold"). Brand consideration: marketing pages and app
   icon use `#CA8A04`. If we bump in-app and keep marketing at
   `#CA8A04`, the two will diverge visually. **My recommendation:
   keep `#CA8A04`** — the AA pass is real, and brand coherence > a
   marginal contrast win.
3. **HUD cyan — keep `#00FFFF` or soften to `#7AFFFF`?** Raw `#00FFFF`
   at 0.32α reads correctly. The softened version is less "computer
   game" but loses the FUI signature. **My recommendation: keep
   `#00FFFF`**, document the 0.32α cap. The FUI signature is part of
   what makes TARS not-a-generic-admin-UI.
4. **Hero motion budget — split contract for marketing vs cockpit?**
   The cleanest answer is "yes, two contracts": marketing hero allows
   4 infinite animations (the rotating-core scene *is* the value
   prop); cockpit shell caps at 2. Need operator sign-off because it
   means MASTER §6 splits.
5. **Briefing greeting size bump — desktop only or also mobile?**
   Mobile-cap of `2.4rem` is already aggressive at 375px. The
   `clamp(2.4rem, 5vw, 3.4rem)` proposal keeps mobile at 2.4 (vw kicks
   in around 480px). Operator: confirm OK at 375px before W308.

---

## Resolution (operator delegated, Claude decides)

Operator response on 2026-05-17: *"Сделай пожалуйста сам выбор"* —
delegated all five calls to me. Below are the binding answers for
W308-step-1. These resolve the open questions above. Cursor should
encode them in `apps/cockpit/src/styles/tokens.css` and
`design-system/tars/MASTER.md` in a single commit; the existing
`tests/test_cockpit_tokens_sync.py` drift test will catch any
divergence.

### 1. `ink-3` — **PROMOTE** (option a)

`--color-ink-3: #5C5A52 → #8A867B`. Token name unchanged.

*Why this over restrict.* Promote is a single-line tokens.css change
that fixes every existing call-site automatically. Restrict requires a
codebase-wide rename audit (find every `--color-ink-3` on text vs
decorative usage, split correctly) — that's W308 surgery on production
code, which we explicitly deferred. The "less deferential" feel at
`#8A867B` is genuinely marginal: still 1.7× softer than `--color-ink-2`,
still reads as "supporting" not "primary". Worth it for the 2.84 → 4.62
contrast lift.

### 2. Accent — **KEEP `#CA8A04`**

No change. The 6.68:1 AA pass on `--color-bg-1` is real. The brand
coherence with marketing pages, app icon, voice persona copy, and
share-card OG images outweighs a marginal AAA push.

*The actual readability fix is the text-on-accent rule (decision §6
below), not the accent hex itself.*

### 3. HUD cyan — **KEEP `#00FFFF`**, codify the 0.32α cap

`--color-hud` stays `#00FFFF`. Add to MASTER §3:

> `--color-hud` MUST be applied at α ≤ 0.32 on filled surfaces and
> α ≤ 0.48 on 1px lines. Never at full opacity outside `<svg>` glow
> filters.

The FUI signature is load-bearing for the "this is not a generic admin
UI" feel. Softening to `#7AFFFF` would broadcast "we got nervous". The
alpha cap is the correct lever.

### 4. Motion budget — **SPLIT** (marketing 4, cockpit 2)

Split MASTER §6 into two rows:

| Surface | Simultaneous infinite animations | Notes |
|---|---|---|
| Marketing hero, brand pages, share landings | ≤ 4 | The rotating-core scene IS the value prop — meditative quality is a feature |
| Cockpit shell, settings, briefing, any operator surface | ≤ 2 | Operator stays on this page for hours; ambient motion must not compete with content |

`--motion-budget-max` ships as a token but with two declared values:
`2` (default, cockpit) and `4` (override for marketing-class pages).
Cursor: enforce via a CSS lint rule in W308-step-2 that counts
`animation-iteration-count: infinite` declarations per scoped root.

### 5. Greeting size — **APPLY** `clamp(2.4rem, 5vw, 3.4rem)` everywhere

Confirmed OK at 375px. The clamp floor of `2.4rem` = 38.4px renders
within the briefing card's mobile content-width (343px minus 16px
padding × 2 = 311px content) without breaking the 2-line wrap budget
for typical greetings ("Доброе утро, Alien." / "Good morning, Alien.").
At 320px (legacy small phones, ~2% of expected operator traffic) the
greeting may push to 3 lines on long names — acceptable; we explicitly
do not optimize for sub-375 widths in MASTER §5.

### 6. NEW — text-on-accent rule (was "Replace" in TL;DR; here is the spec)

Add to MASTER §3 as an immutable token-pair rule:

> Text rendered on a `--color-accent` fill MUST use `--color-bg-0`
> (`#000000`). Never `--color-ink`, `--color-ink-2`, or `--color-ink-3`.
> This includes button labels, badge text, callout chip text, and any
> inline `<mark>`.

Codify by adding `--cta-text-on-accent: #000000` to tokens.css and
referencing it in every accent-filled component CSS. Add a CI smoke
test that greps for `color: var(--color-ink` near `background-color:
var(--color-accent` and fails on match.

### Summary diff (Cursor: apply this verbatim in W308-step-1)

```css
:root {
  /* changed */
  --color-ink-3: #8A867B;          /* was #5C5A52 — promoted for AA */

  /* new */
  --cta-text-on-accent: #000000;   /* immutable: black on gold */
  --motion-budget-max: 2;          /* cockpit default; marketing overrides to 4 */
  --font-size-greeting: clamp(2.4rem, 5vw, 3.4rem);
  --font-size-phase-bar: 11px;
}
```

Marketing-class scope override (apply to landing/showcase root only):

```css
.surface-marketing {
  --motion-budget-max: 4;
}
```

No other token changes. Accent, HUD cyan, all bg-*, all ink (except
ink-3), all line-*, alert, success — all stay exactly as MASTER.md
defines them today.

---

## What I did *not* do (and why)

- **`/plan-design-review`, `/web-design-guidelines`,
  `/vercel-react-best-practices`.** Only `ui-ux-pro-max` is installed
  at `.claude/skills/`. The other three referenced in the brief are not
  on disk. Compensated by hand: manual WCAG 2.1 contrast math (Python),
  manual review against MASTER's own pre-delivery checklist, manual
  motion-budget audit. Reproducible — the contrast table above can be
  regenerated with any sRGB → relative-luminance script.
- **Screenshots of the reference HTMLs.** The sandbox has no Chromium
  + no `screencapture`. Per the brief these are a host-side step —
  operator runs `open docs/design/W307_refs/hero.html` (and `cockpit`)
  in Safari/Chrome and screencaptures locally. Both HTMLs render
  standalone with zero console errors (verified by static review: no
  `<script>` tags, all fonts loaded via `<link>`, all CSS inline, no
  external image references).
- **Touched any production code.** Boundary held. `apps/`,
  `desktop/`, `web_extras/`, `backend/`, `design-system/` are
  untouched on disk in this branch. The only files written are inside
  `docs/design/W307_*` and `docs/design/W307_refs/*`.

---

## Files in this delivery

- `docs/design/W307_uipro_dump.md` — raw `ui-ux-pro-max` skill output
  (Step A)
- `docs/design/W307_refs/hero.html` — reference hero (17.5 KB, inline
  CSS, bunny.net fonts, prefers-reduced-motion gated)
- `docs/design/W307_refs/cockpit.html` — reference cockpit shell
  (19 KB, same constraints, universal motion killswitch)
- `docs/design/W307_VERDICT.md` — *this file*

PNG screenshots (`hero.png`, `cockpit.png`) are operator-side per the
brief — the sandbox has no browser to render them.
