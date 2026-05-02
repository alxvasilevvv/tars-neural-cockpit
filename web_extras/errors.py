"""Unified error envelope for the TARS HTTP surface (Phase O1).

Goals:

- Every error response carries a stable, machine-readable
  ``error_code`` taxonomy entry, not just a free-form string.
- Cockpit / agents / mobile companions can localise / branch on
  ``error_code`` without parsing English prose.
- The legacy FastAPI ``detail`` field is preserved so existing
  tests keep working.

Shape:

::

    {
        "ok": false,
        "error_code": "wallet_not_found",
        "message": "wallet_not_found: wlt_deadbeef",
        "hint": "Re-create the wallet via POST /api/wallet, then retry.",
        "detail": "wallet_not_found: wlt_deadbeef"   // FastAPI legacy
    }

The taxonomy lives in :data:`ERROR_CODES`. Anything not registered
falls through to ``internal_error`` / ``http_<status>``.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("tars.errors")

# Stable taxonomy. Add new entries here, never reuse codes.
ERROR_CODES: Mapping[str, str] = {
    # generic
    "validation_error": "Request body / query failed schema validation.",
    "internal_error": "Unexpected server error. Check logs / retry later.",
    "not_found": "Resource not found.",
    "method_not_allowed": "HTTP method not allowed for this path.",
    "rate_limited": "Too many requests; retry with backoff.",
    "precondition_required": "Operator confirmation required for this destructive action.",
    "precondition_failed": "Confirmation token invalid or expired.",
    # wallet
    "wallet_not_found": "Wallet id does not exist.",
    "wallet_chain_mismatch": "Action requires a wallet on a different chain.",
    "wallet_secret_missing": "Wallet's encrypted private material is unreadable.",
    "wallet_invalid_amount": "Amount could not be parsed.",
    "wallet_invalid_recipient": "Recipient address failed format validation.",
    "wallet_invalid_blockhash": "Solana recent_blockhash failed format validation.",
    "wallet_invalid_tx": "Transaction dict failed signer validation.",
    "wallet_signing_unsupported": "Signing primitive not implemented for this chain.",
    "wallet_balance_rpc_failure": "Live JSON-RPC balance read failed.",
    # agent
    "agent_not_found": "Agent id does not exist.",
    "agent_invalid_status_transition": "Agent status transition is not allowed.",
    "task_not_found": "Task id does not exist.",
    "task_invalid_status_transition": "Task status transition is not allowed.",
    # pairing / vault / recovery
    "pairing_invalid_token": "Pairing token is malformed, unknown, or expired.",
    "pairing_invalid_payload": "Pairing payload failed validation.",
    "pair_rate_limited": "Per-IP pairing-begin rate limit exceeded; retry after the Retry-After window.",
    "recovery_rate_limited": "Per-IP recovery-challenge rate limit exceeded; retry after the Retry-After window.",
    "challenge_not_found": "Recovery challenge id is unknown or has been swept by the in-memory store.",
    "challenge_not_passed": "Recovery challenge has not been passed yet (or was consumed/expired/exhausted).",
    "fingerprint_mismatch": "Recovery challenge fingerprint does not match the current host's bound seed.",
    "recovery_not_bound": "Host identity has no recovery fingerprint bound yet; generate a seed first.",
    "rotate_blocked": "Rotate-identity is gated behind a passed 3-of-24 recovery challenge.",
    "vault_unavailable": "Encrypted vault is locked or missing.",
    "recovery_invalid_mnemonic": "Mnemonic failed BIP-39 validation.",
    # entitlements / billing (Bug #2 + Bug #3 from SYSTEM_AUDIT_2026-05-02)
    "payment_required": (
        "Daily cloud-LLM budget exhausted for the current tier; "
        "upgrade or enable BYO before retrying."
    ),
    "feature_disabled": "Endpoint is disabled in this deployment.",
    "not_implemented": "Endpoint is recognised but the implementation is not live yet.",
}

# Hints map error_code → human-actionable next step. Optional.
ERROR_HINTS: Mapping[str, str] = {
    "wallet_not_found": "Re-create the wallet via POST /api/wallet, then retry.",
    "wallet_chain_mismatch": "Use a wallet whose chain matches the target action.",
    "wallet_invalid_amount": "Pass amounts as digits (lamports / nanoton / wei) "
    "or decimal SOL / TON / ETH.",
    "wallet_balance_rpc_failure": "Check TARS_*_RPC_URL env vars and retry.",
    "agent_invalid_status_transition": "Inspect /api/agents/{id} for the current status.",
    "task_invalid_status_transition": "Cancel the task or wait for it to settle.",
    "pairing_invalid_token": "Mint a fresh token via POST /api/pairing/init.",
    "vault_unavailable": "Set TARS_PAIRING_VAULT and TARS_VAULT_KEY before "
    "calling secret-bearing routes.",
    "precondition_required": "Mint a confirm token via POST /api/wallet/confirm "
    "and resend with X-TARS-Confirm: <token>.",
    "payment_required": (
        "POST /api/entitlements/upgrade {tier:'pro'|'business', payment_token:<...>} "
        "or POST /api/entitlements/byo {enabled:true} to lift the cap."
    ),
}


class TARSAPIError(HTTPException):
    """HTTPException with a ``error_code`` and optional ``hint``.

    Subclasses ``HTTPException`` so existing FastAPI machinery
    (validation flow, ``response_model`` interaction, OpenAPI docs)
    keeps working without further changes.
    """

    def __init__(
        self,
        *,
        status_code: int,
        error_code: str,
        message: str,
        hint: str | None = None,
        headers: Mapping[str, str] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            status_code=status_code, detail=message, headers=dict(headers or {})
        )
        self.error_code = error_code
        self.message = message
        self.hint = hint or ERROR_HINTS.get(error_code)
        # Optional structured payload surfaced into the JSON envelope
        # under the ``context`` key. Cockpit / mobile clients use this
        # to render structured panels (e.g. cap_hit budget snapshot)
        # without parsing the human-readable ``message``.
        self.context: dict[str, Any] | None = (
            dict(context) if context is not None else None
        )


def _envelope(
    *,
    error_code: str,
    message: str,
    hint: str | None,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "ok": False,
        "error_code": error_code,
        "message": message,
        # Legacy: FastAPI clients (and our older tests) check `detail`.
        "detail": message,
    }
    if hint:
        body["hint"] = hint
    if context:
        body["context"] = dict(context)
    return body


def _classify_http(exc: HTTPException) -> tuple[str, str, str | None]:
    """Map a bare HTTPException to (code, message, hint) when the
    handler didn't include one explicitly."""

    if isinstance(exc, TARSAPIError):
        return exc.error_code, exc.message, exc.hint

    # Try to recover a code from `detail` if it follows our convention
    # `"<code>: <message>"`.
    detail = exc.detail
    detail_str = str(detail) if detail is not None else ""
    code = f"http_{exc.status_code}"
    message = detail_str or "request failed"
    if ":" in detail_str:
        head, _, tail = detail_str.partition(":")
        head = head.strip()
        if head and head.replace("_", "").isalnum() and head in ERROR_CODES:
            code = head
            message = detail_str
    elif detail_str in ERROR_CODES:
        code = detail_str
        message = detail_str
    elif exc.status_code == 404:
        code = "not_found"
    elif exc.status_code == 405:
        code = "method_not_allowed"
    elif exc.status_code == 422:
        code = "validation_error"
    elif exc.status_code == 428:
        code = "precondition_required"
    elif exc.status_code == 412:
        code = "precondition_failed"
    elif exc.status_code == 429:
        code = "rate_limited"
    return code, message, ERROR_HINTS.get(code)


