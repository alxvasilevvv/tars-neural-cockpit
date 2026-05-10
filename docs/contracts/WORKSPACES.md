# Workspaces — multi-tenant design contract (Cursor implements)

This document is the design spec Cursor will implement for the
Workspaces feature. It is **design-only**: there is no backend or
frontend code yet. Anything below that contradicts the existing
single-tenant code is an intentional shift the implementer should
follow rather than a description of current behavior.

## Goals

1. Allow a single TARS deployment (cloud or self-hosted) to host
   multiple operator teams without leaking data across them.
2. Preserve the operator-as-owner model — every workspace has at
   least one owner, and everything inside the workspace is scoped to
   it.
3. Make migration from the current single-tenant database mechanical:
   one new column on every tenant-scoped table, one backfill, one
   middleware change.

## ER schema

Two new tables.

### `workspaces`

| Column | Type | Notes |
| ------ | ---- | ----- |
| `id` | uuid pk | |
| `slug` | text unique | URL-safe, e.g. `acme-fund` |
| `name` | text | display name |
| `created_at` | timestamptz | |
| `owner_user_id` | uuid fk → users.id | initial owner; cannot be deleted |
| `tier` | text | `free` / `pro` / `business` / `enterprise` |
| `seats_purchased` | int | denormalized from billing |

### `memberships`

| Column | Type | Notes |
| ------ | ---- | ----- |
| `id` | uuid pk | |
| `workspace_id` | uuid fk → workspaces.id | |
| `user_id` | uuid fk → users.id | |
| `role` | text | `owner` / `admin` / `operator` / `viewer` |
| `invited_by` | uuid fk → users.id | nullable for the first owner |
| `accepted_at` | timestamptz | nullable until invite is accepted |

Unique index on `(workspace_id, user_id)`.

### Tenant-scoped tables

Every table that today carries a `user_id` foreign key gains a
`workspace_id` column with the same nullability + a non-null
constraint after backfill. Affected tables (non-exhaustive):

- `playbooks`, `playbook_runs`, `playbook_run_steps`
- `receipts`, `receipt_anchors`
- `memory_facts`, `memory_reflections`
- `connector_credentials`
- `agent_sessions`, `agent_session_participants`
- `skill_installs`, `skill_payouts`

## Roles

| Role | Read | Write | Settings | Billing | Members |
| --- | --- | --- | --- | --- | --- |
| `owner` | all | all | yes | yes | yes |
| `admin` | all | all | yes | no | yes |
| `operator` | all | own + workspace shared | no | no | no |
| `viewer` | all | none | no | no | no |

There is exactly one workspace owner at any time. Ownership transfer
is a privileged operation that requires the current owner's signed
confirmation.

## JWT claims

Every issued JWT MUST carry these new claims in addition to the
existing `sub` (user id):

```json
{
  "sub": "user_uuid",
  "workspace_id": "workspace_uuid",
  "role": "operator",
  "tier": "pro",
  "exp": 1746825600
}
```

`workspace_id` is required for every API call against a tenant-scoped
endpoint. The `role` claim is the source-of-truth for RBAC checks —
never re-read from the database in the request path.

When a user belongs to multiple workspaces, the frontend issues a
"workspace switch" call that mints a new JWT scoped to the chosen
workspace. The previous token continues to be valid until expiry.

## Middleware contract

A new middleware (`require_workspace`) sits in front of every
tenant-scoped route. Its responsibilities:

1. Decode the JWT and assert `workspace_id` is present.
2. Inject `workspace_id` and `role` into request state for downstream
   handlers and ORM filters.
3. Inject a SQL filter such that every query against a tenant-scoped
   table is automatically `WHERE workspace_id = :workspace_id`. If the
   ORM does not support this transparently, every repository function
   gains an explicit `workspace_id` parameter and the linter rejects
   any query that omits it.
4. Reject the request with HTTP 403 if `role` is below the minimum
   required for the route.

## RBAC matrix

| Endpoint | owner | admin | operator | viewer |
| --- | --- | --- | --- | --- |
| `GET /api/playbooks` | yes | yes | yes | yes |
| `POST /api/playbooks` | yes | yes | yes | no |
| `POST /api/playbooks/{id}/run` | yes | yes | yes | no |
| `GET /api/receipts` | yes | yes | yes | yes |
| `POST /api/receipts/anchor` | yes | yes | no | no |
| `GET /api/memberships` | yes | yes | yes | yes |
| `POST /api/memberships/invite` | yes | yes | no | no |
| `DELETE /api/memberships/{id}` | yes | yes | no | no |
| `POST /api/workspace/transfer-owner` | yes | no | no | no |
| `POST /api/billing/checkout` | yes | no | no | no |

## Migration path from single-tenant

1. Ship the schema change with `workspace_id` nullable and a default
   workspace per existing user (slug = `personal-<userid>`).
2. Backfill: for every existing row in tenant-scoped tables, set
   `workspace_id = personal_workspace_for(user_id)`.
3. Make `workspace_id` non-nullable.
4. Ship `require_workspace` middleware; deprecate the old
   `require_user` path that doesn't carry `workspace_id`.
