"""Pin the operator playbook ↔ release scripts ↔ workflow contracts.

Walking the operator launch playbook end-to-end on 2026-05-08 surfaced
a cluster of factual drift between what the docs told the operator to
expect and what the scripts/workflow actually did. This file pins the
fixed contract so the next drift fails CI loudly instead of silently
shipping a broken playbook.

Specifically guarded:

1. **Tauri release-key path consistency.** `generate-release-keys.sh`
   defaults to `~/.tars-release-keys/tars-desktop.key`. The playbook
   used to claim `~/.tars/release/minisign.key` (a path the script
   never produced), so operators copying commands hit "no such file"
   immediately.

2. **Base64 encoding for `TAURI_SIGNING_PRIVATE_KEY`.** `tauri-action`
   contracts the value as base64. Both the playbook and the script's
   trailing operator hint must show `base64 < <key>` before the
   `gh secret set` pipe — raw piping silently mis-imports on some
   tauri-action versions.

3. **Release workflow trigger language.** The live workflow is
   `on.push.tags: 'v*'`. Stale references to `workflow_dispatch` or
   `gh workflow run` mislead operators who try to ship a release.
   Both the script's footer and `RELEASE_NOTES_v0.1.0-rc.1.md` must
   match the live workflow.

4. **Download base URL.** Post-B-017, all download flows must route
   through `tars.meeet.world/dl/<file>` (Pages Function proxies
   private-repo releases). Direct `github.com/.../releases` URLs
   404 anonymously.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT_GEN_KEYS = REPO / "desktop" / "scripts" / "generate-release-keys.sh"
WORKFLOW = REPO / ".github" / "workflows" / "release-desktop-tagged.yml"
PLAYBOOK = REPO / "docs" / "OPERATOR_LAUNCH_PLAYBOOK.md"
RELEASE_NOTES = REPO / "docs" / "RELEASE_NOTES_v0.1.0-rc.1.md"
OPS_TODO = REPO / "docs" / "TARS_MEEET_OPS_TODO.md"


@pytest.fixture(scope="module")
def gen_keys() -> str:
    return SCRIPT_GEN_KEYS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def playbook() -> str:
    return PLAYBOOK.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def release_notes() -> str:
    return RELEASE_NOTES.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def ops_todo() -> str:
    return OPS_TODO.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Key-path consistency
# ---------------------------------------------------------------------------
def test_gen_keys_default_path_is_tars_release_keys(gen_keys: str) -> None:
    """Source of truth: the script's `SECRET_DIR` line. Any doc that
    promises a different default path will fail this assertion via
    the playbook check below."""
    assert 'SECRET_DIR="${HOME}/.tars-release-keys"' in gen_keys
    assert 'SECRET_PATH="${SECRET_DIR}/tars-desktop.key"' in gen_keys


def test_playbook_uses_actual_key_path(playbook: str) -> None:
    """Playbook must reference the real default path. The old
    `~/.tars/release/minisign.{key,pub}` paths were aspirational —
    the script never produced them."""
    assert "~/.tars-release-keys/tars-desktop.key" in playbook, (
        "OPERATOR_LAUNCH_PLAYBOOK.md must reference the default key "
        "path produced by generate-release-keys.sh "
        "(~/.tars-release-keys/tars-desktop.key). The legacy "
        "~/.tars/release/minisign.key path is fictional."
    )
    assert "~/.tars/release/minisign.key" not in playbook, (
        "OPERATOR_LAUNCH_PLAYBOOK.md still references the fictional "
        "~/.tars/release/minisign.key path; replace with the real "
        "~/.tars-release-keys/tars-desktop.key."
    )


# ---------------------------------------------------------------------------
# 2. base64 encoding contract
# ---------------------------------------------------------------------------
def test_gen_keys_advertises_base64_pipe(gen_keys: str) -> None:
    """tauri-action documents `TAURI_SIGNING_PRIVATE_KEY` as base64.
    The script's operator hint at the end must use `base64 < <key>`
    (or equivalent); raw piping is undefined behavior."""
    assert "base64 < " in gen_keys, (
        "generate-release-keys.sh must show `base64 < <key>` before the "
        "`gh secret set` pipe — tauri-action expects base64."
    )


def test_playbook_uses_base64_pipe(playbook: str) -> None:
    assert "base64 < ~/.tars-release-keys/tars-desktop.key" in playbook, (
        "OPERATOR_LAUNCH_PLAYBOOK.md must base64-encode the Tauri "
        "private key before `gh secret set` / `pbcopy` so the secret "
        "value matches tauri-action's contract."
    )


# ---------------------------------------------------------------------------
# 3. release workflow trigger language
# ---------------------------------------------------------------------------
def test_workflow_actually_uses_tag_push(workflow: str) -> None:
    """The 2026-05-02 audit reverted to tag-push; pin it so future
    drift in the workflow either updates the docs or breaks loudly."""
    assert "push:" in workflow
    assert "tags:" in workflow
    assert '"v*"' in workflow or "'v*'" in workflow or "- v*" in workflow


def test_gen_keys_footer_matches_real_trigger(gen_keys: str) -> None:
    """Operator footer in the script must point at the real workflow
    file + use the real tag pattern (`v*`, NOT `desktop-v*`)."""
    assert "release-desktop-tagged.yml" in gen_keys, (
        "Footer in generate-release-keys.sh must reference "
        "release-desktop-tagged.yml (the live filename), not the "
        "stale `release-desktop.yml`."
    )
    assert "desktop-v" not in gen_keys, (
        "Footer suggests a `desktop-vX.Y.Z` tag, but the workflow "
        "trigger is `v*` (no prefix). Operator following the script's "
        "footer would tag in a way that doesn't fire CI."
    )


def test_release_notes_describe_tag_push(release_notes: str) -> None:
    """RELEASE_NOTES_v0.1.0-rc.1.md previously claimed
    `workflow_dispatch only`, contradicting the live workflow.
    Notes must describe the actual tag-push trigger so operators
    don't waste an hour looking for a missing dispatch button."""
    assert "git tag v" in release_notes, (
        "Release notes must show the `git tag v<x>` flow; the workflow "
        "is tag-triggered."
    )
    assert "workflow_dispatch only" not in release_notes, (
        "Release notes still claim `workflow_dispatch only` — "
        "contradicts the live workflow which is `on.push.tags: 'v*'`."
    )


