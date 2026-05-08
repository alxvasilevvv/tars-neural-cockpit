# GitHub Release notes — v9.1.0

Это шаблон для создания GitHub Release когда ты тегнешь `v9.1.0`. Скопируй в окно "Release notes" на странице создания релиза:
https://github.com/alxvasilevvv/tars-neural-cockpit/releases/new?tag=v9.1.0

---

# TARS v9.1.0 — Phase L9 production release

**Local-first AI agent for Mac, signed and notarized.** This is the first production-grade installable, with native UX (tray, global shortcut, deep links), authoritative billing mirroring, and a hardened sidecar lifecycle.

## What's new

### Native desktop UX (Wave 59-62)
- **Window state persistence** — TARS remembers size & position across launches.
- **System tray icon** — left-click toggles main window; right-click reveals "Show TARS / Quit TARS" menu.
- **Global shortcut** `Cmd+Shift+Space` (macOS) / `Ctrl+Shift+Space` (Windows/Linux) summons the window from anywhere — Spotlight/Raycast pattern.
- **Deep links** `tars://` registered system-wide. Routes: `tars://onboarding[?role=…]`, `tars://login`, `tars://cockpit`, `tars://thread/<id>`, `tars://settings`. Used by magic-link emails and meeet.world handshake.
- **Settings page** — About + Updates check + Keyboard reference; reachable via `tars://settings`, Cmd+K palette, or `/settings` URL.

### Reliability (Wave 60-61)
- **Sidecar status indicator** — visible bottom-left badge when the FastAPI sidecar is starting / failed / crashed mid-session.
- **Mid-session crash detection** — Rust watcher thread + TS-side `/health` heartbeat. Catches both PID exits *and* hung-but-alive zombie sidecars.
- **Pre-flight build gate** — `desktop/scripts/preflight-build.sh` fails fast if the bundled web/ is empty (silent blank-window prevention) or icons are missing.

### Cockpit polish (Wave 53-58)
- WCAG 2.1 AA modal a11y sweep — focus traps on Onboarding custom-role modal, all 3 Cmd+K palettes (`CommandPalette`, `JumpPalette`, `GlobalCommandPalette`).
- ScrollStory regression fix — first/last segments stay visible at section entry/exit, no more 400vh black gap.
- Onboarding role chips moved from hex literals to design tokens (`var(--brand-orchid|color-success|brand-amber)`).
- FAQ accordion `aria-label` shortened (no double-read of question text by screen readers).
- CockpitGate footer hides raw `API_BASE` in production builds.

### Backend (Wave 51-56)
- POST `/operator/usage` retry budget exhaustion now emits structured `meeet.mirror.usage.exhausted` log for ops dashboards.
- New ops scripts: `ops_billing_remote_wizard.sh`, `smoke_billing_tars_backend.{sh,py}`, `backend_tars_up.sh`, `dev_tars_stack.sh`.
- Makefile gates: `smoke-billing-tars`, `backend-tars-up`, `dev-tars-stack`, `ops-billing-remote-wizard`, `test-commercial-readiness`.

### Documentation
- **`docs/DESKTOP.md`** — full operator guide for the desktop app (install, native features, troubleshooting, security model).
- **`docs/INTEGRATION_FOR_BROTHER.md`** — single-source integration spec for meeet.world / Lovable side.
- **`docs/OPERATOR_LAUNCH_PLAYBOOK.md`** — step-by-step from `git push` to launch tweet.
- **`docs/DESKTOP_OWNERSHIP_PASS.md`** — Wave 59 → Wave 63 wrap-up with verify steps.

## Installation

### macOS

```bash
curl -fsSL https://tars.meeet.world/install.sh | sh
```

Or grab signed `.dmg` directly:
- **Universal (Apple Silicon + Intel):** `TARS-9.1.0-universal.dmg`

### Windows

Download `TARS-9.1.0-Setup.exe` and run. Windows SmartScreen may flag the first ~50 installs (we ship with OV Authenticode certificate; reputation builds with each install).

