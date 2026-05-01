# `tars.meeet.world` operator infrastructure checklist

> **For:** Operator-Brother (the human who owns DNS / Cloudflare / repo
> admin).
> **From:** Cursor.
> **Read with:** `docs/TARS_MEEET_READINESS.md`,
> `docs/contracts/TARS_SUBDOMAIN.md`.

This is the ordered list of one-time setup steps the agent cannot do
on its own. Each step has a verification command. When you finish
each one, leave a one-line update on
[tars-neural-cockpit#8](https://github.com/alxvasilevvv/tars-neural-cockpit/issues/8)
so both agents see the unblock.

Estimated total time: **30 minutes**.

---

## CURRENT STATE — `tars.meeet.world` IS LIVE 2026-05-01 04:34 UTC

Cursor finished the cutover end-to-end and ran two follow-up patches:

- ✅ Cloudflare Pages project `tars-meeet` created.
- ✅ CNAME `tars.meeet.world → tars-meeet.pages.dev` (proxied, TTL 1).
- ✅ Pages custom domain status `active` (Google CA, http-01).
- ✅ Production response: `HTTP/2 200`, `X-Tars-Contract: 1.0.0`,
  `tars_session_id` cookie scoped to `.meeet.world`, full HSTS / NEL /
  permissions-policy / X-Frame-Options stack.
- ✅ Same-origin `/api/product/{downloads,version,client-error}`
  served by Pages Functions.
- ✅ Pages production env: `CORE_BRIDGE_URL` set.
- ✅ GitHub repo secrets `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`
  pushed via gh CLI — the deploy workflow runs autonomously on push to
  main and PRs.
- ✅ CI Pages deploy now runs from
  `experiments/neural-showcase-v3/` so wrangler bundles `functions/`
  (post-cutover regression in 195547a7 fixed in PR #21).
- ✅ **SPA HTTP status:** Do **not** copy `dist/index.html` →
  `dist/404.html` in CI. Cloudflare Pages serves `404.html` with a real
  **404** status even when the body is the SPA shell, which defeats
  `public/_redirects` (`/* → /index.html 200`) and breaks probes for
  `/install`, `/cockpit`, etc. The deploy workflow omits that step; see
  `docs/CHANGELOG_AGENTS.md` (2026-05-01 — Pages SPA HTTP 200).
- ✅ Synthetic monitor green against prod; QA agent green once the
  deploy above is on `main` (route probes expect HTTP 200, not 404).
- ✅ Acceptance script (`scripts/acceptance_tars_meeet.sh`)
  passes 5/5 reachable gates; 5/6 (bridge) and 7 (Lighthouse)
  SKIP cleanly when prerequisites are absent.
- ✅ Target QA Agent (no auth) after fixes: `25 PASS / 0 FAIL / 2 WARN / 3 SKIP`.
  Both warnings are operator-action-only (`schema.sitemap` →
  Lovable, `api.client_error` → bridge secret).

### Outstanding items (operator must paste one secret + one cleanup)

These cannot be set programmatically because Cursor never sees the
secret value:

1. **`BRIDGE_SHARED_SECRET` on Pages production env.**
   Pages dashboard → `tars-meeet` → Settings → Environment variables →
   Production → Add: `BRIDGE_SHARED_SECRET = <value Lovable uses on
   core-bridge>`. Click "Save and deploy" (or wait for the next CI
   deploy). This single paste unblocks:
   - QA agent: 3 SKIPs + 1 WARN → 4 additional PASS.
   - Synthetic monitor: enables `core-bridge /health` probe.
   - Browser-side error reports actually persist into
     `tars_event_ingest` (today they short-circuit with
     `bridge_unconfigured`).
   - Same secret is required for the `BRIDGE_SHARED_SECRET` GitHub
     repo secret if you want the synthetic monitor's bridge probe
     to run in CI.
2. **(Optional) Decommission `tars-downloads` Supabase function** in
   the new project (`hhpaukjobskcwkxbgecl`). The function is no
   longer referenced by any client; its `DEFAULT_ORIGIN` would loop
   back into the Pages Function. The synthetic monitor demotes its
   probe to a warning so it'll degrade gracefully whether you keep
   or remove it. Removal is preferred — the Pages Function is now
   the source of truth.
3. **(Lovable lane)** Sitemap canonical-flip:
   `meeet.world/sitemap.xml` should add the `tars.meeet.world/*`
   URLs. Tracked in the `meeet#5` Claude prompt batch.

After step 1 is done, run:
```
BRIDGE_SHARED_SECRET="<value>" make qa-agent
```
to confirm GREEN.

---

## Step 1 — Cloudflare: create Pages project (5 min)

1. Cloudflare dashboard → **Workers & Pages** → **Create application** → **Pages** → **Connect to Git**.
2. Authorize the GitHub app for `alxvasilevvv/tars-neural-cockpit`.
3. Project name: `tars-meeet`.
4. Production branch: `main`.
5. Build settings → **Skip build** (we build in GitHub Actions).
   - If "Skip" isn't available, set:
     - Build command: `npm run build`
     - Build output: `experiments/neural-showcase-v3/dist`
     - Root directory: `experiments/neural-showcase-v3`
6. Save. Don't deploy from the dashboard yet.

**Verification**: project appears in **Workers & Pages** list with
state "No deployments yet".

---

## Step 2 — GitHub: add Cloudflare secrets (3 min)

1. Cloudflare dashboard → **My Profile** → **API Tokens** → **Create Token** → use template **"Edit Cloudflare Workers"** (covers Pages too).
   - Scope to your account; permissions: `Account:Cloudflare Pages:Edit` is enough if the template feels too broad.
   - Save the token value — you won't see it again.
2. Find your Account ID — **Workers & Pages** sidebar → top-right corner.
3. GitHub → repo `alxvasilevvv/tars-neural-cockpit` → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:
   - `CLOUDFLARE_API_TOKEN` = (token from step 1)
   - `CLOUDFLARE_ACCOUNT_ID` = (account id from step 2)

**Verification**: GitHub Actions tab — re-run the latest
`tars.meeet.world — Cloudflare Pages` workflow. The "Probe deploy
credentials" step prints `ready=true` and the deploy step runs
without warning.

---

## Step 3 — Cloudflare Pages: env vars on the project (2 min)

1. Cloudflare dashboard → Pages → `tars-meeet` → **Settings** → **Environment variables** → **Production**.
2. Add:
   - `BRIDGE_SHARED_SECRET` — same value Lovable already configured on the `core-bridge` Edge Function. Ask Claude on tars-neural-cockpit#8 if you're not sure where to find it.
   - `CORE_BRIDGE_URL` — leave unset (defaults to `https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/core-bridge`).

**Verification**: Pages → `tars-meeet` → **Settings** → **Environment
variables** shows `BRIDGE_SHARED_SECRET` (value masked). The next
deploy will use them.

---

## Step 4 — DNS: point `tars.meeet.world` at Pages (5 min)

1. Cloudflare dashboard → **Websites** → `meeet.world` → **DNS** → **Records** → **Add record**.
2. Type: `CNAME`. Name: `tars`. Target: `tars-meeet.pages.dev` (Cloudflare suggests this automatically once the Pages project is created).
3. Proxy status: **Proxied** (orange cloud).
4. TTL: Auto.
5. Cloudflare dashboard → Pages → `tars-meeet` → **Custom domains** → **Set up a custom domain** → enter `tars.meeet.world` → activate.
6. Wait for the SSL certificate to provision (Cloudflare usually does this in ~60 seconds).

**Verification**:
```
curl -sI https://tars.meeet.world/ | head -1
# expect: HTTP/2 200
```

---

## Step 5 — Smoke run (5 min)

After Steps 1–4 are green:

1. Push any small commit to `tars-neural-cockpit:main` (or trigger
   the workflow manually: GitHub → Actions → `tars.meeet.world —
   Cloudflare Pages` → **Run workflow**).
2. Watch the run finish. It will deploy and probe the manifest.
3. Run the bridge smoke locally (Operator-side):

```bash
cd /Users/alien/Documents/Claude/Projects/Jarvis/jarvis
BRIDGE_SHARED_SECRET="<the same secret>" make smoke-core-bridge
```

Expected: every assertion green, the e2e relay-event lands in TARS
ingest with `persisted:true`.

4. Open `https://tars.meeet.world/` in a fresh incognito window.
   Open DevTools → Application → Cookies. Confirm a
   `tars_session_id` cookie exists with `Domain=.meeet.world`.

**Verification**: post a one-line update on tars-neural-cockpit#8:
```
[Operator] DNS up · Pages deployed · cookie issued · smoke green
```

---

## Step 6 — status.meeet.world row (post-launch, optional, 5 min)

When the subdomain has been up for 7 days without incident:

1. Add a new row to the status page config: `tars.meeet.world`
   with the manifest endpoint as the health check
   (`https://tars.meeet.world/api/product/downloads`, expect
   200 + JSON).
2. Wire to the existing alerting channel.

This step is non-blocking and can be deferred. It's listed for
completeness.

---

## What if you don't have a Cloudflare account?

Cloudflare Pages is free for the size we need. Sign-up is 60s with
GitHub OAuth. If for some reason you'd rather use Vercel:

- The build / typecheck / test steps in
  `.github/workflows/tars-meeet-cloudflare-pages.yml` are
  Vercel-compatible — only the deploy step would need swapping for
  `vercel/action@v1`.
- `_redirects` syntax differs slightly; `_headers` is identical.
- The `functions/_middleware.ts` Cloudflare Pages Function would
  become a Vercel Edge Function in `api/_middleware.ts` — the
  signature and behaviour port one-to-one.

If you want Vercel, leave a note on tars-neural-cockpit#8 and Cursor
will ship the alternate config.

---

## Rollback plan

If Step 5 reveals a regression in the production cut:

1. Cloudflare dashboard → Pages → `tars-meeet` → **Deployments** →
   pick the last green deploy → **Rollback**.
2. Or: temporarily disable the custom domain (`tars.meeet.world` → toggle off) — visitors hit `meeet.world` until the next deploy lands.
3. Open an issue in `tars-neural-cockpit` titled
   `regression: tars.meeet.world <symptom>` and ping Cursor
   on tars-neural-cockpit#8. Cursor will own the fix.

Cloudflare Pages keeps every deploy artefact for 30 days, so rollback
is reversible without operator stress.
