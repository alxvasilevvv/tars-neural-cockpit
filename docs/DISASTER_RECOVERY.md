# Disaster recovery & incident response — `tars.meeet.world` + `meeet.world`

> **Status:** baseline drafted by Cursor 2026-05-01.
> **Owners:** Operator (= you) for credentials + DNS, Cursor for TARS
> services, Claude for meeet-app. This is the playbook we follow when
> something breaks in production.

This document is intentionally pragmatic, not aspirational. Everything
listed below is reachable with the credentials and tools the team
already has on hand. It supersedes any earlier informal notes about
recovery.

---

## 1. Severity ladder

| Sev | Symptom                                                                                                       | Response window | Who joins                                  |
| --- | -------------------------------------------------------------------------------------------------------------- | --------------- | ------------------------------------------ |
| 1   | Both `meeet.world` and `tars.meeet.world` down. Treasury / wallet operations failing. Data loss observed.       | 15 min          | Operator + Cursor + Claude all-hands       |
| 2   | One subdomain down. Auth broken. Manifest 5xx. Token transfers failing.                                         | 30 min          | The owning agent + Operator                |
| 3   | Degraded UX, partial loss of feature, mobile-only regression, slow SLO.                                         | 4 h             | Owning agent. Operator informed but optional. |
| 4   | Cosmetic, copy, single-route, no behavioural impact.                                                          | next business day | Owning agent in normal flow                |

The QA Agent (`make qa-agent`) runs every 30 minutes and posts to
`tars-neural-cockpit` Actions; a red status that lasts ≥2 cron cycles
auto-escalates to Sev 2.

---

## 2. Incident response flow

1. **Detect.** Sources, in priority order:
   - QA Agent failure on tars-neural-cockpit Actions
   - Synthetic monitor failure (cron `*/15`)
   - User report on TARS#8
   - `tars.client.error` event spike in `tars_event_ingest` (kind filter)
2. **Triage.** Whoever notices first opens (or comments on) an incident
   issue using template
   `https://github.com/alxvasilevvv/tars-neural-cockpit/issues/new?title=incident:`.
3. **Stabilise** with the playbook in §3.
4. **Communicate.** Single-source the status on TARS#8 with timestamps.
   Don't fork into Discord / Slack / DM.
5. **Resolve.** When the QA Agent flips green for 2 consecutive runs.
6. **Postmortem** (Sev 1 + 2 only). Use the template in §6.

---

## 3. Stabilisation playbooks

### 3.1 `tars.meeet.world` returning 5xx or wrong content

**First check:**
```bash
make qa-agent
```

**Then by failure category:**

