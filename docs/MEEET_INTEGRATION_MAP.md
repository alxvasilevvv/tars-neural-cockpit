# TARS ↔ meeet.world Integration Map

> Generated: 2026-05-14 (W148 audit, read-only).
> Scope: every place TARS currently emits to, reads from, or *should* be
> talking to meeet.world. Maps each channel to current state, required
> env, brother's side of the contract, and what's blocking tighter coupling.

---

## 1. Executive Summary

Today TARS ↔ meeet.world is **a one-way telemetry firehose plus a partial billing
read-back, and almost nothing else**. The wire is real and contract-versioned
(`relay_event.schema.json`, `1.0.0`), but most "integration" surfaces are still
single-tenant best-effort emit-only paths.

| # | Channel | State | Blocker |
| - | --- | --- | --- |
| 1 | core-bridge (Supabase Edge Fn) | LIVE | secret rotation; no multi-tenant fencing |
| 2 | tars-ingest (cross-project sink) | LIVE | same as #1; relies on producer trust |
| 3 | Outgoing webhooks | LIVE (host-side only) | brother has no consumer; only customer URLs targeted |
| 4 | Receipts Solana memo anchor | PARTIAL | live RPC works; signer key offline by default; no relayer path |
| 5 | OAuth bridge for connectors | MISSING in code | only doc stubs; tokens live on local disk |
| 6 | meeet billing operator snapshot | LIVE (opt-in remote) | brother edge fn must exist + populated |
| 7 | Wallet + $MEEET balance | PARTIAL | reads SOL/EVM/TON; no SPL $MEEET balance/mint/burn path |
| 8 | MCP server bridge | MISSING | `backend/core/mcp/` doesn't exist in repo |
| 9 | AI Clone style learning | LOCAL ONLY | nothing syncs to meeet |
| 10 | Marketplace 70/30 payouts | STUB | docstring says v9.3; signature verification skipped |

**Bottom line for v9.1 → v10.0:** the bridge is the foundation but everything
above it (multi-tenant, real auth, $MEEET economy, marketplace settlements,
MCP) is either local-only or stubbed. Brother needs to ship five distinct
edge functions and one Postgres schema before tighter coupling is even
possible (see §4).

---

## 2. Channel-by-Channel Deep Dive

### 2.1 core-bridge — `zujrmifaabkletgnpoyw.supabase.co/functions/v1/core-bridge`

**State:** LIVE.
**Contract:** `docs/contracts/CORE_BRIDGE.md` v1.0.0 +
`docs/contracts/relay_event.schema.json`.
**Auth:** single shared secret (`x-bridge-secret`) + Origin allowlist
(`meeet.world` | `tars.meeet.world`). Constant-time compared.

**TARS-side emit path:**
- `backend/core/meeet/client.py` — `MeeetClient.emit()` is the only
  emitter. Every TARSEvent goes through SQLite WAL store first
  (`backend/core/meeet/store.py`), then `_post_json` to `MEEET_INGEST_URL`.
- Replay paths: `replay_unpushed()` + `repush_trace()` for outage backfill.
- ~21 call-sites across `agents/runner.py`, `chat/orchestrator.py`,
  `council/orchestrator.py`, `playbooks/runner.py`, `planner/runner.py`,
  domain packs (`traders`, `mlm`, `business`), and the crypto envelope.

