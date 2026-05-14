# TARS v10.0.0-rc.1 — Demo Runbook

**Owner:** alienram@icloud.com
**Date:** day-of presentation
**Length:** read in ~6 min · execute in ~45 min end-to-end

> One file. Top-to-bottom. Don't skip. Every step has a "if-this-fails"
> branch right next to it.

---

## 0. Mindset (60 seconds, read this first)

- You have shipped 270+ waves. The product works. The demo works.
- If anything breaks live, you have `scripts/PRESENTATION-EMERGENCY.command`
  on the dock. 30-second total recovery. Use it without apology.
- If recovery fails, you have backup screenshots and a deck. The deck
  is the story; the live demo is the proof. You can give a great talk
  with zero live demo.
- Smile. Speak slowly. Wait for laughs to land before moving on.

---

## 1. T-30 minutes — Pre-flight

**Goal:** every green light on `DEMO-READY.command` before you sit down.

1. Open Terminal. (Not iTerm — Terminal.app, simpler default.)
2. Double-click `scripts/DEMO-READY.command` in Finder.
   - Watch the 8 phases scroll past. Total time: ~90s to 2 min.
   - If all 8 phases green → terminal auto-closes after 10s. You're done.
   - If any fail → terminal stays open with the failure + fix line.
3. Verify the eyeball checklist printed at the end:
   - [ ] Monolith pulsing in TARS.app cockpit
   - [ ] AUDIT tab populated (≥5 receipts visible)
   - [ ] USAGE tab live counter + pie chart
   - [ ] Cmd+K palette opens with fuzzy search
   - [ ] COMPOSER tab shows ≥1 plan with diff
4. Charge laptop (target 100% — talks always run long).
5. Mute notifications:
   - System Settings → Focus → Do Not Disturb → ON until 3 PM
   - Slack: command-shift-y (snooze)
   - Mail: quit it entirely
   - Messages: quit it entirely
6. Close ALL Chrome tabs except:
   - Gmail (so slide-6 "draft visible" works)
   - github.com/alienram/jarvis (for the QR-code share)
   - meeet.world (in case Q&A goes there)
7. Open Keynote: `presentation/TARS_v10.0_PRESENTATION.pptx`
   - Verify all 20 slides render
   - Test the 2 embedded videos play (if any)
8. Open `presentation/TARS_v10.0_DEMO_CHEATSHEET.md` in a side window.
   Print it. Tape it to the laptop palm-rest. **Look down, not at the
   audience, when you forget a line.** That's what the cheat sheet
   is for.

**If `DEMO-READY` fails after 2 retries:** run
`scripts/PRESENTATION-EMERGENCY.command` once. That nukes everything
and rebuilds in 30s. Then re-run `DEMO-READY`. If it still fails →
you go demo-less. Skip to **slide-12 screenshots** strategy below.

---

## 2. T-5 minutes — Dry run

Do the 5-step demo flow ONCE, alone, before the room fills.

| # | Action | Listen for | If it differs |
|---|--------|------------|---------------|
| 1 | `Cmd+Shift+Space` | TARS window front-and-center, monolith breathing | Click dock icon. Retry. |
| 2 | Speak: *"Compose a thank-you to last week's investors."* | STT waveform pulses, text appears in chat | Use text input below mic. Same outcome. |
| 3 | Wait for Composer panel | Diff appears in ~10s with 2-3 file ops | If >20s: cancel, narrate the cheat-sheet diff manually. |
| 4 | Click **Accept hunks** | Toast: "Draft saved to Gmail" | Switch to Gmail tab — draft visible. If not: skip Gmail, show the diff. |
| 5 | Open **Audit Explorer** tab | Latest receipt at top with green check | If empty: scroll the list; older receipts are still proof. |

**Total dry-run target: 45 seconds.** If yours runs 60+, you're
talking too much between steps. Trim.

After the dry run:
- [ ] Reset by restarting TARS.app (so live demo starts fresh)
- [ ] Open Audit Explorer briefly to pre-warm the panel
- [ ] Sip water. Sit down. Breathe.

---

## 3. Live demo — minute-by-minute (15 min total slot)

### Minute 0:00 — Walk-on

Open Keynote slide 1. Title: **TARS v10.0 — your second brain, real**.

**Say (verbatim):**
> "Show of hands — how many of you have shipped a side project this
> month? Keep your hands up if you wish you'd shipped two."

(Pause. Count. Smile.)

> "What if a piece of software could keep both of those projects
> moving while you sleep? Not write a tweet about it. Actually move
> them. That's what I want to show you."

### Minute 0:30 — Problem slide (slide 2)

**Say:**
> "Cursor solved coding. But coding is 5% of the work that ships a
> product. The other 95% — investor email, contract review, expense
> sorting, weekly report — still happens in 12 browser tabs.
> We built TARS for that."

