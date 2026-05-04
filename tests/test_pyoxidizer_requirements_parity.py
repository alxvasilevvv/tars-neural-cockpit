"""Pyoxidizer / requirements.txt parity guard.

The Tauri sidecar (``desktop/src-tauri/src/sidecar.rs``) spawns a
pyoxidizer-built ``tars-backend`` binary in production. The binary is
defined in ``desktop/pyoxidizer.bzl`` via an inline ``RUNTIME_REQUIREMENTS``
list (Starlark dialect — pip-install strings).

Every runtime dependency that ships in ``requirements.txt`` MUST also
be in ``RUNTIME_REQUIREMENTS`` so the bundled binary boots; conversely
every entry in ``RUNTIME_REQUIREMENTS`` MUST be in ``requirements.txt``
so the dev venv installs the same versions and tests catch
incompatibilities before the bundle is built.

Drift is silent today (you only notice when the cross-compiled `.dmg`
crashes on first launch with an `ImportError`), so this test keeps the
two source-of-truth files honest.

Test extras (pytest, pytest-asyncio, jsonschema) deliberately stay
out of the bundle — they're listed in the explicit ``BUNDLE_EXCLUDED``
allow-list.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS_PATH = REPO_ROOT / "requirements.txt"
PYOXIDIZER_BZL_PATH = REPO_ROOT / "desktop" / "pyoxidizer.bzl"

# Distributions that are intentionally NOT bundled into the sidecar
# binary. Test runners + JSON-schema validators are dev-time only;
# the production binary never imports them.
BUNDLE_EXCLUDED = frozenset({"pytest", "pytest-asyncio", "jsonschema"})


_REQ_LINE_RE = re.compile(
    r"""
    ^                     # start of line
    (?P<name>[A-Za-z0-9._\-]+)
    (?P<extras>\[[^\]]*\])?
    \s*
    (?P<spec>(==|>=|<=|~=|!=|>|<).*)?
    \s*$
    """,
    re.VERBOSE,
)


def _normalise_name(name: str) -> str:
    """Mirror PEP 503 normalisation so ``Pydantic-Settings`` ≡
    ``pydantic_settings``."""

    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_pip_lines(lines: Iterable[str]) -> dict[str, str]:
    """Return ``{normalised-name: spec}`` for every parseable pip line.

    Lines starting with ``#``, blank lines, and ``-r`` references are
    skipped — same heuristics pyoxidizer uses internally.
    """

    out: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Strip trailing inline comments (PEP 508 doesn't really define
        # them but `pip install` accepts them and our own
        # requirements.txt uses none, so this is a forward-compat guard).
        if " #" in line:
            line = line.split(" #", 1)[0].strip()
        match = _REQ_LINE_RE.match(line)
        if not match:
            continue
        name = _normalise_name(match.group("name"))
        spec = (match.group("spec") or "").strip()
        out[name] = spec
    return out


def _read_requirements() -> dict[str, str]:
    return _parse_pip_lines(REQUIREMENTS_PATH.read_text().splitlines())


# NB: closing bracket must be at start of a line so the parser doesn't
# bail on the inline `]` inside ``"uvicorn[standard]==0.46.0"``. The
# bzl file is formatted with the closing ``]`` on its own line at
# column 0 — keep it that way.
_BZL_LIST_RE = re.compile(
    r"RUNTIME_REQUIREMENTS\s*=\s*\[(?P<body>.*?)^\]",
    re.DOTALL | re.MULTILINE,
)
_BZL_STR_RE = re.compile(r"\"([^\"]+)\"")


def _read_bundle_pins() -> dict[str, str]:
    """Pull the ``RUNTIME_REQUIREMENTS`` Starlark list from the bzl
    file. Tolerates inline comments inside the list (Starlark accepts
    ``#`` comments anywhere)."""

    text = PYOXIDIZER_BZL_PATH.read_text()
    match = _BZL_LIST_RE.search(text)
    assert match, "RUNTIME_REQUIREMENTS list not found in pyoxidizer.bzl"
    body = match.group("body")
    pins = _BZL_STR_RE.findall(body)
    parsed = _parse_pip_lines(pins)
    return parsed


def test_pyoxidizer_pins_cover_every_runtime_requirement() -> None:
    """Every package in requirements.txt (minus the test extras) must
    appear in the pyoxidizer RUNTIME_REQUIREMENTS list."""

    req = _read_requirements()
    bundle = _read_bundle_pins()

    expected = {n for n in req if n not in BUNDLE_EXCLUDED}
    missing = sorted(expected - set(bundle))
    assert not missing, (
        "pyoxidizer.bzl is missing runtime pins from requirements.txt "
        f"(would crash with ImportError at sidecar launch): {missing!r}\n"
        "Add them to RUNTIME_REQUIREMENTS in desktop/pyoxidizer.bzl, "
        "matching the same version specifier."
    )


def test_pyoxidizer_pins_do_not_invent_packages() -> None:
    """No bundled pin may exist that isn't tracked in requirements.txt
    — otherwise the dev venv runs different code than the shipped
    binary and tests cover the wrong surface."""

    req = _read_requirements()
    bundle = _read_bundle_pins()

    extra = sorted(set(bundle) - set(req))
    assert not extra, (
        "pyoxidizer.bzl bundles packages not declared in requirements.txt "
        "(dev tests would never exercise the bundled version): "
        f"{extra!r}\nEither add them to requirements.txt or drop them "
        "from RUNTIME_REQUIREMENTS in desktop/pyoxidizer.bzl."
    )


def test_pyoxidizer_pin_specs_match_requirements_exactly() -> None:
    """For every common package, the version specifier in pyoxidizer.bzl
    must equal the one in requirements.txt — drift here is the silent
    failure mode (binary boots a different fastapi than the dev tests
    exercised)."""

    req = _read_requirements()
    bundle = _read_bundle_pins()
    common = sorted(set(req) & set(bundle))

    mismatches: list[str] = []
    for name in common:
        if req[name] != bundle[name]:
            mismatches.append(
                f"  {name}: requirements.txt={req[name]!r} "
                f"vs pyoxidizer.bzl={bundle[name]!r}"
            )
    assert not mismatches, (
        "Pyoxidizer pins drifted from requirements.txt:\n"
        + "\n".join(mismatches)
        + "\nKeep both in lockstep so the bundled binary runs the same "
        "versions the dev tests exercise."
    )


def test_test_extras_are_explicitly_excluded() -> None:
    """The known dev-only packages must stay out of the bundle. If
    one of them ever creeps into ``RUNTIME_REQUIREMENTS`` the
    cross-compiled binary balloons and CI takes longer for no
    runtime benefit — guard the policy here."""

    bundle = _read_bundle_pins()
    bundled_dev = sorted(BUNDLE_EXCLUDED & set(bundle))
    assert not bundled_dev, (
        "Dev/test packages must not be in pyoxidizer RUNTIME_REQUIREMENTS: "
        f"{bundled_dev!r}\nIf the policy changed, update BUNDLE_EXCLUDED in "
        "tests/test_pyoxidizer_requirements_parity.py with a clear note."
    )


def test_runtime_requirements_list_is_not_empty() -> None:
    """Sanity: the parser must find a non-empty list. A regex regression
    that returns ``{}`` would silently pass the other guards by
    making both ``missing`` and ``extra`` agree on an empty set."""

    bundle = _read_bundle_pins()
    assert len(bundle) >= 5, (
        f"Parsed only {len(bundle)} pins from pyoxidizer.bzl — the "
        f"regex likely broke. Pins: {sorted(bundle)!r}"
    )
