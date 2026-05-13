# TARS v9.1.1 — release notes

**Released:** 2026-05-13 (Waves 151-157, all on `main`)
**Channel:** stable · additive over v9.1.0
**Platforms:** macOS + Linux (background daemon now ships parity)
**Codename:** Phase L10 — autopilot foundations

## What's in this release

v9.1.1 closes two historical "done-but-missing" honesty drifts
flagged by the W148 reality audit — Background TARS daemon and
MCP server bridge — and adds the cross-system glue (doctor /
sync / webhook) that turns those modules into a coherent autopilot.

No frontend changes; the cockpit UI surface from v9.1.0 is
unchanged. v9.1.1 is purely backend + CLI + contract work.

## TL;DR — one paragraph

The background daemon is now real (macOS LaunchAgent + Linux
systemd user-unit, both via `tars-daemon install`). `tars-doctor`
gives the operator a single command (and an HTTP `/api/doctor`
endpoint, and a self-contained HTML dashboard at
`/api/doctor/page`) to see the health of every TARS subsystem.
The daemon's per-tick watcher fires a `doctor.status_changed`
webhook when health changes, so meeet.world / Telegram / Slack
gets notified the moment something drifts. AI Clone v0.1 grew
cross-machine portability via export/import endpoints + a
debounced sync webhook.

## Wave-by-wave changelog

### W151 — AI Clone v0.2 (style persistence)

- `backend/core/clone/sync.py` — `StyleEnvelope` dataclass +
  `export_profile()` / `import_profile()` (dedup by text,
  preserves original `created_at`).
- New endpoints:
  - `POST /api/clone/export` → envelope JSON
  - `POST /api/clone/import` → rehydrate from envelope
- `record_message()` now fires `clone.profile.synced` webhook every
  Nth message (default 50, env-tunable via `TARS_CLONE_SYNC_INTERVAL`).
- Contract: `docs/contracts/CLONE_SYNC.md` (schema v1, contract 0.2.0).
- Honest framing: still the v0.1 style heuristic — just synced.

### W152 — Background daemon (macOS)

- `backend/core/daemon/` — real launchd LaunchAgent installer,
  heartbeat file, graceful SIGTERM, scheduler integration.
- `scripts/tars-daemon install/uninstall/status/heartbeat/render/restart`.
- Plist at `~/Library/LaunchAgents/com.tars.background.plist`,
  heartbeat at `~/.tars/daemon.heartbeat`.
- Contract: `docs/contracts/BACKGROUND_DAEMON.md`.

### W153 — Daemon Linux parity

- `backend/core/daemon/systemd.py` — `systemctl --user` unit
  installer with platform-auto dispatch in `__main__.py`.
- Unit at `~/.config/systemd/user/tars-background.service`.
- `--platform launchd|systemd|auto` flag for explicit override.

### W154 — `tars-doctor` CLI

- `backend/core/doctor/` — registry of 8 checks: daemon, mcp,
  clone, scheduler, webhooks, cowork, receipts, vault.
- `scripts/tars-doctor` shim — JSON + human + quiet + single-check
  modes; exit codes 0/1/2 for ok/warn/fail.
- Contract: `docs/contracts/DOCTOR.md`.

### W155 — `/api/doctor` HTTP endpoint

- `web_extras/routers/doctor.py` — `GET /api/doctor`,
  `/api/doctor/{slug}`, `/api/doctor/registry`.
- Same JSON shape as the CLI's `--json` output.
- Wired into `web_extras/app.py`.

### W156 — `/api/doctor/page` HTML dashboard

- Self-contained HTML response (no React build, no static-files
  mount) at `GET /api/doctor/page`.
- Auto-refresh every 30s; live status pills + 8-row health table
  + per-row glyphs + suggestions.
- Operator opens `http://localhost:<port>/api/doctor/page` in a
  browser → live cockpit-style status view.

### W157 — Daemon doctor-watch (drift webhook)

- `backend/core/daemon/doctor_watch.py` — per-tick watcher with
  in-memory cache of last-seen statuses, diff against new run,
  emits `doctor.status_changed` webhook on any drift.
- Opt-in: `TARS_DAEMON_DOCTOR_ENABLED=1`; throttle:
  `TARS_DAEMON_DOCTOR_EVERY_N=N` (default 1).
- Webhook payload: `{changes[], summary{}, results[], fired_at}`.
- First-time-seen slugs don't fire (boot-time noise suppression).

## New env vars

| Variable | Default | Effect | Wave |
| --- | --- | --- | --- |
| `TARS_CLONE_SYNC_INTERVAL` | 50 | clone.profile.synced emit cadence | W151 |
| `TARS_DAEMON_FORCE` | unset | keep daemon alive with no scheduler | W152 |
| `TARS_DAEMON_HEARTBEAT_S` | 30 | heartbeat write cadence (floor 0.05s) | W152 |
| `TARS_DAEMON_DOCTOR_ENABLED` | unset | enable per-tick doctor watcher | W157 |
| `TARS_DAEMON_DOCTOR_EVERY_N` | 1 | run doctor every Nth tick | W157 |

