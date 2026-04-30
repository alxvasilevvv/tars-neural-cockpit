# Security baseline — `tars.meeet.world`

> **Status:** drafted by Cursor 2026-05-01.
> **Read with:** `docs/DISASTER_RECOVERY.md`, `docs/OBSERVABILITY.md`,
> `docs/contracts/CORE_BRIDGE.md`.

This is the smallest set of security controls that lets us ship the
TARS subdomain in production without crossing the line into "lol no".
Anything not listed here is either inherited from upstream (Supabase,
Cloudflare) or acknowledged-not-implemented.

---

## 1. Threat model in one paragraph

The high-value asset is the **off-chain treasury** (user $MEEET
balances + agent purchase capital). The most realistic attacks are:

1. Quest reward grooming via repeated Edge Function calls
   (covered by Lovable Prompt 8).
2. Race conditions in stake/unstake leading to free $MEEET
   (covered by Lovable Prompt 9).
3. Service-role key leak via accidentally committed `.env`
   (covered by §3 and `.gitignore`).
4. Cross-site request forgery against authenticated Edge Functions
   (covered by §4 and CORS allow-list).
5. Client-side script injection on user-controlled fields
   (covered by §5 and React's default escaping).

Anything beyond those falls under "we'd like to harden but the
incremental risk doesn't justify the engineering cost yet".

---

## 2. Network boundary

| Boundary                                              | Control                                                          |
| ----------------------------------------------------- | ---------------------------------------------------------------- |
| Public → CF Pages                                     | TLS via Cloudflare. HSTS enforced via `_headers` (max-age 2y).    |
| CF Pages → Supabase Edge Functions                    | TLS via Supabase. Pages Function adds `BRIDGE_SHARED_SECRET`.     |
| Supabase EF → Postgres                               | Service-role key, never returned in responses.                    |
| Supabase EF (TARS) → Supabase EF (core)               | core-bridge with constant-time `x-bridge-secret` check.           |
| Supabase EF (core) → Supabase EF (TARS) `tars-ingest` | Bearer with `TARS_INGEST_API_KEY`.                                |
| Browser → Supabase EF                                 | Origin allow-list (`TARS_ALLOWED_ORIGINS`) + 403 on mismatch.     |
| Tauri WebView → local FastAPI daemon                  | localhost only; daemon binds 127.0.0.1, no external interface.    |

Every cross-trust hop has a probe in the QA Agent (`make qa-agent`).
A regression on any of these should be Sev 2 within 30 minutes.

---

## 3. Secrets at rest

**Rules:**

1. No secret is ever committed to git. Confirmed by manual review on
   2026-05-01. Re-confirmed on every PR by GitHub's secret scanner
   (already enabled on both repos).
2. Production secrets live in exactly two places: Cloudflare Pages env
   (for Pages Functions), Supabase EF env (for Edge Functions). They
   are never duplicated in `wrangler.toml`, `vercel.json`, or any
   committed file.
3. The only commit'able env files are `.env.example` (TARS) and
   `experiments/neural-showcase-v3/.env.production`. The latter
   contains only `VITE_TARS_API`, which is public by design.
4. Rotation policy: see `DISASTER_RECOVERY.md` §5.

**Detection:** GitHub's secret-scanning alerts (free for public repos)
+ pre-commit hook recommended for sensitive contributors.

---

## 4. CSRF / abuse protection

| Surface                          | Control                                                                                                                                              |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `core-bridge/relay-event`        | `x-bridge-secret` header (constant-time compare). Origin allow-list. Schema validation rejects malformed payloads with 400.                          |
| `tars-ingest`                    | Bearer `TARS_INGEST_API_KEY` required if set. Origin allow-list. Stricter `authOk` after 2026-04-30 patch.                                            |
| `tars-downloads`                 | Origin allow-list. Public read otherwise (this is by design — the manifest is meant to be cacheable).                                                |
| Quest reward EF (Lovable)         | Per-user rate-limiting (Lovable Prompt 8). Per-(user,quest) cooldown.                                                                                |
| Stake / unstake EF (Lovable)      | Postgres transaction with `FOR UPDATE` row locks (Lovable Prompt 9).                                                                                |
| Vote EF (Lovable)                 | `UNIQUE(user, proposal)` + idempotency-key (Lovable Prompt 10).                                                                                      |
| Browser → SPA                    | React's default JSX escaping. No `dangerouslySetInnerHTML` of user-controlled data. (Audited 2026-04-29 during code review.)                          |
| Mobile bottom nav                | Tap targets ≥48 CSS px (Lovable Prompt 11).                                                                                                          |

---

## 5. Content security

CSP is **report-only** at the moment because we have a few
known-incompatible dependencies (Spline runtime needs `script-src
'unsafe-eval'`). The `_headers` file ships a permissive CSP that lets
those work; tightening will land alongside Spline removal in the
bundle-optimisation lane.

Acceptable today:
- HSTS (max-age 2y, includeSubDomains, preload-ready)
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy: camera=(), microphone=(), geolocation=()

Pending:
- Tighten CSP to `script-src 'self' https://prod.spline.design`
  (no `'unsafe-inline'`, no `'unsafe-eval'`) once Spline scenes are
  preloaded server-side or replaced with a static SVG fallback.
- Subresource Integrity for the few `<script>` tags pointing at
  `prod.spline.design`.

---

## 6. Auth & session

`tars_session_id` is anonymous, scoped to `Domain=.meeet.world` so it
shares with `meeet.world`. We do not currently authenticate users on
`tars.meeet.world`; the cockpit auth flow is a separate, opt-in step
that uses Supabase Auth on the meeet/core project.

Implications:
- A leaked `tars_session_id` cookie reveals page views but no PII.
- The cookie is HttpOnly + Secure + SameSite=Lax. JS can't read it.
- Lifetime is 1 year. Rotation on logout is a future feature when the
  cockpit gets account binding.

---

## 7. Dependency hygiene

- TARS cockpit (`experiments/neural-showcase-v3`): `npm audit
  --omit=dev` is **0 vulnerabilities** as of 2026-05-01.
- Tauri shell (`desktop/`): Cargo lockfile pinned. `cargo audit` runs
  in CI on every push (workflow: `release-desktop-tagged.yml`).
- meeet-app (Lovable-managed): audit runs as part of the Lovable
  build; results visible on `meeet-solana-state-941a6045` Actions.

Dependabot is enabled on both repos; we accept its PRs after vitest
green and a reviewer pass. Critical / high-severity advisories cut to
the front.

---

## 8. Audit log

Every state-changing Edge Function writes to `audit_*` companion tables:

- `audit_quest_throttle` — quest grooming attempts (success or 429)
- `audit_staking_actions` — stake / unstake events with reason codes
- `audit_governance_votes` — vote attempts with idempotency-key trace
- `tars_event_ingest` (kind = `tars.client.error`) — runtime errors
- `tars_event_ingest` (kind = `tars.qa.probe`) — QA Agent traces

Retention 90 days, visibility limited to service_role + Operator.

This is the minimum viable trail for incident postmortems and grooming
detection. We expand only when an incident reveals a missing column.

---

## 9. What's not implemented (intentional)

- **WAF rules** beyond Cloudflare's default. Adequate for current
  traffic.
- **Bot management.** Cloudflare's free tier covers the obvious
  patterns; paid tier deferred until quest grooming becomes measurable.
- **2FA on Supabase project owner.** Operator's responsibility, please
  confirm enabled.
- **Field-level encryption for `tars_event_ingest`.** Not justified —
  no PII in the column set today. Re-evaluate when adding wallet
  addresses or emails.
- **Pen test.** Deferred until the on-chain treasury cutover. Until
  then the off-chain footprint is small and the audit trail is fast.

If any of those graduate from "deferred" to "needed", they get tracked
in `docs/MEEET_PROJECT_REVIEW.md` risk register.

---

## 10. Quick-reference commands

```bash
# Probe production end-to-end
make qa-agent

# Probe with bridge auth (catches more)
BRIDGE_SHARED_SECRET=… make qa-agent

# Local typecheck + tests
cd experiments/neural-showcase-v3 && npx tsc --noEmit && npx vitest run

# Smoke the cross-project bridge
BRIDGE_SHARED_SECRET=… make smoke-core-bridge

# Audit deps
cd experiments/neural-showcase-v3 && npm audit --omit=dev
```

Anything that returns a non-zero exit on these belongs to **someone**
this hour, not next sprint.
