# Wave 59 — Desktop native UX + ScrollStory fix · sign-off

**Owner:** Claude (Cowork window)
**Date:** 2026-05-05
**Branch:** `main` (uncommitted; commit script `scripts/commit_wave_59.sh` will land it)
**Lane:** desktop shell (Tauri 2 + Rust) + cockpit hook (TS) — clean separation from Cursor's backend lane.

---

## What this wave delivers

The Tauri 2 desktop shell shipped in Phase L9 v1 was functional but minimal — a window pointing at the cockpit React app plus a Python sidecar lifecycle manager. Wave 59 layers the native macOS/Windows behaviours that make TARS stop feeling like a Chromium wrapper and start feeling like a real desktop app.

Plus one cockpit-side regression fix from a user screenshot.

## Cockpit fix — ScrollStory edge-segment opacity

User reported (screenshot) a huge black space in the section "04 · How it works · Four ways TARS pays for itself before lunch". The pinned-scroll storytelling component owns 400vh of scroll, but the per-segment fade-in/fade-out opacity ranges `[start - 0.04, peak, end + 0.04] → [0, 1, 0]` meant:

- **First segment:** `start = 0`, so at scroll=0 (top of section pinning) opacity was 0 — operator saw an empty pinned area until they had scrolled enough to fade the first segment in.
- **Last segment:** faded to 0 *before* the section unpinned — empty area at section exit too.

**Fix** (`experiments/neural-showcase-v3/src/components/ScrollStory.tsx`):

```ts
const isFirst = index === 0;
const isLast = index === segmentCount - 1;
const startScroll = isFirst ? 0 : Math.max(0, start - 0.04);
const endScroll = isLast ? 1 : Math.min(1, end + 0.04);
const opacity = useTransform(
  scrollYProgress,
  [startScroll, peak, endScroll],
  [isFirst ? 1 : 0, 1, isLast ? 1 : 0],
);
const y = useTransform(
  scrollYProgress,
  [startScroll, peak, endScroll],
  [isFirst ? 0 : 16, 0, isLast ? 0 : -16],
);
```

Same pattern in `VisualPane`. Middle segments unchanged.

## Desktop native features — what landed

### 1. Window state persistence

`tauri-plugin-window-state` 2.0 added to `Cargo.toml`, registered in `main.rs` *before* the window is created (so it can hydrate saved state). User's last size + position survives quit-and-relaunch. No additional code; the plugin handles save-on-resize/move + restore-on-launch automatically.

### 2. System tray icon + menu

Native menu bar (macOS) / system tray (Windows/Linux). Built with Tauri 2's core `tray-icon` feature (no plugin):

- **Left-click on the icon** → toggle the main window (Spotlight-style — visible+focused → hide; otherwise show+focus+unminimize).
- **Right-click on the icon** → context menu with two items: "Show TARS" (focuses the window) and "Quit TARS" (clean shutdown via `app.exit(0)`).
- **Tooltip:** "TARS — local-first neural cockpit".
- **Icon:** uses the app's default window icon (already in `src-tauri/icons/`).

### 3. Global shortcut

`tauri-plugin-global-shortcut` 2.0. Cmd+Shift+Space (macOS) / Ctrl+Shift+Space (Windows/Linux) toggles the main window from anywhere — same handler as the tray click. If the OS denies the registration (e.g. another app already owns the combo), a `tars.desktop.shortcut.register_failed` warning is logged but boot proceeds. Future iteration: surface a settings panel where the user can rebind the chord.

### 4. Deep link routing — `tars://`

Two layers:

**Rust side** (`desktop/src-tauri/src/main.rs` + `tauri.conf.json` plugins.deep-link.desktop.schemes): registers the `tars` scheme on app install, captures both **cold-start** (app launched via deep link) and **warm-arrival** (app already running) URLs, focuses the main window, and emits a `tars://deeplink` event with the URL array as payload.

