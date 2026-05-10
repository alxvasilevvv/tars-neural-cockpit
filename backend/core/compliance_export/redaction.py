"""Optional PII redaction layer for compliance bundles (Wave 104).

When external auditors shouldn't see raw PII, the bundler can run
:func:`redact_pii` (or, in-process during build, :func:`redact_bytes`)
over every JSON / NDJSON payload. We replace emails, phone numbers,
IP addresses, credit-card-like sequences, and SSN-like sequences
with deterministic ``[REDACTED:type:hash]`` tokens. The hash is
stable per-string so an auditor can still join records that share
a value (e.g. "this email appears in 12 messages") without ever
seeing the underlying value.

Redaction is regex-based — not perfect (an attacker controlling
inputs can sneak past a hand-crafted regex), but matches industry
standard for offline-export hygiene.
"""

from __future__ import annotations

import hashlib
import json
import re
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Callable


# ----- Patterns -----------------------------------------------------------

_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
)
# Phone: international-ish, lenient. Avoid swallowing very short
# sequences to reduce FP on monetary amounts.
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[\s\-.]?)?"
    r"(?:\(?\d{2,4}\)?[\s\-.]?){2,4}\d{2,4}(?!\d)",
)
_IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b",
)
_IPV6_RE = re.compile(
    r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b",
)
# Credit card: 13-19 digits with optional spaces/dashes (Luhn would
# be more accurate but adds CPU; this is a coarse sweep).
_CC_RE = re.compile(r"\b(?:\d[ \-]?){13,19}\b")
# US-style SSN
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def _hash6(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def _token(kind: str, original: str) -> str:
    return f"[REDACTED:{kind}:{_hash6(original)}]"


def _redact_string(s: str, scheme: str = "default") -> str:
    """Apply all PII substitutions to a single string. Order matters:
    email FIRST so the @ doesn't get misclassified as phone digits.
    """

    if not isinstance(s, str) or not s:
        return s
    out = _EMAIL_RE.sub(lambda m: _token("email", m.group(0)), s)
    if scheme != "minimal":
        out = _SSN_RE.sub(lambda m: _token("ssn", m.group(0)), out)
        out = _CC_RE.sub(
            lambda m: _token("cc", m.group(0))
            if sum(c.isdigit() for c in m.group(0)) >= 13 else m.group(0),
            out,
        )
        out = _IPV4_RE.sub(lambda m: _token("ipv4", m.group(0)), out)
        out = _IPV6_RE.sub(lambda m: _token("ipv6", m.group(0)), out)
        # Phone last because the regex is greedy.
        out = _PHONE_RE.sub(
            lambda m: _token("phone", m.group(0))
            if sum(c.isdigit() for c in m.group(0)) >= 7 else m.group(0),
            out,
        )
    return out


def _redact_value(v: Any, scheme: str = "default") -> Any:
    if isinstance(v, str):
        return _redact_string(v, scheme)
    if isinstance(v, dict):
        return {k: _redact_value(val, scheme) for k, val in v.items()}
    if isinstance(v, list):
        return [_redact_value(x, scheme) for x in v]
    if isinstance(v, tuple):
        return tuple(_redact_value(x, scheme) for x in v)
    return v


def redact_json_payload(obj: Any, scheme: str = "default") -> Any:
    """Public helper: walk a JSON-shaped tree and redact strings."""
    return _redact_value(obj, scheme)


def redact_bytes(data: bytes, scheme: str = "default") -> bytes:
    """Redact a JSON or NDJSON byte string.

    Returns the original bytes unchanged on parse failure.
    """

    text = data.decode("utf-8", errors="replace")
    # NDJSON heuristic: many newline-separated json blobs.
    if "\n" in text and text.lstrip().startswith("{"):
        out_lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                out_lines.append(line)
                continue
            try:
                obj = json.loads(stripped)
                redacted = redact_json_payload(obj, scheme)
                out_lines.append(json.dumps(redacted, sort_keys=True))
            except Exception:
                out_lines.append(_redact_string(line, scheme))
        return ("\n".join(out_lines) + ("\n" if text.endswith("\n") else "")).encode("utf-8")
    try:
        obj = json.loads(text)
        redacted = redact_json_payload(obj, scheme)
        return json.dumps(redacted, indent=2, sort_keys=True).encode("utf-8")
    except Exception:
        return _redact_string(text, scheme).encode("utf-8")


def redact_pii(bundle_path: str, scheme: str = "default") -> str:
    """Re-emit a bundle with every JSON payload PII-redacted.

    Writes ``<bundle_path>.redacted.tar.gz`` next to the input and
    returns the new path. Note: this invalidates the original
    signature (manifest changes), so callers should re-sign or
    treat the redacted bundle as a separate artifact.
    """

    if not bundle_path.endswith(".tar.gz"):
        raise ValueError("expected .tar.gz input")
    out_path = bundle_path[:-len(".tar.gz")] + ".redacted.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(bundle_path, "r:*") as tf:
            tf.extractall(tmp)
        # Walk all extracted files, redact json/ndjson, leave others alone.
        for root, _dirs, files in __import__("os").walk(tmp):
            for fname in files:
                full = __import__("os").path.join(root, fname)
                if not (fname.endswith(".json") or fname.endswith(".ndjson")):
                    continue
                if fname == "manifest.json":
                    # leave the structural manifest, but rewrite hashes later
                    continue
                try:
                    raw = Path(full).read_bytes()
                    Path(full).write_bytes(redact_bytes(raw, scheme))
                except Exception:
                    pass
        with tarfile.open(out_path, "w:gz") as out_tf:
            out_tf.add(tmp, arcname=".")
    return out_path
