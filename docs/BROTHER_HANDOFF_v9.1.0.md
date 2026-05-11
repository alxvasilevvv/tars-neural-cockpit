# Brother handoff — TARS v9.1.0 + v9.1.1

> **Audience:** the meeet.world brother backend team (Andrey, core-bridge
> backend on Lovable + Supabase Edge Functions side).
> **From:** Operator + Claude (TARS-side agent).
> **Date:** 2026-05-09 (Wave 78), **last sync 2026-05-11 (Wave 119 — added
> Waves 90-118 contract sections §§ 7-16, integration milestones § 17,
> quickstart § 18).**
> **Reads with:** [`docs/INTEGRATION_FOR_BROTHER.md`](INTEGRATION_FOR_BROTHER.md),
> [`docs/TARS_MEEET_OPS_TODO.md`](TARS_MEEET_OPS_TODO.md),
> [`docs/contracts/CORE_BRIDGE.md`](contracts/CORE_BRIDGE.md),
> [`docs/contracts/L5_PAIRING_DRAFT.md`](contracts/L5_PAIRING_DRAFT.md),
> [`docs/contracts/WAITLIST.md`](contracts/WAITLIST.md),
> [`docs/contracts/WEBHOOKS.md`](contracts/WEBHOOKS.md),
> [`docs/contracts/RECEIPTS.md`](contracts/RECEIPTS.md),
> [`docs/contracts/COHORT.md`](contracts/COHORT.md),
> [`docs/contracts/SCHEDULER.md`](contracts/SCHEDULER.md),
> [`docs/contracts/OUTREACH.md`](contracts/OUTREACH.md),
> [`docs/contracts/MARKETPLACE.md`](contracts/MARKETPLACE.md),
> [`docs/contracts/WORKSPACES.md`](contracts/WORKSPACES.md),
> [`docs/contracts/COMPLIANCE_EXPORT.md`](contracts/COMPLIANCE_EXPORT.md),
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

---

# Wave 119 addendum — new contracts shipped Waves 90-118 (2026-05-11)

Everything below was added between Wave 78 (2026-05-09) and v9.1.0 soft
launch (2026-05-11). All contracts are **v1.0** unless noted. Brother
does not need to do anything immediately — the contracts below describe
what is **available to integrate** when meeet.world wants to mirror,
react to, or aggregate TARS state.

For each section: **what shipped on TARS side**, **what brother could
integrate**, **link to source-of-truth contract**.

---

## 7. Webhooks subsystem (Wave 90) — contract v1.0

Source-of-truth: [`docs/contracts/WEBHOOKS.md`](contracts/WEBHOOKS.md).

Two-way webhook surface. Both directions are opt-in via env flags
(`TARS_WEBHOOKS_STORE`, `TARS_WEBHOOKS_ENABLED`).

### 7.1 Outgoing — TARS → brother

- HMAC-SHA256 signed POST to brother-registered URLs.
- Signature header: `X-TARS-Signature: t=<unix-seconds>,v1=<hex>`.
  HMAC body = `f"{t}.{request_body_bytes}"`, key = per-subscription
  `secret`.
- Retry policy: **30s / 2m / 10m / 1h, max 4 attempts** (then dead-letter).
- Body envelope:
  ```jsonc
  {
    "id":          "evt_<24 hex>",
    "type":        "playbook.started",         // dotted lowercase
    "occurred_at": "2026-05-11T10:00:00Z",     // ISO-8601 UTC
    "data":        { ... }                     // event-specific
  }
  ```

### 7.2 Incoming — brother → TARS

- Endpoint: `POST /api/webhooks/inbox/{token}`. The `token` is a
  URL-safe random 32-byte string brother registers via the cockpit
  ("Webhooks → Incoming → New").
- Optional shared secret: when `TARS_WEBHOOKS_INBOUND_SECRET` is set,
  TARS verifies HMAC on inbound bodies before triggering the bound
  playbook.

### 7.3 Standard event types brother might subscribe to

| Event type                        | Source                       |
|-----------------------------------|------------------------------|
| `playbook.started`                | autopilot / scheduler / inbox |
| `playbook.finished`               | autopilot                    |
| `playbook.failed`                 | autopilot                    |
| `hil.requested`                   | supervisor / policy_gate     |
| `hil.approved` / `hil.denied`     | HIL inbox                    |
| `agent.created` / `agent.deleted` | agents CRUD                  |
| `report.generated`                | reporting export             |
| `outreach.email_sent`             | outreach (Wave 98)           |
| `bundle.installed`                | vertical bundle generator    |
| `compliance.bundle_generated`     | compliance export (Wave 104) |
| `qa.alert`                        | synthetic monitor (Wave 117) |
| `receipt.created` *(opt-in)*      | receipts ledger (Wave 95)    |

### 7.4 Brother action

1. Stand up `POST /webhook/<topic>` receivers on core-bridge.
2. Generate a per-subscription secret, share it with operator out-of-band.
3. Operator registers via TARS cockpit → "Webhooks → Outgoing → Add"
   (or directly: `POST /api/webhooks/outgoing` with
   `{url, secret, events: ["playbook.finished", ...]}`).

