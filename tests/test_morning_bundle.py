"""Pin the contract of the morning-bundle cron wrapper.

``scripts/playbooks_morning_cron.sh`` is the single-command cron
entry point that runs every playbook tagged ``morning``, flushes
the meeet replay buffer, and writes an aggregate evidence JSON.

This test module covers two surfaces:

1. **Structural** — bash syntax, declared env knobs, exit-code
   contract, the ``morning-bundle`` Make target wiring. Pure
   text / ``bash -n`` checks; no execution required.

2. **End-to-end smoke** — actually invoke the wrapper against
   the live playbooks loader (we use the override path
   ``MORNING_PLAYBOOKS=`` so we don't depend on the four
   built-in morning-tagged playbooks staying ok forever). We
   verify the evidence JSON shape, the per-playbook entry,
   the replay block, and the exit-code branches (0 on full
   green, 1 on any failure, 2 on no playbooks discovered).

Smoke tests use a temporary output dir + ``MORNING_SKIP_REPLAY=1``
so they never touch the real ``~/.tars/meeet.sqlite`` buffer.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "playbooks_morning_cron.sh"
MAKEFILE = REPO / "Makefile"


# ---------------------------------------------------------------- structural


def test_script_exists_and_is_executable():
    assert SCRIPT.exists(), f"missing {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), f"{SCRIPT} not executable"


def test_script_starts_with_bash_shebang():
    first = SCRIPT.read_text(encoding="utf-8").splitlines()[0]
    assert first == "#!/usr/bin/env bash", (
        f"script must start with bash shebang, got: {first!r}"
    )


def test_script_passes_bash_syntax_check():
    proc = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"bash -n failed:\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )


@pytest.mark.parametrize(
    "knob",
    [
        # All env knobs documented in the script header must
        # actually be read by it. Catches doc drift in either
        # direction (knob removed but still documented, or
        # knob added but not documented).
        "MORNING_PLAYBOOKS",
        "MORNING_MODE",
        "MORNING_OUTPUT_DIR",
        "MORNING_SKIP_REPLAY",
        "MORNING_FAIL_FAST",
        "MORNING_TAG",
    ],
)
def test_script_reads_documented_env_knob(knob: str):
    body = SCRIPT.read_text(encoding="utf-8")
    assert knob in body, (
        f"env knob {knob!r} documented in header but never read"
    )


def test_script_documents_exit_code_contract():
    body = SCRIPT.read_text(encoding="utf-8")
    # The header must explain the three exit codes (0/1/2)
    # so the cron operator knows which alert to wire where.
    assert re.search(r"^#\s+0\s*[-—]", body, re.MULTILINE), (
        "exit code 0 (success) must be documented"
    )
    assert re.search(r"^#\s+1\s*[-—]", body, re.MULTILINE), (
        "exit code 1 (playbook failure) must be documented"
    )
    assert re.search(r"^#\s+2\s*[-—]", body, re.MULTILINE), (
        "exit code 2 (operator error) must be documented"
    )


def test_script_invokes_playbooks_cli_via_python_module(tmp_path):
    """The wrapper must shell into ``python -m
    backend.core.playbooks.cli`` (the same entry point as the
    Make targets and the FastAPI router) — never a stale local
    binary or a bespoke runner reimplementation. Pin so a
    "convenience" refactor doesn't fork the runner.
    """

    body = SCRIPT.read_text(encoding="utf-8")
    assert "backend.core.playbooks.cli" in body, (
        "wrapper must invoke the canonical playbooks CLI module"
    )
    assert "backend.core.meeet.replay_cli" in body, (
        "wrapper must flush via the canonical replay CLI module"
    )


# ---------------------------------------------------------------- Makefile


def test_make_target_listed_in_phony():
    text = MAKEFILE.read_text(encoding="utf-8")
    phony_match = re.search(r"\.PHONY:\s*((?:[^\n]*\\\n)*[^\n]*)", text)
    assert phony_match, ".PHONY line not found"
    phony = set(phony_match.group(1).replace("\\\n", " ").split())
    assert "morning-bundle" in phony, (
        "morning-bundle missing from .PHONY"
    )
    assert "morning-bundle-dry" in phony, (
        "morning-bundle-dry missing from .PHONY"
    )


@pytest.mark.parametrize("target", ["morning-bundle", "morning-bundle-dry"])
def test_make_target_has_help_comment(target: str):
    text = MAKEFILE.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^{re.escape(target)}:\s*[^#]*##\s*(\S.*)$",
        re.MULTILINE,
    )
    m = pattern.search(text)
    assert m, f"target {target!r} missing ## help text"
    assert len(m.group(1).strip()) >= 10, (
        f"{target!r} help text too terse"
    )


def test_make_target_invokes_wrapper_script():
    text = MAKEFILE.read_text(encoding="utf-8")
    pattern = re.compile(
        r"^morning-bundle:[^\n]*\n((?:\t[^\n]*\n)+)",
        re.MULTILINE,
    )
    m = pattern.search(text)
    assert m, "morning-bundle recipe not found"
    recipe = m.group(1)
    assert "scripts/playbooks_morning_cron.sh" in recipe, (
        "morning-bundle must invoke scripts/playbooks_morning_cron.sh"
    )


def test_make_dry_target_forces_dry_run_mode():
    """``morning-bundle-dry`` must override the operator's MODE=
    so ``make morning-bundle-dry`` is always a safe rehearsal,
    even if the operator has MODE=autopilot in the environment.
    """

    text = MAKEFILE.read_text(encoding="utf-8")
    pattern = re.compile(
        r"^morning-bundle-dry:[^\n]*\n((?:\t[^\n]*\n)+)",
        re.MULTILINE,
    )
    m = pattern.search(text)
    assert m, "morning-bundle-dry recipe not found"
    recipe = m.group(1)
    assert "MORNING_MODE=dry_run" in recipe, (
        "morning-bundle-dry must force MORNING_MODE=dry_run "
        "regardless of operator env"
    )


# ---------------------------------------------------------------- smoke


def _run_wrapper(env_overrides: dict[str, str], output_dir: Path) -> tuple[int, str, str]:
    """Invoke the wrapper script with a clean env + overrides.

    Returns (rc, stdout, stderr). All smoke tests use
    ``MORNING_OUTPUT_DIR=output_dir`` and ``MORNING_SKIP_REPLAY=1``
    so we don't touch the real meeet buffer.
    """

    env = os.environ.copy()
    env["MORNING_OUTPUT_DIR"] = str(output_dir)
    env.setdefault("MORNING_SKIP_REPLAY", "1")
    env.update(env_overrides)
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO),
    )
    return proc.returncode, proc.stdout, proc.stderr


def _latest_evidence(output_dir: Path) -> dict:
    files = sorted(output_dir.glob("morning-*.json"))
    assert files, f"no evidence files written to {output_dir}"
    return json.loads(files[-1].read_text(encoding="utf-8"))


def test_smoke_no_morning_playbooks_returns_rc2_with_minimal_evidence(tmp_path):
    """When discovery returns zero playbooks (bogus tag, no
    overrides) the wrapper must exit 2 (operator error, distinct
    from playbook failure) and still drop a minimal evidence
    record so the operator can audit which cron runs hit the
    no-playbooks branch.
    """

    rc, stdout, stderr = _run_wrapper(
        {"MORNING_TAG": "no_such_tag_for_test", "MORNING_PLAYBOOKS": ""},
        tmp_path,
    )
    assert rc == 2, (
        f"expected rc=2 for no playbooks, got {rc}\n"
        f"stdout={stdout}\nstderr={stderr}"
    )
    assert "no playbooks discovered" in stderr.lower(), (
        f"expected 'no playbooks discovered' in stderr, got: {stderr!r}"
    )
    evidence = _latest_evidence(tmp_path)
    assert evidence["ok"] is False
    assert evidence["reason"] == "no_playbooks_discovered"
    assert evidence["tag"] == "no_such_tag_for_test"
    assert evidence["playbooks"] == []


def test_smoke_override_with_known_playbook_returns_rc0(tmp_path):
    """End-to-end happy path: invoke with a single known
    playbook in autopilot mode and assert the wrapper exits
    0, the evidence shape is right, and the per-playbook
    entry has the expected keys.
    """

    rc, stdout, stderr = _run_wrapper(
        {
            "MORNING_PLAYBOOKS": "business.morning_brief",
            "MORNING_MODE": "autopilot",
        },
        tmp_path,
    )
    assert rc == 0, (
        f"expected rc=0 for happy path, got {rc}\n"
        f"stdout={stdout}\nstderr={stderr}"
    )
    evidence = _latest_evidence(tmp_path)
    assert evidence["ok"] is True
    assert evidence["mode"] == "autopilot"
    assert evidence["discovery"] == "override"
    assert evidence["playbook_count"] == 1
    assert evidence["failed_count"] == 0
    assert evidence["failed_ids"] == []
    assert evidence["replay"]["skipped"] is True

    [pb] = evidence["playbooks"]
    assert pb["id"] == "business.morning_brief"
    assert pb["ok"] is True
    assert pb["trace_id"], "happy path must produce a trace_id"
    assert pb["took_ms"] >= 0
    assert pb["error"] is None


def test_smoke_unknown_playbook_returns_rc1_with_failed_id(tmp_path):
    """A bad playbook id must surface as rc=1 (playbook failure,
    distinct from rc=2 operator error). The evidence file must
    record the failed id so the cron alert can paste the diff
    into a debug message instead of dumping all of stdout.
    """

    rc, stdout, stderr = _run_wrapper(
        {
            "MORNING_PLAYBOOKS": "no.such.playbook",
            "MORNING_MODE": "autopilot",
        },
        tmp_path,
    )
    assert rc == 1, (
        f"expected rc=1 for playbook failure, got {rc}\n"
        f"stdout={stdout}\nstderr={stderr}"
    )
    evidence = _latest_evidence(tmp_path)
    assert evidence["ok"] is False
    assert evidence["failed_ids"] == ["no.such.playbook"]

    [pb] = evidence["playbooks"]
    assert pb["id"] == "no.such.playbook"
    assert pb["ok"] is False
    assert pb["error"], "failed playbook must record an error reason"


def test_smoke_mixed_results_continue_on_failure(tmp_path):
    """Default (continue-on-failure) mode must run every
    playbook even if an earlier one failed, so the morning
    bundle reports the *complete* state. Verifies both
    playbooks land in the evidence and the failure_count is
    right.
    """

    rc, stdout, stderr = _run_wrapper(
        {
            "MORNING_PLAYBOOKS": "no.first,business.morning_brief",
            "MORNING_MODE": "autopilot",
        },
        tmp_path,
    )
    assert rc == 1, f"mixed results should exit 1, got {rc}"
    evidence = _latest_evidence(tmp_path)
    assert evidence["playbook_count"] == 2
    assert evidence["failed_count"] == 1
    assert evidence["failed_ids"] == ["no.first"]
    assert len(evidence["playbooks"]) == 2, (
        "continue-on-failure must run BOTH playbooks "
        "(otherwise we can't tell partial outage from total)"
    )
    assert evidence["playbooks"][1]["ok"] is True, (
        "second playbook should still succeed"
    )


def test_smoke_fail_fast_stops_after_first_failure(tmp_path):
    """``MORNING_FAIL_FAST=1`` must stop after the first
    failure. The evidence file should still record the
    skipped playbook (so the operator knows what *didn't*
    run), distinct from the continue-on-failure default.
    """

    rc, stdout, stderr = _run_wrapper(
        {
            "MORNING_PLAYBOOKS": "no.first,business.morning_brief",
            "MORNING_MODE": "autopilot",
            "MORNING_FAIL_FAST": "1",
        },
        tmp_path,
    )
    assert rc == 1, f"fail-fast should still exit 1, got {rc}"
    assert "MORNING_FAIL_FAST=1" in stderr, (
        "fail-fast abort must print why we're stopping"
    )
    evidence = _latest_evidence(tmp_path)
    assert evidence["playbook_count"] == 2
    # Only the first playbook actually ran; the second one
    # is recorded with the aborted_by_fail_fast marker so the
    # operator can see what was skipped.
    assert len(evidence["playbooks"]) == 2
    assert evidence["playbooks"][0]["id"] == "no.first"
    assert evidence["playbooks"][1]["id"] == "business.morning_brief"
    assert evidence["playbooks"][1]["error"] == "aborted_by_fail_fast", (
        "skipped playbook must be marked aborted_by_fail_fast "
        "so cron alerts can distinguish 'failed' from 'never ran'"
    )


def test_smoke_evidence_filename_matches_run_id(tmp_path):
    """The evidence file path must match the printed run_id
    (so an operator searching the cron log for ``run_id`` can
    find the evidence on disk in one ``ls``).
    """

    rc, stdout, _ = _run_wrapper(
        {
            "MORNING_PLAYBOOKS": "business.morning_brief",
            "MORNING_MODE": "autopilot",
        },
        tmp_path,
    )
    assert rc == 0
    m = re.search(r"morning-\d{8}T\d{6}-\d+", stdout)
    assert m, f"run_id pattern not found in stdout: {stdout!r}"
    run_id = m.group(0)
    expected = tmp_path / f"{run_id}.json"
    assert expected.exists(), (
        f"evidence file should be {expected}, dir contents: "
        f"{[p.name for p in tmp_path.iterdir()]}"
    )
    body = json.loads(expected.read_text(encoding="utf-8"))
    assert body["run_id"] == run_id


def test_smoke_skip_replay_records_replay_skipped_flag(tmp_path):
    """``MORNING_SKIP_REPLAY=1`` must surface in the evidence
    so a downstream auditor can tell "no events pushed because
    we explicitly skipped" apart from "no events pushed because
    upstream was down".
    """

    rc, _, _ = _run_wrapper(
        {
            "MORNING_PLAYBOOKS": "business.morning_brief",
            "MORNING_MODE": "autopilot",
            "MORNING_SKIP_REPLAY": "1",
        },
        tmp_path,
    )
    assert rc == 0
    evidence = _latest_evidence(tmp_path)
    assert evidence["replay"]["skipped"] is True
    assert evidence["replay"]["pushed"] == 0
