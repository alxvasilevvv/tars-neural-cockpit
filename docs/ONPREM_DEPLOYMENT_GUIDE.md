# TARS — On-Prem Deployment Guide

> **Audience:** ops / SRE / IT security at an enterprise customer, a
> fund, a regulated org, or any team that needs TARS to run inside
> their network instead of dialling out to `meeet.world`.
>
> **Status:** ships with `v10.0.0-rc.1` (W263). Source of truth for
> self-hosted TARS deployments. Pairs with
> `scripts/ONPREM-DEPLOY/` (the compose stack) and
> `backend/core/onprem/` (the local-auth + pg-migrations drop-ins).
>
> **Last touched:** W263 (2026-05-15).

---

## Table of contents

- [§1. When to choose on-prem](#1-when-to-choose-on-prem)
- [§2. Hardware requirements](#2-hardware-requirements)
- [§3. One-line install](#3-one-line-install)
- [§4. What changes when MEEET_MODE=onprem](#4-what-changes-when-meeet_modeonprem)
- [§5. SAML / OIDC setup](#5-saml--oidc-setup)
- [§6. Monitoring (Prometheus + OpenTelemetry)](#6-monitoring-prometheus--opentelemetry)
- [§7. Backup and restore](#7-backup-and-restore)
- [§8. Upgrade procedure](#8-upgrade-procedure)
- [§9. Air-gapped deployments](#9-air-gapped-deployments)
- [§10. Hardening checklist](#10-hardening-checklist)
- [§11. Troubleshooting](#11-troubleshooting)
- [§12. Appendix — file-by-file reference](#12-appendix--file-by-file-reference)

---

## §1. When to choose on-prem

Default TARS shipping (the `.app` from `/Applications/TARS.app`) talks
to `meeet.world` for identity, billing, and (optionally) telemetry. For
most operators that is the right choice — it's free at FREE-tier,
auto-updates, and the operator never touches infra.

You want on-prem if **any** of the following are true:

- Regulated data (HIPAA, SOC2 customer audit clause, financial KYC).
- Outbound network is restricted and you cannot allowlist
  `meeet.world` reliably.
- Multi-user (10+ seats inside one office) and you want SSO + a single
  admin console.
- $MEEET billing economics don't apply (procurement won't sign a
  consumption contract; they want a flat per-seat license).
- You need to retain receipts under your own keys, anchored in your
  own chain (not Solana mainnet).

If none of those apply, run the `.app`. It's faster, easier, and the
hosted billing rails are cheaper than running your own Postgres.

---

## §2. Hardware requirements

The compose stack runs the full TARS surface (cockpit + backend +
watchdog + Postgres + nginx). All numbers are for a **single host**;
multi-host is a fan-out of `backend` + shared Postgres + nginx LB.

| Seats | CPU | RAM | Disk | Notes |
|------:|----:|----:|-----:|-------|
| 1–5    | 2 vCPU | 4 GB  | 20 GB SSD | Dev / proof-of-concept. |
| 5–25   | 4 vCPU | 8 GB  | 50 GB SSD | Small team. Default `UVICORN_WORKERS=2`. |
| 25–100 | 8 vCPU | 16 GB | 200 GB SSD | Bump `UVICORN_WORKERS=4`; pin Postgres to its own host. |
| 100+   | 16 vCPU + | 32 GB + | 500 GB SSD + | Multiple backend replicas behind nginx LB; managed Postgres recommended. |

Codebase indexer (W245) is the heaviest consumer — budget ~1 GB RAM
per concurrently-indexed 500K-LoC repository. Vision (W203) is CPU-only
unless you wire a CUDA host (env var `TARS_VISION_DEVICE=cuda`).

Supported host OS: any Linux with kernel ≥ 5.4 and `docker compose` v2.
Tested: Ubuntu 22.04 / 24.04, Debian 12, RHEL 9. Windows hosts: use
WSL2; ARM hosts: native (images are multi-arch).

---

## §3. One-line install

```bash
curl -L https://meeet.world/install-tars-onprem | bash
```

That's it. The installer (`scripts/ONPREM-DEPLOY/install.sh`) does:

1. Prereq check (`docker`, `docker compose` v2, `curl`, `openssl`, `git`).
2. `git clone` the repo at the pinned release tag into `/opt/tars`.
3. Copy `.env.onprem.example` → `.env.onprem`, mint every `<generate>`
   token with `openssl rand -hex 32`.
4. Generate a self-signed cert in `./certs/` (replace before exposing
   to anyone but localhost).
5. `docker compose pull` + `docker compose up -d --build`.
6. Wait up to 120s for `/health` to return 200.
7. Print URLs and the first-login admin bootstrap token.

To customize before install:

```bash
export TARS_ONPREM_DIR=/srv/tars
export TARS_RELEASE_TAG=v10.0.0-rc.1
curl -L https://meeet.world/install-tars-onprem | bash
```

To run from a checkout instead of curl-pipe-bash:

```bash
git clone https://github.com/alxvasilevvv/tars-neural-cockpit.git /opt/tars
cd /opt/tars
git checkout v10.0.0-rc.1
bash scripts/ONPREM-DEPLOY/install.sh
```

To run as a systemd unit on Linux (recommended for prod):

```bash
sudo cp scripts/ONPREM-DEPLOY/tars-onprem.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tars-onprem
```

---

## §4. What changes when MEEET_MODE=onprem

`MEEET_MODE=onprem` is the single flag that flips the runtime out of
"call meeet.world" mode. Every code path that would otherwise contact
the cloud either short-circuits or routes to a local replacement.

| Surface | Default (`.app`) | On-prem |
|---------|------------------|---------|
| **Identity** | Magic-link or OAuth via `meeet.world`. `web_extras/routers/auth_meeet.py` POSTs to brother's cloud. | Local accounts in `users` table OR your SAML/OIDC IdP. `backend/core/onprem/local_auth.py` mints HS256 JWTs with `TARS_AUTH_LOCAL_SIGNING_KEY`. |
| **Tier / entitlements** | `GET /api/billing/tier` from meeet.world. | `tier` column on the local `users` row (admin-managed). |
| **Usage events** | HMAC-signed POST to `meeet.world/api/billing/usage`. | Written to `usage_events` table only (no outbound). |
| **AI Clone sync** | Webhook to `meeet.world/api/clone/sync` (W195). | `clone_messages` table only; no outbound. |
| **Receipts anchor** | Daily Merkle root → Solana memo on `meeet.world`-owned wallet. | Same local hash-chain, but anchor is opt-in via `ANCHOR_SOLANA_RPC_URL` and the operator's keypair. Air-gapped sites skip anchoring entirely. |
| **Marketplace** | Reads from meeet.world catalog. | Reads from local `marketplace_listings` table (operator curates). |
| **T2T** | Negotiates via meeet.world relayer. | Negotiates peer-to-peer with another on-prem instance, no relayer. |
| **Auto-update** | Tauri updater pulls from `meeet.world/downloads/tars`. | Operator pulls the image via `docker compose pull` and orchestrates rollouts. |
| **Telemetry / error reports** | `meeet.world/api/telemetry`. | OpenTelemetry collector you operate. `OTEL_EXPORTER_OTLP_ENDPOINT`. |
| **Data store** | ~21 SQLite files under `~/.tars/`. | Single Postgres database. `backend/core/onprem/pg_migrations.py` mirrors every SQLite schema. |
| **Backend host** | `127.0.0.1:8765` loopback. | Containerized, fronted by nginx on `:80/:443`. |

What does NOT change:
- The cockpit UI (same React bundle).
- All ~50 routers and ~30 backend core modules.
- The receipt + privacy + voice cockpit paths.
- The Tauri desktop binary (if a seat installs the `.app` and points
  at the on-prem URL via `TARS_BACKEND_URL=https://tars.your-co.local`,
  it works).

---

## §5. SAML / OIDC setup

Local accounts are fine for ≤10 seats. Beyond that, wire your IdP.

### 5.1 OIDC (Okta, Azure AD, Google Workspace, Keycloak, Authentik)

1. In your IdP, register an app named **TARS**:
   - Redirect URI: `https://tars.your-co.local/api/auth/onprem/oidc/callback`
   - Scopes: `openid email profile groups`
   - Application type: Web
2. Copy the issuer / discovery URL, client ID, client secret.
3. Set in `.env.onprem`:

   ```bash
   MEEET_ONPREM_OIDC_DISCOVERY=https://your-tenant.okta.com/.well-known/openid-configuration
   MEEET_ONPREM_OIDC_CLIENT_ID=0oa...your-client-id
   MEEET_ONPREM_OIDC_CLIENT_SECRET=...your-secret
   MEEET_ONPREM_ADMIN_GROUP=tars-admins
   ```

4. Map an IdP group to TARS admin role: every user whose `groups` claim
   contains `tars-admins` is auto-promoted on first login.
5. Restart: `docker compose restart backend`.
6. Visit `/login`. The local password form disappears; "Sign in with
   <IdP>" takes its place.

### 5.2 SAML (legacy SSO)

Set `MEEET_ONPREM_SAML_METADATA_URL` to the IdP metadata XML URL. Same
group-claim-to-role mapping applies.

### 5.3 Mixed mode

Setting both an IdP and keeping local accounts (the
`ADMIN_BOOTSTRAP_TOKEN` flow) gives you a break-glass login path when
the IdP is down. Use sparingly — every local password is a credential
that bypasses your SSO governance.

---

## §6. Monitoring (Prometheus + OpenTelemetry)

### 6.1 Prometheus

The backend exposes `/metrics` (proxied through nginx). Standard FastAPI
+ uvicorn metrics plus TARS-specific counters:

- `tars_receipts_emitted_total{action}` — per-action receipt count
- `tars_usage_tokens_total{user,model}` — token consumption
- `tars_doctor_check{check}` — last health-check result (0/1)
- `tars_request_duration_seconds{route,method}` — request latency histogram
- `tars_active_sessions` — gauge of live JWT sessions

Scrape config:

```yaml
scrape_configs:
  - job_name: tars
    metrics_path: /metrics
    scheme: https
    tls_config:
      ca_file: /etc/prometheus/tars-ca.pem
    static_configs:
      - targets: ['tars.your-co.local:443']
```

Restrict scrape ingress to the Prometheus host via nginx `allow`/`deny`
directives or a firewall rule.

### 6.2 OpenTelemetry

Every consequential request emits a span. To export:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=tars-onprem
OTEL_SERVICE_VERSION=10.0.0-rc.1
```

Spans carry `tars.user_id`, `tars.tier`, `tars.action`, `tars.receipt_id`.
For Honeycomb / Datadog / Tempo / Jaeger, point the collector at them.

### 6.3 Alerts that earn their keep

- Backend `/health` returns non-200 for >30s.
- Postgres replication lag > 60s (multi-host only).
- Receipts table row count growth drops to zero for >15min.
- 95-th percentile request latency > 2000ms.
- Disk usage on `tars-data` or `tars-pg` volumes > 85%.

---

## §7. Backup and restore

### 7.1 What to back up

- **Postgres database** — receipts, usage, users, sessions, codebase,
  everything. Snapshot via `pg_dump`:

  ```bash
  docker compose exec postgres \
    pg_dump -U tars -d tars --format=custom --file=/backup/tars-$(date +%F).pgdump
  ```

- **`tars-data` volume** — vault keys, on-disk receipt NDJSON,
  generated artifacts. `docker run --rm -v tars-onprem_tars-data:/data -v $PWD:/backup alpine tar czf /backup/tars-data-$(date +%F).tar.gz /data`.
- **`.env.onprem`** — secrets. Encrypted backup (age, KMS, vault).
- **`certs/`** — TLS material.

### 7.2 RPO / RTO targets

| Tier | RPO | RTO | Strategy |
|------|-----|-----|----------|
| Standard | 24h | 4h | Nightly pg_dump + tar to S3/Blob. |
| High-availability | 5min | 30min | Streaming replication to standby + WAL shipping. |
| Mission-critical | <1min | <5min | Synchronous replication, hot-spare site, automated DR drill quarterly. |

### 7.3 Restore drill

```bash
# 1. Stop stack
docker compose down

# 2. Restore Postgres
docker compose up -d postgres
docker compose exec postgres dropdb -U tars tars
docker compose exec postgres createdb -U tars tars
docker compose exec -T postgres pg_restore -U tars -d tars < tars-2026-05-15.pgdump

# 3. Restore data volume
docker run --rm -v tars-onprem_tars-data:/data -v $PWD:/backup alpine \
  tar xzf /backup/tars-data-2026-05-15.tar.gz -C /

# 4. Bring stack back up
docker compose up -d
```

Run a restore drill quarterly. A backup you have never restored is
not a backup.

---

## §8. Upgrade procedure

TARS uses git tags as the unit of release. Upgrading is:

```bash
cd /opt/tars
git fetch --tags
git checkout v10.0.1            # or whatever the next tag is
docker compose pull             # pulls the matching image tag
docker compose up -d backend    # rolling restart, postgres stays up
```

`pg_migrations.py` runs on every backend container boot, so new schema
applies automatically. The migration table (`_meta`) ensures
idempotency — re-runs are no-ops.

Zero-downtime is achievable if you run 2+ backend replicas behind nginx;
otherwise budget ~15s of API unavailability during the restart.

Always read `docs/RELEASE_NOTES_<tag>.md` before upgrading. Breaking
changes (when they happen) ship with explicit pre-upgrade scripts.

---

## §9. Air-gapped deployments

For sites with no outbound internet:

1. Build the images on a connected machine:
   ```bash
   docker compose -f scripts/ONPREM-DEPLOY/docker-compose.yml build
   docker save tars/backend:10.0.0-rc.1 tars/frontend:10.0.0-rc.1 postgres:16-alpine \
     | gzip > tars-images-v10.0.0-rc.1.tar.gz
   ```
2. Transfer the tarball + the repo checkout to the air-gapped host.
3. Load + bring up:
   ```bash
   docker load < tars-images-v10.0.0-rc.1.tar.gz
   cd /opt/tars/scripts/ONPREM-DEPLOY
   bash install.sh
   ```
4. Leave `MEEET_INGEST_URL`, `MEEET_BILLING_BASE_URL`,
   `ANCHOR_SOLANA_RPC_URL` empty. The full stack runs without ever
   making an outbound call.
5. For LLM access, either:
   - Run a local model server (Ollama, vLLM, llama.cpp) and set
     `LOCAL_MODEL_BASE_URL`. No outbound needed.
   - Or whitelist a single LLM provider on your egress proxy and set
     the relevant `*_API_KEY`.

The optional `--profile mock-meeet` brings up `tars-meeet-mock` which
stands in for the brother's endpoints; useful for exercising auth /
billing flows in a fully sealed env.

---

## §10. Hardening checklist

Before exposing to production users:

- [ ] Replace `certs/tars.crt` + `certs/tars.key` with a CA-issued cert.
- [ ] Set `TARS_HIDE_TRACEBACKS=1` (default in `.env.onprem.example`).
- [ ] Set `TARS_REQUIRE_OPERATOR_CONFIRM=1` for destructive routes.
- [ ] Rotate every `<generate>` token from `install.sh`; document the
      rotation cadence (recommend 90 days).
- [ ] Restrict ingress to `:80/:443` only; block `:5432` from anywhere
      but the backend container.
- [ ] Restrict `/metrics` scrape to your Prometheus host (nginx
      `allow`/`deny` or firewall).
- [ ] Burn the `ADMIN_BOOTSTRAP_TOKEN` after first login (remove from
      `.env.onprem`).
- [ ] Enable Postgres WAL archiving + offsite backup.
- [ ] Run `tars-doctor --watch` continuously (the watchdog container
      handles this in compose; verify it's up: `docker compose ps`).
- [ ] Wire SAML/OIDC; disable local password login (`TARS_AUTH_LOCAL=0`
      *after* SSO is verified working).
- [ ] Set up an external uptime monitor on `/health`.
- [ ] Configure your alerting destination in the doctor watch fanout.

---

## §11. Troubleshooting

### Backend container restart loops

```bash
docker compose logs backend --tail=200
```

Most common causes:
- `TARS_DB_URL` wrong host/port → Postgres unreachable.
- `TARS_AUTH_LOCAL_SIGNING_KEY` empty (`install.sh` didn't mint it).
- Postgres still booting (watchdog retries; should self-resolve).

### "Schema is up-to-date" but I added a migration

The migration's `id` matched something already in `_meta`. Use a new
unique `id` (recommend timestamp prefix).

### IdP redirect loop

Discovery URL is wrong, or the redirect URI registered at the IdP
doesn't exactly match `https://<your-host>/api/auth/onprem/oidc/callback`.
Both must align byte-for-byte including scheme and trailing path.

### Receipts table growing too fast

Default retention is forever (compliance-grade). To enable rolling
deletion, set `TARS_AUDIT_RETENTION_DAYS=365` and run the prune
endpoint via cron: `curl -X POST https://tars.your-co.local/api/audit/prune`.

### Codebase indexer slow

Verify pgvector is installed:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE codebase_symbols ALTER COLUMN embedding TYPE vector(384) USING embedding::vector;
```
Without pgvector, indexer falls back to text-search ranking — correct
but ~50x slower on big repos.

---

## §12. Appendix — file-by-file reference

| Path | What it does |
|------|--------------|
| `scripts/ONPREM-DEPLOY/docker-compose.yml` | Full stack: backend + watchdog + Postgres + nginx + optional meeet-mock. |
| `scripts/ONPREM-DEPLOY/Dockerfile.backend` | Python 3.12 + deps + uvicorn entrypoint. Multi-arch. |
| `scripts/ONPREM-DEPLOY/Dockerfile.frontend` | Node-build + nginx serve + API/WS reverse-proxy. |
| `scripts/ONPREM-DEPLOY/install.sh` | One-line installer (`curl https://meeet.world/install-tars-onprem`). |
| `scripts/ONPREM-DEPLOY/tars-onprem.service` | systemd unit; `systemctl enable --now tars-onprem`. |
| `scripts/ONPREM-DEPLOY/.env.onprem.example` | Every env var the stack consumes, with `<generate>` placeholders. |
| `backend/core/onprem/__init__.py` | `is_onprem()` predicate; honored by every auth/billing path. |
| `backend/core/onprem/local_auth.py` | HS256 JWT + scrypt password + OIDC bridge stub. |
| `backend/core/onprem/pg_migrations.py` | Schema parity with the 21 SQLite stores; idempotent migrator. |

End. Open an issue or file a ticket with your account team if anything
in this guide is wrong, stale, or missing for your deployment shape.
