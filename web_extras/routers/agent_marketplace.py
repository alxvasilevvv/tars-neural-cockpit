"""W261 -- Agent marketplace v0 (publish + install TARS agents).

Builds on W96 (70/30 revenue share, already shipped) + W49
(marketplace 2.0 registry). The endpoints in W106
(``routers/marketplace.py``) cover *playbooks/skills/templates*; this
router covers *agents* — the persona+pack+system_prompt triples the
W12 agent runtime knows how to instantiate.

Surface (operator-facing, loopback by deployment policy):

- ``GET    /api/marketplace/agents``                browse + filter + sort
- ``POST   /api/marketplace/agents/publish``        body
  ``{agent_id, version, description}`` -> builds a signed manifest,
  POSTs it to the meeet.world marketplace registry, persists a
  local "my published" record.
- ``POST   /api/marketplace/agents/install``        body
  ``{agent_uri}`` -> fetches a signed manifest, verifies the
  ed25519 signature, instantiates the agent via the W12 agent store,
  and writes an InstalledItem-style entry.
- ``DELETE /api/marketplace/agents/{id}/uninstall`` removes the
  local agent + install record.
- ``GET    /api/marketplace/agents/published``      list "my published"
  records emitted by this TARS.

Manifest shape (signed wire payload, version 1):

  {
    "manifest_version": 1,
    "agent":     {id, name, pack_slug, description, system_prompt, version},
    "publisher": {tars_id, pubkey_b64},
    "signature": "<base64(ed25519 sign over canonical agent+publisher)>",
    "signed_at": <epoch float>
  }

Signatures use the **W67 host ed25519 key** -- same key that signs
the receipt ledger and W260 T2T review envelopes, so the whole
stack speaks one identity.

In single-machine / test mode (``TARS_MARKETPLACE_OFFLINE=1``) we
keep a local on-disk registry under
``~/.tars/marketplace/agents/registry.jsonl`` so the contract is
exercised end-to-end without network.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Body, HTTPException, Query

from backend.core.agents.store import get_agent_store


log = logging.getLogger("tars.agent_marketplace")

router = APIRouter(prefix="/api/marketplace/agents", tags=["agent-marketplace"])


# ---------------------------------------------------------------------------
# Paths + config
# ---------------------------------------------------------------------------


def _registry_path() -> Path:
    raw = os.environ.get("TARS_AGENT_REGISTRY_PATH") \
        or "~/.tars/marketplace/agents/registry.jsonl"
    p = Path(os.path.expanduser(raw))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _published_path() -> Path:
    raw = os.environ.get("TARS_AGENT_PUBLISHED_PATH") \
        or "~/.tars/marketplace/agents/my_published.jsonl"
    p = Path(os.path.expanduser(raw))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _installed_path() -> Path:
    raw = os.environ.get("TARS_AGENT_INSTALLED_PATH") \
        or "~/.tars/marketplace/agents/installed.jsonl"
    p = Path(os.path.expanduser(raw))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _is_offline() -> bool:
    flag = (os.environ.get("TARS_MARKETPLACE_OFFLINE") or "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def _registry_base_url() -> str:
    base = (
        os.environ.get("TARS_AGENT_MARKETPLACE_URL")
        or os.environ.get("MEEET_BASE_URL")
        or "https://meeet.world"
    )
    return base.rstrip("/")


# ---------------------------------------------------------------------------
# W67 identity helpers -- sign / verify using the host ed25519 key.
# ---------------------------------------------------------------------------


def _host_identity() -> tuple[bytes, str]:
    """Return (priv_seed_32, public_key_b64) from the W67 receipt store."""

    from backend.core.receipts.store import get_store as _rstore

    rs = _rstore()
    if rs is None:
        raise HTTPException(
            status_code=503,
            detail="receipt store disabled; cannot sign agent manifests",
        )
    rs._init_sync()  # noqa: SLF001 -- matches W260 pattern
    priv = rs._priv  # noqa: SLF001
    pub_b64 = rs.public_key_b64
    if priv is None or pub_b64 is None:
        raise HTTPException(status_code=503, detail="host key not initialised")
    return priv, pub_b64


def _tars_id(pub_b64: str) -> str:
    """Stable short TARS id derived from the host pubkey."""

    import hashlib

    raw = base64.b64decode(pub_b64.encode("ascii"))
    digest = hashlib.sha256(raw).hexdigest()
    return f"tars_{digest[:16]}"


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    """Canonical JSON (sorted, no whitespace) bytes for signing."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign_manifest(manifest_body: dict[str, Any]) -> dict[str, Any]:
    """Wrap ``manifest_body`` in publisher + signature + signed_at envelope."""

    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )

    priv, pub_b64 = _host_identity()
    publisher = {"tars_id": _tars_id(pub_b64), "pubkey_b64": pub_b64}
    inner = {"agent": manifest_body, "publisher": publisher}
    sig = Ed25519PrivateKey.from_private_bytes(priv).sign(_canonical_bytes(inner))
    return {
        "manifest_version": 1,
        "agent": manifest_body,
        "publisher": publisher,
        "signature": base64.b64encode(sig).decode("ascii"),
        "signed_at": time.time(),
    }


