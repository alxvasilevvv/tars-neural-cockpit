# Contract — `tars.meeet.world` subdomain + e2e logging

> **Status:** SPEC ONLY.
> **Owner of execution:** meeet.world infra team (the brother).
> **Owner of spec:** Claude (frontend + design).
> **Authoritative wire shapes:**
>   - downloads manifest → `docs/contracts/MEEET_DOWNLOADS.md`
>   - meeet event store contract → `1.1.0` (see
>     `tests/test_meeet_contract_v11.py`)

This document describes how to mount `tars.meeet.world` so the
TARS marketing surface lives at a meeet-branded subdomain with full
end-to-end logging into the existing meeet.world account / event
store. **No code is shipped here** — the brother imports this spec
into the meeet-app repo and wires it.

---

## 1. Goals

1. **Same brand, separate surface.** `meeet.world` keeps its
   landing-page job; `tars.meeet.world` carries the TARS-specific
   marketing + install funnel. Operators can deep-link both ways
   (account ↔ tars).
2. **Single account, single observability.** A logged-in
   meeet.world operator who lands on `tars.meeet.world` has their
   `session_id` propagate. Every action — page view, install
   click, download, sign-up — lands in the same meeet event store
   as `kind=tars.<sub>`.
3. **No silent contract drift.** The downloads manifest + meeet
   event payloads stay pinned to existing contract versions. Any
   bump goes through a coordinated PR (Cursor side).

---

## 2. DNS + SSL

```
tars.meeet.world.    CNAME   meeet-app.<your-host>.   ; or A → load balancer IP
```

