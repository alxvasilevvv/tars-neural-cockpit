"""End-to-end tests for the new HTTP surfaces (manifest + usage)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.core.domains import packs as _packs  # noqa: F401
from web_extras.app import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_manifest_endpoint_lists_known_slugs(client: TestClient) -> None:
    res = client.get("/api/domains/manifest")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    slugs = {item["slug"] for item in body["domains"]}
    # Leaf packs.
    for s in ("traders", "business", "mlm", "science"):
        assert s in slugs
    # At least one composite registered (research_lab and ops_room ship).
    assert "research_lab" in slugs or "ops_room" in slugs
    # Composite items must self-identify.
    composites = [d for d in body["domains"] if d["composite"]]
    assert composites, "expected at least one composite in manifest"
    for c in composites:
        assert isinstance(c["composed_of"], list)
        assert c["composed_of"], "composite must list its sub-packs"


def test_manifest_counts_actions_and_destructive(client: TestClient) -> None:
    res = client.get("/api/domains/manifest")
    body = res.json()
    by_slug = {item["slug"]: item for item in body["domains"]}
    business = by_slug["business"]
    assert business["action_count"] >= 1
    assert business["destructive_action_count"] >= 1


def test_manifest_mlm_deprecated_fields(client: TestClient) -> None:
    res = client.get("/api/domains/manifest")
    assert res.status_code == 200
    by_slug = {item["slug"]: item for item in res.json()["domains"]}
    mlm = by_slug["mlm"]
    assert mlm["deprecated"] is True
    assert mlm["deprecated_in_favor_of"] == "entrepreneur"


def test_domains_list_includes_deprecated_columns(client: TestClient) -> None:
    res = client.get("/api/domains")
    assert res.status_code == 200
    domains = res.json()["domains"]
    mlm = next(d for d in domains if d["slug"] == "mlm")
    assert mlm["deprecated"] is True
    assert mlm["deprecated_in_favor_of"] == "entrepreneur"


def test_usage_endpoint_smoke(client: TestClient) -> None:
    res = client.get("/api/usage")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    rollup = body["rollup"]
    # Rollup keys are stable even when there's no data.
    for k in (
        "total_calls",
        "total_tokens_in",
        "total_tokens_out",
        "total_cost_usd",
        "by_model",
        "by_route",
        "by_session",
    ):
        assert k in rollup


def test_usage_prices_endpoint_lists_known_models(client: TestClient) -> None:
    res = client.get("/api/usage/prices")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "openai/gpt-4o-mini" in body["prices"]


def test_usage_lines_endpoint_smoke(client: TestClient) -> None:
    res = client.get("/api/usage/lines?limit=5")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "lines" in body
