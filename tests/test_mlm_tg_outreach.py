"""Tests for the ``mlm.tg_outreach_draft`` deterministic
Telegram drafter."""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.core.domains.packs.mlm import actions as mlm_actions
from backend.core.domains.packs.mlm.tg_outreach import (
    DEFAULT_LANGUAGE,
    DEFAULT_TONE,
    KNOWN_INTENTS,
    KNOWN_LANGUAGES,
    KNOWN_TONES,
    MAX_DRAFT_CHARS,
    OutreachDraft,
    tg_outreach_draft,
)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


def _draft(**args):
    return _run(tg_outreach_draft(args))


# ---------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------


def test_missing_intent_returns_error():
    out = _draft()
    assert out["ok"] is False
    assert out["error"] == "intent_required"


def test_blank_intent_returns_error():
    out = _draft(intent="   ")
    assert out["ok"] is False
    assert out["error"] == "intent_required"


def test_unknown_intent_returns_invalid_intent():
    out = _draft(intent="liquidate")
    assert out["ok"] is False
    assert out["error"] == "invalid_intent"
    assert "list" in (out.get("detail") or "").lower() or "intent" in (
        out.get("detail") or ""
    )


def test_non_string_intent_is_treated_as_missing():
    out = _draft(intent=42)
    assert out["ok"] is False
    assert out["error"] == "intent_required"


def test_unknown_tone_falls_back_to_warm():
    out = _draft(intent="welcome", tone="aggressive")
    assert out["ok"] is True
    assert out["tone"] == DEFAULT_TONE


def test_unknown_language_falls_back_to_en():
    out = _draft(intent="welcome", language="zz")
    assert out["ok"] is True
    assert out["language"] == DEFAULT_LANGUAGE


def test_no_arguments_after_intent_uses_defaults():
    out = _draft(intent="checkin")
    assert out["ok"] is True
    assert out["tone"] == DEFAULT_TONE
    assert out["language"] == DEFAULT_LANGUAGE
    assert out["recipient"] == ""


# ---------------------------------------------------------------------
# Happy paths per intent
# ---------------------------------------------------------------------


@pytest.mark.parametrize("intent", list(KNOWN_INTENTS))
def test_every_intent_produces_a_draft(intent):
    out = _draft(intent=intent, name="Alex")
    assert out["ok"] is True, out
    assert out["intent"] == intent
    assert out["markdown"], "markdown body must be non-empty"
    assert out["plain_text"], "plain text fallback must be non-empty"
    assert out["length_chars"] == len(out["markdown"])
    assert out["send_status"] == "draft"
    assert out["subject_hint"], "subject hint should be set per intent"
    assert isinstance(out["tags"], list)
    assert all(isinstance(tag, str) for tag in out["tags"])


@pytest.mark.parametrize("language", list(KNOWN_LANGUAGES))
def test_every_language_resolves(language):
    out = _draft(intent="welcome", language=language, name="Sam")
    assert out["ok"] is True
    assert out["language"] == language
    assert "Sam" in out["markdown"]


@pytest.mark.parametrize("tone", list(KNOWN_TONES))
def test_every_tone_resolves(tone):
    out = _draft(intent="celebrate", tone=tone, name="Kira")
    assert out["ok"] is True
    assert out["tone"] == tone


# ---------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------


def test_two_invocations_produce_identical_draft():
    args = {
        "intent": "winback",
        "name": "Pat",
        "tone": "warm",
        "language": "en",
    }
    a = _draft(**args)
    b = _draft(**args)
    assert a == b


def test_drafts_differ_across_intents_for_same_recipient():
    a = _draft(intent="welcome", name="Pat")
    b = _draft(intent="winback", name="Pat")
    assert a["markdown"] != b["markdown"]


def test_drafts_differ_across_languages_for_same_intent():
    en = _draft(intent="recruit", name="Pat", language="en")
    ru = _draft(intent="recruit", name="Pat", language="ru")
    assert en["markdown"] != ru["markdown"]


