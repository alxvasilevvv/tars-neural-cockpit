"""Local secrets vault for TARS.

Hierarchy of resolution:

1. Environment variable with the literal key name.
2. macOS Keychain entry under service ``tars`` and account = key name
   (e.g. ``security add-generic-password -a tars -s TARS_ANTHROPIC_API_KEY -w sk-...``).
3. ``None`` — caller must handle.

The vault is intentionally narrow: read-only, no writes from the app.
The user adds entries with the ``security`` CLI; we only fetch them.
"""

from .keychain import (
    KNOWN_KEYS,
    SecretRef,
    get_secret,
    list_known,
)

__all__ = [
    "KNOWN_KEYS",
    "SecretRef",
    "get_secret",
    "list_known",
]
