"""``GET /api/domains/health`` — per-pack vault-key readiness.

Covers the operator-dashboard endpoint that surfaces which domain
packs have their declared ``auth_vault_keys`` resolved against env +
macOS Keychain. Tests run with the meeet store disabled to keep the
suite hermetic.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_meeet_store(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEEET_STORE", "disabled")
    yield


def _client_get(monkeypatch, path: str):
    from fastapi.testclient import TestClient

    from web_extras.app import app

    with TestClient(app) as client:
        return client.get(path)


# ---------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------


def test_health_returns_ok_with_pack_array(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r = _client_get(monkeypatch, "/api/domains/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["count"] >= 1
    assert isinstance(body["packs"], list)
    sample = body["packs"][0]
    assert {"slug", "name", "ready", "key_count", "available_count",
            "missing", "keys"}.issubset(sample.keys())


def test_health_pack_with_no_keys_is_ready_with_zero_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Packs that declare no auth_vault_keys must surface as
    ready=true, key_count=0 so the cockpit doesn't paint them red.

    None of the in-tree packs hit this branch today, but the path
    matters for future packs that declare zero secrets — assert via
    the raw helper instead of a slug lookup so the contract stays
    pinned even when the pack registry shifts.
    """

    from unittest.mock import patch

    from backend.core.domains.base import DomainManifest, DomainPack

    class _BarePack(DomainPack):
        def __init__(self) -> None:
            self.manifest = DomainManifest(
                slug="bare-test-pack",
                name="Bare Test Pack",
                short="bare",
                description="zero vault keys",
                color="#000000",
                capabilities=(),
                audience=(),
            )

        def auth_vault_keys(self) -> tuple[str, ...]:
            return ()

        def actions(self):
            return ()

        def awareness(self):
            return ()

        def system_prompt(self) -> str:
            return ""

    bare = _BarePack()

    def _augmented():
        from backend.core.domains.registry import all_packs as orig
        return list(orig()) + [bare]

    with patch(
        "web_extras.routers.domains.all_packs", _augmented
    ):
        from fastapi.testclient import TestClient

        from web_extras.app import app
        with TestClient(app) as client:
            r = client.get("/api/domains/health")

    body = r.json()
    by_slug = {p["slug"]: p for p in body["packs"]}
    assert "bare-test-pack" in by_slug
    item = by_slug["bare-test-pack"]
    assert item["ready"] is True
    assert item["key_count"] == 0
    assert item["available_count"] == 0
    assert item["missing"] == []


def test_health_resolves_unprefixed_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting the unprefixed form (e.g. ``SMTP_HOST``) is enough to
    flip ``ready`` for a pack that declares ``SMTP_HOST``."""

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "alice@example.com")

    r = _client_get(monkeypatch, "/api/domains/health")
    body = r.json()
    by_slug = {p["slug"]: p for p in body["packs"]}
    assert "business" in by_slug
    business = by_slug["business"]
    assert business["ready"] is True
    keys = {k["key"]: k for k in business["keys"]}
    assert keys["SMTP_HOST"]["available"] is True
    assert keys["SMTP_HOST"]["source"] in {"env", "keychain"}


def test_health_resolves_tars_prefixed_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``TARS_<KEY>`` is the canonical form the vault helper looks at;
    it should also flip the per-pack readiness flag."""

    monkeypatch.setenv("TARS_SMTP_HOST", "smtp.example.com")

    r = _client_get(monkeypatch, "/api/domains/health")
    body = r.json()
    business = next(
        p for p in body["packs"] if p["slug"] == "business"
    )
    keys = {k["key"]: k for k in business["keys"]}
    assert keys["SMTP_HOST"]["available"] is True


def test_health_missing_array_includes_unset_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Make sure HUBSPOT_API_KEY is unset.
    monkeypatch.delenv("HUBSPOT_API_KEY", raising=False)
    monkeypatch.delenv("TARS_HUBSPOT_API_KEY", raising=False)

    r = _client_get(monkeypatch, "/api/domains/health")
    body = r.json()
    business = next(
        p for p in body["packs"] if p["slug"] == "business"
    )
    assert "HUBSPOT_API_KEY" in business["missing"]


def test_health_per_key_keys_absent_when_omitted_via_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity: the `keys` array is always present; it's an empty
    list for packs without auth_vault_keys."""

    r = _client_get(monkeypatch, "/api/domains/health")
    body = r.json()
    for p in body["packs"]:
        assert "keys" in p
        assert isinstance(p["keys"], list)


def test_health_does_not_leak_secret_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The endpoint surfaces availability + source, never the value."""

    monkeypatch.setenv("SMTP_PASSWORD", "super-secret-app-password")

    r = _client_get(monkeypatch, "/api/domains/health")
    body = r.json()
    raw = r.text
    assert "super-secret-app-password" not in raw
    business = next(
        p for p in body["packs"] if p["slug"] == "business"
    )
    keys = {k["key"]: k for k in business["keys"]}
    if "SMTP_PASSWORD" in keys:
        assert keys["SMTP_PASSWORD"]["available"] is True


def test_health_ready_flag_is_true_when_at_least_one_key_resolves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    r = _client_get(monkeypatch, "/api/domains/health")
    body = r.json()
    business = next(
        p for p in body["packs"] if p["slug"] == "business"
    )
    assert business["ready"] is True
    assert business["available_count"] >= 1


def test_health_count_matches_pack_array_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r = _client_get(monkeypatch, "/api/domains/health")
    body = r.json()
    assert body["count"] == len(body["packs"])


def test_health_endpoint_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two consecutive GETs return the same shape."""

    r1 = _client_get(monkeypatch, "/api/domains/health")
    r2 = _client_get(monkeypatch, "/api/domains/health")
    assert r1.status_code == 200 and r2.status_code == 200
    s1 = sorted(p["slug"] for p in r1.json()["packs"])
    s2 = sorted(p["slug"] for p in r2.json()["packs"])
    assert s1 == s2
