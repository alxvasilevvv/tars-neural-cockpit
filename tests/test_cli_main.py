"""Tests for the Wave M2 ``tars`` CLI.

We never spawn a subprocess — the CLI is a single ``main(argv)``
function over argparse, so all tests call it directly and
capture stdout via ``capsys``. This keeps the suite fast and
parallel-safe.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

from backend.cli.main import build_parser, main
from backend.cli.output import render


# ---------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------


def test_parser_lists_top_level_commands() -> None:
    parser = build_parser()
    actions = {a.dest: a for a in parser._actions}
    sub = next(
        a for a in parser._actions if a.dest == "command"
    )
    cmds = sorted(sub.choices.keys())
    assert cmds == ["algotrade", "lab", "playbooks", "version"]


def test_no_command_prints_help_and_exits_2(capsys) -> None:
    rc = main([])
    err = capsys.readouterr().err
    assert rc == 2
    assert "tars" in err
    assert "command" in err.lower()


def test_unknown_command_argparse_error(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["bogus"])
    # argparse exits 2 on parse errors.
    assert excinfo.value.code == 2


# ---------------------------------------------------------------------
# Output mode resolution
# ---------------------------------------------------------------------


def test_json_flag_forces_json(capsys) -> None:
    rc = main(["--json", "algotrade", "list-recipes"])
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    assert "ma_cross" in payload["recipes"]


def test_human_flag_forces_pretty(capsys) -> None:
    rc = main(["--human", "algotrade", "list-recipes"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Recipes:" in out
    assert "ma_cross" in out


def test_default_mode_is_json_for_non_tty(capsys) -> None:
    """Tests run with stdout piped to capsys (not a TTY) so the
    default mode resolves to JSON."""

    rc = main(["algotrade", "list-recipes"])
    out = capsys.readouterr().out
    assert rc == 0
    json.loads(out)  # must parse


# ---------------------------------------------------------------------
# Algotrade verbs
# ---------------------------------------------------------------------


def test_algotrade_list_recipes_returns_known_starters(capsys) -> None:
    rc = main(["--json", "algotrade", "list-recipes"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert {"ma_cross", "bollinger_reversion", "rsi_oversold", "trailing_runner"} <= set(
        payload["recipes"]
    )


def test_algotrade_load_recipe_known_name(capsys) -> None:
    rc = main(["--json", "algotrade", "load-recipe", "ma_cross"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["ok"] is True
    assert payload["name"] == "ma_cross"
    assert payload["fingerprint"].startswith("sha256:")


def test_algotrade_load_recipe_unknown_returns_rc_1(capsys) -> None:
    rc = main(["--json", "algotrade", "load-recipe", "totally-not-a-recipe"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["ok"] is False
    assert payload["error"] == "recipe_not_found"


def test_algotrade_register_strategy_requires_source(capsys) -> None:
    rc = main(["--json", "algotrade", "register-strategy"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["error"] == "missing_source"


def test_algotrade_backtest_missing_data_returns_rc_1(capsys) -> None:
    rc = main(
        [
            "--json",
            "algotrade",
            "backtest",
            "--recipe",
            "ma_cross",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["error"] == "missing_data"


# ---------------------------------------------------------------------
# Lab verbs (TARS_ALGOTRADE_HOME isolation per test)
# ---------------------------------------------------------------------


@pytest.fixture
def isolated_home(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("TARS_ALGOTRADE_HOME", tmp)
        # Reset the lab + runtime singletons so the fresh
        # filesystem path is honoured.
        from backend.core.algotrade.exec import reset_runtime
        from backend.core.algotrade.lab import reset_lab_store

        reset_runtime()
        reset_lab_store()
        yield Path(tmp)
        reset_runtime()
        reset_lab_store()


def test_lab_create_workshop_round_trips(capsys, isolated_home) -> None:
    rc = main(
        [
            "--json",
            "lab",
            "create-workshop",
            "--name",
            "CLI test",
            "--workshop-id",
            "ws_test",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["workshop"]["workshop_id"] == "ws_test"


def test_lab_enroll_then_leaderboard(capsys, isolated_home) -> None:
    rc = main(
        [
            "--json",
            "lab",
            "create-workshop",
            "--name",
            "Lab",
            "--workshop-id",
            "ws_lab",
        ]
    )
    capsys.readouterr()  # discard
    assert rc == 0

    rc = main(
        [
            "--json",
            "lab",
            "enroll",
            "--workshop-id",
            "ws_lab",
            "--name",
            "Solo",
            "--attendee-id",
            "att_solo",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["attendee"]["sandbox_id"] == "lab:ws_lab:att_solo"

    rc = main(["--json", "lab", "leaderboard", "--workshop-id", "ws_lab"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["leaderboard"]["attendees_total"] == 1
    assert payload["leaderboard"]["entries"][0]["attendee_id"] == "att_solo"


def test_lab_debrief_to_file(capsys, tmp_path, isolated_home) -> None:
    main(
        [
            "--json",
            "lab",
            "create-workshop",
            "--name",
            "Out",
            "--workshop-id",
            "ws_out",
        ]
    )
    capsys.readouterr()
    main(
        [
            "--json",
            "lab",
            "enroll",
            "--workshop-id",
            "ws_out",
            "--name",
            "X",
            "--attendee-id",
            "att_x",
        ]
    )
    capsys.readouterr()

    target = tmp_path / "debrief" / "bundle.md"
    rc = main(
        [
            "--json",
            "lab",
            "debrief",
            "--workshop-id",
            "ws_out",
            "--output",
            str(target),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["wrote"] == str(target)
    assert target.exists()
    assert target.read_text().startswith("# Workshop debrief — Out")


def test_lab_debrief_unknown_workshop_rc_1(capsys, isolated_home) -> None:
    rc = main(
        [
            "--json",
            "lab",
            "debrief",
            "--workshop-id",
            "ws_does_not_exist",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["error"] == "workshop_not_found"


# ---------------------------------------------------------------------
# Playbooks
# ---------------------------------------------------------------------


def test_playbooks_list_includes_workshop_quant(capsys) -> None:
    rc = main(["--json", "playbooks", "list"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    ids = {p["id"] for p in payload["playbooks"]}
    assert "_workshop.quant.recipe_to_paper" in ids
    assert "_workshop.quant.lab_kickoff" in ids


def test_playbooks_show_known_id(capsys) -> None:
    rc = main(
        ["--json", "playbooks", "show", "_workshop.quant.recipe_to_paper"]
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["playbook"]["id"] == "_workshop.quant.recipe_to_paper"


def test_playbooks_show_unknown_id(capsys) -> None:
    rc = main(["--json", "playbooks", "show", "nope.nope"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["error"] == "playbook_not_found"


def test_playbooks_run_unknown_id(capsys) -> None:
    rc = main(["--json", "playbooks", "run", "nope.nope"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["error"] == "playbook_not_found"


def test_playbooks_run_invalid_context(capsys) -> None:
    rc = main(
        [
            "--json",
            "playbooks",
            "run",
            "_workshop.quant.recipe_to_paper",
            "--context",
            "no-equals-sign",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["error"] == "invalid_context"


# ---------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------


def test_version_default_lists_packs(capsys) -> None:
    rc = main(["--json", "version"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["version"] == "0.1.0"
    assert "packs" in payload
    by_slug = {p["slug"]: p for p in payload["packs"]}
    assert "algotrade" in by_slug
    assert by_slug["algotrade"]["version"] == "0.8.0"
    assert by_slug["algotrade"]["phase"] == "W4-PR3"


def test_version_check_packs_skip(capsys) -> None:
    rc = main(["--json", "version", "--check-packs"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert "packs" not in payload


# ---------------------------------------------------------------------
# Output renderer unit tests (small but high signal)
# ---------------------------------------------------------------------


def test_render_error_envelope_human() -> None:
    out = render(
        {"ok": False, "error": "boom", "detail": "more"},
        mode="human",
    )
    assert "boom" in out
    assert "more" in out


def test_render_recipes_human() -> None:
    out = render(
        {"ok": True, "recipes": ["a", "b"]},
        mode="human",
    )
    assert "Recipes:" in out
    assert "  - a" in out


def test_render_falls_back_to_json_for_unknown_shape() -> None:
    out = render({"ok": True, "weird": [1, 2, 3]}, mode="human")
    parsed = json.loads(out)
    assert parsed["weird"] == [1, 2, 3]
