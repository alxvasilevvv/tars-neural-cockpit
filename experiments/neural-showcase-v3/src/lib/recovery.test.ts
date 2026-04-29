/**
 * Vitest — recovery client (Phase L5 G1 / K3).
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  RecoveryError,
  WORD_COUNT,
  chunkMnemonic,
  generateSeed,
  isCompleteAttempt,
  mnemonicsMatch,
  normaliseMnemonic,
  verifySeed,
} from "./recovery";

afterEach(() => {
  vi.restoreAllMocks();
});

// 24 real-looking words (no digits — `normaliseMnemonic` strips them).
const FULL_24_WORDS = [
  "abandon", "ability", "able", "about", "above", "absent",
  "absorb",  "abstract", "absurd", "abuse", "access", "accident",
  "account", "accuse", "achieve", "acid", "acoustic", "acquire",
  "across",  "act",     "action", "actor", "actress", "actual",
];
const FULL_24 = FULL_24_WORDS.join(" ");

// ---------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------

describe("normaliseMnemonic", () => {
  it("collapses whitespace and lowercases", () => {
    expect(normaliseMnemonic("  Abandon\tAbility   ABLE\n")).toBe(
      "abandon ability able",
    );
  });
  it("strips punctuation", () => {
    expect(normaliseMnemonic("abandon. ability, able!")).toBe(
      "abandon ability able",
    );
  });
});

describe("chunkMnemonic", () => {
  it("returns a 4×6 grid for a 24-word phrase", () => {
    const grid = chunkMnemonic(FULL_24);
    expect(grid).toHaveLength(4);
    grid.forEach((row) => expect(row).toHaveLength(6));
    expect(grid[0][0]).toBe(FULL_24_WORDS[0]);
    expect(grid[3][5]).toBe(FULL_24_WORDS[23]);
  });
  it("rejects mismatched lengths", () => {
    expect(() => chunkMnemonic("abandon")).toThrow();
  });
  it("supports custom shapes", () => {
    const m = FULL_24_WORDS.slice(0, 12).join(" ");
    const grid = chunkMnemonic(m, 3, 4);
    expect(grid).toHaveLength(3);
    grid.forEach((row) => expect(row).toHaveLength(4));
  });
});

describe("mnemonicsMatch", () => {
  it("matches modulo whitespace + case", () => {
    expect(mnemonicsMatch("Abandon ABLE", "  abandon\table  ")).toBe(true);
  });
  it("treats two empty inputs as non-match", () => {
    expect(mnemonicsMatch("", "")).toBe(false);
  });
});

describe("isCompleteAttempt", () => {
  it("requires exactly 24 words", () => {
    expect(isCompleteAttempt(FULL_24)).toBe(true);
  });
  it("rejects partial input", () => {
    expect(isCompleteAttempt("abandon ability")).toBe(false);
  });
});

// ---------------------------------------------------------------------
// HTTP wrappers
// ---------------------------------------------------------------------

function mockFetch(
  status: number,
  body: unknown,
): vi.Mock {
  const fn = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: `HTTP ${status}`,
    json: () => Promise.resolve(body),
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("generateSeed", () => {
  it("POSTs to /api/recovery/generate", async () => {
    const stub = mockFetch(200, {
      ok: true,
      trace_id: "trc",
      mnemonic: FULL_24,
      fingerprint: "ABCD12345678",
      word_count: 24,
    });
    const res = await generateSeed();
    expect(res.fingerprint).toBe("ABCD12345678");
    const [url, init] = stub.mock.calls[0];
    expect(String(url)).toContain("/api/recovery/generate");
    expect((init as RequestInit).method).toBe("POST");
  });
});

describe("verifySeed", () => {
  it("posts the mnemonic body and returns fingerprint", async () => {
    const stub = mockFetch(200, {
      ok: true,
      trace_id: "trc",
      fingerprint: "ABCD12345678",
    });
    const res = await verifySeed({ mnemonic: FULL_24 });
    expect(res.fingerprint).toBe("ABCD12345678");
    const init = stub.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      mnemonic: FULL_24,
      passphrase: null,
    });
  });

  it("propagates RecoveryError on 400", async () => {
    mockFetch(400, { detail: "invalid_mnemonic: bad checksum" });
    await expect(verifySeed({ mnemonic: "garbage" })).rejects.toBeInstanceOf(
      RecoveryError,
    );
  });
});
