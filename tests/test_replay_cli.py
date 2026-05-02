"""Tests for the meeet replay CLI."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from backend.core.meeet import MeeetStore
from backend.core.meeet.replay_cli import _build_arg_parser, _run


def _seed(
    store: MeeetStore,
    *,
    kind: str,
    ts: float = 1.0,
    trace_id: str = "trc",
    session_id: str = "ses_alpha",
) -> None:
    asyncio.run(
        store.insert(
            {
                "kind": kind,
                "trace_id": trace_id,
                "ts": ts,
                "payload": {"x": 1},
                "source": "tars",
                "contract_version": "1.0.0",
                "session_id": session_id,
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


def test_cli_export_trace_id_filters_to_one_run(
    tmp_path: Path, monkeypatch
) -> None:
    """``--trace-id`` scopes the export to a single run's events.

    Pin: when an operator passes ``--trace-id trc_run_a`` they
    only get rows whose ``trace_id`` matches; the other run's
    events stay in the store but are absent from the exported
    JSONL. This is the contract the ``planner-replay-run`` Make
    target relies on for backfill / audit of one plan run after
    a meeet ingest outage.
    """

    db = tmp_path / "meeet.sqlite"
    monkeypatch.setenv("MEEET_STORE_PATH", str(db))
    import backend.core.meeet.store as store_mod

    store_mod._SINGLETON = None
    store = MeeetStore(str(db))
    _seed(store, kind="plan.run.started", trace_id="trc_run_a", ts=1.0)
    _seed(
        store, kind="plan.step.completed", trace_id="trc_run_a", ts=2.0
    )
    _seed(store, kind="plan.run.started", trace_id="trc_run_b", ts=3.0)
    _seed(store, kind="plan.run.completed", trace_id="trc_run_b", ts=4.0)

    out_path = tmp_path / "run_a.jsonl"
    args = _new_args(export=str(out_path), limit=10, trace_id="trc_run_a")
    rc = asyncio.run(_run(args))
    assert rc == 0
    lines = out_path.read_text().strip().splitlines()
    assert len(lines) == 2, "trace filter should leave run B out"
    parsed = [json.loads(line) for line in lines]
    assert all(p["trace_id"] == "trc_run_a" for p in parsed), (
        "every exported row must belong to the requested trace"
    )
    assert {p["kind"] for p in parsed} == {
        "plan.run.started",
        "plan.step.completed",
    }, "both run-A events must round-trip through the CLI"


def test_cli_export_trace_id_with_no_match_writes_empty_file(
    tmp_path: Path, monkeypatch
) -> None:
    """Unknown ``--trace-id`` writes an empty JSONL (rc=0) so the
    Make target's ``echo "wrote $out_path"`` log line still fires
    and downstream cron scripts don't get a non-zero error for a
    legitimate "no events for that trace" case (e.g. trace was
    pruned or was never local).
    """

    db = tmp_path / "meeet.sqlite"
    monkeypatch.setenv("MEEET_STORE_PATH", str(db))
    import backend.core.meeet.store as store_mod

    store_mod._SINGLETON = None
    store = MeeetStore(str(db))
    _seed(store, kind="plan.run.started", trace_id="trc_known", ts=1.0)

    out_path = tmp_path / "missing.jsonl"
    args = _new_args(export=str(out_path), limit=10, trace_id="trc_unknown")
    rc = asyncio.run(_run(args))
    assert rc == 0
    assert out_path.read_text() == "", (
        "no matching events ⇒ empty file (still rc=0 for cron-friendliness)"
    )


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
