/**
 * Maps `/api/product/downloads` manifest data onto the Install page.
 * Keeps the primary CTA aligned with the backend manifest (version + URLs)
 * instead of hard-coded GitHub paths that drift from production (B-001 audit).
 */

import type { DownloadManifest, ReleaseArtifact } from "./downloads";

export type InstallOsTab = "mac" | "linux" | "windows";

export function pickArtifactForTab(
  manifest: DownloadManifest | null,
  os: InstallOsTab,
  macArch: "arm" | "x64",
): ReleaseArtifact | null {
  if (!manifest?.releases?.length) return null;
  const arts = manifest.releases[0].artifacts;
  if (!arts.length) return null;

  if (os === "mac") {
    const arch = macArch === "arm" ? "arm64" : "x64";
    return (
      arts.find((a) => a.os === "macos" && a.arch === arch) ??
      arts.find((a) => a.os === "macos") ??
      null
    );
  }
  if (os === "linux") {
    return (
      arts.find((a) => a.os === "linux" && a.kind === "appimage") ??
      arts.find((a) => a.os === "linux" && a.kind === "deb") ??
      arts.find((a) => a.os === "linux") ??
      null
    );
  }
  return (
    arts.find((a) => a.os === "windows" && a.kind === "exe") ??
    arts.find((a) => a.os === "windows" && a.kind === "msi") ??
    arts.find((a) => a.os === "windows") ??
    null
  );
}

export function artifactsForTab(
  manifest: DownloadManifest | null,
  os: InstallOsTab,
): ReleaseArtifact[] {
  if (!manifest?.releases?.length) return [];
  return manifest.releases[0].artifacts.filter((a) => {
    if (os === "mac") return a.os === "macos";
    if (os === "linux") return a.os === "linux";
    return a.os === "windows";
  });
}

/** True when installers are served from GitHub Releases URLs (may 404 if repo is private). */
export function releaseUsesGithubUrls(manifest: DownloadManifest | null): boolean {
  if (!manifest?.releases?.length) return false;
  return manifest.releases[0].artifacts.some(
    (a) => a.url.includes("github.com") && a.url.includes("/releases/download/"),
  );
}

export function formatArtifactSize(bytes: number | null, fallback: string): string {
  if (bytes == null || bytes <= 0) return fallback;
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `~${kb < 10 ? kb.toFixed(1) : Math.round(kb)} KB`;
  const mb = kb / 1024;
  return `~${mb < 10 ? mb.toFixed(1) : Math.round(mb)} MB`;
}

export function formatDisplayVersion(version: string): string {
  return version.startsWith("v") ? version : `v${version}`;
}

export interface ResolvedInstallPrimary {
  url: string;
  filename: string;
  formatLabel: string;
  archLabel: string;
  sizeApprox: string;
}

export function resolvePrimaryFromManifest(
  manifest: DownloadManifest | null,
  os: InstallOsTab,
  macArch: "arm" | "x64",
): ResolvedInstallPrimary | null {
  const a = pickArtifactForTab(manifest, os, macArch);
  if (!a) return null;

  const archLabel =
    os === "mac"
      ? macArch === "arm"
        ? "Apple Silicon (M1/M2/M3/M4)"
        : "Intel x64"
      : "x86_64";

  return {
    url: a.url,
    filename: a.filename,
    formatLabel: a.kind.toUpperCase(),
    archLabel,
    sizeApprox: formatArtifactSize(a.size_bytes, "—"),
  };
}
