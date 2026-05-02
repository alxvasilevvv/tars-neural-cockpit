/**
 * Pure reducer that turns a stream of `plan.step.*` SSE events into
 * a per-step live state map the cockpit panel can render directly.
 *
 * The contract mirrors `backend/core/planner/runner.py`:
 *
 *   plan.run.started      — once per run; resets the map.
 *   plan.step.requested   — fires before policy check / dispatch.
 *   plan.step.allowed     — carries `allowed` boolean + `reason`.
 *   plan.step.completed   — terminal per step. Possible shapes:
 *                            - skipped=true  → "skipped"
 *                            - blocked=true  → "blocked"
 *                            - ok=false      → "failed"
 *                            - ok=true       → "ok"
 *
 * Scoping rule: we only listen to events whose `trace_id` matches the
 * latest run trace we've seen. When a fresher `plan.run.started`
 * arrives (different trace_id), we reset and start over. This keeps
 * the panel showing the most-recent run's progress without
 * interleaving stale state from older reruns whose terminal events
 * may still be flushing.
 *
 * This module is pure / DOM-free so the Vitest sibling can pin every
 * transition without a React tree.
 */

import type { PlannerEvent } from "@/lib/planner";

export type StepLiveStatus =
  | "pending"
  | "requested"
  | "blocked"
  | "ok"
  | "failed"
  | "skipped";

export interface StepLiveState {
  status: StepLiveStatus;
  /** Last known dispatch latency. */
  took_ms?: number;
  /** Failure / block reason, when relevant. */
  error?: string | null;
  /** Why the policy gate blocked or allowed. */
  reason?: string;
  /** True when this step ran in parallel with siblings. */
  parallel?: boolean;
}

export interface StepLiveSnapshot {
  /** Trace id of the run we're scoped to (null = no run seen yet). */
  trace_id: string | null;
  /** step_id → live state. */
  steps: Record<string, StepLiveState>;
}

export const EMPTY_SNAPSHOT: StepLiveSnapshot = {
  trace_id: null,
  steps: {},
};

/**
 * Build an initial pending snapshot for the given step ids. Used by
 * the panel to seed the map before any SSE events arrive.
 */
export function pendingSnapshot(stepIds: readonly string[]): StepLiveSnapshot {
  const steps: Record<string, StepLiveState> = {};
  for (const id of stepIds) {
    steps[id] = { status: "pending" };
  }
  return { trace_id: null, steps };
}

/**
 * Apply a single SSE event to the snapshot. Returns the same object
 * (===-equal) when the event is irrelevant — lets React skip renders.
 */
export function applyEvent(
  snapshot: StepLiveSnapshot,
  event: PlannerEvent,
  knownStepIds: readonly string[],
): StepLiveSnapshot {
  if (event.kind === "plan.run.started") {
    return _onRunStarted(snapshot, event, knownStepIds);
  }

  // Scoping: ignore events from a different run trace than the one
  // we've locked onto (unless we haven't locked onto anything yet,
  // in which case the next `plan.run.started` will set the trace).
  if (snapshot.trace_id !== null && event.trace_id !== snapshot.trace_id) {
    return snapshot;
  }

  const stepId = (event.payload as { step_id?: string }).step_id;
  if (!stepId) return snapshot;

  switch (event.kind) {
    case "plan.step.requested":
      return _setStep(snapshot, stepId, {
        status: "requested",
        parallel: Boolean(
          (event.payload as { parallel?: unknown }).parallel,
        ),
      });

    case "plan.step.allowed": {
      const allowed = Boolean(
        (event.payload as { allowed?: unknown }).allowed,
      );
      const reason = (event.payload as { reason?: string }).reason;
      // If the gate blocked the step we surface it now; the
      // forthcoming plan.step.completed will confirm with blocked=true
      // but rendering "blocked" instantly feels more responsive.
      if (!allowed) {
        return _setStep(snapshot, stepId, {
          status: "blocked",
          reason,
        });
      }
      // Allowed → keep "requested" (no UI change) but record the reason
      // so the tooltip can show the gate decision text.
      return _patchStep(snapshot, stepId, { reason });
    }

    case "plan.step.completed":
      return _onStepCompleted(snapshot, stepId, event.payload as Record<string, unknown>);

    default:
      return snapshot;
  }
}

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

function _onRunStarted(
  snapshot: StepLiveSnapshot,
  event: PlannerEvent,
  knownStepIds: readonly string[],
): StepLiveSnapshot {
  const newTrace = event.trace_id ?? null;
  // Same trace as last time → no-op (prevents spurious resets when
  // SSE re-delivers the same start frame after a Last-Event-ID reconnect).
  if (snapshot.trace_id !== null && newTrace === snapshot.trace_id) {
    return snapshot;
  }
  return {
    trace_id: newTrace,
    steps: pendingSnapshot(knownStepIds).steps,
  };
}

function _onStepCompleted(
  snapshot: StepLiveSnapshot,
  stepId: string,
  payload: Record<string, unknown>,
): StepLiveSnapshot {
  const skipped = Boolean(payload.skipped);
  const blocked = Boolean(payload.blocked);
  const ok = Boolean(payload.ok);
  const took_ms_raw = payload.took_ms;
  const took_ms =
    typeof took_ms_raw === "number" && Number.isFinite(took_ms_raw)
      ? took_ms_raw
      : undefined;
  const error =
    typeof payload.error === "string" || payload.error === null
      ? (payload.error as string | null)
      : undefined;
  const parallel = Boolean(payload.parallel);

  let status: StepLiveStatus;
  if (skipped) status = "skipped";
  else if (blocked) status = "blocked";
  else if (!ok) status = "failed";
  else status = "ok";

  return _setStep(snapshot, stepId, {
    status,
    took_ms,
    error: error ?? undefined,
    parallel,
  });
}

function _setStep(
  snapshot: StepLiveSnapshot,
  stepId: string,
  next: StepLiveState,
): StepLiveSnapshot {
  return {
    trace_id: snapshot.trace_id,
    steps: { ...snapshot.steps, [stepId]: next },
  };
}

function _patchStep(
  snapshot: StepLiveSnapshot,
  stepId: string,
  patch: Partial<StepLiveState>,
): StepLiveSnapshot {
  const existing = snapshot.steps[stepId] ?? { status: "pending" };
  return {
    trace_id: snapshot.trace_id,
    steps: {
      ...snapshot.steps,
      [stepId]: { ...existing, ...patch },
    },
  };
}

/**
 * Format a step status to a short uppercase label for badges.
 * Symmetric with `statusTone` in PlanFullPanel — reused there.
 */
export function stepStatusLabel(status: StepLiveStatus): string {
  switch (status) {
    case "pending":
      return "PEND";
    case "requested":
      return "RUN";
    case "blocked":
      return "BLK";
    case "ok":
      return "OK";
    case "failed":
      return "ERR";
    case "skipped":
      return "SKP";
  }
}

/** Returns true when the snapshot still has any step actively progressing. */
export function snapshotInFlight(snapshot: StepLiveSnapshot): boolean {
  return Object.values(snapshot.steps).some(
    (s) => s.status === "requested",
  );
}
