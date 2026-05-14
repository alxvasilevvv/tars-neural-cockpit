"""W255 — Receipt-anchored audit explorer (HTTP surface).

Three-panel cockpit AUDIT tab consumes these endpoints. Every TARS
action emits a hash-chained, Ed25519-signed receipt (W67/W89/W95);
once a day a Merkle root anchors them on Solana. This router gives
the cockpit (and B2B compliance officers) a single read-side surface
to browse the chain, verify a receipt against its anchor, and export
a signed PDF compliance bundle.

Endpoints
---------

- ``GET  /api/audit/timeline?since=&until=&kind=&q=&only_anchored=&limit=``
        paginated receipts with anchor status, FTS over kind/summary/payload.
- ``GET  /api/audit/receipt/{hash}`` full receipt JSON + prev/next hashes.
- ``GET  /api/audit/verify/{hash}``  Merkle-proof + signature verification.
- ``POST /api/receipts/export``      body ``{from,to,format}`` ->
        immediate-download URL for ``json|csv``; PDF returns a job_id.
- ``GET  /api/receipts/export/{job_id}`` poll / download endpoint.

Privacy
-------

When ``backend.core.privacy`` reports ``mode == "strict"`` the
timeline + receipt detail responses strip the ``payload`` blob and
elide summary text. Hash + signature + anchor status are always
public; they're deliberately non-identifying and required for the
proof story.

Export bundle
-------------

The PDF cover page lists: date range, total receipt count, hash of
the first/last receipt, Solana anchor tx ids covering the range, and
the Ed25519 host public key. Each row gets one entry: ts, kind,
actor, short payload, receipt hash, anchored-yes/no. The bundle
itself is signed (Ed25519 sig over the sha256 of the body) so a
SOC2 auditor can verify cryptographically that we generated this
exact file.

Saved to ``~/.tars/exports/<ts>-receipts.<ext>``; auto-prune after 7 days.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from backend.core.receipts import (
    Receipt,
    get_store,
    proof as merkle_proof,
    verify as verify_receipt,
)
from backend.core.receipts.merkle import verify_proof

log = logging.getLogger("tars.audit")

router = APIRouter(prefix="/api/audit", tags=["audit"])
export_router = APIRouter(prefix="/api/receipts", tags=["audit", "export"])


# ----- helpers ----------------------------------------------------------


def _store_or_503():
    s = get_store()
    if s is None:
        raise HTTPException(status_code=503, detail="receipts_disabled")
    return s


def _utc_day_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def _exports_dir() -> Path:
    raw = os.getenv("TARS_EXPORTS_DIR") or "~/.tars/exports"
    p = Path(os.path.expanduser(raw))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _privacy_mode() -> str:
    try:
        from backend.core.privacy import load_privacy
        return str(load_privacy().mode or "normal")
    except Exception:
        return "normal"


def _redact_for_mode(payload: dict, mode: str) -> dict:
    if mode == "strict":
        return {"redacted": True}
    return payload


def _summarise(r: Receipt) -> str:
    pl = r.payload or {}
    for k in ("summary", "title", "label", "action", "message"):
        v = pl.get(k)
        if isinstance(v, str) and v:
            return v[:200]
    if r.resource:
        return str(r.resource)[:200]
    try:
        return json.dumps(pl, sort_keys=True)[:120]
    except Exception:
        return ""


def _anchor_explorer_url(sig):
    if not sig:
        return None
    cluster = os.getenv("SOLANA_CLUSTER", "mainnet-beta")
    if cluster == "mainnet-beta":
        return f"https://explorer.solana.com/tx/{sig}"
    return f"https://explorer.solana.com/tx/{sig}?cluster={cluster}"


async def _anchor_for_receipt(s, receipt: Receipt) -> dict:
    day_iso = _utc_day_iso(receipt.ts)
    row = await s.get_merkle_root(day_iso)
    if row is None:
        return {
            "day": day_iso,
            "anchored": False,
            "root_hex": None,
            "solana_signature": None,
            "explorer_url": None,
        }
    return {
        "day": day_iso,
        "anchored": bool(row.solana_signature),
        "root_hex": row.root_hex,
        "solana_signature": row.solana_signature,
        "explorer_url": _anchor_explorer_url(row.solana_signature),
    }


# ----- /timeline --------------------------------------------------------


@router.get("/timeline")
async def timeline(
    since: float | None = Query(default=None),
    until: float | None = Query(default=None),
    kind: str | None = Query(default=None),
    q: str | None = Query(default=None),
    only_anchored: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    s = _store_or_503()
    rows = await s.query(type=kind, since=since, until=until, limit=limit * 2)
    mode = _privacy_mode()

    day_cache: dict = {}
    items: list = []
    needle = (q or "").strip().lower() or None

    for r in rows:
        day_iso = _utc_day_iso(r.ts)
        if day_iso not in day_cache:
            row = await s.get_merkle_root(day_iso)
            if row is None:
                day_cache[day_iso] = {
                    "anchored": False,
                    "solana_signature": None,
                    "root_hex": None,
                }
            else:
                day_cache[day_iso] = {
                    "anchored": bool(row.solana_signature),
                    "solana_signature": row.solana_signature,
                    "root_hex": row.root_hex,
                }
        anchor = day_cache[day_iso]
        if only_anchored and not anchor["anchored"]:
            continue

        summary = _summarise(r)
        if needle:
            hay = " ".join(
                [
                    r.type or "",
                    summary,
                    json.dumps(r.payload or {}, sort_keys=True),
                ]
            ).lower()
            if needle not in hay:
                continue

        items.append(
            {
                "id": r.id,
                "hash": r.hash,
                "hash_short": (r.hash or "")[:8],
                "ts": r.ts,
                "kind": r.type,
                "actor": r.actor,
                "resource": r.resource,
                "summary": "" if mode == "strict" else summary,
                "anchored": anchor["anchored"],
                "day": day_iso,
                "solana_signature": anchor["solana_signature"],
                "explorer_url": _anchor_explorer_url(anchor["solana_signature"]),
            }
        )
        if len(items) >= limit:
            break

    return {
        "ok": True,
        "count": len(items),
        "privacy_mode": mode,
        "items": items,
    }


# ----- /receipt/{hash} --------------------------------------------------


async def _find_by_hash(s, hash_hex: str) -> Receipt | None:
    direct = await s.get_by_id(hash_hex)
    if direct is not None:
        return direct
    rows = await s.query(limit=5000)
    for r in rows:
        if r.hash == hash_hex:
            return r
    return None


@router.get("/receipt/{hash_or_id}")
async def receipt_detail(hash_or_id: str) -> dict:
    s = _store_or_503()
    receipt = await _find_by_hash(s, hash_or_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="receipt_not_found")

    mode = _privacy_mode()
    payload = _redact_for_mode(receipt.payload or {}, mode)

    day_iso = _utc_day_iso(receipt.ts)
    chain = await s.replay_chain_for_day(day_iso)
    next_hash = None
    for r in chain:
        if r.prev_hash == receipt.hash:
            next_hash = r.hash
            break

    anchor = await _anchor_for_receipt(s, receipt)
    public_url_base = os.getenv("TARS_PUBLIC_PROOF_BASE", "https://meeet.world/proof")
    return {
        "ok": True,
        "receipt": {
            **receipt.to_dict(),
            "payload": payload,
        },
        "prev_hash": receipt.prev_hash or None,
        "next_hash": next_hash,
        "anchor": anchor,
        "public_url": f"{public_url_base.rstrip('/')}/{receipt.hash}",
        "privacy_mode": mode,
    }


# ----- /verify/{hash} ---------------------------------------------------


@router.get("/verify/{hash_or_id}")
async def verify_hash(hash_or_id: str) -> dict:
    s = _store_or_503()
    receipt = await _find_by_hash(s, hash_or_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="receipt_not_found")

    sig_ok = False
    try:
        sig_ok = bool(verify_receipt(receipt))
    except Exception:
        sig_ok = False

    day_iso = _utc_day_iso(receipt.ts)
    chain = await s.replay_chain_for_day(day_iso)
    proof_ok = False
    proof_payload = None
    try:
        idx = next(i for i, r in enumerate(chain) if r.id == receipt.id)
        hashes = [r.hash for r in chain]
        proof_payload = merkle_proof(hashes, idx)
        proof_ok = verify_proof(
            proof_payload["leaf"], proof_payload["path"], proof_payload["root"]
        )
    except StopIteration:
        proof_ok = False
    except Exception as exc:
        log.debug("audit.verify.merkle failed: %s", exc)
        proof_ok = False

    anchor = await _anchor_for_receipt(s, receipt)

    return {
        "ok": True,
        "verified": sig_ok and proof_ok,
        "signature_ok": sig_ok,
        "merkle_proof_ok": proof_ok,
        "anchored": anchor["anchored"],
        "solana_tx": anchor["solana_signature"],
        "explorer_url": anchor["explorer_url"],
        "day": day_iso,
        "root_hex": anchor["root_hex"],
        "merkle_proof": proof_payload,
        "verified_at": time.time(),
    }


# ----- /api/receipts/export ---------------------------------------------


_EXPORT_JOBS: dict = {}


def _have_reportlab() -> bool:
    try:
        import reportlab  # noqa: F401
        return True
    except Exception:
        return False


def _have_wkhtmltopdf() -> bool:
    from shutil import which
    return which("wkhtmltopdf") is not None


def _prune_old_exports(days: int = 7) -> None:
    try:
        d = _exports_dir()
        cutoff = time.time() - days * 86400.0
        for f in d.iterdir():
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink()
            except Exception:
                pass
    except Exception:
        pass


def _bundle_filename(fmt: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = "json" if fmt == "json" else ("csv" if fmt == "csv" else "pdf")
    return f"{stamp}-receipts.{suffix}"


async def _gather_for_range(s, from_ts, to_ts, mode):
    rows = await s.query(since=from_ts, until=to_ts, limit=100000)
    items = []
    day_cache: dict = {}
    for r in rows:
        day_iso = _utc_day_iso(r.ts)
        if day_iso not in day_cache:
            row = await s.get_merkle_root(day_iso)
            day_cache[day_iso] = {
                "anchored": bool(row and row.solana_signature),
                "root_hex": row.root_hex if row else None,
                "solana_signature": row.solana_signature if row else None,
            }
        anchor = day_cache[day_iso]
        items.append(
            {
                "id": r.id,
                "hash": r.hash,
                "ts": r.ts,
                "kind": r.type,
                "actor": r.actor,
                "resource": r.resource,
                "summary": "" if mode == "strict" else _summarise(r),
                "payload": _redact_for_mode(r.payload or {}, mode),
                "prev_hash": r.prev_hash,
                "signature": r.signature,
                "public_key": r.public_key,
                "anchored": anchor["anchored"],
                "day": day_iso,
                "root_hex": anchor["root_hex"],
                "solana_signature": anchor["solana_signature"],
            }
        )
    return items


def _sign_bundle_bytes(data: bytes) -> dict:
    try:
        s = get_store()
        if s is None:
            return {"signature_b64": "", "public_key_b64": ""}
        s._init_sync()
        import hashlib

        digest = hashlib.sha256(data).digest()
        priv = s._priv
        if not priv:
            return {"signature_b64": "", "public_key_b64": ""}
        try:
            from nacl.signing import SigningKey
            sig = SigningKey(priv).sign(digest).signature
        except Exception:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PrivateKey,
            )
            sk = Ed25519PrivateKey.from_private_bytes(priv)
            sig = sk.sign(digest)
        return {
            "signature_b64": base64.b64encode(sig).decode("ascii"),
            "public_key_b64": s.public_key_b64,
        }
    except Exception as exc:
        log.debug("audit.export.sign failed: %s", exc)
        return {"signature_b64": "", "public_key_b64": ""}


def _build_json_bundle(items, meta):
    payload = {"meta": meta, "receipts": items}
    body = json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")
    sig = _sign_bundle_bytes(body)
    return json.dumps(
        {**payload, "_signature": sig},
        sort_keys=True,
        indent=2,
    ).encode("utf-8")


def _build_csv_bundle(items):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "ts_iso", "kind", "actor", "resource", "summary",
        "hash", "prev_hash", "anchored", "solana_tx",
    ])
    for it in items:
        ts_iso = datetime.fromtimestamp(it["ts"], tz=timezone.utc).isoformat()
        w.writerow([
            ts_iso,
            it["kind"],
            it["actor"],
            it.get("resource") or "",
            it.get("summary") or "",
            it.get("hash") or "",
            it.get("prev_hash") or "",
            "yes" if it.get("anchored") else "no",
            it.get("solana_signature") or "",
        ])
    return buf.getvalue().encode("utf-8")


def _build_pdf_bundle(items, meta, sig):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )
    except Exception:
        return None

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        title="TARS receipt compliance bundle",
        author="TARS",
    )
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>TARS receipt compliance bundle</b>", styles["Title"]))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        f"Date range: <b>{meta.get('from_iso','-')}</b> -> "
        f"<b>{meta.get('to_iso','-')}</b>", styles["Normal"]))
    story.append(Paragraph(
        f"Receipts in range: <b>{len(items)}</b>", styles["Normal"]))
    story.append(Paragraph(
        f"First hash: <font face='Courier'>{(items[0]['hash'] if items else '-')[:32]}...</font>",
        styles["Normal"]))
    story.append(Paragraph(
        f"Last hash: <font face='Courier'>{(items[-1]['hash'] if items else '-')[:32]}...</font>",
        styles["Normal"]))
    anchored_txs = sorted({i["solana_signature"] for i in items if i.get("solana_signature")})
    if anchored_txs:
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph("<b>Solana anchor transactions covering this range:</b>", styles["Normal"]))
        for tx in anchored_txs[:30]:
            story.append(Paragraph(f"<font face='Courier' size=8>{tx}</font>", styles["Normal"]))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(
        f"Ed25519 signer (host public key): "
        f"<font face='Courier' size=8>{sig.get('public_key_b64','-')}</font>",
        styles["Normal"]))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        "Each row is a hash-chained, Ed25519-signed action receipt. "
        "Anchored rows roll up into a daily Merkle root committed to Solana "
        "via memo transaction; any third party can replay the proof at "
        "/api/public/proof/verify without trusting this report.",
        styles["Italic"]))

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("<b>Receipts</b>", styles["Heading2"]))

    data = [["timestamp (UTC)", "kind", "actor", "summary", "hash", "anchored"]]
    for it in items[:5000]:
        ts_iso = datetime.fromtimestamp(it["ts"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        data.append([
            ts_iso,
            (it.get("kind") or "")[:24],
            (it.get("actor") or "")[:24],
            (it.get("summary") or "")[:60],
            (it.get("hash") or "")[:12],
            "yes" if it.get("anchored") else "no",
        ])
    tbl = Table(
        data, repeatRows=1,
        colWidths=[1.4 * inch, 1.0 * inch, 1.1 * inch, 2.3 * inch, 0.9 * inch, 0.6 * inch],
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#101010")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(tbl)

    story.append(Spacer(1, 0.25 * inch))
    story.append(Paragraph(
        f"<b>Ed25519 signature (over sha256 of report body):</b><br/>"
        f"<font face='Courier' size=7>{sig.get('signature_b64','-')}</font>",
        styles["Normal"]))

    doc.build(story)
    return buf.getvalue()


def _items_to_html(items, meta, sig):
    rows_html = "\n".join(
        "<tr><td>{ts}</td><td>{kind}</td><td>{actor}</td><td>{summary}</td>"
        "<td><code>{hash}</code></td><td>{anchored}</td></tr>".format(
            ts=datetime.fromtimestamp(it["ts"], tz=timezone.utc).isoformat(),
            kind=(it.get("kind") or ""),
            actor=(it.get("actor") or ""),
            summary=(it.get("summary") or "")[:120],
            hash=(it.get("hash") or "")[:12],
            anchored="yes" if it.get("anchored") else "no",
        )
        for it in items
    )
    return f"""<!doctype html><meta charset='utf-8'>
