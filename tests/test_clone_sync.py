"""Wave 151 — coverage for backend.core.clone.sync (AI Clone v0.2).

The v0.2 surface adds three things on top of v0.1:
  1. Portable :class:`StyleEnvelope` (export → JSON → import).
  2. Webhook emit on every Nth recorded message (debounced).
  3. The wiring inside ``record_message`` that fires the emit.

Honest framing reminder (mirrors the module docstring):
  - This is **not** a fine-tuned model. The export carries the same
    heuristic profile + recent traits that v0.1 ships locally.
  - There is **no** automatic restore on a fresh machine. The
    operator hits the import endpoint manually (or via tars-ops).

Test cases (~12):
  - envelope shape (schema_version, contract_version, profile, traits)
  - export builds a populated envelope from a seeded store
  - export against a disabled store returns an empty envelope
  - import inserts new traits into an empty store
  - import dedups by text (re-import is a no-op)
  - import refuses unsupported schema_version
  - import into a disabled store returns ok=False
  - maybe_emit_sync_webhook respects threshold (no emit until Nth call)
  - maybe_emit_sync_webhook resets counter after firing
  - _reset_for_tests clears the in-module counter
  - interval env var (TARS_CLONE_SYNC_INTERVAL) overrides default
  - import preserves the original created_at timestamp
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import unittest


def _run(coro):
    return asyncio.run(coro)


class _IsolatedSync(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w151-sync-")
        os.environ["TARS_CLONE_DB_PATH"] = os.path.join(
            self._tmp, "clone.sqlite"
        )
        os.environ.pop("CLONE_STORE", None)
        os.environ.pop("TARS_CLONE_SYNC_INTERVAL", None)
        for k in (
            "TARS_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY",
            "TARS_OPENAI_API_KEY", "OPENAI_API_KEY",
        ):
            os.environ.pop(k, None)
        from backend.core.clone import reset_clone_store
        from backend.core.clone import sync as sync_mod
        reset_clone_store()
        sync_mod._reset_for_tests()

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass
        os.environ.pop("TARS_CLONE_DB_PATH", None)
        os.environ.pop("CLONE_STORE", None)
        os.environ.pop("TARS_CLONE_SYNC_INTERVAL", None)
        from backend.core.clone import reset_clone_store
        from backend.core.clone import sync as sync_mod
        reset_clone_store()
        sync_mod._reset_for_tests()


# ─── envelope shape ──────────────────────────────────────────────────


class TestEnvelopeShape(_IsolatedSync):
    def test_envelope_default_shape(self) -> None:
        from backend.core.clone.sync import (
            CONTRACT_VERSION,
            ENVELOPE_SCHEMA_VERSION,
            StyleEnvelope,
        )

        env = StyleEnvelope()
        self.assertEqual(env.schema_version, ENVELOPE_SCHEMA_VERSION)
        self.assertEqual(env.contract_version, CONTRACT_VERSION)
        self.assertIsInstance(env.profile, dict)
        self.assertIsInstance(env.traits, list)
        self.assertEqual(env.sample_count, 0)

    def test_envelope_roundtrip(self) -> None:
        from backend.core.clone.sync import StyleEnvelope

        env = StyleEnvelope(
            profile={"version": "0.1"},
            traits=[{"text": "hello", "created_at": 123.0}],
            sample_count=1,
        )
        raw = env.to_dict()
        rebuilt = StyleEnvelope.from_dict(raw)
        self.assertEqual(rebuilt.profile, env.profile)
        self.assertEqual(rebuilt.traits, env.traits)
        self.assertEqual(rebuilt.sample_count, env.sample_count)
        self.assertEqual(rebuilt.contract_version, env.contract_version)


# ─── export ───────────────────────────────────────────────────────────


class TestExport(_IsolatedSync):
    def test_export_populated_store(self) -> None:
        from backend.core.clone import record_message
        from backend.core.clone.sync import export_profile

        for m in [
            "Hello team, quick sync on the deal flow.",
            "Let's wrap the contract review by Friday.",
            "Yeah lol, that was a great quarter, btw.",
        ]:
            _run(record_message(m))

        env = _run(export_profile())
        self.assertEqual(env.schema_version, 1)
        self.assertEqual(env.contract_version, "0.2.0")
        self.assertIsInstance(env.profile, dict)
        self.assertGreaterEqual(env.profile.get("sample_count", 0), 3)
        self.assertGreaterEqual(len(env.traits), 3)
        self.assertEqual(env.sample_count, len(env.traits))

    def test_export_disabled_store_returns_empty_envelope(self) -> None:
        os.environ["CLONE_STORE"] = "disabled"
        from backend.core.clone import reset_clone_store
        from backend.core.clone.sync import export_profile

        reset_clone_store()
        env = _run(export_profile())
        self.assertEqual(env.traits, [])
        self.assertEqual(env.sample_count, 0)


# ─── import ───────────────────────────────────────────────────────────


class TestImport(_IsolatedSync):
    def test_import_into_empty_store(self) -> None:
        from backend.core.clone import profile
        from backend.core.clone.sync import StyleEnvelope, import_profile

        env = StyleEnvelope(
            traits=[
                {"text": "Imported message number one.", "created_at": 100.0},
                {"text": "Imported message number two.", "created_at": 200.0},
            ],
        )
        result = _run(import_profile(env))
        self.assertTrue(result["ok"])
        self.assertEqual(result["imported"], 2)
        self.assertEqual(result["skipped"], 0)

        prof = _run(profile())
        self.assertEqual(prof.sample_count, 2)

    def test_import_dedups_by_text(self) -> None:
        from backend.core.clone import record_message
        from backend.core.clone.sync import StyleEnvelope, import_profile

        _run(record_message("Duplicate-text message that should dedup."))

        env = StyleEnvelope(
            traits=[
                {"text": "Duplicate-text message that should dedup.", "created_at": 1.0},
                {"text": "Fresh new message we have not seen.", "created_at": 2.0},
                {"text": "", "created_at": 3.0},  # skipped (empty)
            ],
        )
        result = _run(import_profile(env))
        self.assertTrue(result["ok"])
        self.assertEqual(result["imported"], 1)
        self.assertGreaterEqual(result["skipped"], 2)

    def test_import_unsupported_schema_version(self) -> None:
        from backend.core.clone.sync import StyleEnvelope, import_profile

        env = StyleEnvelope(schema_version=999, traits=[{"text": "hi"}])
        result = _run(import_profile(env))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "schema_version_unsupported")

    def test_import_into_disabled_store(self) -> None:
        os.environ["CLONE_STORE"] = "disabled"
        from backend.core.clone import reset_clone_store
        from backend.core.clone.sync import StyleEnvelope, import_profile

        reset_clone_store()
        env = StyleEnvelope(traits=[{"text": "any"}])
        result = _run(import_profile(env))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "clone_store_disabled")

    def test_import_preserves_created_at(self) -> None:
        from backend.core.clone import get_clone_store
        from backend.core.clone.sync import StyleEnvelope, import_profile

        env = StyleEnvelope(
            traits=[
                {"text": "Old message from far away.", "created_at": 1000.0},
            ],
        )
        _run(import_profile(env))
        store = get_clone_store()
        rows = _run(store.recent(limit=10))
        self.assertEqual(len(rows), 1)
        # Re-inserted with the original timestamp, not now().
        self.assertAlmostEqual(rows[0]["created_at"], 1000.0, places=2)

    def test_import_accepts_dict_envelope(self) -> None:
        from backend.core.clone import profile
        from backend.core.clone.sync import import_profile

        raw = {
            "schema_version": 1,
            "contract_version": "0.2.0",
            "exported_at": 12345.0,
            "profile": {},
            "traits": [{"text": "Plain-dict-envelope path message.", "created_at": 50.0}],
            "sample_count": 1,
        }
        result = _run(import_profile(raw))
        self.assertTrue(result["ok"])
        self.assertEqual(result["imported"], 1)
        self.assertEqual(_run(profile()).sample_count, 1)


# ─── webhook emit debouncer ───────────────────────────────────────────


class TestEmitDebounce(_IsolatedSync):
    def test_threshold_respected(self) -> None:
        # With interval=3, the first two calls should NOT trigger,
        # the third call should reset counter and fire-and-forget
        # without crashing the sync wrapper.
        os.environ["TARS_CLONE_SYNC_INTERVAL"] = "3"

        from backend.core.clone import sync as sync_mod

        sync_mod._reset_for_tests()
        # First two calls below threshold.
        sync_mod.maybe_emit_sync_webhook()
        sync_mod.maybe_emit_sync_webhook()
        self.assertEqual(sync_mod._sync_counter, 2)

        # Third call hits threshold; counter resets to 0.
        sync_mod.maybe_emit_sync_webhook()
        self.assertEqual(sync_mod._sync_counter, 0)

    def test_default_interval_50(self) -> None:
        from backend.core.clone import sync as sync_mod

        self.assertEqual(sync_mod._interval(), sync_mod.SYNC_INTERVAL_DEFAULT)
        self.assertEqual(sync_mod.SYNC_INTERVAL_DEFAULT, 50)

    def test_interval_env_override(self) -> None:
        from backend.core.clone import sync as sync_mod

        os.environ["TARS_CLONE_SYNC_INTERVAL"] = "7"
        self.assertEqual(sync_mod._interval(), 7)

        os.environ["TARS_CLONE_SYNC_INTERVAL"] = "not-a-number"
        self.assertEqual(sync_mod._interval(), sync_mod.SYNC_INTERVAL_DEFAULT)

        os.environ["TARS_CLONE_SYNC_INTERVAL"] = "-5"
        # Clamped to min 1.
        self.assertEqual(sync_mod._interval(), 1)

    def test_reset_for_tests(self) -> None:
        from backend.core.clone import sync as sync_mod

        sync_mod._sync_counter = 42
        sync_mod._last_emit_ts = 1234.0
        sync_mod._reset_for_tests()
        self.assertEqual(sync_mod._sync_counter, 0)
        self.assertEqual(sync_mod._last_emit_ts, 0.0)


# ─── record_message → emit wiring ─────────────────────────────────────


class TestRecordMessageWiresEmit(_IsolatedSync):
    def test_record_message_calls_maybe_emit(self) -> None:
        # Setting interval=1 means every record_message bumps the
        # counter past threshold and resets. Capture by patching.
        os.environ["TARS_CLONE_SYNC_INTERVAL"] = "10"

        from backend.core.clone import record_message
        from backend.core.clone import sync as sync_mod

        sync_mod._reset_for_tests()
        _run(record_message("Wiring smoke-test message — long enough."))
        self.assertEqual(sync_mod._sync_counter, 1)

        _run(record_message("Second wiring smoke-test message."))
        self.assertEqual(sync_mod._sync_counter, 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
