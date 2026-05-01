"""Zip archive walker — expand zips into child attachments.

Operator pattern: drag a zip onto the cockpit, expect every text /
PDF / etc. inside to land as its own searchable attachment. Until
this slot we treated `application/zip` as a single opaque blob; the
extractor fell back to the bytes-as-binary path and the operator
got nothing useful.

Contract:

- ``walk_zip(blob, ...)`` returns a list of
  :class:`ZipEntryResult` rows, one per member that was attempted
  (success and failure both surface here so the caller can render
  the per-entry outcome).
- Members are streamed via :mod:`zipfile`. Symlinks, directory
  entries, and absolute / parent-traversing paths are dropped.
- Cap on the number of expanded entries: ``ZIP_MAX_ENTRIES``
  (default 200, override ``TARS_ZIP_MAX_ENTRIES``). Cap on per-
  entry uncompressed size: ``ZIP_MAX_ENTRY_BYTES`` (default 25
  MB, override ``TARS_ZIP_MAX_ENTRY_BYTES``).
- Recursion depth: nested zips can be expanded recursively up to
  ``ZIP_MAX_DEPTH`` (default 2, override ``TARS_ZIP_MAX_DEPTH``).
  Past that depth the inner zip lands as a single binary
  attachment (no further walking).

The walker is *only* the recursion engine; it calls back into
:func:`backend.core.attachments.pipeline.ingest` for every leaf
member so the existing dedup / extract / chunk / embed / FTS
discipline applies unchanged.
"""

from __future__ import annotations

import io
import logging
import os
import zipfile
from dataclasses import dataclass, field
from typing import Any, Iterable

from .index import AttachmentRecord, AttachmentStore


log = logging.getLogger("tars.attachments.zip")


_DEFAULT_MAX_ENTRIES = 200
_DEFAULT_MAX_ENTRY_BYTES = 25 * 1024 * 1024
_DEFAULT_MAX_DEPTH = 2

ZIP_MIMES: tuple[str, ...] = (
    "application/zip",
    "application/x-zip-compressed",
    "application/x-zip",
    "multipart/x-zip",
)


@dataclass(frozen=True)
class ZipEntryResult:
    """One entry's outcome — kept separately from the ingest path's
    own dataclasses so the walker can report dropped / failed
    members alongside the successful ones.
    """

    name: str
    ok: bool
    duplicate: bool = False
    attachment_id: str | None = None
    bytes_total: int = 0
    chunk_count: int = 0
    embedding_model: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class ZipWalkSummary:
    """Aggregated outcome of expanding one archive."""

    parent_attachment_id: str
    expanded: int
    skipped: int
    failed: int
    truncated: bool
    entries: tuple[ZipEntryResult, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_attachment_id": self.parent_attachment_id,
            "expanded": self.expanded,
            "skipped": self.skipped,
            "failed": self.failed,
            "truncated": self.truncated,
            "entries": [
                {
                    "name": e.name,
                    "ok": e.ok,
                    "duplicate": e.duplicate,
                    "attachment_id": e.attachment_id,
                    "bytes_total": e.bytes_total,
                    "chunk_count": e.chunk_count,
                    "embedding_model": e.embedding_model,
                    "error": e.error,
                }
                for e in self.entries
            ],
        }


# ---------------------------------------------------------------------
# Env helpers
# ---------------------------------------------------------------------


def zip_max_entries() -> int:
    raw = os.getenv("TARS_ZIP_MAX_ENTRIES")
    if not raw:
        return _DEFAULT_MAX_ENTRIES
    try:
        return max(1, min(int(raw), 5_000))
    except ValueError:
        return _DEFAULT_MAX_ENTRIES


def zip_max_entry_bytes() -> int:
    raw = os.getenv("TARS_ZIP_MAX_ENTRY_BYTES")
    if not raw:
        return _DEFAULT_MAX_ENTRY_BYTES
    try:
        return max(1024, int(raw))
    except ValueError:
        return _DEFAULT_MAX_ENTRY_BYTES


def zip_max_depth() -> int:
    raw = os.getenv("TARS_ZIP_MAX_DEPTH")
    if not raw:
        return _DEFAULT_MAX_DEPTH
    try:
        return max(1, min(int(raw), 5))
    except ValueError:
        return _DEFAULT_MAX_DEPTH


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------


def is_zip_mime(mime: str | None) -> bool:
    if not mime:
        return False
    base = mime.split(";", 1)[0].strip().lower()
    return base in ZIP_MIMES


def looks_like_zip(blob: bytes, filename: str | None = None) -> bool:
    """Best-effort detection.

    Trust the MIME / filename suffix first, then fall back to the
    PK magic bytes. We don't open the archive yet — that happens in
    :func:`walk_zip`.
    """

    if filename and filename.lower().endswith(".zip"):
        return True
    if blob.startswith(b"PK\x03\x04") or blob.startswith(b"PK\x05\x06"):
        return True
    return False


