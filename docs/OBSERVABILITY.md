# TARS × meeet.world — observability runbook

> One place to look when **X breaks**. Built around the constraint Claude
> raised in tars-neural-cockpit#8 Q3: "no Sentry, no external APM."
> Everything below uses tools we already have: Cloudflare Pages, Supabase
> Functions Logs, GitHub Actions, browser DevTools, and our own
> `core-bridge` event stream.

**Status:** active. Last edited 2026-05-01 by Cursor.
**Read with:** `docs/SYNC.md`, `docs/contracts/CORE_BRIDGE.md`,
`docs/TARS_MEEET_READINESS.md`.

---

## TL;DR — when X breaks, look here

| Symptom | First place to look | Second place |
|---|---|---|
| `tars.meeet.world` returns 5xx | Cloudflare → Pages → tars-meeet → Deployments → latest run | `_middleware.ts` logs (CF Pages → Functions → Realtime) |
| `tars.meeet.world` 404 on a known route | `public/_redirects` SPA fallback line | CF Pages build output → confirm `index.html` exists |
| `/api/product/downloads` returns 4xx/5xx | Supabase (TARS project `hhpaukjobskcwkxbgecl`) → Functions → `tars-downloads` → Logs | `TARS_ALLOWED_ORIGINS` env var on the function |
| Page view emitted but missing in Supabase | Supabase (meeet core `zujrmifaabkletgnpoyw`) → Functions → `core-bridge` → Logs | TARS Supabase → `tars_event_ingest` table |
| Cookie not set after first visit | `functions/_middleware.ts` → `isProductionHost()` check | DevTools → Application → Cookies → confirm `Domain=.meeet.world` |
| Client-side JS error in production | Supabase SQL editor → `tars_event_ingest where kind='tars.client.error'` | `functions/api/client-error.ts` logs in CF Pages |
| Deploy succeeded but content stale | CF Pages → Pages → Cache → Purge | `_headers` per-path `Cache-Control` (HTML SWR may be holding) |
| GitHub Actions red | `Actions` tab → click run → "Build" or "Type Check" job | Cursor lane → `release-tagged.yml`; Claude lane → meeet GH Actions |
| Cockpit (Tauri) won't start | macOS Console → search "TARS" | `~/Library/Logs/com.meeet.tars/` |

If a symptom isn't here, **add a row** in the same PR that triages it.
Observability docs decay fast otherwise.

---

## §1 The four event streams

Every interesting thing that happens in `tars.meeet.world` lands in
exactly one of these four streams. Memorize them.

### Stream A — Cloudflare Pages **build & deploy** events

- **Where:** Cloudflare Dashboard → Workers & Pages → `tars-meeet` → Deployments.
- **What:** every `git push origin main`, every PR preview, every
  rollback. Each deployment has its own URL
  (`<sha>.tars-meeet.pages.dev`) so you can A/B compare.
- **Retention:** 30 days for previews, ∞ for production.
- **Alert path:** the GitHub Actions workflow
  `tars-meeet-cloudflare-pages.yml` posts a status check on every PR; CF
  Pages also emails on deploy failure. No paging today.

### Stream B — Cloudflare Pages **runtime** logs (`_middleware.ts`)

- **Where:** CF Dashboard → `tars-meeet` → Functions → Logs (Realtime).
- **What:** every `console.log` / thrown error inside
  `experiments/neural-showcase-v3/functions/_middleware.ts`. Includes
  the `tars.page.viewed` event emit failures, missing
  `BRIDGE_SHARED_SECRET` warnings, and uncaught middleware errors.
- **Retention:** 24h on the free tier; 7d on Pro.
- **Alert path:** none today. Operator-Brother can subscribe to the
  Workers Logpush integration when needed.

### Stream C — Supabase **Edge Functions** logs (both projects)

- **Where (TARS subdomain):** Supabase Dashboard → project
  `hhpaukjobskcwkxbgecl` → Edge Functions → `tars-downloads` /
  `tars-ingest` → Logs.
