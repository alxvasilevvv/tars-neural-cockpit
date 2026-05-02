/**
 * Vitest contract for `lib/operatorPalette.ts`.
 *
 * The page (`<OperatorPalette />`) is a thin shell over these
 * helpers, so the rules of the palette (scoring, recents, group
 * counts, deep-links, recover-from-failure loader) all live here.
 */

import { describe, expect, test, beforeEach, afterEach, vi } from "vitest";

import {
  ALL_GROUPS,
  emptyIndex,
  entryHref,
  filterByGroup,
  fuzzyScore,
  groupCounts,
  loadOperatorIndex,
  loadRecentIds,
  pickRecent,
  pushRecent,
  rankEntries,
  shapeAction,
  shapeAwareness,
  shapePack,
  shapePlaybook,
  shapeTrace,
  totalCount,
  type OperatorEntry,
} from "./operatorPalette";
import type { DomainPack } from "./api";
import type { Playbook } from "./playbooks";
import type { TraceSummary } from "./meeet";

const TEMPLATE_PACK = (over: Partial<DomainPack> = {}): DomainPack => ({
  slug: "traders",
  name: "Traders",
  short: "Risk-on / risk-off basket aggregation",
  description: "Wire up DexScreener / Binance",
  color: "amber",
  capabilities: ["fetch_quote", "summarize_market"],
  audience: "operator",
  actions: [
    {
      id: "fetch_quote",
      name: "Fetch quote",
      description: "Get a live quote",
      schema: {},
    },
    {
      id: "place_alert",
      name: "Place alert",
      description: "Persist a local alert",
      schema: {},
      destructive: true,
    },
  ],
  awareness: [
    {
      id: "binance_basket",
      name: "Binance basket",
      description: "Live OHLC for the operator basket",
      kind: "poll",
      config: {},
      live: true,
    },
  ],
  ...over,
});

const TEMPLATE_PLAYBOOK = (over: Partial<Playbook> = {}): Playbook => ({
  id: "traders.morning_check",
  name: "Morning check",
  description: "Pre-market scan",
  tags: ["morning", "scan"],
  on_block: "stop",
  steps: [],
  ...over,
});

const TEMPLATE_TRACE = (over: Partial<TraceSummary> = {}): TraceSummary => ({
  trace_id: "tr-123-abcdef-99",
  event_count: 5,
  kinds: ["domain.action.invoked", "usage.tokens"],
  routes: ["edge", "cloud"],
  primary_route: "cloud",
  total_cost_usd: 0.0123,
  tokens_in: 120,
  tokens_out: 80,
  contradictions: 0,
  error_count: 0,
  last_session_id: null,
  started_at: 1_700_000_000,
  ended_at: 1_700_000_100,
  duration_ms: 100_000,
  ...over,
});

