"""Mirror ``usage.tokens`` cloud spend to meeet.world ``POST /operator/usage``."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from .client import (
    clear_operator_cache,
    is_remote_billing_configured,
    post_operator_usage_delta,
)

_CLOUD_ROUTES = frozenset({"cloud", "fallback", "mixed"})
_log = logging.getLogger(__name__)


async def after_usage_tokens_emitted(
    *,
    route: str | None,
    payload: Mapping[str, Any],
    trace_id: str | None = None,
) -> None:
    """Fire-and-forget billing mirror; must never raise."""

    if not is_remote_billing_configured():
        return
    if (route or "").strip().lower() not in _CLOUD_ROUTES:
        return
    raw = payload.get("cost_usd")
    if raw is None:
        return
    try:
        delta = float(raw)
    except (TypeError, ValueError):
        return
    if delta <= 0:
        return
    tid = trace_id
    if not tid:
        pt = payload.get("trace_id")
        if isinstance(pt, str) and pt.strip():
            tid = pt.strip()[:256]
    try:
        out = await post_operator_usage_delta(delta, trace_id=tid)
    except Exception as exc:
        _log.warning("billing_usage_mirror_failed trace=%s err=%s", tid, exc)
        return
    if out.get("ok") is True:
        clear_operator_cache()
        return
    _log.warning("billing_usage_mirror_rejected trace=%s response=%s", tid, out)
