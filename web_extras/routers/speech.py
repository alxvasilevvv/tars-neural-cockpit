"""HTTP surface for speech-intents extraction.

`POST /api/speech/intents` accepts a transcript (typed or
dictated) and returns a structured intent so the caller can
dispatch deterministic slash-commands without a chat round-trip.
The route is intentionally thin: parser logic lives in
:mod:`backend.core.speech`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException

from backend.core.meeet import get_client as get_meeet_client, new_trace_id, trace_scope
from backend.core.playbooks.loader import list_playbooks
from backend.core.speech import parse_intent


router = APIRouter(prefix="/api/speech", tags=["speech"])


@router.post("/intents")
async def parse_intent_endpoint(
    payload: dict[str, Any] | None = Body(default=None),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    """Parse one transcript.

    Body: ``{"transcript": "...", "use_playbook_registry": true}``.

    When ``use_playbook_registry`` is true (default), the parser
    consults the loaded playbook ids so ``/run morning_brief``
    routes to ``run_playbook`` instead of being interpreted
    optimistically.

    2026-05-04 audit-2: every parse runs inside a meeet
    ``trace_scope`` and emits
    ``speech.intent.{requested,completed,failed}`` so dictated
    commands are observable in the trail next to chat / voice.
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

    parent_trace = (x_meeet_trace_id or "").strip() or None
    trace_id = parent_trace or new_trace_id()
    meeet = get_meeet_client()
    base_payload = {
        "transcript_len": len(transcript),
        "use_playbook_registry": use_registry,
        "known_playbooks": len(known_ids) if known_ids is not None else None,
    }

    with trace_scope(trace_id):
        await meeet.emit("speech.intent.requested", base_payload)
        try:
            intent = parse_intent(transcript, known_playbook_ids=known_ids)
        except Exception as exc:
            await meeet.emit(
                "speech.intent.failed",
                {**base_payload, "error": str(exc)[:200]},
            )
            raise

        intent_dict = intent.to_dict()
        await meeet.emit(
            "speech.intent.completed",
            {
                **base_payload,
                "intent_kind": intent_dict.get("kind"),
                "intent_target": intent_dict.get("target"),
            },
        )

    return {"ok": True, "intent": intent_dict, "trace_id": trace_id}
