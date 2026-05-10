"""Tests for the W4-PR2 lab action handlers (HTTP surface).

These exercise the same code-path the cockpit / playbooks /
external MCP clients hit through the standard
`/api/domains/algotrade/actions/<id>/invoke` envelope.

We don't go through the HTTP layer here — the action handlers
are pure async functions over a Mapping arg, so we call them
directly. End-to-end through FastAPI is covered by the domain
router tests.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from backend.core.algotrade.exec import reset_runtime
from backend.core.algotrade.lab import reset_lab_store
from backend.core.domains.packs.algotrade.lab_actions import (
    LAB_ACTIONS,
    lab_attendee_snapshot_action,
    lab_create_workshop_action,
    lab_enroll_attendee_action,
    lab_leaderboard_action,
    lab_list_attendees_action,
    lab_list_workshops_action,
    lab_set_workshop_status_action,
)


@pytest.fixture
def tars_home():
    with tempfile.TemporaryDirectory() as tmp:
        old = os.environ.get("TARS_ALGOTRADE_HOME")
        os.environ["TARS_ALGOTRADE_HOME"] = tmp
        reset_runtime()
        reset_lab_store()
        try:
            yield Path(tmp)
        finally:
            reset_runtime()
            reset_lab_store()
            if old is None:
                del os.environ["TARS_ALGOTRADE_HOME"]
            else:
                os.environ["TARS_ALGOTRADE_HOME"] = old


def _run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------- pack surface


def test_lab_actions_are_registered() -> None:
    ids = [a.id for a in LAB_ACTIONS]
    assert ids == [
        "lab_create_workshop",
        "lab_list_workshops",
        "lab_set_workshop_status",
        "lab_enroll_attendee",
        "lab_list_attendees",
        "lab_leaderboard",
        "lab_attendee_snapshot",
    ]
    # Mutating actions must be flagged destructive so the gate
    # / playbook scheduler can route them through confirmation.
    destructive = {a.id for a in LAB_ACTIONS if a.destructive}
    assert destructive == {
        "lab_create_workshop",
        "lab_set_workshop_status",
        "lab_enroll_attendee",
    }


# --------------------------------------------------------- create


def test_create_workshop_requires_name(tars_home: Path) -> None:
    res = _run(lab_create_workshop_action({}))
    assert res["ok"] is False
    assert res["error"] == "missing_name"


def test_create_workshop_returns_workshop_dict(tars_home: Path) -> None:
    res = _run(
        lab_create_workshop_action(
            {
                "name": "Cresco — Day 1",
                "facilitator": "alex",
                "metadata": {"venue": "remote"},
            }
        )
    )
    assert res["ok"] is True
    assert res["workshop"]["name"] == "Cresco — Day 1"
    assert res["workshop"]["facilitator"] == "alex"
    assert res["workshop"]["metadata"] == {"venue": "remote"}
    assert res["workshop"]["status"] == "open"


def test_create_workshop_rejects_duplicate_id(tars_home: Path) -> None:
    _run(
        lab_create_workshop_action(
            {"name": "A", "workshop_id": "ws_dup"}
        )
    )
    res = _run(
        lab_create_workshop_action(
            {"name": "B", "workshop_id": "ws_dup"}
        )
    )
    assert res["ok"] is False
    assert res["error"] == "workshop_exists"


# --------------------------------------------------------- list


def test_list_workshops_returns_total_and_workshops(
    tars_home: Path,
) -> None:
    _run(lab_create_workshop_action({"name": "A", "workshop_id": "ws_a"}))
    _run(lab_create_workshop_action({"name": "B", "workshop_id": "ws_b"}))
    res = _run(lab_list_workshops_action({}))
    assert res["ok"] is True
    assert res["total"] == 2
    ids = {w["workshop_id"] for w in res["workshops"]}
    assert ids == {"ws_a", "ws_b"}


def test_list_workshops_rejects_invalid_status(tars_home: Path) -> None:
    res = _run(lab_list_workshops_action({"status": "bogus"}))
    assert res["ok"] is False
    assert res["error"] == "invalid_status"


def test_list_workshops_filters_by_status(tars_home: Path) -> None:
    _run(lab_create_workshop_action({"name": "A", "workshop_id": "ws_a"}))
    _run(lab_create_workshop_action({"name": "B", "workshop_id": "ws_b"}))
    _run(
        lab_set_workshop_status_action(
            {"workshop_id": "ws_b", "status": "closed"}
        )
    )
    res = _run(lab_list_workshops_action({"status": "open"}))
    assert res["total"] == 1
    assert res["workshops"][0]["workshop_id"] == "ws_a"


# --------------------------------------------------------- status


def test_set_workshop_status_unknown_workshop(tars_home: Path) -> None:
    res = _run(
        lab_set_workshop_status_action(
            {"workshop_id": "ws_missing", "status": "closed"}
        )
    )
    assert res["ok"] is False
    assert res["error"] == "workshop_not_found"


def test_set_workshop_status_requires_status(tars_home: Path) -> None:
    _run(lab_create_workshop_action({"name": "X", "workshop_id": "ws_x"}))
    res = _run(
        lab_set_workshop_status_action({"workshop_id": "ws_x"})
    )
    assert res["ok"] is False
    assert res["error"] == "missing_status"


# --------------------------------------------------------- enroll


def test_enroll_returns_sandbox_id_and_usage_hint(tars_home: Path) -> None:
    _run(lab_create_workshop_action({"name": "W", "workshop_id": "ws_w"}))
    res = _run(
        lab_enroll_attendee_action(
            {
                "workshop_id": "ws_w",
                "display_name": "Alice",
                "attendee_id": "att_alice",
            }
        )
    )
    assert res["ok"] is True
    assert res["attendee"]["sandbox_id"] == "lab:ws_w:att_alice"
    assert "start_paper_session" in res["usage_hint"]


def test_enroll_rejects_missing_workshop_id(tars_home: Path) -> None:
    res = _run(lab_enroll_attendee_action({"display_name": "A"}))
    assert res["ok"] is False
    assert res["error"] == "missing_workshop_id"


def test_enroll_rejects_missing_display_name(tars_home: Path) -> None:
    _run(lab_create_workshop_action({"name": "W", "workshop_id": "ws_w"}))
    res = _run(
        lab_enroll_attendee_action({"workshop_id": "ws_w"})
    )
    assert res["ok"] is False
    assert res["error"] == "missing_display_name"


def test_enroll_rejects_unknown_workshop(tars_home: Path) -> None:
    res = _run(
        lab_enroll_attendee_action(
            {"workshop_id": "ws_missing", "display_name": "A"}
        )
    )
    assert res["ok"] is False
    assert res["error"] == "workshop_not_found"


def test_enroll_rejects_closed_workshop(tars_home: Path) -> None:
    _run(lab_create_workshop_action({"name": "W", "workshop_id": "ws_w"}))
    _run(
        lab_set_workshop_status_action(
            {"workshop_id": "ws_w", "status": "closed"}
        )
    )
    res = _run(
        lab_enroll_attendee_action(
            {"workshop_id": "ws_w", "display_name": "A"}
        )
    )
    assert res["ok"] is False
    assert res["error"] == "workshop_closed"


# --------------------------------------------------------- list attendees


def test_list_attendees_unknown_workshop(tars_home: Path) -> None:
    res = _run(
        lab_list_attendees_action({"workshop_id": "ws_missing"})
    )
    assert res["ok"] is False
    assert res["error"] == "workshop_not_found"


def test_list_attendees_returns_them_in_join_order(
    tars_home: Path,
) -> None:
    _run(lab_create_workshop_action({"name": "W", "workshop_id": "ws_w"}))
    _run(
        lab_enroll_attendee_action(
            {
                "workshop_id": "ws_w",
                "display_name": "First",
                "attendee_id": "att_1",
            }
        )
    )
    _run(
        lab_enroll_attendee_action(
            {
                "workshop_id": "ws_w",
                "display_name": "Second",
                "attendee_id": "att_2",
            }
        )
    )
    res = _run(lab_list_attendees_action({"workshop_id": "ws_w"}))
    assert res["ok"] is True
    assert res["total"] == 2
    assert [a["attendee_id"] for a in res["attendees"]] == [
        "att_1",
        "att_2",
    ]


# --------------------------------------------------------- leaderboard


def test_leaderboard_unknown_workshop(tars_home: Path) -> None:
    res = _run(lab_leaderboard_action({"workshop_id": "ws_missing"}))
    assert res["ok"] is False
    assert res["error"] == "workshop_not_found"


def test_leaderboard_empty_workshop_returns_zero_entries(
    tars_home: Path,
) -> None:
    _run(lab_create_workshop_action({"name": "W", "workshop_id": "ws_w"}))
    res = _run(lab_leaderboard_action({"workshop_id": "ws_w"}))
    assert res["ok"] is True
    assert res["leaderboard"]["attendees_total"] == 0
    assert res["leaderboard"]["entries"] == []


# --------------------------------------------------------- snapshot


def test_attendee_snapshot_unknown_attendee(tars_home: Path) -> None:
    res = _run(
        lab_attendee_snapshot_action({"attendee_id": "att_missing"})
    )
    assert res["ok"] is False
    assert res["error"] == "attendee_not_found"


def test_attendee_snapshot_includes_workshop_and_rank(
    tars_home: Path,
) -> None:
    _run(lab_create_workshop_action({"name": "Snap", "workshop_id": "ws_snap"}))
    _run(
        lab_enroll_attendee_action(
            {
                "workshop_id": "ws_snap",
                "display_name": "Solo",
                "attendee_id": "att_solo",
            }
        )
    )
    res = _run(
        lab_attendee_snapshot_action({"attendee_id": "att_solo"})
    )
    assert res["ok"] is True
    assert res["attendee"]["attendee_id"] == "att_solo"
    assert res["workshop"]["workshop_id"] == "ws_snap"
    assert res["sessions_total"] == 0
    assert res["rank"]["rank"] == 1
    assert res["leaderboard_size"] == 1
