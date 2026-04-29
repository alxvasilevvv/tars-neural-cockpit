from __future__ import annotations

from ...base import DomainManifest, DomainPack
from ...registry import register
from .actions import ACTIONS
from .awareness import SOURCES
from .prompts import SYSTEM_PROMPT


class MLMPack(DomainPack):
    """Deprecated. Use :class:`EntrepreneurPack` instead.

    Kept registered so existing cockpit state and agent records pinned
    to ``pack_slug=mlm`` keep resolving until 2026-07-29 (90 days from
    Phase M ship).
    """

    manifest = DomainManifest(
        slug="mlm",
        name="MLM",
        short="Downline as a graph, not a spreadsheet.",
        description=(
            "Network depth, activity and retention as living nodes; recruiting "
            "playbooks tuned to your tone; auto-content for newcomers across "
            "IG, TG and WA. (Deprecated — use Entrepreneur.)"
        ),
        color="#f472b6",
        capabilities=(
            "downline_graph",
            "recruiting_playbooks",
            "retention_alerts",
            "content_pipeline",
        ),
        audience="MLM founders, network builders, distributors",
        deprecated=True,
        deprecated_in_favor_of="entrepreneur",
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
