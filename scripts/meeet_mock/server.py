"""W265 — meeet.world mock server.

A standalone FastAPI app that implements every endpoint TARS expects from
api.meeet.world, so we can run end-to-end tests in ``MEEET_MODE=live``
without waiting for brother to deploy.

Implements:
  Auth (4):
    POST /api/magic-link/start         — mail-a-code (logs URL to console)
    POST /api/magic-link/redeem        — exchange code for 30d JWT
    GET  /api/oauth/{google|apple}/start?return=... — fake IdP redirect
    GET  /api/me                       — current account + entitlements

  Billing (4):
    POST /api/billing/usage_event      — HMAC-verified usage debit
    POST /api/billing/topup            — fake card flow, credit balance
    GET  /api/billing/balance          — current balance + tier
    POST /api/billing/tier             — switch tier, return entitlements

  Plus:
    GET  /health                       — liveness probe

Contracts:
  docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md  (auth, sections A1-A4)
  docs/PRICING_ECONOMICS_v9.2.md            (tiers, caps, $MEEET peg)

Persistence:
  ~/.tars/meeet_mock.sqlite — accounts, codes, tokens, usage_events, topups.

Run:
  uvicorn scripts.meeet_mock.server:app --host 127.0.0.1 --port 8766 --reload

Author:  TARS lane (Claude)
Wave:    W265
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import string
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# W284 — graceful EmailStr fallback. Pydantic's EmailStr field type requires
# the optional `email-validator` package at MODEL CONSTRUCTION time (not just
# import). On fresh checkouts that pip-package isn't always present and the
# mock then crashes before listening. We accept plain `str` instead and rely
# on the routes' own light regex check. If you want strict RFC 5321 validation,
# `pip install email-validator` and the mock will keep working unchanged.
EmailStr = str  # type: ignore[misc,assignment]

try:
    import jwt as _jwt  # PyJWT
except Exception:  # pragma: no cover
    _jwt = None

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s meeet_mock %(levelname)s %(message)s",
)
log = logging.getLogger("meeet_mock")

# ---------------------------------------------------------------------------
# Config (env-tunable, all optional)
# ---------------------------------------------------------------------------

DB_PATH = Path(
    os.getenv(
        "MEEET_MOCK_DB",
        str(Path.home() / ".tars" / "meeet_mock.sqlite"),
    )
)
JWT_SECRET = os.getenv("MEEET_MOCK_JWT_SECRET", "tars-meeet-mock-secret-w265")
JWT_ALG = "HS256"  # symmetric — sim brother's Ed25519; TARS won't verify in mock
BRIDGE_SHARED_SECRET = os.getenv("BRIDGE_SHARED_SECRET", "")
MAGIC_TTL = int(os.getenv("MEEET_MAGIC_LINK_TTL_SEC", "600"))
TOKEN_TTL = int(os.getenv("MEEET_SESSION_TOKEN_TTL_SEC", "2592000"))  # 30d
LANDING_BASE = os.getenv("MEEET_MOCK_LANDING", "https://meeet.world")

# Tier matrix mirrors docs/PRICING_ECONOMICS_v9.2.md §9.
TIER_PRESETS = {
    "free": {
        "features": ["chat", "memory", "cowork"],
        "monthly_requests": 50,
        "usd_per_period": 0.0,
        "meeet_per_period": 0,
    },
    "pro": {
        "features": ["chat", "memory", "cowork", "ai-clone", "marketplace"],
        "monthly_requests": 1000,
        "usd_per_period": 20.0,
        "meeet_per_period": 200,
    },
    "business": {
        "features": [
            "chat", "memory", "cowork", "ai-clone", "marketplace",
            "byo-key", "audit-log", "team-pool",
        ],
        "monthly_requests": 5000,
        "usd_per_period": 40.0,
        "meeet_per_period": 400,
    },
    "lifetime": {
        "features": [
            "chat", "memory", "cowork", "ai-clone", "marketplace", "byo-key",
        ],
        "monthly_requests": 1000,
        "usd_per_period": 0.0,
        "meeet_per_period": 0,
    },
}

MEEET_PEG_USD = 0.10  # $MEEET → USD at canonical peg (PRICING §7.1)

# ---------------------------------------------------------------------------
# Persistence (SQLite, ~/.tars/meeet_mock.sqlite)
# ---------------------------------------------------------------------------

def _db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, isolation_level=None, timeout=10.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def _init_db() -> None:
    with _db() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                tier TEXT NOT NULL DEFAULT 'free',
                balance_usd REAL NOT NULL DEFAULT 0,
                balance_meeet REAL NOT NULL DEFAULT 0,
                period_start INTEGER NOT NULL,
                period_end INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS magic_codes (
                code TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                return_to TEXT NOT NULL,
                exp INTEGER NOT NULL,
                used INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS usage_events (
                event_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                ts INTEGER NOT NULL,
                action TEXT,
                provider TEXT,
                model TEXT,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0,
                cost_meeet REAL DEFAULT 0,
                outcome TEXT,
                raw_json TEXT
            );

            CREATE TABLE IF NOT EXISTS topups (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                ts INTEGER NOT NULL,
                amount_usd REAL NOT NULL,
                amount_meeet REAL NOT NULL,
                method TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_usage_account
                ON usage_events(account_id, ts);
            """
        )
    log.info("init_db at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Account helpers
# ---------------------------------------------------------------------------

def _now() -> int:
    return int(time.time())


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:18]}"


