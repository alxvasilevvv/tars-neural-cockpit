"""HTTP surface for the chat + attachment layer (Phase L1 + L2).

Endpoints:

- ``POST /api/chat/threads`` — create a thread.
- ``GET /api/chat/threads`` — list threads (filter by archived/pack).
- ``GET /api/chat/threads/{id}`` — describe one thread + recent messages.
- ``PATCH /api/chat/threads/{id}`` — rename / archive / pin a pack /
  pin a voice persona.
- ``DELETE /api/chat/threads/{id}`` — soft delete = archive.
- ``GET /api/chat/threads/{id}/messages`` — paginated history.
- ``POST /api/chat/threads/{id}/messages`` — start an assistant turn,
  stream the response back as SSE.
- ``POST /api/chat/threads/{id}/attachments`` — multipart upload, runs
  the L2 ingest pipeline (extract → chunk → embed → index).
- ``GET  /api/chat/threads/{id}/attachments`` — list ingested files.
- ``GET  /api/chat/attachments/{id}`` — describe one record + chunks.
- ``GET  /api/chat/attachments/{id}/download`` — original bytes.
- ``GET  /api/chat/attachments/{id}/extracted`` — extracted text.
- ``GET  /api/chat/attachments/{id}/chunks/{chunk_id}/neighbours`` —
  return the chunk plus its ord-adjacent neighbours (hover preview).
- ``DELETE /api/chat/attachments/{id}`` — delete row + bytes + chunks.
- ``POST /api/chat/threads/{id}/retrieve`` — manually run hybrid
  retrieval (top-K) for a query against the thread.

Headers honoured app-wide:
    ``x-meeet-trace-id`` (parent trace id),
    ``x-tars-session-id`` (per-tab session),
    ``x-tars-policy-mode`` (autopilot|confirm|dry_run).
"""

from __future__ import annotations

import json
import mimetypes
import os
from typing import Any, Optional

