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
- ``POST /api/chat/threads/{id}/attachments/stream`` — same upload as
  above but yields per-phase SSE frames (``started`` / ``extracted``
  / ``chunked`` / ``embedding`` / ``embedded`` / ``indexed`` /
  ``completed`` / ``error``) so the cockpit can render a live
  "indexing 12 chunks…" pill on the chip.
- ``GET  /api/chat/threads/{id}/attachments`` — list ingested files.
- ``GET  /api/chat/attachments/{id}`` — describe one record + chunks.
- ``GET  /api/chat/attachments/{id}/download`` — original bytes.
- ``GET  /api/chat/attachments/{id}/extracted`` — extracted text.
- ``GET  /api/chat/attachments/{id}/chunks/{chunk_id}/neighbours`` —
  return the chunk plus its ord-adjacent neighbours (hover preview).
- ``POST /api/chat/attachments/{id}/reembed`` — re-embed every chunk
  with a fresh (or explicitly named) embedder.
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
from backend.core.attachments.pipeline import (
    delete_attachment as run_delete_attachment,
    reembed_attachment as run_reembed_attachment,
)
from backend.core.chat import (
    AttachmentRef,
    Thread,
    get_chat_store,
)
from backend.core.chat.orchestrator import ChatOrchestrator
from backend.core.policy import PolicyMode, resolve_mode
from backend.core.voice.personas import iter_personas
from web_extras.entitlements_gate import require_cloud_budget


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

    # Bug #2 fix — chat assistant turns frequently spend cloud-LLM
    # tokens; gate at the HTTP edge so a FREE-tier operator gets a
    # clean 402 *before* the SSE stream opens. Local-only voices
    # (LocalChatVoice) can opt out via ``TARS_CAP_ENFORCEMENT=off``.
    # We deliberately raise BEFORE constructing the StreamingResponse
    # so the cap-hit envelope flies as a normal JSON error rather
    # than a half-open SSE pipe.
    await require_cloud_budget(kind="cloud", surface="chat.post_message")

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


@router.post("/threads/{thread_id}/attachments/stream")
async def upload_attachment_stream(
    thread_id: str,
    file: UploadFile = File(...),
    message_id: Optional[str] = Form(default=None),
    x_tars_session_id: str | None = Header(default=None),
):
    """Multipart upload that returns a Server-Sent Events stream.

    Each phase of the ingest pipeline (``started`` → ``extracted`` →
    ``chunked`` → ``embedding`` → ``embedded`` → ``indexed`` →
    ``completed``) yields one SSE frame so the cockpit can render
    a live "indexing 12 chunks…" pill on the file chip without
    polling. The terminal frame is always one of ``completed``,
    ``dedup_hit``, ``zip_walked``, or ``error``.

    SSE wire format: lines like ``event: <phase>`` followed by
    ``data: <json>`` and a blank line. Frames stay under 2 KB so
    every reasonable proxy will pass them through unchanged.
    """

    import asyncio
    import time

    chat_store = get_chat_store()
    thread = await chat_store.get_thread(thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="thread_not_found")

    blob = await file.read()
    if not blob:
        raise HTTPException(status_code=400, detail="empty_file")

    queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()

    async def progress(phase: str, payload: Any) -> None:
        # Cast to a plain dict so SSE serialisation is deterministic.
        await queue.put((phase, dict(payload)))

    async def runner() -> None:
        try:
            result = await run_ingest(
                thread_id=thread_id,
                blob=blob,
                filename=file.filename,
                mime=file.content_type or None,
                message_id=message_id,
                session_id=x_tars_session_id,
                progress=progress,
            )
            # ``completed`` / ``dedup_hit`` / ``zip_walked`` already
            # arrived through ``progress``. Pipe a final ``result``
            # frame with the canonical envelope so the consumer can
            # update the chip without an extra GET.
            await queue.put(
                (
                    "result",
                    {
                        "ok": True,
                        "duplicate": result.duplicate,
                        "chunk_count": result.chunk_count,
                        "embedding_model": result.embedding_model,
                        "attachment": result.record.to_dict(),
                    },
                )
            )
        except IngestError as exc:
            await queue.put(("error", {"ok": False, "detail": str(exc)}))
        except Exception as exc:
            await queue.put(
                ("error", {"ok": False, "detail": f"unexpected: {exc}"})
            )
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner())

    async def event_stream():
        # Send a comment line so proxies (nginx) flush headers
        # immediately and the consumer sees the connection open.
        yield ": stream-open\n\n"
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                phase, payload = item
                payload = {**payload, "ts": time.time()}
                data = json.dumps(payload, separators=(",", ":"))
                yield f"event: {phase}\ndata: {data}\n\n"
        finally:
            # Wait for the runner to finish before tearing down so we
            # never leak the ingest task even if the consumer hangs up.
            await task

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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


