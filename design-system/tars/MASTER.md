# TARS — Design System (Master)

> Synthesized via `ui-ux-pro-max-skill` v2.5 (Step 2 + Step 3 + Step 4 of
> the SKILL.md workflow). The auto-pick from `--design-system` matched the
> wrong product category, so this file is the manually-synthesized result
> from focused domain searches in `style`, `landing`, `typography`, `ux`
> and `--stack html-tailwind`.

This is the **Source of Truth** for every TARS surface (showcase v2,
cockpit, marketing pages). Page overrides live in `pages/<slug>.md`.

---

## 1. Style direction

A blend of four skill-DB styles, in order of weight:

1. **HUD / Sci-Fi FUI** (primary visual language)
   - 1px hairlines, decorative tech markers (corner brackets, ticker
     ribbons), monospaced labels.
   - Glow only on the single accent, sparingly: `text-shadow: 0 0 12px
     rgba(103, 232, 249, 0.55)` and `box-shadow: 0 0 24px
     rgba(103, 232, 249, 0.18)`.
   - Decorative ambient: scanline opacity ≤ 0.04, only on the WebGL stage.
2. **Exaggerated Minimalism** (typography & whitespace)
   - Hero `clamp(3.5rem, 8.5vw, 9rem)`, weight 800, `letter-spacing:
     -0.05em`. Section vertical rhythm 160–200px.
3. **Dark Mode (OLED)** (palette & contrast)
   - Background near-black, text contrast ≥ 7:1. No `#FFFFFF` background
     anywhere.
4. **AI-Native UI** (contextual surfaces)
   - Context cards with subtle `border-left` accent. Streaming-text
     animations only for AI-generated copy (none on the marketing page).

## 2. Pattern

**TARS Cockpit Hero + Live Rail.** Custom — neither a "Portfolio Grid"
nor an "App Store Landing" fits an AI agent runtime. Section order:

1. Hero — eyebrow + massive split title + 3D core scene + dual CTA.
2. Live Rail — fixed-width horizontal strip of awareness streams with
   tick markers and live integrity number.
3. Domain Packs — 4-up grid, monolithic cards, single accent line on the
   left edge per pack.
4. How It Works — 3 numbered steps, oversized numerals, terse copy.
5. Cockpit footer — single deep-link to the operator surface.

CTA placement: above the fold (Open Cockpit + Explore Domains).
Secondary CTA repeats in the footer ("Open Cockpit").

## 3. Palette

| Token | Hex | Use |
|-------|-----|-----|
| `--bg-0` | `#06070D` | Page background (deep ink). |
| `--bg-1` | `#0A0D18` | Raised surfaces (cards, footer). |
| `--bg-2` | `#11162A` | Sub-surfaces / highlight strips. |
| `--ink` | `#F4F6FB` | Primary text. |
| `--ink-2` | `#9AA3B5` | Secondary text & metadata. |
| `--ink-3` | `#5C6377` | Tertiary / disabled. |
| `--line` | `rgba(244, 246, 251, 0.06)` | Hairlines & cards borders. |
| `--line-hot` | `rgba(103, 232, 249, 0.28)` | Active hairline / focus. |
| `--accent` | `#67E8F9` | The one cyan accent. **Only one.** |
| `--accent-soft` | `rgba(103, 232, 249, 0.55)` | Subtle glow & rims. |
| `--alert` | `#FBBF24` | Live / amber telemetry only (LIVE dot, integrity). |
| `--success` | `#34D399` | Success states only. |

**Anti-patterns (banking AI rules carry over):**
- No AI-purple/pink rainbow gradients. Period.
- No second hue without functional meaning.
- No emoji as icons. Use SVG (Heroicons / Lucide / inline tech glyphs).

## 4. Typography

| Role | Font | Notes |
|------|------|-------|
| Display / hero | **Space Grotesk** 800 | `letter-spacing: -0.05em`, `clamp(3.5rem, 8.5vw, 9rem)`. |
| Body / paragraphs | **Inter** 400/500 | Line-height 1.65, max-width 56ch. |
| Technical labels / nav / HUD | **Space Mono** 400/500 | `letter-spacing: 0.18em`, `text-transform: uppercase`, 11px. |

CSS import:
```css
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700;800&family=Inter:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap');
```

## 5. Layout

- Container max-width: `1280px` (no `max-w-7xl` wider).
- Side padding: `px-4 sm:px-6 lg:px-10`.
- Section vertical: `pt-[140px] pb-[140px]` (down from 200px on mobile).
- Z-index scale: `10 / 20 / 30 / 50`. Never `9999`.
- Floating navbar: `top-4 left-4 right-4`, never `top-0`.

## 6. Effects

- Glow: only on `--accent`, only on hero title's accent word and on
  primary CTA hover. `text-shadow: 0 0 14px var(--accent-soft)`.
- Hover transitions: 200ms ease, color/opacity only (no `scale` shifts on
  cards — use `translateY(-2px)` at most).
- Decorative HUD brackets at viewport corners: 1px cyan, 24×24 SVG, fixed
  position, opacity 0.35, hidden < 880px.
- Bloom in WebGL: intensity ≤ 0.4, threshold ≥ 0.9. The 3D scene is a
  background sculpture, not the focus.
- Scanlines: skip on the page DOM (HUD-only on the canvas if at all).

## 7. Motion

- Hero text: word stagger reveal, 90ms gap, ease-out, 800ms total.
- Magnetic cursor: 18px ring, 4px dot, mix-blend-mode difference.
- ScrollTrigger reveals: y=20, opacity 0→1, 0.6s, stagger 0.08s.
- Counter animation: 1.4s with `gsap.to` + custom easing.
- **Always** wrap motion in `prefers-reduced-motion: reduce` opt-out.

## 8. Implementation checklist (skill-derived)

- [x] No emojis as icons.
- [x] All clickable elements have `cursor-pointer`.
- [x] Hover states = color/border/opacity (no layout-shifting transforms).
- [x] Transitions 150–300ms.
- [x] Focus visible: `focus-visible:ring-2 focus-visible:ring-[var(--accent)]`.
- [x] `prefers-reduced-motion` respected on every animation.
- [x] Z-index scale ≤ 50.
- [x] Body has `overflow-x: hidden` to kill horizontal scroll.
- [x] Responsive at 375 / 768 / 1024 / 1440.
- [x] Text contrast 7:1+ for primary text on `--bg-0`.

## 9. Anti-patterns (avoid)

- Rainbow gradients on hero text or CTAs.
- Multiple competing focal objects in the WebGL scene (no monolith bars,
  no random cluster snowstorm — exactly one sculpture).
- Animated bars / spinners on decorative elements.
- HUD that wraps the entire viewport — keep it minimal, single-corner.
- `font-size` in px without clamp on hero — looks tiny on 4K, huge on iPhone.

## 10. Pages

- `pages/showcase-v2.md` — overrides for the showcase landing.
- `pages/cockpit.md` — overrides for the operator console (when added).
