# Briefing · Component Override

> **Master:** [`design-system/tars/MASTER.md`](../MASTER.md).
> **Skill:** `--domain style "real-time monitoring"` ·
> `--domain ux "loading skeleton aria-live"`.
>
> Briefing isn't a standalone page in v9 — it's the hero block on
> Cockpit. This file documents the component spec so that other
> surfaces (e.g. Operator's morning summary, future digest emails) can
> reuse it consistently.

---

## What this component is

A 60-second personal sit-rep on first cockpit-open of the day:
greeting + summary + 3-4 actionable items + 2-3 quick-action chips.
Item content comes from `/api/v76/briefing/today` which itself sources
calendar / recent files / iMessage / GitHub / connectors. In mock-mode
(default), synthetic data.

## Anatomy

```
┌────────────────────────────────────────────────────────────┐
│  Доброе утро, Alien.                                       │ ← greeting
│  Tuesday, 28 April · 2 встречи · 4 непрочитанных · 3 файлов│ ← summary
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ ▣ 2 встречи     │  │ ◇ 3 PR на review│                  │ ← items grid
│  │ 10:00 Sync · …  │  │ Подключи review…│                  │
│  └─────────────────┘  └─────────────────┘                  │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ ◆ Саша × 4 msg  │  │ ═ proposal.docx │                  │
│  └─────────────────┘  └─────────────────┘                  │
│                                                             │
│  ▢ План на день   ◊ Inbox zero   ↗ Сводка недели           │ ← quick-actions
│                                                             │
│  ⓘ live · last refreshed 14:08                             │ ← source chip
└────────────────────────────────────────────────────────────┘
```

## Tokens

| Element | Spec |
|---------|------|
| Greeting | `Share Tech Mono` 32–40px, ink, `letter-spacing: 0.01em` |
| Summary | `Fira Code` 13px, `--color-ink-2`, `letter-spacing: 0.04em` |
| Items grid | `display: grid; grid-template-columns: 1fr 1fr; gap: 10px;` |
| Item card | bg `--color-bg-1`, hover `--color-bg-2`, border `--color-line`, `border-radius: 14px`, padding `14px 16px` |
| Item glyph | gold, `Fira Code` 700 14px, no decoration |
| Item label | `Fira Code` 500 14px ink |
| Item detail | `Fira Code` 400 12px `--color-ink-2`, indent 22px (under glyph), 2-line clamp |
| Quick chip | bg `--color-accent-deep`, border `--color-line-hot`, text `--color-ink`, `Fira Code` 12px, padding `8px 14px`, `border-radius: 999px` |
| Source chip | `--color-faint`, `Fira Code` 10px UPPER, letter-spacing 0.18em |

## Item action protocol

Each item is a `<button type="button">`. On click → `prompt.value =
item.action; send();`. Send fires the Watch-Me-Work timeline.

If `item.action` is null (informational items only), the card is a
plain `<div>` with no hover/cursor change.

## Source chip variants

`source` from `/api/v76/briefing/today`:
- `live` — gold dot + "live" — all data is fresh from connected
  sources.
- `partial` — amber dot + "partial · connect more sources" — some
  signals missing, fallback to mock for missing ones.
- `mock` — ink-3 dot + "demo mode" — full synthetic.

Tooltip on hover gives the same status with `last refreshed`
timestamp.

## States

### Loading (skeleton)
```
┌────────────────────────────────────────────────────────┐
│  ████████████████                                     │
│  ████ ··· ████ ··· ████ ···                            │
│                                                         │
│  [██████]  [██████]                                     │
│  [██████]  [██████]                                     │
└────────────────────────────────────────────────────────┘
```
- Static rectangles, `--color-bg-2` background.
- Pulse animation: opacity 0.6 → 1.0 over 1.6s ease-in-out (matches
  Master skill rule: status pulse 1.6s).
- Visible only if response takes ≥300ms.

### Empty (no signals)
```
  Доброе утро, Alien.
  All quiet — connect sources to see what's pending.

  [Connect calendar]   [Connect Slack]
```
- Greeting still shows.
- Single inviting line in `--color-ink-2`.
- Two suggestion chips → `connectors.html?focus=calendar` etc.

### Error
- Greeting still shows.
- Inline `⚠ briefing unavailable` chip in `--color-alert-soft`.
- Quick-actions still clickable (they don't depend on briefing).

### After chat starts (collapsed)
```
  ⌃ Briefing · 4 items   [expand]
```
- Briefing collapses to a single 32px-tall strip when chat is active.
- `expand` button reopens the full card; closing chat returns it.

## Accessibility

- `<section aria-labelledby="brief-greet">`.
- Live updates wrap in `aria-live="polite"`.
- Each item button has `aria-label="Run: {item.label}"` for
  screen-readers.
- Source chip is `<span role="status">`.
- Empty/error states use `role="status"` (not "alert"; we don't
  interrupt).

## Motion

- Card mount: fade + 12px translate-up over 500ms ease-out.
- Item hover: border colour 200ms, no transform.
- Skeleton → real: cross-fade 220ms.

## Anti-patterns

- ✗ "Have a great day!" — fluff in greeting. Master says terse.
- ✗ Emojis in items. Use the established mono glyphs (`▣ ◇ ◆ ═ ▢ ◊
  ↗`).
- ✗ More than 4 items. Skill rule: hierarchy + cognitive load.
- ✗ Quick-actions that duplicate the items above. They're *general*
  (Plan day / Inbox zero / Week summary), items are *specific*.
- ✗ Auto-refresh while user is reading. Refresh only on:
  page focus after >5min, manual `↻`, or explicit user action.

## Pre-delivery briefing-checklist

- [ ] Greeting localises to user's preferred language (RU/EN at
      least)
- [ ] Time-of-day greeting accurate to user's clock (5–12 morning,
      12–18 day, 18–23 evening, 23–5 night)
- [ ] User name appears (from MEEET_USER_EMAIL or TARS_USER_NAME) —
      if missing, just "Доброе утро." without name
- [ ] All four states (loading/empty/error/loaded) reachable in dev
      mode for QA
- [ ] Source chip click → opens connectors page with category focus
- [ ] Collapsing on chat start animates in <250ms
