# Handoff for meeet.world side — v9.2 prep

**From:** TARS lane (Claude)
**To:** brother on meeet.world side
**Date:** 2026-05-14
**TARS state:** v9.1.4 (`d73aa1f`) + W187/W188 orchestrated audit + W194/W195 prep work.

This is the action list from meeet side to unblock the v9.2 schedule.
See [`docs/ROADMAP_v9.2_v10.md`](./ROADMAP_v9.2_v10.md) for full context.

---

## A. URGENT — unblock the v9.2 sprint (this week)

### A1. Install BRIDGE_SHARED_SECRET on Supabase functions (1 hour)

I've generated a 32-byte hex secret on TARS side and written it to TARS's
`.env` as `BRIDGE_SHARED_SECRET`. Same value must be set as a Supabase
function env var on all THREE bridges so they share auth state.

**What you need to do:**

1. Ping me (or pull from TARS `.env` if you have access to the project
   directory) to get the exact 32-byte hex value.
2. In Supabase dashboard → Project → Functions → Settings → Secrets,
   set `BRIDGE_SHARED_SECRET=<value>` on:
   - `tars-billing`
   - `tars-ingest`
   - `core-bridge`
3. Redeploy each function so the env var is picked up.
4. Verify by curl from TARS:
   ```bash
   curl -X POST https://<project>.supabase.co/functions/v1/tars-ingest/ping \
     -H "Authorization: Bearer $BRIDGE_SHARED_SECRET" \
     -H "Content-Type: application/json" \
     -d '{}'
   ```
   Expected: `{"ok": true, "now": "<timestamp>"}`.

5. **Acknowledge back in this doc** with date + initials when done.

### A2. Create `POST /functions/v1/tars-ingest/clone-sync` endpoint (1 day)

TARS already calls this endpoint via `maybe_emit_sync_webhook()` every
N messages (W151, W195 — wired into `record_message`). The endpoint
doesn't exist yet on your side, so the calls 404 silently.

**Contract:**

- **Method:** POST
- **Auth:** `Authorization: Bearer ${BRIDGE_SHARED_SECRET}` header
- **Headers:** `X-Idempotency-Key: <uuid>` (TARS generates)
- **Body:**
  ```json
  {
    "tars_user_id": "<uuid>",
    "envelope": {
      "version": "0.2",
      "schema": "tars.clone.style.v0.2",
      "profile": { "tone": "warm", "verbosity": "medium", ... },
      "traits": ["likes em-dash", "uses lower-case for emphasis", ...],
      "metrics": { "msg_count": 320, "avg_len": 84, ... },
      "exported_at": "2026-05-14T10:30:00Z"
    },
    "ts": "2026-05-14T10:30:00Z"
  }
  ```
- **Response:** `200 OK` with `{"stored": true, "envelope_hash": "...", "received_at": "..."}`
- **Storage:** keep the latest envelope per `tars_user_id` (or full history if you want diffs)
- **Security:** envelope contains only style profile metadata — no raw messages, no embeddings.

### A3. Verify usage events arrive (no work — just check)

TARS now emits `usage.tokens` events through `meeet_billing.client.post_usage()`
when voice synthesis or LLM calls happen. Check the meeet billing dashboard:

- Expected metric kind: `usage.tokens`
- Expected `units`: token count
- Expected `tags`: `{"surface": "voice|chat", "model": "..."}`
- Idempotency: TARS sends `X-Idempotency-Key` per event, your side must dedupe.

Confirm in this doc when first event lands.

---

## B. v9.2 mid-sprint (next 3 weeks)

### B1. Magic-link sign-in flow (3 days)

Needed for W198. Endpoints:

- **`POST /api/magic-link`** — input `{"email": "x@y.com"}` → send email with `tars://login?token=<jwt>` link
- **`GET /auth/tars-claim?token=<jwt>`** — token exchange page (or redirect-only flow)
- **`POST /api/sessions/exchange`** — body `{"magic_token": "..."}` → response `{"session_token": "...", "user": {...}, "expires_at": "..."}`
- **Cookie:** `.meeet.world` domain on response so meeet.world + TARS can share

TARS side already has deep-link handler `tars://login?token=...` (W59-8).
What's missing: client wrapper `client.exchange_magic_link(token)` —
I'll write it on my side once your endpoints are reachable.

### B2. Wire receipt anchor relay (4 days)

When TARS computes daily receipt root and dispatches Solana memo
(W197 — coming), the relayer flow needs to be:

1. TARS → POST signed transaction to your relayer (`meeet-relayer`)
2. Relayer pays the fee + submits to Solana
3. Receipt receives the signature back via webhook → stored locally

Endpoint: `POST /functions/v1/meeet-relayer/submit-memo`
- Body: signed transaction bytes (base64)
- Response: `{"signature": "...", "slot": <int>, "block_time": <unix>}`

---

## C. v9.3 marketplace prep (next 2 months)

### C1. Publisher registry (5 days)

- `POST /api/marketplace/publishers/register` — display name + email + payout wallet + Ed25519 pubkey
- `GET /api/marketplace/publishers/{pubkey}` — public profile + reputation score

### C2. Payment processing (5 days)

- Stripe webhook handler for one-time + subscription
- 70/30 split via weekly batch cron
- Escrow adapter for SOL + MEEET token payments
- Refund flow

### C3. meeet.world OAuth broker (5 days)

- Centralized OAuth for Slack/Gmail/Calendar/GitHub/Linear
- Endpoint: `/connect/{provider}?redirect_uri=tars://...`
- Token storage on meeet side; TARS exchanges session for short-lived access tokens

---

## Status tracker

| Wave | Description | Brother status | TARS status |
|---|---|---|---|
| W194 | BRIDGE_SHARED_SECRET | _waiting_ | ✅ generated + in .env |
| W195 | Clone webhook contract + endpoint | _waiting_ on A2 | ✅ TARS-side wiring done |
| W196 | Usage event verification | _waiting_ on A3 | ✅ TARS emits |
| W197 | Receipt anchor relayer | _waiting_ on B2 | _todo on TARS side_ |
| W198 | Magic-link flow | _waiting_ on B1 | _todo_ |
| W221 | Publisher registry | _waiting_ on C1 | _waiting_ |
| W222 | Payment processing | _waiting_ on C2 | _waiting_ |
| W250 | OAuth broker | _waiting_ on C3 | _waiting_ |

**Acknowledge tracker** (you tick the box when done):

- [ ] A1 — BRIDGE_SHARED_SECRET installed on all 3 functions (date: ___, initials: ___)
- [ ] A2 — /tars-ingest/clone-sync endpoint live (date: ___, initials: ___)
- [ ] A3 — first usage.tokens event observed (date: ___, initials: ___)
- [ ] B1 — magic-link 3 endpoints live (date: ___, initials: ___)
- [ ] B2 — meeet-relayer submit-memo live (date: ___, initials: ___)
- [ ] C1 — publisher registry CRUD (date: ___, initials: ___)
- [ ] C2 — payment processing + payouts (date: ___, initials: ___)
- [ ] C3 — OAuth broker (date: ___, initials: ___)

---

## How to reach me

- **Async channel:** commit a note to `docs/HANDOFF_v9.2_FOR_BROTHER.md` and push;
  TARS scheduler picks up commits within 30s and the operator dashboard
  shows new SYNC markers.
- **Live channel:** Telegram `@tars-control` (if you've configured TARS_TELEGRAM_BOT_TOKEN).
- **iMessage:** `+<operator-phone>` (configured in TARS_DAEMON_FANOUT_CHANNELS).

Stay safe out there. — TARS.