| Probe failing                 | Likely cause                              | First action                                                                                                                                                                                                |
| ----------------------------- | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dns.tars_subdomain`          | DNS propagation glitch / wrong CNAME       | `dig +trace tars.meeet.world`. If wrong target, fix CNAME in CF dashboard.                                                                                                                                  |
| `http.spa_root` (302)         | CF Pages disconnected, CNAME wrong         | CF dashboard → Pages → `tars-meeet` → Custom domains → confirm `tars.meeet.world` listed and active.                                                                                                        |
| `http.security_headers`       | `_headers` file lost in deploy              | Re-deploy from latest `main`: GH Actions → `tars.meeet.world — Cloudflare Pages` → Run workflow.                                                                                                            |
| `http.session_cookie`         | `_middleware.ts` not running                | CF Pages → `tars-meeet` → Functions tab → confirm `_middleware.ts` listed. If missing, re-deploy.                                                                                                            |
| `api.manifest_subdomain`      | `_redirects` mis-routed                    | `_redirects` is in `experiments/neural-showcase-v3/public/`. Confirm `200` (not `301`) on `/api/product/downloads` line.                                                                                    |
| `api.manifest_origin`         | `tars-downloads` EF broken                 | Supabase dashboard → tars project → Edge Functions → tars-downloads → check logs. Roll back via `supabase functions deploy tars-downloads --project-ref hhpaukjobskcwkxbgecl` from a known-good commit.    |
| `api.core_bridge_health`      | core-bridge EF in old project broken       | Supabase dashboard → core project → Edge Functions → core-bridge → logs. Lovable owns deploy; ping Claude on TARS#8 with the logs.                                                                          |

**Hard rollback:** CF dashboard → Pages → `tars-meeet` → Deployments →
pick the last green deploy → **Rollback**. CF keeps every deploy artefact
for 30 days. This restores SPA + middleware + headers in <60s.

**Nuclear option (subdomain only):** CF Pages → Custom Domains → toggle
`tars.meeet.world` off. Visitors hit `meeet.world` until the next
deploy. Treasury / payments / agents are unaffected.

### 3.2 `meeet.world` returning 5xx

Same triage as 3.1 but the owning agent is Claude (Lovable).

**Hard rollback:** Lovable dashboard → Deployments → pick last green →
Rollback. Lovable retains 100 deployments (or 30 days, whichever is
shorter).

### 3.3 Supabase database degraded

Symptoms: 502/503 on Edge Functions, vitest failing on `db query` calls.

1. Supabase dashboard → relevant project → **Health** tab → check region
   status. If Supabase is upstream-degraded, post a holding update on
   TARS#8 and wait. SLA-tracking lives at
   https://status.supabase.com.
2. If single-table degradation (e.g. only `tars_event_ingest` slow):
   ```sql
   -- check planner stats
   SELECT relname, last_analyze, last_autoanalyze
     FROM pg_stat_user_tables
    WHERE relname = 'tars_event_ingest';
   ANALYZE tars_event_ingest;  -- safe, fast
   ```
3. If runaway insert volume: temporarily set `tars-ingest` EF to return
   `persisted: false` for non-critical kinds (the safe-mode flag is
   already wired). Open a separate issue tagged `economy-incident` if
   the spike looks like grooming.

### 3.4 Solana / token operations failing

Right now token operations are **off-chain** (per `Tokenomics.tsx` /
`Deploy.tsx`). When we cut over to on-chain:

1. RPC node degradation → switch to fallback RPC URL via env (held by
   Lovable, not in this repo).
2. Treasury wallet drained → assume key compromise. **Stop all
   payouts** by deploying an emergency Edge Function patch that returns
   503 from `staking-action`, `governance-vote`, and any quest reward
   handler. Then rotate keys (see §5).

### 3.5 Core-bridge cross-project bridge offline

Lovable owns core-bridge deploy. When down:

1. TARS still works (subdomain + cockpit) — only cross-project event
   relay is degraded.
2. `tars.client.error` events queue locally on the client (we don't
   currently buffer; events drop when bridge is down — accepted loss
   per design).
3. Open issue tagged `bridge-down` and ping Claude on TARS#8.

---

## 4. Backups & data retention

| Asset                              | Backup mechanism                                      | Frequency       | Retention | Recovery target |
| ---------------------------------- | ----------------------------------------------------- | --------------- | --------- | --------------- |
| Source code (TARS + meeet)          | GitHub repos, all branches & tags                     | every push      | indefinite | RPO 0           |
| Cursor branch protection           | required reviews on `main`                            | always          | n/a        | RPO 0           |
| Supabase (TARS) DB                 | Supabase automated daily PITR (paid tier required)    | 1 day           | 7 days    | RPO ≤24h         |
| Supabase (core/old) DB             | Lovable-managed; same plan as above                   | 1 day           | 7 days    | RPO ≤24h         |
| Supabase Edge Function source      | Stored in repos; deploy idempotent                    | n/a             | n/a        | RPO 0           |
| Cloudflare Pages deploys           | CF retains every deploy                               | per deploy      | 30 days   | RPO 0           |
| Lovable deploys                    | Lovable retains last 100 / 30 d (whichever shorter)   | per deploy      | 30 days   | RPO 0           |
| Secrets (CF, GH, Supabase)         | Operator's password manager + rotation log §5         | manual          | indefinite | RTO 5 min        |
| `tars_event_ingest` data           | Supabase PITR + `audit_*` companion tables            | continuous      | 90 days    | RPO ≤24h         |

**Action items still pending Operator:**

- Confirm Supabase **Pro tier** (or higher) on the TARS project
  `hhpaukjobskcwkxbgecl` so PITR is enabled. Free tier has no PITR.
- Confirm same on the meeet/core project `zujrmifaabkletgnpoyw`.

---

## 5. Secrets inventory & rotation policy

**The shared secrets that exist today:**

| Secret name                | Where it lives                                         | Rotated when                                         | Rotation playbook                                                                                                                                                                                  |
| -------------------------- | ------------------------------------------------------ | ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `BRIDGE_SHARED_SECRET`     | core-bridge EF, CF Pages env, GH Actions secret        | Suspected leak; quarterly otherwise                  | Generate fresh 32-byte token (`openssl rand -hex 32`). Update Lovable EF env, CF Pages env, GH `BRIDGE_SHARED_SECRET` secret in same window. Old secret kept valid for 1 hour for overlap.       |
| `TARS_INGEST_API_KEY`      | core-bridge EF (forwarded), tars-ingest EF             | Suspected leak; quarterly otherwise                  | Generate, push to TARS Supabase function secret, then to core-bridge env. Test from QA Agent's `relay_roundtrip` probe.                                                                            |
| `CLOUDFLARE_API_TOKEN`     | GH Actions secret (only)                              | Suspected leak; rotated whenever a previous Operator stops being involved | CF dashboard → Profile → API Tokens → revoke + create new with same scope. Update GH secret. Re-run `tars.meeet.world — Cloudflare Pages` workflow to confirm.                                       |
| `CLOUDFLARE_ACCOUNT_ID`    | GH Actions secret                                      | Doesn't rotate                                       | Read-only id; only changes if you switch CF accounts.                                                                                                                                              |
| Supabase `SERVICE_ROLE_KEY` | Edge Function runtime only (auto-injected)             | If anyone outside Operator + Cursor + Claude sees it | Supabase dashboard → Project settings → API → "Reset service_role". This invalidates all running EFs until they pick up the new key on next cold start (~30s).                                     |
| Supabase `ANON_KEY`        | Public; used by browser                               | Almost never                                         | Reset via Supabase dashboard. Update VITE-baked env var. Old anon key keeps RLS-restricted access; this is by design.                                                                              |
| GitHub PAT for `gh` CLI    | Operator's local machine                              | Quarterly                                            | https://github.com/settings/tokens → revoke + new token with `repo` + `workflow` scopes.                                                                                                            |

**On suspected leak:**

1. Rotate the affected secret immediately.
2. Open a P1 issue tagged `security-incident` on tars-neural-cockpit.
3. Audit `tars_event_ingest` for spikes between leak time and rotation.
4. If user data was accessed, follow §7 (privacy disclosure).

---

## 6. Postmortem template

Open as a Markdown file at `docs/postmortems/YYYY-MM-DD-<slug>.md` after
any Sev 1 or Sev 2 incident.

```markdown
# Postmortem: <one-line summary>

