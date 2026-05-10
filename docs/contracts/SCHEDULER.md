# Scheduler — Wave 97 contract

Cron-driven playbook scheduler. Replaces the tick-based autopilot
loop for time-driven triggers; durable, restart-safe, no third-party
deps (pure stdlib cron parser).

Contract version: **1.0**

## Module layout

```
backend/core/scheduler/
  __init__.py        — public re-exports
  models.py          — Schedule + RunRecord dataclasses
  cron.py            — pure-stdlib cron parser + next_after()
  store.py           — SQLite CRUD + run history + recovery
  runner.py          — async tick loop + per-schedule fire dispatch
web_extras/routers/
  scheduler.py       — REST surface under /api/scheduler/*
```

Tests:

```
tests/test_scheduler_cron.py   — 30 cases: parse, validate, next_after
tests/test_scheduler_store.py  — 12 cases: CRUD + history + recovery
```

## Cron syntax supported

Five fields plus extensions:

```
minute hour day-of-month month day-of-week
   0-59  0-23     1-31    1-12  0-6 (Sun=0)
```

Each field accepts:

- `*` — any value
- `N` — literal integer
- `A-B` — inclusive range
- `A,B,C` — explicit list (commas can mix with ranges)
- `*/N` or `A-B/N` — step values
- Day-of-week names — `MON`, `TUE`, `WED`, `THU`, `FRI`, `SAT`, `SUN`
  (case-insensitive)
- Month names — `JAN` through `DEC` (case-insensitive)
- `7` is also accepted as Sunday alias (so `0` and `7` both mean Sun)

### Vixie DOM/DOW interaction

When **both** day-of-month and day-of-week are restricted (i.e.
neither is `*`) the entry fires when **either** matches. Most
operators don't hit this corner; it's covered by
`tests/test_scheduler_cron.py::TestVixieDomDowOr`.

### Shortcuts

| Shortcut    | Equivalent     |
| ----------- | -------------- |
| `@hourly`   | `0 * * * *`    |
| `@daily`    | `0 0 * * *`    |
| `@midnight` | `0 0 * * *`    |
| `@weekly`   | `0 0 * * 0`    |
| `@monthly`  | `0 0 1 * *`    |
| `@yearly`   | `0 0 1 1 *`    |
| `@annually` | `0 0 1 1 *`    |

## Timezone handling

- Schedules carry an explicit `timezone` (TZ database name, default
  `"UTC"`). Examples: `"America/Los_Angeles"`, `"Europe/Berlin"`,
  `"Asia/Tokyo"`.
- `next_after` walks in the schedule's local timezone so DST rolls
  cleanly, then converts the firing instant back to UTC for storage.
- Unknown TZ raises `CronParseError`; the validator surfaces the
  error in the JSON body so the FE can flag invalid input.

## Restart safety

On startup the lifespan hook calls
`SchedulerStore.recover_state()`, which:

1. Reads every persisted schedule.
2. For enabled rows, recomputes `next_run_at` from `now()` using the
   stored cron + tz.
3. Writes the new cache value back.
4. Disabled rows are left alone — toggling them on later forces a
   recompute via `update_schedule({"enabled": True})`.

The runner loop then ticks every `TARS_SCHEDULER_TICK_S` seconds
(default 30s) and fires anything where `next_run_at <= now()`. This
means a process restart at most postpones one tick — no scheduled
fire is lost.

## Schedule vs Autopilot

| Trait           | Autopilot                          | Scheduler (Wave 97)              |
| --------------- | ---------------------------------- | -------------------------------- |
| Cadence         | Every agent tick (continuous)      | Cron expression (time-based)     |
| Use case        | Continuous monitoring / awareness  | Daily / hourly batch jobs        |
| Persistence     | Per-agent `autopilot=true` flag    | Dedicated `schedules` SQLite row |
| Run history     | Agent task log                     | `run_history` SQLite table       |
| Restart safety  | Loop resumes from agent state      | `recover_state` recomputes next  |
| Concurrent fire | One per agent                      | `max_concurrent` per schedule    |

Use **autopilot** when you want an agent to react continuously to
incoming signals (e.g. watch a Slack channel, ingest awareness
events). Use the **scheduler** when you want a known playbook to
run at a known cadence (e.g. "0 9 * * 1-5" — every weekday morning).

## Environment flags

| Variable                   | Default | Meaning                                       |
| -------------------------- | ------- | --------------------------------------------- |
| `TARS_SCHEDULER_ENABLED`   | unset   | Set to `1` to start the lifespan tick loop.   |
| `TARS_SCHEDULER_TICK_S`    | `30`    | Tick interval in seconds (min 1).             |
| `TARS_SCHEDULER_DB_PATH`   | `~/.tars/scheduler.sqlite` | Override DB location.        |
| `TARS_SCHEDULER_STORE`     | unset   | Set to `disabled` to short-circuit the store. |

## REST surface

All endpoints live under `/api/scheduler/*`:

- `GET    /api/scheduler/schedules` — list all
- `POST   /api/scheduler/schedules` — create
- `GET    /api/scheduler/schedules/{id}` — show one
- `PATCH  /api/scheduler/schedules/{id}` — update (enable/disable, cron, tz, args)
- `DELETE /api/scheduler/schedules/{id}` — remove (cascades run history)
- `POST   /api/scheduler/schedules/{id}/run-now` — fire immediately, doesn't shift `next_run_at`
- `GET    /api/scheduler/schedules/{id}/history?limit=N` — recent runs
- `POST   /api/scheduler/validate-cron` — `{expression, timezone?}` → `{valid, next_5_runs?, error?}`

Convenience under the playbooks router:

- `POST   /api/playbooks/{id}/schedule` — wire a cron up to a known playbook id
- `GET    /api/playbooks/{id}/schedules` — schedules attached to that playbook

## Run record statuses

| Status     | Meaning                                                |
| ---------- | ------------------------------------------------------ |
| `ok`       | All steps ran without failure or block.                |
| `failed`   | At least one step errored (after on-error: stop).      |
| `blocked`  | At least one step blocked by the policy gate.          |
| `running`  | Run in flight (transient — not normally observed).     |
| `skipped`  | Run was skipped (e.g. max_concurrent gate hit).        |