## New endpoints

| Method | Path | Purpose | Wave |
| --- | --- | --- | --- |
| POST | `/api/clone/export` | dump style envelope | W151 |
| POST | `/api/clone/import` | rehydrate style envelope | W151 |
| GET  | `/api/doctor` | run all checks, return JSON | W155 |
| GET  | `/api/doctor/{slug}` | run one check by slug | W155 |
| GET  | `/api/doctor/registry` | list available checks | W155 |
| GET  | `/api/doctor/page` | HTML dashboard (auto-refresh 30s) | W156 |

## New webhook events

| Event type | Payload (top-level) | Wave |
| --- | --- | --- |
| `clone.profile.synced` | `schema_version, contract_version, exported_at, sample_count, profile, trait_count` | W151 |
| `doctor.status_changed` | `changes[], summary{}, results[], fired_at` | W157 |

## New CLIs

| Command | Subcommands | Wave |
| --- | --- | --- |
| `scripts/tars-daemon` | install / uninstall / status / heartbeat / render / restart / logs | W152/153 |
| `scripts/tars-doctor` | (none — runs all) / --json / --quiet / --check / --list | W154 |

## Operator quick-start

```bash
# 1. Install the background daemon (macOS or Linux)
scripts/tars-daemon install

# 2. Verify it's alive
scripts/tars-daemon status

# 3. Run a one-shot health check
scripts/tars-doctor

# 4. Open the live HTML dashboard
open "http://localhost:8123/api/doctor/page"   # or your TARS port

# 5. Enable the auto-watcher (optional)
export TARS_DAEMON_DOCTOR_ENABLED=1
scripts/tars-daemon restart
```

## Honesty caveats

- **AI Clone v0.2 is still the v0.1 heuristic** — just synced
  across machines. Real fine-tune is still a v9.2 target.
- **Auto-restore is not automatic.** A fresh TARS install
  doesn't pull the cloud-backed envelope; operator runs
  `POST /api/clone/import` manually.
- **The background daemon is not Windows-supported yet.** v9.2
  target. macOS + Linux ship in v9.1.1.
- **The doctor doesn't fix anything.** It diagnoses + suggests;
  fix-mode is a v9.3 target.

## Testing

77 new tests across the 7 waves, all green where stdlib runs them:

- `tests/test_clone_sync.py` — 15 cases
- `tests/test_daemon.py` — 27 cases (macOS + Linux paths)
- `tests/test_doctor.py` — 15 cases
- `tests/test_doctor_router.py` — 7 cases (skips when fastapi missing)
- `tests/test_doctor_watch.py` — 14 cases (W157)

CI plumbing unchanged — the existing GitHub Actions workflow runs
the full test matrix on every push.

## Migration path

No breaking changes. v9.1.1 is purely additive over v9.1.0:

- Existing endpoints unchanged
- Existing webhook contract unchanged
- New env vars all default to off / safe values
- Old clone heuristic still works exactly as before — operators
  who don't import/export simply use the local SQLite store
- Daemon is opt-in via `tars-daemon install`, not auto-installed
  by the desktop app

## Brother handoff (meeet.world side)

Two new webhook events brother's edge function should accept:

1. `clone.profile.synced` — store the latest envelope-summary
   under the user's tenant. Provide `GET /tars/clone/snapshot`
   for restore (Pro tier + explicit consent flag).
2. `doctor.status_changed` — surface in the operator's status
   dashboard and optionally fan out to Telegram/Slack channels
   the operator has wired.

See `docs/contracts/CLONE_SYNC.md` and
`docs/contracts/BACKGROUND_DAEMON.md` for the payload shapes.

## Roadmap (next 30 days)

- **W158-W162:** Windows daemon parity (Task Scheduler)
- **W163-W167:** Real iMessage bridge (closes last W148 drift)
- **W168-W172:** AI Clone v0.3 — signed envelopes (ed25519,
  vault-managed keys)
- **W173-W177:** `tars-doctor --fix` mode (auto-remediation for
  re-installing daemon, restarting scheduler etc.)
- **v9.2 — Phase L11:** cockpit "Background" status panel
  rendering live heartbeat + doctor + clone sync timeline

## Tagging

This release sits at `9b51bd5` on `main`. To tag:

```bash
git tag -a v9.1.1 -m "TARS v9.1.1 — autopilot foundations"
git push origin v9.1.1
```

GitHub Releases artifact: same dmg/app pattern as v9.1.0 since
this is a backend-only release; the existing v9.1.0 desktop
bundle is forward-compatible with v9.1.1 backend modules.
