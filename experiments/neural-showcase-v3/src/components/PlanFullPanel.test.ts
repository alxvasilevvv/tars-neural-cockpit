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
  formatRunAnnouncement,
  formatRunSummary,
  formatStartedAt,
  pickRunAnnouncement,
  shouldAdvanceCursor,
  statusTone,
  summariseStep,
} from "@/components/PlanFullPanel";
import type {
  PlanRun,
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

// ---------------------------------------------------------------------------
// Aria-live announcement helpers
// ---------------------------------------------------------------------------

const _ZERO_USAGE: PlanUsage = {
  calls: 0,
  tokens_in: 0,
  tokens_out: 0,
  cost_usd: null,
  latency_ms_total: 0,
  has_priced_models: false,
};

function _run(overrides: Partial<PlanRun> = {}): PlanRun {
  return {
    plan_id: "pln_x",
    started_at: 1_777_700_000,
    completed_at: null,
    status: "running",
    trace_id: "trc_run_default",
    parent_trace_id: "trc_plan",
    mode: "confirm",
    step_count: 3,
    steps_run: 0,
    steps_blocked: 0,
    steps_failed: 0,
    abort_reason: null,
    abort_requested: false,
    exception: null,
    took_ms: null,
    usage: _ZERO_USAGE,
    steps: [],
    ...overrides,
  };
}

describe("formatRunAnnouncement", () => {
  it("returns null while a run is still in flight", () => {
    // Screen-reader should stay quiet until the run terminates.
    expect(formatRunAnnouncement(_run({ status: "running" }))).toBeNull();
  });

  it("announces a clean completion with latency and cost", () => {
    const r = _run({
      status: "completed",
      took_ms: 1234.5,
      steps_run: 3,
      usage: {
        ..._ZERO_USAGE,
        calls: 2,
        cost_usd: 0.0123,
        has_priced_models: true,
      },
    });
    const msg = formatRunAnnouncement(r);
    expect(msg).toBe("Run completed in 1.23s · $0.0123.");
  });

  it("announces a soft failure when steps_failed > 0 even on completed", () => {
    // Soft failure: run finished but a step errored mid-flight.
    // Screen-reader users would otherwise miss this on dashboards
    // that just tally completed=success.
    const r = _run({
      status: "completed",
      took_ms: 580,
      steps_run: 3,
      steps_failed: 1,
      usage: {
        ..._ZERO_USAGE,
        calls: 1,
        cost_usd: 0.001,
        has_priced_models: true,
      },
    });
    expect(formatRunAnnouncement(r)).toBe(
      "Run completed with 1 failed step in 580.0ms · $0.0010.",
    );
  });

  it("pluralises soft-failure step counts > 1", () => {
    const r = _run({
      status: "completed",
      took_ms: 1500,
      steps_failed: 3,
      usage: { ..._ZERO_USAGE, cost_usd: null },
    });
    expect(formatRunAnnouncement(r)).toBe(
      "Run completed with 3 failed steps in 1.50s · n/a.",
    );
  });

  it("announces an aborted run with the abort reason", () => {
    const r = _run({
      status: "aborted",
      took_ms: 421,
      abort_reason: "operator clicked abort",
    });
    expect(formatRunAnnouncement(r)).toBe(
      "Run aborted after 421.0ms: operator clicked abort.",
    );
  });

  it("falls back to exception when abort_reason is missing", () => {
    const r = _run({
      status: "aborted",
      took_ms: 200,
      abort_reason: null,
      exception: "RuntimeError: boom",
    });
    expect(formatRunAnnouncement(r)).toBe(
      "Run aborted after 200.0ms: RuntimeError: boom.",
    );
  });

  it("falls back to a placeholder reason when neither field is set", () => {
    const r = _run({
      status: "aborted",
      took_ms: 100,
      abort_reason: null,
      exception: null,
    });
    expect(formatRunAnnouncement(r)).toBe(
      "Run aborted after 100.0ms: no reason given.",
    );
  });
});

describe("pickRunAnnouncement", () => {
  it("returns null when the runs list is empty", () => {
    expect(pickRunAnnouncement([], null)).toBeNull();
    expect(pickRunAnnouncement([], "trc_seen")).toBeNull();
  });

  it("returns null when only in-flight runs are present", () => {
    // Brand new plan; first run still ticking. No screen-reader
    // announcement until it terminates.
    const runs = [_run({ status: "running", trace_id: "trc_a" })];
    expect(pickRunAnnouncement(runs, null)).toBeNull();
  });

  it("picks the newest terminal run on first hydration", () => {
    // Brand new mount; lastAnnouncedTraceId is null. The
    // newest terminal run (skipping the in-flight head) gets
    // announced.
    const runs: PlanRun[] = [
      _run({ status: "running", trace_id: "trc_now" }),
      _run({
        status: "completed",
        trace_id: "trc_a",
        took_ms: 250,
        usage: {
          ..._ZERO_USAGE,
          cost_usd: 0.005,
          has_priced_models: true,
        },
      }),
      _run({
        status: "completed",
        trace_id: "trc_old",
        took_ms: 400,
      }),
    ];
    const pick = pickRunAnnouncement(runs, null);
    expect(pick).not.toBeNull();
    expect(pick!.traceId).toBe("trc_a");
    expect(pick!.message).toBe("Run completed in 250.0ms · $0.0050.");
  });

  it("dedupes against the last announced trace_id", () => {
    // Same envelope rendered twice (e.g. SSE refetch). We must
    // not re-announce the same run.
    const runs = [
      _run({
        status: "completed",
        trace_id: "trc_a",
        took_ms: 100,
      }),
    ];
    expect(pickRunAnnouncement(runs, "trc_a")).toBeNull();
  });

  it("announces a fresh terminal run after a previous one was acked", () => {
    // After we announced trc_a, a new run completed (trc_b
    // landed at index 0). The dedupe key is trace_id, not
    // index, so trc_b gets surfaced.
    const runs = [
      _run({
        status: "completed",
        trace_id: "trc_b",
        took_ms: 75,
      }),
      _run({
        status: "completed",
        trace_id: "trc_a",
        took_ms: 100,
      }),
    ];
    const pick = pickRunAnnouncement(runs, "trc_a");
    expect(pick).not.toBeNull();
    expect(pick!.traceId).toBe("trc_b");
  });

  it("treats null trace_id as 'cannot dedupe' and stays silent", () => {
    // Defensive: a terminal run with a null trace_id (legacy /
    // corrupt event chain) shouldn't trigger an announcement —
    // the empty key would swallow every subsequent terminal
    // run because lastAnnouncedTraceId would never advance.
    const runs = [
      _run({
        status: "completed",
        trace_id: null,
        took_ms: 100,
      }),
    ];
    expect(pickRunAnnouncement(runs, null)).toBeNull();
  });

  it("skips an in-flight head to find the newest terminal", () => {
    // Mid-rerun: a new plan.run.started just fired so the head
    // run is `running`, but the previous completion (trc_old)
    // hasn't been announced yet. We still want to announce
    // trc_old once.
    const runs = [
      _run({ status: "running", trace_id: "trc_new" }),
      _run({
        status: "aborted",
        trace_id: "trc_old",
        took_ms: 50,
        abort_reason: "user pressed stop",
      }),
    ];
    const pick = pickRunAnnouncement(runs, null);
    expect(pick).not.toBeNull();
    expect(pick!.traceId).toBe("trc_old");
    expect(pick!.message).toBe(
      "Run aborted after 50.0ms: user pressed stop.",
    );
  });
});