@router.post("/attachments/{attachment_id}/reembed")
async def reembed_attachment_route(
    attachment_id: str,
    payload: dict[str, Any] | None = Body(default=None),
    x_tars_session_id: str | None = Header(default=None),
) -> dict[str, Any]:
    """Re-embed every chunk for ``attachment_id``.

    Body (all optional)::

        {
          "model": "openai" | "hash" | "text-embedding-3-large",
          "force": false,
          "target_model": null
        }

    Two implementations live behind this endpoint and are
    dispatched by the body shape:

    - **Promote-style** (default, or when ``model`` is set):
      :func:`backend.core.attachments.pipeline.reembed_attachment`
      — emits ``attachment.reembedded`` + ``usage.tokens`` through
      the meeet bridge, computes cost, stamps the attachment row
      with the new ``embedding_model``. Response shape is
      :class:`ReembedResult.to_dict()`
      (``chunk_count`` / ``embedding_model`` / ``tokens_used`` /
      ``cost_usd`` / ``previous_model``).
    - **Force / batch-style** (when ``force=true`` or
      ``target_model`` is set):
      :func:`backend.core.attachments.reembed.reembed_attachment`
      — batches chunks (32 at a time), idempotent (already-correct
      chunks become ``skipped_same``), reports per-batch failures.
      Response shape carries ``embedded`` /
      ``skipped_blank`` / ``skipped_same`` / ``failed`` /
      ``batches`` / ``total`` / ``model`` / ``dim``.

    Both shapes include ``ok`` and ``attachment_id``. The
    ``attachment_not_found`` error is mapped to HTTP 404 in both
    paths; every other failure surfaces as ``200`` with
    ``ok=False`` so the cockpit can render the structured detail.
    """

    body = payload or {}
    force = bool(body.get("force"))
    target_model_raw = body.get("target_model")
    target_model = (
        str(target_model_raw).strip()
        if isinstance(target_model_raw, str) and target_model_raw.strip()
        else None
    )

    if force or target_model:
        # Force / batch-style path. The newer module is idempotent
        # and exposes per-batch counters (`embedded`,
        # `skipped_same`, `failed`) which the cockpit's reembed
        # progress UI relies on. Imports lazily to keep the
        # router importable when sqlite is disabled at boot.
        from backend.core.attachments.reembed import reembed_attachment

        res = await reembed_attachment(
            attachment_id, force=force, target_model=target_model,
        )
        if (
            res.get("ok") is False
            and res.get("reason") == "attachment_not_found"
        ):
            raise HTTPException(
                status_code=404, detail="attachment_not_found"
            )
        # Echo back the attachment_id for clients that branch on it
        # — the newer impl only sets it on success.
        res.setdefault("attachment_id", attachment_id)
        return res

    # Promote-style path (default + when `model` field is set).
    model_arg = body.get("model")
    embedder_name = (
        str(model_arg).strip()
        if isinstance(model_arg, str) and model_arg.strip()
        else None
    )
    result = await run_reembed_attachment(
        attachment_id,
        embedder_name=embedder_name,
        session_id=x_tars_session_id,
    )
    if result.error == "attachment_not_found":
        raise HTTPException(
            status_code=404, detail="attachment_not_found"
        )
    return result.to_dict()


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(attachment_id: str) -> dict[str, Any]:
    ok = await run_delete_attachment(attachment_id)
    if not ok:
        raise HTTPException(status_code=404, detail="attachment_not_found")
    return {"ok": True, "deleted": True, "attachment_id": attachment_id}


@router.post("/attachments/reembed-by-model")
async def reembed_by_model_endpoint(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    """Promote chunks whose current embedding_model matches.

    Body::

        {
          "old_model": "tars-hash-bigram-v1-d384",  # required
          "thread_id": "thr_xxx",                   # optional scope
          "limit": 500,                             # 1..5000, default 500
          "force": false,
          "target_model": null
        }

    Designed for the "I just configured ``OPENAI_API_KEY`` — promote
    everything that's still on the offline hash embedder" workflow.
    Returns the same stats dict as the per-attachment endpoint plus
    ``old_model`` / ``thread_id`` echoes for confirmation.
    """

    from backend.core.attachments.reembed import reembed_by_model

    body = payload or {}
    old_model = str(body.get("old_model") or "").strip()
    if not old_model:
        raise HTTPException(
            status_code=400, detail="old_model_required"
        )
    thread_id = body.get("thread_id")
    if thread_id is not None:
        thread_id = str(thread_id).strip() or None
    try:
        limit = int(body.get("limit", 500))
    except (TypeError, ValueError):
        limit = 500
    force = bool(body.get("force"))
    target_model = body.get("target_model")
    target_model = str(target_model).strip() if target_model else None
    return await reembed_by_model(
        old_model,
        thread_id=thread_id,
        limit=limit,
        force=force,
        target_model=target_model,
    )


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
