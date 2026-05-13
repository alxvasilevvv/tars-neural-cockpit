"""Auto-remediation fixers for ``tars-doctor`` (Wave 166).

The diagnostic doctor (Waves 154-156) tells the operator what's
wrong. v0.4 adds a thin remediation layer: for a small set of
slugs we have a *safe, idempotent, non-destructive* fix the
operator can apply with ``tars-doctor --fix``.

Design rules:
  - **Conservative.** Each fixer must be safe to run twice. It
    creates directories, writes idempotent config — never deletes
    or overwrites operator data.
  - **No network, no shell.** Filesystem only. Anything that
    touches launchctl / systemctl / SMTP / etc. lives in a
    separate "operator-confirmed" path (v9.2 target).
  - **Honest about what didn't apply.** If a check is ok or skip
    we don't try to fix it. If we have no fixer for the slug,
    we say so in the result.
  - **No side effects on import.** Fixers do work only when
    ``run_fix`` is called.

Public surface:
  - :class:`FixResult` — what a fixer returns.
  - :data:`FIX_REGISTRY` — ``{slug: fixer_fn}`` mapping.
  - :func:`run_fix` — apply a fixer by slug.
  - :func:`run_all_fixes` — diagnose all + apply every fixer
    that has a registered handler.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Callable

from .checks import CheckResult, run_check


log = logging.getLogger("tars.doctor.fixers")


@dataclass
class FixResult:
    """Outcome of a single fixer invocation."""

    slug: str
    applied: bool = False
    skipped: bool = False
    reason: str = ""
    before_status: str = ""
    after_status: str = ""
    detail: str = ""
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


FixerFn = Callable[[CheckResult], FixResult]


# ─── Individual fixers ────────────────────────────────────────────


def fix_vault(check: CheckResult) -> FixResult:
    """Create the vault directory when it's missing.

    The W154 vault check returns ``status='warn'`` with
    ``error.startswith('vault dir missing')`` when ``~/.tars/vault``
    doesn't exist. The fix is a one-line ``mkdir -p`` — safe,
    idempotent, no operator data at risk.
    """

    r = FixResult(slug="vault", before_status=check.status)
    if check.status == "ok":
        r.skipped = True
        r.reason = "already_ok"
        return r
    if check.status == "skip":
        r.skipped = True
        r.reason = "check_skipped"
        return r

    vault_dir = Path(
        os.getenv("TARS_VAULT_DIR")
        or (Path.home() / ".tars" / "vault")
    )
    try:
        vault_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        r.reason = "mkdir_failed"
        r.detail = str(exc)
        return r

    r.applied = True
    r.detail = f"created {vault_dir}"
    return r


def fix_daemon(check: CheckResult) -> FixResult:
    """Surface the install command — DO NOT auto-run launchctl/systemctl.

    Bootstrapping a LaunchAgent or systemd user-unit changes the
    operator's service-manager state. That's outside the "safe
    fixer" scope; we just emit a clear suggestion and let the
    operator run ``scripts/tars-daemon install`` themselves.
    """

    r = FixResult(slug="daemon", before_status=check.status)
    if check.status == "ok":
        r.skipped = True
        r.reason = "already_ok"
        return r
    r.skipped = True
    r.reason = "manual_action_required"
    r.detail = "run: scripts/tars-daemon install"
    return r


def fix_scheduler(check: CheckResult) -> FixResult:
    """Surface the env-export command — DO NOT mutate the operator's shell.

    Setting ``TARS_SCHEDULER_ENABLED`` from inside a subprocess
    has no effect on the parent shell or the daemon's environment.
    The operator needs to export it in their own profile.
    """

    r = FixResult(slug="scheduler", before_status=check.status)
    if check.status == "ok":
        r.skipped = True
        r.reason = "already_ok"
        return r
    r.skipped = True
    r.reason = "manual_action_required"
    r.detail = "export TARS_SCHEDULER_ENABLED=1 (then restart daemon)"
    return r


# Slugs without a real fixer fall through to a default "no
# auto-fix available; here's the suggestion from the check" path.

FIX_REGISTRY: dict[str, FixerFn] = {
    "vault": fix_vault,
    "daemon": fix_daemon,
    "scheduler": fix_scheduler,
}


# ─── Dispatch ─────────────────────────────────────────────────────


def run_fix(slug: str, *, recheck: bool = True) -> FixResult:
    """Run a single fixer by slug.

    1. Run the diagnostic check to capture ``before_status``.
    2. Look up the fixer; if none, return a ``skipped`` result.
    3. Apply the fixer.
    4. Optionally re-run the check to capture ``after_status``.
    """

    t0 = time.time()
    check = run_check(slug)
    fixer = FIX_REGISTRY.get(slug)
    if fixer is None:
        result = FixResult(
            slug=slug,
            before_status=check.status,
            skipped=True,
            reason="no_fixer_registered",
            detail=check.suggestion or "manual remediation only",
        )
        result.elapsed_ms = round((time.time() - t0) * 1000, 1)
        return result

    try:
        result = fixer(check)
    except Exception as exc:  # never crash the doctor
        result = FixResult(
            slug=slug,
            before_status=check.status,
            reason="fixer_exception",
            detail=f"{type(exc).__name__}: {exc}",
        )

    if recheck and result.applied:
        try:
            after = run_check(slug)
            result.after_status = after.status
        except Exception:  # noqa: BLE001
            pass

    result.elapsed_ms = round((time.time() - t0) * 1000, 1)
    return result


def run_all_fixes() -> list[FixResult]:
    """Apply every registered fixer in registry order."""

    return [run_fix(slug) for slug in FIX_REGISTRY]
