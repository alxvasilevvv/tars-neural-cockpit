/**
 * Vitest contract for `lib/cowork.ts` — Wave 129.
 *
 * Pure-function coverage: `fmtRelative`, `isLive`, plus the mock-fallback
 * paths for `fetchSession`, `listMembers`, `listSessions`, `createHandoff`.
 * The hooks (`useCoworkStream`, `useHeartbeat`) are exercised via the
 * smoke render in `Cowork.smoke.test.tsx`.
 */

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import {
  COWORK_MOCK,
  createHandoff,
  fetchSession,
  fmtRelative,
  isLive,
  listMembers,
  listSessions,
} from "./cowork";

describe("fmtRelative", () => {
  test("under 5 s reads 'just now'", () => {
    const now = 1_000_000;
    expect(fmtRelative(now - 2, now)).toBe("just now");
    expect(fmtRelative(now, now)).toBe("just now");
  });

  test("under 60 s reads in seconds", () => {
    const now = 1_000_000;
    expect(fmtRelative(now - 30, now)).toBe("30s ago");
  });

  test("under 1 h reads in minutes", () => {
    const now = 1_000_000;
    expect(fmtRelative(now - 120, now)).toBe("2m ago");
  });

  test("over 1 h reads in hours", () => {
    const now = 1_000_000;
    expect(fmtRelative(now - 7200, now)).toBe("2h ago");
  });

  test("negative diff (clock skew) still produces 'just now'", () => {
    const now = 1_000_000;
    expect(fmtRelative(now + 60, now)).toBe("just now");
  });
});

describe("isLive", () => {
  test("within 25 s window returns true", () => {
    const now = 1_000_000;
    expect(isLive(now - 5, now)).toBe(true);
    expect(isLive(now - 20, now)).toBe(true);
  });

  test("at or past 25 s returns false", () => {
    const now = 1_000_000;
    expect(isLive(now - 25, now)).toBe(false);
    expect(isLive(now - 60, now)).toBe(false);
  });
});

// ── mock-fallback behaviour ─────────────────────────────────────────

describe("mock fallback when fetch fails", () => {
  beforeEach(() => {
    // Force fetch to fail across the suite so the mock path runs.
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("no network"))),
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("fetchSession returns mock for the demo slug", async () => {
    const s = await fetchSession(COWORK_MOCK.session.slug);
    expect(s).not.toBeNull();
    expect(s?.name).toBe(COWORK_MOCK.session.name);
  });

  test("fetchSession returns mock for the 'demo' alias", async () => {
    const s = await fetchSession("demo");
    expect(s).not.toBeNull();
  });

  test("fetchSession returns null for unknown slugs in mock mode", async () => {
    const s = await fetchSession("nope-does-not-exist");
    expect(s).toBeNull();
  });

  test("listMembers returns mock fixtures", async () => {
    const ms = await listMembers("cw_demo");
    expect(ms.length).toBeGreaterThan(0);
    expect(ms[0].display_name).toBeTruthy();
  });

  test("listSessions returns one mock session", async () => {
    const list = await listSessions();
    expect(list.length).toBe(1);
    expect(list[0].slug).toBe(COWORK_MOCK.session.slug);
  });

  test("createHandoff returns mock token + expires_at", async () => {
    const result = await createHandoff("cw_demo", {
      from_user_id: "u_alice",
      to_email: "bob@example.com",
    });
    expect(result).not.toBeNull();
    expect(typeof result?.token).toBe("string");
    expect(typeof result?.expires_at).toBe("number");
    expect(result!.expires_at).toBeGreaterThan(Date.now() / 1000);
  });
});

// ── real-path branch via stubbed ok response ────────────────────────

describe("when fetch succeeds", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.endsWith("/sessions/realsess")) {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                id: "cw_real",
                name: "Real session",
                slug: "realsess",
                owner_user_id: "u_real",
                status: "live",
                created_at: 1_000_000,
                ended_at: null,
                workspace_id: null,
                metadata: {},
              }),
              { status: 200 },
            ),
          );
        }
        return Promise.resolve(new Response("not found", { status: 404 }));
      }),
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("fetchSession unwraps the real response when 200", async () => {
    const s = await fetchSession("realsess");
    expect(s).not.toBeNull();
    expect(s?.id).toBe("cw_real");
  });

  test("404 from real backend still produces null for unknown slugs", async () => {
    const s = await fetchSession("definitely-unknown-slug");
    expect(s).toBeNull();
  });
});
