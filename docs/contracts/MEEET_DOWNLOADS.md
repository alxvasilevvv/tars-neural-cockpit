# Contract — TARS download manifest (`/api/product/downloads`)

> **Owner:** Cursor agent (functional / backend).
> **Consumers:** marketing site (`neural-showcase-v3` Landing),
> **meeet.world** SSR shell, `tauri-plugin-updater` fallback poller.
> **Contract version:** `1.0.0` (pinned in
> `backend.core.product.manifest.CONTRACT_VERSION`).
> **Cache hint:** `Cache-Control: public, max-age=60`.

This document is the **handshake** between TARS and any surface that
needs to know "what's the latest installer". The wire format is small,
stable, and machine-readable so:

- the marketing site can render Download buttons without scraping HTML;
- **meeet.world** can embed the same manifest as part of its product
  shell without coupling to TARS internals;
- Tauri's auto-updater can keep using its own per-target endpoint
  (`https://meeet.world/updates/<target>/<current_version>.json`) while
  this manifest stays the human/marketing-facing source of truth.

## Endpoints

```
GET /api/product/downloads
GET /api/product/downloads/latest?os=<macos|windows|linux|ios|android>&channel=<stable|beta|nightly>
GET /api/product/version
```

All three are **read-only**, side-effect-free, and emit a permissive
`Cache-Control` so a CDN can sit in front. Responses always carry the
`X-Tars-Contract` header echoing `contract_version` so caches can
invalidate on a major bump.

## Wire shape — `/api/product/downloads`

```jsonc
{
  "ok": true,
  "product": "tars",
  "contract_version": "1.0.0",
  "channel": "stable",
  "released_at": "2026-04-29T00:00:00Z",
  "source": "file:/Users/.../releases.json",   // or "defaults"
  "releases": [
    {
      "version": "0.1.0-alpha.2",
      "channel": "stable",
      "released_at": "2026-04-29T00:00:00Z",
      "notes": "Phase M backbone — see RELEASE_NOTES.",
      "artifacts": [
        {
          "os": "macos",          // macos | windows | linux | ios | android
          "arch": "arm64",        // arm64 | x64 | x86 | universal | any
          "kind": "dmg",          // dmg | pkg | app | exe | msi | appimage | deb | ipa | apk | aab
          "filename": "TARS-0.1.0-alpha.2-arm64.dmg",
          "size_bytes": null,     // null until the build pipeline fills it
          "sha256": null,         // hex, optional
          "url": "https://meeet.world/downloads/tars/0.1.0-alpha.2/TARS-0.1.0-alpha.2-arm64.dmg",
          "signature_url": null   // optional — Apple .dmg.sig / Authenticode side-car
        }
      ]
    }
  ]
}
```

Notes:

1. `releases` is **newest-first**. Consumers should treat
   `releases[0]` as "latest in channel".
2. `source: "defaults"` means the backend has no `releases.json` on
   disk yet (v1 ships with a placeholder so the marketing site never
   hard-fails); replace it by writing the real file (see below).
3. URLs may be **absolute** (`https://...`) or **relative paths**;
   relative paths are resolved against `TARS_DOWNLOAD_BASE_URL` at
   read-time on the server, so consumers always see absolute URLs.

## Wire shape — `/api/product/downloads/latest?os=…`

```jsonc
{
  "ok": true,
  "product": "tars",
  "contract_version": "1.0.0",
  "release": {
    "version": "0.1.0-alpha.2",
    "channel": "stable",
    "released_at": "2026-04-29T00:00:00Z",
    "notes": "Phase M backbone — see RELEASE_NOTES.",
    "artifacts": [ /* same shape as above, filtered if relevant */ ]
  }
}
```

Filter rules:

- `os` (optional) — must be one of the values above; returns the
  newest release that has at least one matching artifact. **400** on
  unknown values.
- `channel` (optional) — exact match against `release.channel`.

If no release matches the filters, returns **404
`{"detail":"no_release_for_filters"}`** so the marketing site can fall
back to a "coming soon" pill.

