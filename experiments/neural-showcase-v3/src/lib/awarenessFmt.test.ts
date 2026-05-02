/**
 * Vitest contract for `lib/awarenessFmt.ts`.
 */

import { describe, expect, test } from "vitest";

import {
  emptySnapshotState,
  filterAwareness,
  fmtAgo,
  fmtTookMs,
  kindTone,
  liveSourceCount,
  pickSlug,
  prettyJson,
  snapshotKey,
  totalSourceCount,
} from "./awarenessFmt";
import type { AwarenessSource } from "./api";

const SRC = (over: Partial<AwarenessSource> = {}): AwarenessSource => ({
  id: "calendar",
  name: "Calendar",
  description: "Local calendar feed",
  kind: "poll",
  config: {},
  live: true,
  ...over,
});

describe("kindTone", () => {
  test.each([
    ["stream", "stream"],
    ["poll", "poll"],
    ["webhook", "webhook"],
    ["local", "local"],
  ])("%s gets a recognisable label", (kind, label) => {
    expect(kindTone(kind).label).toBe(label);
    expect(kindTone(kind).cls).toMatch(/border-/);
  });

  test("unknown kinds fall back to neutral with the raw value", () => {
    expect(kindTone("xyz").label).toBe("xyz");
    expect(kindTone("xyz").cls).toContain("border-line");
  });

  test("null / undefined / blank degrade to '—'", () => {
    expect(kindTone(null).label).toBe("—");
    expect(kindTone(undefined).label).toBe("—");
    expect(kindTone("").label).toBe("—");
    expect(kindTone("   ").label).toBe("—");
  });

  test("case insensitivity", () => {
    expect(kindTone("STREAM").label).toBe("stream");
    expect(kindTone("Webhook").label).toBe("webhook");
  });
});

describe("fmtTookMs", () => {
  test("nullish → '—'", () => {
    expect(fmtTookMs(null)).toBe("—");
    expect(fmtTookMs(undefined)).toBe("—");
    expect(fmtTookMs(NaN)).toBe("—");
    expect(fmtTookMs(Infinity)).toBe("—");
  });

  test("sub-second uses ms units", () => {
    expect(fmtTookMs(0)).toBe("0 ms");
    expect(fmtTookMs(345)).toBe("345 ms");
    expect(fmtTookMs(999)).toBe("999 ms");
  });

  test("≥1s switches to seconds with two decimals", () => {
    expect(fmtTookMs(1000)).toBe("1.00 s");
    expect(fmtTookMs(1234)).toBe("1.23 s");
    expect(fmtTookMs(60_000)).toBe("60.00 s");
  });
});

describe("fmtAgo", () => {
  const now = 1_700_000_000_000;

  test("nullish → '—'", () => {
    expect(fmtAgo(null, now)).toBe("—");
    expect(fmtAgo(undefined, now)).toBe("—");
    expect(fmtAgo(NaN, now)).toBe("—");
  });

  test("ms epoch", () => {
    expect(fmtAgo(now - 500, now)).toBe("just now");
    expect(fmtAgo(now - 10_000, now)).toBe("10 s ago");
    expect(fmtAgo(now - 90_000, now)).toBe("2 min ago");
    expect(fmtAgo(now - 3600_000 * 3, now)).toBe("3 h ago");
    expect(fmtAgo(now - 86_400_000 * 5, now)).toBe("5 d ago");
  });

  test("seconds epoch is auto-promoted", () => {
    const tsSeconds = now / 1000 - 30; // 30 seconds ago in seconds
    expect(fmtAgo(tsSeconds, now)).toBe("30 s ago");
  });
});

