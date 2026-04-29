"""Phase M / P7 — role registry + HTTP router + orchestrator hook."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.roles import (
    DEFAULT_ROLES,
    create_custom_role,
    delete_custom_role,
    get_active_role,
    get_role,
    list_roles,
    set_active_role,
    synthesise_overlay,
)
from backend.core.roles.registry import reset_store_for_tests
from web_extras.app import app


@pytest.fixture
def fresh_store(tmp_path: Path) -> Iterator[None]:
    reset_store_for_tests(path=tmp_path / "roles.json")
    try:
        yield
    finally:
        reset_store_for_tests()


@pytest.fixture
def client(fresh_store: None) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


# ─── default roles ────────────────────────────────────────────────────


def test_default_roles_cover_all_six(fresh_store: None) -> None:
    slugs = {r.slug for r in DEFAULT_ROLES}
    assert slugs == {
        "founder",
        "trader",
        "researcher",
        "marketer",
        "engineer",
        "operator",
    }
    for r in DEFAULT_ROLES:
        assert r.overlay, f"empty overlay for {r.slug}"
        assert r.custom is False


def test_get_role_returns_default_for_known_slug(fresh_store: None) -> None:
    role = get_role("trader")
    assert role is not None
    assert role.name == "Trader"
    assert "traders" in role.backing_packs


def test_get_role_returns_none_for_unknown(fresh_store: None) -> None:
    assert get_role("doesnotexist") is None


# ─── synthesis ────────────────────────────────────────────────────────


def test_synthesise_overlay_is_deterministic() -> None:
    a = synthesise_overlay(name="Coach", description="I coach.")
    b = synthesise_overlay(name="Coach", description="I coach.")
    assert a == b


def test_synthesise_overlay_includes_name_and_description() -> None:
    overlay = synthesise_overlay(
        name="Doctor",
        description="I'm a clinical psychologist. I prioritise consent.",
    )
    assert "Doctor" in overlay
    assert "psychologist" in overlay or "consent" in overlay.lower()


def test_synthesise_overlay_lists_backing_packs() -> None:
    overlay = synthesise_overlay(
        name="Founder",
        description="I'm a founder.",
        backing_packs=("entrepreneur", "business"),
    )
    assert "entrepreneur" in overlay
    assert "business" in overlay


# ─── custom roles ─────────────────────────────────────────────────────


def test_create_and_resolve_custom_role(fresh_store: None) -> None:
    role = create_custom_role(
        name="Therapist",
        description="I work with clients in private practice.",
        backing_packs=["business"],
    )
    assert role.custom is True
    assert role.slug.startswith("custom-")
    fetched = get_role(role.slug)
    assert fetched is not None
    assert fetched.name == "Therapist"


def test_custom_role_persists_across_lookups(fresh_store: None) -> None:
    role = create_custom_role(name="Coach", description="I coach.")
    all_now = list_roles()
    assert any(r.slug == role.slug for r in all_now)


def test_create_custom_role_rejects_empty_name(fresh_store: None) -> None:
    with pytest.raises(ValueError):
        create_custom_role(name="   ", description="x")


def test_delete_custom_role(fresh_store: None) -> None:
    role = create_custom_role(name="Tmp", description="tmp")
    assert delete_custom_role(role.slug) is True
    assert get_role(role.slug) is None


def test_cannot_delete_built_in_role(fresh_store: None) -> None:
    with pytest.raises(ValueError):
        delete_custom_role("founder")


# ─── active role ──────────────────────────────────────────────────────


def test_active_role_starts_unset(fresh_store: None) -> None:
    assert get_active_role() is None


def test_set_active_role_persists(fresh_store: None) -> None:
    set_active_role("trader")
    cur = get_active_role()
    assert cur is not None
    assert cur.slug == "trader"


def test_set_active_unknown_raises(fresh_store: None) -> None:
    with pytest.raises(KeyError):
        set_active_role("ghost")


def test_deleting_active_custom_role_clears_active(fresh_store: None) -> None:
    role = create_custom_role(name="X", description="x")
    set_active_role(role.slug)
    delete_custom_role(role.slug)
    assert get_active_role() is None


# ─── HTTP router ──────────────────────────────────────────────────────


def test_get_roles_route(client: TestClient) -> None:
    r = client.get("/api/roles")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["count"] == len(DEFAULT_ROLES)


def test_activate_route(client: TestClient) -> None:
    r = client.post("/api/roles/founder/activate")
    assert r.status_code == 200
    assert r.json()["role"]["slug"] == "founder"
    a = client.get("/api/roles/active").json()
    assert a["role"]["slug"] == "founder"


def test_activate_unknown_returns_404(client: TestClient) -> None:
    r = client.post("/api/roles/ghost/activate")
    assert r.status_code == 404
    assert r.json()["error_code"] == "role_not_found"


def test_create_custom_via_route(client: TestClient) -> None:
    r = client.post(
        "/api/roles",
        json={
            "name": "Producer",
            "description": "I produce music. I value craft.",
            "backing_packs": ["entrepreneur"],
        },
    )
    assert r.status_code == 200
    role = r.json()["role"]
    assert role["custom"] is True
    listing = client.get("/api/roles").json()
    assert any(r2["slug"] == role["slug"] for r2 in listing["roles"])


def test_delete_custom_via_route(client: TestClient) -> None:
    r = client.post(
        "/api/roles",
        json={"name": "Tmp", "description": "tmp"},
    ).json()
    slug = r["role"]["slug"]
    d = client.delete(f"/api/roles/{slug}")
    assert d.status_code == 200
    assert d.json()["slug"] == slug
    miss = client.get(f"/api/roles/{slug}/overlay")
    assert miss.status_code == 404


def test_overlay_route_returns_synthesised_text(client: TestClient) -> None:
    r = client.get("/api/roles/researcher/overlay")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "researcher"
    assert "TARS" in body["overlay"]
    assert "science" in body["overlay"]


def test_delete_default_role_is_400(client: TestClient) -> None:
    r = client.delete("/api/roles/founder")
    assert r.status_code == 400
    assert r.json()["error_code"] == "role_invalid"


# ─── orchestrator overlay hook ────────────────────────────────────────


def test_orchestrator_prepends_role_overlay(fresh_store: None) -> None:
    """When a role is active, its overlay must precede the pack prompt."""

    from backend.core.chat.orchestrator import ChatOrchestrator
    from backend.core.chat.models import Thread

    set_active_role("researcher")
    thread = Thread(
        id="t1",
        title="Test",
        pack_slug="science",
        project_id=None,
        created_at=0.0,
        updated_at=0.0,
    )
    composed = ChatOrchestrator._system_prompt_for(thread)
    assert composed is not None
    assert "Researcher" in composed
    # Pack prompts have a "TARS" header too — make sure the overlay
    # is BEFORE the pack section delimiter.
    if "---" in composed:
        head, _, tail = composed.partition("\n\n---\n\n")
        assert "Researcher" in head
        assert tail  # pack prompt follows


def test_orchestrator_falls_back_to_pack_prompt_with_no_role(
    fresh_store: None,
) -> None:
    from backend.core.chat.orchestrator import ChatOrchestrator
    from backend.core.chat.models import Thread

    thread = Thread(
        id="t2",
        title="Test",
        pack_slug="science",
        project_id=None,
        created_at=0.0,
        updated_at=0.0,
    )
    composed = ChatOrchestrator._system_prompt_for(thread)
    assert composed is not None
    # No role overlay, just pack prompt — no synthesised role header.
    head = composed.split("\n", 1)[0]
    assert "role for this operator" not in head.lower()
