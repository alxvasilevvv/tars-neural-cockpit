"""Starter-template seeding tests for the outreach module (Wave 98).

Verifies that ``seed_starter_templates`` is idempotent + ships the
five expected slugs with non-empty prompts and well-formed variable
lists.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest

from backend.core.outreach import OutreachStore, USE_CASES, reset_store
from backend.core.outreach.templates import (
    seed_starter_templates,
    starter_specs,
)


def _run(coro):
    return asyncio.run(coro)


_EXPECTED_SLUGS = {"lp_update", "founder_dd", "intro", "follow_up", "welcome_lp"}


class _StarterCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self._tmp.close()
        os.environ["TARS_OUTREACH_DB_PATH"] = self._tmp.name
        os.environ.pop("TARS_OUTREACH_STORE", None)
        reset_store()
        self.store = OutreachStore(self._tmp.name)

    def tearDown(self) -> None:
        for path in (
            self._tmp.name,
            self._tmp.name + "-shm",
            self._tmp.name + "-wal",
            self._tmp.name + "-journal",
        ):
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
        os.environ.pop("TARS_OUTREACH_DB_PATH", None)
        reset_store()


class TestStarterSpecs(unittest.TestCase):
    def test_five_specs_with_expected_slugs(self) -> None:
        specs = starter_specs()
        self.assertEqual(len(specs), 5)
        slugs = {s["slug"] for s in specs}
        self.assertEqual(slugs, _EXPECTED_SLUGS)

    def test_each_spec_has_prompt_and_use_case(self) -> None:
        for spec in starter_specs():
            self.assertIn(spec["use_case"], USE_CASES)
            self.assertGreater(len(spec["system_prompt"]), 50)
            self.assertIsInstance(spec["variables"], list)


class TestSeeder(_StarterCase):
    def test_seed_persists_five(self) -> None:
        seeded = _run(seed_starter_templates(store=self.store))
        self.assertEqual(len(seeded), 5)
        listed = _run(self.store.list_templates())
        self.assertEqual({t.slug for t in listed}, _EXPECTED_SLUGS)

    def test_seed_is_idempotent(self) -> None:
        first = _run(seed_starter_templates(store=self.store))
        first_ids = {t.slug: t.id for t in first}
        # Run again -- IDs preserved, no duplicates.
        second = _run(seed_starter_templates(store=self.store))
        second_ids = {t.slug: t.id for t in second}
        self.assertEqual(first_ids, second_ids)
        listed = _run(self.store.list_templates())
        self.assertEqual(len(listed), 5)

    def test_each_seeded_template_has_variables_list(self) -> None:
        seeded = _run(seed_starter_templates(store=self.store))
        for t in seeded:
            self.assertIsInstance(t.variables, list)
            # All starters except follow-up have at least 3 variables;
            # the bare minimum across all five is "non-empty".
            self.assertTrue(len(t.variables) >= 1, f"{t.slug} missing variables")


if __name__ == "__main__":
    unittest.main()
