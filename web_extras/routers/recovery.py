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
- ``POST /api/recovery/challenge/start`` → mints a 3-of-24 verification challenge.
- ``POST /api/recovery/challenge/verify`` → checks the operator's answers.
- ``GET  /api/recovery/challenge/{id}``  → fetches the public-safe challenge state.
- ``GET  /api/recovery/wordlist/info``  → meta about the bundled BIP-39 wordlist.

Both POST routes flow through the same HTTP policy gate that protects
``/api/wallet/*`` destructive ops. Set ``TARS_REQUIRE_OPERATOR_CONFIRM=1``
to require an ``X-TARS-Confirm`` header signed for ``recovery.generate``
or ``recovery.verify``. Mint the token via
``POST /api/recovery/confirm``. The first-launch cockpit flow can call
``/generate`` directly when the env flag is unset (default for dev).
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, Request
from pydantic import BaseModel, Field

from backend.core.crypto.recovery import (
    WORD_COUNT,
    fingerprint_of,
    make_recovery_seed,
)
from backend.core.crypto.recovery import _wordlist  # type: ignore[attr-defined]
from backend.core.crypto.seed_challenge import (
    DEFAULT_CHALLENGE_COUNT,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_TTL_S,
    MAX_CHALLENGE_COUNT,
    MAX_MAX_ATTEMPTS,
    MAX_TTL_S,
    MIN_CHALLENGE_COUNT,
    MIN_MAX_ATTEMPTS,
    MIN_TTL_S,
    SeedChallenge,
    get_challenge_store,
    mint_challenge,
    verify_challenge,
)
from backend.core.meeet import get_client, trace_scope
from web_extras import policy_gate
from web_extras.errors import TARSAPIError
from web_extras.rate_limit import RateLimitOutcome, get_rate_limiter


router = APIRouter(prefix="/api/recovery", tags=["recovery"])


# Rate-limit defaults: a legit operator scans the QR, types 3 word
# answers, possibly retries once, and is done. So a tight burst with
# a slow refill is plenty of headroom. ``challenge.start`` is more
# expensive (mints + persists a challenge) so it gets a smaller
# burst. ``challenge.verify`` is cheaper (constant-time compare) but
# more attractive to a brute-forcer, so it gets a smaller refill.
RECOVERY_CHALLENGE_START_BUCKET = "recovery.challenge.start"
RECOVERY_CHALLENGE_VERIFY_BUCKET = "recovery.challenge.verify"


def _f(env: str, default: float) -> float:
    raw = os.getenv(env)
    if raw is None or not raw.strip():
        return default
    try:
        return max(0.0, float(raw))
    except ValueError:
        return default


def _configure_recovery_rate_limit_once() -> None:
    limiter = get_rate_limiter()
    if not limiter.is_configured(RECOVERY_CHALLENGE_START_BUCKET):
        capacity = _f("TARS_RECOVERY_CHALLENGE_START_BURST", 5.0)
        rate = _f("TARS_RECOVERY_CHALLENGE_START_RATE_PER_S", 1.0 / 30.0)
        if capacity <= 0:
            capacity = 1.0
        limiter.configure(
            RECOVERY_CHALLENGE_START_BUCKET, capacity=capacity, rate=rate
        )
    if not limiter.is_configured(RECOVERY_CHALLENGE_VERIFY_BUCKET):
        capacity = _f("TARS_RECOVERY_CHALLENGE_VERIFY_BURST", 10.0)
        rate = _f("TARS_RECOVERY_CHALLENGE_VERIFY_RATE_PER_S", 1.0 / 10.0)
        if capacity <= 0:
            capacity = 1.0
        limiter.configure(
            RECOVERY_CHALLENGE_VERIFY_BUCKET, capacity=capacity, rate=rate
        )


def _client_ip(request: Request) -> str:
    """Resolve the source IP. Mirrors the pairing module's helper.

    Honours ``X-Forwarded-For`` only when ``TARS_TRUST_FORWARDED_FOR=1``
    is explicitly set (typical reverse-proxy deployment), otherwise
    falls back to ``request.client.host`` so a hostile client can't
    spoof its source IP via that header.
    """

    if os.getenv("TARS_TRUST_FORWARDED_FOR", "0") in ("1", "true", "yes"):
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    if request.client is not None and request.client.host:
        return request.client.host
    return ""


async def _enforce_recovery_rate_limit(
    request: Request, *, bucket_id: str, route: str
) -> None:
    """Acquire a token from ``bucket_id`` or raise a 429.

    Emits a ``recovery.rate_limited`` event so an operator audit
    pass can spot brute-force attempts. The 429 envelope mirrors
    the pairing one: ``Retry-After`` + ``X-RateLimit-{Remaining,
    Reset,Bucket}`` headers, JSON body with ``error_code``.
    """

    _configure_recovery_rate_limit_once()
    subject = _client_ip(request)
    outcome: RateLimitOutcome = get_rate_limiter().acquire(
        bucket_id=bucket_id, subject=subject
    )
    if outcome.allowed:
        return

    retry_payload = (
        86400.0
        if outcome.retry_after == float("inf") or outcome.retry_after > 86400
        else float(outcome.retry_after)
    )
    retry_seconds = max(1, int(retry_payload) + 1)
    client = get_client()
    await client.emit(
        "recovery.rate_limited",
        {
            "subject": outcome.subject,
            "bucket_id": outcome.bucket_id,
            "retry_after": retry_payload,
            "remaining": outcome.remaining,
            "route": route,
        },
    )
    raise TARSAPIError(
        status_code=429,
        error_code="recovery_rate_limited",
        message=(
            f"recovery_rate_limited: retry in {retry_seconds}s "
            f"(remaining={outcome.remaining:.2f})"
        ),
        hint=(
            "Slow down recovery-challenge attempts from this IP, or "
            "wait until the rate limit resets."
        ),
        headers={
            "Retry-After": str(retry_seconds),
            "X-RateLimit-Remaining": f"{outcome.remaining:.4f}",
            "X-RateLimit-Bucket": outcome.bucket_id,
            "X-RateLimit-Reset": f"{outcome.reset_at:.4f}",
        },
    )


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


class ChallengeStartRequest(BaseModel):
    """Body for ``POST /api/recovery/challenge/start``.

    The mnemonic is consumed only to fingerprint the seed and pick
    word positions; it never persists. The cockpit can mint
    multiple parallel challenges (e.g. one per device pairing
    flow) — they're identified by ``challenge_id``.
    """

    mnemonic: str = Field(..., description="Whitespace-separated BIP-39 phrase.")
    count: int = Field(
        default=DEFAULT_CHALLENGE_COUNT,
        ge=MIN_CHALLENGE_COUNT,
        le=MAX_CHALLENGE_COUNT,
        description="Number of word positions to challenge (1..8, default 3).",
    )
    ttl_s: int = Field(
        default=DEFAULT_TTL_S,
        ge=MIN_TTL_S,
        le=MAX_TTL_S,
        description=(
            "Challenge lifetime in seconds. Default 5 min, hard cap 30 min."
        ),
    )
    max_attempts: int = Field(
        default=DEFAULT_MAX_ATTEMPTS,
        ge=MIN_MAX_ATTEMPTS,
        le=MAX_MAX_ATTEMPTS,
        description="How many wrong tries before the challenge is exhausted.",
    )


class ChallengeVerifyRequest(BaseModel):
    challenge_id: str = Field(..., description="From challenge/start.")
    words: list[str] = Field(
        ...,
        description=(
            "Operator answers, one per challenged position, in the same order."
        ),
    )


@router.post("/challenge/start")
async def challenge_start(
    request: Request,
    body: ChallengeStartRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    """Mint a 3-of-24 (or N-of-24) verification challenge.

    Validates the mnemonic via the existing
    :func:`fingerprint_of` first — a wrong word count or bad
    checksum returns HTTP 400 (rather than a useless challenge
    the operator can't pass). The seed words themselves are never
    echoed back; only the **positions** the operator must answer.

    Rate-limited per source IP (default 5 burst + 1 token / 30 s,
    env-tunable via ``TARS_RECOVERY_CHALLENGE_START_BURST`` /
    ``TARS_RECOVERY_CHALLENGE_START_RATE_PER_S``) so a hostile
    client can't exhaust the in-memory challenge store.
    """

    await _enforce_recovery_rate_limit(
        request,
        bucket_id=RECOVERY_CHALLENGE_START_BUCKET,
        route="recovery.challenge.start",
    )

    try:
        challenge = mint_challenge(
            body.mnemonic,
            count=body.count,
            ttl_s=body.ttl_s,
            max_attempts=body.max_attempts,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"invalid_mnemonic: {exc}"
        ) from exc

    get_challenge_store().put(challenge)

    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as trace_id:
        await client.emit(
            "recovery.challenge.started",
            {
                "challenge_id": challenge.challenge_id,
                "fingerprint": challenge.fingerprint,
                "count": len(challenge.positions),
                "ttl_s": int(challenge.expires_at - challenge.issued_at),
                "word_count": WORD_COUNT,
            },
        )
        public = challenge.to_public_dict()
        return {"ok": True, "trace_id": trace_id, "challenge": public}


@router.post("/challenge/verify")
async def challenge_verify(
    request: Request,
    body: ChallengeVerifyRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    """Check the operator's answers against the in-flight challenge.

    Wrong answers decrement ``attempts_remaining``. Exhausted
    attempts mark the challenge consumed. Expired challenges 410
    so the cockpit can re-mint cleanly.

    On success the cockpit can use the returned
    ``recovery.challenge.passed`` event as the gating proof for
    the rotate-identity flow (now consumed by
    :func:`web_extras.routers.pairing.rotate_identity`).

    Rate-limited per source IP (default 10 burst + 1 token / 10 s,
    env-tunable via ``TARS_RECOVERY_CHALLENGE_VERIFY_BURST`` /
    ``TARS_RECOVERY_CHALLENGE_VERIFY_RATE_PER_S``) so brute-forcing
    answers across many challenges costs more than guessing one.
    """

    await _enforce_recovery_rate_limit(
        request,
        bucket_id=RECOVERY_CHALLENGE_VERIFY_BUCKET,
        route="recovery.challenge.verify",
    )

    store = get_challenge_store()
    challenge = store.get(body.challenge_id)
    if challenge is None:
        raise HTTPException(
            status_code=404, detail="challenge_not_found"
        )

    outcome = verify_challenge(challenge, body.words)
    store.put(outcome.challenge)

    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as trace_id:
        if outcome.ok:
            kind = "recovery.challenge.passed"
        elif outcome.error == "expired":
            kind = "recovery.challenge.expired"
        elif outcome.error == "exhausted":
            kind = "recovery.challenge.exhausted"
        else:
            kind = "recovery.challenge.failed"
        await client.emit(
            kind,
            {
                "challenge_id": outcome.challenge.challenge_id,
                "fingerprint": outcome.challenge.fingerprint,
                "matched": list(outcome.matched),
                "attempts_remaining": outcome.challenge.attempts_remaining,
                "status": outcome.challenge.status,
            },
        )
        body_out: dict[str, Any] = {"trace_id": trace_id, **outcome.to_dict()}
        if outcome.error == "expired":
            raise HTTPException(status_code=410, detail=body_out)
        return body_out


@router.get("/challenge/{challenge_id}")
async def challenge_state(challenge_id: str) -> dict[str, Any]:
    """Public-safe state of an in-flight challenge.

    Useful for the cockpit to resume after a refresh: returns
    only ``challenge_id`` / ``fingerprint`` / ``positions`` /
    ``status`` / ``attempts_remaining`` / ``expires_at`` —
    never the words.
    """

    challenge = get_challenge_store().get(challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="challenge_not_found")
    return {"ok": True, "challenge": challenge.to_public_dict()}


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
