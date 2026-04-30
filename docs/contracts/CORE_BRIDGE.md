# Contract: meeet core ↔ TARS bridge (`core-bridge`)

> Version: **1.0.0**
> Producer: meeet core Supabase (`zujrmifaabkletgnpoyw`), function `core-bridge`
> Consumer: TARS Supabase (`hhpaukjobskcwkxbgecl`), function `tars-ingest`
> Smoke: `make smoke-core-bridge` (in TARS repo) — must be green before any
> bump.
> Schema: `docs/contracts/relay_event.schema.json` (this directory).

This is the canonical contract for the cross-project bridge between the
meeet core (Lovable-managed) and TARS (Cursor-managed) Supabase
projects. Any change to the request / response shape requires a paired
PR in both repos plus a `contract_version` bump.

---

## Endpoints

Mounted at `https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/core-bridge`.

| Method | Path             | Auth                            | Purpose                                     |
| ------ | ---------------- | ------------------------------- | ------------------------------------------- |
| GET    | `/health`        | `x-bridge-secret` + Origin      | Liveness probe                              |
| GET    | `/token-stats`   | `x-bridge-secret` + Origin      | Public-safe $MEEET stats (staked / burned)  |
| POST   | `/relay-event`   | `x-bridge-secret` + Origin      | Forward `TARSEvent` to `tars-ingest`        |

### Required headers

- `Origin`: must be one of the allowlist:
  - `https://meeet.world`
  - `https://tars.meeet.world`
- `x-bridge-secret`: matches `BRIDGE_SHARED_SECRET` env on the
  function (constant-time compared).

### Failure modes

| Code | Body                                                                 | Cause                                       |
| ---- | -------------------------------------------------------------------- | ------------------------------------------- |
| 401  | `{"error":"unauthorized"}`                                           | Missing or wrong `x-bridge-secret`          |
| 403  | `{"error":"origin_not_allowed"}`                                     | Origin header outside allowlist             |
| 400  | `{"error":"invalid_payload","required":[...]}`                       | `relay-event` schema validation failed      |
| 400  | `{"error":"invalid_json"}`                                           | `relay-event` body was not valid JSON       |
| 404  | `{"error":"not_found","path":"<seg>"}`                               | Unknown trailing path segment               |
| 500  | `{"error":"stats_unavailable"}`                                      | Postgres view fetch failed for token-stats  |
| 500  | `{"error":"relay_unconfigured"}`                                     | `TARS_INGEST_API_KEY` env missing on bridge |
| 500  | `{"error":"internal_error"}`                                         | Unhandled exception (masked)                |
| 502  | `{"ok":false,"upstream_status":...,"trace_id":...,"response":...}`   | `tars-ingest` returned non-2xx              |

---

## `POST /relay-event` request schema

See `docs/contracts/relay_event.schema.json` (JSON Schema 2020-12).
All five top-level fields are required and validated by string type
on the bridge before being forwarded.

### Minimal example

```json
{
  "kind": "tars.page.viewed",
  "trace_id": "trace_smoke_001",
  "session_id": "ses_smoke_001",
  "contract_version": "1.0.0",
  "payload": { "path": "/tars", "source": "smoke" }
}
```

### Notes
- `kind`: dotted path. Convention: `<source>.<surface>.<verb>`.
- `trace_id` / `session_id`: opaque strings, length ≤ 128.
- `contract_version`: pin **exactly** to the producer's TARS contract
  version (today: `1.0.0`).
- `payload`: free-form JSON object. Additive keys are fine. Don't put
  PII or secrets in here — the bridge logs the upstream status.

---

## `POST /relay-event` response

Always returns the upstream `tars-ingest` outcome wrapped:

```json
{
  "ok": true,
  "upstream_status": 200,
  "trace_id": "trace_smoke_001",
  "response": {
    "ok": true,
    "accepted": 1,
    "persisted": true,
    "trace_ids": ["trace_smoke_001"]
  }
}
```

`ok` mirrors `upstream.ok`. HTTP code is 200 on success, 502 on
upstream failure.

---

## Versioning rules

- **Additive change** (new optional payload key on either side):
  no version bump required, but document it here.
- **Breaking change** (rename / remove a field, change required
  semantics): bump `contract_version` to next minor (`1.0.0` →
  `1.1.0`); ship paired PRs in both repos same day.
- **Origin allowlist change**: requires SYNC notice
  (`docs/SYNC.md` §9).
- **Secret rotation**: requires both sides re-run
  `make smoke-core-bridge` post-rotation.

---

## Smoke procedure

Single command from TARS repo root:

```bash
BRIDGE_SHARED_SECRET=<secret> make smoke-core-bridge
```

Exit non-zero if any of these fail:
1. `GET /health` → `200 OK`
2. `GET /token-stats` → `200 OK`
3. `POST /relay-event` → `200 OK` + `persisted:true`
4. `GET /health` without secret → `401 unauthorized`
5. `POST /relay-event` from disallowed Origin → `403 origin_not_allowed`

The script lives at `scripts/smoke_core_bridge_e2e.sh`.

---

## Related contracts

- `MEEET_DOWNLOADS.md` — public download manifest contract (1.0.0).
- `ANALYTICS.md` — frontend `tars.<area>.<action>` event naming.
- `TARS_SUBDOMAIN.md` — `tars.meeet.world` routing.
