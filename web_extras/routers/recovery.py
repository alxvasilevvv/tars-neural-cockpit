"""HTTP surface — recovery seed (Phase L5 G1 + O5 policy gate).

The seed is the **last-resort** way to bring the host's master keyring
back to life on a different machine. It is shown to the operator
exactly **once** at first install (or when the operator explicitly
asks to rotate). Everything in this router treats the seed as
sensitive: we never log the words, we never persist them, and we emit
``recovery.shown`` / ``recovery.verified`` events to the meeet store
for audit trail (event payload only carries the **fingerprint**, not
the words).

Endpoints:

- ``POST /api/recovery/generate``       → mints a fresh 24-word seed.
- ``POST /api/recovery/verify``         → checks a mnemonic + returns the fingerprint.
- ``GET  /api/recovery/wordlist/info``  → meta about the bundled BIP-39 wordlist.

Both POST routes flow through the same HTTP policy gate that protects
``/api/wallet/*`` destructive ops. Set ``TARS_REQUIRE_OPERATOR_CONFIRM=1``
to require an ``X-TARS-Confirm`` header signed for ``recovery.generate``
or ``recovery.verify``. Mint the token via
``POST /api/recovery/confirm``. The first-launch cockpit flow can call
``/generate`` directly when the env flag is unset (default for dev).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, Request
from pydantic import BaseModel, Field

from backend.core.crypto.recovery import (
    WORD_COUNT,
    fingerprint_of,
    make_recovery_seed,
)
from backend.core.crypto.recovery import _wordlist  # type: ignore[attr-defined]
from backend.core.meeet import get_client, trace_scope
from web_extras import policy_gate


router = APIRouter(prefix="/api/recovery", tags=["recovery"])


class VerifyRequest(BaseModel):
    mnemonic: str = Field(..., description="Whitespace-separated BIP-39 phrase.")
    passphrase: str | None = Field(default=None, description="Optional 25th word.")


class ConfirmRequest(BaseModel):
    action: str = Field(
        ...,
        description="One of 'recovery.generate' or 'recovery.verify'.",
    )
    # `params` is whatever body the destructive route will receive.
    # For `recovery.generate` it's `null`; for `recovery.verify` it's
    # the {mnemonic, passphrase?} payload.
    params: Any = Field(default=None)
    ttl_s: int | None = Field(
        default=None,
        ge=1,
        le=600,
        description="Optional override (default 60s, max 600s).",
    )


@router.post("/confirm")
async def mint_recovery_confirm(body: ConfirmRequest = Body(...)) -> dict[str, Any]:
    if not policy_gate.is_required():
        return {
            "ok": True,
            "policy_required": False,
            "message": "policy gate disabled — destructive routes are open.",
        }
    if body.action not in {"recovery.generate", "recovery.verify"}:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported action for recovery confirm: {body.action!r}",
        )
    params_hash = policy_gate.params_hash(body.params)
    token = policy_gate.mint_token(
        # The recovery router has no per-wallet identity, so we bind
        # the token to a stable global subject. Same shape as the
        # wallet path so verifying / rate-limiting is uniform.
        wallet_id="__recovery__",
        action=body.action,
        params_hash_hex=params_hash,
        ttl_s=body.ttl_s or 60,
    )
    return {"ok": True, "policy_required": True, **token}


@router.post("/generate")
async def generate(
    request: Request,
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    await policy_gate.require_confirm(
        request,
        wallet_id="__recovery__",
        action="recovery.generate",
        params=None,
    )
    seed = make_recovery_seed()
    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as trace_id:
        # We log the FINGERPRINT only — never the words. The operator
        # screenshot of the seed lives in their head + paper, not in
        # the meeet store.
        await client.emit(
            "recovery.shown",
            {"fingerprint": seed.fingerprint, "word_count": WORD_COUNT},
        )
        return {
            "ok": True,
            "trace_id": trace_id,
            "mnemonic": seed.mnemonic,
            "fingerprint": seed.fingerprint,
            "word_count": WORD_COUNT,
        }


@router.post("/verify")
async def verify(
    request: Request,
    body: VerifyRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    await policy_gate.require_confirm(
        request,
        wallet_id="__recovery__",
        action="recovery.verify",
        params=body.model_dump(exclude_none=True),
    )
    try:
        fp = fingerprint_of(body.mnemonic, passphrase=body.passphrase or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid_mnemonic: {exc}") from exc

    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as trace_id:
        await client.emit(
            "recovery.verified",
            {"fingerprint": fp, "word_count": WORD_COUNT},
        )
        return {"ok": True, "trace_id": trace_id, "fingerprint": fp}


@router.get("/wordlist/info")
async def wordlist_info() -> dict[str, Any]:
    words = _wordlist()
    return {
        "ok": True,
        "language": "english",
        "size": len(words),
        "first": words[0],
        "last": words[-1],
        "word_count": WORD_COUNT,
    }