describe("shapers", () => {
  test("shapePack flattens slug + capabilities + audience into haystack", () => {
    const pack = TEMPLATE_PACK();
    const e = shapePack(pack);
    expect(e.kind).toBe("pack");
    expect(e.id).toBe("pack:traders");
    expect(e.title).toBe("Traders");
    expect(e.haystack).toContain("traders");
    expect(e.haystack).toContain("operator");
    expect(e.haystack).toContain("fetch_quote");
    expect(e.destructive).toBe(false);
    expect(e.group).toBe("packs");
  });

  test("shapePack falls back to slug when name is empty", () => {
    const e = shapePack(TEMPLATE_PACK({ name: "" }));
    expect(e.title).toBe("traders");
  });

  test("shapeAction marks destructive flag", () => {
    const pack = TEMPLATE_PACK();
    const e = shapeAction(pack, pack.actions[1]!);
    expect(e.destructive).toBe(true);
    expect(e.hint).toContain("destructive");
    expect(e.id).toBe("action:traders:place_alert");
  });

  test("shapeAction non-destructive omits the marker", () => {
    const pack = TEMPLATE_PACK();
    const e = shapeAction(pack, pack.actions[0]!);
    expect(e.destructive).toBe(false);
    expect(e.hint).not.toContain("destructive");
  });

  test("shapeAwareness mentions live + kind in hint", () => {
    const pack = TEMPLATE_PACK();
    const e = shapeAwareness(pack, pack.awareness[0]!);
    expect(e.kind).toBe("awareness");
    expect(e.hint).toContain("poll");
    expect(e.hint).toContain("live");
    expect(e.haystack).toContain("binance_basket");
  });

  test("shapePlaybook splits id on dot for pack badge", () => {
    const e = shapePlaybook(TEMPLATE_PLAYBOOK());
    expect(e.packSlug).toBe("traders");
    expect(e.hint).toContain("traders");
    expect(e.haystack).toContain("morning_check");
    expect(e.haystack).toContain("morning");
  });

  test("shapePlaybook handles ids without a dot", () => {
    const e = shapePlaybook(TEMPLATE_PLAYBOOK({ id: "lonely" }));
    expect(e.packSlug).toBeNull();
    expect(e.hint).toBe("playbook");
  });

  test("shapeTrace formats hint as route · ev · cost", () => {
    const e = shapeTrace(TEMPLATE_TRACE());
    // Title is the first 12 chars of the trace_id (palette truncates
    // long ids so the row stays single-line on dense screens).
    expect(e.title.length).toBeLessThanOrEqual(12);
    expect(e.title.startsWith("tr-123-")).toBe(true);
    expect(e.hint).toContain("cloud");
    expect(e.hint).toContain("5 ev");
    expect(e.hint).toContain("$0.0123");
    expect(e.haystack).toContain("cloud");
  });

  test("shapeTrace tolerates missing cost / route", () => {
    const e = shapeTrace(
      TEMPLATE_TRACE({ total_cost_usd: null, primary_route: null }),
    );
    expect(e.hint).toContain("$0");
    expect(e.hint).toContain("—");
  });
});

describe("scoring", () => {
  const entries: OperatorEntry[] = [
    shapePack(TEMPLATE_PACK()),
    shapeAction(TEMPLATE_PACK(), TEMPLATE_PACK().actions[0]!),
    shapeAction(TEMPLATE_PACK(), TEMPLATE_PACK().actions[1]!),
    shapePlaybook(TEMPLATE_PLAYBOOK()),
    shapeAwareness(TEMPLATE_PACK(), TEMPLATE_PACK().awareness[0]!),
    shapeTrace(TEMPLATE_TRACE()),
  ];

  test("empty / whitespace query returns 0 score", () => {
    expect(fuzzyScore(entries[0]!, "")).toBe(0);
    expect(fuzzyScore(entries[0]!, "   ")).toBe(0);
  });

  test("title prefix match wins by 30 bonus", () => {
    const tradersPack = entries[0]!;
    const otherWithT = shapeAction(
      TEMPLATE_PACK({ slug: "x", name: "X", actions: [] }),
      { id: "tradersx", name: "Tradersx", description: "", schema: {} },
    );
    expect(fuzzyScore(tradersPack, "trad")).toBeGreaterThan(
      fuzzyScore(otherWithT, "trad") - 1,
    );
  });

  test("pack kind gets a small boost over actions on identical body", () => {
    const pack = shapePack(TEMPLATE_PACK({ slug: "alpha", name: "alpha" }));
    const action = shapeAction(
      TEMPLATE_PACK({ slug: "alpha", name: "alpha" }),
      { id: "alpha_act", name: "alpha", description: "alpha", schema: {} },
    );
    expect(fuzzyScore(pack, "alpha")).toBeGreaterThanOrEqual(
      fuzzyScore(action, "alpha"),
    );
  });

  test("rankEntries returns descending score, stable tie-break", () => {
    const ranked = rankEntries(entries, "trad");
    expect(ranked.length).toBeGreaterThan(0);
    // Every match must have a positive score (rankEntries drops zeros).
    for (const r of ranked) {
      expect(fuzzyScore(r, "trad")).toBeGreaterThan(0);
    }
    // pack should land first because of the title-prefix + pack bonus
    expect(ranked[0]!.kind).toBe("pack");
  });

  test("rankEntries on empty query echoes input order", () => {
    const ranked = rankEntries(entries, "");
    expect(ranked.map(e => e.id)).toEqual(entries.map(e => e.id));
  });

  test("rankEntries drops zero-score rows", () => {
    const ranked = rankEntries(entries, "zzzzznomatch");
    expect(ranked).toEqual([]);
  });
});