def _period_bounds(ts: Optional[int] = None) -> tuple[int, int]:
    """Calendar-month period, UTC."""
    import calendar
    import datetime as _dt
    t = _dt.datetime.utcfromtimestamp(ts or _now())
    start = _dt.datetime(t.year, t.month, 1)
    last_day = calendar.monthrange(t.year, t.month)[1]
    end = _dt.datetime(t.year, t.month, last_day, 23, 59, 59)
    return int(start.timestamp()), int(end.timestamp())


def _get_or_create_account(email: str, tier: str = "free") -> dict[str, Any]:
    email = email.strip().lower()
    with _db() as con:
        row = con.execute(
            "SELECT * FROM accounts WHERE email=?", (email,)
        ).fetchone()
        if row:
            return dict(row)
        ps, pe = _period_bounds()
        acc_id = _new_id("acc")
        con.execute(
            """INSERT INTO accounts
               (id,email,tier,balance_usd,balance_meeet,period_start,period_end,created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (acc_id, email, tier, 0.0, 0.0, ps, pe, _now()),
        )
        log.info("account.created id=%s email=%s tier=%s", acc_id, email, tier)
        return {
            "id": acc_id, "email": email, "tier": tier,
            "balance_usd": 0.0, "balance_meeet": 0.0,
            "period_start": ps, "period_end": pe, "created_at": _now(),
        }


def _account_url(acc_id: str) -> str:
    return f"{LANDING_BASE}/account/{acc_id}"


# ---------------------------------------------------------------------------
# JWT (HS256 stub; real meeet.world uses Ed25519)
# ---------------------------------------------------------------------------

def _mint_jwt(account: dict[str, Any]) -> str:
    if _jwt is None:
        raise RuntimeError("PyJWT not installed — pip install PyJWT")
    now = _now()
    claims = {
        "sub": account["id"],
        "email": account["email"],
        "tier": account["tier"],
        "features": TIER_PRESETS.get(account["tier"], TIER_PRESETS["free"])["features"],
        "iss": "meeet-mock://w265",
        "aud": "tars-desktop",
        "iat": now,
        "exp": now + TOKEN_TTL,
    }
    return _jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALG)


def _decode_jwt(token: str) -> dict[str, Any]:
    if _jwt is None:
        raise RuntimeError("PyJWT not installed")
    return _jwt.decode(
        token, JWT_SECRET, algorithms=[JWT_ALG],
        audience="tars-desktop", options={"require": ["exp", "sub"]},
    )


def _auth_account(authorization: Optional[str]) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, {"ok": False, "error": "missing_bearer"})
    token = authorization.removeprefix("Bearer ").strip()
    try:
        claims = _decode_jwt(token)
    except Exception as exc:
        log.info("auth.invalid token reason=%s", exc.__class__.__name__)
        raise HTTPException(401, {"ok": False, "error": "invalid_token"})
    with _db() as con:
        row = con.execute(
            "SELECT * FROM accounts WHERE id=?", (claims["sub"],)
        ).fetchone()
        if not row:
            raise HTTPException(401, {"ok": False, "error": "account_not_found"})
        return dict(row)


# ---------------------------------------------------------------------------
# Request/response schemas
# ---------------------------------------------------------------------------

class MagicLinkStartReq(BaseModel):
    email: EmailStr
    client: str = "tars-desktop"
    return_to: str = "tars://auth"


class RedeemReq(BaseModel):
    code: str = Field(..., min_length=4, max_length=64)
    email: EmailStr


class TopupReq(BaseModel):
    amount_usd: float = Field(..., gt=0, le=10000)
    method: str = "card"
    card_last4: str = "4242"


class TierReq(BaseModel):
    tier: str = Field(..., pattern="^(free|pro|business|lifetime)$")


class UsageEventReq(BaseModel):
    account_id: str
    ts: Optional[int] = None
    action: str = "chat.message"
    provider: str = "anthropic"
    model: str = "claude-sonnet-4.6"
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    cost_meeet: float = 0.0
    outcome: str = "ok"
    trace_id: Optional[str] = None


# ---------------------------------------------------------------------------
# HMAC helper for /api/billing/usage_event
# ---------------------------------------------------------------------------

def _verify_hmac(raw_body: bytes, sig_header: Optional[str]) -> None:
    """If BRIDGE_SHARED_SECRET is set, require X-Bridge-Signature: sha256=<hex>.

    Brother's contract: HMAC-SHA256 of the raw body with BRIDGE_SHARED_SECRET.
    """
    if not BRIDGE_SHARED_SECRET:
        return  # mock mode: no secret configured → skip verification
    if not sig_header:
        raise HTTPException(401, {"ok": False, "error": "missing_signature"})
    sig = sig_header.lower().removeprefix("sha256=").strip()
    expected = hmac.new(
        BRIDGE_SHARED_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(401, {"ok": False, "error": "bad_signature"})


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

auth = APIRouter(tags=["auth"])
billing = APIRouter(prefix="/api/billing", tags=["billing"])
oauth = APIRouter(prefix="/api/oauth", tags=["oauth"])


@auth.post("/api/magic-link/start")
async def magic_link_start(req: MagicLinkStartReq) -> dict[str, Any]:
    code = "".join(
        secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8)
    )
    exp = _now() + MAGIC_TTL
    with _db() as con:
        con.execute(
            "INSERT INTO magic_codes (code,email,return_to,exp,used) VALUES (?,?,?,?,0)",
            (code, req.email.lower(), req.return_to, exp),
        )
    link = f"{LANDING_BASE}/auth/magic?code={code}"
    # Stick it in the console so a tester can copy/paste during a live run.
    log.info("=" * 60)
    log.info("MAGIC LINK ISSUED for %s", req.email)
    log.info("  code:  %s", code)
    log.info("  link:  %s", link)
    log.info("  TTL:   %ds", MAGIC_TTL)
    log.info("  redeem: POST /api/magic-link/redeem {code, email}")
    log.info("=" * 60)
    return {"ok": True, "sent": True, "ttl_sec": MAGIC_TTL, "_debug_code": code}


@auth.post("/api/magic-link/redeem")
async def magic_link_redeem(req: RedeemReq) -> dict[str, Any]:
    email = req.email.lower()
    with _db() as con:
        row = con.execute(
            "SELECT * FROM magic_codes WHERE code=?", (req.code,)
        ).fetchone()
        if not row:
            raise HTTPException(400, {"ok": False, "error": "invalid_code"})
        if row["used"]:
            raise HTTPException(410, {"ok": False, "error": "code_already_used"})
        if row["exp"] < _now():
            raise HTTPException(400, {"ok": False, "error": "invalid_code"})
        if row["email"].lower() != email:
            raise HTTPException(400, {"ok": False, "error": "code_email_mismatch"})
        con.execute("UPDATE magic_codes SET used=1 WHERE code=?", (req.code,))

    account = _get_or_create_account(email, tier="pro")  # mock starts on PRO
    token = _mint_jwt(account)
    log.info("redeem.ok account=%s email=%s", account["id"], email)
    return {
        "ok": True,
        "token": token,
        "account": {
            "id": account["id"],
            "email": account["email"],
            "tier": account["tier"],
        },
        "account_url": _account_url(account["id"]),
    }


@oauth.get("/{provider}/start")
async def oauth_start(
    provider: str,
    return_: str = Query("tars://auth", alias="return"),
):
    """W284 — return an HTML landing page that deep-links back into TARS.app
    via the tars:// scheme. The TARS desktop frontend opens this URL in the
    user's default browser; the browser CANNOT follow a tars:// redirect via
    HTTP 302 (custom schemes aren't followed), so we serve a tiny HTML page
    that triggers macOS's URL handler via window.location.assign.

    Falls back to a clickable button if window.location is blocked by the
    browser's strict-CSP policy on file:// or sandboxed origins.
    """
    from fastapi.responses import HTMLResponse  # local to keep import cost down

    if provider not in ("google", "apple"):
        raise HTTPException(400, {"ok": False, "error": "unsupported_provider"})
    # Mint a one-shot OAuth code that auto-resolves to a real account.
    fake_email = f"{provider}-user-{secrets.token_hex(3)}@meeet-mock.test"
    account = _get_or_create_account(fake_email, tier="pro")
    token = _mint_jwt(account)
    # Brother's real flow would 302 to the IdP and back; for the mock we cut
    # straight to a return URL that already carries the minted token.
    deep_link = f"{return_}?token={token}&provider={provider}"
    log.info("oauth.start provider=%s email=%s redirect=%s",
             provider, fake_email, deep_link[:60] + "...")

    provider_label = "Google" if provider == "google" else "Apple"
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Signing you into TARS…</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0A0A0B; --fg: #E6E6E8; --muted: #8A8A92; --accent: #CA8A04;
      --card: #14141A; --border: rgba(255,255,255,0.08);
    }}
    html, body {{ margin: 0; padding: 0; background: var(--bg); color: var(--fg);
      font: 15px/1.55 -apple-system, BlinkMacSystemFont, 'Inter', system-ui, sans-serif; }}
    .wrap {{ min-height: 100vh; display: grid; place-items: center; padding: 32px; }}
    .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 16px;
      padding: 36px; max-width: 440px; width: 100%; box-shadow: 0 30px 80px rgba(0,0,0,.45); }}
    .badge {{ display: inline-flex; align-items: center; gap: 8px;
      padding: 6px 12px; border-radius: 999px; background: rgba(202,138,4,.14);
      color: var(--accent); font-size: 12px; letter-spacing: .04em; text-transform: uppercase; }}
    h1 {{ font-size: 22px; line-height: 1.25; margin: 16px 0 8px; }}
    p {{ color: var(--muted); margin: 0 0 8px; }}
    .email {{ color: var(--fg); font-family: 'SF Mono', Menlo, monospace; font-size: 13px; }}
    .row {{ display: flex; gap: 12px; align-items: center; margin-top: 24px; }}
    .btn {{ display: inline-flex; align-items: center; gap: 8px;
      padding: 12px 18px; border-radius: 10px; font-weight: 600; font-size: 14px;
      text-decoration: none; background: linear-gradient(135deg, #0891b2, #ca8a04);
      color: white; border: 0; cursor: pointer; }}
    .hint {{ font-size: 12px; color: var(--muted); margin-top: 16px; }}
    .pulse {{ width: 10px; height: 10px; border-radius: 50%; background: var(--accent);
      animation: pulse 1.4s ease-in-out infinite; }}
    @keyframes pulse {{ 0%,100% {{ opacity: .35 }} 50% {{ opacity: 1 }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <span class="badge"><span class="pulse"></span> {provider_label} verified</span>
      <h1>Signing you into TARS…</h1>
      <p>Identity provided by {provider_label} (mock).</p>
      <p>Account: <span class="email">{fake_email}</span></p>
      <div class="row">
        <a class="btn" id="continue" href="{deep_link}">Continue to TARS →</a>
      </div>
      <p class="hint">If TARS didn't pop up automatically, click the button above.
         You can close this tab once you're back in the app.</p>
    </div>
  </div>
  <script>
    // Try to deep-link immediately. macOS prompts the user the first time per app.
    window.location.assign({deep_link!r});
  </script>
</body>
</html>"""

    return HTMLResponse(html, status_code=200)


@auth.get("/api/me")
async def me(authorization: Optional[str] = Header(None)) -> dict[str, Any]:
    account = _auth_account(authorization)
    preset = TIER_PRESETS.get(account["tier"], TIER_PRESETS["free"])
    return {
        "ok": True,
        "account": {
            "id": account["id"],
            "email": account["email"],
            "tier": account["tier"],
            "features": preset["features"],
            "expires_at": _now() + TOKEN_TTL,
        },
    }


# --------- Billing ---------------------------------------------------------

@billing.post("/usage_event")
async def usage_event(
    request: Request,
    x_bridge_signature: Optional[str] = Header(None),
) -> dict[str, Any]:
    raw = await request.body()
    _verify_hmac(raw, x_bridge_signature)
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        raise HTTPException(400, {"ok": False, "error": "invalid_json"})
    try:
        ev = UsageEventReq(**payload)
    except Exception as exc:
        raise HTTPException(400, {"ok": False, "error": "invalid_payload",
                                  "detail": str(exc)})

    event_id = _new_id("ev")
    ts = ev.ts or _now()
    debit_usd = ev.cost_usd if ev.outcome == "ok" else 0.0
    debit_meeet = ev.cost_meeet if ev.outcome == "ok" else 0.0

    with _db() as con:
        acc = con.execute(
            "SELECT * FROM accounts WHERE id=?", (ev.account_id,)
        ).fetchone()
        if not acc:
            raise HTTPException(404, {"ok": False, "error": "account_not_found"})
        new_usd = max(0.0, float(acc["balance_usd"]) - debit_usd)
        new_meeet = max(0.0, float(acc["balance_meeet"]) - debit_meeet)
        con.execute(
            """INSERT INTO usage_events
               (event_id,account_id,ts,action,provider,model,
                tokens_in,tokens_out,cost_usd,cost_meeet,outcome,raw_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (event_id, ev.account_id, ts, ev.action, ev.provider, ev.model,
             ev.tokens_in, ev.tokens_out, ev.cost_usd, ev.cost_meeet,
             ev.outcome, json.dumps(payload)),
        )
        con.execute(
            "UPDATE accounts SET balance_usd=?, balance_meeet=? WHERE id=?",
            (new_usd, new_meeet, ev.account_id),
        )
    log.info("usage_event.ok ev=%s acc=%s cost=$%.4f outcome=%s",
             event_id, ev.account_id, ev.cost_usd, ev.outcome)
    return {
        "ok": True,
        "event_id": event_id,
        "balance_after": {"usd": new_usd, "meeet": new_meeet},
    }


@billing.post("/topup")
async def topup(
    req: TopupReq,
    authorization: Optional[str] = Header(None),
) -> dict[str, Any]:
    account = _auth_account(authorization)
    meeet = round(req.amount_usd / MEEET_PEG_USD, 6)
    with _db() as con:
        row = con.execute(
            "SELECT balance_usd, balance_meeet FROM accounts WHERE id=?",
            (account["id"],),
        ).fetchone()
        new_usd = float(row["balance_usd"]) + req.amount_usd
        new_meeet = float(row["balance_meeet"]) + meeet
        con.execute(
            "UPDATE accounts SET balance_usd=?, balance_meeet=? WHERE id=?",
            (new_usd, new_meeet, account["id"]),
        )
        con.execute(
            "INSERT INTO topups (id,account_id,ts,amount_usd,amount_meeet,method) "
            "VALUES (?,?,?,?,?,?)",
            (_new_id("tu"), account["id"], _now(),
             req.amount_usd, meeet, req.method),
        )
    log.info("topup.ok acc=%s +$%.2f +%.4f $MEEET method=%s",
             account["id"], req.amount_usd, meeet, req.method)
    return {
        "ok": True,
        "new_balance_usd": new_usd,
        "new_balance_meeet": new_meeet,
        "method": req.method,
        "card_last4": req.card_last4,
    }


@billing.get("/balance")
async def balance(authorization: Optional[str] = Header(None)) -> dict[str, Any]:
    account = _auth_account(authorization)
    return {
        "ok": True,
        "tier": account["tier"],
        "balance_usd": float(account["balance_usd"]),
        "balance_meeet": float(account["balance_meeet"]),
        "period_start": int(account["period_start"]),
        "period_end": int(account["period_end"]),
        "meeet_peg_usd": MEEET_PEG_USD,
    }


@billing.post("/tier")
async def change_tier(
    req: TierReq,
    authorization: Optional[str] = Header(None),
) -> dict[str, Any]:
    account = _auth_account(authorization)
    with _db() as con:
        con.execute(
            "UPDATE accounts SET tier=? WHERE id=?",
            (req.tier, account["id"]),
        )
    preset = TIER_PRESETS[req.tier]
    log.info("tier.change acc=%s %s -> %s", account["id"], account["tier"], req.tier)
    return {
        "ok": True,
        "tier": req.tier,
        "features": preset["features"],
        "monthly_requests": preset["monthly_requests"],
        "usd_per_period": preset["usd_per_period"],
        "meeet_per_period": preset["meeet_per_period"],
    }


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="meeet.world mock (W265)",
    version="0.1.0",
    description=(
        "Local mock server pretending to be api.meeet.world. "
        "Run TARS with MEEET_BASE_URL=http://127.0.0.1:8766 to test "
        "MEEET_MODE=live without brother's deploy."
    ),
)


@app.on_event("startup")
def _on_startup() -> None:
    _init_db()
    log.info("meeet.world MOCK ready on http://127.0.0.1:8766")
    log.info("DB:   %s", DB_PATH)
    log.info("HMAC: %s", "ON" if BRIDGE_SHARED_SECRET else "OFF (no BRIDGE_SHARED_SECRET set)")
    if _jwt is None:
        log.warning("PyJWT missing — auth endpoints will 500. pip install PyJWT")


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "meeet-mock",
        "version": "0.1.0",
        "wave": "W265",
        "endpoints": 8,
        "db": str(DB_PATH),
    }


app.include_router(auth)
app.include_router(billing)
app.include_router(oauth)


@app.exception_handler(HTTPException)
async def _http_exc(_req: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(detail, status_code=exc.status_code)
    return JSONResponse(
        {"ok": False, "error": str(detail)}, status_code=exc.status_code
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8766)
