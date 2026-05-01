"""Tests for the deterministic ``science.hypothesis_tree`` action.

Replaces the previous one-line stub. Pins the tree shape, depth
clamping, id minting, normalisation, and ActionSpec wiring so the
cockpit can rely on a stable contract.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from backend.core.domains.packs.science.actions import (
    hypothesis_tree,
)
from backend.core.domains.packs.science.actions import ACTIONS as SCIENCE_ACTIONS
from backend.core.domains.packs.science.hypothesis import (
    HypothesisNode,
    grow_tree,
)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- grow_tree

def test_grow_tree_seed_required() -> None:
    with pytest.raises(ValueError, match="seed_required"):
        grow_tree("")
    with pytest.raises(ValueError, match="seed_required"):
        grow_tree("   ")
    with pytest.raises(ValueError, match="seed_required"):
        grow_tree("???")  # punctuation alone strips to empty


def test_grow_tree_depth0_returns_only_seed() -> None:
    tree = grow_tree("X causes Y", depth=0)
    assert tree.kind == "seed"
    assert tree.depth == 0
    assert tree.node == "X causes Y"
    assert tree.children == ()
    assert tree.id == "h-0001"


def test_grow_tree_default_depth_is_one() -> None:
    tree = grow_tree("X causes Y")
    assert len(tree.children) == 5
    assert all(c.depth == 1 for c in tree.children)
    assert all(c.children == () for c in tree.children)


def test_grow_tree_depth2_grandchildren() -> None:
    tree = grow_tree("X causes Y", depth=2)
    assert len(tree.children) == 5
    for child in tree.children:
        assert len(child.children) == 2
        for gc in child.children:
            assert gc.depth == 2
            assert gc.children == ()


def test_grow_tree_depth_clamped_to_max_3() -> None:
    big = grow_tree("X causes Y", depth=99)
    deep = grow_tree("X causes Y", depth=3)
    # depth 3 == depth 99 (we cap at the templates we support)
    assert big.to_dict() == deep.to_dict()


def test_grow_tree_negative_depth_falls_back_to_default() -> None:
    a = grow_tree("X causes Y", depth=-5)
    b = grow_tree("X causes Y")
    assert a.to_dict() == b.to_dict()


def test_grow_tree_normalises_seed_punctuation() -> None:
    tree = grow_tree("Coffee improves focus.", depth=1)
    assert tree.node == "Coffee improves focus"
    assert tree.children[0].node == (
        "What is the causal mechanism of Coffee improves focus?"
    )


def test_grow_tree_normalises_repeated_terminators() -> None:
    tree = grow_tree("Coffee improves focus?!.", depth=0)
    assert tree.node == "Coffee improves focus"


def test_grow_tree_dimensions_in_canonical_order() -> None:
    tree = grow_tree("X causes Y")
    expected = [
        "mechanism",
        "alternatives",
        "confounders",
        "conditions",
        "evidence",
    ]
    assert [c.kind for c in tree.children] == expected


def test_grow_tree_grandchild_kinds_are_typed() -> None:
    tree = grow_tree("X causes Y", depth=2)
    by_parent = {c.kind: c for c in tree.children}

    assert {gc.kind for gc in by_parent["mechanism"].children} == {"step"}
    assert {gc.kind for gc in by_parent["alternatives"].children} == {"alternative"}
    assert {gc.kind for gc in by_parent["confounders"].children} == {"confounder"}
    assert {gc.kind for gc in by_parent["conditions"].children} == {"condition"}
    assert {gc.kind for gc in by_parent["evidence"].children} == {"test"}


def test_grow_tree_ids_are_monotonic_and_unique() -> None:
    tree = grow_tree("X causes Y", depth=2)
    seen: list[str] = []

    def visit(n: HypothesisNode) -> None:
        seen.append(n.id)
        for c in n.children:
            visit(c)

    visit(tree)
    assert seen[0] == "h-0001"
    assert len(seen) == len(set(seen))
    # 1 seed + 5 children + 5*2 grandchildren = 16 nodes
    assert len(seen) == 16


def test_grow_tree_to_dict_round_trips() -> None:
    tree = grow_tree("X causes Y", depth=2)
    out = tree.to_dict()
    assert isinstance(out, dict)
    assert out["id"] == "h-0001"
    assert out["children"][0]["children"][0]["depth"] == 2


def test_grow_tree_is_deterministic() -> None:
    a = grow_tree("X causes Y", depth=2)
    b = grow_tree("X causes Y", depth=2)
    assert a.to_dict() == b.to_dict()


# ---------------------------------------------------------------- action handler

def test_hypothesis_tree_action_blank_seed_returns_error() -> None:
    out = _run(hypothesis_tree({"seed": ""}))
    assert out == {"ok": False, "error": "seed_required"}


def test_hypothesis_tree_action_punctuation_only_seed_errors() -> None:
    out = _run(hypothesis_tree({"seed": "???"}))
    assert out == {"ok": False, "error": "seed_required"}


def test_hypothesis_tree_action_default_depth_one() -> None:
    out = _run(hypothesis_tree({"seed": "X causes Y"}))
    assert out["ok"] is True
    assert out["seed"] == "X causes Y"
    assert out["depth"] == 1
    assert out["model"] == "heuristic-v1"
    assert len(out["tree"]["children"]) == 5
    assert all(c["children"] == [] for c in out["tree"]["children"])


def test_hypothesis_tree_action_depth_2() -> None:
    out = _run(hypothesis_tree({"seed": "X causes Y", "depth": 2}))
    assert out["depth"] == 2
    children = out["tree"]["children"]
    assert all(len(c["children"]) == 2 for c in children)


def test_hypothesis_tree_action_depth_clamped_to_3() -> None:
    out = _run(hypothesis_tree({"seed": "X causes Y", "depth": 9}))
    assert out["depth"] == 3


def test_hypothesis_tree_action_negative_depth_falls_back_to_one(
) -> None:
    out = _run(hypothesis_tree({"seed": "X causes Y", "depth": -2}))
    assert out["depth"] == 1
    assert len(out["tree"]["children"]) == 5


def test_hypothesis_tree_action_garbage_depth_falls_back_to_one() -> None:
    out = _run(hypothesis_tree({"seed": "X causes Y", "depth": "many"}))
    assert out["depth"] == 1


def test_hypothesis_tree_action_seed_punctuation_normalised() -> None:
    out = _run(hypothesis_tree({"seed": "Coffee improves focus."}))
    assert out["seed"] == "Coffee improves focus"


def test_hypothesis_tree_action_tree_carries_kind_and_id() -> None:
    out = _run(hypothesis_tree({"seed": "X causes Y", "depth": 1}))
    tree = out["tree"]
    assert tree["kind"] == "seed"
    assert tree["id"] == "h-0001"
    assert all("kind" in c and "id" in c for c in tree["children"])


def test_hypothesis_tree_action_is_deterministic() -> None:
    a = _run(hypothesis_tree({"seed": "X causes Y", "depth": 2}))
    b = _run(hypothesis_tree({"seed": "X causes Y", "depth": 2}))
    assert a == b


# ---------------------------------------------------------------- ActionSpec wiring

def test_hypothesis_tree_spec_exposes_depth_knob() -> None:
    spec = next(s for s in SCIENCE_ACTIONS if s.id == "hypothesis_tree")
    assert spec.destructive is False
    assert spec.schema["required"] == ["seed"]
    depth_schema = spec.schema["properties"]["depth"]
    assert depth_schema["type"] == "integer"
    assert depth_schema["minimum"] == 0
    assert depth_schema["maximum"] == 3
    assert depth_schema["default"] == 1
