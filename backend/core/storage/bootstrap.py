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


# ---- W270 demo-seed (presentation mode) -------------------------------------


_DEMO_AGENTS = (
    {
        "name": "Briefing assistant",
        "pack_slug": "web_search",
        "description": (
            "Drafts a 3-bullet daily briefing from your calendar, "
            "inbox, and pinned receipts."
        ),
        "system_prompt": (
            "You are TARS in briefing mode. Be concise. Three "
            "bullets. Cite source per bullet."
        ),
    },
    {
        "name": "Email drafter",
        "pack_slug": "web_search",
        "description": (
            "Drafts replies in the operator's tone using AI Clone "
            "style fingerprint."
        ),
        "system_prompt": (
            "You are TARS in email-drafter mode. Match the user's "
            "tone. Keep replies under 80 words unless told otherwise."
        ),
    },
    {
        "name": "Code reviewer",
        "pack_slug": "web_search",
        "description": (
            "Reviews proposed composer plans before apply. Flags "
            "secrets, dead code, and broken contracts."
        ),
        "system_prompt": (
            "You are TARS in code-review mode. Be terse. One line "
            "per finding. Surface only the top 5 issues."
        ),
    },
)


_DEMO_RECEIPTS = (
    {
        "type": "auth.magic_link",
        "actor": "meeet.world",
        "resource": "auth.exchange",
        "payload": {"account": "demo@meeet.world", "method": "magic_link"},
    },
    {
        "type": "chat.message",
        "actor": "tars",
        "resource": "chat.thread.demo-briefing",
        "payload": {"role": "assistant", "tokens_out": 142, "model": "claude-3-opus"},
    },
    {
        "type": "composer.plan.applied",
        "actor": "tars",
        "resource": "composer.plan.demo-001",
        "payload": {
            "files_changed": 2,
            "lines_added": 14,
            "lines_removed": 3,
            "pack": "code",
        },
    },
    {
        "type": "audit.verify",
        "actor": "tars",
        "resource": "audit.receipt.chain",
        "payload": {"verified": 1, "anchor": "solana:devnet:demo-tx"},
    },
    {
        "type": "usage.tokens",
        "actor": "tars",
        "resource": "usage.tokens.demo",
        "payload": {"model": "claude-3-opus", "in": 1820, "out": 412, "cost_usd": 0.052},
    },
)


_DEMO_COMPOSER_PLAN = {
    "plan_id": "demo-plan-001",
    "transcript": "Add a /healthz endpoint to the FastAPI app.",
    "intent_summary": "Add a tiny /healthz route returning 200 OK + uptime.",
    "model": "claude-3-opus",
    "active_pack": "code",
}


async def _demo_seed_agents() -> dict[str, object]:
    """Seed 3 demo agents when ``TARS_DEMO_SEED=1`` is set.

    Skips silently when the env var is unset, when the store is
    disabled, or when any of the demo names already exist.
    """

    if os.getenv("TARS_DEMO_SEED") != "1":
        return {"seeded": False, "reason": "demo_flag_not_set"}

    from backend.core.agents import get_agent_store

    store = get_agent_store()
    if not store.enabled:
        return {"seeded": False, "reason": "agents_store_disabled"}

    existing = await store.list_agents(include_archived=True)
    existing_names = {(a.name or "").strip() for a in existing}

    created: list[str] = []
    for spec in _DEMO_AGENTS:
        if spec["name"] in existing_names:
            continue
        try:
            agent = await store.create_agent(
                name=spec["name"],
                pack_slug=spec["pack_slug"],
                description=spec["description"],
                system_prompt=spec["system_prompt"],
                metadata={"source": "demo_seed", "wave": "W270"},
            )
            created.append(agent.id)
        except Exception as exc:  # pragma: no cover
            _stderr(f"warn: demo_agent {spec['name']}: {exc}")
    return {"seeded": bool(created), "ids": created, "count": len(created)}


