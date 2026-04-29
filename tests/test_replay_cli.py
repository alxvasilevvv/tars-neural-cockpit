"""Tests for the meeet replay CLI."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from backend.core.meeet import MeeetStore
from backend.core.meeet.replay_cli import _build_arg_parser, _run


def _seed(store: MeeetStore, *, kind: str, ts: float = 1.0) -> None:
    asyncio.run(
        store.insert(
            {
                "kind": kind,
                "trace_id": "trc",
                "ts": ts,
                "payload": {"x": 1},
                "source": "tars",
                "contract_version": "1.0.0",
                "session_id": "ses_alpha",
                "route": "edge",
            }
        )
    )


def _new_args(**overrides):
    parser = _build_arg_parser()
    args = parser.parse_args([])
    for k, v in overrides.items():
        setattr(args, k, v)
    return args


def test_cli_export_writes_jsonl(tmp_path: Path, monkeypatch, capsys) -> None:
    db = tmp_path / "meeet.sqlite"
    monkeypatch.setenv("MEEET_STORE_PATH", str(db))
    from backend.core.meeet.store import _SINGLETON as _STORE  # noqa
    import backend.core.meeet.store as store_mod

    store_mod._SINGLETON = None  # force re-init under env
    store = MeeetStore(str(db))
    _seed(store, kind="alpha.evt")
    _seed(store, kind="beta.evt")

    out_path = tmp_path / "export.jsonl"
    args = _new_args(export=str(out_path), limit=10)
    rc = asyncio.run(_run(args))
    assert rc == 0
    lines = out_path.read_text().strip().splitlines()
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    kinds = [p["kind"] for p in parsed]
    assert set(kinds) == {"alpha.evt", "beta.evt"}
    # Session/route round-trips through the CLI.
    assert all(p["session_id"] == "ses_alpha" for p in parsed)


def test_cli_stats_returns_health(tmp_path: Path, monkeypatch, capsys) -> None:
    db = tmp_path / "meeet.sqlite"
    monkeypatch.setenv("MEEET_STORE_PATH", str(db))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    import backend.core.meeet.store as store_mod
    import backend.core.meeet.client as client_mod

    store_mod._SINGLETON = None
    client_mod._SINGLETON = None

    args = _new_args(stats=True, quiet=True)
    rc = asyncio.run(_run(args))
    assert rc == 0
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert "client" in out and "store" in out


def test_cli_replay_no_ingest_returns_disabled(tmp_path: Path, monkeypatch, capsys) -> None:
    db = tmp_path / "meeet.sqlite"
    monkeypatch.setenv("MEEET_STORE_PATH", str(db))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    import backend.core.meeet.store as store_mod
    import backend.core.meeet.client as client_mod

    store_mod._SINGLETON = None
    client_mod._SINGLETON = None

    args = _new_args(quiet=True)
    rc = asyncio.run(_run(args))
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["enabled"] is False
    assert payload["pushed"] == 0
