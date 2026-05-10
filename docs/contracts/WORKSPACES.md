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
