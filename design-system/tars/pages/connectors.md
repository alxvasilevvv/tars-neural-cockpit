# Connectors · Page Override

> **Master:** [`design-system/tars/MASTER.md`](../MASTER.md).
> **Skill:** `--domain ux "trust visible state honest mock"`.
> The honesty surface — TARS lies nowhere, but here it lies *least* of
> all. Status badges (`real / local / bridge / stub`) are the design's
> raison d'être.

---

## What this surface is

A grid of integrations TARS can connect to (12 items in v9). Each card
shows what kind of implementation it has, what auth it needs, and one
clear action button. No "coming soon" disguised as "connect". No fake
green checkmarks.

## Section order

1. **Header** (cockpit pattern).
2. **Hero** — single H1 "Connectors" + 1-line description.
3. **Grouped grid** — by category (Messaging / Email / Calendar /
   Files / Code / Tasks / Notes / Database / Payments). Each group:
   header strip + cards row.

## Components

### Connector card
```
┌────────────────────────────────────────────┐
│ [S]  Slack                  BRIDGE         │
│      OAuth via meeet.world · @alex         │
│                                            │
│      [CONNECT]                              │
└────────────────────────────────────────────┘
```
- Icon 42px square, `border-radius: 10px`, single letter, brand
  colour bg.
- Name 14px Fira Code 600.
- **Implementation tag** to the right of the name: 9px UPPER mono
  letter-spacing 0.18em.
  - `REAL` — `--color-success` text on success-deep bg.
  - `LOCAL` — `--color-accent` text on accent-deep bg.
  - `BRIDGE` — `--color-accent-soft` text on `--color-bg-2`.
  - `STUB` — `--color-ink-3` text on `--color-bg-2`.
- Subline: auth method · current user (if connected). 11px mono,
  `--color-ink-2`.
- Action button (right):
  - `CONNECT` — gold-fill (only solid gold on this page) when not
    connected and impl ≠ stub.
  - `✓ CONNECTED` — green outline when connected.
  - `COMING SOON` — disabled, ink-3, on stub cards.

### Group header strip
```
─── MESSAGING ──────────────────────────────────────────
```
- 11px UPPER mono `letter-spacing: 0.32em`, `--color-ink-2`.
- Hairline below: 1px `--color-line`.
- Margin-top 32px between groups.

### Bridge connect flow modal
- When a bridge card is clicked, modal opens with:
  - User code (e.g. `ABCD-1234`) shown in a large monospaced display
    (24px Share Tech Mono, gold).
  - Verification URL link (button-style).
  - Live polling indicator: 3-dot pulse + "Waiting for confirmation
    in your browser…".
  - Cancel button.
- On approval: modal flashes success-green border 220ms, then closes,
  card updates to connected.

### GitHub PAT prompt
- Special case for `real` tier — opens a smaller inline modal asking
  for the PAT.
- Includes the help text from backend response verbatim:
  "Go to https://github.com/settings/tokens, create a token with
  scopes: repo, read:user, then paste it here."
- Provides a `Generate token →` link to the prefilled token-creation
  page.
- After save, validates with `whoami()`; failure → field shows red
  rim and "GitHub rejected the token".

## Color overrides

The four implementation tiers are the only place where colour encodes
status (besides Master alert/success). Tier colours:

| Tier | Text | Bg |
|------|------|-----|
| real | `--color-success` (#34D399) | `rgba(52, 211, 153, 0.12)` |
| local | `--color-accent` (#CA8A04) | `--color-accent-deep` |
| bridge | `--color-accent-soft` | `--color-bg-2` |
| stub | `--color-ink-3` | `--color-bg-2` |

## Anti-patterns

- ✗ Hiding the tier. Some products show all integrations as
  "available" until you click. We never do.
- ✗ "Beta" alone — too vague. We use precise tier names so the user
  knows what to expect.
- ✗ Auto-connect on click for stubs. A stub card shows `COMING SOON`,
  disabled, no click action.
- ✗ Promotion banners ("Upgrade to Pro for more connectors!"). Pro
  gating lives elsewhere.

## States

- **Loading** — 12 skeleton cards (3 per row) at fixed grid.
- **Empty group** (e.g. user filters by category) — group header
  shown, body says "No connectors in this category yet".
- **Connect failure** — toast: actual backend error string, never
  generic.
- **Disconnect confirmation** — small inline confirm `Disconnect
  Slack?` next to the button, doesn't open a modal.

## Motion

- Tier badge: static. Never pulses.
- Card hover: hairline transition. No translate.
- Bridge modal pulse on user-code (1.6s ease-in-out): subtle
  `text-shadow` pulse on the gold display, signals "waiting".

## Pre-delivery connectors-checklist

- [ ] Tier badge always visible, no truncation
- [ ] Stub button is clearly disabled (cursor `not-allowed`, dim text)
- [ ] PAT-token modal: paste-only, no autocomplete browser hint
      ("autocomplete=off", "type=password")
- [ ] Bridge modal exit (Cancel) cleans the polling timer
- [ ] On reconnect after a disconnect, prior `connected_at` cleared
- [ ] Group order stable across renders (sort by Master spec)
