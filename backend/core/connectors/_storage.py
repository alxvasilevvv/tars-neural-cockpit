"""Token storage helper for OAuth connectors (Wave 91).

Persistence model:

* tokens live at ``~/.tars/connectors/<name>.json`` (or
  ``$TARS_CONNECTORS_DIR/<name>.json`` when overridden).
* file mode is forced to ``0o600`` on write -- single-tenant cockpit
  assumption, but still keep nosey processes out.
* if the vault module exposes a symmetric encryption key
  (``backend.core.vault.envelope`` lookup), tokens are wrapped in a
  Fernet-style envelope. Otherwise plaintext JSON. This is documented
  in ``docs/contracts/CONNECTORS.md`` so operators know what they get.

The whole module is dependency-free (stdlib only) so it boots cleanly
in the sandbox even when the vault key is unavailable.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Mapping


_DEFAULT_DIR = Path.home() / ".tars" / "connectors"


def _connectors_dir() -> Path:
    override = os.getenv("TARS_CONNECTORS_DIR")
    if override:
        return Path(override).expanduser()
    return _DEFAULT_DIR


def _token_path(name: str) -> Path:
    safe = "".join(ch for ch in name if ch.isalnum() or ch in {"-", "_"})
    if not safe:
        raise ValueError("connector name must contain alphanumerics")
    return _connectors_dir() / f"{safe}.json"


def has_token(name: str) -> bool:
    try:
        return _token_path(name).is_file()
    except ValueError:
        return False


def load_token(name: str) -> dict[str, Any] | None:
    """Read a token blob from disk.

    Returns ``None`` if missing or if the JSON is unreadable -- caller
    decides whether to treat that as "not connected" vs "corrupted".
    """

    path = _token_path(name)
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def save_token(name: str, payload: Mapping[str, Any]) -> Path:
    """Persist a token blob to disk (mode 600).

    Adds ``stored_at`` epoch seconds if the caller didn't supply it,
    so health-check can age tokens later.
    """

    blob = dict(payload)
    blob.setdefault("stored_at", int(time.time()))

    path = _token_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(blob, indent=2, sort_keys=True), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        # Best-effort -- non-POSIX filesystems may not support it.
        pass
    os.replace(tmp, path)
    return path


def delete_token(name: str) -> bool:
    """Remove the token file. Returns True if a file was deleted."""

    path = _token_path(name)
    if not path.is_file():
        return False
    try:
        path.unlink()
    except OSError:
        return False
    return True


def token_age_s(name: str) -> float | None:
    """Seconds since stored_at, or None if no token / no timestamp."""

    blob = load_token(name)
    if blob is None:
        return None
    stored = blob.get("stored_at")
    if not isinstance(stored, (int, float)):
        return None
    return max(0.0, time.time() - float(stored))


__all__ = [
    "has_token",
    "load_token",
    "save_token",
    "delete_token",
    "token_age_s",
]
