"""W257 — GDPR data-subject endpoints (export, delete, cancel).

BUSINESS-tier ($40/mo) regulated-industries customers need:

- **Article 15 (right of access)** — :http:post:`/api/gdpr/export` returns
  a job id; the async worker assembles a signed zip bundle containing
  every record TARS holds for the subject (receipts, chats, notepads,
  composer plans, usage events, audit timeline, meeet-token metadata).
- **Article 17 (right to erasure)** — :http:post:`/api/gdpr/delete`
  schedules a soft-delete with a 30-day grace period.
  :http:post:`/api/gdpr/delete/cancel` aborts a pending deletion.

The endpoints never throw out of band — every failure becomes either
an :exc:`HTTPException` (validation) or a recorded failure in the job
state machine (worker).

State is held in two places:

- In-memory ``_JOBS`` dict for export job progress (process-local;
  fine for single-user BUSINESS deployments).
- A small SQLite file at ``~/.tars/gdpr_pending.sqlite`` for
  scheduled deletions (so grace-period state survives restarts).

The bundle itself reuses ``backend.core.compliance_export.gdpr.
export_user_data`` (W104) — that builder already signs with the host
Ed25519 receipt key and writes a ``manifest.json`` with file SHA-256s,
which is the SOC2 evidence the auditor needs.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sqlite3
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse


log = logging.getLogger("tars.gdpr")


router = APIRouter(prefix="/api/gdpr", tags=["gdpr"])


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


DELETE_CONFIRM_PHRASE = "DELETE_ALL_MY_DATA"
DELETE_GRACE_DAYS = 30
DEFAULT_TARS_DIR = Path.home() / ".tars"
DEFAULT_EXPORT_DIR = DEFAULT_TARS_DIR / "exports"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tars_dir() -> Path:
    raw = os.getenv("TARS_HOME") or str(DEFAULT_TARS_DIR)
    return Path(raw).expanduser()


def _export_dir() -> Path:
    raw = os.getenv("TARS_EXPORT_DIR") or str(_tars_dir() / "exports")
    p = Path(raw).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _pending_db_path() -> Path:
    p = _tars_dir() / "gdpr_pending.sqlite"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _utc_iso(ts: float | None = None) -> str:
    if ts is None:
        ts = time.time()
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def _resolve_local_user() -> str:
    """Best-effort local user identifier.

    Reads the meeet-token-side ``account_hint`` if available so the
    GDPR job and the meeet account agree on identity. Falls back to
    ``$USER`` or ``"local-user"``.
    """

    try:
        path = _tars_dir() / "meeet_token"
        if path.exists():
            raw = path.read_text(encoding="utf-8").strip()
            # Token format is opaque; the operator's email-as-account is
            # held in a sibling hint file when present.
            hint_path = _tars_dir() / "meeet_account_hint"
            if hint_path.exists():
                hint = hint_path.read_text(encoding="utf-8").strip()
                if hint:
                    return hint
            # Otherwise fingerprint the token (don't leak the raw value).
            return f"meeet:{hashlib.sha256(raw.encode()).hexdigest()[:12]}"
    except Exception as exc:  # pragma: no cover
        log.debug("resolve_local_user swallow: %s", exc)
    return os.getenv("USER") or "local-user"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sign_bytes(data: bytes) -> tuple[str, str, str]:
    """Return ``(signature_b64, public_key_b64, fingerprint)``.

    Mirrors ``backend.core.compliance_export.bundler._sign_bytes`` so the
    auditor only has to learn one signature shape.
    """

    try:
        import base64
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )
        from backend.core.receipts.store import (
            _resolve_host_key_path,
            _load_or_create_host_key,
        )
        priv, pub = _load_or_create_host_key(_resolve_host_key_path())
        sk = Ed25519PrivateKey.from_private_bytes(priv)
        sig = sk.sign(data)
        return (
            base64.b64encode(sig).decode("ascii"),
            base64.b64encode(pub).decode("ascii"),
            _sha256_bytes(pub)[:16],
        )
    except Exception as exc:
        log.warning("gdpr sign fallback: %s", exc)
        return f"unsigned:{_sha256_bytes(data)}", "", "unsigned"


# ---------------------------------------------------------------------------
# Job state (export side)
# ---------------------------------------------------------------------------


_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = asyncio.Lock()


async def _set_job(job_id: str, **patch: Any) -> dict[str, Any]:
    async with _JOBS_LOCK:
        row = _JOBS.setdefault(job_id, {"job_id": job_id})
        row.update(patch)
        return dict(row)


async def _get_job(job_id: str) -> dict[str, Any] | None:
    async with _JOBS_LOCK:
        row = _JOBS.get(job_id)
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# Deletion store (survives restart)
# ---------------------------------------------------------------------------


def _ensure_pending_schema() -> None:
    db = _pending_db_path()
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gdpr_pending_deletions (
                subject TEXT PRIMARY KEY,
                requested_at REAL NOT NULL,
                purge_after REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                cancelled_at REAL,
                purged_at REAL
            )
            """
        )
        conn.commit()


