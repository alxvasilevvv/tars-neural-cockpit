# Backup Screenshots — slide 12 of TARS_v10.0_PRESENTATION.pptx

These four screenshots go in the four image slots on **slide 12**.
If the live demo fails, slide 12 IS the demo. Make them count.

Output them at **2× retina** (so they look crisp on projectors) and
save in `presentation/backup_screenshots/`:

```
presentation/backup_screenshots/
├── 01_voice_listening.png   # 2880×1800 @ 2x
├── 02_composer_diff.png
├── 03_audit_timeline.png
└── 04_usage_console.png
```

---

## Shot 1 — Voice cockpit listening (`01_voice_listening.png`)

**What it proves:** the monolith breathes; voice input is real, not
mocked.

**Setup:**
1. Launch TARS.app. Wait for monolith to render.
2. Cmd+Shift+Space to focus the window.
3. Press the spacebar / click mic to start listening.
4. Start saying ANY phrase (the waveform must be live).
5. **DO NOT FINISH THE PHRASE.** The mic must still be open at
   capture time.

**Capture:**
- `Cmd+Shift+4`, then **Space**, then click on the TARS window
  (captures the whole window with shadow).
- Save to `~/Desktop/TARS-shot-1.png`.

**Crop / edit:**
- Trim macOS chrome (red/yellow/green buttons) — keep just the
  cockpit panel. Aspect roughly 16:9.
- If the audio waveform is too quiet on the capture, take it again
  while clapping near the mic — gets a fatter, more photogenic
  waveform.

---

## Shot 2 — Composer diff panel (`02_composer_diff.png`)

**What it proves:** the Composer produces real multi-file diffs, not
just chat.

**Setup:**
1. In TARS, click the COMPOSER tab.
2. Type prompt: `Sort my downloads folder and write a one-page report on the contents.`
3. Wait for the plan to render. **Look for ≥3 file ops in the diff
   panel** (1 read of ~/Downloads, 1 write of report.md, 1 move op).
4. Make sure the "Accept hunks" button is visible and unclicked.

**Capture:**
- Same as shot 1 (`Cmd+Shift+4` then `Space` then click window).

**Crop / edit:**
- Frame to show: the prompt at top, the diff in the middle, the
  Accept/Reject CTAs at the bottom. Strip any irrelevant left-nav.

---

## Shot 3 — Audit timeline with verify button (`03_audit_timeline.png`)

**What it proves:** receipts are real, hash-chained, verifiable.

**Setup:**
1. Ensure `TARS_DEMO_SEED=1` ran (Phase 3 of DEMO-READY).
   `/api/receipts/recent` should return ≥5 items.
2. In TARS, click AUDIT tab.
3. Wait for timeline to render. Should show 5-15 receipts with
   green checks.
4. Hover the topmost receipt — the "Verify" button should appear.
5. Click "Verify" on the topmost receipt. A modal shows the Merkle
   path + Solana memo placeholder. **CAPTURE THIS MODAL OPEN.**

**Capture:**
- Cmd+Shift+4, Space, click window. The modal will be captured too.

**Crop / edit:**
- Frame to show: timeline on the left (3-4 receipts visible), modal
  on the right (Merkle proof). This is the most "wow" shot — give
  it the most pixels.

---

## Shot 4 — Usage console with today's spend (`04_usage_console.png`)

**What it proves:** observability is built-in, not afterthought.

**Setup:**
1. Pre-flow: trigger some token usage. Run 3-5 demo prompts so the
   counter is non-zero. (`Compose...`, `Summarize...`, anything.)
2. In TARS, click USAGE tab.
3. Wait for the pie chart to render (donut of provider/model split).
4. Today's spend should show roughly "$0.42" (vary by usage).
5. The live SSE counter at the top should be ticking — if not,
   trigger one more prompt then capture.

**Capture:**
- Cmd+Shift+4, Space, click window.

**Crop / edit:**
- Frame: top counter "Today: $0.42" + pie chart + tier-cap progress
  bar at the bottom. That's the value-density shot.

---

## Insertion into the deck

Open `presentation/TARS_v10.0_PRESENTATION.pptx` in Keynote.
Navigate to **slide 12** (titled "Demo backup — proof in screenshots").

If slide 12 has 4 placeholder boxes:
- Top-left   → `01_voice_listening.png`
- Top-right  → `02_composer_diff.png`
- Bottom-left → `03_audit_timeline.png`
- Bottom-right → `04_usage_console.png`

If slide 12 needs to be created:
- Insert New Slide → Two-column with title → set title to:
  *"Live demo backup — same proof, 0 risk"*
- Drag the four PNGs in. Auto-arrange to a 2×2 grid.
- Add a small caption under each (10pt): "voice", "composer",
  "audit", "usage" — that's it. Don't over-explain.

---

## Verification (do this once shots are in)

- Open the deck. Click slide 12.
- Project to a real screen (or AirPlay to Apple TV) and stand 6 feet
  away. Can you READ the receipt IDs in shot 3? If not, the
  screenshot is too small — re-take with TARS window bigger.
- Same test for the usage counter in shot 4.

If any screenshot is unreadable at projection distance, **take it
again**. A blurry "proof shot" is worse than no proof shot — it
signals "this person doesn't sweat the details."

---

## Bonus shots (optional, for follow-up email)

Capture two extras for the post-demo email send:

5. **Cmd+K palette open** — shows the "everything is one keystroke
   away" story.
6. **Connector page with green badges** — shows real OAuth (Gmail,
   GitHub, Slack, Calendar all wired).

Both go in the leave-behind PDF, not the deck.

---

*Last edit: day-of presentation. Re-take shots if you change cockpit
UI between today and tomorrow morning.*
