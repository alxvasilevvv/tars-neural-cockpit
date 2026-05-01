"""System-wide ``pack.memory.*`` actions.

Every domain pack auto-inherits a set of memory actions so the agent
loop, playbooks, and operators all have a uniform way to read / write
the per-pack memory partition. The action ids are namespaced under
``pack.memory.*`` so they cannot collide with a pack's own actions
(packs in ``backend/core/domains/packs/*`` never use ``pack.`` as
their prefix — that namespace is reserved for system-wide injections).

Action surface (every pack):

- ``pack.memory.set`` — upsert ``(key → value)``. Optional ``kind``,
  ``source``, ``metadata``. TTL via ``ttl_seconds`` (relative) or
  ``ttl_until`` (POSIX seconds). Non-destructive: writing into your
  own memory is the same trust class as reading.
- ``pack.memory.get`` — fetch one entry by ``key``. Returns the
  full row or ``{ok: True, found: False}``.
- ``pack.memory.list`` — list entries (``kind`` filter, ``key_prefix``
  filter, ``limit`` 1..1000, ``include_expired`` flag).
- ``pack.memory.delete`` — drop one entry. **Destructive** — routed
  through the policy gate.
- ``pack.memory.purge_expired`` — purge expired rows for the pack.
  Non-destructive (the rows are already invisible to readers).
- ``pack.memory.stats`` — totals + kind breakdown for the pack.

Wiring into :class:`backend.core.domains.base.DomainPack` happens
via :func:`pack_actions` (system-wide composition with the pack's
own ``actions()`` iterator). Tests pin both the dispatch path and
the registry surface (manifest endpoint shows all six injected
actions on every pack).
"""

from __future__ import annotations

import time
from typing import Any, Mapping

from backend.core.memory import MemoryStore, get_memory_store

from .base import ActionSpec


# ---------------------------------------------------------------------
# Argument helpers
# ---------------------------------------------------------------------


def _str_or_none(args: Mapping[str, Any], key: str) -> str | None:
    raw = args.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raw = str(raw)
    raw = raw.strip()
    return raw or None


def _resolve_ttl(args: Mapping[str, Any]) -> tuple[float | None, str | None]:
    """Return ``(ttl_until, error)``.

    ``error`` is ``None`` on success. Accepts either ``ttl_seconds``
    (relative seconds, must be positive) or ``ttl_until`` (POSIX
    timestamp). When both are absent the entry has no TTL.
    """

    seconds = args.get("ttl_seconds")
    until = args.get("ttl_until")
    if seconds is not None and until is not None:
        return None, "ttl_seconds and ttl_until are mutually exclusive"
    if seconds is not None:
        try:
            secs_f = float(seconds)
        except (TypeError, ValueError):
            return None, "ttl_seconds must be a number"
        if secs_f <= 0:
            return None, "ttl_seconds must be > 0"
        return time.time() + secs_f, None
    if until is not None:
        try:
            until_f = float(until)
        except (TypeError, ValueError):
            return None, "ttl_until must be a POSIX timestamp"
        return until_f, None
    return None, None


def _slug_arg(args: Mapping[str, Any]) -> str | None:
    """Allow callers to override the pack slug (composite playbook hop).

    The dispatcher always supplies ``_pack_slug`` so handlers know
    whose partition they belong to. A few advanced workflows want to
    write into a sibling pack's memory (e.g. ``research_lab`` writes
    into ``science.memory.set``) — the optional ``pack_slug`` arg
    lets that through. Composite packs auto-route via the
    ``<sub_slug>__pack.memory.*`` namespacing already.
    """

    explicit = args.get("pack_slug")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    embedded = args.get("_pack_slug")
    if isinstance(embedded, str) and embedded.strip():
        return embedded.strip()
    return None


# ---------------------------------------------------------------------
# Handler factories — closure captures the pack slug
# ---------------------------------------------------------------------


def _make_set(slug: str, store_factory):
    async def handler(args: Mapping[str, Any]) -> dict[str, Any]:
        target = _slug_arg(args) or slug
        key = _str_or_none(args, "key")
        if not key:
            return {"ok": False, "error": "key is required"}
        if "value" not in args:
            return {"ok": False, "error": "value is required"}
        ttl_until, ttl_error = _resolve_ttl(args)
        if ttl_error:
            return {"ok": False, "error": ttl_error}
        kind = _str_or_none(args, "kind") or "fact"
        source = _str_or_none(args, "source")
        metadata = args.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            return {"ok": False, "error": "metadata must be an object"}
        store: MemoryStore = store_factory()
        if not store.enabled:
            return {"ok": False, "error": "memory_store_disabled"}
        entry = await store.upsert(
            pack_slug=target,
            key=key,
            value=args["value"],
            kind=kind,
            ttl_until=ttl_until,
            source=source,
            metadata=metadata if isinstance(metadata, dict) else None,
        )
        if entry is None:
            return {"ok": False, "error": "memory_store_disabled"}
        return {"ok": True, "pack_slug": target, "entry": entry.to_dict()}

    return handler


def _make_get(slug: str, store_factory):
    async def handler(args: Mapping[str, Any]) -> dict[str, Any]:
        target = _slug_arg(args) or slug
        key = _str_or_none(args, "key")
        if not key:
            return {"ok": False, "error": "key is required"}
        include_expired = bool(args.get("include_expired"))
        store: MemoryStore = store_factory()
        if not store.enabled:
            return {"ok": False, "error": "memory_store_disabled"}
        entry = await store.get(
            pack_slug=target, key=key, include_expired=include_expired,
        )
        if entry is None:
            return {
                "ok": True,
                "pack_slug": target,
                "key": key,
                "found": False,
            }
        return {
            "ok": True,
            "pack_slug": target,
            "key": key,
            "found": True,
            "entry": entry.to_dict(),
        }

    return handler


