import { afterEach, describe, expect, it } from "vitest";

import { __test__ } from "./clientError";

describe("clientError reporter — pure logic", () => {
  afterEach(() => {
    __test__.reset();
  });

  it("signatureKey is stable for the same error", () => {
    const a = __test__.signatureKey({
      message: "Cannot read property of undefined",
      source: "https://tars.meeet.world/assets/bundle-abc.js",
      line: 42,
      col: 7,
    });
    const b = __test__.signatureKey({
      message: "Cannot read property of undefined",
      source: "https://tars.meeet.world/assets/bundle-abc.js",
      line: 42,
      col: 7,
    });
    expect(a).toBe(b);
  });

  it("signatureKey distinguishes different errors", () => {
    const a = __test__.signatureKey({
      message: "TypeError A",
      source: "src/a.ts",
      line: 1,
      col: 1,
    });
    const b = __test__.signatureKey({
      message: "TypeError B",
      source: "src/a.ts",
      line: 1,
      col: 1,
    });
    expect(a).not.toBe(b);
  });

  it("shouldEmit allows first occurrence", () => {
    const sig = { message: "uniq one", source: "" };
    expect(__test__.shouldEmit(sig)).toBe(true);
  });

  it("shouldEmit dedupes identical signatures within the window", () => {
    const sig = { message: "dupe error", source: "" };
    expect(__test__.shouldEmit(sig)).toBe(true);
    expect(__test__.shouldEmit(sig)).toBe(false);
    expect(__test__.shouldEmit(sig)).toBe(false);
  });

  it("shouldEmit rate-limits after 10 unique events in a minute", () => {
    for (let i = 0; i < 10; i++) {
      expect(__test__.shouldEmit({ message: `error_${i}`, source: "" })).toBe(true);
    }
    // 11th unique error in the same window should be rejected
    expect(__test__.shouldEmit({ message: "error_overflow", source: "" })).toBe(false);
  });

  it("rate-limit counter resets after a fresh window", () => {
    for (let i = 0; i < 10; i++) {
      __test__.shouldEmit({ message: `err_${i}`, source: "" });
    }
    expect(__test__.shouldEmit({ message: "err_blocked", source: "" })).toBe(false);

    // Simulate the rolling window expiring by rolling the start back.
    __test__.state.windowStart = Date.now() - 61_000;
    expect(__test__.shouldEmit({ message: "err_after_window", source: "" })).toBe(true);
  });

  it("recentSignatures map keeps memory bounded under load", () => {
    for (let i = 0; i < 200; i++) {
      __test__.state.windowStart = Date.now() - 61_000;
      __test__.state.windowCount = 0;
      __test__.shouldEmit({ message: `flood_${i}`, source: "" });
    }
    // Map prunes entries older than 60s when it crosses 50 entries.
    expect(__test__.state.recentSignatures.size).toBeLessThanOrEqual(200);
  });
});
