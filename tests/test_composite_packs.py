"""Tests for composite packs + the manifest endpoint."""

from __future__ import annotations

from backend.core.domains import packs as _packs  # noqa: F401
from backend.core.domains.composite import CompositePack
from backend.core.domains.registry import all_packs, get_pack


def test_research_lab_composite_registered() -> None:
    pack = get_pack("research_lab")
    assert pack is not None
    assert getattr(pack, "composed_of", ()) == ("science", "business")


def test_ops_room_composite_registered() -> None:
    pack = get_pack("ops_room")
    assert pack is not None
    assert getattr(pack, "composed_of", ()) == ("traders", "mlm")


def test_composite_actions_namespaced_and_destructive_preserved() -> None:
    pack = get_pack("research_lab")
    assert pack is not None
    action_ids = {a.id: a for a in pack.actions()}
    # Composed of science + business — namespacing means business actions
    # surface with the "business__" prefix.
    assert any(aid.startswith("business__") for aid in action_ids)
    assert any(aid.startswith("science__") for aid in action_ids)
    log_deal = action_ids.get("business__log_deal")
    assert log_deal is not None
    assert log_deal.destructive is True
    # Sub-pack non-destructive actions stay non-destructive in the composite.
    summarize = action_ids.get("science__summarize_paper")
    assert summarize is not None
    assert summarize.destructive is False


def test_composite_awareness_namespaced() -> None:
    pack = get_pack("ops_room")
    assert pack is not None
    src_ids = {s.id for s in pack.awareness()}
    assert any(sid.startswith("traders__") for sid in src_ids)
    assert any(sid.startswith("mlm__") for sid in src_ids)


def test_composite_to_dict_marks_composite_true() -> None:
    pack = get_pack("research_lab")
    assert pack is not None
    out = pack.to_dict()
    assert out["composite"] is True
    assert out["composed_of"] == ["science", "business"]
    assert out["color"] == "#a78bfa"


def test_composite_system_prompt_contains_subpacks() -> None:
    pack = get_pack("research_lab")
    assert pack is not None
    prompt = pack.system_prompt()
    assert "Research Lab" in prompt
    assert "science" in prompt
    assert "business" in prompt


def test_composite_auth_keys_union() -> None:
    pack = get_pack("research_lab")
    assert pack is not None
    keys = pack.auth_vault_keys()
    # Pulled from both sub-packs; HUBSPOT comes from business, OPENALEX_EMAIL
    # from science. Union is order-preserving.
    assert "HUBSPOT_API_KEY" in keys
    assert "OPENALEX_EMAIL" in keys


def test_composite_pack_requires_at_least_one_subpack() -> None:
    science = get_pack("science")
    assert science is not None
    try:
        CompositePack(
            slug="empty",
            name="Empty",
            short="",
            description="",
            color="#000",
            audience="",
            sub_packs=(),
        )
    except ValueError as exc:
        assert "sub-pack" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for empty composite")