5. Update the JWT minting flow to include `workspace_id` + `role`.
   Old tokens continue to work via a six-week compatibility shim that
   resolves missing claims to the user's personal workspace + `owner`.
6. Delete the shim after the compatibility window.

## Open questions for Cursor

- Should `viewer` see receipt amounts or only the metadata? Current
  recommendation: full read, including amounts.
- Per-workspace billing vs per-user billing: ship with per-workspace
  to match the SaaS model; revisit if enterprise customers ask for
  per-seat split.
- Cross-workspace skill installs: ship workspace-scoped only;
  marketplace SDK already supports this.


---

## Wave 110 — what shipped (v9.1.0) vs what's deferred (v9.3)

The Wave 110 implementation is intentionally **additive only**. The
existing per-store SQLite databases (chat / agents / memory / planner
/ attachments / wallet / receipts / etc.) stay single-tenant; nothing
in those stores changes. The Workspaces module ships as a new module
that registers tenants and members but does not yet fence reads or
writes anywhere else in the codebase.

### Shipped in Wave 110 (v9.1.0)

- **Module**: `backend/core/workspaces/` (`models.py`, `store.py`,
  `roles.py`, `middleware.py`, `__init__.py`).
- **Schema**: SQLite at `~/.tars/workspaces.sqlite` with three tables
  (`workspaces`, `memberships`, `invites`). Auto-creates a "personal"
  workspace on first call so existing single-tenant code implicitly
  lives in one row without any migration.
- **RBAC**: 5 roles (`owner`, `admin`, `designer`, `analyst`,
  `viewer`) and 13 permissions. `can()` and `roles_with()` helpers
  are pure / sync / no I/O.
- **Invite flow**: `secrets.token_urlsafe(32)` tokens, 7-day default
  expiry, lazy expiry on read, accept-via-token endpoint.
- **HTTP**: `web_extras/routers/workspaces.py` with the full CRUD +
  invite surface listed in the *Endpoints* section above. `POST` on
  `/api/workspaces` and `/api/workspaces/{id}/archive` are HIL-gated
  via `policy_gate.require_confirm`.
- **Middleware**: `extract_workspace_id(request)` reads the
  `X-Workspace-Id` header (or `?workspace=` query param) and falls
  back to the `"personal"` id. `record_requested_workspace` mutates
  request state for downstream code that wants to opt in. **No
  existing endpoint is changed.**
- **FE**: `/workspaces` page (list + detail panel + invite modal +
  archive HIL confirm), `/workspaces/invite/:token` accept route,
  `<WorkspaceSwitcher />` in the nav (hidden when only the personal
  workspace exists), Cmd+K entries, Settings card pointing here.
- **Tests**: `tests/test_workspaces_store.py` and
  `tests/test_workspaces_roles.py` — 42 cases covering CRUD,
  membership, invites, RBAC matrix correctness.

### NOT yet wired (deferred to v9.3)

- **Data fencing**: existing stores keep their current per-deployment
  layout. No `workspace_id` column has been added to any other table.
- **Middleware enforcement**: `workspace_context_middleware` records
  the requested workspace but does not 403 missing / unauthorised
  values. The middleware is not yet mounted in `app.py`.
- **JWT integration**: claims (`workspace_id`, `role`, `tier`) are
  still designed-only. The brother backend (meeet.world) needs to
  mint scoped tokens before TARS can switch from `record_*` to
  `enforce_*`.
- **Multiple owners + ownership transfer**: today every workspace
  has exactly one owner and the store refuses to revoke them.
  Ownership transfer is a v9.3 deliverable.
- **Per-workspace billing**: plan column is informational only; the
  meeet.world billing surface still bills per-user. Wave 9.3 wires
  per-workspace invoicing.

### Migration plan for v9.3

The v9.3 cutover will be a one-shot, reversible migration. The shape
is intentionally identical to the design in this doc — Wave 110 is
the schema-only foundation; v9.3 just turns on the gates one store
at a time.

1. Add nullable `workspace_id` to every tenant-scoped table
   (playbooks, playbook_runs, receipts, memory_*, connector_creds,
   agent_sessions, skill_installs, files, outreach_*).
2. Backfill: every existing row gets
   `workspace_id = personal_workspace_for(user_id)`. For local
   single-tenant deployments that's just the `"personal"` row seeded
   by Wave 110 — no operator action required.
3. Make `workspace_id` NOT NULL.
4. Promote `workspace_context_middleware` to enforce mode: 403 on
   missing `workspace_id` for tenant-scoped routes.
5. Wire JWT claims (brother backend ships the new token format
   alongside).
6. Six-week compatibility shim: missing claims resolve to
   `workspace_id = "personal"` + `role = "owner"` so the existing
   single-tenant install keeps working through the migration window.
7. Delete the shim once telemetry shows zero requests without
   workspace claims.

Each step is independently reversible: a TARS_FENCE_WORKSPACE=0 env
flag at the middleware layer keeps the gate dormant if v9.3 ships
with bugs.
