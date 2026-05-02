/**
 * Pure parse / build helpers for the `/cockpit/planner` URL state.
 *
 * The Planner page mirrors three pieces of UI state in the URL so
 * operators can deep-link, share, or just refresh without losing
 * context:
 *
 *   - `?status=<status>`  — one of the `PlanStatus` values, or
 *     "all" (default).
 *   - `?q=<text>`         — free-text filter applied to plan id /
 *     goal / pack_slug. Empty string means no filter.
 *   - `?selected=<id>`    — currently selected plan id; null when
 *     nothing is selected.
 *
 * The helpers are pure / DOM-free so the Vitest sibling can pin
 * round-tripping (parse(build(state)) === state) without spinning
 * up React or the router.
 *
 * Conventions:
 *
 *   - Build emits `URLSearchParams` (not a string) so the caller can
 *     concat with other params if needed.
 *   - Build OMITS keys at their default values to keep the URL short
 *     ("all" status, empty `q`, null `selected` are all elided).
 *   - Parse is permissive: unknown status falls back to "all"; missing
 *     keys default. Invalid input never throws.
 */

import type { PlanStatus } from "@/lib/planner";

/** UI state mirrored to / from the URL. */
export interface PlannerUrlState {
  status: PlanStatus | "all";
  q: string;
  selected: string | null;
}

export const DEFAULT_STATE: PlannerUrlState = {
  status: "all",
  q: "",
  selected: null,
};

const VALID_STATUSES: ReadonlyArray<PlanStatus | "all"> = [
  "all",
  "proposed",
  "approved",
  "running",
  "completed",
  "aborted",
  "rejected",
];

function isValidStatus(value: string): value is PlanStatus | "all" {
  return (VALID_STATUSES as ReadonlyArray<string>).includes(value);
}

/** Parse a `URLSearchParams` (or anything with `.get`) into UI state. */
export function parsePlannerSearchParams(
  params: URLSearchParams,
): PlannerUrlState {
  const rawStatus = (params.get("status") ?? "").trim();
  const status: PlanStatus | "all" = isValidStatus(rawStatus)
    ? rawStatus
    : "all";

  const q = (params.get("q") ?? "").trim();

  const rawSelected = (params.get("selected") ?? "").trim();
  const selected = rawSelected.length > 0 ? rawSelected : null;

  return { status, q, selected };
}

/**
 * Build a `URLSearchParams` snapshot of the given state. Keys at
 * their defaults are omitted so the rendered URL stays short.
 */
export function buildPlannerSearchParams(
  state: PlannerUrlState,
): URLSearchParams {
  const params = new URLSearchParams();
  if (state.status !== DEFAULT_STATE.status) {
    params.set("status", state.status);
  }
  if (state.q !== DEFAULT_STATE.q) {
    params.set("q", state.q);
  }
  if (state.selected !== null) {
    params.set("selected", state.selected);
  }
  return params;
}

/** Convenience: shallow-equal compare for PlannerUrlState. */
export function plannerStateEquals(
  a: PlannerUrlState,
  b: PlannerUrlState,
): boolean {
  return (
    a.status === b.status && a.q === b.q && a.selected === b.selected
  );
}
