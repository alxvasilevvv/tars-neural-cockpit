"""Tests for the audit-grade compliance export bundle (Wave 104).

Stdlib unittest only. Each test isolates its own ``~/.tars/exports``
via ``TARS_EXPORT_DIR`` env var pointing at a fresh tempdir.
"""

from __future__ import annotations

import asyncio
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path

from backend.core.compliance_export import (
    DEFAULT_SCOPE,
    SCOPE_CATEGORIES,
    build_bundle,
    export_user_data,
    list_bundles,
    redact_pii,
    verify_bundle,
)
from backend.core.compliance_export.bundler import (
    _expand_scope,
    _parse_iso,
    _sha256,
    delete_bundle,
)
from backend.core.compliance_export.redaction import (
    _redact_string as redact_string,
    redact_bytes,
    redact_json_payload,
)


def _run(coro):
    return asyncio.run(coro)


class _IsolatedExportCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-export-test-")
        os.environ["TARS_EXPORT_DIR"] = self._tmp
        # Use a separate receipts dir + host key per test so the
        # signature path is always exercised cleanly.
        self._rcpt_tmp = tempfile.mkdtemp(prefix="tars-rcpt-test-")
        os.environ["TARS_RECEIPT_DIR"] = self._rcpt_tmp
        os.environ["TARS_RECEIPT_DB_PATH"] = os.path.join(
            self._rcpt_tmp, "receipts.sqlite",
        )
        os.environ["TARS_RECEIPT_HOST_KEY_PATH"] = os.path.join(
            self._rcpt_tmp, "host-key.json",
        )
        # Ensure modules see the new env.
        try:
            from backend.core.receipts.store import reset_store
            reset_store()
        except Exception:
            pass

    def tearDown(self) -> None:
        import shutil
        for d in (self._tmp, self._rcpt_tmp):
            try:
                shutil.rmtree(d)
            except Exception:
                pass
        for k in (
            "TARS_EXPORT_DIR", "TARS_RECEIPT_DIR", "TARS_RECEIPT_DB_PATH",
            "TARS_RECEIPT_HOST_KEY_PATH",
        ):
            os.environ.pop(k, None)
        try:
            from backend.core.receipts.store import reset_store
            reset_store()
        except Exception:
            pass


class TestScopeAndIso(unittest.TestCase):
    def test_expand_scope_all(self) -> None:
        self.assertEqual(_expand_scope(["all"]), tuple(DEFAULT_SCOPE))

    def test_expand_scope_drops_unknown(self) -> None:
        out = _expand_scope(["receipts", "bogus"])
        self.assertEqual(out, ("receipts",))

    def test_expand_scope_blobs_with_all(self) -> None:
        out = _expand_scope(["all", "blobs"])
        self.assertIn("blobs", out)
        self.assertIn("receipts", out)

    def test_parse_iso_date_only(self) -> None:
        self.assertGreater(_parse_iso("2026-05-10"), 0)

    def test_parse_iso_z_suffix(self) -> None:
        self.assertGreater(_parse_iso("2026-05-10T00:00:00Z"), 0)

    def test_scope_categories_complete(self) -> None:
        for cat in (
            "receipts", "cohort", "connectors", "hil", "outreach",
            "files", "wallet", "org", "playbooks", "agents", "webhooks",
            "blobs",
        ):
            self.assertIn(cat, SCOPE_CATEGORIES)


class TestBundleCreation(_IsolatedExportCase):
    def test_build_bundle_creates_tarball(self) -> None:
        bundle = _run(build_bundle(
            since="2026-05-01", until="2026-05-10", scope=["all"],
        ))
        self.assertEqual(bundle.status, "done")
        self.assertTrue(os.path.exists(bundle.output_path))
        self.assertTrue(bundle.output_path.endswith(".tar.gz"))
        self.assertGreater(bundle.file_count, 0)
        self.assertEqual(len(bundle.manifest_hash), 64)

    def test_bundle_contains_manifest_and_signature(self) -> None:
        bundle = _run(build_bundle(
            since="2026-05-01", until="2026-05-10", scope=["receipts"],
        ))
        with tarfile.open(bundle.output_path, "r:gz") as tf:
            names = tf.getnames()
        self.assertIn("manifest.json", names)
        self.assertIn("signature.txt", names)
        self.assertIn("README.md", names)

    def test_manifest_hash_recomputable(self) -> None:
        """Recomputed sha256 over manifest.json bytes equals the
        ``manifest_hash`` field on the Bundle."""
        bundle = _run(build_bundle(
            since="2026-05-01", until="2026-05-10", scope=["receipts"],
        ))
        with tarfile.open(bundle.output_path, "r:gz") as tf:
            data = tf.extractfile("manifest.json").read()
        self.assertEqual(_sha256(data), bundle.manifest_hash)

    def test_scope_filtering(self) -> None:
        """When scope=['receipts'] only receipts/ section is populated."""
        bundle = _run(build_bundle(
            since="2026-05-01", until="2026-05-10", scope=["receipts"],
        ))
        with tarfile.open(bundle.output_path, "r:gz") as tf:
            names = tf.getnames()
        # No outreach, no cohort, no webhooks etc.
        self.assertFalse(any(n.startswith("outreach/") for n in names))
        self.assertFalse(any(n.startswith("cohort/") for n in names))
        self.assertTrue(any(n.startswith("receipts/") for n in names))

    def test_index_persists_bundle(self) -> None:
        bundle = _run(build_bundle(
            since="2026-05-01", until="2026-05-10", scope=["receipts"],
        ))
        rows = list_bundles()
        self.assertTrue(any(r.get("id") == bundle.id for r in rows))

    def test_delete_bundle_removes_file(self) -> None:
        bundle = _run(build_bundle(
            since="2026-05-01", until="2026-05-10", scope=["receipts"],
        ))
        self.assertTrue(delete_bundle(bundle.id))
        self.assertFalse(os.path.exists(bundle.output_path))


