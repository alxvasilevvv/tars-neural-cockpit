"""Tests for the strict playbook schema validator.

Three layers:

1. Unit tests against the validator core: top-level keys, step
   shape, action target grammar, ``${steps.<id>...}`` reference
   detection, warning vs. error severity.
2. Smoke: every playbook shipped under ``playbooks/`` must pass
   strict validation. This is the CI gate operators can rely on.
3. HTTP: ``POST /api/playbooks/_validate`` (literal payload + id
   round-trip) and ``GET /api/playbooks/_validate_all``.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------
# Unit: happy path
# ---------------------------------------------------------------------


def _ok_playbook() -> dict:
    return {
        "id": "demo.morning",
        "name": "Demo morning",
        "description": "Demo playbook",
        "pack": "demo",
        "tags": ["smoke"],
        "on_block": "stop",
        "steps": [
            {
                "id": "market",
                "action": "traders.summarize_market",
                "args": {"basket": ["BTC", "ETH"]},
                "store_as": "market",
            },
            {
                "id": "news",
                "action": "traders.awareness.news_feed.snapshot",
                "store_as": "news",
            },
            {
                "id": "report",
                "action": "business.daily_brief",
                "args": {
                    "market": "${steps.market.summary}",
                    "headline": "${steps.news.items.0.title}",
                },
                "when": "${steps.market.summary} != ''",
                "on_error": "continue",
            },
        ],
    }


def test_valid_playbook_passes_with_no_issues():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(_ok_playbook())
    assert res.ok is True
    assert res.errors == ()
    # No warnings on a clean playbook.
    assert res.warnings == ()


def test_minimal_playbook_passes():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "steps": [{"id": "s", "action": "p.a"}],
        }
    )
    assert res.ok is True
    assert res.errors == ()


# ---------------------------------------------------------------------
# Unit: top-level errors
# ---------------------------------------------------------------------


def test_root_must_be_object():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(["not", "an", "object"])
    assert res.ok is False
    codes = [e.code for e in res.errors]
    assert codes == ["playbook_must_be_object"]


def test_missing_id_is_error():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook({"steps": [{"id": "s", "action": "p.a"}]})
    assert res.ok is False
    assert any(e.code == "id_required" for e in res.errors)


def test_id_with_invalid_chars_is_error():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {"id": "no spaces here", "steps": [{"id": "s", "action": "p.a"}]}
    )
    assert res.ok is False
    assert any(e.code == "id_invalid_chars" for e in res.errors)


def test_pack_invalid_slug_is_error():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "pack": "BadPack",
            "steps": [{"id": "s", "action": "p.a"}],
        }
    )
    assert any(e.code == "pack_invalid_slug" for e in res.errors)


def test_tags_must_be_array_of_nonempty_strings():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "tags": "not-an-array",
            "steps": [{"id": "s", "action": "p.a"}],
        }
    )
    assert any(e.code == "tags_must_be_array" for e in res.errors)

    res = validate_playbook(
        {
            "id": "x",
            "tags": ["ok", "", 42],
            "steps": [{"id": "s", "action": "p.a"}],
        }
    )
    codes = [e.code for e in res.errors]
    # Both empty and non-string tags surface.
    assert codes.count("tag_must_be_nonempty_string") == 2


def test_on_block_must_be_known_value():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "on_block": "fly",
            "steps": [{"id": "s", "action": "p.a"}],
        }
    )
    assert any(e.code == "on_block_invalid" for e in res.errors)


def test_unknown_top_level_keys_are_warnings_not_errors():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "owner": "alex",  # unknown
            "steps": [{"id": "s", "action": "p.a"}],
        }
    )
    assert res.ok is True  # warning ≠ error
    assert any(w.code == "unknown_top_level_key" for w in res.warnings)


# ---------------------------------------------------------------------
# Unit: step errors
# ---------------------------------------------------------------------


def test_steps_required():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook({"id": "x"})
    assert any(e.code == "steps_required" for e in res.errors)


def test_steps_must_be_array():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook({"id": "x", "steps": {"not": "an array"}})
    assert any(e.code == "steps_must_be_array" for e in res.errors)


def test_steps_empty_is_error():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook({"id": "x", "steps": []})
    assert any(e.code == "steps_empty" for e in res.errors)


def test_step_must_be_object():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook({"id": "x", "steps": ["string-step"]})
    assert any(e.code == "step_must_be_object" for e in res.errors)


def test_step_missing_id_or_action():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {"id": "x", "steps": [{"action": "p.a"}]}
    )
    assert any(e.code == "step_id_required" for e in res.errors)

    res = validate_playbook(
        {"id": "x", "steps": [{"id": "s"}]}
    )
    assert any(e.code == "action_required" for e in res.errors)


def test_step_id_duplicate_is_error():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "steps": [
                {"id": "s", "action": "p.a"},
                {"id": "s", "action": "p.b"},
            ],
        }
    )
    assert any(e.code == "step_id_duplicate" for e in res.errors)


def test_step_unknown_keys_are_warnings():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "steps": [
                {
                    "id": "s",
                    "action": "p.a",
                    "comment": "ignored field",
                }
            ],
        }
    )
    assert res.ok is True
    assert any(w.code == "unknown_step_key" for w in res.warnings)


def test_args_invalid_type_is_error():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "steps": [{"id": "s", "action": "p.a", "args": 42}],
        }
    )
    assert any(e.code == "args_invalid_type" for e in res.errors)


def test_when_must_be_string():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "steps": [{"id": "s", "action": "p.a", "when": True}],
        }
    )
    assert any(e.code == "when_must_be_string" for e in res.errors)


def test_on_error_must_be_known_value():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "steps": [
                {"id": "s", "action": "p.a", "on_error": "panic"}
            ],
        }
    )
    assert any(e.code == "on_error_invalid" for e in res.errors)


def test_parallel_must_be_bool():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "steps": [
                {"id": "s", "action": "p.a", "parallel": "yes"}
            ],
        }
    )
    assert any(e.code == "parallel_must_be_bool" for e in res.errors)


def test_leading_parallel_is_warning():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "steps": [
                {"id": "a", "action": "p.a", "parallel": True},
                {"id": "b", "action": "p.b"},
            ],
        }
    )
    assert res.ok is True
    assert any(w.code == "leading_parallel_no_op" for w in res.warnings)


# ---------------------------------------------------------------------
# Unit: action target grammar
# ---------------------------------------------------------------------


def test_action_without_dot_is_error():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {"id": "x", "steps": [{"id": "s", "action": "noslug"}]}
    )
    assert any(e.code == "action_malformed" for e in res.errors)


def test_action_slug_must_be_lowercase_snake():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {"id": "x", "steps": [{"id": "s", "action": "Bad-Slug.act"}]}
    )
    assert any(e.code == "action_slug_invalid" for e in res.errors)


def test_action_id_must_match_grammar():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {"id": "x", "steps": [{"id": "s", "action": "pack.Bad ID"}]}
    )
    assert any(e.code == "action_id_invalid" for e in res.errors)


def test_dotted_action_id_is_allowed_for_namespacing():
    """Memory actions look like `pack.memory.set` — the dot is part
    of the id, not a slug separator."""

    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {"id": "x", "steps": [{"id": "s", "action": "business.pack.memory.set"}]}
    )
    assert res.ok is True


def test_awareness_target_happy_path():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "steps": [
                {
                    "id": "s",
                    "action": "traders.awareness.news_feed.snapshot",
                }
            ],
        }
    )
    assert res.ok is True


def test_awareness_target_must_end_with_snapshot():
    from backend.core.playbooks import validate_playbook

    # If the target ends with .snapshot but is missing parts, the
    # validator reports the awareness-specific failure.
    res = validate_playbook(
        {"id": "x", "steps": [{"id": "s", "action": "traders.snapshot"}]}
    )
    assert any(e.code == "action_awareness_malformed" for e in res.errors)


def test_awareness_source_id_can_be_dotted():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "steps": [
                {
                    "id": "s",
                    "action": "traders.awareness.feeds.binance.snapshot",
                }
            ],
        }
    )
    assert res.ok is True


# ---------------------------------------------------------------------
# Unit: cross-step references
# ---------------------------------------------------------------------


def test_unknown_step_reference_warns():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "steps": [
                {
                    "id": "use",
                    "action": "p.a",
                    "args": {"x": "${steps.missing.value}"},
                }
            ],
        }
    )
    assert res.ok is True  # warnings only
    assert any(w.code == "step_ref_unknown" for w in res.warnings)


def test_forward_step_reference_warns():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "steps": [
                {
                    "id": "later",
                    "action": "p.a",
                    "args": {"x": "${steps.next.value}"},
                },
                {"id": "next", "action": "p.b"},
            ],
        }
    )
    assert any(w.code == "step_ref_forward" for w in res.warnings)


def test_backward_reference_is_clean():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "steps": [
                {"id": "first", "action": "p.a"},
                {
                    "id": "second",
                    "action": "p.b",
                    "args": {"x": "${steps.first.value}"},
                },
            ],
        }
    )
    assert res.warnings == ()


def test_self_reference_does_not_warn_as_forward():
    from backend.core.playbooks import validate_playbook

    res = validate_playbook(
        {
            "id": "x",
            "steps": [
                {
                    "id": "self",
                    "action": "p.a",
                    "args": {"x": "${steps.self.value}"},
                }
            ],
        }
    )
    forward = [
        w for w in res.warnings if w.code == "step_ref_forward"
    ]
    assert forward == []


# ---------------------------------------------------------------------
# Smoke: every shipped playbook validates
# ---------------------------------------------------------------------


def test_every_shipped_playbook_passes_strict_validation():
    """CI gate: a malformed bundled playbook should fail this test
    long before it reaches a real operator."""

    from backend.core.playbooks import list_playbooks, validate_playbook

    failures: list[str] = []
    for pb in list_playbooks(refresh=True):
        result = validate_playbook(pb.to_dict())
        if not result.ok:
            failures.append(
                f"{pb.id}: "
                + ", ".join(f"{e.code}@{e.path}" for e in result.errors)
            )
    assert not failures, "\n".join(failures)


# ---------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("MEEET_STORE", "disabled")
    monkeypatch.setenv("MEMORY_STORE", "disabled")

    from fastapi.testclient import TestClient
    from web_extras.app import app

    return TestClient(app)


def test_http_validate_payload_round_trip(client):
    resp = client.post(
        "/api/playbooks/_validate", json={"playbook": _ok_playbook()}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["issue_count"] == 0
    assert body["id"] == "demo.morning"


def test_http_validate_payload_surfaces_errors(client):
    bad = _ok_playbook()
    bad["id"] = "spaces here"  # invalid chars
    resp = client.post("/api/playbooks/_validate", json={"playbook": bad})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    codes = [e["code"] for e in body["errors"]]
    assert "id_invalid_chars" in codes


def test_http_validate_by_id(client):
    """Re-validate a known shipped playbook through the id path."""

    resp = client.post(
        "/api/playbooks/_validate",
        json={"id": "traders.morning_check"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["id"] == "traders.morning_check"


def test_http_validate_id_unknown_returns_404(client):
    resp = client.post(
        "/api/playbooks/_validate",
        json={"id": "definitely.not.a.real.playbook"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "playbook_not_found"


def test_http_validate_rejects_empty_body(client):
    resp = client.post("/api/playbooks/_validate", json={})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "playbook_or_id_required"


def test_http_validate_rejects_both_payload_and_id(client):
    resp = client.post(
        "/api/playbooks/_validate",
        json={"playbook": _ok_playbook(), "id": "demo.morning"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "playbook_and_id_exclusive"


def test_http_validate_all_returns_per_playbook_outcome(client):
    resp = client.get("/api/playbooks/_validate_all")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["error_count"] == 0
    assert body["playbook_count"] >= 1
    for entry in body["playbooks"]:
        assert "id" in entry
        assert "ok" in entry
        assert entry["ok"] is True
