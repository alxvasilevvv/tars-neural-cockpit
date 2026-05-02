"""TARS ↔ meeet.world bridge.

The bridge gives TARS a single ``trace_id`` per request that travels through
the local stack and into meeet.world ingest. The contract follows the
``x_meeet_contract_version`` pin used by every meeet-aligned product.

Usage::

    from backend.core.meeet import get_client, start_trace, current_trace

    trace = start_trace()
    await get_client().emit("domain.action.invoked", {"slug": "traders"})
    print(current_trace())

The client is a no-op when ``MEEET_INGEST_URL`` is unset, which means the
bridge is safe to import in tests and offline environments.
"""

from .client import MeeetClient, get_client, reset_client
from .config import MeeetConfig, load_config
from .events import (
    BASELINE_CONTRACT_VERSION,
    ENCRYPTED_CONTRACT_VERSION,
    TARSEvent,
)
from .store import MeeetStore, StoredEvent, get_store, reset_store
from .trace_summary import (
    TraceSummary,
    TraceSummaryStore,
    get_trace_summary_store,
    reset_trace_summary_store,
)
from .tracing import (
    async_session_scope,
    current_route,
    current_session,
    current_thread_id,
    current_trace,
    new_session_id,
    new_trace_id,
    session_scope,
    set_route,
    start_trace,
    thread_id_scope,
    trace_scope,
)

__all__ = [
    "BASELINE_CONTRACT_VERSION",
    "ENCRYPTED_CONTRACT_VERSION",
    "MeeetClient",
    "MeeetConfig",
    "MeeetStore",
    "StoredEvent",
    "TARSEvent",
    "TraceSummary",
    "TraceSummaryStore",
    "async_session_scope",
    "current_route",
    "current_session",
    "current_thread_id",
    "current_trace",
    "get_client",
    "get_store",
    "get_trace_summary_store",
    "load_config",
    "new_session_id",
    "new_trace_id",
    "reset_client",
    "reset_store",
    "reset_trace_summary_store",
    "session_scope",
    "set_route",
    "start_trace",
    "thread_id_scope",
    "trace_scope",
]
