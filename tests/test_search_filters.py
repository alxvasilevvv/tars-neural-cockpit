"""Operator query DSL — extracts scoped filters and rewrites them
through the unified search engine.

Three layers under test:

1. :func:`parse_query_filters` token recognition + cleanup.
2. Time-bound coercion (``since:7d``, ``since:2026-04-01``).
3. End-to-end wiring: ``search`` / ``search_messages`` /
   ``search_traces`` honour parsed filters.
"""

from __future__ import annotations

import asyncio
import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.core.attachments import index as attachment_index_mod
from backend.core.chat import store as chat_store_mod
from backend.core.chat import Thread
from backend.core.chat.models import Message
from backend.core.chat.store import get_chat_store
from backend.core.search import (
    search,
    search_messages,
    search_traces,
)
from backend.core.search.filters import (
    ParsedQuery,
    merge_filters,
    parse_query_filters,
)


def _run(coro):
    return asyncio.run(coro)


# =====================================================================
# Parser
# =====================================================================


def test_empty_query_returns_empty_parsed() -> None:
    out = parse_query_filters("")
    assert out.text == ""
    assert out.filters == {}
    assert out.filters_neg == {}


def test_blank_only_query_returns_empty_parsed() -> None:
    out = parse_query_filters("   \n\t ")
    assert out.text == ""


def test_no_tokens_returns_query_unchanged() -> None:
    out = parse_query_filters("EMEA blocker GDPR")
    assert out.text == "EMEA blocker GDPR"
    assert out.filters == {}


def test_single_role_token_extracted() -> None:
    out = parse_query_filters("EMEA role:operator blocker")
    assert out.filters == {"role": "operator"}
    assert out.text == "EMEA blocker"


def test_multiple_tokens_extracted_and_text_cleaned() -> None:
    out = parse_query_filters(
        "pack:business EMEA role:operator GDPR thread:thr_abc"
    )
    assert out.filters["pack"] == "business"
    assert out.filters["role"] == "operator"
    assert out.filters["thread"] == "thr_abc"
    assert out.text == "EMEA GDPR"


def test_quoted_value_preserves_spaces() -> None:
    out = parse_query_filters('foo pack:"my pack" bar')
    assert out.filters["pack"] == "my pack"
    assert out.text == "foo bar"


def test_repeated_key_collapses_to_list() -> None:
    out = parse_query_filters("a pack:business pack:traders b")
    assert out.filters["pack"] == ["business", "traders"]


def test_negation_lands_in_filters_neg() -> None:
    out = parse_query_filters("foo -role:tool bar")
    assert out.filters == {}
    assert out.filters_neg == {"role": "tool"}
    assert out.text == "foo bar"


def test_unknown_key_left_in_text() -> None:
    out = parse_query_filters("foo color:red bar role:operator")
    assert "color:red" in out.text
    assert out.filters == {"role": "operator"}


def test_token_at_start_and_end() -> None:
    out = parse_query_filters("role:operator EMEA")
    assert out.text == "EMEA"
    assert out.filters == {"role": "operator"}

    out2 = parse_query_filters("EMEA role:operator")
    assert out2.text == "EMEA"
    assert out2.filters == {"role": "operator"}


def test_keys_are_case_insensitive_values_preserved() -> None:
    out = parse_query_filters("ROLE:Operator KIND:Domain.Action")
    assert out.filters == {"role": "Operator", "kind": "Domain.Action"}


# =====================================================================
# Time bounds
# =====================================================================


def test_since_relative_days() -> None:
    before = time.time()
    out = parse_query_filters("foo since:7d")
    after = time.time()
    assert "since" in out.filters
    delta = before - out.filters["since"]
    assert 7 * 86400 - 1 <= delta <= 7 * 86400 + (after - before) + 1


def test_since_relative_hours() -> None:
    out = parse_query_filters("foo since:24h")
    delta = time.time() - out.filters["since"]
    assert math.isclose(delta, 24 * 3600, abs_tol=2.0)


def test_since_iso_date() -> None:
    out = parse_query_filters("foo since:2026-04-01")
    assert "since" in out.filters
    expected = datetime(2026, 4, 1, tzinfo=timezone.utc).timestamp()
    assert math.isclose(out.filters["since"], expected, abs_tol=1.0)


def test_until_iso_timestamp() -> None:
    out = parse_query_filters("foo until:2026-04-01T12:00")
    assert "until" in out.filters
    expected = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc).timestamp()
    assert math.isclose(out.filters["until"], expected, abs_tol=1.0)


def test_invalid_relative_drops_silently() -> None:
    out = parse_query_filters("foo since:bogus")
    assert "since" not in out.filters
    # Garbage value drops; the cleaned text retains "foo".
    assert "foo" in out.text


def test_invalid_iso_drops_silently() -> None:
    out = parse_query_filters("foo since:2026-13-99")
    assert "since" not in out.filters


# =====================================================================
# merge_filters
# =====================================================================


def test_merge_filters_explicit_wins() -> None:
    parsed = ParsedQuery(text="x", filters={"role": "operator"})
    out = merge_filters(parsed=parsed, explicit={"role": "tars"})
    assert out["role"] == "tars"


def test_merge_filters_keeps_parsed_when_no_explicit() -> None:
    parsed = ParsedQuery(text="x", filters={"pack": "business"})
    out = merge_filters(parsed=parsed, explicit=None)
    assert out["pack"] == "business"


