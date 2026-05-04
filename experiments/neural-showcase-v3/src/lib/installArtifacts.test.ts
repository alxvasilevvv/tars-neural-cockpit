import { describe, expect, it } from "vitest";

import type { DownloadManifest } from "./downloads";
import {
  artifactsForTab,
  formatArtifactSize,
  formatDisplayVersion,
  pickArtifactForTab,
  releaseUsesGithubUrls,
  resolvePrimaryFromManifest,
} from "./installArtifacts";

const sampleManifest: DownloadManifest = {
  ok: true,
  product: "tars",
  contract_version: "1.0.0",
  channel: "stable",
  released_at: "2026-04-22T00:00:00Z",
  source: "test",
  releases: [
    {
      version: "8.4.0",
      channel: "stable",
      released_at: "2026-04-22T00:00:00Z",
      notes: null,
      artifacts: [
        {
          os: "macos",
          arch: "arm64",
          kind: "dmg",
          filename: "TARS_8.4.0_aarch64.dmg",
          url: "https://github.com/org/repo/releases/download/v8.4.0/TARS_8.4.0_aarch64.dmg",
          size_bytes: 7000000,
          sha256: null,
          signature_url: null,
        },
        {
          os: "macos",
          arch: "x64",
          kind: "dmg",
          filename: "TARS_8.4.0_x64.dmg",
          url: "https://example.com/x64.dmg",
          size_bytes: null,
          sha256: null,
          signature_url: null,
        },
        {
          os: "linux",
          arch: "x64",
          kind: "appimage",
          filename: "TARS_8.4.0_amd64.AppImage",
          url: "https://example.com/a.ai",
          size_bytes: null,
          sha256: null,
          signature_url: null,
        },
        {
          os: "windows",
          arch: "x64",
          kind: "exe",
          filename: "TARS_8.4.0_x64-setup.exe",
          url: "https://example.com/setup.exe",
          size_bytes: null,
          sha256: null,
          signature_url: null,
        },
      ],
    },
  ],
};

describe("installArtifacts", () => {
  it("pickArtifactForTab resolves mac arm64", () => {
    const a = pickArtifactForTab(sampleManifest, "mac", "arm");
    expect(a?.filename).toBe("TARS_8.4.0_aarch64.dmg");
  });

  it("pickArtifactForTab resolves mac x64", () => {
    const a = pickArtifactForTab(sampleManifest, "mac", "x64");
    expect(a?.filename).toBe("TARS_8.4.0_x64.dmg");
  });

  it("pickArtifactForTab prefers AppImage on linux", () => {
    const a = pickArtifactForTab(sampleManifest, "linux", "arm");
    expect(a?.kind).toBe("appimage");
  });

  it("pickArtifactForTab prefers exe on windows", () => {
    const a = pickArtifactForTab(sampleManifest, "windows", "arm");
    expect(a?.kind).toBe("exe");
  });

  it("artifactsForTab filters by OS tab", () => {
    expect(artifactsForTab(sampleManifest, "mac")).toHaveLength(2);
    expect(artifactsForTab(sampleManifest, "linux")).toHaveLength(1);
    expect(artifactsForTab(sampleManifest, "windows")).toHaveLength(1);
    expect(artifactsForTab(null, "mac")).toHaveLength(0);
  });

  it("releaseUsesGithubUrls detects github release links", () => {
    expect(releaseUsesGithubUrls(sampleManifest)).toBe(true);
  });

  it("formatDisplayVersion adds v prefix when missing", () => {
    expect(formatDisplayVersion("8.4.0")).toBe("v8.4.0");
    expect(formatDisplayVersion("v9.0.0")).toBe("v9.0.0");
  });

  it("formatArtifactSize formats MB", () => {
    expect(formatArtifactSize(7000000, "—")).toMatch(/MB/);
    expect(formatArtifactSize(null, "~7 MB")).toBe("~7 MB");
  });

  it("resolvePrimaryFromManifest returns URL from manifest", () => {
    const r = resolvePrimaryFromManifest(sampleManifest, "mac", "arm");
    expect(r?.url).toContain("github.com");
    expect(r?.filename).toContain("aarch64");
  });
});
