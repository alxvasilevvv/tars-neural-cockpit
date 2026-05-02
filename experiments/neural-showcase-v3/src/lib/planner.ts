/**
 * Typed client for the TARS planner backend.
 *
 * Mirrors the contracts in `web_extras/routers/planner.py`:
 *
 * - HTTP: synthesize / list / show / runs / **full** / status / run /
 *   abort / clone / **rerun** / delete.
 * - SSE:  GET /api/planner/events with optional plan_id / thread_id
 *   filters and `Last-Event-ID` resume.
 *
 * The cockpit's plan-detail drawer can hit `fetchFullPlan(planId)` on
 * open and render everything (header, runs list, billing pill) from
 * one round-trip; the live stream then fans incremental updates back
 * in via {@link subscribePlannerEvents}.
 *
 * Notes on null cost:
 *
 * - `usage.cost_usd` is `null` when no priced model fired during a run.
 *   Render "n/a" in that case — never "$0.00", which would lie about
 *   pricing.
 * - Same rule applies to `usage_lifetime.cost_usd` on the /full envelope.
 */

import { API_BASE } from "@/lib/api";

// ---------------------------------------------------------------------------
// Shared shapes
// ---------------------------------------------------------------------------

export type PlanStatus =
  | "proposed"
  | "approved"
  | "rejected"
  | "running"
  | "completed"
  | "aborted";

export type PolicyMode = "autopilot" | "confirm" | "dry_run";

/** Per-run usage rollup as it travels on terminal events / PlanRun. */
export interface PlanUsage {
  calls: number;
  tokens_in: number;
  tokens_out: number;
  /** USD spent. `null` when no priced model fired — render "n/a". */
  cost_usd: number | null;
  latency_ms_total: number;
  has_priced_models: boolean;
}

/** Lifetime aggregate rollup as it travels on the /full envelope. */
export interface PlanUsageLifetime extends PlanUsage {
  /** Number of reconstructed runs that contributed to the rollup. */
  runs_aggregated: number;
}

export interface PlanStep {
  id: string;
  action: string;
  args?: Record<string, unknown>;
  when?: string | null;
  on_error?: "continue" | "stop";
  on_block?: "continue" | "stop";
  store_as?: string | null;
  parallel?: boolean;
}

export interface Plan {
  id: string;
  goal: string;
  steps: PlanStep[];
  status: PlanStatus;
  rationale: string;
  model: string;
  pack_slug: string | null;
  playbook_id: string | null;
  thread_id: string | null;
  trace_id: string | null;
  created_at: number;
  updated_at: number;
  estimated_cost_usd?: number | null;
  error?: string | null;
}

export interface RunStep {
  id: string;
  action: string;
  ok: boolean;
  skipped: boolean;
  blocked: boolean;
  took_ms: number;
  error: string | null;
  allowed: boolean | null;
  allow_reason: string | null;
  parallel: boolean;
}

export interface PlanRun {
  plan_id: string;
  started_at: number;
  completed_at: number | null;
  status: "running" | "completed" | "aborted";
  /** Per-run trace; lets the cockpit deep-link into the trace lane. */
  trace_id: string | null;
  /** Plan's birth trace; lets the cockpit group sibling runs. */
  parent_trace_id: string | null;
  mode: string | null;
  step_count: number | null;
  steps_run: number;
  steps_blocked: number;
  steps_failed: number;
  abort_reason: string | null;
  abort_requested: boolean;
  exception: string | null;
  took_ms: number | null;
  usage: PlanUsage;
  steps: RunStep[];
}

// ---------------------------------------------------------------------------
// Endpoint envelopes
// ---------------------------------------------------------------------------

export interface ListPlansResponse {
  ok: boolean;
  count: number;
  plans: Plan[];
}

export interface PlanRunsResponse {
  ok: boolean;
  plan_id: string;
  count: number;
  in_flight: number;
  runs: PlanRun[];
}

