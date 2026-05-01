"""``async_session_scope`` emits paired ``session.opened`` / ``session.closed`` events.

These two boundary events let the meeet event log reconstruct an
operator narrative end-to-end (start, topic, who joined, duration). The
synchronous :func:`session_scope` stays silent so existing call sites
keep their wire shape unchanged — opt-in by switching to
:func:`async_session_scope`.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from backend.core.meeet import (
    async_session_scope,
    current_session,
    get_store,
    reset_client,
    reset_store,
    session_scope,
)


@pytest.fixture()
def isolated_store(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite")
    )
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_LOCAL_LOG", raising=False)
    reset_store()
    reset_client()
    try:
        yield
    finally:
        reset_store()
        reset_client()


def _list_events():
    store = get_store()
    return asyncio.run(store.list_events(limit=20))


def test_sync_session_scope_does_not_emit(isolated_store) -> None:
    with session_scope("ses_silent"):
        assert current_session() == "ses_silent"
    events = _list_events()
    assert events == []


def test_async_session_scope_emits_open_and_close(isolated_store) -> None:
    async def run() -> None:
        async with async_session_scope(
            "ses_alpha",
            topic="morning_standup",
            participants=["operator", "tars"],
        ) as sid:
            assert sid == "ses_alpha"
            assert current_session() == "ses_alpha"

    asyncio.run(run())

    events = _list_events()
    kinds = [e.kind for e in events]
    assert "session.opened" in kinds
    assert "session.closed" in kinds

    by_kind = {e.kind: e for e in events}
    opened = by_kind["session.opened"]
    closed = by_kind["session.closed"]

    assert opened.session_id == "ses_alpha"
    assert closed.session_id == "ses_alpha"

    assert opened.payload["topic"] == "morning_standup"
    assert opened.payload["participants"] == ["operator", "tars"]
    assert isinstance(opened.payload["started_at"], str)
    assert opened.payload["started_at"].endswith("+00:00")

    assert closed.payload["topic"] == "morning_standup"
    assert closed.payload["participants"] == ["operator", "tars"]
    assert closed.payload["started_at"] == opened.payload["started_at"]
    assert isinstance(closed.payload["ended_at"], str)
    assert isinstance(closed.payload["duration_ms"], int)
    assert closed.payload["duration_ms"] >= 0


def test_async_session_scope_generates_id(isolated_store) -> None:
    captured: list[str] = []

    async def run() -> None:
        async with async_session_scope(topic="adhoc") as sid:
            captured.append(sid)

    asyncio.run(run())
    assert captured and captured[0].startswith("ses_")

    events = _list_events()
    by_kind = {e.kind: e for e in events}
    assert by_kind["session.opened"].session_id == captured[0]
    assert by_kind["session.closed"].session_id == captured[0]


def test_async_session_scope_emit_boundary_off(isolated_store) -> None:
    async def run() -> None:
        async with async_session_scope(
            "ses_quiet", emit_boundary=False
        ) as sid:
            assert sid == "ses_quiet"
            assert current_session() == "ses_quiet"

    asyncio.run(run())
    events = _list_events()
    assert events == []


def test_async_session_scope_emits_close_on_exception(isolated_store) -> None:
    async def run() -> None:
        with pytest.raises(RuntimeError):
            async with async_session_scope(
                "ses_explode", topic="bad", participants=["alice"]
            ):
                raise RuntimeError("boom")

    asyncio.run(run())

    events = _list_events()
    kinds = [e.kind for e in events]
    assert kinds.count("session.opened") == 1
    assert kinds.count("session.closed") == 1


def test_async_session_scope_pops_context_after_exit(isolated_store) -> None:
    async def run() -> str | None:
        async with async_session_scope("ses_popme"):
            assert current_session() == "ses_popme"
        return current_session()

    assert asyncio.run(run()) is None


def test_async_session_scope_handles_emit_failure(
    isolated_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A broken ingest path must not crash the wrapped block.

    Patches the underlying ``MeeetClient.emit`` (not the safe wrapper)
    so the ``try/except`` inside ``_safe_emit_session_event`` is what
    actually catches.
    """

    from backend.core.meeet import client as client_mod

    class _BoomClient:
        async def emit(self, *_a, **_kw):  # noqa: ANN001
            raise RuntimeError("ingest_down")

    monkeypatch.setattr(client_mod, "get_client", lambda: _BoomClient())

    async def run() -> str:
        async with async_session_scope("ses_resilient") as sid:
            return sid

    assert asyncio.run(run()) == "ses_resilient"
