"""Saved-search alert pipeline.

Three layers under test:

1. ``hit_fingerprint`` — stable string identifier per hit kind.
2. ``poll_saved_search`` — first poll seeds, drift fires, idempotent
   on quiet polls, fingerprint cap, MeeetClient emit + chat-store
   persistence.
3. HTTP wiring — ``POST /api/search/saved/{id}/poll`` and
   ``POST /api/search/saved/poll-all`` over the live FastAPI app.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from backend.core.attachments import index as attachment_index_mod
from backend.core.chat import SavedSearch, Thread
from backend.core.chat import store as chat_store_mod
from backend.core.chat.models import Message
from backend.core.chat.store import get_chat_store
from backend.core.search import alerts as alerts_mod
from backend.core.search.alerts import (
    MAX_SEEN_HITS,
    hit_fingerprint,
    poll_all_saved_searches,
    poll_saved_search,
)
from backend.core.search.engine import SearchHit


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


def _seed_thread_with_messages(*, label: str, pack: str, msgs: list[str]) -> str:
    chat = get_chat_store()
    t = Thread.fresh(title=label, pack_slug=pack)
    _run(chat.insert_thread(t))
    for body in msgs:
        _run(chat.insert_message(Message.from_operator(t.id, body)))
    return t.id


def _make_saved_search(query: str, scope: str = "messages") -> SavedSearch:
    chat = get_chat_store()
    s = SavedSearch.fresh(label="watch-" + query, query=query, scope=scope)
    _run(chat.insert_saved_search(s))
    return s


# ---------------------------------------------------------------------
# Fingerprint helper
# ---------------------------------------------------------------------


def test_fingerprint_for_chunk_uses_chunk_id() -> None:
    h = SearchHit(
        kind="chunk", score=1.0, title="x", snippet="x",
        ref={"chunk_id": "c123", "attachment_id": "a"},
    )
    assert hit_fingerprint(h) == "chunk:c123"


def test_fingerprint_for_message_uses_msg_id() -> None:
    h = SearchHit(
        kind="message", score=1.0, title="x", snippet="x",
        ref={"msg_id": "m999"},
    )
    assert hit_fingerprint(h) == "message:m999"


def test_fingerprint_for_trace_prefers_event_id() -> None:
    h = SearchHit(
        kind="trace", score=1.0, title="x", snippet="x",
        ref={"event_id": 42, "trace_id": "trc_x"},
    )
    assert hit_fingerprint(h) == "trace:42"


def test_fingerprint_for_trace_falls_back_to_trace_id() -> None:
    h = SearchHit(
        kind="trace", score=1.0, title="x", snippet="x",
        ref={"trace_id": "trc_x"},
    )
    assert hit_fingerprint(h) == "trace:trc_x"


def test_fingerprint_handles_unknown_kind() -> None:
    h = SearchHit(
        kind="other",  # type: ignore[arg-type]
        score=1.0, title="x", snippet="x", ref={},
    )
    assert hit_fingerprint(h) == "other:?"


# ---------------------------------------------------------------------
# Poll cycle
# ---------------------------------------------------------------------


def test_first_poll_seeds_without_emitting(
    isolated_chat, captured_emits
) -> None:
    _seed_thread_with_messages(
        label="deal", pack="business",
        msgs=["EMEA blocker A", "EMEA blocker B"],
    )
    s = _make_saved_search("EMEA")

    res = _run(poll_saved_search(s.id))
    assert res["ok"] is True
    assert res["first_poll"] is True
    assert res["alerted"] is False
    assert res["new_count"] == 2  # both hits "new" but we don't fire
    assert captured_emits == []

    refreshed = _run(get_chat_store().get_saved_search(s.id))
    assert refreshed and len(refreshed.seen_hits) == 2
    assert refreshed.last_run_at is not None
    assert refreshed.last_alert_at is None


def test_second_poll_with_no_drift_is_quiet(
    isolated_chat, captured_emits
) -> None:
    _seed_thread_with_messages(
        label="deal", pack="business", msgs=["EMEA stable"],
    )
    s = _make_saved_search("EMEA")
    _run(poll_saved_search(s.id))

    res = _run(poll_saved_search(s.id))
    assert res["ok"] is True
    assert res["first_poll"] is False
    assert res["new_count"] == 0
    assert res["alerted"] is False
    assert captured_emits == []  # still quiet


def test_third_poll_with_drift_fires_alert(
    isolated_chat, captured_emits
) -> None:
    chat = get_chat_store()
    thread_id = _seed_thread_with_messages(
        label="deal", pack="business", msgs=["EMEA initial"],
    )
    s = _make_saved_search("EMEA")
    _run(poll_saved_search(s.id))  # seed
    _run(poll_saved_search(s.id))  # quiet

    _run(chat.insert_message(
        Message.from_operator(thread_id, "EMEA fresh news")
    ))
    res = _run(poll_saved_search(s.id))
    assert res["alerted"] is True
    assert res["new_count"] == 1
    assert len(captured_emits) == 1
    kind, payload = captured_emits[0]
    assert kind == "saved_search.new_hits"
    assert payload["search_id"] == s.id
    assert payload["label"] == s.label
    assert payload["scope"] == "messages"
    assert payload["new_count"] == 1
    assert len(payload["new_hits"]) == 1

    refreshed = _run(chat.get_saved_search(s.id))
    assert refreshed and refreshed.last_alert_at is not None


def test_alert_only_fires_for_genuinely_new_fingerprints(
    isolated_chat, captured_emits
) -> None:
    """Polling the same hit set twice doesn't re-alert."""

    chat = get_chat_store()
    thread_id = _seed_thread_with_messages(
        label="deal", pack="business", msgs=["EMEA one"],
    )
    s = _make_saved_search("EMEA")
    _run(poll_saved_search(s.id))  # seed

    _run(chat.insert_message(
        Message.from_operator(thread_id, "EMEA two")
    ))
    res1 = _run(poll_saved_search(s.id))
    assert res1["alerted"] is True
    assert len(captured_emits) == 1

    res2 = _run(poll_saved_search(s.id))
    assert res2["alerted"] is False
    assert res2["new_count"] == 0
    assert len(captured_emits) == 1  # didn't double-fire