from fastapi import (
    APIRouter,
    Body,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse

from backend.core.attachments import (
    IngestError,
    get_attachment_store,
    ingest as run_ingest,
    retrieve as run_retrieve,
)
from backend.core.attachments.pipeline import delete_attachment as run_delete_attachment
from backend.core.chat import (
    AttachmentRef,
    Thread,
    get_chat_store,
)
from backend.core.chat.orchestrator import ChatOrchestrator
from backend.core.policy import PolicyMode, resolve_mode
from backend.core.voice.personas import iter_personas


def _validate_voice_persona_id(value: Any) -> str | None:
    """Coerce / validate a ``voice_persona_id`` payload value.

    Accepts ``None`` and the empty string (both clear the pin) plus
    any registered persona id. Raises ``HTTPException(400)`` on an
    unknown id so the cockpit gets a clear error rather than a
    silent no-op.
    """

    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(
            status_code=400, detail="voice_persona_id_invalid"
        )
    cleaned = value.strip()
    if not cleaned:
        return None
    known = {persona.id for persona in iter_personas()}
    if cleaned not in known:
        raise HTTPException(
            status_code=400, detail="voice_persona_id_unknown"
        )
    return cleaned

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ----------------------------------------------------------------------
# Threads CRUD
# ----------------------------------------------------------------------


@router.post("/threads")
async def create_thread(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    body = payload or {}
    title = body.get("title")
    pack_slug = body.get("pack_slug")
    project_id = body.get("project_id")
    voice_persona_id = (
        _validate_voice_persona_id(body.get("voice_persona_id"))
        if "voice_persona_id" in body
        else None
    )
    thread = Thread.fresh(
        title=str(title).strip() if title else None,
        pack_slug=str(pack_slug).strip() if pack_slug else None,
        project_id=str(project_id).strip() if project_id else None,
        voice_persona_id=voice_persona_id,
    )
    await get_chat_store().insert_thread(thread)
    return {"ok": True, "thread": thread.to_dict()}


@router.get("/threads")
async def list_threads(
    limit: int = Query(default=50, ge=1, le=500),
    archived: Optional[bool] = Query(default=False),
    pack_slug: Optional[str] = Query(default=None),
    project_id: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    threads = await get_chat_store().list_threads(
        limit=limit,
        archived=archived,
        pack_slug=pack_slug,
        project_id=project_id,
    )
    return {
        "ok": True,
        "count": len(threads),
        "threads": [t.to_dict() for t in threads],
    }


@router.get("/threads/{thread_id}")
async def describe_thread(
    thread_id: str,
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    store = get_chat_store()
    thread = await store.get_thread(thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="thread_not_found")
    messages = await store.list_messages(thread_id, limit=limit)
    return {
        "ok": True,
        "thread": thread.to_dict(),
        "messages": [m.to_dict() for m in messages],
    }


@router.patch("/threads/{thread_id}")
async def patch_thread(
    thread_id: str,
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    if not payload:
        raise HTTPException(status_code=400, detail="empty_patch")
    updates: dict[str, Any] = {}
    for k in ("title", "pack_slug", "project_id", "archived"):
        if k in payload:
            updates[k] = payload[k]
    if "voice_persona_id" in payload:
        updates["voice_persona_id"] = _validate_voice_persona_id(
            payload["voice_persona_id"]
        )
    thread = await get_chat_store().patch_thread(thread_id, updates)
    if thread is None:
        raise HTTPException(status_code=404, detail="thread_not_found")
    return {"ok": True, "thread": thread.to_dict()}


@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str) -> dict[str, Any]:
    thread = await get_chat_store().patch_thread(
        thread_id, {"archived": True}
    )
    if thread is None:
        raise HTTPException(status_code=404, detail="thread_not_found")
    return {"ok": True, "thread": thread.to_dict()}


# ----------------------------------------------------------------------
# Messages
# ----------------------------------------------------------------------


@router.get("/threads/{thread_id}/messages")
async def list_messages(
    thread_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    before: Optional[float] = Query(default=None),
) -> dict[str, Any]:
    store = get_chat_store()
    thread = await store.get_thread(thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="thread_not_found")
    msgs = await store.list_messages(thread_id, limit=limit, before=before)
    return {
        "ok": True,
        "thread_id": thread_id,
        "count": len(msgs),
        "messages": [m.to_dict() for m in msgs],
    }


@router.post("/threads/{thread_id}/messages")
async def post_message(
    thread_id: str,
    payload: dict[str, Any] | None = Body(default=None),
    x_meeet_trace_id: str | None = Header(default=None),
    x_tars_session_id: str | None = Header(default=None),
    x_tars_policy_mode: str | None = Header(default=None),
) -> StreamingResponse:
    body = payload or {}
    text = str(body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text_required")
    raw_attachments = body.get("attachments") or []
    attachments = [
        AttachmentRef(
            id=str(a.get("id") or ""),
            filename=a.get("filename"),
            mime=a.get("mime"),
            extracted_text=a.get("extracted_text"),
        )
        for a in raw_attachments
        if isinstance(a, dict)
    ]
    mode_arg = body.get("policy_mode")
    mode = resolve_mode(
        header=x_tars_policy_mode,
        request_arg=str(mode_arg) if mode_arg else None,
    )

    orchestrator = ChatOrchestrator()

    async def _generate():
        # SSE handshake: emit a small comment so curl/EventSource open
        # the connection promptly even before the voice yields.
        yield ": stream-open\n\n"
        try:
            async for event in orchestrator.post_message(
                thread_id,
                text,
                session_id=x_tars_session_id,
                attachments=attachments,
                policy_mode=mode,
            ):
                yield _encode_sse(event.kind, event.data)
        except Exception as exc:  # never crash the SSE pipe
            yield _encode_sse("error", {"error": str(exc)})
        yield _encode_sse("stream.closed", {"thread_id": thread_id})

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


# ----------------------------------------------------------------------
# Attachments (Phase L2)
# ----------------------------------------------------------------------


@router.post("/threads/{thread_id}/attachments")
async def upload_attachment(
    thread_id: str,
    file: UploadFile = File(...),
    message_id: Optional[str] = Form(default=None),
    x_tars_session_id: str | None = Header(default=None),
) -> dict[str, Any]:
    """Multipart upload → ingest pipeline → durable record + chunks."""

    chat_store = get_chat_store()
    thread = await chat_store.get_thread(thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="thread_not_found")

    blob = await file.read()
    if not blob:
        raise HTTPException(status_code=400, detail="empty_file")
    try:
        result = await run_ingest(
            thread_id=thread_id,
            blob=blob,
            filename=file.filename,
            mime=file.content_type or None,
            message_id=message_id,
            session_id=x_tars_session_id,
        )
    except IngestError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "ok": True,
        "duplicate": result.duplicate,
        "chunk_count": result.chunk_count,
        "embedding_model": result.embedding_model,
        "attachment": result.record.to_dict(),
    }


@router.get("/threads/{thread_id}/attachments")
async def list_attachments(thread_id: str) -> dict[str, Any]:
    chat_store = get_chat_store()
    thread = await chat_store.get_thread(thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="thread_not_found")
    records = await get_attachment_store().list_attachments(thread_id)
    return {
        "ok": True,
        "thread_id": thread_id,
        "count": len(records),
        "attachments": [r.to_dict() for r in records],
    }


@router.get("/attachments/{attachment_id}")
async def describe_attachment(attachment_id: str) -> dict[str, Any]:
    store = get_attachment_store()
    record = await store.get_attachment(attachment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="attachment_not_found")
    chunks = await store.list_chunks(record.thread_id, attachment_id=attachment_id)
    return {
        "ok": True,
        "attachment": record.to_dict(),
        "chunks": [
            {
                "id": c.id,
                "ord": c.ord,
                "char_start": c.char_start,
                "char_end": c.char_end,
                "heading": c.heading,
                "page": c.page,
                "preview": (c.text or "")[:240],
            }
            for c in chunks
        ],
    }


@router.get("/attachments/{attachment_id}/download")
async def download_attachment(attachment_id: str):
    record = await get_attachment_store().get_attachment(attachment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="attachment_not_found")
    if not record.storage_path or not os.path.isfile(record.storage_path):
        raise HTTPException(status_code=410, detail="bytes_missing")
    media_type = record.mime or "application/octet-stream"
    return FileResponse(
        record.storage_path,
        media_type=media_type,
        filename=record.filename or os.path.basename(record.storage_path),
    )


@router.get("/attachments/{attachment_id}/extracted")
async def extracted_attachment(attachment_id: str):
    record = await get_attachment_store().get_attachment(attachment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="attachment_not_found")
    return PlainTextResponse(
        record.extracted_text or "",
        media_type="text/plain; charset=utf-8",
        headers={
            "x-tars-attachment-id": record.id,
            "x-tars-attachment-mime": record.mime,
            "x-tars-attachment-status": record.status,
        },
    )


def _chunk_to_payload(chunk: Any, *, full_text: bool) -> dict[str, Any]:
    text = chunk.text or ""
    body: dict[str, Any] = {
        "id": chunk.id,
        "ord": chunk.ord,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "heading": chunk.heading,
        "page": chunk.page,
        "preview": text[:240],
    }
    if full_text:
        body["text"] = text
    return body


@router.get("/attachments/{attachment_id}/chunks/{chunk_id}/neighbours")
async def chunk_neighbours(
    attachment_id: str,
    chunk_id: str,
    before: int = Query(default=1, ge=0, le=10),
    after: int = Query(default=1, ge=0, le=10),
    full_text: bool = Query(default=True),
) -> dict[str, Any]:
    """Return the chunk plus its ord-adjacent neighbours.

    Powers the per-attachment hover preview from IDEAS — the
    cockpit highlights one chunk hit and renders ±N around it
    without paying for the whole document.
    """

    store = get_attachment_store()
    record = await store.get_attachment(attachment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="attachment_not_found")
    bundle = await store.get_chunk_neighbours(
        chunk_id, before=before, after=after
    )
    if bundle is None:
        raise HTTPException(status_code=404, detail="chunk_not_found")
    target, before_chunks, after_chunks = bundle
    if target.attachment_id != attachment_id:
        # Defend against operator-typo'd ids: a chunk that
        # happens to live under a different attachment must not
        # leak through this endpoint.
        raise HTTPException(status_code=404, detail="chunk_not_found")
    return {
        "ok": True,
        "attachment": {
            "id": record.id,
            "filename": record.filename,
            "mime": record.mime,
            "thread_id": record.thread_id,
        },
        "chunk": _chunk_to_payload(target, full_text=full_text),
        "before": [
            _chunk_to_payload(c, full_text=full_text) for c in before_chunks
        ],
        "after": [
            _chunk_to_payload(c, full_text=full_text) for c in after_chunks
        ],
        "window": {"before": before, "after": after},
    }


@router.get("/attachments/{attachment_id}/chunks/{chunk_id}/neighbors")
async def chunk_neighbors_alias(
    attachment_id: str,
    chunk_id: str,
    before: int = Query(default=1, ge=0, le=10),
    after: int = Query(default=1, ge=0, le=10),
    full_text: bool = Query(default=True),
) -> dict[str, Any]:
    """US-spelling alias of :func:`chunk_neighbours` — the
    cockpit can use either spelling without surprises.
    """

    return await chunk_neighbours(
        attachment_id,
        chunk_id,
        before=before,
        after=after,
        full_text=full_text,
    )


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(attachment_id: str) -> dict[str, Any]:
    ok = await run_delete_attachment(attachment_id)
    if not ok:
        raise HTTPException(status_code=404, detail="attachment_not_found")
    return {"ok": True, "deleted": True, "attachment_id": attachment_id}


@router.post("/threads/{thread_id}/retrieve")
async def retrieve_for_thread(
    thread_id: str,
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    body = payload or {}
    query = str(body.get("query") or "").strip()
    top_k = int(body.get("top_k") or 6)
    if not query:
        raise HTTPException(status_code=400, detail="query_required")
    chat_store = get_chat_store()
    thread = await chat_store.get_thread(thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="thread_not_found")
    chunks = await run_retrieve(thread_id, query, top_k=max(1, min(top_k, 20)))
    return {
        "ok": True,
        "thread_id": thread_id,
        "query": query,
        "count": len(chunks),
        "chunks": [c.to_dict() for c in chunks],
    }


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _encode_sse(event: str, data: Any) -> str:
    payload = json.dumps(data, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"