SSL: extend the existing `*.meeet.world` wildcard certificate
(Let's Encrypt or your certificate authority) to include
`tars.meeet.world` automatically. If you currently issue per-host,
add a SAN for `tars.meeet.world`.

**Verification:**
```
curl -sI https://tars.meeet.world/ | head -1
# → HTTP/2 200 (or 301 to canonical https path)
```

---

## 3. Routing

### 3.1 Origin selection

Two viable shapes, pick the one that matches your existing
meeet-app deployment:

**Option A — vhost on the existing meeet-app**
```
meeet-app router:
  meeet.world/*               → existing handler
  tars.meeet.world/*          → new handler (tars-handler)
  app.meeet.world/*           → existing app handler
```
Add `tars.meeet.world` to the same TLS listener; no new origin.

**Option B — separate Cloudflare worker / Vercel project**
```
tars.meeet.world  →  vercel project "meeet-tars"
                  →  cloudflare worker "tars-edge"
```
Useful if the marketing build cadence wants to differ from the main
app. Slightly more config to keep auth state shared (see § 5).

We recommend **Option A** unless build cadence forces B.

### 3.2 Path map

The `tars.meeet.world` handler should route as follows:

| Path | Behaviour |
|------|-----------|
| `GET /` | Serve the static marketing site (build artefact from `experiments/neural-showcase-v3/dist`). |
| `GET /assets/*` | Serve hashed bundle assets with `Cache-Control: public, max-age=31536000, immutable`. |
| `GET /install` | Serve the `/install` SPA route (same static index.html, client-side router). |
| `GET /pitch` | Same — static SPA route. |
| `GET /faq`, `/pricing`, `/compare`, `/cockpit` | Same. |
| `GET /install.sh` | 302 to the canonical S3 URL of the latest installer script (or proxy directly if you prefer single-origin). |
| `GET /api/product/downloads` | Proxy to `meeet-app:/api/tars/downloads` (see § 4). |
| `GET /api/product/version` | Same shape as `/downloads` but minimal. |
| `GET /auth/callback` | Hand off to the meeet-app standard OAuth callback; preserve the `tars_session_id` (see § 5). |
| `GET /privacy`, `/terms` | Render the markdown docs from `docs/PRIVACY_POLICY.md` and `docs/TERMS_OF_SERVICE.md`. |
| `GET /security` | Render `docs/SECURITY.md`. |
| `*` (404) | Static custom 404 with brand triad styling. |

### 3.3 Cache hints

- Marketing HTML: `Cache-Control: public, max-age=60, s-maxage=300,
  stale-while-revalidate=86400`. Short TTL because we ship the
  manifest version pill on the page.
- Manifest endpoint: `Cache-Control: public, max-age=60` (Cursor
  already sets this on origin).
- Static assets: `immutable`.

---

## 4. Downloads proxy (the only "API" on this subdomain)

The marketing site needs `/api/product/downloads` to render Hero
and Footer CTAs. Two options:

**Recommended: proxy through meeet-app.**
```
tars.meeet.world/api/product/downloads
  → tars-handler proxies to meeet-app/api/tars/downloads
  → meeet-app proxies to backend.meeet.world/api/product/downloads
  → returns the contract 1.0.0 manifest
```

This way the canonical source of truth stays on the TARS backend
service; meeet.world is just a routing edge.

**Fallback: bake the manifest into the build.**

If the meeet-app can't easily proxy to the backend, bake a static
copy of the manifest at build time and serve as
`/api/product/downloads`. Refresh nightly via cron + CI redeploy.
Loses freshness but works without any backend dep.

**Required headers:**
- `Cache-Control: public, max-age=60`
- `X-Tars-Contract: 1.0.0` (echo from origin)
- `Access-Control-Allow-Origin: https://meeet.world` (so meeet.world
  itself can render the same widget)

---

## 5. Auth & session linking

### 5.1 Single session across surfaces

When an operator is logged in to `meeet.world` and lands on
`tars.meeet.world`, the same session cookie should authenticate
them. Mechanism:

- **Cookie domain** = `.meeet.world` (shared parent), `httpOnly`,
  `Secure`, `SameSite=Lax`.
- **Cookie name** = `meeet_session` (existing).

The marketing site uses this cookie only to render
"Welcome, operator" personalisation (e.g. show wallet balance in
`<MeeetWorldStrip />`). It doesn't need to write the cookie.

### 5.2 New session on first visit

If an unauthenticated visitor lands on `tars.meeet.world`:

1. Edge issues a **`tars_session_id`** in a `Set-Cookie` header (UUID4,
   `Domain=.meeet.world`, 30 day TTL, httpOnly, Secure, Lax).
2. This `tars_session_id` is independent of `meeet_session`. It
   tracks a **visitor**, not an authenticated operator.

If they later log in, link the two:

```
POST meeet-app/api/sessions/link
  Body: { "anonymous_id": "<tars_session_id>", "operator_id": "<from auth>" }
```

### 5.3 Logout

Standard meeet logout clears `meeet_session` across all subdomains
(cookie domain `.meeet.world`). The `tars_session_id` keeps
tracking the visitor anonymously until cookie expiry.

---

## 6. End-to-end logging contract

### 6.1 What to log

Every HTTP request to `tars.meeet.world` emits a meeet event:

```jsonc
{
  "kind": "tars.<page|api|click>.<action>",   // e.g. tars.page.viewed
  "trace_id": "<uuid4 from x-trace-id header or generated>",
  "session_id": "<tars_session_id cookie>",
  "operator_id": "<meeet_session if authenticated, else null>",
  "ts": <epoch seconds>,
  "payload": {
    "path": "/install",
    "referer": "https://meeet.world/",
    "ua": "<truncated user-agent>",
    "country": "<from CDN headers>",
    "source": "tars_subdomain"
  }
}
```

### 6.2 Event kinds to emit

- `tars.page.viewed` — every HTML page load (sample at edge or full).
- `tars.api.downloads.fetched` — every `/api/product/downloads` hit.
- `tars.click.cta` — when the marketing site fires the `track('cta',
  {...})` beacon (cockpit can wire this on Hero CTAs).
- `tars.install.script.fetched` — every `/install.sh` hit (single
  most important conversion event).
- `tars.auth.signup` — operator signed up via the subdomain
  funnel.

Sample at edge if volumes are high; sub-1% sampling is fine for
`tars.page.viewed` once we have ~100k DAU. Other events stay full.

### 6.3 How to ingest

The meeet event store is the canonical sink. Two paths:

**Path A — direct.** The edge handler POSTs to
`meeet-app/api/events/ingest` with the event row. meeet-app has
existing rate-limit + auth.

**Path B — Cloudflare Logpush / Vercel Analytics → ingestor.**
Cheaper at scale. Requires a small ingestor service that maps
log lines to event rows.

We recommend Path A initially; switch to Path B when traffic
makes A's per-event RTT noticeable.

### 6.4 Trace propagation

Outgoing requests from `tars.meeet.world` to other meeet services
should propagate the `x-trace-id` header. If the visitor is also
authenticated, `x-tars-session-id` and `x-meeet-session-id` ride
along. This way one operator = one trace tree spanning the
marketing visit, the install, the OAuth signup, and the first
cockpit action.

Sample propagation:
```
GET tars.meeet.world/api/product/downloads
  ↓
  x-trace-id: <generated or echoed>
  x-tars-session-id: <cookie>
  x-meeet-session-id: <cookie if logged in>
  ↓
meeet-app:/api/tars/downloads (forwards headers)
  ↓
backend.meeet.world:/api/product/downloads (forwards)
```

Every hop logs `tars.api.downloads.fetched` with the same
`trace_id` — replay → operator-level reconstruction of the entire
funnel.

---

## 7. Open Graph & SEO

The marketing site already ships:
- `<title>TARS — Neural Cockpit · meeet.world</title>`
- `<link rel="canonical" href="https://meeet.world/" />`
- `og:url`, `og:title`, `og:image` to `meeet.world/og.svg`
- Twitter card meta

If `tars.meeet.world` becomes the canonical, **flip the canonical
to `https://tars.meeet.world/`** in `index.html` and update
`og:url` accordingly. Coordinate with the marketing team to avoid
indexing both as separate canonicals.

`robots.txt`: allow all on `tars.meeet.world`. Sitemap at
`tars.meeet.world/sitemap.xml` listing the SPA routes.

---

## 8. Observability

For you (infra) to operate this:

| Metric | Target | Where |
|--------|--------|-------|
| `tars.meeet.world` p99 latency | < 200 ms (cached HTML) | Cloudflare/Vercel |
| Downloads manifest p99 | < 300 ms | meeet-app |
| Install conversion (page view → `install.sh` fetch) | track in meeet | meeet-app /admin |
| 5xx rate | < 0.1% / month | per usual |

Status page at `status.meeet.world` adds a `tars.meeet.world` row.

---

## 9. Rollout

1. **Stage:** `tars-staging.meeet.world` for 7 days.
   Smoke: end-to-end install flow succeeds on macOS arm64;
   the trace_id from a marketing visit is queryable in meeet-app
   admin UI.
2. **Production:** flip DNS to `tars.meeet.world`; keep staging
   running for 30 days as fallback.
3. **Communication:** banner on `meeet.world/`: "TARS marketing
   moved → tars.meeet.world". 30-day grace before removing.

---

## 10. Acceptance checklist

- [ ] DNS resolves; SSL valid; HTTP/2 200 on `/`.
- [ ] Marketing SPA routes work (`/`, `/install`, `/pricing`, `/faq`,
      `/compare`, `/onboarding`, `/cockpit`).
- [ ] `/api/product/downloads` returns contract 1.0.0 with
      `X-Tars-Contract: 1.0.0` header.
- [ ] `meeet_session` cookie shared with `meeet.world` — login on
      one surface authenticates the other.
- [ ] `tars_session_id` cookie issued on first anon visit.
- [ ] Each page view emits `tars.page.viewed` event with
      session_id + operator_id (if logged in) into meeet event
      store.
- [ ] `trace_id` propagates host→hop and is queryable in meeet
      admin within 30s of the request.
- [ ] Status page row green for 7 consecutive days before
      flipping DNS to production.

---

## 11. Cross-references

- `docs/contracts/MEEET_DOWNLOADS.md` — wire shape for the manifest.
- `docs/contracts/L5_PAIRING_DRAFT.md` — pairing/sync (orthogonal,
  not on the marketing subdomain).
- `docs/SECURITY.md` § 9 — network surface (no inbound LAN; this
  subdomain is the only public face).
- `docs/PRIVACY_POLICY.md` § 3 — sub-processor list (Cloudflare,
  Stripe).

---

*Pin this file: `docs/contracts/TARS_SUBDOMAIN.md`.
Once executed, mark the related entry in `AGENT_HANDOFF.md`
(P4 in `docs/PRODUCT_PHASE_M.md`) as ✅.*
