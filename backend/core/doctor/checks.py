"""Individual health checks + the registry that drives ``tars-doctor``.

Each check is a function ``(timeout_s: float) -> CheckResult``.
Checks are added by appending to :data:`REGISTRY`. The doctor's
``--json`` mode serialises the list of results; ``--quiet`` filters
to status != ok.

Design rules:
  - Imports are local to the check function so a broken module
    never breaks the doctor itself.
  - No network. (The web app's ``/health`` endpoint covers the
    network side.)
  - Each check has a fixed ``slug`` so machine-readable consumers
    can pick out specific rows.
  - Wall-time is captured per check; slow checks are flagged.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal


log = logging.getLogger("tars.doctor")


CheckStatus = Literal["ok", "warn", "fail", "skip"]


@dataclass
class CheckResult:
    """One row in the health-check table."""

    slug: str
    label: str
    status: CheckStatus = "ok"
    summary: str = ""
    suggestion: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CheckFn = Callable[[float], CheckResult]


# ─── Individual checks ──────────────────────────────────────────────


def _stale_seconds(ts: float) -> float:
    return max(0.0, time.time() - float(ts))


def check_background_daemon(_timeout_s: float) -> CheckResult:
    """Heartbeat freshness + service registration."""

    r = CheckResult(slug="daemon", label="Background daemon")
    try:
        from backend.core.daemon import read_heartbeat
    except Exception as exc:  # noqa: BLE001
        r.status = "skip"
        r.summary = f"daemon module import failed: {exc}"
        return r

    hb = read_heartbeat()
    if hb is None:
        r.status = "warn"
        r.summary = "no heartbeat file (daemon not yet started?)"
        r.suggestion = "run: scripts/tars-daemon install"
        return r

    last_tick = float(hb.get("last_tick") or 0.0)
    age = _stale_seconds(last_tick) if last_tick > 0 else None
    r.details = {
        "pid": hb.get("pid"),
        "last_status": hb.get("last_status"),
        "tick_count": hb.get("tick_count"),
        "last_tick_age_s": round(age, 1) if age is not None else None,
        "contract_version": hb.get("contract_version"),
    }
    if age is None:
        r.status = "warn"
        r.summary = f"daemon present but no ticks yet (status={hb.get('last_status')})"
    elif age > 300:
        r.status = "fail"
        r.summary = f"heartbeat stale: last tick {age:.0f}s ago"
        r.suggestion = "run: scripts/tars-daemon restart"
    elif age > 90:
        r.status = "warn"
        r.summary = f"heartbeat older than 90s ({age:.0f}s)"
    else:
        r.status = "ok"
        r.summary = (
            f"alive ({age:.0f}s ago, {hb.get('tick_count')} ticks, status={hb.get('last_status')})"
        )
    return r


def check_mcp_server(_timeout_s: float) -> CheckResult:
    """MCP tool registry — present + non-empty."""

    r = CheckResult(slug="mcp", label="MCP server tool registry")
    try:
        from backend.core.mcp import CONTRACT_VERSION, builtin_tools  # type: ignore
    except Exception as exc:  # noqa: BLE001
        r.status = "skip"
        r.summary = f"mcp module not importable: {exc}"
        r.suggestion = "verify backend/core/mcp/ is present (Wave 150)"
        return r

    try:
        tools = builtin_tools()
        names = [getattr(t, "name", "?") for t in tools]
    except Exception as exc:  # noqa: BLE001
        r.status = "fail"
        r.summary = f"registry failed: {exc}"
        return r

    r.details = {
        "contract_version": CONTRACT_VERSION,
        "tool_count": len(tools),
        "tools": names,
    }
    if not tools:
        r.status = "warn"
        r.summary = "no tools registered (expected ≥5 builtins)"
    elif len(tools) < 5:
        r.status = "warn"
        r.summary = f"only {len(tools)} tools registered"
    else:
        r.status = "ok"
        r.summary = f"{len(tools)} tools, contract {CONTRACT_VERSION}"
    return r


def check_clone_sync(_timeout_s: float) -> CheckResult:
    """AI Clone store — DB reachable + sync interval sane."""

    r = CheckResult(slug="clone", label="AI Clone store + sync")
    if (os.getenv("CLONE_STORE") or "").strip().lower() in {"disabled", "off", "0", "no", "false"}:
        r.status = "skip"
        r.summary = "CLONE_STORE=disabled"
        return r
    try:
        from backend.core.clone import sync as clone_sync  # type: ignore
        from backend.core.clone.style import get_clone_store  # type: ignore
    except Exception as exc:  # noqa: BLE001
        r.status = "skip"
        r.summary = f"clone module not importable: {exc}"
        return r

    try:
        store = get_clone_store()
        enabled = bool(getattr(store, "enabled", False))
        db_path = str(getattr(store, "db_path", "")) or "?"
        sync_interval = clone_sync._interval() if hasattr(clone_sync, "_interval") else None
    except Exception as exc:  # noqa: BLE001
        r.status = "fail"
        r.summary = f"clone store failed: {exc}"
        return r

    r.details = {
        "db_path": db_path,
        "store_enabled": enabled,
        "sync_interval": sync_interval,
        "contract_version": getattr(clone_sync, "CONTRACT_VERSION", "?"),
    }
    if not enabled:
        r.status = "warn"
        r.summary = "store present but disabled"
        r.suggestion = "unset CLONE_STORE=disabled (or ensure ~/.tars writable)"
    else:
        r.status = "ok"
        r.summary = f"db at {db_path}, sync every {sync_interval} msgs"
    return r


def check_scheduler(_timeout_s: float) -> CheckResult:
    """Scheduler store — present + opt-in flag visible."""

    r = CheckResult(slug="scheduler", label="Scheduler store")
    try:
        from backend.core.scheduler.runner import _is_enabled  # type: ignore
        from backend.core.scheduler.store import get_store  # type: ignore
    except Exception as exc:  # noqa: BLE001
        r.status = "skip"
        r.summary = f"scheduler module not importable: {exc}"
        return r

    enabled = _is_enabled()
    try:
        store = get_store()
        store_ok = bool(getattr(store, "enabled", False))
        db_path = str(getattr(store, "db_path", "")) or "?"
    except Exception as exc:  # noqa: BLE001
        r.status = "fail"
        r.summary = f"scheduler store failed: {exc}"
        return r

    r.details = {
        "tick_loop_enabled": enabled,
        "store_enabled": store_ok,
        "db_path": db_path,
    }
    if not enabled:
        r.status = "warn"
        r.summary = "store ok; tick loop NOT enabled (TARS_SCHEDULER_ENABLED unset)"
        r.suggestion = "export TARS_SCHEDULER_ENABLED=1 for the web app / daemon"
    elif not store_ok:
        r.status = "fail"
        r.summary = "scheduler enabled but store init failed"
    else:
        r.status = "ok"
        r.summary = f"enabled, db at {db_path}"
    return r


def check_webhooks(_timeout_s: float) -> CheckResult:
    """Webhooks store + dispatcher import."""

    r = CheckResult(slug="webhooks", label="Webhooks dispatcher")
    try:
        from backend.core.webhooks import emit, store as wh_store  # type: ignore  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        r.status = "skip"
        r.summary = f"webhooks module not importable: {exc}"
        return r

    try:
        ws = wh_store.get_store() if hasattr(wh_store, "get_store") else None
        enabled = bool(getattr(ws, "enabled", True)) if ws else True
        db_path = str(getattr(ws, "db_path", "")) if ws else "?"
    except Exception as exc:  # noqa: BLE001
        r.status = "fail"
        r.summary = f"webhooks store failed: {exc}"
        return r

    r.details = {"store_enabled": enabled, "db_path": db_path}
    r.status = "ok" if enabled else "warn"
    r.summary = f"dispatcher importable, store at {db_path}" if enabled else "store disabled"
    return r


def check_cowork(_timeout_s: float) -> CheckResult:
    """Cowork store reachable (W129)."""

    r = CheckResult(slug="cowork", label="Cowork sessions store")
    try:
        from backend.core.cowork.store import (  # type: ignore
            CoworkStore,
            _resolve_db_path,
            is_disabled,
        )
    except Exception as exc:  # noqa: BLE001
        r.status = "skip"
        r.summary = f"cowork module not importable: {exc}"
        return r

    if is_disabled():
        r.status = "skip"
        r.summary = "TARS_COWORK_STORE=disabled"
        return r

    try:
        db_path = _resolve_db_path()
    except Exception as exc:  # noqa: BLE001
        r.status = "fail"
        r.summary = f"cowork db path resolution failed: {exc}"
        return r

    r.details = {"enabled": True, "db_path": db_path}
    r.status = "ok"
    r.summary = f"store db at {db_path}"
    return r


def check_receipts(_timeout_s: float) -> CheckResult:
    """Receipts ledger reachable (W95)."""

    r = CheckResult(slug="receipts", label="Receipt ledger")
    try:
        from backend.core.receipts.ledger import get_ledger  # type: ignore
    except Exception:
        try:
            # Fallback to older module surface
            from backend.core.receipts import store as r_store  # type: ignore
            get_ledger = r_store.get_store  # type: ignore
        except Exception as exc:  # noqa: BLE001
            r.status = "skip"
            r.summary = f"receipts module not importable: {exc}"
            return r

    try:
        led = get_ledger()
        enabled = bool(getattr(led, "enabled", True))
        path = str(getattr(led, "db_path", getattr(led, "path", ""))) or "?"
    except Exception as exc:  # noqa: BLE001
        r.status = "fail"
        r.summary = f"ledger init failed: {exc}"
        return r

    r.details = {"enabled": enabled, "path": path}
    r.status = "ok" if enabled else "warn"
    r.summary = f"ledger at {path}" if enabled else "ledger disabled"
    return r


def check_llm_provider(_timeout_s: float) -> CheckResult:
    """At least one LLM provider key is configured.

    Operators frequently set up TARS without realizing the chat
    layer needs an Anthropic, OpenAI, OR OpenRouter key. This
    check surfaces that early. We only check env presence —
    never call the provider (that's a network check, out of
    scope here).

    Recognised env vars (in this priority order):
      - ANTHROPIC: TARS_ANTHROPIC_API_KEY, ANTHROPIC_API_KEY
      - OPENAI:    TARS_OPENAI_API_KEY,    OPENAI_API_KEY
      - OPENROUTER: TARS_OPENROUTER_API_KEY, OPENROUTER_API_KEY
    """

    r = CheckResult(slug="llm_provider", label="LLM provider keys")
    anth = (os.getenv("TARS_ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "").strip()
    oai = (os.getenv("TARS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    orouter = (
        os.getenv("TARS_OPENROUTER_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or ""
    ).strip()

    def _redact(s: str) -> str:
        if not s:
            return ""
        return s[:6] + "…" + s[-3:] if len(s) > 12 else "…redacted…"

    r.details = {
        "anthropic_set": bool(anth),
        "anthropic_preview": _redact(anth) if anth else None,
        "openai_set": bool(oai),
        "openai_preview": _redact(oai) if oai else None,
        "openrouter_set": bool(orouter),
        "openrouter_preview": _redact(orouter) if orouter else None,
    }
    configured = []
    if anth:
        configured.append("Anthropic")
    if oai:
        configured.append("OpenAI")
    if orouter:
        configured.append("OpenRouter")

    if not configured:
        r.status = "warn"
        r.summary = "no LLM provider key set"
        r.suggestion = (
            "set TARS_ANTHROPIC_API_KEY, TARS_OPENAI_API_KEY, "
            "or TARS_OPENROUTER_API_KEY env"
        )
    elif len(configured) == 1:
        r.status = "ok"
        r.summary = f"{configured[0]} configured"
    else:
        r.status = "ok"
        r.summary = " + ".join(configured) + " configured"
    return r


def check_disk_space(_timeout_s: float) -> CheckResult:
    """Free space at ``~/.tars/`` (or its parent if it doesn't exist).

    SQLite stores (clone, cowork, receipts, webhooks) live here.
    Below 100MB free → fail; below 1GB → warn; else ok.
    """

    import shutil

    r = CheckResult(slug="disk_space", label="Disk space (~/.tars)")
    target = Path.home() / ".tars"
    probe_dir = target if target.exists() else target.parent
    try:
        total, used, free = shutil.disk_usage(probe_dir)
    except OSError as exc:
        r.status = "fail"
        r.summary = f"disk_usage failed: {exc}"
        return r

    free_mb = free / (1024 * 1024)
    free_gb = free_mb / 1024
    r.details = {
        "probe_dir": str(probe_dir),
        "total_gb": round(total / (1024**3), 1),
        "used_gb": round(used / (1024**3), 1),
        "free_gb": round(free_gb, 1),
        "free_mb": round(free_mb, 1),
    }
    if free_mb < 100:
        r.status = "fail"
        r.summary = f"only {free_mb:.0f} MB free at {probe_dir}"
        r.suggestion = "free disk space — TARS SQLite stores live here"
    elif free_gb < 1:
        r.status = "warn"
        r.summary = f"{free_mb:.0f} MB free (< 1 GB)"
        r.suggestion = "consider freeing disk space"
    else:
        r.status = "ok"
        r.summary = f"{free_gb:.1f} GB free at {probe_dir}"
    return r


def check_log_freshness(_timeout_s: float) -> CheckResult:
    """Daemon log file freshness.

    If the daemon is running, ``~/.tars/daemon.out.log`` should
    have been written to recently. A stale log (no writes in the
    last hour) often means the daemon crashed without updating
    the heartbeat. This is a complementary signal to the daemon
    heartbeat check.
    """

    r = CheckResult(slug="log_freshness", label="Daemon log file freshness")
    log_path = Path.home() / ".tars" / "daemon.out.log"
    if not log_path.exists():
        r.status = "skip"
        r.summary = "no daemon log file yet"
        return r

    try:
        mtime = log_path.stat().st_mtime
        size = log_path.stat().st_size
    except OSError as exc:
        r.status = "fail"
        r.summary = f"stat failed: {exc}"
        return r

    age_s = max(0.0, time.time() - mtime)
    r.details = {
        "log_path": str(log_path),
        "size_bytes": size,
        "age_s": round(age_s, 1),
    }
    if age_s < 300:  # 5 min
        r.status = "ok"
        r.summary = f"updated {age_s:.0f}s ago, {size} bytes"
    elif age_s < 3600:  # 1 hour
        r.status = "warn"
        r.summary = f"updated {age_s/60:.0f} min ago"
    else:
        r.status = "fail"
        r.summary = f"updated {age_s/3600:.1f} hours ago — daemon may be hung"
        r.suggestion = "run: scripts/tars-daemon restart"
    return r


def check_vault(_timeout_s: float) -> CheckResult:
    """Vault dir exists + key files readable."""

    r = CheckResult(slug="vault", label="Vault (key + secrets storage)")
    vault_dir = Path(os.getenv("TARS_VAULT_DIR") or (Path.home() / ".tars" / "vault"))
    r.details["vault_dir"] = str(vault_dir)
    if not vault_dir.exists():
        r.status = "warn"
        r.summary = f"vault dir missing: {vault_dir}"
        r.suggestion = "first cockpit launch initialises this automatically"
        return r
    try:
        # We don't *read* the contents — just count the files so the
        # operator can tell whether they have any secrets at all.
        files = [p for p in vault_dir.iterdir() if p.is_file()]
        r.details["file_count"] = len(files)
    except OSError as exc:
        r.status = "fail"
        r.summary = f"vault dir not readable: {exc}"
        return r
    r.status = "ok"
    r.summary = f"{len(files)} entries in {vault_dir}"
    return r


# ─── Registry ───────────────────────────────────────────────────────


REGISTRY: list[tuple[str, CheckFn]] = [
    ("daemon", check_background_daemon),
    ("mcp", check_mcp_server),
    ("clone", check_clone_sync),
    ("scheduler", check_scheduler),
    ("webhooks", check_webhooks),
    ("cowork", check_cowork),
    ("receipts", check_receipts),
    ("vault", check_vault),
    ("llm_provider", check_llm_provider),
    ("disk_space", check_disk_space),
    ("log_freshness", check_log_freshness),
]


def run_check(slug: str, *, timeout_s: float = 5.0) -> CheckResult:
    for s, fn in REGISTRY:
        if s == slug:
            t0 = time.time()
            try:
                result = fn(timeout_s)
            except Exception as exc:  # never let the doctor crash
                result = CheckResult(
                    slug=s,
                    label=s,
                    status="fail",
                    summary=f"unhandled exception: {type(exc).__name__}: {exc}",
                )
            result.elapsed_ms = round((time.time() - t0) * 1000, 1)
            return result
    return CheckResult(
        slug=slug, label=slug, status="fail",
        summary=f"unknown check slug: {slug}",
    )


def run_all(*, timeout_s: float = 5.0) -> list[CheckResult]:
    out: list[CheckResult] = []
    for slug, _ in REGISTRY:
        out.append(run_check(slug, timeout_s=timeout_s))
    return out
