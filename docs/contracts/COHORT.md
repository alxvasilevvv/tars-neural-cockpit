# Cohort Tracking Contract — v1.0 (Wave 94)

**Module:** `backend/core/cohort/` · **Router:** `web_extras/routers/cohort.py` · **DB:** `~/.tars/cohort.sqlite`

The cohort subsystem powers the `/workshop/cohort` facilitator dashboard
with real attendee tracking, replacing the Wave 89 mock SSE. It reuses
the same event envelope shape as the Wave 90 webhooks module so events
flow naturally between subsystems (ledger ↔ cohort ↔ webhooks).

## Lifecycle

```
create → invite → join → activity → end
   |        |       |        |        |
 POST    add_     POST     POST    POST
/cohort  attendee /join/   /action /end
         (token   {token}
          out)
```

1. **Create** — facilitator hits `POST /api/cohort` with `{name, slug?, max_attendees?}`. Returns the cohort record.
2. **Invite** — facilitator adds attendees via `POST /api/cohort/{id}/attendees` with `{display_name, email?}`. The response carries a 32-byte URL-safe **join token** — this is the only time the token is highlighted in the UI; copy it into the invite link the attendee receives.
3. **Join** — attendee opens `POST /api/cohort/join/{token}` (idempotent — pings record a fresh `join` action without duplicating the row).
4. **Activity** — every meaningful event (playbook start/finish, HIL gate hit, error, broadcast ack, phase advance) becomes an `AttendeeAction` row. Webhook envelopes are translated automatically by `events.record_from_webhook_event`.
5. **End** — facilitator hits `POST /api/cohort/{id}/end`. Record stays for analytics; can be hard-deleted via `DELETE /api/cohort/{id}` (cascades attendees + actions).

## Attendee Tokens

- 32 bytes URL-safe random (`secrets.token_urlsafe(32)` = 43 chars).
- Stored **plaintext** in SQLite. This is fine for v9.x single-tenant local installs (the DB lives in the user's home).
- **v9.3 multi-tenant note:** swap to per-cohort HMAC + token hash before TARS multi-tenant ships; the column is already indexed.
- Tokens are not rotated automatically — revoke an attendee by deleting them or flagging them.

## Event Schema (reused from webhooks)

Every action record and SSE frame mirrors the webhook envelope:

```json
{
  "id": "act_…",
  "type": "playbook_finish",
  "occurred_at": 1715300000.0,
  "data": {
    "attendee_id": "att_…",
    "display_name": "Alice C.",
    "email": "alice@x.com",
    "playbook_id": "pb_…"
  }
}
```

The router accepts any `type` string but recognises and renders these well-known types: `join`, `playbook_start`, `playbook_finish`, `hil_gate`, `error`, `phase_advance`, `broadcast_ack`, `broadcast`.

### Webhook event → action mapping

| Webhook `type`            | Cohort action  |
| ------------------------- | -------------- |
| `playbook.started`        | `playbook_start` |
| `playbook.finished`       | `playbook_finish` |
| `playbook.completed`      | `playbook_finish` |
| `playbook.failed`         | `error` |
| `hil.requested`           | `hil_gate` |
| `cohort.broadcast.ack`    | `broadcast_ack` |
| `cohort.attendee.joined`  | `join` |
| `cohort.phase.advanced`   | `phase_advance` |

Anything else passes through verbatim with `payload.source_event_type` preserved for debugging.

## Phase Lifecycle

`intake → design → test → deploy → done`

`done` is terminal. The `events.infer_phase_advance()` helper is intentionally conservative: it advances **exactly one phase** at a time, never skips, and never auto-advances past `deploy` (an explicit `phase_advance` payload is required to enter `done`).

## SSE Stream

`GET /api/cohort/{id}/stream` returns `text/event-stream`. Frames:

```
retry: 15000

id: open_…
event: stream.open
data: {"id":"open_…","type":"stream.open","occurred_at":…,"data":{"cohort_id":"coh_…"}}

id: act_…
event: playbook_finish
data: {…envelope…}
```

A synthetic `event: heartbeat` frame fires every 15 s so intermediate proxies don't kill an idle connection. The frontend filters out `heartbeat` and `stream.open` before passing events to UI state.

## Privacy

- All cohort data persists in `~/.tars/cohort.sqlite` (override with `TARS_COHORT_DB_PATH`).
- The whole module can be disabled with `TARS_COHORT_STORE=disabled` — `is_member` and `record_action_if_member` short-circuit, the router 503s.
- `DELETE /api/cohort/{id}` cascades through attendees + actions (hard delete; not soft).
- No data leaves the machine: there is no outbound network call from the cohort module itself. Webhook bridging is purely inbound (the webhooks dispatcher independently fans events out, but the cohort module only *consumes* the envelope shape).

## Hot-Path Hooks

The runner (`backend/core/playbooks/runner.py`) calls `cohort.record_action_if_member(email, type, payload)` after the Wave 90 webhook emit, wrapped in `try/except`. The helper:

1. Returns instantly if the store is disabled.
2. Returns `{matched: false}` when no attendee matches the email.
3. Records the action + publishes an SSE frame on match.

It **never raises** — every failure is swallowed at debug level.

## Contract Version

`CONTRACT_VERSION = "1.0"`. Surface bumps require:

- Adding a non-optional field to `Cohort`, `Attendee`, or `AttendeeAction`.
- Renaming any of the well-known action types (additions are backwards-compatible).
- Changing the SSE frame shape.