def test_merge_filters_explicit_none_value_ignored() -> None:
    parsed = ParsedQuery(text="x", filters={"role": "operator"})
    out = merge_filters(
        parsed=parsed, explicit={"role": None, "pack": "business"}
    )
    assert out["role"] == "operator"
    assert out["pack"] == "business"


# =====================================================================
# Engine integration
# =====================================================================


@pytest.fixture()
def chat_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv("TARS_ATTACHMENT_ROOT", str(tmp_path / "attachments"))
    monkeypatch.setenv("TARS_EMBEDDER", "hash")
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


def _seed_two_packs():
    chat = get_chat_store()
    biz = Thread.fresh(title="biz", pack_slug="business")
    trd = Thread.fresh(title="trd", pack_slug="traders")
    _run(chat.insert_thread(biz))
    _run(chat.insert_thread(trd))
    _run(
        chat.insert_message(
            Message.from_operator(biz.id, "EMEA blocker on three deals")
        )
    )
    _run(
        chat.insert_message(
            Message.from_operator(trd.id, "EMEA risk-on bias on rally")
        )
    )
    return biz, trd


def test_search_messages_role_filter_via_query(chat_env) -> None:
    biz, _ = _seed_two_packs()
    chat = get_chat_store()
    # Operator + tars rows for the same query body.
    _run(
        chat.insert_message(
            Message(
                id="msg_tars",
                thread_id=biz.id,
                role="tars",
                content="EMEA pipeline summary",
                created_at=time.time(),
            )
        )
    )
    hits = _run(search_messages("EMEA role:operator"))
    assert hits
    assert all(h.ref["role"] == "operator" for h in hits)


def test_search_messages_pack_filter_via_query(chat_env) -> None:
    biz, trd = _seed_two_packs()
    biz_hits = _run(search_messages("EMEA pack:business"))
    assert biz_hits
    assert all(h.ref["thread_id"] == biz.id for h in biz_hits)

    trd_hits = _run(search_messages("EMEA pack:traders"))
    assert trd_hits
    assert all(h.ref["thread_id"] == trd.id for h in trd_hits)


def test_search_messages_since_filter_clamps(chat_env) -> None:
    chat = get_chat_store()
    biz = Thread.fresh(title="biz", pack_slug="business")
    _run(chat.insert_thread(biz))
    old_ts = (datetime.now(timezone.utc) - timedelta(days=30)).timestamp()
    _run(
        chat.insert_message(
            Message(
                id="msg_old",
                thread_id=biz.id,
                role="operator",
                content="EMEA legacy blocker note",
                created_at=old_ts,
            )
        )
    )
    _run(
        chat.insert_message(
            Message.from_operator(biz.id, "EMEA fresh blocker today")
        )
    )

    recent = _run(search_messages("EMEA since:7d"))
    assert recent
    ids = {h.ref["msg_id"] for h in recent}
    assert "msg_old" not in ids


def test_search_messages_explicit_kwarg_wins_over_inline(chat_env) -> None:
    biz, trd = _seed_two_packs()
    # Inline says traders, explicit kwarg says business — explicit wins.
    biz_hits = _run(
        search_messages(
            "EMEA pack:traders", pack="business"
        )
    )
    assert biz_hits
    assert all(h.ref["thread_id"] == biz.id for h in biz_hits)


def test_search_unified_returns_filters_and_cleaned_query(chat_env) -> None:
    biz, _ = _seed_two_packs()
    res = _run(search("EMEA role:operator pack:business"))
    payload = res.to_dict()
    assert payload["filters"] == {
        "role": "operator", "pack": "business"
    }
    assert payload["cleaned_query"] == "EMEA"
    assert payload["query"] == "EMEA role:operator pack:business"
    # Hits land — at minimum the operator EMEA blocker row.
    assert payload["count"] >= 1


def test_search_traces_filters_passthrough(chat_env) -> None:
    """When the meeet store is disabled (test env) the call returns
    [] but must not raise on parsed filters."""

    out = _run(
        search_traces(
            "foo kind:domain.action.completed since:7d trace:trc_abc"
        )
    )
    assert out == []


# =====================================================================
# HTTP wiring
# =====================================================================


@pytest.fixture()
def http_app(chat_env):
    from fastapi.testclient import TestClient

    from web_extras.app import app

    with TestClient(app) as client:
        yield client


def test_unified_endpoint_returns_filters(http_app) -> None:
    biz, _ = _seed_two_packs()
    resp = http_app.post(
        "/api/search",
        json={"query": "EMEA role:operator pack:business", "scope": "all"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["filters"]["role"] == "operator"
    assert body["filters"]["pack"] == "business"
    assert body["cleaned_query"] == "EMEA"


def test_messages_endpoint_honours_inline_filter(http_app) -> None:
    biz, trd = _seed_two_packs()
    resp = http_app.post(
        "/api/search/messages",
        json={"query": "EMEA pack:business"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    for h in body["hits"]:
        assert h["ref"]["thread_id"] == biz.id


def test_saved_search_run_carries_inline_filter(http_app) -> None:
    biz, trd = _seed_two_packs()
    create = http_app.post(
        "/api/search/saved",
        json={
            "label": "EMEA biz",
            "query": "EMEA pack:business",
            "scope": "messages",
        },
    )
    sv_id = create.json()["item"]["id"]
    run = http_app.post(f"/api/search/saved/{sv_id}/run")
    assert run.status_code == 200
    body = run.json()
    for h in body["hits"]:
        assert h["ref"]["thread_id"] == biz.id
