# What Needs Hardening

MEDIUM / LOW findings deferred past the v9.1.0 launch. Open as separate
issues / waves; safe to defer because the launch surface is
single-user-desktop with a loopback bind by default.

Source: `docs/security/AUDIT_2026-05-09.md` (Wave 79 audit).

## MEDIUM (fix before scaling)

1. **Most `/api/*` routers do not require auth.**
   - `/api/agents/*` (CRUD + `/{id}/tasks`, `/tasks/{id}/run`,
     `/tasks/{id}/cancel`, `/agents/{id}/autopilot`)
   - `/api/memory/*` (read + write per-pack memory)
   - `/api/wallet` (non-sign endpoints: list / create / import / GET)
   - `/api/clone/profile`, `/api/clone/record`
   - `/api/chat/threads` listing / patch / delete
   - `/api/usage`, `/api/policy/*`, `/api/playbooks`, `/api/planner`,
     `/api/voice/personas`, `/api/voice/health`, `/api/awareness/*`,
     `/api/recovery`, `/api/pairing/*`
   - **Acceptable on loopback / desktop.** When the sidecar is exposed
     publicly, every endpoint above should be behind a session token.
   - Suggested fix: introduce a single `Depends(require_session)` and
     stamp it onto every router via `app.include_router(...,
     dependencies=[Depends(require_session)])` keyed by
     `TARS_SESSION_TOKEN` env (mirrors the QA pattern).

2. **`/api/qa/report` GET is unauthenticated.**
   - Returns probe names, status counts, `base_url`, `started_at`,
     `finished_at`. No env / secrets / PII, but a remote bind
     fingerprints the QA setup.
   - Fix: gate behind `QA_INGEST_TOKEN` (already used for POST) or move
     into an admin sub-router.

3. **Cloudflare Pages CSP is `frame-ancestors`-only.**
   - Lacks `default-src` / `script-src` / `connect-src`. Site is
     statically built so risk is low, but a future regression that adds
     inline JS would not be caught by CSP.
   - Fix: add `default-src 'self'; script-src 'self'; style-src 'self'
     'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'
     https://meeet.world` to `experiments/neural-showcase-v3/public/_headers`.
     Verify the marketing build doesn't ship inline scripts before
     shipping — Vite occasionally injects 1-line bootstraps for
     `<script type="module">` polyfills.

4. **`/docs` (Swagger UI) is auto-enabled.**
   - FastAPI default; useful in single-user dev. On a remote bind, it
     leaks the full route catalogue + schemas to anyone who can reach
     port 8765.
   - Fix: either gate on env (`TARS_DOCS_PUBLIC=1`) or
     `app = FastAPI(docs_url=None, redoc_url=None)` and re-enable only
     under `TARS_ENABLE_DOCS=1`.

5. **Wallet `/policy/status` and `/api/wallet` (list / get) leak wallet
   IDs without auth.**
   - Knowing a wallet ID is not a credential by itself, but combined
     with a remote bind it gives attackers per-wallet endpoint targets
     for the destructive operations.
   - Fix: same blanket session token as item 1.

## LOW (cosmetic / defence-in-depth)

1. **Confirm-token signing key falls back to in-memory random.**
   - When `TARS_CONFIRM_KEY` is unset, the policy gate generates a
     fresh 32-byte secret per process (`web_extras/policy_gate.py:50`).
     A sidecar restart silently invalidates every issued token.
     Operators relying on confirm tokens across restarts must set
     `TARS_CONFIRM_KEY` (already documented in `OPERATOR_ACTIONS.md`).
   - Optional fix: log a warning at startup when
     `TARS_REQUIRE_OPERATOR_CONFIRM=1` AND `TARS_CONFIRM_KEY` is
     missing.

2. **Test fixtures use weak inline credentials.**
   - `tests/test_business_smtp_oauth.py:263` uses `password="hunter2"`
     etc. These are scoped to the test process; cosmetic.
   - Optional fix: move to `pytest.fixture(name="dummy_password")`
     and read from a constants module.

3. **`AKIA…` / `AIza…` substrings in
   `desktop/src-tauri/web/assets/physics-BM4kW-A5.js`.**
   - These are random base32-ish slices inside a minified physics
     library bundle, not credentials. Confirmed by manual inspection
     (surrounding context is `IAEMMIAAsg…`, base32 of WASM tables).
   - Optional fix: add the file path to the
     `credential-sentinel.yml` allowlist so future scans don't re-flag
     it.

## Watch list (re-audit if any of these happen)

- TARS publishes a hosted multi-tenant flavour of the sidecar.
- The Cloudflare `_headers` CSP starts blocking real assets after
  build (means inline scripts crept in — fix the build, not the CSP).
- `core-bridge` proxies to the sidecar on a public origin (then every
  MEDIUM item becomes HIGH).
- Anyone proposes turning off `TARS_RATE_LIMIT_EXPENSIVE` outside
  tests.
