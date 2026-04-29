# Cockpit · Page Override

> **Master:** [`design-system/tars/MASTER.md`](../MASTER.md). This file
> overrides only what differs. For tokens, typography, motion rules — see Master.
>
> **Skill source:** `--design-system "AI neural cockpit local-first dark
> futurism sci-fi HUD operator console"` + supplemental
> `--domain style "real-time monitoring HUD operator dark"`.

---

## What this surface is

The **operator's runtime**. Unlike the marketing showcase which is
hero-driven, the cockpit is a workspace: the user opens it daily, expects
to see what changed, what's pending, what they should attend to in 2
seconds. Pattern is **Real-Time Monitoring → Operator Console**, not a
landing page.

This file replaces the auto-generated "Hero + Features + CTA" landing
pattern from the skill page-stub — that pattern doesn't fit a workspace.

## Section order (replaces Master pattern §2)

1. **HUD shell** — fixed header (left: logo + mode tabs · centre: live
   phase bar · right: health dot, awareness bell, login pill, drawer
   triggers).
2. **Daily Briefing** — single full-width card directly under hero space.
   No marketing hero. Briefing IS the hero on first open of the day.
3. **Conversation strand** — once the user types or speaks, briefing
   collapses to a chip and chat takes over. Watch-Me-Work timeline pinned
   to top of stage.
4. **Drawers** — left ⌘L (agents), right ⌘R (skills + workspace),
   palette ⌘K (commands).
5. **Footer-less** — no marketing footer. Input bar lives at the bottom
   of the stage instead.

## Layout overrides

- **No `max-w-6xl`** — the cockpit fills the viewport edge-to-edge. Use
  a `1280px` content rail centred for chat + briefing, but headers/dock
  span the full width.
- **Z-index scale** (cockpit-specific, narrows the Master 10/20/30/50):
  - `5` — stage content (chat, briefing)
  - `8` — Watch-Me-Work bar (over stage, under header)
  - `30` — header
  - `40` — drawers + scrim
  - `50` — modals (approval gate, login)
- **Header height** — fixed 56px. Content offset top accordingly. No
  floating navbar pattern here (we always need that 56px reserved).

## Color overrides

Strict adherence to Master gold accent:

| Surface | Token | Note |
|---------|-------|------|
| Header bg | `var(--color-bg-1)` 90% + `backdrop-filter: blur(20px)` | Glass on top of OLED |
| Stage bg | `var(--color-bg-0)` (`#000`) | True OLED |
| Briefing card bg | `var(--color-bg-1)` (`#0B0B10`) | Raised 1 step |
| Brief item hover | `var(--color-bg-2)` (`#14141B`) | Raised 2 steps |
| Hairlines | `var(--color-line)` (0.06 alpha) — never solid | |
| Active hairline | `var(--color-line-hot)` (gold 0.32) — focus / selected | |
| Health dot OK | `var(--color-success)` (`#34D399`) | Functional, not accent |
| Health dot degraded | `var(--color-accent)` (gold) | Degraded ≠ alarm |
| Health dot down | `var(--color-alert)` (`#EF4444`) — pulse only when down | |
| Login pill (logged out) | gold accent fill | Single primary CTA in chrome |
| Login pill (logged in) | `var(--color-bg-2)` outline | Secondary state |
| Watch-Me-Work pills | mono labels, gold rim active, fade trail | |

Never AI-purple/pink gradients. Never two accent colours simultaneously
(if alert is up, accent dims).

## Typography overrides

- **Briefing greeting** — `Share Tech Mono` 32–40px, `letter-spacing:
  0.01em`. Smaller than the marketing hero (master says `clamp(3.4rem,
  8vw, 8rem)`) because the cockpit hero is data, not slogan.
- **Briefing summary line** — `Fira Code` 13px, `--color-ink-2`,
  `letter-spacing: 0.04em`.
- **Brief item label** — `Fira Code` 500 14px, `--color-ink`.
- **Brief item detail** — `Fira Code` 400 12px, `--color-ink-2`,
  line-height 1.5.
- **Phase bar labels** — `Fira Code` 500 11px UPPER, `letter-spacing:
  0.18em`.

## Components

### HUD header
```
┌────────────────────────────────────────────────────────────┐
│ [●] T A R S · meeet  ▣Cockpit ▤Project ◫Cowork  [○ ◌ Login]│
└────────────────────────────────────────────────────────────┘
```
- Logo dot pulses (1.6s ease-in-out) only when supervisor is busy.
  Pulse uses `--color-accent-soft` glow (skill: alert pulse/glow rule).
- Mode tabs: pill group, gold fill on active, `--color-ink-2` on
  inactive.
- Health dot is a real status from `GET /api/v76/health/dot` (not
  decorative).
- Login pill is gold-filled when logged out (the only solid gold in
  chrome).