- **Where (meeet core):** Supabase Dashboard → project
  `zujrmifaabkletgnpoyw` → Edge Functions → `core-bridge` → Logs.
- **What:** every request, response code, latency, and `console.log`
  output. Filterable by `trace_id` since Cursor wires that header through
  every function.
- **Retention:** 24h on free, 7d on Pro, 28d on Team.
- **Alert path:** Supabase emails project owners on
  >5% error rate increase. No PagerDuty-grade alerting.

### Stream D — Supabase **Postgres** (`tars_event_ingest` table)

- **Where:** TARS Supabase → SQL editor → `select * from
  public.tars_event_ingest order by created_at desc limit 100;`
- **What:** every event that survived `tars-ingest` (i.e., every
  `tars.*` event the bridge or middleware fired). Schema:
  `id`, `kind`, `trace_id`, `session_id`, `payload jsonb`, `created_at`,
  `contract_version`, `source`.
- **Retention:** indefinite. Cursor will add a daily Supabase cron
  archive job if the table crosses 10M rows.
- **Alert path:** none today. Add a Supabase pg_cron query that emails
  Operator if `count(*) where created_at > now() - interval '15
  minutes'` drops below the 24h average — that's our pulse alert.

---

## §2 trace_id — the through-line

Every TARS event has a `trace_id`. It is generated in three places (see
`docs/contracts/CORE_BRIDGE.md` §authn for the full contract):

1. **Origin: client browser visit.** `_middleware.ts` reads the inbound
   `x-trace-id` header. If absent, it generates a UUID v4 and echoes it
   on the response as `X-Tars-Trace-Id`. Same id flows to
   `tars.page.viewed` via `core-bridge`.
2. **Origin: Tauri desktop event.** The TARS desktop shell generates
   trace ids via `Jarvis/jarvis/backend/core/meeet/trace.py`
   (`trace_scope`) and includes them in every meeet ingest call.
3. **Origin: meeet-app server-side action.** When the meeet-app on
   `meeet.world` calls `core-bridge/relay-event`, it includes its own
   `trace_id` so we can stitch the two halves of one user journey.

**To investigate a single user journey:**

```sql
-- Supabase SQL editor on hhpaukjobskcwkxbgecl
select created_at, kind, source, payload
from public.tars_event_ingest
where trace_id = '<paste-from-X-Tars-Trace-Id-header>'
order by created_at;
```

You should see, in order, something like:
`tars.page.viewed` → `tars.click.install_copy` → `tars.install.dmg.opened`
all sharing one `trace_id`. If the chain breaks, the `kind` that's
missing is the failure point.

---

## §3 Common diagnostics — copy-paste runbooks

### 3.1 "Site is down"

```bash
# Step 1 — is DNS resolving?
dig +short tars.meeet.world

# Step 2 — is CF Pages serving?
curl -sI https://tars.meeet.world/ | head -5

# Step 3 — is the contract header set?
curl -sI https://tars.meeet.world/ | grep -i x-tars-contract
# Expected: X-Tars-Contract: 1.0.0

# Step 4 — drop in CF dashboard for deploy state
open "https://dash.cloudflare.com/?to=/:account/pages/view/tars-meeet"
```

### 3.2 "Downloads manifest is wrong"

```bash
# Step 1 — what does the proxy return?
curl -sf https://tars.meeet.world/api/product/downloads | jq

# Step 2 — what does the source of truth return?
curl -sf https://hhpaukjobskcwkxbgecl.supabase.co/functions/v1/tars-downloads | jq

# Step 3 — hop to Supabase logs to see why it differs
open "https://supabase.com/dashboard/project/hhpaukjobskcwkxbgecl/functions/tars-downloads/logs"
```

