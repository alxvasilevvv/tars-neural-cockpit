"""Role dataclass + small canonical types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# Built-in role slugs; custom roles get a `custom-<random>` slug.
RoleSlug = str


@dataclass(frozen=True)
class Role:
    """A role bound to the operator.

    ``backing_packs`` lists the canonical pack slugs whose tools the
    role expects (the cockpit installs the corresponding packs by
    default). ``overlay`` is the synthesised system-prompt fragment
    that prepends to the pack prompt at orchestration time.
    """

    slug: RoleSlug
    name: str
    description: str
    backing_packs: tuple[str, ...]
    overlay: str
    custom: bool = False
    color: str = "#6366F1"
    icon: str = "Briefcase"  # cockpit-side lucide name; informational only

    def to_dict(self) -> dict[str, object]:
        return {
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "backing_packs": list(self.backing_packs),
            "overlay": self.overlay,
            "custom": self.custom,
            "color": self.color,
            "icon": self.icon,
        }