def _verify_manifest(manifest: dict[str, Any]) -> bool:
    """Verify a signed manifest. Never raises; returns False on bad input."""

    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey,
    )

    try:
        publisher = manifest.get("publisher") or {}
        pub_b64 = str(publisher.get("pubkey_b64") or "")
        sig_b64 = str(manifest.get("signature") or "")
        agent = manifest.get("agent") or {}
        if not pub_b64 or not sig_b64 or not agent:
            return False
        inner = {"agent": agent, "publisher": publisher}
        vk = Ed25519PublicKey.from_public_bytes(base64.b64decode(pub_b64))
        vk.verify(base64.b64decode(sig_b64), _canonical_bytes(inner))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# JSONL helpers -- registry / published / installed are append-only.
# ---------------------------------------------------------------------------


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        for raw in path.read_text("utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return out


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, sort_keys=True) + "\n")


def _rewrite_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fp:
        for r in rows:
            fp.write(json.dumps(r, sort_keys=True) + "\n")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Receipt emission (best effort -- never raises)
# ---------------------------------------------------------------------------


async def _emit_receipt(type_: str, resource: str, payload: dict[str, Any]) -> None:
    try:
        from backend.core.receipts import record

        await record(type_, "agent_marketplace", resource, payload)
    except Exception as exc:  # noqa: BLE001
        log.debug("agent_marketplace.receipt_failed type=%s err=%s", type_, exc)


# ---------------------------------------------------------------------------
# GET /api/marketplace/agents -- browse
# ---------------------------------------------------------------------------


@router.get("")
async def browse_agents(
    pack: str | None = Query(default=None, description="filter by pack_slug"),
    sort: str = Query(default="installs", description="installs | rating | recent"),
    q: str | None = Query(default=None, description="substring search"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Return the published-agent registry, filtered + sorted."""

    rows = _read_jsonl(_registry_path())

    if pack:
        rows = [r for r in rows if str(r.get("agent", {}).get("pack_slug") or "") == pack]
    if q:
        needle = q.lower().strip()

        def _match(r: dict[str, Any]) -> bool:
            ag = r.get("agent") or {}
            blob = " ".join(
                str(ag.get(k) or "") for k in ("name", "description", "pack_slug")
            ).lower()
            return needle in blob

        rows = [r for r in rows if _match(r)]

    if sort == "rating":
        rows.sort(key=lambda r: float(r.get("stats", {}).get("rating") or 0.0), reverse=True)
    elif sort == "recent":
        rows.sort(key=lambda r: float(r.get("signed_at") or 0.0), reverse=True)
    else:  # installs (default)
        rows.sort(key=lambda r: int(r.get("stats", {}).get("installs") or 0), reverse=True)

    return {"ok": True, "count": len(rows), "agents": rows[:limit]}


# ---------------------------------------------------------------------------
# POST /api/marketplace/agents/publish
# ---------------------------------------------------------------------------


@router.post("/publish")
async def publish_agent(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Sign a local agent's config into a manifest and POST it upstream.

    Body: ``{agent_id, version, description}``.
    """

    body = payload or {}
    agent_id = str(body.get("agent_id") or "").strip()
    version = str(body.get("version") or "0.1.0").strip() or "0.1.0"
    description = str(body.get("description") or "").strip()
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id required")

    store = get_agent_store()
    agent = await store.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"agent not found: {agent_id}")

    inner = {
        "id": agent.id,
        "name": agent.name,
        "pack_slug": agent.pack_slug,
        "description": description or agent.description,
        "system_prompt": agent.system_prompt,
        "version": version,
    }
    manifest = _sign_manifest(inner)

    base = _registry_base_url()
    agent_uri = f"{base}/api/marketplace/agents/{agent.id}"

    upstream_ok = False
    upstream_err: str | None = None
    if not _is_offline():
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{base}/api/marketplace/agents",
                    json={"manifest": manifest, "agent_uri": agent_uri},
                )
                upstream_ok = 200 <= resp.status_code < 300
                if not upstream_ok:
                    upstream_err = f"{resp.status_code}:{resp.text[:120]}"
        except Exception as exc:  # noqa: BLE001
            upstream_err = str(exc)
            log.info("agent_marketplace.publish.upstream_failed err=%s", exc)
    else:
        _append_jsonl(
            _registry_path(),
            {
                **manifest,
                "agent_uri": agent_uri,
                "stats": {"installs": 0, "rating": 0.0},
            },
        )
        upstream_ok = True

    _append_jsonl(
        _published_path(),
        {
            "agent_id": agent.id,
            "version": version,
            "agent_uri": agent_uri,
            "upstream_ok": upstream_ok,
            "upstream_err": upstream_err,
            "manifest": manifest,
            "published_at": time.time(),
        },
    )

    await _emit_receipt(
        "agent_marketplace.published",
        agent.id,
        {
            "version": version,
            "agent_uri": agent_uri,
            "upstream_ok": upstream_ok,
        },
    )

    return {
        "ok": True,
        "agent_uri": agent_uri,
        "manifest": manifest,
        "upstream_ok": upstream_ok,
        "upstream_err": upstream_err,
    }


