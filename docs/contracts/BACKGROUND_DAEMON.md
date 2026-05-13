# TARS Background daemon — v0.1 contract (Wave 152)

**Module:** `backend/core/daemon/` · **Contract:** `0.1.0` · **Platform:** macOS (launchd LaunchAgent)

The Background daemon is the **autopilot path** — the headless
process that ticks the scheduler, fires due playbooks, and keeps
the AI Clone webhook sync alive even when the operator hasn't
opened the cockpit.

This closes the historic "Background TARS" honesty gap (task #65
was marked complete back in Wave 8.4.0 with no code shipped; the
W148 reality audit flagged it; W152 actually delivers it).

## Architecture

```
launchd (LaunchAgent gui/<uid>) ──spawn──► python -m backend.core.daemon
                                                      │
                                                      ▼
                                               SchedulerRunner.tick()
                                                      │
                                                      ├─ fires due playbooks
                                                      ├─ updates store
                                                      └─ writes heartbeat
                                                      ▼
                                           ~/.tars/daemon.heartbeat
```

Pure stdlib (no `mcp`, `apscheduler`, or `python-daemon` deps).
The plist boots on user-login and respawns on crash (KeepAlive
policy: `SuccessfulExit=false`, `Crashed=true`,
`ThrottleInterval=30`).

## What this is NOT

- **Not a system daemon.** LaunchAgent runs in the operator's
  session — it has `$HOME`, vault keys, browser cookies, and
  meeet.world tokens. A LaunchDaemon (system-level) wouldn't.
- **Not Linux/Windows.** v0.1 ships macOS only. systemd is on the
  v9.2 roadmap; Windows Task Scheduler is v9.3.
- **Not real-time.** Ticks every `TARS_SCHEDULER_TICK_S` seconds
  (default 30). The web-app lifespan loop uses the same cadence.
- **Not a replacement for FastAPI.** The web app keeps owning
  HTTP, WS, and cockpit UI. The daemon is the "even when no human
  is here" path.

## Install / Uninstall

```bash
# Via CLI shim (recommended)
scripts/tars-daemon install

# Or via the module entrypoint
python -m backend.core.daemon --install

# Inspect the plist before bootstrap
python -m backend.core.daemon --render-plist

# Status
scripts/tars-daemon status

# Uninstall
scripts/tars-daemon uninstall
```

The plist is written to `~/Library/LaunchAgents/com.tars.background.plist`.
`launchctl bootstrap gui/<uid>` loads it; `launchctl bootout`
unloads. Both calls are idempotent.

## Files on disk

| Path | Owner | Purpose |
| --- | --- | --- |
| `~/Library/LaunchAgents/com.tars.background.plist` | operator | LaunchAgent definition |
| `~/.tars/daemon.heartbeat` | daemon | runtime status JSON (atomically replaced) |
| `~/.tars/daemon.out.log` | daemon | stdout (rotated by launchd) |
| `~/.tars/daemon.err.log` | daemon | stderr (rotated by launchd) |

## Heartbeat shape

```json
{
  "pid": 12345,
  "started_at": 1747252800.0,
  "last_tick": 1747252830.0,
  "tick_count": 142,
  "last_status": "running",
  "error_count": 0,
  "last_error": null,
  "contract_version": "0.1.0"
}
```

`last_status` ∈ `starting | running | heartbeat_only | error | idle_exit | stopped`.

A stale heartbeat (last_tick > 5× tick_s ago) means the daemon
crashed between launchctl respawns; `tars-doctor` and the cockpit
"Background" badge surface this.

## Environment

| Variable | Default | Effect |
| --- | --- | --- |
| `TARS_SCHEDULER_ENABLED` | unset | Enable the scheduler tick loop. Required for the daemon to actually fire playbooks. |
| `TARS_DAEMON_FORCE` | unset | Keep the daemon alive (heartbeat-only) even when scheduler is disabled. Set in the plist by default. |
| `TARS_SCHEDULER_TICK_S` | 30 | Seconds between ticks. |
| `TARS_DAEMON_HEARTBEAT_S` | 30 | Heartbeat write cadence when scheduler is off. Floor 0.05s. |

## Subcommands

| Subcommand | Effect |
| --- | --- |
| (none) | Run the daemon loop (the launchd path) |
| `--install [--dry-run]` | Write plist + `launchctl bootstrap` (skip bootstrap with `--dry-run`) |
| `--uninstall` | `launchctl bootout` + remove plist |
| `--status` | Print plist + heartbeat snapshot as JSON |
| `--heartbeat` | Print latest heartbeat JSON only |
| `--render-plist` | Print the plist XML, no side effects |

## Error model

| Wire | Cause |
| --- | --- |
| `launchctl_not_found` | non-Darwin host (or PATH missing launchctl) |
| `launchd_not_supported_on_platform` | `os.getuid()` not available (Windows) |
| `unlink_failed: <reason>` | plist file removal failed (typically permissions) |

The daemon process itself never raises uncaught exceptions — tick
errors are logged + counted, the loop continues. launchd respawns
the process if it exits abnormally; `idle_exit` (status 0) is the
"nothing to do" branch where launchd doesn't re-spawn.

## Versioning

- `CONTRACT_VERSION = "0.1.0"` — daemon contract (this file)
- `PLIST_LABEL = "com.tars.background"` — canonical LaunchAgent label

Bump CONTRACT_VERSION on every breaking change to the heartbeat
shape or plist semantics. Additive env knobs = patch bump.

## Roadmap

- **v0.1 (this release):** macOS LaunchAgent, heartbeat, scheduler integration, CLI shim
- **v0.2 (v9.1.3 target):** Linux systemd unit + parity install CLI
- **v0.3 (v9.2 target):** Windows Task Scheduler integration
- **v0.4 (v9.2 target):** Cockpit "Background" status panel pulls live heartbeat
- **v1.0 (v9.3 target):** Multi-instance daemon (per-workspace launchd labels)
