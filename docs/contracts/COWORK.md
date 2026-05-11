# Cowork Contract — v1.0 (Wave 129)

**Module:** `backend/core/cowork/` · **DB:** `~/.tars/cowork.sqlite` · **Stream:** in-process pub/sub (SSE)

The cowork subsystem powers the `/cowork` and `/cowork/:slug` pages —
multi-user real-time collaboration over agent sessions. It closes the
W122 QA-audit gap on **task #99 (Shared Agent Sessions)** and **task
#100 (TARS Handoff)**, which had historically been marked complete but
shipped no live backend code.

## Mental model

A **Session** is a live collaboration room. Several **Members** (humans)
join a session; a TARS agent operates inside it. Every member has a
**role** (`owner` / `editor` / `viewer`) and a **presence** record
(updated every 10 s by a heartbeat ping). Members can publish their
**cursor** position over arbitrary client-defined paths so others see
where they are in shared files. Agent runs, cursors, chats, and handoff
state transitions are fan-out to every live subscriber via SSE.

The **owner** can initiate a **Handoff** — a one-time, short-TTL token
that transfers ownership of the session to another user (typically by
sharing a `/cowork/handoff/:token` URL).

## Lifecycle

```
create → join → heartbeat → activity → handoff? → end
   |       |       |          |          |          |
 POST    POST    POST      (events)    POST       POST
/sess   /join   /hbeat                /handoff   /end
```

1. **Create** — owner hits `POST /api/cowork/sessions` with `{name, owner_user_id, workspace_id?}`. Returns the `Session` record (id + slug + status=live).
2. **Join** — any user (or anonymous) hits `POST /api/cowork/sessions/:id/members` with `{display_name, user_id?, email?, role?}`. Returns a `Member` carrying a 32-byte URL-safe **join token** — used as the credential on every subsequent heartbeat/cursor/handoff call from that member.
3. **Heartbeat** — every 10 s the client pings `POST /api/cowork/sessions/:id/heartbeat` with `{member_token, typing?, focus_path?}`. Stale members drop off the live roster after 25 s.
4. **Cursor** — `POST /api/cowork/sessions/:id/cursor` with `{member_token, path, line, col, selection?}`. Upserts on `(session_id, member_id, path)`.
5. **Activity** — the orchestrator calls `cowork.emit_agent_frame(session_id, frame_type, payload)` on every agent step. Best-effort: failures are swallowed.
6. **Handoff** — owner hits `POST /api/cowork/sessions/:id/handoff` with `{from_user_id, to_email?}`. Returns `{token, expires_at}`. Token TTL: 15 min default.
7. **Accept** — recipient hits `POST /api/cowork/handoff/:token/accept` with `{accepted_by_user_id}`. Atomic — concurrent accepts lose the race deterministically. Ownership transfers; a `handoff.accepted` event is broadcast.
8. **End** — owner hits `POST /api/cowork/sessions/:id/end`. Session row stays for analytics; W104 compliance bundler picks it up automatically.

## Endpoints (target for brother's core-bridge)

| Method | Path                                          | Notes                                                                         |
| ------ | --------------------------------------------- | ----------------------------------------------------------------------------- |
| POST   | `/api/cowork/sessions`                        | Create session (owner-authed via core-bridge).                                |
| GET    | `/api/cowork/sessions`                        | List sessions. Optional `?workspace_id=…&active_only=1`.                      |
| GET    | `/api/cowork/sessions/:slug`                  | Fetch by slug. Returns 404 on miss.                                           |
| POST   | `/api/cowork/sessions/:id/members`            | Add a member. Returns `Member` with `token`.                                  |
| GET    | `/api/cowork/sessions/:id/members`            | List members. Always returns full roster; presence filtering is client-side. |
| POST   | `/api/cowork/sessions/:id/heartbeat`          | Body `{member_token, typing?, focus_path?}`. Returns `{ok:true}`.             |
| POST   | `/api/cowork/sessions/:id/cursor`             | Body `{member_token, path, line, col, selection?}`. Returns the `Cursor`.    |
| POST   | `/api/cowork/sessions/:id/handoff`            | Body `{from_user_id, to_email?, ttl_seconds?}`. Returns `{token, expires_at}`.|
| POST   | `/api/cowork/handoff/:token/accept`           | Body `{accepted_by_user_id}`. Returns `Handoff`.                              |
| POST   | `/api/cowork/sessions/:id/end`                | Ends session. Idempotent — second call is a no-op.                            |
| GET    | `/api/cowork/sessions/:id/stream`             | SSE stream. See **Event envelope** below.                                     |

All non-stream responses are JSON. All POST bodies are JSON.

## Member Tokens

