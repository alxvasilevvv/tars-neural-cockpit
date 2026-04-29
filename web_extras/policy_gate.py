"""HTTP-level policy gate for destructive wallet actions (Phase O2).

The agent runner already routes destructive actions
(``wallet.propose_send``, ``wallet.sign_*_tx``, ``wallet.delete``)
through a confirmation flow. Until O2, the HTTP surface had no
equivalent — anyone with `127.0.0.1:8765` (i.e. anyone who can
reach the loopback interface) could call destructive endpoints
without an explicit operator gesture.

This module adds an opt-in HMAC-token gate:

1. Operator (or cockpit on its behalf) hits
   ``POST /api/wallet/{wallet_id}/confirm`` with
   ``{action, params_hash, ttl_s?}`` to mint a one-shot token.
2. Destructive endpoints check ``X-TARS-Confirm: <token>`` against
   the same ``(wallet_id, action, params_hash)`` tuple.
3. Token is HMAC-SHA256 signed; the signing key is read from
   ``TARS_CONFIRM_KEY`` env var (auto-generated random in-memory
   if missing — fine for single-process desktop sidecar).

The gate is **opt-in**: enabled only when
``TARS_REQUIRE_OPERATOR_CONFIRM=1``. Default off so every existing
test and dev workflow keeps working.

Token format: ``<b64url(payload_json)>.<b64url(hmac)>``. Payload is
``{w, a, p, e}`` (wallet_id, action, params_hash, expires_at unix).
"""

from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
import os
import secrets
import time
from typing import Any

from fastapi import Header, HTTPException, Request

from web_extras.errors import TARSAPIError


_DEFAULT_TTL_S = 300  # 5 minutes
_MAX_TTL_S = 3600  # 1 hour cap

# Lazily-initialised in-memory key (not env-derived). Stable for the
# lifetime of the process, which is what we need on desktop.
_in_memory_key: bytes | None = None


def _signing_key() -> bytes:
    """Return the HMAC signing key — env var if set, else process-stable random."""
    env = os.getenv("TARS_CONFIRM_KEY")
    if env:
        return env.encode("utf-8")
    global _in_memory_key
    if _in_memory_key is None:
        _in_memory_key = secrets.token_bytes(32)
    return _in_memory_key


def is_required() -> bool:
    """Whether the policy gate is currently enforced for destructive HTTP routes."""
    return os.getenv("TARS_REQUIRE_OPERATOR_CONFIRM", "0") in ("1", "true", "yes")


def params_hash(payload: Any) -> str:
    """Deterministic SHA-256 hex of the request params dict.

    Used as a binding factor in the confirm token so changing any
    field after minting invalidates the token.
    """

    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def mint_token(
    *,
    wallet_id: str,
    action: str,
    params_hash_hex: str,
    ttl_s: int = _DEFAULT_TTL_S,
) -> dict[str, Any]:
    """Mint a confirm token. Returns ``{token, expires_at, ttl_s}``."""

    ttl = max(1, min(int(ttl_s), _MAX_TTL_S))
    expires_at = int(time.time()) + ttl
    payload = {
        "w": wallet_id,
        "a": action,
        "p": params_hash_hex,
        "e": expires_at,
    }
    payload_bytes = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    sig = _hmac.new(_signing_key(), payload_bytes, hashlib.sha256).digest()
    token = f"{_b64url_encode(payload_bytes)}.{_b64url_encode(sig)}"
    return {"token": token, "expires_at": expires_at, "ttl_s": ttl}


def verify_token(
    *,
    token: str | None,
    wallet_id: str,
    action: str,
    params_hash_hex: str,
) -> None:
    """Validate ``token`` for the (wallet_id, action, params_hash) tuple.

    Raises :class:`TARSAPIError` (412 / 428 / 400) on any failure.
    Returns silently on success.
    """

    if not token:
        raise TARSAPIError(
            status_code=428,
            error_code="precondition_required",
            message=(
                "operator confirmation required for this destructive action; "
                "mint a token via POST /api/wallet/{wallet_id}/confirm and "
                "resend with X-TARS-Confirm: <token>"
            ),
        )
    if "." not in token:
        raise TARSAPIError(
            status_code=400,
            error_code="precondition_failed",
            message="confirm_token_malformed: missing signature segment",
        )
    payload_b64, _, sig_b64 = token.partition(".")
    try:
        payload_bytes = _b64url_decode(payload_b64)
        sig = _b64url_decode(sig_b64)
    except (ValueError, TypeError) as exc:
        raise TARSAPIError(
            status_code=400,
            error_code="precondition_failed",
            message=f"confirm_token_malformed: {exc}",
        ) from exc
    expected = _hmac.new(_signing_key(), payload_bytes, hashlib.sha256).digest()
    if not _hmac.compare_digest(sig, expected):
        raise TARSAPIError(
            status_code=412,
            error_code="precondition_failed",
            message="confirm_token_signature_invalid",
        )
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TARSAPIError(
            status_code=400,
            error_code="precondition_failed",
            message=f"confirm_token_payload_unreadable: {exc}",
        ) from exc
    if payload.get("w") != wallet_id:
        raise TARSAPIError(
            status_code=412,
            error_code="precondition_failed",
            message="confirm_token_wallet_mismatch",
        )
    if payload.get("a") != action:
        raise TARSAPIError(
            status_code=412,
            error_code="precondition_failed",
            message="confirm_token_action_mismatch",
        )
    if payload.get("p") != params_hash_hex:
        raise TARSAPIError(
            status_code=412,
            error_code="precondition_failed",
            message="confirm_token_params_mismatch",
        )
    if int(payload.get("e", 0)) < int(time.time()):
        raise TARSAPIError(
            status_code=412,
            error_code="precondition_failed",
            message="confirm_token_expired",
        )


async def require_confirm(
    request: Request,
    *,
    wallet_id: str,
    action: str,
    params: Any,
) -> None:
    """FastAPI dependency-shim used inside destructive route handlers.

    Reads ``X-TARS-Confirm`` from the request, computes the
    canonical params hash, and verifies. Skipped entirely when
    ``TARS_REQUIRE_OPERATOR_CONFIRM`` is off so the dev flow stays
    frictionless.
    """

    if not is_required():
        return
    token = request.headers.get("X-TARS-Confirm") or request.headers.get(
        "x-tars-confirm"
    )
    verify_token(
        token=token,
        wallet_id=wallet_id,
        action=action,
        params_hash_hex=params_hash(params),
    )


# Re-export for clean imports.
__all__ = [
    "is_required",
    "params_hash",
    "mint_token",
    "verify_token",
    "require_confirm",
]
