"""W209 — Weekly digest HTTP router.

Two endpoints:
  POST /api/digest/run        — generate the weekly digest now
  GET  /api/digest/latest     — read ~/.tars/reflection_latest.json

Designed so the scheduler can hit /run on Sunday 9am cron and the
cockpit can render /latest in the STATUS tab.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.core.playbooks.weekly_digest import run_weekly_digest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/digest", tags=["digest"])


class RunRequest(BaseModel):
    channels: Optional[list[str]] = Field(
        default=None,
        description="Override fanout channels (default reads TARS_DIGEST_CHANNELS env).",
    )


@router.post("/run")
async def run(req: RunRequest | None = None) -> dict[str, Any]:
    """Generate the weekly digest now. Best-effort fanout to channels."""
    channels = req.channels if req else None
    result = await run_weekly_digest(channels=channels)
    return result


@router.get("/latest")
async def latest() -> dict[str, Any]:
    """Return the last-generated reflection JSON if one exists."""
    p = Path(os.path.expanduser("~")) / ".tars" / "reflection_latest.json"
    if not p.exists():
        return {"ok": True, "exists": False, "hint": "Run POST /api/digest/run to generate."}
    try:
        body = json.loads(p.read_text())
        return {"ok": True, "exists": True, **body}
    except Exception as exc:
        return {"ok": False, "error": "read_failed", "message": str(exc)}
