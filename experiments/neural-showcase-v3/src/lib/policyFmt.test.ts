/**
 * Pure-helper contract tests for `lib/policyFmt.ts`.
 *
 * Pin the formatting / coercion contracts the Policy Inbox page
 * depends on so a future refactor can't quietly drift the operator
 * UI (e.g. flipping "expired" pills back to "—" or losing the
 * relative-age cliff at the day boundary).
 */

import { describe, expect, it } from "vitest";

import {
  ALL_STATUSES,
  compareConfirmationsNewestFirst,
  fmtAge,
  fmtTimeLeft,
  matchesQuery,
  statusTone,
  type ConfirmationStatus,
} from "./policyFmt";
import type { PendingConfirmation } from "./policy";

const NOW = 1_700_000_000;

function mkConfirmation(overrides: Partial<PendingConfirmation> = {}): PendingConfirmation {
  return {
    token: "tok_default",
    slug: "business",
    action_id: "log_deal",
    args: {},
    created_at: NOW - 60,
    expires_at: NOW + 600,
    status: "pending",
    resolved_at: null,
    result: null,
    trace_id: null,
    requested_by: null,
    ...overrides,
  };
}

describe("ALL_STATUSES", () => {
  it("enumerates the 5 backend statuses in stable order", () => {
    expect(ALL_STATUSES).toEqual([
      "pending",
      "confirmed",
      "cancelled",
      "expired",
      "failed",
    ]);
  });
});

describe("statusTone", () => {
  it("returns a non-empty class string for every documented status", () => {
    for (const s of ALL_STATUSES) {
      const tone = statusTone(s);
      expect(tone.label).toBe(s);
      expect(tone.cls.length).toBeGreaterThan(0);
    }
  });

  it("falls back to a muted tone for an unknown status (no crash)", () => {
    const tone = statusTone("ghost" as ConfirmationStatus);
    expect(tone.cls).toContain("text-ink-3");
    expect(tone.label).toBe("ghost");
  });
});

describe("fmtAge", () => {
  it("renders sub-minute / sub-hour / sub-day spans", () => {
    expect(fmtAge(NOW - 5, NOW)).toBe("5s ago");
    expect(fmtAge(NOW - 60, NOW)).toBe("1m ago");
    expect(fmtAge(NOW - 3600, NOW)).toBe("1h ago");
    expect(fmtAge(NOW - 7200, NOW)).toBe("2h ago");
    expect(fmtAge(NOW - 86400, NOW)).toBe("1d ago");
  });

  it("renders sub-second as 'just now'", () => {
    expect(fmtAge(NOW - 0.4, NOW)).toBe("just now");
    expect(fmtAge(NOW, NOW)).toBe("just now");
  });

  it("renders an em-dash for null / 0 / NaN / negative", () => {
    expect(fmtAge(null, NOW)).toBe("—");
    expect(fmtAge(undefined, NOW)).toBe("—");
    expect(fmtAge(0, NOW)).toBe("—");
    expect(fmtAge(-1, NOW)).toBe("—");
    expect(fmtAge(NaN, NOW)).toBe("—");
  });

  it("clamps future timestamps to 'just now' instead of '-5s ago'", () => {
    expect(fmtAge(NOW + 5, NOW)).toBe("just now");
  });
});

describe("fmtTimeLeft", () => {
  it("renders sub-minute / sub-hour / sub-day windows", () => {
    expect(fmtTimeLeft(NOW + 30, NOW)).toBe("30s left");
    expect(fmtTimeLeft(NOW + 60, NOW)).toBe("1m left");
    expect(fmtTimeLeft(NOW + 3600, NOW)).toBe("1h left");
    expect(fmtTimeLeft(NOW + 86400, NOW)).toBe("1d left");
  });

  it("renders 'expired' once the clock has passed", () => {
    expect(fmtTimeLeft(NOW - 1, NOW)).toBe("expired");
    expect(fmtTimeLeft(NOW, NOW)).toBe("expired");
  });

  it("returns 'no expiry' for null / 0 / NaN", () => {
    expect(fmtTimeLeft(null, NOW)).toBe("no expiry");
    expect(fmtTimeLeft(undefined, NOW)).toBe("no expiry");
    expect(fmtTimeLeft(0, NOW)).toBe("no expiry");
    expect(fmtTimeLeft(NaN, NOW)).toBe("no expiry");
  });
});

describe("compareConfirmationsNewestFirst", () => {
  it("sorts by created_at descending", () => {
    const a = mkConfirmation({ token: "t_old", created_at: 100 });
    const b = mkConfirmation({ token: "t_new", created_at: 200 });
    const sorted = [a, b].sort(compareConfirmationsNewestFirst);
    expect(sorted.map((c) => c.token)).toEqual(["t_new", "t_old"]);
  });

  it("breaks ties on token (descending) so output is stable", () => {
    const a = mkConfirmation({ token: "t_a", created_at: 100 });
    const b = mkConfirmation({ token: "t_b", created_at: 100 });
    const sorted = [a, b].sort(compareConfirmationsNewestFirst);
    expect(sorted.map((c) => c.token)).toEqual(["t_b", "t_a"]);
  });
});

describe("matchesQuery", () => {
  const c = mkConfirmation({
    token: "tok_alpha_123",
    slug: "business",
    action_id: "log_deal",
    requested_by: "operator@meeet.world",
    trace_id: "trc_abc",
  });

  it("returns true on empty / whitespace-only query (filter is no-op)", () => {
    expect(matchesQuery(c, "")).toBe(true);
    expect(matchesQuery(c, "   ")).toBe(true);
  });

  it("matches against token / slug / action_id / requested_by / trace_id", () => {
    expect(matchesQuery(c, "tok_alpha")).toBe(true);
    expect(matchesQuery(c, "business")).toBe(true);
    expect(matchesQuery(c, "log_deal")).toBe(true);
    expect(matchesQuery(c, "operator@")).toBe(true);
    expect(matchesQuery(c, "trc_abc")).toBe(true);
    // Combined slug.action_id form for cockpit-flavoured queries.
    expect(matchesQuery(c, "business.log_deal")).toBe(true);
  });

  it("is case-insensitive", () => {
    expect(matchesQuery(c, "BUSINESS")).toBe(true);
    expect(matchesQuery(c, "TOK_alpha")).toBe(true);
  });

  it("returns false on a non-matching substring", () => {
    expect(matchesQuery(c, "traders")).toBe(false);
    expect(matchesQuery(c, "ghost-token")).toBe(false);
  });
});
