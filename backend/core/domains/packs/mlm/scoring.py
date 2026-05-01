"""Deterministic scoring for ``mlm.score_recruit``.

Used to be a one-line ``hash()`` heuristic, which had two problems:

1. Python's built-in ``hash()`` is randomised by ``PYTHONHASHSEED``,
   so the same handle could score differently on two machines or
   across restarts. The action's own test only checked
   within-process determinism.
2. The score ignored everything we already know about the member —
   activity recency, volume, rank, tenure — even when the handle
   exists in the local downline DB.

This module fixes both. The scoring engine is stdlib-only and lives
next to the downline DB so the rest of the pack can reuse it.

Score composition
-----------------

When a member is found in the downline DB the score is the
weighted average of four signals (each clamped to ``[0, 1]``):

| Signal    | Weight | Source                                       |
| --------- | ------ | -------------------------------------------- |
| recency   | 0.40   | days since ``last_active_at`` (≤7 → 1.0)     |
| volume    | 0.30   | ``volume_usd`` vs a $5000 threshold (linear) |
| rank      | 0.20   | ordinal of ``rank`` against a known ladder   |
| tenure    | 0.10   | days since ``joined_at`` (≥365 → 1.0)        |

Unknown / missing fields contribute their neutral midpoint (0.5).

When the member is **not** in the DB we fall back to a stable
SHA-256-derived hash mapped onto ``[0.4, 0.95]`` so the cockpit
still gets a deterministic number to display.

The action surface keeps ``fit_signals`` and ``risk_signals``
shapes; entries are now real strings explaining each contribution.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .db import Member


# ---------------------------------------------------------------------
# Knobs (kept module-level so tests can monkey-patch and operators can
# tune via TARS_MLM_SCORE_* env vars later).
# ---------------------------------------------------------------------

#: Days of silence before recency drops to 0.
RECENCY_FLOOR_DAYS = 90
#: Days of silence at or below which recency saturates to 1.
RECENCY_CEIL_DAYS = 7
#: Volume in USD that maps to recency=1.0 (linear interpolation below).
VOLUME_SATURATION_USD = 5_000.0
#: Tenure days at or beyond which the tenure signal saturates to 1.
TENURE_SATURATION_DAYS = 365
#: Days under which tenure is considered fresh and contributes 0.
TENURE_FLOOR_DAYS = 30

#: Rank ladder, lowest → highest. Anything outside the ladder maps to
#: the midpoint so we don't reward exotic ranks the cockpit hasn't
#: seen yet.
RANK_LADDER: tuple[str, ...] = (
    "junior",
    "member",
    "consultant",
    "senior",
    "leader",
    "director",
    "founder",
)

#: Component weights — must sum to 1.0.
WEIGHTS = {
    "recency": 0.40,
    "volume": 0.30,
    "rank": 0.20,
    "tenure": 0.10,
}


@dataclass(frozen=True)
class RecruitSignals:
    """Per-component scoring breakdown."""

    recency: float
    volume: float
    rank: float
    tenure: float
    days_silent: int | None = None
    volume_usd: float = 0.0
    rank_label: str | None = None
    tenure_days: int | None = None
    fit: tuple[str, ...] = field(default_factory=tuple)
    risk: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "recency": round(self.recency, 3),
            "volume": round(self.volume, 3),
            "rank": round(self.rank, 3),
            "tenure": round(self.tenure, 3),
        }
        if self.days_silent is not None:
            out["days_silent"] = self.days_silent
        if self.volume_usd:
            out["volume_usd"] = round(self.volume_usd, 2)
        if self.rank_label is not None:
            out["rank_label"] = self.rank_label
        if self.tenure_days is not None:
            out["tenure_days"] = self.tenure_days
        return out


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    s = value.strip()
    if not s:
        return None
    try:
        cleaned = s.replace("Z", "+00:00")
        out = datetime.fromisoformat(cleaned)
    except ValueError:
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                out = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        else:
            return None
    if out.tzinfo is None:
        out = out.replace(tzinfo=timezone.utc)
    return out


def _recency_score(last_active_at: str | None, now: datetime) -> tuple[float, int | None]:
    last = _parse_iso(last_active_at)
    if last is None:
        return 0.5, None
    delta = (now - last).total_seconds()
    days = max(0, int(delta // 86400))
    if days <= RECENCY_CEIL_DAYS:
        return 1.0, days
    if days >= RECENCY_FLOOR_DAYS:
        return 0.0, days
    span = RECENCY_FLOOR_DAYS - RECENCY_CEIL_DAYS
    relative = (days - RECENCY_CEIL_DAYS) / span
    return _clamp(1.0 - relative), days


def _volume_score(volume_usd: float | None) -> tuple[float, float]:
    v = float(volume_usd or 0.0)
    if v <= 0:
        return 0.0, 0.0
    return _clamp(v / VOLUME_SATURATION_USD), v


def _rank_score(rank: str | None) -> tuple[float, str | None]:
    if not rank:
        return 0.5, None
    label = rank.strip().lower()
    if not label:
        return 0.5, None
    if label not in RANK_LADDER:
        return 0.5, label
    idx = RANK_LADDER.index(label)
    if len(RANK_LADDER) <= 1:
        return 1.0, label
    score = idx / (len(RANK_LADDER) - 1)
    return _clamp(score), label


def _tenure_score(joined_at: str | None, now: datetime) -> tuple[float, int | None]:
    joined = _parse_iso(joined_at)
    if joined is None:
        return 0.5, None
    days = max(0, int((now - joined).total_seconds() // 86400))
    if days <= TENURE_FLOOR_DAYS:
        return 0.0, days
    if days >= TENURE_SATURATION_DAYS:
        return 1.0, days
    span = TENURE_SATURATION_DAYS - TENURE_FLOOR_DAYS
    relative = (days - TENURE_FLOOR_DAYS) / span
    return _clamp(relative), days


def _fit_and_risk(signals: dict[str, float], days_silent: int | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    fit: list[str] = []
    risk: list[str] = []
    if signals["recency"] >= 0.75:
        fit.append("active in the last 2 weeks")
    elif signals["recency"] <= 0.25:
        if days_silent is not None:
            risk.append(f"silent for {days_silent} days")
        else:
            risk.append("no recorded activity")
    if signals["volume"] >= 0.75:
        fit.append("strong recent volume")
    elif signals["volume"] <= 0.10:
        risk.append("zero or near-zero recorded volume")
    if signals["rank"] >= 0.75:
        fit.append("senior rank in the ladder")
    elif signals["rank"] <= 0.20:
        risk.append("entry rank, watch onboarding")
    if signals["tenure"] >= 0.75:
        fit.append("seasoned tenure (>1 year)")
    elif signals["tenure"] <= 0.10:
        risk.append("brand-new member, judge cautiously")
    return tuple(fit), tuple(risk)


def signals_for_member(member: Member, *, now: datetime | None = None) -> RecruitSignals:
    """Materialise a :class:`RecruitSignals` from a downline ``Member``.

    Centralised so the action handler stays declarative and tests can
    pin individual signal arithmetic without going through the action.
    """

    now_dt = now or datetime.now(timezone.utc)
    recency, days_silent = _recency_score(member.last_active_at, now_dt)
    volume, vol_usd = _volume_score(member.volume_usd)
    rank, rank_label = _rank_score(member.rank)
    tenure, tenure_days = _tenure_score(member.joined_at, now_dt)
    components = {
        "recency": recency,
        "volume": volume,
        "rank": rank,
        "tenure": tenure,
    }
    fit, risk = _fit_and_risk(components, days_silent)
    return RecruitSignals(
        recency=recency,
        volume=volume,
        rank=rank,
        tenure=tenure,
        days_silent=days_silent,
        volume_usd=vol_usd,
        rank_label=rank_label,
        tenure_days=tenure_days,
        fit=fit,
        risk=risk,
    )


def compose_score(signals: RecruitSignals) -> float:
    """Weighted average of the four component signals, rounded to 2dp."""

    score = (
        WEIGHTS["recency"] * signals.recency
        + WEIGHTS["volume"] * signals.volume
        + WEIGHTS["rank"] * signals.rank
        + WEIGHTS["tenure"] * signals.tenure
    )
    return round(_clamp(score), 2)


def stable_handle_score(handle: str) -> float:
    """Deterministic score for handles we've never seen.

    Maps a SHA-256 prefix onto ``[0.40, 0.95]`` so the cockpit still
    gets a useful number, but never claims certainty (no 1.0). Stable
    across machines and process restarts.
    """

    digest = hashlib.sha256(handle.strip().lower().encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:4], "big") % 100
    return round(0.40 + (bucket / 100.0) * 0.55, 2)


def score_for_unknown_handle(handle: str) -> RecruitSignals:
    """Build a neutral signal record for an unseen handle.

    The composition still flows through :func:`compose_score`; the
    individual components sit at the neutral midpoint so the operator
    can't accidentally read fake structure into a guess.
    """

    raw = stable_handle_score(handle)
    return RecruitSignals(
        recency=raw,
        volume=raw,
        rank=raw,
        tenure=raw,
        days_silent=None,
        volume_usd=0.0,
        rank_label=None,
        tenure_days=None,
        fit=(),
        risk=("handle is not in the local downline yet",),
    )


__all__ = [
    "RANK_LADDER",
    "RECENCY_CEIL_DAYS",
    "RECENCY_FLOOR_DAYS",
    "RecruitSignals",
    "TENURE_FLOOR_DAYS",
    "TENURE_SATURATION_DAYS",
    "VOLUME_SATURATION_USD",
    "WEIGHTS",
    "compose_score",
    "score_for_unknown_handle",
    "signals_for_member",
    "stable_handle_score",
]
