"""Tests for the ``daily_brief`` × ``log_deal`` closed loop.

When the operator logs a deal via ``business.log_deal`` without a
CRM key, the row lands in a local JSON store (PR landed earlier
on 2026-05-01). ``daily_brief`` now unions that store with the
bundled snapshot so the brief reflects what was logged after the
snapshot was taken.

The union prefers the local row when ids collide (operator's
latest action wins). Brand-new local ids append.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.core.domains.packs.business import actions as business_actions


@pytest.fixture
def isolated_brief(tmp_path, monkeypatch):
    """Prevent the test from picking up real ``~/.tars/`` data and
    point ``daily_brief`` at deterministic tmp paths.

    Returns a small helper bag with the resolved paths so each test
    can write whatever fixture data it needs.
    """

    bundled = tmp_path / "bundled-deals.json"
    local = tmp_path / "local-deals.json"
    kpi = tmp_path / "kpi.json"
    cal = tmp_path / "cal.json"

    # Disable the env override so the action falls back to our
    # tmp paths via the kwargs.
    monkeypatch.delenv("TARS_LOCAL_DEALS_PATH", raising=False)
    monkeypatch.delenv("BUSINESS_DEALS_PATH", raising=False)
    monkeypatch.delenv("BUSINESS_KPI_PATH", raising=False)
    monkeypatch.delenv("CALENDAR_PATH", raising=False)

    return {
        "tmp": tmp_path,
        "bundled": bundled,
        "local": local,
        "kpi": kpi,
        "cal": cal,
    }


def _write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _run_brief(args):
    return asyncio.run(business_actions.daily_brief(args))


# ---------------------------------------------------------------------
# Union behaviour
# ---------------------------------------------------------------------


def test_daily_brief_unions_local_deals_when_both_exist(isolated_brief):
    _write(
        isolated_brief["bundled"],
        [
            {"id": "d-001", "name": "Bundled", "amount": 1000, "stage": "discovery"}
        ],
    )
    _write(
        isolated_brief["local"],
        [
            {
                "id": "local-0001",
                "name": "Operator-logged",
                "amount": 5000,
                "stage": "proposal",
            }
        ],
    )

    out = _run_brief(
        {
            "kpi_path": str(isolated_brief["kpi"]),
            "deals_path": str(isolated_brief["bundled"]),
            "local_deals_path": str(isolated_brief["local"]),
            "calendar_path": str(isolated_brief["cal"]),
            "council": False,
        }
    )

    assert out["ok"] is True
    assert out["deals_total"] == 2
    assert out["deals_local_logged"] == 1
    names = [a["name"] for a in out["actions"]]
    assert "Bundled" in names
    assert "Operator-logged" in names
    assert "local-store" in out["sources"]


def test_daily_brief_local_only_when_bundled_missing(isolated_brief):
    _write(
        isolated_brief["local"],
        [
            {
                "id": "local-0001",
                "name": "OnlyLocal",
                "amount": 9000,
                "stage": "negotiation",
            }
        ],
    )

    out = _run_brief(
        {
            "kpi_path": str(isolated_brief["kpi"]),
            "deals_path": str(isolated_brief["tmp"] / "bundled-missing.json"),
            "local_deals_path": str(isolated_brief["local"]),
            "calendar_path": str(isolated_brief["cal"]),
            "council": False,
        }
    )

    assert out["deals_total"] == 1
    assert out["deals_local_logged"] == 1
    assert out["actions"][0]["name"] == "OnlyLocal"


def test_daily_brief_no_local_when_local_path_missing(isolated_brief):
    _write(
        isolated_brief["bundled"],
        [
            {"id": "d-001", "name": "Bundled", "amount": 1000, "stage": "discovery"}
        ],
    )

    out = _run_brief(
        {
            "kpi_path": str(isolated_brief["kpi"]),
            "deals_path": str(isolated_brief["bundled"]),
            "local_deals_path": str(isolated_brief["tmp"] / "missing-local.json"),
            "calendar_path": str(isolated_brief["cal"]),
            "council": False,
        }
    )

    assert out["deals_total"] == 1
    assert out["deals_local_logged"] == 0
    assert "local-store" not in out["sources"]


def test_daily_brief_local_collision_overwrites_bundled(isolated_brief):
    """When a local row carries the same id as a bundled row the
    local payload wins (operator's most recent action)."""

    _write(
        isolated_brief["bundled"],
        [
            {
                "id": "d-001",
                "name": "Old amount",
                "amount": 1000,
                "stage": "discovery",
            }
        ],
    )
    _write(
        isolated_brief["local"],
        [
            {
                "id": "d-001",
                "name": "Old amount",
                "amount": 9999,
                "stage": "negotiation",
            }
        ],
    )

    out = _run_brief(
        {
            "kpi_path": str(isolated_brief["kpi"]),
            "deals_path": str(isolated_brief["bundled"]),
            "local_deals_path": str(isolated_brief["local"]),
            "calendar_path": str(isolated_brief["cal"]),
            "council": False,
        }
    )

    assert out["deals_total"] == 1
    target = next(a for a in out["actions"] if a["deal_id"] == "d-001")
    assert target["amount"] == 9999
    assert target["stage"] == "negotiation"
    assert out["deals_local_logged"] == 0  # not a 'local-' prefix


def test_daily_brief_local_corrupted_falls_back_silently(isolated_brief):
    _write(
        isolated_brief["bundled"],
        [{"id": "d-001", "name": "B", "amount": 1, "stage": "discovery"}],
    )
    isolated_brief["local"].write_text("not json", encoding="utf-8")

    out = _run_brief(
        {
            "kpi_path": str(isolated_brief["kpi"]),
            "deals_path": str(isolated_brief["bundled"]),
            "local_deals_path": str(isolated_brief["local"]),
            "calendar_path": str(isolated_brief["cal"]),
            "council": False,
        }
    )

    assert out["ok"] is True
    assert out["deals_total"] == 1


def test_daily_brief_include_local_false_skips_union(isolated_brief):
    _write(
        isolated_brief["bundled"],
        [{"id": "d-001", "name": "B", "amount": 1, "stage": "discovery"}],
    )
    _write(
        isolated_brief["local"],
        [
            {
                "id": "local-0001",
                "name": "L",
                "amount": 1,
                "stage": "discovery",
            }
        ],
    )

    out = _run_brief(
        {
            "kpi_path": str(isolated_brief["kpi"]),
            "deals_path": str(isolated_brief["bundled"]),
            "local_deals_path": str(isolated_brief["local"]),
            "calendar_path": str(isolated_brief["cal"]),
            "council": False,
            "include_local_deals": False,
        }
    )

    assert out["deals_total"] == 1
    assert out["deals_local_logged"] == 0
    assert "local-store" not in out["sources"]


def test_daily_brief_local_path_falls_back_to_env(isolated_brief, monkeypatch):
    """When ``local_deals_path`` arg is omitted the action should
    honour ``TARS_LOCAL_DEALS_PATH``."""

    _write(
        isolated_brief["bundled"],
        [{"id": "d-001", "name": "B", "amount": 1, "stage": "discovery"}],
    )
    _write(
        isolated_brief["local"],
        [
            {
                "id": "local-0001",
                "name": "FromEnv",
                "amount": 1,
                "stage": "discovery",
            }
        ],
    )
    monkeypatch.setenv("TARS_LOCAL_DEALS_PATH", str(isolated_brief["local"]))

    out = _run_brief(
        {
            "kpi_path": str(isolated_brief["kpi"]),
            "deals_path": str(isolated_brief["bundled"]),
            "calendar_path": str(isolated_brief["cal"]),
            "council": False,
        }
    )

    assert out["deals_total"] == 2
    assert out["deals_local_logged"] == 1
    assert out["local_deals_path"] == str(isolated_brief["local"])


def test_daily_brief_same_path_as_bundled_does_not_double_load(isolated_brief):
    """If the operator points local_deals_path at the same file as
    deals_path we mustn't load it twice and inflate the count."""

    _write(
        isolated_brief["bundled"],
        [
            {"id": "d-001", "name": "Single", "amount": 1, "stage": "discovery"}
        ],
    )

    out = _run_brief(
        {
            "kpi_path": str(isolated_brief["kpi"]),
            "deals_path": str(isolated_brief["bundled"]),
            "local_deals_path": str(isolated_brief["bundled"]),
            "calendar_path": str(isolated_brief["cal"]),
            "council": False,
        }
    )
    assert out["deals_total"] == 1


# ---------------------------------------------------------------------
# Schema wiring
# ---------------------------------------------------------------------


def test_daily_brief_schema_documents_local_deals_path():
    spec = next(
        a for a in business_actions.ACTIONS if a.id == "daily_brief"
    )
    props = spec.schema["properties"]
    assert "local_deals_path" in props
    assert "include_local_deals" in props
    assert props["include_local_deals"]["type"] == "boolean"


# ---------------------------------------------------------------------
# log_deal → daily_brief end-to-end (the real "closed loop" test)
# ---------------------------------------------------------------------


def test_log_deal_then_daily_brief_includes_logged_row(
    isolated_brief, monkeypatch
):
    monkeypatch.delenv("HUBSPOT_API_KEY", raising=False)
    monkeypatch.delenv("PIPEDRIVE_API_KEY", raising=False)
    monkeypatch.setenv("TARS_LOCAL_DEALS_PATH", str(isolated_brief["local"]))

    _write(
        isolated_brief["bundled"],
        [
            {"id": "d-001", "name": "Bundled", "amount": 1000, "stage": "discovery"}
        ],
    )

    asyncio.run(
        business_actions.log_deal(
            {
                "name": "Closed loop",
                "amount": 2500,
                "stage": "qualification",
            }
        )
    )

    out = _run_brief(
        {
            "kpi_path": str(isolated_brief["kpi"]),
            "deals_path": str(isolated_brief["bundled"]),
            "calendar_path": str(isolated_brief["cal"]),
            "council": False,
        }
    )

    assert out["deals_total"] == 2
    assert out["deals_local_logged"] == 1
    names = [a["name"] for a in out["actions"]]
    assert "Closed loop" in names
