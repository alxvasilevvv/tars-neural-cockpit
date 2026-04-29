"""EntrepreneurPack — canonical Phase M name for what was MLM.

Reuses the MLM awareness sources verbatim (the underlying SQLite/CSV
shape didn't change). Action ids are renamed; system prompt is
broader (founder + growth, not just network).

The legacy ``mlm`` pack stays registered (marked
``manifest.deprecated=True``) so saved cockpit state and agents
pinned to it keep working until 2026-07-29.
"""

from __future__ import annotations

from ...base import DomainManifest, DomainPack
from ...registry import register
from ..mlm.awareness import SOURCES as _MLM_SOURCES
from .actions import ACTIONS
from .prompts import SYSTEM_PROMPT


class EntrepreneurPack(DomainPack):
    manifest = DomainManifest(
        slug="entrepreneur",
        name="Entrepreneur",
        short="Founder + growth operator. People, channels, retention.",
        description=(
            "Network depth, lead quality, retention signals, and a "
            "weekly cadence of qualified outreach + content. Tuned to "
            "your tone, never spammy, never pushy."
        ),
        color="#f472b6",
        capabilities=(
            "network_graph",
            "lead_qualification",
            "retention_alerts",
            "content_pipeline",
            "growth_experiments",
        ),
        audience="founders, growth operators, distributors, network builders",
    )

    def auth_vault_keys(self) -> tuple[str, ...]:
        return ("MEEET_API_KEY",)

    def actions(self):
        return ACTIONS

    def awareness(self):
        # Reuse the same awareness sources — the underlying store didn't
        # rename. The cockpit will just see them under the canonical
        # entrepreneur slug.
        return _MLM_SOURCES

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT


register(EntrepreneurPack())
