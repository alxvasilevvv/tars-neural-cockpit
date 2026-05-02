"""Bug #6 regression guard — no orphan ``__pycache__`` dirs.

The audit found ``backend/core/i18n/__pycache__/`` and
``backend/core/economy/__pycache__/`` lying around with Python
3.10 ``.pyc`` files for modules that no longer exist in the
source tree. This is not a hard runtime bug (pytest skips them)
but it confuses spelunkers who think the modules still exist
and breaks ``importlib.resources`` callers that walk the
package tree.

This test enumerates every ``__pycache__`` under ``backend/`` and
``web_extras/`` and asserts each one belongs to a real source
package — i.e. the parent directory contains at least one
``.py`` file (other than ``__pycache__/__init__.cpython-*.pyc``).

To clean up new orphans:

    rm -rf backend/core/<orphan_dir>
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories whose entire subtree is scanned for __pycache__.
SCAN_ROOTS = (
    REPO_ROOT / "backend",
    REPO_ROOT / "web_extras",
)


def _all_pycache_dirs() -> list[Path]:
    out: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("__pycache__"):
            # Skip vendor / .venv / similar (paranoid; SCAN_ROOTS
            # are already first-party but cheap to belt-and-brace).
            if any(part in {".venv", "node_modules", ".git"} for part in p.parts):
                continue
            out.append(p)
    return out


def _parent_has_py_sources(pycache: Path) -> bool:
    parent = pycache.parent
    if not parent.exists():
        return False
    for child in parent.iterdir():
        if child.is_file() and child.suffix == ".py":
            return True
    return False


def test_no_orphan_pycache_directories() -> None:
    orphans: list[Path] = []
    for pycache in _all_pycache_dirs():
        if not _parent_has_py_sources(pycache):
            orphans.append(pycache)
    if orphans:
        rel = "\n  ".join(
            str(p.relative_to(REPO_ROOT)) for p in sorted(orphans)
        )
        pytest.fail(
            "Orphan __pycache__ directories detected — the parent\n"
            "package no longer has any .py source files. Run:\n"
            f"  rm -rf {' '.join(str(p) for p in sorted(orphans))}\n\n"
            f"Orphans:\n  {rel}"
        )