export interface PlanFullResponse {
  ok: boolean;
  plan_id: string;
  plan: Plan;
  runs: {
    count: number;
    in_flight: number;
    items: PlanRun[];
  };
  usage_lifetime: PlanUsageLifetime;
}

export interface RerunResponse {
  ok: boolean;
  plan: Plan;
  source_plan_id: string;
  auto_approved: boolean;
  auto_run: boolean;
  /** Run result envelope (status / steps / usage); null when --run was not requested. */
  run_result: {
    plan_id: string;
    status: "completed" | "aborted";
    trace_id: string;
    parent_trace_id: string | null;
    mode: string;
    steps: RunStep[];
    context: Record<string, unknown>;
    abort_reason: string | null;
    usage: PlanUsage;
    ok: boolean;
  } | null;
}

// ---------------------------------------------------------------------------
// HTTP API
// ---------------------------------------------------------------------------

interface RequestOpts {
  /** `x-meeet-trace-id` — propagate caller trace into backend trace_scope. */
  traceId?: string;
  /** `x-tars-thread-id` — bind plans / clones to the current chat thread. */
  threadId?: string;
  /** `x-tars-policy-mode` — override the policy gate per-call. */
  mode?: PolicyMode;
}

function buildHeaders(opts: RequestOpts = {}, json = false): Record<string, string> {
  const headers: Record<string, string> = {};
  if (json) headers["content-type"] = "application/json";
  if (opts.traceId) headers["x-meeet-trace-id"] = opts.traceId;
  if (opts.threadId) headers["x-tars-thread-id"] = opts.threadId;
  if (opts.mode) headers["x-tars-policy-mode"] = opts.mode;
  return headers;
}

async function asJson<T>(r: Response): Promise<T> {
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`HTTP ${r.status} · ${text}`);
  }
  return (await r.json()) as T;
}

export async function fetchFullPlan(
  planId: string,
  opts: RequestOpts & { limit?: number } = {},
): Promise<PlanFullResponse> {
  const qs =
    typeof opts.limit === "number"
      ? `?limit=${encodeURIComponent(String(opts.limit))}`
      : "";
  const r = await fetch(
    `${API_BASE}/api/planner/${encodeURIComponent(planId)}/full${qs}`,
    { headers: buildHeaders(opts) },
  );
  return asJson<PlanFullResponse>(r);
}

export async function listPlans(
  opts: RequestOpts & { status?: PlanStatus; threadId?: string; limit?: number } = {},
): Promise<ListPlansResponse> {
  const params = new URLSearchParams();
  if (opts.status) params.set("status", opts.status);
  if (opts.threadId) params.set("thread_id", opts.threadId);
  if (opts.limit !== undefined) params.set("limit", String(opts.limit));
  const qs = params.toString();
  const url = `${API_BASE}/api/planner${qs ? `?${qs}` : ""}`;
  const r = await fetch(url, { headers: buildHeaders(opts) });
  return asJson<ListPlansResponse>(r);
}

export async function listPlanRuns(
  planId: string,
  opts: RequestOpts & { limit?: number } = {},
): Promise<PlanRunsResponse> {
  const qs =
    typeof opts.limit === "number"
      ? `?limit=${encodeURIComponent(String(opts.limit))}`
      : "";
  const r = await fetch(
    `${API_BASE}/api/planner/${encodeURIComponent(planId)}/runs${qs}`,
    { headers: buildHeaders(opts) },
  );
  return asJson<PlanRunsResponse>(r);
}

export async function rerunPlan(
  planId: string,
  body: {
    thread_id?: string;
    goal_override?: string;
    mode?: PolicyMode;
  } = {},
  opts: RequestOpts = {},
): Promise<RerunResponse> {
  const r = await fetch(
    `${API_BASE}/api/planner/${encodeURIComponent(planId)}/rerun`,
    {
      method: "POST",
      headers: buildHeaders(opts, true),
      body: JSON.stringify(body),
    },
  );
  return asJson<RerunResponse>(r);
}

