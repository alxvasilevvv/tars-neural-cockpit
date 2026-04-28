"""Tests for the SQLite downline DB and the new MLM mutation actions
(Phase H).
"""

from __future__ import annotations

import asyncio
import csv
from pathlib import Path

import pytest

from backend.core.domains import packs as _packs  # noqa: F401
from backend.core.domains.packs.mlm import db as db_module
from backend.core.domains.packs.mlm.actions import (
    add_member,
    downline_snapshot,
    log_activity,
    retention_alert,
)
from backend.core.domains.packs.mlm.db import (
    DownlineDB,
    Member,
    reset_downline_db,
)


def _seed_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["handle", "sponsor", "joined_at", "last_active_at", "rank", "volume_usd"]
        )
        w.writerow(["@root", "", "2025-01-01", "2026-04-26", "gold", "20000"])
        w.writerow(["@anna", "@root", "2025-03-01", "2026-04-25", "silver", "5000"])
        w.writerow(["@oleg", "@root", "2025-02-01", "2026-01-10", "starter", "800"])


def _isolate_db(tmp_path: Path, monkeypatch) -> DownlineDB:
    csv_path = tmp_path / "data" / "mlm_network.csv"
    _seed_csv(csv_path)
    db = DownlineDB(
        db_path=str(tmp_path / "downline.sqlite"),
        csv_seed_path=csv_path,
    )
    # Use monkeypatch so the singleton is restored after each test —
    # otherwise downline_snapshot() in unrelated tests would still see
    # this isolated DB.
    monkeypatch.setattr(db_module, "_SINGLETON", db, raising=False)
    monkeypatch.setattr(
        "backend.core.domains.packs.mlm.actions.get_downline_db", lambda: db
    )
    return db


def test_db_is_empty_on_fresh_create(tmp_path: Path) -> None:
    db = DownlineDB(db_path=str(tmp_path / "x.sqlite"))
    members = asyncio.run(db.list_members())
    assert members == []


def test_db_seeds_from_csv_when_empty(tmp_path: Path, monkeypatch) -> None:
    db = _isolate_db(tmp_path, monkeypatch)

    async def run():
        out = await db.ensure_seeded()
        members = await db.list_members()
        return out, members

    out, members = asyncio.run(run())
    assert out["seeded"] is True
    assert out["inserted"] == 3
    assert {m.handle for m in members} == {"@root", "@anna", "@oleg"}


def test_db_ensure_seeded_idempotent(tmp_path: Path, monkeypatch) -> None:
    db = _isolate_db(tmp_path, monkeypatch)

    async def run():
        first = await db.ensure_seeded()
        second = await db.ensure_seeded()
        return first, second

    first, second = asyncio.run(run())
    assert first["seeded"] is True
    assert second["seeded"] is False
    assert second["members"] == 3


def test_db_upsert_inserts_then_updates(tmp_path: Path) -> None:
    db = DownlineDB(db_path=str(tmp_path / "y.sqlite"))

    async def run():
        ins = await db.upsert(
            {
                "handle": "@x",
                "sponsor": None,
                "rank": "starter",
                "joined_at": "2026-04-28",
                "volume_usd": 100.0,
            }
        )
        upd = await db.upsert(
            {
                "handle": "@x",
                "rank": "bronze",
                "volume_usd": 250.0,
            }
        )
        m = await db.get("@x")
        return ins, upd, m

    ins, upd, m = asyncio.run(run())
    assert ins == "inserted"
    assert upd == "updated"
    assert m is not None and m.rank == "bronze" and m.volume_usd == 250.0


def test_db_upsert_skip_strategy(tmp_path: Path) -> None:
    db = DownlineDB(db_path=str(tmp_path / "z.sqlite"))

    async def run():
        await db.upsert({"handle": "@x", "volume_usd": 100.0})
        out = await db.upsert(
            {"handle": "@x", "volume_usd": 999.0},
            conflict_strategy="skip",
        )
        m = await db.get("@x")
        return out, m

    out, m = asyncio.run(run())
    assert out == "skipped"
    assert m is not None and m.volume_usd == 100.0


