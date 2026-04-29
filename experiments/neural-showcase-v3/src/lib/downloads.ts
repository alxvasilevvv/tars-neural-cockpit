/**
 * Download manifest client (Phase L9 / website CTAs).
 *
 * Hits `GET /api/product/downloads`, picks the right artifact for the
 * visiting browser's platform, and exposes a typed React hook the
 * Landing buttons can consume. The wire shape is pinned by
 * `docs/contracts/MEEET_DOWNLOADS.md`.
 *
 * Detection rules (mirrors what Slack / Cursor do):
 *   - macOS Apple Silicon  → arm64 dmg
 *   - macOS Intel          → x64 dmg
 *   - Windows              → x64 exe
 *   - everything else      → keep the manifest, render "all installers"
 */

import { useEffect, useMemo, useState } from "react";

import { API_BASE } from "./api";

export type ArtifactOS = "macos" | "windows" | "linux" | "ios" | "android";
export type ArtifactArch = "arm64" | "x64" | "x86" | "universal" | "any";
export type ArtifactKind =
  | "dmg" | "pkg" | "app"
  | "exe" | "msi"
  | "appimage" | "deb"
  | "ipa" | "apk" | "aab";

export interface ReleaseArtifact {
  os: ArtifactOS;
  arch: ArtifactArch;
  kind: ArtifactKind;
  filename: string;
  url: string;
  size_bytes: number | null;
  sha256: string | null;
  signature_url: string | null;
}

export interface ReleaseEntry {
  version: string;
  channel: "stable" | "beta" | "nightly";
  released_at: string;
  notes: string | null;
  artifacts: ReleaseArtifact[];
}

export interface DownloadManifest {
  ok: boolean;
  product: "tars";
  contract_version: string;
  channel: ReleaseEntry["channel"];
  released_at: string;
  source: string;
  releases: ReleaseEntry[];
}

export async function fetchManifest(
  signal?: AbortSignal,
): Promise<DownloadManifest> {
  const r = await fetch(`${API_BASE}/api/product/downloads`, { signal });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as DownloadManifest;
}

// --------------------------------------------------------------------
// Platform detection — runs once at module load.
// --------------------------------------------------------------------

export interface DetectedPlatform {
  os: ArtifactOS | "unknown";
  arch: ArtifactArch;
  label: string;
}

export function detectPlatform(ua: string = navigator.userAgent): DetectedPlatform {
  const lower = ua.toLowerCase();
  // Check mobile/iOS *before* macOS (iPhone UA contains "Mac OS X")
  // and *before* Linux (Android UA contains "Linux").
  if (lower.includes("iphone") || lower.includes("ipad")) {
    return { os: "ios", arch: "arm64", label: "iOS" };
  }
  if (lower.includes("android")) {
    return { os: "android", arch: "arm64", label: "Android" };
  }
  if (lower.includes("mac os") || lower.includes("macintosh")) {
    // Apple Silicon hint — Safari on M-series sometimes spoofs Intel
    // in the UA. We bias to arm64 when explicit hints fire, otherwise
    // x64. `navigator.userAgentData` (where present) gives a stronger
    // signal than the legacy UA string.
    const arm =
      /arm|apple silicon|aarch64/.test(lower) ||
      (typeof navigator !== "undefined" &&
        "userAgentData" in navigator &&
        (navigator as any).userAgentData?.platform === "macOS");
    return {
      os: "macos",
      arch: arm ? "arm64" : "x64",
      label: arm ? "macOS · Apple silicon" : "macOS · Intel",
    };
  }
  if (lower.includes("windows")) {
    return { os: "windows", arch: "x64", label: "Windows" };
  }
  if (lower.includes("linux")) {
    return { os: "linux", arch: "x64", label: "Linux" };
  }
  return { os: "unknown", arch: "any", label: "your device" };
}

export function pickArtifact(
  manifest: DownloadManifest | null,
  detected: DetectedPlatform,
): ReleaseArtifact | null {
  if (!manifest || manifest.releases.length === 0) return null;
  const release = manifest.releases[0];
  if (detected.os === "unknown") return null;
  // exact arch match wins; fall back to "any" / "universal"
  const matches = release.artifacts.filter((a) => a.os === detected.os);
  if (!matches.length) return null;
  return (
    matches.find((a) => a.arch === detected.arch) ??
    matches.find((a) => a.arch === "universal") ??
    matches.find((a) => a.arch === "any") ??
    matches[0]
  );
}

// --------------------------------------------------------------------
// React hook
// --------------------------------------------------------------------

export interface UseDownloadsState {
  manifest: DownloadManifest | null;
  primary: ReleaseArtifact | null;
  detected: DetectedPlatform;
  loading: boolean;
  error: string | null;
  /** All artifacts in the latest release, useful for an "all installers" panel. */
  artifacts: ReleaseArtifact[];
}

export function useDownloads(): UseDownloadsState {
  const [manifest, setManifest] = useState<DownloadManifest | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const detected = useMemo<DetectedPlatform>(
    () => (typeof navigator === "undefined" ? { os: "unknown", arch: "any", label: "your device" } : detectPlatform()),
    [],
  );

  useEffect(() => {
    const ctrl = new AbortController();
    fetchManifest(ctrl.signal)
      .then((m) => {
        setManifest(m);
        setLoading(false);
      })
      .catch((exc) => {
        if ((exc as Error)?.name === "AbortError") return;
        setError(String((exc as Error)?.message ?? exc));
        setLoading(false);
      });
    return () => ctrl.abort();
  }, []);

  return useMemo<UseDownloadsState>(() => {
    const primary = pickArtifact(manifest, detected);
    const artifacts = manifest?.releases?.[0]?.artifacts ?? [];
    return { manifest, primary, detected, loading, error, artifacts };
  }, [manifest, detected, loading, error]);
}