If step 1 ≠ step 2: CF Pages is caching. Hit purge in CF Dashboard.
If both are wrong: `TARS_DOWNLOADS_MANIFEST_URL` env var on the
function got overridden, or `tars-downloads/index.ts` changed. Check the
`hhpaukjobskcwkxbgecl` deployment list for unexpected pushes.

### 3.3 "I emitted an event but it's not in the database"

```bash
TRACE=acceptance_$(date -u +%s)
SESS=acceptance_session_$(date -u +%s)

curl -sS -X POST \
  https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/core-bridge/relay-event \
  -H "Content-Type: application/json" \
  -H "Origin: https://tars.meeet.world" \
  -H "x-bridge-secret: $BRIDGE_SHARED_SECRET" \
  -d '{
    "kind": "tars.observability.probe",
    "trace_id": "'"$TRACE"'",
    "session_id": "'"$SESS"'",
    "contract_version": "1.0.0",
    "payload": { "source": "observability_runbook" }
  }'
# Expected response: {"ok":true,"persisted":true,...}
```

Then in Supabase SQL editor:

```sql
select created_at, kind, source from tars_event_ingest
where trace_id = '<paste-TRACE-from-above>'
order by created_at;
```

Failure modes:
- `403 origin_not_allowed` → CORS allowlist on `core-bridge` doesn't
  include the origin. Fix in `TARS_ALLOWED_ORIGINS` env var.
- `401` → wrong `BRIDGE_SHARED_SECRET`. Rotate and re-set in both
  Cloudflare Pages env and Supabase secrets.
- `200 OK` but row missing → `core-bridge` swallowed the relay. Check
  the function's logs for `relay rejected` or `tars-ingest unreachable`.
- `200 OK persisted:false` → `tars-ingest` is in safe-mode (table
  missing). Re-apply the migration `20260430094500_tars_event_ingest.sql`.

### 3.4 "OG preview shows the wrong thing"

```bash
# Force-refresh the cached og:image URL on the four big platforms.
# (You only need to do this once per deploy, but humans forget.)
open "https://www.linkedin.com/post-inspector/inspect/$(printf '%s' 'https://tars.meeet.world/' | jq -sRr @uri)"
open "https://cards-dev.twitter.com/validator"
open "https://developers.facebook.com/tools/debug/?q=$(printf '%s' 'https://tars.meeet.world/' | jq -sRr @uri)"
open "https://www.opengraph.xyz/url/$(printf '%s' 'https://tars.meeet.world/' | jq -sRr @uri)"
```

If those still show stale images >24h after canonical flip, the most
likely cause is that `og:image` URLs on `meeet.world` (older fanout
posts on social) are still resolving. They will expire as scrapers
re-fetch.

### 3.5 "Client-side error: how do I see it?"

Every uncaught browser error and unhandled promise rejection on
`tars.meeet.world` is now captured by
`src/lib/clientError.ts` → `functions/api/client-error.ts` →
`core-bridge` → `tars-ingest`. To inspect:

```sql
-- Supabase SQL editor on hhpaukjobskcwkxbgecl
select created_at, payload->>'sub_kind' as kind, payload->>'message' as message,
       payload->>'page' as page, payload->>'source' as source,
       payload->>'line' as line, trace_id, session_id
from public.tars_event_ingest
where kind = 'tars.client.error'
  and created_at > now() - interval '1 hour'
order by created_at desc limit 100;
```

To follow a single user's error chain (errors share a session):

```sql
select created_at, kind, payload from public.tars_event_ingest
where session_id = '<paste-from-tars_session_id-cookie>'
order by created_at;
```

If errors are missing for a real user-reported failure, check:
- `BRIDGE_SHARED_SECRET` is set on Cloudflare Pages (without it,
  `/api/client-error` returns `200 persisted:false`).
- `core-bridge` accepts `https://tars.meeet.world` origin.
- The reporter is no-op on `localhost` and in the Tauri shell — both
  by design.

### 3.6 "GitHub Actions is red"

