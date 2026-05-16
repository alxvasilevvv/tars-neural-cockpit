"""W231 — boot-time DB init tests.

Exercises ``backend.core.storage.bootstrap.init_all_databases`` against
a sandbox ``TARS_HOME`` so the user's real ``~/.tars`` is never
touched. Four scenarios:

* fresh empty directory                        — seeds run, files appear.
* re-run on an already-initialised directory   — idempotent (no dup rows,
                                                 no exception, agents stays
                                                 at count 1).
* partial state — only `agents.sqlite` exists  — bootstrap fills the rest
                                                 and skips the agent seed
                                                 because one is already present.
* the returned :class:`BootstrapResult` shape  — must be JSON-friendly
                                                 with ``ok=True`` semantics.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def _flush_singletons() -> None:
    """Drop cached store singletons so the next call picks up the
    new ``TARS_HOME``/path env override."""

    # Agents
    try:
        from backend.core.agents import store as _agents_store  # type: ignore

        _agents_store._SINGLETON = None
    except Exception:
        pass
    # Receipts
    try:
        from backend.core.receipts import store as _r_store  # type: ignore

        _r_store._STORE = None
    except Exception:
        pass
    # Meeet (best effort — module exposes get_store but may not have a
    # module-level singleton symbol we can null out)
    try:
        from backend.core.meeet import store as _m_store  # type: ignore

        for attr in ("_STORE", "_SINGLETON"):
            if hasattr(_m_store, attr):
                setattr(_m_store, attr, None)
    except Exception:
        pass


@pytest.fixture
def sandbox_tars_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every TARS path env var at a per-test tmp dir."""

    home = tmp_path / "tars-home"
    monkeypatch.setenv("TARS_HOME", str(home))
    # Pin every store path env at the new home so the various stores
    # we touch don't smear into the real user home.
    monkeypatch.setenv("TARS_AGENTS_DB_PATH", str(home / "agents.sqlite"))
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(home / "chat.sqlite"))
    monkeypatch.setenv("TARS_MEMORY_DB_PATH", str(home / "memory.sqlite"))
    monkeypatch.setenv("TARS_MEEET_DB_PATH", str(home / "meeet.sqlite"))
    monkeypatch.setenv("TARS_POLICY_DB_PATH", str(home / "policy.sqlite"))
    monkeypatch.setenv("TARS_SCHEDULER_DB_PATH", str(home / "scheduler.sqlite"))
    monkeypatch.setenv("TARS_WORKSPACES_DB_PATH", str(home / "workspaces.sqlite"))
    monkeypatch.setenv("TARS_WEBHOOKS_DB_PATH", str(home / "webhooks.sqlite"))
    monkeypatch.setenv("TARS_RECEIPT_DB_PATH", str(home / "receipts.sqlite"))
    monkeypatch.setenv("TARS_RECEIPT_NDJSON_DIR", str(home / "receipts"))
    monkeypatch.setenv("TARS_RECEIPT_HOST_KEY_PATH", str(home / "host-key.json"))
    # Disable Solana / webhook side effects.
    monkeypatch.delenv("TARS_RECEIPT_ANCHOR_ENABLED", raising=False)
    monkeypatch.delenv("TARS_WEBHOOKS_ENABLED", raising=False)
    _flush_singletons()
    yield home
    _flush_singletons()


@pytest.mark.asyncio
async def test_init_all_databases_fresh(sandbox_tars_home: Path) -> None:
    """First run creates the dir, seeds agent + welcome receipt."""

    from backend.core.storage import init_all_databases

    result = await init_all_databases()

    assert Path(result.tars_dir).exists()
    # 0o700 perms when possible (skip on platforms that don't honour chmod)
    try:
        mode = Path(result.tars_dir).stat().st_mode & 0o777
        assert mode in (0o700, 0o755)  # macOS / Linux sometimes coerce
    except OSError:
        pass

    payload = result.to_dict()
    assert payload["ok"] is True
    assert "agents_store" in payload["steps_ok"]
    assert "receipts_store" in payload["steps_ok"]
    # Seeded blocks present and positive.
    agent = payload["seeded"].get("agent") or {}
    assert agent.get("seeded") is True
    assert agent.get("pack") == "web_search"
    receipt = payload["seeded"].get("receipt") or {}
    assert receipt.get("seeded") is True
    assert receipt.get("receipt_id")


@pytest.mark.asyncio
async def test_init_all_databases_idempotent(sandbox_tars_home: Path) -> None:
    """Second call must not duplicate seeded rows or raise."""

    from backend.core.storage import init_all_databases
    from backend.core.agents import get_agent_store

    first = await init_all_databases()
    _flush_singletons()

    store = get_agent_store()
    first_agents = await store.list_agents(include_archived=True)
    assert any(a.name == "TARS Default" for a in first_agents)
    first_count = len(first_agents)

    second = await init_all_databases()

    # Re-run reports the agent seed step as already-existing.
    agent_seed = second.seeded.get("agent") or {}
    assert agent_seed.get("seeded") is False
    assert agent_seed.get("reason") == "already_exists"
    # And the agent count is stable (no duplicates from re-seed).
    store = get_agent_store()
    agents = await store.list_agents(include_archived=True)
    assert len(agents) == first_count
    assert any(a.name == "TARS Default" for a in agents)


@pytest.mark.asyncio
async def test_init_all_databases_handles_partial_state(
    sandbox_tars_home: Path,
) -> None:
    """If only agents.sqlite already exists with a row, seed should
    skip the agent block but still create / verify every other store."""

    from backend.core.storage import init_all_databases
    from backend.core.agents import get_agent_store

    # Seed an unrelated agent so the bootstrap will short-circuit
    # its own seed.
    store = get_agent_store()
    await store.create_agent(
        name="Pre-existing agent",
        pack_slug="web_search",
        description="set up by the test before bootstrap ran",
    )

    _flush_singletons()
    result = await init_all_databases()

    agent_seed = result.seeded.get("agent") or {}
    assert agent_seed.get("seeded") is False
    assert agent_seed.get("reason") in {"already_exists", "agents_store_disabled"}
    # Other stores still touched.
    assert "memory_store" in result.steps_ok
    assert "scheduler_store" in result.steps_ok
    # Sandbox dir exists with files in it.
    assert (sandbox_tars_home / "agents.sqlite").exists()


@pytest.mark.asyncio
async def test_init_all_databases_result_shape(sandbox_tars_home: Path) -> None:
    """``BootstrapResult.to_dict`` must be JSON-serialisable and carry
    the keys the cockpit / docs promise."""

    import json

    from backend.core.storage import init_all_databases

    result = await init_all_databases()
    blob = result.to_dict()
    # Round-trips through JSON unmodified.
    encoded = json.dumps(blob, default=str)
    decoded = json.loads(encoded)
    for key in ("ok", "tars_dir", "steps_ok", "steps_warn", "seeded", "elapsed_ms"):
        assert key in decoded, f"missing key: {key}"
    assert isinstance(decoded["steps_ok"], list)
    assert isinstance(decoded["steps_warn"], list)
    assert decoded["elapsed_ms"] >= 0