describe("snapshotKey + emptySnapshotState", () => {
  test("snapshotKey is stable and slug-bound", () => {
    expect(snapshotKey("traders", "binance")).toBe("traders::binance");
    expect(snapshotKey("a", "b")).not.toBe(snapshotKey("b", "a"));
  });

  test("emptySnapshotState shape", () => {
    const s = emptySnapshotState();
    expect(s.loading).toBe(false);
    expect(s.lastFetchedAt).toBeNull();
    expect(s.envelope).toBeNull();
    expect(s.error).toBeNull();
  });
});

describe("filterAwareness", () => {
  const sources: AwarenessSource[] = [
    SRC({ id: "calendar", name: "Calendar", description: "ical agenda", kind: "poll" }),
    SRC({ id: "binance_basket", name: "Binance basket", description: "OHLC tickers", kind: "poll" }),
    SRC({ id: "news_feed", name: "News feed", description: "headlines stream", kind: "stream" }),
    SRC({
      id: "webhook_x",
      name: "Webhook X",
      description: "incoming alerts",
      kind: "webhook",
    }),
  ];

  test("empty query echoes input", () => {
    expect(filterAwareness(sources, "").length).toBe(sources.length);
    expect(filterAwareness(sources, "   ").length).toBe(sources.length);
  });

  test("matches by name (case-insensitive)", () => {
    const r = filterAwareness(sources, "binance");
    expect(r).toHaveLength(1);
    expect(r[0]!.id).toBe("binance_basket");
  });

  test("matches by id substring", () => {
    expect(filterAwareness(sources, "feed")).toHaveLength(1);
    expect(filterAwareness(sources, "feed")[0]!.id).toBe("news_feed");
  });

  test("matches by description", () => {
    const r = filterAwareness(sources, "alerts");
    expect(r).toHaveLength(1);
    expect(r[0]!.id).toBe("webhook_x");
  });

  test("matches by kind", () => {
    expect(filterAwareness(sources, "stream")).toHaveLength(1);
    expect(filterAwareness(sources, "poll")).toHaveLength(2);
  });

  test("no match returns []", () => {
    expect(filterAwareness(sources, "zzznomatch")).toEqual([]);
  });
});

describe("prettyJson", () => {
  test("null / undefined → empty string", () => {
    expect(prettyJson(null)).toBe("");
    expect(prettyJson(undefined)).toBe("");
  });

  test("simple objects pretty-print with two-space indent", () => {
    const out = prettyJson({ a: 1, b: [2, 3] });
    expect(out).toContain('"a": 1');
    expect(out).toContain('"b": [');
    expect(out).toContain("\n");
  });

  test("circular falls back to String(value)", () => {
    const obj: Record<string, unknown> = { a: 1 };
    obj.self = obj;
    const out = prettyJson(obj);
    expect(out).toBe("[object Object]");
  });
});

describe("pickSlug", () => {
  test("returns null on empty pack list", () => {
    expect(pickSlug([], "anything")).toBeNull();
  });

  test("query slug wins when valid", () => {
    expect(pickSlug(["a", "b", "c"], "b")).toBe("b");
  });

  test("falls back to first slug on missing / stale query", () => {
    expect(pickSlug(["a", "b"], null)).toBe("a");
    expect(pickSlug(["a", "b"], undefined)).toBe("a");
    expect(pickSlug(["a", "b"], "ghost")).toBe("a");
  });
});

describe("count helpers", () => {
  const packs = [
    { awareness: [SRC(), SRC({ id: "a2", live: false })] },
    { awareness: [SRC({ id: "b1" })] },
    { awareness: [] },
    { awareness: undefined },
  ];

  test("totalSourceCount sums every awareness", () => {
    expect(totalSourceCount(packs)).toBe(3);
  });

  test("liveSourceCount only counts live sources", () => {
    expect(liveSourceCount(packs[0]!.awareness)).toBe(1);
    expect(liveSourceCount(packs[1]!.awareness)).toBe(1);
    expect(liveSourceCount([])).toBe(0);
    expect(liveSourceCount(null)).toBe(0);
    expect(liveSourceCount(undefined)).toBe(0);
  });
});
