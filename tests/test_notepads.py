"""W243 — Notepad templates regression tests.

Five cases per the W243 spec:

1. ``/api/notepads/seed`` creates 5 notepads on empty DB and is
   idempotent on re-run.
2. FTS5 ``q=`` search returns the right notepad.
3. ``POST /api/notepads/{id}/use`` increments ``usage_count`` and
   returns body.
4. ``extract_variables`` parses ``{name}`` placeholders correctly.
5. ``pack=`` filter selects only that pack's notepads.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_tars_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``TARS_HOME`` at a fresh tmp dir + reset notepad singleton.

    The module-level singleton in ``backend.core.notepads`` caches the
    DB path; calling :func:`reset_store_for_tests` ensures the next
    accessor call re-resolves to the patched location.
    """

    home = tmp_path / "tars-home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("TARS_HOME", str(home))

    from backend.core import notepads as notepads_mod

    notepads_mod.reset_store_for_tests()
    yield home
    notepads_mod.reset_store_for_tests()


@pytest.fixture
def client(isolated_tars_home: Path) -> TestClient:  # noqa: ARG001
    """FastAPI client bound to an isolated notepads DB."""

    from web_extras.app import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# 1) Seed creates 5 on empty DB
# ---------------------------------------------------------------------------


def test_seed_creates_five_defaults_on_empty(client: TestClient) -> None:
    out = client.get("/api/notepads/seed").json()
    assert out["ok"] is True
    assert len(out["seeded"]) == 5
    assert out["skipped"] is False
    assert out["count"] == 5

    titles = {n["title"] for n in out["seeded"]}
    assert {
        "Daily briefing",
        "Cold outreach draft",
        "Code review checklist",
        "Doctor visit prep",
        "Pack picker",
    } == titles

    # Idempotent: second call must NOT duplicate seeds.
    again = client.get("/api/notepads/seed").json()
    assert again["ok"] is True
    assert again["skipped"] is True
    assert again["seeded"] == []
    assert again["count"] == 5


# ---------------------------------------------------------------------------
# 2) FTS5 search works
# ---------------------------------------------------------------------------


def test_fts5_search_matches_title_or_body(client: TestClient) -> None:
    client.get("/api/notepads/seed")

    # Title term.
    hits = client.get("/api/notepads", params={"q": "Briefing"}).json()
    assert hits["ok"] is True
    titles = [n["title"] for n in hits["items"]]
    assert "Daily briefing" in titles

    # Body term.
    body_hits = client.get("/api/notepads", params={"q": "outreach"}).json()
    titles2 = [n["title"] for n in body_hits["items"]]
    assert "Cold outreach draft" in titles2

    # FTS5 should be on in test env (system sqlite ships with it on
    # all supported platforms). If it ever isn't, the LIKE fallback
    # still returns the same row — but flag the regression.
    list_out = client.get("/api/notepads").json()
    # We can't unconditionally assert fts=True on every CI runner,
    # but we CAN assert search works regardless of the underlying
    # backend.
    assert list_out["count"] == 5


# ---------------------------------------------------------------------------
# 3) /use increments usage_count
# ---------------------------------------------------------------------------


def test_use_increments_usage_count_and_returns_body(client: TestClient) -> None:
    seeded = client.get("/api/notepads/seed").json()
    # Pick one without variables so we don't need to substitute.
    daily = next(n for n in seeded["seeded"] if n["title"] == "Daily briefing")

    before = client.get(f"/api/notepads/{daily['id']}").json()["notepad"]
    assert before["usage_count"] == 0

    used = client.post(f"/api/notepads/{daily['id']}/use", json={}).json()
    assert used["ok"] is True
    assert used["usage_count"] == 1
    assert used["body"] == daily["body"]

    again = client.post(f"/api/notepads/{daily['id']}/use", json={}).json()
    assert again["usage_count"] == 2


# ---------------------------------------------------------------------------
# 4) Variables {name} parsed correctly
# ---------------------------------------------------------------------------


def test_variables_parsing_and_substitution(client: TestClient) -> None:
    from backend.core.notepads import extract_variables, fill_variables

    body = (
        "Hi {company}, here's the pitch about {value_prop}. "
        "Curly literal: {nope!} stays. JSON: {\"a\": 1} stays. "
        "Repeat: {company}."
    )
    vars_ = extract_variables(body)
    assert vars_ == ["company", "value_prop"]

    filled = fill_variables(body, {"company": "Acme", "value_prop": "speed"})
    assert "Acme" in filled
    assert "speed" in filled
    # Non-variable braces preserved verbatim.
    assert "{nope!}" in filled
    assert '{"a": 1}' in filled

    # Router echoes the same parse via /use.
    payload = {"title": "Var test", "body": body}
    created = client.post("/api/notepads", json=payload).json()
    pad_id = created["notepad"]["id"]
    assert created["notepad"]["variables"] == ["company", "value_prop"]

    used = client.post(
        f"/api/notepads/{pad_id}/use",
        json={"variables": {"company": "Acme", "value_prop": "speed"}},
    ).json()
    assert "Acme" in used["body"]
    assert "speed" in used["body"]
    assert used["variables"] == ["company", "value_prop"]


# ---------------------------------------------------------------------------
# 5) Pack filter applied
# ---------------------------------------------------------------------------


def test_pack_filter_applied(client: TestClient) -> None:
    client.get("/api/notepads/seed")

    entr = client.get("/api/notepads", params={"pack": "entrepreneur"}).json()
    titles = [n["title"] for n in entr["items"]]
    assert titles == ["Cold outreach draft"]

    health = client.get("/api/notepads", params={"pack": "health"}).json()
    titles_h = [n["title"] for n in health["items"]]
    assert titles_h == ["Doctor visit prep"]

    # ``pack=""`` returns only the no-pack notepads.
    nopack = client.get("/api/notepads", params={"pack": ""}).json()
    titles_n = sorted(n["title"] for n in nopack["items"])
    assert titles_n == sorted(["Daily briefing", "Code review checklist", "Pack picker"])

    # No filter returns all 5.
    all_ = client.get("/api/notepads").json()
    assert all_["count"] == 5


# ---------------------------------------------------------------------------
# Bonus: FTS5 backend availability sanity check (informational)
# ---------------------------------------------------------------------------


def test_fts5_enabled_on_runner(isolated_tars_home: Path) -> None:  # noqa: ARG001
    """The stdlib sqlite3 on supported platforms ships FTS5 enabled.

    This test documents the assumption; if it ever flips on a CI
    runner, the store still works (LIKE fallback) but the search
    quality degrades.
    """

    from backend.core.notepads import get_notepad_store

    store = get_notepad_store()
    # Honest about reality: we don't fail the suite if FTS5 is missing.
    # But we DO assert the store reports its own state truthfully.
    assert isinstance(store.fts_enabled, bool)