### Linux

```bash
# AppImage (portable):
chmod +x TARS-9.1.0-x86_64.AppImage && ./TARS-9.1.0-x86_64.AppImage

# Debian/Ubuntu:
sudo dpkg -i TARS-9.1.0-amd64.deb
```

## Verifying signatures

Each release artifact ships with a minisign signature sidecar. To verify:

```bash
brew install minisign
curl -O https://tars.meeet.world/minisign.pub
minisign -V -p minisign.pub -m TARS-9.1.0-universal.dmg
```

Public key fingerprint: `<INSERT_AFTER_KEY_GENERATION>`

## Architecture

- **Cockpit** — React 18 + Vite 5 + Tailwind v4 (~3MB built dist).
- **Sidecar** — CPython 3.12 + FastAPI + 14 pinned dependencies, embedded via pyoxidizer into a single binary (`tars-backend`), bundled into the Tauri app resource directory.
- **Shell** — Tauri 2.0 with plugins: shell, notification, updater, window-state, global-shortcut, deep-link, plus core `tray-icon` feature.
- **Memory** — SQLite + sqlite-vec for embeddings.
- **Sync** — encrypted via X25519 + XChaCha20-Poly1305 envelope (L5 Pairing); meeet.world cloud sees only ciphertext.
- **Billing** — authoritative on meeet.world Supabase via idempotent POST `/operator/usage` with `trace_id` dedupe.
- **Settlement** — SOL on-chain for $MEEET payments.

## What's NOT in this release (yet)

- Windows + Linux pyoxidizer cross-target — currently arm64-darwin / x86_64-darwin only; CI rewrite scheduled for v9.2.
- iOS / Android companion app — Phase M (estimated 6-10 weeks).
- Built-in Notion / Linear connectors — coming via OAuth bridge, post-launch.
- Magic-link email auth flow — depends on meeet.world side, scheduled v9.1.1.

## Breaking changes

None — first production v9 release.

## Known issues

- macOS Gatekeeper may show "TARS was downloaded from the internet" prompt on first launch (this is normal first-run behavior, not a notarization problem; click "Open" once and it never appears again).
- Windows SmartScreen reputation builds with installs — first ~50 users may need to click "More info → Run anyway".
- TARS service worker (`public/sw.js`) is currently not registered; PWA install-to-home-screen is a no-op. Tracked, low priority.

## Contributors

Built by Алексей (founder + product) with code from Claude (architecture, cockpit, desktop polish), Cursor (backend, billing infrastructure, ops scripts), and Lovable (meeet.world Edge Functions). See `docs/CHANGELOG_AGENTS.md` for per-wave attribution and SYNC markers.

## Links

- **Marketing site:** https://tars.meeet.world
- **Source:** https://github.com/alxvasilevvv/tars-neural-cockpit
- **Documentation:** https://tars.meeet.world/docs
- **Status:** https://tars.meeet.world/status
- **Discord / Community:** [TBD — meeet.world community]

## Checksum reference

After CI completes the build, verify your download with:

```bash
shasum -a 256 TARS-9.1.0-universal.dmg
# Expected: <CI will fill this in the release notes>
```

Or pull the signed `latest.json` from the release and verify with minisign as above.

---

## Что добавить руками после CI закончил

Когда GitHub Actions закончит билд:

1. **Public key fingerprint** — после первого signed release, `minisign -F -p ~/.tars/release/minisign.pub` даст fingerprint, замени `<INSERT_AFTER_KEY_GENERATION>`.

2. **SHA256 checksums** — каждый `.dmg / .msi / .AppImage / .deb` имеет sha256. CI кладёт их в `latest.json`. Скопируй в секцию Checksum reference.

3. **Discord invite** — если у тебя есть meeet.world community Discord, замени `[TBD ...]`.

4. **Demo video** — embed YouTube / Vimeo link в начале если у тебя есть launch video.
