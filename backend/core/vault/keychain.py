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
from typing import Iterable

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
    # Wave M1 — web-search domain pack. Optional: when present the
    # pack prefers Brave over SearXNG / DuckDuckGo. Free tier is
    # 2 000 queries/month and only needs an X-Subscription-Token
    # header. See docs/WEB_SEARCH.md.
    "BRAVE_SEARCH_API_KEY",
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


# --------------------------------------------------------- write-back


def _to_keychain(
    key: str,
    value: str,
    *,
    service: str = DEFAULT_SERVICE,
    timeout_s: float = 5.0,
) -> bool:
    """Persist ``key=value`` into the macOS Keychain via the
    ``security`` CLI. Returns ``True`` on success, ``False`` on any
    failure (non-Darwin host, missing CLI, timeout, non-zero exit).

    Uses ``add-generic-password -U`` so the call is idempotent — an
    existing entry with the same ``service`` + ``account`` gets
    overwritten instead of erroring.
    """

    if sys.platform != "darwin":
        return False
    if shutil.which("security") is None:
        return False
    try:
        out = subprocess.run(
            [
                "security",
                "add-generic-password",
                "-a",
                service,
                "-s",
                key,
                "-w",
                value,
                "-U",  # update if exists
            ],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return out.returncode == 0


def _delete_keychain(
    key: str,
    *,
    service: str = DEFAULT_SERVICE,
    timeout_s: float = 5.0,
) -> bool:
    """Drop a Keychain entry. Returns ``True`` if the entry was
    removed, ``False`` if it didn't exist or the call failed."""

    if sys.platform != "darwin":
        return False
    if shutil.which("security") is None:
        return False
    try:
        out = subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-a",
                service,
                "-s",
                key,
            ],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return out.returncode == 0


def set_secret(
    key: str,
    value: str,
    *,
    service: str = DEFAULT_SERVICE,
    timeout_s: float = 5.0,
) -> SecretRef:
    """Write ``key=value`` into the durable vault.

    Resolution order matches :func:`get_secret`:

    - On Darwin with ``security`` available, writes into the Keychain
      under ``service`` and returns ``SecretRef(source="keychain")``.
    - On any platform where the Keychain isn't reachable, sets
      ``os.environ[key]`` so the value is at least available for the
      remainder of the process and returns
      ``SecretRef(source="env")``. The operator should then mirror it
      into their shell config / systemd unit / launchd plist for the
      value to survive a restart.
    - Refuses to write empty values (raises ``ValueError``) — that's
      almost always a programming bug; explicit deletion goes through
      :func:`delete_secret`.

    The function never echoes ``value`` back to the caller — only the
    resolved storage location, so the same return shape as
    :func:`list_known` keeps audit logs free of secret material.
    """

    if not isinstance(key, str) or not key.strip():
        raise ValueError("set_secret: key must be a non-empty string")
    if value is None or not isinstance(value, str) or not value.strip():
        raise ValueError(
            "set_secret: refusing to write an empty value (use delete_secret)"
        )
    key = key.strip()
    value = value.strip()

    if _to_keychain(key, value, service=service, timeout_s=timeout_s):
        return SecretRef(key=key, source="keychain", available=True)

    # Fallback: process-lifetime env so the rest of the app sees the
    # new value immediately. Operator follow-up is responsible for
    # making it durable across restarts.
    os.environ[key] = value
    return SecretRef(key=key, source="env", available=True)


def delete_secret(
    key: str,
    *,
    service: str = DEFAULT_SERVICE,
    timeout_s: float = 5.0,
) -> bool:
    """Drop ``key`` from the vault and ``os.environ``.

    Returns ``True`` when at least one storage location was cleared.
    ``False`` only when the key was already absent everywhere.
    """

    if not isinstance(key, str) or not key.strip():
        raise ValueError("delete_secret: key must be a non-empty string")
    key = key.strip()

    cleared = False
    if _delete_keychain(key, service=service, timeout_s=timeout_s):
        cleared = True
    if key in os.environ:
        del os.environ[key]
        cleared = True
    return cleared


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


def status_for_keys(
    keys: Iterable[str],
    *,
    service: str = DEFAULT_SERVICE,
) -> list[SecretRef]:
    """Resolve availability for an arbitrary subset of vault keys.

    Keys can include identifiers not listed in KNOWN_KEYS — they still
    resolve via env → Keychain the same way.
    """

    out: list[SecretRef] = []
    seen: set[str] = set()
    for raw in keys:
        key = str(raw).strip()
        if not key or key in seen:
            continue
        seen.add(key)
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