async def _demo_seed_receipts() -> dict[str, object]:
    """Seed 5 demo receipts spanning all major surfaces."""

    if os.getenv("TARS_DEMO_SEED") != "1":
        return {"seeded": False, "reason": "demo_flag_not_set"}

    from backend.core.receipts import get_store as _r_get

    store = _r_get()
    if store is None:
        return {"seeded": False, "reason": "receipts_disabled"}

    # Idempotency — query for any prior W270 demo receipt; bail if found.
    if hasattr(store, "query"):
        try:
            prior = await store.query(type="audit.verify", actor="tars", limit=5)
            for rec in prior or []:
                payload = getattr(rec, "payload", None) or {}
                if isinstance(payload, dict) and payload.get("wave") == "W270":
                    return {"seeded": False, "reason": "already_exists"}
        except Exception:
            pass

    created: list[str] = []
    for spec in _DEMO_RECEIPTS:
        try:
            rec = await store.append(
                type=spec["type"],
                actor=spec["actor"],
                resource=spec["resource"],
                payload={**spec["payload"], "demo": True, "wave": "W270"},
            )
            created.append(rec.id)
        except Exception as exc:  # pragma: no cover
            _stderr(f"warn: demo_receipt {spec['type']}: {exc}")
    return {"seeded": bool(created), "count": len(created)}


def _demo_seed_composer() -> dict[str, object]:
    """Seed one drafted (not-applied) composer plan."""

    if os.getenv("TARS_DEMO_SEED") != "1":
        return {"seeded": False, "reason": "demo_flag_not_set"}

    try:
        from backend.core.composer.storage import get_store as _c_get
        from backend.core.composer.types import ComposerPlan, EditOp
    except Exception as exc:
        return {"seeded": False, "reason": f"composer_import_failed: {exc}"}

    store = _c_get()
    if store is None:
        return {"seeded": False, "reason": "composer_disabled"}

    # Idempotency — bail if the demo plan already exists.
    existing = store.load_plan(_DEMO_COMPOSER_PLAN["plan_id"])
    if existing is not None:
        return {"seeded": False, "reason": "already_exists"}

    plan = ComposerPlan(
        plan_id=_DEMO_COMPOSER_PLAN["plan_id"],
        transcript=_DEMO_COMPOSER_PLAN["transcript"],
        intent_summary=_DEMO_COMPOSER_PLAN["intent_summary"],
        model=_DEMO_COMPOSER_PLAN["model"],
        active_pack=_DEMO_COMPOSER_PLAN["active_pack"],
        state="draft",
        estimated_tokens=480,
        estimated_cost_usd=0.012,
        ops=[
            EditOp(
                op="modify",
                path="backend/web_extras/app.py",
                old_content="# app routes",
                new_content=(
                    "# app routes\n\n"
                    "@app.get('/healthz')\n"
                    "def healthz():\n"
                    "    return {'ok': True, 'uptime_s': int(time.time() - BOOT_TS)}\n"
                ),
                diff_unified=(
                    "--- a/backend/web_extras/app.py\n"
                    "+++ b/backend/web_extras/app.py\n"
                    "@@\n"
                    " # app routes\n"
                    "+\n"
                    "+@app.get('/healthz')\n"
                    "+def healthz():\n"
                    "+    return {'ok': True, 'uptime_s': int(time.time() - BOOT_TS)}\n"
                ),
            ),
        ],
    )
    try:
        store.save_plan(plan)
    except Exception as exc:  # pragma: no cover
        return {"seeded": False, "reason": f"save_failed: {exc}"}
    return {"seeded": True, "plan_id": plan.plan_id, "state": "draft"}