export async function abortPlan(
  planId: string,
  opts: RequestOpts = {},
): Promise<{ ok: boolean; plan_id: string; flipped: boolean }> {
  const r = await fetch(
    `${API_BASE}/api/planner/${encodeURIComponent(planId)}/abort`,
    { method: "POST", headers: buildHeaders(opts) },
  );
  return asJson<{ ok: boolean; plan_id: string; flipped: boolean }>(r);
}

// ---------------------------------------------------------------------------
// SSE: GET /api/planner/events
// ---------------------------------------------------------------------------

/** All event kinds the planner SSE stream may emit. */
export type PlannerEventKind =
  | "plan.proposed"
  | "planner.synthesis.completed"
  | "planner.synthesis.failed"
  | "planner.approved"
  | "planner.rejected"
  | "planner.cloned"
  | "planner.deleted"
  | "plan.run.started"
  | "plan.step.requested"
  | "plan.step.allowed"
  | "plan.step.completed"
  | "plan.run.usage"
  | "plan.completed"
  | "plan.aborted"
  | "plan.abort.requested";

/**
 * One SSE frame as emitted by the producer in
 * `web_extras/routers/planner.py::_planner_sse_producer`. The `id`
 * field is the meeet store's row id and should be persisted as the
 * cursor for `Last-Event-ID` resume.
 */
export interface PlannerEvent {
  id: number;
  kind: PlannerEventKind;
  ts: number;
  trace_id: string | null;
  payload: Record<string, unknown>;
}

export interface PlannerSubscribeOptions {
  /** Filter to events whose payload `plan_id` matches. */
  planId?: string;
  /** Filter to events whose payload `thread_id` matches. */
  threadId?: string;
  /** Last seen meeet row id; sets `?after_id=` for resume. */
  afterId?: number;
  /** Backend poll interval seconds; passed through as query. */
  pollIntervalS?: number;
  /** Backend max stream duration seconds; passed through as query. */
  maxDurationS?: number;
}

export interface PlannerSubscribeHandlers {
  onEvent?: (e: PlannerEvent) => void;
  onError?: (err: Event) => void;
  onOpen?: () => void;
}

export function subscribePlannerEvents(
  opts: PlannerSubscribeOptions,
  handlers: PlannerSubscribeHandlers,
): () => void {
  const params = new URLSearchParams();
  if (opts.planId) params.set("plan_id", opts.planId);
  if (opts.threadId) params.set("thread_id", opts.threadId);
  if (typeof opts.afterId === "number") {
    params.set("after_id", String(opts.afterId));
  }
  if (typeof opts.pollIntervalS === "number") {
    params.set("poll_interval_s", String(opts.pollIntervalS));
  }
  if (typeof opts.maxDurationS === "number") {
    params.set("max_duration_s", String(opts.maxDurationS));
  }
  const qs = params.toString();
  const url = `${API_BASE}/api/planner/events${qs ? `?${qs}` : ""}`;
  const es = new EventSource(url);
  es.onopen = () => handlers.onOpen?.();
  es.onerror = (err) => handlers.onError?.(err);
  es.onmessage = (msg) => {
    try {
      const data = JSON.parse(msg.data) as PlannerEvent;
      handlers.onEvent?.(data);
    } catch {
      // Bad frame, ignore — the next tick will resync.
    }
  };
  return () => es.close();
}

/**
 * Helper: format a `cost_usd` value the way the cockpit's billing
 * pills are supposed to render it. `null` → "n/a"; `0` and any other
 * number → `$X.XXXX` with four decimals so micro-costs are visible.
 */
export function formatCostUSD(cost: number | null | undefined): string {
  if (cost === null || cost === undefined) return "n/a";
  return `$${cost.toFixed(4)}`;
}