# ---------------------------------------------------------------------------
# POST /api/marketplace/agents/install
# ---------------------------------------------------------------------------


@router.post("/install")
async def install_agent(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Fetch a signed manifest by URI, verify, then install locally.

    Body: ``{agent_uri}`` (or inline ``{manifest}`` for tests).
    """

    body = payload or {}
    agent_uri = str(body.get("agent_uri") or "").strip()
    inline = body.get("manifest")
    if not agent_uri and not inline:
        raise HTTPException(status_code=400, detail="agent_uri or manifest required")

    manifest: dict[str, Any] | None = None
    if isinstance(inline, dict):
        manifest = inline
    elif _is_offline():
        for r in _read_jsonl(_registry_path()):
            if str(r.get("agent_uri") or "") == agent_uri:
                manifest = {k: v for k, v in r.items() if k != "stats"}
                break
        if manifest is None:
            raise HTTPException(
                status_code=404,
                detail=f"agent_uri not in offline registry: {agent_uri}",
            )
    else:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(agent_uri)
                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=502,
                        detail=f"upstream {resp.status_code}: {resp.text[:120]}",
                    )
                data = resp.json()
                manifest = data.get("manifest") if isinstance(data, dict) else None
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"fetch failed: {exc}")

    if not isinstance(manifest, dict):
        raise HTTPException(status_code=400, detail="manifest missing")
    if not _verify_manifest(manifest):
        raise HTTPException(status_code=400, detail="signature verification failed")

    inner = manifest.get("agent") or {}
    name = str(inner.get("name") or "").strip() or "Imported agent"
    pack_slug = str(inner.get("pack_slug") or "general").strip()
    description = str(inner.get("description") or "").strip()
    system_prompt = inner.get("system_prompt")

    store = get_agent_store()
    new_agent = await store.create_agent(
        name=name,
        pack_slug=pack_slug,
        description=description,
        system_prompt=system_prompt if isinstance(system_prompt, str) else None,
        wallet_address=None,
        metadata={
            "source": "marketplace",
            "source_agent_uri": agent_uri,
            "publisher": (manifest.get("publisher") or {}).get("tars_id"),
            "version": inner.get("version") or "0.1.0",
        },
    )

    _append_jsonl(
        _installed_path(),
        {
            "local_agent_id": new_agent.id,
            "remote_agent_id": inner.get("id"),
            "agent_uri": agent_uri,
            "version": inner.get("version") or "0.1.0",
            "publisher": (manifest.get("publisher") or {}).get("tars_id"),
            "installed_at": time.time(),
        },
    )

    await _emit_receipt(
        "agent_marketplace.installed",
        new_agent.id,
        {
            "agent_uri": agent_uri,
            "remote_id": inner.get("id"),
            "publisher": (manifest.get("publisher") or {}).get("tars_id"),
        },
    )

    return {
        "ok": True,
        "local_agent_id": new_agent.id,
        "name": new_agent.name,
        "pack_slug": new_agent.pack_slug,
        "agent_uri": agent_uri,
    }


# ---------------------------------------------------------------------------
# DELETE /api/marketplace/agents/{id}/uninstall
# ---------------------------------------------------------------------------


@router.delete("/{agent_id}/uninstall")
async def uninstall_agent(agent_id: str) -> dict[str, Any]:
    """Remove the local agent + its install record."""

    store = get_agent_store()
    agent = await store.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"agent not found: {agent_id}")

    from backend.core.agents.models import AgentStatus

    await store.patch_agent(agent_id, status=AgentStatus.ARCHIVED)

    installed = _read_jsonl(_installed_path())
    remaining = [r for r in installed if str(r.get("local_agent_id") or "") != agent_id]
    _rewrite_jsonl(_installed_path(), remaining)

    await _emit_receipt(
        "agent_marketplace.uninstalled",
        agent_id,
        {"removed_install_rows": len(installed) - len(remaining)},
    )

    return {"ok": True, "agent_id": agent_id, "archived": True}


# ---------------------------------------------------------------------------
# GET /api/marketplace/agents/published -- "my published" list
# ---------------------------------------------------------------------------


@router.get("/published")
async def my_published() -> dict[str, Any]:
    rows = _read_jsonl(_published_path())
    rows.sort(key=lambda r: float(r.get("published_at") or 0.0), reverse=True)
    return {"ok": True, "count": len(rows), "published": rows}


# ---------------------------------------------------------------------------
# GET /api/marketplace/agents/installed -- local installs
# ---------------------------------------------------------------------------


@router.get("/installed")
async def list_installed() -> dict[str, Any]:
    rows = _read_jsonl(_installed_path())
    rows.sort(key=lambda r: float(r.get("installed_at") or 0.0), reverse=True)
    return {"ok": True, "count": len(rows), "installed": rows}
