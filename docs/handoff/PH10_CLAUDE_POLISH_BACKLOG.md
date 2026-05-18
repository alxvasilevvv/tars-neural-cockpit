# PH10 — Claude design-polish backlog (continuous lane)

> **W310-ac.** Inventories the 13-item Claude-owned visual-polish backlog
> from `docs/AGENT_HANDOFF.md` "Pending — Owned by Claude" section.
> Prioritizes by **GA visibility** vs **engineering dependency** so
> Claude can sequence solo work in parallel with the Cursor engineering
> lane. Continuous; not a single shipped feature.
>
> **Owner:** Claude Code (design lane), with `gstack-claude review`
> gate for each PR.
> **Cadence:** 1–2 items per week, continuous.
> **Effort total:** ~13 items × 0.5–2 days each = ~3–5 weeks Claude
> wall-clock if done back-to-back; in practice spread across v10.0
> → v11 timeline as design lane refresh between engineering waves.
> **GA gate:** **none of the 13 items is a v10.0.0 hard blocker.**
> `V10_GA_CHECKLIST.md` is engineering-driven; Claude polish lands
> on its own cadence and is reconciled in HANDOFF / SHIPPED rows
> per item.

---

## 1. Motivation

After v10 GA the cockpit + landing are **functionally complete**
but visually **plain-HUD**. PR #195's recovery + pairing panels are
explicitly tagged "*Plain HUD styling — Claude polishes visuals later*"
in HANDOFF Wave-PH3-K. Same pattern across L2 attachment chips, L5
pairing flow, L8 search palette, L9 download CTAs — engineering
shipped the surface; Claude lifts the surface.

**This brief gives Claude a single dashboard view** instead of
13 scattered `Pending — Owned by Claude` rows in a 3500-line
HANDOFF file. Each item gets:

