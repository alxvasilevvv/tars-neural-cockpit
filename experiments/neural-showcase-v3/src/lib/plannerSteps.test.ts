/**
 * Vitest contract for the per-step live reducer that powers the
 * cockpit's `PlanFullPanel` step list. Every transition the
 * backend can emit is exercised here so a payload-shape change
 * surfaces in CI before it surfaces in the cockpit.
 */

import { describe, expect, it } from "vitest";

import {
  EMPTY_SNAPSHOT,
  applyEvent,
  pendingSnapshot,
  snapshotInFlight,
  stepStatusLabel,
} from "@/lib/plannerSteps";
import type { PlannerEvent } from "@/lib/planner";

const STEP_IDS = ["s1", "s2", "s3"] as const;

function ev(
  kind: PlannerEvent["kind"],
  payload: Record<string, unknown>,
  opts: { id?: number; trace_id?: string | null } = {},
): PlannerEvent {
  return {
    id: opts.id ?? 1,
    kind,
    ts: 1234567890,
    trace_id: opts.trace_id ?? "trc_run_1",
    payload,
  };
}

describe("pendingSnapshot", () => {
  it("seeds every known step id as pending with no trace lock yet", () => {
    const snap = pendingSnapshot(STEP_IDS);
    expect(snap.trace_id).toBeNull();
    for (const id of STEP_IDS) {
      expect(snap.steps[id]).toEqual({ status: "pending" });
    }
  });

  it("returns an empty steps map when no ids are provided", () => {
    expect(pendingSnapshot([])).toEqual(EMPTY_SNAPSHOT);
  });
});

describe("applyEvent · plan.run.started", () => {
  it("locks onto the run trace and resets every step to pending", () => {
    const seeded = pendingSnapshot(STEP_IDS);
    const next = applyEvent(
      seeded,
      ev("plan.run.started", { plan_id: "pln_1" }, { trace_id: "trc_run_a" }),
      STEP_IDS,
    );
    expect(next.trace_id).toBe("trc_run_a");
    expect(Object.values(next.steps).every((s) => s.status === "pending")).toBe(
      true,
    );
  });

  it("ignores a re-delivery of the same start frame (same trace)", () => {
    const seeded = applyEvent(
      pendingSnapshot(STEP_IDS),
      ev("plan.run.started", {}, { trace_id: "trc_run_a", id: 1 }),
      STEP_IDS,
    );
    // Walk a step to "requested" so we can prove the redelivery doesn't reset.
    const after = applyEvent(
      seeded,
      ev("plan.step.requested", { step_id: "s1" }, { trace_id: "trc_run_a", id: 2 }),
      STEP_IDS,
    );
    expect(after.steps["s1"]?.status).toBe("requested");

    const redelivered = applyEvent(
      after,
      ev("plan.run.started", {}, { trace_id: "trc_run_a", id: 3 }),
      STEP_IDS,
    );
    expect(redelivered.steps["s1"]?.status).toBe("requested");
    expect(redelivered).toBe(after);
  });

  it("a fresh run trace resets the snapshot even mid-flight", () => {
    const seeded = applyEvent(
      pendingSnapshot(STEP_IDS),
      ev("plan.run.started", {}, { trace_id: "trc_run_a" }),
      STEP_IDS,
    );
    const mid = applyEvent(
      seeded,
      ev("plan.step.requested", { step_id: "s1" }, { trace_id: "trc_run_a" }),
      STEP_IDS,
    );
    const restarted = applyEvent(
      mid,
      ev("plan.run.started", {}, { trace_id: "trc_run_b" }),
      STEP_IDS,
    );
    expect(restarted.trace_id).toBe("trc_run_b");
    for (const id of STEP_IDS) {
      expect(restarted.steps[id]?.status).toBe("pending");
    }
  });
});