async def walk_zip(
    *,
    parent_record: AttachmentRecord,
    blob: bytes,
    thread_id: str,
    message_id: str | None = None,
    session_id: str | None = None,
    store: AttachmentStore | None = None,
    depth: int = 0,
) -> ZipWalkSummary:
    """Expand ``blob`` (a zip archive) into child attachments.

    The parent zip's :class:`AttachmentRecord` must already exist —
    the pipeline creates it before delegating here so the children
    can carry ``parent_attachment_id`` in their ``meta``.

    Returns a :class:`ZipWalkSummary` even on partial failures;
    individual entry errors land on the per-entry rows.
    """

    # Local import keeps the walker import-clean — the pipeline
    # depends on us, not the other way around.
    from .pipeline import IngestError, ingest as run_ingest

    max_entries = zip_max_entries()
    max_entry_bytes = zip_max_entry_bytes()
    max_depth = zip_max_depth()

    entries: list[ZipEntryResult] = []
    truncated = False
    expanded = 0
    skipped = 0
    failed = 0

    try:
        archive = zipfile.ZipFile(io.BytesIO(blob))
    except (zipfile.BadZipFile, OSError) as exc:
        return ZipWalkSummary(
            parent_attachment_id=parent_record.id,
            expanded=0,
            skipped=0,
            failed=1,
            truncated=False,
            entries=(
                ZipEntryResult(
                    name="<archive>",
                    ok=False,
                    error=f"bad_zip: {exc}",
                ),
            ),
        )

    try:
        members = archive.infolist()
    except (zipfile.BadZipFile, OSError) as exc:
        archive.close()
        return ZipWalkSummary(
            parent_attachment_id=parent_record.id,
            expanded=0,
            skipped=0,
            failed=1,
            truncated=False,
            entries=(
                ZipEntryResult(
                    name="<archive>",
                    ok=False,
                    error=f"bad_zip: {exc}",
                ),
            ),
        )

    try:
        for info in members:
            if expanded + skipped + failed >= max_entries:
                truncated = True
                break

            name = info.filename
            if _is_unsafe_name(name):
                skipped += 1
                entries.append(
                    ZipEntryResult(
                        name=name,
                        ok=False,
                        error="skip_unsafe_path",
                    )
                )
                continue
            if info.is_dir():
                skipped += 1
                entries.append(
                    ZipEntryResult(name=name, ok=False, error="skip_directory")
                )
                continue
            if info.file_size > max_entry_bytes:
                skipped += 1
                entries.append(
                    ZipEntryResult(
                        name=name,
                        ok=False,
                        error=(
                            f"skip_oversize bytes={info.file_size} "
                            f"max={max_entry_bytes}"
                        ),
                    )
                )
                continue

            try:
                with archive.open(info, "r") as fp:
                    member_bytes = fp.read(max_entry_bytes + 1)
            except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
                failed += 1
                entries.append(
                    ZipEntryResult(name=name, ok=False, error=f"read_failed: {exc}")
                )
                continue

            if len(member_bytes) > max_entry_bytes:
                # File header lied about the size — drop.
                skipped += 1
                entries.append(
                    ZipEntryResult(
                        name=name,
                        ok=False,
                        error=(
                            f"skip_oversize_actual bytes={len(member_bytes)} "
                            f"max={max_entry_bytes}"
                        ),
                    )
                )
                continue
            if not member_bytes:
                skipped += 1
                entries.append(
                    ZipEntryResult(name=name, ok=False, error="skip_empty")
                )
                continue

            try:
                ingest_res = await run_ingest(
                    thread_id=thread_id,
                    blob=member_bytes,
                    filename=os.path.basename(name) or "member",
                    message_id=message_id,
                    session_id=session_id,
                    store=store,
                    parent_attachment_id=parent_record.id,
                    walk_archives=depth + 1 < max_depth,
                )
            except IngestError as exc:
                failed += 1
                entries.append(
                    ZipEntryResult(name=name, ok=False, error=str(exc))
                )
                continue
            except Exception as exc:  # never crash the walk
                log.warning(
                    "zip member ingest crashed: name=%s err=%s",
                    name, exc,
                )
                failed += 1
                entries.append(
                    ZipEntryResult(name=name, ok=False, error=f"crashed: {exc}")
                )
                continue

            expanded += 1
            entries.append(
                ZipEntryResult(
                    name=name,
                    ok=True,
                    duplicate=ingest_res.duplicate,
                    attachment_id=ingest_res.record.id,
                    bytes_total=ingest_res.record.bytes_total,
                    chunk_count=ingest_res.chunk_count,
                    embedding_model=ingest_res.embedding_model,
                )
            )

    finally:
        archive.close()

    return ZipWalkSummary(
        parent_attachment_id=parent_record.id,
        expanded=expanded,
        skipped=skipped,
        failed=failed,
        truncated=truncated,
        entries=tuple(entries),
    )


def _is_unsafe_name(name: str) -> bool:
    """Reject zip-slip variants and absolute paths.

    Liberal on purpose — we never write zip members to disk, but
    we still don't want to ingest payloads named ``../../etc/passwd``
    so the cockpit doesn't show confusing paths.
    """

    if not name:
        return True
    if name.startswith("/") or name.startswith("\\"):
        return True
    parts = name.replace("\\", "/").split("/")
    if any(p == ".." for p in parts):
        return True
    if any(p.startswith("__MACOSX") for p in parts):
        return True
    return False


__all__ = [
    "ZipEntryResult",
    "ZipWalkSummary",
    "is_zip_mime",
    "looks_like_zip",
    "walk_zip",
    "zip_max_entries",
    "zip_max_entry_bytes",
    "zip_max_depth",
]
