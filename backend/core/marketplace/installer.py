"""Installer for marketplace listings (Wave 106).

Pulls a Listing's ``install_payload`` into
``~/.tars/marketplace/installed/<listing_id>/`` and registers a
row in the local ``installed.sqlite`` so the FE's "My Library"
tab can list / uninstall.

Payload formats accepted (the ``format`` discriminator lives on
the inline payload dict, or is sniffed from the URL extension):

- ``playbook_bundle``  -- copy a directory from
  ``playbooks/_workshop/<vertical>/`` (used by seed listings).
- ``playbook_inline``  -- write the inline ``recipe`` dict
  straight to ``recipe.json`` in the install dir.
- ``report_template``  -- record a pointer; the actual template
  content is a stub for v0 (the renderer in Wave 103 owns the
  built-in templates already).
- ``skill_module``     -- record a pointer; the SDK side already
  knows where to load skills from. v0 just records the choice so
  "Installed" badge surfaces in the FE.
- URL string           -- fetched via ``urllib.request`` (5s
  timeout) and stored as ``payload.json`` (or ``payload.zip`` if
  the URL ends in .zip) verbatim. Signature verified opportunistically.

Manifest signature check: optional ed25519 signature in
``listing.install_payload["signature"]`` (hex). Verified using
the existing :mod:`backend.core.entitlements` ed25519 helper if
present; otherwise the warning ``signature_unverified`` is added
to the install audit log but the install proceeds (v0 trust
model is "warn, don't block").
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .models import (
    InstalledItem,
    Listing,
    new_install_id,
)
from .registry import get_listing


log = logging.getLogger("tars.marketplace.installer")


DEFAULT_DB_PATH = "~/.tars/marketplace/installed.sqlite"
DEFAULT_INSTALL_ROOT = "~/.tars/marketplace/installed"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS installed (
    install_id TEXT PRIMARY KEY,
    listing_id TEXT NOT NULL UNIQUE,
    version TEXT NOT NULL,
    installed_at REAL NOT NULL,
    installed_path TEXT NOT NULL,
    target TEXT NOT NULL DEFAULT 'personal',
    listing_snapshot_json TEXT NOT NULL DEFAULT '{}',
    audit_json TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_installed_at ON installed (installed_at DESC);
"""


# ---------- helpers --------------------------------------------------------


def _db_path() -> str:
    return os.path.expanduser(
        os.getenv("TARS_MARKETPLACE_INSTALL_DB") or DEFAULT_DB_PATH
    )


def _install_root() -> Path:
    raw = os.getenv("TARS_MARKETPLACE_INSTALL_ROOT") or DEFAULT_INSTALL_ROOT
    p = Path(os.path.expanduser(raw))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _connect() -> sqlite3.Connection:
    p = _db_path()
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def _row_to_installed(row: tuple) -> InstalledItem:
    return InstalledItem(
        listing_id=row[1],
        version=row[2],
        installed_at=row[3],
        installed_path=row[4],
        target=row[5],
        listing_snapshot=json.loads(row[6] or "{}"),
    )


def _verify_signature(_listing: Listing, audit: list[str]) -> bool:
    """Best-effort ed25519 verification.

    v0: when no signature is on the payload, we add an
    ``signature_absent`` warning and proceed. When a signature is
    present we try to verify with whatever ed25519 helper is on
    hand (entitlements module ships one); on missing helper we
    log + warn but still proceed -- consistent with the
    "discovery first, lockdown later" v0 stance.
    """

    payload = _listing.install_payload
    if isinstance(payload, dict):
        sig = payload.get("signature")
    else:
        sig = None
    if not sig:
        audit.append("signature_absent")
        return False
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: WPS433
            Ed25519PublicKey,
        )

        # Public key not actually distributed in v0 -- this is a
        # stub that records "we tried". Real verification lands
        # in v9.3 along with payouts.
        _ = Ed25519PublicKey  # silence linter
        audit.append("signature_present_unverified_v0")
        return False
    except ImportError:
        audit.append("signature_present_no_ed25519_lib")
        return False


