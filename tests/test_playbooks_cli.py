"""Contract tests for the playbooks CLI (``backend.core.playbooks.cli``).

The CLI mirrors the HTTP surface in
``web_extras/routers/playbooks.py``:

- ``GET  /api/playbooks``               ↔ ``list``
- ``GET  /api/playbooks/{id}``          ↔ ``show``
- ``POST /api/playbooks/{id}/run``      ↔ ``run``
- ``POST /api/playbooks/_validate``     ↔ ``validate``
- ``GET  /api/playbooks/_validate_all`` ↔ ``validate-all``
- ``POST /api/playbooks/_reload``       ↔ ``reload``

What we pin here:

1. **Each subcommand** — happy path + one error envelope.
2. **Run subcommand context handling** — JSON inline,
   JSON file, file-wins-over-inline, parse errors,
   non-object payloads.
3. **Argparse plumbing** — required positionals enforce
   ``SystemExit(2)``; ``--quiet`` produces single-line
   JSON; ``main([...])`` end-to-end smoke through
   ``asyncio.run``.

We use a temp playbooks dir (via ``TARS_PLAYBOOKS_DIR``) so
the tests don't depend on the shipped repo playbooks (which
would couple test outcomes to whatever business / traders /
mlm layouts happen to be on disk that day).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from backend.core.playbooks import reset_loader_cache
from backend.core.playbooks.cli import _build_arg_parser, _run, main


# ---------------------------------------------------------------------------
# Test helpers — point the loader at a temp dir with predictable playbooks
# ---------------------------------------------------------------------------


_PROBE_OK_BODY = {
    "id": "probe.read_only",
    "name": "Probe — read-only",
    "description": "One non-destructive step for CLI tests.",
    "tags": ["probe"],
    "steps": [
        {
            "id": "kpi",
            "action": "business.kpi_snapshot",
            "args": {},
            "store_as": "kpi",
            "on_error": "continue",
        }
    ],
}


@pytest.fixture
def playbooks_root(tmp_path: Path, monkeypatch) -> Path:
    """Lay down a fresh ``playbooks/probe/`` directory with one valid
    playbook and point ``TARS_PLAYBOOKS_DIR`` at it.

    The single playbook (``probe.read_only``) wraps the
    ``business.kpi_snapshot`` action — non-destructive, fast,
    deterministic — so we can exercise the full ``run`` path
    without needing live network.
    """

    pack_dir = tmp_path / "probe"
    pack_dir.mkdir(parents=True)
    (pack_dir / "read_only.json").write_text(
        json.dumps(_PROBE_OK_BODY), encoding="utf-8"
    )
    monkeypatch.setenv("TARS_PLAYBOOKS_DIR", str(tmp_path))
    reset_loader_cache()
    yield tmp_path
    reset_loader_cache()


def _capture_json(capsys: pytest.CaptureFixture, rc: int) -> dict[str, Any]:
    out = capsys.readouterr().out
    payload = json.loads(out)
    if payload.get("ok"):
        assert rc == 0
    else:
        assert rc == 1
    return payload


# ---------------------------------------------------------------------------
# `list` subcommand
# ---------------------------------------------------------------------------


def test_list_returns_every_playbook(playbooks_root, capsys):
    parser = _build_arg_parser()
    args = parser.parse_args(["list"])
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["playbooks"][0]["id"] == "probe.read_only"
    assert payload["playbooks"][0]["pack"] == "probe"


def test_list_filters_by_pack(playbooks_root, capsys):
    parser = _build_arg_parser()
    args = parser.parse_args(["list", "--pack", "no_such_pack"])
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is True
    assert payload["count"] == 0
    assert payload["playbooks"] == []


def test_list_filters_by_pack_match(playbooks_root, capsys):
    parser = _build_arg_parser()
    args = parser.parse_args(["list", "--pack", "probe"])
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["playbooks"][0]["pack"] == "probe"


# ---------------------------------------------------------------------------
# `show` subcommand
# ---------------------------------------------------------------------------


def test_show_returns_full_playbook(playbooks_root, capsys):
    parser = _build_arg_parser()
    args = parser.parse_args(["show", "probe.read_only"])
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is True
    pb = payload["playbook"]
    assert pb["id"] == "probe.read_only"
    assert pb["name"] == "Probe — read-only"
    assert len(pb["steps"]) == 1
    assert pb["steps"][0]["action"] == "business.kpi_snapshot"


def test_show_unknown_playbook_returns_404_envelope(playbooks_root, capsys):
    parser = _build_arg_parser()
    args = parser.parse_args(["show", "no.such"])
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is False
    assert payload["reason"] == "playbook_not_found"
    assert payload["playbook_id"] == "no.such"


# ---------------------------------------------------------------------------
# `run` subcommand
# ---------------------------------------------------------------------------


def test_run_happy_path_executes_and_returns_envelope(playbooks_root, capsys):
    parser = _build_arg_parser()
    args = parser.parse_args(["run", "probe.read_only"])
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is True
    assert payload["playbook_id"] == "probe.read_only"
    # Runner mints its own trace_id; CLI surfaces it.
    assert payload["trace_id"], "run must surface a trace_id"
    assert payload["mode"] == "confirm", "default policy mode is confirm"
    assert isinstance(payload["took_ms"], (int, float))
    assert isinstance(payload["steps"], list)
    assert len(payload["steps"]) == 1
    assert payload["steps"][0]["id"] == "kpi"


def test_run_unknown_playbook_returns_404_envelope(playbooks_root, capsys):
    parser = _build_arg_parser()
    args = parser.parse_args(["run", "no.such"])
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is False
    assert payload["reason"] == "playbook_not_found"


def test_run_bad_inline_context_returns_invalid_context_envelope(
    playbooks_root, capsys
):
    parser = _build_arg_parser()
    args = parser.parse_args(
        ["run", "probe.read_only", "--context", "not actually json"]
    )
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is False
    assert payload["reason"] == "invalid_context"
    assert "context_not_json" in payload["message"]


def test_run_non_object_context_rejected(playbooks_root, capsys):
    """Context must be a JSON object, not a list / scalar."""

    parser = _build_arg_parser()
    args = parser.parse_args(
        ["run", "probe.read_only", "--context", "[1, 2, 3]"]
    )
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is False
    assert payload["reason"] == "invalid_context"
    assert payload["message"] == "context_must_be_object"


def test_run_context_file_loads_json_from_disk(
    playbooks_root, tmp_path, capsys
):
    ctx_path = tmp_path / "ctx.json"
    ctx_path.write_text(json.dumps({"lane": "morning"}), encoding="utf-8")
    parser = _build_arg_parser()
    args = parser.parse_args(
        ["run", "probe.read_only", "--context-file", str(ctx_path)]
    )
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is True
    # Runner echoes the context back so we can assert on it.
    assert payload["context"]["context"] == {"lane": "morning"}


def test_run_context_file_wins_over_inline_when_both_supplied(
    playbooks_root, tmp_path, capsys
):
    """``--context-file`` is the cron-baked sidecar; ``--context`` is
    the operator's ad-hoc tweak. We documented file-wins-over-inline
    so the operator can override per-call without retyping the long
    string. Pin that contract here so a future reorder doesn't
    silently flip cron behaviour.
    """

    ctx_path = tmp_path / "ctx.json"
    ctx_path.write_text(json.dumps({"src": "file"}), encoding="utf-8")
    parser = _build_arg_parser()
    args = parser.parse_args(
        [
            "run",
            "probe.read_only",
            "--context",
            json.dumps({"src": "inline"}),
            "--context-file",
            str(ctx_path),
        ]
    )
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is True
    assert payload["context"]["context"] == {"src": "file"}


def test_run_context_file_unreadable_returns_clean_envelope(
    playbooks_root, tmp_path, capsys
):
    parser = _build_arg_parser()
    args = parser.parse_args(
        [
            "run",
            "probe.read_only",
            "--context-file",
            str(tmp_path / "no-such.json"),
        ]
    )
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is False
    assert payload["reason"] == "invalid_context"
    assert "context_file_unreadable" in payload["message"]


def test_run_mode_flag_is_passed_to_runner(playbooks_root, capsys):
    parser = _build_arg_parser()
    args = parser.parse_args(
        ["run", "probe.read_only", "--mode", "autopilot"]
    )
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is True
    assert payload["mode"] == "autopilot", (
        "--mode autopilot must reach the runner envelope"
    )


def test_run_invalid_mode_falls_back_to_default(playbooks_root, capsys):
    """``resolve_mode`` is permissive — an unknown string falls back
    to ``confirm`` rather than raising. Pin that behaviour so the
    CLI doesn't crash on a typo in a cron command line.
    """

    parser = _build_arg_parser()
    args = parser.parse_args(
        ["run", "probe.read_only", "--mode", "totally-not-a-mode"]
    )
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is True
    # Falls through to env / hard-coded default.
    assert payload["mode"] in {"confirm", "autopilot", "dry_run"}


# ---------------------------------------------------------------------------
# `validate` / `validate-all` subcommands
# ---------------------------------------------------------------------------


def test_validate_one_playbook_returns_zero_issues_for_good(
    playbooks_root, capsys
):
    parser = _build_arg_parser()
    args = parser.parse_args(["validate", "probe.read_only"])
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is True
    assert payload["id"] == "probe.read_only"
    assert payload["errors"] == []


def test_validate_unknown_playbook_returns_404_envelope(playbooks_root, capsys):
    parser = _build_arg_parser()
    args = parser.parse_args(["validate", "no.such"])
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is False
    assert payload["reason"] == "playbook_not_found"


def test_validate_all_returns_aggregate_envelope(playbooks_root, capsys):
    parser = _build_arg_parser()
    args = parser.parse_args(["validate-all"])
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is True
    assert payload["playbook_count"] == 1
    assert payload["error_count"] == 0
    assert payload["warning_count"] == 0
    assert payload["playbooks"][0]["id"] == "probe.read_only"
    assert payload["playbooks"][0]["ok"] is True


def test_validate_all_returns_ok_false_when_any_playbook_invalid(
    tmp_path, monkeypatch, capsys
):
    """Drop a malformed playbook into the dir and confirm overall
    ``ok`` flips to ``false`` with non-zero ``error_count``. This
    is the **CI gate** behaviour cron operators rely on to halt
    rollouts when an authoring error lands.
    """

    pack_dir = tmp_path / "probe"
    pack_dir.mkdir(parents=True)
    # Valid playbook.
    (pack_dir / "good.json").write_text(
        json.dumps(_PROBE_OK_BODY), encoding="utf-8"
    )
    # Invalid playbook: well-formed JSON that the *loader* accepts
    # (id + steps + each step has id+action), but the strict
    # validator rejects because the action format violates
    # ``<slug>.<action_id>`` (no dot).
    bad_body = {
        "id": "probe.bad",
        "name": "Bad",
        "on_error": "panic",  # not in {stop, continue}
        "steps": [
            {
                "id": "step1",
                "action": "noslugformat",
                "on_error": "panic",
            }
        ],
    }
    (pack_dir / "bad.json").write_text(json.dumps(bad_body), encoding="utf-8")
    monkeypatch.setenv("TARS_PLAYBOOKS_DIR", str(tmp_path))
    reset_loader_cache()
    try:
        parser = _build_arg_parser()
        args = parser.parse_args(["validate-all"])
        rc = asyncio.run(_run(args))
        payload = _capture_json(capsys, rc)
        assert payload["ok"] is False, (
            "any playbook with errors must flip overall ok to false"
        )
        assert payload["error_count"] >= 1
    finally:
        reset_loader_cache()


# ---------------------------------------------------------------------------
# `reload` subcommand
# ---------------------------------------------------------------------------


def test_reload_picks_up_freshly_added_playbook(
    playbooks_root, tmp_path, capsys
):
    """Drop a second playbook into the dir AFTER first listing, then
    confirm ``reload`` surfaces it (not ``list``, which returns the
    cached set).
    """

    pack_dir = tmp_path / "probe2"
    pack_dir.mkdir(parents=True)
    (pack_dir / "second.json").write_text(
        json.dumps(
            {
                "id": "probe.second",
                "name": "Probe 2",
                "steps": [
                    {
                        "id": "kpi",
                        "action": "business.kpi_snapshot",
                        "args": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    parser = _build_arg_parser()
    args = parser.parse_args(["reload"])
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is True
    assert payload["count"] == 2
    assert "probe.second" in payload["ids"]


# ---------------------------------------------------------------------------
# Argparse plumbing
# ---------------------------------------------------------------------------


def test_subcommand_required_else_systemexit():
    parser = _build_arg_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args([])
    assert exc.value.code == 2


def test_show_requires_playbook_id():
    parser = _build_arg_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["show"])
    assert exc.value.code == 2


def test_run_requires_playbook_id():
    parser = _build_arg_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["run"])
    assert exc.value.code == 2


def test_validate_requires_playbook_id():
    parser = _build_arg_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["validate"])
    assert exc.value.code == 2


def test_quiet_flag_emits_compact_json(playbooks_root, capsys):
    parser = _build_arg_parser()
    args = parser.parse_args(["--quiet", "list"])
    rc = asyncio.run(_run(args))
    out = capsys.readouterr().out
    assert out.count("\n") == 1, (
        "--quiet must produce one-line JSON for jq piping"
    )
    assert rc == 0


def test_main_entrypoint_dispatches_to_run(playbooks_root, capsys):
    rc = main(["--quiet", "list"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["count"] == 1
