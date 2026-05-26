"""Spec-contract pins for W312 Cursor GA helper scripts."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (REPO / "scripts" / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "name",
    [
        "CURSOR-GA-STATUS.command",
        "SOAK-CRON-INSTALL.command",
        "SOAK-CRON-DIAGNOSE.command",
        "CURSOR-OVERNIGHT-SOAK.command",
        "CURSOR-SOAK-UNTIL-72.command",
        "APPLE-GH-SECRET-TEMPLATE.command",
    ],
)
def test_script_meta(name: str) -> None:
    path = REPO / "scripts" / name
    assert path.is_file()
    assert path.stat().st_mode & 0o111
    subprocess.run(["bash", "-n", str(path)], check=True)
    assert _read(name).startswith("#!/usr/bin/env bash\n")


def test_cursor_ga_status_documents_gates() -> None:
    body = _read("CURSOR-GA-STATUS.command")
    for needle in (
        "BROTHER-PREFLIGHT",
        "PREFLIGHT-APPLE-SIGN",
        "GA-COOKBOOK",
        "FINAL-QA-VERDICT",
        "RELEASE-TAG-GUARD",
        "docs/W310_WAVE_SUMMARY.md",
        "VERDICT: BLOCK",
        "VERDICT: PROCEED",
    ):
        assert needle in body
    assert "git tag" not in body
    assert "RELEASE-v10.0.command" in body


def test_soak_cron_install_idempotent_marker() -> None:
    body = _read("SOAK-CRON-INSTALL.command")
    assert "SOAK-HOURLY.command" in body
    assert "grep -Fq" in body
    assert "crontab -" in body


def test_overnight_soak_loop_contract() -> None:
    body = _read("CURSOR-OVERNIGHT-SOAK.command")
    assert "CURSOR_OVERNIGHT_HOURS" in body
    assert "SOAK-HOURLY.command" in body
    assert ".soak/overnight-watch.log" in body


def test_soak_until_72_target_loop() -> None:
    body = _read("CURSOR-SOAK-UNTIL-72.command")
    assert "CURSOR_SOAK_TARGET" in body
    assert "hourly.log" in body
    assert ".soak/until-72.log" in body


def test_soak_cron_diagnose_contract() -> None:
    body = _read("SOAK-CRON-DIAGNOSE.command")
    assert "Operation not permitted" in body
    assert "CURSOR-SOAK-UNTIL-72" in body
    assert "cron.log" in body


def test_cursor_ga_status_cron_permission_hint() -> None:
    body = _read("CURSOR-GA-STATUS.command")
    assert "SOAK_CRON_PERMISSIONS.md" in body
