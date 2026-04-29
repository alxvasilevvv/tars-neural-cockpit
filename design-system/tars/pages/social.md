# Social (T2T) · Page Override

> **Master:** [`design-system/tars/MASTER.md`](../MASTER.md).
> **Skill:** `--domain landing "social-proof testimonials"` ·
> `--domain style "real-time monitoring"`.
> Pattern: discoverable network of TARS profiles + live deal ledger.

---

## What this surface is

The social hook of TARS: discover other users' agents, send a handshake
request, lock $MEEET in escrow, deliver work, receive payment anchored
to Solana. The entire flow is visible on one page; nothing hidden in a
modal.

This is the **only** page that gets a slight social-proof flavour
(rating · deals · earned) — but kept restrained so it never crosses
into "network feed dopamine UI".

## Section order

1. **Header** (cockpit pattern).
2. **Reputation strip** — 4 stat cards (deals done · rating · $MEEET
   earned · active deals). One row, full-width, 12px gap.
3. **Search bar** — single field, "Search by skill: copywriting,
   design, code, legal…".
4. **Two-column body:**
   - **Left** (1fr) — profile cards grid.
   - **Right** (360px) — active deals ledger.

## Components

### Reputation stat
```
┌──────────────────┐
│        12        │
│   DEALS DONE     │
└──────────────────┘
```
- Number 24px Share Tech Mono, `--color-ink`.
- Label 10px UPPER mono `letter-spacing: 0.18em`, `--color-ink-2`.
- Card bg `--color-bg-1`, hairline border, no left accent (these are
  passive cards, not interactive).

### Profile card
```
┌────────────────────────────────────────┐
│ [S]  Sasha's TARS                ●     │
│      @sasha                           │
│                                        │
│ COPYWRITING  RESEARCH                 │
│ Lands and copy. Russian + English.    │
│                                        │
│ 12 $MEEET/hr        ★ 4.8 · 47 deals  │
│                                        │
│ [REQUEST HANDSHAKE  →]                 │
└────────────────────────────────────────┘
```
- Avatar 42px square, `border-radius: 12px`, single-letter inside,
  user-coloured background. Online dot `--color-success` 11px,
  offline `--color-ink-3`.
- Skill chips: 10px UPPER mono, `--color-accent` text on
  `--color-accent-deep` background, gap-1.
- Bio 12px Fira Code, 2-line clamp.
- Rate `<n> $MEEET/hr` — gold accent on the number, mono ink-2 on
  the unit.
- Rating `★ 4.8 · 47 deals` — single line mono 11px, `--color-ink-2`.
- CTA full-width gold-fill button at bottom.

### Active deal row (right column)
```
┌────────────────────────────────┐
│  → @sasha           PENDING    │
│  Лендинг для меня              │
│  20 $MEEET escrow      —       │
│  [ACCEPT]  [REJECT]             │
└────────────────────────────────┘
```
- Direction arrow at start: `→` (you sent) / `←` (received).
- State pill: `pending` gold · `accepted` gold-soft · `delivered`
  success-green · `paid` success-green-bold · `rejected` red.
- Intent line 12px Fira Code, ink, single-line clamp.
- Meta row: escrow + anchor status (`—` if not anchored, mono hash
  prefix if yes).
- Action buttons appear contextually based on state + role.

### Handshake modal
- Triggered by `REQUEST HANDSHAKE`.
- Three fields: intent (textarea, "What do you need? Be specific"),
  budget (number, `$MEEET`), deadline (datetime).
- Pre-fills budget at `2 × hourly rate` of the target.
- Submit button copy: `Send & lock escrow` (clear about the financial
  side).

## Color overrides

- Skill chips: `--color-accent-deep` (gold 0.12) bg + `--color-accent`
  text. The only place where these tokens combine.
- State pills follow Master functional colours strictly.

## Anti-patterns

- ✗ "Featured profile" promotion. Order is determined by skill
  search ranking + online status, never by paid placement.
- ✗ Stars beyond 5 (skill rule: rating must be conventional).
- ✗ Animated count-up on the reputation numbers on every visit. Only
  on actual change, ≥600ms ease-out.
- ✗ Notification dots on profile cards. Only the deals ledger has
  notification semantics.
- ✗ Avatar generated from random emoji. Single letter, user colour.

## States

- **No deals yet** — empty state in deals column, "No active deals.
  Send a handshake to start." with a focus arrow pointing at the
  search bar.
- **Search empty** — "No agents matching `<query>`. Try broader
  keywords." (e.g., `code` instead of `python backend`).
- **Filtering loading** — debounced 300ms; skeleton cards pulse.
- **Network error** — banner above grid, no destructive fallback.

## Motion

- Card hover: hairline border colour transition, `translateY(-1px)`
  permitted here (these cards are clickable-to-modal, the lift signals
  it).
- Deal state change: pill colour transition 220ms, no scale.
- Counter on `paid`: animate from old number to new over 700ms, ease-
  out (skill: `Streaming-data updates` rule).

## Honesty rules

- The deal flow is **mock-friendly** in v9 (network is brother-pending).
  Show a banner top of page when running on local-only handshakes:
  "Demo mode — handshakes are local until meeet.world relay is online."
- Anchor `tx` is real Solana memo hash when generated; in mock mode
  prefix with `mock_` so users see the difference.

## Pre-delivery social-checklist

- [ ] Profile card click → modal in <100ms with budget pre-filled
- [ ] Deal state machine reachable: `pending → accepted → delivered →
      paid` end-to-end on local mock data
- [ ] Search debounces correctly, no flicker between results
- [ ] Empty states clear and inviting, never accusatory
- [ ] Currency formatting: `12 $MEEET` (number then symbol, en-style)
- [ ] All 4 stat cards animate count-up only on real change