async def _http_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    code, message, hint = _classify_http(exc)
    context = getattr(exc, "context", None) if isinstance(exc, TARSAPIError) else None
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(
            error_code=code, message=message, hint=hint, context=context
        ),
        headers=exc.headers or {},
    )


async def _validation_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            **_envelope(
                error_code="validation_error",
                message="request body / query failed schema validation",
                hint="Inspect `errors` for the per-field breakdown.",
            ),
            "errors": exc.errors(),
        },
    )


async def _unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled API error: %s", exc)
    return JSONResponse(
        status_code=500,
        content=_envelope(
            error_code="internal_error",
            message=f"internal_error: {type(exc).__name__}",
            hint="Inspect server logs; this should not happen in production.",
        ),
    )


def install(app: FastAPI) -> None:
    """Wire the unified envelope handlers onto a FastAPI app.

    Call once at startup, before serving traffic.
    """

    # Starlette routing emits its own HTTPException class for 404 /
    # 405 / etc. before the FastAPI layer; register both.
    from starlette.exceptions import HTTPException as StarletteHTTPException

    app.add_exception_handler(HTTPException, _http_handler)
    app.add_exception_handler(StarletteHTTPException, _http_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    # Catch-all only kicks in when nothing else handled the exception.
    # We do NOT register Exception in dev mode because it swallows
    # tracebacks; production deployments should set TARS_HIDE_TRACEBACKS=1.
    import os

    if os.getenv("TARS_HIDE_TRACEBACKS", "0") in ("1", "true", "yes"):
        app.add_exception_handler(Exception, _unhandled_handler)
