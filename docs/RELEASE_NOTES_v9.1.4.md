# TARS v9.1.4 — release notes

**Released:** 2026-05-13 (Waves 171-173)
**Channel:** stable · additive over v9.1.3
**Platforms:** macOS + Linux + **Windows** (daemon trifecta now complete)
**Codename:** Phase L10.3 — cross-platform observability

## What's in this release

v9.1.4 closes the daemon cross-platform trifecta (Windows joins
macOS + Linux) and extends doctor observability with 3 new
checks. Plus a `--watch` continuous tail mode brings CLI parity
with the HTML dashboard's auto-refresh.

## TL;DR — one paragraph

`scripts/tars-daemon install` now works on Windows (Task
Scheduler), Linux (systemd user-unit), and macOS (LaunchAgent)
with a single command — platform auto-detected. `tars-doctor`
gains `--watch` for live tailing in the terminal, plus 3 new
checks: LLM provider keys configured?, disk space at `~/.tars/`,
daemon log file freshness. The doctor REGISTRY grows from 8 → 11
checks. All operator surfaces (CLI, HTTP, HTML dashboard) pick
up the new checks automatically.

## Wave-by-wave changelog

### W171 — Windows Task Scheduler parity

- `backend/core/daemon/windows.py` — new module.
- `WindowsTaskConfig` dataclass + `render_task_xml()` builds the
  full Task Scheduler XML schema with:
  - `LogonTrigger` — runs at user logon (matches mac/linux posture)
  - `RestartOnFailure` — 30s interval, 999 retries
  - `Priority=7 (Background)` — matches launchd Background type
  - `MultipleInstancesPolicy=IgnoreNew` — won't double-spawn
  - `LeastPrivilege RunLevel` — no admin escalation
- `install_task()` — UTF-16 XML to temp, `schtasks /Create /XML`
- `uninstall_task()` — `schtasks /Delete /F`; treats "cannot find"
  as success (idempotent)
- `task_status()` — parses `schtasks /Query /FO LIST` for the
  Status line
- `__main__.py` platform dispatch grows the `schtasks` branch +
  `--render-task` flag + `--platform schtasks` override
- 7 new tests; daemon test suite now 34 cases covering all three
  service managers via mocked subprocess

### W172 — `tars-doctor --watch` continuous tail

- `--watch` runs `run_all()` every `--interval` seconds
  (default 30s, floor 1s)
- `--max-ticks N` exits after N ticks (default 0 = forever)
- Output is **quiet by design**: prints only rows whose status
  changed since the previous tick. First tick prints any non-ok
  rows (initial state). Steady-state ok rows stay silent.
- `Ctrl+C` returns rc=0 with `(watch stopped)` footer — clean
  shutdown, no traceback
- Header line: `TARS doctor — watch mode (interval Ns, max-ticks ∞)`
- Per-transition: `[HH:MM:SS] ⚠ vault WARN heartbeat stale`
- 2 new tests verify the only-on-transition behaviour

### W173 — three new doctor checks

- `check_llm_provider` — verifies `ANTHROPIC_API_KEY` /
  `OPENAI_API_KEY` (or `TARS_*` prefixed variants). Status: warn
  if neither set, ok otherwise. Redacted preview in `details`
  (`sk-ant-…xyz`) so operators can sanity-check without leaking.
- `check_disk_space` — `shutil.disk_usage(~/.tars)`. Below 100 MB
  = fail, below 1 GB = warn, else ok. Important because the
  SQLite stores (clone, cowork, receipts, webhooks) all live here.
- `check_log_freshness` — `~/.tars/daemon.out.log` mtime.
  Below 5 min = ok, below 1 hour = warn, else fail with
  `daemon may be hung` suggestion. Complementary signal to the
  heartbeat check.
- Doctor REGISTRY grows from 8 → 11 entries. All consumers
  (CLI, HTTP, HTML dashboard, drift webhook) pick them up
  automatically.

## New CLI flags

| Flag | Wave |
| --- | --- |
| `tars-doctor --watch` | W172 |
| `tars-doctor --interval N` | W172 |
| `tars-doctor --max-ticks N` | W172 |
| `python -m backend.core.daemon --render-task` | W171 |
| `--platform schtasks` (alongside launchd/systemd/auto) | W171 |

## New doctor checks (W173)

| Slug | Status semantics |
| --- | --- |
| `llm_provider` | warn if no keys; ok if at least one |
| `disk_space` | < 100 MB fail; < 1 GB warn; else ok |
| `log_freshness` | < 5 min ok; < 1 hour warn; else fail; skip if no log yet |

## Doctor surface inventory after v9.1.4

- **11 health checks** across daemon / autopilot / storage
- **3 fixers** (vault auto-applied; daemon + scheduler skip-with-hint)
- **CLI flags:** `--list`, default, `--check`, `--fix`,
  `--test-notify`, `--watch`, `--json`, `--quiet`, `--timeout`
- **HTTP routes:** `GET /api/doctor*`, `POST /api/doctor/fix*`,
  `POST /api/doctor/test/notify`
- **HTML dashboard:** auto-refresh + Fix buttons + Test button +
  toast feedback

## Daemon platform inventory after v9.1.4

| Platform | Service definition | Install command |
| --- | --- | --- |
| macOS (darwin) | `~/Library/LaunchAgents/com.tars.background.plist` | `scripts/tars-daemon install` |
| Linux | `~/.config/systemd/user/tars-background.service` | `scripts/tars-daemon install` |
| Windows | Task Scheduler task `tars-background` | `python -m backend.core.daemon --install` |

Auto-detected — operator runs the same command, dispatcher
routes by `sys.platform`. Override with `--platform <slug>` if
needed.

## Honest framing

- **Windows tests run via mocked subprocess.** Real Windows CI
  in a Windows GitHub Actions matrix is on the v9.2 roadmap;
  for now the unit tests verify XML rendering + install/uninstall
  dispatch shape against mocked `schtasks.exe`.
- **`log_freshness` may flap.** A daemon that's healthy but
  silent (no events to log) can drift to `warn` after an hour.
  The threshold is conservative — v9.2 may add a heartbeat-log
  emit to keep this row green during quiet periods.
- **`llm_provider` only checks env presence.** It never calls
  Anthropic / OpenAI. A wrong/expired key still returns `ok`.
  Real key validation requires a network probe; we stay local.

## Migration

Zero breaking changes. v9.1.4 is purely additive over v9.1.3:

- No new env vars (the doctor checks read existing ones)
- New CLI flags + endpoints are opt-in
- Existing operator scripts work unchanged

## Testing

10 new test cases (165+ cumulative this release cycle):

- `tests/test_daemon.py` — 34 cases (Windows path: 7)
- `tests/test_doctor.py` — 23 cases (W173: +8)
- `tests/test_doctor_fixers.py` — 21 cases (W172: +2)

All run on pure stdlib; cross-platform paths fully mocked.

## Roadmap

- **W175-W178:** AI Clone v0.3 — ed25519 signed envelopes
- **W179-W182:** Cockpit React rebuild atop CF Pages skeleton
- **v9.2:** Per-severity routing in notifications, group-chat
  iMessage, HTML email, cockpit Background status panel

## Tagging

This release sits at `dced5f2` on `main`. Push the tag:

```bash
scripts/auto-push-tag.command v9.1.4
```

The auto-push-tag helper defaults to the most-recent tag (per
W159), so a bare invocation pushes whatever's freshest.
