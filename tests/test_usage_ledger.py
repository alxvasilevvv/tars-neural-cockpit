"""Tests for the cost / token rollup ledger."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.core.meeet import MeeetStore
from backend.core.usage import (
    PriceEntry,
    PriceTable,
    UsageLedger,
    default_price_table,
)


def _store(tmp_path: Path) -> MeeetStore:
    return MeeetStore(str(tmp_path / "meeet.sqlite"))


def _ledger(store: MeeetStore, prices: PriceTable | None = None) -> UsageLedger:
    return UsageLedger(price_table=prices, store=store)


def _seed_event(
    store: MeeetStore,
    *,
    model: str,
    tokens_in: int,
    tokens_out: int,
    session_id: str | None = "ses_x",
    route: str | None = "cloud",
    kind: str = "usage.tokens",
    cost_usd=None,
):
    payload = {
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": 12.5,
    }
    if cost_usd is not None:
        payload["cost_usd"] = cost_usd
    return store.insert(
        {
            "kind": kind,
            "trace_id": "trc",
            "ts": 1.0,
            "payload": payload,
            "source": "tars",
            "contract_version": "1.0.0",
            "session_id": session_id,
            "route": route,
        }
    )


def test_default_price_table_known_models() -> None:
    table = default_price_table()
    sonnet = table.lookup("anthropic/claude-3-5-sonnet-20241022")
    assert sonnet is not None and sonnet.input_per_mtok == 3.0
    mini = table.lookup("openai/gpt-4o-mini")
    assert mini is not None and mini.output_per_mtok == 0.60
    assert table.lookup("nope/whatever") is None


def test_price_table_cost_calc() -> None:
    table = PriceTable(entries={"foo/bar": PriceEntry(2.0, 4.0)})
    cost = table.cost_usd("foo/bar", tokens_in=500_000, tokens_out=250_000)
    assert cost == 2.0 * 0.5 + 4.0 * 0.25
    assert table.cost_usd("foo/bar", 0, 0) == 0.0
    assert table.cost_usd("missing", 100, 100) is None


def test_ledger_lines_pull_from_store(tmp_path: Path) -> None:
    store = _store(tmp_path)
    ledger = _ledger(store)

    async def run() -> list:
        await _seed_event(store, model="anthropic/claude-3-5-sonnet-20241022", tokens_in=100, tokens_out=50)
        await _seed_event(store, model="openai/gpt-4o-mini", tokens_in=200, tokens_out=80)
        return await ledger.list_lines()

    lines = asyncio.run(run())
    assert len(lines) == 2
    by_model = {ln.model: ln for ln in lines}
    assert by_model["anthropic/claude-3-5-sonnet-20241022"].cost_usd is not None
    assert by_model["openai/gpt-4o-mini"].tokens_in == 200


def test_ledger_rollup_groups_by_model_and_route(tmp_path: Path) -> None:
    store = _store(tmp_path)
    ledger = _ledger(store)

    async def run():
        await _seed_event(store, model="openai/gpt-4o-mini", tokens_in=1000, tokens_out=500, route="cloud", session_id="ses_1")
        await _seed_event(store, model="openai/gpt-4o-mini", tokens_in=200, tokens_out=100, route="cloud", session_id="ses_1")
        await _seed_event(store, model="tars-local-v1", tokens_in=0, tokens_out=0, route="edge", session_id="ses_1")
        await _seed_event(store, model="anthropic/claude-3-5-sonnet-20241022", tokens_in=10, tokens_out=20, route="cloud", session_id="ses_2")
        return await ledger.rollup()

    rollup = asyncio.run(run())
    assert rollup.total_calls == 4
    assert rollup.total_tokens_in == 1210
    assert rollup.by_model["openai/gpt-4o-mini"]["calls"] == 2
    assert rollup.by_route["cloud"]["calls"] == 3
    assert rollup.by_route["edge"]["calls"] == 1
    assert "ses_1" in rollup.by_session
    assert "ses_2" in rollup.by_session


def test_ledger_uses_payload_cost_when_provided(tmp_path: Path) -> None:
    store = _store(tmp_path)
    ledger = _ledger(store)

    async def run():
        await _seed_event(
            store,
            model="weird/voice",  # not in price table
            tokens_in=1000,
            tokens_out=500,
            cost_usd=0.42,
        )
        return await ledger.list_lines()

    lines = asyncio.run(run())
    assert lines[0].cost_usd == 0.42


def test_ledger_rolls_up_unknown_model_with_none_cost(tmp_path: Path) -> None:
    store = _store(tmp_path)
    ledger = _ledger(store)

    async def run():
        await _seed_event(
            store,
            model="weird/voice",
            tokens_in=1000,
            tokens_out=500,
        )
        return await ledger.rollup()

    rollup = asyncio.run(run())
    assert rollup.total_calls == 1
    assert rollup.total_cost_usd == 0.0  # unknown model contributes nothing
    assert "weird/voice" in rollup.by_model


def test_ledger_filters_by_session(tmp_path: Path) -> None:
    store = _store(tmp_path)
    ledger = _ledger(store)

    async def run():
        await _seed_event(store, model="openai/gpt-4o-mini", tokens_in=100, tokens_out=50, session_id="ses_a")
        await _seed_event(store, model="openai/gpt-4o-mini", tokens_in=200, tokens_out=100, session_id="ses_b")
        return await ledger.rollup(session_id="ses_b")

    rollup = asyncio.run(run())
    assert rollup.total_calls == 1
    assert rollup.total_tokens_in == 200
