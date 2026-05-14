"""Tests for W253 — voice-driven Composer (multi-file edits).

Each test points the composer store at a temp SQLite + temp backup
dir so they can run in parallel without sharing state. The LLM path
is disabled (``allow_llm=False``) so we exercise the deterministic
stub planner — the LLM bridge is exercised separately at integration
test time via the providers router.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.core.composer import (
    SafetyError,
    apply_plan,
    plan_from_transcript,
    reset_store,
    rollback,
)
from backend.core.composer.types import ComposerPlan, EditOp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path):
    """A minimal repo with two files referencing 'Customer'."""

    (tmp_path / "models.py").write_text(
        "class Customer:\n    name: str\n    def greet(self):\n        return 'Hi ' + self.name\n",
        encoding="utf-8",
    )
    (tmp_path / "readme.md").write_text(
        "# App\n\nThe Customer model is the heart of the app.\n",
        encoding="utf-8",
    )
    (tmp_path / "secret.env").write_text("API_KEY=donotleak\n", encoding="utf-8")
    # Symlink-free target for tests that need to confirm we don't reach .env.
    return tmp_path


@pytest.fixture(autouse=True)
def _isolate_tars_dirs(tmp_path, monkeypatch):
    home = tmp_path / "tars-home"
    home.mkdir()
    monkeypatch.setenv("TARS_HOME", str(home))
    monkeypatch.setenv("TARS_COMPOSER_DB", str(home / "composer.sqlite"))
    monkeypatch.setenv("TARS_COMPOSER_BACKUP_DIR", str(home / "backups"))
    monkeypatch.setenv(
        "TARS_RECEIPT_HOST_KEY_PATH", str(home / "host-key.json")
    )
    monkeypatch.setenv("TARS_RECEIPT_DIR", str(home / "receipts"))
    monkeypatch.setenv(
        "TARS_RECEIPT_DB_PATH", str(home / "receipts.sqlite")
    )
    reset_store()
    yield
    reset_store()


# ---------------------------------------------------------------------------
# 1 — plan_from_transcript returns a valid ComposerPlan
# ---------------------------------------------------------------------------


def test_plan_from_transcript_returns_valid_plan(project):
    plan = plan_from_transcript(
        "rename Customer to Account", project, allow_llm=False
    )
    assert isinstance(plan, ComposerPlan)
    assert plan.plan_id.startswith("cmp_")
    assert plan.state == "draft"
    assert plan.ops, "stub planner should produce at least one op"
    # Every op should have a cached unified diff.
    for op in plan.ops:
        assert isinstance(op, EditOp)
        assert op.diff_unified is not None
        assert op.op in {"create", "modify", "delete", "rename"}
    # Cost preview is non-negative.
    assert plan.estimated_tokens >= 1
    assert plan.estimated_cost_usd >= 0


# ---------------------------------------------------------------------------
# 2 — safety: refuses to touch .env / *.key / .git
# ---------------------------------------------------------------------------


def test_plan_refuses_forbidden_paths(project):
    # The transcript explicitly references the .env we seeded above.
    # The stub planner won't emit it (no recogniser), so we craft a
    # ``create`` directive that names a forbidden path.
    with pytest.raises(SafetyError) as ei:
        plan_from_transcript(
            "compose: create file .env with API_KEY=test",
            project,
            allow_llm=False,
        )
    assert "forbidden" in str(ei.value).lower() or ei.value.reason
    # And the secret file on disk is untouched.
    assert (project / "secret.env").read_text() == "API_KEY=donotleak\n"


def test_plan_allows_secrets_with_explicit_token(project):
    # Same transcript, but with the opt-in token.
    plan = plan_from_transcript(
        "compose: create file .env.local --allow-secrets",
        project,
        allow_llm=False,
    )
    # Stub planner doesn't actually emit it (regex doesn't match the
    # bare ``.env.local`` form), but the call must not raise.
    assert plan.state == "draft"


# ---------------------------------------------------------------------------
# 3 — apply_plan succeeds and creates backup
# ---------------------------------------------------------------------------


def test_apply_creates_backup_and_modifies_files(project, tmp_path):
    plan = plan_from_transcript(
        "rename Customer to Account", project, allow_llm=False
    )
    assert len(plan.ops) >= 1
    result = apply_plan(plan, project)
    assert result.ok, f"apply failed: {result.error}"
    assert result.backup_dir, "backup dir should be recorded"
    backup_dir = Path(result.backup_dir)
    assert backup_dir.exists()
    # At least one of the touched files has a backup copy.
    backed_up = list(backup_dir.rglob("*"))
    assert any(b.is_file() for b in backed_up)
    # And the live file actually changed.
    assert "Account" in (project / "models.py").read_text()
    assert "Customer" not in (project / "models.py").read_text()


# ---------------------------------------------------------------------------
# 4 — rollback restores the original state
# ---------------------------------------------------------------------------


def test_rollback_restores_original_state(project):
    original = (project / "models.py").read_text()
    plan = plan_from_transcript(
        "rename Customer to Account", project, allow_llm=False
    )
    apply_plan(plan, project)
    # Sanity: file changed.
    assert (project / "models.py").read_text() != original

    ok = rollback(plan.plan_id, project)
    assert ok, "rollback should succeed for an applied plan"
    assert (project / "models.py").read_text() == original


# ---------------------------------------------------------------------------
# 5 — receipt emitted per op
# ---------------------------------------------------------------------------


def test_receipt_per_op_emitted(project):
    plan = plan_from_transcript(
        "rename Customer to Account", project, allow_llm=False
    )
    n_ops = len(plan.ops)
    assert n_ops >= 1
    result = apply_plan(plan, project)
    assert result.ok
    # One receipt per op + one summary receipt at minimum.
    assert len(result.receipts) >= n_ops, (
        f"expected >={n_ops} receipts, got {len(result.receipts)}"
    )


# ---------------------------------------------------------------------------
# 6 — reject keeps state untouched
# ---------------------------------------------------------------------------


def test_reject_keeps_state_untouched(project):
    original = (project / "models.py").read_text()
    plan = plan_from_transcript(
        "rename Customer to Account", project, allow_llm=False
    )
    # Manually mark rejected — this is what the HTTP /reject does.
    plan.state = "rejected"
    # Importing get_store to persist.
    from backend.core.composer import get_store
    store = get_store()
    assert store is not None
    store.save_plan(plan)

    # File on disk must not have been touched.
    assert (project / "models.py").read_text() == original
    # And the stored plan must reflect the rejected state.
    persisted = store.load_plan(plan.plan_id)
    assert persisted is not None
    assert persisted.state == "rejected"


# ---------------------------------------------------------------------------
# 7 — rename op handles missing target gracefully
# ---------------------------------------------------------------------------


def test_rename_handles_missing_source_gracefully(project):
    # Build a plan by hand — the stub planner doesn't emit rename ops
    # but the executor must still handle them when an LLM does.
    plan = ComposerPlan(
        plan_id="cmp_renametest1",
        transcript="rename file old.py to new.py",
        intent_summary="manual rename test",
        project_root=str(project),
        ops=[
            EditOp(
                op="rename",
                path="old.py",  # does not exist
                new_path="new.py",
                new_content="# new file\nprint('hello')\n",
            )
        ],
    )
    # Validator tolerates the missing source — it degrades to a
    # create at new_path. Apply should succeed.
    result = apply_plan(plan, project)
    assert result.ok, f"apply failed: {result.error}"
    assert (project / "new.py").exists()
    # And the (non-existent) source remains absent.
    assert not (project / "old.py").exists()