- 32 bytes URL-safe random (`secrets.token_urlsafe(32)` = 43 chars).
- Stored **plaintext** in SQLite. Fine for v9.x single-tenant local installs (the DB lives in the user's home). v9.3 multi-tenant will move to per-workspace HMAC.
- The token is the **only credential** the client needs on subsequent calls. Treat it as a session-bearer.
- Tokens are **per-member**, not per-session — kicking one member out doesn't affect the others.

## Event envelope

Every SSE frame is a JSON object with a stable shape:

```json
{
  "id": "ev_<uuid18>",
  "type": "agent.frame" | "cursor" | "chat" | "presence"
          | "handoff.created" | "handoff.accepted" | "handoff.revoked"
          | "session.ended" | "heartbeat",
  "occurred_at": <unix-seconds-float>,
  "data": { ... type-specific ... }
}
```

A synthetic `heartbeat` frame is emitted every 15 s when there's no
real traffic — keeps the SSE connection alive through proxies that
kill idle streams. Clients should **ignore** heartbeat frames in the
visible event log (the FE filter does this already).

### `agent.frame` payload

```json
{ "frame_type": "playbook_step" | "tool_call" | "thought" | ..., "label": "<human-readable>" }
```

### `cursor` payload

```json
{ "member_id": "cm_…", "path": "plan.md", "line": 12, "col": 5 }
```

### `handoff.*` payloads

`handoff.created` → `{ handoff_id, to_email | null, expires_at }`.
`handoff.accepted` → `{ handoff_id, accepted_by_user_id, from_user_id }`.
`handoff.revoked` → `{ handoff_id }`.

## Storage

SQLite at `~/.tars/cowork.sqlite` (override with `TARS_COWORK_DB_PATH`).
WAL + foreign_keys ON. Four tables:

- `sessions(id, name, slug, owner_user_id, status, created_at, ended_at, workspace_id, metadata_json)`
- `members(id, session_id, user_id, display_name, email, role, token, joined_at, color, last_seen_at)` — `token` UNIQUE.
- `cursors(id, session_id, member_id, path, line, col, selection_json, updated_at)` — UNIQUE `(session_id, member_id, path)` for upsert semantics.
- `handoffs(id, session_id, from_user_id, to_email, token, created_at, expires_at, accepted_at, accepted_by_user_id, revoked_at)` — `token` UNIQUE.

Disable the entire module with `TARS_COWORK_STORE=disabled` (the hot-path helpers short-circuit).

## Presence semantics

- Tracker is **in-process**. v9.3 multi-tenant will swap to Redis.
- A member is **present** when `now - last_seen_at < 25 s` (`PRESENCE_TTL_S`).
- The frontend pings at 10 s cadence → up to 2 missed beats of slack before a presence dot flips grey.
- Stale records are filtered on read; a periodic `gc()` cleans them up. Cheap enough to call inside the SSE heartbeat tick.

## Concurrency + safety

- **Handoff accept** is atomic via conditional `UPDATE … WHERE accepted_at IS NULL AND revoked_at IS NULL AND expires_at > now`. Two concurrent accepts can't both win.
- **Ownership transfer** happens in the same logical transaction as the accept (back-to-back writes; race window is microseconds).
- **Member tokens** are checked at every call site that mutates state. The brother's core-bridge enforces auth at the HTTP layer; the Python module trusts the caller to validate.
- **Workspace fencing** is not yet enforced in this contract version. The `workspace_id` column ships in v1.0 for forward compatibility; data isolation lands in v9.3 alongside the rest of W110 multi-tenant work.

## Integration touchpoints

- **Orchestrator** — calls `cowork.emit_agent_frame(session_id, frame_type, payload)` on every step. Best-effort, swallows exceptions.
- **W90 webhooks** — outgoing webhook on `cowork.handoff.accepted` is a v9.2 candidate (not shipped in W129).
- **W104 compliance export** — automatically includes the `cowork_*` tables in the audit bundle (W104 walks every SQLite DB under `~/.tars/`).
- **W110 workspaces** — sessions carry an optional `workspace_id`. UI surfaces the workspace badge on each session card (planned v9.3).

## What v9.3 will change

- **Multi-tenant fencing** — `workspace_id` becomes mandatory and every read/write filters by the caller's workspace membership.
- **Presence backend** — swap in-process tracker for Redis so multi-process bridges can share state.
- **SSE → WebSocket option** — bidirectional channel for cursor publishes (today the client POSTs each cursor move — fine at human cadence, but a WebSocket halves latency on chatty sessions).
- **Per-workspace token HMAC** — replace plaintext member tokens with HMAC-signed bearers so a leaked DB doesn't grant cross-workspace access.

## Contract version

`backend.core.cowork.CONTRACT_VERSION = "1.0"`. Bump on any breaking
change to endpoint shapes or event envelope. Additive fields are OK
without a bump — the FE tolerates unknown keys.
