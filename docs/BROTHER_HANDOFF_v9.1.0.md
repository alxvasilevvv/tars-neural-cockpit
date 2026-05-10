# Brother handoff — TARS v9.1.0 + v9.1.1

> **Audience:** the meeet.world brother backend team (Lovable + Supabase
> Edge Functions side).
> **From:** Operator + Claude (TARS-side agent).
> **Date:** 2026-05-09 (Wave 78).
> **Reads with:** [`docs/INTEGRATION_FOR_BROTHER.md`](INTEGRATION_FOR_BROTHER.md),
> [`docs/TARS_MEEET_OPS_TODO.md`](TARS_MEEET_OPS_TODO.md),
> [`docs/contracts/CORE_BRIDGE.md`](contracts/CORE_BRIDGE.md),
> [`docs/contracts/L5_PAIRING_DRAFT.md`](contracts/L5_PAIRING_DRAFT.md),
> [`docs/contracts/WAITLIST.md`](contracts/WAITLIST.md),
> [`docs/RELEASE_NOTES_v9.1.0.md`](RELEASE_NOTES_v9.1.0.md),
> [`docs/ROADMAP.md`](ROADMAP.md).

This is **the** single document for the brother side at v9.1.0 launch and
the v9.1.1 follow-up (magic-link auth). Everything below is either DONE
on the operator side (no action) or a numbered required action with a
verification command.

---

## 1. v9.1.0 launch readiness — operator side (DONE)

These are closed; listed so brother knows not to re-do them.

| # | Item | Status | Evidence |
|---|------|--------|----------|
| 1.1 | **B-019 custom domain swap** — `tars.meeet.world` re-bound from legacy `tars-meeet` project to `tars-meeet-git` (auto-built from `main`). | done | `curl -s https://tars.meeet.world/api/product/version | jq .version` → `9.1.0` |
| 1.2 | **CF Pages deploy** — `tars-meeet-git` Cloudflare Pages project live, Git integration auto-builds on every push to `main`. Build cmd: `npm ci && npm run build:cf`, output `dist`, root `experiments/neural-showcase-v3`. | done | Cloudflare → Workers & Pages → `tars-meeet-git` → green deployments |
| 1.3 | **Marketing surface honesty pass** (Wave 71-A + 71-B + Wave 67) — Mac-only download badge, "Coming soon" gated until signed installers are ready, no overpromises on Windows / Linux / wake-word / Slack / Marketplace. Every shipping URL resolves; every claimed feature has a code path. | done | [`docs/WHAT_WORKS.md`](WHAT_WORKS.md) reflects PARTIAL / NOT-IMPLEMENTED honestly |
| 1.4 | **Pages SPA HTTP status fix** — `dist/index.html → 404.html` copy removed from CI; `_redirects` (`/* → /index.html 200`) handles SPA routing. | done | `curl -sI https://tars.meeet.world/install` → `HTTP/2 200` |
| 1.5 | **Same-origin Pages Functions** for `/api/product/{downloads,version,client-error}` and `/dl/<file>` proxy. | done | `experiments/neural-showcase-v3/functions/` |
| 1.6 | **`tars_session_id` cookie** scoped to `.meeet.world`, full HSTS / NEL / permissions-policy / X-Frame-Options stack. | done | DevTools → Application → Cookies on `tars.meeet.world` |
| 1.7 | **v9.1.0 release notes + ROADMAP + CHANGELOG** synced and cross-linked. | done | [`docs/RELEASE_NOTES_v9.1.0.md`](RELEASE_NOTES_v9.1.0.md) |

---

## 2. v9.1.0 launch readiness — brother side (REQUIRED)

**Each item blocks a specific TARS feature.** WHAT / WHY / WHERE / HOW
format. If you can only do one thing, do **2.a** — it is the single
biggest unblock.

### 2.a — `BRIDGE_SHARED_SECRET` env var on Cloudflare Pages

- **WHAT.** Add encrypted env var `BRIDGE_SHARED_SECRET` on the
  Cloudflare Pages project **`tars-meeet-git`**, **Production**
  environment. Value = the same string you already configured as
  `BRIDGE_SHARED_SECRET` on the `core-bridge` Supabase Edge Function
  (project `zujrmifaabkletgnpoyw`).
- **WHY.** Without this:
  - `/api/client-error` reports from the browser short-circuit with
    `bridge_unconfigured` and **drop to /dev/null** — we lose every
    client-side exception report.
  - The synthetic monitor `core-bridge /health` probe stays **red**
    (the auth header is missing on the outbound call from the Pages
    Function).
  - The QA agent reports 3 SKIPs + 1 WARN that should all flip to
    PASS once the secret lands.