def test_db_log_activity_updates_timestamp_and_volume(tmp_path: Path, monkeypatch) -> None:
    db = _isolate_db(tmp_path, monkeypatch)

    async def run():
        await db.ensure_seeded()
        before = await db.get("@anna")
        updated = await db.log_activity(
            "@anna", ts="2026-04-28T12:00:00", volume_delta=750.0
        )
        return before, updated

    before, updated = asyncio.run(run())
    assert before is not None and before.volume_usd == 5000.0
    assert updated is not None
    assert updated.last_active_at == "2026-04-28T12:00:00"
    assert updated.volume_usd == 5750.0


def test_db_log_activity_unknown_returns_none(tmp_path: Path, monkeypatch) -> None:
    db = _isolate_db(tmp_path, monkeypatch)

    async def run():
        await db.ensure_seeded()
        return await db.log_activity("@nobody", volume_delta=1.0)

    assert asyncio.run(run()) is None


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------


def test_downline_snapshot_uses_sqlite(tmp_path: Path, monkeypatch) -> None:
    _isolate_db(tmp_path, monkeypatch)

    out = asyncio.run(downline_snapshot({}))
    assert out["ok"] is True
    assert out["source"] == "sqlite"
    assert out["total"] == 3
    by_handle = {m["handle"]: m for m in out["members"]}
    assert by_handle["@anna"]["sponsor"] == "@root"


def test_retention_alert_uses_sqlite(tmp_path: Path, monkeypatch) -> None:
    _isolate_db(tmp_path, monkeypatch)
    out = asyncio.run(retention_alert({"threshold_days": 30}))
    assert out["ok"] is True
    assert out["source"] == "sqlite"
    handles = {a["handle"] for a in out["at_risk"]}
    # @oleg last active 2026-01-10 → ~108 days silent → flagged.
    assert "@oleg" in handles


def test_add_member_requires_handle(tmp_path: Path, monkeypatch) -> None:
    _isolate_db(tmp_path, monkeypatch)
    out = asyncio.run(add_member({}))
    assert out["ok"] is False
    assert out["error"] == "handle_required"


def test_add_member_requires_existing_sponsor(tmp_path: Path, monkeypatch) -> None:
    _isolate_db(tmp_path, monkeypatch)
    out = asyncio.run(add_member({"handle": "@x", "sponsor": "@nope"}))
    assert out["ok"] is False
    assert out["error"] == "sponsor_not_found"


def test_add_member_inserts_and_log_activity(tmp_path: Path, monkeypatch) -> None:
    _isolate_db(tmp_path, monkeypatch)

    async def run():
        out_add = await add_member(
            {
                "handle": "@nina",
                "sponsor": "@anna",
                "rank": "bronze",
                "volume_usd": 0,
            }
        )
        out_log = await log_activity(
            {"handle": "@nina", "volume_delta": 1500.0}
        )
        snap = await downline_snapshot({})
        return out_add, out_log, snap

    out_add, out_log, snap = asyncio.run(run())
    assert out_add["ok"] is True and out_add["outcome"] == "inserted"
    assert out_log["ok"] is True and out_log["volume_usd"] == 1500.0
    by_handle = {m["handle"]: m for m in snap["members"]}
    assert "@nina" in by_handle
    assert by_handle["@nina"]["volume_usd"] == 1500.0
    # Newly logged activity → counts as active in the default 14-day window.
    assert by_handle["@nina"]["active"] is True


def test_log_activity_unknown_handle(tmp_path: Path, monkeypatch) -> None:
    _isolate_db(tmp_path, monkeypatch)
    out = asyncio.run(log_activity({"handle": "@ghost"}))
    assert out["ok"] is False
    assert out["error"] == "member_not_found"


def test_log_activity_rejects_invalid_ts(tmp_path: Path, monkeypatch) -> None:
    _isolate_db(tmp_path, monkeypatch)
    out = asyncio.run(log_activity({"handle": "@anna", "ts": "yesterday"}))
    assert out["ok"] is False
    assert out["error"] == "invalid_ts"


def test_destructive_flags_on_new_actions() -> None:
    from backend.core.domains.registry import get_pack

    pack = get_pack("mlm")
    assert pack is not None
    by_id = {a.id: a for a in pack.actions()}
    assert by_id["add_member"].destructive is True
    assert by_id["log_activity"].destructive is True
    assert by_id["downline_snapshot"].destructive is False
