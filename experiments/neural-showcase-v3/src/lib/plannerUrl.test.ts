/**
 * Vitest contract for the Planner page's URL-state mirror. Pins
 * round-tripping, default elision, and permissive parsing of bad
 * input — the bits most likely to break a deep-link.
 */

import { describe, expect, it } from "vitest";

import {
  DEFAULT_STATE,
  buildPlannerSearchParams,
  parsePlannerSearchParams,
  plannerStateEquals,
  type PlannerUrlState,
} from "@/lib/plannerUrl";

function rt(state: PlannerUrlState): PlannerUrlState {
  return parsePlannerSearchParams(buildPlannerSearchParams(state));
}

describe("parsePlannerSearchParams", () => {
  it("returns DEFAULT_STATE for an empty URL", () => {
    expect(parsePlannerSearchParams(new URLSearchParams())).toEqual(
      DEFAULT_STATE,
    );
  });

  it("accepts every valid status", () => {
    for (const s of [
      "all",
      "proposed",
      "approved",
      "running",
      "completed",
      "aborted",
      "rejected",
    ]) {
      const params = new URLSearchParams({ status: s });
      expect(parsePlannerSearchParams(params).status).toBe(s);
    }
  });

  it("falls back to 'all' for unknown / empty / whitespace status", () => {
    expect(
      parsePlannerSearchParams(new URLSearchParams({ status: "nope" })).status,
    ).toBe("all");
    expect(
      parsePlannerSearchParams(new URLSearchParams({ status: "" })).status,
    ).toBe("all");
    expect(
      parsePlannerSearchParams(new URLSearchParams({ status: "   " })).status,
    ).toBe("all");
  });

  it("trims q and treats whitespace-only as empty", () => {
    expect(
      parsePlannerSearchParams(new URLSearchParams({ q: "  hello  " })).q,
    ).toBe("hello");
    expect(
      parsePlannerSearchParams(new URLSearchParams({ q: "   " })).q,
    ).toBe("");
  });

  it("treats missing / empty / whitespace selected as null", () => {
    expect(parsePlannerSearchParams(new URLSearchParams()).selected).toBeNull();
    expect(
      parsePlannerSearchParams(new URLSearchParams({ selected: "" }))
        .selected,
    ).toBeNull();
    expect(
      parsePlannerSearchParams(new URLSearchParams({ selected: "   " }))
        .selected,
    ).toBeNull();
  });

  it("preserves a non-empty selected verbatim (after trim)", () => {
    expect(
      parsePlannerSearchParams(new URLSearchParams({ selected: "pln_abc123" }))
        .selected,
    ).toBe("pln_abc123");
    expect(
      parsePlannerSearchParams(
        new URLSearchParams({ selected: "  pln_xyz  " }),
      ).selected,
    ).toBe("pln_xyz");
  });
});

describe("buildPlannerSearchParams", () => {
  it("emits no params for the default state (URL stays short)", () => {
    expect(buildPlannerSearchParams(DEFAULT_STATE).toString()).toBe("");
  });

  it("emits status only when not 'all'", () => {
    expect(
      buildPlannerSearchParams({ ...DEFAULT_STATE, status: "running" })
        .toString(),
    ).toBe("status=running");
  });

  it("emits q only when non-empty", () => {
    expect(
      buildPlannerSearchParams({ ...DEFAULT_STATE, q: "hello" }).toString(),
    ).toBe("q=hello");
  });

  it("URL-encodes q (spaces, ampersand, unicode)", () => {
    const out = buildPlannerSearchParams({
      ...DEFAULT_STATE,
      q: "hello & world ☃",
    }).toString();
    // URLSearchParams uses '+' for spaces, percent-encoded otherwise.
    expect(out).toMatch(/^q=hello/);
    expect(out).toContain("%26");
    expect(out).toContain("%E2%98%83");
  });

  it("emits selected only when non-null", () => {
    expect(
      buildPlannerSearchParams({ ...DEFAULT_STATE, selected: "pln_1" })
        .toString(),
    ).toBe("selected=pln_1");
    expect(
      buildPlannerSearchParams({ ...DEFAULT_STATE, selected: null })
        .toString(),
    ).toBe("");
  });

  it("composes all three params in a stable order", () => {
    const out = buildPlannerSearchParams({
      status: "running",
      q: "wbtc",
      selected: "pln_xyz",
    }).toString();
    expect(out).toBe("status=running&q=wbtc&selected=pln_xyz");
  });
});

describe("round-trip parse(build(state)) === state", () => {
  it("preserves the default state", () => {
    expect(rt(DEFAULT_STATE)).toEqual(DEFAULT_STATE);
  });

  it("preserves a fully-filled state", () => {
    const s: PlannerUrlState = {
      status: "completed",
      q: "graph neural",
      selected: "pln_42",
    };
    expect(rt(s)).toEqual(s);
  });

  it("preserves status alone", () => {
    const s: PlannerUrlState = {
      ...DEFAULT_STATE,
      status: "aborted",
    };
    expect(rt(s)).toEqual(s);
  });

  it("preserves q alone (non-trimmed body)", () => {
    const s: PlannerUrlState = { ...DEFAULT_STATE, q: "hello world" };
    expect(rt(s)).toEqual(s);
  });
});

describe("plannerStateEquals", () => {
  it("returns true for the same content", () => {
    expect(plannerStateEquals(DEFAULT_STATE, DEFAULT_STATE)).toBe(true);
    const s: PlannerUrlState = {
      status: "running",
      q: "hi",
      selected: "x",
    };
    expect(plannerStateEquals(s, { ...s })).toBe(true);
  });

  it("returns false for any field difference", () => {
    expect(
      plannerStateEquals(DEFAULT_STATE, { ...DEFAULT_STATE, status: "running" }),
    ).toBe(false);
    expect(
      plannerStateEquals(DEFAULT_STATE, { ...DEFAULT_STATE, q: "x" }),
    ).toBe(false);
    expect(
      plannerStateEquals(DEFAULT_STATE, { ...DEFAULT_STATE, selected: "x" }),
    ).toBe(false);
  });
});
