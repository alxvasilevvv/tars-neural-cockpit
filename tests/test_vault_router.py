"""HTTP contract for ``GET /api/vault/status``.

Merges ``KNOWN_KEYS`` with every registered pack's ``auth_vault_keys()`` so
extras (e.g. ``SMTP_HOST``) appear with correct source metadata.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.core.domains import packs as _packs  # noqa: F401
from web_extras.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_vault_status_includes_known_and_pack_only_keys(client: TestClient) -> None:
    r = client.get("/api/vault/status")
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    keys = [k["key"] for k in body.get("keys", [])]
    assert "TARS_ANTHROPIC_API_KEY" in keys
    assert "SMTP_HOST" in keys
    assert all("source" in k for k in body["keys"])
    assert body["count"] == len(keys)
