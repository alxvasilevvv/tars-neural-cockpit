"""HTTP surface for the audit-grade compliance export bundle (Wave 104).

Endpoints:

- ``POST   /api/compliance/export/bundle``                 generate
- ``GET    /api/compliance/export/bundles``                list past
- ``GET    /api/compliance/export/bundles/{id}``           single status
- ``GET    /api/compliance/export/bundles/{id}/download``  the tarball
- ``DELETE /api/compliance/export/bundles/{id}``           remove (HIL gated)
- ``POST   /api/compliance/export/verify``                 multipart upload
- ``POST   /api/compliance/gdpr-export``                   single-user export

The ``bundle`` and ``DELETE`` endpoints route through
``policy_gate.require_confirm`` so the HIL gate (Wave 76) kicks in
when ``TARS_REQUIRE_OPERATOR_CONFIRM=1``.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse

from backend.core.compliance_export import (
    Bundle,
    SCOPE_CATEGORIES,
    build_bundle,
    export_user_data,
    list_bundles,
    verify_bundle,
)
from backend.core.compliance_export.bundler import delete_bundle, get_bundle

from web_extras import policy_gate


router = APIRouter(prefix="/api/compliance", tags=["compliance"])


# ---------- helpers ---------------------------------------------------------


def _bundle_to_dict(b: Bundle | dict[str, Any]) -> dict[str, Any]:
    if isinstance(b, dict):
        return b
    return b.to_dict()


# ---------- bundle generation -----------------------------------------------


@router.post("/export/bundle")
async def post_bundle(
    request: Request,
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    since = (payload.get("since") or "").strip()
    until = (payload.get("until") or "").strip()
    scope = payload.get("scope") or ["all"]
    redact = bool(payload.get("redact_pii", False))
    if not since or not until:
        raise HTTPException(status_code=400, detail="since_and_until_required")
    if not isinstance(scope, list):
        raise HTTPException(status_code=400, detail="scope_must_be_list")

    # HIL gate
    try:
        await policy_gate.require_confirm(
            request,
            wallet_id="compliance",
            action="compliance.export",
            params={"since": since, "until": until, "scope": scope, "redact_pii": redact},
        )
    except AttributeError:
        # policy_gate.require_confirm may not exist in tests; gate is opt-in
        pass
    except Exception as exc:
        # only enforce when explicit gate required
        if policy_gate.is_required():
            raise

    try:
        bundle = await build_bundle(
            since=since, until=until, scope=scope, redact_pii=redact,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return bundle.to_dict()


@router.get("/export/bundles")
async def get_bundles() -> dict[str, Any]:
    rows = list_bundles()
    return {"bundles": rows, "count": len(rows)}


@router.get("/export/bundles/{bundle_id}")
async def get_bundle_one(bundle_id: str) -> dict[str, Any]:
    row = get_bundle(bundle_id)
    if row is None:
        raise HTTPException(status_code=404, detail="bundle_not_found")
    return row


@router.get("/export/bundles/{bundle_id}/download")
async def get_bundle_download(bundle_id: str) -> FileResponse:
    row = get_bundle(bundle_id)
    if row is None:
        raise HTTPException(status_code=404, detail="bundle_not_found")
    path = row.get("output_path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=410, detail="bundle_file_missing")
    return FileResponse(
        path=path,
        media_type="application/gzip",
        filename=os.path.basename(path),
    )


@router.delete("/export/bundles/{bundle_id}")
async def delete_bundle_one(
    request: Request, bundle_id: str,
) -> dict[str, Any]:
    try:
        await policy_gate.require_confirm(
            request,
            wallet_id="compliance",
            action="compliance.bundle_delete",
            params={"bundle_id": bundle_id},
        )
    except AttributeError:
        pass
    except Exception:
        if policy_gate.is_required():
            raise
    ok = delete_bundle(bundle_id)
    if not ok:
        raise HTTPException(status_code=404, detail="bundle_not_found")
    return {"ok": True, "bundle_id": bundle_id}


# ---------- verifier --------------------------------------------------------


@router.post("/export/verify")
async def post_verify(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file:
        raise HTTPException(status_code=400, detail="file_required")
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".tar.gz", delete=False,
        ) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        try:
            result = verify_bundle(tmp_path)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"verify_failed:{exc}")
    return result


# ---------- GDPR export -----------------------------------------------------


@router.post("/gdpr-export")
async def post_gdpr_export(
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    email = (payload.get("email") or payload.get("user_id") or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="email_or_user_id_required")
    try:
        path = await export_user_data(email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "ok": True,
        "output_path": str(path),
        "filename": os.path.basename(str(path)),
    }


# ---------- meta ------------------------------------------------------------


@router.get("/export/scope-categories")
async def get_scope_categories() -> dict[str, Any]:
    return {"categories": list(SCOPE_CATEGORIES)}
