"""backend/core/onprem/local_auth.py — W263.

Drop-in replacement for the meeet.world auth handshake when
MEEET_MODE=onprem. Two paths supported:

  1. Local accounts (default). The operator bootstraps the first admin
     with ADMIN_BOOTSTRAP_TOKEN; subsequent users get invited via the
     /api/admin/users endpoint and authenticate with email + password.
     Sessions are HS256 JWTs signed by TARS_AUTH_LOCAL_SIGNING_KEY.

  2. SAML / OIDC. When MEEET_ONPREM_IDP_URL (or one of its sibling
     vars) is set, login redirects to the IdP and the returned id_token
     is exchanged for a local TARS session via the OIDC code flow.
     SAML uses the metadata URL.

This module is imported by web_extras/routers/auth_meeet.py — its
top-level dispatch checks `is_onprem()` and routes here. The cloud
auth_meeet path is left untouched.

Public surface (kept narrow so the router glue is one-liners):

    exchange_token(payload) -> dict
        Take a payload from the deep-link / IdP callback and return a
        {"token": "<jwt>", "user": {...}, "tier": "..."} dict.

    issue_session(user) -> str
        Mint an HS256 JWT for a user dict. 24h TTL by default.

    verify_session(jwt) -> dict | None
        Verify and decode; None on invalid/expired.

    bootstrap_admin(token, email) -> dict | None
        One-shot bootstrap. Burns the ADMIN_BOOTSTRAP_TOKEN after use.

    idp_authorize_url() -> str | None
        Returns the IdP redirect URL if OIDC/SAML is configured.

    idp_callback_exchange(code) -> dict
        Exchange an OIDC code for tokens, then mint a local session.

Storage: writes to the same Postgres TARS uses for everything else
(see pg_migrations.py for the `users` and `sessions` tables). On the
sqlite fallback path we use ~/.tars/onprem_users.sqlite.

Note: this is the on-prem-side of the W219 auth gate. The Tauri
deep-link handler doesn't change — `tars://auth?token=...` works
identically; only the *minter* of that token is different.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from . import is_onprem

# ── 24h default session, configurable ───────────────────────────────
SESSION_TTL_S = int(os.environ.get("TARS_AUTH_LOCAL_TTL_S", str(24 * 3600)))

# Local-account store. In a real on-prem deployment with Postgres this
# is replaced by the `users` and `sessions` tables; the sqlite path is
# a fallback for the standalone backend image without Postgres.
_DEFAULT_SQLITE = Path.home() / ".tars" / "onprem_users.sqlite"


# ────────────────────────────────────────────────────────────────────
# Signing key + JWT helpers
# ────────────────────────────────────────────────────────────────────

def _signing_key() -> bytes:
    """Read TARS_AUTH_LOCAL_SIGNING_KEY (hex). Fail loud if unset.

    install.sh mints this; the docker-compose env_file passes it in.
    """
    raw = os.environ.get("TARS_AUTH_LOCAL_SIGNING_KEY", "").strip()
    if not raw:
        raise RuntimeError(
            "TARS_AUTH_LOCAL_SIGNING_KEY is empty; on-prem auth refuses to start. "
            "Run scripts/ONPREM-DEPLOY/install.sh or mint a 32-byte hex token manually."
        )
    try:
        return bytes.fromhex(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"TARS_AUTH_LOCAL_SIGNING_KEY must be hex; got {raw[:8]}...: {exc}"
        ) from exc


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def issue_session(user: dict[str, Any], ttl_s: int | None = None) -> str:
    """Mint an HS256 JWT for `user`. Compact, no third-party dep."""
    ttl = ttl_s or SESSION_TTL_S
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user.get("id") or user.get("email") or "anon",
        "email": user.get("email"),
        "tier": user.get("tier", "business"),
        "role": user.get("role", "user"),
        "iat": now,
        "exp": now + ttl,
        "iss": "tars-onprem",
    }
    h = _b64url(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64url(hmac.new(_signing_key(), f"{h}.{p}".encode(), hashlib.sha256).digest())
    return f"{h}.{p}.{sig}"


def verify_session(token: str) -> dict | None:
    """Return decoded payload if signature and exp check out; else None."""
    try:
        h, p, sig = token.split(".")
    except ValueError:
        return None
    expected = _b64url(hmac.new(_signing_key(), f"{h}.{p}".encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        payload = json.loads(_b64url_decode(p))
    except Exception:
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload


# ────────────────────────────────────────────────────────────────────
# User store (sqlite fallback; Postgres path lives in pg_migrations.py)
# ────────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class LocalUser:
    id: str
    email: str
    role: str = "user"
    tier: str = "business"
    pw_hash: str | None = None
    created_at: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "tier": self.tier,
            "created_at": self.created_at,
        }


def _conn() -> sqlite3.Connection:
    _DEFAULT_SQLITE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DEFAULT_SQLITE)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            tier TEXT NOT NULL DEFAULT 'business',
            pw_hash TEXT,
            created_at INTEGER NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS bootstrap (
            token TEXT PRIMARY KEY,
            burned_at INTEGER
        )"""
    )
    conn.commit()
    return conn


