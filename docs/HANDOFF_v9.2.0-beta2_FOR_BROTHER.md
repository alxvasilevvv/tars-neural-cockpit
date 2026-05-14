# Handoff for meeet.world side — v9.2.0-beta2 (W233 — final)

**From:** TARS lane (Claude)
**To:** brother on meeet.world side
**Date:** 2026-05-15
**Supersedes:** `docs/HANDOFF_v9.2_FOR_BROTHER.md`, `docs/BROTHER_HANDOFF_v9.1.0.md`,
`docs/INTEGRATION_FOR_BROTHER.md`, `docs/HANDOFF_v9.1.1_FOR_BROTHER.md`,
`docs/HANDOFF_brother_v9.2_beta2.md` for the auth flow only — the other
docs remain authoritative for ingest / billing / clone-sync.

This is the **single source of truth** for the four endpoints brother
must ship on `api.meeet.world` so that TARS' v9.2.0-beta2 auth screen
(W219) and voice cockpit (W220) flip from mock to live.

---

## TL;DR

TARS already has all the TARS-side wiring in place at
`web_extras/routers/auth_meeet.py`:

- `POST /api/auth/meeet/magic-link-start` -> calls your `POST {MEEET_BASE_URL}/api/magic-link/start`
- `GET  /api/auth/meeet/oauth/{provider}/start` -> returns the redirect URL to your `GET {MEEET_BASE_URL}/api/oauth/{provider}/start?return=tars://auth`
- `POST /api/auth/meeet/exchange` -> persists the token from a redeemed magic-link or OAuth callback (also called by `tars://auth?token=...` deep-link handler)
- `GET /api/auth/meeet/status`
- `DELETE /api/auth/meeet/disconnect`

What's missing is **your side**. Ship the 4 endpoints in section A,
set the env vars in section B, then run section C and you're done.

While you're shipping these, TARS users have two graceful fallbacks
(see section D), so the desktop app remains usable.

---

## A. The 4 endpoints you MUST ship on `api.meeet.world`

### A1. `POST /api/magic-link/start`

**Purpose:** TARS asks meeet.world to mail a one-time-use magic code to
the user's email. The landing page at
`https://meeet.world/auth/magic?code=...` redirects the browser to
`tars://auth?code=...&email=...&exp=...` on success, which Tauri's
deep-link handler picks up and POSTs to TARS' `/api/auth/meeet/exchange`.

**Request body (JSON):**

```json
{
  "email": "alien@example.com",
  "client": "tars-desktop",
  "return_to": "tars://auth"
}
```

**Response (200 OK):**

```json
{
  "ok": true,
  "sent": true,
  "ttl_sec": 600
}
```

**Errors:**

| Code | Body                                                            | When                                  |
|------|-----------------------------------------------------------------|---------------------------------------|
| 400  | `{"ok":false,"error":"invalid_email"}`                          | email regex fails                     |
| 400  | `{"ok":false,"error":"return_to_not_allowed"}`                  | return_to not in `MEEET_TARS_RETURN_HOSTS` |
| 429  | `{"ok":false,"error":"rate_limited","retry_after_sec":60}`      | >3 sends per email per 10 min         |

**FastAPI signature:**

```python
from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, HTTPException

class MagicLinkStartReq(BaseModel):
    email: EmailStr
    client: str = "tars-desktop"
    return_to: str = "tars://auth"

class MagicLinkStartResp(BaseModel):
    ok: bool
    sent: bool
    ttl_sec: int

@router.post("/api/magic-link/start", response_model=MagicLinkStartResp)
async def magic_link_start(req: MagicLinkStartReq) -> MagicLinkStartResp:
    # 1. validate return_to in MEEET_TARS_RETURN_HOSTS
    # 2. generate one-time code (base32, 8 chars), TTL 600s
    # 3. store {code, email, return_to, exp} in redis or pg
    # 4. send email with link https://meeet.world/auth/magic?code=<code>
    # 5. return MagicLinkStartResp(ok=True, sent=True, ttl_sec=600)
    ...
```

**Landing page (`https://meeet.world/auth/magic?code=...`):**

On successful click:

1. Look up `{email, return_to, exp}` by code.
2. If valid, redirect 302 to `return_to?code=<code>&email=<email>&exp=<exp>`.
3. If expired/missing, render a "link expired, request a new one" page.

The browser opens `tars://auth?code=...&email=...` -- Tauri's W219 deep-link handler reads `code` + `email`, then TARS calls **A2** to redeem.

---

### A2. `POST /api/magic-link/redeem`

**Purpose:** TARS swaps the one-time code for a long-lived session token.
This is single-use (the code is invalidated on first call); expires after
10 min.

**Request body (JSON):**

