/**
 * Pin the OS + Mac-arch detection used by /install (Bug audit
 * 2026-05-04). The heuristic was the riskiest piece of the new
 * Install rewrite — wrong arch picks an x64 binary on M-series
 * Macs (Rosetta runs it but it's slower) — so it gets a tight
 * test net here.
 */

import { describe, expect, it } from "vitest";
import {
  detectMacArch,
  detectOS,
  primaryAssetName,
  type NavigatorLike,
} from "./installDetect";

const VERSION = "9.1.0";

describe("detectOS", () => {
  it("returns 'mac' for Apple Silicon Safari", () => {
    const nav: NavigatorLike = {
      platform: "MacIntel",
      userAgent:
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605 Version/17.4 Safari/605",
    };
    expect(detectOS(nav)).toBe("mac");
  });

  it("returns 'mac' for Intel Mac Chrome", () => {
    const nav: NavigatorLike = {
      platform: "MacIntel",
      userAgent:
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537 Chrome/120 Safari/537",
    };
    expect(detectOS(nav)).toBe("mac");
  });

  it("returns 'windows' on Win10 Edge", () => {
    const nav: NavigatorLike = {
      platform: "Win32",
      userAgent:
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537 Edg/120 Safari/537",
    };
    expect(detectOS(nav)).toBe("windows");
  });

  it("returns 'linux' on Ubuntu Firefox", () => {
    const nav: NavigatorLike = {
      platform: "Linux x86_64",
      userAgent: "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Firefox/120",
    };
    expect(detectOS(nav)).toBe("linux");
  });

  it("returns 'linux' as the default when nothing matches", () => {
    expect(detectOS({ platform: "Plan9", userAgent: "9P" })).toBe("linux");
  });

  it("tolerates missing navigator", () => {
    expect(detectOS()).toBe("linux");
    expect(detectOS(null)).toBe("linux");
    expect(detectOS({})).toBe("linux");
  });
});

describe("detectMacArch", () => {
  it("explicit 'arm64' UA marker → arm", () => {
    expect(
      detectMacArch({
        userAgent:
          "Mozilla/5.0 (Macintosh; arm64 Mac OS X 14_0_0) AppleWebKit/605",
      }),
    ).toBe("arm");
  });

  it("'aarch64' UA marker → arm", () => {
    expect(
      detectMacArch({
        userAgent: "Some odd browser aarch64 Mac OS X",
      }),
    ).toBe("arm");
  });

  it("legacy 'Intel' UA + 8-core hardware → arm (Apple Silicon M1/M2 base)", () => {
    expect(
      detectMacArch({
        userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0_0)",
        hardwareConcurrency: 8,
      }),
    ).toBe("arm");
  });

  it("legacy 'Intel' UA + 12-core hardware → arm (Apple Silicon M-Pro)", () => {
    expect(
      detectMacArch({
        userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0_0)",
        hardwareConcurrency: 12,
      }),
    ).toBe("arm");
  });

  it("legacy 'Intel' UA + 4-core hardware → x64 (genuine 2017 Intel MBP)", () => {
    expect(
      detectMacArch({
        userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        hardwareConcurrency: 4,
      }),
    ).toBe("x64");
  });

  it("legacy 'Intel' UA + 6-core hardware → x64 (Intel hex-core)", () => {
    expect(
      detectMacArch({
        userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        hardwareConcurrency: 6,
      }),
    ).toBe("x64");
  });

  it("falls back to x64 when there's no signal at all", () => {
    expect(detectMacArch()).toBe("x64");
    expect(detectMacArch({})).toBe("x64");
  });
});

describe("primaryAssetName", () => {
  it("mac arm → aarch64.dmg", () => {
    expect(primaryAssetName("mac", VERSION, "arm")).toBe(
      "TARS_9.1.0_aarch64.dmg",
    );
  });

  it("mac x64 → x64.dmg", () => {
    expect(primaryAssetName("mac", VERSION, "x64")).toBe(
      "TARS_9.1.0_x64.dmg",
    );
  });

  it("linux → AppImage", () => {
    expect(primaryAssetName("linux", VERSION)).toBe(
      "TARS_9.1.0_amd64.AppImage",
    );
  });

  it("windows → MSI", () => {
    expect(primaryAssetName("windows", VERSION)).toBe(
      "TARS_9.1.0_x64_en-US.msi",
    );
  });

  it("intelMacFallbackToArm option swaps Intel dmg for arm64 dmg", () => {
    expect(
      primaryAssetName("mac", VERSION, "x64", {
        intelMacFallbackToArm: true,
      }),
    ).toBe("TARS_9.1.0_aarch64.dmg");
  });

  it("intelMacFallbackToArm has no effect for arm64 macs", () => {
    expect(
      primaryAssetName("mac", VERSION, "arm", {
        intelMacFallbackToArm: true,
      }),
    ).toBe("TARS_9.1.0_aarch64.dmg");
  });

  it("intelMacFallbackToArm has no effect for non-mac OSes", () => {
    expect(
      primaryAssetName("linux", VERSION, "x64", {
        intelMacFallbackToArm: true,
      }),
    ).toBe("TARS_9.1.0_amd64.AppImage");
  });
});
