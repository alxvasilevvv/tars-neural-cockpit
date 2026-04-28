from __future__ import annotations

from ...base import DomainManifest, DomainPack
from ...registry import register
from .actions import ACTIONS
from .awareness import SOURCES
from .prompts import SYSTEM_PROMPT


class TradersPack(DomainPack):
    manifest = DomainManifest(
        slug="traders",
        name="Traders",
        short="Markets & signals at the speed of a thought.",
        description=(
            "Live market awareness, signal generation with explainable model "
            "votes, and policy-guarded portfolio actions."
        ),
        color="#22d3ee",
        capabilities=(
            "market_awareness",
            "signal_generation",
            "portfolio_actions",
            "risk_policy",
        ),
        audience="active traders, quants, prop desks",
    )

    def auth_vault_keys(self) -> tuple[str, ...]:
        return ("MEEET_API_KEY", "TARS_ANTHROPIC_API_KEY", "TARS_OPENAI_API_KEY")

    def actions(self):
        return ACTIONS

    def awareness(self):
        return SOURCES

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT


register(TradersPack())
