/**
 * PlanFullPanel — drawer/panel that hydrates from
 * `GET /api/planner/{plan_id}/full` and stays live via the planner SSE
 * stream. Built on top of `lib/planner.ts` — does not speak HTTP
 * directly, so URL/header drift is caught by the client's Vitest
 * contract.
 *
 * Render anatomy (top → bottom):
 *
 *   - Plan header: pack · status pill · goal (one-liner) ·
 *     trace_id · created_at.
 *   - Step list: id · action · args (collapsed JSON one-liner).
 *   - Run history (newest first): trace_id · status pill ·
 *     started_at · took_ms · per-run usage pills (calls / tokens /
 *     $cost · `n/a` honoured).
 *   - Lifetime usage rollup: total calls / tokens / cost across
 *     `runs_aggregated` runs.
 *   - Action row: Rerun (POST /rerun, refetch on success) · Abort
 *     (POST /abort, refetch on success) · Close.
 *
 * Live updates: while open, subscribes to
 * `subscribePlannerEvents({ planId })` and refetches `/full` on any
 * `plan.run.usage` / `plan.completed` / `plan.aborted` /
 * `plan.run.started` event. The stream's `id` cursor is held in
 * `lastEventIdRef` so a reconnect (which the cockpit doesn't trigger
 * here yet, but the client supports) can resume cleanly.
 *
 * The pure helpers (`statusTone`, `formatLatencyMs`,
 * `formatStartedAt`, `formatRunSummary`, `formatLifetimeSummary`,
 * `summariseStep`) are exported so the Vitest sibling can pin
 * formatting without a DOM.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Play, RefreshCw, X } from "lucide-react";

import {
  abortPlan,
  fetchFullPlan,
  formatCostUSD,
  rerunPlan,
  subscribePlannerEvents,
  type Plan,
  type PlanFullResponse,
  type PlanRun,
  type PlanStep,
  type PlanStatus,
  type PlanUsage,
  type PlanUsageLifetime,
  type PolicyMode,
  type PlannerEvent,
} from "@/lib/planner";
import {
  EMPTY_SNAPSHOT,
  applyEvent as applyStepEvent,
  pendingSnapshot,
  snapshotInFlight,
  stepStatusLabel,
  type StepLiveSnapshot,
  type StepLiveState,
  type StepLiveStatus,
} from "@/lib/plannerSteps";

// ---------------------------------------------------------------------------
// Pure helpers (exported for Vitest)
// ---------------------------------------------------------------------------

export type StatusTone = "muted" | "accent" | "success" | "alert" | "warning";

/** Map a plan / run status to a render tone. */
export function statusTone(status: PlanStatus | PlanRun["status"]): StatusTone {
  switch (status) {
    case "proposed":
      return "muted";
    case "approved":
      return "accent";
    case "running":
      return "warning";
    case "completed":
      return "success";
    case "aborted":
    case "rejected":
      return "alert";
    default:
      return "muted";
  }
}

