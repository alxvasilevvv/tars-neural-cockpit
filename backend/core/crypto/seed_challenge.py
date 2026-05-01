"""3-of-24 recovery-seed verification challenge.

Backs the "Recovery seed verification policy" idea from
``docs/IDEAS.md`` (Pairing & sync). On rotation flows, asking the
operator to retype the **entire** 24-word phrase is high-friction
and bug-prone. Asking them to confirm three random word
**positions** (e.g. "what's word #7? word #14? word #22?") balances
friction against a meaningful proof-of-knowledge signal.

The module is a pure-stdlib state machine so it can sit safely in
the policy lane without pulling new deps:

- :class:`SeedChallenge` — one in-flight challenge:
  ``challenge_id`` (urlsafe random), ``fingerprint`` of the seed
  (no plaintext), ``positions`` (1-indexed selection over the 24
  words), ``ttl_s`` / ``expires_at``, ``attempts_remaining``,
  ``status`` (``pending`` / ``passed`` / ``failed`` /
  ``expired`` / ``exhausted``).
- :func:`mint_challenge` — accept a mnemonic, validate it, pick
  ``count`` random positions, return the public-safe shape with
  the position list (the words themselves stay in the operator's
  head + paper, never echoed back).
- :func:`verify_challenge` — accept the in-flight challenge and a
  parallel list of operator answers, return whether the proof
  matched. Wrong answers decrement ``attempts_remaining``;
  exhausted attempts mark the challenge consumed.
- :class:`SeedChallengeStore` — thread-safe in-memory dict with
  expiry-aware lookup. Persistence is intentionally out of scope:
  challenges are short-lived (default 5 min) and tied to a single
  cockpit session.

The store sweeps expired entries on every read to keep memory
bounded without a separate background loop.

Trace-friendly: the public payloads carry only the
``challenge_id`` + the 12-char ``fingerprint`` of the seed (same
shape as ``recovery.shown`` / ``recovery.verified`` events) so we
can correlate without ever exposing the words.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from .recovery import WORD_COUNT, fingerprint_of


DEFAULT_CHALLENGE_COUNT = 3
MIN_CHALLENGE_COUNT = 1
MAX_CHALLENGE_COUNT = 8

DEFAULT_TTL_S = 300        # 5 minutes
MIN_TTL_S = 30
MAX_TTL_S = 1800           # 30 minutes hard cap

DEFAULT_MAX_ATTEMPTS = 3
MIN_MAX_ATTEMPTS = 1
MAX_MAX_ATTEMPTS = 10


_VALID_STATUSES: frozenset[str] = frozenset(
    {"pending", "passed", "failed", "expired", "exhausted", "consumed"}
)


@dataclass(frozen=True)
class SeedChallenge:
    """One in-flight challenge.

    The seed words live only in the operator's memory; this object
    stores the **positions** that were asked (so the verifier can
    cross-check answers) plus the seed fingerprint (so we can audit
    which seed is being challenged without revealing it).
    """

    challenge_id: str
    fingerprint: str
    positions: tuple[int, ...]
    expected_words: tuple[str, ...]  # only used by the verifier
    expires_at: float
    attempts_remaining: int
    issued_at: float
    status: str = "pending"

    def to_public_dict(self) -> dict:
        """Operator-facing shape — never echoes the expected words.

        ``positions`` is 1-indexed so the cockpit can render
        "word #7" without an off-by-one stumble.
        """

        return {
            "challenge_id": self.challenge_id,
            "fingerprint": self.fingerprint,
            "positions": list(self.positions),
            "expires_at": self.expires_at,
            "attempts_remaining": self.attempts_remaining,
            "status": self.status,
            "issued_at": self.issued_at,
            "word_count": WORD_COUNT,
        }


@dataclass(frozen=True)
class VerifyOutcome:
    """Result of a :func:`verify_challenge` attempt."""

    ok: bool
    challenge: SeedChallenge
    matched: tuple[bool, ...]  # per-position result, mirrors challenge.positions
    error: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict:
        body: dict = {
            "ok": self.ok,
            "challenge_id": self.challenge.challenge_id,
            "fingerprint": self.challenge.fingerprint,
            "matched": list(self.matched),
            "attempts_remaining": self.challenge.attempts_remaining,
            "status": self.challenge.status,
            "expires_at": self.challenge.expires_at,
        }
        if self.error is not None:
            body["error"] = self.error
        if self.detail is not None:
            body["detail"] = self.detail
        return body


@dataclass(frozen=True)
class ConsumeOutcome:
    """Result of :func:`consume_passed_challenge`.

    Reports whether the requested challenge was a fresh ``passed``
    proof tied to the expected fingerprint. On success the embedded
    ``challenge`` carries ``status="consumed"`` so the same proof
    can never be replayed against a second destructive action.
    """

    ok: bool
    challenge: SeedChallenge | None
    error: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict:
        body: dict = {"ok": self.ok}
        if self.challenge is not None:
            body["challenge_id"] = self.challenge.challenge_id
            body["fingerprint"] = self.challenge.fingerprint
            body["status"] = self.challenge.status
        if self.error is not None:
            body["error"] = self.error
        if self.detail is not None:
            body["detail"] = self.detail
        return body


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _normalise_words(mnemonic: str) -> tuple[str, ...]:
    """Lowercase + strip whitespace; raise ValueError on wrong word count."""

    parts = mnemonic.strip().lower().split()
    if len(parts) != WORD_COUNT:
        raise ValueError(
            f"recovery_seed_word_count: expected {WORD_COUNT} words, got {len(parts)}"
        )
    return tuple(parts)


def _clamp(value: int, *, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _new_id() -> str:
    return f"chal_{secrets.token_urlsafe(8)}"


# ---------------------------------------------------------------------
# Mint / verify
# ---------------------------------------------------------------------


def mint_challenge(
    mnemonic: str,
    *,
    count: int = DEFAULT_CHALLENGE_COUNT,
    ttl_s: int = DEFAULT_TTL_S,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    rng: secrets.SystemRandom | None = None,
    now: float | None = None,
) -> SeedChallenge:
    """Mint a fresh challenge against ``mnemonic``.

    Validates the mnemonic via :func:`fingerprint_of` (which raises
    on invalid checksum / unknown word / wrong length) before
    picking positions, so a typo never produces a challenge that
    can't be passed.

    ``count`` is clamped to ``[1, 8]`` and defaults to 3 — three
    positions out of 24 produce a meaningful ~0.001 chance of a
    blind guess, while staying low-friction.

    ``ttl_s`` is clamped to ``[30, 1800]``; ``max_attempts`` is
    clamped to ``[1, 10]``.

    The expected word list is stored on the challenge for the
    verifier; it's never returned to the operator.
    """

    words = _normalise_words(mnemonic)
    fingerprint = fingerprint_of(" ".join(words))

    n = _clamp(count, lo=MIN_CHALLENGE_COUNT, hi=MAX_CHALLENGE_COUNT)
    ttl = _clamp(ttl_s, lo=MIN_TTL_S, hi=MAX_TTL_S)
    attempts = _clamp(
        max_attempts, lo=MIN_MAX_ATTEMPTS, hi=MAX_MAX_ATTEMPTS
    )

    rng = rng or secrets.SystemRandom()
    sample = sorted(rng.sample(range(1, WORD_COUNT + 1), n))
    positions = tuple(sample)
    expected = tuple(words[p - 1] for p in positions)

    issued = now if now is not None else time.time()
    return SeedChallenge(
        challenge_id=_new_id(),
        fingerprint=fingerprint,
        positions=positions,
        expected_words=expected,
        expires_at=issued + ttl,
        attempts_remaining=attempts,
        issued_at=issued,
        status="pending",
    )


def verify_challenge(
    challenge: SeedChallenge,
    answers: Iterable[str],
    *,
    now: float | None = None,
) -> VerifyOutcome:
    """Compare ``answers`` to ``challenge.expected_words`` 1:1.

    Returns a :class:`VerifyOutcome` whose embedded ``challenge``
    is updated with the new ``status`` and ``attempts_remaining``.
    Inputs are normalised (lowercase + strip) so a stray uppercase
    doesn't cost an attempt.

    Status transitions:

    - ``pending`` + match           → ``passed``
    - ``pending`` + miss + retries  → ``pending`` (decrement)
    - ``pending`` + miss + exhausted → ``exhausted``
    - ``pending`` + expired         → ``expired``

    Once a challenge is not ``pending`` further verify calls
    return ``ok=False`` with a structured error.
    """

    current = now if now is not None else time.time()

    if challenge.status != "pending":
        return VerifyOutcome(
            ok=False,
            challenge=challenge,
            matched=tuple(False for _ in challenge.positions),
            error="not_pending",
            detail=f"challenge already {challenge.status!r}",
        )

    if current >= challenge.expires_at:
        expired = SeedChallenge(
            challenge_id=challenge.challenge_id,
            fingerprint=challenge.fingerprint,
            positions=challenge.positions,
            expected_words=challenge.expected_words,
            expires_at=challenge.expires_at,
            attempts_remaining=challenge.attempts_remaining,
            issued_at=challenge.issued_at,
            status="expired",
        )
        return VerifyOutcome(
            ok=False,
            challenge=expired,
            matched=tuple(False for _ in challenge.positions),
            error="expired",
        )

    answers_norm = tuple(str(a).strip().lower() for a in answers)
    if len(answers_norm) != len(challenge.positions):
        return VerifyOutcome(
            ok=False,
            challenge=challenge,
            matched=tuple(False for _ in challenge.positions),
            error="answer_count_mismatch",
            detail=(
                f"expected {len(challenge.positions)} answers, "
                f"got {len(answers_norm)}"
            ),
        )

    matched = tuple(
        a == w for a, w in zip(answers_norm, challenge.expected_words)
    )
    if all(matched):
        passed = SeedChallenge(
            challenge_id=challenge.challenge_id,
            fingerprint=challenge.fingerprint,
            positions=challenge.positions,
            expected_words=challenge.expected_words,
            expires_at=challenge.expires_at,
            attempts_remaining=challenge.attempts_remaining,
            issued_at=challenge.issued_at,
            status="passed",
        )
        return VerifyOutcome(
            ok=True,
            challenge=passed,
            matched=matched,
        )

    new_remaining = challenge.attempts_remaining - 1
    new_status = "exhausted" if new_remaining <= 0 else "pending"
    failed = SeedChallenge(
        challenge_id=challenge.challenge_id,
        fingerprint=challenge.fingerprint,
        positions=challenge.positions,
        expected_words=challenge.expected_words,
        expires_at=challenge.expires_at,
        attempts_remaining=max(0, new_remaining),
        issued_at=challenge.issued_at,
        status=new_status,
    )
    return VerifyOutcome(
        ok=False,
        challenge=failed,
        matched=matched,
        error="word_mismatch" if new_status == "pending" else "exhausted",
    )


def consume_passed_challenge(
    store: "SeedChallengeStore",
    challenge_id: str,
    *,
    expected_fingerprint: str | None = None,
    now: float | None = None,
) -> ConsumeOutcome:
    """Atomically transition a ``passed`` challenge to ``consumed``.

    A passed challenge is a one-shot proof: the operator demonstrated
    knowledge of the seed once, so subsequent destructive actions
    against the same fingerprint must mint and pass a *fresh*
    challenge. Without this transition a single proof could be
    replayed forever (e.g. rotate identity → rotate again →
    revoke → …).

    Returns :class:`ConsumeOutcome` with structured ``error`` codes
    suitable for an HTTP 4xx envelope:

    - ``challenge_not_found``    → unknown id or evicted by sweep.
    - ``fingerprint_mismatch``   → caller pinned a different seed.
    - ``challenge_not_passed``   → status is anything other than
      ``passed`` (``pending`` / ``failed`` / ``expired`` /
      ``exhausted`` / ``consumed``).
    """

    current = now if now is not None else time.time()
    with store._lock:
        challenge = store._by_id.get(challenge_id)
        if challenge is None:
            return ConsumeOutcome(
                ok=False,
                challenge=None,
                error="challenge_not_found",
            )
        if (
            expected_fingerprint is not None
            and challenge.fingerprint != expected_fingerprint
        ):
            return ConsumeOutcome(
                ok=False,
                challenge=challenge,
                error="fingerprint_mismatch",
                detail=(
                    "challenge fingerprint does not match the requested "
                    "destructive action's expected seed"
                ),
            )
        if challenge.status != "passed":
            return ConsumeOutcome(
                ok=False,
                challenge=challenge,
                error="challenge_not_passed",
                detail=f"status is {challenge.status!r}, must be 'passed'",
            )

        consumed = SeedChallenge(
            challenge_id=challenge.challenge_id,
            fingerprint=challenge.fingerprint,
            positions=challenge.positions,
            expected_words=challenge.expected_words,
            expires_at=challenge.expires_at,
            attempts_remaining=challenge.attempts_remaining,
            issued_at=challenge.issued_at,
            status="consumed",
        )
        store._by_id[challenge.challenge_id] = consumed
        _ = current  # intentionally unused; reserved for future TTL semantics
        return ConsumeOutcome(ok=True, challenge=consumed)


# ---------------------------------------------------------------------
# In-memory store (one challenge per challenge_id)
# ---------------------------------------------------------------------


@dataclass
class SeedChallengeStore:
    """Thread-safe in-memory store with expiry-aware reads.

    Challenges are short-lived (default 5 min) and tied to a single
    cockpit session, so SQLite persistence would be overkill. The
    store sweeps expired entries on every read so memory stays
    bounded without a separate background loop.
    """

    _by_id: dict[str, SeedChallenge] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def put(self, challenge: SeedChallenge) -> SeedChallenge:
        with self._lock:
            self._by_id[challenge.challenge_id] = challenge
        return challenge

    def get(self, challenge_id: str, *, now: float | None = None) -> SeedChallenge | None:
        current = now if now is not None else time.time()
        self._sweep_locked_or_unlocked(current)
        with self._lock:
            return self._by_id.get(challenge_id)

    def consume(self, challenge_id: str) -> SeedChallenge | None:
        """Pop a challenge id (no-op if missing)."""

        with self._lock:
            return self._by_id.pop(challenge_id, None)

    def list(self, *, now: float | None = None) -> tuple[SeedChallenge, ...]:
        current = now if now is not None else time.time()
        self._sweep_locked_or_unlocked(current)
        with self._lock:
            return tuple(self._by_id.values())

    def stats(self, *, now: float | None = None) -> Mapping[str, int]:
        current = now if now is not None else time.time()
        self._sweep_locked_or_unlocked(current)
        with self._lock:
            counts: dict[str, int] = {}
            for c in self._by_id.values():
                counts[c.status] = counts.get(c.status, 0) + 1
            counts["total"] = len(self._by_id)
            return counts

    def clear(self) -> None:
        with self._lock:
            self._by_id.clear()

    def _sweep_locked_or_unlocked(self, now: float) -> None:
        with self._lock:
            stale = [
                cid
                for cid, c in self._by_id.items()
                if c.status in {"passed", "exhausted", "expired", "consumed"}
                and (now - c.issued_at) >= 3600  # keep terminal records 1h
            ]
            for cid in stale:
                self._by_id.pop(cid, None)
            still_pending: list[str] = []
            for cid, c in self._by_id.items():
                if c.status == "pending" and now >= c.expires_at:
                    still_pending.append(cid)
            for cid in still_pending:
                old = self._by_id[cid]
                self._by_id[cid] = SeedChallenge(
                    challenge_id=old.challenge_id,
                    fingerprint=old.fingerprint,
                    positions=old.positions,
                    expected_words=old.expected_words,
                    expires_at=old.expires_at,
                    attempts_remaining=old.attempts_remaining,
                    issued_at=old.issued_at,
                    status="expired",
                )


_SINGLETON: SeedChallengeStore | None = None


def get_challenge_store() -> SeedChallengeStore:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = SeedChallengeStore()
    return _SINGLETON


def reset_challenge_store() -> None:
    """Test-only helper to reset the module singleton."""

    global _SINGLETON
    _SINGLETON = None


__all__ = [
    "DEFAULT_CHALLENGE_COUNT",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_TTL_S",
    "MAX_CHALLENGE_COUNT",
    "MAX_MAX_ATTEMPTS",
    "MAX_TTL_S",
    "MIN_CHALLENGE_COUNT",
    "MIN_MAX_ATTEMPTS",
    "MIN_TTL_S",
    "ConsumeOutcome",
    "SeedChallenge",
    "SeedChallengeStore",
    "VerifyOutcome",
    "consume_passed_challenge",
    "get_challenge_store",
    "mint_challenge",
    "reset_challenge_store",
    "verify_challenge",
]
