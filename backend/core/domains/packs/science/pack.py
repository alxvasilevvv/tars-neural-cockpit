from __future__ import annotations

from ...base import DomainManifest, DomainPack
from ...registry import register
from .actions import ACTIONS
from .awareness import SOURCES
from .prompts import SYSTEM_PROMPT


class SciencePack(DomainPack):
    manifest = DomainManifest(
        slug="science",
        name="Science",
        short="From paper pile to citation-aware council.",
        description=(
            "arXiv / Crossref / Semantic Scholar awareness, equation and "
            "dataset graph across your projects, hypothesis trees with "
            "model-voted evidence."
        ),
        color="#ffb429",
        capabilities=(
            "literature_awareness",
            "dataset_graph",
            "hypothesis_trees",
            "equation_index",
        ),
        audience="researchers, PhD students, R&D leads",
    )

    def actions(self):
        return ACTIONS

    def awareness(self):
        return SOURCES

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT


register(SciencePack())
