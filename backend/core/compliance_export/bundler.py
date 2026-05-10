"""Audit-grade compliance bundle builder (Wave 104).

A single :func:`build_bundle` call collects all TARS state in the
requested time range, packages it as a deterministic ``tar.gz`` at
``~/.tars/exports/audit-<timestamp>.tar.gz``, signs the manifest
with the host receipt key (Wave 95), and records a
``compliance.bundle_generated`` receipt.

The bundle is laid out so an auditor with the included
``README.md`` and ``signature.txt`` can verify both individual
file integrity (sha256 in ``manifest.json``) and the cryptographic
signature over the manifest itself — without any TARS-specific
tooling beyond the ``cryptography`` package.

Scope categories (default == "all"):

- ``receipts``    — NDJSON per day + merkle_roots + chain verification
- ``cohort``      — cohorts + attendees + timelines
- ``connectors``  — pull activity per connector
- ``hil``         — HIL approval log (decided actions)
- ``outreach``    — drafts + sends + recipients
- ``files``       — file manifest (blobs only when ``blobs`` in scope)
- ``wallet``      — wallet audit / signed events
- ``org``         — org info + invites
- ``playbooks``   — playbook run history
- ``agents``      — agent definitions
- ``webhooks``    — outgoing deliveries + incoming events
- ``blobs``       — include actual file blobs (large; opt-in)
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import sqlite3
import tarfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


log = logging.getLogger("tars.compliance_export")


DEFAULT_OUTPUT_DIR = "~/.tars/exports"
SIZE_WARN_BYTES = 500 * 1024 * 1024  # 500 MiB

SCOPE_CATEGORIES = (
    "receipts",
    "cohort",
    "connectors",
    "hil",
    "outreach",
    "files",
    "wallet",
    "org",
    "playbooks",
    "agents",
    "webhooks",
    "blobs",
)

DEFAULT_SCOPE: tuple[str, ...] = (
    "receipts",
    "cohort",
    "connectors",
    "hil",
    "outreach",
    "files",
    "wallet",
    "org",
    "playbooks",
    "agents",
    "webhooks",
)


def _resolve_output_dir(override: str | None = None) -> str:
    raw = override or os.getenv("TARS_EXPORT_DIR") or DEFAULT_OUTPUT_DIR
    return os.path.expanduser(raw)


def _new_bundle_id() -> str:
    return f"bundle_{uuid.uuid4().hex[:16]}"


def _utc_iso(ts: float | None = None) -> str:
    if ts is None:
        ts = time.time()
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def _parse_iso(s: str) -> float:
    """Permissive ISO parser (date or datetime, optional Z)."""
    if not s:
        raise ValueError("empty iso string")
    try:
        if "T" not in s:
            dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            v = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception as exc:  # pragma: no cover -- bad input
        raise ValueError(f"bad iso datetime: {s!r}: {exc}") from exc


def _expand_scope(scope: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    """Normalise scope: ``["all"]`` → DEFAULT_SCOPE; unknown items dropped."""
    if not scope:
        return tuple(DEFAULT_SCOPE)
    items = [str(s).strip().lower() for s in scope if str(s).strip()]
    if "all" in items:
        out = list(DEFAULT_SCOPE)
        if "blobs" in items:
            out.append("blobs")
        return tuple(out)
    valid = [s for s in items if s in SCOPE_CATEGORIES]
    return tuple(valid) if valid else tuple(DEFAULT_SCOPE)


# ----- Bundle dataclass ---------------------------------------------------


@dataclass
class Bundle:
    """Result of a :func:`build_bundle` call.

    ``manifest_hash`` is the sha256 hex of the canonical ``manifest.json``
    bytes; ``signature`` is the base64 ed25519 signature of the same
    bytes using the host receipt key (Wave 95).
    """

    id: str
    started_at: float
    completed_at: float | None
    since_iso: str
    until_iso: str
    output_path: str
    status: str
    manifest_hash: str
    signature: str
    scope: list[str] = field(default_factory=list)
    file_count: int = 0
    total_bytes: int = 0
    redacted: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["scope"] = list(self.scope)
        return d


# ----- Collectors ---------------------------------------------------------
#
# Each collector returns a list of (relpath, bytes) pairs. They are
# resilient by design: failure to import / open a backing store
# returns a stub readme rather than aborting the whole bundle.


async def _collect_receipts(since: float, until: float) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    try:
        from backend.core.receipts import get_store, verify_chain
    except Exception as exc:  # pragma: no cover - import-time
        return [("receipts/README.txt",
                 f"receipts module unavailable: {exc}\n".encode())]
    store = get_store()
    if store is None:
        return [("receipts/README.txt",
                 b"receipt store disabled (TARS_RECEIPT_STORE=disabled)\n")]
    # Walk every day in the range and dump the NDJSON.
    start_day = datetime.fromtimestamp(since, tz=timezone.utc).date()
    end_day = datetime.fromtimestamp(until, tz=timezone.utc).date()
    day = start_day
    merkle_roots: dict[str, dict[str, Any]] = {}
    chain_walk: dict[str, Any] = {"days": {}, "ok": True}
    while day <= end_day:
        day_iso = day.strftime("%Y-%m-%d")
        try:
            receipts = await store.replay_chain_for_day(day_iso)
        except Exception:
            receipts = []
        if receipts:
            lines = "\n".join(
                json.dumps(r.to_dict(), sort_keys=True) for r in receipts
            ) + "\n"
            out.append((f"receipts/{day_iso}.ndjson", lines.encode("utf-8")))
            try:
                walk = verify_chain(receipts)
            except Exception as exc:
                walk = {"ok": False, "reason": f"verify_error: {exc}"}
            chain_walk["days"][day_iso] = walk
            if not walk.get("ok"):
                chain_walk["ok"] = False
        try:
            mk = await store.get_merkle_root(day_iso)
        except Exception:
            mk = None
        if mk is not None:
            merkle_roots[day_iso] = {
                "id": mk.id,
                "day_iso": mk.day_iso,
                "root_hex": mk.root_hex,
                "leaf_count": mk.leaf_count,
                "anchored_at": mk.anchored_at,
                "solana_signature": mk.solana_signature,
                "created_at": mk.created_at,
            }
        day = day + timedelta(days=1)
    out.append((
        "receipts/merkle_roots.json",
        json.dumps(merkle_roots, indent=2, sort_keys=True).encode("utf-8"),
    ))
    out.append((
        "receipts/chain_verification.json",
        json.dumps(chain_walk, indent=2, sort_keys=True).encode("utf-8"),
    ))
    return out


async def _collect_cohort(since: float, until: float) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    try:
        from backend.core.cohort import get_store
    except Exception as exc:
        return [("cohort/README.txt",
                 f"cohort module unavailable: {exc}\n".encode())]
    try:
        store = get_store()
        if not getattr(store, "enabled", True):
            return [("cohort/README.txt",
                     b"cohort store disabled (TARS_COHORT_STORE=disabled)\n")]
    except Exception as exc:
        return [("cohort/README.txt", f"cohort init failed: {exc}\n".encode())]
    cohorts: list[dict[str, Any]] = []
    try:
        rows = await store.list_cohorts() if hasattr(store, "list_cohorts") else []
    except Exception:
        rows = []
    for c in rows or []:
        as_dict = c.to_dict() if hasattr(c, "to_dict") else dict(c)
        cohorts.append(as_dict)
        cid = as_dict.get("id")
        if not cid:
            continue
        try:
            attendees = await store.list_attendees(cid) if hasattr(store, "list_attendees") else []
        except Exception:
            attendees = []
        timeline_block: dict[str, Any] = {
            "cohort": as_dict,
            "attendees": [
                a.to_dict() if hasattr(a, "to_dict") else dict(a)
                for a in attendees or []
            ],
            "timelines": {},
        }
        for a in attendees or []:
            aid = a.id if hasattr(a, "id") else a.get("id")
            if not aid:
                continue
            try:
                actions = await store.list_actions(aid) if hasattr(store, "list_actions") else []
            except Exception:
                actions = []
            timeline_block["timelines"][aid] = [
                ac.to_dict() if hasattr(ac, "to_dict") else dict(ac)
                for ac in actions or []
            ]
        out.append((
            f"cohort/{cid}.json",
            json.dumps(timeline_block, indent=2, sort_keys=True, default=str).encode("utf-8"),
        ))
    out.append((
        "cohort/cohorts.json",
        json.dumps(cohorts, indent=2, sort_keys=True, default=str).encode("utf-8"),
    ))
    return out


async def _collect_connectors(since: float, until: float) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    activity: dict[str, list[dict[str, Any]]] = {
        "slack": [], "gmail": [], "calendar": [], "github": [],
    }
    # Replay receipts for connector.* events as the activity log.
    try:
        from backend.core.receipts import get_store
        store = get_store()
        if store is not None:
            rs = await store.query(since=since, until=until, limit=10000)
            for r in rs:
                if r.type and r.type.startswith("connector."):
                    parts = r.type.split(".")
                    bucket = parts[1] if len(parts) > 1 else "unknown"
                    activity.setdefault(bucket, []).append({
                        "id": r.id,
                        "ts": r.ts,
                        "type": r.type,
                        "actor": r.actor,
                        "resource": r.resource,
                        "payload": r.payload,
                    })
    except Exception as exc:
        log.debug("connectors collector swallow: %s", exc)
    for name, rows in activity.items():
        out.append((
            f"connectors/{name}.json",
            json.dumps(rows, indent=2, sort_keys=True, default=str).encode("utf-8"),
        ))
    out.append((
        "connectors/README.txt",
        (
            "Connector activity history reconstructed from the receipt\n"
            "ledger by filtering type prefixes (connector.<name>.<event>).\n"
        ).encode("utf-8"),
    ))
    return out


async def _collect_hil(since: float, until: float) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    rows: list[dict[str, Any]] = []
    try:
        from backend.core.receipts import get_store
        store = get_store()
        if store is not None:
            rs = await store.query(since=since, until=until, limit=10000)
            for r in rs:
                t = (r.type or "").lower()
                if t.startswith("hil.") or t.startswith("policy.confirm"):
                    rows.append({
                        "id": r.id,
                        "ts": r.ts,
                        "action_type": r.type,
                        "decided_by": r.actor,
                        "decided_at": r.ts,
                        "resource": r.resource,
                        "reason": (r.payload or {}).get("reason"),
                        "outcome": (r.payload or {}).get("outcome"),
                        "payload": r.payload,
                    })
    except Exception as exc:
        log.debug("hil collector swallow: %s", exc)
    out.append((
        "hil/approval_log.json",
        json.dumps(rows, indent=2, sort_keys=True, default=str).encode("utf-8"),
    ))
    out.append((
        "hil/README.txt",
        b"HIL approval log derived from policy.confirm + hil.* receipts.\n",
    ))
    return out


async def _collect_outreach(since: float, until: float) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    try:
        from backend.core.outreach.store import get_store as _get
    except Exception as exc:
        return [("outreach/README.txt",
                 f"outreach module unavailable: {exc}\n".encode())]
    drafts: list[dict[str, Any]] = []
    sends: list[dict[str, Any]] = []
    recipients: list[dict[str, Any]] = []
    try:
        store = _get()
        if hasattr(store, "list_drafts"):
            ds = await store.list_drafts(since=since, until=until)
            drafts = [d.to_dict() if hasattr(d, "to_dict") else dict(d) for d in ds or []]
        if hasattr(store, "list_sends"):
            ss = await store.list_sends(since=since, until=until)
            sends = [s.to_dict() if hasattr(s, "to_dict") else dict(s) for s in ss or []]
        if hasattr(store, "list_recipients"):
            rs = await store.list_recipients()
            recipients = [r.to_dict() if hasattr(r, "to_dict") else dict(r) for r in rs or []]
    except Exception as exc:
        log.debug("outreach collector swallow: %s", exc)
    out.append((
        "outreach/drafts.json",
        json.dumps(drafts, indent=2, sort_keys=True, default=str).encode("utf-8"),
    ))
    out.append((
        "outreach/sends.json",
        json.dumps(sends, indent=2, sort_keys=True, default=str).encode("utf-8"),
    ))
    out.append((
        "outreach/recipients.json",
        json.dumps(recipients, indent=2, sort_keys=True, default=str).encode("utf-8"),
    ))
    return out


async def _collect_files(since: float, until: float, include_blobs: bool) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    files: list[dict[str, Any]] = []
    blobs: list[tuple[str, bytes]] = []
    candidates = [
        ("backend.core.attachments.store", "get_store"),
    ]
    for module_name, fn_name in candidates:
        try:
            mod = __import__(module_name, fromlist=[fn_name])
            fn = getattr(mod, fn_name, None)
            if fn is None:
                continue
            store = fn()
            if hasattr(store, "list_files"):
                rows = await store.list_files()
            elif hasattr(store, "list_attachments"):
                rows = await store.list_attachments()
            else:
                rows = []
            for r in rows or []:
                d = r.to_dict() if hasattr(r, "to_dict") else dict(r)
                files.append({
                    "id": d.get("id"),
                    "name": d.get("name") or d.get("filename"),
                    "hash": d.get("hash") or d.get("sha256"),
                    "size": d.get("size") or d.get("bytes"),
                    "category": d.get("category"),
                    "tags": d.get("tags") or [],
                    "created_at": d.get("created_at"),
                })
                if include_blobs:
                    path = d.get("path") or d.get("file_path")
                    if path and os.path.exists(path):
                        try:
                            with open(path, "rb") as fh:
                                blobs.append((f"files/blobs/{d.get('id')}", fh.read()))
                        except Exception:
                            pass
        except Exception as exc:
            log.debug("files collector swallow %s: %s", module_name, exc)
    out.append((
        "files/manifest.json",
        json.dumps(files, indent=2, sort_keys=True, default=str).encode("utf-8"),
    ))
    out.extend(blobs)
    if not include_blobs:
        out.append((
            "files/README.txt",
            (b"Blobs not included; pass scope=['all','blobs'] to embed them.\n"),
        ))
    return out


async def _collect_wallet(since: float, until: float) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    rows: list[dict[str, Any]] = []
    try:
        from backend.core.meeet import get_store as _get
        store = _get()
        if store is not None and hasattr(store, "list_kind_prefix"):
            rows = await store.list_kind_prefix(prefix="wallet.", limit=10000)
            rows = [
                r if isinstance(r, dict) else (r.to_dict() if hasattr(r, "to_dict") else dict(r))
                for r in rows or []
            ]
    except Exception as exc:
        log.debug("wallet meeet store swallow: %s", exc)
    if not rows:
        # fall back to receipts for wallet.*
        try:
            from backend.core.receipts import get_store
            store = get_store()
            if store is not None:
                rs = await store.query(since=since, until=until, limit=10000)
                rows = [
                    {
                        "id": r.id, "ts": r.ts, "type": r.type, "actor": r.actor,
                        "resource": r.resource, "payload": r.payload,
                    }
                    for r in rs if (r.type or "").startswith("wallet.")
                ]
        except Exception:
            rows = []
    out.append((
        "wallet/audit.json",
        json.dumps(rows, indent=2, sort_keys=True, default=str).encode("utf-8"),
    ))
    return out


async def _collect_org(since: float, until: float) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    org_info: dict[str, Any] = {}
    invites: list[dict[str, Any]] = []
    try:
        from backend.core.org.store import get_store as _get
        store = _get()
        if hasattr(store, "get_org"):
            o = await store.get_org()
            if o is not None:
                org_info = o.to_dict() if hasattr(o, "to_dict") else dict(o)
        if hasattr(store, "list_invites"):
            inv = await store.list_invites()
            invites = [i.to_dict() if hasattr(i, "to_dict") else dict(i) for i in inv or []]
    except Exception as exc:
        log.debug("org collector swallow: %s", exc)
    out.append((
        "org/info.json",
        json.dumps(org_info, indent=2, sort_keys=True, default=str).encode("utf-8"),
    ))
    out.append((
        "org/invites.json",
        json.dumps(invites, indent=2, sort_keys=True, default=str).encode("utf-8"),
    ))
    return out


async def _collect_playbooks(since: float, until: float) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    runs: list[dict[str, Any]] = []
    try:
        from backend.core.receipts import get_store
        store = get_store()
        if store is not None:
            rs = await store.query(since=since, until=until, limit=10000)
            for r in rs:
                if (r.type or "").startswith("playbook."):
                    runs.append({
                        "id": r.id, "ts": r.ts, "type": r.type, "actor": r.actor,
                        "resource": r.resource, "payload": r.payload,
                    })
    except Exception:
        pass
    out.append((
        "playbooks/runs.json",
        json.dumps(runs, indent=2, sort_keys=True, default=str).encode("utf-8"),
    ))
    return out


async def _collect_agents(since: float, until: float) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    agents: list[dict[str, Any]] = []
    try:
        from backend.core.agents.store import get_store as _get
        store = _get()
        if hasattr(store, "list_agents"):
            rows = await store.list_agents()
            agents = [a.to_dict() if hasattr(a, "to_dict") else dict(a) for a in rows or []]
    except Exception as exc:
        log.debug("agents collector swallow: %s", exc)
    out.append((
        "agents/definitions.json",
        json.dumps(agents, indent=2, sort_keys=True, default=str).encode("utf-8"),
    ))
    return out


async def _collect_webhooks(since: float, until: float) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    outgoing: list[dict[str, Any]] = []
    incoming: list[dict[str, Any]] = []
    try:
        from backend.core.webhooks.store import get_store as _get
        store = _get()
        if hasattr(store, "list_deliveries"):
            d = await store.list_deliveries(since=since, until=until)
            outgoing = [r.to_dict() if hasattr(r, "to_dict") else dict(r) for r in d or []]
        if hasattr(store, "list_inbox"):
            i = await store.list_inbox(since=since, until=until)
            incoming = [r.to_dict() if hasattr(r, "to_dict") else dict(r) for r in i or []]
    except Exception as exc:
        log.debug("webhooks collector swallow: %s", exc)
    out.append((
        "webhooks/outgoing.json",
        json.dumps(outgoing, indent=2, sort_keys=True, default=str).encode("utf-8"),
    ))
    out.append((
        "webhooks/incoming.json",
        json.dumps(incoming, indent=2, sort_keys=True, default=str).encode("utf-8"),
    ))
    return out


# ----- README generation --------------------------------------------------


def _readme(bundle_id: str, since_iso: str, until_iso: str,
            scope: tuple[str, ...], file_count: int, redacted: bool) -> bytes:
    lines = [
        "# TARS Audit-Grade Compliance Bundle",
        "",
        f"Bundle ID: {bundle_id}",
        f"Window: {since_iso} -> {until_iso}",
        f"Scope: {', '.join(scope)}",
        f"File count: {file_count}",
        f"PII redaction: {'on' if redacted else 'off'}",
        "",
        "## Layout",
        "",
        "- manifest.json           — versioning + per-file sha256 index",
        "- signature.txt           — ed25519 signature over manifest.json",
        "- receipts/               — NDJSON per day + merkle_roots + chain_verification",
        "- cohort/                 — cohort exports + attendee timelines",
        "- connectors/             — pull activity per connector",
        "- hil/                    — approval_log.json (decided actions)",
        "- outreach/               — drafts + sends + recipients",
        "- files/                  — manifest.json (+ blobs/ if scope has 'blobs')",
        "- wallet/                 — wallet audit / signed events",
        "- org/                    — info + invites",
        "- playbooks/              — runs.json",
        "- agents/                 — definitions.json",
        "- webhooks/               — outgoing + incoming",
        "",
        "## Verification (3 steps)",
        "",
        "1. Recompute every file's sha256 and compare against",
        "   manifest.json.files[*].sha256.",
        "2. Read signature.txt → base64 decode → verify against",
        "   manifest.json bytes using the ed25519 public key in",
        "   manifest.json.signing_key_b64.",
        "3. Walk receipts/*.ndjson in chronological order: for each",
        "   line re-derive the sha256 over (prev_hash, ts, type,",
        "   actor, resource, payload) and confirm it matches `hash`,",
        "   and that the next receipt's prev_hash equals this one.",
        "",
        "Compare to receipts/chain_verification.json which TARS",
        "computed at bundle time — both walks should agree.",
        "",
        "## Recommended retention",
        "",
        "Most fund regulations require keeping export bundles for 7",
        "years. Store the bundle alongside the host signing key",
        "fingerprint (manifest.json.signing_key_fingerprint) so a",
        "future auditor can confirm provenance.",
        "",
    ]
    return ("\n".join(lines)).encode("utf-8")


# ----- Manifest + signing -------------------------------------------------


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sign_bytes(data: bytes) -> tuple[str, str, str]:
    """Return (signature_b64, public_key_b64, fingerprint).

    Lazy-loads the receipt host key (Wave 95) so non-receipt code
    paths don't pay the import cost. Falls back to a deterministic
    placeholder signature when the receipt module is unavailable —
    the bundle is still verifiable for hash integrity, just not
    cryptographically signed.
    """

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )
        from backend.core.receipts.store import (
            _resolve_host_key_path,
            _load_or_create_host_key,
        )
        path = _resolve_host_key_path()
        priv, pub = _load_or_create_host_key(path)
        sk = Ed25519PrivateKey.from_private_bytes(priv)
        sig = sk.sign(data)
        sig_b64 = base64.b64encode(sig).decode("ascii")
        pub_b64 = base64.b64encode(pub).decode("ascii")
        fp = _sha256(pub)[:16]
        return sig_b64, pub_b64, fp
    except Exception as exc:
        log.warning("compliance bundle signing fallback: %s", exc)
        h = _sha256(data)
        return f"unsigned:{h}", "", "unsigned"


def _build_manifest(
    *,
    bundle_id: str,
    since_iso: str,
    until_iso: str,
    scope: tuple[str, ...],
    files: list[tuple[str, bytes]],
    redacted: bool,
    pub_b64: str,
    fingerprint: str,
) -> dict[str, Any]:
    file_index = []
    total_bytes = 0
    for relpath, data in files:
        file_index.append({
            "path": relpath,
            "sha256": _sha256(data),
            "size": len(data),
        })
        total_bytes += len(data)
    file_index.sort(key=lambda r: r["path"])
    return {
        "bundle_id": bundle_id,
        "contract_version": "1.0",
        "wave": 104,
        "generated_at": _utc_iso(),
        "since": since_iso,
        "until": until_iso,
        "scope": list(scope),
        "redacted": bool(redacted),
        "signing_key_b64": pub_b64,
        "signing_key_fingerprint": fingerprint,
        "file_count": len(file_index),
        "total_bytes": total_bytes,
        "files": file_index,
    }


# ----- Bundle list/index --------------------------------------------------


_INDEX_FILENAME = "_index.json"


def _index_path(output_dir: str) -> str:
    return os.path.join(output_dir, _INDEX_FILENAME)


def _read_index(output_dir: str) -> list[dict[str, Any]]:
    p = _index_path(output_dir)
    if not os.path.exists(p):
        return []
    try:
        return json.loads(Path(p).read_text("utf-8"))
    except Exception:
        return []


def _write_index(output_dir: str, rows: list[dict[str, Any]]) -> None:
    os.makedirs(output_dir, exist_ok=True)
    Path(_index_path(output_dir)).write_text(
        json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8",
    )


def list_bundles(output_dir: str | None = None) -> list[dict[str, Any]]:
    """Return all known bundles' metadata, newest first."""
    out_dir = _resolve_output_dir(output_dir)
    rows = _read_index(out_dir)
    rows.sort(key=lambda r: r.get("started_at", 0), reverse=True)
    return rows


