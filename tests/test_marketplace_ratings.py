"""Tests for the local-only marketplace ratings store (Wave 106).

Stdlib unittest only -- runs under ``python3 -m unittest``.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest

from backend.core.marketplace import anonymise_rater
from backend.core.marketplace import ratings as ratings_mod


def _run(coro):
    return asyncio.run(coro)


class _IsolatedRatingsCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self._tmp.close()
        os.environ["TARS_MARKETPLACE_RATINGS_DB"] = self._tmp.name
        ratings_mod.reset_db()

    def tearDown(self) -> None:
        ratings_mod.reset_db()
        os.environ.pop("TARS_MARKETPLACE_RATINGS_DB", None)


class SubmitTests(_IsolatedRatingsCase):
    def test_submit_then_get_aggregate_round_trip(self) -> None:
        out = _run(
            ratings_mod.submit_rating(
                "mlst_a", 5, comment="great", rater_email="op@example.com"
            )
        )
        self.assertTrue(out["ok"])
        agg = _run(ratings_mod.get_aggregate("mlst_a"))
        self.assertEqual(agg["count"], 1)
        self.assertEqual(agg["avg"], 5.0)

    def test_double_vote_from_same_rater_updates_in_place(self) -> None:
        _run(ratings_mod.submit_rating("mlst_b", 5, rater_email="op@x.com"))
        _run(ratings_mod.submit_rating("mlst_b", 1, rater_email="op@x.com"))
        agg = _run(ratings_mod.get_aggregate("mlst_b"))
        self.assertEqual(agg["count"], 1)
        self.assertEqual(agg["avg"], 1.0)

    def test_distinct_raters_each_count(self) -> None:
        _run(ratings_mod.submit_rating("mlst_c", 5, rater_email="alice@a.com"))
        _run(ratings_mod.submit_rating("mlst_c", 3, rater_email="bob@b.com"))
        agg = _run(ratings_mod.get_aggregate("mlst_c"))
        self.assertEqual(agg["count"], 2)
        self.assertEqual(agg["avg"], 4.0)

    def test_score_out_of_range_rejected(self) -> None:
        out = _run(
            ratings_mod.submit_rating("mlst_d", 7, rater_email="op@x.com")
        )
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "score_must_be_1_to_5")


class AnonymiseTests(unittest.TestCase):
    def test_stable_and_anonymous(self) -> None:
        h1 = anonymise_rater("Op@Example.com")
        h2 = anonymise_rater("op@example.com")
        h3 = anonymise_rater("other@example.com")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)
        self.assertNotIn("@", h1)
        self.assertEqual(anonymise_rater(""), "anonymous")


if __name__ == "__main__":
    unittest.main()