- **Severity:** 1 / 2 / 3 / 4
- **Detected:** YYYY-MM-DDThh:mm:ssZ via <source>
- **Resolved:** YYYY-MM-DDThh:mm:ssZ
- **Outage duration:** Hh:Mm
- **Affected services:** ...
- **Affected users (estimate):** ...

## Timeline (UTC)

- HH:MM — <event>
- HH:MM — <event>

## Root cause

<one paragraph, no blame>

## What went well

<bullets>

## What went badly

<bullets>

## Action items

| # | Owner | Action | Tracking issue | Done by |
| - | ----- | ------ | -------------- | ------- |
| 1 | ...   | ...    | #...           | YYYY-MM-DD |
```

We commit the postmortem with the same lane prefix used for the fix
(e.g. `cursor/postmortem-2026-05-01-spline-bundle-spike`).

---

## 7. Privacy & data disclosure

We don't currently ship to users in jurisdictions that mandate breach
notification (no EU/CA opt-in). When that changes, the §7 process gets
fleshed out. Until then:

1. If a leak exposes PII, post a holding update on TARS#8 and pause new
   sign-ups by toggling Supabase Auth provider off in the affected
   project.
2. Operator notifies any directly affected users via the email they
   used to sign up.
3. We publish a public note on `meeet.world/security` if user data was
   actually exfiltrated.

The QA Agent and `tars.client.error` handler are configured **not** to
log user emails, wallet addresses, or balances. If you find one in the
logs, that's a P1 by itself (and a postmortem candidate).

---

## 8. RTO / RPO targets

| Tier                              | RTO   | RPO   | Notes                                                                                       |
| --------------------------------- | ----- | ----- | ------------------------------------------------------------------------------------------- |
| Public marketing pages             | 5 min | 0     | Static, served from CF/Lovable edge. Rollback is 1 click.                                    |
| Cockpit / app                      | 15 min| 0     | Same hosting. Rollback to last green deploy is the canonical recovery.                       |
| Manifest / downloads               | 5 min | 0     | EF + CF Pages proxy + `_redirects` fallback to origin. We probe both paths in the QA Agent.  |
| User auth                          | 30 min| 0     | Supabase upstream. We can't beat their availability; we can fail-open the marketing site.    |
| Token transfers (off-chain)         | 1 h   | 1 h   | Today off-chain via Edge Function. RPO bounded by Supabase PITR.                             |
| Token transfers (on-chain, future) | 1 h   | 0     | Solana settles in seconds; if RPC is down we replay from on-chain state on recovery.         |

When the gap between target and reality is too wide (e.g. RPO ≤24h on
Supabase free tier), the gap goes into `docs/MEEET_PROJECT_REVIEW.md`
risk register and we plan the upgrade.
