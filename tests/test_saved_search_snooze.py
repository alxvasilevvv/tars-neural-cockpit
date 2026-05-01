"""Saved-search snooze pipeline.

Snooze is "mute the alarm, not the watcher": polling continues so the
fingerprint snapshot stays current, but the
``saved_search.new_hits`` emit is suppressed while
``time.time() < snoozed_until``. When the snooze lifts, only
*genuinely new* hits fire — the snapshot was kept up to date during
the silent window.

Tests cover:

1. Schema migration + dataclass round-trip.
2. ``ChatStore.set_saved_search_snooze`` (set / clear / missing id).
3. ``poll_saved_search`` — snoozed → silent + snapshot still updates.
4. ``poll_saved_search`` — unsnooze + new drift → alert fires.
5. HTTP wiring (``POST /api/search/saved/{id}/snooze``):
   - relative ``minutes`` / ``hours`` / absolute ``until``,
   - past timestamp clears the snooze,
   - 400 for non-numeric inputs,
   - 404 for missing saved search.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from backend.core.attachments import index as attachment_index_mod
from backend.core.chat import SavedSearch, Thread
from backend.core.chat import store as chat_store_mod
from backend.core.chat.models import Message
from backend.core.chat.store import get_chat_store
from backend.core.search import alerts as alerts_mod
from backend.core.search.alerts import poll_saved_search


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def isolated_chat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv("TARS_ATTACHMENT_ROOT", str(tmp_path / "attachments"))
    monkeypatch.setenv("MEEET_STORE", "disabled")
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(
        attachment_index_mod, "_SINGLETON", None, raising=False
    )
    yield
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(
        attachment_index_mod, "_SINGLETON", None, raising=False
    )


@pytest.fixture()
def captured_emits(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict]]:
    captured: list[tuple[str, dict]] = []

    class _Stub:
        async def emit(self, kind: str, payload: dict) -> None:
            captured.append((kind, dict(payload)))

    monkeypatch.setattr(alerts_mod, "get_client", lambda: _Stub())
    return captured


def _seed_with_drift(label: str, *, msgs: list[str]) -> tuple[str, SavedSearch]:
    chat = get_chat_store()
    t = Thread.fresh(title="deal", pack_slug="business")
    _run(chat.insert_thread(t))
    for body in msgs:
        _run(chat.insert_message(Message.from_operator(t.id, body)))
    s = SavedSearch.fresh(label=label, query=label, scope="messages")
    _run(chat.insert_saved_search(s))
    return t.id, s


# ---------------------------------------------------------------------
# Schema + dataclass
# ---------------------------------------------------------------------


def test_saved_search_loads_with_default_snoozed_until(
    isolated_chat,
) -> None:
    chat = get_chat_store()
    s = SavedSearch.fresh(label="x", query="y", scope="all")
    _run(chat.insert_saved_search(s))
    refreshed = _run(chat.get_saved_search(s.id))
    assert refreshed is not None
    assert refreshed.snoozed_until is None
    assert refreshed.is_snoozed() is False


def test_set_snooze_persists_until_value(isolated_chat) -> None:
    chat = get_chat_store()
    s = SavedSearch.fresh(label="x", query="y", scope="all")
    _run(chat.insert_saved_search(s))
    target = time.time() + 600
    refreshed = _run(
        chat.set_saved_search_snooze(s.id, snoozed_until=target)
    )
    assert refreshed and refreshed.snoozed_until == target
    assert refreshed.is_snoozed() is True


def test_set_snooze_clears_with_none(isolated_chat) -> None:
    chat = get_chat_store()
    s = SavedSearch.fresh(label="x", query="y", scope="all")
    _run(chat.insert_saved_search(s))
    _run(chat.set_saved_search_snooze(s.id, snoozed_until=time.time() + 600))
    cleared = _run(chat.set_saved_search_snooze(s.id, snoozed_until=None))
    assert cleared and cleared.snoozed_until is None
    assert cleared.is_snoozed() is False


def test_set_snooze_returns_none_for_missing(isolated_chat) -> None:
    chat = get_chat_store()
    out = _run(chat.set_saved_search_snooze("sv_nope", snoozed_until=None))
    assert out is None


def test_is_snoozed_respects_past_until(isolated_chat) -> None:
    chat = get_chat_store()
    s = SavedSearch.fresh(label="x", query="y", scope="all")
    _run(chat.insert_saved_search(s))
    past = time.time() - 60
    refreshed = _run(chat.set_saved_search_snooze(s.id, snoozed_until=past))
    assert refreshed.is_snoozed() is False


# ---------------------------------------------------------------------
# poll_saved_search interaction
# ---------------------------------------------------------------------


def test_snoozed_poll_keeps_silent_but_updates_snapshot(
    isolated_chat, captured_emits
) -> None:
    chat = get_chat_store()
    thread_id, s = _seed_with_drift(
        "EMEA", msgs=["EMEA initial"],
    )
    _run(poll_saved_search(s.id))  # seed
    _run(chat.set_saved_search_snooze(
        s.id, snoozed_until=time.time() + 600
    ))

    _run(chat.insert_message(
        Message.from_operator(thread_id, "EMEA fresh during snooze")
    ))
    out = _run(poll_saved_search(s.id))
    assert out["snoozed"] is True
    assert out["alerted"] is False
    assert out["new_count"] == 1  # we did SEE the new hit
    assert captured_emits == []  # …but didn't fire the alarm

    refreshed = _run(chat.get_saved_search(s.id))
    # Snapshot was updated so a future unsnooze + same hit won't
    # re-fire.
    fingerprints = set(refreshed.seen_hits)
    assert any(fp.startswith("message:") for fp in fingerprints)


def test_unsnooze_then_drift_fires_alert(
    isolated_chat, captured_emits
) -> None:
    chat = get_chat_store()
    thread_id, s = _seed_with_drift(
        "EMEA", msgs=["EMEA initial"],
    )
    _run(poll_saved_search(s.id))  # seed
    _run(chat.set_saved_search_snooze(
        s.id, snoozed_until=time.time() + 600
    ))
    _run(chat.insert_message(
        Message.from_operator(thread_id, "EMEA during snooze"),
    ))
    _run(poll_saved_search(s.id))  # silent
    assert captured_emits == []

    # Unsnooze. The "during snooze" hit was already snapshotted, so
    # adding ANOTHER hit is what triggers the alert — proving
    # snooze is "mute the alarm, not lose state".
    _run(chat.set_saved_search_snooze(s.id, snoozed_until=None))
    _run(chat.insert_message(
        Message.from_operator(thread_id, "EMEA after unsnooze"),
    ))
    out = _run(poll_saved_search(s.id))
    assert out["alerted"] is True
    assert out["new_count"] == 1
    assert len(captured_emits) == 1


def test_snoozed_poll_response_includes_snooze_metadata(
    isolated_chat, captured_emits
) -> None:
    chat = get_chat_store()
    _, s = _seed_with_drift("EMEA", msgs=["EMEA"])
    _run(poll_saved_search(s.id))  # seed
    until = time.time() + 600
    _run(chat.set_saved_search_snooze(s.id, snoozed_until=until))
    out = _run(poll_saved_search(s.id))
    assert out["snoozed"] is True
    assert abs(out["snoozed_until"] - until) < 1


# ---------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------


def _client():
    from fastapi.testclient import TestClient

    from web_extras.app import app

    return TestClient(app)


def test_http_snooze_with_minutes(isolated_chat) -> None:
    chat = get_chat_store()
    s = SavedSearch.fresh(label="x", query="y", scope="all")
    _run(chat.insert_saved_search(s))

    with _client() as client:
        r = client.post(
            f"/api/search/saved/{s.id}/snooze", json={"minutes": 30}
        )
    assert r.status_code == 200
    body = r.json()
    assert body["snoozed"] is True
    refreshed = _run(chat.get_saved_search(s.id))
    assert refreshed.snoozed_until > time.time()


def test_http_snooze_with_hours(isolated_chat) -> None:
    chat = get_chat_store()
    s = SavedSearch.fresh(label="x", query="y", scope="all")
    _run(chat.insert_saved_search(s))

    with _client() as client:
        r = client.post(
            f"/api/search/saved/{s.id}/snooze", json={"hours": 2}
        )
    body = r.json()
    assert body["snoozed"] is True
    refreshed = _run(chat.get_saved_search(s.id))
    assert refreshed.snoozed_until > time.time() + 3000  # at least ~50min


def test_http_snooze_with_until_timestamp(isolated_chat) -> None:
    chat = get_chat_store()
    s = SavedSearch.fresh(label="x", query="y", scope="all")
    _run(chat.insert_saved_search(s))

    target = time.time() + 7200
    with _client() as client:
        r = client.post(
            f"/api/search/saved/{s.id}/snooze", json={"until": target}
        )
    body = r.json()
    assert body["snoozed"] is True
    assert abs(body["snoozed_until"] - target) < 1


def test_http_snooze_with_past_until_clears_snooze(isolated_chat) -> None:
    chat = get_chat_store()
    s = SavedSearch.fresh(label="x", query="y", scope="all")
    _run(chat.insert_saved_search(s))
    _run(chat.set_saved_search_snooze(
        s.id, snoozed_until=time.time() + 600
    ))

    past = time.time() - 60
    with _client() as client:
        r = client.post(
            f"/api/search/saved/{s.id}/snooze", json={"until": past}
        )
    body = r.json()
    assert body["snoozed"] is False
    assert body["snoozed_until"] is None


def test_http_snooze_with_empty_body_clears(isolated_chat) -> None:
    """No body → resume immediately."""

    chat = get_chat_store()
    s = SavedSearch.fresh(label="x", query="y", scope="all")
    _run(chat.insert_saved_search(s))
    _run(chat.set_saved_search_snooze(
        s.id, snoozed_until=time.time() + 600
    ))

    with _client() as client:
        r = client.post(f"/api/search/saved/{s.id}/snooze")
    body = r.json()
    assert body["snoozed"] is False


def test_http_snooze_rejects_non_numeric_minutes(isolated_chat) -> None:
    chat = get_chat_store()
    s = SavedSearch.fresh(label="x", query="y", scope="all")
    _run(chat.insert_saved_search(s))

    with _client() as client:
        r = client.post(
            f"/api/search/saved/{s.id}/snooze",
            json={"minutes": "soon"},
        )
    assert r.status_code == 400


def test_http_snooze_returns_404_for_missing(isolated_chat) -> None:
    with _client() as client:
        r = client.post(
            "/api/search/saved/sv_nope/snooze", json={"minutes": 5}
        )
    assert r.status_code == 404