```json
{
  "code": "QX7A4LM2",
  "email": "alien@example.com"
}
```

**Response (200 OK):**

```json
{
  "ok": true,
  "token": "<Ed25519-signed JWT, exp in 30d>",
  "account": {
    "id": "acc_01HZ...",
    "email": "alien@example.com",
    "tier": "free"
  },
  "account_url": "https://meeet.world/account/acc_01HZ..."
}
```

**Errors:**

| Code | Body                                                | When                            |
|------|-----------------------------------------------------|---------------------------------|
| 400  | `{"ok":false,"error":"invalid_code"}`               | code not found / expired        |
| 400  | `{"ok":false,"error":"code_email_mismatch"}`        | email doesn't match code's      |
| 410  | `{"ok":false,"error":"code_already_used"}`          | second redemption               |

**JWT claims (signed with `MEEET_MAGIC_LINK_SIGNING_KEY`):**

```json
{
  "sub": "acc_01HZ...",
  "email": "alien@example.com",
  "tier": "free",
  "features": ["chat", "memory", "cowork"],
  "iss": "https://meeet.world",
  "aud": "tars-desktop",
  "iat": 1747315200,
  "exp": 1749907200
}
```

**FastAPI signature:**

```python
class RedeemReq(BaseModel):
    code: str = Field(..., min_length=4, max_length=64)
    email: EmailStr

class AccountOut(BaseModel):
    id: str
    email: EmailStr
    tier: Literal["free", "pro", "business", "lifetime"]

class RedeemResp(BaseModel):
    ok: bool
    token: str         # Ed25519-signed JWT, 30d
    account: AccountOut
    account_url: str

@router.post("/api/magic-link/redeem", response_model=RedeemResp)
async def magic_link_redeem(req: RedeemReq) -> RedeemResp:
    ...
```

---

### A3. `GET /api/oauth/{provider}/start`

**Providers:** `google`, `apple` (others can come later).

**Purpose:** TARS asks for the URL to redirect the user's default browser
to. meeet.world owns the IdP dance; on completion meeet.world redirects
the browser to `return?token=...`, the Tauri deep-link handler picks it
up, TARS POSTs to its own `/api/auth/meeet/exchange` (token-only path,
no redeem needed).

**Request:** `GET /api/oauth/google/start?return=tars://auth`

**Response (200 OK):**

```json
{
  "ok": true,
  "redirect_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&state=...&redirect_uri=https%3A%2F%2Fmeeet.world%2Fauth%2Foauth%2Fgoogle%2Fcallback"
}
```

**Errors:**

| Code | Body                                              | When                                |
|------|---------------------------------------------------|-------------------------------------|
| 400  | `{"ok":false,"error":"return_not_allowed"}`       | `return` not in `MEEET_TARS_RETURN_HOSTS` |
| 400  | `{"ok":false,"error":"unsupported_provider"}`     | provider not in {google, apple}     |

**Callback contract on meeet.world side:**

After IdP success, your callback at `/auth/oauth/{provider}/callback`
should:

1. Mint the same Ed25519 JWT as A2 (30d, same claims).
2. Persist `{account, provider_sub, refresh_token}`.
3. Redirect 302 to `<return>?token=<jwt>` (i.e. `tars://auth?token=...`).

**FastAPI signature:**

```python
class OAuthStartResp(BaseModel):
    ok: bool
    redirect_url: HttpUrl

@router.get("/api/oauth/{provider}/start", response_model=OAuthStartResp)
async def oauth_start(provider: Literal["google", "apple"], return_: str = Query("tars://auth", alias="return")) -> OAuthStartResp:
    ...
```

---

### A4. `GET /api/me`

**Purpose:** TARS polls this every 24h to refresh tier + feature flags
(e.g., a user upgrades from free -> pro -- this endpoint is how the
desktop app finds out).

**Request:** `GET /api/me`
**Header:** `Authorization: Bearer <jwt-from-A2-or-A3>`

**Response (200 OK):**

```json
{
  "ok": true,
  "account": {
    "id": "acc_01HZ...",
    "email": "alien@example.com",
    "tier": "pro",
    "features": ["chat", "memory", "cowork", "ai-clone", "marketplace"],
    "expires_at": 1749907200
  }
}
```

**Errors:**

| Code | Body                                            | When                                |
|------|-------------------------------------------------|-------------------------------------|
| 401  | `{"ok":false,"error":"invalid_token"}`          | bad signature / expired             |
| 401  | `{"ok":false,"error":"revoked"}`                | token in revocation list            |

**FastAPI signature:**

```python
class MeResp(BaseModel):
    ok: bool
    account: AccountFull  # extends AccountOut with features + expires_at

@router.get("/api/me", response_model=MeResp)
async def me(authorization: str = Header(...)) -> MeResp:
    token = authorization.removeprefix("Bearer ").strip()
    # verify Ed25519 sig, check revocation, return account
    ...
```

