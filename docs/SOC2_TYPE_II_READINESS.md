# SOC 2 Type II Readiness — TARS BUSINESS

**Status:** Pre-audit readiness assessment
**Last updated:** 2026-05-15
**Owner:** TARS Engineering (Claude lane)
**Reviewed by:** TARS Security / meeet.world (operator)
**Tier targeted:** BUSINESS ($40/mo) — regulated industries (funds, RIAs, law firms, clinics, accounting practices)
**Audit window targeted:** 12 months continuous evidence from the date this document is approved.

This is the readiness document a SOC 2 Type II auditor will receive before fieldwork. Each Trust Service Criterion ("TSC") is treated as one section. For each TSC we record:

1. **Control description** — what the system actually does today.
2. **Evidence** — where the auditor can sample (commits, files, endpoints, NDJSON).
3. **Gap** — what is honestly *not yet* good enough for Type II opinion.

We do not claim Type II compliance today. We claim *readiness*: every control surface exists in code, every artefact is reproducible, and every gap is named.

Cursor — the closest comparable product — runs the user's source through a hosted cloud, cannot demonstrate cryptographic hash-chains over agent actions, and has no GDPR data-subject export endpoint. That delta is the BUSINESS tier sales angle.

---

## How to read this document

- Trust Service Criteria are the AICPA's five categories. Security is mandatory; the other four are optional but BUSINESS-tier customers in regulated industries ask for all five.
- Each "Evidence" pointer is a file path (relative to repo root), a commit / wave marker (e.g. **W67**, **W95**, **W250**), or an HTTP endpoint that an auditor can hit on a running BUSINESS deployment.
- "Gap" items are the to-do list before opening Type II fieldwork. We do not hide them.

---

## CC — Security (Common Criteria)

The mandatory TSC. SOC 2 *cannot* be issued without it.

### CC1 — Control environment