/** "12.3ms" / "1.2s" / "n/a" — never NaN, never negative. */
export function formatLatencyMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return "n/a";
  if (ms < 0) return "n/a";
  if (ms < 1000) return `${ms.toFixed(1)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

/** Compact ISO-style timestamp in UTC: "2026-05-01 12:34:56Z". */
export function formatStartedAt(unix: number | null | undefined): string {
  if (unix === null || unix === undefined || Number.isNaN(unix)) return "—";
  const d = new Date(unix * 1000);
  if (Number.isNaN(d.getTime())) return "—";
  const iso = d.toISOString();
  return `${iso.slice(0, 10)} ${iso.slice(11, 19)}Z`;
}

/** "calls=N · tokens=A+B · cost=…" — usage pill text for one run. */
export function formatRunSummary(usage: PlanUsage): string {
  return `calls=${usage.calls} · tokens=${usage.tokens_in}+${usage.tokens_out} · cost=${formatCostUSD(usage.cost_usd)}`;
}

/**
 * Lifetime rollup line: includes runs_aggregated count so the
 * cockpit can render "across N runs · …" naturally.
 */
export function formatLifetimeSummary(u: PlanUsageLifetime): string {
  return `across ${u.runs_aggregated} run${u.runs_aggregated === 1 ? "" : "s"} · calls=${u.calls} · tokens=${u.tokens_in}+${u.tokens_out} · cost=${formatCostUSD(u.cost_usd)}`;
}

/** "step.id · action · args(json)" — empty args render as "{}". */
export function summariseStep(step: PlanStep): string {
  const args = step.args ? JSON.stringify(step.args) : "{}";
  return `${step.id} · ${step.action} · ${args}`;
}

/** SSE event kinds that should trigger a `/full` refetch. */
export const REFETCH_KINDS = new Set([
  "plan.run.started",
  "plan.run.usage",
  "plan.completed",
  "plan.aborted",
  "plan.abort.requested",
  "planner.cloned",
]);

/** Returns true if the SSE event id is newer than the cursor. */
export function shouldAdvanceCursor(
  cursor: number | null,
  eventId: number,
): boolean {
  if (cursor === null) return true;
  return eventId > cursor;
}

// ---------------------------------------------------------------------------
// Tone → tailwind classes (kept in sync with cockpit's StatusLozenge)
// ---------------------------------------------------------------------------

const TONE_CLASS: Record<StatusTone, string> = {
  muted: "border-line text-ink-3",
  accent: "border-line-strong text-accent",
  success: "border-line-strong text-[color:var(--color-success)]",
  alert: "border-alert/60 text-alert",
  warning: "border-line-strong text-[color:var(--brand-amber,#FBBF24)]",
};

function StatusPill({ status }: { status: PlanStatus | PlanRun["status"] }) {
  const tone = statusTone(status);
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 font-mono-tech text-[9.5px] uppercase tracking-[2px] ${TONE_CLASS[tone]}`}
    >
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface PlanFullPanelProps {
  /** Plan to show. When null, the panel renders nothing. */
  planId: string | null;
  onClose?: () => void;
  /** Override policy mode for rerun / abort. */
  mode?: PolicyMode;
  /** Optional thread id to bind reruns to a specific chat thread. */
  threadId?: string;
  /** Test seam: inject a synthetic /full payload (skips the fetch). */
  initialData?: PlanFullResponse;
  /** Test seam: disable SSE wiring (used by storybook / unit tests). */
  disableLive?: boolean;
}

