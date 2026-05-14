# Quickstart — developing tars-tab

## What's in this folder

* `package.json` — extension manifest (commands, views, settings).
* `src/extension.ts` — activation, command handlers, HTTP helper.
* `src/chatView.ts` / `composerView.ts` / `receiptsView.ts` —
  `WebviewViewProvider` implementations for the activity-bar container.
* `media/tars-icon.svg` — activity bar icon.
* `scripts/PACKAGE-EXTENSION.command` — installs npm deps and runs
  `vsce package`.

## Get up and running

```bash
cd vscode-extension
npm install
npm run compile         # emits ./out
```

Press `F5` from VS Code with this folder open to launch an Extension
Development Host. The TARS icon should appear in the activity bar.

## Make changes

* Edit anything under `src/`.
* `npm run watch` keeps the TypeScript output fresh.
* `Cmd+R` in the Extension Development Host reloads the extension.

## Package

```bash
./scripts/PACKAGE-EXTENSION.command
```

Produces `tars-tab-0.1.0.vsix`. Install locally with:

```bash
code --install-extension tars-tab-0.1.0.vsix
```

## What backend endpoints we depend on

* `GET  /health`                 — reachability probe.
* `GET  /api/chat/embed`         — embedded HTML chat UI.
* `POST /api/composer/plan`      — transcript → plan (ops).
* `GET  /api/composer/plans`     — list recent plans.
* `GET  /api/receipts/recent`    — recent signed receipts
  (falls back to `GET /api/receipts?limit=20` if /recent is absent).

All other URLs are derived from the `tars.backendUrl` setting.