---

## Sequence diagram — magic-link flow

```
TARS desktop                TARS backend                       meeet.world
   |                            |                                   |
   | user types email           |                                   |
   |--------------------------->|                                   |
   |   POST /api/auth/meeet/    |                                   |
   |        magic-link-start    |                                   |
   |   {email}                  |                                   |
   |                            | POST /api/magic-link/start        |
   |                            |--------------------------------->|
   |                            |   {email, client, return_to}      |
   |                            |                                   | --(mail code)--> user inbox
   |                            |<---------------------------------|
   |                            |   {ok, sent, ttl_sec}             |
   |<---------------------------|                                   |
   |   {ok, sent}               |                                   |
   |                            |                                   |
   | user clicks email link --> https://meeet.world/auth/magic?code=...
   |                            |                                   | --(302)--> tars://auth?code=...&email=...
   |<-------- Tauri deep-link handler ------------------------------|
   |                            |                                   |
   | POST /api/auth/meeet/      |                                   |
   |   exchange {code,email}    |                                   |
   |--------------------------->|                                   |
   |                            | POST /api/magic-link/redeem       |
   |                            |--------------------------------->|
   |                            |<---------------------------------|
   |                            |   {ok, token, account}            |
   |                            | persists token at ~/.tars/meeet_token
   |<---------------------------|                                   |
   |   {ok, account}            |                                   |
   |                            |                                   |
   | (every 24h)                |                                   |
   |   GET /api/auth/meeet/     |                                   |
   |     status                 |                                   |
   |--------------------------->|                                   |
   |                            | GET /api/me                       |
   |                            |   Authorization: Bearer <token>   |
   |                            |--------------------------------->|
   |                            |<---------------------------------|
   |                            |   {ok, account: {tier, features}} |
   |<---------------------------|                                   |
```

---

## Sequence diagram — OAuth flow

```
TARS desktop                TARS backend                       meeet.world           Google/Apple IdP
   |                            |                                   |                       |
   | click "Continue with Google"
   |--------------------------->|                                   |                       |
   |   GET /api/auth/meeet/     |                                   |                       |
   |     oauth/google/start     |                                   |                       |
   |                            | GET /api/oauth/google/start       |                       |
   |                            |   ?return=tars://auth             |                       |
   |                            |--------------------------------->|                       |
   |                            |<---------------------------------|                       |
   |                            |   {ok, redirect_url}              |                       |
   |<---------------------------|                                   |                       |
   |   {redirect_url}           |                                   |                       |
   |                            |                                   |                       |
   | open redirect_url in default browser                            |                       |
   |  ----------------------------------------------------------------------------->|
   |                            |                                   |<----------------------|
   |                            |                                   |  IdP success          |
   |                            |                                   | mint Ed25519 JWT      |
   |                            |                                   | 302 -> tars://auth?token=...
   |<-------- Tauri deep-link handler ------------------------------|                       |
   |                            |                                   |                       |
   | POST /api/auth/meeet/      |                                   |                       |
   |   exchange {token}         |                                   |                       |
   |--------------------------->|                                   |                       |
   |                            | (verify via /api/me)              |                       |
   |                            |--------------------------------->|                       |
   |                            |<---------------------------------|                       |
   |<---------------------------|                                   |                       |
```

---

## B. Environment variables (brother side)

Set these in your Supabase function env / Vercel env / wherever
`api.meeet.world` runs.

| Var                            | Purpose                                                                 |
|--------------------------------|-------------------------------------------------------------------------|
| `MEEET_BRIDGE_SHARED_SECRET`   | HMAC on `/api/me` (and other server-to-server) calls. Must match TARS' `BRIDGE_SHARED_SECRET` already in `.env.example`. |
| `MEEET_TARS_RETURN_HOSTS`      | Allowlist of `tars://` return URLs. Comma-separated. For now: `tars://auth`. |
| `MEEET_MAGIC_LINK_SIGNING_KEY` | Ed25519 keypair (private key, PEM or base64) used to sign the 30d session JWT in A2/A3. Public key is published at `https://meeet.world/.well-known/jwks.json` so TARS can verify offline. |
| `MEEET_MAGIC_LINK_TTL_SEC`     | Optional, default 600. TTL on the one-time code in A1.                  |
| `MEEET_SESSION_TOKEN_TTL_SEC`  | Optional, default 2592000 (30d). TTL on A2/A3 JWTs.                     |

TARS already has `BRIDGE_SHARED_SECRET` in `.env.example` (line 25). Set
`MEEET_BRIDGE_SHARED_SECRET` to the same value -- W194 already generated
and distributed the hex.

---

