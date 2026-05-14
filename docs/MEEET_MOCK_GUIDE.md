# meeet.world Mock — Local Dev Guide (W265)

A local FastAPI server that pretends to be `api.meeet.world`. Use it to
develop and test TARS end-to-end in `MEEET_MODE=live` while brother
finishes shipping the real backend.

- **Port:** `127.0.0.1:8766`
- **Module:** `scripts.meeet_mock.server:app`
- **Persist:** `~/.tars/meeet_mock.sqlite` (accounts, magic codes, usage
  events, top-ups survive restarts)
- **Wave:** W265

---

## 1. TL;DR — three commands

```bash
# 1. start the mock (background)
./scripts/MEEET-MOCK.command

# 2. point TARS at the mock (one-shot env file, doesn't touch your .env)
echo 'MEEET_MODE=live
MEEET_BASE_URL=http://127.0.0.1:8766
MEEET_BILLING_BASE_URL=http://127.0.0.1:8766/api/billing
BRIDGE_SHARED_SECRET=' > .env.live-test

# 3. run the scripted end-to-end test
./scripts/ONE-CLICK-LIVE-TEST.command
```

Watch the mock terminal: when you POST to `/api/magic-link/start`, the
issued code + landing URL are dumped to console so you don't actually
need an email server.

---

## 2. The 8 endpoints

### Auth

| Method | Path                            | Behaviour                                                |
|--------|---------------------------------|----------------------------------------------------------|
| POST   | `/api/magic-link/start`         | Issues 8-char code, logs link to console, TTL 600s       |
| POST   | `/api/magic-link/redeem`        | Single-use code → 30d HS256 JWT                          |
| GET    | `/api/oauth/{google\|apple}/start?return=...` | Fakes IdP, mints account+token, returns redirect URL |
| GET    | `/api/me`                       | Bearer → `{tier, features, expires_at}`                  |

### Billing

| Method | Path                       | Behaviour                                                             |
|--------|----------------------------|-----------------------------------------------------------------------|
| POST   | `/api/billing/usage_event` | Optional HMAC verify, append event, debit balance, return `event_id`  |
| POST   | `/api/billing/topup`       | Bearer, fake card flow, credit USD + $MEEET at `$0.10/MEEET` peg      |
| GET    | `/api/billing/balance`     | Bearer → `{tier, balance_usd, balance_meeet, period_start, period_end}` |
| POST   | `/api/billing/tier`        | Bearer, switch tier in {free,pro,business,lifetime}, return entitlements |

### Plus

| Method | Path      | Behaviour                |
|--------|-----------|--------------------------|
| GET    | `/health` | Liveness — always 200 ok |

---

## 3. Why the mock exists

Brother's 8 endpoints aren't deployed on `api.meeet.world` yet. Without
the mock, TARS in `MEEET_MODE=live` would 404 or connection-refuse and
the dev loop would be: "wait for brother". With the mock:

1. We can ship TARS-side features that depend on `/api/billing/*` and
   `/api/me` *now*, with real HTTP round-trips.
2. The acceptance test (`ONE-CLICK-LIVE-TEST.command`) gives a green
   light before brother is ready.
3. Brother gets a runnable reference for response shapes — the mock is
   the executable spec.

---

## 4. Brother — use this as your contract reference

The mock implements the request/response shapes defined in
`docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md` (auth) and
`docs/PRICING_ECONOMICS_v9.2.md` (billing). The single source of truth
is still those two docs, but if you want a runnable sample:

```bash
# what TARS sends:
curl -X POST http://127.0.0.1:8766/api/magic-link/start \
  -H "Content-Type: application/json" \
  -d '{"email":"alien@example.com","client":"tars-desktop","return_to":"tars://auth"}'

# what TARS expects back (mock returns this):
{"ok":true,"sent":true,"ttl_sec":600,"_debug_code":"QX7A4LM2"}
```

Drop `_debug_code` in your prod response — it's only there so the mock
is testable without a real mailbox.

Differences between mock and prod brother should match:

- **JWT alg:** mock uses **HS256** with a static secret; prod must use
  **Ed25519** (alg `EdDSA`) per the handoff doc §A2. TARS verifies via
  `https://meeet.world/.well-known/jwks.json`.
- **HMAC:** mock verifies `X-Bridge-Signature: sha256=<hex>` only if
  `BRIDGE_SHARED_SECRET` is set in the mock's env. Prod must always
  verify.
- **Account IDs:** mock uses `acc_<uuid-hex-18>`. Brother is free to
  choose ULID or UUIDv4 — TARS doesn't parse the ID, just stores it.

---

## 5. Switching between mock and real meeet.world

Use two separate env files so you don't keep flipping the main `.env`:

