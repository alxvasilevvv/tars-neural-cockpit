"""Local-first secret storage for the TARS host.

This module spans two related but distinct concerns:

1. **Domain pack secrets** — env-vars / macOS Keychain lookup for API
   keys (Anthropic, OpenAI, HubSpot, …). See :mod:`.keychain`.
2. **Host identity vault** — durable storage for the host's long-term
   X25519 keypair so that Phase L5 pairings survive restarts. See
   :mod:`.file_vault`.

Both live behind this single module so callers don't have to learn
two import paths.
"""

from .file_vault import (
    FileKeyringVault,
    KeyringVault,
    StoredHostIdentity,
    VaultCorruptError,
    VaultPermissionError,
)
from .keychain import (
    DEFAULT_SERVICE,
    KNOWN_KEYS,
    SecretRef,
    delete_secret,
    get_secret,
    list_known,
    set_secret,
    status_for_keys,
)

__all__ = [
    # Host identity vault (Phase L5 K1)
    "FileKeyringVault",
    "KeyringVault",
    "StoredHostIdentity",
    "VaultCorruptError",
    "VaultPermissionError",
    # Domain pack secret resolver
    "DEFAULT_SERVICE",
    "KNOWN_KEYS",
    "SecretRef",
    "delete_secret",
    "get_secret",
    "list_known",
    "set_secret",
    "status_for_keys",
]