---

## 8. Receipts ledger (Wave 95) — contract v1.0

Source-of-truth: [`docs/contracts/RECEIPTS.md`](contracts/RECEIPTS.md).

Hash-chained, **ed25519-signed** event stream at
`~/.tars/receipts/<YYYY-MM-DD>.ndjson`. Replaces the scattered receipt
emitters with a single tamper-evident trail. Daily Merkle root → Solana
memo anchor (env-gated `TARS_RECEIPT_ANCHOR_ENABLED=1`).

### 8.1 Brother integration paths

- **Verify a single receipt** — `POST /api/receipts/verify` with the
  receipt JSON; TARS recomputes hash + ed25519 sig and returns
  `{valid: true, chain_position: <n>, anchored: true|false}`.
- **Live mirror** — subscribe to outgoing webhook event
  `receipt.created` (opt-in; off by default to avoid flood) for a real-
  time stream into the meeet.world reputation graph.
- **Daily anchor proof** — once `TARS_RECEIPT_ANCHOR_ENABLED=1`, the
  daily Solana memo tx signature is exposed via
  `GET /api/receipts/anchor/{YYYY-MM-DD}` so brother can independently
  verify chain integrity.

---

## 9. Cohort backend (Wave 94) — contract v1.0

Source-of-truth: [`docs/contracts/COHORT.md`](contracts/COHORT.md).

Real attendee tracking for B2B workshops + cohort sessions.

- **Live metrics SSE** — `GET /api/cohort/{id}/stream` (Server-Sent
  Events) — pushes `cohort.attendee.joined`,
  `cohort.attendee.progress`, `cohort.checkpoint.passed` events.
- **Attendee join** — `POST /api/cohort/join/{token}` where `token` is
  a URL-safe random 32-byte string from the invite (one-shot consume).
- **Brother integration** — mirror the SSE stream into meeet.world
  cohort dashboards; aggregate into the operator's tenant scoreboard.

---

## 10. Scheduler (Wave 97) — contract v1.0

Source-of-truth: [`docs/contracts/SCHEDULER.md`](contracts/SCHEDULER.md).

Real cron-based playbook scheduler at `~/.tars/scheduler.sqlite`
(replaces the autopilot-tick polling).

- `GET /api/scheduler/schedules` — list all schedules.
- `POST /api/scheduler/schedules` — create `{playbook_id, cron, tz, enabled}`.
- `POST /api/scheduler/schedules/{id}/run-now` — ad-hoc trigger
  (bypasses cron, runs once immediately, still emits the same
  `playbook.started` webhook).
- `GET /api/scheduler/runs?schedule_id=<id>` — execution history.

For meeet.world cross-tenant cron (v9.3+): use this contract as the
reference shape; brother's distributed cron will publish into the same
event envelope.

---

## 11. Outreach module (Wave 98) — contract v1.0

Source-of-truth: [`docs/contracts/OUTREACH.md`](contracts/OUTREACH.md).

Email outreach via Gmail connector + AI-Clone style adaptation.

- Drafts are AI-Clone-styled per operator (v8.21 memory module).
- **Send is HIL-gated** — `policy_gate.require_confirm("outreach.send")`
  blocks until human approves in the HIL inbox.
- Brother integration: subscribe to outgoing webhook event
  `outreach.email_sent` for meeet.world receipt aggregation +
  per-tenant compliance trail.

---

## 12. Marketplace (Wave 106) — contract v1.0

Source-of-truth: [`docs/contracts/MARKETPLACE.md`](contracts/MARKETPLACE.md).

In-process registry + browse + install for community-published
playbooks, skills, templates, report templates. v0 ships as
**local install + ratings only — no payouts** until v9.3.

- Public registry URL (file may not exist yet — placeholder until
  community grows):
  `https://raw.githubusercontent.com/alxvasilevvv/tars-marketplace/main/registry.json`.
- Brother could host the registry file on a meeet.world subdomain
  (e.g. `marketplace.meeet.world/registry.json`) when scaling — the
  contract is just an HTTP-fetched signed JSON document, no special
  infra needed.
- v9.3 payouts (70/30 split) need brother's payment rails — Stripe is
  out (Wave 58); $MEEET + SOL are the planned settlement layers.

---

## 13. Workspaces (Wave 110) — schema-only MVP

Source-of-truth: [`docs/contracts/WORKSPACES.md`](contracts/WORKSPACES.md).

Multi-tenant scaffolding shipped in v9.1.0 as **schema + RBAC roles
only**. Data fencing is **NOT enforced** for v9.1.0 (single-tenant in
practice).

- Brother dependency for v9.3 multi-tenant fencing: meeet.world JWT must
  carry `workspace_id` and `role` (one of `owner|admin|member|viewer`)
  claims. Once those land, TARS server middleware will start enforcing
  row-level scoping on every query.
