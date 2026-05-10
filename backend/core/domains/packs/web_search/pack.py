"""Web-search domain pack.

Why this exists: TARS used to be search-blind unless the operator
spoke specifically to the science pack (arXiv only). Real assistants —
Claude, Cursor, ChatGPT — all have outbound web access. Without it,
TARS can't answer "what's the latest version of pandas" or
"who won the 2026 Champions League" without lying.

Design choices:

- Three adapters so the cockpit works on day-1 (DDG keyless), upgrades
  smoothly when the operator pastes a Brave key (2 000 q/month free),
  and stays fully private when SearXNG is self-hosted.
- Adapter selection is deterministic and auditable: the response
  always includes a ``tried`` array showing every backend that was
  consulted and why each succeeded / failed.
- No background polling — search verbs are explicit, the council
  invokes ``search`` when the operator asks for it.
"""

from __future__ import annotations

from ...base import DomainManifest, DomainPack
from ...registry import register
from .actions import ACTIONS
from .awareness import SOURCES
from .prompts import SYSTEM_PROMPT


class WebSearchPack(DomainPack):
    manifest = DomainManifest(
        slug="web_search",
        name="Web search",
        short="Outbound web access via Brave / SearXNG / DDG.",
        description=(
            "Live search adapter with three backends: Brave "
            "(preferred, free 2k/month), SearXNG (self-host, max "
            "privacy), and DuckDuckGo (keyless fallback). Returns "
            "title / url / snippet rows the council can cite."
        ),
        color="#34d399",
        capabilities=(
            "web_search_brave",
            "web_search_searxng",
            "web_search_ddg",
            "adapter_health",
        ),
        audience="everyone — recency-sensitive Q&A, fact-checking, citation",
    )

    def auth_vault_keys(self) -> tuple[str, ...]:
        return ("BRAVE_SEARCH_API_KEY",)

    def actions(self):
        return ACTIONS

    def awareness(self):
        return SOURCES

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT


register(WebSearchPack())
