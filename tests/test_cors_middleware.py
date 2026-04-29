"""CORS middleware — production marketing origin allowed for credentialed-free API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from web_extras.app import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_options_api_entitlements_allows_tars_subdomain(client: TestClient) -> None:
    res = client.options(
        "/api/entitlements",
        headers={
            "Origin": "https://tars.meeet.world",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "https://tars.meeet.world"
