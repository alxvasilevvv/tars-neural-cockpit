"""Saved-search auto-poll lifespan loop.

Pins the env-driven cadence helpers, the loop's short-circuit when
disabled, single-tick behaviour over the live ``poll_all_saved_searches``
helper, and the lifespan wiring (so pulling the kill switch shuts the
task down cleanly).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.core.attachments import index as attachment_index_mod
from backend.core.chat import SavedSearch, Thread
from backend.core.chat import store as chat_store_mod
from backend.core.chat.models import Message
from backend.core.chat.store import get_chat_store
from backend.core.search import alerts as alerts_mod
from web_extras import app as app_mod


# ---------------------------------------------------------------------
# Env helpers
# ---------------------------------------------------------------------


def test_interval_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TARS_SAVED_SEARCH_POLL_INTERVAL_S", raising=False)
    assert app_mod._saved_search_poll_interval_s() == 0.0


def test_interval_parses_float(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARS_SAVED_SEARCH_POLL_INTERVAL_S", "120")
    assert app_mod._saved_search_poll_interval_s() == 120.0


def test_interval_clamps_negative_to_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TARS_SAVED_SEARCH_POLL_INTERVAL_S", "-5")
    assert app_mod._saved_search_poll_interval_s() == 0.0


def test_interval_treats_garbage_as_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TARS_SAVED_SEARCH_POLL_INTERVAL_S", "abc")
    assert app_mod._saved_search_poll_interval_s() == 0.0


def test_top_k_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TARS_SAVED_SEARCH_POLL_TOP_K", raising=False)
    assert app_mod._saved_search_poll_top_k() == 25


def test_top_k_clamps_to_max(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARS_SAVED_SEARCH_POLL_TOP_K", "9999")
    assert app_mod._saved_search_poll_top_k() == 100


def test_top_k_clamps_to_min(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARS_SAVED_SEARCH_POLL_TOP_K", "0")
    assert app_mod._saved_search_poll_top_k() == 1


def test_limit_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TARS_SAVED_SEARCH_POLL_LIMIT", raising=False)
    assert app_mod._saved_search_poll_limit() == 100


def test_limit_clamps_to_max(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARS_SAVED_SEARCH_POLL_LIMIT", "9999")
    assert app_mod._saved_search_poll_limit() == 500


# ---------------------------------------------------------------------
# Loop behaviour
# ---------------------------------------------------------------------


def test_loop_short_circuits_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TARS_SAVED_SEARCH_POLL_INTERVAL_S", raising=False)

    # If the loop didn't short-circuit it would block forever; running
    # it under asyncio.run + a timeout shows that the early-return
    # path returns instantly.
    async def go():
        await asyncio.wait_for(app_mod._saved_search_poll_loop(), timeout=1.0)

    asyncio.run(go())


def test_loop_runs_one_tick_and_alerts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv("TARS_ATTACHMENT_ROOT", str(tmp_path / "attachments"))
    monkeypatch.setenv("MEEET_STORE", "disabled")
    monkeypatch.setenv("TARS_SAVED_SEARCH_POLL_INTERVAL_S", "0.05")
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(
        attachment_index_mod, "_SINGLETON", None, raising=False
    )

    captured: list[tuple[str, dict]] = []

    class _Stub:
        async def emit(self, kind: str, payload: dict) -> None:
            captured.append((kind, dict(payload)))

    monkeypatch.setattr(alerts_mod, "get_client", lambda: _Stub())

    async def go():
        chat = get_chat_store()
        t = Thread.fresh(title="deal", pack_slug="business")
        await chat.insert_thread(t)
        await chat.insert_message(Message.from_operator(t.id, "EMEA initial"))
        s = SavedSearch.fresh(label="emea", query="EMEA", scope="messages")
        await chat.insert_saved_search(s)
        # First tick → seed (no alert).
        # Second tick → drift (we'll inject a new message between
        # ticks and let the loop fire).

        task = asyncio.create_task(app_mod._saved_search_poll_loop())
        try:
            # Wait for the first tick to seed.
            await asyncio.sleep(0.12)
            await chat.insert_message(
                Message.from_operator(t.id, "EMEA fresh news")
            )
            # Wait for at least one more tick.
            await asyncio.sleep(0.12)
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        return captured

    out = asyncio.run(go())
    # We saw one or more alerts (the loop may have ticked multiple
    # times — the alerts module's idempotence ensures only the first
    # genuine drift fires).
    assert any(k == "saved_search.new_hits" for k, _ in out), (
        f"expected at least one alert event, got: {out}"
    )
    # Reset singletons so other tests don't pick up our DB.
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(
        attachment_index_mod, "_SINGLETON", None, raising=False
    )


def test_lifespan_starts_and_cancels_saved_search_poll(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The TestClient's ``__enter__``/``__exit__`` round-trip should
    spin the loop up and shut it down without raising."""

    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv("MEEET_STORE", "disabled")
    monkeypatch.setenv("TARS_SAVED_SEARCH_POLL_INTERVAL_S", "60")
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)

    from fastapi.testclient import TestClient

    from web_extras.app import app

    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200

    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