**Cockpit side** (`experiments/neural-showcase-v3/src/lib/useTarsDeepLink.ts` + `App.tsx`): the `useTarsDeepLink()` hook is mounted in `<AppShell />`. It detects whether we're in a Tauri runtime (via `window.__TAURI_INTERNALS__`) — if not, it's a no-op (browser builds don't fire). When in Tauri, it dynamically imports `@tauri-apps/api/event`, listens for `tars://deeplink`, parses the URL via `parseTarsUrl()`, and navigates via React Router.

Routing table:

| `tars://` URL                           | React Router target                         |
|-----------------------------------------|---------------------------------------------|
| `tars://onboarding`                     | `/onboarding`                               |
| `tars://onboarding?role=founder`        | `/onboarding?role=founder`                  |
| `tars://login`                          | `/onboarding` (alias for magic-link land)   |
| `tars://cockpit`                        | `/cockpit`                                  |
| `tars://thread/abc123`                  | `/cockpit?thread=abc123`                    |
| `tars://settings`                       | `/cockpit?panel=settings`                   |
| anything else                           | `console.warn` + no-op                      |

This unblocks the meeet.world ↔ TARS handshake: a magic-link email can land users straight into the right cockpit pane.

### 5. Pre-flight build gate

`desktop/scripts/preflight-build.sh` (new). Three checks:

1. **`src-tauri/web/` populated.** Catches the silent blank-window failure mode where `tauri build` succeeds but the bundled installer opens to an empty Chromium window because the cockpit dist wasn't copied. Asserts `index.html` exists *and* `assets/` has ≥5 chunks (catches partial/stale builds too).
2. **Icons present.** All five referenced icon files exist before Tauri tries to build the bundle.
3. **Updater pubkey** (release mode only). Fails if `tauri.conf.json` still has `TODO_PUBLIC_KEY` in `--release` mode. Dev mode tolerates the placeholder so contributors can iterate without minisign keys.

Wired into `pnpm release` chain via `package.json`:

```json
"release": "pnpm cockpit:build && pnpm cockpit:package && pnpm preflight:release && pnpm tauri:build"
```

Standalone invocation: `bash desktop/scripts/preflight-build.sh` (dev) or `--release` (full gate).

### 6. Stale TODO cleanup

- `desktop/README.md` L54 — old comment claimed `sidecar.rs ← TODO: bring up FastAPI` even though the sidecar shipped in Phase L9 A1. Updated to describe the actual responsibility.
- `desktop/README.md` Status section — added the Wave 59 features so the status reflects reality.
- `tauri.conf.json` `TODO_PUBLIC_KEY` is **intentionally** left in place — `desktop/scripts/updater-pubkey-status.sh` exists specifically to detect that placeholder and warn before release; replacing it would break the existing flow.

### 7. Download URL drift

`.env.example` `TARS_DOWNLOAD_BASE_URL` was `https://meeet.world/downloads/tars` — that path was never hosted (404). CI publishes installers + `latest.json` to GitHub Releases. Switched the default to the actual location with a multi-line comment explaining the proxy plan (when meeet.world hosts a 1st-party mirror, operators can swap back without recompiling).

### Capabilities manifest

`desktop/src-tauri/capabilities/default.json` (new) declares permissions for the new plugins, scoped to the `main` window. No widening of the security envelope beyond what the new features require:

```json
"permissions": [
  "core:default",
  "core:window:default",
  "core:window:allow-show",
  "core:window:allow-hide",
  "core:window:allow-set-focus",
  "core:window:allow-unminimize",
  "shell:default",
  "notification:default",
  "updater:default",
  "window-state:default",
  "global-shortcut:allow-register",
  "global-shortcut:allow-unregister",
  "global-shortcut:allow-is-registered",
  "deep-link:default"
]
```

## What was *not* touched

- **Backend lane** (`backend/`, `web_extras/`, `tests/`, `Makefile`, `scripts/` outside desktop) — Cursor's lane.
- **Pyoxidizer vs pyinstaller CI parity** — recon flagged the discrepancy. Out of Wave 59 scope; needs CI workflow rewrite + cross-target test matrix. Track for a future wave.
- **Apple Developer ID / Authenticode signing infrastructure** — needs operator's accounts + cert purchases. Wave 59 leaves the signing scripts (`generate-release-keys.sh`, `sign-artifacts.sh`, `updater-pubkey-status.sh`) untouched and ready for when the operator runs them locally.
- **Native menu bar (File / Edit / View)** — kept out of scope. The macOS `titleBarStyle: "Overlay"` already deals with chrome cleanly; adding a full native menu would conflict and adds drift between platforms. Can be added later as a separate wave if needed.

## Verification

Sandbox-side: I cannot compile Rust here (no toolchain + no network for `cargo fetch`). All changes were checked for syntactic correctness against the documented Tauri 2.0 API surface. The diff is small enough that `cargo check` on the operator's machine should reveal any drift immediately:

```bash
cd desktop/src-tauri
cargo check
```

Cockpit-side TypeScript should compile without TS errors — the dynamic `@tauri-apps/api/event` import is the only browser-vs-Tauri ambiguity, and it's gated by `__TAURI_INTERNALS__` so Vite browser builds never reach it.

End-to-end manual test (operator's machine):

```bash
cd desktop
pnpm install
pnpm tauri:dev          # window opens; tray icon visible; window state survives close+open
                        # Cmd+Shift+Space toggles
                        # `open tars://onboarding?role=founder` from terminal routes correctly
pnpm preflight          # should pass (web/ already populated)
```

For the deep-link macOS test specifically: in development the `tars://` scheme registration may not stick for transient builds. Final verification belongs to a release-mode test once a signed installer is built.

## Launch impact

**Cockpit fix** is launch-blocking (visible empty section was breaking the marketing page first impression). Already in working tree.

**Desktop features** are NOT launch-blocking — TARS can ship the v1 .dmg/.msi without them. They turn first-week impressions from "is this even a real app?" into "this thinks like a Mac app". Recommend shipping in v9.1.1 or v9.2 patch following launch.

— Claude
