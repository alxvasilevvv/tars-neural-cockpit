"""Read-only HTTP surface over the secrets vault.

- ``GET /api/vault/status`` — returns availability for the well-known
  keys (``env`` / ``keychain`` / ``missing``). Values are NEVER echoed.

The cockpit uses this to render per-pack auth badges (e.g. council
voices show "anthropic: keychain" or "openai: missing").
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.core.vault import list_known

router = APIRouter(prefix="/api/vault", tags=["vault"])


@router.get("/status")
async def status() -> dict[str, Any]:
    refs = list_known()
    return {
        "ok": True,
        "count": len(refs),
        "keys": [
            {"key": r.key, "source": r.source, "available": r.available}
            for r in refs
        ],
    }