```bash
# .env.live-test   (mock)
MEEET_MODE=live
MEEET_BASE_URL=http://127.0.0.1:8766
MEEET_BILLING_BASE_URL=http://127.0.0.1:8766/api/billing
BRIDGE_SHARED_SECRET=

# .env             (real, once brother is up)
MEEET_MODE=live
MEEET_BASE_URL=https://api.meeet.world
MEEET_BILLING_BASE_URL=https://api.meeet.world/api/billing
BRIDGE_SHARED_SECRET=<hex from W194>
```

The `ONE-CLICK-LIVE-TEST.command` writes `.env.live-test` automatically
and removes it on cleanup, so your real `.env` is never touched.

---

## 6. Persistence

```
~/.tars/meeet_mock.sqlite
  accounts(id, email, tier, balance_usd, balance_meeet, period_start, period_end)
  magic_codes(code, email, return_to, exp, used)
  usage_events(event_id, account_id, ts, action, provider, model,
               tokens_in, tokens_out, cost_usd, cost_meeet, outcome, raw_json)
  topups(id, account_id, ts, amount_usd, amount_meeet, method)
```

Survives restarts. Wipe with `rm ~/.tars/meeet_mock.sqlite` to reset.

To inspect:

```bash
sqlite3 ~/.tars/meeet_mock.sqlite "SELECT email, tier, balance_usd, balance_meeet FROM accounts;"
sqlite3 ~/.tars/meeet_mock.sqlite "SELECT count(*) FROM usage_events;"
```

---

## 7. HMAC verification (optional)

By default, the mock **skips** HMAC verification on
`/api/billing/usage_event` so smoke tests are simple. To exercise the
verification path:

```bash
BRIDGE_SHARED_SECRET=$(grep BRIDGE_SHARED_SECRET .env | cut -d= -f2-) \
  ./scripts/MEEET-MOCK.command
```

Now `usage_event` requires `X-Bridge-Signature: sha256=<hex>` where
`<hex>` is `HMAC-SHA256(BRIDGE_SHARED_SECRET, raw_body)`. Same algorithm
brother will run in prod.

---

## 8. Tier presets

Mirrors `docs/PRICING_ECONOMICS_v9.2.md` §9 verbatim:

| Tier      | Monthly requests | USD/period | $MEEET/period | Features                                     |
|-----------|------------------|------------|---------------|----------------------------------------------|
| free      | 50               | 0          | 0             | chat, memory, cowork                         |
| pro       | 1 000            | 20.00      | 200           | + ai-clone, marketplace                      |
| business  | 5 000            | 40.00      | 400           | + byo-key, audit-log, team-pool              |
| lifetime  | 1 000            | 0          | 0             | (one-off purchase; same caps as pro + byo)   |

`$MEEET` peg is `$0.10` — `topup($10)` credits `100 $MEEET`.

---

## 9. Known mock-only behaviours (won't match prod)

- `/api/magic-link/start` returns an extra `_debug_code` field. Prod
  won't.
- `/api/oauth/{provider}/start` mints a token immediately and returns
  a `tars://auth?token=...` URL. Prod must do the actual IdP dance.
- New magic-link accounts default to `tier=pro` (so you can test PRO
  features end-to-end without a separate `/api/billing/tier` step).
  Prod defaults to `free`.
- HS256 JWT vs prod's Ed25519. TARS' verifier (when it eventually
  fetches `jwks.json`) won't accept the mock's tokens for cryptographic
  verification — but for HTTP-level integration that's a non-issue.

---

## 10. Stopping the mock

```bash
lsof -i :8766          # find the uvicorn pid
kill <pid>             # graceful
kill -9 <pid>          # if it hangs
```

Or just `Ctrl+C` if you launched it in the foreground instead of via
the `.command` double-click.

---

## 11. File map

| File                                | Purpose                                             |
|-------------------------------------|-----------------------------------------------------|
| `scripts/meeet_mock/server.py`      | FastAPI app, all 8 endpoints + `/health`            |
| `scripts/meeet_mock/__init__.py`    | Package marker                                      |
| `scripts/MEEET-MOCK.command`        | Double-click launcher (port 8766, logs to file)     |
| `scripts/ONE-CLICK-LIVE-TEST.command` | Scripted user journey, pass/fail per step         |
| `docs/MEEET_MOCK_GUIDE.md`          | This doc                                            |
| `~/.tars/meeet_mock.sqlite`         | Persistent state (gitignored — outside repo)        |

---

## 12. When can I delete this?

When brother's 8 endpoints are live on `api.meeet.world` and
`scripts/CHECK-MEEET-LIVE.command` prints `4/4 + /api/me live=yes`,
the mock becomes redundant.

Even then, keep it for:
- offline development on planes/trains
- CI runs that shouldn't touch real billing
- debugging integration bugs by toggling between mock vs prod with
  one env-file swap
