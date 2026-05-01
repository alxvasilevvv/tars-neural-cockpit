# Contract — TARS Receipt-Ledger bridge

> **Status:** DRAFT v0.1
> **Owner of execution:** Lovable / Claude (`meeet.world` Supabase + producer
> path on payment success).
> **Owner of spec / consumer:** Cursor / TARS (cockpit reads
> `useTier()` + `<ReceiptList />`).
> **Resolves:** TARS#8 task 4 (pricing tier backend) follow-on.
> **Pin / wire example:** see §3.

This document is the **handshake** between meeet.world (which charges
the operator in `$MEEET` / `$SOL`) and TARS (which renders the cockpit
behind a tier-gated UI). It is **draft** because the producer side
(meeet.world Edge Functions + the on-chain settlement path) is owned
by the Lovable lane; once Claude pins exact column names and the
read endpoint URL, this file flips to `Status: SHIPPED` and the
consumer is wired in code.

Cursor ships the **consumer-side stub** today (no live
calls until §5 lands):

- `experiments/neural-showcase-v3/src/lib/tier.ts` — typed client +
  `useTier()` React hook + `TIER_GATES` constant. Returns the
  `free` tier in dev, swallows fetch failures so a missing producer
  doesn't break the cockpit. Vitest pins the matrix.

---

## 1. Tiers + feature gate map

This is the **source of truth** that meeet.world and TARS both
honour. The matrix is mirrored at `experiments/neural-showcase-v3/
src/lib/tier.ts` (`TIER_GATES` constant) so the cockpit can ship a
no-op render today and flip to live-checked on the day the producer
endpoint goes online.

| Feature                  | `free` | `pro`   | `business`     | `lifetime` |
| ------------------------ | :----: | :-----: | :------------: | :--------: |
| Modes available          |  Chat  |  All 5  |     All 5      |   All 5    |
| Messages / day           |   50   |   500   |   Unlimited    | Unlimited  |
| Background tasks         |   ❌   |   ✅    |      ✅        |    ✅      |
| Morning briefs           |   ❌   |   ✅    |      ✅        |    ✅      |
| Memory reflection        |   ❌   |   ✅    |      ✅        |    ✅      |
| Receipt-ledger UI        |   ❌   |   ❌    |      ✅        |    ✅      |
| Team collaboration       |   ❌   |   ❌    |      ✅        |    ✅      |
| Share links + UTM        |   ❌   |   ❌    |      ✅        |    ✅      |
| API access               |   ❌   |   ❌    |      ✅        |    ✅      |
| Custom persona presets   |   ❌   |   ❌    |      ❌        |    ✅      |
| Early access features    |   ❌   |   ❌    |      ❌        |    ✅      |
| Priority support         |   ❌   |   ❌    |      ❌        |    ✅      |

**Pricing reference** (informational, not part of the wire shape):

- `pro` — $19 / month
- `business` — $79 / seat / month
- `lifetime` — $299 one-time

The cockpit never enforces revenue; it just renders the matrix
above when `useTier()` returns the corresponding tier slug.

---

## 2. Source tables — meeet.world side (Lovable)

Lovable owns the producer. Suggested minimum schema:

```sql
-- meeet.world Supabase (project zujrmifaabkletgnpoyw)
create table public.tars_receipts (
  id                  uuid primary key default gen_random_uuid(),
  operator_id         uuid not null references auth.users (id) on delete cascade,
  tars_tier           text not null check (tars_tier in ('free','pro','business','lifetime')),
  amount_usd          numeric(10,2) not null,
  payment_method      text not null check (payment_method in ('MEEET','SOL','OFF_CHAIN')),
  payment_tx_hash     text,                              -- nullable for OFF_CHAIN (free promo)
  created_at          timestamptz not null default now(),
  expires_at          timestamptz,                       -- null for lifetime
  status              text not null default 'active'
                      check (status in ('active','expired','cancelled','pending')),
  chain_hash          text not null,                     -- hash-chain proof (see §4)
  contract_version    text not null default '1.0.0'
);

create index on public.tars_receipts (operator_id, status);
create index on public.tars_receipts (created_at desc);
create unique index on public.tars_receipts (payment_tx_hash)
  where payment_tx_hash is not null;
```

`status='active'` and `expires_at > now()` (or `expires_at IS NULL`)
are the **only** rows TARS treats as currently entitled. Anything
else falls back to `tier='free'`.

---

## 3. Wire shape — `GET /api/receipts`

Mounted on the meeet.world Edge Functions surface (Lovable repo,
exact path TBD; suggested
`https://meeet.world/functions/v1/tars-receipts`). The TARS cockpit
calls these via the existing `core-bridge` allowlist (Origin
`https://tars.meeet.world` is already in `ALLOWED_ORIGINS` per
`docs/contracts/CORE_BRIDGE.md`).

### 3.1 List active receipts for the calling operator

```
GET  /functions/v1/tars-receipts?status=active
Authorization: Bearer <meeet user JWT>
Origin: https://tars.meeet.world
```

```jsonc
{
  "ok": true,
  "contract_version": "1.0.0",
  "operator_id": "9c1b18c7-...-6f2",
  "receipts": [
    {
      "id":             "f3a1c8d2-...-9b1",
      "operator_id":    "9c1b18c7-...-6f2",
      "tars_tier":      "pro",                       // free | pro | business | lifetime
      "amount_usd":     19.00,
      "payment_method": "MEEET",                     // MEEET | SOL | OFF_CHAIN
      "payment_tx_hash":"5UwL...mock",
      "created_at":     "2026-05-01T18:30:00Z",
      "expires_at":     "2026-06-01T18:30:00Z",      // null for lifetime
      "status":         "active",                    // active | expired | cancelled | pending
      "chain_hash":     "0xa1b2c3..."
    }
  ],
  "count": 1
}
```

