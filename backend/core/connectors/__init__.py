"""Real OAuth-based connectors (Wave 91).

Until Wave 91 the Gmail / Calendar / Slack integrations were stubs
returning ``{messages: []}``-shaped payloads from the awareness pack.
This module promotes them to real read-only connectors backed by the
provider OAuth flows.

Each connector follows the same shape:

* ``is_configured()`` -> ``bool`` -- env vars present
* ``get_auth_url(state=...)`` -> str -- OAuth consent URL
* ``exchange_code(code, state=None)`` -> token dict (also persisted)
* ``has_token()`` -> ``bool`` -- token file present on disk
* a ``Client.from_stored_token()`` factory + read methods

If env vars are missing every method raises
:class:`ConnectorNotConfigured`. Callers (awareness fetchers, router
endpoints) MUST catch this and fall back to the legacy stub so dev /
local installs keep working without OAuth credentials.

Token storage lives at ``~/.tars/connectors/<name>.json`` (mode 600).
The vault key is preferred when available -- see
:func:`backend.core.connectors._storage._token_path`. Plaintext fallback
is documented but discouraged for shared machines.
"""

from __future__ import annotations


class ConnectorNotConfigured(RuntimeError):
    """Raised when env vars for a connector are missing."""


class ConnectorAuthError(RuntimeError):
    """Raised when OAuth handshake fails or stored token is rejected."""


class ConnectorTransportError(RuntimeError):
    """Raised when the upstream API call fails (network / 5xx)."""


__all__ = [
    "ConnectorNotConfigured",
    "ConnectorAuthError",
    "ConnectorTransportError",
]
