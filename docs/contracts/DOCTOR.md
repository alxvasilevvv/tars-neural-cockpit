# tars-doctor — unified health check (Wave 154)

**Module:** `backend/core/doctor/` · **CLI:** `scripts/tars-doctor`

After Waves 150 (MCP), 151 (Clone v0.2), 152 (Background daemon
macOS), and 153 (daemon Linux parity), the operator has a lot of
moving parts. `tars-doctor` is the **one command** that surfaces
the health of every TARS subsystem at once.

## What it checks

| Slug | Subsystem | What "ok" means |
| --- | --- | --- |
| `daemon` | Background daemon (W152/153) | heartbeat fresh (< 90s old) |
| `mcp` | MCP server tool registry (W150) | ≥5 tools registered |
| `clone` | AI Clone store + sync (W73/151) | store enabled + sync interval sane |
| `scheduler` | Playbook scheduler (W97) | enabled + store reachable |
| `webhooks` | Webhooks dispatcher (W90) | module importable + store ok |
| `cowork` | Cowork sessions store (W129/149) | db path resolves |
| `receipts` | Receipt ledger (W95) | ledger reachable |
| `vault` | Vault (key + secrets storage) | dir exists + readable |

Each check returns `CheckResult { slug, label, status, summary, suggestion, details, elapsed_ms }`.

`status` ∈ `ok` | `warn` | `fail` | `skip`. The doctor itself
never raises — broken-module branches return `skip` with the import
error in the summary so the operator can fix in place.

## CLI

```bash
# Human-readable table
scripts/tars-doctor

# Only show problems (status != ok)
scripts/tars-doctor --quiet

# Machine-readable JSON
scripts/tars-doctor --json

# Run a single check
scripts/tars-doctor --check mcp

# List available check slugs
scripts/tars-doctor --list
```

Behind the shim: `python -m backend.core.doctor [flags]`.

## Exit codes

| Code | Condition |
| --- | --- |
| 0 | every row is `ok` or `skip` |
| 1 | at least one `warn` (degraded but functional) |
| 2 | at least one `fail` (something is actually broken) |

CI workflows can `tars-doctor` as a smoke step — exit-2 fails the
job, exit-1 lets it pass but flags warnings in the log.

## Example output

```
TARS doctor — health check (Wave 154)

  ⚠  Background daemon              WARN  no heartbeat file (daemon not yet started?)
      → run: scripts/tars-daemon install
  ✓  MCP server tool registry       OK    5 tools, contract 0.1.0
  ✓  AI Clone store + sync          OK    db at ~/.tars/clone.sqlite, sync every 50 msgs
  ⚠  Scheduler store                WARN  store ok; tick loop NOT enabled (TARS_SCHEDULER_ENABLED unset)
      → export TARS_SCHEDULER_ENABLED=1 for the web app / daemon
  ✓  Webhooks dispatcher            OK    dispatcher importable, store at ~/.tars/webhooks.sqlite
  ✓  Cowork sessions store          OK    store db at ~/.tars/cowork.sqlite
  ✓  Receipt ledger                 OK    ledger at ~/.tars/receipts.sqlite
  ✓  Vault (key + secrets storage)  OK    3 entries in ~/.tars/vault

  Summary: 6 ok · 2 warn · 0 fail · 0 skip
```

## JSON output shape

```json
[
  {
    "slug": "daemon",
    "label": "Background daemon",
    "status": "ok",
    "summary": "alive (5s ago, 142 ticks, status=running)",
    "suggestion": "",
    "details": {
      "pid": 12345,
      "last_status": "running",
      "tick_count": 142,
      "last_tick_age_s": 5.0,
      "contract_version": "0.1.0"
    },
    "elapsed_ms": 4.2
  }
]
```

## Adding a new check

