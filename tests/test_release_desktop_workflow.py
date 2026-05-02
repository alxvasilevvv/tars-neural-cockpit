"""Pin the contract of the release-desktop-tagged workflow (Phase L9 L3).

The file MUST live at ``.github/workflows/release-desktop-tagged.yml``
— GitHub Actions only schedules workflows from that directory.

> **Regression history:** PR #4 moved the file to the repo root to
> reset a stuck GitHub workflow_id. The unintended side effect was
> that the file was no longer scheduled at all, leaving the
> ``release-desktop`` workflow stuck in ``queued`` for >12h on
> 2026-05-02 because the last actually-executed run was the one
> right before the move. The 2026-05-02 system audit restored the
> file and added :func:`test_workflow_lives_under_dot_github_workflows`
> as a regression guard.

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
6. ``pnpm/action-setup@v4`` runs BEFORE ``actions/setup-node@v4``
   (the latter uses ``cache: pnpm`` and fails to locate pnpm
   otherwise — pinned by
   :func:`test_workflow_installs_pnpm_before_setup_node_with_pnpm_cache`).

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
# The release workflow lives at ``.github/workflows/`` —
# GitHub Actions only schedules workflows from that directory.
# Older branches that left the file at the repo root may still be
# read as a *fallback* (the contract tests below still apply); the
# regression guard ``test_workflow_lives_under_dot_github_workflows``
# is the one that fails CI if the file ever gets moved out again.
_WORKFLOW_CANONICAL = REPO / ".github" / "workflows" / "release-desktop-tagged.yml"
_WORKFLOW_LEGACY_ROOT = REPO / "release-desktop-tagged.yml"
_WORKFLOW_CANDIDATES = (_WORKFLOW_CANONICAL, _WORKFLOW_LEGACY_ROOT)


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


def test_workflow_lives_under_dot_github_workflows() -> None:
    """**Regression guard.** GitHub Actions only schedules workflows
    that live under ``.github/workflows/``. PR #4 once moved this
    file to the repo root to "reset a stuck workflow_id" and the
    unintended side effect was that the file stopped being
    scheduled at all (the ``release-desktop`` workflow sat in
    ``queued`` for 12+ hours on 2026-05-02 because the last
    actually-executed run was the one right before the move).
    Pin the canonical path so the next "let's just move it" never
    quietly disables the desktop release pipeline again.
    """

    assert _WORKFLOW_CANONICAL.exists(), (
        f"release-desktop-tagged.yml MUST live at {_WORKFLOW_CANONICAL.relative_to(REPO)} "
        f"(GitHub Actions only schedules workflows from that dir). "
        f"If you need to reset the workflow_id, rename the file in "
        f"place — do not move it out."
    )
    # Belt-and-braces: also ensure the legacy root copy is gone, so
    # we never end up with two copies that drift.
    assert not _WORKFLOW_LEGACY_ROOT.exists(), (
        f"Legacy copy at {_WORKFLOW_LEGACY_ROOT.relative_to(REPO)} "
        f"should be removed; the canonical location is "
        f"{_WORKFLOW_CANONICAL.relative_to(REPO)}."
    )


def test_workflow_uses_dispatch_with_version_input(workflow: str) -> None:
    assert "workflow_dispatch:" in workflow
    assert "inputs:" in workflow
    assert "version:" in workflow
    assert "Semver to publish" in workflow


def test_workflow_installs_pnpm_before_setup_node_with_pnpm_cache(workflow: str) -> None:
    """**Regression guard.** ``actions/setup-node@v4`` with
    ``cache: pnpm`` requires pnpm to already be on PATH; otherwise
    the cache step fails with ``Unable to locate executable file:
    pnpm``. ``pnpm/action-setup@v4`` MUST run earlier in the
    ``build`` job's ``steps`` list. The 2026-05-02 audit caught
    the inverted order plus the stuck-queued workflow at the same
    time — pin the order so the regression can't recur silently.
    """

    pnpm_setup_idx = workflow.find("pnpm/action-setup@v4")
    setup_node_idx = workflow.find("actions/setup-node@v4")
    assert pnpm_setup_idx > -1, "pnpm/action-setup@v4 step missing"
    assert setup_node_idx > -1, "actions/setup-node@v4 step missing"
    # ``cache: pnpm`` is what makes the order matter; assert it
    # explicitly so a future "drop pnpm cache" change doesn't
    # accidentally make this guard vacuous.
    assert "cache: \"pnpm\"" in workflow or "cache: pnpm" in workflow, (
        "actions/setup-node@v4 must use cache: pnpm — drop this "
        "guard if you intentionally moved off pnpm caching."
    )
    assert pnpm_setup_idx < setup_node_idx, (
        f"pnpm/action-setup@v4 (idx={pnpm_setup_idx}) must appear "
        f"BEFORE actions/setup-node@v4 (idx={setup_node_idx}) so "
        f"the latter can resolve pnpm for cache: pnpm."
    )


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
