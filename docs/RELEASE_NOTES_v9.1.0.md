# TARS v9.1.0 — release notes

**Released:** 2026-05-09
**Channel:** stable
**Platforms:** macOS only (Apple Silicon native, Intel via Rosetta-on-arm64-dmg)
**Codename:** Phase L9 — production desktop

This is the first production-grade installable. Local-first AI cockpit with native UX, hardened sidecar lifecycle, authoritative billing mirror, and an honest scope. See `docs/WHAT_WORKS.md` for the full capability ledger; this file just describes the v9.1.0 delta.

---

## What's new

### Native desktop (Wave 59 → 62)
- Tauri 2 shell with **system tray icon**, **window state persistence**, **global shortcut** (`Cmd+Shift+Space`), and **deep links** (`tars://onboarding`, `tars://login`, `tars://cockpit`, `tars://thread/<id>`, `tars://settings`).
- **Settings page** — About + Updater + keyboard reference, reachable via `tars://settings`, Cmd+K, or `/settings`.
- **Auto-updater** wired to GitHub Releases `latest.json` channel manifest.

### Reliability (Wave 60 → 61)
- **Sidecar status indicator** in the cockpit (starting / failed / crashed / healthy).
- **Mid-session crash detection** — Rust watcher thread + TS heartbeat. Catches both PID exits and zombie hung processes.
- **Pre-flight build gate** — `desktop/scripts/preflight-build.sh` fails if web/ is empty or icons are missing (prevents silent blank-window installers).

### Cockpit polish (Wave 51 → 70)
- WCAG 2.1 AA modal a11y sweep — focus traps on Onboarding custom-role modal and all 3 Cmd+K palettes.
- ScrollStory regression fix (no more 400vh black gap at section entry/exit).
- Onboarding role chips → design tokens (no hex literals).
- FAQ accordion screen-reader cleanup.
- Force-EN locale (Wave 70) — operator-friendly default until other locales are re-translated.

### Marketing surface (Wave 65 → 71)
- Section divider renumber + tighter section transitions.
- Honest downloads — "Mac only, signed installer" instead of vapor Windows / Linux buttons.
- Reality alignment passes (Wave 71-A backend, Wave 71-B marketing) — every shipping URL resolves, every claimed feature has a code path.

### Backend (Wave 51 → 56)
- POST `/operator/usage` retry-budget exhaustion now emits structured `meeet.mirror.usage.exhausted` log for ops dashboards.
- New ops scripts: `ops_billing_remote_wizard.sh`, `smoke_billing_tars_backend.{sh,py}`, `backend_tars_up.sh`, `dev_tars_stack.sh`.
- New Makefile gates: `smoke-billing-tars`, `backend-tars-up`, `dev-tars-stack`, `ops-billing-remote-wizard`, `test-commercial-readiness`.

### Wave 72 launch hardening (this commit)
- Sidecar binary name aligned with CI (`tars-sidecar-<triple>` via `bundle.externalBin`); legacy `tars-backend` resolution kept as a fallback.
- `/api/product/downloads` defaults reduced to Mac-only artifacts so the manifest never advertises files the `/dl/<file>` proxy will 404.
- Pairing store backed by SQLite at `~/.tars/pairings.sqlite` — paired devices survive app restart.
- Dead Russian i18n dictionary deleted (~780 lines) — was already unreachable after Wave 70 force-EN, removed to prevent future regression.
- Release workflow boundary documented (`release-desktop-tagged.yml` is authoritative on tag push; `release-tagged.yml` is manual-dispatch only).
- New `eval-suite.yml` CI workflow — runs the eval scaffolding non-blockingly on PRs and nightly.
- `AttachmentChipStrip` wired into Cockpit chat composer.
- `docs/WHAT_WORKS.md` — honest capability ledger created.
- `docs/RELEASE_NOTES_v9.1.0.md` — this file.

---

## What's changed

