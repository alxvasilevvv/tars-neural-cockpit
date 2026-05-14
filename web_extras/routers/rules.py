"""W239 - HTTP surface for the Rules-for-TARS module.

Endpoints
---------

- ``GET    /api/rules``                  -> global + pack overlay
- ``POST   /api/rules``                  -> replace global rules
- ``PUT    /api/rules/{id}``             -> patch one rule's text/enabled
- ``DELETE /api/rules/{id}``             -> remove from global
- ``POST   /api/rules/preview``          -> inject rules into a sample prompt

Pack-scope rules are read-only from the pack source. ``POST`` rejects
pack-scope entries with 400.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from backend.core.rules import (
    Rule,
    delete_global_rule,
    inject_rules_into_prompt,
    load_global_rules,
    load_pack_rules,
    patch_global_rule,
    save_global_rules,
)


router = APIRouter(prefix="/api/rules", tags=["rules"])


def _active_pack_default() -> str | None:
    """Best-effort: read the currently active pack from the chat store.

    Returns ``None`` if the chat layer isn't ready or no pack is
    pinned. The Settings UI also passes ``active_pack`` explicitly
    via the preview endpoint when needed.
    """

    try:
        from backend.core.chat.store import get_chat_store  # noqa: PLC0415
    except Exception:
        return None
    try:
        store = get_chat_store()
        # Some implementations expose ``active_pack`` directly; fall
        # back to None when not present. We don't await async helpers
        # here - this is a synchronous best-effort.
        pack = getattr(store, "active_pack", None)
        if isinstance(pack, str) and pack.strip():
            return pack.strip()
    except Exception:
        return None
    return None


@router.get("")
async def get_rules(active_pack: str | None = None) -> dict[str, Any]:
    """Return the operator's global rules + read-only pack overlay."""

    pack = active_pack or _active_pack_default()
    g = [r.to_dict() for r in load_global_rules()]
    p = [r.to_dict() for r in load_pack_rules(pack)]
    return {
        "ok": True,
        "global": g,
        "pack_overlay": p,
        "active_pack": pack,
    }


@router.post("")
async def post_rules(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Replace the global rule set (pack-scope rejected)."""

    body = payload or {}
    items = body.get("rules")
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="rules_must_be_list")

    rules: list[Rule] = []
    for item in items:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="rule_must_be_object")
        scope = str(item.get("scope") or "global").strip().lower()
        if scope == "pack":
            raise HTTPException(
                status_code=400,
                detail="pack_scope_read_only",
            )
        text = str(item.get("text") or "").strip()
        if not text:
            # silently drop empty rows from the UI
            continue
        rules.append(
            Rule(
                id=str(item.get("id") or "").strip() or f"rule-{len(rules)+1}",
                text=text,
                enabled=bool(item.get("enabled", True)),
                scope="global",
                pack=None,
            )
        )
    save_global_rules(rules)
    return {
        "ok": True,
        "count": len(rules),
        "global": [r.to_dict() for r in load_global_rules()],
    }


@router.put("/{rule_id}")
async def put_rule(
    rule_id: str,
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    """Patch one rule's ``text`` and/or ``enabled`` flag."""

    body = payload or {}
    text = body.get("text")
    enabled = body.get("enabled")
    if text is None and enabled is None:
        raise HTTPException(status_code=400, detail="nothing_to_patch")
    updated = patch_global_rule(
        rule_id,
        text=str(text) if text is not None else None,
        enabled=bool(enabled) if enabled is not None else None,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="rule_not_found")
    return {"ok": True, "rule": updated.to_dict()}


@router.delete("/{rule_id}")
async def delete_rule(rule_id: str) -> dict[str, Any]:
    """Remove a rule from the global store."""

    ok = delete_global_rule(rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="rule_not_found")
    return {"ok": True, "removed": rule_id}


@router.post("/preview")
async def preview_prompt(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Return the injected system prompt for debugging."""

    body = payload or {}
    base = str(body.get("system_prompt") or "")
    pack = body.get("active_pack")
    if pack is not None:
        pack = str(pack).strip() or None
    else:
        pack = _active_pack_default()
    injected = inject_rules_into_prompt(base, pack)
    return {
        "ok": True,
        "active_pack": pack,
        "system_prompt": base,
        "injected": injected,
    }
