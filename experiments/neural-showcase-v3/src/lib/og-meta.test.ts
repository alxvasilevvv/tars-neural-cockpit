/**
 * Wave 127 — vitest contract for `lib/og-meta.ts`. Pins the same
 * thresholds the build-time validator (`scripts/validate-og-cards.mjs`)
 * enforces, so a future change to TITLE_MAX or IMG_MIN_W can never
 * silently desync the gate.
 */

import { describe, expect, test } from "vitest";

import {
  CANONICAL_HOST,
  DESC_MAX,
  IMG_MIN_H,
  IMG_MIN_W,
  TITLE_MAX,
  TITLE_SUFFIX,
  isAbsoluteOgUrl,
  isValidOgType,
  isValidTwitterCard,
  meetsImageDims,
  parseSvgDims,
  suggestOgSlug,
  validateDescription,
  validateTitle,
} from "./og-meta";

describe("validateTitle", () => {
  test("accepts a short title and appends the suffix", () => {
    const r = validateTitle("Cockpit");
    expect(r.ok).toBe(true);
    expect(r.effective).toBe(`Cockpit${TITLE_SUFFIX}`);
    expect(r.length).toBeLessThanOrEqual(TITLE_MAX);
  });

  test("flags a title that overflows the cap and suggests a trim", () => {
    const long = "A".repeat(80);
    const r = validateTitle(long);
    expect(r.ok).toBe(false);
    expect(r.length).toBeGreaterThan(TITLE_MAX);
    expect(r.suggestion).toBeDefined();
    expect(r.suggestion!.length).toBeLessThanOrEqual(
      TITLE_MAX - TITLE_SUFFIX.length,
    );
    expect(r.suggestion!.endsWith("…")).toBe(true);
  });

  test("rawTitle skips the suffix and keeps the literal length", () => {
    const r = validateTitle("Custom marketing page", true);
    expect(r.ok).toBe(true);
    expect(r.effective).toBe("Custom marketing page");
  });

  test("empty string is rejected", () => {
    expect(validateTitle("").ok).toBe(false);
  });
});

describe("validateDescription", () => {
  test("accepts a normal description", () => {
    expect(validateDescription("hello").ok).toBe(true);
  });
  test("rejects empty", () => {
    expect(validateDescription("").ok).toBe(false);
  });
  test("rejects > DESC_MAX", () => {
    expect(validateDescription("x".repeat(DESC_MAX + 1)).ok).toBe(false);
  });
  test("accepts exactly DESC_MAX", () => {
    expect(validateDescription("x".repeat(DESC_MAX)).ok).toBe(true);
  });
});

describe("isAbsoluteOgUrl", () => {
  test("accepts a tars.meeet.world URL", () => {
    expect(isAbsoluteOgUrl(`${CANONICAL_HOST}/og.svg`)).toBe(true);
  });
  test("rejects a relative path", () => {
    expect(isAbsoluteOgUrl("/og.svg")).toBe(false);
  });
  test("rejects another host", () => {
    expect(isAbsoluteOgUrl("https://meeet.world/og.svg")).toBe(false);
  });
});

describe("parseSvgDims", () => {
  test("parses explicit width/height", () => {
    const dims = parseSvgDims(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">',
    );
    expect(dims).toEqual({ width: 1200, height: 630 });
    expect(meetsImageDims(dims)).toBe(true);
  });
  test("falls back to viewBox when width/height absent", () => {
    const dims = parseSvgDims(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900">',
    );
    expect(dims).toEqual({ width: 1600, height: 900 });
  });
  test("returns zeros on a malformed payload", () => {
    expect(parseSvgDims("<not-an-svg>")).toEqual({ width: 0, height: 0 });
  });
  test("meetsImageDims rejects undersized SVGs", () => {
    expect(meetsImageDims({ width: IMG_MIN_W - 1, height: IMG_MIN_H })).toBe(
      false,
    );
    expect(meetsImageDims({ width: IMG_MIN_W, height: IMG_MIN_H - 1 })).toBe(
      false,
    );
  });
});

describe("suggestOgSlug", () => {
  const available = [
    "og.svg",
    "og-pricing.svg",
    "og-workshop.svg",
    "og-workshop-enterprise.svg",
  ];
  test("exact match wins", () => {
    expect(suggestOgSlug("/pricing", available)).toBe("/og-pricing.svg");
  });
  test("prefix match for nested route", () => {
    expect(suggestOgSlug("/workshop/enterprise", available)).toBe(
      "/og-workshop.svg",
    );
  });
  test("falls back to default", () => {
    expect(suggestOgSlug("/something-new", available)).toBe("/og.svg");
  });
});

describe("Twitter / OG type", () => {
  test("twitter:card must be summary_large_image", () => {
    expect(isValidTwitterCard("summary_large_image")).toBe(true);
    expect(isValidTwitterCard("summary")).toBe(false);
    expect(isValidTwitterCard(null)).toBe(false);
  });
  test("og:type accepts website or article", () => {
    expect(isValidOgType("website")).toBe(true);
    expect(isValidOgType("article")).toBe(true);
    expect(isValidOgType("video")).toBe(false);
  });
});
