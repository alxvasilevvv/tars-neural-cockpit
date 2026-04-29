"""Single-tenant JSON store for the operator's current tier.

The desktop is single-user — there is no auth boundary, so the entire
store is "the operator". On a fresh install every host is ``free``.

File shape (v1):

    {
      "tier": "pro",
      "byo_enabled": true,
      "upgraded_at": 1745798400.123,
      "operator_alias": null
    }

Anything not understood by a future version is preserved on round-trip.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from .tiers import Tier


def _default_path() -> Path:
    env = os.getenv("TARS_ENTITLEMENTS_PATH")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".tars" / "entitlements.json"


class EntitlementsStore:
    """Thread-safe single-file JSON store. No crypto — tier is not secret."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = (path or _default_path()).resolve()
        self._lock = threading.RLock()

    def _read_raw(self) -> dict[str, Any]:
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
        except FileNotFoundError:
            return {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_raw(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file, then atomic rename. 0o600 perms.
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            # Windows / FAT — best-effort.
            pass
        os.replace(tmp, self.path)

    def load(self) -> Tier:
        with self._lock:
            data = self._read_raw()
            raw = data.get("tier")
            if isinstance(raw, str):
                try:
                    return Tier(raw)
                except ValueError:
                    return Tier.FREE
            return Tier.FREE

    def set_tier(self, tier: Tier, *, byo_enabled: bool | None = None) -> dict[str, Any]:
        """Persist ``tier`` and return the updated record."""

        with self._lock:
            data = self._read_raw()
            data["tier"] = tier.value
            data["upgraded_at"] = time.time()
            if byo_enabled is not None:
                data["byo_enabled"] = bool(byo_enabled)
            data.setdefault("byo_enabled", False)
            self._write_raw(data)
            return data

    def set_byo(self, enabled: bool) -> dict[str, Any]:
        with self._lock:
            data = self._read_raw()
            data.setdefault("tier", Tier.FREE.value)
            data["byo_enabled"] = bool(enabled)
            self._write_raw(data)
            return data

    def snapshot(self) -> dict[str, Any]:
        """Read-only summary of the current state."""

        with self._lock:
            data = self._read_raw()
            data.setdefault("tier", Tier.FREE.value)
            data.setdefault("byo_enabled", False)
            return data


_singleton: EntitlementsStore | None = None
_singleton_lock = threading.Lock()


def get_store() -> EntitlementsStore:
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = EntitlementsStore()
        return _singleton


def reset_store_for_tests(path: Path | None = None) -> EntitlementsStore:
    """Replace the singleton (used by tests with a tmp_path)."""

    global _singleton
    with _singleton_lock:
        _singleton = EntitlementsStore(path=path)
    return _singleton


def load_tier() -> Tier:
    return get_store().load()


def set_tier(tier: Tier, *, byo_enabled: bool | None = None) -> dict[str, Any]:
    return get_store().set_tier(tier, byo_enabled=byo_enabled)
