"""Wave 102 — /api/files document & file management surface.

A first-class file browser on top of the existing
``backend.core.attachments`` pipeline. Endpoints here are thread-
agnostic — they expose every attachment that has been ingested
across every chat thread so a B2B operator can manage hundreds of
PDFs without remembering which thread each one came from.

Existing per-thread attachment endpoints in
:mod:`web_extras.routers.chat` are untouched — this router is purely
additive. Internally we share the same ``AttachmentStore`` singleton
and reuse the ingest pipeline.

Endpoints (all under ``/api/files`` unless noted):

- ``GET    /``                 list with filters + sort + pagination
- ``GET    /stats``            aggregate counts / sizes
- ``GET    /categories``       static catalogue (standard slugs)
- ``GET    /{id}``             one file metadata + chunk preview
- ``GET    /{id}/download``    bytes (FileResponse)
- ``POST   /upload``           multipart, accepts MULTIPLE files
- ``PATCH  /{id}``             update tags / category / pinned / name
- ``DELETE /{id}``             soft-delete (HIL gated)
- ``POST   /{id}/restore``     undo soft-delete
- ``POST   /bulk-tag``         body {ids, tags, operation}
- ``POST   /bulk-categorize``  body {ids, category}
- ``POST   /bulk-delete``      body {ids, reason}      HIL gated
- ``POST   /auto-categorize``  body {id} or {ids}      LLM-driven

The router is mounted by ``web_extras.app`` in the standard
``include_router`` block; see ``app.py`` for the wiring.
"""

from __future__ import annotations

import os
import time
from typing import Any, Iterable, Optional

