"""W253 — HTTP surface for the voice-driven Composer.

Endpoints
---------

- ``POST   /api/composer/plan``                 -> ComposerPlan JSON
- ``GET    /api/composer/plans``                -> recent plans (max 100)
- ``GET    /api/composer/plans/{plan_id}``      -> single plan + diffs
- ``POST   /api/composer/plans/{plan_id}/approve``  -> apply_plan
- ``POST   /api/composer/plans/{plan_id}/reject``   -> mark rejected
- ``POST   /api/composer/plans/{plan_id}/rollback`` -> restore from backup
- ``GET    /api/composer/plans/{plan_id}/diff/{op_index}``
                                                 -> raw unified diff text
- ``GET    /api/composer/config``                -> project_root config
- ``POST   /api/composer/config``                -> persist project_root

W256 endpoints — domain-pack-aware composer:

- ``GET    /api/composer/pack-info``             -> active pack + vocab + hints
- ``POST   /api/composer/switch-pack``           -> body {pack: str}

The project root resolves with this precedence:

1. ``project_root`` field in the request body.
2. ``~/.tars/composer_config.json`` ``project_root`` key.
3. ``TARS_COMPOSER_ROOT`` env var.
4. ``~/Documents`` (default).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import PlainTextResponse

from backend.core.composer import (
    KNOWN_PACKS,
    SafetyError,
    apply_plan as _apply_plan,
    get_pack_info as _get_pack_info,
    get_store as _get_store,
    plan_from_transcript,
    rollback as _rollback,
    set_active_pack as _set_active_pack,
)


router = APIRouter(prefix="/api/composer", tags=["composer"])


# ---------------------------------------------------------------------------
# Project-root config
# ---------------------------------------------------------------------------


def _config_path() -> Path:
    raw = os.environ.get("TARS_COMPOSER_CONFIG") or "~/.tars/composer_config.json"
    return Path(os.path.expanduser(raw))


def _read_config() -> dict[str, Any]:
    p = _config_path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_config(cfg: dict[str, Any]) -> None:
    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _resolve_root(explicit: str | None) -> Path:
    if explicit:
        return Path(os.path.expanduser(explicit)).resolve()
    cfg = _read_config()
    if cfg.get("project_root"):
        return Path(os.path.expanduser(str(cfg["project_root"]))).resolve()
    env_root = os.environ.get("TARS_COMPOSER_ROOT")
    if env_root:
        return Path(os.path.expanduser(env_root)).resolve()
    return Path(os.path.expanduser("~/Documents")).resolve()


# ---------------------------------------------------------------------------
# /plan
# ---------------------------------------------------------------------------


@router.post("/plan")
async def post_plan(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Plan from a transcript. Body: ``{transcript, project_root?}``."""

    body = payload or {}
    transcript = str(body.get("transcript") or "").strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="transcript required")
    root = _resolve_root(body.get("project_root"))
    if not root.exists():
        raise HTTPException(
            status_code=400,
            detail=f"project_root not found: {root}",
        )

    try:
        plan = await asyncio.to_thread(
            plan_from_transcript, transcript, root
        )
    except SafetyError as exc:
        return {
            "ok": False,
            "error": "safety_violation",
            "reason": exc.reason,
            "op_index": exc.op_index,
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"planner failed: {exc}")

    store = _get_store()
    if store is not None:
        try:
            await asyncio.to_thread(store.save_plan, plan)
        except Exception:  # noqa: BLE001
            pass

    # Receipt for the plan itself — so even rejected plans leave a trace.
    try:
        from backend.core.receipts.store import get_store as _rstore  # noqa: PLC0415

        rs = _rstore()
        if rs is not None:
            await rs.append(
                "composer.plan.drafted",
                "composer",
                plan.plan_id,
                {
                    "ops": len(plan.ops),
                    "summary": plan.intent_summary,
                    "transcript_chars": len(plan.transcript),
                },
            )
    except Exception:  # noqa: BLE001
        pass

    return {"ok": True, "plan": plan.to_dict()}


# ---------------------------------------------------------------------------
# /plans (list + get)
# ---------------------------------------------------------------------------


