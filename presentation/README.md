# TARS v10.0.0-rc.1 — Presentation Pack

> **Built:** W272, 2026-05-15 — the night before v10.0 GA.
> **Purpose:** the one deck Alien presents tomorrow morning.

This folder is the speaker's kit. Everything inside is camera-ready,
nothing here ships with the product.

---

## Files

| File | Use |
|---|---|
| `TARS_v10.0_PRESENTATION.pptx` | 20-slide deck. Cinematic dark, Interstellar-monolith inspired. Open in Keynote or PowerPoint. |
| `TARS_v10.0_DEMO_CHEATSHEET.md` | Single page, tape it next to the laptop. Pre-demo checklist + 5-step flow + backup plans + Q&A. |
| `build_deck.py` | Source builder. Re-run to regenerate the PPTX after any copy change. |
| `qa_render/` | LibreOffice → PDF → JPG render set used during visual QA. Safe to delete. |

---

## How to use

### 1. Open the deck

- **Keynote** (preferred for macOS):
  `open TARS_v10.0_PRESENTATION.pptx`
  Keynote will offer to convert — accept. Save the `.key` next to it so you
  don't lose the cinematic motion if you add Magic-Move transitions.
- **PowerPoint:** opens natively. The deck is 16:9, no template
  dependencies, no embedded fonts — Calibri + Consolas only.

### 2. Replace the placeholder screenshots (slide 12)

Slide 12 ships four dark placeholders. **Replace before going live.**

Capture order on `TARS.app`, 2x retina, dark theme, no devtools overlay:

1. Monolith in **listening** state — cyan-violet strip visible
2. **Audit Explorer** with at least one receipt + Solana TX hash badge
3. **Composer panel** with a real multi-file diff in view
4. **USAGE tab** showing live token meter + $MEEET balance

Drop the four images onto the four "[ screenshot placeholder ]" frames
on slide 12. Keep the captions and color borders as-is.

### 3. Dry-run twice before going live

- **Dry-run #1 — slides only.** Speak the speaker notes verbatim. Time
  yourself. Target: 18 minutes for 20 slides, plus 5 minutes for the
  live demo (slide 5 → slide 6). If you exceed 23 minutes, cut slide 17
  or 14.
- **Dry-run #2 — full rehearsal with the laptop demo.** Run the
  5-step demo flow from the cheatsheet end-to-end. Don't read from
  the cheatsheet during live delivery — only glance.

### 4. Hide slide 19 before live delivery

Slide 19 is the Q&A presenter notes. **Hide it** before going live:

- Keynote: right-click slide 19 → **Skip Slide**
- PowerPoint: right-click slide 19 → **Hide Slide**

It's safe if you forget — the answers are accurate — but the audience
shouldn't see the prompt-cards mid-deck.

### 5. Export a leave-behind PDF

After replacing screenshots:

```bash
soffice --headless --convert-to pdf TARS_v10.0_PRESENTATION.pptx
```

That gives you `TARS_v10.0_PRESENTATION.pdf` to email after the meeting.

---

## Regenerating the deck

If you change any speaker copy:

```bash
python3 build_deck.py TARS_v10.0_PRESENTATION.pptx
```

Requires `python-pptx >= 1.0`. No other dependencies.

For visual QA after a change:

```bash
soffice --headless --convert-to pdf TARS_v10.0_PRESENTATION.pptx --outdir qa_render
cd qa_render && pdftoppm -jpeg -r 100 TARS_v10.0_PRESENTATION.pdf slide
open slide-01.jpg  # spot-check
```

---

## Design notes (for future edits)

- **Palette:** background `#07080d` near-black, body `#cbd5e1` light gray,
  primary white. Accents indigo `#6366f1`, violet `#8b5cf6`, cyan `#06b6d4`.
  See `STORYBOARD_VOICE_COCKPIT.md` palette tokens — same family.
- **Typography:** Calibri for titles/body, Consolas for eyebrows / code /
  numbers. Don't add a third typeface.
- **Visual motif:** the cyan-violet light strip on the monolith. It repeats
  on slides 1 and 20 and the title-bar eyebrow color on every interior slide.
- **No accent underlines** (per SKILL.md pptx rules — they read as
  AI-generated). Use whitespace to separate eyebrow + title instead.
- **Footer:** `TARS · v10.0.0-rc.1 · meeet.world` on every interior slide.
  Page number bottom-right.

---

## Owner

Alien (founder).  This deck is W272 in the master roadmap. Treat it as
canonical until the GA cut goes out tomorrow.