(Click through slide 3-5: problem → market → product overview.
30 seconds total. Don't dwell.)

### Minute 1:30 — Product slide (slide 6)

> "Let me just show you."

Switch to TARS.app. (Cmd+Tab. Don't fumble.)

### Minute 1:35 — THE DEMO

**Run the 5-step flow from §2 above.** Words in the cheat sheet.
Eyes on the audience, not the screen, except when something visually
lands (Composer diff, Audit receipt). Then you LOOK at the screen so
they do too.

Land it at **~45 seconds**. Resist the urge to "and also..." If they
want to see more, they'll ask in Q&A.

### Minute 2:20 — Receipts slide (slide 11)

> "Every single thing you just saw is hash-chained in that receipt
> ledger. Tomorrow night we anchor the day's root to Solana. That's
> the moat — proof that your second brain actually did what it said
> it did."

(Slide 12 has the backup screenshots in case the live demo failed.
If demo succeeded, fly past slide 12 in 2 seconds — don't re-show.)

### Minute 2:40 — Market / GTM (slides 13-16)

Pricing, tiers, distribution. Stick to the deck — don't improvise.
4 minutes total.

### Minute 6:40 — Roadmap (slide 17)

> "Here's what's already merged for v10.1. Multi-user workspaces.
> Marketplace open. AI Clone v2."

### Minute 7:30 — Ask (slide 18)

State the ask. **Sharp. One sentence. Stop talking.**

### Minute 7:45 — Q&A (5-min buffer)

Use the 5 anticipated questions on the cheat sheet. Answers are
one-line. If a question is off-script, say:

> "Good question — let me think. [Take 3 seconds.] Here's how I'd
> answer that."

(Three seconds of silence read as "thoughtful." Three seconds of
"um" read as "unprepared." Use the pause.)

### Minute 12:45 — Closing line (slide 20)

**Verbatim. Don't improvise. This is the line that gets quoted.**

> "Cursor did this for code. We're doing this for everything else.
> v10 ships tomorrow."

Then stop. Don't add. Don't apologize.
First audience question after this line tells you what landed.

---

## 4. Fallback strategy — if live demo fails

You have THREE layers of fallback. Use them in order:

### Layer 1: Emergency script (recover in 30s, finish the demo)

If TARS hangs, crashes, or refuses to respond mid-step:
1. Say: "One sec — let me give it the engineering equivalent of a coffee."
2. Open dock, click `PRESENTATION-EMERGENCY.command` (you put it
   there at T-30).
3. Wait ~30s while it runs. Fill the silence with the *value prop*
   slide story from cheat-sheet §1 (the four bullet points).
4. When TARS comes back up, resume from step 1 of the demo.

### Layer 2: Backup screenshots (skip live entirely)

If the emergency script also fails (rare, but possible):
1. Don't apologize. Don't explain. Just say:
   > "I prepared screenshots in case the wifi was weird — they make
   > the same point faster."
2. Click slide 12 (screenshots are pre-loaded — see
   `BACKUP_SCREENSHOTS_GUIDE.md`).
3. Narrate the same 5-step story over the screenshots. ~35 seconds.

### Layer 3: No-demo talk (hard fail mode)

If TARS won't run at all (cert revoked, OS update, etc.):
1. Skip slides 6-11 entirely. The deck still tells the full story.
2. Spend the time on slides 13-16 (GTM, traction, pricing).
3. Promise: "I'll send everyone a 90-second screen-recording link
   tonight." (Then actually do that.)

The talk still works because the deck stands alone. The demo is the
proof, not the product. Audiences want to invest in conviction.
Show conviction by **not panicking**.

---

## 5. After the presentation

### Immediately (in the room, before leaving)

- [ ] Screenshot the receipt ledger (proof receipt for the room)
- [ ] Hand out one-pager PDF (`presentation/TARS_v10.0_ONEPAGER.pdf`
      if generated; otherwise the deck)
- [ ] Capture questions on phone notes — these go straight into v10.1
      roadmap as RICE items
- [ ] Get business cards / LinkedIns from the 3 most-engaged faces

### Within 1 hour

- [ ] Post the demo recording to twitter / X with the closing line
- [ ] Send a thank-you email to the host with the install link
- [ ] DM the 3 engaged faces with a 90-second async loom

### Within 24 hours

- [ ] Update the cheat sheet with any question that stumped you
- [ ] Add slides to address the 2-3 questions that came up MOST
- [ ] Submit v10.0 GA tag (only if demo conviction was high — postpone
      otherwise)

### Within 1 week

- [ ] Convert the most-engaged contact into a paid pilot
- [ ] Re-do the demo for the next room. Each room teaches you one thing.

---

## 6. Emergency contacts (during the demo)

If a live disaster — laptop dies, projector fails, network drops:

- Brother (meeet.world ops): @meeet-handle on Telegram
- GitHub repo: github.com/alienram/jarvis (open if asked)
- Backup laptop: TARS installed but not pre-flighted. Pre-flight on it
  the night before just in case.

---

## 7. Pre-demo grooming checklist (the small things)

- [ ] Battery 100% · charger packed
- [ ] HDMI + USB-C adapters packed
- [ ] Clicker tested · spare batteries
- [ ] Water bottle within reach (NOT on the table — you'll spill it)
- [ ] Phone on silent + airplane mode optional
- [ ] Apple Watch on theatre mode (no notifications during talk)
- [ ] Shirt has no stain · check teeth · check fly · breath mint
- [ ] Practice the closing line in the bathroom mirror ONCE before
      walking out

---

## 8. The one thing you MUST do first thing after waking up

**Double-click `scripts/DEMO-READY.command`.**

Nothing else. Not coffee. Not email. Not Twitter.

That one click runs the 8 phases. If everything is green, you have
20 free minutes for coffee. If anything is red, you have 20 minutes
to fix it — far better than discovering at T-5 that the backend is
crashed.

Coffee can wait 90 seconds. The pre-flight cannot.

---

*Print this. Highlight the bits you forget. Tape it to your laptop.
You wrote the product. You earned this. Now go.*