describe("applyEvent · scoping", () => {
  it("ignores step events from a foreign trace", () => {
    const seeded = applyEvent(
      pendingSnapshot(STEP_IDS),
      ev("plan.run.started", {}, { trace_id: "trc_run_a" }),
      STEP_IDS,
    );
    const stray = applyEvent(
      seeded,
      ev(
        "plan.step.completed",
        { step_id: "s1", ok: true },
        { trace_id: "trc_run_other" },
      ),
      STEP_IDS,
    );
    expect(stray).toBe(seeded);
  });

  it("ignores step events with no step_id payload", () => {
    const seeded = applyEvent(
      pendingSnapshot(STEP_IDS),
      ev("plan.run.started", {}, { trace_id: "trc_run_a" }),
      STEP_IDS,
    );
    const noisy = applyEvent(
      seeded,
      ev("plan.step.completed", {}, { trace_id: "trc_run_a" }),
      STEP_IDS,
    );
    expect(noisy).toBe(seeded);
  });

  it("ignores unrelated kinds (cosmetic-only events)", () => {
    const seeded = applyEvent(
      pendingSnapshot(STEP_IDS),
      ev("plan.run.started", {}, { trace_id: "trc_run_a" }),
      STEP_IDS,
    );
    const noisy = applyEvent(
      seeded,
      ev(
        "planner.synthesis.completed",
        { plan_id: "pln_x" },
        { trace_id: "trc_run_a" },
      ),
      STEP_IDS,
    );
    expect(noisy).toBe(seeded);
  });
});

describe("applyEvent · plan.step.requested", () => {
  it("flips the step to requested and records parallel flag", () => {
    const seeded = applyEvent(
      pendingSnapshot(STEP_IDS),
      ev("plan.run.started", {}, { trace_id: "trc_run_a" }),
      STEP_IDS,
    );
    const next = applyEvent(
      seeded,
      ev(
        "plan.step.requested",
        { step_id: "s1", parallel: true },
        { trace_id: "trc_run_a" },
      ),
      STEP_IDS,
    );
    expect(next.steps["s1"]).toEqual({ status: "requested", parallel: true });
  });
});

describe("applyEvent · plan.step.allowed", () => {
  it("flips to blocked when allowed=false (eager update)", () => {
    const seeded = applyEvent(
      pendingSnapshot(STEP_IDS),
      ev("plan.run.started", {}, { trace_id: "trc_run_a" }),
      STEP_IDS,
    );
    const requested = applyEvent(
      seeded,
      ev(
        "plan.step.requested",
        { step_id: "s1" },
        { trace_id: "trc_run_a" },
      ),
      STEP_IDS,
    );
    const blocked = applyEvent(
      requested,
      ev(
        "plan.step.allowed",
        { step_id: "s1", allowed: false, reason: "blocked_by_policy" },
        { trace_id: "trc_run_a" },
      ),
      STEP_IDS,
    );
    expect(blocked.steps["s1"]).toEqual({
      status: "blocked",
      reason: "blocked_by_policy",
    });
  });

  it("keeps status when allowed=true but records reason for tooltip", () => {
    const seeded = applyEvent(
      pendingSnapshot(STEP_IDS),
      ev("plan.run.started", {}, { trace_id: "trc_run_a" }),
      STEP_IDS,
    );
    const requested = applyEvent(
      seeded,
      ev(
        "plan.step.requested",
        { step_id: "s1" },
        { trace_id: "trc_run_a" },
      ),
      STEP_IDS,
    );
    const allowed = applyEvent(
      requested,
      ev(
        "plan.step.allowed",
        { step_id: "s1", allowed: true, reason: "executed" },
        { trace_id: "trc_run_a" },
      ),
      STEP_IDS,
    );
    expect(allowed.steps["s1"]?.status).toBe("requested");
    expect(allowed.steps["s1"]?.reason).toBe("executed");
  });
});

