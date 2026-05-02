/**
 * Contract tests for `lib/policy.ts`.
 *
 * The cockpit talks to the FastAPI router in
 * `web_extras/routers/policy.py`. The Python side already pins the
 * shape with pytest; this file pins the TS-side wire shape so a
 * regression there can't silently drift the operator-facing inbox.
 *
 * Pinned:
 *
 * 1. `listPending` / `listRecent` hit the documented URLs and
 *    deserialise into `PendingConfirmation[]`.
 * 2. `confirmToken` / `cancelToken` POST (not GET) and propagate
 *    the token through the path segment.
 * 3. `expireStale` POSTs `/api/policy/expire` and returns the
 *    `{ expired: number }` envelope.
 * 4. Empty / missing-field response shapes default to ``[]`` so
 *    the cockpit never crashes on a benign null.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cancelToken,
  confirmToken,
  expireStale,
  listPending,
  listRecent,
  type PendingConfirmation,
} from "./policy";
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

const FIXTURE: PendingConfirmation = {
  token: "tok_abc",
  slug: "business",
  action_id: "log_deal",
  args: { name: "Acme", amount: 12000 },
  created_at: 1714665600,
  expires_at: 1714669200,
  status: "pending",
  resolved_at: null,
  result: null,
  trace_id: "trc_birth",
  requested_by: "operator@meeet.world",
};

describe("listPending", () => {
  it("hits /api/policy/pending and round-trips the envelope", async () => {
    mockFetchOnce({ ok: true, count: 1, pending: [FIXTURE] });
    const out = await listPending();
    expect(out).toEqual([FIXTURE]);
    expect(recordedCalls[0].url).toBe(`${API_BASE}/api/policy/pending`);
  });

  it("returns [] when the server omits the pending field entirely", async () => {
    mockFetchOnce({ ok: true });
    expect(await listPending()).toEqual([]);
  });

  it("throws on a non-2xx response", async () => {
    mockFetchOnceRaw(503, "store-degraded");
    await expect(listPending()).rejects.toThrow(/HTTP 503/);
  });
});

describe("listRecent", () => {
  it("hits /api/policy/recent?limit=N and round-trips the envelope", async () => {
    const resolved: PendingConfirmation = {
      ...FIXTURE,
      token: "tok_done",
      status: "confirmed",
      resolved_at: FIXTURE.created_at + 5,
      result: { ok: true, deal_id: "local-0001" },
    };
    mockFetchOnce({ ok: true, count: 1, recent: [resolved] });
    const out = await listRecent(25);
    expect(out).toEqual([resolved]);
    expect(recordedCalls[0].url).toBe(
      `${API_BASE}/api/policy/recent?limit=25`,
    );
  });

  it("defaults to limit=50 when no value is supplied", async () => {
    mockFetchOnce({ ok: true, count: 0, recent: [] });
    await listRecent();
    expect(recordedCalls[0].url).toBe(`${API_BASE}/api/policy/recent?limit=50`);
  });

  it("returns [] on missing-field responses", async () => {
    mockFetchOnce({ ok: true });
    expect(await listRecent()).toEqual([]);
  });
});

describe("confirmToken", () => {
  it("POSTs to /api/policy/confirm/{token} with a JSON body", async () => {
    mockFetchOnce({ ok: true, confirmation: { ...FIXTURE, status: "confirmed" } });
    await confirmToken("tok_abc");
    expect(recordedCalls[0].init?.method).toBe("POST");
    expect(recordedCalls[0].url).toBe(
      `${API_BASE}/api/policy/confirm/tok_abc`,
    );
    const headers = (recordedCalls[0].init?.headers ?? {}) as Record<string, string>;
    expect(headers["content-type"]).toBe("application/json");
  });

  it("propagates the body text on a non-2xx response", async () => {
    mockFetchOnceRaw(409, "confirmation_already_cancelled");
    await expect(confirmToken("tok_abc")).rejects.toThrow(
      /HTTP 409 · confirmation_already_cancelled/,
    );
  });
});

describe("cancelToken", () => {
  it("POSTs to /api/policy/cancel/{token}", async () => {
    mockFetchOnce({ ok: true, confirmation: { ...FIXTURE, status: "cancelled" } });
    await cancelToken("tok_abc");
    expect(recordedCalls[0].init?.method).toBe("POST");
    expect(recordedCalls[0].url).toBe(`${API_BASE}/api/policy/cancel/tok_abc`);
  });
});

describe("expireStale", () => {
  it("POSTs to /api/policy/expire and returns the envelope", async () => {
    mockFetchOnce({ ok: true, expired: 3, tokens: ["tok_a", "tok_b", "tok_c"] });
    const out = await expireStale();
    expect((out as { expired: number }).expired).toBe(3);
    expect(recordedCalls[0].init?.method).toBe("POST");
    expect(recordedCalls[0].url).toBe(`${API_BASE}/api/policy/expire`);
  });
});