def _demo_seed_mcp_server() -> dict[str, object]:
    """Seed the W150 reference MCP server entry in the panel registry."""

    if os.getenv("TARS_DEMO_SEED") != "1":
        return {"seeded": False, "reason": "demo_flag_not_set"}

    try:
        from web_extras.routers.mcp_panel import (
            _config_path,
            _read_servers,
            _write_servers,
        )
    except Exception as exc:
        return {"seeded": False, "reason": f"mcp_panel_import_failed: {exc}"}

    rows = _read_servers()
    existing_names = {r.get("name") for r in rows}
    demo_name = "tars-native-skills (W150)"
    if demo_name in existing_names:
        return {"seeded": False, "reason": "already_exists"}

    import time as _time
    import uuid as _uuid

    rows.append(
        {
            "id": str(_uuid.uuid4()),
            "name": demo_name,
            "command": "python",
            "args": ["-m", "backend.core.mcp"],
            "env": {},
            "enabled": True,
            "status": "enabled",
            "last_seen": int(_time.time()),
            "error": None,
            "created_at": int(_time.time()),
        }
    )
    try:
        _write_servers(rows)
    except Exception as exc:  # pragma: no cover
        return {"seeded": False, "reason": f"write_failed: {exc}"}
    return {"seeded": True, "name": demo_name, "config_path": str(_config_path())}



def _demo_seed_conversations() -> dict[str, object]:
    """W274 — Seed 3 demo conversation sessions for the memory tab demo."""

    if os.getenv("TARS_DEMO_SEED") != "1":
        return {"seeded": False, "reason": "demo_flag_not_set"}

    try:
        from backend.core.memory.conversation import (
            ConversationTurn,
            get_conversation_memory,
        )
    except Exception as exc:  # pragma: no cover
        return {"seeded": False, "reason": f"import_failed: {exc}"}

    mem = get_conversation_memory()
    existing = {row["id"] for row in mem.list_sessions(limit=200)}

    demo: list[tuple[str, str, list[tuple[str, str]]]] = [
        (
            "demo_session_q3",
            "Q3 outreach planning",
            [
                ("user", "Plan our Q3 outreach to the top 50 funds — what's the right cadence?"),
                ("tars", "I'd open with a 3-touch sequence: warm intro, value drop, ask. Roughly day 0 / +5 / +12. Want me to draft the first email in your voice?"),
                ("user", "Yes — keep it under 90 words, friendly but professional."),
                ("tars", "Draft attached to the Outreach inbox. 84 words, opens with their recent portfolio move, closes with a Tuesday/Thursday slot ask."),
                ("user", "Great. Schedule the follow-ups."),
                ("tars", "Scheduled. Sequence will pause if anyone replies."),
            ],
        ),
        (
            "demo_session_health",
            "Health check-up prep",
            [
                ("user", "I have a physical next Monday. What should I prep?"),
                ("tars", "Fast 8 hours before bloodwork, bring your medication list, and bring questions for your doctor. Want me to compile your last six months of sleep + activity data?"),
                ("user", "Yes, summarize sleep + steps + any meds I refilled."),
                ("tars", "Done — one-page summary in your Documents. Average 7h12m sleep, 8,400 steps/day, two refills (Vitamin D, magnesium)."),
                ("user", "Send a copy to my doctor."),
                ("tars", "Sent via secure email. Receipt logged."),
            ],
        ),
        (
            "demo_session_code",
            "Code review session",
            [
                ("user", "Walk me through the new payment retry logic."),
                ("tars", "The retry uses exponential backoff capped at 5 attempts, with idempotency keys on every charge. Tests cover the timeout + duplicate-key paths. Want a diff summary?"),
                ("user", "Yes, focus on edge cases."),
                ("tars", "Edge cases: network-flap mid-charge, duplicate webhook delivery, partial refund race. All three have explicit tests. Coverage 94% on the retry module."),
                ("user", "Approve it."),
                ("tars", "Approved. Plan ID composer_pay_retry_v3 applied. Receipt anchored."),
            ],
        ),
    ]

    seeded = 0
    base = time.time() - 86_400 * 2  # two days ago, three sessions over recent days
    for idx, (sid, label, turns) in enumerate(demo):
        if sid in existing:
            continue
        mem.ensure_session(sid, label=label)
        ts0 = base + idx * 18_000  # spread sessions 5h apart
        for t_idx, (role, text) in enumerate(turns):
            mem.add_turn(ConversationTurn(
                id=f"{sid}_t{t_idx}",
                session_id=sid,
                role=role,
                text=text,
                ts_utc=ts0 + t_idx * 45.0,
            ))
        seeded += 1

    return {"seeded": bool(seeded), "count": seeded}


