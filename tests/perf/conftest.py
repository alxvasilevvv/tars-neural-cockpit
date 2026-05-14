"""Perf-suite-local pytest configuration.

* Registers the ``perf`` marker so the bench files don't trigger a
  PytestUnknownMarkWarning when run via the top-level pytest invocation
  from ``RUN-PERF-SUITE.command``.
* Wipes the ``.results/`` directory at session start so a re-run of
  the suite never reports stale numbers from a previous machine.
"""

from __future__ import annotations

import shutil

import pytest

from tests.perf._perf_utils import RESULTS_DIR


def pytest_configure(config: pytest.Config) -> None:  # noqa: D401
    config.addinivalue_line(
        "markers",
        "perf: load benchmark (opt-in; run via scripts/RUN-PERF-SUITE.command).",
    )


@pytest.fixture(scope="session", autouse=True)
def _wipe_results_dir():
    if RESULTS_DIR.exists():
        shutil.rmtree(RESULTS_DIR, ignore_errors=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    yield
