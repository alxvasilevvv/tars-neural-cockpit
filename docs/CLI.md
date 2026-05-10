# `tars` CLI — operator + workshop power-user manual

> Wave M2. Stdlib-only argparse wrapper around the same action
> handlers the cockpit and external MCP clients call. No new
> dependency, no new audit path — every CLI verb routes through
> the canonical pipeline so the audit log, risk gate, and
> council voices behave identically whether the operator drives
> from the cockpit, an MCP client, or the terminal.

## Install

The CLI ships in this repo at `backend/cli/`. Two ways to run:

```bash
# Direct: works from a clone of the repo with no setup.
python3 -m backend.cli --help

# Shim: link the bin/tars script onto your $PATH.
ln -s "$(pwd)/bin/tars" /usr/local/bin/tars
tars --help
```

The shim auto-detects the repo root from its own location; a
`TARS_PYTHON` env var overrides the interpreter (default
`python3`). No virtualenv required; no third-party dependencies
are installed by the CLI itself.

## Output modes

Every command emits one of two formats:

- **`--json`** — machine-readable, sorted-keys, indent=2. Pipe
  into `jq` / `yq` / scripts. Default when stdout is **not** a
  TTY (e.g. cron, CI, redirected to a file).
- **`--human`** — opinionated Markdown tables + bullet lists.
  Default when stdout **is** a TTY. Falls back to JSON for
  payloads we don't have a dedicated pretty-renderer for, so
  you always see *something* readable.

`--json` and `--human` are mutually exclusive.

## Exit codes

| Code | Meaning                                                    |
| ---: | ---------------------------------------------------------- |
| `0`  | Success — handler returned `ok=True`.                      |
| `1`  | Handler returned `ok=False` (a structured error).          |
| `2`  | argparse / usage error (or no command supplied).           |
| `3`  | Uncaught exception. Set `TARS_CLI_TRACEBACK=1` for a trace.|
| `130`| User pressed Ctrl-C.                                       |

## Verbs

### `tars version`

```bash
tars version
tars version --check-packs   # skip pack inventory (faster)
```

Outputs CLI version, Python version, platform, `TARS_HOME`,
and (by default) the registered pack inventory with each
pack's version + phase.

### `tars algotrade ...`

| Verb                  | What it does                                                                 |
| --------------------- | ---------------------------------------------------------------------------- |
| `list-recipes`        | List bundled starter strategies.                                             |
| `load-recipe NAME`    | Print one recipe's IR + fingerprint.                                         |
| `list-strategies`     | Inventory of registered strategies. `--tag` / `--instrument` / `--author`.   |
| `get-strategy FP`     | Fetch a stored strategy by sha256 fingerprint.                               |
| `register-strategy`   | `--recipe NAME` or `--ir-file PATH`.                                         |
| `backtest`            | Strategy via `--recipe / --fingerprint / --ir-file`. Data via `--csv-path` or `--binance SYMBOL[:INTERVAL[:LIMIT]]`. |
| `list-sessions`       | `--mode paper|live`, `--status …`, `--sandbox-id …`.                          |
| `get-session ID`      | Full snapshot: session + policy + open positions + open orders + audit tail. |
| `session-report ID`   | W3-PR2 markdown report. `--top-n-trades N`.                                  |
| `council-review ID`   | W3-PR3 trading council voices.                                               |

#### Workshop one-liner

```bash
# Backtest the bundled MA-cross recipe against 500 1h Binance bars
tars algotrade backtest \
  --recipe ma_cross \
  --binance BTCUSDT:1h:500 \
  --equity-down-sample 200
```

### `tars lab ...`

The W4-PR2 + W4-PR3 facilitator surface. Every verb maps
1-to-1 onto an action.

| Verb                     | What it does                                                          |
| ------------------------ | --------------------------------------------------------------------- |
| `create-workshop`        | `--name`, `--facilitator`, `--workshop-id`. Returns the minted id.    |
| `list-workshops`         | `--status open|paused|closed`.                                         |
| `set-workshop-status`    | `--workshop-id`, `--status`. Pause / close / re-open.                 |
| `enroll`                 | `--workshop-id`, `--name`, `--attendee-id`. Returns the minted `sandbox_id`. |
| `list-attendees`         | `--workshop-id`.                                                      |
| `leaderboard`            | `--workshop-id`. Net-edge ranking with deterministic tie-breakers.    |
| `snapshot`               | `--attendee-id`. Per-attendee handout.                                |
| `debrief`                | `--workshop-id`. Renders the W4-PR3 markdown bundle. `--no-session-reports` for headlines-only. `--output PATH` writes to disk and prints a one-line confirmation instead of dumping the full bundle to stdout. |

#### Bulk enrollment

```bash
for name in "Alice Karpov" "Bob Sun" "Carol Lee"; do
  tars --json lab enroll \
    --workshop-id ws_cresco-day-1_… \
    --name "$name" \
    | jq -r '.attendee.sandbox_id'
done
```

#### End-of-workshop email bundle

```bash
tars lab debrief \
  --workshop-id ws_cresco-day-1_… \
  --output ~/cresco-debrief-$(date +%Y%m%d).md
```

### `tars playbooks ...`

| Verb                | What it does                                                                  |
| ------------------- | ----------------------------------------------------------------------------- |
| `list`              | Discover all playbooks (recursive loader from W4-PR1).                        |
| `show ID`           | Show one playbook's full definition.                                          |
| `run ID`            | Execute a playbook. `--mode dry_run|confirm|auto`. `--context KEY=VALUE` (repeatable). |

#### Run the bundled morning brief

```bash
tars playbooks run business.morning_brief --mode dry_run
```

## Environment variables

| Variable                 | Default                       | Purpose                                                        |
| ------------------------ | ----------------------------- | -------------------------------------------------------------- |
| `TARS_HOME`              | `~/.tars`                     | Root for all on-disk state (sessions, audit, lab, playbooks).  |
| `TARS_ALGOTRADE_HOME`    | `$TARS_HOME`                  | Override just the algotrade data dir.                          |
| `TARS_PLAYBOOKS_DIR`     | repo `playbooks/`             | Where the playbook loader scans.                               |
| `TARS_CLI_TRACEBACK`     | unset                         | When set, prints full Python traceback on uncaught errors.     |
| `TARS_PYTHON`            | `python3`                     | Override the interpreter used by `bin/tars`.                   |

## Why argparse + stdlib?

- **Cold start under 100ms.** No `click` / `typer` / `rich`
  parser-build overhead, so `tars list-recipes` feels
  instantaneous in a workshop demo.
- **Zero dependency footprint.** A workshop attendee on a
  fresh laptop runs `python3 -m backend.cli` against a clone
  of the repo with **no `pip install` required**. Same
  property the algotrade pack itself maintains.
- **Stable parser.** argparse is stdlib, so the help text and
  exit-code contract are pinned to the Python version, not to
  a third-party CLI library that might break on upgrade.

## Testing

The CLI has its own pytest module at `tests/test_cli_main.py`
(25 cases — every verb has at least an error-path + a
success-path assertion). Tests call `main(argv)` directly,
capture stdout via `capsys`, and parse the JSON envelope.
No subprocess spawning — the suite runs in <500ms total.

## What's next

Wave M3 / M4 will add the MCP client + server. The CLI is the
natural testing harness for the bidirectional MCP exchange,
and the same action handlers it routes to today will become
the MCP tool surface tomorrow.
