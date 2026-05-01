/**
 * Tests for `lib/tier.ts` — TIER_GATES + tier resolution + fetchTier
 * stub. Pure helpers; no live network.
 *
 * Mirrors the contract draft at `docs/contracts/RECEIPT_LEDGER.md`.
 */

import { describe, expect, it } from "vitest";

import {
  fetchTier,
  featureToTier,
  featuresForTier,
  FREE_TIER_RESOLUTION,
  normaliseTierResolution,
  resolveTierFromReceipts,
  TIER_GATES,
  tierAllows,
  type ReceiptLike,
  type TierFeature,
  type TierResolution,
  type TierSlug,
} from "./tier";

// --------------------------------------------------------------------
// TIER_GATES — frozen feature matrix
// --------------------------------------------------------------------

describe("TIER_GATES", () => {
  it("free gates only chat-only mode + 50 messages/day", () => {
    expect(TIER_GATES.free).toContain("modes.chat_only");
    expect(TIER_GATES.free).toContain("messages.50_per_day");
    expect(TIER_GATES.free).not.toContain("background_tasks");
  });

  it("pro adds the productivity tier (background tasks, briefs, reflection)", () => {
    expect(TIER_GATES.pro).toContain("background_tasks");
    expect(TIER_GATES.pro).toContain("morning_briefs");
    expect(TIER_GATES.pro).toContain("memory_reflection");
    expect(TIER_GATES.pro).not.toContain("receipt_ledger");
  });

  it("business adds team / api / receipt-ledger", () => {
    expect(TIER_GATES.business).toContain("receipt_ledger");
    expect(TIER_GATES.business).toContain("team_collaboration");
    expect(TIER_GATES.business).toContain("api_access");
    expect(TIER_GATES.business).not.toContain("custom_persona_presets");
  });

  it("lifetime is a strict superset of business", () => {
    for (const f of TIER_GATES.business) {
      expect(TIER_GATES.lifetime).toContain(f);
    }
    expect(TIER_GATES.lifetime).toContain("custom_persona_presets");
    expect(TIER_GATES.lifetime).toContain("priority_support");
  });

  it("messages cap is monotonic free < pro < business = lifetime", () => {
    expect(TIER_GATES.free).toContain("messages.50_per_day");
    expect(TIER_GATES.pro).toContain("messages.500_per_day");
    expect(TIER_GATES.business).toContain("messages.unlimited");
    expect(TIER_GATES.lifetime).toContain("messages.unlimited");
  });
});

// --------------------------------------------------------------------
// featureToTier — minimum tier per feature
// --------------------------------------------------------------------

describe("featureToTier", () => {
  it("maps each feature to the minimum tier that includes it", () => {
    const cases: Array<[TierFeature, TierSlug]> = [
      ["modes.chat_only", "free"],
      ["messages.50_per_day", "free"],
      ["background_tasks", "pro"],
      ["morning_briefs", "pro"],
      ["receipt_ledger", "business"],
      ["api_access", "business"],
      ["custom_persona_presets", "lifetime"],
      ["priority_support", "lifetime"],
    ];
    for (const [feature, expected] of cases) {
      expect(featureToTier[feature]).toBe(expected);
    }
  });

  it("contains every feature listed in TIER_GATES.lifetime", () => {
    for (const f of TIER_GATES.lifetime) {
      expect(featureToTier[f]).toBeTruthy();
    }
  });
});

// --------------------------------------------------------------------
// resolveTierFromReceipts
// --------------------------------------------------------------------

const BASE_DATE = new Date("2026-05-01T20:00:00Z");

function r(overrides: Partial<ReceiptLike>): ReceiptLike {
  return {
    tars_tier: "free",
    status: "active",
    expires_at: null,
    created_at: "2026-05-01T18:00:00Z",
    ...overrides,
  };
}

describe("resolveTierFromReceipts", () => {
  it("falls back to free when no active receipts", () => {
    const out = resolveTierFromReceipts([], BASE_DATE);
    expect(out).toEqual({ tier: "free", tier_source: "default", active_receipt: null });
  });

  it("ignores expired receipts even when status is still 'active'", () => {
    const out = resolveTierFromReceipts(
      [r({ tars_tier: "pro", expires_at: "2026-04-01T00:00:00Z" })],
      BASE_DATE,
    );
    expect(out.tier).toBe("free");
  });

  it("ignores cancelled / expired statuses", () => {
    const out = resolveTierFromReceipts(
      [
        r({ tars_tier: "pro", status: "cancelled" }),
        r({ tars_tier: "business", status: "expired" }),
      ],
      BASE_DATE,
    );
    expect(out.tier).toBe("free");
  });

  it("treats null expires_at as lifetime / non-expiring", () => {
    const out = resolveTierFromReceipts(
      [r({ tars_tier: "lifetime", expires_at: null })],
      BASE_DATE,
    );
    expect(out.tier).toBe("lifetime");
    expect(out.tier_source).toBe("receipt");
  });

  it("picks the most recent active receipt when several exist", () => {
    const out = resolveTierFromReceipts(
      [
        r({
          tars_tier: "pro",
          created_at: "2026-04-01T00:00:00Z",
          expires_at: "2026-06-01T00:00:00Z",
        }),
        r({
          tars_tier: "business",
          created_at: "2026-05-01T00:00:00Z",
          expires_at: "2026-06-01T00:00:00Z",
        }),
      ],
      BASE_DATE,
    );
    expect(out.tier).toBe("business");
    expect(out.active_receipt?.tars_tier).toBe("business");
  });
});

