"""In-memory token-bucket rate limiter for HTTP routes.

Backs the "Pairing relay rate-limit" idea from ``docs/IDEAS.md``
(Pairing & sync section) on the host side. The bucket is keyed
by an arbitrary subject string — typically the source IP — and
sweeps stale entries on every read so memory stays bounded
without a background loop.

Why not aiohttp / starlette / slowapi:

- This module sits in the policy lane: it must run on a bare
  Python 3.10+ install, never reach over the network, and
  introduce zero new top-level deps.
- Token bucket is the right algorithm for QR-mint storms —
  it allows short bursts (rapid retries during one pairing
  attempt) while throttling sustained spam.
- The host always owns the truth: the meeet.world relay can
  enforce its own per-IP cap, but the host stops minting fresh
  ``pair_id``s once the bucket runs dry.

Public surface:

- :class:`TokenBucket` — single bucket primitive (capacity +
  refill rate). Pure, no I/O.
- :class:`RateLimiter` — thread-safe registry of buckets keyed
  by subject string with a :func:`acquire` helper that returns
  whether the request is allowed plus telemetry
  (``remaining`` / ``retry_after`` / ``reset_at``).
- :func:`get_rate_limiter` / :func:`reset_rate_limiter` — module
  singleton + test reset.

The HTTP layer is responsible for:

1. Choosing the subject (typically ``request.client.host``,
   falling back to a stable header like ``X-Forwarded-For``
   when behind a trusted proxy).
2. Mapping a denied bucket to an HTTP 429 with
   ``Retry-After`` + structured detail. Helpers in this
   module compute the seconds, the route does the response.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Mapping


@dataclass
class TokenBucket:
    """A single token bucket.

    The bucket starts full; each successful :meth:`acquire`
    consumes one token. Tokens refill at ``rate`` per second up
    to ``capacity``. Negative or zero ``rate`` keeps the bucket
    pinned to its current level (effectively a quota).
    """

    capacity: float
    rate: float
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise ValueError("capacity must be > 0")
        self.tokens = float(self.capacity)
        self.last_refill = time.time()

    def _refill(self, *, now: float) -> None:
        if self.rate <= 0:
            self.last_refill = now
            return
        elapsed = max(0.0, now - self.last_refill)
        if elapsed > 0:
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

    def acquire(self, *, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        self._refill(now=current)
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    def retry_after(self, *, now: float | None = None) -> float:
        """Seconds until the next token will be available.

        Returns ``0.0`` when a token is already available.
        """

        current = time.time() if now is None else now
        self._refill(now=current)
        if self.tokens >= 1.0:
            return 0.0
        if self.rate <= 0:
            # Quota mode: never refills.
            return float("inf")
        return max(0.0, (1.0 - self.tokens) / self.rate)

    def reset_at(self, *, now: float | None = None) -> float:
        """Wall-clock timestamp at which the bucket will be full again."""

        current = time.time() if now is None else now
        self._refill(now=current)
        if self.rate <= 0:
            return current  # Never; surface as "right now" to keep the type stable.
        deficit = max(0.0, self.capacity - self.tokens)
        return current + (deficit / self.rate)


@dataclass(frozen=True)
class RateLimitOutcome:
    """Result of a :meth:`RateLimiter.acquire` call."""

    allowed: bool
    subject: str
    bucket_id: str
    remaining: float
    retry_after: float
    reset_at: float
    capacity: float
    rate: float

    def to_dict(self) -> dict[str, float | str | bool]:
        return {
            "allowed": self.allowed,
            "subject": self.subject,
            "bucket_id": self.bucket_id,
            "remaining": round(self.remaining, 4),
            "retry_after": round(self.retry_after, 4),
            "reset_at": round(self.reset_at, 4),
            "capacity": self.capacity,
            "rate": self.rate,
        }


class RateLimiter:
    """Thread-safe registry of named buckets.

    A "bucket id" is a logical name (e.g. ``"pairing.begin"``)
    paired with an arbitrary subject (e.g. an IP address). The
    pair ``(bucket_id, subject)`` keys exactly one bucket. New
    buckets are minted lazily with the configured capacity and
    refill rate.

    The registry sweeps stale entries (idle longer than
    ``idle_ttl``) on every :meth:`acquire` so memory stays
    bounded without a background loop.
    """

    def __init__(
        self,
        *,
        idle_ttl: float = 600.0,
    ) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[tuple[str, str], TokenBucket] = {}
        self._configs: dict[str, tuple[float, float]] = {}
        self._idle_ttl = max(60.0, idle_ttl)

    def configure(
        self,
        bucket_id: str,
        *,
        capacity: float,
        rate: float,
    ) -> None:
        """Define the (capacity, refill rate) for a logical bucket id.

        ``capacity`` is the burst allowance; ``rate`` is tokens per
        second. ``rate <= 0`` makes the bucket a pure quota that
        never refills (useful for one-shot caps; the bucket will
        only allow ``capacity`` requests over its lifetime).
        """

        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        with self._lock:
            self._configs[bucket_id] = (float(capacity), float(rate))

    def is_configured(self, bucket_id: str) -> bool:
        with self._lock:
            return bucket_id in self._configs

    def configured(self) -> Mapping[str, tuple[float, float]]:
        with self._lock:
            return dict(self._configs)

    def acquire(
        self,
        *,
        bucket_id: str,
        subject: str,
        now: float | None = None,
    ) -> RateLimitOutcome:
        if not subject:
            subject = "__anonymous__"

        current = time.time() if now is None else now

        with self._lock:
            cfg = self._configs.get(bucket_id)
            if cfg is None:
                # Unconfigured buckets allow everything but report a
                # neutral remaining=inf so callers can degrade gracefully.
                return RateLimitOutcome(
                    allowed=True,
                    subject=subject,
                    bucket_id=bucket_id,
                    remaining=float("inf"),
                    retry_after=0.0,
                    reset_at=current,
                    capacity=float("inf"),
                    rate=0.0,
                )
            capacity, rate = cfg
            self._sweep_stale_locked(now=current)
            key = (bucket_id, subject)
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = TokenBucket(capacity=capacity, rate=rate)
                self._buckets[key] = bucket

            allowed = bucket.acquire(now=current)
            remaining = bucket.tokens
            retry = 0.0 if allowed else bucket.retry_after(now=current)
            reset = bucket.reset_at(now=current)

        return RateLimitOutcome(
            allowed=allowed,
            subject=subject,
            bucket_id=bucket_id,
            remaining=remaining,
            retry_after=retry,
            reset_at=reset,
            capacity=capacity,
            rate=rate,
        )

    def reset_subject(self, *, bucket_id: str, subject: str) -> bool:
        """Drop the bucket for a single (bucket_id, subject) pair.

        Returns True when a bucket existed; False otherwise.
        """

        with self._lock:
            return self._buckets.pop((bucket_id, subject), None) is not None

    def reset_bucket(self, bucket_id: str) -> int:
        """Drop every subject's bucket for a logical id."""

        with self._lock:
            keys = [k for k in self._buckets if k[0] == bucket_id]
            for k in keys:
                self._buckets.pop(k, None)
            return len(keys)

    def stats(self) -> Mapping[str, int]:
        with self._lock:
            counts: dict[str, int] = {}
            for bid, _subject in self._buckets:
                counts[bid] = counts.get(bid, 0) + 1
            counts["total"] = len(self._buckets)
            counts["configured"] = len(self._configs)
            return counts

    def _sweep_stale_locked(self, *, now: float) -> None:
        stale: list[tuple[str, str]] = []
        for k, b in self._buckets.items():
            if (now - b.last_refill) <= self._idle_ttl:
                continue
            # Refill (which clamps to capacity) before deciding —
            # otherwise an idle bucket that was partially drained
            # would never get cleaned up.
            b._refill(now=now)
            if b.tokens >= b.capacity:
                stale.append(k)
        for k in stale:
            self._buckets.pop(k, None)


_SINGLETON: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = RateLimiter()
    return _SINGLETON


def reset_rate_limiter() -> None:
    """Test-only helper to reset the module singleton."""

    global _SINGLETON
    _SINGLETON = None


__all__ = [
    "RateLimitOutcome",
    "RateLimiter",
    "TokenBucket",
    "get_rate_limiter",
    "reset_rate_limiter",
]
