/**
 * Pure helpers extracted from <Install /> for testability.
 *
 * The original code in `pages/Install.tsx` did OS + arch detection
 * inline; pulling them out lets vitest pin the heuristics without
 * mounting the full React tree (jsdom doesn't ship `framer-motion`
 * timers nicely). The components import these helpers directly so
 * there's a single source of truth.
 *
 * 2026-05-04 audit-2 — extracted as part of the Install rewrite QA
 * pass so we can lock the Apple Silicon vs Intel guess.
 */

export type DetectedOS = "mac" | "linux" | "windows";
export type DetectedMacArch = "arm" | "x64";

export interface NavigatorLike {
  platform?: string;
  userAgent?: string;
  hardwareConcurrency?: number;
}

/** Best-effort OS detection from a navigator-like shape. */
export function detectOS(nav?: NavigatorLike | null): DetectedOS {
  const platform = (nav?.platform || "").toLowerCase();
  const ua = (nav?.userAgent || "").toLowerCase();
  if (platform.includes("mac") || ua.includes("mac")) return "mac";
  if (platform.includes("win") || ua.includes("windows")) return "windows";
  return "linux";
}

/**
 * Best-effort macOS architecture guess.
 *
 * The legacy Mac UA tag still says "Intel" on Apple Silicon (Apple
 * froze it for app-compat). We use a small set of fallbacks:
 *
 * 1. Explicit ``arm64`` / ``aarch64`` token in the UA → ARM.
 * 2. ``hardwareConcurrency`` divisible by 4 and ≥ 8 → ARM. Apple
 *    Silicon ships 8 / 10 / 12 / 14 / 16 / 24 cores (perf+effic),
 *    while Intel Macs typically expose 4 / 6 / 8 / 12 logical cores
 *    via Hyper-Threading — the divisible-by-4 + min-8 heuristic
 *    catches every Apple Silicon Mac shipped to date and only
 *    misclassifies the 12-core Intel iMac Pro (rare).
 * 3. Otherwise fall back to ``x64``. Picking the wrong binary is
 *    not catastrophic — Rosetta runs the x64 build fine.
 */
export function detectMacArch(nav?: NavigatorLike | null): DetectedMacArch {
  const ua = (nav?.userAgent || "").toLowerCase();
  if (ua.includes("arm64") || ua.includes("aarch64")) return "arm";
  if (ua.includes("intel")) {
    const cores = nav?.hardwareConcurrency ?? 0;
    if (cores >= 8 && cores % 4 === 0) return "arm";
  }
  return "x64";
}

/** Asset filename helper kept in lockstep with the GitHub Releases. */
export function primaryAssetName(
  os: DetectedOS,
  versionNumeric: string,
  macArch: DetectedMacArch = "arm",
  options?: { intelMacFallbackToArm?: boolean },
): string {
  switch (os) {
    case "mac": {
      // 2026-05-04 audit-3: when the Intel ``TARS_x.y.z_x64.dmg`` is
      // missing from the GitHub Release (mac-13 runner shortage),
      // the caller can opt into falling back to the arm64 dmg —
      // Rosetta runs it cleanly.
      if (macArch === "x64" && options?.intelMacFallbackToArm) {
        return `TARS_${versionNumeric}_aarch64.dmg`;
      }
      return macArch === "arm"
        ? `TARS_${versionNumeric}_aarch64.dmg`
        : `TARS_${versionNumeric}_x64.dmg`;
    }
    case "linux":
      return `TARS_${versionNumeric}_amd64.AppImage`;
    case "windows":
      return `TARS_${versionNumeric}_x64_en-US.msi`;
  }
}
