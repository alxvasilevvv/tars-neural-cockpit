# tars-tab — TARS inside VS Code

A thin bridge between [VS Code](https://code.visualstudio.com/) and the
local [TARS](https://github.com/meeet-world/tars) backend. TARS itself
keeps running as the Mac app (or any process bound to
`127.0.0.1:8765`); this extension just surfaces chat, the voice
composer, and signed receipts inside the editor so you don't have to
alt-tab away while coding.

> This is **not** a full Cursor clone. It does not embed a model. It is
> a bridge — the backend does all the work.

## Install

```bash
code --install-extension tars-tab-0.1.0.vsix
```

Or open VS Code → `Extensions` → `…` → `Install from VSIX…` and pick
the `.vsix` produced by the build script below.

You also need TARS itself running:

- macOS: launch **TARS.app**, or
- any platform: start the backend with `make backend` (binds to
  `127.0.0.1:8765` by default).

## Configure

By default the extension talks to `http://127.0.0.1:8765`. Override
this in `settings.json`:

```jsonc
{
  "tars.backendUrl": "http://127.0.0.1:8765"
}
```

Useful when you've tunneled the backend over SSH, are running it on a
different port, or are pointing at a staging environment.

## Commands

All three live under the `TARS:` category in the command palette
(`Cmd+Shift+P`).

| Command | What it does |
| --- | --- |
| `TARS: Open Chat` | Opens a Webview panel pointing at `${backend}/api/chat/embed`. If the backend is down, you get a one-button "Launch TARS.app" fallback that opens the `tars://` deep link. |
| `TARS: Compose Edit From Selection` | Grabs the active selection, asks you what to do, POSTs to `/api/composer/plan`, then walks you through each generated op as a native **VS Code diff editor**. Approve/reject the plan itself from the TARS.app Composer panel. |
| `TARS: Show Recent Receipts` | Focuses the TARS activity-bar container and renders the most recent receipts (signed, hash-chained, optionally Solana-anchored) from `/api/receipts/recent` (falls back to `/api/receipts?limit=20` for older backends). |

The activity bar gets a TARS container with three side-panel views —
**Chat**, **Composer Plans**, **Receipts** — that mirror the same
endpoints. Each one falls back gracefully to "TARS backend not
running. Launch TARS.app." if the backend is unreachable.

## Limitations

- Requires TARS.app (or `make backend`) to be running. There is **no
  offline mode** yet — without the backend, every view shows the
  fallback page.
- The composer command opens diffs but does **not** apply them. Use
  TARS.app's Composer panel to approve/reject — the receipt of the
  decision is part of the value.
- Webviews use a sandboxed iframe; cookies / localStorage are
  isolated. Voice still happens in TARS.app, not in VS Code.
- No telemetry, no model calls, no marketplace integration shipped in
  0.1.0.

## Build

```bash
cd vscode-extension
./scripts/PACKAGE-EXTENSION.command
```

Produces `tars-tab-0.1.0.vsix` in the extension folder.

## Distribution plan

For 0.1.x we ship the `.vsix` alongside TARS releases and link it from
the docs ("Install in your editor"). Publishing to the VS Code
Marketplace happens after we (a) finalize the publisher account on the
`meeet-world` org and (b) have at least one user-visible iteration past
this scaffold.
