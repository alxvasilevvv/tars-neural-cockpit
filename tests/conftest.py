"""Pytest session-wide configuration for the TARS test suite.

Currently scoped to one concern: **default off for the
entitlements cap-enforcement gate**.

When Bug #2 from ``docs/SYSTEM_AUDIT_2026-05-02.md`` was fixed
(``web_extras/entitlements_gate.py``), every cloud-LLM-touching
endpoint started returning HTTP 402 for FREE-tier callers. The
existing test suite didn't seed an entitlements DB and didn't
need to — most of those tests assert downstream behaviour
(audio bytes, streaming envelopes, planner runs) that should
remain provider-driven.

The simplest non-invasive fix is to flip the env kill switch
to ``off`` for the test session. Tests that *want* to verify
the gate (``tests/test_entitlements_gate.py``) explicitly set
the env var back to ``on`` via ``monkeypatch`` inside their
own fixture.

Production / dev shells keep enforcement on by default.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _disable_cap_enforcement_by_default(monkeypatch: pytest.MonkeyPatch):
    """Flip ``TARS_CAP_ENFORCEMENT=off`` for every test by default.

    Tests that exercise the gate explicitly re-enable it via their
    own ``monkeypatch.setenv("TARS_CAP_ENFORCEMENT", "on")`` (see
    ``tests/test_entitlements_gate.py``). The autouse=True scope
    matters: the fixture has to run *before* any test imports the
    cap helper or constructs a TestClient that exercises a gated
    route.
    """

    # Only override when the operator hasn't pinned a value
    # explicitly via the shell. This keeps `TARS_CAP_ENFORCEMENT=on
    # pytest tests/...` honest if someone wants to flush out cap
    # leaks from the full suite.
    if os.environ.get("TARS_CAP_ENFORCEMENT") is None:
        monkeypatch.setenv("TARS_CAP_ENFORCEMENT", "off")
    # Same logic for the Bug #4 expensive-routes throttle: the
    # middleware is on by default in production but the test suite
    # would otherwise hit 429 on routine repeated calls. Tests that
    # exercise it explicitly flip the env back to ``on``.
    if os.environ.get("TARS_RATE_LIMIT_EXPENSIVE") is None:
        monkeypatch.setenv("TARS_RATE_LIMIT_EXPENSIVE", "off")
    yield
