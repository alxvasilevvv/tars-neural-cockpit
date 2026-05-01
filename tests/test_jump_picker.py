"""Cross-thread Cmd+J jump picker.

Three layers under test:

1. ``fuzzy_score`` — the cheap matcher behind the palette.
2. ``rank`` — query-vs-candidate scoring + sort + cap.
3. ``jump`` (engine) + ``POST /api/search/jump`` (HTTP) — full
   end-to-end fan-out across threads / attachments / saved-searches /
   packs / playbooks.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from backend.core.attachments import index as attachment_index_mod
from backend.core.chat import SavedSearch, Thread
from backend.core.chat import store as chat_store_mod
from backend.core.chat.models import Attachment, new_attachment_id
from backend.core.chat.store import get_chat_store
from backend.core.search.jump import (
    JumpHit,
    fuzzy_score,
    jump,
    rank,
)


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


# ---------------------------------------------------------------------
# fuzzy_score
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "query,text,expected_min,expected_max",
    [
        ("emea", "EMEA blocker", 0.85, 0.95),  # token-prefix
        ("emea", "EMEA", 1.0, 1.0),  # exact
        ("mar", "Marketing brief", 0.85, 0.95),  # word prefix
        ("ket", "Marketing brief", 0.7, 0.8),  # mid-text substring
        ("xyz", "Marketing brief", 0.0, 0.0),  # no match
        ("mb", "Marketing brief", 0.1, 0.5),  # subsequence
    ],
)
def test_fuzzy_score_ranges(query, text, expected_min, expected_max) -> None:
    s = fuzzy_score(query, text)
    assert expected_min <= s <= expected_max, (
        f"fuzzy_score({query!r}, {text!r}) = {s}"
    )


def test_fuzzy_score_empty_inputs_return_zero() -> None:
    assert fuzzy_score("", "anything") == 0.0
    assert fuzzy_score("anything", "") == 0.0
    assert fuzzy_score("", "") == 0.0


def test_fuzzy_score_is_case_insensitive() -> None:
    assert fuzzy_score("EMEA", "emea") == fuzzy_score("emea", "EMEA")
    assert fuzzy_score("Mar", "marketing brief") == fuzzy_score(
        "mar", "Marketing brief"
    )


# ---------------------------------------------------------------------
# rank
# ---------------------------------------------------------------------


def _hit(kind: str, label: str, *, sublabel: str = "") -> JumpHit:
    return JumpHit(
        kind=kind,  # type: ignore[arg-type]
        id=label,
        label=label,
        sublabel=sublabel,
        score=0.0,
        ref={},
    )


def test_rank_returns_recent_pool_for_blank_query() -> None:
    pool = [_hit("thread", "T1"), _hit("thread", "T2")]
    out = rank("", pool, limit=5)
    assert [h.label for h in out] == ["T1", "T2"]


def test_rank_drops_zero_score_entries() -> None:
    pool = [_hit("thread", "Marketing brief"), _hit("thread", "EMEA blocker")]
    out = rank("xyz", pool, limit=5)
    assert out == []


def test_rank_sorts_by_descending_score() -> None:
    pool = [
        _hit("thread", "Quantum paper"),
        _hit("thread", "Marketing brief"),
        _hit("thread", "Margin pressure"),
    ]
    out = rank("mar", pool, limit=5)
    labels = [h.label for h in out]
    # Token-prefix matches outrank loose subsequence matches.
    assert labels[0] in ("Marketing brief", "Margin pressure")
    assert labels[1] in ("Marketing brief", "Margin pressure")
    # "Quantum paper" only matches as a loose subsequence, so it
    # ranks last (or doesn't appear).
    if "Quantum paper" in labels:
        assert labels.index("Quantum paper") >= 2


def test_rank_caps_at_limit() -> None:
    pool = [_hit("thread", f"item-{i}") for i in range(20)]
    out = rank("item", pool, limit=5)
    assert len(out) == 5


# ---------------------------------------------------------------------
# jump engine
# ---------------------------------------------------------------------


def _seed_threads_with_payload(isolated_chat) -> None:
    chat = get_chat_store()
    for title, pack in [
        ("EMEA blocker", "business"),
        ("Quantum computing paper", "science"),
        ("Marketing brief", "business"),
        ("Risk-flagged trades", "traders"),
    ]:
        _run(chat.insert_thread(Thread.fresh(title=title, pack_slug=pack)))
    _run(
        chat.insert_saved_search(
            SavedSearch.fresh(
                label="watch-emea", query="EMEA", scope="all", pinned=True
            )
        )
    )
    _run(
        chat.insert_saved_search(
            SavedSearch.fresh(
                label="market-brief", query="market", scope="messages"
            )
        )
    )


def test_jump_finds_thread_by_token_prefix(isolated_chat) -> None:
    _seed_threads_with_payload(isolated_chat)
    res = _run(jump("mar"))
    labels = [(h["kind"], h["label"]) for h in res["hits"]]
    assert ("thread", "Marketing brief") in labels


def test_jump_returns_recent_threads_for_empty_query(isolated_chat) -> None:
    _seed_threads_with_payload(isolated_chat)
    res = _run(jump(""))
    assert res["count"] > 0
    # Empty query shouldn't crash; first hit is recency-sorted.


def test_jump_empty_store_returns_empty_hits(isolated_chat) -> None:
    res = _run(jump("anything"))
    assert res["ok"] is True
    assert res["count"] == 0
    assert res["hits"] == []


def test_jump_kinds_filter_restricts_to_saved_searches(
    isolated_chat,
) -> None:
    _seed_threads_with_payload(isolated_chat)
    res = _run(jump("emea", kinds=["saved_search"]))
    kinds = {h["kind"] for h in res["hits"]}
    assert kinds <= {"saved_search"}
    # We have one saved search labelled "watch-emea" → it should hit.
    assert any(h["label"] == "watch-emea" for h in res["hits"])


def test_jump_attachment_lookup(isolated_chat) -> None:
    chat = get_chat_store()
    t = Thread.fresh(title="deal", pack_slug="business")
    _run(chat.insert_thread(t))

    a = Attachment(
        id=new_attachment_id(),
        thread_id=t.id,
        message_id=None,
        mime="application/pdf",
        filename="quarterly-report.pdf",
        bytes_total=10,
        storage_path="/tmp/x.pdf",
        extracted_text=None,
        embedding_id=None,
        created_at=time.time(),
    )
    _run(chat.insert_attachment(a))

    res = _run(jump("quarterly"))
    kinds = {h["kind"] for h in res["hits"]}
    assert "attachment" in kinds
    hit = next(h for h in res["hits"] if h["kind"] == "attachment")
    assert hit["ref"]["attachment_id"] == a.id
    assert hit["ref"]["thread_id"] == t.id


def test_jump_query_field_alias_accepted(isolated_chat) -> None:
    """``q`` is the canonical key but ``query`` works too."""

    _seed_threads_with_payload(isolated_chat)

    from fastapi.testclient import TestClient

    from web_extras.app import app

    with TestClient(app) as client:
        r1 = client.post("/api/search/jump", json={"q": "mar"})
        r2 = client.post("/api/search/jump", json={"query": "mar"})
    assert r1.status_code == 200 and r2.status_code == 200
    body1 = r1.json()
    body2 = r2.json()
    assert {h["label"] for h in body1["hits"]} == {
        h["label"] for h in body2["hits"]
    }


# ---------------------------------------------------------------------
# HTTP wiring
# ---------------------------------------------------------------------


def test_http_jump_returns_ok_with_hits(isolated_chat) -> None:
    _seed_threads_with_payload(isolated_chat)

    from fastapi.testclient import TestClient

    from web_extras.app import app

    with TestClient(app) as client:
        r = client.post("/api/search/jump", json={"q": "emea", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["count"] > 0
    labels = [h["label"] for h in body["hits"]]
    assert "EMEA blocker" in labels


def test_http_jump_rejects_non_string_query(isolated_chat) -> None:
    from fastapi.testclient import TestClient

    from web_extras.app import app

    with TestClient(app) as client:
        r = client.post("/api/search/jump", json={"q": ["emea"]})
    assert r.status_code == 400


def test_http_jump_rejects_non_list_kinds(isolated_chat) -> None:
    from fastapi.testclient import TestClient

    from web_extras.app import app

    with TestClient(app) as client:
        r = client.post(
            "/api/search/jump", json={"q": "emea", "kinds": "thread"}
        )
    assert r.status_code == 400


def test_http_jump_silently_drops_unknown_kinds(isolated_chat) -> None:
    """Unknown kinds in the list are filtered out, not rejected."""

    _seed_threads_with_payload(isolated_chat)

    from fastapi.testclient import TestClient

    from web_extras.app import app

    with TestClient(app) as client:
        r = client.post(
            "/api/search/jump",
            json={"q": "emea", "kinds": ["thread", "bogus_kind"]},
        )
    assert r.status_code == 200
    body = r.json()
    assert all(h["kind"] == "thread" for h in body["hits"])


def test_http_jump_clamps_limit(isolated_chat) -> None:
    _seed_threads_with_payload(isolated_chat)

    from fastapi.testclient import TestClient

    from web_extras.app import app

    with TestClient(app) as client:
        r = client.post(
            "/api/search/jump", json={"q": "", "limit": 9999}
        )
    body = r.json()
    assert body["ok"] is True
    assert len(body["hits"]) <= 100  # endpoint clamps to 100
