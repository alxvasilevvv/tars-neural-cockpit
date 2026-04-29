import { describe, expect, it } from "vitest";

import { chainBadgeClass, shortenAddress } from "./wallet";

describe("shortenAddress", () => {
  it("returns short addresses unchanged", () => {
    expect(shortenAddress("0xabc")).toBe("0xabc");
  });
  it("truncates the middle of long addresses", () => {
    const a = "11111111111111111111111111111111";
    const out = shortenAddress(a);
    expect(out.startsWith("111111")).toBe(true);
    expect(out.endsWith("111111")).toBe(true);
    expect(out).toContain("…");
    expect(out.length).toBeLessThan(a.length);
  });
  it("respects custom head/tail lengths", () => {
    const out = shortenAddress("ABCDEFGHIJKLMNOPQRST", 3, 3);
    expect(out).toBe("ABC…RST");
  });
  it("preserves EIP-55 checksum casing", () => {
    const a = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266";
    const out = shortenAddress(a);
    // Default head=6, tail=6 → "0xf39F…b92266"
    expect(out).toContain("0xf39F");
    expect(out).toContain("b92266");
    // The mixed-case "F" in 0xf39F is preserved (would lower-case if buggy).
    expect(out.startsWith("0xf39F")).toBe(true);
  });
});

describe("chainBadgeClass", () => {
  it("uses chain-stable colour tokens", () => {
    expect(chainBadgeClass("solana")).toContain("violet");
    expect(chainBadgeClass("evm")).toContain("sky");
    expect(chainBadgeClass("ton")).toContain("cyan");
  });
});
