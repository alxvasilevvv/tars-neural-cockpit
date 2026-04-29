# Code · Page Override

> **Master:** [`design-system/tars/MASTER.md`](../MASTER.md).
> **Skill:** `--stack html-tailwind "dark dashboard hairline border mono
> labels card hover"` · `--domain ux "focus visible keyboard"`.
> The IDE-feel surface — closest to a developer tool, so it leans hardest
> into Master's mono/HUD layer.

---

## What this surface is

Chat-with-codebase. Three columns: file tree (left), file viewer
(centre), search/citations strip (right). User opens a folder, asks a
question, gets cited results.

## Section order

1. **Header** — slim 48px (smaller than cockpit's 56px because content
   density is higher). Logo + path-input + Open + back-to-cockpit link.
2. **Three-column grid:**
   - Left 280px — file tree.
   - Centre `1fr` — file viewer (header + scrollable code).
   - Right 360px — "Ask the codebase" input + cited hits.

## Layout

- Grid: `grid-template-columns: 280px 1fr 360px;
   grid-template-rows: 48px 1fr;` (full viewport height, no scroll on
   container).
- Each column scrolls independently.
- `<880px`: collapse to single column with tabs (Tree / View / Search).

## Color overrides

- File tree bg `--color-bg-1`, dir entries `--color-ink`, file entries
  `--color-ink-2`. Active file `--color-bg-2` background +
  `--color-accent` text.
- File viewer bg `var(--color-bg-0)` (true black) — code reads better
  on pure black.
- Citations panel bg `--color-bg-1`.
- Hairline columns separators `--color-line`.

## Components

### File tree node
- Padding `4px 8px`, `border-radius: 5px`.
- Glyph prefix: `▸ ` for dir, `· ` for file (single space file glyph
  to avoid noise).
- Indent: 12px per depth level.
- Hover: `--color-bg-2` background.
- Active: gold accent text.
- Truncate names with ellipsis at panel width.

### File header (above viewer)
```
~/projects/tars/web_extras/routers/briefing_router.py    PY · 312 LINES
```
- Path left-aligned, mono 11px, `--color-ink-2`.
- Meta right-aligned, mono 10px UPPER, `--color-ink-2`.
- 1px hairline below, `--color-line`.

### File viewer
- `<pre>` `Fira Code` 13px, line-height 1.6.
- Line numbers (gutter): 11px, `--color-ink-3`, right-aligned, 2-char
  min, padded by mono ch units.
- No syntax highlighting in v9 (kept honest — TF-IDF mode). v9.1+
  may add Prism.
- Long lines wrap with a hanging indent of 2ch.

### Citation card (right column)
```
┌──────────────────────────────────────────┐
│ web_extras/routers/briefing_router.py    │
│ :161                                      │
│ def _build_mock(name: str) -> Briefing:  │
└──────────────────────────────────────────┘
```
- Path 11px mono UPPER, `letter-spacing: 0.18em`, `--color-ink-2`.
- Line ref `:161` in gold accent, 11px.
- Preview 12px Fira Code, `--color-ink`, single line, ellipsis on
  overflow.
- Click → opens that file in the centre column, scrolls to line.

### Ask-the-codebase input
- Sticky-top of right column.
- Full-width, gold rim, "Where is the auth handler?" placeholder.
- Debounce 350ms before search hits backend.

## Motion

Allowed:
- Citation card appearing — fade-in 180ms.
- Active file highlight on tree — `--color-bg-2` fades in 150ms.

Forbidden:
- Tree node expand/collapse animation (instant — devs hate slow
  expand).
- Smooth-scroll on jumping to a citation line. Use `scrollIntoView({
  block: 'start' })` (instant). Smooth scroll feels off in a code
  context.

## Honesty rules

- Search results show their `score` (TF-IDF) for transparency.
- Index status (`indexed: true`, `chunks: N`) shown in the right-column
  footer. The user must know whether they're searching the latest.
- Re-index button visible if `last_built` is older than 1 hour OR if
  `git status` shows changes (when ide-aware).

## Anti-patterns

- ✗ "Smart suggestions" panel that LLM-completes the user's query.
  We're TF-IDF — say so.
- ✗ Pretty syntax highlighting in v9 (out of scope, stay mono).
- ✗ Auto-opening the first file in the tree on folder load. User
  picks.
- ✗ Hover-preview tooltips on tree nodes. Click to view.

## States

- **No folder opened** — centre column shows centred mono prompt
  "Open a folder to start" with the path-input pre-focused.
- **Empty tree** (folder has no code files) — "No supported files in
  this folder. Supported: .py .js .ts .go ..." 12-line dim list.
- **Search empty** — "No matches for `<query>`."
- **Search loading** — 3-dot pulse next to the input.
- **Index out of date** — soft yellow banner "Index is 2h old, files
  may have changed. [Re-index]" above search input.

## Pre-delivery code-checklist

- [ ] Tree node click → file in viewer in <100ms (file already
      fetched preferred)
- [ ] Search latency target: <200ms for indexed folder
- [ ] Keyboard: `↑/↓` to navigate citations, `Enter` to open
- [ ] File >500KB → graceful "file too big to preview, use search
      instead" placeholder
- [ ] Re-index runs in background, doesn't block UI
- [ ] Index status visible at all times