- **WHERE.** Cloudflare dashboard → **Workers & Pages** →
  **`tars-meeet-git`** → **Settings** → **Environment variables** →
  **Production** → **Add variable**.
- **HOW (step-by-step).**
  1. Open Cloudflare → Workers & Pages → `tars-meeet-git`.
  2. Settings → Environment variables → Production → **Add**.
  3. Variable name: `BRIDGE_SHARED_SECRET`.
  4. Value: paste the same string already set on `core-bridge`.
  5. Type: **Encrypt** (NOT plain text).
  6. Save.
  7. Trigger a fresh deploy (push an empty commit to `main` or
     **Retry deployment** in the dashboard) — Pages env vars only
     attach to *new* deployments.
  8. Verify with the operator from TARS repo:
     ```bash
     BRIDGE_SHARED_SECRET="<the same secret>" make smoke-core-bridge
     ```
     Expected: every assertion green, e2e relay event lands with
     `persisted: true`.

### 2.b — Confirm `core-bridge` Edge Function is public + healthy

- **WHAT.** Confirm the `core-bridge` Edge Function on Supabase
  project `zujrmifaabkletgnpoyw` is publicly reachable, accepts
  `GET /health`, and accepts `POST /contracts/L5/pair` (relay route
  for the L5 pairing fallback when the LAN handshake fails).
- **WHY.** TARS desktop pairing falls back to
  `https://meeet.world/pair/<pair_id>` when LAN is unreachable
  (see [`docs/contracts/L5_PAIRING_DRAFT.md`](contracts/L5_PAIRING_DRAFT.md)
  § 3.1 + § 4 fallback). Without the relay route working, paired
  devices off-LAN cannot complete the X25519 handshake and the
  fallback path silently fails.
- **WHERE.** Supabase dashboard → project `zujrmifaabkletgnpoyw` →
  Edge Functions → `core-bridge`.
- **HOW.**
  1. Confirm function status is **Active** (not paused).
  2. Run from anywhere with the secret:
     ```bash
     curl -s -H "x-bridge-secret: $BRIDGE_SHARED_SECRET" \
              -H "Origin: https://tars.meeet.world" \
              https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/core-bridge/health
     # expect: 200 OK + JSON body
     ```
  3. Confirm `POST /contracts/L5/pair` accepts an opaque encrypted
     blob body (the bridge **never** sees plaintext — see contract
     § 4). Today the route can be a stub that 200s; the wire shape
     is finalised in v9.1.1 alongside JWKS.
  4. If `core-bridge` is private (Supabase verify-JWT enabled),
     **disable verify-JWT** for this function — the bridge does its
     own auth via `x-bridge-secret` (constant-time compare).

### 2.c — Confirm `meeet_session` cookie domain is `.meeet.world` (with leading dot)

- **WHAT.** The session cookie issued by `meeet.world` after login
  must have `Domain=.meeet.world` (with the leading dot), not
  `Domain=meeet.world`.
- **WHY.** Without the leading dot, the cookie is bound to
  `meeet.world` only and is **NOT sent** to subdomains like
  `tars.meeet.world`. The TARS cockpit cannot read the session →
  every visitor lands on the marketing surface as anonymous, and
  magic-link onboarding (v9.1.1) breaks completely.
- **WHERE.** Wherever Lovable / your auth code sets `Set-Cookie`
  for `meeet_session` (Edge Function or app middleware).
- **HOW.**
  1. Inspect the current `Set-Cookie` header:
     ```bash
     curl -sI https://meeet.world/ | grep -i 'set-cookie'
     ```
  2. If `Domain=meeet.world` (no leading dot), update the cookie
     options to `Domain=.meeet.world; HttpOnly; Secure; SameSite=Lax`.
  3. Verify in DevTools → Application → Cookies on
     `https://tars.meeet.world/` — the `meeet_session` cookie should
     appear with `Domain` column showing `.meeet.world`.

### 2.d — Confirm DNS for `tars.meeet.world` is CF-proxied (orange cloud)

- **WHAT.** The DNS record `tars.meeet.world` must be **proxied**
  through Cloudflare (orange cloud icon), not DNS-only (grey cloud).
- **WHY.** Without the proxy:
  - Cloudflare cannot do SSL termination → SSL cert fails to
    provision → users get a browser warning.
  - HSTS / WAF / DDoS protection is bypassed.
  - The `_headers` and `_redirects` Pages config is also bypassed.