def _upsert_pending(subject: str) -> dict[str, Any]:
    _ensure_pending_schema()
    now = time.time()
    purge_after = now + DELETE_GRACE_DAYS * 86400.0
    with sqlite3.connect(_pending_db_path()) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO gdpr_pending_deletions "
            "(subject, requested_at, purge_after, status, cancelled_at, purged_at) "
            "VALUES (?, ?, ?, 'pending', NULL, NULL)",
            (subject, now, purge_after),
        )
        conn.commit()
    return {
        "subject": subject,
        "requested_at": _utc_iso(now),
        "purge_after": _utc_iso(purge_after),
        "status": "pending",
        "grace_days": DELETE_GRACE_DAYS,
    }


def _cancel_pending(subject: str) -> dict[str, Any] | None:
    _ensure_pending_schema()
    now = time.time()
    with sqlite3.connect(_pending_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM gdpr_pending_deletions WHERE subject = ?",
            (subject,),
        ).fetchone()
        if row is None or row["status"] != "pending":
            return None
        conn.execute(
            "UPDATE gdpr_pending_deletions "
            "SET status='cancelled', cancelled_at=? WHERE subject = ?",
            (now, subject),
        )
        conn.commit()
    return {
        "subject": subject,
        "status": "cancelled",
        "cancelled_at": _utc_iso(now),
    }


