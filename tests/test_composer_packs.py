"""W256 — domain-pack-aware composer tests.

Five cases per the W256 spec:

1. Plan uses pack-specific overlay when set
2. Switch-pack endpoint persists to disk
3. Default pack when unset is ``web_search``
4. ACTION_VOCABULARY shortcuts expand correctly
5. Pack info returned matches active config

The router-level tests use FastAPI's TestClient against a fresh app
that mounts only the composer router so we don't need the entire
web_extras app graph.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.composer import (
    DEFAULT_PACK,
    KNOWN_PACKS,
    expand_action_shortcut,
    get_active_pack,
    get_pack_action_vocabulary,
    get_pack_file_hints,
    get_pack_info,
    get_pack_overlay,
    plan_from_transcript,
    set_active_pack,
)
from web_extras.routers.composer import router as composer_router


@pytest.fixture(autouse=True)
def _isolated_pack_file(tmp_path, monkeypatch):
    """Point the active-pack JSON at a temp path so tests don't leak."""

    p = tmp_path / "active_pack.json"
    monkeypatch.setenv("TARS_ACTIVE_PACK_PATH", str(p))
    # Also isolate composer DB + receipts so the router path is silent.
    monkeypatch.setenv("TARS_COMPOSER_DB", str(tmp_path / "composer.sqlite"))
    monkeypatch.setenv(
        "TARS_COMPOSER_BACKUP_DIR", str(tmp_path / "backups")
    )
    monkeypatch.setenv(
        "TARS_RECEIPT_HOST_KEY_PATH", str(tmp_path / "host.json")
    )
    monkeypatch.setenv("TARS_RECEIPT_DIR", str(tmp_path / "receipts"))
    monkeypatch.setenv(
        "TARS_RECEIPT_DB_PATH", str(tmp_path / "receipts.sqlite")
    )
    yield p


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(composer_router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1 — Plan uses pack-specific overlay when set
# ---------------------------------------------------------------------------


def test_plan_records_active_pack(tmp_path):
    """The planner should annotate the returned plan with the pack it
    used. Setting a pack explicitly via the kwarg pins it for one call.
    """

    project = tmp_path / "proj"
    project.mkdir()
    (project / "readme.md").write_text("hi\n", encoding="utf-8")

    # Default (no pack file written) — falls back to web_search.
    plan = plan_from_transcript(
        "create foo.py", project, allow_llm=False
    )
    assert plan.active_pack == "web_search"

    # Explicit pack override on the call.
    plan2 = plan_from_transcript(
        "create bar.py", project, allow_llm=False, pack="wallet"
    )
    assert plan2.active_pack == "wallet"

    # Plan's to_dict round-trips the pack field.
    payload = plan2.to_dict()
    assert payload["active_pack"] == "wallet"


# ---------------------------------------------------------------------------
# 2 — Switch-pack endpoint persists to disk
# ---------------------------------------------------------------------------


def test_switch_pack_endpoint_persists(client, _isolated_pack_file):
    r = client.post(
        "/api/composer/switch-pack",
        json={"pack": "entrepreneur"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["pack"] == "entrepreneur"

    # File persists with the expected shape.
    assert _isolated_pack_file.is_file()
    data = json.loads(_isolated_pack_file.read_text(encoding="utf-8"))
    assert data["pack"] == "entrepreneur"
    assert "updated_at" in data

    # Unknown pack is rejected with 400.
    bad = client.post(
        "/api/composer/switch-pack",
        json={"pack": "definitely-not-a-pack"},
    )
    assert bad.status_code == 400


# ---------------------------------------------------------------------------
# 3 — Default pack when unset is web_search
# ---------------------------------------------------------------------------


def test_default_pack_is_web_search(_isolated_pack_file):
    # Nothing has been written yet.
    assert not _isolated_pack_file.exists()
    assert DEFAULT_PACK == "web_search"
    assert get_active_pack() == "web_search"

    # A malformed file also falls back to the default.
    _isolated_pack_file.write_text("not json at all", encoding="utf-8")
    assert get_active_pack() == "web_search"

    # An unknown slug in the file also falls back.
    _isolated_pack_file.write_text(
        json.dumps({"pack": "bogus"}), encoding="utf-8"
    )
    assert get_active_pack() == "web_search"


# ---------------------------------------------------------------------------
# 4 — ACTION_VOCABULARY shortcuts expand correctly
# ---------------------------------------------------------------------------


def test_action_vocabulary_expansion():
    # entrepreneur "post about X" -> long-form draft prompt.
    expanded = expand_action_shortcut(
        "post about Q3 launch", "entrepreneur"
    )
    assert "post draft" in expanded
    assert "Q3 launch" in expanded

    # wallet "rebalance" with no args -> bare template, no formatting.
    expanded = expand_action_shortcut("rebalance", "wallet")
    assert "rebalance script" in expanded
    assert "portfolio.csv" in expanded

    # Unknown word -> passes through unchanged.
    assert (
        expand_action_shortcut("frobnicate the widgets", "wallet")
        == "frobnicate the widgets"
    )

    # business has a "draft" shortcut.
    expanded = expand_action_shortcut("draft to alice", "business")
    assert "draft" in expanded.lower()


# ---------------------------------------------------------------------------
# 5 — Pack info returned matches active config
# ---------------------------------------------------------------------------


def test_pack_info_matches_active_config(client):
    # Start by switching to traders.
    r = client.post("/api/composer/switch-pack", json={"pack": "traders"})
    assert r.status_code == 200

    info = client.get("/api/composer/pack-info").json()
    assert info["ok"] is True
    assert info["pack"] == "traders"
    assert info["default"] is False
    assert set(KNOWN_PACKS).issubset(set(info["known_packs"]))

    # Vocabulary + hints non-empty for a real pack.
    assert isinstance(info["action_vocabulary"], dict)
    assert len(info["action_vocabulary"]) >= 1
    assert isinstance(info["file_hints"], dict)
    assert len(info["file_hints"]) >= 1

    # System prompt overlay is present and mentions the pack context.
    overlay = info["system_prompt_overlay"]
    assert "traders" in overlay.lower()

    # Direct call to get_pack_info() returns the same payload shape.
    direct = get_pack_info()
    assert direct["pack"] == "traders"
    assert direct["action_vocabulary"] == info["action_vocabulary"]
    assert direct["file_hints"] == info["file_hints"]
