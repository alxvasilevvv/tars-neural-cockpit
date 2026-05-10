"""Independent bundle verifier (Wave 104).

Auditors run :func:`verify_bundle` to PROVE the tarball wasn't
tampered with after generation. The function:

1. Extracts the archive into a temp directory.
2. Loads ``manifest.json`` and recomputes sha256 for every listed file.
3. Reads ``signature.txt`` and verifies the ed25519 signature against
   the manifest bytes using the public key embedded in the manifest.
4. Replays each ``receipts/*.ndjson`` to confirm the hash chain
   linkage is intact (re-derives every hash + checks prev_hash).

Returns a structured dict — never raises on bad input.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import tarfile
import tempfile
from pathlib import Path
from typing import Any


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract_signature(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line and not line.startswith("-----"):
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out


def _verify_signature(manifest_bytes: bytes, sig_b64: str, pub_b64: str) -> bool:
    if not sig_b64 or not pub_b64:
        return False
    if sig_b64.startswith("unsigned:"):
        return False
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey,
        )
        pub = base64.b64decode(pub_b64)
        sig = base64.b64decode(sig_b64)
        vk = Ed25519PublicKey.from_public_bytes(pub)
        vk.verify(sig, manifest_bytes)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
    except Exception:
        return False


def _replay_chain_lines(lines: list[str]) -> dict[str, Any]:
    """Independent reimplementation: re-derive each receipt hash and
    confirm prev_hash linkage. Doesn't touch the receipts module so
    the verifier stays standalone.
    """

    prev_hash = ""
    for i, raw in enumerate(lines):
        raw = raw.strip()
        if not raw:
            continue
        try:
            r = json.loads(raw)
        except json.JSONDecodeError:
            return {"ok": False, "broken_at_index": i, "reason": "bad_json"}
        body = [
            r.get("prev_hash", ""),
            round(float(r.get("ts", 0.0)), 6),
            r.get("type", ""),
            r.get("actor", ""),
            r.get("resource"),
            r.get("payload") or {},
        ]
        canon = json.dumps(
            body, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
        recomputed = hashlib.sha256(canon).hexdigest()
        if recomputed != r.get("hash"):
            return {
                "ok": False,
                "broken_at_index": i,
                "expected": recomputed,
                "actual": r.get("hash"),
                "reason": "hash_mismatch",
            }
        if r.get("prev_hash", "") != prev_hash:
            return {
                "ok": False,
                "broken_at_index": i,
                "expected": prev_hash,
                "actual": r.get("prev_hash"),
                "reason": "prev_hash_mismatch",
            }
        prev_hash = r.get("hash", "")
    return {"ok": True, "count": len(lines)}


def _safe_member(name: str) -> bool:
    """Reject path-traversal in tarball entries."""
    n = name.replace("\\", "/")
    if n.startswith("/") or ".." in n.split("/"):
        return False
    return True


def verify_bundle(tarball_path: str) -> dict[str, Any]:
    """Verify a TARS audit bundle independently.

    Returns ``{"ok": bool, "broken_at"?, "signature_valid": bool,
    "file_count": int, "manifest_hash": str, "chain": {...}, "errors": [...]}``.
    """

    result: dict[str, Any] = {
        "ok": False,
        "signature_valid": False,
        "file_count": 0,
        "manifest_hash": "",
        "chain": {"ok": True, "days": {}},
        "errors": [],
    }
    if not os.path.exists(tarball_path):
        result["errors"].append("file_not_found")
        return result

    with tempfile.TemporaryDirectory() as tmp:
        try:
            with tarfile.open(tarball_path, "r:*") as tf:
                for m in tf.getmembers():
                    if not _safe_member(m.name):
                        result["errors"].append(f"unsafe_member:{m.name}")
                        return result
                tf.extractall(tmp)
        except (tarfile.TarError, OSError) as exc:
            result["errors"].append(f"extract_failed:{exc}")
            return result

        manifest_path = os.path.join(tmp, "manifest.json")
        if not os.path.exists(manifest_path):
            result["errors"].append("manifest_missing")
            return result
        manifest_bytes = Path(manifest_path).read_bytes()
        result["manifest_hash"] = _sha256(manifest_bytes)
        try:
            manifest = json.loads(manifest_bytes)
        except json.JSONDecodeError as exc:
            result["errors"].append(f"manifest_bad_json:{exc}")
            return result

        # Recompute every file's sha256 and compare.
        file_index = manifest.get("files", []) or []
        broken: list[dict[str, Any]] = []
        for entry in file_index:
            relpath = entry.get("path") or ""
            expected = entry.get("sha256") or ""
            full = os.path.join(tmp, relpath)
            if not os.path.exists(full):
                broken.append({"path": relpath, "reason": "missing"})
                continue
            actual = _sha256(Path(full).read_bytes())
            if actual != expected:
                broken.append({
                    "path": relpath,
                    "expected": expected,
                    "actual": actual,
                    "reason": "sha256_mismatch",
                })
        result["file_count"] = len(file_index)
        if broken:
            result["broken_at"] = broken
            result["errors"].append("file_hash_mismatch")

        # Verify the signature over manifest.json bytes.
        sig_path = os.path.join(tmp, "signature.txt")
        if os.path.exists(sig_path):
            sig_text = Path(sig_path).read_text("utf-8")
            sig_kv = _extract_signature(sig_text)
            sig_b64 = sig_kv.get("signature_b64", "")
            pub_b64 = sig_kv.get("public_key_b64", "") or manifest.get(
                "signing_key_b64", ""
            )
            result["signature_valid"] = _verify_signature(
                manifest_bytes, sig_b64, pub_b64,
            )
            result["signing_key_fingerprint"] = sig_kv.get(
                "key_fingerprint",
            ) or manifest.get("signing_key_fingerprint", "")
            # Cross-check: the manifest_sha256 baked into the sig file
            # should match what we just computed.
            stored = sig_kv.get("manifest_sha256", "")
            if stored and stored != result["manifest_hash"]:
                result["errors"].append("signature_manifest_hash_mismatch")
        else:
            result["errors"].append("signature_missing")

        # Replay every receipts/*.ndjson chain.
        receipts_dir = os.path.join(tmp, "receipts")
        if os.path.isdir(receipts_dir):
            day_re = re.compile(r"^\d{4}-\d{2}-\d{2}\.ndjson$")
            chain_all_ok = True
            for fname in sorted(os.listdir(receipts_dir)):
                if not day_re.match(fname):
                    continue
                full = os.path.join(receipts_dir, fname)
                lines = Path(full).read_text("utf-8").splitlines()
                walk = _replay_chain_lines(lines)
                result["chain"]["days"][fname] = walk
                if not walk.get("ok"):
                    chain_all_ok = False
            result["chain"]["ok"] = chain_all_ok
            if not chain_all_ok:
                result["errors"].append("chain_broken")

    result["ok"] = (
        not result["errors"]
        and result["signature_valid"]
        and result["chain"].get("ok", True)
    )
    return result
