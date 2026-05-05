"""Commercial-readiness chain — one sweep of HTTP surfaces a paying
operator relies on (no marketing pages).

These are **GET-only**, hermetic, and ordered so a single failure
pinpoints which subsystem regressed before a release or demo.

Complements :mod:`tests.test_e2e_smoke` (wallet/pairing/agent depth)
with **product + governance + observability** breadth.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from web_extras.app import app

    return TestClient(app)


def test_commercial_surface_chain_public_get_routers(client: TestClient) -> None:
    """Sweep critical read APIs the cockpit + installers + audit trail depend on."""

    # 1) Domain packs — discovery + static manifest + one pack detail
    r_dom = client.get("/api/domains")
    assert r_dom.status_code == 200, r_dom.text
    dj = r_dom.json()
    assert isinstance(dj.get("domains"), list)
    assert len(dj["domains"]) >= 1
    first_slug = dj["domains"][0]["slug"]
    assert first_slug

    r_man = client.get("/api/domains/manifest")
    assert r_man.status_code == 200, r_man.text
    mj = r_man.json()
    assert mj["ok"] is True
    assert mj["count"] >= 1
    assert isinstance(mj["domains"], list)
    assert mj["domains"][0]["slug"]

    r_pack = client.get(f"/api/domains/{first_slug}")
    assert r_pack.status_code == 200, r_pack.text
    pj = r_pack.json()
    assert pj["slug"] == first_slug

    r_dh = client.get("/api/domains/health")
    assert r_dh.status_code == 200, r_dh.text
    assert r_dh.json()["ok"] is True

    # 2) Entitlements + usage ledger — caps / sellability contracts
    r_ent = client.get("/api/entitlements")
    assert r_ent.status_code == 200, r_ent.text
    ej = r_ent.json()
    assert ej["ok"] is True
    assert ej["tier"] in {"free", "pro", "business"}
    assert "caps" in ej
    assert "live" in ej

    r_use = client.get("/api/usage")
    assert r_use.status_code == 200, r_use.text
    uj = r_use.json()
    assert uj["ok"] is True
    assert "rollup" in uj

    # 3) Product / downloads — same wire the Install page + Tauri updater use
    r_dl = client.get("/api/product/downloads")
    assert r_dl.status_code == 200, r_dl.text
    assert r_dl.headers.get("X-Tars-Contract")
    dlj = r_dl.json()
    assert dlj["ok"] is True
    assert "releases" in dlj or "channel" in dlj

    r_ver = client.get("/api/product/version")
    assert r_ver.status_code == 200, r_ver.text
    vj = r_ver.json()
    assert vj.get("ok") is True or "version" in vj

    # 4) Policy queue — destructive actions must remain confirmable
    r_pol = client.get("/api/policy/pending")
    assert r_pol.status_code == 200, r_pol.text
    polj = r_pol.json()
    assert polj["ok"] is True
    assert "pending" in polj

    # 5) Meeet bridge observability — local black box + health
    r_ms = client.get("/api/meeet/stats")
    assert r_ms.status_code == 200, r_ms.text
    msj = r_ms.json()
    assert "enabled" in msj

    r_mh = client.get("/api/meeet/health")
    assert r_mh.status_code == 200, r_mh.text
    mhj = r_mh.json()
    assert mhj.get("ok") is True
    assert "client" in mhj
    assert "store" in mhj

    # 6) Playbooks catalog — automation SKU surface
    r_pb = client.get("/api/playbooks")
    assert r_pb.status_code == 200, r_pb.text
    pbj = r_pb.json()
    assert pbj.get("ok") is True
    assert isinstance(pbj.get("playbooks"), list)


def test_legacy_download_redirects_resolve(client: TestClient) -> None:
    """B-001 legacy filenames must 302 to a real GitHub release asset (install funnel)."""

    r = client.get("/dl/TARS-9.1.0-arm64.dmg", follow_redirects=False)
    assert r.status_code == 302
    assert "github.com" in (r.headers.get("location") or "")

    r2 = client.get("/install.sh", follow_redirects=False)
    assert r2.status_code == 302
    assert "install" in (r2.headers.get("location") or "").lower()