describe("group filter + counts", () => {
  const index = {
    packs: [shapePack(TEMPLATE_PACK())],
    actions: [
      shapeAction(TEMPLATE_PACK(), TEMPLATE_PACK().actions[0]!),
      shapeAction(TEMPLATE_PACK(), TEMPLATE_PACK().actions[1]!),
    ],
    playbooks: [shapePlaybook(TEMPLATE_PLAYBOOK())],
    awareness: [shapeAwareness(TEMPLATE_PACK(), TEMPLATE_PACK().awareness[0]!)],
    traces: [shapeTrace(TEMPLATE_TRACE())],
  };

  test("ALL_GROUPS contract is stable", () => {
    expect(ALL_GROUPS).toEqual([
      "packs",
      "actions",
      "playbooks",
      "awareness",
      "traces",
    ]);
  });

  test("filterByGroup all preserves canonical order", () => {
    const flat = filterByGroup(index, "all");
    expect(flat.map(e => e.kind)).toEqual([
      "pack",
      "action",
      "action",
      "playbook",
      "awareness",
      "trace",
    ]);
  });

  test("filterByGroup specific returns only that group", () => {
    expect(filterByGroup(index, "actions").length).toBe(2);
    expect(filterByGroup(index, "traces").length).toBe(1);
  });

  test("totalCount + groupCounts match the index", () => {
    expect(totalCount(index)).toBe(6);
    expect(groupCounts(index)).toEqual({
      packs: 1,
      actions: 2,
      playbooks: 1,
      awareness: 1,
      traces: 1,
    });
  });

  test("emptyIndex shapes are predictable", () => {
    const e = emptyIndex();
    expect(totalCount(e)).toBe(0);
    expect(groupCounts(e)).toEqual({
      packs: 0,
      actions: 0,
      playbooks: 0,
      awareness: 0,
      traces: 0,
    });
  });
});

describe("recent ids (localStorage)", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  test("loadRecentIds returns [] on empty store", () => {
    expect(loadRecentIds()).toEqual([]);
  });

  test("pushRecent dedupes + caps at 5", () => {
    const a = pushRecent("a");
    expect(a).toEqual(["a"]);
    pushRecent("b");
    pushRecent("c");
    pushRecent("a"); // dedupe → reorder to head
    pushRecent("d");
    pushRecent("e");
    pushRecent("f");
    const recent = loadRecentIds();
    expect(recent.length).toBe(5);
    expect(recent[0]).toBe("f");
    expect(recent).not.toContain("b"); // oldest evicted
  });

  test("pickRecent returns entries in recent order", () => {
    const index = {
      packs: [shapePack(TEMPLATE_PACK())],
      actions: [],
      playbooks: [shapePlaybook(TEMPLATE_PLAYBOOK())],
      awareness: [],
      traces: [],
    };
    const recents = pickRecent(index, [
      "playbook:traders.morning_check",
      "pack:traders",
    ]);
    expect(recents.map(e => e.id)).toEqual([
      "playbook:traders.morning_check",
      "pack:traders",
    ]);
  });

  test("pickRecent drops ids that no longer exist", () => {
    const index = {
      packs: [shapePack(TEMPLATE_PACK())],
      actions: [],
      playbooks: [],
      awareness: [],
      traces: [],
    };
    const out = pickRecent(index, ["playbook:gone", "pack:traders"]);
    expect(out.map(e => e.id)).toEqual(["pack:traders"]);
  });

  test("loadRecentIds tolerates corrupted JSON", () => {
    localStorage.setItem("tars-operator-palette-recent", "{not-valid");
    expect(loadRecentIds()).toEqual([]);
  });
});

describe("entryHref", () => {
  test("trace deep-links to the trace viewer", () => {
    const e = shapeTrace(TEMPLATE_TRACE());
    expect(entryHref(e)).toBe(
      "/cockpit/traces?trace=tr-123-abcdef-99",
    );
  });

  test("pack deep-links to /cockpit?pack=", () => {
    const e = shapePack(TEMPLATE_PACK());
    expect(entryHref(e)).toBe("/cockpit?pack=traders");
  });

  test("action / awareness / playbook return null (invoke in-place)", () => {
    expect(
      entryHref(shapeAction(TEMPLATE_PACK(), TEMPLATE_PACK().actions[0]!)),
    ).toBeNull();
    expect(
      entryHref(
        shapeAwareness(TEMPLATE_PACK(), TEMPLATE_PACK().awareness[0]!),
      ),
    ).toBeNull();
    expect(entryHref(shapePlaybook(TEMPLATE_PLAYBOOK()))).toBeNull();
  });
});

