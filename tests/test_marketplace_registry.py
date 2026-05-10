"""Tests for the marketplace registry (Wave 106).

Covers: seed fallback, force-refresh path, on-disk cache TTL, the
search/category/kind/min_rating filters, and per-listing lookup.
Network is faked via ``TARS_MARKETPLACE_OFFLINE=1`` so no live
HTTP touches the sandbox.

Stdlib ``unittest`` only -- runs under ``python3 -m unittest``.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest

from backend.core.marketplace import LISTING_KINDS
from backend.core.marketplace import registry as registry_mod
from backend.core.marketplace.seed import seed_count


def _run(coro):
    return asyncio.run(coro)


class _IsolatedRegistryCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="mkt-cache-")
        os.environ["TARS_MARKETPLACE_CACHE_DIR"] = self._tmp
        os.environ["TARS_MARKETPLACE_OFFLINE"] = "1"
        registry_mod.reset_cache()

    def tearDown(self) -> None:
        registry_mod.reset_cache()
        os.environ.pop("TARS_MARKETPLACE_CACHE_DIR", None)
        os.environ.pop("TARS_MARKETPLACE_OFFLINE", None)


class FetchRegistryTests(_IsolatedRegistryCase):
    def test_returns_seed_when_offline(self) -> None:
        payload = _run(registry_mod.fetch_registry())
        self.assertEqual(payload["source"], "seed")
        self.assertEqual(len(payload["listings"]), seed_count())
        self.assertTrue(all("id" in item for item in payload["listings"]))

    def test_caches_payload_on_disk(self) -> None:
        os.environ["TARS_MARKETPLACE_OFFLINE"] = "0"
        original = registry_mod._fetch_remote_sync
        registry_mod._fetch_remote_sync = lambda: [
            {"id": "mlst_alpha", "kind": "playbook", "name": "A", "slug": "a"}
        ]
        try:
            payload = _run(registry_mod.fetch_registry(force_refresh=True))
            self.assertEqual(payload["source"], "remote")
            self.assertEqual(payload["listings"][0]["id"], "mlst_alpha")
            registry_mod._fetch_remote_sync = lambda: None
            cached = _run(registry_mod.fetch_registry())
            self.assertEqual(cached["source"], "remote")
            self.assertEqual(cached["listings"][0]["id"], "mlst_alpha")
        finally:
            registry_mod._fetch_remote_sync = original

    def test_force_refresh_bypasses_cache(self) -> None:
        os.environ["TARS_MARKETPLACE_OFFLINE"] = "0"
        original = registry_mod._fetch_remote_sync
        calls: list[int] = []

        def fake_fetch():
            calls.append(1)
            return [
                {"id": "mlst_x", "kind": "playbook", "name": "X", "slug": "x"}
            ]

        registry_mod._fetch_remote_sync = fake_fetch
        try:
            _run(registry_mod.fetch_registry(force_refresh=True))
            _run(registry_mod.fetch_registry(force_refresh=True))
            self.assertEqual(len(calls), 2)
        finally:
            registry_mod._fetch_remote_sync = original


class FilterTests(_IsolatedRegistryCase):
    def test_filters_by_kind(self) -> None:
        items = _run(registry_mod.list_listings(kind="report_template"))
        self.assertTrue(items)
        self.assertTrue(all(it.kind == "report_template" for it in items))

    def test_filters_by_category(self) -> None:
        items = _run(registry_mod.list_listings(category="fund"))
        self.assertTrue(items)
        self.assertTrue(all(it.category == "fund" for it in items))

    def test_search_q(self) -> None:
        items = _run(registry_mod.list_listings(q="algotrade"))
        # Two algotrade-ish seeds (pack + community).
        self.assertGreaterEqual(len(items), 2)

    def test_min_rating_filter(self) -> None:
        items = _run(registry_mod.list_listings(min_rating=4.5))
        self.assertTrue(all(it.ratings_avg >= 4.5 for it in items))

    def test_combined_filters(self) -> None:
        items = _run(
            registry_mod.list_listings(category="algotrade", kind="playbook")
        )
        self.assertTrue(items)
        for it in items:
            self.assertEqual(it.category, "algotrade")
            self.assertEqual(it.kind, "playbook")


class GetListingTests(_IsolatedRegistryCase):
    def test_round_trip_by_id(self) -> None:
        payload = _run(registry_mod.fetch_registry())
        first_id = payload["listings"][0]["id"]
        listing = _run(registry_mod.get_listing(first_id))
        self.assertIsNotNone(listing)
        assert listing is not None
        self.assertEqual(listing.id, first_id)

    def test_unknown_returns_none(self) -> None:
        self.assertIsNone(_run(registry_mod.get_listing("mlst_does_not_exist")))


class SeedVocabTests(_IsolatedRegistryCase):
    def test_seed_kinds_aligned_with_vocab(self) -> None:
        payload = _run(registry_mod.fetch_registry())
        seed_kinds = {item.get("kind") for item in payload["listings"]}
        self.assertTrue(
            seed_kinds.issubset(set(LISTING_KINDS)),
            f"unknown kinds in seed: {seed_kinds - set(LISTING_KINDS)}",
        )


if __name__ == "__main__":
    unittest.main()