// --------------------------------------------------------------------
// featuresForTier + tierAllows
// --------------------------------------------------------------------

describe("featuresForTier + tierAllows", () => {
  it("returns the canonical projection for each tier", () => {
    expect(featuresForTier("free")).toBe(TIER_GATES.free);
    expect(featuresForTier("lifetime")).toBe(TIER_GATES.lifetime);
  });

  it("tierAllows returns false for null resolution (defensive)", () => {
    expect(tierAllows(null, "background_tasks")).toBe(false);
  });

  it("tierAllows reads from resolution.features", () => {
    const res: TierResolution = {
      ...FREE_TIER_RESOLUTION,
      tier: "pro",
      tier_source: "receipt",
      features: TIER_GATES.pro,
    };
    expect(tierAllows(res, "background_tasks")).toBe(true);
    expect(tierAllows(res, "receipt_ledger")).toBe(false);
  });
});

// --------------------------------------------------------------------
// normaliseTierResolution — defensive parsing of producer payloads
// --------------------------------------------------------------------

describe("normaliseTierResolution", () => {
  it("falls back to free + projected features for unknown tier", () => {
    const out = normaliseTierResolution({ tier: "unknown" as unknown as TierSlug });
    expect(out.tier).toBe("free");
    expect(out.features).toBe(TIER_GATES.free);
  });

  it("trusts a coherent payload from the producer", () => {
    const out = normaliseTierResolution({
      ok: true,
      contract_version: "1.0.0",
      operator_id: "op-1",
      tier: "pro",
      tier_source: "receipt",
      active_receipt_id: "rec-1",
      expires_at: "2026-06-01T00:00:00Z",
      features: ["modes.all", "messages.500_per_day", "background_tasks"],
    });
    expect(out.tier).toBe("pro");
    expect(out.tier_source).toBe("receipt");
    expect(out.features).toEqual([
      "modes.all",
      "messages.500_per_day",
      "background_tasks",
    ]);
  });

  it("strips unknown features but keeps known ones from the producer payload", () => {
    const out = normaliseTierResolution({
      tier: "business",
      features: [
        "background_tasks",
        // unknown — must be filtered out
        "telepathy" as unknown as TierFeature,
        "receipt_ledger",
      ],
    });
    expect(out.features).toContain("background_tasks");
    expect(out.features).toContain("receipt_ledger");
    expect(out.features).not.toContain("telepathy" as unknown as TierFeature);
  });

  it("falls back to TIER_GATES projection when producer omits features", () => {
    const out = normaliseTierResolution({ tier: "lifetime" });
    expect(out.features).toBe(TIER_GATES.lifetime);
  });
});

// --------------------------------------------------------------------
// fetchTier — stub today
// --------------------------------------------------------------------

describe("fetchTier", () => {
  it("returns the free fallback when no producer URL is configured", async () => {
    const out = await fetchTier({ url: null });
    expect(out).toEqual(FREE_TIER_RESOLUTION);
  });

  it("returns the free fallback on non-OK response (silent)", async () => {
    const fetchImpl: typeof fetch = async () =>
      new Response("not ok", { status: 503 });
    const out = await fetchTier({ url: "https://example/tier", fetchImpl });
    expect(out.tier).toBe("free");
  });

  it("returns the free fallback when fetch throws", async () => {
    const fetchImpl: typeof fetch = async () => {
      throw new Error("network down");
    };
    const out = await fetchTier({ url: "https://example/tier", fetchImpl });
    expect(out.tier).toBe("free");
  });

  it("propagates the operator JWT in the Authorization header", async () => {
    const seen: { authorization?: string } = {};
    const fetchImpl: typeof fetch = async (_input, init) => {
      const headers = init?.headers as Record<string, string> | undefined;
      seen.authorization = headers?.authorization;
      return new Response(
        JSON.stringify({
          ok: true,
          tier: "pro",
          tier_source: "receipt",
          features: TIER_GATES.pro,
        }),
        { status: 200 },
      );
    };
    const out = await fetchTier({
      url: "https://example/tier",
      jwt: "abc.def.ghi",
      fetchImpl,
    });
    expect(seen.authorization).toBe("Bearer abc.def.ghi");
    expect(out.tier).toBe("pro");
    expect(out.features).toEqual(TIER_GATES.pro);
  });
});
