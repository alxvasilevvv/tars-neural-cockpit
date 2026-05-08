"""Pin the fresh-machine `make bootstrap` contract.

Walking the operator playbook end-to-end on 2026-05-08 surfaced a
"first-time setup" gap: every `make` target that uses `$(PY)` or
`./.venv/bin/python` would fail with `bash: ./.venv/bin/python: no
such file or directory` for an operator coming from a fresh clone.
This is true for `make qa-agent`, `make dev-tars-stack`,
`make smoke-billing-tars`, `make gate-control-tower`, and most
planner targets.

The fix is a single golden command — `make bootstrap` — that:
- creates `.venv` with the highest Python 3.10+ on PATH (preferring
  3.12 because that's what CI pins),
- upgrades pip,
- installs `requirements.txt`,
- is **idempotent**: re-runs as a no-op if `.venv` already exists.

Two scripts also got actionable error hints when the venv isn't
bootstrapped yet: `scripts/backend_tars_up.sh` and
`scripts/smoke_billing_tars_backend.sh`. They now print the same
quick-fix recipe so operators don't have to grep the README.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MAKEFILE = REPO / "Makefile"
PLAYBOOK = REPO / "docs" / "OPERATOR_LAUNCH_PLAYBOOK.md"
BACKEND_UP = REPO / "scripts" / "backend_tars_up.sh"
SMOKE_BILLING = REPO / "scripts" / "smoke_billing_tars_backend.sh"


@pytest.fixture(scope="module")
def makefile() -> str:
    return MAKEFILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def playbook() -> str:
    return PLAYBOOK.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def backend_up() -> str:
    return BACKEND_UP.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def smoke_billing() -> str:
    return SMOKE_BILLING.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. `make bootstrap` exists and is wired into .PHONY
# ---------------------------------------------------------------------------
def test_bootstrap_target_declared(makefile: str) -> None:
    assert "bootstrap:" in makefile, (
        "Makefile must define a `bootstrap` target so fresh-machine "
        "operators have a single command to set up the venv."
    )
    assert " bootstrap " in makefile or " bootstrap\n" in makefile, (
        "`bootstrap` must be in the .PHONY list so make doesn't "
        "look for a file named `bootstrap` in the working dir."
    )


def test_bootstrap_uses_idempotent_venv_check(makefile: str) -> None:
    """The target must be safe to re-run — it should detect an
    existing `.venv` and skip create instead of `python3 -m venv`-ing
    over the top."""
    assert "if [[ -x \"./.venv/bin/python\" ]]" in makefile or (
        "./.venv/bin/python" in makefile and "skipping create" in makefile
    ), (
        "bootstrap target must short-circuit when ./.venv/bin/python "
        "already exists (idempotency)."
    )


def test_bootstrap_picks_best_python(makefile: str) -> None:
    """We prefer 3.12 (CI pin) but fall back through 3.11/3.10/python3
    so the target works on a Linux box that only has 3.11 installed."""
    assert "PYTHON_BOOTSTRAP" in makefile
    assert "python3.12" in makefile
    assert "python3.11" in makefile or "python3.10" in makefile


def test_bootstrap_installs_requirements(makefile: str) -> None:
    assert "pip install -r requirements.txt" in makefile, (
        "bootstrap must `pip install -r requirements.txt` so the venv "
        "is actually usable for `make qa-agent` / `make backend-tars-up`."
    )


def test_bootstrap_prints_next_step(makefile: str) -> None:
    assert "[bootstrap] next:" in makefile, (
        "bootstrap should leave the operator with a clear next command "
        "(e.g. `cp .env.example .env`) so they don't get stuck."
    )


# ---------------------------------------------------------------------------
# 2. Playbook surfaces `make bootstrap` as the first concrete command
# ---------------------------------------------------------------------------
def test_playbook_has_bootstrap_step(playbook: str) -> None:
    assert "make bootstrap" in playbook, (
        "OPERATOR_LAUNCH_PLAYBOOK.md must surface `make bootstrap` as "
        "the first concrete command (Step 0a) so a fresh-machine "
        "operator doesn't stumble on `bash: ./.venv/bin/python: not "
        "found` halfway through Step 3."
    )


# ---------------------------------------------------------------------------
# 3. Scripts that depend on .venv now print actionable hints
# ---------------------------------------------------------------------------
def test_backend_up_explains_missing_venv(backend_up: str) -> None:
    """`backend_tars_up.sh` used to die with one terse line —
    `missing: ./.venv/bin/python — create venv first` — without
    showing the operator HOW to create it. Now it includes the
    full quick-fix block."""
    assert "virtualenv not yet bootstrapped" in backend_up
    assert "python3.12 -m venv .venv" in backend_up
    assert "pip install -r requirements.txt" in backend_up


def test_smoke_billing_explains_missing_venv(smoke_billing: str) -> None:
    assert "virtualenv not bootstrapped" in smoke_billing, (
        "smoke_billing_tars_backend.sh must guard ./.venv/bin/python "
        "and emit the same quick-fix hint as backend_tars_up.sh — "
        "otherwise operators get bash's terse exec-not-found error."
    )
    assert "python3.12 -m venv .venv" in smoke_billing