### 3.2 Fetch a single receipt by id

```
GET  /functions/v1/tars-receipts/{receipt_id}
Authorization: Bearer <meeet user JWT>
Origin: https://tars.meeet.world
```

Returns the **receipt object** above (no envelope wrapper) when the
caller's `auth.users.id` matches `operator_id`. Returns `404` with
`{"ok":false,"error":"receipt_not_found"}` otherwise (also for
foreign-operator-id to avoid leaking existence).

### 3.3 Tier resolution — what TARS actually consumes

The cockpit does not reason about line-items. It consumes a
**resolved tier** for the calling operator. Suggested helper:

```
GET  /functions/v1/tars-tier
Authorization: Bearer <meeet user JWT>
Origin: https://tars.meeet.world
```

```jsonc
{
  "ok": true,
  "contract_version": "1.0.0",
  "operator_id": "9c1b18c7-...-6f2",
  "tier": "pro",                            // free | pro | business | lifetime
  "tier_source": "receipt",                 // "receipt" | "default" | "promo"
  "active_receipt_id": "f3a1c8d2-...-9b1",  // nullable
  "expires_at":         "2026-06-01T18:30:00Z",  // nullable
  "features": [
    "modes.all",
    "messages.500_per_day",
    "background_tasks",
    "morning_briefs",
    "memory_reflection"
  ]
}
```

Resolution rule (Lovable side):

1. Pick the most recent `tars_receipts` row where `operator_id`
   matches and `status='active'` and (`expires_at IS NULL` or
   `expires_at > now()`). Use that tier.
2. Fall back to `tier='free'`, `tier_source='default'`,
   `features=[features for free]`.

`features` is the **derived projection** of the tier matrix in §1
so the cockpit can do simple `features.includes('background_tasks')`
without reproducing the matrix. Lovable owns the projection;
Cursor mirrors it in `TIER_GATES` for offline / dev.

---

## 4. Hash-chain proof (`chain_hash`)

`chain_hash` is the on-chain commitment that ties the receipt to
the payment transaction. Construction (suggested):

```
chain_hash = sha256(
  prev_chain_hash       // "" for the first receipt of an operator
  || receipt_id
  || operator_id
  || tars_tier
  || amount_usd          // serialised as "19.00"
  || payment_tx_hash     // "" for OFF_CHAIN
  || created_at          // RFC3339, UTC, no fractional seconds
)
```

`prev_chain_hash` is the `chain_hash` of the *previous* receipt for
the same operator (chronological by `created_at`). The first
receipt has `prev_chain_hash = ""`.

Verification on the TARS side is **best-effort and optional** at
launch — the cockpit trusts the meeet.world Edge Function. We pin
the algorithm here so a future on-chain verifier (or a
`receipt-ledger.audit()` Edge Function) can re-derive the chain
without ambiguity.

---

## 5. Failure modes + caching

| HTTP | Body                                                                        | Cause                                  |
| ---- | --------------------------------------------------------------------------- | -------------------------------------- |
| 200  | Resolved envelope (§3.1 / §3.2 / §3.3)                                      | OK                                     |
| 401  | `{"ok":false,"error":"unauthorized"}`                                       | Missing / invalid JWT                  |
| 403  | `{"ok":false,"error":"origin_not_allowed"}`                                 | Origin outside `ALLOWED_ORIGINS`       |
| 404  | `{"ok":false,"error":"receipt_not_found"}`                                  | Unknown receipt id (or foreign owner)  |
| 5xx  | `{"ok":false,"error":"<error_code>"}`                                       | Producer error                         |

**Cache hints (suggested):**

- `Cache-Control: private, max-age=15` on `/tars-tier` so a cockpit
  doesn't hammer the function on every render but a freshly-paid
  upgrade lands in the UI within ~15 s.
- `Cache-Control: no-store` on `/tars-receipts` (full list is the
  raw ledger; users may sort / paginate client-side).

The TARS cockpit **must** treat any non-200 response as
`tier='free'` and continue rendering. Logging is wired through
`tars.client.error` (see `docs/OBSERVABILITY.md`).

---

## 6. Producer events (meeet → TARS via core-bridge)

Whenever the producer mints, expires, or cancels a receipt, it
SHOULD emit a `relay-event` so the TARS cockpit can react in
near-real-time without polling. Already covered by
`docs/contracts/CORE_BRIDGE.md`; `kind` strings reserved for this
contract:

- `tars.receipt.minted`
- `tars.receipt.expired`
- `tars.receipt.cancelled`

Payload shape mirrors the `receipt` row (§3.1). The cockpit
listens via the existing `tars_event_ingest` SSE bridge and busts
the `useTier()` cache when one of these arrives.

---

## 7. Roadmap → SHIPPED

This file flips to `Status: SHIPPED` when **all** of the following
are true:

1. Lovable lands the `tars_receipts` table + RLS audit on
   `meeet.world` Supabase.
2. Lovable deploys `/functions/v1/tars-receipts` and
   `/functions/v1/tars-tier` Edge Functions matching §3.
3. Cursor wires `useTier()` to call `/tars-tier` (currently a
   stub — flips with a one-line change to `tier.ts`).
4. `tests/test_tier_contract.py` lands on the TARS side (mocks the
   meeet endpoint, asserts shape + cache + free fallback).

Until then this contract exists so both lanes can build against
the same blueprint.

---

## Changelog

- **0.1** (2026-05-01, Cursor) — initial draft from TARS#8 task 4
  follow-on. Tier matrix + wire shapes mirror Claude's PM update on
  the issue. Producer side is Lovable-owned; consumer
  (`useTier()` + `TIER_GATES`) ships in this batch as a no-op stub.
