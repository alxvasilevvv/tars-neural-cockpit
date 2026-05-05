# TARS ↔ meeet.world billing (authoritative operator plane)

**Status:** contract for cross-stack integration.  
**Prod reference (2026-05-05):** authoritative billing edge is live on meeet core Supabase project **`zujrmifaabkletgnpoyw`** — deploy **`tars-billing`** at `https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/tars-billing`, table **`tars_billing_usage_dedupe`** for **`POST /operator/usage`** idempotency; operator smoke + anon RLS check passed (Lovable). TARS `remote` mode must use the same **`MEEET_BILLING_API_KEY`** as the function secret **`TARS_BILLING_API_KEY`**.

**Principle:** **meeet.world** owns accounts, SOL / $MEEET settlement, tier state,
and **authoritative consumption** for cloud capacity. TARS remains local-first:
it mirrors that state for the cockpit and **must not** grant paid cloud capacity
when the remote plane is unreachable (fail closed for `cloud`).

## Environment (TARS host)

| Variable | Required when | Meaning |
|----------|---------------|---------|
| `TARS_BILLING_SOURCE` | optional | `local` (default) — legacy `~/.tars/entitlements.json` + local usage ledger. `remote` — tier / caps / cloud gate from meeet.world. |
| `MEEET_BILLING_BASE_URL` | `remote` | Base URL with **no** trailing slash. TARS calls `{BASE}/operator`. Typical deploy: Supabase edge `https://<project-ref>.supabase.co/functions/v1/tars-billing`. A reverse proxy may instead expose `https://meeet.world/api/tars-billing/v1` mapping to the same function. |
| `MEEET_BILLING_API_KEY` | `remote` | Shared secret; sent as `Authorization: Bearer <key>`. Must match Supabase secret `TARS_BILLING_API_KEY` or `MEEET_BILLING_API_KEY` on the billing function. |
| `TARS_OPERATOR_ID` | optional | Opaque id for this seat (future multi-host); sent as `X-Tars-Operator-Id`. |
| `MEEET_BILLING_MAX_DELTA_USD` | optional | When TARS mirrors cloud spend per `usage.tokens`, cap each POST body `delta_usd` at this value (default **50**). |
| `MEEET_BILLING_USAGE_RETRIES` | optional | Attempts for `POST /operator/usage` on transient HTTP / transport errors (default **3**, clamped **1–8**). Exponential backoff between attempts. |

## HTTP — meeet.world implements

### `GET {MEEET_BILLING_BASE_URL}/operator`

**Headers**

- `Authorization: Bearer <MEEET_BILLING_API_KEY>`
- `X-Tars-Operator-Id: <optional>` — stable id for this TARS installation.

**Response 200** (`application/json`)

```json
{
  "ok": true,
  "contract_version": "1.0.0",
  "tier": "free",
  "byo_enabled": false,
  "live": {
    "spent_usd_24h": 0.0,
    "cap_usd_daily": 0.0,
    "remaining_usd": 0.0,
    "allowed_cloud": false,
    "reason": null
  },
  "checkout": {
    "pro": "https://meeet.world/billing/tars?plan=pro",
    "business": "https://meeet.world/billing/tars?plan=business"
  },
  "account_url": "https://meeet.world/account"
}
```

**Semantics**

- `tier` — one of `free` | `pro` | `business` (same strings as TARS `Tier`).
- `live` — **authoritative** for cloud LLM gating when `TARS_BILLING_SOURCE=remote`:
  - `allowed_cloud` — if `false`, TARS must treat cloud routes as blocked (same UX as local cap).
  - `spent_usd_24h` / `cap_usd_daily` / `remaining_usd` — cockpit display; TARS does not recompute
    these from the local meeet SQLite when remote is healthy.
- `checkout.*` — HTTPS URLs where the user completes **SOL / $MEEET** payment on meeet.world.
- `account_url` — profile / subscription management on meeet.world.

**Errors**

- Non-200 or malformed JSON → TARS fails **closed** for cloud (`can_run` reason `billing_unreachable`)
  and `GET /api/entitlements` falls back to the local JSON snapshot with `billing.remote_ok: false`.

### `POST {MEEET_BILLING_BASE_URL}/operator/usage`

**When:** `TARS_BILLING_SOURCE=remote` and TARS emits `usage.tokens` with route `cloud` | `fallback` | `mixed` and a positive `cost_usd` in the payload (after the event is persisted locally).

**Headers** — same as `GET /operator` (`Authorization`, optional `X-Tars-Operator-Id`).

**Body** (`application/json`)

```json
{
  "delta_usd": 0.012345,
  "trace_id": "trc_…"
}
```

- `delta_usd` — positive finite USD increment for the rolling 24h window (server rejects non-positive or absurd values; per-request cap **500** USD on the edge; TARS may further cap via `MEEET_BILLING_MAX_DELTA_USD`).
- `trace_id` (optional) — opaque string (≤256 chars after trim). When present, the billing edge records it in **`tars_billing_usage_dedupe`** before applying spend. A second POST with the same `trace_id` returns **200** with **`duplicate: true`** and the current `live`-style fields **without** incrementing spend again (idempotent retry safe).
- `idempotency_key` (optional, edge alias) — same semantics as `trace_id` if the host accepts it; prefer **`trace_id`** for TARS ↔ meeet alignment with ingest traces.

**Response 200** (applied)

```json
{
  "ok": true,
  "contract_version": "1.0.0",
  "operator_id": "default",
  "delta_usd": 0.012345,
  "spent_usd_24h": 0.05,
  "cap_usd_daily": 0.333333,
  "remaining_usd": 0.283333,
  "allowed_cloud": true,
  "reason": null,
  "duplicate": false
}
```

**Response 200** (dedupe hit — same `trace_id` / key as a prior successful apply)

- Body includes **`"duplicate": true`** and current operator spend / gate fields; **`delta_usd`** in the response reflects the **original** request increment (for logging); **spent** counters are unchanged.

**Errors** — `400` invalid body / delta, `401` bad Bearer, `5xx` DB. Failures on this POST **do not** roll back the local meeet event store (best-effort mirror). TARS retries transient codes (**408**, **425**, **429**, **500–504**) and URL / timeout-style errors per `MEEET_BILLING_USAGE_RETRIES`.

### Consumption & shared data

- **Authoritative DB** lives on meeet.world. TARS **POSTs** incremental `delta_usd` from priced
  `usage.tokens` on cloud-class routes so `spent_usd_24h` on the operator row stays authoritative.
  TARS still emits the same events into the local meeet store and ingest for debugging / replay.

### `POST` upgrade / BYO on TARS when `remote`

- `POST /api/entitlements/upgrade` (paid tier) → **does not** mutate local tier; returns
  `delegated: true` + `redirect` from `checkout.{tier}` when present.
- `POST /api/entitlements/byo` → **503** `feature_disabled` with hint to toggle BYO on meeet.world
  until a delegated endpoint exists.

---

**Version:** 1.2.0 — 2026-05-05 (`trace_id` dedupe on edge, client retries, TARS mirror passes trace).
