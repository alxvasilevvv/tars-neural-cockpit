# DB & Storage Audit — TARS v9.2.0-beta2 (W231)

Snapshot of every persistent surface the backend touches. Generated as
part of W231 so future contributors can answer "where does X live?"
without grepping.

Everything lives under `~/.tars/` (mode 0o700, created on first boot
by `backend.core.storage.bootstrap.init_all_databases`).

## Canonical SQLite stores

Each store auto-creates its schema in `__init__` (CREATE TABLE IF NOT
EXISTS). All paths are `os.path.expanduser`-resolved and overridable
via env var.

| Store               | Path                              | Env override                | Used by                            |
|---------------------|-----------------------------------|-----------------------------|------------------------------------|
| Agents              | `~/.tars/agents.sqlite`           | `TARS_AGENTS_DB_PATH`       | `/api/agents/*`                    |
| Chat                | `~/.tars/chat.sqlite`             | `TARS_CHAT_DB_PATH`         | `/api/chat/*` + attachments + FTS  |
| Memory              | `~/.tars/memory.sqlite`           | `TARS_MEMORY_DB_PATH`       | `/api/memory/*`                    |
| Meeet events        | `~/.tars/meeet.sqlite`            | `TARS_MEEET_DB_PATH`        | `/api/meeet/*` + replay loop       |
| Policy              | (per `policy/store.py` default)   | `TARS_POLICY_DB_PATH`       | `/api/policy/*`                    |
| Receipts            | `~/.tars/receipts.sqlite`         | `TARS_RECEIPT_DB_PATH`      | `/api/receipts` + Merkle anchor    |
| Scheduler           | `~/.tars/scheduler.sqlite`        | `TARS_SCHEDULER_DB_PATH`    | `/api/scheduler/*`                 |
| Workspaces          | `~/.tars/workspaces.sqlite`       | `TARS_WORKSPACES_DB_PATH`   | `/api/workspaces/*`                |
| Webhooks            | `~/.tars/webhooks.sqlite`         | `TARS_WEBHOOKS_DB_PATH`     | `/api/webhooks/*`                  |
| Cowork              | `~/.tars/cowork.sqlite`           | `TARS_COWORK_DB_PATH`       | `/api/cowork/*`                    |
| Pairing             | `~/.tars/pairings.sqlite`         | `TARS_PAIRINGS_DB_PATH`     | `/api/pairing/*`                   |
| Outreach            | `~/.tars/outreach.sqlite`         | `TARS_OUTREACH_DB_PATH`     | `/api/outreach/*`                  |
| Reports             | `~/.tars/reports.sqlite`          | `TARS_REPORTS_DB_PATH`      | `/api/reports/*`                   |
| Wallets             | `~/.tars/wallets.sqlite`          | `TARS_WALLETS_DB_PATH`      | `/api/wallet/*`                    |
| Clone               | `~/.tars/clone.sqlite`            | `TARS_CLONE_DB_PATH`        | `/api/clone/*`                     |
| Cohort              | `~/.tars/cohort.sqlite`           | `TARS_COHORT_DB_PATH`       | `/api/cohort/*`                    |
| Marketplace install | `~/.tars/marketplace/installed.sqlite` | `TARS_MARKETPLACE_DB_PATH` | `/api/marketplace/*`           |
| Marketplace ratings | `~/.tars/marketplace/ratings.sqlite`   | —                           | `/api/marketplace/*`           |
| Bundles installed   | `~/.tars/bundles/installed.sqlite`     | —                           | `/api/bundles/*`               |
| Org                 | `~/.tars/org.sqlite`              | `TARS_ORG_DB_PATH`          | `/api/org/*`                       |
| Planner             | `~/.tars/planner/store.sqlite`    | —                           | `/api/planner/*`                   |
| MLM downline (legacy) | `~/.tars/downline.sqlite`       | —                           | deprecated pack                    |

## JSON / blob state

| File                              | Used by                                |
|-----------------------------------|----------------------------------------|
| `~/.tars/entitlements.json`       | tier + caps for `/api/entitlements`    |
| `~/.tars/roles.json`              | role registry for `/api/roles`         |
| `~/.tars/meeet_token`             | meeet.world session token (0o600)      |
| `~/.tars/host-key.json`           | Ed25519 receipt-signing key            |
| `~/.tars/host_identity.json`      | Pairing identity                       |
| `~/.tars/reflection_latest.json`  | Latest weekly digest output            |
| `~/.tars/releases.json`           | Cached upstream release manifest       |
| `~/.tars/daemon.heartbeat`        | Background daemon liveness             |
| `~/.tars/daemon.out.log`          | Daemon stdout                          |
| `~/.tars/daemon.err.log`          | Daemon stderr                          |
| `~/.tars/wallet_secrets.json`     | Wallet keys (0o600)                    |
| `~/.tars/portfolio.json`          | Traders pack — manual portfolio        |
| `~/.tars/traders_alerts.json`     | Traders pack — destructive-action log  |
| `~/.tars/business_deals.json`    | Business pack — local deals            |

## Directories

| Path                              | Purpose                                 |
|-----------------------------------|-----------------------------------------|
| `~/.tars/receipts/`               | One NDJSON per UTC day                  |
| `~/.tars/exports/`                | Compliance / GDPR export bundles        |
| `~/.tars/reports/`                | Rendered PDF/PPTX/XLSX outputs          |
| `~/.tars/attachments/`            | Chat attachment originals               |
| `~/.tars/connectors/`             | Per-connector OAuth blobs (0o600 each)  |
| `~/.tars/marketplace/installed/`  | Marketplace install roots               |
| `~/.tars/marketplace/` (cache)    | Registry cache                          |
| `~/.tars/vault/`                  | Encrypted vault entries                 |

## Boot sequence (post-W231)

`web_extras/app.py` lifespan now calls
`backend.core.storage.init_all_databases()` before any router takes
traffic. That routine:

1. Creates `~/.tars/` with mode 0o700.
2. Instantiates each store's singleton, forcing the SQLite schema to
   materialise.
3. Seeds one default agent (``TARS Default`` / pack ``web_search``)
   when the agents table is empty.
4. Seeds one ``system.bootstrap`` welcome receipt when the receipts
   ledger is empty.
5. Logs ``ok=N warn=M elapsed_ms=...`` to stderr (visible in
   `/tmp/tars-backend-8765.log`).

Idempotent: a second run short-circuits all seed steps and just
verifies the schema is current.

## Migrations

There are **no** Alembic migrations for the user-local SQLite stores
— each store owns its own `CREATE TABLE IF NOT EXISTS` schema and
treats additive column drift as backwards-compatible. Receipts use a
hash-chained NDJSON for cross-version durability; the SQLite mirror
is rebuildable from NDJSON via `ReceiptStore.replay_chain_for_day`.

## Reading vs writing — who owns what

* **Writers** are the routers under `web_extras/routers/` plus
  background loops in the lifespan (autopilot, scheduler, replay).
* **Readers** are the cockpit, the doctor checks, and the
  daily-briefing / digest routers.
* **No cross-process sharing** — single backend process per user.