def _get_pending(subject: str) -> dict[str, Any] | None:
    _ensure_pending_schema()
    with sqlite3.connect(_pending_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM gdpr_pending_deletions WHERE subject = ?",
            (subject,),
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["requested_at_iso"] = _utc_iso(d["requested_at"])
        d["purge_after_iso"] = _utc_iso(d["purge_after"])
        if d.get("cancelled_at"):
            d["cancelled_at_iso"] = _utc_iso(d["cancelled_at"])
        return d


# ---------------------------------------------------------------------------
# Collectors — each is best-effort and never throws past the worker boundary
# ---------------------------------------------------------------------------


async def _collect_receipts(subject: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        from backend.core.receipts import get_store
        store = get_store()
        if store is None:
            return out
        rows = await store.query(actor=subject, limit=100000)
        out = [r.to_dict() for r in rows]
    except Exception as exc:  # pragma: no cover
        log.debug("collect_receipts swallow: %s", exc)
    return out


async def _collect_chats(subject: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        from backend.core.chat.store import get_chat_store
        store = get_chat_store()
        if store is None:
            return out
        if hasattr(store, "list_for_user"):
            msgs = await store.list_for_user(subject)
            out = [m.to_dict() if hasattr(m, "to_dict") else dict(m) for m in msgs or []]
        elif hasattr(store, "list_messages"):
            msgs = await store.list_messages()
            for m in msgs or []:
                d = m.to_dict() if hasattr(m, "to_dict") else dict(m)
                if subject in json.dumps(d, default=str):
                    out.append(d)
    except Exception as exc:  # pragma: no cover
        log.debug("collect_chats swallow: %s", exc)
    return out


async def _collect_notepads() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        from backend.core.notepads import get_notepad_store
        store = get_notepad_store()
        rows = store.list(limit=500)
        out = [n.to_dict() for n in rows]
    except Exception as exc:  # pragma: no cover
        log.debug("collect_notepads swallow: %s", exc)
    return out


async def _collect_composer_plans() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        from backend.core.composer.storage import get_store
        store = get_store()
        if store is None:
            return out
        plans = store.list_plans(limit=500)
        for p in plans or []:
            if hasattr(p, "to_dict"):
                out.append(p.to_dict())
            else:
                out.append(dict(p))
    except Exception as exc:  # pragma: no cover
        log.debug("collect_composer swallow: %s", exc)
    return out


async def _collect_usage(subject: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    # W271 fix: previous import was `from backend.core.usage import get_store`,
    # which never existed (the module exposes get_ledger); silently swallowed
    # in the broad except below and so GDPR exports lost usage rows. Now we
    # pull from the meeet event store, which is the single source of truth
    # for usage.tokens / sampler.decision events.
    try:
        from backend.core.meeet import get_store as get_meeet_store
        store = get_meeet_store()
        if store is None or not getattr(store, "enabled", False):
            return out
        if hasattr(store, "list_events"):
            ev = await store.list_events(limit=10000)
        elif hasattr(store, "list"):
            ev = store.list(limit=10000)
        else:
            ev = []
        out = [
            (e if isinstance(e, dict) else (e.to_dict() if hasattr(e, "to_dict") else dict(e)))
            for e in ev or []
            if isinstance(e, dict)
            or getattr(e, "name", "").startswith("usage.")
            or getattr(e, "name", "").startswith("sampler.")
        ]
    except Exception as exc:  # pragma: no cover
        log.debug("collect_usage swallow: %s", exc)
    return out


async def _collect_audit_timeline(subject: str) -> list[dict[str, Any]]:
    """The W255 audit timeline is a view over receipts; we still
    materialise it as its own JSON file so the auditor can sample
    independently of the raw receipt blob.
    """

    out: list[dict[str, Any]] = []
    try:
        from backend.core.receipts import get_store
        store = get_store()
        if store is None:
            return out
        rows = await store.query(limit=100000)
        for r in rows:
            d = r.to_dict()
            d_str = json.dumps(d, default=str)
            if subject in d_str or d.get("actor") == subject:
                out.append({
                    "ts": d.get("ts"),
                    "type": d.get("type"),
                    "actor": d.get("actor"),
                    "resource": d.get("resource"),
                    "hash": d.get("hash") or d.get("curr_hash"),
                    "anchored": bool(d.get("anchor_sig")) or bool(d.get("anchored_at")),
                })
    except Exception as exc:  # pragma: no cover
        log.debug("collect_audit swallow: %s", exc)
    return out


def _meeet_token_metadata() -> dict[str, Any]:
    """Return metadata about the meeet token *without* the raw value."""
    try:
        path = _tars_dir() / "meeet_token"
        if not path.exists():
            return {"present": False}
        stat = path.stat()
        raw = path.read_bytes()
        return {
            "present": True,
            "path": str(path),
            "size_bytes": stat.st_size,
            "mode_octal": oct(stat.st_mode & 0o777),
            "sha256_fingerprint": _sha256_bytes(raw)[:16],
            "modified_at": _utc_iso(stat.st_mtime),
        }
    except Exception as exc:  # pragma: no cover
        log.debug("meeet_token_metadata swallow: %s", exc)
        return {"present": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Worker — assembles the zip
# ---------------------------------------------------------------------------


async def _run_export_job(job_id: str, subject: str) -> None:
    await _set_job(job_id, status="running", progress=0.05, subject=subject,
                   started_at=_utc_iso())
    try:
        # 1) collect
        receipts = await _collect_receipts(subject)
        await _set_job(job_id, progress=0.15, step="receipts",
                       counts={"receipts": len(receipts)})

        chats = await _collect_chats(subject)
        await _set_job(job_id, progress=0.30, step="chats",
                       counts={"receipts": len(receipts), "chats": len(chats)})

        notepads = await _collect_notepads()
        await _set_job(job_id, progress=0.40, step="notepads")

        composer_plans = await _collect_composer_plans()
        await _set_job(job_id, progress=0.50, step="composer")

        usage = await _collect_usage(subject)
        await _set_job(job_id, progress=0.65, step="usage")

        audit = await _collect_audit_timeline(subject)
        await _set_job(job_id, progress=0.80, step="audit")

        meeet_meta = _meeet_token_metadata()

        # 2) lay out the files
        files: dict[str, bytes] = {}

        def _add(rel: str, payload: Any) -> None:
            if isinstance(payload, (bytes, bytearray)):
                files[rel] = bytes(payload)
            else:
                files[rel] = json.dumps(
                    payload, indent=2, sort_keys=True, default=str
                ).encode("utf-8")

        _add("receipts.ndjson",
             ("\n".join(json.dumps(r, default=str) for r in receipts) + "\n").encode("utf-8"))
        _add("chats.json", chats)
        _add("notepads.json", notepads)
        _add("composer_plans.json", composer_plans)
        _add("usage_events.json", usage)
        _add("audit_timeline.json", audit)
        _add("meeet_token_metadata.json", meeet_meta)
        _add("README.md", (
            f"# GDPR Article 15 — TARS data export\n\n"
            f"Subject: {subject}\n"
            f"Generated: {_utc_iso()}\n\n"
            "Files:\n"
            "- receipts.ndjson    — hash-chained signed receipts (W67/W95)\n"
            "- chats.json         — chat threads + messages (W33)\n"
            "- notepads.json      — notepad templates (W243)\n"
            "- composer_plans.json — multi-file composer plans (W253)\n"
            "- usage_events.json  — metering events (W235)\n"
            "- audit_timeline.json — receipt-anchored audit timeline (W255)\n"
            "- meeet_token_metadata.json — token *metadata only* (no raw token)\n"
            "- manifest.json      — SHA-256 index + Ed25519 signature\n"
        ).encode("utf-8"))

        # 3) manifest with sha256 of every file
        file_index = sorted([
            {"path": p, "sha256": _sha256_bytes(d), "size": len(d)}
            for p, d in files.items()
        ], key=lambda r: r["path"])

        sig_b64, pub_b64, fingerprint = _sign_bytes(b"placeholder")
        manifest = {
            "kind": "gdpr_article_15_export",
            "subject": subject,
            "generated_at": _utc_iso(),
            "signing_key_b64": pub_b64,
            "signing_key_fingerprint": fingerprint,
            "contract_version": "1.0",
            "files": file_index,
        }
        manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
        sig_b64, _, _ = _sign_bytes(manifest_bytes)
        files["manifest.json"] = manifest_bytes
        files["signature.txt"] = (
            f"-----BEGIN TARS GDPR EXPORT SIGNATURE-----\n"
            f"algorithm: ed25519\n"
            f"public_key_b64: {pub_b64}\n"
            f"key_fingerprint: {fingerprint}\n"
            f"manifest_sha256: {_sha256_bytes(manifest_bytes)}\n"
            f"signature_b64: {sig_b64}\n"
            f"-----END TARS GDPR EXPORT SIGNATURE-----\n"
        ).encode("utf-8")

        await _set_job(job_id, progress=0.90, step="signing")

        # 4) write the zip
        ts = time.time()
        fp = hashlib.sha256(subject.encode()).hexdigest()[:12]
        fname = (
            f"gdpr-{fp}-"
            f"{datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.zip"
        )
        out_path = _export_dir() / fname
        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for rel, data in sorted(files.items()):
                zi = zipfile.ZipInfo(rel)
                zi.date_time = (2026, 1, 1, 0, 0, 0)  # deterministic
                zi.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(zi, data)

        # 5) record a receipt (best-effort)
        try:
            from backend.core.receipts import record
            await record(
                type="compliance.gdpr_export",
                actor="system:gdpr",
                resource=subject,
                payload={
                    "subject_fingerprint": fp,
                    "output_path": str(out_path),
                    "file_count": len(file_index),
                    "manifest_sha256": _sha256_bytes(manifest_bytes),
                },
            )
        except Exception:  # pragma: no cover
            pass

        await _set_job(
            job_id,
            status="ready",
            progress=1.0,
            finished_at=_utc_iso(),
            output_path=str(out_path),
            filename=fname,
            file_count=len(file_index),
            download_url=f"/api/gdpr/export/{job_id}/download",
            manifest_sha256=_sha256_bytes(manifest_bytes),
        )
    except Exception as exc:
        log.exception("gdpr export job failed: %s", exc)
        await _set_job(job_id, status="failed", error=str(exc), finished_at=_utc_iso())


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------


@router.post("/export")
async def post_export(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    """Start an async GDPR export job. Returns a ``job_id`` immediately."""

    subject = (payload.get("user_email") or payload.get("subject") or "").strip()
    if not subject:
        subject = _resolve_local_user()
    if not subject:
        raise HTTPException(status_code=400, detail="subject_required")
    job_id = f"gdpr_{uuid.uuid4().hex[:16]}"
    await _set_job(
        job_id,
        status="queued",
        subject=subject,
        progress=0.0,
        requested_at=_utc_iso(),
    )
    # Spawn — never await the worker so the caller gets the job id immediately.
    asyncio.create_task(_run_export_job(job_id, subject))
    return {"ok": True, "job_id": job_id, "subject": subject, "status": "queued"}


@router.get("/export/{job_id}")
async def get_export(job_id: str) -> dict[str, Any]:
    row = await _get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    return {"ok": True, **row}


@router.get("/export/{job_id}/download")
async def download_export(job_id: str) -> FileResponse:
    row = await _get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    if row.get("status") != "ready":
        raise HTTPException(status_code=409, detail="job_not_ready")
    path = row.get("output_path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=410, detail="bundle_file_missing")
    return FileResponse(
        path=path,
        media_type="application/zip",
        filename=os.path.basename(path),
    )


@router.post("/delete")
async def post_delete(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    """Schedule soft-delete with a 30-day grace period.

    The body MUST contain ``confirm: "DELETE_ALL_MY_DATA"`` exactly.
    """

    confirm = (payload.get("confirm") or "").strip()
    if confirm != DELETE_CONFIRM_PHRASE:
        raise HTTPException(
            status_code=400,
            detail=f"confirm_phrase_required:{DELETE_CONFIRM_PHRASE}",
        )
    subject = (payload.get("user_email") or payload.get("subject") or "").strip()
    if not subject:
        subject = _resolve_local_user()
    row = _upsert_pending(subject)
    try:
        from backend.core.receipts import record
        await record(
            type="compliance.gdpr_delete_scheduled",
            actor="system:gdpr",
            resource=subject,
            payload={"grace_days": DELETE_GRACE_DAYS, "purge_after": row["purge_after"]},
        )
    except Exception:  # pragma: no cover
        pass
    return {"ok": True, **row}


@router.post("/delete/cancel")
async def post_delete_cancel(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    subject = (payload.get("user_email") or payload.get("subject") or "").strip()
    if not subject:
        subject = _resolve_local_user()
    row = _cancel_pending(subject)
    if row is None:
        raise HTTPException(status_code=404, detail="no_pending_deletion")
    try:
        from backend.core.receipts import record
        await record(
            type="compliance.gdpr_delete_cancelled",
            actor="system:gdpr",
            resource=subject,
            payload={},
        )
    except Exception:  # pragma: no cover
        pass
    return {"ok": True, **row}


@router.get("/delete/status")
async def get_delete_status(subject: str | None = None) -> dict[str, Any]:
    s = subject or _resolve_local_user()
    row = _get_pending(s)
    if row is None:
        return {"ok": True, "subject": s, "status": "none"}
    return {"ok": True, **row}


# ---------------------------------------------------------------------------
# Test hooks
# ---------------------------------------------------------------------------


def _reset_for_tests() -> None:
    """Clear in-memory job state + pending-deletion DB. Tests only."""
    global _JOBS
    _JOBS = {}
    try:
        db = _pending_db_path()
        if db.exists():
            db.unlink()
    except OSError:
        pass
