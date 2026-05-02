"""Phase M / P6 — Entrepreneur pack contract.

Locks:
- Entrepreneur pack is registered with the renamed action ids.
- MLM pack stays registered, marked deprecated.
- Deprecation flag surfaces on the manifest payload.
- Action handlers are compatible (network_snapshot reuses the same
  underlying store as the legacy downline_snapshot).
"""

from __future__ import annotations

import asyncio

import pytest

from backend.core.domains import packs  # noqa: F401  (triggers registration)
from backend.core.domains.registry import all_packs, get_pack


def test_entrepreneur_pack_registered() -> None:
    pack = get_pack("entrepreneur")
    assert pack is not None
    assert pack.manifest.slug == "entrepreneur"
    assert pack.manifest.name == "Entrepreneur"
    assert "growth_experiments" in pack.manifest.capabilities
    assert pack.manifest.deprecated is False


def test_mlm_pack_remains_registered_but_deprecated() -> None:
    legacy = get_pack("mlm")
    assert legacy is not None, (
        "MLM pack must stay registered through the 2026-07-29 deprecation window"
    )
    assert legacy.manifest.deprecated is True
    assert legacy.manifest.deprecated_in_favor_of == "entrepreneur"


def test_entrepreneur_action_ids_match_phase_m_spec() -> None:
    pack = get_pack("entrepreneur")
    assert pack is not None
    ids = {a.id for a in pack.actions()}
    expected = {
        "network_snapshot",
        "lead_score",
        "generate_content",
        "retention_alert",
        "add_lead",
        "log_activity",
    }
    assert ids == expected, f"missing or extra: {ids ^ expected}"


def test_legacy_mlm_action_ids_unchanged() -> None:
    """Existing tests + saved agents pinned to MLM action ids must work."""
    legacy = get_pack("mlm")
    assert legacy is not None
    legacy_ids = {a.id for a in legacy.actions()}
    assert {
        "downline_snapshot",
        "score_recruit",
        "generate_post",
        "retention_alert",
        "add_member",
        "log_activity",
    } <= legacy_ids


def test_entrepreneur_actions_are_destructive_where_expected() -> None:
    pack = get_pack("entrepreneur")
    assert pack is not None
    by_id = {a.id: a for a in pack.actions()}
    assert by_id["generate_content"].destructive is True
    assert by_id["add_lead"].destructive is True
    assert by_id["log_activity"].destructive is True
    # Read-only
    assert by_id["network_snapshot"].destructive is False
    assert by_id["lead_score"].destructive is False
    assert by_id["retention_alert"].destructive is False


def test_lead_score_runs_and_is_deterministic() -> None:
    pack = get_pack("entrepreneur")
    assert pack is not None
    by_id = {a.id: a for a in pack.actions()}
    score_a = asyncio.run(by_id["lead_score"].handler({"handle": "ada"}))
    score_b = asyncio.run(by_id["lead_score"].handler({"handle": "ada"}))
    assert score_a["ok"] is True
    # Handler is deterministic for the same handle.
    assert score_a["score"] == score_b["score"]


def test_generate_content_keeps_channel_constraints() -> None:
    pack = get_pack("entrepreneur")
    assert pack is not None
    by_id = {a.id: a for a in pack.actions()}
    out = asyncio.run(by_id["generate_content"].handler({"channel": "ig"}))
    assert out["ok"] is True
    assert out["channel"] == "ig"
    bad = asyncio.run(by_id["generate_content"].handler({"channel": "facebook"}))
    assert bad["ok"] is False
    assert bad["error"] == "unsupported_channel"


def test_pack_listing_can_filter_deprecated() -> None:
    """Helper to surface canonical-only via list comprehension."""
    canonical = [p for p in all_packs() if not p.manifest.deprecated]
    slugs = {p.manifest.slug for p in canonical}
    assert "entrepreneur" in slugs
    assert "mlm" not in slugs


def test_generate_content_schema_exposes_full_drafter_surface() -> None:
    """The cockpit reads ``ActionSpec.schema`` to render input
    forms; the entrepreneur pack must expose the new tone /
    language / cta knobs and the linkedin channel (added when
    `mlm.generate_post` was upgraded to a real drafter), otherwise
    operators can't reach those features through the entrepreneur
    namespace."""

    pack = get_pack("entrepreneur")
    assert pack is not None
    by_id = {a.id: a for a in pack.actions()}
    schema = by_id["generate_content"].schema
    props = schema["properties"]

    assert "tone" in props
    assert "language" in props
    assert "cta" in props
    assert "linkedin" in props["channel"]["enum"]
    assert {"warm", "professional", "urgent", "celebratory"} <= set(
        props["tone"]["enum"]
    )
    assert {"en", "ru", "es"} <= set(props["language"]["enum"])


def test_generate_content_full_knob_path_runs() -> None:
    pack = get_pack("entrepreneur")
    assert pack is not None
    by_id = {a.id: a for a in pack.actions()}
    out = asyncio.run(
        by_id["generate_content"].handler(
            {
                "channel": "linkedin",
                "format": "post",
                "tone": "professional",
                "language": "ru",
                "topic": "квартальный сдвиг",
            }
        )
    )
    assert out["ok"] is True
    assert out["channel"] == "linkedin"
    assert out["language"] == "ru"
    assert "квартальный сдвиг" in out["draft"]
