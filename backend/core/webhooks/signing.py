"""HMAC-SHA256 sign + verify with replay protection.

Signature header format::

    t=<unix_ts>,v1=<hex_digest>

The signed string is ``f"{ts}.{payload_json}"`` (Stripe-compatible
shape so existing tooling that already parses ``t=,v1=`` works without
modification). Replay window defaults to 5 minutes — older
timestamps are rejected even if the digest matches.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import time

_HEADER_RE = re.compile(r"^\s*t=(?P<ts>\d+)\s*,\s*v1=(?P<sig>[0-9a-f]+)\s*$", re.IGNORECASE)


def _signed_string(timestamp: int, payload_json: bytes) -> bytes:
    return f"{timestamp}.".encode("utf-8") + payload_json


def sign_payload(secret: bytes, payload_json: bytes, timestamp: int) -> str:
    """Return ``t=<ts>,v1=<hex_sig>`` for the given payload + timestamp.

    Caller is responsible for picking ``timestamp`` (usually ``int(time.time())``).
    """

    if not isinstance(secret, (bytes, bytearray)):
        raise TypeError("secret must be bytes")
    if not isinstance(payload_json, (bytes, bytearray)):
        raise TypeError("payload_json must be bytes")
    sig = hmac.new(
        bytes(secret),
        _signed_string(int(timestamp), bytes(payload_json)),
        hashlib.sha256,
    ).hexdigest()
    return f"t={int(timestamp)},v1={sig}"


def parse_header(signature_header: str) -> tuple[int, str] | None:
    """Return ``(timestamp, hex_sig)`` or ``None`` on malformed input."""

    if not isinstance(signature_header, str):
        return None
    match = _HEADER_RE.match(signature_header)
    if match is None:
        return None
    try:
        ts = int(match.group("ts"))
    except (TypeError, ValueError):
        return None
    return ts, match.group("sig").lower()


def verify_payload(
    secret: bytes,
    payload_json: bytes,
    signature_header: str,
    *,
    max_age_s: int = 300,
    now: float | None = None,
) -> bool:
    """Verify ``signature_header`` against ``payload_json``.

    Returns ``True`` only when:

    1. Header parses as ``t=<ts>,v1=<hex>``.
    2. ``ts`` is within ``max_age_s`` of ``now`` (default = wall clock).
    3. ``hmac_sha256(secret, f"{ts}.{payload}")`` matches in constant
       time.

    Negative ``max_age_s`` disables the freshness check (use only for
    deterministic tests).
    """

    parsed = parse_header(signature_header)
    if parsed is None:
        return False
    ts, sig_hex = parsed
    if max_age_s >= 0:
        wall = float(now) if now is not None else time.time()
        if abs(wall - ts) > max_age_s:
            return False
    expected_hex = hmac.new(
        bytes(secret),
        _signed_string(ts, bytes(payload_json)),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_hex, sig_hex)
