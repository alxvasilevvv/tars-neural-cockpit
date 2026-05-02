/**
 * Contract tests for `shouldScrollTo` — the pure decision helper
 * that gates "should we call `el.scrollIntoView()` on the planner
 * page?". Every branch in the four "should I scroll?" cases listed
 * in the source-file docstring is pinned here so a refactor that
 * accidentally reverses one (e.g. "always scroll on selection
 * change" — bad UX, jumps the page when the user just clicked) is
 * caught by CI.
 */

import { describe, expect, it } from "vitest";

import { shouldScrollTo } from "@/lib/plannerScroll";

const planRow = (id: string) => ({ id });

describe("shouldScrollTo", () => {
  it("returns false when nothing is selected", () => {
    // `?selected=` empty / null → no row to scroll to.
    expect(
      shouldScrollTo(null, [planRow("pln_a"), planRow("pln_b")], null),
    ).toBe(false);
    expect(
      shouldScrollTo(null, [planRow("pln_a")], "pln_a"),
    ).toBe(false);
  });

  it("returns false while the plans list is still loading", () => {
    // `plansListed === null` ⇒ the initial fetch hasn't resolved
    // yet. We cannot scroll to a row that doesn't exist in the DOM.
    expect(shouldScrollTo("pln_a", null, null)).toBe(false);
  });

  it("returns false when the selected plan isn't in the visible list", () => {
    // Operator pasted a deep link to ?selected=pln_xyz but
    // ?status=approved hides it from the filtered list. The
    // PlanFullPanel still hydrates from /full (deep-link works),
    // but there's no row to scroll *to* in the rail.
    expect(
      shouldScrollTo("pln_xyz", [planRow("pln_a"), planRow("pln_b")], null),
    ).toBe(false);
  });

  it("returns false when we already scrolled for this selection", () => {
    // SSE refresh re-rendered the list but selection didn't change.
    // Re-scrolling would (a) waste a frame and (b) on Safari sometimes
    // fight with user scroll position.
    expect(
      shouldScrollTo("pln_a", [planRow("pln_a")], "pln_a"),
    ).toBe(false);
  });

  it("returns true on first paint with ?selected= in the URL", () => {
    // The "deep link from a paste" case — lastScrolled is null
    // because we haven't scrolled this session yet, and the row
    // exists in the DOM. The page MUST scroll the row into view.
    expect(
      shouldScrollTo(
        "pln_b",
        [planRow("pln_a"), planRow("pln_b"), planRow("pln_c")],
        null,
      ),
    ).toBe(true);
  });

  it("returns true when selection changes to a different in-list plan", () => {
    // Browser back/forward navigated the URL to a different plan
    // (or operator clicked a plan via list rail — which is also
    // safe to scroll because `block: "nearest"` makes it a no-op
    // when the row is already visible).
    expect(
      shouldScrollTo(
        "pln_c",
        [planRow("pln_a"), planRow("pln_b"), planRow("pln_c")],
        "pln_a",
      ),
    ).toBe(true);
  });

  it("returns true even when selected matches the first row", () => {
    // Defensive: there's no special-case "skip scroll for index 0"
    // — the helper trusts the caller's `block: \"nearest\"` to do
    // the right thing for the always-visible top row.
    expect(
      shouldScrollTo(
        "pln_a",
        [planRow("pln_a"), planRow("pln_b")],
        null,
      ),
    ).toBe(true);
  });

  it("treats empty plans array the same as 'no row to scroll to'", () => {
    // After a status filter change, the list can be empty even
    // though `plansListed` itself is non-null.
    expect(shouldScrollTo("pln_a", [], null)).toBe(false);
  });

  it("is pure: identical inputs ⇒ identical outputs across calls", () => {
    // No hidden state — same args always return the same boolean.
    const args = (): [string, { id: string }[], null] => [
      "pln_b",
      [planRow("pln_a"), planRow("pln_b")],
      null,
    ];
    const a = shouldScrollTo(...args());
    const b = shouldScrollTo(...args());
    const c = shouldScrollTo(...args());
    expect([a, b, c]).toEqual([true, true, true]);
  });
});