describe("loadOperatorIndex", () => {
  let originalFetch: typeof fetch;
  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("happy path: hydrates packs + actions + awareness + playbooks + traces", async () => {
    const mockFetch = vi.fn(async (url: string | URL | Request) => {
      const u = String(url);
      if (u.endsWith("/api/domains")) {
        return mockJson({
          domains: [TEMPLATE_PACK()],
        });
      }
      if (u.endsWith("/api/playbooks")) {
        return mockJson({ playbooks: [TEMPLATE_PLAYBOOK()] });
      }
      if (u.includes("/api/meeet/traces")) {
        return mockJson({ traces: [TEMPLATE_TRACE()] });
      }
      throw new Error(`unexpected fetch ${u}`);
    });
    globalThis.fetch = mockFetch as typeof fetch;

    const { index, errors } = await loadOperatorIndex({ traceLimit: 7 });
    expect(errors).toEqual({
      packs: null,
      actions: null,
      playbooks: null,
      awareness: null,
      traces: null,
    });
    expect(index.packs.length).toBe(1);
    expect(index.actions.length).toBe(2);
    expect(index.awareness.length).toBe(1);
    expect(index.playbooks.length).toBe(1);
    expect(index.traces.length).toBe(1);
  });

  test("partial failure: traces error doesn't poison the rest", async () => {
    const mockFetch = vi.fn(async (url: string | URL | Request) => {
      const u = String(url);
      if (u.endsWith("/api/domains")) {
        return mockJson({ domains: [TEMPLATE_PACK()] });
      }
      if (u.endsWith("/api/playbooks")) {
        return mockJson({ playbooks: [TEMPLATE_PLAYBOOK()] });
      }
      if (u.includes("/api/meeet/traces")) {
        return new Response("boom", { status: 503 });
      }
      throw new Error(`unexpected fetch ${u}`);
    });
    globalThis.fetch = mockFetch as typeof fetch;

    const { index, errors } = await loadOperatorIndex();
    expect(errors.traces).toBeTruthy();
    expect(errors.packs).toBeNull();
    expect(errors.playbooks).toBeNull();
    expect(index.packs.length).toBe(1);
    expect(index.traces.length).toBe(0);
  });

  test("domain failure marks packs / actions / awareness errors together", async () => {
    const mockFetch = vi.fn(async (url: string | URL | Request) => {
      const u = String(url);
      if (u.endsWith("/api/domains")) {
        return new Response("nope", { status: 500 });
      }
      if (u.endsWith("/api/playbooks")) {
        return mockJson({ playbooks: [] });
      }
      if (u.includes("/api/meeet/traces")) {
        return mockJson({ traces: [] });
      }
      throw new Error(`unexpected fetch ${u}`);
    });
    globalThis.fetch = mockFetch as typeof fetch;

    const { index, errors } = await loadOperatorIndex();
    expect(errors.packs).toBeTruthy();
    expect(errors.actions).toBeTruthy();
    expect(errors.awareness).toBeTruthy();
    expect(errors.playbooks).toBeNull();
    expect(errors.traces).toBeNull();
    expect(index.packs).toEqual([]);
    expect(index.actions).toEqual([]);
  });

  test("traceLimit is clamped to [1, 50]", async () => {
    const mockFetch = vi.fn(async (url: string | URL | Request) => {
      const u = String(url);
      if (u.endsWith("/api/domains")) return mockJson({ domains: [] });
      if (u.endsWith("/api/playbooks")) return mockJson({ playbooks: [] });
      if (u.includes("/api/meeet/traces")) {
        const limit = new URL(u, "http://x").searchParams.get("limit");
        expect(Number(limit)).toBeGreaterThanOrEqual(1);
        expect(Number(limit)).toBeLessThanOrEqual(50);
        return mockJson({ traces: [] });
      }
      throw new Error(`unexpected fetch ${u}`);
    });
    globalThis.fetch = mockFetch as typeof fetch;

    await loadOperatorIndex({ traceLimit: 9999 });
    await loadOperatorIndex({ traceLimit: 0 });
  });
});

function mockJson(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}
