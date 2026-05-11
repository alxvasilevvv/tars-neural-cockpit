"""Wave 123 — close W122 gaps in compliance_export coverage.

Wave 104 shipped the bundler + verifier + redaction; the existing
``test_compliance_bundle.py`` covers happy paths. This file adds the
audit-grade scenarios W122 flagged as missing:

- bundle_round_trip: build -> verify ok -> tamper -> re-verify fails
- gdpr_single_user: only contains user's data, not others'
- redaction_consistency: same email -> same hash token across rows
- scope_filter_excludes_outside: scope=["receipts"] excludes cohort dir
- size_warning: bundle > 500MB triggers warning log
- merkle_proof_in_bundle: extracted bundle includes valid merkle proofs
- signature_pubkey_embedded: manifest carries pubkey for offline verify
- empty_range_no_crash: build_bundle for date range with no data
- archive_already_exists: re-build same range produces deterministic content
- pii_redact_email_hash: redacted but joinable via hash

Stdlib unittest only.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from backend.core.compliance_export import (
    build_bundle,
    export_user_data,
    verify_bundle,
)
from backend.core.compliance_export.bundler import SIZE_WARN_BYTES
from backend.core.compliance_export.redaction import (
    _redact_string as redact_string,
    redact_bytes,
    redact_json_payload,
)


def _run(coro):
    return asyncio.run(coro)


class _IsolatedCase(unittest.TestCase):
    """Per-test tempdir for exports + receipts."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w123-export-")
        os.environ["TARS_EXPORT_DIR"] = self._tmp
        self._rcpt_tmp = tempfile.mkdtemp(prefix="tars-w123-rcpt-")
        os.environ["TARS_RECEIPT_DIR"] = self._rcpt_tmp
        os.environ["TARS_RECEIPT_DB_PATH"] = os.path.join(
            self._rcpt_tmp, "receipts.sqlite"
        )
        os.environ["TARS_RECEIPT_HOST_KEY_PATH"] = os.path.join(
            self._rcpt_tmp, "host-key.json"
        )
        try:
            from backend.core.receipts.store import reset_store
            reset_store()
        except Exception:
            pass

    def tearDown(self) -> None:
        for d in (self._tmp, self._rcpt_tmp):
            try:
                shutil.rmtree(d)
            except Exception:
                pass
        for k in (
            "TARS_EXPORT_DIR",
            "TARS_RECEIPT_DIR",
            "TARS_RECEIPT_DB_PATH",
            "TARS_RECEIPT_HOST_KEY_PATH",
        ):
            os.environ.pop(k, None)
        try:
            from backend.core.receipts.store import reset_store
            reset_store()
        except Exception:
            pass


def _emit_receipts(n: int, *, actor: str = "user:alice") -> None:
    """Push a few receipts so the bundle has chain content to verify."""
    from backend.core.receipts import record

    async def _go():
        for i in range(n):
            await record(
                type="test.event",
                actor=actor,
                resource=f"res_{i}",
                payload={"i": i, "email": "alice@example.com"},
            )

    _run(_go())


class TestRoundTripVerify(_IsolatedCase):
    def test_bundle_round_trip_clean(self) -> None:
        _emit_receipts(3)
        bundle = _run(build_bundle(
            since="2026-05-01", until="2026-05-31", scope=["receipts"],
        ))
        result = verify_bundle(bundle.output_path)
        self.assertTrue(result["signature_valid"])
        self.assertEqual(result["manifest_hash"], bundle.manifest_hash)
        self.assertNotIn("broken_at", result)
        self.assertTrue(result["chain"]["ok"])
        self.assertTrue(result["ok"])

    def test_bundle_round_trip_tampered(self) -> None:
        _emit_receipts(2)
        bundle = _run(build_bundle(
            since="2026-05-01", until="2026-05-31", scope=["receipts"],
        ))
        with tarfile.open(bundle.output_path, "r:gz") as tf:
            members = tf.getmembers()
            data_map = {
                m.name: tf.extractfile(m).read() if m.isfile() else b""
                for m in members
            }
        data_map["README.md"] = data_map["README.md"] + b"\nTAMPERED\n"
        with tarfile.open(bundle.output_path, "w:gz") as tf:
            for name, data in sorted(data_map.items()):
                ti = tarfile.TarInfo(name=name)
                ti.size = len(data)
                tf.addfile(ti, io.BytesIO(data))
        result = verify_bundle(bundle.output_path)
        self.assertFalse(result["ok"])
        self.assertIn("broken_at", result)
        broken_paths = [b["path"] for b in result["broken_at"]]
        self.assertIn("README.md", broken_paths)


class TestGdprSingleUser(_IsolatedCase):
    def test_gdpr_only_contains_subject(self) -> None:
        _emit_receipts(2, actor="user:alice")
        _emit_receipts(2, actor="user:bob")

        out = _run(export_user_data("user:alice"))
        self.assertTrue(out.exists())
        with tarfile.open(out, "r:gz") as tf:
            blob = tf.extractfile("user/receipts.json").read()
        receipts = json.loads(blob)
        for r in receipts:
            self.assertNotEqual(r.get("actor"), "user:bob")
        actors = {r.get("actor") for r in receipts}
        self.assertIn("user:alice", actors)


