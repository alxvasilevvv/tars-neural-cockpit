/**
 * Pure-helper tests for PlanFullPanel.
 *
 * The component itself is exercised live in `/cockpit/planner` (and
 * via Storybook-style props through `initialData`). What we lock in
 * here is the formatting + tone-mapping that the cockpit will use to
 * render plan / run rows — those are the bits most likely to drift
 * silently when backend payload shapes change.
 */

import { describe, expect, it } from "vitest";

import {
  REFETCH_KINDS,
  formatLatencyMs,
  formatLifetimeSummary,
  formatRunSummary,
  formatStartedAt,
  shouldAdvanceCursor,
  statusTone,
  summariseStep,
} from "@/components/PlanFullPanel";
import type {
  PlanStep,
  PlanUsage,
  PlanUsageLifetime,
} from "@/lib/planner";

describe("statusTone", () => {
  it("maps each plan / run status to a stable tone", () => {
    expect(statusTone("proposed")).toBe("muted");
    expect(statusTone("approved")).toBe("accent");
    expect(statusTone("running")).toBe("warning");
    expect(statusTone("completed")).toBe("success");
    expect(statusTone("aborted")).toBe("alert");
    expect(statusTone("rejected")).toBe("alert");
  });

  it("falls back to muted for unknown values", () => {
    // @ts-expect-error -- exercising the defensive default branch
    expect(statusTone("nope")).toBe("muted");
  });
});

describe("formatLatencyMs", () => {
  it("returns n/a for nullish, NaN, negative", () => {
    expect(formatLatencyMs(null)).toBe("n/a");
    expect(formatLatencyMs(undefined)).toBe("n/a");
    expect(formatLatencyMs(Number.NaN)).toBe("n/a");
    expect(formatLatencyMs(-1)).toBe("n/a");
  });

  it("renders sub-second values in ms with one decimal", () => {
    expect(formatLatencyMs(0)).toBe("0.0ms");
    expect(formatLatencyMs(12.345)).toBe("12.3ms");
    expect(formatLatencyMs(999.9)).toBe("999.9ms");
  });

  it("renders ≥1s values in seconds with two decimals", () => {
    expect(formatLatencyMs(1000)).toBe("1.00s");
    expect(formatLatencyMs(1234)).toBe("1.23s");
    expect(formatLatencyMs(60_000)).toBe("60.00s");
  });
});

describe("formatStartedAt", () => {
  it("returns em-dash for nullish / NaN / out-of-range", () => {
    expect(formatStartedAt(null)).toBe("—");
    expect(formatStartedAt(undefined)).toBe("—");
    expect(formatStartedAt(Number.NaN)).toBe("—");
  });

  it("renders unix seconds as YYYY-MM-DD HH:MM:SSZ in UTC", () => {
    // 2026-05-01T12:34:56Z
    const unix = Date.UTC(2026, 4, 1, 12, 34, 56) / 1000;
    expect(formatStartedAt(unix)).toBe("2026-05-01 12:34:56Z");
  });
});

describe("formatRunSummary", () => {
  it("includes calls / tokens / cost honouring null cost", () => {
    const usage: PlanUsage = {
      calls: 3,
      tokens_in: 120,
      tokens_out: 45,
      cost_usd: 0.0234,
      latency_ms_total: 100,
      has_priced_models: true,
    };
    expect(formatRunSummary(usage)).toBe(
      "calls=3 · tokens=120+45 · cost=$0.0234",
    );
  });

  it("renders cost=n/a when no priced model fired", () => {
    const usage: PlanUsage = {
      calls: 1,
      tokens_in: 0,
      tokens_out: 0,
      cost_usd: null,
      latency_ms_total: 0,
      has_priced_models: false,
    };
    expect(formatRunSummary(usage)).toBe(
      "calls=1 · tokens=0+0 · cost=n/a",
    );
  });
});

describe("formatLifetimeSummary", () => {
  it("uses singular 'run' for runs_aggregated=1", () => {
    const u: PlanUsageLifetime = {
      calls: 1,
      tokens_in: 10,
      tokens_out: 20,
      cost_usd: 0.001,
      latency_ms_total: 5,
      has_priced_models: true,
      runs_aggregated: 1,
    };
    expect(formatLifetimeSummary(u)).toBe(
      "across 1 run · calls=1 · tokens=10+20 · cost=$0.0010",
    );
  });

  it("uses plural 'runs' otherwise (incl. 0)", () => {
    const zero: PlanUsageLifetime = {
      calls: 0,
      tokens_in: 0,
      tokens_out: 0,
      cost_usd: null,
      latency_ms_total: 0,
      has_priced_models: false,
      runs_aggregated: 0,
    };
    expect(formatLifetimeSummary(zero)).toBe(
      "across 0 runs · calls=0 · tokens=0+0 · cost=n/a",
    );

    const many: PlanUsageLifetime = { ...zero, runs_aggregated: 7 };
    expect(formatLifetimeSummary(many).startsWith("across 7 runs · ")).toBe(
      true,
    );
  });
});

describe("summariseStep", () => {
  it("emits id · action · {} for argless steps", () => {
    const s: PlanStep = { id: "s1", action: "noop.action" };
    expect(summariseStep(s)).toBe("s1 · noop.action · {}");
  });

  it("emits id · action · args(json) for steps with args", () => {
    const s: PlanStep = {
      id: "s2",
      action: "traders.fetch_quote",
      args: { ticker: "WBTC" },
    };
    expect(summariseStep(s)).toBe(
      's2 · traders.fetch_quote · {"ticker":"WBTC"}',
    );
  });
});

describe("REFETCH_KINDS", () => {
  it("includes the lifecycle events the panel must react to", () => {
    [
      "plan.run.started",
      "plan.run.usage",
      "plan.completed",
      "plan.aborted",
      "plan.abort.requested",
      "planner.cloned",
    ].forEach((kind) => {
      expect(REFETCH_KINDS.has(kind)).toBe(true);
    });
  });

  it("does NOT include cosmetic / verbose-only events", () => {
    [
      "plan.proposed",
      "plan.step.requested",
      "plan.step.allowed",
      "plan.step.completed",
      "planner.synthesis.completed",
    ].forEach((kind) => {
      expect(REFETCH_KINDS.has(kind)).toBe(false);
    });
  });
});

describe("shouldAdvanceCursor", () => {
  it("always advances when cursor is null (first frame)", () => {
    expect(shouldAdvanceCursor(null, 0)).toBe(true);
    expect(shouldAdvanceCursor(null, 999)).toBe(true);
  });

  it("advances when the new id is strictly greater", () => {
    expect(shouldAdvanceCursor(10, 11)).toBe(true);
    expect(shouldAdvanceCursor(10, 10)).toBe(false);
    expect(shouldAdvanceCursor(10, 9)).toBe(false);
  });
});
