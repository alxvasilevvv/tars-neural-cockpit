"""FTS5 drift-detect + auto-repair (Phase L8 follow-up).

Three layers under test:

1. ``verify_and_repair_chat_fts`` — chat WAL DB (``chunks_fts`` +
   ``messages_fts``).
2. ``verify_and_repair_events_fts`` — meeet WAL DB (``events_fts``).
3. ``POST /api/search/fts-repair`` HTTP wiring + boot-time hook
   (``TARS_FTS_VERIFY_ON_BOOT=1``).
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from backend.core.attachments import index as attachment_index_mod
from backend.core.chat import Thread
from backend.core.chat import store as chat_store_mod
from backend.core.chat.models import Message
from backend.core.chat.store import ChatStore, get_chat_store
from backend.core.meeet import store as meeet_store_mod
from backend.core.search.fts import (
    drop_fts_tables,
    ensure_events_fts,
    ensure_fts_indexes,
    verify_and_repair_chat_fts,
    verify_and_repair_events_fts,
)


def _run(coro):
    return asyncio.run(coro)


# =====================================================================
# Chat FTS drift / repair
# =====================================================================


@pytest.fixture()
def isolated_chat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv("TARS_ATTACHMENT_ROOT", str(tmp_path / "attachments"))
    monkeypatch.setenv("MEEET_STORE", "disabled")
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(
        attachment_index_mod, "_SINGLETON", None, raising=False
    )
    # A previous test (test_attachments_chunk_neighbours et al.) may
    # have created an *enabled* MeeetStore singleton pointing at the
    # real ~/.tars/meeet.sqlite. The fts-repair endpoint reads that
    # singleton, sees ``enabled=True``, and tries to repair an
    # ``events_fts`` index that has nothing to do with this test —
    # which appears as ``rebuilt == ['events_fts']`` instead of ``[]``.
    # Drop the singleton so the next ``get_meeet_store()`` re-reads
    # ``MEEET_STORE=disabled`` and short-circuits.
    monkeypatch.setattr(meeet_store_mod, "_SINGLETON", None, raising=False)
    yield
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(
        attachment_index_mod, "_SINGLETON", None, raising=False
    )
    monkeypatch.setattr(meeet_store_mod, "_SINGLETON", None, raising=False)


def _seed_messages(chat: ChatStore, n: int = 5) -> str:
    thread = Thread.fresh(title="x", pack_slug="business")
    _run(chat.insert_thread(thread))
    for i in range(n):
        _run(
            chat.insert_message(
                Message.from_operator(thread.id, f"EMEA blocker note {i}")
            )
        )
    return thread.id


def _wipe_fts_messages(chat: ChatStore) -> None:
    conn = sqlite3.connect(chat.db_path)
    try:
        conn.execute("DELETE FROM messages_fts")
        conn.commit()
    finally:
        conn.close()


def test_repair_no_drift_returns_idempotent(isolated_chat) -> None:
    chat = get_chat_store()
    _seed_messages(chat, 3)
    ensure_fts_indexes(chat=chat)

    out = verify_and_repair_chat_fts(chat=chat)
    assert out["ok"] is True
    assert out["rebuilt"] == []
    by_name = {s["name"]: s for s in out["scopes"]}
    assert by_name["messages_fts"]["fts"] == 3
    assert by_name["messages_fts"]["source"] == 3
    assert by_name["messages_fts"]["rebuilt"] is False


def test_repair_detects_drift_when_fts_wiped(isolated_chat) -> None:
    chat = get_chat_store()
    _seed_messages(chat, 4)
    ensure_fts_indexes(chat=chat)
    _wipe_fts_messages(chat)

    out = verify_and_repair_chat_fts(chat=chat)
    assert out["ok"] is True
    assert "messages_fts" in out["rebuilt"]
    by_name = {s["name"]: s for s in out["scopes"]}
    assert by_name["messages_fts"]["rebuilt"] is True
    assert by_name["messages_fts"]["inserted"] == 4
    assert by_name["messages_fts"]["fts"] == 0
    assert by_name["messages_fts"]["source"] == 4


def test_repair_force_rebuilds_both_indexes(isolated_chat) -> None:
    chat = get_chat_store()
    _seed_messages(chat, 2)
    ensure_fts_indexes(chat=chat)

    out = verify_and_repair_chat_fts(chat=chat, force=True)
    assert out["ok"] is True
    assert "messages_fts" in out["rebuilt"]
    assert "chunks_fts" in out["rebuilt"]


def test_repair_handles_dropped_fts_tables(isolated_chat) -> None:
    chat = get_chat_store()
    _seed_messages(chat, 2)
    ensure_fts_indexes(chat=chat)
    drop_fts_tables(chat=chat)

    out = verify_and_repair_chat_fts(chat=chat)
    assert out["ok"] is True
    by_name = {s["name"]: s for s in out["scopes"]}
    assert by_name["messages_fts"]["rebuilt"] is True
    assert by_name["messages_fts"]["inserted"] == 2


def test_repair_returns_disabled_when_chat_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TARS_CHAT_STORE", "disabled")
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "x.sqlite"))
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)

    out = verify_and_repair_chat_fts()
    assert out["ok"] is False
    assert out["reason"] == "chat_store_disabled"
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)


# =====================================================================
# Events FTS drift / repair
# =====================================================================


def test_repair_events_no_drift(tmp_path: Path) -> None:
    db = tmp_path / "meeet.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL, trace_id TEXT, kind TEXT,
            source TEXT, contract_version TEXT,
            payload TEXT, session_id TEXT,
            pushed INTEGER NOT NULL DEFAULT 0,
            pushed_at REAL, last_error TEXT,
            route TEXT, ciphertext TEXT, envelope TEXT
        );
        INSERT INTO events (ts, trace_id, kind, source, contract_version, payload)
            VALUES
            (1, 't1', 'a.completed', 's', '1', '{}'),
            (2, 't2', 'b.completed', 's', '1', '{}'),
            (3, 't3', 'c.failed',    's', '1', '{}');
        """
    )
    conn.commit()
    conn.close()

    ensure_events_fts(str(db))
    out = verify_and_repair_events_fts(str(db))
    assert out["ok"] is True
    assert out["rebuilt"] == []
    assert out["scopes"][0]["fts"] == 3
    assert out["scopes"][0]["source"] == 3


