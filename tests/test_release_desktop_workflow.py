"""Pin the contract of the release-desktop-tagged workflow (Phase L9 L3).

The file lives at the repo root (`release-desktop-tagged.yml`) since
PR #4 moved it out of `.github/workflows/` to reset a stuck
GitHub workflow_id. We still accept the old path as a fallback for
older branches.

We do not run GitHub Actions locally; instead we assert the workflow
file has the shape downstream tools depend on:

1. Triggered via `workflow_dispatch` with an explicit semver `version`
   input (tag-push triggers were retired to silence GitHub's spurious
   validation runs — see YAML header comment.)
2. Reads the minisign secret from `TAURI_SIGNING_PRIVATE_KEY` (and the
   passphrase from `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`).
3. Calls `python -m backend.core.product.publish` with `--updater-out`
   AND at least one `--updater-alias` so the marketing site can
   hard-link a stable URL.
4. Builds the four canonical Tauri targets (macOS arm64+x86_64,
   Windows x86_64, Linux x86_64).
5. Invokes `desktop/scripts/sign-artifacts.sh`.

The sign script itself must:

- Exit cleanly when no minisign secret is configured (dev mode).
- Use the Tauri 2 `tauri signer sign` CLI with `--private-key` and
  optional `--password`, and emit `<artifact>.sig` sidecar files
  (which `backend/core/product/updater.py` already picks up — see
  `tests/test_product_updater.py`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
# The release workflow used to live under ``.github/workflows/`` but
# was relocated to the repo root in commit d1984f1 to reset a stuck
# GitHub workflow_id (see PR #4). Look at the new location first,
# fall back to the old path so the test stays green either way.
_WORKFLOW_CANDIDATES = (
    REPO / "release-desktop-tagged.yml",
    REPO / ".github" / "workflows" / "release-desktop-tagged.yml",
)


def _resolve_workflow_path() -> Path:
    for candidate in _WORKFLOW_CANDIDATES:
        if candidate.exists():
            return candidate
    # Surface a clear failure mentioning every path we checked
    # rather than a bare FileNotFoundError on whichever happens to
    # be first.
    raise FileNotFoundError(
        "release-desktop-tagged.yml not found at any of: "
        + ", ".join(str(p) for p in _WORKFLOW_CANDIDATES)
    )


WORKFLOW = _resolve_workflow_path()
SIGN_SCRIPT = REPO / "desktop" / "scripts" / "sign-artifacts.sh"


@pytest.fixture(scope="module")
def workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sign_script() -> str:
    return SIGN_SCRIPT.read_text(encoding="utf-8")


def test_workflow_uses_dispatch_with_version_input(workflow: str) -> None:
    assert "workflow_dispatch:" in workflow
    assert "inputs:" in workflow
    assert "version:" in workflow
    assert "Semver to publish" in workflow


def test_workflow_passes_minisign_secret_to_env(workflow: str) -> None:
    assert "TAURI_SIGNING_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY }}" in workflow
    assert (
        "TAURI_SIGNING_PRIVATE_KEY_PASSWORD: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY_PASSWORD }}"
        in workflow
    )


def test_workflow_publishes_updater_channel(workflow: str) -> None:
    assert "python -m backend.core.product.publish" in workflow
    assert "--updater-out" in workflow
    assert "--updater-alias latest" in workflow


def test_workflow_covers_all_four_targets(workflow: str) -> None:
    for target in (
        "aarch64-apple-darwin",
        "x86_64-apple-darwin",
        "x86_64-pc-windows-msvc",
        "x86_64-unknown-linux-gnu",
    ):
        assert target in workflow, f"matrix missing target {target}"


def test_workflow_invokes_sign_script(workflow: str) -> None:
    assert "scripts/sign-artifacts.sh" in workflow


def test_sign_script_skips_in_dev_mode_with_no_secret(sign_script: str) -> None:
    assert 'if [[ -z "${TAURI_SIGNING_PRIVATE_KEY:-}" ]]; then' in sign_script
    assert "exit 0" in sign_script


def test_sign_script_calls_tauri_signer_with_private_key(sign_script: str) -> None:
    assert "tauri signer sign" in sign_script
    assert "--private-key" in sign_script
    assert "TAURI_SIGNING_PRIVATE_KEY_PASSWORD" in sign_script


def test_sign_script_fails_loud_if_sig_sidecar_missing(sign_script: str) -> None:
    assert 'if [[ ! -f "$art.sig" ]]; then' in sign_script
    assert "exit 2" in sign_script


def test_sign_script_is_executable() -> None:
    import os

    mode = SIGN_SCRIPT.stat().st_mode
    assert mode & 0o100, f"sign-artifacts.sh is not executable (mode={oct(mode)})"
    # Sanity: shebang on first line.
    with SIGN_SCRIPT.open() as f:
        first = f.readline()
    assert first.startswith("#!"), f"sign-artifacts.sh missing shebang: {first!r}"
