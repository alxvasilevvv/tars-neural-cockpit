"""Tests for the ``backend.core.speech`` intent parser + HTTP route.

Two layers:

1. Unit tests for ``parse_intent`` covering the intent vocabulary
   (run_action / run_playbook / jump / search / snooze / help /
   none), wake-word stripping, voice-form handling, JSON args
   parsing, and error surfaces.
2. HTTP tests for ``POST /api/speech/intents`` including the
   playbook-registry hint and validation errors.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------


def test_empty_transcript_returns_none_intent():
    from backend.core.speech import parse_intent

    intent = parse_intent("")
    assert intent.kind == "none"
    assert intent.consumed is False
    assert intent.cleaned == ""

    # Whitespace-only is identical.
    intent = parse_intent("   \n\t  ")
    assert intent.kind == "none"
    assert intent.consumed is False


def test_wake_word_only_consumes_silently():
    from backend.core.speech import parse_intent

    intent = parse_intent("TARS")
    assert intent.kind == "none"
    assert intent.consumed is True
    # Operator just got TARS's attention with no payload — there is
    # nothing to forward to the LLM.
    assert intent.cleaned == ""


def test_chat_text_returns_none_with_residual():
    """Plain chat must fall through with cleaned == wake-stripped
    transcript so the caller can hand it to the LLM."""

    from backend.core.speech import parse_intent

    intent = parse_intent("TARS, tell me about Mars")
    assert intent.kind == "none"
    assert intent.consumed is False
    assert intent.cleaned == "tell me about Mars"


def test_canonical_run_action_target():
    from backend.core.speech import parse_intent

    intent = parse_intent("/run traders.morning_check")
    assert intent.kind == "run_action"
    assert intent.target == "traders.morning_check"
    assert intent.confidence == 1.0
    assert intent.error is None
    assert intent.args == {}


def test_run_action_with_json_args():
    from backend.core.speech import parse_intent

    intent = parse_intent('/run business.kpi_snapshot {"path": "x.json"}')
    assert intent.kind == "run_action"
    assert intent.target == "business.kpi_snapshot"
    assert intent.args == {"path": "x.json"}
    assert intent.error is None


def test_run_action_with_invalid_json_args_surfaces_error():
    from backend.core.speech import parse_intent

    intent = parse_intent("/run business.kpi_snapshot {bad json}")
    assert intent.kind == "run_action"
    assert intent.target == "business.kpi_snapshot"
    assert intent.error == "invalid_json_args"


def test_run_action_args_must_be_object():
    from backend.core.speech import parse_intent

    intent = parse_intent('/run x.y {"not_an_array": true}')
    # JSON object ✓
    assert intent.args == {"not_an_array": True}

    intent = parse_intent("/run x.y [1, 2, 3]")
    # leading "[" is not "{" so it's silently treated as no args
    # (the parser only attempts JSON when the body looks like an
    # object). Args land as {} with no error.
    assert intent.args == {}
    assert intent.error is None


def test_voice_run_form_with_dot_keyword():
    from backend.core.speech import parse_intent

    intent = parse_intent("/run traders dot morning check")
    assert intent.kind == "run_action"
    assert intent.target == "traders.morning_check"
    # voice form lowers confidence vs canonical.
    assert 0.5 <= intent.confidence < 1.0


def test_voice_run_form_without_dot():
    from backend.core.speech import parse_intent

    intent = parse_intent("TARS, run traders morning check")
    assert intent.kind == "run_action"
    assert intent.target == "traders.morning_check"
    # voice form via wake word AND no canonical dot → low confidence.
    assert intent.confidence < 0.7


def test_run_action_missing_target():
    from backend.core.speech import parse_intent

    intent = parse_intent("/run")
    assert intent.kind == "run_action"
    assert intent.target is None
    assert intent.error == "run_target_required"
    assert intent.confidence == 0.0


def test_run_playbook_resolves_against_registry():
    from backend.core.speech import parse_intent

    intent = parse_intent(
        "/run morning_brief", known_playbook_ids={"morning_brief"}
    )
    assert intent.kind == "run_playbook"
    assert intent.target == "morning_brief"


def test_run_dotted_resolves_to_playbook_when_in_registry():
    """If the transcript looks like a pack.action AND it's a known
    playbook id, the playbook wins — operators can reference
    namespaced playbooks (``traders.morning_check``) without
    ambiguity."""

    from backend.core.speech import parse_intent

    intent = parse_intent(
        "/run traders.morning_check",
        known_playbook_ids={"traders.morning_check"},
    )
    assert intent.kind == "run_playbook"
    assert intent.target == "traders.morning_check"


def test_run_playbook_optimistic_dispatch_without_registry():
    """If the parser has no registry to consult and the body is a
    bare token (no dot), we optimistically dispatch as a playbook
    so the runner can give a real error instead of double-routing
    via the LLM."""

    from backend.core.speech import parse_intent

    intent = parse_intent("/run morning_brief")
    assert intent.kind == "run_playbook"
    assert intent.target == "morning_brief"
    # Optimistic dispatch lowers confidence so the cockpit can
    # surface a confirm prompt.
    assert intent.confidence < 0.8


def test_run_playbook_with_empty_registry_rejects_unknown():
    """When the registry is provided and empty, the parser must
    refuse a bare-token playbook reference rather than guess."""

    from backend.core.speech import parse_intent

    intent = parse_intent("/run morning_brief", known_playbook_ids=set())
    assert intent.kind == "run_action"
    assert intent.target is None
    assert intent.error == "run_target_unrecognised"


def test_jump_with_query():
    from backend.core.speech import parse_intent

    intent = parse_intent("/jump research lab")
    assert intent.kind == "jump"
    assert intent.query == "research lab"
    assert intent.error is None

    intent2 = parse_intent("Hey TARS, jump to research lab")
    assert intent2.kind == "jump"
    assert intent2.query == "research lab"


def test_jump_missing_query():
    from backend.core.speech import parse_intent

    intent = parse_intent("/jump")
    assert intent.kind == "jump"
    assert intent.error == "jump_query_required"
    assert intent.confidence == 0.0


def test_search_with_query():
    from backend.core.speech import parse_intent

    intent = parse_intent("/search openai gpt-4o pricing")
    assert intent.kind == "search"
    assert intent.query == "openai gpt-4o pricing"

    intent2 = parse_intent("TARS search for openai gpt-4o pricing")
    assert intent2.kind == "search"
    assert intent2.query == "openai gpt-4o pricing"


def test_search_missing_query():
    from backend.core.speech import parse_intent

    intent = parse_intent("/search")
    assert intent.kind == "search"
    assert intent.error == "search_query_required"


def test_snooze_with_duration():
    from backend.core.speech import parse_intent

    intent = parse_intent("/snooze srch_abc for 2 hours")
    assert intent.kind == "snooze"
    assert intent.target == "srch_abc"
    assert intent.duration_s == 7200
    assert intent.error is None


def test_snooze_supports_minute_and_day_units():
    from backend.core.speech import parse_intent

    assert parse_intent("/snooze srch_x for 30 minutes").duration_s == 1800
    assert parse_intent("/snooze srch_x for 30m").duration_s == 1800
    assert parse_intent("/snooze srch_x for 1 day").duration_s == 86400
    assert parse_intent("/snooze srch_x for 2 weeks").duration_s == (
        2 * 7 * 86400
    )


def test_snooze_missing_duration_surfaces_error():
    from backend.core.speech import parse_intent

    intent = parse_intent("/snooze srch_abc")
    assert intent.kind == "snooze"
    assert intent.target == "srch_abc"
    assert intent.duration_s is None
    assert intent.error == "snooze_duration_missing"


def test_snooze_missing_target_surfaces_error():
    from backend.core.speech import parse_intent

    intent = parse_intent("/snooze")
    assert intent.kind == "snooze"
    assert intent.target is None
    assert intent.error == "snooze_target_required"


def test_help_slash_and_voice():
    from backend.core.speech import parse_intent

    assert parse_intent("/help").kind == "help"
    assert parse_intent("TARS, help").kind == "help"
    assert parse_intent("TARS, what can you do?").kind == "help"
    assert parse_intent("TARS, commands").kind == "help"


def test_unknown_slash_verb_falls_through():
    from backend.core.speech import parse_intent

    intent = parse_intent("/foo bar")
    assert intent.kind == "none"
    assert intent.error == "unknown_verb:foo"
    assert intent.consumed is False


def test_wake_word_variants_all_strip():
    from backend.core.speech import parse_intent

    for prefix in [
        "Hey TARS,",
        "Ok TARS",
        "OKAY TARS,",
        "TARS please",
        "Computer,",
        "Hey computer",
        "Jarvis",
    ]:
        intent = parse_intent(f"{prefix} jump research")
        assert intent.kind == "jump", f"failed for prefix {prefix!r}"
        assert intent.query == "research"


def test_to_dict_serialises_all_fields():
    from backend.core.speech import parse_intent

    intent = parse_intent("/run traders.morning_check")
    d = intent.to_dict()
    assert d["kind"] == "run_action"
    assert d["target"] == "traders.morning_check"
    assert d["args"] == {}
    assert d["query"] is None
    assert d["duration_s"] is None
    assert d["consumed"] is True
    assert d["confidence"] == 1.0
    assert d["error"] is None
    assert d["raw"] == "/run traders.morning_check"


def test_known_kinds_exposed():
    from backend.core.speech import KNOWN_KINDS

    assert set(KNOWN_KINDS) == {
        "run_action",
        "run_playbook",
        "jump",
        "search",
        "snooze",
        "help",
        "none",
    }


# ---------------------------------------------------------------------
# HTTP tests
# ---------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Spin up the FastAPI app with isolated stores."""

    monkeypatch.setenv("MEEET_STORE", "disabled")
    monkeypatch.setenv("MEMORY_STORE", "disabled")
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv(
        "TARS_ATTACHMENT_ROOT", str(tmp_path / "attachments")
    )

    from fastapi.testclient import TestClient
    from web_extras.app import app

    return TestClient(app)