from fastapi import (
    APIRouter,
    Body,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse

from backend.core.attachments import (
    AttachmentRecord,
    get_attachment_store,
)
from backend.core.attachments.categories import (
    DEFAULT_CATEGORY,
    auto_categorize,
    heuristic_category,
    is_standard,
    list_standard,
)
from backend.core.attachments.pipeline import (
    IngestError,
    ingest as run_ingest,
)
from backend.core.chat.models import Thread
from backend.core.chat.store import get_chat_store
from web_extras import policy_gate


router = APIRouter(prefix="/api/files", tags=["files"])


# ---------------------------------------------------------------------
# Limits — keep the upload path predictable on a desktop sidecar.
# ---------------------------------------------------------------------

# Per-file ceiling. Mirrors what the public contract advertises.
_MAX_FILE_BYTES = int(os.getenv("TARS_FILES_MAX_FILE_BYTES", str(100 * 1024 * 1024)))
# Cumulative ceiling per single multipart request.
_MAX_BULK_BYTES = int(os.getenv("TARS_FILES_MAX_BULK_BYTES", str(1024 * 1024 * 1024)))
# Max number of files allowed in a single bulk action body.
_MAX_BULK_IDS = int(os.getenv("TARS_FILES_MAX_BULK_IDS", "200"))


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _record_to_card(record: AttachmentRecord) -> dict[str, Any]:
    """Trim the record dict for grid/list rendering on the FE."""

    body = record.to_dict()
    body["extension"] = _ext(record.filename)
    body["thumbnail_url"] = (
        f"/api/files/{record.id}/download"
        if (record.mime or "").startswith("image/")
        else None
    )
    body["preview_url"] = f"/api/files/{record.id}/download"
    return body


def _ext(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return str(filename).rsplit(".", 1)[-1].lower()[:16]


def _coerce_ids(raw: Iterable[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for r in raw or ():
        if not r:
            continue
        sid = str(r).strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        out.append(sid)
        if len(out) >= _MAX_BULK_IDS:
            break
    return out


# ---------------------------------------------------------------------
# Routes — read
# ---------------------------------------------------------------------


@router.get("/categories")
async def categories() -> dict[str, Any]:
    """Standard catalogue rendered by the sidebar."""

    return {
        "ok": True,
        "categories": list_standard(),
        "default": DEFAULT_CATEGORY,
        "auto_categorize_enabled": (
            os.getenv("TARS_AUTO_CATEGORIZE_ENABLED", "0")
            in ("1", "true", "yes")
        ),
    }


@router.get("/stats")
async def stats() -> dict[str, Any]:
    store = get_attachment_store()
    s = await store.file_stats()
    return {"ok": True, **s}


@router.get("")
async def list_files(
    category: Optional[str] = Query(default=None),
    tag: Optional[str] = Query(default=None),
    pinned: Optional[bool] = Query(default=None),
    since: Optional[float] = Query(default=None),
    until: Optional[float] = Query(default=None),
    thread_id: Optional[str] = Query(default=None),
    include_deleted: bool = Query(default=False),
    sort: str = Query(default="created_desc"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    query: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    """List files across all threads.

    When ``query`` is provided we route through the shared FTS5
    ``chunks_fts`` index, gather distinct attachment ids whose
    chunks matched, then re-hydrate full records (so the grid
    shows the operator metadata, not chunk fragments).
    """

    store = get_attachment_store()

    # FTS-driven branch: rank by relevance, then apply post-filters.
    if query and query.strip():
        try:
            from backend.core.search.fts import (
                ensure_fts_indexes,
                fts_match_chunks,
            )

            ensure_fts_indexes(chat=store.chat)
            hits = fts_match_chunks(
                query.strip(),
                chat=store.chat,
                limit=max(limit * 4, 50),
                thread_id=thread_id or None,
            )
        except Exception:
            hits = []

        seen: set[str] = set()
        ordered_ids: list[str] = []
        snippet_for: dict[str, str] = {}
        for hit in hits:
            aid = str(hit.get("attachment_id") or "")
            if not aid or aid in seen:
                continue
            seen.add(aid)
            ordered_ids.append(aid)
            snippet = hit.get("snippet")
            if snippet and aid not in snippet_for:
                snippet_for[aid] = str(snippet)

        records: list[AttachmentRecord] = []
        for aid in ordered_ids:
            rec = await store.get_attachment(aid)
            if rec is None:
                continue
            if rec.deleted_at and not include_deleted:
                continue
            if category and rec.category != category:
                continue
            if pinned is not None and bool(rec.pinned) != bool(pinned):
                continue
            if tag and tag not in rec.tags:
                continue
            if since is not None and rec.created_at < since:
                continue
            if until is not None and rec.created_at > until:
                continue
            records.append(rec)

        sliced = records[offset : offset + limit]
        items = [_record_to_card(r) for r in sliced]
        for item in items:
            sn = snippet_for.get(item["id"])
            if sn:
                item["match_snippet"] = sn
        return {
            "ok": True,
            "total": len(records),
            "limit": limit,
            "offset": offset,
            "sort": "relevance",
            "query": query,
            "items": items,
        }

    records = await store.query_files(
        category=category,
        tag=tag,
        pinned=pinned,
        since=since,
        until=until,
        thread_id=thread_id,
        include_deleted=include_deleted,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return {
        "ok": True,
        "total": len(records),
        "limit": limit,
        "offset": offset,
        "sort": sort,
        "items": [_record_to_card(r) for r in records],
    }


@router.get("/{file_id}")
async def get_file(file_id: str) -> dict[str, Any]:
    store = get_attachment_store()
    record = await store.get_attachment(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="file_not_found")
    chunks = await store.list_chunks(record.thread_id, attachment_id=file_id)
    return {
        "ok": True,
        "file": _record_to_card(record),
        "chunk_count": len(chunks),
        "chunks_preview": [
            {
                "id": c.id,
                "ord": c.ord,
                "preview": (c.text or "")[:240],
                "page": c.page,
                "heading": c.heading,
            }
            for c in chunks[:6]
        ],
    }


@router.get("/{file_id}/download")
async def download_file(file_id: str):
    record = await get_attachment_store().get_attachment(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="file_not_found")
    if record.deleted_at:
        raise HTTPException(status_code=410, detail="file_deleted")
    if not record.storage_path or not os.path.isfile(record.storage_path):
        raise HTTPException(status_code=410, detail="bytes_missing")
    return FileResponse(
        record.storage_path,
        media_type=record.mime or "application/octet-stream",
        filename=record.filename or os.path.basename(record.storage_path),
    )


# ---------------------------------------------------------------------
# Routes — write (single)
# ---------------------------------------------------------------------


@router.post("/upload")
async def upload_files(
    files: list[UploadFile] = File(...),
    thread_id: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    auto: bool = Query(default=False),
) -> dict[str, Any]:
    """Accept one or many files in a single multipart request.

    A "files" inbox thread is created lazily when the operator
    uploads from /files (no chat thread to attach to). All files
    in the same upload share that thread so chunk retrieval still
    works downstream.
    """

    if not files:
        raise HTTPException(status_code=400, detail="no_files")

    target_thread = thread_id or await _ensure_files_inbox_thread()
    cumulative = 0
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    store = get_attachment_store()

    for f in files:
        blob = await f.read()
        if not blob:
            errors.append({"filename": f.filename, "error": "empty_file"})
            continue
        if len(blob) > _MAX_FILE_BYTES:
            errors.append(
                {"filename": f.filename, "error": "file_too_large"}
            )
            continue
        cumulative += len(blob)
        if cumulative > _MAX_BULK_BYTES:
            errors.append(
                {"filename": f.filename, "error": "bulk_quota_exceeded"}
            )
            break
        try:
            result = await run_ingest(
                thread_id=target_thread,
                blob=blob,
                filename=f.filename,
                mime=f.content_type or None,
            )
        except IngestError as exc:
            errors.append({"filename": f.filename, "error": str(exc)})
            continue

        # Pick a category — operator-provided > LLM auto > heuristic.
        target_cat: str
        if category and (is_standard(category) or len(category) <= 64):
            target_cat = category
        elif auto:
            target_cat = await auto_categorize(
                filename=result.record.filename,
                excerpt=result.record.extracted_text or "",
                mime=result.record.mime,
            )
        else:
            target_cat = heuristic_category(
                result.record.filename, result.record.mime
            )

        updated = await store.update_file_metadata(
            result.record.id, category=target_cat
        ) or result.record

        results.append(
            {
                "duplicate": result.duplicate,
                "chunk_count": result.chunk_count,
                "embedding_model": result.embedding_model,
                "file": _record_to_card(updated),
            }
        )

    return {
        "ok": True,
        "thread_id": target_thread,
        "uploaded": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }


async def _ensure_files_inbox_thread() -> str:
    """Get-or-create the synthetic thread that owns Cabinet uploads.

    Files uploaded via the /files browser don't necessarily belong
    to any conversation — they live in a single shared thread that
    we lazily create on first use. The thread title is stable so
    the FE's "Inbox" label resolves to the same thread across
    sessions.
    """

    chat = get_chat_store()
    title = "Files inbox"
    threads = await chat.list_threads(limit=200)
    for t in threads:
        if (t.title or "") == title:
            return t.id
    thread = Thread.fresh(title=title)
    await chat.insert_thread(thread)
    return thread.id


@router.patch("/{file_id}")
async def patch_file(
    file_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    store = get_attachment_store()
    existing = await store.get_attachment(file_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="file_not_found")

    updated = await store.update_file_metadata(
        file_id,
        tags=payload.get("tags") if "tags" in payload else None,
        category=payload.get("category") if "category" in payload else None,
        pinned=payload.get("pinned") if "pinned" in payload else None,
        filename=payload.get("filename") if "filename" in payload else None,
    )
    return {"ok": True, "file": _record_to_card(updated or existing)}


@router.delete("/{file_id}")
async def delete_file(
    request: Request,
    file_id: str,
    reason: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    """Soft-delete a single file. HIL gated."""

    store = get_attachment_store()
    record = await store.get_attachment(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="file_not_found")
    if record.pinned:
        raise HTTPException(status_code=409, detail="file_pinned")
    await policy_gate.require_confirm(
        request,
        wallet_id=file_id,
        action="file.delete",
        params={"id": file_id, "reason": reason or ""},
    )
    updated = await store.soft_delete_attachment(file_id)
    return {"ok": True, "file": _record_to_card(updated or record)}


@router.post("/{file_id}/restore")
async def restore_file(file_id: str) -> dict[str, Any]:
    store = get_attachment_store()
    record = await store.get_attachment(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="file_not_found")
    updated = await store.restore_attachment(file_id)
    return {"ok": True, "file": _record_to_card(updated or record)}


# ---------------------------------------------------------------------
# Routes — bulk
# ---------------------------------------------------------------------


@router.post("/bulk-tag")
async def bulk_tag(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Bulk add / remove / replace tags on N files."""

    ids = _coerce_ids(payload.get("ids") or ())
    op = str(payload.get("operation") or "add").lower()
    raw_tags = payload.get("tags") or []
    if not isinstance(raw_tags, list):
        raise HTTPException(status_code=400, detail="tags_must_be_list")
    incoming = [str(t).strip() for t in raw_tags if str(t).strip()]
    if op not in {"add", "remove", "replace"}:
        raise HTTPException(status_code=400, detail="bad_operation")
    if not ids:
        raise HTTPException(status_code=400, detail="no_ids")

    store = get_attachment_store()
    updated: list[dict[str, Any]] = []
    missing: list[str] = []
    for fid in ids:
        rec = await store.get_attachment(fid)
        if rec is None:
            missing.append(fid)
            continue
        if op == "replace":
            new_tags = list(incoming)
        elif op == "add":
            new_tags = list(rec.tags) + [t for t in incoming if t not in rec.tags]
        else:  # remove
            drop = {t.lower() for t in incoming}
            new_tags = [t for t in rec.tags if t.lower() not in drop]
        out = await store.update_file_metadata(fid, tags=new_tags)
        if out is not None:
            updated.append(_record_to_card(out))

    return {
        "ok": True,
        "operation": op,
        "updated": len(updated),
        "missing": missing,
        "files": updated,
    }


@router.post("/bulk-categorize")
async def bulk_categorize(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    ids = _coerce_ids(payload.get("ids") or ())
    category = str(payload.get("category") or "").strip()
    if not ids:
        raise HTTPException(status_code=400, detail="no_ids")
    if not category:
        raise HTTPException(status_code=400, detail="no_category")
    if len(category) > 64:
        raise HTTPException(status_code=400, detail="category_too_long")

    store = get_attachment_store()
    updated: list[dict[str, Any]] = []
    missing: list[str] = []
    for fid in ids:
        rec = await store.get_attachment(fid)
        if rec is None:
            missing.append(fid)
            continue
        out = await store.update_file_metadata(fid, category=category)
        if out is not None:
            updated.append(_record_to_card(out))
    return {
        "ok": True,
        "category": category,
        "updated": len(updated),
        "missing": missing,
        "files": updated,
    }


@router.post("/bulk-delete")
async def bulk_delete(
    request: Request, payload: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    """Bulk soft-delete. HIL gated. Pinned files are rejected."""

    ids = _coerce_ids(payload.get("ids") or ())
    reason = str(payload.get("reason") or "").strip()
    if not ids:
        raise HTTPException(status_code=400, detail="no_ids")

    await policy_gate.require_confirm(
        request,
        wallet_id="files",
        action="file.delete",
        params={"ids": sorted(ids), "reason": reason},
    )

    store = get_attachment_store()
    deleted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    missing: list[str] = []
    for fid in ids:
        rec = await store.get_attachment(fid)
        if rec is None:
            missing.append(fid)
            continue
        if rec.pinned:
            skipped.append({"id": fid, "reason": "pinned"})
            continue
        out = await store.soft_delete_attachment(fid)
        if out is not None:
            deleted.append(_record_to_card(out))

    return {
        "ok": True,
        "deleted": len(deleted),
        "skipped": skipped,
        "missing": missing,
        "files": deleted,
        "at": time.time(),
    }


@router.post("/auto-categorize")
async def auto_categorize_endpoint(
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    """LLM-backed (with heuristic fallback) classifier for one or many files."""

    raw = payload.get("ids") or []
    if not raw and payload.get("id"):
        raw = [payload.get("id")]
    ids = _coerce_ids(raw)
    if not ids:
        raise HTTPException(status_code=400, detail="no_ids")

    store = get_attachment_store()
    results: list[dict[str, Any]] = []
    missing: list[str] = []
    for fid in ids:
        rec = await store.get_attachment(fid)
        if rec is None:
            missing.append(fid)
            continue
        slug = await auto_categorize(
            filename=rec.filename,
            excerpt=(rec.extracted_text or "")[:600],
            mime=rec.mime,
        )
        out = await store.update_file_metadata(fid, category=slug)
        if out is not None:
            results.append(
                {"id": fid, "category": slug, "file": _record_to_card(out)}
            )
    return {
        "ok": True,
        "updated": len(results),
        "missing": missing,
        "results": results,
    }


__all__ = ["router"]
