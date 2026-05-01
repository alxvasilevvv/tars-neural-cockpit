"""Pin the contract of the production Pages workflow + SPA fallback rule.

Regression context (2026-05-01):

A previous deploy step copied ``dist/index.html`` → ``dist/404.html`` so
that Cloudflare Pages would still render the SPA shell on unknown paths.
Cloudflare actually serves that body with a real **HTTP 404** status,
which silently breaks every probe (`scripts/qa_agent` `http.route/*`)
and analytics ping for client-side routes such as ``/install`` or
``/cockpit``. The fix is to ship only ``public/_redirects`` with a
trailing rewrite rule that returns 200 — see
``docs/CHANGELOG_AGENTS.md`` (2026-05-01 — Pages SPA HTTP 200).

These tests ensure the regression cannot recur unnoticed:

1. The CI workflow does not contain ``cp dist/index.html dist/404.html``
   (or any sibling shape).
2. The CI workflow has the post-deploy ``/install`` smoke gate.
3. ``public/_redirects`` ends with a wildcard SPA fallback rule that
   maps any unknown path to ``/index.html`` with status 200.
4. ``public/_redirects`` does **not** introduce a competing
   ``/* /404.html`` rule.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "tars-meeet-cloudflare-pages.yml"
REDIRECTS = REPO / "experiments" / "neural-showcase-v3" / "public" / "_redirects"


@pytest.fixture(scope="module")
def workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def redirects() -> str:
    return REDIRECTS.read_text(encoding="utf-8")


def test_workflow_has_no_404_html_copy_step(workflow: str) -> None:
    forbidden_patterns = (
        r"cp\s+dist/index\.html\s+dist/404\.html",
        r"cp\s+\$\{?[A-Z_]*\}?/index\.html\s+\$\{?[A-Z_]*\}?/404\.html",
        r"copy\s+dist/index\.html\s+dist/404\.html",
    )
    for pattern in forbidden_patterns:
        assert not re.search(pattern, workflow, re.IGNORECASE), (
            f"forbidden pattern {pattern!r} reappeared in Pages workflow — "
            "Cloudflare serves 404.html with a real HTTP 404 status; rely on "
            "public/_redirects (`/* /index.html 200`) instead."
        )


def test_workflow_documents_the_404_pitfall(workflow: str) -> None:
    assert "404.html" in workflow, (
        "Pages workflow must keep the explanatory comment about why we do "
        "**not** ship a 404.html copy."
    )
    assert "_redirects" in workflow, (
        "comment block should reference _redirects as the SPA fallback owner"
    )


def test_workflow_has_install_smoke_gate(workflow: str) -> None:
    assert "/install" in workflow, "missing /install smoke step body"
    assert "Smoke (SPA install route" in workflow, (
        "missing `Smoke (SPA install route → HTTP 200)` step name"
    )


def test_redirects_has_spa_fallback_last(redirects: str) -> None:
    rules = [
        line.strip()
        for line in redirects.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert rules, "_redirects must contain at least one rule"
    last = rules[-1]
    parts = last.split()
    assert len(parts) >= 3, f"malformed last rule: {last!r}"
    src, dst, status = parts[0], parts[1], parts[2]
    assert src == "/*", f"SPA fallback source must be /* (got {src!r})"
    assert dst == "/index.html", (
        f"SPA fallback destination must be /index.html (got {dst!r})"
    )
    assert status == "200", (
        f"SPA fallback status must be 200 to return real HTTP 200 (got {status!r}) — "
        "anything else regresses to the 2026-05-01 incident."
    )


def test_redirects_has_no_404_fallback(redirects: str) -> None:
    for line in redirects.splitlines():
        bare = line.strip()
        if not bare or bare.startswith("#"):
            continue
        parts = bare.split()
        if len(parts) < 2:
            continue
        if parts[0] == "/*" and "/404" in parts[1]:
            pytest.fail(
                f"_redirects must not point /* at a 404 page: {bare!r}. "
                "Cloudflare would emit HTTP 404 for every client route."
            )