- Default `_DEFAULT_VERSION` in `backend/core/product/manifest.py` bumped from `0.1.0-alpha.2` → `9.1.0`.
- Default artifact filenames migrated to CI naming (`TARS_<version>_<arch>.dmg`, underscore + raw arch).
- `tauri.conf.json` adds `bundle.externalBin: ["binaries/tars-sidecar"]` so Tauri picks the correct target-triple binary at bundle time.
- `experiments/neural-showcase-v3/src/lib/i18n.tsx` is now ~1000 lines (was ~1770); only EN dictionary remains.

## Breaking changes

None for end users. For integrators:
- The `Locale` type in `@/lib/i18n` is now `"en"` only. Code that did `setLocale("ru")` no longer type-checks — it was a no-op anyway after Wave 70.
- `~/.tars/pairings.sqlite` is now created on first sidecar boot. Set `TARS_PAIRINGS_DB=disabled` to opt back into in-memory only (tests / packaged distros).

---

## Known limitations (be honest)

- **macOS only.** Windows + Linux pyoxidizer cross-target builds are scheduled for v9.2 — the Tauri code path is identical, only the CI matrix is missing.
- **No notarization.** Ad-hoc codesigned only (Apple Developer Program at $99/yr is post-launch). First-run `xattr -dr com.apple.quarantine` documented in install.sh.
- **No STT.** Speech-to-text pipeline is not in v9.1.0. Voice intents work for TTS-out + text-in. Whisper integration scheduled for v9.2.
- **No marketplace.** Third-party skill registry is scaffolded (Wave 49, 96–97) but not live; install via filesystem only.
- **No T2T live.** TARS-to-TARS handshake exists in mock-escrow form (Wave 81); live counterparty discovery scheduled for v9.3.
- **Mac-x64 dmg may fall back to arm64+Rosetta.** When the macos-13 GitHub runner pool is queue-starved, the Intel dmg is missing and the `/dl/TARS_9.1.0_x64.dmg` proxy redirects to the arm64 dmg, which Rosetta runs cleanly.
- **No Windows SmartScreen reputation yet.** First ~50 Windows users (once v9.2 ships) will hit "More info → Run anyway".

See `docs/WHAT_WORKS.md` for the full FULLY-IMPLEMENTED / PARTIAL / NOT-IMPLEMENTED breakdown.

---

## Roadmap pointer

- **v9.2** — Windows + Linux installers (pyoxidizer cross-target), STT (Whisper), Slack connector v1.
- **v9.3** — Wake-word, marketplace v1, live T2T handshake.
- **v9.4** — RBAC, webhooks, Gmail send-side.
- **v9.5** — Shared agent sessions (multiplayer), public skill ratings.

Authoritative roadmap: `docs/ROADMAP_TO_RELEASE.md` and `docs/PHASE_L_ROADMAP.md`.

---

## Version → contract → infra mapping

| Surface | Pinned identifier in v9.1.0 |
| --- | --- |
| App version (cockpit + sidecar) | `9.1.0` |
| Tauri config `version` | `9.1.0` (`desktop/src-tauri/tauri.conf.json`) |
| Download manifest `contract_version` | `1.0.0` (`backend/core/product/manifest.py`) |
| Pairing schema (paired devices) | unversioned; one table `pairings` (Wave 72) |
| Updater channel JSON | `latest.json` at `releases/latest/download/latest.json` |
| Marketing site asset hosting | Cloudflare Pages `tars-meeet` → GitHub Releases proxy `/dl/<file>` |
| Magic-link auth | meeet.world bridge, route `tars://login` |
| Allowlisted CSP origins | `127.0.0.1:8765`, `meeet.world` |

---

## Verifying the build

```bash
# Architecture: Tauri 2 shell, CPython 3.12 + FastAPI sidecar, SQLite memory.
# Verify the sidecar before shipping:
codesign --verify --deep --strict --verbose=2 /Applications/TARS.app
xattr -dr com.apple.quarantine /Applications/TARS.app   # first run only
```

Channel manifest (the one Tauri's updater polls):

```bash
curl -s https://github.com/alxvasilevvv/tars-neural-cockpit/releases/latest/download/latest.json | jq .
```

---

## Credits

Wave 72 launch hardening: alienram@icloud.com (operator), Claude (assistant).
Backend & desktop: brother-of-meeet.world.
Marketing & cockpit: meeet.world team + Lovable.