## C. Acceptance criteria

Run TARS' `scripts/CHECK-MEEET-LIVE.command` (W233, double-clickable).
You're done when:

```
meeet.world live readiness:
  POST /api/magic-link/start         -> OK (200) live
  POST /api/magic-link/redeem        -> OK (4xx) endpoint deployed (request rejected, counts as live)
  GET  /api/oauth/google/start       -> OK (200) live
  GET  /api/oauth/apple/start        -> OK (200) live
  GET  /api/me                       -> OK (401) endpoint deployed (request rejected, counts as live)

Verdict: 4/4 auth endpoints live, /api/me live=yes
  can switch MEEET_MODE=live? yes (all green)
```

The script accepts both 2xx and 4xx as "endpoint exists" -- a 401 from
`/api/me` with no token, or a 400 from `/api/magic-link/redeem` with a
bogus code, both prove the endpoint is deployed and the routing is
wired. Only `404` and connection-refused count as "not deployed."

When the script prints 4/4 + /api/me live, it will (if `.env` still has
`MEEET_MODE=mock`) prompt via a macOS dialog to flip `.env` to
`MEEET_MODE=live`. Click "Yes" and restart the backend
(`./scripts/launch_tars.command` or whatever PID manager you're using)
and TARS is now talking to real meeet.world.

---

## D. Until brother is ready — TARS user fallbacks

Even while sections A-C are not yet shipped, the desktop app remains
usable thanks to two W219+W232 fallbacks:

1. **"Skip -- local-only mode"** on the auth screen.
   No cloud sync, no T2T, no marketplace. FREE tier forever.
   The user can connect later from Settings -> Connections.

2. **Text input fallback** (W232) under the voice cockpit mic.
   If STT isn't configured (no `OPENAI_API_KEY` / no `whisper.cpp`),
   the user types a command and presses Enter; it hits
   `/api/voice/command` directly.

The frontend (W233) also shows a specific toast when it detects your
endpoint isn't deployed (looks for `error: "not_deployed"` or
`error: "meeet_unreachable"` in TARS' own response, or 404/503 from the
backend):

> meeet.world cloud not deployed yet. Use "Skip -- local-only mode"
> for now. Brother is wiring it up.

This keeps the user calm and tells them whose turn it is.

---

## E. Open questions for brother

Reply in this doc (or ping Alien) when you have answers:

1. **JWT alg:** confirm Ed25519 (alg `EdDSA`) over RS256. TARS' verifier
   in `web_extras/routers/auth_meeet.py` will fetch
   `https://meeet.world/.well-known/jwks.json` on first verify and
   cache the public key for 24h.

2. **Account ID format:** ULID (`acc_01HZ...`) or UUIDv4? Whichever you
   pick, lock it in -- TARS persists this in `~/.tars/meeet_token`
   alongside the token.

3. **Tier values:** confirmed list is `free | pro | business | lifetime`?
   TARS' gating code (`backend/billing/tiers.py`) expects exactly those.

4. **Refresh strategy:** does `GET /api/me` rotate the token, or does
   TARS need a separate `POST /api/refresh`? If rotation, document the
   response shape (new `token` field on `/api/me`).

5. **`MEEET_BASE_URL`:** TARS' `.env` has `https://api.meeet.world` --
   confirm this is correct, or do you serve auth on
   `https://meeet.world/api` instead? Whichever you pick, just tell
   us; one-line change to TARS' `.env`.

---

## F. Where to look on TARS side

| What                                                | Where                                                            |
|-----------------------------------------------------|------------------------------------------------------------------|
| Auth router (the 5 TARS-side endpoints)             | `web_extras/routers/auth_meeet.py`                               |
| Auth screen (HTML/JS)                               | `desktop/src-tauri/web/index.html` (search `authMagicLink`)      |
| Deep-link handler (`tars://auth?token=...`)         | same file, search `_parseAuthDeeplink`                           |
| Token persistence                                   | `~/.tars/meeet_token`                                            |
| Local diagnostic                                    | `scripts/CHECK-MEEET-LIVE.command` (W233)                        |
| Other diagnostics                                   | `scripts/CHECK-STATUS.command`, `scripts/probe-meeet-billing.command` |
| Env config                                          | `.env` (search `MEEET_`), `.env.example`                         |
| This doc                                            | `docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md`                       |

---

**Done state:** all four endpoints live, `MEEET_BRIDGE_SHARED_SECRET`
matches, `CHECK-MEEET-LIVE.command` prints 4/4, alien flips `.env` to
`MEEET_MODE=live` via the dialog, restarts the backend, magic-link
login works end-to-end.

Once that's true, this doc closes and the next round (W148 master roadmap
items: cowork core-bridge, AI Clone sync, real receipts on Solana) opens.
