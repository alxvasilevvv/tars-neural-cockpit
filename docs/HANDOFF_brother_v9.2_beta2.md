# Brother handoff — meeet.world side for TARS v9.2.0-beta2

Updated 2026-05-14. Replaces previous handoff snapshots.

## What TARS has ready & waiting for you

### 1. Magic-link 1-click connect (the killer feature)

**TARS side (DONE, committed):**
- `POST /api/auth/meeet/exchange` — accepts a token the user pastes
  after signing in on meeet.world. Saves to `~/.tars/meeet_token` with
  0o600 perms.
- Cockpit Settings → "🌐 MEEET.WORLD · 1-CLICK CONNECT" button opens
  `https://meeet.world/account/tars-connect?source=tars-desktop&v=9.2.0-beta2`
  via Tauri shell.open.
- After paste, returns `{ok: true, account: ...}` and the cockpit
  shows ✓ connected.

**What we need from you on meeet.world:**
1. **Landing page** at `/account/tars-connect`
   - Query params: `source`, `v` (version)
   - Show "Sign in / Sign up" if not logged in
   - After auth, show a one-time token + copy button
   - Token format: opaque, 64+ chars, server-side hash for revocation
   - Token TTL: 5 minutes from issue
   
2. **POST `/api/magic-link/redeem`** (TARS will call this in W215)
   - Body: `{token: string, device_id: string}`
   - Returns: `{account_email, expires_at, scopes, refresh_token}`
   - If token expired/invalid: 401 `{error: "invalid_or_expired"}`
   - On success: invalidate the token (one-shot)

3. **POST `/api/magic-link/refresh`** (for the long-lived flow)
   - Body: `{refresh_token, device_id}`
   - Returns: `{access_token, expires_at}`
   - Same TTL semantics as standard OAuth refresh

**Contract example (TARS side will adapt):**

```http
POST https://meeet.world/api/magic-link/redeem HTTP/1.1
Content-Type: application/json
{
  "token": "tars_mlT_aB12cD34eF56gH78iJ90kL12mN34oP56qR78sT90uV12wX34",
  "device_id": "tars-desktop-aarch64-9.2.0-beta2"
}

HTTP/1.1 200 OK
{
  "account_email": "alienram@icloud.com",
  "scopes": ["billing.read", "receipts.write", "agents.sync"],
  "expires_at": "2026-08-14T12:00:00Z",
  "refresh_token": "tars_rt_..."
}
```

### 2. Public verifiable proof (no auth needed your side)

**TARS side (DONE):**
- `GET /api/public/proof/anchor/{merkle_root}` returns Solana
  explorer URL + day + leaf count
- `POST /api/public/proof/verify` is pure-function, runs entirely
  on TARS user's local backend

**What we need from you:**
- Just a docs link from `tars.meeet.world/proof` → public-facing
  explainer of how to verify a TARS-printed receipt. Don't need any
  endpoints on your side.

### 3. Cowork core-bridge wiring

**TARS side (committed since W129):**
- Full `web_extras/routers/cowork.py` with sessions/presence/handoff
- WebSocket streaming via emit_agent_frame from real orchestrator

**What we need from you:**
- The persistent Solana receipt index for cross-device cowork sessions
  (you said you'd handle this in your domain after the W148 sync)

### 4. CF Pages / `tars.meeet.world` updates

The marketing site needs:

- `/docs` route to point to a hostable docs builder (we have
  `docs/OPERATOR_v9.2.md` ready — content-wise it's complete)
- DownloadStrip → unhide DMG link once Apple Developer signing lands
  (currently shows "Coming soon")
- Roadmap / Changelog pages → auto-pull from this repo's docs/

## What's blocking us right now

1. **Apple Developer cert** — your task per W121. Without it we can't
   sign TARS.app for distribution → users get "unidentified developer"
   warning. `docs/HANDOFF_brother_apple_cert.md` has the full guide.

2. **`/api/magic-link/*`** — per section 1 above.

3. **meeet.world account → TARS receipt anchor visibility** — when a
   TARS user signs in via magic-link, your /account dashboard should
   show their TARS instance + recent receipts. Optional but high-value
   for the "social proof" angle.

## Commits in this push (W205-W213, all in `main`)

```
ff11eb8  W205  Welcome onboarding modal
5d1f042  W206  Daily briefing endpoint + Today card
81026e0  W207  backend-watchdog.command
00474db  W208  Footer: Docs / Report / Restart tour links
af9ba69  W211  pytest coverage for briefing/digest
99e5d79  W210  Tier-aware visual gating
ad964ae  W212  RELEASE_NOTES_v9.2.0-beta2
314539c  W213  Operator one-pager
```

Plus the W209 weekly digest (commit not yet hash-stamped — see
`backend/core/playbooks/weekly_digest.py` and `web_extras/routers/digest.py`).

## Test coverage now

27 new pytest cases land with this push. Existing test suite (~323
cases) all pass. Run with:

```bash
bash scripts/test-all.command
```

Output ends with `=== DONE ===` and exit 0.

## What you should reply with

1. Apple cert ETA
2. Magic-link endpoint ETA (after section 1)
3. Whether you want the docs site auto-built from this repo, or
   hand-rolled separately

Ping me on Telegram or open a tracker issue tagged `meeet-side`.