- **GA visibility tier** (1 = first 30s of user's life, 2 = first 5 min, 3 = power-user)
- **Engineering dependency status** (ready-to-polish vs blocked-on-X)
- **Estimated Claude effort** (XS / S / M / L)
- **Done criteria** (when does Claude close the row)

---

## 2. Goals / non-goals

### Goals

- Inventory all 13 items with current status + dependency state.
- Prioritize sequence so **highest-GA-visibility ready items land
  first** — Hero copy + brand dressing + landing download CTAs before
  pairing-flow visual or chat hover details.
- Define **per-item done criteria** so Claude knows when to stop
  polishing and ship.
- Keep this brief **append-only**: as items complete, mark `✅ shipped
  W<wave>` inline; don't delete. Tracking history matters.
- Provide **single-shot reconciliation target**: after all 13 ship,
  add `Phase 10 design polish closed (13/13)` row to HANDOFF + close
  this brief with `STATUS: SHIPPED ✅`.

### Non-goals

- ❌ Not a unified design system overhaul (that's `ui-ux-pro-max-skill`
  re-run, separate). Each item is targeted polish on an already-shipped
  surface.
- ❌ Not a rewrite of any landed component (`<ChatPane />`, `<PairingPanel />`,
  etc.). Touch chrome only.
- ❌ Not a blocker for any engineering phase (PH2-PH9). Claude lane is
  parallel; merge order doesn't matter for engineering.
- ❌ Not 13 separate PRs required — Claude can batch related items
  (e.g. items 4 + 5 + 11 = "Landing brand pass" single PR).
- ❌ Not a contract for visual quality; that's Claude's own taste +
  the `ui-ux-pro-max-skill` lane.

---

## 3. The 13-item inventory (with prioritization)

> Source-of-truth: `docs/AGENT_HANDOFF.md` lines 3326–3394 (the
> "Owned by Claude Code (design)" block). Items numbered 1–13 here
> match the numbers in HANDOFF.

| # | Item | GA-vis tier | Dep status | Effort | Notes |
|---|---|---|---|---|---|
| 4 | **Landing copy pass** (Hero subhead, Domains bullets, Steps cues) | **1** | ready | S | Match `MASTER.md` operator-grade voice |
| 5 | **Brand dressing** (favicon + OG image from v3 palette) | **1** | ready | S | Gold accent + cyan HUD on OLED |
| 11 | **Landing download CTAs** (`<DownloadStrip />` polish) | **1** | ready | M | OS-glyph icons, version pulse, "verified · sha256 ✓" once manifest gets checksum |
| 1 | **GLB brain asset** (CC0 brain mesh to `brain.glb`) | **2** | ready | S | Procedural stays as offline fallback |
| 2 | **v3 micro-interactions polish** (re-run `ui-ux-pro-max` for `--page cockpit` / `--page hero`) | **2** | ready | M | Especially Cockpit empty / loading / error states |
| 3 | **Page-transition richness** (shared overlay sweep on route change) | **2** | ready | S | Blur-slide already in `App.tsx`; layer on |
| 6 | **Sound design polish** (richer ambient bed 4-5 tones + press cues) | **2** | ready | M | Respect `prefers-reduced-motion`; default-muted |
| 7 | **`<AwarenessTicker />` rev** (3-pane card → single ticker bar / chart) | **3** | ready | M | UX exploration before code |
| 8 | **`<ChatPane />` chrome polish** (motion / copy / hover / focus / mobile) | **2** | ready | M | Touch chrome only — functional surface is locked |
| 9 | **Attachment + sources visual** (chip motion `queued→uploading→ingesting→ready`, mime icons, hover chunk preview) | **3** | ready | M | All wiring shipped L2 |
| 10 | **⌘K palette + `<ThreadTimeline />` visual** (gold-on-bg pulses, recent-threads empty state, timeline-spine motif) | **3** | ready | L | Cytoscape trace-graph view deferred to future pass |
| 12 | **meeet.world embed** (marketing site `meeet.world/tars` consumes `/api/product/downloads`, matching CTAs + OG cards + deep-link into cockpit) | **2** | **blocked on brother** | M | Coordinate any contract bump via Cursor PR — never silent. Contract pinned `1.0.0`. |
| 13 | **Pairing-flow visual** (desktop fp pulse + accept-token confirm sheet + iOS / Android scan UX sketch) | **3** | ready (engineering shipped PR #195 + #196) | M | Now post-engineering polish, not pre-engineering sketch as originally framed in HANDOFF |

### Tier-1 items (first 30 s of user life) — **ship first, GA-adjacent**

- **#4 Landing copy** — XS, 1 day Claude wall-clock
- **#5 Brand dressing** — XS, 0.5–1 day
- **#11 Download CTAs** — M, 2 days

→ **Recommended first wave (single PR or 2 PRs): items 4 + 5 + 11 =
"v10 landing brand pass."** Lands ideally **before** or
**immediately after** v10.0.0 tag so first-time visitors see polished
landing.

### Tier-2 items (cockpit polish for active users)

- **#1 GLB asset** — S, 0.5 day
- **#2 Micro-interactions** — M, 2–3 days
- **#3 Page transitions** — S, 1 day
- **#6 Sound design** — M, 2 days
- **#8 ChatPane chrome** — M, 2–3 days
- **#12 meeet.world embed** — **blocked on brother**, ~M when unblocked

→ **Recommended second wave (v10.1):** items 1 + 2 + 3 + 6 + 8 as
"cockpit polish v10.1." Each can ship as standalone PR (Claude judges
batching).

→ **Item 12 (brother coord):** parked until brother PH11 sync #198
lands first; then loop in TARS-side coordination.

### Tier-3 items (power-user surfaces)

- **#7 AwarenessTicker rev** — M, 2 days (needs UX exploration first)
- **#9 Attachment/sources polish** — M, 2 days
- **#10 ⌘K palette + ThreadTimeline** — L, 4–5 days (biggest single item)
- **#13 Pairing visual** — M, 2 days (now POST-engineering polish since #195+#196 shipped the functional surface)

→ **Recommended third wave (v10.2):** items 7 + 9 + 10 + 13. Item
13 timing flips with engineering — originally HANDOFF said "sketch
**before** code lands so Cursor wires components against a
pre-approved layout"; in practice engineering shipped first (PR
#195 functional + PR #196 UX implementation brief), so this is now
**post-engineering polish**, not pre-engineering sketch.

---

## 4. Per-item done criteria

For each item, "done" = all four:

1. **Component / asset shipped** to the codebase (PR merged to main).
2. **HANDOFF row** `Owned by Claude` → `✅ shipped W<wave>` inline.
3. **No regression** in pytest / vitest / `tsc --noEmit` / `eslint`.
4. **`gstack-claude review` pass** on the PR (Claude's own gate; no
   `Cursor agent` review needed since Claude lane is design-only).

After all 13 ship, single closing PR adds `Phase 10 polish closed
(13/13 W<wave>)` row to HANDOFF and updates this brief STATUS to
SHIPPED ✅.

---

## 5. Cadence recommendation

- **1–2 items per week** spread across v10.0.0 → v11 timeline.
- **Single batched wave around v10.0.0 tag** for items 4 + 5 + 11
  ("v10 landing brand pass") so first-time visitors land on polished
  surface.
- **No engineering blocker.** Claude lane runs purely in parallel;
  engineering merge order (PR #187 → #211) doesn't affect Claude
  sequence.
- **Don't perfectionism-creep.** Each item has a finite scope per
  HANDOFF source-of-truth; ship when done, move to next. Re-polish
  passes for v11+ are a separate brief (PH10 v2 or "Phase 12 design
  refresh").

---

## 6. Effort total (Claude wall-clock)

| Tier | Items | Effort |
|---|---|---|
| 1 | 4, 5, 11 (landing brand pass) | ~3.5 days |
| 2 | 1, 2, 3, 6, 8, (12 blocked) | ~10–12 days |
| 3 | 7, 9, 10, 13 | ~10 days |
| **Total** | **13 items** | **~23–25 days** Claude wall-clock |

At 1–2 items per week cadence: **~3–5 months wall-clock** across
the v10.0 → v11 arc. Naturally docks into v11 engineering wrap
without rushing.

---

## 7. What this brief does **not** do

- ❌ Doesn't prescribe specific colors / type / motion params — that's
  `ui-ux-pro-max-skill` output + Claude's taste.
- ❌ Doesn't gate any engineering merge.
- ❌ Doesn't track ongoing polish beyond the 13 items (e.g. future
  v11 visual refresh, meeet.world brand-pack lift, mobile-app first-
  party visual). Those are separate briefs.
- ❌ Doesn't enforce a specific PR-grouping. Claude judges batching;
  recommendation in §3 is just default.

---

## 8. Open questions

1. **Item 12 (meeet.world embed)** — wait for brother PR #198 sync to
   complete before loop-in, or start coord now via existing
   `docs/contracts/MEEET_DOWNLOADS.md`? *Recommend: wait for #198.*
2. **Item 13 (pairing visual)** — now post-engineering polish since
   PR #195 + #196 shipped functional. Re-frame in HANDOFF as
   "post-engineering visual lift" rather than "pre-code sketch"? *Yes,
   update HANDOFF row 13 wording when item ships.*
3. **`gstack-claude review`** — Claude's self-review gate. Confirm
   this is sufficient (no Cursor functional review) for design-lane
   PRs? *Recommend: yes for items touching only `experiments/*` chrome;
   Cursor review needed only if item 12 brother coord touches contract
   schema.*
4. **v10 landing brand pass timing** — ship items 4+5+11 in a single
   PR before `bash scripts/RELEASE-v10.0.command` runs, or as fast-
   follow PR after v10.0.0 tag? *Operator picks; either works.
   Recommend: fast-follow within 48h of tag so v10 GA blog post + OG
   share images use the polished brand.*

---

## 9. Cross-references

- `docs/AGENT_HANDOFF.md` lines 3326–3394 — source-of-truth 13-item
  list (this brief inventories + sequences it).
- `docs/PRODUCT_MASTER_PLAN.md` §3.10 — Phase 10 "Claude design polish
  — continuous, lane-isolated" callout.
- `docs/W310_WAVE_SUMMARY.md` — closes this brief out as W310-ac in
  the next summary refresh.
- `docs/contracts/MEEET_DOWNLOADS.md` — item 12 cross-stack contract.
- PR #195 (cockpit recovery + pairing functional) + PR #196 (cockpit
  pairing UX brief) — items 13's engineering surface, now ready for
  Claude visual lift.

---

## 10. Status timeline

| Date | Item(s) | Status | Notes |
|---|---|---|---|
| 2026-05-18 | this brief | OPEN | Inventory + sequence captured. Claude lane greenlit. |
| _next_ | items 4 + 5 + 11 | _pending_ | "v10 landing brand pass" — recommended first batch |
| _next_ | items 1, 2, 3, 6, 8 | _pending_ | v10.1 cockpit polish wave |
| _next_ | items 7, 9, 10, 13 | _pending_ | v10.2 power-user surfaces |
| _next_ | item 12 | _blocked_ | unblocks after PR #198 brother sync completes |
| _on close_ | all 13 | SHIPPED ✅ | reconcile HANDOFF + close this brief |

---

**STATUS:** OPEN — backlog scoped, Claude lane greenlit, sequence
recommended. Engineering lane (PH2-PH9) runs in parallel; no merge-
order dependency.
