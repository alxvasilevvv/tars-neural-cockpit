"""Base types for domain packs.

Stdlib-only on purpose: domain packs must be importable in any Python
environment that runs TARS, even before the rest of the backend boots.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable, Mapping, Optional

from backend.core.vault import status_for_keys

ActionHandler = Callable[[Mapping[str, Any]], Awaitable[Mapping[str, Any]]]
AwarenessFetcher = Callable[[Mapping[str, Any]], Awaitable[Mapping[str, Any]]]


@dataclass(frozen=True)
class ActionSpec:
    """A single domain action.

    The ``handler`` receives a mapping of arguments and must return a mapping.
    Handlers should be safe to call with empty or partial arguments and must
    not raise for ordinary user input — they should return a structured error
    instead.

    ``destructive`` flags actions that mutate external state (send mail,
    push to CRM, place an alert, post content). The HTTP invoke pipeline
    routes destructive calls through the policy gate; non-destructive
    actions run immediately regardless of mode.
    """

    id: str
    name: str
    description: str
    handler: ActionHandler
    schema: Mapping[str, Any] = field(default_factory=dict)
    destructive: bool = False


@dataclass(frozen=True)
class AwarenessSource:
    """A data source feeding into the pack's slice of the awareness graph.

    ``fetcher`` is optional. When set, the cockpit can call
    ``GET /api/domains/<slug>/awareness/<id>/snapshot`` to materialise
    the source. Sources without a fetcher are advertised as config-only
    (e.g. webhook receivers) and respond with ``ok=False / status=fetcher_unavailable``
    when a snapshot is requested.
    """

    id: str
    name: str
    description: str
    kind: str  # "stream" | "poll" | "webhook" | "local"
    config: Mapping[str, Any] = field(default_factory=dict)
    fetcher: Optional[AwarenessFetcher] = None


@dataclass(frozen=True)
class DomainManifest:
    """Static metadata describing a pack.

    Phase M / P6 adds a ``deprecated`` flag. Deprecated packs stay
    importable and resolvable through ``get_pack`` so saved cockpit
    state and agents pinned to the old slug keep working, but the
    ``/api/domains/manifest`` payload omits them by default — pass
    ``include_deprecated=true`` to surface the legacy entries.
    ``deprecated_in_favor_of`` points operators at the canonical slug.
    """

    slug: str
    name: str
    short: str
    description: str
    color: str  # hex, e.g. "#22d3ee"
    capabilities: tuple[str, ...]
    audience: str
    deprecated: bool = False
    deprecated_in_favor_of: str | None = None


class DomainPack(ABC):
    """Abstract base for a TARS domain pack.

    Subclasses set a ``manifest`` class attribute and implement the three
    accessor methods. Subclasses register themselves by calling
    :func:`backend.core.domains.registry.register` at import time.
    """

    manifest: DomainManifest

    @abstractmethod
    def actions(self) -> Iterable[ActionSpec]:
        """Return the actions this pack contributes."""

    @abstractmethod
    def awareness(self) -> Iterable[AwarenessSource]:
        """Return the awareness sources this pack listens to."""

    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt the council uses in this mode."""

    def auth_vault_keys(self) -> tuple[str, ...]:
        """Names of secrets / API keys this pack may consume.

        Used only for UI badges via :meth:`to_dict` — resolves each key
        through the vault (env → Keychain → missing). Values are never
        exposed.
        """

        return ()

    def find_action(self, action_id: str) -> ActionSpec | None:
        for spec in self.actions():
            if spec.id == action_id:
                return spec
        return None

    def find_awareness(self, source_id: str) -> AwarenessSource | None:
        for src in self.awareness():
            if src.id == source_id:
                return src
        return None

    def to_dict(self) -> dict[str, Any]:
        m = self.manifest
        auth_refs = status_for_keys(self.auth_vault_keys())
        return {
            "slug": m.slug,
            "name": m.name,
            "short": m.short,
            "description": m.description,
            "color": m.color,
            "capabilities": list(m.capabilities),
            "audience": m.audience,
            "deprecated": m.deprecated,
            "deprecated_in_favor_of": m.deprecated_in_favor_of,
            "auth": {
                "keys": [
                    {"key": r.key, "source": r.source, "available": r.available}
                    for r in auth_refs
                ]
            },
            "actions": [
                {
                    "id": a.id,
                    "name": a.name,
                    "description": a.description,
                    "schema": dict(a.schema),
                    "destructive": a.destructive,
                }
                for a in self.actions()
            ],
            "awareness": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "kind": s.kind,
                    "config": dict(s.config),
                    "live": s.fetcher is not None,
                }
                for s in self.awareness()
            ],
        }
