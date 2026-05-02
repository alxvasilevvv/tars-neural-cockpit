"""Deterministic hypothesis-tree generator for the science pack.

The original ``hypothesis_tree`` action returned a single empty node.
This module replaces it with a deterministic, audit-friendly
decomposition: from a *seed claim* it grows children along five
canonical scientific dimensions (mechanism, alternatives, confounders,
conditions, evidence) that any researcher would probe.

Why deterministic?
- Tests pin the shape and stay fast / offline.
- The cockpit can render the tree as a stable layout per seed.
- A future LLM-backed generator can wrap this as a "fast path" or be
  A/B-compared against it; the contract is identical.

Why these five dimensions?
- They cover the standard interrogation a peer reviewer applies to a
  causal / structural claim. They are domain-agnostic enough to fit
  biology, physics, ML, or economics without bespoke vocab.

Output shape (JSON-serialisable):

    {
        "node": "<seed claim>",
        "kind": "seed",
        "id": "h-0001",
        "depth": 0,
        "children": [
            {
                "node": "What is the causal mechanism of <seed>?",
                "kind": "mechanism",
                "id": "h-0002",
                "depth": 1,
                "children": [...],   # only when ``depth >= 2``
            },
            ...
        ]
    }

``depth`` is the *requested tree depth* in the action (0 = seed only,
1 = seed + one child layer, 2 = + grandchildren). Depths above 3 are
clamped because the templates start to repeat.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# A single child template carries (kind, prompt template). The
# template uses ``{seed}`` for the parent claim. Keep these short
# and concrete — the cockpit renders them as collapsible chips.
_DIMENSIONS: tuple[tuple[str, str], ...] = (
    (
        "mechanism",
        "What is the causal mechanism of {seed}?",
    ),
    (
        "alternatives",
        "What is the strongest alternative to {seed}?",
    ),
    (
        "confounders",
        "Which confounders could fake the {seed} pattern?",
    ),
    (
        "conditions",
        "Under what conditions does {seed} hold?",
    ),
    (
        "evidence",
        "What evidence would falsify {seed}?",
    ),
)


# Per-dimension grandchildren templates. These give a deterministic
# 2-deep tree without hand-authoring 5×5 prompts. Each entry is
# ``(kind, template)``; ``{seed}`` refers to the *grandparent* (the
# original claim) so the chain stays readable.
_GRANDCHILDREN: dict[str, tuple[tuple[str, str], ...]] = {
    "mechanism": (
        ("step", "Decompose the mechanism of {seed} into its first step."),
        ("step", "Decompose the mechanism of {seed} into its bottleneck."),
    ),
    "alternatives": (
        ("alternative", "Could the inverse of {seed} fit the data equally well?"),
        ("alternative", "Could a third-variable model subsume {seed}?"),
    ),
    "confounders": (
        ("confounder", "Is selection bias the dominant driver behind {seed}?"),
        ("confounder", "Is measurement bias inflating evidence for {seed}?"),
    ),
    "conditions": (
        ("condition", "Does {seed} replicate across populations?"),
        ("condition", "Does {seed} hold at the limits of the parameter range?"),
    ),
    "evidence": (
        ("test", "Design an intervention that would refute {seed}."),
        ("test", "Identify a natural experiment that would refute {seed}."),
    ),
}


_MAX_DEPTH = 3


@dataclass(frozen=True)
class HypothesisNode:
    """A node in the deterministic hypothesis tree."""

    id: str
    node: str
    kind: str
    depth: int
    children: tuple["HypothesisNode", ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "node": self.node,
            "kind": self.kind,
            "depth": self.depth,
            "children": [c.to_dict() for c in self.children],
        }


class _IdMint:
    """Monotonic ``h-NNNN`` id minter, scoped to one tree generation."""

    def __init__(self) -> None:
        self._n = 0

    def next(self) -> str:
        self._n += 1
        return f"h-{self._n:04d}"


def _normalise_seed(seed: str) -> str:
    """Strip whitespace and trailing punctuation so prompts read cleanly."""

    out = seed.strip()
    while out and out[-1] in ".?!,;:":
        out = out[:-1]
    return out


def _build_grandchildren(
    parent_kind: str,
    seed: str,
    minter: _IdMint,
) -> tuple[HypothesisNode, ...]:
    templates = _GRANDCHILDREN.get(parent_kind) or ()
    return tuple(
        HypothesisNode(
            id=minter.next(),
            node=tmpl.format(seed=seed),
            kind=child_kind,
            depth=2,
            children=(),
        )
        for child_kind, tmpl in templates
    )


def grow_tree(seed: str, *, depth: int = 1) -> HypothesisNode:
    """Grow a deterministic hypothesis tree from ``seed``.

    ``depth`` is the requested tree depth; clamped to ``[0, 3]``.
    Negative or non-int values are treated as ``1`` (sensible default
    for the cockpit).
    """

    raw = _normalise_seed(seed)
    if not raw:
        raise ValueError("seed_required")
    if not isinstance(depth, int) or depth < 0:
        depth = 1
    depth = min(depth, _MAX_DEPTH)

    minter = _IdMint()
    seed_id = minter.next()

    if depth == 0:
        return HypothesisNode(
            id=seed_id,
            node=raw,
            kind="seed",
            depth=0,
            children=(),
        )

    children: list[HypothesisNode] = []
    for child_kind, tmpl in _DIMENSIONS:
        child_id = minter.next()
        grandchildren = (
            _build_grandchildren(child_kind, raw, minter) if depth >= 2 else ()
        )
        children.append(
            HypothesisNode(
                id=child_id,
                node=tmpl.format(seed=raw),
                kind=child_kind,
                depth=1,
                children=grandchildren,
            )
        )
    return HypothesisNode(
        id=seed_id,
        node=raw,
        kind="seed",
        depth=0,
        children=tuple(children),
    )


__all__ = [
    "HypothesisNode",
    "grow_tree",
]
