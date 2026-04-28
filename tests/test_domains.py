"""Smoke tests for domain packs.

These tests only depend on the stdlib + ``backend.core.domains`` and intentionally
do not import the FastAPI router, so they keep working even if the host app is
mid-refactor.
"""

from __future__ import annotations

import asyncio

import pytest

from backend.core.domains import all_packs, get_pack
from backend.core.domains import packs as _packs  # noqa: F401 (registers)

EXPECTED_SLUGS = {"traders", "business", "mlm", "science"}


def test_all_expected_packs_registered() -> None:
    slugs = {p.manifest.slug for p in all_packs()}
    missing = EXPECTED_SLUGS - slugs
    assert not missing, f"missing packs: {missing}"


@pytest.mark.parametrize("slug", sorted(EXPECTED_SLUGS))
def test_pack_to_dict_shape(slug: str) -> None:
    pack = get_pack(slug)
    assert pack is not None
    payload = pack.to_dict()
    for key in (
        "slug",
        "name",
        "short",
        "description",
        "color",
        "capabilities",
        "audience",
        "actions",
        "awareness",
        "auth",
    ):
        assert key in payload, f"missing key {key} in {slug}"
    assert payload["slug"] == slug
    assert payload["color"].startswith("#")
    assert isinstance(payload["actions"], list) and payload["actions"]
    assert isinstance(payload["awareness"], list) and payload["awareness"]
    assert isinstance(payload["auth"], dict)
    assert isinstance(payload["auth"].get("keys"), list)


@pytest.mark.parametrize("slug", sorted(EXPECTED_SLUGS))
def test_action_handlers_are_safe_with_empty_args(slug: str) -> None:
    pack = get_pack(slug)
    assert pack is not None
    for spec in pack.actions():
        result = asyncio.run(spec.handler({}))
        assert isinstance(result, dict) or hasattr(result, "items")
        # All handlers must always return a mapping with an "ok" boolean,
        # never raise on empty input.
        assert "ok" in result, f"{slug}.{spec.id} missing ok"
