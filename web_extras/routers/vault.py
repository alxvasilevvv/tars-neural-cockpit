"""Read-only HTTP surface over the secrets vault.

- ``GET /api/vault/status`` — returns availability for every well-known
  key plus any name declared by a registered domain pack via
  :meth:`~backend.core.domains.base.DomainPack.auth_vault_keys`
  (``env`` / ``keychain`` / ``missing``). Values are NEVER echoed.

The cockpit uses this to render per-pack auth badges (e.g. council
voices show "anthropic: keychain" or "openai: missing") and SMTP keys.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.core.domains.registry import all_packs
from backend.core.vault import KNOWN_KEYS, status_for_keys

router = APIRouter(prefix="/api/vault", tags=["vault"])


def _merged_vault_key_order() -> list[str]:
    """``KNOWN_KEYS`` first, then any pack-declared keys not yet listed."""

    out: list[str] = []
    seen: set[str] = set()
    for k in KNOWN_KEYS:
        if k not in seen:
            out.append(k)
            seen.add(k)
    for pack in all_packs():
        for k in pack.auth_vault_keys():
            if k not in seen:
                out.append(k)
                seen.add(k)
    return out


@router.get("/status")
async def status() -> dict[str, Any]:
    refs = status_for_keys(_merged_vault_key_order())
    return {
        "ok": True,
        "count": len(refs),
        "keys": [
            {"key": r.key, "source": r.source, "available": r.available}
            for r in refs
        ],
    }
