# TARS — Backend Catalog

> **For:** Claude (Lovable-side / meeet.world agent)
> **By:** Cursor (TARS-side agent)
> **Date:** 2026-05-01
> **Supabase ref:** `hhpaukjobskcwkxbgecl`

The full surface area of the TARS-side backend is intentionally tiny:
2 Edge Functions and 1 Postgres table. Everything else lives in the
client (Tauri / browser) or rides on `core-bridge`.

## Edge Functions

### `tars-downloads`

Source: `supabase/functions/tars-downloads/index.ts` (in
[meeet-solana-state-941a6045](https://github.com/alxvasilevvv/meeet-solana-state-941a6045)
because that repo is the operational home of every Edge Function on
this project. Cursor authors there and Lovable owns the deployment
trigger).

**Endpoint:** `GET https://hhpaukjobskcwkxbgecl.supabase.co/functions/v1/tars-downloads`

**Purpose:** serves the TARS desktop releases manifest. Consumed by:

- `experiments/neural-showcase-v3/src/lib/downloads.ts` (the website)
- The Tauri auto-updater (post-launch, planned)
- Anything that wants the latest DMG / signature / changelog URL

**Request:** no body, no auth. Optional `?platform=mac|win|linux` query.

**Response (JSON, contract `1.0.0`):**

```json
{
  "contract_version": "1.0.0",
  "generated_at": "2026-05-01T00:00:00Z",
  "releases": [
    {
      "version": "v0.9.0-rc.1",
      "channel": "stable",
      "platforms": {
        "mac-arm64": {
          "url": "https://meeet.world/dl/tars-v0.9.0-rc.1-mac-arm64.dmg",
          "sha256": "<hex>",
          "size_bytes": 89234567
        },
        "mac-x64": { ... },
        "linux-x64": { ... }
      },
      "released_at": "2026-04-29T00:00:00Z",
      "release_notes_url": "https://tars.meeet.world/changelog#v0-9-0-rc-1"
    }
  ]
}
```

**Failure modes:**
- `403 origin_not_allowed` — caller's `Origin` not in
  `TARS_ALLOWED_ORIGINS` env var.
- `5xx` — Supabase function runtime issue. Check `Functions > Logs`.

**Env vars (function side):**
- `TARS_ALLOWED_ORIGINS` — comma-separated. Default
  `"https://meeet.world,https://tars.meeet.world"`.
- `TARS_DOWNLOADS_MANIFEST_URL` — optional; when set, the function
  fetches the manifest from this URL instead of returning the inline
  fallback.

### `tars-ingest`

**Endpoint:** `POST https://hhpaukjobskcwkxbgecl.supabase.co/functions/v1/tars-ingest`

**Purpose:** receives every TARS-side analytics / observability event.
Inserts into `public.tars_event_ingest`.

**Request (JSON, contract `1.0.0`):**

```json
{
  "kind": "tars.page.viewed",
  "trace_id": "<uuid>",
  "session_id": "ses_<rand>",
  "contract_version": "1.0.0",
  "payload": { "path": "/install", "source": "edge_middleware" }
}
```

**Auth:** one of:
- `Authorization: Bearer <TARS_INGEST_API_KEY>` (preferred)
- `x-api-key: <TARS_INGEST_API_KEY>` (legacy)
- If `TARS_INGEST_API_KEY` is unset on the function, all callers are
  allowed (bootstrap mode — to be removed before public launch).

**Response (200):**

```json
{
  "ok": true,
  "persisted": true,
  "trace_id": "<uuid>",
  "row_id": "<uuid>"
}
```

`persisted: false` is **not an error** — it means the
`tars_event_ingest` table is missing (safe-mode). Run the migration
`20260430094500_tars_event_ingest.sql`.

**Failure modes:**
- `401 unauthorized` — bad / missing API key.
- `403 origin_not_allowed` — see `tars-downloads`.
- `400 schema_error` — `kind`, `trace_id`, `session_id`, or
  `contract_version` missing or malformed (see
  `docs/contracts/relay_event.schema.json`).
- `5xx` — Supabase function runtime issue.

## Postgres tables

### `public.tars_event_ingest`

Migration: `supabase/migrations/20260430094500_tars_event_ingest.sql`.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid primary key default gen_random_uuid()` | |
| `created_at` | `timestamptz default now()` | indexed |
| `kind` | `text not null` | dotted, e.g. `tars.page.viewed` |
| `trace_id` | `text not null` | indexed |
| `session_id` | `text not null` | indexed |
| `contract_version` | `text not null` | pinned `1.0.0` today |
| `source` | `text` | optional, e.g. `edge_middleware`, `desktop`, `core_bridge` |
| `payload` | `jsonb not null default '{}'` | free-form |

RLS: not enabled — only the `tars-ingest` Edge Function (using the
project's service role) writes. Reads are gated through Supabase auth.

## Local development entry points

```bash
make cockpit              # vite dev server on :5173
make cockpit-build        # production build → dist/
make cockpit-tsc          # noEmit type check
make cockpit-test         # vitest run

make desktop-dev          # Tauri shell against the dev cockpit
make desktop-build        # release artifact (.dmg / .app on macOS)

make smoke-core-bridge    # full e2e against core-bridge → tars-ingest
make smoke-tars-bridge    # tars-downloads + tars-ingest sanity
make acceptance-tars-meeet # 7-gate acceptance against live tars.meeet.world

make gate-control-tower   # cockpit-tsc + cockpit-test + smoke-core-bridge
```

## Where Cursor stages new backend changes

1. Edit `supabase/functions/<name>/index.ts` in
   `meeet-solana-state-941a6045` (the meeet-core repo).
2. Open a PR there on a `cursor/<topic>` branch.
3. Tag Claude on the PR.
4. Once merged, Lovable auto-deploys the Edge Function (typically
   <2 min after merge).
5. Cursor runs `make smoke-tars-bridge` against the new deploy to
   confirm.

For the TARS-side Postgres schema, the same flow but the migration
goes via `npx supabase db query --linked --file ...` against the
`hhpaukjobskcwkxbgecl` project. Cursor owns this command path; it does
not transit Lovable.
