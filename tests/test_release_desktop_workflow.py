"""Pin the contract of the release-desktop-tagged workflow (Phase L9 L3).

The file MUST live at ``.github/workflows/release-desktop-tagged.yml``
— GitHub Actions only schedules workflows from that directory.

> **Regression history (2026-05-02 audit):**
> PR #4 once moved the file to the repo root to "reset a stuck
> GitHub workflow_id". The unintended side effect was that the
> file was no longer scheduled at all, leaving the
> ``release-desktop`` workflow stuck in ``queued`` for >12h.
> A parallel fix (commits ``df3d491`` + ``a01b568``) restored the
> canonical path concurrent with the audit. The audit added
> :func:`test_workflow_lives_under_dot_github_workflows` as a
> regression guard so the file can never be silently disabled
> by a future move.
>
> Same audit also: the post-restoration version (commit
> ``df3d491``) migrated from the original "build → minisign-sign
> → publish updater channel JSON" pipeline to the simpler
> ``tauri-apps/tauri-action@v0`` flow that uploads to GitHub
> Releases. The original contract tests (``workflow_dispatch``,
> ``python -m backend.core.product.publish``,
> ``desktop/scripts/sign-artifacts.sh``) no longer apply to the
> live workflow; they're preserved here as ``xfail`` so the
> intent isn't lost when the operator decides whether to
> re-add updater channel publishing (Bug #9 in
> ``docs/SYSTEM_AUDIT_2026-05-02.md``).

Currently-enforced contract:

1. The file lives under ``.github/workflows/`` (regression guard).
2. Builds the four canonical Tauri targets (macOS arm64+x86_64,
   Windows x86_64, Linux x86_64).
3. Reads the minisign secret from ``TAURI_SIGNING_PRIVATE_KEY``
   (and the passphrase from ``TAURI_SIGNING_PRIVATE_KEY_PASSWORD``)
   so the tauri-action signing path can pick them up.
4. ``pnpm/action-setup@v4`` runs BEFORE
   ``actions/setup-node@v4`` whenever ``setup-node`` opts in to
   ``cache: pnpm`` (the latter blows up otherwise; only enforced
   when the cache config is actually present).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_WORKFLOW_CANONICAL = REPO / ".github" / "workflows" / "release-desktop-tagged.yml"
_WORKFLOW_LEGACY_ROOT = REPO / "release-desktop-tagged.yml"
_WORKFLOW_CANDIDATES = (_WORKFLOW_CANONICAL, _WORKFLOW_LEGACY_ROOT)


def _resolve_workflow_path() -> Path:
    for candidate in _WORKFLOW_CANDIDATES:
        if candidate.exists():
            return candidate
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
def sign_script() -> str | None:
    if not SIGN_SCRIPT.exists():
        return None
    return SIGN_SCRIPT.read_text(encoding="utf-8")


# ------------------------------------------------------------------------
# Live contract — these must stay green.
# ------------------------------------------------------------------------


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


def test_workflow_passes_minisign_secret_to_env(workflow: str) -> None:
    assert "TAURI_SIGNING_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY }}" in workflow
    assert (
        "TAURI_SIGNING_PRIVATE_KEY_PASSWORD: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY_PASSWORD }}"
        in workflow
    )


def test_workflow_covers_all_four_targets(workflow: str) -> None:
    for target in (
        "aarch64-apple-darwin",
        "x86_64-apple-darwin",
        "x86_64-pc-windows-msvc",
        "x86_64-unknown-linux-gnu",
    ):
        assert target in workflow, f"matrix missing target {target}"


def test_workflow_installs_pnpm_before_setup_node_with_pnpm_cache(workflow: str) -> None:
    """**Regression guard (conditional).** ``actions/setup-node@v4``
    with ``cache: pnpm`` requires pnpm to already be on PATH;
    otherwise the cache step fails with ``Unable to locate
    executable file: pnpm``. ``pnpm/action-setup@v4`` MUST run
    earlier in the ``build`` job's ``steps`` list. We only enforce
    the order when ``cache: pnpm`` is present — the post-2026-05-02
    workflow may drop the cache config (no lockfile in repo) and
    that's fine, but the moment someone re-adds it the order has
    to be right.
    """

    has_pnpm_cache = (
        'cache: "pnpm"' in workflow
        or "cache: pnpm" in workflow
        or "cache: 'pnpm'" in workflow
    )
    if not has_pnpm_cache:
        pytest.skip(
            "actions/setup-node@v4 doesn't request cache: pnpm — order "
            "is irrelevant. Guard re-enables itself when the cache "
            "config returns."
        )

    pnpm_setup_idx = workflow.find("pnpm/action-setup@v4")
    setup_node_idx = workflow.find("actions/setup-node@v4")
    assert pnpm_setup_idx > -1, "pnpm/action-setup@v4 step missing"
    assert setup_node_idx > -1, "actions/setup-node@v4 step missing"
    assert pnpm_setup_idx < setup_node_idx, (
        f"pnpm/action-setup@v4 (idx={pnpm_setup_idx}) must appear "
        f"BEFORE actions/setup-node@v4 (idx={setup_node_idx}) so "
        f"the latter can resolve pnpm for cache: pnpm."
    )


# ------------------------------------------------------------------------
# Legacy contract (xfail) — pre-2026-05-02 workflow shape. Restore as
# strict assertions if/when the operator decides to re-add updater
# channel JSON publishing + first-class minisign signing
# (Bug #9 in docs/SYSTEM_AUDIT_2026-05-02.md).
# ------------------------------------------------------------------------


@pytest.mark.xfail(
    reason=(
        "post-2026-05-02 workflow uses tauri-action's tag-push trigger "
        "instead of workflow_dispatch + Semver input; Bug #9 in audit "
        "tracks the migration trade-off"
    ),
    strict=False,
)
def test_workflow_uses_dispatch_with_version_input(workflow: str) -> None:
    assert "workflow_dispatch:" in workflow
    assert "inputs:" in workflow
    assert "version:" in workflow
    assert "Semver to publish" in workflow


def test_workflow_publishes_updater_channel(workflow: str) -> None:
    """**Bug #9 closed (2026-05-02 audit cleanup).** The workflow MUST
    pass ``includeUpdaterJson: true`` to ``tauri-apps/tauri-action@v0``
    so that ``latest.json`` (Tauri updater channel manifest) is
    published as a release asset. Without it,
    ``tauri-plugin-updater`` polling
    ``releases/latest/download/latest.json`` returns 404 and
    auto-update silently fails.

    Also pin ``updaterJsonPreferNsis: false`` so the published JSON
    advertises the MSI on Windows (Tauri default is NSIS, but our
    bundle ships both — operators on locked-down corporate boxes
    need the MSI path so InTune can pre-stage the installer).
    """

    assert "includeUpdaterJson: true" in workflow, (
        "release workflow must publish latest.json (Tauri updater "
        "channel manifest) so auto-update flows. See Bug #9 in "
        "docs/SYSTEM_AUDIT_2026-05-02.md for context."
    )
    assert "updaterJsonPreferNsis: false" in workflow, (
        "Windows preference must point to MSI for corporate IT "
        "compatibility; flip to true only if the operator confirms "
        "InTune / SCCM picked up NSIS support."
    )


@pytest.mark.xfail(
    reason=(
        "post-2026-05-02 workflow delegates signing to tauri-action's "
        "built-in signer (env var TAURI_SIGNING_PRIVATE_KEY); the "
        "explicit sign-artifacts.sh hop is no longer invoked from the "
        "matrix. Bug #9 in audit tracks the migration."
    ),
    strict=False,
)
def test_workflow_invokes_sign_script(workflow: str) -> None:
    assert "scripts/sign-artifacts.sh" in workflow


# ------------------------------------------------------------------------
# Sign script structural contract — only enforced if the script is
# still present. Skipped (not failed) once the operator removes it.
# ------------------------------------------------------------------------


def test_sign_script_skips_in_dev_mode_with_no_secret(sign_script: str | None) -> None:
    if sign_script is None:
        pytest.skip("sign-artifacts.sh removed; tauri-action handles signing now")
    assert 'if [[ -z "${TAURI_SIGNING_PRIVATE_KEY:-}" ]]; then' in sign_script
    assert "exit 0" in sign_script


def test_sign_script_calls_tauri_signer_with_private_key(sign_script: str | None) -> None:
    if sign_script is None:
        pytest.skip("sign-artifacts.sh removed; tauri-action handles signing now")
    assert "tauri signer sign" in sign_script
    assert "--private-key" in sign_script
    assert "TAURI_SIGNING_PRIVATE_KEY_PASSWORD" in sign_script


def test_sign_script_fails_loud_if_sig_sidecar_missing(sign_script: str | None) -> None:
    if sign_script is None:
        pytest.skip("sign-artifacts.sh removed; tauri-action handles signing now")
    assert 'if [[ ! -f "$art.sig" ]]; then' in sign_script
    assert "exit 2" in sign_script


def test_sign_script_is_executable() -> None:
    if not SIGN_SCRIPT.exists():
        pytest.skip("sign-artifacts.sh removed; tauri-action handles signing now")
    import os

    mode = SIGN_SCRIPT.stat().st_mode
    assert mode & 0o100, f"sign-artifacts.sh is not executable (mode={oct(mode)})"
    with SIGN_SCRIPT.open() as f:
        first = f.readline()
    assert first.startswith("#!"), f"sign-artifacts.sh missing shebang: {first!r}"
