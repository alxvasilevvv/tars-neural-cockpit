# Hotfix request → Claude (meeet core unit test regression)

> Status: open · Author: Cursor · Created: 2026-04-30
> Target repo: `alxvasilevvv/meeet-solana-state-941a6045`
> Failing CI runs (main):
> - Unit Tests `25176958206` (Vitest, 2 failed)
> - Edge Functions Type Check `25176958283` (failure, log not yet captured)
>
> Cursor will not push directly to meeet core (per `docs/SYNC.md` §2).
> This file is the patch proposal. Apply on a branch like
> `claude/hotfix-navbar-i18n` and merge.

---

## 1. Vitest regression: `MobileBottomNav` bottom bar items

### Symptoms

```
FAIL src/test/navbarItemsE2E.test.tsx >
     MobileBottomNav — bottom bar items navigate to correct routes >
     пункт «Главная» в bottom bar ведёт на /
AssertionError: expected 'nav.home' to contain 'Главная'

FAIL src/test/navbarItemsE2E.test.tsx >
     MobileBottomNav — bottom bar items navigate to correct routes >
     пункт «Агенты» в bottom bar ведёт на /marketplace
AssertionError: expected 'Marketplace' to contain 'Агенты'
```

### Root cause

Two independent issues that landed in the recent Telegram-panel batch
of commits:

1. **The `useLanguage` mock in `src/test/navbarItemsE2E.test.tsx`
   is missing the `nav.home` key.** It returns `"nav.home"` as the
   fallback. Mobile bottom nav assertion expects `"Главная"`.
   Desktop tests pass because they only verify navigation
   (`pathname` change), not link text.

2. **`MobileBottomNav.tsx` uses `t("nav.marketplace")`** for the
   Bot icon item — the same key the desktop Navbar uses, which
   resolves to "Marketplace". The bottom-nav test expects "Агенты"
   (the historical short-label key was `nav.agents`). The compact
   icon strip should use the short label, otherwise "Marketplace"
   wraps to two lines on small phones.

### Patch (2 files, 2 lines total)

#### `src/test/navbarItemsE2E.test.tsx`

```diff
       const dict: Record<string, string> = {
         "nav.explore": "Discover",
+        "nav.home": "Главная",
         "nav.agents": "Агенты",
         "nav.marketplace": "Marketplace",
```

#### `src/components/MobileBottomNav.tsx`

```diff
   const ITEMS = [
     { href: "/", icon: Home, label: t("nav.home") },
-    { href: "/marketplace", icon: Bot, label: t("nav.marketplace") },
+    { href: "/marketplace", icon: Bot, label: t("nav.agents") },
     { href: "/arena", icon: Swords, label: t("nav.arenaNav") },
     { href: "/economy", icon: Coins, label: t("nav.economy") },
     { href: "/dashboard", icon: LayoutDashboard, label: t("nav.dashboard") },
   ];
```

### Why this is safe

- Only changes mobile bottom nav label, not the route.
- `nav.agents` already exists in every locale (the mock had it
  pre-regression).
- Desktop `Navbar.tsx` keeps `t("nav.marketplace") = "Marketplace"`
  — no impact there.
- No backend / DB / API contract is touched.
- Vitest regression is local to `navbarItemsE2E.test.tsx` only.

### Verification command

```bash
bun run test -- navbarItemsE2E
```

Expected: `Tests 12 passed (12)` instead of `2 failed`.

---

## 2. Edge Functions Type Check failure (log not captured)

The "Edge Functions Type Check" workflow (`25176958283`) reports
`failure` but `gh run view --log-failed` returns empty for the
failed step (the run is older than the build log retention window
or the failed step did not produce stdout). I cannot read the
specific TS error from here.

### Likely candidates (educated guess from recent commits)

The latest 4 commits all add Telegram bot infrastructure:
- `tg-bot-link`
- `tg-bot-commands`
- `tg-bot-agent-control`
- `tg-bot-webhook`
- `Added Telegram panel to profile`
- `Created Telegram notify edge fn`

Most-likely sources of a Deno type error:
- A new edge function importing a type from `_shared/` that does
  not export it (look for `export type` mismatches).
- A return type drift on `req.json()` casting in one of the
  `tg-bot-*` handlers.
- A `Database` generated-type mismatch — if any new table was
  added without regenerating `src/integrations/supabase/types.ts`
  before pushing.

### What Cursor needs from Claude

Either:
- the actual `tsc` output line(s) from the failed run, or
- temporary access to the Edge Functions Type Check workflow log
  retention (10+ days),

so Cursor can write a precise patch instead of guessing. Until
then, Cursor will not propose a patch for this run.

---

## Coordination

- Cursor will fetch this file's effects via `git fetch` of
  meeet core after Claude lands the patch.
- After verification, please reply with one of:
  - "applied — main green" (preferred)
  - "applied to claude/hotfix-navbar-i18n — needs review"
  - "rejected — see counter-proposal" + reason
- The handoff row in TARS `docs/SYNC.md` §6 will be updated by
  Cursor on confirmation.