def _make_list(slug: str, store_factory):
    async def handler(args: Mapping[str, Any]) -> dict[str, Any]:
        target = _slug_arg(args) or slug
        kind = _str_or_none(args, "kind")
        prefix = _str_or_none(args, "key_prefix")
        include_expired = bool(args.get("include_expired"))
        try:
            limit = int(args.get("limit", 100))
        except (TypeError, ValueError):
            limit = 100
        limit = max(1, min(limit, 1000))
        store: MemoryStore = store_factory()
        if not store.enabled:
            return {"ok": False, "error": "memory_store_disabled"}
        entries = await store.list(
            pack_slug=target,
            kind=kind,
            key_prefix=prefix,
            limit=limit,
            include_expired=include_expired,
        )
        return {
            "ok": True,
            "pack_slug": target,
            "count": len(entries),
            "entries": [e.to_dict() for e in entries],
        }

    return handler


def _make_delete(slug: str, store_factory):
    async def handler(args: Mapping[str, Any]) -> dict[str, Any]:
        target = _slug_arg(args) or slug
        key = _str_or_none(args, "key")
        if not key:
            return {"ok": False, "error": "key is required"}
        store: MemoryStore = store_factory()
        if not store.enabled:
            return {"ok": False, "error": "memory_store_disabled"}
        deleted = await store.delete(pack_slug=target, key=key)
        return {
            "ok": True,
            "pack_slug": target,
            "key": key,
            "deleted": bool(deleted),
        }

    return handler


def _make_purge(slug: str, store_factory):
    async def handler(args: Mapping[str, Any]) -> dict[str, Any]:
        target = _slug_arg(args) or slug
        store: MemoryStore = store_factory()
        if not store.enabled:
            return {"ok": False, "error": "memory_store_disabled"}
        return await store.purge_expired(pack_slug=target)

    return handler


def _make_stats(slug: str, store_factory):
    async def handler(args: Mapping[str, Any]) -> dict[str, Any]:
        target = _slug_arg(args) or slug
        store: MemoryStore = store_factory()
        if not store.enabled:
            return {"ok": False, "error": "memory_store_disabled"}
        return await store.stats(pack_slug=target)

    return handler


# ---------------------------------------------------------------------
# Public factory — one tuple per pack (closure captures the slug)
# ---------------------------------------------------------------------


def memory_actions(
    pack_slug: str, *, store_factory=get_memory_store,
) -> tuple[ActionSpec, ...]:
    """Return the six ``pack.memory.*`` actions bound to ``pack_slug``.

    ``store_factory`` is a callable returning a :class:`MemoryStore`
    — the default points at the process-wide singleton; tests inject
    their own to keep the SQLite file scoped.
    """

    return (
        ActionSpec(
            id="pack.memory.set",
            name="Memory · Set",
            description=(
                "Upsert a per-pack memory entry. Accepts optional "
                "kind, source, metadata, and TTL "
                "(ttl_seconds or ttl_until)."
            ),
            handler=_make_set(pack_slug, store_factory),
            schema={
                "type": "object",
                "required": ["key", "value"],
                "properties": {
                    "key": {"type": "string"},
                    "value": {},
                    "kind": {"type": "string"},
                    "source": {"type": "string"},
                    "metadata": {"type": "object"},
                    "ttl_seconds": {"type": "number"},
                    "ttl_until": {"type": "number"},
                },
            },
            destructive=False,
        ),
        ActionSpec(
            id="pack.memory.get",
            name="Memory · Get",
            description=(
                "Fetch a single memory entry by key. Returns "
                "``found=False`` when the key is missing or expired."
            ),
            handler=_make_get(pack_slug, store_factory),
            schema={
                "type": "object",
                "required": ["key"],
                "properties": {
                    "key": {"type": "string"},
                    "include_expired": {"type": "boolean"},
                },
            },
            destructive=False,
        ),
        ActionSpec(
            id="pack.memory.list",
            name="Memory · List",
            description=(
                "List memory entries for the pack. Supports kind / "
                "key_prefix filters and an include_expired flag."
            ),
            handler=_make_list(pack_slug, store_factory),
            schema={
                "type": "object",
                "properties": {
                    "kind": {"type": "string"},
                    "key_prefix": {"type": "string"},
                    "limit": {"type": "integer"},
                    "include_expired": {"type": "boolean"},
                },
            },
            destructive=False,
        ),
        ActionSpec(
            id="pack.memory.delete",
            name="Memory · Delete",
            description=(
                "Remove a memory entry. Routed through the policy "
                "gate as a destructive operation."
            ),
            handler=_make_delete(pack_slug, store_factory),
            schema={
                "type": "object",
                "required": ["key"],
                "properties": {"key": {"type": "string"}},
            },
            destructive=True,
        ),
        ActionSpec(
            id="pack.memory.purge_expired",
            name="Memory · Purge expired",
            description=(
                "Drop entries whose TTL is in the past. Scoped to "
                "this pack."
            ),
            handler=_make_purge(pack_slug, store_factory),
            schema={"type": "object", "properties": {}},
            destructive=False,
        ),
        ActionSpec(
            id="pack.memory.stats",
            name="Memory · Stats",
            description=(
                "Totals and kind breakdown for the pack's memory "
                "partition."
            ),
            handler=_make_stats(pack_slug, store_factory),
            schema={"type": "object", "properties": {}},
            destructive=False,
        ),
    )


__all__ = ["memory_actions"]
