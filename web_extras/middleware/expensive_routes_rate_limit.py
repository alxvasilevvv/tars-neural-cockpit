"""Per-IP rate limiter for expensive cloud-touching endpoints.

Bug #4 fix from ``docs/SYSTEM_AUDIT_2026-05-02.md``. The audit
found that :class:`web_extras.rate_limit.RateLimiter` was wired
into 2 of 22 routers (pairing + recovery) — leaving the
expensive cloud-touching endpoints (chat / planner / voice /
council) with no per-IP throttle. A burst of cloud-LLM calls
from one client could starve every other operator (and inflate
the bill before the entitlements gate kicks in).

This middleware adds a generic per-IP token-bucket throttle on
the four high-cost endpoint patterns. It runs *before* the
entitlements gate so abusive clients hit 429 first instead of
burning through the cap and getting 402 (which is "your money's
gone" — the wrong message for a brute-force scenario).

Defaults are tuned for an interactive single-operator cockpit:
- 30 req / minute burst, 10 req / minute sustained for chat
  (assistant turns) and planner runs.
- 60 req / minute burst, 20 req / minute sustained for voice
  (TTS is short-lived, multiple per turn is normal).
- 12 req / minute burst, 4 req / minute sustained for council
  (deliberations are heavy and rare).

All thresholds are env-overridable so ops can dial them up for
shared deployments.

Why a middleware (not a per-router decorator):

- One source of truth for the route → bucket mapping.
- Easier to expand to additional routes (just add a pattern to
  ``EXPENSIVE_ROUTES``).
- Test surface stays one file.
- The pattern matches the existing CORS / errors install style
  — wired once in ``web_extras.app``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.core.meeet import get_client
from web_extras.rate_limit import get_rate_limiter


@dataclass(frozen=True)
class ExpensiveRoute:
    """One throttled route.

    Patterns are anchored python regexes against ``request.url.path``.
    ``methods`` filters the HTTP verb so e.g. ``GET /api/chat`` is
    never throttled — only the assistant-turn POST.
    """

    bucket_id: str
    method: str
    pattern: re.Pattern[str]
    capacity_default: float
    rate_per_minute_default: float
    capacity_env: str
    rate_per_minute_env: str

    def matches(self, *, method: str, path: str) -> bool:
        if method.upper() != self.method.upper():
            return False
        return bool(self.pattern.match(path))


def _make_route(
    *,
    bucket_id: str,
    method: str,
    pattern: str,
    capacity_default: float,
    rate_per_minute_default: float,
) -> ExpensiveRoute:
    env_prefix = "TARS_RATE_LIMIT_" + bucket_id.upper().replace(".", "_")
    return ExpensiveRoute(
        bucket_id=bucket_id,
        method=method,
        pattern=re.compile(pattern),
        capacity_default=capacity_default,
        rate_per_minute_default=rate_per_minute_default,
        capacity_env=f"{env_prefix}_BURST",
        rate_per_minute_env=f"{env_prefix}_PER_MINUTE",
    )


# Each bucket id is unique. The path patterns are deliberately
# narrow — match only the high-cost endpoint, never the listing
# endpoints that share the same prefix (e.g. ``GET /api/chat`` is
# fine; only ``POST /api/chat/threads/{id}/messages`` is throttled).
EXPENSIVE_ROUTES: tuple[ExpensiveRoute, ...] = (
    _make_route(
        bucket_id="chat.post_message",
        method="POST",
        pattern=r"^/api/chat/threads/[^/]+/messages/?$",
        capacity_default=30.0,
        rate_per_minute_default=10.0,
    ),
    _make_route(
        bucket_id="planner.run",
        method="POST",
        pattern=r"^/api/planner/[^/]+/run/?$",
        capacity_default=30.0,
        rate_per_minute_default=10.0,
    ),
    _make_route(
        bucket_id="voice.speak",
        method="POST",
        pattern=r"^/api/voice/speak/?$",
        capacity_default=60.0,
        rate_per_minute_default=20.0,
    ),
    _make_route(
        bucket_id="council.deliberate",
        method="POST",
        pattern=r"^/api/council/deliberate/?$",
        capacity_default=12.0,
        rate_per_minute_default=4.0,
    ),
    # Wave 79 security audit — Whisper STT is one of the most
    # expensive cloud surfaces (~$0.006/min against OpenAI). Without
    # a throttle a single client could push thousands of audio
    # uploads through the loopback before the operator notices the
    # bill. 20/min sustained matches a chatty dictation session;
    # 30/min burst absorbs short retry storms.
    _make_route(
        bucket_id="voice.transcribe",
        method="POST",
        pattern=r"^/api/voice/transcribe/?$",
        capacity_default=30.0,
        rate_per_minute_default=20.0,
    ),
    # Wave 79 — smart-router LLM classifier. Each call hits the
    # configured chat provider with a small prompt; cheap per-call
    # but trivial to weaponise from a tab full of cockpit clones.
    _make_route(
        bucket_id="agents.route",
        method="POST",
        pattern=r"^/api/agents/route/?$",
        capacity_default=30.0,
        rate_per_minute_default=15.0,
    ),
    # Wave 79 — AI Clone draft endpoint also hits the cloud LLM
    # with the operator's style examples appended. Same bucket
    # shape as agents.route.
    _make_route(
        bucket_id="clone.draft",
        method="POST",
        pattern=r"^/api/clone/draft/?$",
        capacity_default=20.0,
        rate_per_minute_default=10.0,
    ),
    # Wave 98 -- outreach drafting also hits the cloud LLM (per-recipient
    # email body generation in the operator's voice). 30/min burst,
    # 20/min sustained matches a thoughtful ops session (one campaign
    # of ~20 LPs in a single sitting) without leaking budget on a
    # tab-spam scenario.
    _make_route(
        bucket_id="outreach.draft",
        method="POST",
        pattern=r"^/api/outreach/drafts/?$",
        capacity_default=30.0,
        rate_per_minute_default=20.0,
    ),
    # Wave 98 -- outreach send is the cumulative daily-cap. The bucket
    # capacity is the daily budget (50 sends / day default; the safety
    # layer enforces this independently against the SQLite store, the
    # bucket is the second line of defence at the HTTP edge). Per-
    # minute drip is set so a normal one-by-one approval pace
    # (5 s between sends in the campaign loop) flows through.
    _make_route(
        bucket_id="outreach.send",
        method="POST",
        pattern=r"^/api/outreach/drafts/[^/]+/send/?$",
        capacity_default=50.0,
        rate_per_minute_default=12.0,
    ),
)


def _f_env(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _is_enabled() -> bool:
    """Env kill switch. Defaults ON.

    Set ``TARS_RATE_LIMIT_EXPENSIVE=off`` (or 0/false) to bypass
    the middleware entirely — useful for tests, local dev, or
    self-hosted single-operator boxes that don't need throttling.
    """

    raw = (os.getenv("TARS_RATE_LIMIT_EXPENSIVE") or "").strip().lower()
    if raw in {"off", "0", "false", "no", "disabled"}:
        return False
    return True


def _client_subject(request: Request) -> str:
    """Best-effort subject extraction for the limiter.

    Honours ``X-Forwarded-For`` when running behind a trusted proxy
    (controlled via env), falling back to ``request.client.host``,
    falling back to ``__anonymous__`` (which keeps memory bounded —
    every unidentifiable client shares one bucket so a single bad
    actor can't blow up the registry by spoofing addresses).
    """

    if os.getenv("TARS_TRUST_FORWARDED_FOR", "0") in ("1", "true", "yes"):
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            # First entry is the original client per RFC 7239.
            head = xff.split(",")[0].strip()
            if head:
                return head
    if request.client is not None:
        return request.client.host or "__anonymous__"
    return "__anonymous__"


def _configure_buckets_once() -> None:
    """Push every expensive-route bucket into the global limiter.

    Idempotent — :meth:`RateLimiter.configure` overwrites the same
    bucket id, so re-calling this on hot-reload picks up env
    changes without restarting the host.
    """

    limiter = get_rate_limiter()
    for route in EXPENSIVE_ROUTES:
        capacity = max(1.0, _f_env(route.capacity_env, route.capacity_default))
        per_minute = max(0.0, _f_env(route.rate_per_minute_env, route.rate_per_minute_default))
        # Token bucket rate is per-second; users configure per-minute
        # because that's how SaaS quotas usually read.
        rate_per_s = per_minute / 60.0
        limiter.configure(route.bucket_id, capacity=capacity, rate=rate_per_s)


class ExpensiveRoutesRateLimitMiddleware(BaseHTTPMiddleware):
    """Apply per-IP token-bucket throttle to expensive routes.

    The middleware iterates ``EXPENSIVE_ROUTES`` and, for the first
    match, asks the global :class:`RateLimiter` whether the
    request is allowed. On a deny it returns a 429 with a
    ``Retry-After`` header and the canonical TARS error envelope
    (``error_code="rate_limited"``).
    """

    def __init__(self, app, *, routes: Iterable[ExpensiveRoute] = EXPENSIVE_ROUTES) -> None:
        super().__init__(app)
        self._routes = tuple(routes)
        # Configure on first construction; safe to call again at
        # request time too (idempotent).
        _configure_buckets_once()

    async def dispatch(self, request: Request, call_next):
        if not _is_enabled():
            return await call_next(request)

        method = request.method.upper()
        path = request.url.path or "/"

        match: ExpensiveRoute | None = None
        for r in self._routes:
            if r.matches(method=method, path=path):
                match = r
                break

        if match is None:
            return await call_next(request)

        # Re-apply env config on every request — cheap (one dict
        # write) and lets ops bump the bucket without a restart.
        _configure_buckets_once()

        subject = _client_subject(request)
        outcome = get_rate_limiter().acquire(
            bucket_id=match.bucket_id, subject=subject
        )

        if outcome.allowed:
            return await call_next(request)

        # ``retry_after`` can be ``+inf`` for pure-quota buckets
        # (rate <= 0). Cap at ``86400`` (24 h) so the header is
        # always a valid integer per RFC 7231.
        retry_after = outcome.retry_after
        if not retry_after or retry_after != retry_after:  # NaN check
            retry_after = 1.0
        if retry_after == float("inf"):
            retry_after = 86400.0
        retry_seconds = max(1, int(retry_after) + 1)

        # Best-effort emission to meeet for the dashboard. Never
        # raise — limiter behaviour must be deterministic even if
        # the bridge is down.
        try:
            await get_client().emit(
                "rate_limit.denied",
                {
                    "subject": outcome.subject,
                    "bucket_id": outcome.bucket_id,
                    "retry_after_s": retry_seconds,
                    "remaining": outcome.remaining,
                    "method": method,
                    "path": path,
                },
            )
        except Exception:
            pass

        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_seconds)},
            content={
                "ok": False,
                "error_code": "rate_limited",
                "message": (
                    f"rate_limited: {match.bucket_id} bucket exhausted "
                    f"for {outcome.subject}; retry in {retry_seconds}s"
                ),
                "detail": (
                    f"rate_limited: {match.bucket_id} bucket exhausted "
                    f"for {outcome.subject}; retry in {retry_seconds}s"
                ),
                "hint": (
                    "Reduce request rate or set TARS_RATE_LIMIT_"
                    f"{match.bucket_id.upper().replace('.', '_')}_PER_MINUTE "
                    "/ _BURST higher for trusted deployments."
                ),
                "context": {
                    "bucket_id": outcome.bucket_id,
                    "retry_after_s": retry_seconds,
                    "remaining": round(outcome.remaining, 4),
                    "capacity": outcome.capacity,
                    "rate_per_minute": round(outcome.rate * 60.0, 4),
                },
            },
        )


def install_expensive_routes_rate_limit(app) -> None:
    """Convenience wrapper for :mod:`web_extras.app` to one-line install."""

    app.add_middleware(ExpensiveRoutesRateLimitMiddleware)


__all__ = [
    "EXPENSIVE_ROUTES",
    "ExpensiveRoute",
    "ExpensiveRoutesRateLimitMiddleware",
    "install_expensive_routes_rate_limit",
]
