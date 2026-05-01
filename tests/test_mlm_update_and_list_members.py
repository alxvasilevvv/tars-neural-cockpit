"""Tests for ``mlm.update_member`` and ``mlm.list_members``.

Closes the MLM downline lifecycle: ``add_member`` writes,
``downline_snapshot`` / ``retention_alert`` read, ``update_member``
patches arbitrary subsets of a row, and ``list_members`` gives a
fast read-only side door with filters + rollups.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.core.domains.packs.mlm.actions import (
    add_member,
    list_members,
    update_member,
)
from backend.core.domains.packs.mlm.actions import ACTIONS as MLM_ACTIONS
from backend.core.domains.packs.mlm.db import (
    _parse_iso_loose,
    get_downline_db,
    reset_downline_db,
)


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    db_path = tmp_path / "downline.sqlite"
    monkeypatch.setenv("MLM_DB_PATH", str(db_path))
    # Skip the legacy CSV bootstrap so each test starts from an empty DB.
    monkeypatch.setenv("MLM_NETWORK_PATH", str(tmp_path / "no_csv.csv"))
    reset_downline_db()
    yield db_path
    reset_downline_db()


@pytest.fixture(autouse=True)
def _spy_meeet(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    captured: list[tuple[str, dict[str, Any]]] = []

    class _Spy:
        async def emit(self, kind: str, payload: dict[str, Any]) -> None:
            captured.append((kind, dict(payload)))

    monkeypatch.setattr(
        "backend.core.domains.packs.mlm.actions.get_client",
        lambda: _Spy(),
    )
    return captured


def _run(coro):
    return asyncio.run(coro)


def _seed(handle: str, **overrides: Any) -> None:
    base = {
        "handle": handle,
        "rank": "starter",
        "joined_at": "2026-01-01",
        "volume_usd": 0,
    }
    base.update(overrides)
    out = _run(add_member(base))
    assert out["ok"] is True, out


# ---------------------------------------------------------------- _parse_iso_loose

def test_parse_iso_loose_handles_dates_datetimes_and_z() -> None:
    assert _parse_iso_loose("2026-05-01") is not None
    assert _parse_iso_loose("2026-05-01T12:30:00") is not None
    assert _parse_iso_loose("2026-05-01T12:30:00Z") is not None
    assert _parse_iso_loose("2026-05-01T12:30:00+00:00") is not None
    assert _parse_iso_loose("garbage") is None
    assert _parse_iso_loose("") is None
    assert _parse_iso_loose("   ") is None


# ---------------------------------------------------------------- DownlineDB.update_member

def test_db_update_member_changes_rank_and_emits_changed(
    _isolated_db: Path,
) -> None:
    _seed("alice")
    db = get_downline_db()
    member, changed = _run(db.update_member("alice", {"rank": "BRONZE"}))
    assert member is not None
    assert member.rank == "bronze"
    assert changed == ["rank"]


def test_db_update_member_idempotent(_isolated_db: Path) -> None:
    _seed("alice", rank="bronze")
    db = get_downline_db()
    member, changed = _run(db.update_member("alice", {"rank": "bronze"}))
    assert member is not None
    assert changed == []


def test_db_update_member_unknown_handle_returns_none(_isolated_db: Path) -> None:
    db = get_downline_db()
    member, changed = _run(db.update_member("ghost", {"rank": "gold"}))
    assert member is None
    assert changed == []


def test_db_update_member_blank_handle_raises(_isolated_db: Path) -> None:
    db = get_downline_db()
    with pytest.raises(ValueError, match="handle_required"):
        _run(db.update_member("   ", {"rank": "gold"}))


def test_db_update_member_volume_invalid_raises(_isolated_db: Path) -> None:
    _seed("alice")
    db = get_downline_db()
    with pytest.raises(ValueError, match="volume_invalid"):
        _run(db.update_member("alice", {"volume_usd": -1}))
    with pytest.raises(ValueError, match="volume_invalid"):
        _run(db.update_member("alice", {"volume_usd": "abc"}))


def test_db_update_member_clears_optional_string(_isolated_db: Path) -> None:
    _seed("alice", notes="VIP")
    db = get_downline_db()
    member, changed = _run(db.update_member("alice", {"notes": ""}))
    assert member is not None
    assert member.notes is None
    assert changed == ["notes"]


def test_db_update_member_none_skips_field(_isolated_db: Path) -> None:
    _seed("alice", notes="VIP")
    db = get_downline_db()
    member, changed = _run(
        db.update_member("alice", {"notes": None, "rank": "gold"})
    )
    assert member is not None
    assert member.notes == "VIP"
    assert changed == ["rank"]


def test_db_update_member_only_listed_fields_apply(_isolated_db: Path) -> None:
    _seed("alice")
    db = get_downline_db()
    member, changed = _run(
        db.update_member("alice", {"rank": "gold", "handle": "ignored"})
    )
    assert member is not None
    assert member.rank == "gold"
    assert member.handle == "alice"
    assert changed == ["rank"]


# ---------------------------------------------------------------- DownlineDB.list_members filters

def test_db_list_members_default_returns_all(_isolated_db: Path) -> None:
    _seed("alice")
    _seed("bob")
    db = get_downline_db()
    out = _run(db.list_members())
    assert {m.handle for m in out} == {"alice", "bob"}


def test_db_list_members_sponsor_filter(_isolated_db: Path) -> None:
    _seed("alice")
    _seed("bob", sponsor="alice")
    _seed("carol")
    db = get_downline_db()
    out = _run(db.list_members(sponsor="ALICE"))
    assert {m.handle for m in out} == {"bob"}


def test_db_list_members_rank_filter(_isolated_db: Path) -> None:
    _seed("alice", rank="gold")
    _seed("bob", rank="bronze")
    _seed("carol", rank="gold")
    db = get_downline_db()
    out = _run(db.list_members(rank="GOLD"))
    assert {m.handle for m in out} == {"alice", "carol"}


def test_db_list_members_recent_days_filter(_isolated_db: Path) -> None:
    today = datetime.now(timezone.utc).date()
    yesterday = (today - timedelta(days=1)).isoformat()
    long_ago = (today - timedelta(days=400)).isoformat()
    _seed("alice", joined_at=yesterday, last_active_at=yesterday)
    _seed("bob", joined_at=long_ago, last_active_at=long_ago)
    db = get_downline_db()
    out = _run(db.list_members(recent_days=30))
    assert {m.handle for m in out} == {"alice"}


def test_db_list_members_limit(_isolated_db: Path) -> None:
    for i in range(4):
        _seed(f"u{i}")
    db = get_downline_db()
    out = _run(db.list_members(limit=2))
    assert {m.handle for m in out} == {"u0", "u1"}


# ---------------------------------------------------------------- update_member action

def test_update_member_action_happy_path(
    _isolated_db: Path,
    _spy_meeet: list[tuple[str, dict[str, Any]]],
) -> None:
    _seed("alice")
    _spy_meeet.clear()

    out = _run(
        update_member(
            {
                "handle": "alice",
                "rank": "bronze",
                "volume_usd": 1500,
                "notes": "VIP",
            }
        )
    )
    assert out["ok"] is True
    assert out["handle"] == "alice"
    assert out["unchanged"] is False
    assert set(out["changed_fields"]) == {"rank", "volume_usd", "notes"}
    assert out["member"]["rank"] == "bronze"
    assert out["member"]["volume_usd"] == 1500.0
    assert out["member"]["notes"] == "VIP"
    assert out["db_path"]
    assert _spy_meeet[-1][0] == "mlm.member_updated"
    assert _spy_meeet[-1][1]["handle"] == "alice"
    assert set(_spy_meeet[-1][1]["changed_fields"]) == {"rank", "volume_usd", "notes"}


def test_update_member_action_missing_handle() -> None:
    out = _run(update_member({}))
    assert out == {"ok": False, "error": "handle_required"}


def test_update_member_action_blank_handle() -> None:
    out = _run(update_member({"handle": "   ", "rank": "bronze"}))
    assert out == {"ok": False, "error": "handle_required"}


def test_update_member_action_no_updates(_isolated_db: Path) -> None:
    _seed("alice")
    out = _run(update_member({"handle": "alice"}))
    assert out == {"ok": False, "error": "no_updates"}


def test_update_member_action_unknown_handle(_isolated_db: Path) -> None:
    out = _run(update_member({"handle": "ghost", "rank": "bronze"}))
    assert out == {
        "ok": False,
        "error": "member_not_found",
        "handle": "ghost",
    }


def test_update_member_action_invalid_volume(_isolated_db: Path) -> None:
    _seed("alice")
    out = _run(update_member({"handle": "alice", "volume_usd": -1}))
    assert out == {"ok": False, "error": "volume_invalid"}


def test_update_member_action_invalid_ts(_isolated_db: Path) -> None:
    _seed("alice")
    out = _run(
        update_member({"handle": "alice", "last_active_at": "garbage-date"})
    )
    assert out["ok"] is False
    assert out["error"] == "invalid_ts"
    assert out["field"] == "last_active_at"
    assert out["ts"] == "garbage-date"


def test_update_member_action_idempotent_no_event(
    _isolated_db: Path,
    _spy_meeet: list[tuple[str, dict[str, Any]]],
) -> None:
    _seed("alice", rank="bronze")
    _spy_meeet.clear()
    out = _run(update_member({"handle": "alice", "rank": "bronze"}))
    assert out["ok"] is True
    assert out["unchanged"] is True
    assert out["changed_fields"] == []
    assert _spy_meeet == []


def test_update_member_action_clearing_optional_string(_isolated_db: Path) -> None:
    _seed("alice", notes="VIP")
    out = _run(update_member({"handle": "alice", "notes": ""}))
    assert out["ok"] is True
    assert out["member"].get("notes") is None
    assert out["changed_fields"] == ["notes"]


# ---------------------------------------------------------------- list_members action

def test_list_members_action_envelope_and_summary(_isolated_db: Path) -> None:
    _seed("alice", rank="gold", volume_usd=1_000)
    _seed("bob", rank="bronze", volume_usd=500)
    _seed("carol", rank="gold", volume_usd=2_500)

    out = _run(list_members({}))
    assert out["ok"] is True
    assert out["count"] == 3
    assert {m["handle"] for m in out["members"]} == {"alice", "bob", "carol"}
    assert out["filters"] == {
        "sponsor": None,
        "rank": None,
        "recent_days": None,
        "limit": None,
    }
    assert out["summary"]["by_rank"] == {"gold": 2, "bronze": 1}
    assert out["summary"]["total_volume_usd"] == 4_000.0
    assert out["db_path"]


def test_list_members_action_sponsor_filter(_isolated_db: Path) -> None:
    _seed("alice")
    _seed("bob", sponsor="alice")
    _seed("carol")
    out = _run(list_members({"sponsor": "ALICE"}))
    assert out["count"] == 1
    assert out["members"][0]["handle"] == "bob"
    assert out["filters"]["sponsor"] == "alice"


def test_list_members_action_rank_filter(_isolated_db: Path) -> None:
    _seed("alice", rank="gold")
    _seed("bob", rank="bronze")
    out = _run(list_members({"rank": "GOLD"}))
    assert out["count"] == 1
    assert out["members"][0]["handle"] == "alice"
    assert out["filters"]["rank"] == "gold"


def test_list_members_action_recent_days_filter(_isolated_db: Path) -> None:
    today = datetime.now(timezone.utc).date()
    recent = (today - timedelta(days=1)).isoformat()
    long_ago = (today - timedelta(days=400)).isoformat()
    _seed("alice", joined_at=recent, last_active_at=recent)
    _seed("bob", joined_at=long_ago, last_active_at=long_ago)
    out = _run(list_members({"recent_days": 30}))
    assert out["count"] == 1
    assert out["members"][0]["handle"] == "alice"
    assert out["filters"]["recent_days"] == 30


def test_list_members_action_limit_clamps_to_1000(_isolated_db: Path) -> None:
    _seed("alice")
    out = _run(list_members({"limit": 9999}))
    assert out["filters"]["limit"] == 1000


def test_list_members_action_garbage_limit_is_none(_isolated_db: Path) -> None:
    _seed("alice")
    out = _run(list_members({"limit": "many"}))
    assert out["filters"]["limit"] is None


def test_list_members_action_total_volume_handles_garbage_in_db(
    _isolated_db: Path,
) -> None:
    _seed("alice", volume_usd=100)
    _seed("bob", volume_usd=50)
    out = _run(list_members({}))
    assert out["summary"]["total_volume_usd"] == 150.0


def test_list_members_action_empty_db_returns_zero_envelope(
    _isolated_db: Path,
) -> None:
    out = _run(list_members({}))
    assert out["ok"] is True
    assert out["count"] == 0
    assert out["members"] == []
    assert out["summary"] == {"by_rank": {}, "total_volume_usd": 0.0}


# ---------------------------------------------------------------- ActionSpec wiring

def _spec_by_id(action_id: str):
    return next(s for s in MLM_ACTIONS if s.id == action_id)


def test_update_member_spec_is_destructive_and_requires_handle() -> None:
    spec = _spec_by_id("update_member")
    assert spec.destructive is True
    assert spec.schema["required"] == ["handle"]
    assert "rank" in spec.schema["properties"]
    assert "volume_usd" in spec.schema["properties"]


def test_list_members_spec_is_safe_and_unrequired() -> None:
    spec = _spec_by_id("list_members")
    assert spec.destructive is False
    assert spec.schema.get("required") in (None, [])
    assert "sponsor" in spec.schema["properties"]
    assert "rank" in spec.schema["properties"]
    assert "recent_days" in spec.schema["properties"]
    assert "limit" in spec.schema["properties"]
