"""Helpers that wire the reports module into the Wave 97 scheduler.

Use case: an operator wants the LP quarterly update auto-generated
on the first business day of every quarter, with FRESH data pulled
each time. We model this as a Wave 97 ``Schedule`` whose
``playbook_id`` is the synthetic identifier ``report:<template_id>``;
the ``args`` bag carries the ``inputs_provider`` slug.

The actual cron tick is owned by Wave 97; this module exposes a
small helper :func:`create_scheduled_report` that operators (or the
router) call to register a schedule, plus :func:`fire_scheduled_report`
which the scheduler runner can dispatch into when the playbook id
prefix is ``report:``.
"""

from __future__ import annotations

import logging
from typing import Any

from .providers import get_provider
from .renderer import render
from .store import ReportStore, get_store


log = logging.getLogger("tars.reports.scheduling")


REPORT_PLAYBOOK_PREFIX = "report:"


def report_playbook_id(template_id: str) -> str:
    """Encode a template id as a synthetic Wave 97 playbook id."""

    return f"{REPORT_PLAYBOOK_PREFIX}{template_id}"


def is_report_playbook(playbook_id: str) -> bool:
    return bool(playbook_id) and playbook_id.startswith(REPORT_PLAYBOOK_PREFIX)


def template_id_from_playbook(playbook_id: str) -> str:
    if not is_report_playbook(playbook_id):
        raise ValueError(f"not_a_report_playbook:{playbook_id}")
    return playbook_id[len(REPORT_PLAYBOOK_PREFIX) :]


async def create_scheduled_report(
    *,
    template_id: str,
    inputs_provider: str,
    cron_expression: str,
    timezone: str = "UTC",
    enabled: bool = True,
) -> dict[str, Any]:
    """Register a recurring schedule that fires this report.

    ``inputs_provider`` is a string handle resolved at fire time via
    :func:`backend.core.reports.providers.get_provider`. The provider
    returns the inputs dict against the template's schema.

    Returns ``{ok, schedule_id?, error?}``.
    """

    store = get_store()
    if not store.enabled:
        return {"ok": False, "error": "reports_store_disabled"}
    template = await store.get_template(template_id)
    if template is None:
        return {"ok": False, "error": "template_not_found"}

    # Validate provider exists up front -- fail fast.
    provider = get_provider(inputs_provider)
    if provider is None:
        return {"ok": False, "error": f"unknown_provider:{inputs_provider}"}

    try:
        from backend.core.scheduler import get_store as get_scheduler_store
    except Exception as exc:
        return {"ok": False, "error": f"scheduler_unavailable:{exc}"}

    sched_store = get_scheduler_store()
    if not sched_store.enabled:
        return {"ok": False, "error": "scheduler_store_disabled"}

    schedule = await sched_store.create_schedule(
        playbook_id=report_playbook_id(template.id),
        cron_expression=cron_expression,
        timezone=timezone,
        args={
            "inputs_provider": inputs_provider,
            "template_id": template.id,
            "template_slug": template.slug,
        },
        enabled=enabled,
    )
    return {"ok": True, "schedule_id": schedule.id}


async def fire_scheduled_report(
    schedule_args: dict[str, Any],
    *,
    store: ReportStore | None = None,
) -> dict[str, Any]:
    """Dispatch hook: run the report with provider-supplied inputs.

    Called by the Wave 97 runner when the synthetic playbook id is
    prefixed with ``report:``. The runner already has the schedule's
    ``args`` bag handy -- we just resolve the provider and call
    :func:`render`.
    """

    s = store or get_store()
    if not s.enabled:
        return {"ok": False, "error": "reports_store_disabled"}
    template_id = schedule_args.get("template_id")
    provider_name = schedule_args.get("inputs_provider")
    if not template_id or not provider_name:
        return {"ok": False, "error": "bad_schedule_args"}

    provider = get_provider(provider_name)
    if provider is None:
        return {"ok": False, "error": f"unknown_provider:{provider_name}"}

    try:
        inputs = await provider()
    except Exception as exc:
        log.warning("reports.scheduling.provider_failed name=%s err=%s", provider_name, exc)
        return {"ok": False, "error": f"provider_failed:{exc}"}

    try:
        run = await render(template_id, inputs, store=s, background=False)
    except Exception as exc:
        log.warning("reports.scheduling.render_failed template=%s err=%s", template_id, exc)
        return {"ok": False, "error": f"render_failed:{exc}"}

    return {"ok": True, "run_id": run.id, "status": run.status}


__all__ = [
    "REPORT_PLAYBOOK_PREFIX",
    "create_scheduled_report",
    "fire_scheduled_report",
    "is_report_playbook",
    "report_playbook_id",
    "template_id_from_playbook",
]
