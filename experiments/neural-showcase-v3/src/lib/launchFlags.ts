/**
 * launchFlags.ts — single source of truth for "is feature X ready to ship?".
 *
 * Wave 68 — hide download buttons + install page CTAs until v9.1.0
 * installers are actually signed (Apple Developer ID notarisation +
 * Windows Authenticode + minisign updater key all populated in CI).
 * Flipping `INSTALLERS_READY` to `true` re-enables every download
 * surface across the site — no other code changes needed.
 *
 * When operator completes:
 *   - desktop/scripts/generate-release-keys.sh --patch-tauri-conf
 *   - GitHub Actions secrets: TAURI_SIGNING_PRIVATE_KEY{,_PASSWORD},
 *     APPLE_CERTIFICATE{,_PASSWORD}, APPLE_SIGNING_IDENTITY,
 *     APPLE_ID, APPLE_PASSWORD, APPLE_TEAM_ID,
 *     WINDOWS_CERTIFICATE{,_PASSWORD}
 *   - First successful CI release on `v9.1.0` tag with .sig files
 * → flip `INSTALLERS_READY` below to `true` and ship.
 *
 * The flag intentionally lives in code (not env) so a marketing-side
 * release toggle requires a code review + commit — prevents accidental
 * "Download TARS" surfacing of broken artefacts during ops drift.
 */

export const INSTALLERS_READY = false as const;

/**
 * Approximate launch ETA shown next to "Coming soon" UI. Keep loose
 * — operators care about week, not date. Update when there's a
 * confirmed CI release on a tag.
 */
export const INSTALLER_ETA = "soon" as const;
