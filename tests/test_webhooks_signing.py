"""HMAC-SHA256 sign + verify + replay-window tests for the webhooks module.

Stdlib unittest only — runs in any environment with vanilla Python.
"""

from __future__ import annotations

import time
import unittest

from backend.core.webhooks import sign_payload, verify_payload
from backend.core.webhooks.signing import parse_header


SECRET = b"super-secret-key-do-not-leak"
PAYLOAD = b'{"id":"evt_1","type":"playbook.started","data":{"playbook_id":"pb1"}}'


class TestSignPayload(unittest.TestCase):
    def test_sign_returns_well_formed_header(self):
        ts = 1_700_000_000
        header = sign_payload(SECRET, PAYLOAD, ts)
        self.assertTrue(header.startswith("t=1700000000,v1="))
        # 64-hex sha256 digest after the comma
        _, _, sig = header.partition("v1=")
        self.assertEqual(len(sig), 64)
        # all hex
        int(sig, 16)

    def test_sign_is_deterministic_for_same_inputs(self):
        ts = 42
        a = sign_payload(SECRET, PAYLOAD, ts)
        b = sign_payload(SECRET, PAYLOAD, ts)
        self.assertEqual(a, b)

    def test_sign_changes_when_timestamp_changes(self):
        a = sign_payload(SECRET, PAYLOAD, 100)
        b = sign_payload(SECRET, PAYLOAD, 101)
        self.assertNotEqual(a, b)

    def test_sign_changes_when_payload_changes(self):
        a = sign_payload(SECRET, PAYLOAD, 100)
        b = sign_payload(SECRET, PAYLOAD + b"x", 100)
        self.assertNotEqual(a, b)

    def test_sign_rejects_non_bytes(self):
        with self.assertRaises(TypeError):
            sign_payload("not-bytes", PAYLOAD, 1)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            sign_payload(SECRET, "not-bytes", 1)  # type: ignore[arg-type]


class TestVerifyPayload(unittest.TestCase):
    def test_verify_round_trip(self):
        ts = int(time.time())
        header = sign_payload(SECRET, PAYLOAD, ts)
        self.assertTrue(verify_payload(SECRET, PAYLOAD, header))

    def test_verify_rejects_tampered_payload(self):
        ts = int(time.time())
        header = sign_payload(SECRET, PAYLOAD, ts)
        self.assertFalse(verify_payload(SECRET, PAYLOAD + b" tamper", header))

    def test_verify_rejects_wrong_secret(self):
        ts = int(time.time())
        header = sign_payload(SECRET, PAYLOAD, ts)
        self.assertFalse(verify_payload(b"wrong-secret", PAYLOAD, header))

    def test_verify_rejects_old_timestamp(self):
        old_ts = int(time.time()) - 999
        header = sign_payload(SECRET, PAYLOAD, old_ts)
        self.assertFalse(
            verify_payload(SECRET, PAYLOAD, header, max_age_s=300)
        )

    def test_verify_rejects_future_timestamp_outside_window(self):
        future_ts = int(time.time()) + 999
        header = sign_payload(SECRET, PAYLOAD, future_ts)
        self.assertFalse(
            verify_payload(SECRET, PAYLOAD, header, max_age_s=300)
        )

    def test_verify_accepts_within_window(self):
        ts = int(time.time()) - 60
        header = sign_payload(SECRET, PAYLOAD, ts)
        self.assertTrue(
            verify_payload(SECRET, PAYLOAD, header, max_age_s=300)
        )

    def test_verify_with_disabled_freshness_check(self):
        # Negative max_age_s → freshness check is skipped.
        header = sign_payload(SECRET, PAYLOAD, 1)
        self.assertTrue(
            verify_payload(SECRET, PAYLOAD, header, max_age_s=-1)
        )

    def test_verify_with_explicit_now(self):
        ts = 1_000_000
        header = sign_payload(SECRET, PAYLOAD, ts)
        self.assertTrue(
            verify_payload(
                SECRET,
                PAYLOAD,
                header,
                max_age_s=300,
                now=ts + 100,
            )
        )
        # 301s in the future → just outside the window
        self.assertFalse(
            verify_payload(
                SECRET,
                PAYLOAD,
                header,
                max_age_s=300,
                now=ts + 301,
            )
        )

    def test_verify_rejects_malformed_header(self):
        for bogus in ("", "not-a-header", "t=abc,v1=def", "v1=abcd", "t=1"):
            self.assertFalse(verify_payload(SECRET, PAYLOAD, bogus))


class TestParseHeader(unittest.TestCase):
    def test_parses_canonical_form(self):
        out = parse_header("t=12345,v1=abcdef0123456789")
        self.assertIsNotNone(out)
        ts, sig = out  # type: ignore[misc]
        self.assertEqual(ts, 12345)
        self.assertEqual(sig, "abcdef0123456789")

    def test_parses_with_whitespace(self):
        out = parse_header("  t=42 , v1=DEADBEEF  ")
        self.assertIsNotNone(out)
        ts, sig = out  # type: ignore[misc]
        self.assertEqual(ts, 42)
        # case folded to lower
        self.assertEqual(sig, "deadbeef")

    def test_returns_none_for_garbage(self):
        for bogus in (None, 123, "", "tts=1,v1=ab", "t=1.5,v1=ab"):
            self.assertIsNone(parse_header(bogus))  # type: ignore[arg-type]


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
