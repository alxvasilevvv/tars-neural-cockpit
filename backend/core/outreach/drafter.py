"""Outreach draft generator (Wave 98).

:func:`generate_draft` builds a prompt that fuses three things:

1. The template's ``system_prompt`` (use-case-specific instructions).
2. The operator's AI Clone style profile + nearest-example messages
   (from :mod:`backend.core.clone.style`).
3. The variables in ``context`` (substituted into both the subject
   template and the LLM prompt context).

It then asks the council LLM (``backend.core.council.llm``) to render
the email body. Output is persisted as a ``status='draft'`` row and
returned as a dict.

Cost-tracking: respects the existing entitlements gate
(:func:`backend.core.entitlements.can_run`). On a deny the function
returns a structured failure dict instead of raising -- the router
maps it to a 402.

Honest fallback: if no LLM key is configured the function still
returns a draft (using the operator's nearest-style example as the
body skeleton and a templated subject), with ``fallback=True`` so the
caller can flag it in the UI.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from backend.core.clone import style as clone_style

from .models import OutreachDraft, new_draft_id
from .safety import check_unsubscribe
from .store import OutreachStore, get_store


log = logging.getLogger("tars.outreach.drafter")


_DRAFT_TIMEOUT_S = 30.0
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def _resolve_anthropic_key() -> str | None:
    return (os.getenv("ANTHROPIC_API_KEY") or "").strip() or None


def _resolve_openai_key() -> str | None:
    return (os.getenv("OPENAI_API_KEY") or "").strip() or None


def _post_json(
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    timeout_s: float,
) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json", **headers},
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _render_subject(template: str, context: dict[str, Any]) -> str:
    """Apply ``{{var}}`` substitution against ``context``.

    Missing variables are left to the safety layer -- it'll flag
    untouched braces in the subject.
    """

    if not template:
        return ""
    out = template
    for k, v in (context or {}).items():
        out = out.replace("{{" + str(k) + "}}", str(v))
    return out


def _format_variables_block(context: dict[str, Any]) -> str:
    if not context:
        return "(no variables provided)"
    lines = []
    for k, v in context.items():
        if isinstance(v, (list, tuple)):
            joined = "\n      - " + "\n      - ".join(str(x) for x in v)
            lines.append(f"  - {k}:{joined}")
        else:
            lines.append(f"  - {k}: {v}")
    return "\n".join(lines)


def _format_recipient_block(recipient: dict[str, Any]) -> str:
    name = recipient.get("name") or "(no name)"
    email = recipient.get("email") or ""
    company = recipient.get("company")
    if company:
        return f"{name} <{email}> at {company}"
    return f"{name} <{email}>"


def _build_user_prompt(
    *,
    recipient: dict[str, Any],
    context: dict[str, Any],
    examples: list[str],
    style: clone_style.StyleProfile,
) -> str:
    style_summary = (
        f"avg sentence length: {style.avg_sentence_length:.1f} words; "
        f"casual_vs_formal: {style.casual_vs_formal}; "
        f"top vocab: {', '.join(style.top_vocab[:8]) or '(none yet)'}; "
        f"sample_count: {style.sample_count}."
    )
    ex_block = "\n\n---\n".join(ex.strip() for ex in examples[:5]) if examples else (
        "(no operator examples yet -- write in a measured, professional tone)"
    )
    return (
        f"RECIPIENT: {_format_recipient_block(recipient)}\n\n"
        f"VARIABLES:\n{_format_variables_block(context)}\n\n"
        f"STYLE PROFILE:\n{style_summary}\n\n"
        f"NEAREST OPERATOR EXAMPLES:\n{ex_block}\n\n"
        "Output ONLY the email body (no subject line, no headers, no "
        "salutation outside the body itself). Do not include any "
        "leftover {{variable}} or {variable} placeholders."
    )


def _llm_call_anthropic(*, system: str, user: str) -> str | None:
    key = _resolve_anthropic_key()
    if not key:
        return None
    body = {
        "model": os.getenv("TARS_OUTREACH_MODEL_ANTHROPIC")
        or os.getenv("TARS_CHAT_MODEL_ANTHROPIC")
        or "claude-3-5-sonnet-latest",
        "max_tokens": 1200,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    try:
        payload = _post_json(
            _ANTHROPIC_URL,
            body,
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            timeout_s=_DRAFT_TIMEOUT_S,
        )
        content = payload.get("content") or []
        if isinstance(content, list) and content:
            blk = content[0]
            if isinstance(blk, dict) and isinstance(blk.get("text"), str):
                return blk["text"].strip()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        log.warning("outreach drafter anthropic fail: %s", exc)
    return None


def _llm_call_openai(*, system: str, user: str) -> str | None:
    key = _resolve_openai_key()
    if not key:
        return None
    body = {
        "model": os.getenv("TARS_OUTREACH_MODEL_OPENAI")
        or os.getenv("TARS_CHAT_MODEL_OPENAI")
        or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.7,
    }
    try:
        payload = _post_json(
            _OPENAI_URL,
            body,
            headers={"authorization": f"Bearer {key}"},
            timeout_s=_DRAFT_TIMEOUT_S,
        )
        choices = payload.get("choices") or []
        if isinstance(choices, list) and choices:
            msg = (choices[0] or {}).get("message") or {}
            text = msg.get("content")
            if isinstance(text, str) and text.strip():
                return text.strip()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        log.warning("outreach drafter openai fail: %s", exc)
    return None


async def _entitlements_allow(kind: str = "cloud") -> tuple[bool, str | None]:
    """Wrap the entitlements gate so the drafter never crashes when the
    module is offline (e.g. running tests with no meeet bridge).
    """

    try:
        from backend.core.entitlements import can_run

        result = await can_run(kind=kind)
        if not result.allowed:
            return False, result.reason or "entitlement_denied"
        return True, None
    except Exception as exc:
        log.debug("entitlements gate unavailable in drafter: %s", exc)
        return True, None


async def generate_draft(
    *,
    template_id: str,
    recipient: dict[str, Any],
    context: dict[str, Any] | None = None,
    campaign_id: str | None = None,
    store: OutreachStore | None = None,
    apply_unsubscribe: bool = True,
) -> dict[str, Any]:
    """Generate one draft and persist it as ``status='draft'``.

    Returns ``{"ok": True, "draft": {...}}`` on success, or
    ``{"ok": False, "reason": "...", "detail": "..."}`` on failure.
    The caller is expected to surface the failure reason verbatim.
    """

    s = store or get_store()
    if not s.enabled:
        return {"ok": False, "reason": "store_disabled"}

    template = await s.get_template(template_id)
    if not template:
        return {"ok": False, "reason": "template_not_found", "detail": template_id}

    ctx = dict(context or {})

    allowed, ent_reason = await _entitlements_allow(kind="cloud")
    if not allowed:
        return {"ok": False, "reason": "entitlement_denied", "detail": ent_reason}

    # Pull style profile + nearest examples to seed the prompt. The
    # clone module is best-effort -- if it's disabled the result is a
    # neutral profile, which still works.
    try:
        style = await clone_style.profile()
    except Exception as exc:
        log.debug("clone profile unavailable: %s", exc)
        style = clone_style.StyleProfile(note="clone_unavailable")
    try:
        examples = await clone_style._nearest_examples(  # type: ignore[attr-defined]
            template.system_prompt, k=3
        )
    except Exception:
        examples = []

    user_prompt = _build_user_prompt(
        recipient=recipient,
        context=ctx,
        examples=examples,
        style=style,
    )

    body_text = _llm_call_anthropic(system=template.system_prompt, user=user_prompt)
    fallback = False
    if not body_text:
        body_text = _llm_call_openai(system=template.system_prompt, user=user_prompt)
    if not body_text:
        # Honest fallback: surface a templated skeleton built from the
        # nearest example. Better than silent success on a blank body.
        recipient_name = (recipient or {}).get("name") or "there"
        seed_example = (examples[0].strip() if examples else "")[:400]
        body_text = (
            f"Hi {recipient_name},\n\n"
            f"{seed_example}\n\n"
            "(LLM unreachable -- this is a stylised draft skeleton; please "
            "edit before sending.)"
        )
        fallback = True

    if apply_unsubscribe:
        body_text = check_unsubscribe(body_text)

    subject = _render_subject(template.default_subject_template, ctx)

    draft = OutreachDraft(
        id=new_draft_id(),
        template_id=template.id,
        recipient=dict(recipient or {}),
        context=ctx,
        subject=subject,
        body=body_text,
        status="draft",
        campaign_id=campaign_id,
    )
    try:
        await s.insert_draft(draft)
    except Exception as exc:
        log.warning("outreach drafter insert fail: %s", exc)
        return {"ok": False, "reason": "store_insert_failed", "detail": str(exc)}

    return {
        "ok": True,
        "draft": draft.to_dict(),
        "fallback": fallback,
        "examples_used": len(examples),
        "profile": style.to_dict(),
    }


__all__ = ["generate_draft"]