describe("applyEvent · plan.step.completed", () => {
  function seedRun(): ReturnType<typeof applyEvent> {
    return applyEvent(
      pendingSnapshot(STEP_IDS),
      ev("plan.run.started", {}, { trace_id: "trc_run_a" }),
      STEP_IDS,
    );
  }

  it("ok=true → status=ok with took_ms", () => {
    const r = applyEvent(
      seedRun(),
      ev(
        "plan.step.completed",
        { step_id: "s1", ok: true, took_ms: 12.345 },
        { trace_id: "trc_run_a" },
      ),
      STEP_IDS,
    );
    expect(r.steps["s1"]).toMatchObject({ status: "ok", took_ms: 12.345 });
  });

  it("ok=false (no skip / no block) → status=failed; carries error", () => {
    const r = applyEvent(
      seedRun(),
      ev(
        "plan.step.completed",
        { step_id: "s1", ok: false, error: "boom", took_ms: 4 },
        { trace_id: "trc_run_a" },
      ),
      STEP_IDS,
    );
    expect(r.steps["s1"]).toMatchObject({
      status: "failed",
      error: "boom",
      took_ms: 4,
    });
  });

  it("blocked=true wins over ok=false", () => {
    const r = applyEvent(
      seedRun(),
      ev(
        "plan.step.completed",
        { step_id: "s1", ok: false, blocked: true, took_ms: 0 },
        { trace_id: "trc_run_a" },
      ),
      STEP_IDS,
    );
    expect(r.steps["s1"]?.status).toBe("blocked");
  });

  it("skipped=true wins over ok / blocked", () => {
    const r = applyEvent(
      seedRun(),
      ev(
        "plan.step.completed",
        {
          step_id: "s1",
          skipped: true,
          ok: false,
          blocked: true,
          took_ms: 0,
        },
        { trace_id: "trc_run_a" },
      ),
      STEP_IDS,
    );
    expect(r.steps["s1"]?.status).toBe("skipped");
  });

  it("non-numeric took_ms falls back to undefined (no NaN poisoning)", () => {
    const r = applyEvent(
      seedRun(),
      ev(
        "plan.step.completed",
        { step_id: "s1", ok: true, took_ms: "fast" },
        { trace_id: "trc_run_a" },
      ),
      STEP_IDS,
    );
    expect(r.steps["s1"]?.took_ms).toBeUndefined();
  });
});

describe("snapshotInFlight", () => {
  it("true while at least one step is requested", () => {
    const seeded = applyEvent(
      pendingSnapshot(STEP_IDS),
      ev("plan.run.started", {}, { trace_id: "trc_run_a" }),
      STEP_IDS,
    );
    const mid = applyEvent(
      seeded,
      ev(
        "plan.step.requested",
        { step_id: "s1" },
        { trace_id: "trc_run_a" },
      ),
      STEP_IDS,
    );
    expect(snapshotInFlight(mid)).toBe(true);
  });

  it("false once every step is terminal", () => {
    let snap = applyEvent(
      pendingSnapshot(["s1"]),
      ev("plan.run.started", {}, { trace_id: "trc_run_a" }),
      ["s1"],
    );
    snap = applyEvent(
      snap,
      ev(
        "plan.step.completed",
        { step_id: "s1", ok: true, took_ms: 1 },
        { trace_id: "trc_run_a" },
      ),
      ["s1"],
    );
    expect(snapshotInFlight(snap)).toBe(false);
  });

  it("false on a fresh pending snapshot (nothing has run)", () => {
    expect(snapshotInFlight(pendingSnapshot(STEP_IDS))).toBe(false);
  });
});

describe("stepStatusLabel", () => {
  it("returns a short uppercase label for every status", () => {
    expect(stepStatusLabel("pending")).toBe("PEND");
    expect(stepStatusLabel("requested")).toBe("RUN");
    expect(stepStatusLabel("blocked")).toBe("BLK");
    expect(stepStatusLabel("ok")).toBe("OK");
    expect(stepStatusLabel("failed")).toBe("ERR");
    expect(stepStatusLabel("skipped")).toBe("SKP");
  });
});