def test_http_parse_intent_success(client, monkeypatch):
    """An action target that is *not* a registered playbook stays
    a ``run_action`` intent end-to-end."""

    from web_extras.routers import speech as speech_router

    monkeypatch.setattr(speech_router, "list_playbooks", lambda: [])

    resp = client.post(
        "/api/speech/intents",
        json={"transcript": "/run traders.morning_check"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["intent"]["kind"] == "run_action"
    assert body["intent"]["target"] == "traders.morning_check"


def test_http_jump_intent_round_trip(client):
    resp = client.post(
        "/api/speech/intents",
        json={"transcript": "/jump research lab"},
    )
    assert resp.status_code == 200
    intent = resp.json()["intent"]
    assert intent["kind"] == "jump"
    assert intent["query"] == "research lab"


def test_http_rejects_empty_transcript(client):
    resp = client.post("/api/speech/intents", json={"transcript": ""})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "transcript_required"


def test_http_rejects_oversize_transcript(client):
    resp = client.post(
        "/api/speech/intents",
        json={"transcript": "x" * 5000},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "transcript_too_long"


def test_http_rejects_missing_body(client):
    resp = client.post("/api/speech/intents", json={})
    assert resp.status_code == 400


def test_http_default_uses_playbook_registry(monkeypatch, client):
    """With ``use_playbook_registry`` defaulting to True, the route
    consults loaded playbook ids. We patch ``list_playbooks`` to
    register a known id and assert routing flips from optimistic
    ``run_playbook`` to a verified one."""

    from web_extras.routers import speech as speech_router

    class _FakePB:
        def __init__(self, pid: str):
            self.id = pid

    monkeypatch.setattr(
        speech_router, "list_playbooks", lambda: [_FakePB("morning_brief")]
    )

    resp = client.post(
        "/api/speech/intents",
        json={"transcript": "/run morning_brief"},
    )
    assert resp.status_code == 200
    intent = resp.json()["intent"]
    assert intent["kind"] == "run_playbook"
    assert intent["target"] == "morning_brief"
    # registry-confirmed targets get full confidence.
    assert intent["confidence"] == 1.0


def test_http_disabling_registry_falls_back_to_optimistic(client):
    resp = client.post(
        "/api/speech/intents",
        json={
            "transcript": "/run morning_brief",
            "use_playbook_registry": False,
        },
    )
    assert resp.status_code == 200
    intent = resp.json()["intent"]
    # Without a registry the parser optimistically dispatches as a
    # playbook with reduced confidence.
    assert intent["kind"] == "run_playbook"
    assert intent["confidence"] < 0.8


def test_http_registry_error_does_not_crash(monkeypatch, client):
    """A flapping playbook loader should not bring down the
    endpoint — the route swallows the error and falls through to
    the empty-registry path."""

    from web_extras.routers import speech as speech_router

    def _boom():
        raise RuntimeError("loader exploded")

    monkeypatch.setattr(speech_router, "list_playbooks", _boom)

    resp = client.post(
        "/api/speech/intents",
        json={"transcript": "/run morning_brief"},
    )
    assert resp.status_code == 200
    intent = resp.json()["intent"]
    # Empty registry → unknown playbook → run_target_unrecognised.
    assert intent["kind"] == "run_action"
    assert intent["error"] == "run_target_unrecognised"
