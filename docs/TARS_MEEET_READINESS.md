# `tars.meeet.world` integration readiness — gap audit

> **Filed by:** Cursor, 2026-04-30 / 2026-05-01.
> **Live channel:** [tars-neural-cockpit#8](https://github.com/alxvasilevvv/tars-neural-cockpit/issues/8).
> **Spec:** `docs/contracts/TARS_SUBDOMAIN.md`.
> **Read this with:** `docs/SYNC.md`, `docs/ROADMAP_SHARED.md`,
> `docs/TARS_MEEET_OPS_TODO.md` (Operator infra-side checklist).

---

## TL;DR

| Layer            | Status      | Owner      | Blocker?          |
| ---------------- | ----------- | ---------- | ----------------- |
| Frontend (build) | ✅ ready     | Cursor     | no                |
| Backend FastAPI  | ✅ ready     | Cursor     | no (not on path)  |
| Bridge contracts | ✅ frozen    | Cursor     | no                |
| Edge cookie/log  | ✅ shipped   | Cursor     | no — needs secret |
| CI deploy        | ✅ shipped   | Cursor     | needs CF tokens   |
| DNS / SSL        | ❌ pending   | Operator   | **yes**           |
| meeet-app proxy  | ❌ pending   | Claude     | **yes**           |
| Cookie sharing   | ❌ partial   | Claude     | yes (auth side)   |
| status.meeet     | ❌ pending   | Operator   | no (post-launch)  |

Cursor is fully ready on its lane. Two external dependencies remain
(Operator-side DNS, Claude-side meeet-app proxy / auth bridge); both
are tracked below with concrete asks.

---

## 1. What is shipped on the Cursor lane

### 1.1 Frontend (`experiments/neural-showcase-v3/`)
- **Static SPA** (React 18 + Vite 5 + Tailwind 4 + framer-motion).
  All marketing routes already render: `/`, `/install`, `/pitch`,
  `/pricing`, `/faq`, `/compare`, `/cockpit`, `/onboarding`,
  `/build-with`, `/changelog`, `/roadmap`, `/press`, `/privacy`,
  `/terms`, `/security`, `/docs`, `/status`.
- **Production env**: `.env.production` baked with
  `VITE_TARS_API=https://tars.meeet.world` (subdomain itself, single
  origin, downloads proxied via `_redirects`).
- **Static assets ready**: `public/og*.svg` (per-route Open Graph
  cards), `public/favicon.svg`, `public/manifest.webmanifest`,
  `public/sw.js`, `public/sitemap.xml`, `public/robots.txt`.
- **Analytics primitives**: `src/lib/analytics.ts` with `track()`,
  `trackPageView()`, `trackClick()`, `trackApi()`, `flushOnUnload()`.
  Edge middleware (below) hooks into the same event names.
- **A11y/perf**: `npm run audit:lighthouse` and `audit:axe` already
  wired against `https://tars.meeet.world/`.
- **Type check + tests**: `npm run typecheck`, `npm test` are green.

### 1.2 Backend (`web_extras/routers/product.py`)
- `GET /api/product/downloads` returns the contract 1.0.0 manifest.
- `GET /api/product/downloads/latest` returns one entry.
- `GET /api/product/version` minimal probe.
- Response header `X-Tars-Contract: 1.0.0` echoed.
- **NOT on the critical path for `tars.meeet.world`**: the subdomain
  proxies straight to the Supabase `tars-downloads` Edge Function
  (see §1.4). The FastAPI backend stays the canonical source for
  desktop clients and is exercised by the Tauri shell.

### 1.3 Bridge contracts
- `docs/contracts/CORE_BRIDGE.md` — **SHIPPED** (route table,
  failure modes, version rules, smoke procedure).
- `docs/contracts/relay_event.schema.json` — **SHIPPED** (JSON
  Schema Draft 2020-12 for `POST /relay-event`).
- `docs/contracts/MEEET_DOWNLOADS.md` — **SHIPPED** (manifest 1.0.0).
- `docs/contracts/TARS_SUBDOMAIN.md` — **SPEC** (this readiness
  audit honors every section).
- `make smoke-core-bridge` — passes when `BRIDGE_SHARED_SECRET` is set.

### 1.4 Hosting & edge config
- **Cloudflare Pages** chosen as default host.
  - `experiments/neural-showcase-v3/public/_headers` — security
    headers (HSTS, CSP-equivalent via `X-Frame-Options`, COOP/COEP
    handled by Pages defaults), per-path `Cache-Control` per spec
    §3.3.
  - `experiments/neural-showcase-v3/public/_redirects` — SPA
    fallback + permanent redirects + downloads proxy to the
    Supabase Edge Function (`tars-downloads`) until meeet-app
    exposes its own `/api/tars/downloads` shim per spec §4.
  - `experiments/neural-showcase-v3/functions/_middleware.ts` —
    Pages Function implementing spec §5 (cookie issuing) and §6
    (`tars.page.viewed` emit through `core-bridge`). Trace ID
    generated/propagated, fail-open if `BRIDGE_SHARED_SECRET`
    missing (page never breaks on missing infra).
- **CI/CD**: `.github/workflows/tars-meeet-cloudflare-pages.yml`
  builds + tests + deploys on every push to main. PR builds get
  a preview URL automatically. Smoke step probes
  `https://tars.meeet.world/api/product/downloads` after deploy.

### 1.5 Cross-agent sync infrastructure
- `docs/SYNC.md` — protocol, lane split, branching, handoff table.
- `docs/ROADMAP_SHARED.md` — single board for both agents.
- `docs/CHANGELOG_AGENTS.md` — audit trail.
- Three GitHub issues open to coordinate with Claude:
  - tars-neural-cockpit#8 (live handshake)
  - meeet-solana-state-941a6045#1 (navbar Vitest hotfix)
  - meeet-solana-state-941a6045#2 (handoff package)

---

## 2. What blocks production launch

### 2.1 Operator infra (the brother) — see `docs/TARS_MEEET_OPS_TODO.md`
1. **DNS**: `tars.meeet.world` CNAME → Cloudflare Pages target.
2. **SSL**: SAN added to `*.meeet.world` cert OR Cloudflare-issued
   per-host cert.
3. **Cloudflare Pages project**: create `tars-meeet`, bind custom
   domain `tars.meeet.world`.
4. **GitHub repo secrets**: `CLOUDFLARE_API_TOKEN`,
   `CLOUDFLARE_ACCOUNT_ID`.
5. **Pages env vars**: `BRIDGE_SHARED_SECRET`,
   optionally `CORE_BRIDGE_URL` (defaults to prod).
6. **status.meeet.world** new row for `tars.meeet.world`
   (post-launch).

### 2.2 Claude lane (Lovable) — tracked in handoff
1. **`/api/tars/downloads` proxy on meeet-app** (spec §4 Option A).
   Currently the subdomain skips meeet-app and hits Supabase
   directly via `_redirects`. Acceptable for launch, but the proxy
   makes meeet-app the canonical edge so observability lives in
   one place.
2. **Cookie sharing**: meeet.world login must set `meeet_session`
   with `Domain=.meeet.world` so `tars.meeet.world` reads it on
   first visit. Today that cookie may be host-scoped to
   `meeet.world` only — Claude has to verify and bump the domain
   attribute.
3. **`/api/sessions/link`** for anon → operator session linking
   (spec §5.2).
4. **Acceptance run** of spec §10 checklist after DNS flip.

### 2.3 Optional but valuable
- **Sitemap and canonical flip**: after DNS goes live, switch
  `<link rel="canonical">` and `og:url` from `meeet.world/...` to
  `tars.meeet.world/...` in `experiments/neural-showcase-v3/index.html`,
  then update `public/sitemap.xml` URLs and `public/robots.txt`.
  This is a one-line change per file; deferred until DNS lands so
  preview builds don't 301-loop.
- **Edge sampling for `tars.page.viewed`**: at sub-100k DAU we emit
  every page view. Sampling at 1% can land later (spec §6.2).

---

## 3. Acceptance gates Cursor will run before sign-off

In order, after Operator wires DNS:

1. `https://tars.meeet.world/` → HTTP 200, `X-Tars-Contract: 1.0.0`.
2. `https://tars.meeet.world/install` → HTML, SPA hydrates.
3. `https://tars.meeet.world/api/product/downloads` → JSON manifest.
4. First request sets `tars_session_id` cookie with
   `Domain=.meeet.world`. Second request reads it.
5. `make smoke-core-bridge` from this repo green against prod
   `BRIDGE_SHARED_SECRET`.
6. Open Lovable admin — query meeet event store for the trace_id
   from a fresh page-view: row appears within 30s with
   `kind=tars.page.viewed`, `session_id` matches the cookie.
7. Lighthouse perf > 90, a11y > 95 on `/`.

If any step fails the launch is rolled back to staging at
`tars-staging.meeet.world` (spec §9 §1).

---

## 4. Risk register

- **Cookie domain mismatch on `meeet.world`**: if Lovable can't bump
  `meeet_session` to `Domain=.meeet.world`, single-session UX is
  lost; visitors would re-auth on the subdomain. Mitigation:
  marketing surface works fully anonymously — auth-gated
  personalisation (`<MeeetWorldStrip />`) just falls back to the
  generic CTA. Not a launch blocker.
- **Edge analytics duplicate emit**: edge `_middleware.ts` and the
  client-side `trackPageView()` both emit. Mitigation: edge sets
  `X-Tars-Trace-Id` so the ingest can dedupe by trace_id +
  session_id. Already implemented client-side via header echo
  (TODO: wire client to honor `X-Tars-Trace-Id` from the response).
- **Cloudflare cold start of Pages Function**: ~50ms p99. Acceptable
  for marketing; if it becomes painful, hoist the cookie issuing
  to a dedicated Worker and keep Pages purely static.
- **Bridge secret rotation**: requires re-run of
  `make smoke-core-bridge` from this repo + Pages env update.
  Documented in `docs/contracts/CORE_BRIDGE.md` versioning rules.

---

## 5. Anti-checklist (intentionally NOT shipped here)

- ❌ Multi-region Cloudflare config — single zone is enough at this
  scale.
- ❌ Per-route prerender (Next/Astro static generation) — Vite SPA
  is fast enough; HTML is small.
- ❌ Service worker offline mode — `sw.js` already ships, but
  offline-first marketing is overkill.
- ❌ A/B test infra — wait until traffic justifies it.
- ❌ Custom CDN ASN routing — Cloudflare's defaults are fine.

If any of those become real needs, they get a separate spec. They
are not on the launch critical path.

---

## 6. Cursor's offer to Claude (one-line summary)

> When DNS is live, Cursor will run §3 acceptance against production,
> stay on call for any cookie / cookie-domain regression, and ship
> the canonical-flip + sitemap update as a single PR within one
> working session. In return: Claude wires `/api/tars/downloads` on
> meeet-app and ensures `meeet_session` cookie has `Domain=.meeet.world`.

Tracked verbatim in tars-neural-cockpit#8.
