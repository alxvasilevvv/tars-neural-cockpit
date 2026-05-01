"""Background message-embed loop wiring.

The follow-up to PR #42 (Vector + BM25 blend for messages). The loop
stays disabled by default — operators opt in via
``TARS_MESSAGE_EMBED_INTERVAL_S``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


def test_interval_helper_defaults_to_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TARS_MESSAGE_EMBED_INTERVAL_S", raising=False)
    from web_extras.app import _message_embed_interval_s

    assert _message_embed_interval_s() == 0.0


def test_interval_helper_parses_float(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARS_MESSAGE_EMBED_INTERVAL_S", "120")
    from web_extras.app import _message_embed_interval_s

    assert _message_embed_interval_s() == pytest.approx(120.0)


def test_interval_helper_clamps_negative(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARS_MESSAGE_EMBED_INTERVAL_S", "-5")
    from web_extras.app import _message_embed_interval_s

    assert _message_embed_interval_s() == 0.0


def test_interval_helper_falls_back_on_garbage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TARS_MESSAGE_EMBED_INTERVAL_S", "not-a-number")
    from web_extras.app import _message_embed_interval_s

    assert _message_embed_interval_s() == 0.0


def test_batch_limit_helper_clamps(monkeypatch: pytest.MonkeyPatch) -> None:
    from web_extras.app import _message_embed_batch_limit

    monkeypatch.setenv("TARS_MESSAGE_EMBED_LIMIT", "5000")
    assert _message_embed_batch_limit() == 1000
    monkeypatch.setenv("TARS_MESSAGE_EMBED_LIMIT", "0")
    assert _message_embed_batch_limit() == 1
    monkeypatch.setenv("TARS_MESSAGE_EMBED_LIMIT", "junk")
    assert _message_embed_batch_limit() == 100


def test_loop_short_circuits_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TARS_MESSAGE_EMBED_INTERVAL_S", raising=False)
    from web_extras.app import _message_embed_loop

    # With interval 0 the loop returns immediately; .run() must not hang.
    asyncio.run(asyncio.wait_for(_message_embed_loop(), timeout=2.0))


def test_loop_runs_one_tick_then_cancels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A single tick walks pending messages, batches the embedder, and
    persists the vectors. We spin the loop with a tiny interval, wait
    for one tick, then cancel."""

    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv("TARS_EMBEDDER", "hash")
    monkeypatch.setenv("MEEET_STORE", "disabled")
    monkeypatch.setenv("TARS_MESSAGE_EMBED_INTERVAL_S", "0.05")
    monkeypatch.setenv("TARS_MESSAGE_EMBED_LIMIT", "20")

    from backend.core.chat import store as chat_store_mod
    from backend.core.chat import Thread
    from backend.core.chat.models import Message
    from backend.core.chat.store import get_chat_store

    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)

    async def scenario() -> None:
        chat = get_chat_store()
        thread = Thread.fresh(title="loop", pack_slug="business")
        await chat.insert_thread(thread)
        await chat.insert_message(
            Message.from_operator(thread.id, "EMEA blocker on three deals")
        )
        await chat.insert_message(
            Message.from_operator(thread.id, "APAC pipeline healthy")
        )
        assert await chat.count_messages_pending_embedding() == 2

        from web_extras.app import _message_embed_loop

        task = asyncio.create_task(_message_embed_loop())
        try:
            for _ in range(40):
                await asyncio.sleep(0.05)
                if await chat.count_messages_pending_embedding() == 0:
                    break
            assert await chat.count_messages_pending_embedding() == 0
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())

    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)


def test_lifespan_starts_and_cancels_message_embed_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The FastAPI lifespan must spin the new loop alongside the others
    without crashing — TestClient explodes on startup error."""

    monkeypatch.delenv("TARS_MESSAGE_EMBED_INTERVAL_S", raising=False)

    from fastapi.testclient import TestClient

    from web_extras.app import app

    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