- **Invite tokens** — URL-safe random 32-byte strings, **7-day expiry**.
  Brother could mirror these into meeet.world for cross-fund collaboration
  (an invite issued on TARS for `workspace_id=X` lands as a
  cross-tenant pending invite in meeet.world).

---

## 14. Org onboarding (Wave 99)

Single-tenant org info captured during onboarding wizard, persisted to
`~/.tars/org.sqlite`. Schema:

| Field            | Notes                                          |
|------------------|------------------------------------------------|
| `name`           | string                                         |
| `org_type`       | `fund | family-office | dao | saas | other` |
| `aum`            | optional, USD numeric                          |
| `primary_use`    | freeform string (e.g. `algotrade`, `research`) |
| `team_size`      | optional, int                                  |

Brother could mirror this metadata into meeet.world for cohort/segment
analysis (no PII beyond `name` is captured).

---

## 15. Compliance export (Wave 104) — contract v1.0

Source-of-truth: [`docs/contracts/COMPLIANCE_EXPORT.md`](contracts/COMPLIANCE_EXPORT.md).

Audit-grade tarball with:
- Full receipts ledger slice for the requested window.
- Hash-chain proof + per-day Merkle root + Solana anchor txs (if
  anchoring was on).
- Detached **ed25519 signature** of the bundle root manifest.

Brother integration: register an outgoing webhook for
`compliance.bundle_generated` to push notifications when a tenant
exports — useful for the meeet.world ops dashboard ("Tenant X just
shipped a Q1 audit bundle").

---

## 16. Telegram bridge (Wave 108)

Telegram-as-transport for outgoing webhooks. The `webhooks.dispatcher`
recognises a `telegram://self` URL scheme and routes the payload via
the configured `TelegramClient` instead of HTTP POST.

Brother integration paths:
- For meeet.world ops: brother subscribes his own Telegram chat to TARS
  `qa.alert` events (Wave 117 synthetic monitor) → instant pager
  channel without standing up a separate alerting service.
- For tenant ops: same pattern, per-tenant Telegram chat → per-tenant
  webhook subscription.

---

## 17. Brother integration milestones — release-by-release

What brother needs to do per release. Items marked DONE are closed; TODO
are queued.

### v9.1.0 (this release — soft launch live, 2026-05-11)

| Status | Item |
|--------|------|
| DONE   | B-019 CF custom domain swap (`tars.meeet.world` → `tars-meeet-git`). |
| TODO   | Add `BRIDGE_SHARED_SECRET` to core-bridge env (same value operator set in CF Pages). See § 2.a. |
| TODO   | Verify core-bridge `/health` returns `200` (currently red without secret). See § 2.b. |

### v9.1.1 (~2 weeks)

| Status | Item |
|--------|------|
| TODO   | Magic-link auth backend on meeet.world. TARS UI shipped — brother backend pending. See § 3. |
| TODO   | *Optional:* register first webhook subscriber (e.g. `receipt.created` → meeet.world reputation graph mirror). |

### v9.2 (~1 month)

| Status | Item |
|--------|------|
| TODO   | Marketplace registry hosting (only if community grows past ~10 listings). See § 12. |
| TODO   | $MEEET enterprise invoice path (Business tier billing). |
| TODO   | Win/Linux installers (or wait for v9.3 if Mac-only signal is enough). |

### v9.3 (~3 months)

| Status | Item |
|--------|------|
| TODO   | JWT issuance with `workspace_id` + `role` claims (unblocks multi-tenant data fencing on TARS side — see § 13). |
| TODO   | Marketplace 70/30 payout rails ($MEEET + SOL settlement, no Stripe). |

---

## 18. Quickstart for brother — 5-minute integration verify

Three curl checks brother can paste to verify the integration is live.

```bash
# 1. Verify TARS prod is up (Service Worker should respond)
curl -s https://tars.meeet.world/sw.js | head -1
# expect: a JS source line starting with /* or // or 'self.'

# 2. Verify brother's webhook receiver endpoint is reachable from public
#    (use ngrok / preview deployment of core-bridge if local)
curl -X POST https://your-bridge.meeet.world/webhook/test \
  -H "X-TARS-Signature: t=$(date +%s),v1=test" \
  -H "Content-Type: application/json" \
  -d '{"id":"evt_test","type":"test","occurred_at":"2026-05-11T00:00:00Z","data":{}}'
# expect: HTTP 2xx (TARS treats anything 2xx as ack; non-2xx triggers retry)

# 3. Verify shared-secret roundtrip (run from operator machine with the
#    secret set in env)
BRIDGE_SHARED_SECRET="<paste>" \
  curl -s -H "x-bridge-secret: $BRIDGE_SHARED_SECRET" \
       -H "Origin: https://tars.meeet.world" \
       https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/core-bridge/health
# expect: HTTP 200 + JSON body. 401 means the secret on CF Pages != the
# secret on the Edge Function.
```

If all three pass: the integration surface is live and brother can
register his first webhook subscriber (§ 7.4).

>>> SYNC: Claude · 2026-05-11 · Wave 119 brother handoff sync.