# ---------------------------------------------------------------------------
# 4. Download base URL is the Pages-Function proxy (B-017)
# ---------------------------------------------------------------------------
def test_playbook_download_base_url_uses_proxy(playbook: str) -> None:
    """The B-017 fix routes downloads through `tars.meeet.world/dl/*`.
    Direct `github.com/.../releases` URLs 404 anonymously while the
    repo is private."""
    assert "TARS_DOWNLOAD_BASE_URL=https://tars.meeet.world/dl" in playbook, (
        "OPERATOR_LAUNCH_PLAYBOOK.md must instruct the operator to set "
        "TARS_DOWNLOAD_BASE_URL=https://tars.meeet.world/dl — "
        "github.com URLs return 404 to anonymous callers (B-017)."
    )


def test_ops_todo_documents_release_token(ops_todo: str) -> None:
    """`GITHUB_RELEASE_TOKEN` is the single secret that unblocks the
    B-017 install funnel; ops checklist must spell out the setup."""
    assert "GITHUB_RELEASE_TOKEN" in ops_todo, (
        "docs/TARS_MEEET_OPS_TODO.md must document GITHUB_RELEASE_TOKEN "
        "setup — it's the only operator action the B-017 fix needs."
    )
    # Markdown wrap can split "Contents:" and "Read-only" across lines.
    # Collapse whitespace so the contract check is layout-tolerant.
    flat = " ".join(ops_todo.split())
    assert "Contents: Read-only" in flat, (
        "Operator setup must specify the fine-grained PAT scope "
        "(Contents: Read-only) so the operator picks the minimum-priv "
        "permission set."
    )
