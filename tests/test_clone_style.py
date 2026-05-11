"""Wave 123 — coverage for backend.core.clone.style (W73 AI Clone v0.1).

Wave 122 audit found this module had ZERO tests despite shipping in
v9.1.0. This file covers the minimum surface a future v0.2 refactor
mustn't regress.

Cases:
- record_message persists a row (and respects MIN_LENGTH guard)
- profile aggregates style metrics over rolling window
- nearest_examples returns top-K via hash-trigram fallback
- empty_history returns sensible defaults (no zero division)
- draft falls back gracefully when no LLM key is configured
- profile_after_N_messages stays stable shape across re-builds
- record_message returns False when CLONE_STORE=disabled
- store_isolation_per_db_path: distinct paths -> distinct content
- corrupt_db file recovers via init_schema (best-effort)
- v0_1_metadata in profile output (honest version label)
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import unittest
from pathlib import Path


def _run(coro):
    return asyncio.run(coro)


class _IsolatedClone(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w123-clone-")
        os.environ["TARS_CLONE_DB_PATH"] = os.path.join(
            self._tmp, "clone.sqlite"
        )
        os.environ.pop("CLONE_STORE", None)
        # Make sure the LLM rewrite path stays in fallback mode.
        for k in (
            "TARS_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY",
            "TARS_OPENAI_API_KEY", "OPENAI_API_KEY",
        ):
            os.environ.pop(k, None)
        from backend.core.clone import reset_clone_store
        reset_clone_store()

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass
        os.environ.pop("TARS_CLONE_DB_PATH", None)
        os.environ.pop("CLONE_STORE", None)
        from backend.core.clone import reset_clone_store
        reset_clone_store()


class TestRecordMessage(_IsolatedClone):
    def test_records_message_into_store(self) -> None:
        from backend.core.clone import record_message, profile
        ok = _run(record_message("Hello there, this is a test message."))
        self.assertTrue(ok)
        prof = _run(profile())
        self.assertEqual(prof.sample_count, 1)

    def test_min_length_guard(self) -> None:
        from backend.core.clone import record_message
        # Three-character text below the MIN_LENGTH guard returns False.
        self.assertFalse(_run(record_message("hi")))
        self.assertFalse(_run(record_message("")))
        self.assertFalse(_run(record_message("   ")))

    def test_disabled_store_short_circuits(self) -> None:
        os.environ["CLONE_STORE"] = "disabled"
        from backend.core.clone import reset_clone_store, record_message
        reset_clone_store()
        ok = _run(record_message("This message would normally be recorded."))
        self.assertFalse(ok)


class TestProfileAggregation(_IsolatedClone):
    def test_profile_aggregates_metrics(self) -> None:
        from backend.core.clone import record_message, profile
        msgs = [
            "Hello! How are you doing today?",
            "I'm gonna head out, btw, see ya later.",
            "Therefore the analysis indicates a positive trend.",
            "Yeah lol that was funny haha.",
            "However, we should consider the formal aspects.",
        ]
        for m in msgs:
            _run(record_message(m))
        prof = _run(profile())
        self.assertEqual(prof.sample_count, 5)
        self.assertGreater(prof.avg_sentence_length, 0.0)
        self.assertGreater(prof.avg_message_length_words, 0.0)
        self.assertGreaterEqual(prof.exclamation_rate, 0.0)
        self.assertIn(prof.casual_vs_formal, {"casual", "formal", "neutral"})
        # top_vocab is a list of word strings.
        self.assertIsInstance(prof.top_vocab, list)

    def test_v0_1_version_metadata(self) -> None:
        from backend.core.clone import profile
        prof = _run(profile())
        self.assertEqual(prof.version, "0.1")
        self.assertIn("v0.1", prof.note)


class TestEmptyHistory(_IsolatedClone):
    def test_empty_profile_no_zero_division(self) -> None:
        from backend.core.clone import profile
        prof = _run(profile())
        # Zero rows => sensible defaults, no crash.
        self.assertEqual(prof.sample_count, 0)
        self.assertEqual(prof.avg_sentence_length, 0.0)
        self.assertEqual(prof.exclamation_rate, 0.0)
        self.assertEqual(prof.casual_vs_formal, "neutral")
        self.assertEqual(prof.top_vocab, [])


class TestNearestExamples(_IsolatedClone):
    def test_nearest_returns_top_k_via_fallback(self) -> None:
        # No embedder configured in the test env -> hash-trigram bag fallback.
        from backend.core.clone import record_message
        from backend.core.clone.style import _nearest_examples

        for m in [
            "I love writing detailed reports about quarterly performance.",
            "The cat sat on the mat and purred contentedly.",
            "Quarterly revenue analysis suggests strong upward trajectory.",
            "Can you take the dog out for a walk this evening please?",
        ]:
            _run(record_message(m))
        out = _run(_nearest_examples("quarterly revenue report", k=2))
        self.assertEqual(len(out), 2)
        # The two business-flavoured examples should rank above the pets.
        joined = " ".join(out).lower()
        self.assertIn("quarterly", joined)


class TestDraftFallback(_IsolatedClone):
    def test_draft_without_seed_returns_no_seed_messages(self) -> None:
        from backend.core.clone import draft
        out = _run(draft(context="What should I say to the client?"))
        self.assertFalse(out["ok"])
        self.assertEqual(out["reason"], "no_seed_messages")
        self.assertEqual(out["examples_used"], 0)

    def test_draft_falls_back_to_closest_example(self) -> None:
        from backend.core.clone import record_message, draft
        for m in [
            "Hey team, quick check in on the deal flow this week.",
            "Following up on the contract review timeline.",
        ]:
            _run(record_message(m))
        out = _run(draft(context="contract deal update"))
        self.assertTrue(out["ok"])
        # No LLM key in the env -> fallback path: returns most-similar example.
        self.assertTrue(out["fallback"])
        self.assertGreater(out["examples_used"], 0)
        self.assertEqual(out["version"], "0.1")
        self.assertIn("profile", out)


class TestStorePathIsolation(unittest.TestCase):
    def test_distinct_db_paths_distinct_content(self) -> None:
        from backend.core.clone import reset_clone_store, record_message, profile
        tmp_a = tempfile.mkdtemp(prefix="tars-w123-clone-A-")
        tmp_b = tempfile.mkdtemp(prefix="tars-w123-clone-B-")
        try:
            os.environ["TARS_CLONE_DB_PATH"] = os.path.join(tmp_a, "a.sqlite")
            reset_clone_store()
            for m in ["First message in A.", "Second one in A."]:
                _run(record_message(m))
            prof_a = _run(profile())

            os.environ["TARS_CLONE_DB_PATH"] = os.path.join(tmp_b, "b.sqlite")
            reset_clone_store()
            prof_b = _run(profile())
            # B should be empty even though A has rows.
            self.assertEqual(prof_a.sample_count, 2)
            self.assertEqual(prof_b.sample_count, 0)
        finally:
            for d in (tmp_a, tmp_b):
                try:
                    shutil.rmtree(d)
                except Exception:
                    pass
            os.environ.pop("TARS_CLONE_DB_PATH", None)
            reset_clone_store()


class TestCorruptDbRecovery(_IsolatedClone):
    def test_corrupt_db_does_not_crash_record_path(self) -> None:
        # Pre-write garbage to the db path; the schema init should
        # raise but the store flips enabled=False rather than crash
        # the chat write hook.
        from backend.core.clone import reset_clone_store, record_message
        path = Path(os.environ["TARS_CLONE_DB_PATH"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"not a sqlite file at all")
        reset_clone_store()
        # Must not raise; returns False because the store treats itself
        # as disabled OR returns True if sqlite3 manages to overlay
        # the schema. Either way: no exception bubbles out.
        try:
            _run(record_message("hello world this is a test"))
        except Exception as exc:  # pragma: no cover
            self.fail(f"record_message raised on corrupt db: {exc}")


class TestProfileShapeStable(_IsolatedClone):
    def test_profile_shape_consistent_across_calls(self) -> None:
        from backend.core.clone import record_message, profile
        for i in range(5):
            _run(record_message(f"Message number {i} for the test run."))
        a = _run(profile()).to_dict()
        b = _run(profile()).to_dict()
        self.assertEqual(set(a.keys()), set(b.keys()))
        for key in (
            "version", "sample_count", "avg_sentence_length",
            "avg_message_length_words", "exclamation_rate",
            "casual_vs_formal", "top_vocab", "note",
        ):
            self.assertIn(key, a)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