<style>body{{font-family:Helvetica,Arial,sans-serif;font-size:10px;margin:24px}}
h1{{font-size:18px}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:4px;font-size:8px;text-align:left}}
th{{background:#101010;color:#fff}}</style>
<h1>TARS receipt compliance bundle</h1>
<p>Range: {meta.get('from_iso','-')} -> {meta.get('to_iso','-')}; receipts: {len(items)}.</p>
<p>Signer pub-key: <code>{sig.get('public_key_b64','-')}</code></p>
<table><thead><tr><th>ts</th><th>kind</th><th>actor</th><th>summary</th>
<th>hash</th><th>anchored</th></tr></thead><tbody>{rows_html}</tbody></table>
<p>Ed25519 signature: <code>{sig.get('signature_b64','-')}</code></p>
"""


@export_router.post("/export")
async def receipts_export(payload: dict = Body(default_factory=dict)):
    s = _store_or_503()
    _prune_old_exports()

    fmt = str(payload.get("format") or "json").lower()
    if fmt not in ("json", "csv", "pdf"):
        raise HTTPException(status_code=400, detail="bad_format")
    from_ts = payload.get("from")
    to_ts = payload.get("to")
    try:
        from_ts = float(from_ts) if from_ts is not None else None
        to_ts = float(to_ts) if to_ts is not None else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="bad_from_to")

    mode = _privacy_mode()
    items = await _gather_for_range(s, from_ts, to_ts, mode)

    meta = {
        "from": from_ts,
        "to": to_ts,
        "from_iso": (
            datetime.fromtimestamp(from_ts, tz=timezone.utc).isoformat()
            if from_ts is not None else None
        ),
        "to_iso": (
            datetime.fromtimestamp(to_ts, tz=timezone.utc).isoformat()
            if to_ts is not None else None
        ),
        "generated_at": time.time(),
        "generated_at_iso": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "privacy_mode": mode,
        "format": fmt,
    }

    fname = _bundle_filename(fmt)
    out_path = _exports_dir() / fname
    job_id = f"exp_{uuid.uuid4().hex[:18]}"

    if fmt == "json":
        body = _build_json_bundle(items, meta)
        out_path.write_bytes(body)
    elif fmt == "csv":
        body = _build_csv_bundle(items)
        out_path.write_bytes(body)
    else:
        if not _have_reportlab() and not _have_wkhtmltopdf():
            return JSONResponse(
                status_code=501,
                content={
                    "ok": False,
                    "error": "pdf_renderer_missing",
                    "hint": "PDF export requires reportlab or wkhtmltopdf installed.",
                    "fallback_format": "json",
                },
            )
        body_bytes = _build_json_bundle(items, meta)
        sig = _sign_bundle_bytes(body_bytes)
        pdf_bytes = _build_pdf_bundle(items, meta, sig)
        if pdf_bytes is None:
            try:
                import subprocess
                import tempfile

                html_body = _items_to_html(items, meta, sig)
                with tempfile.NamedTemporaryFile(
                    "w", suffix=".html", delete=False, encoding="utf-8"
                ) as tf:
                    tf.write(html_body)
                    html_path = tf.name
                subprocess.run(
                    ["wkhtmltopdf", "--quiet", html_path, str(out_path)],
                    check=True, timeout=60,
                )
                os.unlink(html_path)
            except Exception as exc:
                return JSONResponse(
                    status_code=500,
                    content={
                        "ok": False,
                        "error": "pdf_render_failed",
                        "detail": str(exc),
                    },
                )
        else:
            out_path.write_bytes(pdf_bytes)

    _EXPORT_JOBS[job_id] = {
        "path": str(out_path),
        "format": fmt,
        "status": "ready",
        "created_at": time.time(),
        "meta": meta,
    }
    return {
        "ok": True,
        "job_id": job_id,
        "status": "ready",
        "format": fmt,
        "count": len(items),
        "filename": fname,
        "download_url": f"/api/receipts/export/{job_id}",
    }


@export_router.get("/export/{job_id}")
async def receipts_export_download(job_id: str):
    job = _EXPORT_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    path = Path(job["path"])
    if not path.exists():
        raise HTTPException(status_code=410, detail="export_file_pruned")
    media = (
        "application/json" if job["format"] == "json"
        else ("text/csv" if job["format"] == "csv" else "application/pdf")
    )
    return FileResponse(str(path), media_type=media, filename=path.name)