- **WHERE.** Cloudflare dashboard → Websites → `meeet.world` →
  **DNS** → **Records**.
- **HOW.**
  1. Find the `CNAME` record for `tars` → `tars-meeet-git.pages.dev`
     (or whatever the auto-assigned `*.pages.dev` host is).
  2. Click the cloud icon in the **Proxy status** column → set to
     **Proxied** (orange).
  3. Verify:
     ```bash
     curl -sI https://tars.meeet.world/ | head -5
     # expect: HTTP/2 200 + 'server: cloudflare' header
     ```

---

## 3. v9.1.1 magic-link auth (brother's main blocker, ~2 weeks out)

This is the single biggest blocker for v9.1.1. The TARS onboarding wizard
already renders the magic-link UI; today it's UI-only because the
backend endpoints don't exist. Below is the **exact API contract** the
TARS desktop + cockpit expects.

### 3.1 — Endpoints

#### `POST /auth/magic-link/request`

Mounted at `https://meeet.world/auth/magic-link/request`.

Request:
```http
POST /auth/magic-link/request HTTP/2
Host: meeet.world
Content-Type: application/json

{
  "email": "operator@example.com",
  "return_url": "tars://login"
}
```

Response (202 Accepted):
```json
{
  "message_id": "ml_01HX9P2K8QF3M0VVB3J7E5RTHB",
  "expires_at": 1747680000
}
```

Notes:
- `return_url` is the deep link TARS desktop wants to bounce back to
  after the click-through. Must be allowlisted server-side
  (`tars://login`, `https://tars.meeet.world/login`).
- `expires_at` is Unix seconds, UTC. Default lifetime: **15 minutes**.
- Rate limit: `5/min/IP`, `1/min/email`.
- Response status: `202` on success, `422` on `invalid_email`,
  `429` on `rate_limit`.

#### `GET /auth/magic-link/verify?token=...`

Request:
```http
GET /auth/magic-link/verify?token=ml_tok_<opaque>&message_id=<id> HTTP/2
Host: meeet.world
```

Response: `302 Found` redirect to `<return_url>?meeet_session=<JWT>`,
plus `Set-Cookie: meeet_session=<JWT>; Domain=.meeet.world; Path=/;
HttpOnly; Secure; SameSite=Lax; Max-Age=2592000`.

If the `return_url` scheme is `tars://`, return the `<JWT>` directly
in the redirect URL fragment so the desktop deep-link handler can
parse it (`tars://login#meeet_session=<JWT>`).

Failure: `400 invalid_token`, `410 token_expired`, `410 token_consumed`.

### 3.2 — Cookie format (`meeet_session`)

```
Set-Cookie: meeet_session=<JWT>; Domain=.meeet.world; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=2592000
```

- `Domain=.meeet.world` — leading dot REQUIRED (see § 2.c).
- `HttpOnly` — JS cannot read it; only server-side / Pages Functions.
- `Secure` — HTTPS only.
- `SameSite=Lax` — sent on top-level navigation (the redirect).
- `Max-Age=2592000` — 30 days. Refresh on each verified API call.

### 3.3 — JWT claims

Standard JWT, signed with **EdDSA (Ed25519)** or **RS256**:

```jsonc
{
  "sub":  "user_01HX9P2K8QF3M0VVB3J7E5RTHB",   // user_id, opaque
  "iss":  "meeet.world",
  "aud":  "tars",
  "iat":  1747679100,
  "exp":  1750271100,                          // sub + 30 days
  "tier": "pro",                               // optional: free|pro|business|lifetime
  "email_verified": true                       // optional but expected
}
```

Required: `sub`, `iss`, `iss=meeet.world`, `aud=tars`, `iat`, `exp`.
Optional: `tier`, `email_verified`. TARS reads `tier` to gate
entitlements and falls back to `free` if absent.

### 3.4 — JWKS endpoint

Brother MUST publish the JWT signing public key at:

```
https://meeet.world/.well-known/jwks.json
```

Standard JWKS format:
```json
{
  "keys": [
    {
      "kty": "OKP",
      "crv": "Ed25519",
      "kid": "meeet-2026-05",
      "x":   "<base64url-encoded public key>",
      "use": "sig",
      "alg": "EdDSA"
    }
  ]
}
```

TARS desktop + Pages Functions fetch this once per hour (cached via
`Cache-Control` header you should set: `public, max-age=3600`). On
key rotation, increment `kid` and serve **both old and new** for at
least one rotation period (24 h) so in-flight tokens stay valid.