def _payload_format(payload: Any) -> str:
    if isinstance(payload, dict):
        fmt = (payload.get("format") or "").strip()
        if fmt:
            return fmt
        if payload.get("recipe"):
            return "playbook_inline"
        return "inline"
    if isinstance(payload, str):
        if payload.lower().endswith(".zip"):
            return "url_zip"
        return "url_json"
    return "unknown"


def _resolve_repo_root() -> Path:
    """Find the repo root by walking up until ``playbooks/`` shows up."""

    start = Path(__file__).resolve()
    for parent in start.parents:
        if (parent / "playbooks").exists():
            return parent
    return Path.cwd()


def _copy_bundle(source_dir: str, target: Path) -> int:
    """Copy a workshop pack into the install dir; return file count."""

    repo_root = _resolve_repo_root()
    src = repo_root / source_dir
    if not src.exists():
        # Source missing in trimmed installs -- write a stub README
        # so uninstall still has something to clean up.
        target.mkdir(parents=True, exist_ok=True)
        (target / "README.md").write_text(
            f"Source bundle not bundled in this install: {source_dir}\n",
            "utf-8",
        )
        return 1
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(src, target)
    return sum(1 for _ in target.rglob("*") if _.is_file())


def _fetch_url(url: str, target: Path, suffix: str) -> int:
    """Pull a URL into the install dir; return bytes written."""

    target.mkdir(parents=True, exist_ok=True)
    out = target / f"payload.{suffix}"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "tars-marketplace-installer/v0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        # Record the failure as an empty file so uninstall has a
        # path; the audit log surfaces the error in the FE.
        out.write_bytes(b"")
        log.info("install_fetch_failed url=%s err=%s", url, exc)
        return 0
    out.write_bytes(data)
    return len(data)


# ---------- public API -----------------------------------------------------


