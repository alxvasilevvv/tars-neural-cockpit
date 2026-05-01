"""Tests for the system-wide ``pack.memory.*`` action family.

The memory subsystem ships in two slices:

1. The storage core in ``backend/core/memory/`` (PR #56).
2. The system-injected actions in this slice — every domain pack
   auto-inherits the same ``pack.memory.*`` API.

These tests pin the *injection* layer and the dispatch path: the
storage core is exercised end-to-end via the ``business`` pack, and
the composite hop (``research_lab``) is verified to flatten
sub-pack memory actions under ``<sub_slug>__pack.memory.*``.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolated_memory_db(monkeypatch, tmp_path: Path):
    """Pin the memory DB to a tmp file per test.

    Without this every test run would mutate ``~/.tars/memory.sqlite``
    on the developer's machine — the chat / meeet stores already
    follow this pattern.
    """

    db = tmp_path / "memory.sqlite"
    monkeypatch.setenv("TARS_MEMORY_DB_PATH", str(db))
    monkeypatch.setenv("MEEET_STORE", "disabled")
    from backend.core.memory import store as memory_store_mod
    monkeypatch.setattr(memory_store_mod, "_SINGLETON", None, raising=False)
    yield
    monkeypatch.setattr(memory_store_mod, "_SINGLETON", None, raising=False)


# ---------------------------------------------------------------------
# Direct factory tests — pin the action surface
# ---------------------------------------------------------------------


def test_memory_actions_returns_six_actions():
    from backend.core.domains.memory_actions import memory_actions

    actions = memory_actions("test_pack")
    assert len(actions) == 6
    ids = [a.id for a in actions]
    assert ids == [
        "pack.memory.set",
        "pack.memory.get",
        "pack.memory.list",
        "pack.memory.delete",
        "pack.memory.purge_expired",
        "pack.memory.stats",
    ]


def test_memory_actions_only_delete_is_destructive():
    from backend.core.domains.memory_actions import memory_actions

    actions = {a.id: a for a in memory_actions("test_pack")}
    assert actions["pack.memory.delete"].destructive is True
    for k in ("set", "get", "list", "purge_expired", "stats"):
        assert actions[f"pack.memory.{k}"].destructive is False, k


def test_memory_actions_have_schema():
    """Schema is non-empty for inputs that require validation —
    cockpit form-builder uses this to render the input UI.
    """

    from backend.core.domains.memory_actions import memory_actions

    actions = {a.id: a for a in memory_actions("test_pack")}
    set_schema = actions["pack.memory.set"].schema
    assert set_schema["type"] == "object"
    assert "key" in set_schema["required"]
    assert "value" in set_schema["required"]


# ---------------------------------------------------------------------
# Pack injection — every registered pack has the family
# ---------------------------------------------------------------------


def test_every_registered_pack_has_memory_actions():
    """The whole point of this slice — uniform memory contract."""

    import backend.core.domains.packs  # register
    from backend.core.domains.registry import all_packs

    for pack in all_packs():
        ids = {a.id for a in pack.all_actions()}
        for sys_id in (
            "pack.memory.set",
            "pack.memory.get",
            "pack.memory.list",
            "pack.memory.delete",
            "pack.memory.purge_expired",
            "pack.memory.stats",
        ):
            assert sys_id in ids, (pack.manifest.slug, sys_id, ids)


def test_pack_actions_iterator_excludes_memory_actions():
    """``pack.actions()`` (the abstract iterator) stays clean — only
    ``pack.all_actions()`` includes the system-injected ones.
    """

    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    business = get_pack("business")
    own_ids = {a.id for a in business.actions()}
    assert "pack.memory.set" not in own_ids


def test_find_action_resolves_memory_actions():
    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    business = get_pack("business")
    spec = business.find_action("pack.memory.set")
    assert spec is not None
    assert spec.id == "pack.memory.set"


# ---------------------------------------------------------------------
# Handlers — closure binds to the right slug
# ---------------------------------------------------------------------


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_set_then_get_round_trip():
    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    business = get_pack("business")
    set_spec = business.find_action("pack.memory.set")
    get_spec = business.find_action("pack.memory.get")

    set_res = asyncio.run(
        set_spec.handler({"key": "kpi.q1", "value": {"revenue": 12_345}})
    )
    assert set_res["ok"] is True
    assert set_res["pack_slug"] == "business"
    assert set_res["entry"]["value"] == {"revenue": 12_345}

    get_res = asyncio.run(get_spec.handler({"key": "kpi.q1"}))
    assert get_res["ok"] is True
    assert get_res["found"] is True
    assert get_res["entry"]["value"] == {"revenue": 12_345}


def test_get_missing_returns_found_false():
    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    business = get_pack("business")
    spec = business.find_action("pack.memory.get")

    res = asyncio.run(spec.handler({"key": "does.not.exist"}))
    assert res["ok"] is True
    assert res["found"] is False
    assert "entry" not in res


def test_set_validates_required_args():
    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    business = get_pack("business")
    spec = business.find_action("pack.memory.set")

    no_key = asyncio.run(spec.handler({"value": 1}))
    assert no_key["ok"] is False
    assert "key" in no_key["error"]

    no_value = asyncio.run(spec.handler({"key": "x"}))
    assert no_value["ok"] is False
    assert "value" in no_value["error"]


def test_set_validates_metadata_type():
    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    business = get_pack("business")
    spec = business.find_action("pack.memory.set")

    res = asyncio.run(
        spec.handler({"key": "x", "value": 1, "metadata": "not a dict"})
    )
    assert res["ok"] is False
    assert "metadata" in res["error"]


def test_set_with_ttl_seconds_evicts():
    """``ttl_seconds`` is relative — past TTL is filtered by default."""

    import time
    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    business = get_pack("business")
    set_spec = business.find_action("pack.memory.set")
    get_spec = business.find_action("pack.memory.get")

    # Tiny TTL, sleep past it.
    asyncio.run(
        set_spec.handler({"key": "ephemeral", "value": 1, "ttl_seconds": 0.05})
    )
    time.sleep(0.1)
    res = asyncio.run(get_spec.handler({"key": "ephemeral"}))
    assert res["found"] is False


def test_set_with_ttl_until_in_past_evicts():
    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    business = get_pack("business")
    set_spec = business.find_action("pack.memory.set")
    get_spec = business.find_action("pack.memory.get")

    asyncio.run(
        set_spec.handler(
            {"key": "expired", "value": 1, "ttl_until": 1.0}  # 1970-01-01
        )
    )
    res = asyncio.run(get_spec.handler({"key": "expired"}))
    assert res["found"] is False
    res2 = asyncio.run(
        get_spec.handler({"key": "expired", "include_expired": True})
    )
    assert res2["found"] is True


def test_set_rejects_both_ttl_args():
    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    business = get_pack("business")
    spec = business.find_action("pack.memory.set")

    res = asyncio.run(
        spec.handler(
            {"key": "x", "value": 1, "ttl_seconds": 60, "ttl_until": 99999}
        )
    )
    assert res["ok"] is False
    assert "mutually exclusive" in res["error"]


def test_set_rejects_non_positive_ttl_seconds():
    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    business = get_pack("business")
    spec = business.find_action("pack.memory.set")

    res = asyncio.run(spec.handler({"key": "x", "value": 1, "ttl_seconds": 0}))
    assert res["ok"] is False
    assert "ttl_seconds" in res["error"]


def test_list_returns_only_pack_partition():
    """Smoke for the partitioning invariant via the action layer."""

    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    business = get_pack("business")
    science = get_pack("science")
    set_b = business.find_action("pack.memory.set")
    set_s = science.find_action("pack.memory.set")
    list_b = business.find_action("pack.memory.list")

    asyncio.run(set_b.handler({"key": "shared.key", "value": "biz"}))
    asyncio.run(set_s.handler({"key": "shared.key", "value": "sci"}))

    res = asyncio.run(list_b.handler({}))
    assert res["ok"] is True
    assert res["count"] == 1
    assert res["entries"][0]["pack_slug"] == "business"
    assert res["entries"][0]["value"] == "biz"


def test_list_kind_and_prefix_filter():
    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    business = get_pack("business")
    set_spec = business.find_action("pack.memory.set")
    list_spec = business.find_action("pack.memory.list")

    asyncio.run(set_spec.handler({"key": "kpi.q1", "value": 1, "kind": "fact"}))
    asyncio.run(set_spec.handler({"key": "kpi.q2", "value": 2, "kind": "fact"}))
    asyncio.run(set_spec.handler({"key": "note.x", "value": 3, "kind": "note"}))

    by_kind = asyncio.run(list_spec.handler({"kind": "note"}))
    assert by_kind["count"] == 1
    assert by_kind["entries"][0]["key"] == "note.x"

    by_prefix = asyncio.run(list_spec.handler({"key_prefix": "kpi."}))
    assert by_prefix["count"] == 2


def test_delete_removes_and_returns_flag():
    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    business = get_pack("business")
    set_spec = business.find_action("pack.memory.set")
    del_spec = business.find_action("pack.memory.delete")
    get_spec = business.find_action("pack.memory.get")

    asyncio.run(set_spec.handler({"key": "tmp", "value": 1}))
    res = asyncio.run(del_spec.handler({"key": "tmp"}))
    assert res["ok"] is True
    assert res["deleted"] is True

    again = asyncio.run(del_spec.handler({"key": "tmp"}))
    assert again["deleted"] is False

    gone = asyncio.run(get_spec.handler({"key": "tmp"}))
    assert gone["found"] is False


def test_purge_expired_only_drops_past_ttl():
    import time
    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    business = get_pack("business")
    set_spec = business.find_action("pack.memory.set")
    purge_spec = business.find_action("pack.memory.purge_expired")
    list_spec = business.find_action("pack.memory.list")

    asyncio.run(set_spec.handler({"key": "live", "value": 1}))
    asyncio.run(
        set_spec.handler({"key": "soon", "value": 2, "ttl_seconds": 0.05})
    )
    time.sleep(0.1)

    res = asyncio.run(purge_spec.handler({}))
    assert res["ok"] is True
    assert res["deleted"] == 1
    assert res["pack_slug"] == "business"

    listed = asyncio.run(list_spec.handler({}))
    keys = {e["key"] for e in listed["entries"]}
    assert keys == {"live"}


def test_stats_breaks_down_by_kind():
    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    business = get_pack("business")
    set_spec = business.find_action("pack.memory.set")
    stats_spec = business.find_action("pack.memory.stats")

    asyncio.run(set_spec.handler({"key": "a", "value": 1, "kind": "fact"}))
    asyncio.run(set_spec.handler({"key": "b", "value": 2, "kind": "fact"}))
    asyncio.run(set_spec.handler({"key": "c", "value": 3, "kind": "draft"}))

    stats = asyncio.run(stats_spec.handler({}))
    assert stats["ok"] is True
    assert stats["pack_slug"] == "business"
    assert stats["total"] == 3
    assert stats["live"] == 3
    assert stats["expired"] == 0
    assert stats["kinds"] == {"fact": 2, "draft": 1}


# ---------------------------------------------------------------------
# Composite packs — sub-pack memory hop
# ---------------------------------------------------------------------


def test_composite_pack_namespaces_sub_pack_memory_actions():
    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    rl = get_pack("research_lab")
    if rl is None:
        pytest.skip("research_lab composite not registered")

    # Composite has its own memory partition + each sub-pack's
    # ``<slug>__pack.memory.*`` namespaced.
    ids = {a.id for a in rl.all_actions()}
    assert "pack.memory.set" in ids  # composite's own
    assert "business__pack.memory.set" in ids
    assert "science__pack.memory.set" in ids


def test_composite_sub_pack_memory_writes_into_sub_pack_partition():
    """The namespaced action's handler is the sub-pack's *own* memory
    set — i.e. writing through ``business__pack.memory.set`` lands in
    the ``business`` partition, not the composite's.
    """

    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    rl = get_pack("research_lab")
    if rl is None:
        pytest.skip("research_lab composite not registered")
    business = get_pack("business")

    sub_set = rl.find_action("business__pack.memory.set")
    biz_get = business.find_action("pack.memory.get")

    asyncio.run(
        sub_set.handler({"key": "deal.beta", "value": "from-composite"})
    )
    res = asyncio.run(biz_get.handler({"key": "deal.beta"}))
    assert res["found"] is True
    assert res["entry"]["pack_slug"] == "business"
    assert res["entry"]["value"] == "from-composite"


def test_pack_slug_override_writes_into_target_partition():
    """``pack_slug`` arg lets a caller redirect into another pack
    without going through the composite's namespaced action.
    """

    import backend.core.domains.packs  # register
    from backend.core.domains.registry import get_pack

    business = get_pack("business")
    science = get_pack("science")
    biz_set = business.find_action("pack.memory.set")
    sci_get = science.find_action("pack.memory.get")

    asyncio.run(
        biz_set.handler(
            {"key": "lead.x", "value": "via-override", "pack_slug": "science"}
        )
    )
    res = asyncio.run(sci_get.handler({"key": "lead.x"}))
    assert res["found"] is True


# ---------------------------------------------------------------------
# Manifest / domain HTTP surface — reflects the injected actions
# ---------------------------------------------------------------------


@pytest.fixture
def http_client():
    from web_extras.app import app
    return TestClient(app)


def test_domain_describe_includes_memory_actions(http_client: TestClient):
    res = http_client.get("/api/domains/business")
    assert res.status_code == 200
    body = res.json()
    ids = {a["id"] for a in body["actions"]}
    for sys_id in (
        "pack.memory.set",
        "pack.memory.get",
        "pack.memory.list",
        "pack.memory.delete",
        "pack.memory.purge_expired",
        "pack.memory.stats",
    ):
        assert sys_id in ids


def test_manifest_action_count_includes_memory_actions(
    http_client: TestClient,
):
    res = http_client.get("/api/domains/manifest")
    body = res.json()
    by_slug = {p["slug"]: p for p in body["domains"]}
    business = by_slug["business"]
    assert business["action_count"] >= 6
    assert business["destructive_action_count"] >= 1


def test_invoke_pack_memory_set_via_http(
    http_client: TestClient, monkeypatch
):
    """Round-trip: POST set → POST get hits the same partition."""

    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")
    res = http_client.post(
        "/api/domains/business/actions/pack.memory.set",
        json={"key": "via.http", "value": {"a": 1}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["result"]["ok"] is True

    got = http_client.post(
        "/api/domains/business/actions/pack.memory.get",
        json={"key": "via.http"},
    )
    body2 = got.json()
    assert body2["result"]["found"] is True
    assert body2["result"]["entry"]["value"] == {"a": 1}


def test_invoke_pack_memory_delete_routes_through_policy_gate(
    http_client: TestClient, monkeypatch
):
    """``pack.memory.delete`` is destructive — confirm-mode (default)
    queues it via the policy gate instead of running immediately.
    """

    monkeypatch.setenv("TARS_POLICY_MODE", "confirm")
    res = http_client.post(
        "/api/domains/business/actions/pack.memory.delete",
        json={"key": "anything"},
    )
    assert res.status_code == 200
    body = res.json()["result"]
    # Either the policy gate queued it (allowed=False, token issued)
    # or autopilot allowed it; the contract is that the response
    # carries a ``policy`` block when blocked.
    assert "policy" in body
    assert body["policy"]["mode"] == "confirm"
    assert body["policy"]["allowed"] is False
    assert body["policy"]["confirmation_token"]


def test_invoke_pack_memory_delete_in_autopilot_runs_immediately(
    http_client: TestClient, monkeypatch
):
    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")
    # Seed something to delete
    http_client.post(
        "/api/domains/business/actions/pack.memory.set",
        json={"key": "deleteme", "value": 1},
    )
    res = http_client.post(
        "/api/domains/business/actions/pack.memory.delete",
        json={"key": "deleteme"},
    )
    body = res.json()["result"]
    assert body["ok"] is True
    assert body["deleted"] is True