## Wire shape — `/api/product/version`

Minimal probe used by Tauri updater fallbacks and uptime monitors:

```json
{
  "ok": true,
  "product": "tars",
  "contract_version": "1.0.0",
  "channel": "stable",
  "version": "0.1.0-alpha.2"
}
```

## Source of truth — `releases.json`

The manifest is loaded from disk at request time:

- Path: `$TARS_RELEASES_PATH` (default: `~/.tars/releases.json`).
- Format: same JSON as `/api/product/downloads`, **without** the `ok`
  / `source` keys (those are added by the router).
- Missing or malformed → falls back to the bundled `DEFAULT_MANIFEST`.

Example minimal `releases.json`:

```json
{
  "product": "tars",
  "contract_version": "1.0.0",
  "channel": "stable",
  "released_at": "2026-05-01T00:00:00Z",
  "releases": [
    {
      "version": "1.0.0",
      "channel": "stable",
      "released_at": "2026-05-01T00:00:00Z",
      "notes": "First stable. macOS notarised, Windows Authenticode-signed.",
      "artifacts": [
        {
          "os": "macos",  "arch": "arm64", "kind": "dmg",
          "filename": "TARS-1.0.0-arm64.dmg",
          "url": "/releases/1.0.0/TARS-1.0.0-arm64.dmg",
          "size_bytes": 92321312,
          "sha256": "deadbeef...32 bytes hex...",
          "signature_url": "/releases/1.0.0/TARS-1.0.0-arm64.dmg.sig"
        },
        {
          "os": "macos",  "arch": "x64",   "kind": "dmg",
          "filename": "TARS-1.0.0-x64.dmg",
          "url": "/releases/1.0.0/TARS-1.0.0-x64.dmg"
        },
        {
          "os": "windows","arch": "x64",   "kind": "exe",
          "filename": "TARS-1.0.0-Setup.exe",
          "url": "/releases/1.0.0/TARS-1.0.0-Setup.exe"
        }
      ]
    }
  ]
}
```

## Environment variables

| Var | Purpose | Default |
|-----|---------|---------|
| `TARS_RELEASES_PATH` | Path to the manifest file. | `~/.tars/releases.json` |
| `TARS_DOWNLOAD_BASE_URL` | Base URL to prefix relative artifact paths with at request time. | (unset → returns paths as-is) |

## Validation rules

The loader is **soft-failing**: invalid artifacts / releases are
**dropped with a `WARNING`**, not 5xx'd. Specifically:

- `os` must be one of `macos | windows | linux | ios | android`.
- `arch` must be one of `arm64 | x64 | x86 | universal | any`.
- `kind` must be one of `dmg | pkg | app | exe | msi | appimage | deb | ipa | apk | aab`.
- `version`, `filename`, `url` are required strings.
- `sha256` (if present) must be hex; not enforced by the loader yet
  (UI / updater enforce on download).

## meeet.world integration recipe

Server-side render in **meeet.world** (whichever framework lives there):

```ts
const r = await fetch("https://app.meeet.world/api/product/downloads", {
  next: { revalidate: 60 },          // Next.js ISR-style cache
});
if (!r.ok) throw new Error("download manifest unavailable");
const manifest: DownloadManifest = await r.json();
const latest = manifest.releases[0];
const macos = latest.artifacts.find(a => a.os === "macos" && a.arch === "arm64");
```

Render the version string from `latest.version` and link the artifact
URLs straight from the manifest — no other coupling required.

## Versioning policy

- The **major** of `contract_version` is the contract barrier.
  Consumers must reject manifests whose major doesn't match the major
  they were compiled against (`tauri-plugin-updater` should keep using
  its dedicated per-target endpoint regardless).
- Adding new optional artifact fields = **minor** bump
  (`1.0.0 → 1.1.0`).
- Renaming or removing fields = **major** bump.

## Changelog

- `1.0.0` (2026-04-29) — initial shape; macOS, Windows, Linux, iOS,
  Android targets supported.