def test_repair_events_detects_drift_after_fts_wipe(tmp_path: Path) -> None:
    db = tmp_path / "meeet.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL, trace_id TEXT, kind TEXT,
            source TEXT, contract_version TEXT,
            payload TEXT, session_id TEXT,
            pushed INTEGER NOT NULL DEFAULT 0,
            pushed_at REAL, last_error TEXT,
            route TEXT, ciphertext TEXT, envelope TEXT
        );
        INSERT INTO events (ts, trace_id, kind, source, contract_version, payload)
            VALUES (1, 't1', 'a', 's', '1', 'EMEA blocker payload');
        """
    )
    conn.commit()
    conn.close()

    ensure_events_fts(str(db))
    # wipe the FTS contents — simulates a backup/restore that brought
    # source rows but forgot the FTS shadow.
    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM events_fts")
    conn.commit()
    conn.close()

    out = verify_and_repair_events_fts(str(db))
    assert out["ok"] is True
    assert "events_fts" in out["rebuilt"]
    assert out["scopes"][0]["inserted"] == 1


def test_repair_events_returns_disabled_when_path_blank() -> None:
    out = verify_and_repair_events_fts("")
    assert out["ok"] is False
    assert out["reason"] == "meeet_store_disabled"


# =====================================================================
# HTTP endpoint + boot hook
# =====================================================================


@pytest.fixture()
def http_app(isolated_chat):
    from fastapi.testclient import TestClient

    from web_extras.app import app

    with TestClient(app) as client:
        yield client


def test_endpoint_returns_no_drift_when_indexes_are_synced(
    http_app,
) -> None:
    chat = get_chat_store()
    _seed_messages(chat, 2)
    ensure_fts_indexes(chat=chat)

    resp = http_app.post("/api/search/fts-repair")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "chat" in body
    assert body["chat"]["ok"] is True
    assert body["rebuilt"] == []
    # Events scope is disabled in this fixture (MEEET_STORE=disabled).
    assert body["events"]["ok"] is False


def test_endpoint_rebuilds_after_fts_wipe(http_app) -> None:
    chat = get_chat_store()
    _seed_messages(chat, 3)
    ensure_fts_indexes(chat=chat)
    _wipe_fts_messages(chat)

    resp = http_app.post("/api/search/fts-repair")
    body = resp.json()
    assert resp.status_code == 200
    assert body["ok"] is True
    assert "messages_fts" in body["rebuilt"]


def test_endpoint_force_flag(http_app) -> None:
    chat = get_chat_store()
    _seed_messages(chat, 2)
    ensure_fts_indexes(chat=chat)

    resp = http_app.post(
        "/api/search/fts-repair", json={"force": True, "scopes": ["chat"]}
    )
    body = resp.json()
    assert resp.status_code == 200
    assert "messages_fts" in body["rebuilt"]
    assert "chunks_fts" in body["rebuilt"]
    assert "events" not in body  # scoped to chat only


def test_endpoint_rejects_non_list_scopes(http_app) -> None:
    resp = http_app.post(
        "/api/search/fts-repair", json={"scopes": "chat"}
    )
    assert resp.status_code == 400


def test_boot_hook_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TARS_FTS_VERIFY_ON_BOOT", raising=False)
    from web_extras.app import _fts_verify_on_boot

    assert _fts_verify_on_boot() is False


def test_boot_hook_recognises_truthy_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from web_extras.app import _fts_verify_on_boot

    for raw in ("1", "true", "TRUE", "Yes", "on"):
        monkeypatch.setenv("TARS_FTS_VERIFY_ON_BOOT", raw)
        assert _fts_verify_on_boot() is True


def test_boot_hook_rebuilds_on_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: env flag on + drifted FTS → boot rebuilds."""

    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv("MEEET_STORE", "disabled")
    monkeypatch.setenv("TARS_FTS_VERIFY_ON_BOOT", "1")
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)

    chat = get_chat_store()
    _seed_messages(chat, 5)
    ensure_fts_indexes(chat=chat)
    _wipe_fts_messages(chat)

    from fastapi.testclient import TestClient

    from web_extras.app import app

    # Lifespan enter triggers _verify_fts_on_boot.
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200

    # After boot, the FTS rows should be back.
    conn = sqlite3.connect(chat.db_path)
    try:
        cnt = conn.execute("SELECT COUNT(*) FROM messages_fts").fetchone()[0]
    finally:
        conn.close()
    assert cnt == 5

    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
