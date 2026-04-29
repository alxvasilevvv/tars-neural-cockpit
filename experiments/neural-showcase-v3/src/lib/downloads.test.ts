/**
 * Tests for `lib/downloads.ts` — UA detection + artifact picking.
 * Phase L9: nail the platform detection edges so the wrong CTA never
 * appears in production.
 */

import { describe, expect, it } from "vitest";

import {
  detectPlatform,
  pickArtifact,
  type DownloadManifest,
  type ReleaseArtifact,
} from "./downloads";

// --------------------------------------------------------------------
// detectPlatform
// --------------------------------------------------------------------

const UAS = {
  macSafariARM:
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
  macChromeARM:
    "Mozilla/5.0 (Macintosh; Apple Silicon Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  macIntel:
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_2_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  windows10:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  ubuntu:
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  iphone:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Version/17.4 Mobile/15E148 Safari/604.1",
  pixel:
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
  unknown: "Mozilla/5.0 (PlayStation; PlayStation 5)",
};

describe("detectPlatform", () => {
  it("flags macOS Apple Silicon when UA hints aarch64/apple silicon", () => {
    const out = detectPlatform(UAS.macChromeARM);
    expect(out.os).toBe("macos");
    expect(out.arch).toBe("arm64");
    expect(out.label).toContain("Apple silicon");
  });

  it("falls back to macOS Intel when no arm hint is present", () => {
    const out = detectPlatform(UAS.macIntel);
    expect(out.os).toBe("macos");
    expect(out.arch).toBe("x64");
    expect(out.label).toContain("Intel");
  });

  it("detects Windows", () => {
    const out = detectPlatform(UAS.windows10);
    expect(out).toMatchObject({ os: "windows", arch: "x64" });
  });

  it("detects Linux", () => {
    const out = detectPlatform(UAS.ubuntu);
    expect(out.os).toBe("linux");
  });

  it("detects iOS (iPhone)", () => {
    const out = detectPlatform(UAS.iphone);
    expect(out.os).toBe("ios");
    expect(out.arch).toBe("arm64");
  });

  it("detects Android (Pixel)", () => {
    const out = detectPlatform(UAS.pixel);
    expect(out.os).toBe("android");
    expect(out.arch).toBe("arm64");
  });

  it("returns unknown for esoteric UAs", () => {
    const out = detectPlatform(UAS.unknown);
    expect(out.os).toBe("unknown");
    expect(out.label).toBe("your device");
  });
});

// --------------------------------------------------------------------
// pickArtifact
// --------------------------------------------------------------------

function makeManifest(arts: Partial<ReleaseArtifact>[]): DownloadManifest {
  const full: ReleaseArtifact[] = arts.map((a) => ({
    os: "macos",
    arch: "arm64",
    kind: "dmg",
    filename: "f.dmg",
    url: "https://example/f.dmg",
    size_bytes: null,
    sha256: null,
    signature_url: null,
    ...a,
  }));
  return {
    ok: true,
    product: "tars",
    contract_version: "1.0.0",
    channel: "stable",
    released_at: "2026-04-29T00:00:00Z",
    source: "test",
    releases: [
      {
        version: "1.0.0",
        channel: "stable",
        released_at: "2026-04-29T00:00:00Z",
        notes: null,
        artifacts: full,
      },
    ],
  };
}

describe("pickArtifact", () => {
  it("picks the exact arch match", () => {
    const m = makeManifest([
      { os: "macos", arch: "arm64", filename: "arm.dmg" },
      { os: "macos", arch: "x64", filename: "x64.dmg" },
    ]);
    const out = pickArtifact(m, { os: "macos", arch: "arm64", label: "macOS" });
    expect(out?.filename).toBe("arm.dmg");
  });

  it("falls back to universal then any when arch doesn't match", () => {
    const m = makeManifest([
      { os: "macos", arch: "universal", filename: "universal.dmg" },
      { os: "macos", arch: "any", filename: "any.dmg" },
    ]);
    const out = pickArtifact(m, { os: "macos", arch: "x86", label: "macOS" });
    expect(out?.filename).toBe("universal.dmg");
  });

  it("returns null when there's no artifact for the OS", () => {
    const m = makeManifest([{ os: "macos", arch: "arm64" }]);
    const out = pickArtifact(m, { os: "windows", arch: "x64", label: "Windows" });
    expect(out).toBeNull();
  });

  it("returns null when detection is unknown", () => {
    const m = makeManifest([{ os: "macos", arch: "arm64" }]);
    const out = pickArtifact(m, { os: "unknown", arch: "any", label: "x" });
    expect(out).toBeNull();
  });

  it("handles a missing manifest gracefully", () => {
    expect(pickArtifact(null, { os: "macos", arch: "arm64", label: "macOS" })).toBeNull();
  });
});