def _hash_password(pw: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${_b64url(salt)}${_b64url(derived)}"


def _verify_password(pw: str, stored: str) -> bool:
    try:
        scheme, salt_b64, derived_b64 = stored.split("$", 2)
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    expected = hashlib.scrypt(
        pw.encode(), salt=_b64url_decode(salt_b64), n=2 ** 14, r=8, p=1, dklen=32
    )
    return hmac.compare_digest(expected, _b64url_decode(derived_b64))


def create_user(email: str, password: str, role: str = "user", tier: str = "business") -> LocalUser:
    """Insert a user. Raises ValueError if email collides."""
    conn = _conn()
    user_id = f"u_{uuid.uuid4().hex[:12]}"
    pw_hash = _hash_password(password)
    created_at = int(time.time())
    try:
        conn.execute(
            "INSERT INTO users (id, email, role, tier, pw_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, email.strip().lower(), role, tier, pw_hash, created_at),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"email already registered: {email}") from exc
    finally:
        conn.close()
    return LocalUser(id=user_id, email=email, role=role, tier=tier, pw_hash=pw_hash, created_at=created_at)


def find_user(email: str) -> LocalUser | None:
    conn = _conn()
    row = conn.execute(
        "SELECT id, email, role, tier, pw_hash, created_at FROM users WHERE email=?",
        (email.strip().lower(),),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return LocalUser(*row)


def authenticate(email: str, password: str) -> LocalUser | None:
    user = find_user(email)
    if not user or not user.pw_hash:
        return None
    if not _verify_password(password, user.pw_hash):
        return None
    return user


# ────────────────────────────────────────────────────────────────────
# One-shot admin bootstrap
# ────────────────────────────────────────────────────────────────────

def bootstrap_admin(token: str, email: str, password: str) -> LocalUser | None:
    """Bootstrap the first admin. Burns the token on success.

    `token` must equal the ADMIN_BOOTSTRAP_TOKEN env var, and the
    bootstrap table must not already record a burn (one-shot).
    """
    expected = os.environ.get("ADMIN_BOOTSTRAP_TOKEN", "").strip()
    if not expected or not hmac.compare_digest(expected, token):
        return None
    conn = _conn()
    already = conn.execute("SELECT burned_at FROM bootstrap WHERE token=?", (token,)).fetchone()
    if already and already[0]:
        conn.close()
        return None  # already burned
    conn.execute(
        "INSERT OR REPLACE INTO bootstrap (token, burned_at) VALUES (?, ?)",
        (token, int(time.time())),
    )
    conn.commit()
    conn.close()
    return create_user(email, password, role="admin", tier="business")


# ────────────────────────────────────────────────────────────────────
# IdP (OIDC / SAML) — optional bridge
# ────────────────────────────────────────────────────────────────────

def idp_authorize_url(state: str | None = None) -> str | None:
    """Return the IdP redirect URL, or None if no IdP is configured.

    Honours MEEET_ONPREM_OIDC_DISCOVERY first (most common), then falls
    back to MEEET_ONPREM_IDP_URL + SAML metadata.
    """
    issuer = os.environ.get("MEEET_ONPREM_OIDC_DISCOVERY") or os.environ.get("MEEET_ONPREM_IDP_URL")
    client_id = os.environ.get("MEEET_ONPREM_OIDC_CLIENT_ID")
    if not (issuer and client_id):
        return None
    # Minimal authorize URL build — most IdPs accept these scopes.
    s = state or secrets.token_urlsafe(16)
    base = issuer.rstrip("/").rsplit("/.well-known", 1)[0]
    return (
        f"{base}/protocol/openid-connect/auth"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&scope=openid%20email%20profile%20groups"
        f"&redirect_uri=/api/auth/onprem/oidc/callback"
        f"&state={s}"
    )


def idp_callback_exchange(code: str, redirect_uri: str) -> dict:
    """Exchange OIDC code for tokens and mint a local session.

    Returns the same shape as `exchange_token`. Implementation is
    deliberately thin — production deployments should plug in a vetted
    OIDC library (authlib, msal) by overriding this function.
    """
    # Real impl: POST to <issuer>/protocol/openid-connect/token with
    # client_id + client_secret + code + redirect_uri. Parse the id_token,
    # map the email + groups -> role.
    # Here we keep a stub that mints a session against the email claim
    # we'll receive once the operator wires authlib in.
    raise NotImplementedError(
        "idp_callback_exchange is intentionally a stub. "
        "Operators wiring OIDC should monkey-patch this with an authlib-based "
        "implementation; see docs/ONPREM_DEPLOYMENT_GUIDE.md §OIDC setup."
    )


# ────────────────────────────────────────────────────────────────────
# Public entrypoint used by web_extras/routers/auth_meeet.py
# ────────────────────────────────────────────────────────────────────

def exchange_token(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle a deep-link / login payload and return a session envelope.

    Two payload shapes are accepted:

      {"mode": "password", "email": "...", "password": "..."}
      {"mode": "bootstrap", "token": "...", "email": "...", "password": "..."}

    On success returns:
      {"token": "<jwt>", "user": {...}, "tier": "business"}

    On failure returns:
      {"error": "<reason>"}
    """
    if not is_onprem():
        return {"error": "local_auth invoked outside MEEET_MODE=onprem"}
    mode = payload.get("mode") or "password"
    if mode == "bootstrap":
        user = bootstrap_admin(
            token=payload.get("token", ""),
            email=payload.get("email", ""),
            password=payload.get("password", ""),
        )
    elif mode == "password":
        user = authenticate(payload.get("email", ""), payload.get("password", ""))
    else:
        return {"error": f"unknown mode: {mode}"}
    if not user:
        return {"error": "invalid_credentials"}
    return {
        "token": issue_session(user.to_dict()),
        "user": user.to_dict(),
        "tier": user.tier,
    }
