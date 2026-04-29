"""Composite domain packs.

A composite pack stitches multiple existing packs into a single virtual
pack so the cockpit can present a unified tab (e.g. "Research Lab" =
business + science). Action ids are namespaced as ``<sub_slug>__<id>``
so the underlying handlers don't collide.

Composites are read-only views — they delegate every action, awareness
fetch, and prompt back to the source pack. Source packs keep ownership
of their secrets, policy flags, and rate limits.
"""

from __future__ import annotations

from typing import Iterable

from .base import (
    ActionSpec,
    AwarenessSource,
    DomainManifest,
    DomainPack,
)


def _namespaced_action(sub_slug: str, spec: ActionSpec) -> ActionSpec:
    """Return a copy of ``spec`` with a namespaced id and tagged name.

    Same handler reference — keeping the closure means rate-limits,
    schemas, and destructive flag stay correct.
    """

    return ActionSpec(
        id=f"{sub_slug}__{spec.id}",
        name=f"{sub_slug}: {spec.name}",
        description=spec.description,
        handler=spec.handler,
        schema=dict(spec.schema),
        destructive=spec.destructive,
    )


def _namespaced_source(sub_slug: str, src: AwarenessSource) -> AwarenessSource:
    return AwarenessSource(
        id=f"{sub_slug}__{src.id}",
        name=f"{sub_slug}: {src.name}",
        description=src.description,
        kind=src.kind,
        config=dict(src.config),
        fetcher=src.fetcher,
    )


class CompositePack(DomainPack):
    """A pack that aggregates multiple sub-packs."""

    def __init__(
        self,
        *,
        slug: str,
        name: str,
        short: str,
        description: str,
        color: str,
        audience: str,
        sub_packs: Iterable[DomainPack],
        extra_capabilities: tuple[str, ...] = (),
    ) -> None:
        self._sub_packs: tuple[DomainPack, ...] = tuple(sub_packs)
        if not self._sub_packs:
            raise ValueError("CompositePack requires at least one sub-pack")
        capabilities: list[str] = list(extra_capabilities)
        for p in self._sub_packs:
            for cap in p.manifest.capabilities:
                if cap not in capabilities:
                    capabilities.append(cap)
        self.manifest = DomainManifest(
            slug=slug,
            name=name,
            short=short,
            description=description,
            color=color,
            capabilities=tuple(capabilities),
            audience=audience,
        )

    @property
    def composed_of(self) -> tuple[str, ...]:
        return tuple(p.manifest.slug for p in self._sub_packs)

    def actions(self) -> Iterable[ActionSpec]:
        out: list[ActionSpec] = []
        for sub in self._sub_packs:
            for spec in sub.actions():
                out.append(_namespaced_action(sub.manifest.slug, spec))
        return out

    def awareness(self) -> Iterable[AwarenessSource]:
        out: list[AwarenessSource] = []
        for sub in self._sub_packs:
            for src in sub.awareness():
                out.append(_namespaced_source(sub.manifest.slug, src))
        return out

    def auth_vault_keys(self) -> tuple[str, ...]:
        keys: list[str] = []
        for sub in self._sub_packs:
            for k in sub.auth_vault_keys():
                if k not in keys:
                    keys.append(k)
        return tuple(keys)

    def system_prompt(self) -> str:
        chunks: list[str] = [
            f"You are operating in TARS composite mode '{self.manifest.name}'."
            f" The composite covers: {', '.join(p.manifest.name for p in self._sub_packs)}.",
            (
                "When the operator's intent maps cleanly onto one sub-pack,"
                " quote that sub-pack and stay scoped. When the intent crosses"
                " sub-packs (e.g. research → pitch, KPI → outreach), do the"
                " hand-off explicitly and label each step with the source"
                " sub-pack name."
            ),
            "",
            "--- sub-pack prompts ---",
        ]
        for sub in self._sub_packs:
            chunks.append(f"\n## {sub.manifest.name} ({sub.manifest.slug})")
            chunks.append(sub.system_prompt())
        return "\n".join(chunks).strip() + "\n"

    def to_dict(self) -> dict[str, object]:
        out = super().to_dict()
        out["composite"] = True
        out["composed_of"] = list(self.composed_of)
        return out
