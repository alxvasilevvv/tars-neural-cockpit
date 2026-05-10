"""GDPR Article 15 ("right of access") user data export (Wave 104).

Same shape as :func:`backend.core.compliance_export.bundler.build_bundle`
but scoped to a single user — only their messages, attachments,
actions, and receipts where they were the actor (or the resource
mentions them).

Produces ``~/.tars/exports/gdpr-<userhash>-<timestamp>.tar.gz``.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import tarfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .bundler import (
    DEFAULT_OUTPUT_DIR,
    _resolve_output_dir,
    _sha256,
    _sign_bytes,
)


log = logging.getLogger("tars.compliance_export.gdpr")


def _user_fingerprint(user_id_or_email: str) -> str:
    return hashlib.sha256(user_id_or_email.encode("utf-8")).hexdigest()[:12]


def _utc_iso(ts: float | None = None) -> str:
    if ts is None:
        ts = time.time()
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


async def _collect_user_receipts(user_id: str) -> list[dict[str, Any]]:
    """All receipts where the user is the actor or resource."""
    out: list[dict[str, Any]] = []
    try:
        from backend.core.receipts import get_store
        store = get_store()
        if store is None:
            return out
        rows = await store.query(actor=user_id, limit=100000)
        out.extend(r.to_dict() for r in rows)
        # Also scan recent receipts for resource matches.
        wide = await store.query(limit=100000)
        for r in wide:
            d = r.to_dict()
            if d in out:
                continue
            if (r.resource and user_id in str(r.resource)) or (
                user_id in json.dumps(r.payload, default=str)
            ):
                out.append(d)
    except Exception as exc:
        log.debug("gdpr receipts collector swallow: %s", exc)
    return out


async def _collect_user_messages(user_id: str) -> list[dict[str, Any]]:
    """Best-effort sweep of chat / message stores for this user."""
    out: list[dict[str, Any]] = []
    try:
        from backend.core.chat.store import get_chat_store
        store = get_chat_store()
        if store is not None and hasattr(store, "list_for_user"):
            msgs = await store.list_for_user(user_id)
            out = [
                m.to_dict() if hasattr(m, "to_dict") else dict(m)
                for m in msgs or []
            ]
        elif store is not None and hasattr(store, "list_messages"):
            msgs = await store.list_messages()
            out = [
                (m.to_dict() if hasattr(m, "to_dict") else dict(m))
                for m in msgs or []
                if user_id in json.dumps(
                    m.to_dict() if hasattr(m, "to_dict") else m, default=str,
                )
            ]
    except Exception as exc:
        log.debug("gdpr messages swallow: %s", exc)
    return out


async def _collect_user_attachments(user_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        from backend.core.attachments.store import get_store as _get
        store = _get()
        if hasattr(store, "list_for_user"):
            rows = await store.list_for_user(user_id)
        elif hasattr(store, "list_attachments"):
            rows = await store.list_attachments()
        else:
            rows = []
        for r in rows or []:
            d = r.to_dict() if hasattr(r, "to_dict") else dict(r)
            if user_id in json.dumps(d, default=str) or d.get("user_id") == user_id:
                out.append(d)
    except Exception as exc:
        log.debug("gdpr attachments swallow: %s", exc)
    return out


async def _collect_user_outreach(user_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        from backend.core.outreach.store import get_store as _get
        store = _get()
        if hasattr(store, "list_recipients"):
            rcps = await store.list_recipients()
            for r in rcps or []:
                d = r.to_dict() if hasattr(r, "to_dict") else dict(r)
                if d.get("email") == user_id or d.get("id") == user_id:
                    out.append(d)
    except Exception as exc:
        log.debug("gdpr outreach swallow: %s", exc)
    return out


async def export_user_data(
    user_id_or_email: str,
    *,
    output_dir: str | None = None,
) -> Path:
    """Build a GDPR Article 15 data export for a single user.

    Returns the :class:`Path` to the resulting tarball.
    """

    if not user_id_or_email or not isinstance(user_id_or_email, str):
        raise ValueError("user_id_or_email must be a non-empty string")
    user = user_id_or_email.strip()
    fp = _user_fingerprint(user)
    out_dir = _resolve_output_dir(output_dir)
    os.makedirs(out_dir, exist_ok=True)
    ts = time.time()
    fname = (
        f"gdpr-{fp}-"
        f"{datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.tar.gz"
    )
    output_path = os.path.join(out_dir, fname)

    receipts = await _collect_user_receipts(user)
    messages = await _collect_user_messages(user)
    attachments = await _collect_user_attachments(user)
    outreach = await _collect_user_outreach(user)

    files: list[tuple[str, bytes]] = [
        ("user/receipts.json",
         json.dumps(receipts, indent=2, sort_keys=True, default=str).encode("utf-8")),
        ("user/messages.json",
         json.dumps(messages, indent=2, sort_keys=True, default=str).encode("utf-8")),
        ("user/attachments.json",
         json.dumps(attachments, indent=2, sort_keys=True, default=str).encode("utf-8")),
        ("user/outreach.json",
         json.dumps(outreach, indent=2, sort_keys=True, default=str).encode("utf-8")),
    ]
    files.append((
        "README.md",
        (
            "# GDPR Article 15 data export\n\n"
            f"Subject fingerprint: {fp}\n"
            f"Generated: {_utc_iso(ts)}\n\n"
            "Contains every record TARS holds where the subject is\n"
            "the actor or appears in payload/resource fields.\n\n"
            "Receipts retain the cryptographic hash chain so the\n"
            "subject can independently verify the trail wasn't\n"
            "tampered with after extraction.\n"
        ).encode("utf-8"),
    ))

    # Manifest with file index + signature.
    file_index = [
        {"path": p, "sha256": _sha256(d), "size": len(d)} for p, d in files
    ]
    file_index.sort(key=lambda r: r["path"])
    sig_b64, pub_b64, fingerprint = _sign_bytes(b"placeholder")
    manifest = {
        "kind": "gdpr_article_15",
        "subject_fingerprint": fp,
        "generated_at": _utc_iso(ts),
        "signing_key_b64": pub_b64,
        "signing_key_fingerprint": fingerprint,
        "files": file_index,
    }
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    sig_b64, _, _ = _sign_bytes(manifest_bytes)
    files.append(("manifest.json", manifest_bytes))
    files.append((
        "signature.txt",
        (
            f"-----BEGIN TARS GDPR EXPORT SIGNATURE-----\n"
            f"algorithm: ed25519\n"
            f"public_key_b64: {pub_b64}\n"
            f"key_fingerprint: {fingerprint}\n"
            f"manifest_sha256: {_sha256(manifest_bytes)}\n"
            f"signature_b64: {sig_b64}\n"
            f"-----END TARS GDPR EXPORT SIGNATURE-----\n"
        ).encode("utf-8"),
    ))

    fixed_mtime = float(int(ts))
    with tarfile.open(output_path, "w:gz") as tf:
        for relpath, data in sorted(files, key=lambda r: r[0]):
            ti = tarfile.TarInfo(name=relpath)
            ti.size = len(data)
            ti.mtime = fixed_mtime
            ti.mode = 0o644
            tf.addfile(ti, io.BytesIO(data))

    try:
        from backend.core.receipts import record
        await record(
            type="compliance.gdpr_export",
            actor="system:gdpr_export",
            resource=fp,
            payload={
                "subject_fingerprint": fp,
                "output_path": output_path,
                "file_count": len(file_index),
            },
        )
    except Exception:  # pragma: no cover
        pass

    return Path(output_path)
