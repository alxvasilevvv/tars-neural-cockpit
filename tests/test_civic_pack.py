"""W204 — civic domain pack tests.

Verifies the pack registers correctly, exposes 3 actions, and that each
handler returns a structured ``{ok, ...}`` response on bad input (no
500s even when args are missing or the network is down).

The HTTP layer is monkey-patched so tests never hit the public APIs.
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any


class TestCivicPack(unittest.TestCase):
    def test_pack_registered_with_seven_slug(self) -> None:
        # Trigger registration through the canonical package import path.
        from backend.core.domains import packs as _packs  # noqa: F401
        from backend.core.domains.registry import get_pack

        pack = get_pack("civic")
        self.assertIsNotNone(pack)
        self.assertEqual(pack.manifest.slug, "civic")
        self.assertEqual(pack.manifest.name, "Civic")
        self.assertFalse(pack.manifest.deprecated)

    def test_pack_exposes_three_actions(self) -> None:
        from backend.core.domains.registry import get_pack

        pack = get_pack("civic")
        action_ids = sorted(a.id for a in pack.actions())
        self.assertEqual(
            action_ids,
            ["court_case_search", "lookup_legislator", "recent_votes"],
        )

    def test_pack_has_no_vault_keys(self) -> None:
        # Civic pack is keyless by design — free public APIs only.
        from backend.core.domains.registry import get_pack

        pack = get_pack("civic")
        self.assertEqual(pack.auth_vault_keys(), ())

    def test_lookup_legislator_missing_query(self) -> None:
        from backend.core.domains.packs.civic.actions import _lookup_legislator

        result = asyncio.run(_lookup_legislator({}))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "missing_query")
        self.assertIn("hint", result)

    def test_recent_votes_missing_id(self) -> None:
        from backend.core.domains.packs.civic.actions import _recent_votes

        result = asyncio.run(_recent_votes({}))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "missing_openstates_id")

    def test_court_case_search_missing_query(self) -> None:
        from backend.core.domains.packs.civic.actions import _court_case_search

        result = asyncio.run(_court_case_search({}))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "missing_query")

    def test_lookup_legislator_network_failure_returns_structured_error(self) -> None:
        # Monkey-patch get_json to raise so we hit the upstream_failed branch.
        from backend.core.domains.packs.civic import actions as civic_actions

        original_get_json = civic_actions.get_json

        async def boom(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("network down")

        civic_actions.get_json = boom  # type: ignore[assignment]
        try:
            result = asyncio.run(civic_actions._lookup_legislator({"name": "Pelosi"}))
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"], "upstream_failed")
            self.assertIn("network down", result["message"])
        finally:
            civic_actions.get_json = original_get_json  # type: ignore[assignment]

    def test_lookup_legislator_parses_results(self) -> None:
        from backend.core.domains.packs.civic import actions as civic_actions

        original_get_json = civic_actions.get_json

        async def fake(*args: Any, **kwargs: Any) -> Any:
            return {
                "results": [
                    {
                        "id": "ocd-person/abc",
                        "name": "Jane Doe",
                        "party": "Democratic",
                        "jurisdiction": {"name": "California"},
                        "current_role": {
                            "title": "State Senator",
                            "district": "11",
                        },
                        "image": "https://example/img.jpg",
                        "openstates_url": "https://openstates.org/p/jane-doe",
                    }
                ]
            }

        civic_actions.get_json = fake  # type: ignore[assignment]
        try:
            result = asyncio.run(civic_actions._lookup_legislator({"name": "Jane"}))
            self.assertTrue(result["ok"])
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["results"][0]["name"], "Jane Doe")
            self.assertEqual(result["results"][0]["state"], "California")
            self.assertEqual(result["results"][0]["district"], "11")
        finally:
            civic_actions.get_json = original_get_json  # type: ignore[assignment]


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