def get_bundle(bundle_id: str, output_dir: str | None = None) -> dict[str, Any] | None:
    for r in list_bundles(output_dir):
        if r.get("id") == bundle_id:
            return r
    return None


def delete_bundle(bundle_id: str, output_dir: str | None = None) -> bool:
    out_dir = _resolve_output_dir(output_dir)
    rows = _read_index(out_dir)
    found = None
    keep: list[dict[str, Any]] = []
    for r in rows:
        if r.get("id") == bundle_id:
            found = r
        else:
            keep.append(r)
    if not found:
        return False
    path = found.get("output_path")
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
    _write_index(out_dir, keep)
    return True


# ----- Public entry -------------------------------------------------------


async def build_bundle(
    since: str,
    until: str,
    scope: list[str] | None = None,
    *,
    output_dir: str | None = None,
    redact_pii: bool = False,
) -> Bundle:
    """Build the audit bundle and write it to disk.

    ``since`` / ``until`` are ISO-8601 (date or datetime). ``scope``
    defaults to ``["all"]``. ``redact_pii`` runs the redaction
    layer over every JSON payload before tarring.
    """

    since_ts = _parse_iso(since)
    until_ts = _parse_iso(until)
    if until_ts < since_ts:
        raise ValueError("until must be >= since")
    scope_t = _expand_scope(scope)
    bundle_id = _new_bundle_id()
    started_at = time.time()
    out_dir = _resolve_output_dir(output_dir)
    os.makedirs(out_dir, exist_ok=True)
    fname = f"audit-{datetime.fromtimestamp(started_at, tz=timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.tar.gz"
    output_path = os.path.join(out_dir, fname)

    files: list[tuple[str, bytes]] = []

    if "receipts" in scope_t:
        files.extend(await _collect_receipts(since_ts, until_ts))
    if "cohort" in scope_t:
        files.extend(await _collect_cohort(since_ts, until_ts))
    if "connectors" in scope_t:
        files.extend(await _collect_connectors(since_ts, until_ts))
    if "hil" in scope_t:
        files.extend(await _collect_hil(since_ts, until_ts))
    if "outreach" in scope_t:
        files.extend(await _collect_outreach(since_ts, until_ts))
    if "files" in scope_t:
        files.extend(await _collect_files(
            since_ts, until_ts, include_blobs="blobs" in scope_t
        ))
    if "wallet" in scope_t:
        files.extend(await _collect_wallet(since_ts, until_ts))
    if "org" in scope_t:
        files.extend(await _collect_org(since_ts, until_ts))
    if "playbooks" in scope_t:
        files.extend(await _collect_playbooks(since_ts, until_ts))
    if "agents" in scope_t:
        files.extend(await _collect_agents(since_ts, until_ts))
    if "webhooks" in scope_t:
        files.extend(await _collect_webhooks(since_ts, until_ts))

    # Optional PII redaction over every JSON payload.
    if redact_pii:
        from .redaction import redact_bytes
        redacted_files: list[tuple[str, bytes]] = []
        for relpath, data in files:
            if relpath.endswith(".json") or relpath.endswith(".ndjson"):
                try:
                    data = redact_bytes(data)
                except Exception as exc:
                    log.debug("redaction skipped %s: %s", relpath, exc)
            redacted_files.append((relpath, data))
        files = redacted_files

    # README is generated last so file count is correct (sans manifest +
    # signature + readme themselves).
    readme = _readme(
        bundle_id, _utc_iso(since_ts), _utc_iso(until_ts),
        scope_t, len(files) + 3, redact_pii,
    )
    files.append(("README.md", readme))

    # Build manifest BEFORE signing.
    sig_placeholder, pub_b64, fingerprint = _sign_bytes(b"placeholder")
    manifest = _build_manifest(
        bundle_id=bundle_id,
        since_iso=_utc_iso(since_ts),
        until_iso=_utc_iso(until_ts),
        scope=scope_t,
        files=files,
        redacted=redact_pii,
        pub_b64=pub_b64,
        fingerprint=fingerprint,
    )
    manifest_bytes = json.dumps(
        manifest, indent=2, sort_keys=True
    ).encode("utf-8")
    manifest_hash = _sha256(manifest_bytes)
    sig_b64, _, _ = _sign_bytes(manifest_bytes)
    signature_text = (
        f"-----BEGIN TARS AUDIT BUNDLE SIGNATURE-----\n"
        f"algorithm: ed25519\n"
        f"public_key_b64: {pub_b64}\n"
        f"key_fingerprint: {fingerprint}\n"
        f"manifest_sha256: {manifest_hash}\n"
        f"signature_b64: {sig_b64}\n"
        f"-----END TARS AUDIT BUNDLE SIGNATURE-----\n"
    ).encode("utf-8")

    files.append(("manifest.json", manifest_bytes))
    files.append(("signature.txt", signature_text))

    # Write the tarball deterministically (sorted, fixed mtime).
    fixed_mtime = float(int(started_at))
    files_sorted = sorted(files, key=lambda r: r[0])
    with tarfile.open(output_path, "w:gz") as tf:
        for relpath, data in files_sorted:
            ti = tarfile.TarInfo(name=relpath)
            ti.size = len(data)
            ti.mtime = fixed_mtime
            ti.mode = 0o644
            ti.uname = "tars"
            ti.gname = "tars"
            tf.addfile(ti, io.BytesIO(data))

    total_bytes = os.path.getsize(output_path)
    if total_bytes > SIZE_WARN_BYTES:
        log.warning(
            "compliance bundle %s exceeds 500MB warning threshold (%d bytes)",
            bundle_id, total_bytes,
        )

    completed_at = time.time()
    bundle = Bundle(
        id=bundle_id,
        started_at=started_at,
        completed_at=completed_at,
        since_iso=_utc_iso(since_ts),
        until_iso=_utc_iso(until_ts),
        output_path=output_path,
        status="done",
        manifest_hash=manifest_hash,
        signature=sig_b64,
        scope=list(scope_t),
        file_count=len(files_sorted),
        total_bytes=total_bytes,
        redacted=redact_pii,
    )

    rows = _read_index(out_dir)
    rows.append(bundle.to_dict())
    _write_index(out_dir, rows)

    # Best-effort receipt for the export action itself.
    try:
        from backend.core.receipts import record
        await record(
            type="compliance.bundle_generated",
            actor="system:compliance_export",
            resource=bundle_id,
            payload={
                "since": bundle.since_iso,
                "until": bundle.until_iso,
                "scope": list(scope_t),
                "file_count": bundle.file_count,
                "total_bytes": bundle.total_bytes,
                "manifest_hash": bundle.manifest_hash,
                "redacted": redact_pii,
            },
        )
    except Exception as exc:  # pragma: no cover - best effort
        log.debug("compliance bundle receipt swallow: %s", exc)

    return bundle
