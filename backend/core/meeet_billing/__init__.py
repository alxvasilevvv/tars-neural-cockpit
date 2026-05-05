"""meeet.world authoritative billing mirror (TARS side).

When ``TARS_BILLING_SOURCE=remote``, tier + cloud gate + spend display
are fetched from meeet.world per ``docs/contracts/TARS_MEEET_BILLING.md``.
"""

from .client import (
    clear_operator_cache,
    fetch_operator_snapshot,
    is_remote_billing_configured,
    post_operator_usage_delta,
)

__all__ = [
    "clear_operator_cache",
    "fetch_operator_snapshot",
    "is_remote_billing_configured",
    "post_operator_usage_delta",
]