def _demo_seed_notepads() -> dict[str, object]:
    """W273 — seed the 5 stock notepad templates so the cockpit list is
    non-empty for the demo. Gated by TARS_DEMO_SEED=1 but the underlying
    ``seed_defaults`` is itself idempotent (only fills if DB is empty),
    so this is also safe to call when the flag is off.
    """

    if os.getenv("TARS_DEMO_SEED") != "1":
        return {"seeded": False, "reason": "demo_flag_not_set"}

    try:
        from backend.core.notepads import get_store as _np_get
    except Exception as exc:
        return {"seeded": False, "reason": f"notepads_import_failed: {exc}"}

    store = _np_get()
    if store is None:
        return {"seeded": False, "reason": "notepads_disabled"}

    try:
        created = store.seed_defaults()
    except Exception as exc:  # pragma: no cover
        return {"seeded": False, "reason": f"seed_failed: {exc}"}
    return {"seeded": bool(created), "count": len(created)}


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

    # W270 — demo-seed pack (presentation mode, gated by TARS_DEMO_SEED=1).
    try:
        result.seeded["demo_agents"] = await _demo_seed_agents()
        _stderr(f"seed: demo_agents: {result.seeded['demo_agents']}")
    except Exception as exc:
        result.steps_warn.append(("demo_seed_agents", str(exc)[:240]))
        _stderr(f"warn: demo_seed_agents: {exc}")

    try:
        result.seeded["demo_receipts"] = await _demo_seed_receipts()
        _stderr(f"seed: demo_receipts: {result.seeded['demo_receipts']}")
    except Exception as exc:
        result.steps_warn.append(("demo_seed_receipts", str(exc)[:240]))
        _stderr(f"warn: demo_seed_receipts: {exc}")

    try:
        result.seeded["demo_composer"] = _demo_seed_composer()
        _stderr(f"seed: demo_composer: {result.seeded['demo_composer']}")
    except Exception as exc:
        result.steps_warn.append(("demo_seed_composer", str(exc)[:240]))
        _stderr(f"warn: demo_seed_composer: {exc}")

    try:
        result.seeded["demo_mcp"] = _demo_seed_mcp_server()
        _stderr(f"seed: demo_mcp: {result.seeded['demo_mcp']}")
    except Exception as exc:
        result.steps_warn.append(("demo_seed_mcp", str(exc)[:240]))
        _stderr(f"warn: demo_seed_mcp: {exc}")

    # W274 — seed 3 demo conversations for the Memory tab demo
    try:
        result.seeded["demo_conversations"] = _demo_seed_conversations()
        _stderr(f"seed: demo_conversations: {result.seeded['demo_conversations']}")
    except Exception as exc:
        result.steps_warn.append(("demo_seed_conversations", str(exc)[:240]))
        _stderr(f"warn: demo_seed_conversations: {exc}")

    # W273 — seed notepad templates so the Notepads tab is non-empty for the demo
    try:
        result.seeded["demo_notepads"] = _demo_seed_notepads()
        _stderr(f"seed: demo_notepads: {result.seeded['demo_notepads']}")
    except Exception as exc:
        result.steps_warn.append(("demo_seed_notepads", str(exc)[:240]))
        _stderr(f"warn: demo_seed_notepads: {exc}")

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
