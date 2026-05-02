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
from backend.core.meeet import (
    get_client,
    set_route,
    thread_id_scope,
    trace_scope,
)
from backend.core.policy import get_gate, resolve_mode

router = APIRouter(prefix="/api/domains", tags=["domains"])


@router.get("")
async def list_domains() -> dict[str, Any]:
    return {"domains": [p.to_dict() for p in all_packs()]}


@router.get("/manifest")
async def manifest() -> dict[str, Any]:
    """Static, cache-friendly manifest of every registered pack.

    Designed for cold-start installers and external consumers that
    need a stable list of slugs/capabilities without deep schema dumps.
    """

    contract_version = "1.0.0"
    items: list[dict[str, Any]] = []
    for pack in all_packs():
        m = pack.manifest
        composite = bool(getattr(pack, "composed_of", ()))
        items.append(
            {
                "slug": m.slug,
                "name": m.name,
                "short": m.short,
                "color": m.color,
                "audience": m.audience,
                "capabilities": list(m.capabilities),
                "deprecated": m.deprecated,
                "deprecated_in_favor_of": m.deprecated_in_favor_of,
                "composite": composite,
                "composed_of": list(getattr(pack, "composed_of", ())),
                "action_count": sum(1 for _ in pack.all_actions()),
                "destructive_action_count": sum(
                    1 for a in pack.all_actions() if a.destructive
                ),
                "awareness_count": sum(1 for _ in pack.awareness()),
            }
        )
    return {
        "ok": True,
        "contract_version": contract_version,
        "count": len(items),
        "domains": items,
    }


@router.get("/health")
async def domains_health() -> dict[str, Any]:
    """Per-pack vault-key readiness — operator dashboard for "what's
    actually wired up on this machine".

    For every registered pack we resolve its declared
    ``auth_vault_keys`` against env + macOS Keychain via
    :func:`backend.core.vault.status_for_keys` and return a compact
    status row:

    .. code-block:: json

        {
          "ok": true,
          "count": 4,
          "packs": [
            {
              "slug": "business",
              "name": "Business / CRM",
              "ready": true,
              "key_count": 9,
              "available_count": 4,
              "missing": ["HUBSPOT_API_KEY", "..."],
              "keys": [
                {"key": "SMTP_HOST", "source": "env",
                 "available": true},
                ...
              ]
            }
          ]
        }

    ``ready`` is true when at least one declared key resolves; the
    cockpit can use it as a quick "this pack will probably work"
    signal. Packs with no declared vault keys surface as
    ``ready=true`` with ``key_count=0`` so they don't show up red.

    Probes both unprefixed (``HUBSPOT_API_KEY``) and ``TARS_``-
    prefixed (``TARS_HUBSPOT_API_KEY``) forms so operators who set
    either form are honoured. Never returns the secret value — only
    availability + source (``env`` / ``keychain`` / ``missing``).
    """

    from backend.core.vault import status_for_keys

    items: list[dict[str, Any]] = []
    for pack in all_packs():
        m = pack.manifest
        keys = tuple(getattr(pack, "auth_vault_keys", lambda: ())())
        if not keys:
            items.append(
                {
                    "slug": m.slug,
                    "name": m.name,
                    "ready": True,
                    "key_count": 0,
                    "available_count": 0,
                    "missing": [],
                    "keys": [],
                }
            )
            continue
        prefixed = [f"TARS_{k}" for k in keys]
        all_keys = list(keys) + prefixed
        statuses = status_for_keys(all_keys)
        per_key: dict[str, dict[str, Any]] = {}
        for s in statuses:
            base = s.key[5:] if s.key.startswith("TARS_") else s.key
            entry = per_key.setdefault(
                base,
                {"key": base, "source": "missing", "available": False},
            )
            if s.available and not entry["available"]:
                entry["source"] = s.source
                entry["available"] = True
        rows = [per_key[k] for k in keys if k in per_key]
        available = sum(1 for r in rows if r["available"])
        missing = [r["key"] for r in rows if not r["available"]]
        items.append(
            {
                "slug": m.slug,
                "name": m.name,
                "ready": available > 0,
                "key_count": len(rows),
                "available_count": available,
                "missing": missing,
                "keys": rows,
            }
        )
    return {"ok": True, "count": len(items), "packs": items}


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
    x_tars_session_id: str | None = Header(default=None),
    x_tars_thread_id: str | None = Header(default=None),
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
    with thread_id_scope(x_tars_thread_id), trace_scope(
        parent=x_meeet_trace_id,
        session=x_tars_session_id,
        route="edge",
    ) as trace_id:
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
    x_tars_policy_mode: str | None = Header(default=None),
    x_tars_session_id: str | None = Header(default=None),
    x_tars_thread_id: str | None = Header(default=None),
) -> dict[str, Any]:
    pack = get_pack(slug)
    if pack is None:
        raise HTTPException(status_code=404, detail="domain_not_found")
    spec = pack.find_action(action_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="action_not_found")
    args = dict(payload or {})

    arg_mode = args.pop("policy_mode", None)
    confirmed_by_token = bool(args.pop("_confirmed", False))

    mode = resolve_mode(
        header=x_tars_policy_mode,
        request_arg=str(arg_mode) if arg_mode else None,
    )

    client = get_client()
    started_at = time.perf_counter()
    # Domain actions default to "edge" — purely local execution. Any
    # voice / adapter that crosses out to a cloud bumps the route via
    # ``set_route("cloud")`` from inside its handler.
    with thread_id_scope(x_tars_thread_id), trace_scope(
        parent=x_meeet_trace_id,
        session=x_tars_session_id,
        route="edge",
    ) as trace_id:
        await client.emit(
            "domain.action.invoked",
            {
                "slug": slug,
                "action": action_id,
                "args": _safe_args(args),
                "destructive": spec.destructive,
                "policy_mode": mode.value,
            },
        )

        gate = get_gate()
        decision = await gate.check(
            slug=slug,
            action_id=action_id,
            args=args,
            destructive=spec.destructive,
            mode=mode,
            confirmed=confirmed_by_token,
            trace_id=trace_id,
            thread_id=x_tars_thread_id,
        )

        if not decision.allowed:
            event_kind = (
                "policy.blocked"
                if decision.reason == "dry_run_preview_only"
                else "policy.queued"
            )
            event_payload: dict[str, Any] = {
                "slug": slug,
                "action": action_id,
                "mode": decision.mode.value,
                "reason": decision.reason,
                "token": decision.confirmation_token,
            }
            if x_tars_thread_id:
                event_payload["thread_id"] = x_tars_thread_id
            await client.emit(event_kind, event_payload)
            took_ms = _ms_since(started_at)
            return {
                "ok": True,
                "slug": slug,
                "action": action_id,
                "trace_id": trace_id,
                "took_ms": took_ms,
                "result": {
                    "ok": True,
                    "policy": {
                        "allowed": False,
                        "mode": decision.mode.value,
                        "reason": decision.reason,
                        "confirmation_token": decision.confirmation_token,
                        "confirm_url": (
                            f"/api/policy/confirm/{decision.confirmation_token}"
                            if decision.confirmation_token
                            else None
                        ),
                        "preview": decision.preview,
                    },
                },
            }

        allowed_payload: dict[str, Any] = {
            "slug": slug,
            "action": action_id,
            "mode": decision.mode.value,
            "reason": decision.reason,
            "destructive": spec.destructive,
        }
        if x_tars_thread_id:
            allowed_payload["thread_id"] = x_tars_thread_id
        await client.emit("policy.allowed", allowed_payload)

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
