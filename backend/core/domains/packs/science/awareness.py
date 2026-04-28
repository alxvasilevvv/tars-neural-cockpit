from __future__ import annotations

from ...base import AwarenessSource

SOURCES: tuple[AwarenessSource, ...] = (
    AwarenessSource(
        id="arxiv",
        name="arXiv",
        description="arXiv listings filtered by user-selected categories.",
        kind="poll",
        config={
            "interval_s": 1800,
            "categories": ["cs.AI", "cs.LG", "stat.ML"],
        },
    ),
    AwarenessSource(
        id="crossref",
        name="Crossref",
        description="DOI metadata + citations.",
        kind="poll",
        config={"interval_s": 3600},
    ),
    AwarenessSource(
        id="semantic_scholar",
        name="Semantic Scholar",
        description="Author / paper graph with embeddings.",
        kind="poll",
        config={"interval_s": 3600},
    ),
    AwarenessSource(
        id="local_papers",
        name="Local papers",
        description="A folder of PDFs/markdown indexed locally.",
        kind="local",
        config={"path": "~/Documents/papers"},
    ),
    AwarenessSource(
        id="datasets_dir",
        name="Datasets dir",
        description="Versioned local datasets surface.",
        kind="local",
        config={"path": "~/Datasets"},
    ),
)