**Control:** TARS is single-tenant by default (every BUSINESS deployment is the customer's own Mac mini / VM / Tauri app). The Engineering org maintains a documented role split: Claude lane (this repo) ships product; Cursor lane ships installer + Apple signing; operator (alien@meeet.world) approves releases.

**Evidence:**
- Role split: `CLAUDE.md` (lane charter), `HANDOFF_INSTRUCTIONS.md`.
- Code-of-conduct + commit etiquette: `CLAUDE.md` ("never commit without operator confirmation in HIL mode").
- Background-check substitute: the only humans with merge rights are the operator and his designated Cursor agent.

**Gap:** No written Acceptable Use Policy yet for sub-contractors. Mitigation: BUSINESS deployments are single-tenant, so the contractor surface is the operator's own laptop.

### CC2 — Communication of objectives

**Control:** Security objectives are published as part of `docs/SECURITY.md` and `marketing/legal/`. Every release ships with a CHANGELOG that flags security-relevant waves (W67, W95, W194, W228, W244, W250, W255).

**Evidence:**
- `docs/SECURITY.md` (threat model, hardening checklist).
- `CHANGELOG.md` (release-by-release deltas).
- `marketing/legal/PRIVACY.md`, `marketing/legal/TERMS.md`.

**Gap:** No external-facing trust portal yet. Plan: publish a `tars.meeet.world/trust` page mirroring this document with the gaps redacted.

### CC3 — Risk assessment

**Control:** The risk register is the open-issue list of waves. Every W### wave that closes a P0 / P1 risk is annotated in `CHANGELOG.md`. Quarterly cadence: operator re-reads `docs/SECURITY.md` + this doc, opens a new wave for each unaddressed risk.

**Evidence:**
- `docs/SECURITY.md` (threat model).
- Wave history: every commit message in the form `W### — …` is a risk-treatment decision.

**Gap:** Risk assessment is currently informal (in waves, not in a structured matrix). Mitigation before Type II: produce `docs/RISK_REGISTER.csv` with likelihood × impact × treatment per identified risk.

### CC4 — Monitoring activities

**Control:** Three independent monitoring surfaces are live and emit receipts.

- **tars-doctor** (W154) — health check across 10 sub-systems (LLM provider, vault, disk, log freshness, scheduler, daemon, bridges). Exposed via `/api/doctor`, dashboarded at `/api/doctor/page`, alertable via `/api/doctor/notify`.
- **W117 synthetic monitor** — hits every public route + the JS bundle every 5 min and pages Telegram on failure.
- **W255 audit timeline** — every receipt-emitting action is replayable from `/api/audit/list?since=...&until=...`.

**Evidence:**
- `backend/core/doctor/` (CLI + checks).
- `web_extras/routers/doctor.py` (`/api/doctor`, `/api/doctor/page`, `/api/doctor/fix`).
- `scripts/monitor/` (synthetic monitor).
- `web_extras/routers/audit.py` (W255 audit explorer).

**Gap:** Operator-only paging today (Telegram + iMessage + SMTP). For multi-customer BUSINESS we will need a per-tenant on-call rotation. Tracked for v9.5.

### CC5 — Control activities

See CC6, CC7, CC8 — each is a discrete control family.

### CC6 — Logical & physical access controls

**Control surfaces:**

| Subsystem | Control |
|---|---|
| Meeet token | Stored at `~/.tars/meeet_token` mode `0o600`, never logged, redacted in every error path. |
| Bridge HMAC | `BRIDGE_SHARED_SECRET` distributed only via `auto-push-tag.command` over a sealed channel; verified on every webhook (W194). |
| OAuth secrets (Slack/Gmail/Calendar/GitHub) | Stored in `~/.tars/vault.sqlite` encrypted with the host receipt key (Ed25519 derivative). |
| Local SQLite | Single-tenant per machine. File-system permissions inherited from `~/.tars/` (mode `0700`). |
| Backend HTTP | Bound to `127.0.0.1:8765` by default. CORS allow-list is explicit (`web_extras/app.py::_cors_allow_origins`). |
| Tauri WebView | CSP locked down to `self` + Vite dev origin (W228). |

**Evidence:**
- `backend/core/crypto/` (Ed25519 host key, derivation).
- `web_extras/routers/auth_meeet.py` (token read; the raw token never leaves `.tars/meeet_token`).
- `web_extras/app.py::_cors_allow_origins`.
- `desktop/src-tauri/tauri.conf.json` (CSP).
- `web_extras/routers/webhooks.py` (HMAC verify on every incoming webhook).

**Gap:** Database encryption at rest is **filesystem-level only** (whatever FileVault / dm-crypt the operator runs). True application-level encryption of `~/.tars/*.sqlite` with a key derived from the meeet token is on the roadmap — see `docs/IDEAS.md` / W260. For Type II we will sample `diskutil apfs list` proof of FileVault on every BUSINESS Mac.

### CC7 — System operations

**Control:** Every long-running action emits a signed receipt (W67) into a hash-chained NDJSON ledger (W95). The ledger is append-only and Merkle-anchored every N receipts to Solana (W89).

**Evidence:**
- `backend/core/receipts/store.py` — Ed25519 signing per row.
- `backend/core/receipts/chain.py` — hash chain (prev_hash → curr_hash).
- `backend/core/receipts/merkle.py` — Merkle tree builder.
- `backend/core/receipts/anchor.py` — Solana memo anchor.
- `web_extras/routers/public_proof.py` — `/api/public/proof/*` unauthenticated verifier so an auditor can prove a receipt belongs to the chain without TARS-side tooling.

**Gap:** Solana anchoring is opt-in (env `TARS_ANCHOR_ENABLED=1`). For Type II we will flip default-on for BUSINESS deployments and document the operator's Solana fee budget.

### CC8 — Change management

**Control:**

- Every release is a signed git tag (`v9.x.y`), produced by `scripts/RELEASE-v9.3.0-beta1.command`.
- Every macOS binary is code-signed + notarised through `scripts/SIGN-AND-NOTARIZE.command` (W250).
- Every release runs through CI workflows in `.github/workflows/` before the tag is pushed.
- Pre-deploy: `scripts/launch_precheck.sh` + W116 route-import lint + W127 OG validator.

**Evidence:**
- `scripts/SIGN-AND-NOTARIZE.command`, `docs/APPLE_SIGNING_SETUP.md`.
- `.github/workflows/` (CI matrix).
- `scripts/gate_release.sh` (release gate).
- Code-Signing certificate fingerprint published in `docs/APPLE_SIGNING_NEXT_TIME.md` once cert is acquired.

**Gap:** No formal Change Advisory Board. Mitigation: BUSINESS deployments lock to a specific signed tag; the operator approves each version in writing (chat message kept as audit artefact).

### CC9 — Risk mitigation

Cross-cuts CC3 + CC7 + CC8. See those sections.

---

## A — Availability

**Optional TSC.** BUSINESS-tier customers in regulated industries (funds during quarterly reporting, law firms near a filing deadline) treat availability as a hard SLA, so we include it.

### A1.1 — Capacity planning

**Control:** TARS is local-first; capacity is the operator's own machine. Backend memory + open-file ceiling are emitted via the `/api/perf` aggregator (W108). The doctor watcher will fire `doctor.status_changed` if disk_space < 10% or log freshness drifts.

**Evidence:**
- `web_extras/routers/perf.py`.
- `backend/core/doctor/checks/` — `disk_space.py`, `log_freshness.py` (W173).

**Gap:** No queue-depth metric on the realtime WS bus yet. Will add `realtime.ws.queue_depth` in v9.4.

### A1.2 — Backups & redundancy

**Control:** TARS writes everything to `~/.tars/`. Backup is the operator's Time Machine / borg / rsync rotation. The compliance bundle generator (W104, this commit's W257) emits a self-contained, signed archive that *is* the cold-backup.