@router.get("/plans")
async def list_plans(limit: int = 20) -> dict[str, Any]:
    limit = max(1, min(int(limit), 100))
    store = _get_store()
    if store is None:
        return {"ok": True, "plans": []}
    plans = await asyncio.to_thread(store.list_plans, limit=limit)
    return {"ok": True, "plans": [p.to_dict() for p in plans]}


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: str) -> dict[str, Any]:
    store = _get_store()
    if store is None:
        raise HTTPException(status_code=503, detail="composer store disabled")
    plan = await asyncio.to_thread(store.load_plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan not found")
    applied = await asyncio.to_thread(store.get_applied, plan_id)
    return {"ok": True, "plan": plan.to_dict(), "applied": applied}


# ---------------------------------------------------------------------------
# /plans/{id}/approve|reject|rollback
# ---------------------------------------------------------------------------


@router.post("/plans/{plan_id}/approve")
async def approve_plan(plan_id: str) -> dict[str, Any]:
    store = _get_store()
    if store is None:
        raise HTTPException(status_code=503, detail="composer store disabled")
    plan = await asyncio.to_thread(store.load_plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan not found")
    if plan.state not in ("draft", "approved"):
        raise HTTPException(
            status_code=409,
            detail=f"plan in state {plan.state!r}; cannot approve",
        )
    plan.state = "approved"
    await asyncio.to_thread(store.save_plan, plan)
    result = await asyncio.to_thread(_apply_plan, plan)
    # Receipt for the approval itself happens inside the executor.
    return {"ok": result.ok, "result": result.to_dict()}


@router.post("/plans/{plan_id}/reject")
async def reject_plan(plan_id: str) -> dict[str, Any]:
    store = _get_store()
    if store is None:
        raise HTTPException(status_code=503, detail="composer store disabled")
    plan = await asyncio.to_thread(store.load_plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan not found")
    if plan.state == "applied":
        raise HTTPException(
            status_code=409,
            detail="plan already applied; use /rollback instead",
        )
    plan.state = "rejected"
    await asyncio.to_thread(store.save_plan, plan)
    try:
        from backend.core.receipts.store import get_store as _rstore  # noqa: PLC0415

        rs = _rstore()
        if rs is not None:
            await rs.append(
                "composer.plan.rejected",
                "composer",
                plan_id,
                {"ops": len(plan.ops), "summary": plan.intent_summary},
            )
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "state": "rejected"}


@router.post("/plans/{plan_id}/rollback")
async def rollback_plan(plan_id: str) -> dict[str, Any]:
    ok = await asyncio.to_thread(_rollback, plan_id)
    if not ok:
        return {"ok": False, "error": "rollback_failed"}
    store = _get_store()
    if store is not None:
        await asyncio.to_thread(store.mark_rolled_back, plan_id)
    return {"ok": True, "state": "rolled_back"}


# ---------------------------------------------------------------------------
# /plans/{id}/diff/{op_index}
# ---------------------------------------------------------------------------


@router.get("/plans/{plan_id}/diff/{op_index}", response_class=PlainTextResponse)
async def get_diff(plan_id: str, op_index: int) -> str:
    store = _get_store()
    if store is None:
        raise HTTPException(status_code=503, detail="composer store disabled")
    plan = await asyncio.to_thread(store.load_plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan not found")
    if op_index < 0 or op_index >= len(plan.ops):
        raise HTTPException(status_code=404, detail="op_index out of range")
    return plan.ops[op_index].diff_unified or ""


# ---------------------------------------------------------------------------
# /config — project root settings
# ---------------------------------------------------------------------------


@router.get("/config")
async def get_config() -> dict[str, Any]:
    cfg = _read_config()
    return {
        "ok": True,
        "project_root": cfg.get("project_root")
        or os.environ.get("TARS_COMPOSER_ROOT")
        or os.path.expanduser("~/Documents"),
        "persisted": bool(cfg),
    }


@router.post("/config")
async def post_config(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    body = payload or {}
    root = str(body.get("project_root") or "").strip()
    if not root:
        raise HTTPException(status_code=400, detail="project_root required")
    expanded = Path(os.path.expanduser(root))
    if not expanded.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"not a directory: {expanded}",
        )
    cfg = _read_config()
    cfg["project_root"] = str(expanded)
    _write_config(cfg)
    return {"ok": True, "project_root": str(expanded)}


# ---------------------------------------------------------------------------
# W256 — pack-aware composer
# ---------------------------------------------------------------------------


@router.get("/pack-info")
async def get_pack_info_endpoint() -> dict[str, Any]:
    """Return current active pack + action vocabulary + file hints.

    Falls back to ``web_search`` when no pack has been selected. The
    payload mirrors the structure consumed by the Composer panel
    chip + pack-switcher modal.
    """

    info = await asyncio.to_thread(_get_pack_info)
    return {"ok": True, **info}


@router.post("/switch-pack")
async def switch_pack_endpoint(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    """Switch composer session to a different pack.

    Body: ``{pack: str}``. Persists to ``~/.tars/active_pack.json``.
    Returns the full pack-info payload of the *new* active pack.
    """

    body = payload or {}
    pack = str(body.get("pack") or "").strip()
    if not pack:
        raise HTTPException(status_code=400, detail="pack required")
    if pack not in KNOWN_PACKS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"unknown pack {pack!r}; expected one of "
                f"{sorted(KNOWN_PACKS)}"
            ),
        )
    try:
        await asyncio.to_thread(_set_active_pack, pack)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    info = await asyncio.to_thread(_get_pack_info)
    # Receipt so we have a trace of pack switches in the audit feed.
    try:
        from backend.core.receipts.store import get_store as _rstore  # noqa: PLC0415

        rs = _rstore()
        if rs is not None:
            await rs.append(
                "composer.pack.switched",
                "composer",
                pack,
                {"pack": pack},
            )
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, **info}


# ---------------------------------------------------------------------------
# W262 -- Voice-first pair programming (continuous voice session in Composer).
#
# Two endpoints power the cockpit "Pair mode" toggle:
#
# 1. POST /api/composer/plans/{plan_id}/refine
#    body {additional_transcript: str}
#    -> re-runs plan_from_transcript with the accumulated transcript
#       (original + new utterance) and returns the updated ops. Used
#       every time the operator says something while pair mode is on.
#
# 2. POST /api/composer/voice-approve
#    body {utterance: str}
#    -> classifies the utterance into APPROVE / REJECT / UNCLEAR using
#       a small phrase whitelist. The FE wires this to the Approve /
#       Reject buttons when pair mode is on so the operator never has
#       to touch the keyboard.
#
# Both endpoints are intentionally lean -- the heavy lifting (LLM
# planner, safety fence) is already in backend.core.composer; we only
# add the conversational glue here.
# ---------------------------------------------------------------------------


# Phrase whitelist for voice intent recognition.  Lowercase, trimmed.
# Order matters: a longer match wins (we check substring containment).
_VOICE_APPROVE_PHRASES: tuple[str, ...] = (
    "approve",
    "apply",
    "ship it",
    "looks good",
    "lgtm",
    "do it",
    "go ahead",
    "yes apply",
    "yes go",
    "make it so",
    "send it",
)
_VOICE_REJECT_PHRASES: tuple[str, ...] = (
    "reject",
    "cancel",
    "no don't",
    "do not",
    "stop",
    "abort",
    "scrap it",
    "throw it out",
    "discard",
    "never mind",
    "nevermind",
)


def _classify_voice_intent(utterance: str) -> tuple[str, str]:
    """Return ``(intent, matched_phrase)``.

    Intent is one of ``approve`` / ``reject`` / ``unclear``. The
    matched phrase is the longest whitelist entry contained in the
    (lower-cased) utterance, or ``""`` when no entry matched.
    """

    text = (utterance or "").strip().lower()
    if not text:
        return "unclear", ""

    best_intent = "unclear"
    best_phrase = ""
    best_len = 0
    for phrase in _VOICE_APPROVE_PHRASES:
        if phrase in text and len(phrase) > best_len:
            best_intent = "approve"
            best_phrase = phrase
            best_len = len(phrase)
    for phrase in _VOICE_REJECT_PHRASES:
        if phrase in text and len(phrase) > best_len:
            best_intent = "reject"
            best_phrase = phrase
            best_len = len(phrase)
    return best_intent, best_phrase


@router.post("/plans/{plan_id}/refine")
async def refine_plan(
    plan_id: str,
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    """Re-run the planner with appended transcript text.

    Body: ``{additional_transcript: str, project_root?: str}``.

    Loads the existing plan, appends the new utterance to its
    transcript, re-plans, then persists the refined plan **under the
    same plan_id** so the FE doesn't need to rewire UI state. Returns
    the updated plan JSON.
    """

    body = payload or {}
    addition = str(body.get("additional_transcript") or "").strip()
    if not addition:
        raise HTTPException(status_code=400, detail="additional_transcript required")

    store = _get_store()
    if store is None:
        raise HTTPException(status_code=503, detail="composer store disabled")
    existing = await asyncio.to_thread(store.load_plan, plan_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="plan not found")
    if existing.state not in ("draft", "approved"):
        # Refining an already-applied plan would be confusing; force a
        # fresh /plan call instead.
        raise HTTPException(
            status_code=409,
            detail=f"plan in state {existing.state!r}; cannot refine",
        )

    root = _resolve_root(body.get("project_root"))
    if not root.exists():
        raise HTTPException(
            status_code=400,
            detail=f"project_root not found: {root}",
        )

    # Concatenate the accumulated transcript so the planner sees the
    # whole conversational thread, not just the latest utterance.
    combined = (existing.transcript or "").strip()
    if combined:
        combined = combined + "\n" + addition
    else:
        combined = addition

    try:
        refined = await asyncio.to_thread(
            plan_from_transcript, combined, root
        )
    except SafetyError as exc:
        return {
            "ok": False,
            "error": "safety_violation",
            "reason": exc.reason,
            "op_index": exc.op_index,
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"planner failed: {exc}")

    # Overlay the refined ops onto the existing plan_id so the FE
    # keeps showing the same panel instead of swapping context.
    refined.plan_id = existing.plan_id
    refined.state = "draft"
    try:
        await asyncio.to_thread(store.save_plan, refined)
    except Exception:  # noqa: BLE001
        pass

    # Receipt -- so the audit feed shows the conversation, not just
    # the final apply.
    try:
        from backend.core.receipts.store import get_store as _rstore  # noqa: PLC0415

        rs = _rstore()
        if rs is not None:
            await rs.append(
                "composer.plan.refined",
                "composer.pair",
                refined.plan_id,
                {
                    "ops": len(refined.ops),
                    "summary": refined.intent_summary,
                    "additional_chars": len(addition),
                    "total_transcript_chars": len(combined),
                },
            )
    except Exception:  # noqa: BLE001
        pass

    return {
        "ok": True,
        "plan": refined.to_dict(),
        "refined_from": existing.plan_id,
        "addition_chars": len(addition),
    }


@router.post("/voice-approve")
async def voice_approve(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Classify a voice utterance into approve / reject / unclear.

    Body: ``{utterance: str, plan_id?: str}``.

    The FE calls this after every Pair-mode utterance whose plain-text
    classification reveals an approval intent. Returns the recognised
    intent and the phrase that matched; the FE then triggers the
    corresponding Approve / Reject endpoint on its own so the user
    journey stays auditable.
    """

    body = payload or {}
    utter = str(body.get("utterance") or "").strip()
    plan_id = str(body.get("plan_id") or "").strip() or None
    if not utter:
        raise HTTPException(status_code=400, detail="utterance required")

    intent, matched = _classify_voice_intent(utter)

    # Receipt -- voice intents are a load-bearing audit trail.
    try:
        from backend.core.receipts.store import get_store as _rstore  # noqa: PLC0415

        rs = _rstore()
        if rs is not None:
            await rs.append(
                "composer.voice.intent",
                "composer.pair",
                plan_id or "(no-plan)",
                {
                    "intent": intent,
                    "matched_phrase": matched,
                    "utterance_chars": len(utter),
                },
            )
    except Exception:  # noqa: BLE001
        pass

    return {
        "ok": True,
        "intent": intent,
        "matched_phrase": matched,
        "plan_id": plan_id,
    }
