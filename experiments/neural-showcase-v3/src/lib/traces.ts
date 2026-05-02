/**
 * Pure helpers for the local Trace Viewer (`/cockpit/traces`).
 *
 * All side-effect-free so the cockpit page stays a thin shell on
 * top of these — and the helpers stay unit-testable without
 * wiring React / DOM / router infra into the test suite.
 */

export type RouteFilter = "all" | "edge" | "cloud" | "fallback" | "mixed";

export const ROUTE_FILTERS: readonly RouteFilter[] = [
  "all",
  "edge",
  "cloud",
  "fallback",
  "mixed",
] as const;

const _ROUTE_SET: ReadonlySet<string> = new Set(ROUTE_FILTERS);

/**
 * Coerce a possibly-null URL search-param into a {@link RouteFilter}.
 * Anything unrecognised falls back to "all" so the page never blows
 * up on a hand-crafted querystring.
 */
export function readRouteFilter(raw: string | null | undefined): RouteFilter {
  if (raw && _ROUTE_SET.has(raw)) return raw as RouteFilter;
  return "all";
}

/**
 * Map a primary_route value (or null) to a Tailwind class + a
 * short label suitable for a status pill. Centralised here so the
 * cockpit can test the colour contract once (rather than scattering
 * `case "edge":` clauses across components).
 */
export interface RouteTone {
  cls: string;
  label: string;
}

export function routeToTone(route: string | null | undefined): RouteTone {
  switch (route) {
    case "edge":
      return {
        cls: "border-line-strong text-[color:var(--color-success)]",
        label: "edge",
      };
    case "cloud":
      return { cls: "border-line-strong text-accent", label: "cloud" };
    case "fallback":
      return {
        cls: "border-line-strong text-[color:var(--brand-amber,#FBBF24)]",
        label: "fallback",
      };
    case "mixed":
      return { cls: "border-line text-ink-2", label: "mixed" };
    default:
      return { cls: "border-line text-ink-3", label: "—" };
  }
}

/** Format a millisecond duration with locale-aware unit suffixes. */
export function formatDurationMs(
  ms: number | null | undefined,
  units: { ms: string; s: string },
): string {
  if (ms == null || !Number.isFinite(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)} ${units.ms}`;
  return `${(ms / 1000).toFixed(2)} ${units.s}`;
}

/**
 * Format a USD cost. Sub-cent amounts render with 4 decimal
 * places so micro-costs stay visible (matches `formatCostUSD`
 * in `lib/planner.ts`); $0 stays as $0.00 to keep the column
 * aligned.
 */
export function formatCostUsd(usd: number, label = "USD"): string {
  if (!Number.isFinite(usd) || usd === 0) return `$0.00 ${label}`;
  if (Math.abs(usd) < 0.01) return `$${usd.toFixed(4)} ${label}`;
  return `$${usd.toFixed(2)} ${label}`;
}

/**
 * Format an epoch-seconds timestamp as a locale string. Returns
 * "—" on null / undefined / invalid input so the column never
 * renders "Invalid Date" in the operator's face.
 */
export function formatTs(epoch: number | null | undefined): string {
  if (epoch == null || !Number.isFinite(epoch) || epoch <= 0) return "—";
  try {
    const d = new Date(epoch * 1000);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleString();
  } catch {
    return "—";
  }
}
