"""Base types for domain packs.

Stdlib-only on purpose: domain packs must be importable in any Python
environment that runs TARS, even before the rest of the backend boots.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable, Mapping

ActionHandler = Callable[[Mapping[str, Any]], Awaitable[Mapping[str, Any]]]


@dataclass(frozen=True)
class ActionSpec:
    """A single domain action.

    The ``handler`` receives a mapping of arguments and must return a mapping.
    Handlers should be safe to call with empty or partial arguments and must
    not raise for ordinary user input — they should return a structured error
    instead.
    """

    id: str
    name: str
    description: str
    handler: ActionHandler
    schema: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AwarenessSource:
    """A data source feeding into the pack's slice of the awareness graph."""

    id: str
    name: str
    description: str
    kind: str  # "stream" | "poll" | "webhook" | "local"
    config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DomainManifest:
    """Static metadata describing a pack."""

    slug: str
    name: str
    short: str
    description: str
    color: str  # hex, e.g. "#22d3ee"
    capabilities: tuple[str, ...]
    audience: str


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

    def find_action(self, action_id: str) -> ActionSpec | None:
        for spec in self.actions():
            if spec.id == action_id:
                return spec
        return None

    def to_dict(self) -> dict[str, Any]:
        m = self.manifest
        return {
            "slug": m.slug,
            "name": m.name,
            "short": m.short,
            "description": m.description,
            "color": m.color,
            "capabilities": list(m.capabilities),
            "audience": m.audience,
            "actions": [
                {
                    "id": a.id,
                    "name": a.name,
                    "description": a.description,
                    "schema": dict(a.schema),
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
                }
                for s in self.awareness()
            ],
        }
