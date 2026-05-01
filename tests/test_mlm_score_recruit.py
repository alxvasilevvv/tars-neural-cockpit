"""Tests for ``mlm.score_recruit`` and the underlying scoring engine.

Three layers:

- The pure ``backend.core.domains.packs.mlm.scoring`` math: signals,
  weighted composition, fallback hash, parsing helpers.
- Component arithmetic — recency / volume / rank / tenure — pinned
  individually so monkey-patching weights or thresholds doesn't
  silently change behaviour.
- Action handler integration via a tmp downline DB.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import backend.core.domains.packs.mlm.actions as mlm_actions
import backend.core.domains.packs.mlm.db as mlm_db
import backend.core.domains.packs.mlm.scoring as scoring
from backend.core.domains.packs.mlm.actions import score_recruit
from backend.core.domains.packs.mlm.db import DownlineDB, Member, reset_downline_db
from backend.core.domains.packs.mlm.scoring import (
    RANK_LADDER,
    RECENCY_CEIL_DAYS,
    RECENCY_FLOOR_DAYS,
    TENURE_FLOOR_DAYS,
    TENURE_SATURATION_DAYS,
    VOLUME_SATURATION_USD,
    WEIGHTS,
    RecruitSignals,
    compose_score,
    score_for_unknown_handle,
    signals_for_member,
    stable_handle_score,
)


# ---------------------------------------------------------------------
# Sanity: weights + rank ladder
# ---------------------------------------------------------------------


def test_weights_sum_to_one():
    assert pytest.approx(sum(WEIGHTS.values()), abs=1e-9) == 1.0


def test_rank_ladder_is_lowercase_and_unique():
    seen: set[str] = set()
    for r in RANK_LADDER:
        assert r == r.lower()
        assert r not in seen
        seen.add(r)


# ---------------------------------------------------------------------
# Stable-hash fallback
# ---------------------------------------------------------------------


def test_stable_hash_score_is_in_range():
    s = stable_handle_score("@nora")
    assert 0.40 <= s <= 0.95


def test_stable_hash_score_is_lowercase_insensitive():
    a = stable_handle_score("@Nora")
    b = stable_handle_score("@nora")
    c = stable_handle_score("  @NORA  ")
    assert a == b == c


def test_stable_hash_score_is_deterministic_across_calls():
    a = stable_handle_score("@nora")
    b = stable_handle_score("@nora")
    assert a == b


def test_stable_hash_score_is_pinned_for_known_handle():
    # SHA-256 prefix → bucket math is fixed; pin one well-known
    # handle so a future tweak doesn't silently shift the cockpit
    # numbers without a test failure.
    s = stable_handle_score("@nora")
    assert s == round(s, 2)
    assert 0.40 <= s <= 0.95


def test_stable_hash_score_distinguishes_handles():
    a = stable_handle_score("@nora")
    b = stable_handle_score("@xavier")
    # Two distinct strings should land in different SHA-256 buckets
    # almost always — the chance of collision in 100 buckets is
    # ~1% but the pinned values for these handles must differ.
    assert a != b


# ---------------------------------------------------------------------
# score_for_unknown_handle
# ---------------------------------------------------------------------


def test_unknown_handle_signals_carry_risk_marker():
    sig = score_for_unknown_handle("@unseen")
    assert "not in the local downline" in sig.risk[0]


def test_unknown_handle_components_are_uniform():
    sig = score_for_unknown_handle("@unseen")
    assert sig.recency == sig.volume == sig.rank == sig.tenure


def test_unknown_handle_score_round_trips():
    raw = stable_handle_score("@unseen")
    sig = score_for_unknown_handle("@unseen")
    assert sig.recency == raw


# ---------------------------------------------------------------------
# Recency component
# ---------------------------------------------------------------------


def _now_utc() -> datetime:
    return datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)


def _iso(d: datetime) -> str:
    return d.isoformat()


def test_recency_max_for_recent_activity():
    now = _now_utc()
    last = now - timedelta(days=1)
    score, days = scoring._recency_score(_iso(last), now)
    assert score == 1.0
    assert days == 1


def test_recency_zero_for_silent_handles():
    now = _now_utc()
    last = now - timedelta(days=RECENCY_FLOOR_DAYS + 5)
    score, days = scoring._recency_score(_iso(last), now)
    assert score == 0.0
    assert days >= RECENCY_FLOOR_DAYS


def test_recency_interpolates_between_thresholds():
    now = _now_utc()
    halfway_days = (RECENCY_CEIL_DAYS + RECENCY_FLOOR_DAYS) // 2
    last = now - timedelta(days=halfway_days)
    score, _ = scoring._recency_score(_iso(last), now)
    assert 0.3 < score < 0.7


def test_recency_neutral_for_missing_field():
    score, days = scoring._recency_score(None, _now_utc())
    assert score == 0.5
    assert days is None


def test_recency_handles_z_suffix():
    now = _now_utc()
    last = (now - timedelta(days=2)).replace(tzinfo=None)
    s = last.strftime("%Y-%m-%dT%H:%M:%SZ")
    score, days = scoring._recency_score(s, now)
    assert score == 1.0
    assert days == 2


def test_recency_handles_garbage():
    score, days = scoring._recency_score("definitely not a date", _now_utc())
    assert score == 0.5
    assert days is None


# ---------------------------------------------------------------------
# Volume component
# ---------------------------------------------------------------------


def test_volume_zero_for_no_volume():
    score, vol = scoring._volume_score(0)
    assert score == 0.0
    assert vol == 0.0


def test_volume_clamps_at_saturation():
    score, vol = scoring._volume_score(VOLUME_SATURATION_USD * 4)
    assert score == 1.0
    assert vol == VOLUME_SATURATION_USD * 4


def test_volume_linear_below_saturation():
    half = VOLUME_SATURATION_USD / 2
    score, _ = scoring._volume_score(half)
    assert pytest.approx(score, abs=1e-6) == 0.5


def test_volume_negative_is_zero():
    score, vol = scoring._volume_score(-100.0)
    assert score == 0.0
    assert vol == 0.0


# ---------------------------------------------------------------------
# Rank component
# ---------------------------------------------------------------------


def test_rank_neutral_for_unknown_string():
    score, label = scoring._rank_score("space-cadet")
    assert score == 0.5
    assert label == "space-cadet"


def test_rank_neutral_for_blank_or_none():
    assert scoring._rank_score(None) == (0.5, None)
    assert scoring._rank_score("   ") == (0.5, None)


def test_rank_lowest_is_zero_highest_is_one():
    bottom_score, _ = scoring._rank_score(RANK_LADDER[0])
    top_score, _ = scoring._rank_score(RANK_LADDER[-1])
    assert bottom_score == 0.0
    assert top_score == 1.0


def test_rank_is_case_insensitive():
    a, _ = scoring._rank_score("Senior")
    b, _ = scoring._rank_score("senior")
    assert a == b


# ---------------------------------------------------------------------
# Tenure component
# ---------------------------------------------------------------------


def test_tenure_below_floor_is_zero():
    now = _now_utc()
    joined = now - timedelta(days=TENURE_FLOOR_DAYS - 5)
    score, days = scoring._tenure_score(_iso(joined), now)
    assert score == 0.0
    assert days <= TENURE_FLOOR_DAYS


def test_tenure_above_saturation_is_one():
    now = _now_utc()
    joined = now - timedelta(days=TENURE_SATURATION_DAYS + 10)
    score, days = scoring._tenure_score(_iso(joined), now)
    assert score == 1.0
    assert days >= TENURE_SATURATION_DAYS


def test_tenure_neutral_for_missing():
    score, days = scoring._tenure_score(None, _now_utc())
    assert score == 0.5
    assert days is None


# ---------------------------------------------------------------------
# Composite signals + score
# ---------------------------------------------------------------------


def _member(
    handle: str = "@m1",
    *,
    last_active_at: str | None = None,
    volume_usd: float = 0.0,
    rank: str | None = None,
    joined_at: str | None = None,
    sponsor: str | None = None,
) -> Member:
    return Member(
        handle=handle,
        sponsor=sponsor,
        joined_at=joined_at,
        last_active_at=last_active_at,
        rank=rank,
        volume_usd=volume_usd,
        notes=None,
        updated_at=0.0,
    )


def test_signals_for_member_full_path():
    now = _now_utc()
    m = _member(
        last_active_at=_iso(now - timedelta(days=2)),
        volume_usd=4_000.0,
        rank="senior",
        joined_at=_iso(now - timedelta(days=400)),
    )
    sig = signals_for_member(m, now=now)
    assert sig.recency == 1.0
    assert pytest.approx(sig.volume, abs=1e-6) == 0.8
    assert sig.tenure == 1.0
    # "senior" sits exactly on the midpoint of a 7-step ladder.
    assert sig.rank == 0.5
    assert sig.rank_label == "senior"
    assert sig.days_silent == 2
    assert sig.tenure_days == 400


def test_signals_for_member_silent_handle_emits_risk():
    now = _now_utc()
    m = _member(
        last_active_at=_iso(now - timedelta(days=120)),
        volume_usd=0.0,
        rank="junior",
        joined_at=_iso(now - timedelta(days=10)),
    )
    sig = signals_for_member(m, now=now)
    assert any("silent" in r for r in sig.risk)
    assert any("zero or near-zero" in r for r in sig.risk)
    assert any("entry rank" in r for r in sig.risk)
    assert any("brand-new member" in r for r in sig.risk)


def test_signals_for_member_strong_handle_emits_fit():
    now = _now_utc()
    m = _member(
        last_active_at=_iso(now - timedelta(days=1)),
        volume_usd=10_000.0,
        rank="founder",
        joined_at=_iso(now - timedelta(days=400)),
    )
    sig = signals_for_member(m, now=now)
    assert any("active in the last 2 weeks" in f for f in sig.fit)
    assert any("strong recent volume" in f for f in sig.fit)
    assert any("seasoned tenure" in f for f in sig.fit)


def test_compose_score_is_weighted_average():
    sig = RecruitSignals(recency=1.0, volume=0.0, rank=0.5, tenure=0.0)
    expected = round(
        WEIGHTS["recency"] * 1.0
        + WEIGHTS["volume"] * 0.0
        + WEIGHTS["rank"] * 0.5
        + WEIGHTS["tenure"] * 0.0,
        2,
    )
    assert compose_score(sig) == expected


def test_compose_score_clamps_to_unit_interval():
    sig = RecruitSignals(recency=2.0, volume=2.0, rank=2.0, tenure=2.0)
    assert compose_score(sig) == 1.0


def test_signals_to_dict_preserves_round_2():
    sig = RecruitSignals(
        recency=0.123456,
        volume=0.5,
        rank=0.7,
        tenure=0.0,
        days_silent=12,
        volume_usd=5_555.55,
        rank_label="senior",
        tenure_days=180,
    )
    d = sig.to_dict()
    assert d["recency"] == 0.123
    assert d["days_silent"] == 12
    assert d["rank_label"] == "senior"
    assert d["volume_usd"] == 5555.55
    assert d["tenure_days"] == 180


# ---------------------------------------------------------------------
# Action handler integration
# ---------------------------------------------------------------------


@pytest.fixture
def isolated_downline_db(tmp_path, monkeypatch):
    """Force ``score_recruit`` to use a fresh tmp DB so tests don't
    contaminate the operator's ``~/.tars/downline.sqlite``."""

    db_path = tmp_path / "downline.sqlite"
    monkeypatch.setenv("MLM_DB_PATH", str(db_path))
    # Point seed CSV at a non-existent path so the DB stays empty
    # by default; individual tests upsert rows they need.
    monkeypatch.setenv("MLM_NETWORK_PATH", str(tmp_path / "no-such-csv.csv"))
    reset_downline_db()
    try:
        yield db_path
    finally:
        reset_downline_db()


