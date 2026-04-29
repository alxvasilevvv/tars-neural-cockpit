/**
 * Pure-helper tests for the cinematic mnemonic reveal. The DOM/visual
 * choreography is exercised manually inside the cockpit — this suite
 * just locks the input parsing + grid layout heuristics.
 */

import { describe, expect, it } from "vitest";

import { gridTemplateForCount, splitMnemonic } from "@/components/MnemonicReveal";

describe("splitMnemonic", () => {
  it("splits 24-word phrase on whitespace", () => {
    const phrase = Array.from({ length: 24 }, (_, i) => `w${i}`).join(" ");
    expect(splitMnemonic(phrase)).toHaveLength(24);
  });

  it("collapses repeated whitespace", () => {
    expect(splitMnemonic("alpha   beta\n\tgamma")).toEqual(["alpha", "beta", "gamma"]);
  });

  it("trims and rejects empty fragments", () => {
    expect(splitMnemonic("  alpha  beta  ")).toEqual(["alpha", "beta"]);
    expect(splitMnemonic("")).toEqual([]);
    expect(splitMnemonic("   ")).toEqual([]);
  });
});

describe("gridTemplateForCount", () => {
  it("uses 3 columns for short phrases", () => {
    expect(gridTemplateForCount(6)).toMatch(/repeat\(3/);
  });

  it("uses 4 columns for 12 / 24 words", () => {
    expect(gridTemplateForCount(12)).toMatch(/repeat\(4/);
    expect(gridTemplateForCount(24)).toMatch(/repeat\(4/);
  });

  it("clamps anything larger to 4 columns", () => {
    expect(gridTemplateForCount(48)).toMatch(/repeat\(4/);
  });
});
