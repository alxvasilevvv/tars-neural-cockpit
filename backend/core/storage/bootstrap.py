"""W231 — boot-time DB bootstrap.

A single ``init_all_databases()`` is called from
``web_extras/app.py``'s lifespan. It:

1. Creates ``~/.tars/`` with mode 0o700.
2. Touches every canonical SQLite/JSON path the cockpit reads
   (each store auto-creates its own schema in __init__).
3. Seeds a minimum-viable set of rows so empty tabs don't show
   "no data":
     * one default agent (``TARS Default`` on the ``web_search`` pack)
     * one welcome receipt (``system.bootstrap``) into the ledger
     * one entitlements file at the free tier
4. Returns a :class:`BootstrapResult` describing every step.

The whole function is IDEMPOTENT — running it twice never throws,
never duplicates seeded rows, never re-creates the host key.

Failures inside any single step are logged but never raise, so a
busted optional component (e.g. receipts disabled) cannot block the
backend from booting.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("tars.storage.bootstrap")

DEFAULT_TARS_DIR = Path.home() / ".tars"


def tars_dir() -> Path:
    """Resolve the per-user TARS state dir.

    Honours ``TARS_HOME`` for tests, falls back to ``~/.tars``.
    Creates it with 0o700 if missing.
    """

    raw = os.getenv("TARS_HOME")
    base = Path(raw).expanduser() if raw else DEFAULT_TARS_DIR
    base.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(base, 0o700)
    except OSError:
        pass
    return base


@dataclass
class BootstrapResult:
    """Summary returned by :func:`init_all_databases`."""

    tars_dir: str = ""
    steps_ok: list[str] = field(default_factory=list)
    steps_warn: list[tuple[str, str]] = field(default_factory=list)
    seeded: dict[str, object] = field(default_factory=dict)
    elapsed_ms: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": True,
            "tars_dir": self.tars_dir,
            "steps_ok": list(self.steps_ok),
            "steps_warn": [
                {"step": s, "warn": w} for s, w in self.steps_warn
            ],
            "seeded": dict(self.seeded),
            "elapsed_ms": self.elapsed_ms,
        }


def _stderr(msg: str) -> None:
    """Always-visible boot log (also surfaces in /tmp/tars-backend-8765.log)."""
    try:
        sys.stderr.write(f"[storage.bootstrap] {msg}\n")
        sys.stderr.flush()
    except Exception:
        pass


def _safe(step: str, fn, result: BootstrapResult) -> object | None:
    """Run a single bootstrap step; capture exceptions as warn entries."""
    try:
        out = fn()
        result.steps_ok.append(step)
        _stderr(f"ok: {step}")
        return out
    except Exception as exc:  # never raise to caller
        msg = str(exc)[:240]
        result.steps_warn.append((step, msg))
        _stderr(f"warn: {step}: {msg}")
        log.warning("bootstrap step failed: %s -- %s", step, msg)
        return None


# ---- individual steps -------------------------------------------------------


def _init_dir() -> str:
    d = tars_dir()
    return str(d)


def _init_agents() -> dict[str, object]:
    from backend.core.agents import get_agent_store

    store = get_agent_store()
    if not store.enabled:
        return {"enabled": False}
    return {"enabled": True, "db_path": store.db_path}


def _init_meeet() -> dict[str, object]:
    # Schema is created lazily on first write; the construct itself is
    # cheap. We import + instantiate to force the path to materialise.
    from backend.core.meeet import get_store as _get_meeet_store

    store = _get_meeet_store()
    enabled = bool(getattr(store, "enabled", False))
    return {"enabled": enabled, "db_path": getattr(store, "db_path", None)}


def _init_chat() -> dict[str, object]:
    from backend.core.chat.store import get_chat_store

    store = get_chat_store()
    enabled = bool(getattr(store, "enabled", False))
    return {"enabled": enabled, "db_path": getattr(store, "db_path", None)}


def _init_memory() -> dict[str, object]:
    from backend.core.memory import get_memory_store

    store = get_memory_store()
    enabled = bool(getattr(store, "enabled", False))
    return {"enabled": enabled, "db_path": getattr(store, "db_path", None)}


def _init_policy() -> dict[str, object]:
    from backend.core.policy import get_policy_store

    store = get_policy_store()
    return {"enabled": True, "db_path": getattr(store, "db_path", None)}


def _init_scheduler() -> dict[str, object]:
    from backend.core.scheduler import get_store as _scheduler_get

    store = _scheduler_get()
    enabled = bool(getattr(store, "enabled", False))
    return {"enabled": enabled, "db_path": getattr(store, "_db_path", None)}


def _init_workspaces() -> dict[str, object]:
    from backend.core.workspaces.store import get_store as _ws_get

    store = _ws_get()
    enabled = bool(getattr(store, "enabled", False))
    return {"enabled": enabled, "db_path": getattr(store, "_db_path", None)}


def _init_webhooks() -> dict[str, object]:
    from backend.core.webhooks.store import get_store as _wh_get

    store = _wh_get()
    enabled = bool(getattr(store, "enabled", False))
    return {"enabled": enabled, "db_path": getattr(store, "_db_path", None)}


def _init_receipts() -> dict[str, object]:
    from backend.core.receipts import get_store as _r_get

    store = _r_get()
    if store is None:
        return {"enabled": False}
    return {"enabled": True, "db_path": getattr(store, "db_path", None)}


def _init_entitlements() -> dict[str, object]:
    """Touch the entitlements JSON file so cockpit reads succeed."""
    from backend.core.entitlements import get_store as _ent_get

    store = _ent_get()
    snap = store.snapshot()
    return {"enabled": True, "tier": snap.get("tier")}


# ---- seeders ----------------------------------------------------------------


async def _seed_default_agent() -> dict[str, object]:
    """If no agents exist yet, create the welcome agent.

    Idempotent: short-circuits when at least one agent is already
    persisted.
    """
    from backend.core.agents import get_agent_store

    store = get_agent_store()
    if not store.enabled:
        return {"seeded": False, "reason": "agents_store_disabled"}
    existing = await store.list_agents(include_archived=True)
    if existing:
        return {
            "seeded": False,
            "reason": "already_exists",
            "count": len(existing),
        }
    agent = await store.create_agent(
        name="TARS Default",
        pack_slug="web_search",
        description=(
            "Welcome agent created on first boot. Rename or replace "
            "from the Agents tab; the universal web_search pack covers "
            "the broadest range of intents."
        ),
        system_prompt=(
            "You are TARS, a local-first assistant. Be concise, "
            "factual, and honest about what you don't know."
        ),
        metadata={"source": "bootstrap", "wave": "W231"},
    )
    return {"seeded": True, "agent_id": agent.id, "pack": agent.pack_slug}


async def _seed_welcome_receipt() -> dict[str, object]:
    """One ``system.bootstrap`` receipt on first ever boot."""
    from backend.core.receipts import get_store as _r_get

    store = _r_get()
    if store is None:
        return {"seeded": False, "reason": "receipts_disabled"}
    # Only seed when ledger is completely empty.
    last = await store.last_receipt() if hasattr(store, "last_receipt") else None
    if last is not None:
        return {"seeded": False, "reason": "already_exists"}
    rec = await store.append(
        type="system.bootstrap",
        actor="tars",
        resource="storage.bootstrap",
        payload={
            "wave": "W231",
            "note": "first-boot welcome receipt",
            "ts": int(time.time()),
        },
    )
    return {"seeded": True, "receipt_id": rec.id}


# ---- entrypoint -------------------------------------------------------------


async def init_all_databases() -> BootstrapResult:
    """Boot-time DB init + minimum seed. Idempotent + never raises.

    Called from the FastAPI lifespan. Safe to call directly from a
    REPL or a one-shot script.
    """

    t0 = time.time()
    result = BootstrapResult()

    # Step 0 — directory + permissions
    out = _safe("tars_dir", _init_dir, result)
    result.tars_dir = str(out) if out else str(DEFAULT_TARS_DIR)

    # Step 1 — every SQLite-backed store gets touched so the schema
    # is materialised (each constructor handles CREATE IF NOT EXISTS).
    for label, runner in (
        ("agents_store", _init_agents),
        ("meeet_store", _init_meeet),
        ("chat_store", _init_chat),
        ("memory_store", _init_memory),
        ("policy_store", _init_policy),
        ("scheduler_store", _init_scheduler),
        ("workspaces_store", _init_workspaces),
        ("webhooks_store", _init_webhooks),
        ("receipts_store", _init_receipts),
        ("entitlements_store", _init_entitlements),
    ):
        _safe(label, runner, result)

    # Step 2 — seed minimum rows. These are async because the stores
    # they touch are async-first.
    try:
        seeded_agent = await _seed_default_agent()
        result.seeded["agent"] = seeded_agent
        _stderr(f"seed: agent: {seeded_agent}")
    except Exception as exc:
        result.steps_warn.append(("seed_default_agent", str(exc)[:240]))
        _stderr(f"warn: seed_default_agent: {exc}")

    try:
        seeded_receipt = await _seed_welcome_receipt()
        result.seeded["receipt"] = seeded_receipt
        _stderr(f"seed: receipt: {seeded_receipt}")
    except Exception as exc:
        result.steps_warn.append(("seed_welcome_receipt", str(exc)[:240]))
        _stderr(f"warn: seed_welcome_receipt: {exc}")

    # Step 3 — default domain pack is already auto-registered via
    # ``backend.core.domains.packs`` import-side-effects in app.py;
    # no separate seed needed. Just record what's known.
    try:
        from backend.core.domains.registry import all_packs

        packs = sorted(p.manifest.slug for p in all_packs())
        result.seeded["packs"] = packs
        _stderr(f"packs registered: {len(packs)}: {packs[:6]}")
    except Exception as exc:
        result.steps_warn.append(("registered_packs", str(exc)[:240]))

    result.elapsed_ms = int((time.time() - t0) * 1000)
    _stderr(
        f"done: ok={len(result.steps_ok)} warn={len(result.steps_warn)} "
        f"elapsed_ms={result.elapsed_ms}"
    )
    return result
