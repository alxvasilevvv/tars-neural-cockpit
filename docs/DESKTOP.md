# TARS desktop — operator guide

This guide covers the **desktop app** specifically — the `.dmg` (macOS) / `.msi` / `.exe` (Windows) / `.AppImage` / `.deb` (Linux) installers built from this repo. For the web version (`tars.meeet.world`) and the underlying CLI, see `README.md` and `INSTALL.md`.

## What you get

TARS desktop is a Tauri 2 wrapper around two things:

- **Neural cockpit** — the same React UI you see on `tars.meeet.world/cockpit`, built fresh into the bundle for offline-first.
- **FastAPI sidecar** — a Python child process that boots automatically on `127.0.0.1:8765` and serves `/health`, `/api/*`, websocket streams. Bundled as a single binary (pyoxidizer) so the user doesn't need a Python install.

Everything works locally by default. No login required to use the app — sign-in only matters when you want $MEEET payments / cross-device sync / authoritative billing on `meeet.world`.

## Install

```bash
# Choose your platform's installer:
open TARS-9.1.0-universal.dmg          # macOS
TARS-9.1.0-Setup.exe                   # Windows
chmod +x TARS-9.1.0-x86_64.AppImage    # Linux portable
sudo dpkg -i TARS-9.1.0-amd64.deb      # Linux .deb
```

Direct downloads: <https://github.com/alxvasilevvv/tars-neural-cockpit/releases/latest>

After install, just launch TARS from Applications / Start Menu / your launcher. The sidecar boots automatically; you'll see a brief "Starting backend…" pill in the bottom-left corner, then "Backend ready · :8765" for ~2.5 s, then it disappears.

## Native features (Wave 59)

### Window state persistence

TARS remembers where you left it. Move and resize the window — close + relaunch — same spot, same size. No setting to toggle; the plugin (`tauri-plugin-window-state`) handles it transparently. State lives at:

- macOS: `~/Library/Application Support/world.meeet.tars/.window-state.json`
- Windows: `%APPDATA%\world.meeet.tars\.window-state.json`
- Linux: `~/.local/share/world.meeet.tars/.window-state.json`

Delete the file to reset to the centred 1440 × 900 default.

### Menu bar / system tray icon

A small TARS icon lives in your menu bar (macOS) or system tray (Windows / Linux):

- **Left-click the icon** → toggle the main window. If it's hidden or in the background, it pops to front. If it's already focused, it hides (handy for parking TARS while keeping the sidecar running).
- **Right-click the icon** → mini menu:
  - **Show TARS** — same as a left-click, explicit.
  - **Quit TARS** — clean shutdown. The sidecar gets a SIGTERM (5 s grace) then SIGKILL; receipts are flushed and the app exits.

Tooltip on hover: "TARS — local-first neural cockpit".

### Global shortcut — `Cmd+Shift+Space` / `Ctrl+Shift+Space`

Anywhere on your machine — even with TARS hidden — the chord summons the main window. Same toggle semantics as the tray click (visible+focused → hide; otherwise show + focus + unminimize). Spotlight / Raycast / Alfred-style.

If your OS denies the registration (because another app already owns the same combo), TARS logs `tars.desktop.shortcut.register_failed` and starts without the shortcut. Quit the conflicting app and relaunch TARS to retry.

Future iteration will surface a settings panel where you can rebind. For now the chord is fixed.

### Deep links — `tars://`

The `tars://` URL scheme is registered system-wide on first launch. From Terminal:

```bash
open "tars://onboarding?role=founder"
open "tars://thread/abc123"
open "tars://cockpit"
open "tars://settings"
```

…or from any browser link, email, or another app. The handler:

1. **Cold start:** TARS launches and routes to the URL.
2. **Warm arrival:** TARS focuses, then routes to the URL.

Supported verbs:

| URL                                | Lands on                                          |
|------------------------------------|---------------------------------------------------|
| `tars://onboarding`                | First-run wizard                                  |
| `tars://onboarding?role=founder`   | First-run wizard, founder role pre-picked         |
| `tars://login`                     | Magic-link landing (alias of onboarding)          |
| `tars://cockpit`                   | Main cockpit                                      |
| `tars://thread/<id>`               | Cockpit, deep-linked to a thread                  |
| `tars://settings`                  | Standalone Settings page (`/settings`)            |

