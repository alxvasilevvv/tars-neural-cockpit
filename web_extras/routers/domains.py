"""Domain packs HTTP router.

Mount with ``app.include_router(domains.router)`` after importing
``backend.core.domains.packs`` once so the registry is populated.

Endpoints:

- ``GET /api/domains`` — list all packs
- ``GET /api/domains/{slug}`` — describe one pack
- ``POST /api/domains/{slug}/actions/{action_id}`` — invoke an action
- ``GET /api/domains/{slug}/awareness`` — list awareness sources
- ``GET /api/domains/{slug}/prompt`` — return the system prompt

Every action invocation runs inside a meeet trace scope so the same
``trace_id`` flows through TARS and into the meeet.world ingest.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Header, HTTPException

from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from backend.core.domains.registry import all_packs, get_pack
from backend.core.meeet import get_client, trace_scope

router = APIRouter(prefix="/api/domains", tags=["domains"])


@router.get("")
async def list_domains() -> dict[str, Any]:
    return {"domains": [p.to_dict() for p in all_packs()]}


@router.get("/{slug}")
async def describe_domain(slug: str) -> dict[str, Any]:
    pack = get_pack(slug)
    if pack is None:
        raise HTTPException(status_code=404, detail="domain_not_found")
    return pack.to_dict()


@router.get("/{slug}/awareness")
async def list_awareness(slug: str) -> dict[str, Any]:
    pack = get_pack(slug)
    if pack is None:
        raise HTTPException(status_code=404, detail="domain_not_found")
    return {
        "slug": slug,
        "awareness": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "kind": s.kind,
                "config": dict(s.config),
                "live": s.fetcher is not None,
            }
            for s in pack.awareness()
        ],
    }


@router.get("/{slug}/awareness/{source_id}/snapshot")
async def awareness_snapshot(
    slug: str,
    source_id: str,
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    pack = get_pack(slug)
    if pack is None:
        raise HTTPException(status_code=404, detail="domain_not_found")
    source = pack.find_awareness(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="awareness_not_found")
    if source.fetcher is None:
        return {
            "ok": False,
            "slug": slug,
            "source_id": source_id,
            "kind": source.kind,
            "error": "fetcher_unavailable",
            "hint": (
                "this source is config-only (likely a webhook receiver); "
                "no live snapshot is implemented yet"
            ),
        }

    client = get_client()
    started_at = time.perf_counter()
    with trace_scope(parent=x_meeet_trace_id) as trace_id:
        await client.emit(
            "awareness.snapshot.requested",
            {"slug": slug, "source_id": source_id, "kind": source.kind},
        )
        try:
            data = await source.fetcher(dict(source.config))
        except Exception as exc:
            await client.emit(
                "awareness.snapshot.failed",
                {
                    "slug": slug,
                    "source_id": source_id,
                    "error": str(exc),
                    "took_ms": _ms_since(started_at),
                },
            )
            raise HTTPException(
                status_code=500,
                detail=f"awareness_failed: {exc}",
            ) from exc

        took_ms = _ms_since(started_at)
        await client.emit(
            "awareness.snapshot.completed",
            {
                "slug": slug,
                "source_id": source_id,
                "took_ms": took_ms,
                "ok": bool(data.get("ok", True)) if isinstance(data, dict) else True,
            },
        )
        return {
            "ok": True,
            "slug": slug,
            "source_id": source_id,
            "kind": source.kind,
            "trace_id": trace_id,
            "took_ms": took_ms,
            "data": data,
        }


@router.get("/{slug}/prompt")
async def get_prompt(slug: str) -> dict[str, Any]:
    pack = get_pack(slug)
    if pack is None:
        raise HTTPException(status_code=404, detail="domain_not_found")
    return {"slug": slug, "system_prompt": pack.system_prompt()}


@router.post("/{slug}/actions/{action_id}")
async def invoke_action(
    slug: str,
    action_id: str,
    payload: dict[str, Any] | None = None,
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    pack = get_pack(slug)
    if pack is None:
        raise HTTPException(status_code=404, detail="domain_not_found")
    spec = pack.find_action(action_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="action_not_found")
    args = payload or {}

    client = get_client()
    started_at = time.perf_counter()
    with trace_scope(parent=x_meeet_trace_id) as trace_id:
        await client.emit(
            "domain.action.invoked",
            {"slug": slug, "action": action_id, "args": _safe_args(args)},
        )
        try:
            result = await spec.handler(args)
        except Exception as exc:  # surface as 500, never crash the app
            await client.emit(
                "domain.action.failed",
                {
                    "slug": slug,
                    "action": action_id,
                    "error": str(exc),
                    "took_ms": _ms_since(started_at),
                },
            )
            raise HTTPException(status_code=500, detail=f"action_failed: {exc}") from exc

        took_ms = _ms_since(started_at)
        await client.emit(
            "domain.action.completed",
            {
                "slug": slug,
                "action": action_id,
                "took_ms": took_ms,
                "result_kind": type(result).__name__,
            },
        )
        return {
            "ok": True,
            "slug": slug,
            "action": action_id,
            "trace_id": trace_id,
            "took_ms": took_ms,
            "result": result,
        }


def _ms_since(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000.0, 3)


def _safe_args(args: dict[str, Any]) -> dict[str, Any]:
    """Strip obvious secrets and oversized blobs before logging.

    Keys containing 'token', 'secret', 'key', 'password' get redacted; any
    string value over 1024 chars is truncated. Nested dicts are walked
    one level deep — domain action args are flat by convention.
    """

    redacted: dict[str, Any] = {}
    for k, v in args.items():
        lower = k.lower()
        if any(needle in lower for needle in ("token", "secret", "key", "password")):
            redacted[k] = "***"
            continue
        if isinstance(v, str) and len(v) > 1024:
            redacted[k] = v[:1021] + "..."
            continue
        redacted[k] = v
    return redacted
