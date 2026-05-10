"""Pre-built starter templates for the outreach module (Wave 98).

Five starter templates ship with TARS so a fresh operator can draft an
LP update without first writing their own prompt:

1. ``lp_update``    quarterly update to limited partners.
2. ``founder_dd``   founder-DD reach-out after a deck review.
3. ``intro``        warm intro to a portfolio company.
4. ``follow_up``    7+ day no-reply nudge.
5. ``welcome_lp``   onboarding a new LP after the wire lands.

Each template's ``system_prompt`` instructs the LLM to mimic the
operator's existing AI Clone style profile + apply the template
variables. The drafter (:mod:`backend.core.outreach.drafter`) layers
the actual style examples + variable values on top at draft time.

The seeder is idempotent (the store upserts by slug), so calling it on
every cold-start is safe.
"""

from __future__ import annotations

from typing import Any

from .models import OutreachTemplate
from .store import OutreachStore, get_store


# Each starter uses the same closing instruction so the LLM doesn't
# leave placeholder braces in the body. The safety layer also verifies
# this, but a clear instruction up front meaningfully reduces retries.
_NO_PLACEHOLDERS = (
    "Never leave template placeholders like {{name}} or {variable} in the "
    "final text. If a variable is missing, work around it gracefully."
)


def _starter_lp_update() -> dict[str, Any]:
    return {
        "name": "Quarterly LP update",
        "slug": "lp_update",
        "use_case": "lp_update",
        "default_subject_template": "{{quarter}} update -- portfolio + outlook",
        "variables": [
            "quarter",
            "aum_change",
            "top_3_wins",
            "headwinds",
            "next_quarter",
        ],
        "system_prompt": (
            "You are drafting a quarterly LP update email IN THE OPERATOR'S "
            "VOICE. Mimic the cadence, sentence length, and casual/formal "
            "balance from the supplied style profile + example messages.\n\n"
            "Structure: short greeting, one-paragraph state-of-the-fund "
            "(use ``aum_change`` + ``quarter``), three bulleted wins "
            "(``top_3_wins``), one honest paragraph on headwinds, then a "
            "forward-looking paragraph (``next_quarter``). Close with the "
            "operator's usual sign-off. Aim for 200-280 words. " + _NO_PLACEHOLDERS
        ),
    }


def _starter_founder_dd() -> dict[str, Any]:
    return {
        "name": "Founder DD reach-out",
        "slug": "founder_dd",
        "use_case": "founder_dd",
        "default_subject_template": "Quick follow-up on {{company}}",
        "variables": ["founder_name", "company", "key_points", "meeting_request"],
        "system_prompt": (
            "You are drafting a founder DD reach-out IN THE OPERATOR'S VOICE "
            "after a deck review. Open with a specific reference to the "
            "deck (use ``company``), call out the three concrete points "
            "(``key_points`` -- treat as a 3-bullet list inline or as "
            "prose, whichever the operator's style prefers), then make the "
            "meeting ask (``meeting_request``). Keep it warm, specific, "
            "and under 180 words. Address ``founder_name`` by first name. "
            + _NO_PLACEHOLDERS
        ),
    }


def _starter_intro() -> dict[str, Any]:
    return {
        "name": "Warm portfolio intro",
        "slug": "intro",
        "use_case": "intro",
        "default_subject_template": "intro: {{intro_party}} <> {{recipient_party}}",
        "variables": [
            "intro_party",
            "recipient_party",
            "mutual_context",
            "ask",
        ],
        "system_prompt": (
            "You are drafting a warm intro email IN THE OPERATOR'S VOICE. "
            "Address both parties by first name in the opener "
            "(``intro_party`` and ``recipient_party``). One short paragraph "
            "explaining the context (``mutual_context``), one short "
            "paragraph on what each party does, then a clear ask "
            "(``ask``) with no obligation pressure. Sign off in the "
            "operator's usual register. 120-180 words. " + _NO_PLACEHOLDERS
        ),
    }


def _starter_follow_up() -> dict[str, Any]:
    return {
        "name": "Gentle follow-up",
        "slug": "follow_up",
        "use_case": "follow_up",
        "default_subject_template": "Re: {{original_thread_subject}}",
        "variables": ["original_thread_subject", "original_ask", "urgency"],
        "system_prompt": (
            "You are drafting a follow-up nudge IN THE OPERATOR'S VOICE "
            "after 7+ days of no reply. Keep it short -- 60-100 words. "
            "Reference the original ask (``original_ask``) without "
            "repeating it verbatim. Match the urgency level (``urgency`` "
            "is one of low / medium / high; calibrate tone accordingly -- "
            "low = soft check-in, high = explicit deadline reminder). "
            "Never accuse the recipient of ignoring you. " + _NO_PLACEHOLDERS
        ),
    }


def _starter_welcome_lp() -> dict[str, Any]:
    return {
        "name": "New LP welcome",
        "slug": "welcome_lp",
        "use_case": "welcome_lp",
        "default_subject_template": "Welcome aboard, {{lp_name}}",
        "variables": ["lp_name", "commit_amount", "first_call_date"],
        "system_prompt": (
            "You are drafting a welcome email to a new LP IN THE OPERATOR'S "
            "VOICE after their commitment wire has landed. Open warmly "
            "(address ``lp_name`` by first name), confirm the commit "
            "(``commit_amount`` -- formatted as currency), set "
            "expectations (next quarterly update cadence + the first call "
            "on ``first_call_date``), then a single closing line that "
            "invites them to reach out directly. 130-170 words. " + _NO_PLACEHOLDERS
        ),
    }


def starter_specs() -> list[dict[str, Any]]:
    """Return the five starter templates as plain dicts."""

    return [
        _starter_lp_update(),
        _starter_founder_dd(),
        _starter_intro(),
        _starter_follow_up(),
        _starter_welcome_lp(),
    ]


async def seed_starter_templates(
    store: OutreachStore | None = None,
) -> list[OutreachTemplate]:
    """Idempotently upsert the five starter templates into the DB.

    Returns the persisted templates. Safe to call on every cold start
    (the store upserts by slug -- existing rows have their prompt /
    variables refreshed to the latest spec, but the ``id`` and
    ``created_at`` are preserved so the FE doesn't see ID churn).
    """

    s = store or get_store()
    if not s.enabled:
        return []
    out: list[OutreachTemplate] = []
    for spec in starter_specs():
        tpl = await s.upsert_template(
            name=spec["name"],
            slug=spec["slug"],
            use_case=spec["use_case"],
            system_prompt=spec["system_prompt"],
            variables=spec["variables"],
            default_subject_template=spec["default_subject_template"],
        )
        out.append(tpl)
    return out


__all__ = [
    "seed_starter_templates",
    "starter_specs",
]