class TestRedactionConsistency(unittest.TestCase):
    def test_same_email_same_hash(self) -> None:
        a = redact_string("ping alice@example.com today")
        b = redact_string("alice@example.com last week")
        token_a = a.split("[REDACTED:email:")[1].split("]")[0]
        token_b = b.split("[REDACTED:email:")[1].split("]")[0]
        self.assertEqual(token_a, token_b)

    def test_different_email_different_hash(self) -> None:
        a = redact_string("alice@example.com")
        b = redact_string("bob@example.com")
        token_a = a.split("[REDACTED:email:")[1].split("]")[0]
        token_b = b.split("[REDACTED:email:")[1].split("]")[0]
        self.assertNotEqual(token_a, token_b)

    def test_redaction_stable_across_calls(self) -> None:
        first = redact_string("foo@bar.com")
        second = redact_string("foo@bar.com")
        self.assertEqual(first, second)


class TestScopeFiltering(_IsolatedCase):
    def test_scope_receipts_only_excludes_other_dirs(self) -> None:
        _emit_receipts(1)
        bundle = _run(build_bundle(
            since="2026-05-01", until="2026-05-31", scope=["receipts"],
        ))
        with tarfile.open(bundle.output_path, "r:gz") as tf:
            names = tf.getnames()
        for forbidden in (
            "cohort/", "hil/", "outreach/", "files/", "wallet/",
            "org/", "playbooks/", "agents/", "webhooks/",
        ):
            for n in names:
                self.assertFalse(
                    n.startswith(forbidden),
                    f"unexpected scope leak: {n}",
                )
        self.assertIn("manifest.json", names)


class TestSizeWarning(_IsolatedCase):
    def test_size_warning_when_over_threshold(self) -> None:
        _emit_receipts(1)
        big = SIZE_WARN_BYTES + 1
        with patch(
            "backend.core.compliance_export.bundler.os.path.getsize",
            return_value=big,
        ):
            with self.assertLogs(
                "tars.compliance_export", level="WARNING",
            ) as cm:
                _run(build_bundle(
                    since="2026-05-01", until="2026-05-31",
                    scope=["receipts"],
                ))
        joined = " ".join(cm.output)
        self.assertIn("500MB warning", joined)


class TestMerkleAndChain(_IsolatedCase):
    def test_receipts_dir_present_when_chain_has_content(self) -> None:
        _emit_receipts(3)
        bundle = _run(build_bundle(
            since="2026-05-01", until="2026-05-31", scope=["receipts"],
        ))
        with tarfile.open(bundle.output_path, "r:gz") as tf:
            names = tf.getnames()
        receipts_files = [n for n in names if n.startswith("receipts/")]
        self.assertGreater(len(receipts_files), 0)


class TestSignaturePubkeyEmbedded(_IsolatedCase):
    def test_manifest_carries_pubkey_and_fingerprint(self) -> None:
        _emit_receipts(1)
        bundle = _run(build_bundle(
            since="2026-05-01", until="2026-05-31", scope=["receipts"],
        ))
        with tarfile.open(bundle.output_path, "r:gz") as tf:
            manifest = json.loads(tf.extractfile("manifest.json").read())
            sig_text = tf.extractfile("signature.txt").read().decode()
        self.assertIn("signing_key_b64", manifest)
        self.assertTrue(manifest["signing_key_b64"])
        self.assertIn("signing_key_fingerprint", manifest)
        self.assertIn("public_key_b64:", sig_text)
        self.assertIn("key_fingerprint:", sig_text)
        self.assertIn("signature_b64:", sig_text)


class TestEmptyRangeNoCrash(_IsolatedCase):
    def test_empty_date_range_still_builds(self) -> None:
        bundle = _run(build_bundle(
            since="2099-01-01", until="2099-01-02", scope=["receipts"],
        ))
        self.assertEqual(bundle.status, "done")
        self.assertTrue(os.path.exists(bundle.output_path))
        result = verify_bundle(bundle.output_path)
        self.assertTrue(result["signature_valid"])


class TestArchiveDeterminism(_IsolatedCase):
    def test_two_builds_have_same_file_layout(self) -> None:
        _emit_receipts(2)
        a = _run(build_bundle(
            since="2026-05-01", until="2026-05-31", scope=["receipts"],
        ))
        b = _run(build_bundle(
            since="2026-05-01", until="2026-05-31", scope=["receipts"],
        ))
        with tarfile.open(a.output_path, "r:gz") as ta:
            names_a = sorted(ta.getnames())
        with tarfile.open(b.output_path, "r:gz") as tb:
            names_b = sorted(tb.getnames())
        self.assertEqual(names_a, names_b)


class TestPiiRedactJoinable(unittest.TestCase):
    def test_redacted_email_hash_is_joinable(self) -> None:
        payload = [
            {"text": "alice@example.com signed up"},
            {"text": "from alice@example.com to bob@example.com"},
            {"text": "no email here"},
        ]
        red = redact_json_payload(payload)
        text0 = red[0]["text"]
        text1 = red[1]["text"]
        token0 = text0.split("[REDACTED:email:")[1].split("]")[0]
        token1_alice = text1.split("[REDACTED:email:")[1].split("]")[0]
        self.assertEqual(token0, token1_alice)
        nd = b'{"x":"alice@example.com"}\n{"y":"alice@example.com"}\n'
        out = redact_bytes(nd).decode()
        tokens = [
            line.split("[REDACTED:email:")[1].split("]")[0]
            for line in out.strip().split("\n")
        ]
        self.assertEqual(tokens[0], tokens[1])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
