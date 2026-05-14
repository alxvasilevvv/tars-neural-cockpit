# Changelog — tars-tab

All notable changes to the **tars-tab** VS Code extension are
documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the version line is the **package.json** version and the date is
the build date, not the publish date (those can differ when a
release goes to Marketplace later than it's tagged).

## [0.1.0] — 2026-05-15

First public Marketplace release.

### Added

- **Chat view** in the activity bar — talks to the local TARS
  backend over `tars.backendUrl` (default `http://127.0.0.1:8765`).
  Supports streaming token-by-token responses.
- **Composer Plans view** — surfaces the latest composer drafts
  (W253 / W256 domain-pack-aware composer) so you can review
  agent-proposed edits without leaving the editor.
- **Receipts view** — last 50 signed action receipts pulled from
  the local backend, with one-click "verify" against the local
  hash chain.
- **Commands**
  - `tars.openChat` — opens the chat view and focuses input.
  - `tars.composeFromSelection` — sends the current editor
    selection to the composer with the active language as a
    domain-pack hint.
  - `tars.showReceipts` — focuses the receipts view.
- **Configuration**
  - `tars.backendUrl` — base URL of the local TARS backend.
    Defaults to `http://127.0.0.1:8765`. Change this if you
    moved the backend or are tunnelling to a remote instance.

### Known limitations (v0.1)

- No remote-only mode — extension assumes a local backend on
  `tars.backendUrl`. A SaaS-aware build is on the v0.2 roadmap.
- Receipt verification is read-only — the editor doesn't yet
  expose "anchor batch to Solana" buttons (use the cockpit).
- No bundled icon binary — `icon.png` is a placeholder; we ship
  the SVG-only Activity Bar icon until a 128×128 raster icon
  lands. See `icon.png` for the upgrade contract.

### Notes for first-time installers

- Requires VS Code **1.85.0** or newer.
- The extension is a **thin bridge**: with no local TARS running
  on `127.0.0.1:8765` you'll see a banner asking you to start the
  cockpit or change `tars.backendUrl`. No errors, no crash.
- We do not collect telemetry from the extension itself. Backend
  events follow the existing TARS data-plane mode (Normal /
  Local-only / Ephemeral).