Anything else logs a `tars.unknown.deeplink` warning in the console and stays on the current page.

### Sidecar status indicator

If the FastAPI sidecar fails to boot (`spawn` failure, health-check timeout, or premature exit), a small amber banner appears bottom-left with:

- The failure stage (`spawn failed` / `didn't respond` / `exited too early`)
- The error message (truncated to 140 chars)
- A "troubleshooting →" link

If the sidecar was running and *crashes mid-session*, the banner turns red and reads "backend crashed" with the exit code or signal. In that case relaunch TARS — the sidecar will spawn fresh.

## Updates

Tauri's auto-updater is configured to check `https://github.com/.../releases/latest/download/latest.json` on launch. When a new signed release is available, the app silently downloads it and applies on next quit. There is no in-app prompt yet; that lands in a future wave.

To force-check now: relaunch TARS. To freeze on a specific version, disable network or use the offline `.AppImage`.

## Troubleshooting

### "Backend didn't respond" amber banner

The sidecar started but `127.0.0.1:8765/health` didn't return 200 within 15 s. Common causes:

- **Port 8765 in use.** Another TARS, an old `serve.py`, or some other service. Check with `lsof -i :8765` (macOS/Linux) / `netstat -ano | findstr 8765` (Windows). Kill the offender and relaunch.
- **Antivirus quarantined the sidecar binary.** macOS Gatekeeper may flag the unsigned `tars-backend` binary embedded in the bundle. Run `xattr -dr com.apple.quarantine /Applications/TARS.app` once.
- **Custom Python install conflict.** If you set `TARS_BACKEND_BIN` to a custom binary, TARS uses that instead of the bundled one. Unset it (`unset TARS_BACKEND_BIN`) to fall back.

### "Spawn failed" amber banner

The OS refused to start the sidecar process. On macOS this usually means the bundled binary isn't executable (broken install) or quarantined. On Windows, antivirus is the most likely culprit.

Re-download the installer from <https://github.com/alxvasilevvv/tars-neural-cockpit/releases/latest> and reinstall.

### Window opens blank

This is the silent-blank-window failure mode the build pipeline is supposed to prevent (Wave 59 added a pre-flight check). If you hit it on a release build, please file an issue with:

```bash
ls -la /Applications/TARS.app/Contents/Resources/_up_/web/
```

(adjust path for your OS) and the contents of the app's launcher log.

### Global shortcut not firing

- Another app owns `Cmd+Shift+Space` (macOS Input Sources picker is a common conflict). Disable that combo on the conflict and relaunch TARS.
- TARS is sandboxed (Mac App Store build, future). Sandboxing blocks global hotkeys; we ship outside the App Store specifically to avoid this.

### Tray icon missing on Linux

Most modern Linux desktops support `org.kde.StatusNotifierItem`; some minimal window managers don't. If you don't see a tray icon, use the global shortcut and the cockpit Cmd+K palette — same affordances.

## Security note

The cockpit runs with a tight CSP that only allows:

- `'self'` (the bundled web assets)
- `http://127.0.0.1:8765` and `ws://127.0.0.1:8765` (the sidecar)
- `https://meeet.world` (brand assets, billing edge, OAuth bridge)

Outbound traffic to anywhere else is blocked by the browser engine itself. The Rust shell does not run unrestricted user JavaScript; everything is gated by the capability manifest at `desktop/src-tauri/capabilities/default.json`.

Updater uses minisign signature verification — a tampered installer won't auto-apply. (When the operator generates and pins a release key — see `desktop/scripts/generate-release-keys.sh`.)

## Where to go next

- Local cockpit: `http://127.0.0.1:8765` (handy when debugging via curl)
- Cockpit UI: just launch TARS
- Public docs: <https://tars.meeet.world>
- Source: <https://github.com/alxvasilevvv/tars-neural-cockpit>
- Operator guide for second machine: `docs/SECOND_MACHINE_HANDOFF.md`

— Updated 2026-05-05 (Wave 59 + Wave 60).