**Endpoints exposed by the bridge:**
- `GET /health` — liveness, secret-gated.
- `GET /token-stats` — public-safe $MEEET stats (relies on brother's view).
- `POST /relay-event` — forwards to TARS Supabase project `tars-ingest`.

**Required env:**
- TARS side: `MEEET_INGEST_URL`, `MEEET_API_KEY` (bearer for `tars-ingest`),
  `MEEET_CONTRACT_VERSION` (default `1.0.0`, `.env.example` pins `1.1.0`).
- Bridge side: `BRIDGE_SHARED_SECRET`, `TARS_INGEST_API_KEY` (passthrough
  to forwarder).
- Smoke: `make smoke-core-bridge` (scripts/smoke_core_bridge_e2e.sh).

**Brother's side:** ✅ already shipping. He owns the Supabase function +
secret rotation cadence.

**What blocks tighter coupling:**
- Single shared secret per environment. No per-tenant key, no rotation
  log. Loss of secret = full firehose access. Wave 79 hardening flagged
  this; mitigation deferred.
- No replay/idempotency token honored upstream — events are deduped only
  on producer side via `pushed_at` flag.

### 2.2 tars-ingest — cross-project event sink

**State:** LIVE (downstream consumer of core-bridge).
Operates inside TARS Supabase project (`hhpaukjobskcwkxbgecl`).
Visible at: `https://hhpaukjobskcwkxbgecl.supabase.co/functions/v1/tars-ingest`.

**TARS-side:** producer indirection only. TARS never POSTs to
`tars-ingest` directly in prod (the smoke script does, for the secret-less
case). Production flow: `MeeetClient.emit → core-bridge → tars-ingest`.

**Brother's side:** ✅ deployed (per `docs/agent-handoff/TARS_BACKEND_CATALOG.md` §70).
He owns the table schema, partitioning, and any downstream materialised
views.

**What blocks:** see §2.1. Plus the contract bump from `1.0.0` → `1.1.0`
(adds optional `ciphertext` + `envelope` for sealed payloads) is shipped
on the producer side; consumer should already ignore unknown fields per
contract.

### 2.3 Outgoing webhooks

**State:** LIVE (host-side); meeet.world is **not currently a registered
consumer**.
**Code:** `backend/core/webhooks/dispatcher.py` +
`docs/contracts/WEBHOOKS.md` v1.0.

**Wired event types** (sources that fire `from backend.core.webhooks import emit`):
- `playbook.started` / `playbook.completed` — `playbooks/runner.py`
- agent task lifecycle — `agents/store.py` (lines 202, 317)
- policy gate decisions — `policy/gate.py`
- report deliveries — `reports/delivery.py`

**Sink:** any operator-registered HTTPS URL **plus** `telegram://self`
or `telegram://chat/<id>` (Wave 108). HMAC-SHA256 signed
(`X-TARS-Signature: t=<ts>,v1=<hex>`). Retry: 30s/2m/10m/1h
exponential w/ `Retry-After` honoring.

**What's NOT wired:** meeet.world itself does not yet appear as a default
outgoing webhook target. To turn this into a real bidirectional channel
brother needs a `POST /api/tars/events` (or similar) endpoint that:
- validates `X-TARS-Signature`
- mirrors events into the same Postgres table `tars-ingest` writes to
- returns `2xx` < 250 ms (otherwise the retry budget eats him)

**Required env:** `TARS_WEBHOOKS_ENABLED=1`, plus per-webhook secrets
stored in the local SQLite at `~/.tars/webhooks.sqlite`.

### 2.4 Receipts ledger — Solana memo anchor

**State:** PARTIAL.
**Code:** `backend/core/receipts/anchor.py` + `backend/core/receipts/dispatch.py`.

**What's live:**
- `anchor_to_solana(day_iso, root_hex)` builds + signs + submits a real
  memo transaction (`MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr`).
- Uses `solders` for tx assembly, raw httpx JSON-RPC for blockhash +
  sendTransaction.
- Default RPC: `https://api.mainnet-beta.solana.com` (override
  `SOLANA_RPC_URL`).
- Reads keypair JSON array from `SOLANA_KEYPAIR_PATH` (64 ints).

**What's gated:**
- `_is_configured()` returns False unless `SOLANA_KEYPAIR_PATH` is set,
  so anchoring is off-by-default. Operator must drop a keypair file on
  disk to enable.
- **No meeet.world relayer path.** All anchoring is direct user→Solana.
  Brother is NOT involved in receipt anchoring today.

**What blocks:**
- Operator-held key = key custody problem (single point of compromise).
- No relayer endpoint on meeet.world side that would let TARS submit
  the memo via brother's signer (preserves user wallet for actual SOL).
- Off-by-default = most operators never enable it; we never aggregate
  receipts upward.

### 2.5 OAuth bridge for connectors

**State:** MISSING in code.
The token T142 in the task log ("OAuth bridge protocol через meeet.world")
is marked completed but does not exist as a runtime path.

**Current code:** `backend/core/connectors/` ships **per-provider direct
OAuth** (Slack/Gmail/Calendar/Telegram). Tokens stored locally in
`~/.tars/connectors/<name>.json` (mode 600), see
`backend/core/connectors/_storage.py`. Optional vault encryption via
`backend.core.vault.envelope` lookup (lazy import).

**Connectors with direct OAuth:**
- Slack — `SLACK_CLIENT_ID/SECRET/REDIRECT_URI`
- Gmail / Google Calendar — `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI`
- Telegram — `TELEGRAM_BOT_TOKEN` (bot token, no OAuth)
- SMTP OAuth consent — `web_extras/routers/oauth_consent.py` PKCE flow,
  HMAC-signed state — but **endpoint runs on the local backend, not
  meeet.world**.

**Brother's responsibility (when it lands):**
- Host an OAuth proxy at `https://meeet.world/oauth/<provider>/start`
  that holds the master client_id/secret pair, and returns a
  short-lived bearer to TARS keyed by operator-id.
- This removes the requirement that every operator register their own
  Google Cloud project / Slack app.

**What blocks:** brother hasn't built it; today every operator has to
register their own OAuth app per provider. Major friction wall.

### 2.6 meeet_billing — operator snapshot + spend mirror

**State:** LIVE (opt-in remote mode).
**Code:** `backend/core/meeet_billing/client.py` (read snapshot),
`backend/core/meeet_billing/mirror_usage.py` (write delta).

**Read path** — `GET {MEEET_BILLING_BASE_URL}/operator`:
- Returns `{tier, byo_enabled, live: {spent_usd_24h, cap_usd_daily,
  remaining_usd, allowed_cloud, reason}}`.
- Consumed by `backend/core/entitlements/checker.py:_can_run_with_remote`
  to gate cloud calls.
- Cached 5 s; thread-locked.

**Write path** — `POST {MEEET_BILLING_BASE_URL}/operator/usage`:
- Fired automatically by `MeeetClient.emit()` when `kind=="usage.tokens"`
  and `route in {cloud, fallback, mixed}` and `cost_usd > 0`
  (see `mirror_usage.after_usage_tokens_emitted`).
- Idempotent on server side via `trace_id`.
- Retries 3 attempts (configurable `MEEET_BILLING_USAGE_RETRIES`, max 8)
  with 2^n × 0.12 s backoff. Exhaustion logs
  `meeet.mirror.usage.exhausted`.
- Cap per delta: `MEEET_BILLING_MAX_DELTA_USD` default 50.

**Required env:**
- `TARS_BILLING_SOURCE=remote` (gate; default `local` no-ops)
- `MEEET_BILLING_BASE_URL` (e.g. `https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/tars-billing`)
- `MEEET_BILLING_API_KEY`
- Optional: `TARS_OPERATOR_ID` (sent as `X-Tars-Operator-Id` header).

**Brother's responsibility:**
- Host `tars-billing` Supabase function with `GET /operator` and
  `POST /operator/usage`. Wire it into the meeet.world authoritative
  Postgres ledger.
- See `docs/contracts/TARS_MEEET_BILLING.md` for the full request/response
  shape.

**What blocks:** This is actually shippable as-is once the function exists.
The protocol is well-defined. Main risk: the cache (5 s) and the retry
budget combined can leave a 30 s window where TARS thinks it's allowed
to spend while brother has already shut the gate.

### 2.7 Wallet + $MEEET (SPL token)

**State:** PARTIAL.
**Code:** `backend/core/wallet/balance.py` (read), `wallet/sign_sol.py`,
`wallet/sign_evm.py`, `wallet/sign_ton.py` (sign).

**What's live:**
- Native balance reads for SOL / ETH / TON via JSON-RPC
  (`getBalance`, `eth_getBalance`, `getAddressBalance`).
- Read-only — module **never broadcasts**, signing is policy-gate's
  problem.
- HD derivation, slip-10, ed25519/secp256k1 signing all present.

**What's NOT live:**
- No SPL token balance reader (`getTokenAccountBalance`). $MEEET token
  balance cannot be fetched today.
- `MEEET_TOKEN_MINT` env var referenced only in handoff docs, **no
  runtime code reads it**.
- No mint / burn paths — there's no relayer call to brother's wallet
  service.

**What blocks:**
- Brother needs to publish the $MEEET mint address (today only in docs)
  and a stake/burn relayer endpoint (so users don't pay SOL gas to
  participate).
- TARS needs an SPL balance reader (`spl-token getAccountBalance` via
  RPC) — fairly trivial to add.

### 2.8 MCP server bridge

**State:** MISSING.
There is no `backend/core/mcp/` directory in this repo. The task log
references T17 "MCP-сервер мост" and T85 "MCP server reference — exposes
5 native skills как tools" as complete, but those are either older
artifacts or never landed in the current monorepo layout.

**What's present:** Tauri MCP UI panels (per task log T124), but no
backend Python module that exposes TARS skills via MCP for external
clients (Claude Desktop, Cursor, etc.).

**What blocks:** product decision needed — is MCP something the brother
hosts (so any logged-in meeet.world user can plug TARS skills into their
agent), or is it always operator-local? If the former, brother needs a
relay + skill registry.

### 2.9 AI Clone — style learning

**State:** LOCAL ONLY.
**Code:** `backend/core/clone/style.py` (v0.1).
**Storage:** `~/.tars/clone.sqlite` (override `TARS_CLONE_DB_PATH`).

Operates entirely on operator's machine — sentence-length /
casual-vs-formal counters, optional embedding column when embedder is
reachable. Nothing syncs upward.

**What's NOT wired:**
- No emit to meeet.world. Brother never sees user style snapshots.
- Therefore no cross-device clone portability and no premium per-tier
  gating (the Lifetime/Business AI Clone tiering exists only in the
  pricing UI, not in code).

**What blocks:** product question first — do we want clones to be
portable / sellable? If yes, brother needs an opaque `clone_profile`
blob store keyed by operator_id, with versioning so style hashes are
diffable across devices.

### 2.10 Marketplace — 70/30 payouts

**State:** STUB.
**Code:** `backend/core/marketplace/__init__.py` literal docstring:

> No payouts in v0 — ratings are local-only and the listings are
> tagged with a `price` field for forward-compat with v9.3.

`installer.py` (lines 138-146) also has stub signature verification:

```python
# Public key not actually distributed in v0 -- this is a
# stub that records "we tried". Real verification lands
# in v9.3 along with payouts.
audit.append("signature_present_unverified_v0")
return False
```

**What blocks (everything):**
- Brother needs to publish the marketplace registry signing pubkey
  (ed25519) so TARS can verify install payloads.
- Brother needs a `POST /api/marketplace/purchase` that takes
  `{listing_id, buyer_operator_id, price_meeet}` and returns a signed
  install grant; this also where 70/30 settlement lives.
- TARS already has hooks for `Listing.install_payload` and
  `Rating` (local) — they're forward-compat.

---

## 3. Environment / Secrets Matrix

Source: `.env.example` (committed, sensitive values blanked) +
`backend/core/meeet/config.py` + `backend/core/meeet_billing/client.py` +
per-connector env constants.

| Var | Channel | Set in .env.example | Required for prod? |
| --- | --- | --- | --- |
| `MEEET_INGEST_URL` | core-bridge | blank | yes |
| `MEEET_API_KEY` | core-bridge bearer | blank | yes |
| `MEEET_CONTRACT_VERSION` | event schema | `1.1.0` | optional (default `1.0.0`) |
| `MEEET_SOURCE` | event tagging | `tars` | optional |
| `MEEET_LOCAL_LOG` | NDJSON audit | blank | local debug only |
| `BRIDGE_SHARED_SECRET` | core-bridge auth | blank | yes (operator → bridge) |
| `TARS_INGEST_API_KEY` | bridge → ingest | blank | bridge-side only |
| `TARS_BILLING_SOURCE` | billing gate | commented | yes for paid tiers |
| `MEEET_BILLING_BASE_URL` | billing read/write | commented | yes for paid tiers |
| `MEEET_BILLING_API_KEY` | billing bearer | commented | yes for paid tiers |
| `MEEET_BILLING_MAX_DELTA_USD` | usage cap | default 50 | optional |
| `MEEET_BILLING_USAGE_RETRIES` | retry budget | default 3 | optional |
| `TARS_OPERATOR_ID` | seat correlation | commented | recommended |
| `TARS_DOWNLOAD_BASE_URL` | release CDN | GitHub Releases | configurable; meeet.world mirror not live |
| `SOLANA_KEYPAIR_PATH` | receipt anchoring | not in example | anchor opt-in |
| `SOLANA_RPC_URL` | anchor + wallet | not in example | optional (defaults work) |
| `TARS_SOLANA_RPC_URL` | wallet balance | not in example | optional |
| `TARS_EVM_RPC_URL` | wallet balance | not in example | optional |
| `TARS_TON_RPC_URL` | wallet balance | not in example | optional |
| `MEEET_TOKEN_MINT` | $MEEET ref | **not read in code** | future |
| `TARS_WEBHOOKS_ENABLED` | webhook loop | not in example | opt-in |
| `TARS_WEBHOOKS_DB_PATH` | webhook store | not in example | optional |
| `TARS_RECEIPT_STORE` | receipts on/off | not in example | optional (`disabled` short-circuits) |
| `TARS_CLONE_DB_PATH` | AI clone store | not in example | optional |
| `CLONE_STORE` | clone gate | not in example | `disabled` short-circuits |
| `SLACK_CLIENT_ID/SECRET/REDIRECT_URI` | OAuth | not in example | per-operator app |
| `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI` | OAuth | not in example | per-operator app |
| `TELEGRAM_BOT_TOKEN` | Telegram bridge | not in example | per-operator bot |

**Gap:** `MEEET_TOKEN_MINT` is documented as part of the design but
**no code path reads it**. Either drop it or wire the SPL balance reader.

---

## 4. Brother's TODO List (concrete, actionable)

P0 — required for the channels we already have:
1. **Maintain the `BRIDGE_SHARED_SECRET`** at parity in
   Cloudflare Pages env + GitHub Actions secrets + meeet core Supabase
   secrets. Rotation runbook lives in `docs/TARS_MEEET_OPS_TODO.md` §1.
2. **Deploy `tars-billing` Supabase function** with `GET /operator` +
   `POST /operator/usage` per `docs/contracts/TARS_MEEET_BILLING.md`.
   This unblocks remote billing mode for ALL TARS instances.
3. **Mirror `core-bridge` origin allowlist** — add new TARS domains
   (e.g. `app.tars.meeet.world`) before they go live.

P1 — required for v9.3 (marketplace + economy):
4. **Publish $MEEET mint address** (single source of truth in
   `docs/contracts/MARKETPLACE.md` or similar). Today it's only in
   marketing docs. Wire `MEEET_TOKEN_MINT` env to a real value or drop
   the var.
5. **Ship marketplace registry signing key** (ed25519 public, distributed
   via `tars-downloads` so installer verification works offline).
6. **Build `POST /api/marketplace/purchase`** (Supabase function on
   meeet core). Accepts `{listing_id, buyer_operator_id, price_meeet}`,
   returns a signed install grant. Settle 70/30 on the meeet.world side.

P2 — required for tighter coupling (v10.0+):
7. **OAuth proxy at `meeet.world/oauth/<provider>/start`** — holds master
   Google/Slack client_id+secret, hands TARS a short-lived per-operator
   bearer. Removes the "every operator must register their own app"
   wall.
8. **Receipt-anchor relayer** — `POST /api/receipts/anchor` accepts a
   `{day_iso, root_hex}` from TARS, brother's signer drops the memo,
   returns the txid. Removes operator-held Solana key requirement.
9. **Outgoing-webhook consumer** at `meeet.world/api/tars/events`.
   Validates `X-TARS-Signature`, persists into the same table
   `tars-ingest` writes to. Gives us a second ingest path for
   redundancy.
10. **Multi-tenant fencing** — replace single `BRIDGE_SHARED_SECRET` with
   per-operator API keys minted by meeet.world dashboard.
11. **Solana mint/burn relayer for $MEEET** — `POST /api/wallet/spl/transfer`
   (operator-signed, brother-broadcast). Lets users participate without
   holding SOL for gas.
12. **AI Clone profile blob store** — `PUT /api/clone/profile` (opaque
   blob keyed by operator_id, versioned). Enables cross-device clones +
   tier gating.
13. **MCP relay** — if we want third-party clients to talk to operator
   TARS instances, brother needs a tunnel/relay; otherwise document
   that MCP is local-only.

---

## 5. Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Operator's Machine                             │
│                                                                       │
│  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐  │
│  │ FastAPI Backend │    │ Tauri Desktop UI │    │ CLI / Make tgts │  │
│  │  (uvicorn)      │    │  (cockpit)       │    │ (planner etc.)  │  │
│  └────────┬────────┘    └────────┬─────────┘    └────────┬────────┘  │
│           │                      │                       │           │
│           v                      v                       v           │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                backend/core/meeet/client.py                    │  │
│  │  emit() ─► SQLite WAL store ─► (if MEEET_INGEST_URL) POST      │  │
│  └────────┬───────────────────────────────────────────────────────┘  │
│           │                                                          │
│           │  (usage.tokens + route ∈ {cloud,fallback,mixed})         │
│           ├──► backend/core/meeet_billing/mirror_usage.py            │
│           │      POST /operator/usage                                │
│           │                                                          │
│           │   (every event — never-throws)                           │
│           │   backend/core/webhooks/emit                             │
│           │     ──► registered URLs (HMAC-signed)                    │
│           │     ──► telegram://self                                  │
│           │                                                          │
│           │   (opt-in, daily roll-up)                                │
│           │   backend/core/receipts/anchor.py                        │
│           │     ──► Solana memo tx (direct, mainnet RPC)             │
│  ┌────────┴──────────────────────────────────────────────────────┐   │
│  │       Local SQLite stores (~/.tars/*.sqlite)                  │   │
│  │  meeet.sqlite, webhooks.sqlite, receipts.sqlite,              │   │
│  │  clone.sqlite, connectors/*.json, marketplace/*.sqlite        │   │
│  └───────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
                    │ (POST + bearer + Origin)
                    │
                    v
┌──────────────────────────────────────────────────────────────────────┐
│       meeet core Supabase project (zujrmifaabkletgnpoyw)             │
│       — Lovable-managed —                                            │
│                                                                       │
│  ┌────────────────────┐    ┌────────────────────┐                    │
│  │  core-bridge fn    │    │  tars-billing fn   │   (PARTIAL — needs │
│  │  /health           │    │  GET /operator     │    deploy)         │
│  │  /token-stats      │    │  POST /usage       │                    │
│  │  /relay-event ─────┼──► │                    │                    │
│  └────────┬───────────┘    └────────────────────┘                    │
│           │ (forwards to TARS-project ingest)                        │
│           v                                                          │
│  ┌────────────────────────────────────────────┐                      │
│  │  TARS Supabase project (hhpaukjobskcwkxbgecl)                     │
│  │  tars-ingest fn ──► events table           │                      │
│  └────────────────────────────────────────────┘                      │
│                                                                       │
│  MISSING (brother's TODO):                                           │
│    • /oauth/<provider>/start (proxy)                                 │
│    • /api/receipts/anchor    (relayer)                               │
│    • /api/marketplace/purchase                                       │
│    • /api/wallet/spl/transfer                                        │
│    • /api/clone/profile                                              │
│    • /api/tars/events  (webhook consumer)                            │
└──────────────────────────────────────────────────────────────────────┘
                    │
                    │ (anchor txs — if relayer existed)
                    v
              Solana mainnet
```

---

## 6. Integration Risks

1. **Single shared secret = single point of compromise.** Loss of
   `BRIDGE_SHARED_SECRET` grants firehose write access to every TARS
   operator. No per-tenant key today. Mitigation: rotate via
   `make ops-bridge-secret`, but until per-operator keys exist the
   blast radius is "all TARS instances".

2. **`MEEET_TOKEN_MINT` is documented but unread.** Drift between
   marketing copy and code. Either wire it (SPL balance reader) or
   strip it from the design surface.

3. **Receipt anchoring requires operator-held Solana key.** Off by
   default in practice. Anchoring is a no-op for almost every install.
   We aggregate receipts locally and nothing percolates upward.

4. **Marketplace signature verification is a docstring stub.**
   `installer.py` records `signature_present_unverified_v0` and returns
   False — meaning ALL installs proceed unverified. This is fine for
   v0/v1 (no payouts) but blocks any compliance / supply-chain story.

5. **No idempotency guarantee end-to-end.** `tars-ingest` consumer is
   trusted to dedupe by `trace_id`; meeet `mirror_usage` retries can
   double-bill if brother's idempotency window misses one. Producer side
   uses `pushed_at` flag but that's local-only.

6. **Billing cache (5 s) + retry budget (∼2 s × 3) creates a 7-10 s
   window** where TARS can spend after brother has shut the gate.
   Acceptable for current scale; not for tiered enterprise SLAs.

7. **Telegram webhooks live inside the outgoing dispatcher** but use
   `telegram://` URL scheme. If the dispatcher loop crashes, Telegram
   alerts go silent — same channel that powers the synthetic monitor
   alerting. Single failure mode for two surfaces.

8. **Connector tokens stored on disk plaintext if vault unavailable.**
   `backend/core/connectors/_storage.py` documents this; mode 0600 only
   stops other UNIX users, not malware. Vault encryption is opt-in.

9. **No multi-tenant fencing anywhere.** Every TARS install is
   effectively a separate operator with shared secrets. When we ship
   to teams (v9.3+ Workspaces), the entire bridge contract needs to
   carry an `operator_id` or `workspace_id` in the auth token, not
   just in the payload.

10. **AI Clone profiles are 100 % local.** A user reinstalling TARS
    loses everything — no path to restore from meeet.world side. This
    is a retention risk masquerading as a privacy feature.

---

## Appendix: References

- `docs/contracts/CORE_BRIDGE.md` — wire contract v1.0.0
- `docs/contracts/relay_event.schema.json` — JSON Schema 2020-12
- `docs/contracts/TARS_MEEET_BILLING.md` — billing protocol
- `docs/contracts/WEBHOOKS.md` — outgoing webhook envelope shape
- `docs/contracts/RECEIPTS.md` — receipt ledger + Merkle anchor contract
- `docs/contracts/MARKETPLACE.md` — marketplace listing schema (v0)
- `docs/contracts/CONNECTORS.md` — per-connector OAuth flows
- `docs/contracts/COWORK.md` — cowork channel (Wave 129; in-process
  pub/sub, not yet exported)
- `docs/TARS_MEEET_OPS_TODO.md` — operator playbook for bridge ops
- `docs/BROTHER_HANDOFF_v9.1.0.md` — brother's most recent handoff brief
- `docs/agent-handoff/TARS_BACKEND_CATALOG.md` — function inventory
- `Makefile` targets: `smoke-core-bridge`, `smoke-billing-tars`,
  `ops-bridge-secret`, `ops-billing-remote-wizard`,
  `gate-control-tower`.