export function PlanFullPanel(props: PlanFullPanelProps) {
  const { planId, onClose, mode, threadId, initialData, disableLive } = props;

  const [data, setData] = useState<PlanFullResponse | null>(initialData ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rerunning, setRerunning] = useState(false);
  const [aborting, setAborting] = useState(false);
  const [stepSnapshot, setStepSnapshot] =
    useState<StepLiveSnapshot>(EMPTY_SNAPSHOT);
  const lastEventIdRef = useRef<number | null>(null);

  const stepIds = useMemo(
    () => (data?.plan.steps ?? []).map((s) => s.id),
    [data?.plan.steps],
  );

  // Whenever the plan envelope arrives (or its step list changes), seed
  // the live snapshot to "all pending" so the rows render immediately
  // instead of waiting for the first SSE frame.
  useEffect(() => {
    if (!stepIds.length) {
      setStepSnapshot(EMPTY_SNAPSHOT);
      return;
    }
    setStepSnapshot((prev) =>
      prev.trace_id === null ? pendingSnapshot(stepIds) : prev,
    );
  }, [stepIds]);

  const refetch = useCallback(async () => {
    if (!planId) return;
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchFullPlan(planId, { mode, threadId });
      setData(payload);
    } catch (e) {
      setError(String((e as Error)?.message ?? e));
    } finally {
      setLoading(false);
    }
  }, [planId, mode, threadId]);

  // Initial load when planId changes (or on first mount with no initialData).
  useEffect(() => {
    if (!planId) {
      setData(null);
      return;
    }
    if (initialData && initialData.plan_id === planId) {
      setData(initialData);
      return;
    }
    void refetch();
    // We intentionally exclude `initialData` from deps — it's a one-shot seed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planId, refetch]);

  // Live updates — refetch on lifecycle events, and feed every
  // step.* event through the per-step reducer so the rows tick
  // without an extra round-trip.
  useEffect(() => {
    if (!planId || disableLive) return;
    const cleanup = subscribePlannerEvents(
      { planId, afterId: lastEventIdRef.current ?? undefined },
      {
        onEvent: (e: PlannerEvent) => {
          if (shouldAdvanceCursor(lastEventIdRef.current, e.id)) {
            lastEventIdRef.current = e.id;
          }
          // Step-state reducer first — pure, cheap, no fetch.
          if (
            e.kind === "plan.run.started" ||
            e.kind === "plan.step.requested" ||
            e.kind === "plan.step.allowed" ||
            e.kind === "plan.step.completed"
          ) {
            setStepSnapshot((prev) => applyStepEvent(prev, e, stepIds));
          }
          if (REFETCH_KINDS.has(e.kind)) {
            void refetch();
          }
        },
      },
    );
    return cleanup;
  }, [planId, disableLive, refetch, stepIds]);

  const onRerun = useCallback(async () => {
    if (!planId) return;
    setRerunning(true);
    setError(null);
    try {
      await rerunPlan(planId, { mode, thread_id: threadId }, { mode, threadId });
      await refetch();
    } catch (e) {
      setError(String((e as Error)?.message ?? e));
    } finally {
      setRerunning(false);
    }
  }, [planId, mode, threadId, refetch]);

  const onAbort = useCallback(async () => {
    if (!planId) return;
    setAborting(true);
    setError(null);
    try {
      await abortPlan(planId, { mode, threadId });
      await refetch();
    } catch (e) {
      setError(String((e as Error)?.message ?? e));
    } finally {
      setAborting(false);
    }
  }, [planId, mode, threadId, refetch]);

  if (!planId) return null;

  return (
    <aside className="relative grid gap-5 overflow-hidden rounded-[14px] border border-line bg-bg-1 p-5 md:p-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="mb-1 font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
            plan //{" "}
            <span className="text-ink">{planId}</span>
            {data?.plan.pack_slug && (
              <>
                {" · "}
                <span className="text-accent">{data.plan.pack_slug}</span>
              </>
            )}
          </div>
          {data && (
            <h3 className="truncate font-display text-[15px] font-medium uppercase tracking-[0.02em] text-ink">
              {data.plan.goal}
            </h3>
          )}
        </div>
        <div className="flex items-center gap-2">
          {data && <StatusPill status={data.plan.status} />}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close plan panel"
              className="rounded-md border border-line p-1.5 text-ink-3 transition-colors hover:border-line-strong hover:text-ink"
            >
              <X size={12} strokeWidth={1.6} />
            </button>
          )}
        </div>
      </header>

      {loading && !data && (
        <div className="flex items-center gap-2 font-mono-tech text-[11px] text-ink-3">
          <Loader2 size={12} className="animate-spin" strokeWidth={1.6} />
          loading plan…
        </div>
      )}

      {error && (
        <div className="rounded-md border border-alert/40 bg-alert/[0.04] p-3 font-mono-tech text-[11px] text-alert">
          {error}
        </div>
      )}

      {data && <PlanBody data={data} stepSnapshot={stepSnapshot} />}

      {data && (
        <footer className="flex flex-wrap items-center gap-2 border-t border-line pt-4">
          <button
            type="button"
            disabled={rerunning || aborting}
            onClick={onRerun}
            className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-line-hot bg-accent-deep px-3 py-1.5 font-display text-[11px] uppercase tracking-[0.18em] text-accent transition-colors hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {rerunning ? (
              <Loader2 size={12} className="animate-spin" strokeWidth={1.6} />
            ) : (
              <Play size={11} strokeWidth={1.8} />
            )}
            {rerunning ? "rerunning…" : "rerun"}
          </button>
          <button
            type="button"
            disabled={rerunning || aborting || data.plan.status !== "running"}
            onClick={onAbort}
            className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-line px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-2 transition-colors hover:border-alert/60 hover:text-alert disabled:cursor-not-allowed disabled:opacity-40"
          >
            {aborting ? (
              <Loader2 size={11} className="animate-spin" strokeWidth={1.6} />
            ) : (
              <X size={11} strokeWidth={1.8} />
            )}
            abort
          </button>
          <button
            type="button"
            disabled={loading || rerunning || aborting}
            onClick={() => void refetch()}
            className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-line px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-2 transition-colors hover:border-line-strong hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Refetch plan envelope"
          >
            <RefreshCw size={11} strokeWidth={1.6} />
            refresh
          </button>
        </footer>
      )}
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Sub-renderers (no state, no fetch)
// ---------------------------------------------------------------------------

function PlanBody({
  data,
  stepSnapshot,
}: {
  data: PlanFullResponse;
  stepSnapshot: StepLiveSnapshot;
}) {
  const { plan, runs, usage_lifetime } = data;
  const inFlight = snapshotInFlight(stepSnapshot);
  return (
    <div className="grid gap-5">
      <PlanMetaRow plan={plan} />
      <Steps
        steps={plan.steps}
        snapshot={stepSnapshot}
        inFlight={inFlight}
      />
      <Runs runs={runs.items} inFlight={runs.in_flight} />
      <Lifetime usage={usage_lifetime} />
    </div>
  );
}

function PlanMetaRow({ plan }: { plan: Plan }) {
  return (
    <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 font-mono-tech text-[10.5px] tracking-[1.4px] text-ink-2">
      <span className="text-ink-3">model</span>
      <span className="text-ink">{plan.model || "—"}</span>
      <span className="text-ink-3">trace</span>
      <span className="truncate text-ink">{plan.trace_id ?? "—"}</span>
      <span className="text-ink-3">created</span>
      <span className="text-ink">{formatStartedAt(plan.created_at)}</span>
      {plan.error && (
        <>
          <span className="text-alert">error</span>
          <span className="text-alert">{plan.error}</span>
        </>
      )}
    </div>
  );
}

/** Pure helper: classes for the per-step status badge. */
const STEP_STATUS_CLASS: Record<StepLiveStatus, string> = {
  pending: "border-line text-ink-3",
  requested:
    "border-line-strong text-[color:var(--brand-amber,#FBBF24)] animate-pulse",
  blocked: "border-alert/60 text-alert",
  ok: "border-line-strong text-[color:var(--color-success)]",
  failed: "border-alert/60 text-alert",
  skipped: "border-line text-ink-3 opacity-60",
};

function StepBadge({ state }: { state: StepLiveState }) {
  return (
    <span
      title={state.reason ?? state.error ?? undefined}
      className={`inline-flex shrink-0 items-center rounded-md border px-1.5 py-0.5 font-mono-tech text-[9px] uppercase tracking-[1.6px] ${
        STEP_STATUS_CLASS[state.status]
      }`}
    >
      {stepStatusLabel(state.status)}
    </span>
  );
}

function Steps({
  steps,
  snapshot,
  inFlight,
}: {
  steps: PlanStep[];
  snapshot: StepLiveSnapshot;
  inFlight: boolean;
}) {
  return (
    <section>
      <div className="mb-1.5 flex items-center justify-between font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
        <span>steps · {steps.length}</span>
        {inFlight && (
          <span className="text-[color:var(--brand-amber,#FBBF24)]">
            live · run in flight
          </span>
        )}
      </div>
      <ol className="grid gap-1 font-mono-tech text-[11px] tracking-[0.6px] text-ink-2">
        {steps.length === 0 && <li className="text-ink-3">no steps</li>}
        {steps.map((s) => {
          const state = snapshot.steps[s.id] ?? { status: "pending" as const };
          return (
            <li
              key={s.id}
              className="grid grid-cols-[auto_60px_1fr_auto] items-center gap-2"
            >
              <StepBadge state={state} />
              <span className="truncate text-ink-3">{s.id}</span>
              <span className="truncate text-ink">{summariseStep(s)}</span>
              {typeof state.took_ms === "number" && (
                <span className="text-ink-3 tabular-nums">
                  {formatLatencyMs(state.took_ms)}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function Runs({ runs, inFlight }: { runs: PlanRun[]; inFlight: number }) {
  return (
    <section>
      <div className="mb-1.5 flex items-center justify-between font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
        <span>runs · {runs.length}</span>
        {inFlight > 0 && (
          <span className="text-[color:var(--brand-amber,#FBBF24)]">
            in-flight · {inFlight}
          </span>
        )}
      </div>
      <ol className="grid gap-2">
        {runs.length === 0 && (
          <li className="font-mono-tech text-[11px] text-ink-3">no runs yet</li>
        )}
        {runs.map((r) => (
          <li
            key={`${r.trace_id ?? "no-trace"}-${r.started_at}`}
            className="rounded-md border border-line bg-bg-2/30 p-2.5"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="truncate font-mono-tech text-[10.5px] tracking-[1.4px] text-ink">
                {r.trace_id ?? "—"}
              </span>
              <StatusPill status={r.status} />
            </div>
            <div className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 font-mono-tech text-[10.5px] tracking-[1.4px] text-ink-2">
              <span className="text-ink-3">started</span>
              <span>{formatStartedAt(r.started_at)}</span>
              <span className="text-ink-3">took</span>
              <span>{formatLatencyMs(r.took_ms)}</span>
              <span className="text-ink-3">usage</span>
              <span>{formatRunSummary(r.usage)}</span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Lifetime({ usage }: { usage: PlanUsageLifetime }) {
  return (
    <section className="rounded-md border border-line bg-bg-2/40 p-3">
      <div className="mb-1 font-mono-tech text-[9.5px] uppercase tracking-[2.6px] text-ink-2">
        lifetime usage
      </div>
      <div className="font-mono-tech text-[11px] tracking-[0.6px] text-ink">
        {formatLifetimeSummary(usage)}
      </div>
    </section>
  );
}

// Re-export for convenience.
export { formatCostUSD };