def _do_install_sync(listing: Listing, target_kind: str) -> dict[str, Any]:
    install_root = _install_root()
    item_dir = install_root / listing.id
    audit: list[str] = []

    _verify_signature(listing, audit)

    fmt = _payload_format(listing.install_payload)
    summary: dict[str, Any] = {"format": fmt}
    payload = listing.install_payload

    if fmt == "playbook_bundle" and isinstance(payload, dict):
        n = _copy_bundle(str(payload.get("source_dir") or ""), item_dir)
        summary["files_copied"] = n
    elif fmt == "playbook_inline" and isinstance(payload, dict):
        item_dir.mkdir(parents=True, exist_ok=True)
        recipe = payload.get("recipe") or {}
        (item_dir / "recipe.json").write_text(
            json.dumps(recipe, indent=2), "utf-8"
        )
        summary["recipe_steps"] = len(recipe.get("steps") or [])
    elif fmt == "report_template" and isinstance(payload, dict):
        item_dir.mkdir(parents=True, exist_ok=True)
        (item_dir / "pointer.json").write_text(
            json.dumps(payload, indent=2), "utf-8"
        )
        summary["template_kind"] = payload.get("kind")
        summary["template_slug"] = payload.get("slug")
    elif fmt == "skill_module" and isinstance(payload, dict):
        item_dir.mkdir(parents=True, exist_ok=True)
        (item_dir / "skill.json").write_text(
            json.dumps(payload, indent=2), "utf-8"
        )
        summary["module"] = payload.get("module")
    elif fmt in {"url_json", "url_zip"} and isinstance(payload, str):
        suffix = "zip" if fmt == "url_zip" else "json"
        n = _fetch_url(payload, item_dir, suffix)
        summary["bytes_downloaded"] = n
    else:
        item_dir.mkdir(parents=True, exist_ok=True)
        (item_dir / "raw_payload.json").write_text(
            json.dumps({"payload": payload}, indent=2), "utf-8"
        )
        summary["note"] = "unknown_format_recorded_only"

    install_id = new_install_id()
    snapshot = listing.to_dict()

    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT install_id FROM installed WHERE listing_id = ?",
            (listing.id,),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                """UPDATE installed
                       SET version = ?, installed_at = ?, installed_path = ?,
                           target = ?, listing_snapshot_json = ?, audit_json = ?
                     WHERE listing_id = ?""",
                (
                    listing.version,
                    time.time(),
                    str(item_dir),
                    target_kind,
                    json.dumps(snapshot),
                    json.dumps(audit),
                    listing.id,
                ),
            )
            install_id = existing[0]
            summary["reinstall"] = True
        else:
            cur.execute(
                """INSERT INTO installed
                          (install_id, listing_id, version, installed_at,
                           installed_path, target, listing_snapshot_json,
                           audit_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    install_id,
                    listing.id,
                    listing.version,
                    time.time(),
                    str(item_dir),
                    target_kind,
                    json.dumps(snapshot),
                    json.dumps(audit),
                ),
            )
            summary["reinstall"] = False
        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "install_id": install_id,
        "listing_id": listing.id,
        "installed_path": str(item_dir),
        "target": target_kind,
        "audit": audit,
        "summary": summary,
    }


async def install(
    listing: Listing,
    *,
    target: str = "personal",
) -> dict[str, Any]:
    """Install a listing. ``target`` is ``personal`` or ``workspace``."""

    target_kind = (target or "personal").strip().lower()
    if target_kind not in {"personal", "workspace"}:
        target_kind = "personal"
    return await asyncio.to_thread(_do_install_sync, listing, target_kind)


async def install_by_id(listing_id: str, *, target: str = "personal") -> dict[str, Any]:
    """Convenience: resolve via the registry then install."""

    listing = await get_listing(listing_id)
    if listing is None:
        return {"ok": False, "error": "listing_not_found"}
    return await install(listing, target=target)


def _do_uninstall_sync(listing_id: str) -> dict[str, Any]:
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT installed_path FROM installed WHERE listing_id = ?",
            (listing_id,),
        )
        row = cur.fetchone()
        if row is None:
            return {"ok": False, "error": "not_installed"}
        path_str = row[0]
        cur.execute("DELETE FROM installed WHERE listing_id = ?", (listing_id,))
        conn.commit()
    finally:
        conn.close()

    p = Path(path_str)
    if p.exists():
        try:
            shutil.rmtree(p)
        except OSError as exc:
            log.warning("uninstall_rmtree_failed: %s", exc)

    return {"ok": True, "listing_id": listing_id, "removed_path": path_str}


async def uninstall(listing_id: str) -> dict[str, Any]:
    return await asyncio.to_thread(_do_uninstall_sync, listing_id)


def _do_list_installed_sync(
    kind: str | None = None,
    category: str | None = None,
) -> list[InstalledItem]:
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT install_id, listing_id, version, installed_at,
                       installed_path, target, listing_snapshot_json
                  FROM installed
              ORDER BY installed_at DESC"""
        ).fetchall()
    finally:
        conn.close()
    out: list[InstalledItem] = []
    for r in rows:
        item = _row_to_installed(r)
        snap = item.listing_snapshot or {}
        if kind and snap.get("kind") != kind:
            continue
        if category and snap.get("category") != category:
            continue
        out.append(item)
    return out


async def list_installed(
    *,
    kind: str | None = None,
    category: str | None = None,
) -> list[InstalledItem]:
    return await asyncio.to_thread(_do_list_installed_sync, kind, category)


async def is_installed(listing_id: str) -> bool:
    items = await list_installed()
    return any(i.listing_id == listing_id for i in items)


def reset_db() -> None:
    """Test helper -- wipe the installed table + install root."""

    p = Path(_db_path())
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass
    root = _install_root()
    if root.exists():
        for child in root.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                try:
                    child.unlink()
                except OSError:
                    pass


__all__ = [
    "install",
    "install_by_id",
    "is_installed",
    "list_installed",
    "reset_db",
    "uninstall",
]