**Evidence:**
- `backend/core/compliance_export/bundler.py` — produces `~/.tars/exports/audit-<ts>.tar.gz` with manifest + signature.
- `scripts/COMPLIANCE-BUNDLE.command` (W257) — one-click annual export.
- `docs/DISASTER_RECOVERY.md` — restore procedure.

**Gap:** No cross-region replication. Out of scope for local-first product; documented in DR runbook.

### A1.3 — Recovery & incident response

**Control:**

- LaunchAgent watchdog (`scripts/backend-watchdog.command`) restarts backend if it dies.
- `/api/health` is the cockpit liveness probe.
- Doctor watch mode (W172) tails health and fires notifications via 3 sibling bridges (W160 iMessage, W161 Telegram, W163 SMTP).
- `tars-doctor --fix` (W166) auto-remediates the 4 most common failure modes (stale lockfile, env missing key, scheduler off, vault locked).
- Incident-response runbook documents severity, comms, postmortem template.

**Evidence:**
- `scripts/backend-watchdog.command`, `scripts/install-tars-watchdog.command`.
- `web_extras/routers/doctor.py` (`/api/doctor`, `/api/doctor/fix`).
- `backend/core/doctor/watch.py` (W172).
- `backend/core/notifications/` (W164 contract).
- `docs/INCIDENT_RESPONSE.md` (W164 sibling runbook).

**Gap:** RTO/RPO are operator-defined, not contractually committed. For BUSINESS we will publish a 4-hour RTO / 24-hour RPO baseline tied to the LaunchAgent watchdog cadence + daily compliance-bundle snapshot.

---

## PI — Processing Integrity

**Optional TSC.** Critical for funds / accounting customers who must prove that an agent action wasn't tampered with retroactively.

### PI1.1 — Receipt chain immutability

