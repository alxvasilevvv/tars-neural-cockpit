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
