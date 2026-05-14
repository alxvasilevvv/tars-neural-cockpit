"""Wave 203 — meeet.world 1-click connect endpoint.

This is the TARS side of the magic-link flow. The brother is implementing
``POST https://meeet.world/api/magic-link`` (token issue) and
``GET  https://meeet.world/auth/tars-claim`` (browser landing page).

Until that ships, this router accepts ``POST /api/auth/meeet/exchange``
with a token the user pasted, stores it locally at
``~/.tars/meeet_token``, and returns the account hint so the cockpit can
render "✓ connected as <email>" — exactly what the W203 cockpit expects.

When the brother's endpoint is live, we'll:
  1. POST {token} → meeet.world/api/magic-link/redeem
  2. Receive {account_email, expires_at, scopes}
  3. Persist + return.

Right now we store the token and return optimistic
``account="meeet user"`` because there's nothing to verify against yet.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/meeet", tags=["auth", "meeet"])


def _token_path() -> Path:
    home = Path(os.path.expanduser("~"))
    d = home / ".tars"
    d.mkdir(parents=True, exist_ok=True)
    return d / "meeet_token"


class ExchangeRequest(BaseModel):
    token: str = Field(..., min_length=8, max_length=2048)


@router.post("/exchange")
async def exchange(req: ExchangeRequest) -> dict[str, Any]:
    """Persist a meeet.world session token.

    Once brother's /api/magic-link is live, swap the body for the real
    HTTP call and return the verified account. For now we just save +
    optimistically report 'connected'.
    """
    token = (req.token or "").strip()
    if len(token) < 8:
        raise HTTPException(status_code=400, detail={"error": "token_too_short"})

    try:
        p = _token_path()
        p.write_text(token)
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass
        logger.info("auth.meeet.exchange.saved chars=%d", len(token))
    except Exception as exc:
        logger.exception("auth.meeet.exchange.write_failed")
        raise HTTPException(status_code=500, detail={"error": "persist_failed", "message": str(exc)})

    # TODO(W204): swap to real verification once brother ships endpoint.
    base = os.getenv("MEEET_BASE_URL", "https://meeet.world").rstrip("/")
    return {
        "ok": True,
        "account": "meeet user",
        "stored_at": str(_token_path()),
        "note": "Token saved. Verification will happen on next sync once meeet.world ships /api/magic-link/redeem.",
        "account_url": f"{base}/account",
    }


@router.get("/status")
async def status() -> dict[str, Any]:
    """Is a meeet.world token configured locally?"""
    p = _token_path()
    if not p.exists():
        return {"ok": True, "connected": False}
    try:
        size = p.stat().st_size
    except OSError:
        size = 0
    return {
        "ok": True,
        "connected": size > 8,
        "path": str(p),
        "token_chars": size,
    }


@router.delete("/disconnect")
async def disconnect() -> dict[str, Any]:
    """Remove the locally stored meeet.world token."""
    p = _token_path()
    if p.exists():
        try:
            p.unlink()
        except OSError as exc:
            raise HTTPException(status_code=500, detail={"error": "unlink_failed", "message": str(exc)})
    return {"ok": True, "disconnected": True}


# ─── W219 — Magic-link + OAuth start ────────────────────────────────────


def _meeet_base() -> str:
    return os.getenv("MEEET_BASE_URL", "https://meeet.world").rstrip("/")


class MagicLinkRequest(BaseModel):
    """Wrap pydantic EmailStr if available; fall back to plain str so the
    router still loads on dev machines without pydantic[email] extras."""

    email: str = Field(..., min_length=3, max_length=320)


@router.post("/magic-link-start")
async def magic_link_start(req: MagicLinkRequest) -> dict[str, Any]:
    """Ask meeet.world to mail a magic-link to the user.

    Returns ``{ok: true, sent: true}`` if the brother's endpoint accepted
    the request. Returns ``{ok: false, error: "meeet_unreachable"}`` on
    connection error so the UI can offer a "Skip — local-only" path.
    """
    email = (req.email or "").strip().lower()
    # W230 — return a friendly envelope instead of raising 422, so the
    # frontend can render "Please enter a valid email like you@meeet.world"
    # instead of the raw Pydantic "string did not match expected pattern"
    # message that an EmailStr would produce.
    import re
    _email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    if not email or not _email_re.match(email):
        return {
            "ok": False,
            "error": "invalid_email",
            "hint": "Please enter a valid email like you@meeet.world",
        }

    try:
        import httpx
    except ImportError:
        return {"ok": False, "error": "httpx_unavailable"}

    base = _meeet_base()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                f"{base}/api/magic-link/start",
                json={"email": email, "client": "tars-desktop"},
            )
        if 200 <= r.status_code < 300:
            return {"ok": True, "sent": True, "email": email}
        return {
            "ok": False,
            "error": "meeet_rejected",
            "status": r.status_code,
            "body": r.text[:200],
        }
    except Exception as exc:
        logger.warning("auth.meeet.magic_link.unreachable: %s", exc)
        return {"ok": False, "error": "meeet_unreachable", "message": str(exc)}


@router.get("/oauth/{provider}/start")
async def oauth_start(provider: str) -> dict[str, Any]:
    """Return the meeet.world OAuth start URL for ``provider``.

    The frontend opens this URL in the default browser; meeet.world
    handles the IdP dance and finally redirects to ``tars://auth?token=…``
    which the Tauri deep-link handler picks up.
    """
    provider = (provider or "").strip().lower()
    if provider not in {"google", "apple"}:
        raise HTTPException(status_code=400, detail={"error": "unsupported_provider"})

    base = _meeet_base()
    redirect_url = f"{base}/api/oauth/{provider}/start?return=tars://auth"
    return {"ok": True, "provider": provider, "redirect_url": redirect_url}
