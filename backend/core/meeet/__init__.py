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
from .events import TARSEvent
from .store import MeeetStore, StoredEvent, get_store, reset_store
from .tracing import current_trace, new_trace_id, start_trace, trace_scope

__all__ = [
    "MeeetClient",
    "MeeetConfig",
    "MeeetStore",
    "StoredEvent",
    "TARSEvent",
    "current_trace",
    "get_client",
    "get_store",
    "load_config",
    "new_trace_id",
    "reset_client",
    "reset_store",
    "start_trace",
    "trace_scope",
]
