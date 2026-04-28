"""Smoke tests for the meeet.world bridge.

Cover the no-op path, local jsonl logging, and trace propagation. Network
calls are stubbed so tests stay offline.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from backend.core.meeet import (
    MeeetClient,
    MeeetStore,
    TARSEvent,
    current_trace,
    new_trace_id,
    start_trace,
    trace_scope,
)
from backend.core.meeet.config import MeeetConfig


def test_new_trace_id_unique() -> None:
    a = new_trace_id()
    b = new_trace_id()
    assert a != b
    assert a.startswith("trc_")


def test_start_trace_and_current() -> None:
    trace_id = start_trace()
    assert current_trace() == trace_id

    parent = "trc_external_abc"
    forced = start_trace(parent=parent)
    assert forced == parent
    assert current_trace() == parent


def test_trace_scope_restores_previous() -> None:
    start_trace(parent="trc_outer")
    with trace_scope(parent="trc_inner") as inner:
        assert inner == "trc_inner"
        assert current_trace() == "trc_inner"
    assert current_trace() == "trc_outer"


def test_event_to_dict_shape() -> None:
    e = TARSEvent(
        trace_id="trc_x",
        kind="test.event",
        payload={"slug": "traders"},
    )
    d = e.to_dict()
    assert d["trace_id"] == "trc_x"
    assert d["kind"] == "test.event"
    assert d["source"] == "tars"
    assert d["contract_version"] == "1.0.0"
    assert d["payload"] == {"slug": "traders"}
    assert "ts" in d


def test_disabled_client_returns_payload(tmp_path: Path) -> None:
    cfg = MeeetConfig(
        ingest_url=None,
        contract_version="1.0.0",
        api_key=None,
        source="tars",
        local_log_path=str(tmp_path / "events.jsonl"),
    )
    client = MeeetClient(cfg, store=MeeetStore(str(tmp_path / "meeet.sqlite")))
    start_trace(parent="trc_test")

    body = asyncio.run(client.emit("domain.action.invoked", {"slug": "traders"}))

    assert body["trace_id"] == "trc_test"
    assert body["kind"] == "domain.action.invoked"
    log_path = tmp_path / "events.jsonl"
    assert log_path.exists()
    line = log_path.read_text().strip()
    parsed = json.loads(line)
    assert parsed["payload"]["slug"] == "traders"


def test_safe_args_redaction() -> None:
    from web_extras.routers.domains import _safe_args

    out = _safe_args({"token": "abcd", "amount": 10, "long": "x" * 2000})
    assert out["token"] == "***"
    assert out["amount"] == 10
    assert out["long"].endswith("...")
    assert len(out["long"]) == 1024


@pytest.mark.parametrize(
    "envs",
    [
        {"MEEET_INGEST_URL": "", "MEEET_CONTRACT_VERSION": ""},
        {"MEEET_INGEST_URL": "  ", "MEEET_CONTRACT_VERSION": "  "},
    ],
)
def test_config_blanks_treated_as_unset(envs: dict[str, str]) -> None:
    from backend.core.meeet.config import load_config

    snapshot = {k: os.environ.get(k) for k in envs}
    try:
        os.environ.update(envs)
        cfg = load_config()
        assert cfg.ingest_url is None
        assert cfg.contract_version == "1.0.0"
        assert cfg.enabled is False
    finally:
        for k, v in snapshot.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