**Control:** Every action emits a receipt. Each receipt carries `prev_hash` (SHA-256 of the previous receipt's signed canonical form). Tampering with any historical receipt invalidates every downstream hash. Chain head is computed at startup; mismatches refuse to write further.

**Evidence:**
- `backend/core/receipts/chain.py` — `compute_curr_hash()`, `verify_chain()`.
- `backend/core/receipts/store.py` — signing + chain-append transaction.
- Test: `tests/test_receipts_chain.py`.

### PI1.2 — Independent Merkle anchor

**Control:** Every N receipts (default 256, configurable via `TARS_ANCHOR_BATCH`) TARS builds a Merkle root over the batch and writes the root to Solana via a memo transaction (W89). This is a third-party-witnessed timestamp: an auditor can verify a receipt's inclusion in a Solana-anchored root without trusting TARS storage.

**Evidence:**
- `backend/core/receipts/merkle.py` — Merkle tree builder + inclusion proofs.
- `backend/core/receipts/anchor.py` — Solana memo writer.
- `web_extras/routers/public_proof.py` — public unauthenticated proof verifier.

**Gap:** Anchor cadence is best-effort (skipped if Solana RPC is down). The next-best-attempt is logged but not paged; will be paged in v9.4.

### PI1.3 — Test coverage of integrity path

**Control:** Receipts + chain + merkle have dedicated test files. Pytest sweep is the gate; CI runs on every push.

**Evidence:**
- `tests/test_receipts_*.py`.
- `tests/test_compliance_export.py`.
- `tests/test_audit_router.py`.
- `tests/test_gdpr_export.py` (this commit).
- `.github/workflows/ci.yml`.

**Coverage stats (last full sweep, W122):** receipts core 92%, compliance_export 89%, doctor 81%. Target for Type II: ≥85% across security-relevant modules.

**Gap:** Branch coverage on the anchor failure paths is thin (the Solana RPC mock only exercises the happy path). Will be addressed in W262.

### PI1.4 — Composer plan integrity

**Control:** Multi-file edit plans (W253, W256) are persisted with their pre-image diffs and post-apply receipts. A rollback is a single operation that re-applies the inverse from the stored diff. Every applied plan emits a `composer.plan_applied` receipt that hashes the diff.

**Evidence:**
- `backend/core/composer/storage.py::record_applied`.
- `backend/core/composer/executor.py`.
- `tests/test_composer_executor.py`.

---

## C — Confidentiality

**Optional TSC.** This is the table-stakes ask for any regulated-industries customer choosing TARS over Cursor.

### C1.1 — Local-first by default

**Control:** No code, chat, file content, or receipt leaves the operator's machine unless the operator explicitly enables a cloud feature (LLM provider, OAuth connector, meeet.world sync). The default deployment is fully offline-capable.

**Evidence:**
- `web_extras/app.py::_cors_allow_origins` — backend bound to `127.0.0.1` by default.
- `backend/core/privacy/` — privacy mode toggles (W244).
- `web_extras/routers/privacy.py` — `/api/privacy/state` exposes the current data-plane.

### C1.2 — Privacy mode

**Control:** `POST /api/privacy/mode` toggles a global "no cloud" lock that:

- Suspends every outbound connector.
- Pins the LLM provider to the local Ollama backend (or refuses to serve if unavailable).
- Stamps every chat / composer / agent receipt with `privacy_mode=true` so auditors can reconstruct which actions ran offline.

**Evidence:**
- `backend/core/privacy/` (W244).
- `web_extras/routers/privacy.py`.
- `tests/test_privacy_router.py`.

### C1.3 — Secret storage & file permissions

**Control:**

- Meeet token: `~/.tars/meeet_token`, mode `0o600`, never logged.
- Vault (`~/.tars/vault.sqlite`) — OAuth refresh tokens encrypted with a key derived from the host Ed25519 receipt key.
- Bridge HMAC secret: stored in env (`BRIDGE_SHARED_SECRET`), not on disk; signed-cookie + body HMAC on every bridge call (W194).

**Evidence:**
- `web_extras/routers/auth_meeet.py` (token path + redaction).
- `web_extras/routers/vault.py` (vault access guarded).
- `web_extras/routers/webhooks.py` (HMAC verify).

### C1.4 — No telemetry without consent

**Control:** TARS does not emit anonymous telemetry. The opt-in `meeet.world` sync (chat embeddings → AI Clone, usage events, doctor heartbeats) requires:

1. The operator to have written the meeet token to `~/.tars/meeet_token`.
2. The respective feature flag (`TARS_CLONE_SYNC_ENABLED`, `TARS_USAGE_EMIT_ENABLED`, ...) to be set.

Every outbound payload is redacted of PII before send (the meeet wire format is a hash + summary, not the raw text).

**Evidence:**
- `backend/core/clone/sync.py` — payload redaction + opt-in gate.
- `backend/core/meeet/client.py` — explicit `enabled` flag check.
- `backend/core/usage/` (W235).

**Gap:** "Redaction" today is regex-based and unit-tested for the known fields. Type II will require a written enumeration of every wire field × redaction rule — drafted in `docs/contracts/MEEET_WIRE.md` (sibling of W164).

---

## P — Privacy (GDPR / CCPA aligned)

**Optional TSC.** Required for any EU customer; treated as table-stakes for the BUSINESS tier.

### P1.1 — Data-subject access (GDPR Article 15)

**Control:** `POST /api/gdpr/export` produces a signed zip bundle containing every record TARS holds for the requesting subject:

- All receipts (ledger NDJSON + signature)
- All chats (W33)
- All notepads (W243)
- All composer plans (W253)
- All usage events (W235)
- All audit timeline (W255)
- Meeet-token metadata (without the raw token)
- A `manifest.json` SHA-256-indexed and Ed25519-signed

**Evidence:**
- `web_extras/routers/gdpr.py` (W257, this commit).
- `tests/test_gdpr_export.py`.
- The pre-existing one-shot export at `backend/core/compliance_export/gdpr.py` (W104) is folded in as the bundler.

### P1.2 — Right to erasure (GDPR Article 17)

**Control:** `POST /api/gdpr/delete` with confirmation phrase `DELETE_ALL_MY_DATA` marks the subject as pending-erasure with a 30-day grace period (so accidental requests are recoverable). `POST /api/gdpr/delete/cancel` aborts a pending erasure.

A nightly job (the same scheduler that drives W97) sweeps pending erasures past the grace window and:

- Drops the subject's chat messages.
- Drops the subject's notepads, composer plans, usage events.
- Replaces receipt rows with tombstones (the chain hash stays; the payload is replaced by `{"erased": true, "tombstoned_at": "..."}`) — this preserves the chain integrity that PI demands while honouring the erasure request.

**Evidence:**
- `web_extras/routers/gdpr.py` (W257).
- `tests/test_gdpr_export.py::test_delete_soft_deletes_with_grace`.

**Gap:** Chain-tombstone semantics need to be documented in `docs/contracts/RECEIPT_LEDGER.md` as a permitted ledger operation. Drafted; pending review.

### P1.3 — Retention policy

**Control:**

- Receipts: retained for the lifetime of the chain (immutable by design; tombstoned on erasure).
- Chats: retained until the user deletes the thread or triggers GDPR delete.
- Notepads: retained until the user deletes.
- Usage events: 365-day rolling window then aggregated to monthly counters.
- Doctor logs: 14-day rolling window.
- Solana anchors: permanent (on-chain).

**Evidence:** `docs/RETENTION_POLICY.md` (sibling of this doc; lives in marketing/legal/).

### P1.4 — Data minimization

**Control:** TARS stores only the data the local app needs to function. No third-party analytics SDK. No ad ID. No background contact-sync. The complete list of "data classes collected" is enumerable from the SQLite schemas under `~/.tars/`.

**Evidence:**
- `backend/core/storage/bootstrap.py` — every SQLite file is created here; the list is the data inventory.
- `marketing/legal/PRIVACY.md` — public-facing data-class enumeration.

### P1.5 — Consent management

**Control:** OAuth consent (Slack, Gmail, Calendar, GitHub) flows through `web_extras/routers/oauth_consent.py`. Each grant emits a `consent.granted` receipt with the scope; revocations emit `consent.revoked`. The operator can `POST /api/oauth/consent/revoke` at any time.

**Evidence:**
- `web_extras/routers/oauth_consent.py`.
- `web_extras/routers/connectors.py` — per-connector disconnect.

---

## Annual auditor bundle

The `scripts/COMPLIANCE-BUNDLE.command` script (W257) produces a single double-clickable artefact every BUSINESS customer can hand to their auditor at the start of fieldwork. The bundle contains:

- This document (`docs/SOC2_TYPE_II_READINESS.md`), rendered to PDF.
- A 12-month receipt audit PDF (`/api/audit/list` exported via `web_extras/routers/audit.py::export_router`).
- A 12-month GDPR data-export zip (`/api/gdpr/export` scoped to the operator).
- A signed manifest tying all three together.

Output: `~/Documents/TARS/compliance-bundle-<year>/`.

---

## BUSINESS-tier sales angle

Cursor's pricing tops out at the team / enterprise tier with a marketing claim of "SOC 2 Type II compliant" — but the auditor sees Cursor's own cloud SOC 2, not the customer's data trail. There is no cryptographic chain over the user's coding sessions, no per-action receipt the customer's own auditor can sample, and no GDPR self-serve export endpoint.

TARS BUSINESS inverts that: the *customer* owns the receipt chain, the *customer* signs the manifest with a key on their own machine, and the *customer's* auditor verifies the trail without TARS-side tooling. For a regulated buyer ($40/mo × multiple seats) that is the only credible answer.

---

## Sign-off

The operator signs this document by tagging a release whose CHANGELOG entry reads `SOC2 readiness sign-off — <date>`. The auditor receives the tag SHA + the bundle, then opens fieldwork on the next business day.

Until that sign-off, this document is *readiness*, not *attestation*.
