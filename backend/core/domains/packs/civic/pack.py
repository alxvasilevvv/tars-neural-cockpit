"""CivicPack — public-records access as a baseline TARS utility."""

from __future__ import annotations

from ...base import DomainManifest, DomainPack
from ...registry import register
from .actions import ACTIONS
from .awareness import SOURCES
from .prompts import SYSTEM_PROMPT


class CivicPack(DomainPack):
    manifest = DomainManifest(
        slug="civic",
        name="Civic",
        short="Free public-records lookups: legislators, votes, court cases.",
        description=(
            "Free, keyless access to public-records APIs (OpenStates for "
            "state and federal legislators, CourtListener for federal "
            "court records). Available on every tier including Free — "
            "civic information should not be a paid upsell."
        ),
        color="#22d3ee",
        capabilities=(
            "lookup_legislator",
            "recent_votes",
            "court_case_search",
        ),
        audience="every citizen, journalist, researcher, civic technologist",
    )

    def auth_vault_keys(self) -> tuple[str, ...]:
        # All adapters use keyless free tiers.
        return ()

    def actions(self):
        return ACTIONS

    def awareness(self):
        return SOURCES

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT


register(CivicPack())