```python
from backend.core.doctor.checks import CheckResult, REGISTRY


def check_my_subsystem(_timeout_s: float) -> CheckResult:
    r = CheckResult(slug="myslug", label="My subsystem")
    try:
        from my.module import probe
        out = probe()
    except Exception as exc:
        r.status = "skip"
        r.summary = f"module not importable: {exc}"
        return r
    r.status = "ok"
    r.summary = f"alive ({out.uptime}s)"
    r.details = {"uptime": out.uptime}
    return r


REGISTRY.append(("myslug", check_my_subsystem))
```

The `run_check` wrapper records `elapsed_ms` and converts any
exception your handler raises into a `fail` row — you don't need
to catch.

## Non-goals

- **No network.** The web app's `/health` endpoint covers the live
  cockpit badge + the W117 synthetic monitor.
- **No fixes.** The doctor diagnoses, not heals. `suggestion`
  fields point at the specific command (`tars-daemon install`,
  `export TARS_SCHEDULER_ENABLED=1`) the operator runs.
- **Local-only.** No remote inspection, no SSH, no cluster
  rollup. v0.1 is single-host.

## HTTP surface (Wave 155)

The same results are exposed via the FastAPI app:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/doctor` | Run every check; returns `{ok, summary, results[]}` |
| `GET` | `/api/doctor/{slug}` | Run a single check by slug; 404 if unknown |
| `GET` | `/api/doctor/registry` | List slugs + labels without running |
| `GET` | `/api/doctor/page` | Self-contained HTML dashboard (Wave 156); auto-refresh 30s |
| `POST` | `/api/doctor/fix` | Run every registered fixer (Wave 167) |
| `POST` | `/api/doctor/fix/{slug}` | Run a single fixer by slug; 404 if unknown |
| `POST` | `/api/doctor/test/notify` | Wave 168 — fire synthetic doctor.status_changed through fanout_all so operator can verify channel wiring |

The cockpit Status page consumes `/api/doctor` to render a live
health table. The W117 synthetic monitor scrapes the same endpoint
so an outage in MCP / Clone / daemon flips the public status
dashboard.

`/api/doctor` is read-only (idempotent GET), no auth required —
same posture as `/health` and `/api/status`.

## Roadmap

- **v0.1 (Wave 154):** 8 built-in checks, JSON / human / quiet / single-check modes
- **v0.2 (Wave 155):** HTTP `/api/doctor` endpoint surface
- **v0.3 (Wave 156):** self-contained HTML dashboard at `/api/doctor/page` (auto-refresh, no React build)
- **v0.4 (Wave 166 — *this release*):** `--fix` mode — safe auto-remediation framework (vault dir mkdir; daemon + scheduler surface manual commands; future fixers register via `FIX_REGISTRY`)
- **v0.5 (v9.2 target):** time-series log of past doctor runs under `~/.tars/doctor.log`
- **v0.6 (v9.2 target):** Tauri cockpit embeds the page in a webview tab
- **v1.0 (v9.3 target):** Destructive fixers behind explicit `--fix --confirm` flag (re-install LaunchAgent, restart scheduler etc.)

## `--fix` mode (Wave 166)

```bash
scripts/tars-doctor --fix          # apply every registered fixer
scripts/tars-doctor --fix vault    # apply one
scripts/tars-doctor --fix --json   # machine-readable output
```

Each registered fixer returns a `FixResult { slug, applied,
skipped, reason, before_status, after_status, detail, elapsed_ms }`.
The CLI prints a human table; `--json` returns the array.

Posture: **conservative**. Only filesystem mkdir is applied
automatically. Destructive ops (launchctl bootstrap, env exports,
scheduler restart) require manual action — fixers for those
slugs return `skipped: manual_action_required` with the exact
command in `detail`.

Built-in fixers:

| Slug | Behaviour |
| --- | --- |
| `vault` | `mkdir -p $TARS_VAULT_DIR` (idempotent) |
| `daemon` | surfaces `scripts/tars-daemon install` — never auto-runs |
| `scheduler` | surfaces `export TARS_SCHEDULER_ENABLED=1` — never mutates parent shell |
| (anything else) | `skipped: no_fixer_registered` |

Exit codes: `0` when all fixers applied or skipped cleanly;
`2` when any fixer failed (mkdir permission denied etc.).