class TestVerifier(_IsolatedExportCase):
    def test_verify_bundle_signature_valid(self) -> None:
        bundle = _run(build_bundle(
            since="2026-05-01", until="2026-05-10", scope=["receipts"],
        ))
        result = verify_bundle(bundle.output_path)
        # signature_valid depends on cryptography being importable;
        # the test environment ships it (Wave 95 dep).
        self.assertEqual(result["manifest_hash"], bundle.manifest_hash)
        self.assertGreater(result["file_count"], 0)
        # No file hash mismatches expected on a fresh build.
        self.assertNotIn("broken_at", result)
        self.assertTrue(result["signature_valid"])

    def test_verify_detects_tamper(self) -> None:
        bundle = _run(build_bundle(
            since="2026-05-01", until="2026-05-10", scope=["receipts"],
        ))
        # Repack the tarball with a mutated README; signature over the
        # manifest still ought to validate (we didn't touch manifest)
        # but the file's recorded sha256 will mismatch.
        import io
        with tarfile.open(bundle.output_path, "r:gz") as tf:
            members = tf.getmembers()
            data_map = {m.name: tf.extractfile(m).read() if m.isfile() else b"" for m in members}
        data_map["README.md"] = data_map["README.md"] + b"\n[TAMPERED]\n"
        with tarfile.open(bundle.output_path, "w:gz") as tf:
            for name, data in sorted(data_map.items()):
                ti = tarfile.TarInfo(name=name)
                ti.size = len(data)
                tf.addfile(ti, io.BytesIO(data))
        result = verify_bundle(bundle.output_path)
        self.assertFalse(result["ok"])
        self.assertIn("broken_at", result)

    def test_verify_chain_integrity(self) -> None:
        bundle = _run(build_bundle(
            since="2026-05-01", until="2026-05-10", scope=["receipts"],
        ))
        result = verify_bundle(bundle.output_path)
        self.assertTrue(result["chain"]["ok"])


class TestRedaction(unittest.TestCase):
    def test_redact_email_consistent(self) -> None:
        a = redact_string("ping me at alice@example.com please")
        b = redact_string("alice@example.com is the contact")
        # Both contain the same hash token for the same email.
        self.assertIn("[REDACTED:email:", a)
        self.assertIn("[REDACTED:email:", b)
        token_a = a.split("[REDACTED:email:")[1].split("]")[0]
        token_b = b.split("[REDACTED:email:")[1].split("]")[0]
        self.assertEqual(token_a, token_b)

    def test_redact_phone(self) -> None:
        s = "call +1 415 555 0199 ext 200"
        out = redact_string(s)
        self.assertIn("[REDACTED:phone:", out)

    def test_redact_ipv4(self) -> None:
        s = "request from 192.168.1.42 dropped"
        out = redact_string(s)
        self.assertIn("[REDACTED:ipv4:", out)

    def test_redact_json_payload_walks_nested(self) -> None:
        obj = {"user": {"email": "bob@x.com"}, "ips": ["10.0.0.1"]}
        red = redact_json_payload(obj)
        self.assertIn("REDACTED", red["user"]["email"])
        self.assertIn("REDACTED", red["ips"][0])

    def test_redact_bytes_ndjson(self) -> None:
        nd = b'{"x":"a@b.com"}\n{"y":"c@d.com"}\n'
        out = redact_bytes(nd)
        self.assertIn(b"REDACTED:email:", out)
        # Both lines should still be valid JSON after redaction.
        for line in out.decode().strip().split("\n"):
            json.loads(line)


class TestRedactedBundle(_IsolatedExportCase):
    def test_redacted_flag_propagates(self) -> None:
        bundle = _run(build_bundle(
            since="2026-05-01", until="2026-05-10",
            scope=["receipts"], redact_pii=True,
        ))
        self.assertTrue(bundle.redacted)
        with tarfile.open(bundle.output_path, "r:gz") as tf:
            manifest = json.loads(tf.extractfile("manifest.json").read())
        self.assertTrue(manifest["redacted"])


class TestGdprExport(_IsolatedExportCase):
    def test_gdpr_export_creates_tarball(self) -> None:
        path = _run(export_user_data("alien@icloud.com"))
        self.assertTrue(os.path.exists(str(path)))
        self.assertTrue(str(path).endswith(".tar.gz"))
        with tarfile.open(str(path), "r:gz") as tf:
            names = tf.getnames()
        self.assertIn("manifest.json", names)
        self.assertIn("signature.txt", names)
        self.assertIn("user/messages.json", names)
        self.assertIn("user/receipts.json", names)
        self.assertIn("README.md", names)

    def test_gdpr_subject_only(self) -> None:
        """The GDPR export readme should mention the subject fingerprint
        (deterministic hash of the email)."""
        path = _run(export_user_data("subject@example.com"))
        with tarfile.open(str(path), "r:gz") as tf:
            readme = tf.extractfile("README.md").read().decode()
            manifest = json.loads(tf.extractfile("manifest.json").read())
        self.assertIn(manifest["subject_fingerprint"], readme)
        self.assertEqual(manifest["kind"], "gdpr_article_15")


if __name__ == "__main__":
    unittest.main()