### Daily Briefing card
```
┌────────────────────────────────────────────────────────────┐
│  Доброе утро, Alien.                              ⟶ 2 sec  │
│  Tuesday, 28 April · 2 встречи · 4 непрочитанных · 3 файлов│
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ ▣ 2 встречи     │  │ ◇ 3 PR на review│                  │
│  │ 10:00 Sync · …  │  │ Подключи review…│                  │
│  └─────────────────┘  └─────────────────┘                  │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ ◆ Саша × 4 msg  │  │ ═ proposal.docx │                  │
│  │ упомянул meeet  │  │ редактировался… │                  │
│  └─────────────────┘  └─────────────────┘                  │
│                                                             │
│  ▢ План на день   ◊ Inbox zero   ↗ Сводка недели           │
│                                                             │
│  ⓘ live · last refreshed 14:08                             │
└────────────────────────────────────────────────────────────┘
```
- 2×2 grid on desktop, 1-column on `<700px`.
- Each brief-item is a button (semantic) — clicking sends its `action`
  prompt into the chat. `cursor-pointer`, focus-visible ring with
  `--color-line-hot`.
- Hover: only `border-color` transition (200ms ease-out). No
  translateY, no scale. Skill rule: stable hover states.
- Empty state (no signals): a dim mono line "All quiet — nothing pulled
  from your sources yet" + two suggestion chips.
- Loading state: skeleton shows greeting + 4 grey item placeholders
  pulsing at 1.6s. Always visible during `> 300ms` waits (skill rule).
- Error state: small inline `⚠ briefing temporarily unavailable` chip,
  greeting still shows, quick-actions still clickable.

### Watch-Me-Work timeline (centre header)
```
              ◇ ROUTING · ◈ TOOL · ◆ DRAFTING · ◉ DONE
                                  └─ web_search ─┘
```
- Pill row with phase glyphs. Active phase brightens to `--color-ink`.
  Done phases tint `--color-success` 70% (very subtle).
- Tool pills (max 3 visible) appear inline under their phase. New pill
  fades in over 250ms, oldest fades out.
- Phase events come over WebSocket `/api/v76/events/ws` — backend now
  emits real `route → tool → draft → done`.
- Bar shows on `tars:user-input` event, hides 1.2s after `done`.

### Health dot (top-left of head-icons)
- 10px circle with status colour. `box-shadow: 0 0 8px <color> at 0.7
  alpha`.
- Click: opens a 480px modal with per-component breakdown
  (`memory_store / calendar_reader / code_index / connectors / briefing
  / disk / meeet_login`). Each row: name, status pill, terse `detail`,
  duration.
- Polls `/api/v76/health/dot` every 30s; immediate refresh on modal
  open.

### Awareness bell (◌)
- Adjacent to health dot. Badge shows `unseen` count from
  `/api/v76/awareness/stream`.
- Click: opens right-side drawer with the always-on stream.

## States required (skill UX rule)

For every async surface in the cockpit:
- **Loading** (≥300ms) — skeleton pulse, no spinners.
- **Empty** — informative text, no zero-state hostility, optional
  suggestion chips.
- **Error** — inline pill, never blank screen, never raw stack trace.
- **Success** — implicit (the data arrives). For destructive actions
  (operator approve), a brief toast confirming the receipt id.

## Motion (overrides Master §7)

The cockpit allows **at most three** simultaneous motions:
1. Header logo pulse (only when supervisor busy)
2. Watch-Me-Work phase glow (only during a request)
3. Health dot pulse (only when status = down)

Everything else is static. Skill UX result: "Excessive Motion →
Severity High".

## Anti-patterns (cockpit-specific)

- ✗ Marketing copy in the hero. The briefing IS the hero.
- ✗ Two accents at once. If alert is shown, gold dims to inactive state.
- ✗ Static cards that look interactive. Cards either click
  (cursor-pointer) or have no hover at all. No middle ground.
- ✗ Modal-stacking. Health modal, login modal, approval gate — never
  two open at once. Open one closes others.
- ✗ Auto-scroll the chat without user intent. Always pinned-to-bottom
  on user message; never on TARS reply alone.
- ✗ "AI sparkles" gradient on TARS messages. Plain mono text.

## Pre-delivery cockpit-checklist

- [ ] First-paint shows the briefing skeleton in <100ms (no white flash)
- [ ] Health dot reaches first state in <500ms
- [ ] WebSocket `/events/ws` reconnects with exp backoff if cockpit was
      idle for >5min
- [ ] All four states (loading/empty/error/success) hand-tested for
      briefing + connectors + memory + operator
- [ ] Keyboard: ⌘K palette, ⌘L left drawer, ⌘R right drawer, `Esc`
      closes any open modal/drawer
- [ ] `prefers-reduced-motion: reduce` kills all the three permitted
      motions
- [ ] Cockpit usable without login (mock mode); login pill stays gold
      until tapped
