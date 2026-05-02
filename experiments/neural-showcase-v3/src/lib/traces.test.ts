/**
 * Pure-helper contract tests for `lib/traces.ts`.
 *
 * These pin the format / coercion contracts the Trace Viewer page
 * depends on so a future refactor can't quietly drift the operator
 * UI (e.g. flipping "—" placeholders to "Invalid Date" or losing
 * the sub-cent decimal precision).
 */

import { describe, expect, it } from "vitest";

import {
  ROUTE_FILTERS,
  formatCostUsd,
  formatDurationMs,
  formatTs,
  readRouteFilter,
  routeToTone,
} from "./traces";

const UNITS = { ms: "ms", s: "s" };

describe("readRouteFilter", () => {
  it("returns the value when it is a known route", () => {
    for (const r of ROUTE_FILTERS) {
      expect(readRouteFilter(r)).toBe(r);
    }
  });

  it("falls back to 'all' on null / undefined / unknown", () => {
    expect(readRouteFilter(null)).toBe("all");
    expect(readRouteFilter(undefined)).toBe("all");
    expect(readRouteFilter("")).toBe("all");
    expect(readRouteFilter("not-a-route")).toBe("all");
    expect(readRouteFilter("Edge")).toBe("all"); // case-sensitive on purpose
  });
});

describe("routeToTone", () => {
  it("returns a Tailwind class + label for every documented route", () => {
    expect(routeToTone("edge").label).toBe("edge");
    expect(routeToTone("cloud").label).toBe("cloud");
    expect(routeToTone("fallback").label).toBe("fallback");
    expect(routeToTone("mixed").label).toBe("mixed");
  });

  it("renders an em-dash for null / unknown routes (no 'undefined' leak)", () => {
    expect(routeToTone(null).label).toBe("—");
    expect(routeToTone(undefined).label).toBe("—");
    expect(routeToTone("not-a-route").label).toBe("—");
  });

  it("never returns an empty class string (would break the pill border)", () => {
    for (const r of [...ROUTE_FILTERS, null, undefined, "weird"] as const) {
      const tone = routeToTone(r as string | null | undefined);
      expect(tone.cls.length).toBeGreaterThan(0);
    }
  });
});

describe("formatDurationMs", () => {
  it("renders sub-second ms with a rounded integer", () => {
    expect(formatDurationMs(0, UNITS)).toBe("0 ms");
    expect(formatDurationMs(12, UNITS)).toBe("12 ms");
    expect(formatDurationMs(999, UNITS)).toBe("999 ms");
    expect(formatDurationMs(123.7, UNITS)).toBe("124 ms");
  });

  it("renders ≥ 1s as a 2-decimal seconds value", () => {
    expect(formatDurationMs(1000, UNITS)).toBe("1.00 s");
    expect(formatDurationMs(1500, UNITS)).toBe("1.50 s");
    expect(formatDurationMs(60_000, UNITS)).toBe("60.00 s");
  });

  it("renders an em-dash for null / NaN / Infinity (never 'undefined ms')", () => {
    expect(formatDurationMs(null, UNITS)).toBe("—");
    expect(formatDurationMs(undefined, UNITS)).toBe("—");
    expect(formatDurationMs(NaN, UNITS)).toBe("—");
    expect(formatDurationMs(Infinity, UNITS)).toBe("—");
  });

  it("respects locale-aware unit suffixes", () => {
    expect(formatDurationMs(50, { ms: "мс", s: "с" })).toBe("50 мс");
    expect(formatDurationMs(2000, { ms: "мс", s: "с" })).toBe("2.00 с");
  });
});

describe("formatCostUsd", () => {
  it("renders 0 / NaN / Infinity as $0.00 (never 'NaN USD')", () => {
    expect(formatCostUsd(0)).toBe("$0.00 USD");
    expect(formatCostUsd(NaN)).toBe("$0.00 USD");
    expect(formatCostUsd(Infinity)).toBe("$0.00 USD");
  });

  it("renders sub-cent values with 4 decimals so micro-costs stay visible", () => {
    expect(formatCostUsd(0.0001)).toBe("$0.0001 USD");
    expect(formatCostUsd(0.0099)).toBe("$0.0099 USD");
  });

  it("renders ≥ 1¢ values with 2 decimals", () => {
    expect(formatCostUsd(0.01)).toBe("$0.01 USD");
    expect(formatCostUsd(1.2345)).toBe("$1.23 USD");
    expect(formatCostUsd(999.9)).toBe("$999.90 USD");
  });

  it("respects a custom currency label suffix", () => {
    expect(formatCostUsd(0.5, "$MEEET")).toBe("$0.50 $MEEET");
  });
});

describe("formatTs", () => {
  it("renders a non-empty locale string for a valid epoch", () => {
    const out = formatTs(1714665600); // 2024-05-02T16:00:00Z
    expect(out).not.toBe("—");
    expect(out.length).toBeGreaterThan(0);
  });

  it("renders an em-dash for null / NaN / 0 / negative values", () => {
    expect(formatTs(null)).toBe("—");
    expect(formatTs(undefined)).toBe("—");
    expect(formatTs(0)).toBe("—");
    expect(formatTs(-1)).toBe("—");
    expect(formatTs(NaN)).toBe("—");
  });
});
