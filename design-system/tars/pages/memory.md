# Memory · Page Override

> **Master:** [`design-system/tars/MASTER.md`](../MASTER.md).
> **Skill:** `--domain style "AI-Native UI"` ·
> `--domain ux "context cards"` ·
> Pattern: **AI-Native UI** with context-card border-left accents
> (Master §1.4 calls this out explicitly).

---

## What this surface is

A ledger of facts TARS knows about the user, their AI Clone style
profile, and a forgotten-items audit log. The user comes here to
confirm "yes, that's what I told it" and to delete things they don't
want remembered. Trust is the dominant emotion to design for —
visibility, easy editing, easy forgetting.

## Section order

1. **Header** (cockpit pattern, mode tab `Memory` active in drawer
   shortcuts).
2. **Tabs** — Facts / AI Clone / Forgotten. Single horizontal pill
   group, gold fill on active.
3. **Per-tab body** — see component specs below.
4. **Add-fact bar** (only on Facts tab) — sticky-bottom input,
   gold-rim, "Tell TARS something about you…" placeholder.

## Layout

- Container `max-w-[960px] px-6` centred.
- Per-tab body: vertical stack of cards, gap-2.
- Mobile: tab pills wrap to 2 rows; cards 100%.

## Components

### Fact card
```
┌────────────────────────────────────────────────────────┐
│ ▌ Я работаю над платформой meeet.world                │
│   work · created 2 days ago · 86%                  ×   │
└────────────────────────────────────────────────────────┘
```
- 1px border + a `border-left: 2px solid var(--color-accent-soft)`
  (skill: AI-Native context-card pattern).
- Body text 14px Fira Code 400, `--color-ink`.
- Meta row 11px UPPER mono, `letter-spacing: 0.18em`,
  `--color-ink-2`: `<tag> · <relative-created> · <confidence>%`.
- Forget button (`×` glyph) right-aligned, ghost, on hover turns
  `--color-alert`.
- Forgetting requires `confirm("Forget this fact?")` — never silent.

### Confidence treatment
- `≥70%` — confidence number in `--color-success`.
- `30-70%` — `--color-ink-2`.
- `<30%` — italicised, `--color-ink-3`. The fact is dim — it's barely
  remembered.

### AI Clone profile (inline form)
```
TONE
  [direct, dry, pragmatic              ]

LENGTH PREFERENCE
  [short to medium                     ]

FAVOURITE PHRASES (comma-separated)
  [если честно, по факту, коротко      ]

AVOID (comma-separated)
  [канцелярит, избыточные оговорки     ]

LANGUAGES
  [ru, en                              ]

42 samples · last updated 2026-04-26
                                          [SAVE PROFILE]
```
- Each input: full-width, `--color-bg-1` background, gold-rim on
  focus.
- Labels 11px UPPER mono, `letter-spacing: 0.18em`,
  `--color-ink-2`.
- Save button gold-fill, only solid gold on this page.

### Forgotten log row
- Same shape as Fact card but at 60% opacity, no left accent, no
  `×` button. Meta row replaces "created" with "forgotten <relative>".
- Empty state: "Nothing forgotten yet" centred, mono 12px.

## Color overrides

- `--color-accent-soft` (gold 0.55) on fact card left border.
- `--color-success` for high-confidence number.
- `--color-alert` only on `×` hover and on Forgotten meta row.
  Never as a background.

## Motion

- Fact card delete: collapse height + fade out 220ms.
- New fact added: slide in from bottom-right of input bar, 250ms.
- Tab switch: cross-fade body 180ms.

## Anti-patterns

- ✗ Sliders / chips representing confidence. A number is enough
  (skill rule: numerical clarity > visual abstraction for trust
  contexts).
- ✗ "Suggested facts" a la auto-suggesting things to remember. User
  must opt in explicitly. Never proactive on this page.
- ✗ Bulk delete. Each delete is intentional, one at a time.
- ✗ Restore-from-forgotten button. Forgetting is a contract.

## States

- **Empty Facts** — "Nothing yet — chat with TARS so it can learn."
  + a `[Add a fact]` chip that focuses the input bar.
- **Loading** — 3 skeleton cards pulsing 1.6s.
- **Error** — `⚠ memory store unreachable` banner above tabs, retry
  button.

## Pre-delivery memory-checklist

- [ ] Tab switch is keyboard-accessible (`←/→` arrow keys when tab
      strip focused)
- [ ] Forget action requires double-confirmation only on `≥70%`
      confidence facts (preserve high-trust facts)
- [ ] Add-fact input always has visible focus ring
- [ ] AI Clone Save shows toast confirming `last_updated` timestamp
- [ ] Empty state on Forgotten tab is informative, not patronising