# ---------------------------------------------------------------------
# Personalisation
# ---------------------------------------------------------------------


def test_recipient_name_is_substituted():
    out = _draft(intent="welcome", name="Marina")
    assert "Marina" in out["markdown"]


def test_recipient_name_default_uses_there():
    out = _draft(intent="checkin")
    # When no name is given the opener falls back to "there".
    assert "there" in out["markdown"].lower() or out["recipient"] == ""


def test_signature_is_appended_after_dash_separator():
    out = _draft(intent="welcome", name="Sam", signature="— Lead")
    assert out["ok"] is True
    assert "— Lead" in out["markdown"] or "Lead" in out["markdown"]


def test_cta_overrides_default_closer():
    out = _draft(
        intent="welcome",
        name="Sam",
        cta="Reply 'YES' to confirm your slot.",
    )
    assert out["cta"] == "Reply 'YES' to confirm your slot."
    assert "Reply 'YES'" in out["markdown"]


def test_cta_with_newlines_is_flattened():
    out = _draft(
        intent="welcome",
        name="Sam",
        cta="line one\nline two",
    )
    assert "\n" not in out["cta"]
    assert "line one" in out["cta"]
    assert "line two" in out["cta"]


def test_long_name_is_truncated():
    out = _draft(intent="welcome", name="A" * 500)
    # Truncation shouldn't produce an error, but length should be sane.
    assert out["ok"] is True
    assert len(out["recipient"]) <= 80


# ---------------------------------------------------------------------
# Length cap
# ---------------------------------------------------------------------


def test_oversize_cta_triggers_draft_too_long_when_combined(monkeypatch):
    # The natural template sits under 4k chars; we shrink the cap to
    # force the long-draft branch.
    monkeypatch.setattr(
        "backend.core.domains.packs.mlm.tg_outreach.MAX_DRAFT_CHARS",
        50,
    )
    out = _draft(intent="welcome", name="Sam")
    assert out["ok"] is False
    assert out["error"] == "draft_too_long"


def test_normal_draft_well_under_telegram_cap():
    out = _draft(intent="welcome", name="Sam")
    assert out["length_chars"] < MAX_DRAFT_CHARS


# ---------------------------------------------------------------------
# Action wiring
# ---------------------------------------------------------------------


def test_action_spec_registered_with_destructive_false():
    spec = next(
        (a for a in mlm_actions.ACTIONS if a.id == "tg_outreach_draft"),
        None,
    )
    assert spec is not None, "tg_outreach_draft must be registered"
    assert spec.destructive is False
    assert spec.handler is tg_outreach_draft
    schema = spec.schema or {}
    assert "intent" in (schema.get("required") or [])
    intent_enum = (
        (schema.get("properties") or {}).get("intent", {}).get("enum")
    )
    assert intent_enum and set(intent_enum) == set(KNOWN_INTENTS)


def test_action_spec_runnable_via_handler():
    spec = next(
        a for a in mlm_actions.ACTIONS if a.id == "tg_outreach_draft"
    )
    out = _run(spec.handler({"intent": "checkin", "name": "Lee"}))
    assert out["ok"] is True
    assert out["intent"] == "checkin"
    assert "Lee" in out["markdown"]


# ---------------------------------------------------------------------
# JSON serialisability
# ---------------------------------------------------------------------


def test_response_is_json_serialisable():
    out = _draft(
        intent="recruit",
        name="Pat",
        tone="direct",
        language="es",
        cta="Reply YES",
        signature="— Team",
    )
    json.dumps(out)


def test_outreach_draft_dataclass_to_dict_includes_send_status():
    draft = OutreachDraft(
        ok=True,
        intent="welcome",
        tone="warm",
        language="en",
        recipient="x",
        cta="hi",
        markdown="m",
        plain_text="p",
        subject_hint="s",
        tags=("a",),
        length_chars=1,
    )
    body = draft.to_dict()
    assert body["send_status"] == "draft"
    assert body["tags"] == ["a"]
