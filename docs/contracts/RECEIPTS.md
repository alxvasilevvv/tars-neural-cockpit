# Receipts contract (Wave 95 · contract version 1.0)

The unified TARS receipt ledger replaces the scattered receipt
emitters (`wallet/audit.py` signed wallet events, `meeet/store.py`
unsigned event mirror) with a single tamper-evident, hash-chained,
ed25519-signed stream. B2B compliance reviewers get **one**
verifiable trail.

## Receipt envelope

```jsonc
{
  "id":         "rcpt_<24 hex>",
  "ts":         1736464800.123,        // unix seconds, UTC
  "type":       "playbook.completed",  // dotted lowercase
  "actor":      "operator|agent:<id>|wallet:<id>|system:<comp>",
  "resource":   "playbook-id|wallet-tx-sig|null",
  "payload":    { ... },               // arbitrary, sort-keys canonical
  "prev_hash":  "<sha256 hex of previous receipt or empty>",
  "hash":       "<sha256 hex over canonical body>",
  "signature":  "<base64 ed25519 over hash bytes>",
  "public_key": "<base64 ed25519 verify key>"
}
```

`payload` is a free-form dict. Operators **MUST hash or scrub PII
before storing** (see Privacy below).

## Chain construction

Each receipt's `hash` is the lower-case hex sha256 of the canonical
JSON list

    [prev_hash, round(ts, 6), type, actor, resource, payload]

serialised with `json.dumps(..., sort_keys=True,
separators=(',', ':'), ensure_ascii=False)` and UTF-8 encoded.

`prev_hash` is the previous receipt's `hash`, or the empty string for
the very first receipt. The chain is single-process, single-host: if
multiple TARS instances need to share a ledger, they MUST coordinate
through a shared SQLite (or move to a per-host suffix, planned for
v9.3).

## Signing

`signature` is a 64-byte ed25519 signature over the **hash bytes**
(`bytes.fromhex(hash)`), base64 encoded. The signing key lives in
`~/.tars/host-key.json` (override via `TARS_RECEIPT_HOST_KEY_PATH`).
Mode 0600. On first append, a fresh keypair is generated.

`public_key` is the matching ed25519 verify key, base64 encoded,
embedded in **every receipt** so verifiers don't need an out-of-band
key distribution channel. Verifiers MAY check the embedded key
against a known operator pubkey for stricter trust.

## Storage layout

- `~/.tars/receipts/<YYYY-MM-DD>.ndjson` — append-only NDJSON, one
  receipt per line. **Source of truth** for chain replay + Merkle
  root computation. Auto-rotates at UTC midnight; the first receipt
  of a new day still chains via `prev_hash` to yesterday's last
  receipt.
- `~/.tars/receipts.sqlite` — read-side mirror keyed by `id` for
  fast filter queries, plus the per-day `merkle_roots` table.

Both are configurable via `TARS_RECEIPT_DIR` and `TARS_RECEIPT_DB_PATH`.
Disable the whole module with `TARS_RECEIPT_STORE=disabled`.

## Daily Merkle root + Solana anchoring

Once UTC midnight passes, the daemon (lifespan task `merkle_root_loop`)
computes the previous day's Merkle root over the ordered list of
receipt hashes for that day. The Merkle tree is the textbook
duplicate-last-leaf binary sha256:

- Pairs at each level concatenated as **raw bytes** (not hex strings).
- Odd-length levels duplicate the last node.
- Empty day → root is `""` (empty string); `leaf_count` = 0.

The root is cached in the `merkle_roots` table (one row per day).

If `TARS_RECEIPT_ANCHOR_ENABLED=1` AND `SOLANA_KEYPAIR_PATH` is set,
the loop submits a Solana memo transaction with the body
`tars-receipt-root:<YYYY-MM-DD>:<root_hex>`. The txid is recorded
back into the `merkle_roots` row (`solana_signature`, `anchored_at`).

## Verification recipe (auditor view)

1. **Replay** the day's NDJSON: read each line, parse JSON, build a
   list of `Receipt` records.
2. **Walk the chain**: for each receipt re-derive `compute_hash`,
   confirm it matches `hash`, confirm `prev_hash` matches the
   previous receipt's `hash`, and verify `signature` against
   `public_key`. Stop at first mismatch (`POST /api/receipts/chain/verify?day=YYYY-MM-DD`
   does this for you).
3. **Recompute the Merkle root** over the ordered receipt hashes
   (`compute_root`). Compare against the cached `merkle_roots.root_hex`.
4. **(Optional) Verify the Solana memo**: query the recorded
   `solana_signature` via any Solana RPC; the memo body must equal
   `tars-receipt-root:<day>:<root_hex>`.

A single-receipt Merkle proof (`GET
/api/receipts/merkle/{day}/proof/{receipt_id}`) lets a third party
verify a specific receipt is in the day's tree without downloading
the whole NDJSON.

## HTTP surface

| Method | Path | Description |
| --- | --- | --- |
| GET    | `/api/receipts`                                        | filterable list (type / actor / time-range) |
| GET    | `/api/receipts/{id}`                                   | single + verification status |
| POST   | `/api/receipts/verify`                                 | verify a body or stored id |
| GET    | `/api/receipts/chain/verify?day=YYYY-MM-DD`            | full-day chain check |
| GET    | `/api/receipts/merkle/{day}`                           | root + leaf count + anchor status |
| GET    | `/api/receipts/merkle/{day}/proof/{receipt_id}`        | per-receipt Merkle proof |
| POST   | `/api/receipts/anchor/{day}`                           | manually fire Solana anchor |
| GET    | `/api/receipts/export?since=...&format=ndjson\|csv`    | bulk export for compliance |

503 on every endpoint when `TARS_RECEIPT_STORE=disabled`.

## Hooked event sources

These callers fire receipts via `backend.core.receipts.record`
(best-effort, never raises):

- **Playbook runner** — `playbook.completed` / `playbook.failed` for
  each finished run.
- **Policy gate** — `hil.approved` / `hil.denied` on operator
  confirmation flow.
- **Wallet router** — `wallet.<chain>_<kind>_signed` for every
  signed transfer / EVM tx.

Future waves may add: agents.action.completed, connectors.sync.completed,
billing.charge.applied. The contract above is stable across additions.

## Privacy considerations

`payload` is opaque to the ledger — nothing inspects or strips
fields. Callers MUST:

- Hash emails / phone numbers before storing
  (`sha256(normalise(email))[:16]` is the recommended shape — full
  reversibility breaks compliance).
- Avoid raw IDs that link back to PII (use `actor: "operator"` not
  `actor: "alice@example.com"`).
- Strip free-text user content (chat messages, file names) when
  emitting from skills — pass a hashed summary instead.

Encryption-at-rest is **not** provided by the ledger. Operators
relying on disk encryption (FileVault, LUKS) get it transitively;
others should run TARS inside a VM with encrypted backing store.

## Versioning

`CONTRACT_VERSION = "1.0"`. Breaking changes (renaming fields,
changing canonicalisation, changing signature input) require a
version bump and a parallel-run window.

Additive changes (new optional payload keys, new receipt types, new
endpoints) DO NOT bump the contract version.

## v9.3 deprecation note

`backend/core/wallet/audit.py::enrich_signed_event` still emits
raw-tx metadata to the meeet store under the legacy `TARS_AUDIT_RAW_TX`
flag for backward-compat. v9.3 will remove that path entirely; every
wallet caller will write through the receipt ledger as the sole
audit trail.
