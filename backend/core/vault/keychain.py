"""macOS Keychain reader for the TARS secrets vault.

Stdlib-only — uses the ``security`` CLI via ``subprocess``. On non-Darwin
hosts the Keychain branch is a no-op and only the env-var path runs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass

DEFAULT_SERVICE = "tars"

#: Keys the host expects to find. The vault never echoes values back —
#: only whether each key resolves.
KNOWN_KEYS: tuple[str, ...] = (
    "TARS_ANTHROPIC_API_KEY",
    "TARS_OPENAI_API_KEY",
    "MEEET_API_KEY",
    "HUBSPOT_API_KEY",
    "PIPEDRIVE_API_KEY",
    "OPENALEX_EMAIL",
)


@dataclass(frozen=True)
class SecretRef:
    """Where a secret resolved from. The value is intentionally not stored."""

    key: str
    source: str  # "env" | "keychain" | "missing"
    available: bool


def _from_env(key: str) -> str | None:
    val = os.environ.get(key)
    if val is None:
        return None
    val = val.strip()
    return val or None


def _from_keychain(
    key: str,
    *,
    service: str = DEFAULT_SERVICE,
    timeout_s: float = 2.0,
) -> str | None:
    if sys.platform != "darwin":
        return None
    if shutil.which("security") is None:
        return None
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-a", service, "-s", key, "-w"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if out.returncode != 0:
        return None
    val = (out.stdout or "").strip()
    return val or None


def get_secret(
    key: str,
    *,
    service: str = DEFAULT_SERVICE,
    timeout_s: float = 2.0,
) -> str | None:
    """Resolve a secret: env first, then Keychain, then ``None``.

    Tests can monkeypatch :func:`_from_env` or :func:`_from_keychain`.
    """

    val = _from_env(key)
    if val is not None:
        return val
    return _from_keychain(key, service=service, timeout_s=timeout_s)


def list_known(*, service: str = DEFAULT_SERVICE) -> list[SecretRef]:
    """Return availability metadata for the well-known keys."""

    out: list[SecretRef] = []
    for key in KNOWN_KEYS:
        env_val = _from_env(key)
        if env_val is not None:
            out.append(SecretRef(key=key, source="env", available=True))
            continue
        kc_val = _from_keychain(key, service=service)
        if kc_val is not None:
            out.append(SecretRef(key=key, source="keychain", available=True))
            continue
        out.append(SecretRef(key=key, source="missing", available=False))
    return out
