"""HTTP surface for the SMTP OAuth initial-consent (authorization-code)
dance.

Endpoints:

- ``POST /api/oauth/smtp/start``    → builds the consent URL, returns
  ``{url, state, code_verifier, provider}``. The cockpit caches
  ``code_verifier`` locally (it must NOT round-trip through the
  provider) and redirects the operator's browser to ``url``.
- ``POST /api/oauth/smtp/exchange`` → swaps the auth code for refresh
  + access tokens, optionally persists them into the vault, and
  emits ``business.smtp.oauth.consent.{started,completed,failed}``
  events into the meeet store.

Why stateless: the consent flow's "session" is just the PKCE
``code_verifier`` + the signed ``state`` token. The verifier rides
on the cockpit, the state is HMAC-signed (so TARS doesn't need a
database row per pending consent), and the exchange call carries
both back. This means the cockpit can be reloaded mid-flow, the
operator can switch tabs, and the dance still completes — the only
durable state is "pending consent" which already lives in the
operator's browser via the OAuth provider's URL.

The CLI helper at ``scripts/smtp_oauth_consent.py`` calls
``build_consent_url`` / ``exchange_authorization_code`` /
``persist_refresh_token`` directly without going through HTTP; that
path stays for operators who don't want to expose the consent
endpoints publicly. Both callers share the same primitives in
``backend/core/domains/packs/business/oauth_consent.py``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.domains.packs.business.oauth_consent import (
    PersistedConsent,
    TokenExchangeResult,
    build_consent_url,
    exchange_authorization_code,
    persist_refresh_token,
    verify_state,
)
from backend.core.meeet import get_client, trace_scope


router = APIRouter(prefix="/api/oauth/smtp", tags=["oauth"])
log = logging.getLogger("tars.routers.oauth_consent")


SUPPORTED_PROVIDERS = {
    "gmail",
    "google",
    "googlemail",
    "office365",
    "o365",
    "outlook",
}


# -------------------------------------------------------------- request shapes


class StartRequest(BaseModel):
    """Body for ``POST /api/oauth/smtp/start``."""

    provider: str = Field(
        ..., description="Provider shorthand: gmail, google, office365, outlook, …"
    )
    client_id: str = Field(..., min_length=1)
    redirect_uri: str = Field(
        ...,
        min_length=1,
        description=(
            "Where the OAuth provider should redirect after consent. "
            "Must match the URI registered with the OAuth app."
        ),
    )
    scope: str | None = Field(
        default=None,
        description="Optional override; falls back to provider default.",
    )
    tenant: str | None = Field(
        default=None,
        description="Microsoft tenant id (default: common).",
    )
    login_hint: str | None = Field(
        default=None,
        description="Pre-fill the user account in the consent screen.",
    )


class ExchangeRequest(BaseModel):
    """Body for ``POST /api/oauth/smtp/exchange``."""

    provider: str
    client_id: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)
    code_verifier: str = Field(
        ...,
        min_length=1,
        description="The PKCE verifier returned by /start; must be cached client-side.",
    )
    state: str = Field(
        ..., min_length=1, description="The signed state from /start."
    )
    redirect_uri: str = Field(..., min_length=1)
    client_secret: str | None = None
    tenant: str | None = None
    persist: bool = Field(
        default=True,
        description=(
            "Persist refresh_token + accompanying config into the vault "
            "(Keychain on macOS, env fallback elsewhere). Set to false "
            "for dry-run operator validation."
        ),
    )


# ------------------------------------------------------------------- helpers


def _validate_provider(value: str) -> str:
    """Normalise + validate the provider shorthand. Raises HTTP 400
    on unsupported values so operators see a clear error early."""

    if not value or not isinstance(value, str):
        raise HTTPException(status_code=400, detail="provider is required")
    norm = value.strip().lower()
    if norm not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"unsupported provider {value!r}; "
                f"choose one of {sorted(SUPPORTED_PROVIDERS)}"
            ),
        )
    return norm


# ------------------------------------------------------------------ endpoints


@router.post("/start")
async def start_consent(body: StartRequest) -> dict[str, Any]:
    """Build the consent URL the operator visits.

    The ``code_verifier`` returned here MUST be persisted by the
    cockpit (localStorage / sessionStorage) and replayed in the
    ``/exchange`` body — the OAuth provider only sees the
    ``code_challenge`` derived from it, so without the verifier the
    exchange will fail at the provider's token endpoint.
    """

    provider = _validate_provider(body.provider)

    extra = {"login_hint": body.login_hint} if body.login_hint else None
    try:
        consent = build_consent_url(
            client_id=body.client_id,
            redirect_uri=body.redirect_uri,
            provider=provider,
            scope=body.scope,
            tenant=body.tenant,
            extra_params=extra,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with trace_scope() as trace_id:
        await get_client().emit(
            "business.smtp.oauth.consent.started",
            {
                "provider": provider,
                "client_id_tail": body.client_id[-6:],
                "tenant": body.tenant,
                "redirect_uri": body.redirect_uri,
            },
        )

    return {
        "ok": True,
        "url": consent.url,
        "state": consent.state,
        "code_verifier": consent.code_verifier,
        "provider": provider,
        "trace_id": trace_id,
    }


@router.post("/exchange")
async def exchange_consent(body: ExchangeRequest) -> dict[str, Any]:
    """Swap the auth code for tokens; persist if requested.

    Verifies ``state`` first (HMAC + freshness + provider match) so a
    tampered or expired callback never reaches the token endpoint.
    Both success and failure emit a meeet event so the audit trail
    shows every consent attempt — useful for incident review when an
    operator's refresh token gets revoked upstream.
    """

    provider = _validate_provider(body.provider)

    try:
        verify_state(body.state, expected_provider=provider)
    except ValueError as exc:
        with trace_scope() as trace_id:
            await get_client().emit(
                "business.smtp.oauth.consent.failed",
                {
                    "provider": provider,
                    "stage": "state_verify",
                    "reason": str(exc),
                },
            )
        raise HTTPException(
            status_code=400, detail="invalid state"
        ) from exc

    result: TokenExchangeResult = exchange_authorization_code(
        code=body.code,
        code_verifier=body.code_verifier,
        redirect_uri=body.redirect_uri,
        client_id=body.client_id,
        client_secret=body.client_secret,
        provider=provider,
        tenant=body.tenant,
    )

    persisted: PersistedConsent | None = None
    if result.ok and body.persist:
        try:
            persisted = persist_refresh_token(
                result,
                client_id=body.client_id,
                client_secret=body.client_secret,
                provider=provider,
                tenant=body.tenant,
            )
        except ValueError as exc:
            # Should never trigger because we already gated on
            # `result.ok`, but the helper can also reject on missing
            # refresh token shape — surface that as a structured
            # operator-facing field rather than a 500.
            log.warning("persist_refresh_token rejected ok-result: %s", exc)
            persisted = None

    with trace_scope() as trace_id:
        kind = (
            "business.smtp.oauth.consent.completed"
            if result.ok
            else "business.smtp.oauth.consent.failed"
        )
        payload: dict[str, Any] = {
            "provider": provider,
            "client_id_tail": body.client_id[-6:],
            "had_refresh_token": bool(result.refresh_token),
            "persisted": persisted.to_dict() if persisted else None,
            "reason": result.reason,
        }
        await get_client().emit(kind, payload)

    if not result.ok:
        # Surface OAuth + transport failures as 4xx for client-side
        # retries; the body still carries the structured `reason`
        # field so the cockpit can render a useful error.
        return {
            "ok": False,
            "reason": result.reason,
            "error": result.error,
            "provider": provider,
            "trace_id": trace_id,
        }

    response: dict[str, Any] = {
        "ok": True,
        "provider": provider,
        "had_refresh_token": bool(result.refresh_token),
        "expires_in": result.expires_in,
        "scope": result.scope,
        "token_type": result.token_type,
        "trace_id": trace_id,
    }
    if persisted is not None:
        response["persisted"] = persisted.to_dict()
    # Refresh token is intentionally NOT echoed back when persistence
    # succeeded — vault is the canonical store and an HTTP echo would
    # leak it into browser history / proxy logs. When the operator
    # set ``persist=false`` (dry-run), we DO echo so they can copy it
    # into a script.
    if not body.persist and result.refresh_token:
        response["refresh_token"] = result.refresh_token
    return response
