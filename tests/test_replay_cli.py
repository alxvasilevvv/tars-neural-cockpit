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


def test_cli_repush_trace_no_ingest_returns_disabled_envelope(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Without an ingest URL configured, ``--repush-trace`` mirrors
    the default replay branch: returns an ``enabled=False`` envelope
    and exits 0. This is the cron-friendly behaviour — operators
    running the target on a host with no upstream configured get
    a clean noop, not an error.
    """

    db = tmp_path / "meeet.sqlite"
    monkeypatch.setenv("MEEET_STORE_PATH", str(db))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    import backend.core.meeet.store as store_mod
    import backend.core.meeet.client as client_mod

    store_mod._SINGLETON = None
    client_mod._SINGLETON = None

    args = _new_args(repush_trace="trc_anything", quiet=True)
    rc = asyncio.run(_run(args))
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["enabled"] is False
    assert payload["trace_id"] == "trc_anything"
    assert payload["pushed"] == 0


def test_cli_repush_trace_pushes_via_client_when_ingest_set(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """With an ingest URL set, ``--repush-trace`` calls
    ``MeeetClient.repush_trace`` and prints the envelope on
    success (rc=0 since ``failed=0``). We monkeypatch the HTTP
    primitive so the test stays hermetic.
    """

    db = tmp_path / "meeet.sqlite"
    monkeypatch.setenv("MEEET_STORE_PATH", str(db))
    monkeypatch.setenv("MEEET_INGEST_URL", "https://example.invalid/meeet")
    import backend.core.meeet.store as store_mod
    import backend.core.meeet.client as client_mod

    store_mod._SINGLETON = None
    client_mod._SINGLETON = None

    # Hermetic HTTP: never actually open a socket.
    pushed_bodies: list[dict] = []

    def fake_post(url, body, api_key, contract_version, timeout_s):
        pushed_bodies.append(body)

    monkeypatch.setattr(client_mod, "_post_json", fake_post)

    store = MeeetStore(str(db))
    _seed(store, kind="plan.run.started", trace_id="trc_repush", ts=1.0)
    _seed(store, kind="plan.run.completed", trace_id="trc_repush", ts=2.0)
    _seed(store, kind="other.evt", trace_id="trc_other", ts=3.0)

    args = _new_args(repush_trace="trc_repush", quiet=True, limit=10)
    rc = asyncio.run(_run(args))
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["pushed"] == 2
    assert payload["failed"] == 0
    assert payload["trace_id"] == "trc_repush"
    assert payload["enabled"] is True
    # Decoy event MUST NOT be pushed.
    assert all(b["trace_id"] == "trc_repush" for b in pushed_bodies)
    # Oldest-first push order.
    assert [b["kind"] for b in pushed_bodies] == [
        "plan.run.started",
        "plan.run.completed",
    ]


def test_cli_repush_trace_returns_rc1_on_failure(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """When the upstream HTTP call raises, the CLI must exit
    ``rc=1`` (cron-friendly: the operator's `set -e` script
    halts on the failure instead of merrily continuing).
    """

    db = tmp_path / "meeet.sqlite"
    monkeypatch.setenv("MEEET_STORE_PATH", str(db))
    monkeypatch.setenv("MEEET_INGEST_URL", "https://example.invalid/meeet")
    import backend.core.meeet.store as store_mod
    import backend.core.meeet.client as client_mod

    store_mod._SINGLETON = None
    client_mod._SINGLETON = None

    def boom_post(*_args, **_kw):
        raise RuntimeError("ingest down")

    monkeypatch.setattr(client_mod, "_post_json", boom_post)

    store = MeeetStore(str(db))
    _seed(store, kind="plan.run.started", trace_id="trc_boom", ts=1.0)

    args = _new_args(repush_trace="trc_boom", quiet=True, limit=10)
    rc = asyncio.run(_run(args))
    assert rc == 1, "any failed push must surface as rc=1 for cron `set -e`"
    payload = json.loads(capsys.readouterr().out)
    assert payload["pushed"] == 0
    assert payload["failed"] == 1


def test_cli_repush_trace_takes_precedence_over_export(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """If an operator passes both ``--repush-trace`` and
    ``--export`` by mistake, the more meaningful action (pushing)
    wins; export is silently skipped. Pin this so a future
    refactor of the if-else chain doesn't accidentally invert the
    precedence and have us write a JSONL file when the operator
    wanted to actually push.
    """

    db = tmp_path / "meeet.sqlite"
    monkeypatch.setenv("MEEET_STORE_PATH", str(db))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    import backend.core.meeet.store as store_mod
    import backend.core.meeet.client as client_mod

    store_mod._SINGLETON = None
    client_mod._SINGLETON = None

    out_path = tmp_path / "should_not_exist.jsonl"
    args = _new_args(
        repush_trace="trc_anything",
        export=str(out_path),
        quiet=True,
    )
    rc = asyncio.run(_run(args))
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    # Repush envelope shape (has trace_id / pushed / failed) — NOT
    # export ("exported N events to ...").
    assert "trace_id" in payload
    assert "pushed" in payload
    # Export branch never ran ⇒ no file created.
    assert not out_path.exists(), (
        "export branch must NOT execute when --repush-trace is set"
    )