### 3.5 — Estimated effort

- **2–3 days** backend implementation (endpoints + JWT mint + JWKS).
- **1 day** testing (smoke + e2e from TARS side via
  `make smoke-magic-link` — script will be added in TARS repo on the
  same day brother lands the endpoints).

---

## 4. v9.2 wishlist (1 month out, NOT blocking v9.1.0 / v9.1.1)

Forward-looking; brother can spec these in parallel but no rush:

| Item | Owner | Reference |
|------|-------|-----------|
| **Marketplace REST API** — registry / browse / ratings (GET `/marketplace/skills`, GET `/marketplace/skills/<id>`, POST `/marketplace/skills/<id>/rate`, GET `/marketplace/skills/<id>/reviews`). | brother backend | [`docs/ROADMAP.md`](ROADMAP.md) v9.2 row |
| **T2T escrow contracts** — Solana program for TARS-to-TARS counterparty escrow. Mock today; live deployment + program-id publish needed. | brother + Solana ops | [`docs/ROADMAP.md`](ROADMAP.md) v9.3+ row |
| **Receipt-ledger anchoring service** — batch Merkle-root anchoring of TARS receipts into Solana memo (Wave 89 shipped client side; needs server-side batcher). | brother backend | [`docs/contracts/RECEIPT_LEDGER.md`](contracts/RECEIPT_LEDGER.md) |

---

## 5. Contract version table

| Contract | Current | Next | Trigger |
|----------|---------|------|---------|
| **`meeet` event contract** (used by `core-bridge` relay + L5 pairing envelope) | **1.1.0** | **1.2.0** | Adds magic-link verification fields + JWKS reference (v9.1.1). |
| **`core-bridge`** (cross-project bridge, `relay-event` schema) | **1.0.0** | **1.1.0** | Bumps when magic-link emits land. |
| **L5 pairing payload** (`v` field in QR envelope) | **1** | **1** (no change) | Stable; no change planned in v9.1.1. |
| **MEEET_DOWNLOADS** (download manifest) | **1.0.0** | **1.0.0** (no change) | Stable. |
| **WAITLIST** | draft 1.0 | draft 1.0 (no change) | Stable. |

Bump rules — see [`docs/contracts/CORE_BRIDGE.md`](contracts/CORE_BRIDGE.md)
§ "Versioning rules": additive change = no bump, document only;
breaking change = bump + paired PRs same day.

---

## 6. Communication channels

- **Sync repo (TARS side):** `alxvasilevvv/tars-neural-cockpit`
  (this repo). Brother has read access; PRs welcomed via fork.
- **Brother's repo (meeet.world side):** linked from
  [`docs/INTEGRATION_FOR_BROTHER.md`](INTEGRATION_FOR_BROTHER.md).
  Two-way sync via `>>> SYNC: ...` markers in commit bodies (see
  below).
- **Async issue tracker:** `tars-neural-cockpit#8` — the long-running
  meta-issue for cross-side work. Leave one-line updates per
  unblocked item.
- **TARS sync markers:** every commit on either side that affects
  the other side appends a `>>> SYNC: <author> · <date> · <one-line
  summary>` line in the commit body. Both agents grep for these so
  nothing is invisible.
- **Secrets:** never in GitHub / email / Telegram. Use Signal,
  1Password sharing, or encrypted Apple Notes shared. See
  [`docs/templates/BROTHER_HANDOFF_MESSAGE.md`](templates/BROTHER_HANDOFF_MESSAGE.md)
  § "Что НЕ говорить брату".

---

## Quick-reference card (paste this into your task tracker)

```
TARS v9.1.0 + v9.1.1 — brother backlog (Wave 78)
[ ] 1. Set BRIDGE_SHARED_SECRET on CF Pages tars-meeet-git Production env  (unblocks /api/client-error + monitor)
[ ] 2. Confirm core-bridge /health public + accepting POST /contracts/L5/pair  (unblocks L5 pairing relay fallback)
[ ] 3. Set meeet_session cookie Domain=.meeet.world  (with leading dot — unblocks subdomain auth)
[ ] 4. v9.1.1: implement /auth/magic-link/{request,verify} + JWT mint + /.well-known/jwks.json  (~3 days)
[ ] 5. Ping operator on tars-neural-cockpit#8 when done — operator runs `make smoke-core-bridge` + `make smoke-magic-link`
```

>>> SYNC: Claude · 2026-05-09 · Wave 78 brother handoff.