def test_emit_failure_does_not_crash_poll(
    isolated_chat, monkeypatch
) -> None:
    chat = get_chat_store()
    thread_id = _seed_thread_with_messages(
        label="deal", pack="business", msgs=["EMEA seed"],
    )
    s = _make_saved_search("EMEA")
    _run(poll_saved_search(s.id))  # seed

    class _Boom:
        async def emit(self, kind, payload):
            raise RuntimeError("bridge offline")

    monkeypatch.setattr(alerts_mod, "get_client", lambda: _Boom())

    _run(chat.insert_message(
        Message.from_operator(thread_id, "EMEA new"),
    ))
    res = _run(poll_saved_search(s.id))
    # Emit blew up → alerted False, but the snapshot still updates.
    assert res["ok"] is True
    assert res["alerted"] is False
    refreshed = _run(chat.get_saved_search(s.id))
    assert refreshed
    # The new fingerprint is now in the snapshot so the next poll
    # won't re-fire.
    assert any(fp.startswith("message:") for fp in refreshed.seen_hits)


def test_poll_returns_not_found_for_missing_id(isolated_chat) -> None:
    res = _run(poll_saved_search("sv_does_not_exist"))
    assert res["ok"] is False
    assert res["reason"] == "not_found"


def test_seen_hits_capped_at_max(
    isolated_chat, captured_emits
) -> None:
    chat = get_chat_store()
    s = _make_saved_search("EMEA")
    # Seed seen_hits with N existing fingerprints.
    huge = [f"message:msg_{i}" for i in range(MAX_SEEN_HITS - 5)]
    _run(chat.record_saved_search_alert(
        s.id, seen_hits=huge, had_new_hits=True,
    ))

    thread_id = _seed_thread_with_messages(
        label="deal", pack="business",
        msgs=[f"EMEA {i}" for i in range(20)],
    )
    res = _run(poll_saved_search(s.id))
    assert res["ok"] is True
    refreshed = _run(chat.get_saved_search(s.id))
    assert refreshed
    assert len(refreshed.seen_hits) <= MAX_SEEN_HITS


