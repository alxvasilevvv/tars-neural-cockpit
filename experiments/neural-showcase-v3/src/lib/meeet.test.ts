/**
 * Contract tests for the trace-summary helpers in `lib/meeet.ts`.
 *
 * The cockpit talks to the FastAPI router in
 * `web_extras/routers/meeet.py`. The Python side already pins the
 * shape with pytest; this file pins the TS-side wire shape so a
 * regression there can't silently drift the cockpit out of sync.
 *
 * Specifically:
 *
 * 1. URL + method + querystring construction is correct (no
 *    accidental drift in path encoding or filter-name typos).
 * 2. The response envelope round-trips into the typed shape
 *    (`TraceSummary`).
 * 3. ``getTrace`` returns ``null`` on a 404 (missing trace) and
 *    throws on any other non-2xx status.
 * 4. ``refreshTraces`` POSTs (not GETs) and propagates the
 *    ``since`` filter through the querystring.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getTrace,
  listTraces,
  refreshTraces,
  type TraceSummary,
} from "./meeet";
import { API_BASE } from "./api";

interface RecordedCall {
  url: string;
  init: RequestInit | undefined;
}

let recordedCalls: RecordedCall[];
let fetchMock: ReturnType<typeof vi.fn>;

function mockFetchOnce(body: unknown, init: ResponseInit = { status: 200 }): void {
  fetchMock.mockImplementationOnce(
    (url: RequestInfo | URL, init2?: RequestInit) => {
      recordedCalls.push({ url: String(url), init: init2 });
      return Promise.resolve(
        new Response(JSON.stringify(body), {
          ...init,
          headers: { "content-type": "application/json", ...(init.headers ?? {}) },
        }),
      );
    },
  );
}

function mockFetchOnceRaw(status: number, body = ""): void {
  fetchMock.mockImplementationOnce(
    (url: RequestInfo | URL, init2?: RequestInit) => {
      recordedCalls.push({ url: String(url), init: init2 });
      return Promise.resolve(new Response(body, { status }));
    },
  );
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

const FIXTURE_TRACE: TraceSummary = {
  trace_id: "trc_abc",
  event_count: 3,
  kinds: ["domain.action.invoked", "domain.action.completed"],
  routes: ["edge"],
  primary_route: "edge",
  total_cost_usd: 0.0042,
  tokens_in: 100,
  tokens_out: 200,
  contradictions: 0,
  error_count: 0,
  last_session_id: "ses_xyz",
  started_at: 1714665600,
  ended_at: 1714665601,
  duration_ms: 1000,
  updated_at: 1714665602,
};

describe("listTraces", () => {
  it("hits /api/meeet/traces (no qs) by default", async () => {
    mockFetchOnce({ ok: true, count: 1, traces: [FIXTURE_TRACE] });
    const out = await listTraces();
    expect(out).toEqual([FIXTURE_TRACE]);
    expect(recordedCalls[0].url).toBe(`${API_BASE}/api/meeet/traces`);
  });

  it("builds the querystring from limit / since / primary_route / session_id", async () => {
    mockFetchOnce({ ok: true, count: 0, traces: [] });
    await listTraces({
      limit: 25,
      since: 12345,
      primary_route: "cloud",
      session_id: "ses_xyz",
    });
    const url = new URL(recordedCalls[0].url);
    expect(url.pathname).toBe("/api/meeet/traces");
    expect(url.searchParams.get("limit")).toBe("25");
    expect(url.searchParams.get("since")).toBe("12345");
    expect(url.searchParams.get("primary_route")).toBe("cloud");
    expect(url.searchParams.get("session_id")).toBe("ses_xyz");
  });

  it("returns [] when the server responds with empty traces", async () => {
    mockFetchOnce({ ok: true, count: 0, traces: [] });
    expect(await listTraces()).toEqual([]);
  });

  it("returns [] when the server omits the traces field entirely", async () => {
    mockFetchOnce({ ok: true });
    expect(await listTraces()).toEqual([]);
  });

  it("throws on a non-2xx response", async () => {
    mockFetchOnceRaw(500, "boom");
    await expect(listTraces()).rejects.toThrow(/HTTP 500/);
  });
});

describe("getTrace", () => {
  it("hits /api/meeet/traces/{trace_id} and round-trips the envelope", async () => {
    mockFetchOnce({ ok: true, trace: FIXTURE_TRACE });
    const out = await getTrace("trc_abc");
    expect(out).toEqual(FIXTURE_TRACE);
    expect(recordedCalls[0].url).toBe(
      `${API_BASE}/api/meeet/traces/trc_abc`,
    );
  });

  it("URL-encodes a trace_id with slashes / spaces", async () => {
    mockFetchOnce({ ok: true, trace: FIXTURE_TRACE });
    await getTrace("trc/abc with space");
    expect(recordedCalls[0].url).toBe(
      `${API_BASE}/api/meeet/traces/trc%2Fabc%20with%20space`,
    );
  });

  it("returns null on 404 (trace not yet rolled up)", async () => {
    mockFetchOnceRaw(404, "trace_not_found");
    const out = await getTrace("trc_unknown");
    expect(out).toBeNull();
  });

  it("returns null when the response omits the trace field", async () => {
    mockFetchOnce({ ok: true });
    const out = await getTrace("trc_abc");
    expect(out).toBeNull();
  });

  it("throws on any other non-2xx status (5xx, 401, …)", async () => {
    mockFetchOnceRaw(500, "boom");
    await expect(getTrace("trc_abc")).rejects.toThrow(/HTTP 500/);
  });
});

describe("refreshTraces", () => {
  it("POSTs to /api/meeet/traces/refresh", async () => {
    mockFetchOnce({ ok: true, rebuilt: 17 });
    const out = await refreshTraces();
    expect(out).toEqual({ ok: true, rebuilt: 17 });
    expect(recordedCalls[0].init?.method).toBe("POST");
    expect(recordedCalls[0].url).toBe(
      `${API_BASE}/api/meeet/traces/refresh`,
    );
  });

  it("propagates ``since`` through the querystring", async () => {
    mockFetchOnce({ ok: true, rebuilt: 0 });
    await refreshTraces({ since: 999_999 });
    const url = new URL(recordedCalls[0].url);
    expect(url.searchParams.get("since")).toBe("999999");
  });

  it("throws on a non-2xx response", async () => {
    mockFetchOnceRaw(503, "rebuilding-locked");
    await expect(refreshTraces()).rejects.toThrow(/HTTP 503/);
  });
});
