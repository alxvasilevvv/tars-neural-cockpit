/**
 * Pure-helper contract tests for `lib/councilFmt.ts`.
 *
 * Pin the formatting / coercion contracts the Council Debug page
 * depends on so a future refactor can't quietly drift the cockpit
 * UI (e.g. flipping confidence percentages back to 0..1 or losing
 * the "voice unavailable" stance routing).
 */

import { describe, expect, it } from "vitest";

import {
  confidenceWidth,
  fmtConfidencePct,
  fmtLatencyMs,
  normaliseStance,
  pickWinningVoice,
  rollupVoices,
  stanceTone,
} from "./councilFmt";
import type { Proposal } from "./council";

const UNITS = { ms: "ms", s: "s" };

function mkVoice(overrides: Partial<Proposal> = {}): Proposal {
  return {
    model: "tars-local-rules-v1",
    stance: "neutral",
    summary: "no-op",
    actions_recommended: [],
    confidence: 0.5,
    rationale: "",
    latency_ms: 12,
    tokens_in: 100,
    tokens_out: 200,
    ...overrides,
  };
}

describe("normaliseStance", () => {
  it("lowercases + trims, returning '' for null/undefined", () => {
    expect(normaliseStance("RISK_ON")).toBe("risk_on");
    expect(normaliseStance("  Bullish  ")).toBe("bullish");
    expect(normaliseStance(null)).toBe("");
    expect(normaliseStance(undefined)).toBe("");
  });
});

describe("stanceTone", () => {
  it("maps risk_on / bullish / buy / long to success tone", () => {
    for (const s of ["risk_on", "bullish", "buy", "long"]) {
      expect(stanceTone(s).cls).toContain("color-success");
    }
  });

  it("maps risk_off / bearish / sell / short to alert tone", () => {
    for (const s of ["risk_off", "bearish", "sell", "short"]) {
      expect(stanceTone(s).cls).toContain("text-alert");
    }
  });

  it("maps neutral / hold to muted", () => {
    expect(stanceTone("neutral").cls).toContain("text-ink-2");
    expect(stanceTone("hold").cls).toContain("text-ink-2");
  });

  it("maps unavailable / empty to ink-3", () => {
    expect(stanceTone("unavailable").cls).toContain("text-ink-3");
    expect(stanceTone("").cls).toContain("text-ink-3");
    expect(stanceTone(null).cls).toContain("text-ink-3");
  });

  it("falls back to accent tone for unknown stances", () => {
    const tone = stanceTone("frothy");
    expect(tone.cls).toContain("text-accent");
    expect(tone.label).toBe("frothy");
  });
});

describe("fmtConfidencePct", () => {
  it("renders [0..1] floats as percent strings", () => {
    expect(fmtConfidencePct(0)).toBe("0.0%");
    expect(fmtConfidencePct(0.5)).toBe("50.0%");
    expect(fmtConfidencePct(1)).toBe("100.0%");
    expect(fmtConfidencePct(0.823)).toBe("82.3%");
  });

  it("clamps out-of-range values into [0..1]", () => {
    expect(fmtConfidencePct(-0.5)).toBe("0.0%");
    expect(fmtConfidencePct(1.7)).toBe("100.0%");
  });

  it("returns '—' on null / undefined / NaN / Infinity", () => {
    expect(fmtConfidencePct(null)).toBe("—");
    expect(fmtConfidencePct(undefined)).toBe("—");
    expect(fmtConfidencePct(NaN)).toBe("—");
    expect(fmtConfidencePct(Infinity)).toBe("—");
  });
});

describe("confidenceWidth", () => {
  it("returns the clamped fraction", () => {
    expect(confidenceWidth(0)).toBe(0);
    expect(confidenceWidth(0.5)).toBe(0.5);
    expect(confidenceWidth(1)).toBe(1);
    expect(confidenceWidth(2)).toBe(1);
    expect(confidenceWidth(-1)).toBe(0);
  });

  it("returns 0 on null / NaN", () => {
    expect(confidenceWidth(null)).toBe(0);
    expect(confidenceWidth(undefined)).toBe(0);
    expect(confidenceWidth(NaN)).toBe(0);
  });
});

describe("pickWinningVoice", () => {
  it("returns null on empty input", () => {
    expect(pickWinningVoice([])).toBeNull();
  });

  it("returns the highest-confidence voice", () => {
    const voices = [
      mkVoice({ model: "a", confidence: 0.4 }),
      mkVoice({ model: "b", confidence: 0.9 }),
      mkVoice({ model: "c", confidence: 0.7 }),
    ];
    expect(pickWinningVoice(voices)).toBe("b");
  });

  it("breaks ties by first-seen (no instability)", () => {
    const voices = [
      mkVoice({ model: "first", confidence: 0.8 }),
      mkVoice({ model: "second", confidence: 0.8 }),
    ];
    expect(pickWinningVoice(voices)).toBe("first");
  });
});

describe("rollupVoices", () => {
  it("sums tokens / latency across voices and counts them", () => {
    const out = rollupVoices([
      mkVoice({ tokens_in: 10, tokens_out: 20, latency_ms: 100 }),
      mkVoice({ tokens_in: 30, tokens_out: 40, latency_ms: 200 }),
    ]);
    expect(out).toEqual({
      total_tokens_in: 40,
      total_tokens_out: 60,
      total_latency_ms: 300,
      voice_count: 2,
    });
  });

  it("returns zeroed rollup for empty input", () => {
    expect(rollupVoices([])).toEqual({
      total_tokens_in: 0,
      total_tokens_out: 0,
      total_latency_ms: 0,
      voice_count: 0,
    });
  });

  it("ignores NaN tokens / latency (treats as 0) so the cockpit doesn't print 'NaN'", () => {
    const out = rollupVoices([
      mkVoice({ tokens_in: NaN, tokens_out: 10, latency_ms: NaN }),
      mkVoice({ tokens_in: 5, tokens_out: 15, latency_ms: 30 }),
    ]);
    expect(out.total_tokens_in).toBe(5);
    expect(out.total_tokens_out).toBe(25);
    expect(out.total_latency_ms).toBe(30);
  });
});

describe("fmtLatencyMs", () => {
  it("renders sub-second ms with rounded integer", () => {
    expect(fmtLatencyMs(0, UNITS)).toBe("0 ms");
    expect(fmtLatencyMs(123.7, UNITS)).toBe("124 ms");
    expect(fmtLatencyMs(999, UNITS)).toBe("999 ms");
  });

  it("renders ≥ 1s as a 2-decimal seconds value", () => {
    expect(fmtLatencyMs(1000, UNITS)).toBe("1.00 s");
    expect(fmtLatencyMs(1500, UNITS)).toBe("1.50 s");
  });

  it("renders an em-dash for null / NaN / Infinity", () => {
    expect(fmtLatencyMs(null, UNITS)).toBe("—");
    expect(fmtLatencyMs(NaN, UNITS)).toBe("—");
    expect(fmtLatencyMs(Infinity, UNITS)).toBe("—");
  });
});
