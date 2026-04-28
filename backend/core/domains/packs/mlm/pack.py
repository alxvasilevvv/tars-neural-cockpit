from __future__ import annotations

from ...base import DomainManifest, DomainPack
from ...registry import register
from .actions import ACTIONS
from .awareness import SOURCES
from .prompts import SYSTEM_PROMPT


class MLMPack(DomainPack):
    manifest = DomainManifest(
        slug="mlm",
        name="MLM",
        short="Downline as a graph, not a spreadsheet.",
        description=(
            "Network depth, activity and retention as living nodes; recruiting "
            "playbooks tuned to your tone; auto-content for newcomers across "
            "IG, TG and WA."
        ),
        color="#f472b6",
        capabilities=(
            "downline_graph",
            "recruiting_playbooks",
            "retention_alerts",
            "content_pipeline",
        ),
        audience="MLM founders, network builders, distributors",
    )

    def auth_vault_keys(self) -> tuple[str, ...]:
        return ("MEEET_API_KEY",)

    def actions(self):
        return ACTIONS

    def awareness(self):
        return SOURCES

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT


register(MLMPack())
