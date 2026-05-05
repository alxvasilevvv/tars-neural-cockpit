"""Mirror ``usage.tokens`` cloud spend to meeet.world ``POST /operator/usage``."""

from __future__ import annotations

from typing import Any, Mapping

from .client import (
    clear_operator_cache,
    is_remote_billing_configured,
    post_operator_usage_delta,
)

_CLOUD_ROUTES = frozenset({"cloud", "fallback", "mixed"})


async def after_usage_tokens_emitted(
    *,
    route: str | None,
    payload: Mapping[str, Any],
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
    try:
        out = await post_operator_usage_delta(delta)
    except Exception:
        return
    if out.get("ok") is True:
        clear_operator_cache()