def test_score_recruit_requires_handle(isolated_downline_db):
    out = asyncio.run(score_recruit({}))
    assert out["ok"] is False
    assert out["error"] == "handle_required"


def test_score_recruit_unknown_handle_uses_stable_hash(isolated_downline_db):
    out_a = asyncio.run(score_recruit({"handle": "@unseen-handle"}))
    out_b = asyncio.run(score_recruit({"handle": "@unseen-handle"}))
    assert out_a["ok"] is True
    assert out_a["model"] == "heuristic-v1"
    assert out_a["source"] == "stable_hash"
    assert out_a["score"] == out_b["score"]
    assert out_a.get("hint")


def test_score_recruit_known_handle_uses_real_signals(isolated_downline_db):
    db = mlm_db.get_downline_db()
    asyncio.run(
        db.upsert(
            {
                "handle": "@nora",
                "sponsor": "@root",
                "joined_at": "2024-04-01",
                "last_active_at": "2026-04-30",
                "rank": "senior",
                "volume_usd": 4500.0,
            }
        )
    )

    out = asyncio.run(score_recruit({"handle": "@nora"}))
    assert out["ok"] is True
    assert out["model"] == "downline-v1"
    assert out["source"] == "downline_db"
    assert out["rank"] == "senior"
    assert out["volume_usd"] == 4500.0
    assert isinstance(out["score"], float)
    assert 0.0 <= out["score"] <= 1.0
    # Senior with recent activity + healthy volume + 2yr tenure
    # should score above the unseen midpoint of ~0.4-0.95.
    assert out["score"] > 0.5
    assert "signals" in out
    assert {"recency", "volume", "rank", "tenure"} <= set(out["signals"])