# ---------------------------------------------------------------------
# Migration / backwards-compat
# ---------------------------------------------------------------------


def test_legacy_rows_without_seen_hits_column_still_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pre-migration DB row hydrates with empty seen_hits + None
    last_alert_at, then the next migration adds the column."""

    db = tmp_path / "legacy.sqlite"
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(db))
    monkeypatch.setenv("MEEET_STORE", "disabled")
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)

    chat = get_chat_store()
    s = SavedSearch.fresh(label="legacy", query="x", scope="all")
    _run(chat.insert_saved_search(s))

    # Simulate a DB created before the migration: drop the new
    # columns and reopen.
    conn = sqlite3.connect(db)
    try:
        conn.execute("ALTER TABLE saved_searches DROP COLUMN seen_hits_json")
        conn.execute("ALTER TABLE saved_searches DROP COLUMN last_alert_at")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    chat = get_chat_store()  # re-creates singleton, runs migrations
    refreshed = _run(chat.get_saved_search(s.id))
    assert refreshed is not None
    assert refreshed.seen_hits == ()
    assert refreshed.last_alert_at is None


# ---------------------------------------------------------------------
# poll_all
# ---------------------------------------------------------------------


def test_poll_all_walks_every_saved_search(
    isolated_chat, captured_emits
) -> None:
    chat = get_chat_store()
    thread_id = _seed_thread_with_messages(
        label="deal", pack="business", msgs=["EMEA one"],
    )
    s1 = _make_saved_search("EMEA")
    s2 = _make_saved_search("missing-token")  # zero hits

    _run(poll_all_saved_searches())  # seed both

    _run(chat.insert_message(
        Message.from_operator(thread_id, "EMEA new"),
    ))
    res = _run(poll_all_saved_searches())
    assert res["ok"] is True
    assert res["polled"] == 2
    assert res["alerted"] == 1
    by_id = {r["search_id"]: r for r in res["results"]}
    assert by_id[s1.id]["alerted"] is True
    assert by_id[s2.id]["alerted"] is False


def test_poll_all_returns_empty_when_no_saved_searches(
    isolated_chat,
) -> None:
    res = _run(poll_all_saved_searches())
    assert res == {"ok": True, "polled": 0, "alerted": 0, "results": []}


# ---------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------


def test_http_poll_endpoint_seeds_then_alerts(
    isolated_chat, captured_emits
) -> None:
    from fastapi.testclient import TestClient

    from web_extras.app import app

    chat = get_chat_store()
    thread_id = _seed_thread_with_messages(
        label="deal", pack="business", msgs=["EMEA one"],
    )
    s = _make_saved_search("EMEA")

    with TestClient(app) as client:
        r1 = client.post(f"/api/search/saved/{s.id}/poll")
        assert r1.status_code == 200
        assert r1.json()["first_poll"] is True

        _run(chat.insert_message(
            Message.from_operator(thread_id, "EMEA fresh"),
        ))
        r2 = client.post(f"/api/search/saved/{s.id}/poll")
        body = r2.json()
        assert body["alerted"] is True
        assert body["new_count"] == 1


def test_http_poll_endpoint_returns_404_for_missing(isolated_chat) -> None:
    from fastapi.testclient import TestClient

    from web_extras.app import app

    with TestClient(app) as client:
        r = client.post("/api/search/saved/sv_nope/poll")
    assert r.status_code == 404


def test_http_poll_all_endpoint(isolated_chat, captured_emits) -> None:
    from fastapi.testclient import TestClient

    from web_extras.app import app

    _seed_thread_with_messages(
        label="deal", pack="business", msgs=["EMEA one"],
    )
    _make_saved_search("EMEA")

    with TestClient(app) as client:
        r = client.post(
            "/api/search/saved/poll-all", json={"top_k": 5, "limit": 50}
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["polled"] == 1
