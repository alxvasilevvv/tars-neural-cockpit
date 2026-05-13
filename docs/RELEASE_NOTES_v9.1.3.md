# TARS v9.1.3 — release notes

**Released:** 2026-05-13 (Waves 166-169)
**Channel:** stable · additive over v9.1.2
**Platforms:** macOS + Linux (Windows daemon still pending — v9.2)
**Codename:** Phase L10.2 — auto-remediation

## What's in this release

v9.1.3 turns the doctor from "diagnose-only" into a real
operator console. Auto-remediation lands as a framework (W166),
HTTP endpoint (W167), self-tests for notification wiring (W168 +
W169). Operators now have CLI + HTTP + HTML parity across every
doctor operation.

## TL;DR — one paragraph

The doctor's `--fix` mode auto-creates the vault directory and
surfaces actionable hints for daemon + scheduler issues
(without auto-mutating service-manager or shell state).
`POST /api/doctor/fix[/{slug}]` exposes the same surface to the
cockpit; the HTML dashboard grows clickable `⚒ fix` buttons that
flip a row from warn → ok in place. `POST /api/doctor/test/notify`
+ `tars-doctor --test-notify` let operators verify their
Telegram/iMessage/Email channels are wired in one click — no
waiting for a real drift to find out the config is broken.

## Wave-by-wave changelog

### W166 — `tars-doctor --fix` (CLI framework)

- New module: `backend/core/doctor/fixers.py`
- `FixResult` dataclass: `{slug, applied, skipped, reason,
  before_status, after_status, detail, elapsed_ms}`
- `FIX_REGISTRY: {slug → fixer_fn}` mapping
- Three built-in fixers:
  - `vault` — real fix: `mkdir -p $TARS_VAULT_DIR` (idempotent)
  - `daemon` — skip-only: surfaces `scripts/tars-daemon install`
  - `scheduler` — skip-only: surfaces `export TARS_SCHEDULER_ENABLED=1`
- `--fix` / `--fix SLUG` flags on the CLI; `--json` mode supported
- `--list` grows `[fixer]` markers
- 13 new test cases

### W167 — `POST /api/doctor/fix` (HTTP + dashboard)

- `POST /api/doctor/fix` → applies all
- `POST /api/doctor/fix/{slug}` → applies one; 404 with `fixable`
  list when slug unknown
- HTML dashboard grows clickable `⚒ fix` buttons next to non-ok
  rows that have a registered fixer
- Toast notifications at bottom-right show the transition
  (e.g. `✓ vault: warn → ok`)
- 4 new test cases

### W168 — `POST /api/doctor/test/notify` (HTTP + dashboard)

- `POST /api/doctor/test/notify` fires synthetic
  `doctor.status_changed` through `fanout_all`
- Body shape: `{channels, slug, from, to, summary}` — all optional
- HTML dashboard grows `📣 test alert` button in the header
- 3 new test cases

### W169 — `tars-doctor --test-notify` (CLI parity)

- `--test-notify` flag fires the same synthetic alert
- `--channel SLUG` to pin a single channel (otherwise reads env)
- Human + JSON output modes; exit codes 0/1/2 for delivered/no-config/failed
- 3 new test cases
- Also fixes missing `_print_json` helper in `__main__.py`
  (worked by accident pre-W169 because no test hit the path)

## New endpoints

| Method | Path | Wave |
| --- | --- | --- |
| `POST` | `/api/doctor/fix` | W167 |
| `POST` | `/api/doctor/fix/{slug}` | W167 |
| `POST` | `/api/doctor/test/notify` | W168 |

## New CLI flags

| Flag | Wave |
| --- | --- |
| `tars-doctor --fix [SLUG]` | W166 |
| `tars-doctor --test-notify` | W169 |
| `tars-doctor --channel SLUG` | W169 |

## Operator-surface parity

| Operation | CLI | HTTP | HTML dashboard |
| --- | --- | --- | --- |
| Run all checks | `tars-doctor` | `GET /api/doctor` | auto-refresh 30s |
| Apply all fixers | `tars-doctor --fix` | `POST /api/doctor/fix` | — |
| Apply one fixer | `tars-doctor --fix SLUG` | `POST /api/doctor/fix/{slug}` | `⚒ fix` button |
| Test notifications | `tars-doctor --test-notify` | `POST /api/doctor/test/notify` | `📣 test alert` button |

## Honest framing

- **Only `vault` is auto-applied.** `daemon` and `scheduler`
  fixers return `skipped: manual_action_required` with the exact
  command — touching service-manager or shell state is reserved
  for the v1.0 `--fix --confirm` flow.
- **Conservative-by-default.** Failures don't cascade — a fixer
  exception lands as `reason='fixer_exception'`, never crashes
  the doctor.
- **No new fixers since W166.** Adding more is a one-function
  PR against `FIX_REGISTRY`; v9.2 will land them as needed.

## Migration

Zero breaking changes. v9.1.3 is purely additive over v9.1.2:
- All existing CLI flags + endpoints unchanged
- No new env vars
- New endpoints + flags are opt-in

## Testing

20 new test cases (130+ cumulative this release cycle):

- `tests/test_doctor_fixers.py` — 16 cases (W166 framework + W169 CLI)
- `tests/test_doctor_router.py` — 17 cases (W167 + W168 endpoints)

All run on pure stdlib; FastAPI-dependent tests skip cleanly when
fastapi isn't installed (sandbox safe).

## Roadmap

- **W171-W175:** Windows daemon parity (`schtasks.exe`)
- **W176-W180:** AI Clone v0.3 — signed envelopes (ed25519)
- **v9.2:** HTML dashboard keyboard shortcuts, sort/filter,
  receipts ledger viewer at `/api/receipts/page`

## Tagging

This release sits at `8bc980e` on `main`. Tag via:

```bash
scripts/auto-push-tag.command v9.1.3
```

The auto-push-tag helper now defaults to the most-recent tag
(see W159 / ff8a1f2), so a bare `auto-push-tag.command` pushes
whatever's freshest.
