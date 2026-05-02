/**
 * Pure decision helper for "should the planner page scroll the
 * currently-selected plan into view?".
 *
 * The Planner page (`/cockpit/planner`) keeps a registry of `<li>`
 * refs keyed by plan id and calls `scrollIntoView({ block: "nearest" })`
 * on the matching ref when this helper returns `true`. Splitting the
 * decision out of the React component lets us pin the contract with
 * Vitest without spinning up a full DOM (the actual scroll is a
 * no-op when the row is already visible thanks to `block: "nearest"`,
 * so the helper's only job is to *gate the call* so we don't fire it
 * uselessly on every re-render).
 *
 * The four "should I scroll?" cases:
 *
 * 1. **First paint with `?selected=<id>` in the URL** — operator
 *    pasted a deep link; the row is probably below the fold of the
 *    overflow-scroll list. → scroll.
 * 2. **User clicked a plan row in the list** — the row is by
 *    definition already in view (they just clicked it). The
 *    `selected` prop changes, but `block: "nearest"` makes the
 *    actual scroll a no-op anyway. → scroll (cheap; correct).
 * 3. **SSE event refreshed the plans list but selection unchanged**
 *    — `lastScrolled` already matches `selected`. → no-op.
 * 4. **Selected plan vanished from the filtered list** — operator
 *    flipped a status filter; we have no row to scroll to. → no-op.
 *
 * Returning `false` for cases 3-4 keeps the React effect cheap and
 * (more importantly) lets the helper double as a guard for the ref
 * lookup: if `shouldScrollTo` returns `true` but the ref map is
 * empty, the caller knows to bail without throwing.
 */

export interface PlanLike {
  readonly id: string;
}

/**
 * @param selected      Currently selected plan id (from URL state).
 * @param plansListed   The plans currently rendered in the list (post-filter).
 *                      `null` while the initial fetch is in flight.
 * @param lastScrolled  The plan id we last scrolled to, or `null` if
 *                      we haven't scrolled yet this session. The
 *                      caller persists this in a ref between renders.
 * @returns `true` iff the helper recommends a `scrollIntoView` call
 *          for the row matching `selected`. The caller is then
 *          responsible for updating `lastScrolled` to `selected`.
 */
export function shouldScrollTo(
  selected: string | null,
  plansListed: ReadonlyArray<PlanLike> | null,
  lastScrolled: string | null,
): boolean {
  if (!selected) return false;
  if (selected === lastScrolled) return false;
  if (!plansListed) return false;
  return plansListed.some((p) => p.id === selected);
}