```bash
# Step 1 — which workflow?
gh run list --repo alxvasilevvv/tars-neural-cockpit --limit 5
gh run list --repo alxvasilevvv/meeet-solana-state-941a6045 --limit 5

# Step 2 — view the failing run
gh run view <run-id> --repo <owner/repo> --log-failed
```

Repository-specific failure clusters:
- `tars-neural-cockpit` → see `docs/CHANGELOG_AGENTS.md`
  ("YAML scanner error on line 139") for the canonical YAML-trap.
- `meeet-solana-state-941a6045` → most red runs are vitest. Check
  `useLanguage` mock dictionary first (history of missing keys).

---

## §4 What we explicitly do NOT do

- **No Sentry / Datadog / New Relic.** Adding a vendor is a separate
  decision and requires Operator approval.
- **No PagerDuty / OpsGenie.** Alerting today is "GitHub email +
  Supabase email + ad-hoc Telegram message".
- **No frontend RUM beyond `_middleware.ts` page-view.** If we want
  Core Web Vitals over time, `web-vitals` npm package + `core-bridge`
  emit is the next-step pattern (kept off the roadmap until requested).
- **No client-side error reporting beyond `console.error`.** A
  unhandledrejection handler that emits `tars.client.error` through
  `core-bridge` is a 30-line follow-up if/when needed.

---

## §5 Owners

| Stream | Primary owner | Backup |
|---|---|---|
| CF Pages build & deploy | Cursor | Operator-Brother |
| CF Pages runtime (`_middleware.ts`) | Cursor | — |
| Supabase TARS project (`hhpaukjobskcwkxbgecl`) | Cursor | Operator-Brother |
| Supabase meeet core (`zujrmifaabkletgnpoyw`) | Claude / Lovable | Operator-Brother |
| Postgres `tars_event_ingest` table | Cursor | — |
| GitHub Actions (TARS repo) | Cursor | — |
| GitHub Actions (meeet repo) | Claude | Cursor (advisory) |

When in doubt, ping the primary owner via the corresponding GitHub
issue thread (`tars-neural-cockpit#8` is the live channel).

---

## §6 Future work — in priority order

1. ~~**`tars.client.error` emit**~~ — **SHIPPED 2026-05-01.**
   `src/lib/clientError.ts` + `functions/api/client-error.ts` +
   `installClientErrorReporter()` call in `src/main.tsx`. Captures
   uncaught errors and unhandled rejections, dedupes per signature,
   rate-limits to 10/min, pipes through `core-bridge` →
   `tars-ingest` → `tars_event_ingest` table as
   `kind = "tars.client.error"`. No-op on `localhost` and inside the
   Tauri shell. Closes meeet OPEN_QUESTIONS.md Q4.
2. ~~**Pulse alert via pg_cron**~~ — **REPLACED 2026-05-01** with
   `.github/workflows/tars-meeet-synthetic-monitor.yml` (zero-vendor
   GitHub Actions cron probe every 15 min). Avoids the email-credential
   dependency that pg_cron alerts would have introduced. Probes SPA
   root, `/api/product/downloads`, the origin manifest, and
   `core-bridge/health`; failure is a workflow red → GitHub email.
3. **Web Vitals pipe** — `web-vitals` npm package emitting
   `tars.perf.lcp / fid / cls` through `core-bridge`. Maps to a single
   Supabase view that the cockpit dashboard can render.
4. **Cloudflare Workers Logpush → Supabase** — long-tail retention for
   CF Pages function logs (today: 24h on free, 7d on Pro).
5. **Status page** — `status.meeet.world` row for `tars.meeet.world`
   (per `docs/TARS_MEEET_OPS_TODO.md` post-launch step).

Each of the above is an issue waiting to be filed, not a commitment.
The runbook above is sufficient for first 90 days of production.

---

> **If this document is wrong, the next person on call will lose 30
> minutes.** Edit, don't apologize.
