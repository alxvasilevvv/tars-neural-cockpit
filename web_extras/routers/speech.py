"""HTTP surface for speech-intents extraction.

`POST /api/speech/intents` accepts a transcript (typed or
dictated) and returns a structured intent so the caller can
dispatch deterministic slash-commands without a chat round-trip.
The route is intentionally thin: parser logic lives in
:mod:`backend.core.speech`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from backend.core.speech import parse_intent
from backend.core.playbooks.loader import list_playbooks


router = APIRouter(prefix="/api/speech", tags=["speech"])


@router.post("/intents")
async def parse_intent_endpoint(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    """Parse one transcript.

    Body: ``{"transcript": "...", "use_playbook_registry": true}``.

    When ``use_playbook_registry`` is true (default), the parser
    consults the loaded playbook ids so ``/run morning_brief``
    routes to ``run_playbook`` instead of being interpreted
    optimistically.
    """

    body = payload or {}
    transcript = str(body.get("transcript") or "").strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="transcript_required")
    if len(transcript) > 4000:
        raise HTTPException(status_code=400, detail="transcript_too_long")

    use_registry = bool(body.get("use_playbook_registry", True))
    known_ids: set[str] | None = None
    if use_registry:
        try:
            known_ids = {pb.id for pb in list_playbooks()}
        except Exception:  # never crash the endpoint on a registry blip
            known_ids = set()

    intent = parse_intent(transcript, known_playbook_ids=known_ids)
    return {"ok": True, "intent": intent.to_dict()}
