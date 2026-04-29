"""Domain pack registry.

Packs register themselves at import time by calling :func:`register`. The
registry is a simple in-process mapping; nothing here implies how the host
app discovers packs (the app should ``import backend.core.domains.packs``).

Phase M (P6) adds *aliases*: a deprecated slug that resolves to the same
pack instance. This lets us rename ``mlm`` → ``entrepreneur`` without
breaking saved cockpit state, agent metadata, or third-party clients
that pinned the old name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .base import DomainPack

_REGISTRY: dict[str, DomainPack] = {}


@dataclass(frozen=True)
class _Alias:
    """Old slug → new slug pointer with a deprecation deadline."""

    canonical: str
    deprecated_until: str  # ISO date — informational, not enforced.


_ALIASES: dict[str, _Alias] = {}


def register(pack: DomainPack) -> None:
    """Register a pack instance under its manifest slug.

    Re-registration with the same slug overwrites the previous entry. Tests
    rely on this for monkey-patching; production should not need it.
    """

    slug = pack.manifest.slug
    if not slug:
        raise ValueError("DomainPack manifest.slug must be non-empty")
    _REGISTRY[slug] = pack


def register_alias(*, alias: str, canonical: str, deprecated_until: str) -> None:
    """Register that ``alias`` should resolve to the pack under ``canonical``.

    The canonical pack must already be registered (raises ``ValueError`` if
    not). Aliases are tracked separately from real packs so
    :func:`all_packs` and :func:`/api/domains/manifest` keep returning the
    canonical list — the alias only affects :func:`get_pack`.
    """

    if not alias or not canonical:
        raise ValueError("alias and canonical must be non-empty")
    if alias == canonical:
        raise ValueError("alias must differ from canonical slug")
    if canonical not in _REGISTRY:
        raise ValueError(
            f"cannot alias {alias!r} → {canonical!r}: canonical not registered"
        )
    _ALIASES[alias] = _Alias(canonical=canonical, deprecated_until=deprecated_until)


def get_pack(slug: str) -> DomainPack | None:
    """Return the pack registered under ``slug`` or ``None``.

    If ``slug`` is an alias, return the canonical pack (callers see the
    new name on ``pack.manifest.slug``).
    """

    direct = _REGISTRY.get(slug)
    if direct is not None:
        return direct
    alias = _ALIASES.get(slug)
    if alias is not None:
        return _REGISTRY.get(alias.canonical)
    return None


def resolve_alias(slug: str) -> str:
    """Return the canonical slug for ``slug`` (no-op if already canonical)."""

    alias = _ALIASES.get(slug)
    return alias.canonical if alias is not None else slug


def aliases() -> dict[str, _Alias]:
    """Return a copy of the alias map for introspection / docs."""

    return dict(_ALIASES)


def all_packs() -> Iterable[DomainPack]:
    """Return all registered packs in insertion order."""

    return tuple(_REGISTRY.values())


def clear() -> None:
    """Remove every registered pack and alias. Test helper, not for production."""

    _REGISTRY.clear()
    _ALIASES.clear()