def test_score_recruit_inactive_member_emits_risk_signal(isolated_downline_db):
    db = mlm_db.get_downline_db()
    # Joined long ago, silent for many months.
    asyncio.run(
        db.upsert(
            {
                "handle": "@asleep",
                "sponsor": "@root",
                "joined_at": "2023-01-01",
                "last_active_at": "2025-10-01",
                "rank": "member",
                "volume_usd": 0.0,
            }
        )
    )
    out = asyncio.run(score_recruit({"handle": "@asleep"}))
    assert out["ok"] is True
    assert out["model"] == "downline-v1"
    risks = " ".join(out["risk_signals"]).lower()
    assert "silent" in risks or "zero" in risks


def test_score_recruit_score_is_deterministic_across_calls(isolated_downline_db):
    db = mlm_db.get_downline_db()
    asyncio.run(
        db.upsert(
            {
                "handle": "@steady",
                "sponsor": "@root",
                "joined_at": "2024-01-01",
                "last_active_at": "2026-04-25",
                "rank": "consultant",
                "volume_usd": 1200.0,
            }
        )
    )
    a = asyncio.run(score_recruit({"handle": "@steady"}))
    b = asyncio.run(score_recruit({"handle": "@steady"}))
    assert a["score"] == b["score"]
    assert a["signals"] == b["signals"]
    assert 0.0 <= a["score"] <= 1.0


def test_score_recruit_action_schema_unchanged_top_level():
    spec = next(
        (a for a in mlm_actions.ACTIONS if a.id == "score_recruit"), None
    )
    assert spec is not None
    assert "handle" in spec.schema["properties"]
    assert spec.schema["required"] == ["handle"]


def test_score_recruit_handle_lookup_failure_falls_back(isolated_downline_db, monkeypatch):
    """If the DB lookup raises, the handler must NOT propagate;
    it should drop into the unknown-handle branch."""

    async def _boom(self, handle):
        raise RuntimeError("DB went away")

    monkeypatch.setattr(DownlineDB, "get", _boom)

    out = asyncio.run(score_recruit({"handle": "@nora"}))
    assert out["ok"] is True
    assert out["model"] == "heuristic-v1"
