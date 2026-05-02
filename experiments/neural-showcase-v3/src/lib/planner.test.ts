/**
 * Contract tests for `lib/planner.ts`.
 *
 * The cockpit talks to FastAPI routes in `web_extras/routers/planner.py`.
 * The Python side already has end-to-end pytest coverage; this file
 * pins the TS-side wire shape so a regression there can't drift the
 * cockpit out of sync without CI complaining.
 *
 * Specifically:
 *
 * 1. Each helper hits the documented URL with the right method and
 *    headers (no accidental drift in path encoding, query params, or
 *    header names).
 * 2. The response envelope deserialises 1:1 into our typed shape
 *    (`PlanFullResponse`, `PlanRunsResponse`, `RerunResponse`).
 * 3. The SSE subscriber wires `EventSource` correctly and parses the
 *    server's JSON frames into typed events.
 * 4. `formatCostUSD` renders `null` as "n/a" and a number with four
 *    decimals — the contract the cockpit's billing pills depend on.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  abortPlan,
  fetchFullPlan,
  formatCostUSD,
  listPlanRuns,
  listPlans,
  rerunPlan,
  subscribePlannerEvents,
  type PlanEvent,
  type PlanFullResponse,
  type PlannerEvent,
  type PlanRunsResponse,
  type RerunResponse,
} from "./planner";

import { API_BASE } from "./api";

// ---------------------------------------------------------------------------
// fetch mocking utilities
// ---------------------------------------------------------------------------

interface RecordedCall {
  url: string;
  init: RequestInit | undefined;
}

let recordedCalls: RecordedCall[];
let fetchMock: ReturnType<typeof vi.fn>;

function mockFetchOnce(body: unknown, init: ResponseInit = { status: 200 }): void {
  fetchMock.mockImplementationOnce((url: RequestInfo | URL, init2?: RequestInit) => {
    recordedCalls.push({ url: String(url), init: init2 });
    return Promise.resolve(
      new Response(JSON.stringify(body), {
        ...init,
        headers: { "content-type": "application/json", ...(init.headers ?? {}) },
      }),
    );
  });
}

beforeEach(() => {
  recordedCalls = [];
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// fetchFullPlan
// ---------------------------------------------------------------------------

describe("fetchFullPlan", () => {
  it("hits /api/planner/{id}/full and round-trips the envelope", async () => {
    const fixture: PlanFullResponse = {
      ok: true,
      plan_id: "pln_abc",
      plan: {
        id: "pln_abc",
        goal: "ship probe",
        steps: [],
        status: "completed",
        rationale: "test",
        model: "heuristic-v1",
        pack_slug: "traders",
        playbook_id: null,
        thread_id: null,
        trace_id: "trc_birth",
        created_at: 1,
        updated_at: 2,
      },
      runs: { count: 1, in_flight: 0, items: [] },
      usage_lifetime: {
        calls: 1,
        tokens_in: 10,
        tokens_out: 20,
        cost_usd: 0.0123,
        latency_ms_total: 5,
        has_priced_models: true,
        runs_aggregated: 1,
      },
    };
    mockFetchOnce(fixture);
    const out = await fetchFullPlan("pln_abc");
    expect(out).toEqual(fixture);
    expect(recordedCalls[0].url).toBe(`${API_BASE}/api/planner/pln_abc/full`);
  });

  it("appends a limit query when supplied and propagates trace header", async () => {
    mockFetchOnce({
      ok: true,
      plan_id: "pln_abc",
      plan: {} as PlanFullResponse["plan"],
      runs: { count: 0, in_flight: 0, items: [] },
      usage_lifetime: {
        calls: 0,
        tokens_in: 0,
        tokens_out: 0,
        cost_usd: null,
        latency_ms_total: 0,
        has_priced_models: false,
        runs_aggregated: 0,
      },
    });
    await fetchFullPlan("pln_abc", { limit: 50, traceId: "trc_caller" });
    expect(recordedCalls[0].url).toBe(
      `${API_BASE}/api/planner/pln_abc/full?limit=50`,
    );
    const headers = (recordedCalls[0].init?.headers ?? {}) as Record<string, string>;
    expect(headers["x-meeet-trace-id"]).toBe("trc_caller");
  });

  it("URL-encodes a plan id with slashes / spaces", async () => {
    mockFetchOnce({
      ok: true,
      plan_id: "pln/with space",
      plan: {} as PlanFullResponse["plan"],
      runs: { count: 0, in_flight: 0, items: [] },
      usage_lifetime: {
        calls: 0,
        tokens_in: 0,
        tokens_out: 0,
        cost_usd: null,
        latency_ms_total: 0,
        has_priced_models: false,
        runs_aggregated: 0,
      },
    });
    await fetchFullPlan("pln/with space");
    expect(recordedCalls[0].url).toBe(
      `${API_BASE}/api/planner/pln%2Fwith%20space/full`,
    );
  });

  it("throws on non-2xx response with the body text appended", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response("plan_not_found", { status: 404 }),
    );
    await expect(fetchFullPlan("pln_unknown")).rejects.toThrow(/HTTP 404/);
  });
});

// ---------------------------------------------------------------------------
// listPlans / listPlanRuns / abortPlan
// ---------------------------------------------------------------------------

describe("listPlans", () => {
  it("builds the query string from status / threadId / limit", async () => {
    mockFetchOnce({ ok: true, count: 0, plans: [] });
    await listPlans({ status: "approved", threadId: "thr_x", limit: 5 });
    const url = new URL(recordedCalls[0].url);
    expect(url.pathname).toBe("/api/planner");
    expect(url.searchParams.get("status")).toBe("approved");
    expect(url.searchParams.get("thread_id")).toBe("thr_x");
    expect(url.searchParams.get("limit")).toBe("5");
  });

  it("omits the query when no filters are passed", async () => {
    mockFetchOnce({ ok: true, count: 0, plans: [] });
    await listPlans();
    expect(recordedCalls[0].url).toBe(`${API_BASE}/api/planner`);
  });
});

describe("listPlanRuns", () => {
  it("hits /runs and decodes count + in_flight + runs", async () => {
    const fixture: PlanRunsResponse = {
      ok: true,
      plan_id: "pln_abc",
      count: 2,
      in_flight: 1,
      runs: [],
    };
    mockFetchOnce(fixture);
    const out = await listPlanRuns("pln_abc");
    expect(out).toEqual(fixture);
    expect(recordedCalls[0].url).toBe(
      `${API_BASE}/api/planner/pln_abc/runs`,
    );
  });
});

describe("abortPlan", () => {
  it("POSTs to /abort and propagates the policy mode header", async () => {
    mockFetchOnce({ ok: true, plan_id: "pln_abc", flipped: true });
    await abortPlan("pln_abc", { mode: "autopilot", traceId: "trc_x" });
    expect(recordedCalls[0].init?.method).toBe("POST");
    expect(recordedCalls[0].url).toBe(
      `${API_BASE}/api/planner/pln_abc/abort`,
    );
    const headers = (recordedCalls[0].init?.headers ?? {}) as Record<string, string>;
    expect(headers["x-tars-policy-mode"]).toBe("autopilot");
    expect(headers["x-meeet-trace-id"]).toBe("trc_x");
  });
});

// ---------------------------------------------------------------------------
// rerunPlan
// ---------------------------------------------------------------------------

describe("rerunPlan", () => {
  it("POSTs JSON body with thread/goal/mode and returns the typed envelope", async () => {
    const fixture: RerunResponse = {
      ok: true,
      plan: {
        id: "pln_clone",
        goal: "ship probe (rebrand)",
        steps: [],
        status: "completed",
        rationale: "rerun",
        model: "heuristic-v1",
        pack_slug: "traders",
        playbook_id: null,
        thread_id: "thr_new",
        trace_id: "trc_clone",
        created_at: 10,
        updated_at: 20,
      },
      source_plan_id: "pln_abc",
      auto_approved: true,
      auto_run: true,
      run_result: {
        plan_id: "pln_clone",
        status: "completed",
        trace_id: "trc_run",
        parent_trace_id: "trc_clone",
        mode: "autopilot",
        steps: [],
        context: {},
        abort_reason: null,
        usage: {
          calls: 1,
          tokens_in: 5,
          tokens_out: 10,
          cost_usd: 0.001,
          latency_ms_total: 4,
          has_priced_models: true,
        },
        ok: true,
      },
    };
    mockFetchOnce(fixture);
    const out = await rerunPlan(
      "pln_abc",
      { thread_id: "thr_new", goal_override: "ship probe (rebrand)" },
      { mode: "autopilot" },
    );
    expect(out).toEqual(fixture);

    const call = recordedCalls[0];
    expect(call.init?.method).toBe("POST");
    expect(call.url).toBe(`${API_BASE}/api/planner/pln_abc/rerun`);

    const headers = (call.init?.headers ?? {}) as Record<string, string>;
    expect(headers["content-type"]).toBe("application/json");
    expect(headers["x-tars-policy-mode"]).toBe("autopilot");

    expect(JSON.parse(String(call.init?.body))).toEqual({
      thread_id: "thr_new",
      goal_override: "ship probe (rebrand)",
    });
  });

  it("sends an empty body when no overrides are provided", async () => {
    mockFetchOnce({
      ok: true,
      plan: {} as RerunResponse["plan"],
      source_plan_id: "pln_abc",
      auto_approved: true,
      auto_run: true,
      run_result: null,
    });
    await rerunPlan("pln_abc");
    expect(JSON.parse(String(recordedCalls[0].init?.body))).toEqual({});
  });
});

// ---------------------------------------------------------------------------
// SSE subscriber
// ---------------------------------------------------------------------------

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  closed = false;
  onopen: (() => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  emit(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent);
  }

  emitRaw(raw: string) {
    this.onmessage?.({ data: raw } as MessageEvent);
  }

  close() {
    this.closed = true;
  }
}

describe("subscribePlannerEvents", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);
  });

  it("builds the URL with planId / threadId / afterId / poll / max query params", () => {
    const dispose = subscribePlannerEvents(
      {
        planId: "pln_abc",
        threadId: "thr_y",
        afterId: 42,
        pollIntervalS: 2,
        maxDurationS: 60,
      },
      {},
    );
    expect(FakeEventSource.instances).toHaveLength(1);
    const url = new URL(FakeEventSource.instances[0].url);
    expect(url.pathname).toBe("/api/planner/events");
    expect(url.searchParams.get("plan_id")).toBe("pln_abc");
    expect(url.searchParams.get("thread_id")).toBe("thr_y");
    expect(url.searchParams.get("after_id")).toBe("42");
    expect(url.searchParams.get("poll_interval_s")).toBe("2");
    expect(url.searchParams.get("max_duration_s")).toBe("60");
    dispose();
    expect(FakeEventSource.instances[0].closed).toBe(true);
  });

  it("hits the bare /events URL when no filters are supplied", () => {
    const dispose = subscribePlannerEvents({}, {});
    expect(FakeEventSource.instances[0].url).toBe(
      `${API_BASE}/api/planner/events`,
    );
    dispose();
  });

  it("parses JSON frames and forwards them as PlannerEvent", () => {
    const seen: PlannerEvent[] = [];
    const dispose = subscribePlannerEvents(
      { planId: "pln_abc" },
      { onEvent: (e) => seen.push(e) },
    );
    const fixture: PlannerEvent = {
      id: 7,
      kind: "plan.run.usage",
      ts: 12345,
      trace_id: "trc_run",
      payload: {
        plan_id: "pln_abc",
        status: "completed",
        usage: {
          calls: 2,
          tokens_in: 100,
          tokens_out: 50,
          cost_usd: 0.0123,
          latency_ms_total: 12,
          has_priced_models: true,
        },
      },
    };
    FakeEventSource.instances[0].emit(fixture);
    expect(seen).toEqual([fixture]);
    dispose();
  });

  it("ignores malformed frames silently (does not crash the subscriber)", () => {
    const seen: PlannerEvent[] = [];
    const dispose = subscribePlannerEvents(
      {},
      { onEvent: (e) => seen.push(e) },
    );
    FakeEventSource.instances[0].emitRaw("not-json{{{");
    // Then a good frame still works.
    FakeEventSource.instances[0].emit({
      id: 1,
      kind: "plan.proposed",
      ts: 0,
      trace_id: null,
      payload: {},
    });
    expect(seen).toHaveLength(1);
    expect(seen[0].kind).toBe("plan.proposed");
    dispose();
  });

  it("invokes onOpen / onError handlers verbatim", () => {
    const events: string[] = [];
    const dispose = subscribePlannerEvents(
      {},
      {
        onOpen: () => events.push("open"),
        onError: () => events.push("error"),
      },
    );
    FakeEventSource.instances[0].onopen?.();
    FakeEventSource.instances[0].onerror?.(new Event("error"));
    expect(events).toEqual(["open", "error"]);
    dispose();
  });
});

// ---------------------------------------------------------------------------
// formatCostUSD
// ---------------------------------------------------------------------------

describe("formatCostUSD", () => {
  it("renders null as 'n/a' so the cockpit never lies about pricing", () => {
    expect(formatCostUSD(null)).toBe("n/a");
    expect(formatCostUSD(undefined)).toBe("n/a");
  });

  it("renders a number with four decimals so micro-costs are visible", () => {
    expect(formatCostUSD(0)).toBe("$0.0000");
    expect(formatCostUSD(0.0001234)).toBe("$0.0001");
    expect(formatCostUSD(1.2)).toBe("$1.2000");
    expect(formatCostUSD(12.3456789)).toBe("$12.3457");
  });
});
