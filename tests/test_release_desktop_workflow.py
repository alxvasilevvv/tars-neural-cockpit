"""Pin the contract of `.github/workflows/release-desktop.yml` (Phase L9 L3).

We do not run GitHub Actions locally; instead we assert the workflow
file has the shape downstream tools depend on:

1. Triggered by the `desktop-v*.*.*` tag prefix.
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
WORKFLOW = REPO / ".github" / "workflows" / "release-desktop.yml"
SIGN_SCRIPT = REPO / "desktop" / "scripts" / "sign-artifacts.sh"


@pytest.fixture(scope="module")
def workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sign_script() -> str:
    return SIGN_SCRIPT.read_text(encoding="utf-8")


def test_workflow_triggers_on_desktop_tag(workflow: str) -> None:
    assert '"desktop-v*.*.*"' in workflow
    assert '"desktop-v*.*.*-*"' in workflow


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
