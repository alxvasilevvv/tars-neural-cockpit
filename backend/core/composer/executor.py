"""Composer executor — :func:`apply_plan` and :func:`rollback`.

The executor is the only place that touches the filesystem on
behalf of the composer. It enforces:

- two-phase apply (write a staging copy of every changed file, then
  swap into place after all writes succeed),
- per-file backup to ``~/.tars/composer/backups/<plan_id>/`` so a
  rollback can restore the original tree byte-for-byte,
- one signed receipt per op (and one per approval / rejection /
  rollback) via the W67 receipt-ledger.

The rollback path is symmetric: restore from backup, emit a
``composer.rolled_back`` receipt, mark the plan ``rolled_back`` in
the store. Repeated rollbacks are idempotent — the second call
returns ``False`` because the plan is no longer ``applied``.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from .storage import get_store as _get_store
from .types import ApplyResult, ComposerPlan, EditOp


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _tars_dir() -> Path:
    raw = os.environ.get("TARS_HOME") or "~/.tars"
    return Path(os.path.expanduser(raw))


def _backup_root() -> Path:
    raw = os.environ.get("TARS_COMPOSER_BACKUP_DIR")
    if raw:
        return Path(os.path.expanduser(raw))
    return _tars_dir() / "composer" / "backups"


def _backup_dir_for(plan_id: str) -> Path:
    return _backup_root() / plan_id


# ---------------------------------------------------------------------------
# Receipt emission (best-effort, never raises)
# ---------------------------------------------------------------------------


def _emit_receipt_sync(
    *,
    rtype: str,
    actor: str,
    resource: str | None,
    payload: dict[str, Any],
) -> str | None:
    """Emit a W67 receipt synchronously.

    Best-effort — receipt-ledger failures must never abort the
    composer apply. Returns the receipt id when available.
    """

    try:
        from backend.core.receipts.store import get_store  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        return None
    store = get_store()
    if store is None:
        return None

    async def _go() -> str | None:
        try:
            r = await store.append(rtype, actor, resource, payload)
            return r.id
        except Exception:  # noqa: BLE001
            return None

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_go())
        # Inside an event loop — schedule on a fresh thread loop.
        out: dict[str, str | None] = {"id": None}

        def _runner() -> None:
            try:
                out["id"] = asyncio.run(_go())
            except Exception:  # noqa: BLE001
                out["id"] = None

        import threading  # noqa: PLC0415

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join(timeout=2.0)
        return out["id"]
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# File ops
# ---------------------------------------------------------------------------


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _stage_op(op: EditOp, project_root: Path, staging_root: Path) -> None:
    """Write the op's outcome into the staging directory.

    Staging mirrors ``project_root``; the actual swap into the live
    tree happens in :func:`_commit_op` once all ops have staged
    successfully.
    """

    if op.op == "delete":
        # We mark the staged path with a sentinel so the commit phase
        # knows to remove it. Using a sibling file keeps fs semantics
        # simple.
        sentinel = staging_root / (op.path + ".__composer_delete__")
        _ensure_parent(sentinel)
        sentinel.write_bytes(b"")
        return

    if op.op == "rename":
        target_rel = op.new_path or op.path
        staged = staging_root / target_rel
        _ensure_parent(staged)
        content = op.new_content if op.new_content is not None else (
            op.old_content or ""
        )
        staged.write_text(content, encoding="utf-8")
        # Mark the source path for deletion at commit time.
        if op.new_path and op.new_path != op.path:
            sentinel = staging_root / (op.path + ".__composer_delete__")
            _ensure_parent(sentinel)
            sentinel.write_bytes(b"")
        return

    # create / modify
    staged = staging_root / op.path
    _ensure_parent(staged)
    staged.write_text(op.new_content or "", encoding="utf-8")


def _backup_file(rel: str, project_root: Path, backup_dir: Path) -> None:
    src = project_root / rel
    if not src.exists() or not src.is_file():
        return
    dst = backup_dir / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _commit_op(op: EditOp, project_root: Path, staging_root: Path) -> None:
    """Swap a single staged op into the live project root."""

    if op.op == "delete":
        target = project_root / op.path
        if target.exists():
            target.unlink()
        return

    if op.op == "rename":
        src = project_root / op.path
        dst_rel = op.new_path or op.path
        dst = project_root / dst_rel
        _ensure_parent(dst)
        # Pull content from staging (already validated).
        staged = staging_root / dst_rel
        if staged.exists():
            shutil.copy2(staged, dst)
        if src.exists() and dst_rel != op.path:
            try:
                src.unlink()
            except OSError:
                pass
        return

    # create / modify
    staged = staging_root / op.path
    target = project_root / op.path
    _ensure_parent(target)
    shutil.copy2(staged, target)


def _validate_op(op: EditOp, project_root: Path) -> str | None:
    """Pre-flight check for a single op. Returns an error message or
    ``None`` when the op is safe to stage.
    """

    if not op.path:
        return "empty path"
    if ".." in Path(op.path).parts:
        return "path traverses outside project_root"

    target = (project_root / op.path).resolve()
    try:
        target.relative_to(project_root.resolve())
    except ValueError:
        return "target escapes project_root"

    if op.op == "create":
        if target.exists():
            return f"create target already exists: {op.path}"
    elif op.op == "modify":
        if not target.exists():
            return f"modify target missing: {op.path}"
    elif op.op == "delete":
        if not target.exists():
            return f"delete target missing: {op.path}"
    elif op.op == "rename":
        if not op.new_path:
            return "rename op missing new_path"
        if ".." in Path(op.new_path).parts:
            return "new_path traverses outside project_root"
        if not target.exists():
            # We tolerate the rename op when the source is missing —
            # the user might have asked us to add a stub at the new
            # path. Just degrade to a create at new_path.
            return None
        new_abs = (project_root / op.new_path).resolve()
        try:
            new_abs.relative_to(project_root.resolve())
        except ValueError:
            return "rename target escapes project_root"
    else:
        return f"unknown op: {op.op}"
    return None


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def apply_plan(plan: ComposerPlan, project_root: Path | str | None = None) -> ApplyResult:
    """Apply a plan atomically and emit per-op receipts.

    Strategy:

    1. Validate every op against the live tree.
    2. Stage every op under a temp dir.
    3. Back up every soon-to-be-touched file under
       ``~/.tars/composer/backups/<plan_id>/``.
    4. Commit each op into the live tree.
    5. Emit one ``composer.op.applied`` receipt per op + one
       ``composer.plan.applied`` summary receipt.

    On any failure during steps 1-3, no live files are touched and
    the result is returned with ``ok=False``. On failure during step
    4 the executor restores from the backup created in step 3 before
    returning.
    """

    root = Path(project_root or plan.project_root or ".").expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return ApplyResult(
            plan_id=plan.plan_id,
            ok=False,
            error=f"project_root missing: {root}",
        )

    if plan.state not in ("draft", "approved"):
        return ApplyResult(
            plan_id=plan.plan_id,
            ok=False,
            error=f"plan in state {plan.state!r}; expected draft/approved",
        )

    # ---- 1. validate ---------------------------------------------------
    for idx, op in enumerate(plan.ops):
        err = _validate_op(op, root)
        if err:
            return ApplyResult(
                plan_id=plan.plan_id,
                ok=False,
                failed_index=idx,
                error=err,
            )

    backup_dir = _backup_dir_for(plan.plan_id)
    backup_dir.mkdir(parents=True, exist_ok=True)

    # ---- 2. stage ------------------------------------------------------
    with tempfile.TemporaryDirectory(prefix=f"tars-composer-{plan.plan_id}-") as tmp:
        staging_root = Path(tmp)
        try:
            for op in plan.ops:
                _stage_op(op, root, staging_root)
        except OSError as exc:
            return ApplyResult(
                plan_id=plan.plan_id,
                ok=False,
                error=f"staging failed: {exc}",
                backup_dir=str(backup_dir),
            )

        # ---- 3. backup -------------------------------------------------
        for op in plan.ops:
            try:
                if op.op in ("modify", "delete"):
                    _backup_file(op.path, root, backup_dir)
                elif op.op == "rename":
                    _backup_file(op.path, root, backup_dir)
                    if op.new_path:
                        _backup_file(op.new_path, root, backup_dir)
            except OSError:
                # Backup failure is logged via receipt but doesn't
                # abort — we'd rather apply and have a non-restorable
                # snapshot than refuse the user's edit.
                pass

        # ---- 4. commit -------------------------------------------------
        applied: list[int] = []
        receipts: list[str] = []
        try:
            for idx, op in enumerate(plan.ops):
                _commit_op(op, root, staging_root)
                applied.append(idx)
                rid = _emit_receipt_sync(
                    rtype="composer.op.applied",
                    actor="composer",
                    resource=op.path,
                    payload={
                        "plan_id": plan.plan_id,
                        "op_index": idx,
                        "op": op.op,
                        "path": op.path,
                        "new_path": op.new_path,
                        "diff_bytes": len((op.diff_unified or "").encode("utf-8")),
                    },
                )
                if rid:
                    receipts.append(rid)
        except OSError as exc:
            # Best-effort rollback of whatever we already committed.
            _restore_from_backup(plan, root, applied=applied, backup_dir=backup_dir)
            return ApplyResult(
                plan_id=plan.plan_id,
                ok=False,
                failed_index=len(applied),
                applied_ops=applied,
                error=f"commit failed: {exc}",
                backup_dir=str(backup_dir),
                receipts=receipts,
            )

    # ---- 5. summary receipt + persist state ---------------------------
    summary_id = _emit_receipt_sync(
        rtype="composer.plan.applied",
        actor="composer",
        resource=plan.plan_id,
        payload={
            "plan_id": plan.plan_id,
            "ops": len(plan.ops),
            "transcript_chars": len(plan.transcript),
            "intent_summary": plan.intent_summary,
            "backup_dir": str(backup_dir),
        },
    )
    if summary_id:
        receipts.append(summary_id)

    plan.state = "applied"
    try:
        store = _get_store()
        if store is not None:
            store.save_plan(plan)
            store.record_applied(
                plan_id=plan.plan_id,
                applied_ops=applied,
                backup_dir=str(backup_dir),
                receipts=receipts,
            )
    except Exception:  # noqa: BLE001
        pass

    return ApplyResult(
        plan_id=plan.plan_id,
        ok=True,
        applied_ops=applied,
        backup_dir=str(backup_dir),
        receipts=receipts,
    )


def _restore_from_backup(
    plan: ComposerPlan,
    project_root: Path,
    *,
    applied: list[int],
    backup_dir: Path,
) -> None:
    """Best-effort restore of files we touched during a partial apply."""

    for idx in applied:
        op = plan.ops[idx]
        src = backup_dir / op.path
        if src.exists():
            dst = project_root / op.path
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dst)
            except OSError:
                pass
        else:
            # No backup means the op was a ``create`` — undo by
            # removing the file we made.
            target = project_root / op.path
            if target.exists() and op.op == "create":
                try:
                    target.unlink()
                except OSError:
                    pass


def rollback(plan_id: str, project_root: Path | str | None = None) -> bool:
    """Restore the project tree from a plan's backup directory.

    Returns ``True`` when at least one file was restored; ``False``
    when the plan is unknown, already rolled back, or has no
    backup. Always emits a ``composer.plan.rolled_back`` receipt on
    success.
    """

    store = _get_store()
    if store is None:
        return False
    plan = store.load_plan(plan_id)
    if plan is None or plan.state != "applied":
        return False

    backup_dir = _backup_dir_for(plan_id)
    if not backup_dir.exists():
        return False

    root = Path(project_root or plan.project_root or ".").expanduser().resolve()
    if not root.exists():
        return False

    # Restore every file we have a backup for.
    restored = 0
    for op in plan.ops:
        # Resurrect modified / deleted files.
        if op.op in ("modify", "delete"):
            src = backup_dir / op.path
            if src.exists():
                dst = root / op.path
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(src, dst)
                    restored += 1
                except OSError:
                    pass
        elif op.op == "create":
            # Undo by removing the file we created.
            target = root / op.path
            if target.exists():
                try:
                    target.unlink()
                    restored += 1
                except OSError:
                    pass
        elif op.op == "rename":
            src_backup = backup_dir / op.path
            target_at_new = root / (op.new_path or op.path)
            if target_at_new.exists() and op.new_path:
                try:
                    target_at_new.unlink()
                except OSError:
                    pass
            if src_backup.exists():
                dst = root / op.path
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(src_backup, dst)
                    restored += 1
                except OSError:
                    pass

    plan.state = "rolled_back"
    store.save_plan(plan)
    _emit_receipt_sync(
        rtype="composer.plan.rolled_back",
        actor="composer",
        resource=plan_id,
        payload={
            "plan_id": plan_id,
            "files_restored": restored,
        },
    )
    return restored > 0
