# Operator · Page Override

> **Master:** [`design-system/tars/MASTER.md`](../MASTER.md).
> **Skill:** `--domain style "real-time monitoring HUD operator dark"`,
> Operator is the **highest-stakes** surface (Mac actions execute on the
> user's machine), so design bias is toward clarity, friction at the right
> moments, and explicit risk signalling.

---

## What this surface is

The Mac Operator panel. User picks an action (Sort Downloads / Reply
iMessage / Schedule meeting / Run script / Browse+Extract / Send email /
Summarize file / Web search). Low-risk auto-executes. Medium/high
requires an explicit approval gate with a payload preview. Every
execution drops a signed receipt into the right-side ledger.

## Section order (replaces Master §2)

1. **Header** (same as cockpit, with mode tab `▤ Operator` active).
2. **Two-column grid:**
   - **Left** (1fr) — actions tile grid, 2 → 4 columns responsive.
   - **Right** (360px) — receipts ledger, sticky, scrolls
     independently.
3. **Approval modal** — appears over scrim only when a medium/high
   action is started. Single source of risk signalling.

## Layout

- Container `max-w-[1200px] px-6` centred, no edge-to-edge.
- Tile grid: `repeat(auto-fit, minmax(220px, 1fr))`, `gap-3`.
- Tiles square-ish, `min-h-[160px]`, `rounded-[14px]`, hairline border.
- Ledger column collapses below tiles on `<880px`.

## Color overrides

Risk colouring is the only place where we permit colour to encode
meaning beyond the gold accent:

| Risk | Token | Visual |
|------|-------|--------|
| `low` | `var(--color-success)` (green) | small chip bottom-left of tile |
| `medium` | `var(--color-accent)` (gold) | gold rim on tile |
| `high` | `var(--color-alert)` (red) | red chip + dim gold rim |

The chip is a 9px monospaced UPPER label. Never bigger.

## Components

### Action tile
```
┌────────────────────────────┐
│ ▤  Sort Downloads          │
│                            │
│ Группирует ~/Downloads по  │
│ типу: PDF / Images / …     │
│                            │
│ [LOW RISK]                 │
└────────────────────────────┘
```
- Glyph 18px, gold tint, top-left.
- Title `Fira Code` 15px / 500.
- Description 12px / 400 / `--color-ink-2`, max 2 lines clamp.
- Risk chip at bottom-left, no decoration except the colour.
- Whole tile is a `<button>`. `cursor-pointer`, focus-visible gold ring.
- Hover: `border-color` to `--color-line-hot`. No translateY.

### Receipts ledger row
```
┌─────────────────────────────┐
│ Sort Downloads      [EXEC]  │
│ rcp_a91f0c2…       14:08    │
└─────────────────────────────┘
```
- 14px name + status pill (`PENDING` gold / `EXECUTED` green /
  `REJECTED` red).
- Mono row below: receipt id (truncated 10 chars) + relative time.
- Hover row → expand inline preview of `result` json, monospace.
- Pending rows show `APPROVE` / `REJECT` mono buttons inline.

### Approval gate (modal)
```
┌──────────────────────────────────────────────┐
│  Approve: Send email                          │
│  rcp_a91f0c2 · risk: high                     │
│                                                │
│  ┌────────────────────────────────────────┐   │
│  │ {                                       │   │
│  │   "to": "alex@meeet.world",            │   │
│  │   "subject": "weekly summary",         │   │
│  │   "body": "..."                         │   │
│  │ }                                       │   │
│  └────────────────────────────────────────┘   │
│                                                │
│           [CANCEL]  [REJECT]  [APPROVE & RUN]  │
└──────────────────────────────────────────────┘
```
- Modal width 500px max.
- Payload preview: `<pre>` with `Fira Code` 12px, line-height 1.5,
  scrollable to 280px. Syntax-coloured: keys gold, strings ink-2,
  numbers success-green.
- Three buttons: `Cancel` (ghost), `Reject` (red outline),
  `Approve & run` (success-green fill, only solid green button in the
  product).
- `Esc` cancels. Enter approves only if a checkbox "I understand this
  acts on my machine" is ticked (high-risk only).

## Motion

Allowed motions on this surface:
- Receipt row appearing — fade-in 200ms ease-out.
- Modal scrim — opacity 0 → 1 in 180ms.
- Modal card — slide-up 8px + fade in 220ms.

Forbidden:
- Tile hover scaling.
- Risk chip pulsing (the chip is loud enough; pulse implies
  "live alert", not "static state").
- Confetti / success animations on receipt completion.

## Anti-patterns

- ✗ Auto-approving anything tagged `medium` or `high`. Only `low`
  auto-runs.
- ✗ Hiding the approval gate behind a settings toggle ("trust this app
  for 30 days"). The gate is non-bypassable for non-low actions in v9.
- ✗ Generic "are you sure?" copy. The modal must show the actual
  payload, no exceptions.
- ✗ Risk colour on the action title (e.g. red title for "Send email").
  Risk lives in the chip only — title stays default-ink.

## States

- **Empty ledger** — "No actions yet. Click a tile to start." centred
  in the receipts column, mono 11px.
- **Loading action** (between click and modal open) — tile shows
  3-dot pulse top-right, brief.
- **Network error** — toast bottom-centre `⚠ couldn't reach operator
  backend`. Tiles disable for 8s.

## Honesty rules (this surface specifically)

- A stub action (`reply_imessage`, `schedule_meeting`, `send_email`)
  must show its tile but with a clear "BETA · returns informative
  error" badge. No hidden mocks.
- Receipt `result.ok=false` rows are visually distinct: dimmed text +
  red `FAILED` pill. User must see when something didn't work.

## Pre-delivery operator-checklist

- [ ] All 8 actions render with correct risk colour
- [ ] Low-risk action click → executes → receipt appears in <500ms
- [ ] High-risk action click → modal opens → payload preview correct
- [ ] Approval modal: Esc cancels, focus-trap works, focus returns to
      triggering tile on close
- [ ] Receipts list updates without full re-render (DOM-stable)
- [ ] Failed receipts visibly distinct
- [ ] Mobile: tiles → 1 column at 480px, ledger moves below
