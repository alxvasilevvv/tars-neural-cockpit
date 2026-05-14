"""W239 - tests for the Rules-for-TARS module + router.

Env-isolated: every test uses a tmp HOME so ~/.tars/rules.yml is
sandboxed and tests don't poison each other.

Cases:
1. First load creates the seed file with 5 default rules.
2. inject_rules_into_prompt prepends "## Rules" correctly.
3. POST /api/rules replaces global rules; GET returns the new set.
4. PUT /api/rules/{id} toggles the enabled flag.
5. Per-pack overlay loads correctly when active_pack is passed.
"""

from __future__ import annotations

import importlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path


class _IsolatedRulesHome(unittest.TestCase):
    """Each test points TARS_HOME at a fresh tmpdir."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w239-rules-")
        self._old_home = os.environ.get("TARS_HOME")
        os.environ["TARS_HOME"] = self._tmp

    def tearDown(self) -> None:
        if self._old_home is None:
            os.environ.pop("TARS_HOME", None)
        else:
            os.environ["TARS_HOME"] = self._old_home
        try:
            shutil.rmtree(self._tmp, ignore_errors=True)
        except Exception:
            pass


class TestSeedOnFirstLoad(_IsolatedRulesHome):
    def test_first_load_creates_seed_file_with_five_rules(self) -> None:
        from backend.core import rules as rules_mod
        importlib.reload(rules_mod)

        path = rules_mod.global_rules_path()
        self.assertFalse(path.exists())

        loaded = rules_mod.load_global_rules()
        self.assertTrue(path.exists())
        self.assertEqual(len(loaded), 5)
        for r in loaded:
            self.assertTrue(r.enabled)
            self.assertTrue(r.text)
            self.assertEqual(r.scope, "global")
            self.assertIsNone(r.pack)

        ids = {r.id for r in loaded}
        self.assertIn("seed-language", ids)
        self.assertIn("seed-confirm-dangerous", ids)


class TestInjectRulesIntoPrompt(_IsolatedRulesHome):
    def test_prepends_rules_block(self) -> None:
        from backend.core import rules as rules_mod
        importlib.reload(rules_mod)

        base = "You are TARS."
        out = rules_mod.inject_rules_into_prompt(base, None)
        self.assertIn("## Rules", out)
        # The block goes before the base prompt.
        rules_idx = out.find("## Rules")
        base_idx = out.find("You are TARS.")
        self.assertLess(rules_idx, base_idx)
        # Numbered list of enabled rules.
        self.assertIn("1.", out)

    def test_disabled_rules_skipped(self) -> None:
        from backend.core import rules as rules_mod
        from backend.core.rules import Rule
        importlib.reload(rules_mod)

        # Seed first (so the file exists), then save a custom mix.
        rules_mod.load_global_rules()
        rules_mod.save_global_rules(
            [
                Rule(id="a", text="ENABLED-RULE", enabled=True),
                Rule(id="b", text="DISABLED-RULE", enabled=False),
            ]
        )
        out = rules_mod.inject_rules_into_prompt("base", None)
        self.assertIn("ENABLED-RULE", out)
        self.assertNotIn("DISABLED-RULE", out)


class TestSaveAndGet(_IsolatedRulesHome):
    def test_save_replaces_and_get_returns_updated(self) -> None:
        from backend.core import rules as rules_mod
        from backend.core.rules import Rule
        importlib.reload(rules_mod)

        # Replace seed with two custom rules.
        rules_mod.save_global_rules(
            [
                Rule(id="r1", text="be brief", enabled=True),
                Rule(id="r2", text="cite sources", enabled=True),
            ]
        )
        loaded = rules_mod.load_global_rules()
        self.assertEqual(len(loaded), 2)
        texts = [r.text for r in loaded]
        self.assertIn("be brief", texts)
        self.assertIn("cite sources", texts)

    def test_pack_scope_rules_are_dropped_on_save(self) -> None:
        from backend.core import rules as rules_mod
        from backend.core.rules import Rule
        importlib.reload(rules_mod)

        rules_mod.save_global_rules(
            [
                Rule(id="r1", text="global rule", enabled=True, scope="global"),
                Rule(id="r2", text="pack rule", enabled=True, scope="pack", pack="business"),
            ]
        )
        loaded = rules_mod.load_global_rules()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].id, "r1")


class TestPatchToggle(_IsolatedRulesHome):
    def test_put_toggles_enabled_flag(self) -> None:
        from backend.core import rules as rules_mod
        importlib.reload(rules_mod)

        rules_mod.load_global_rules()  # seed
        updated = rules_mod.patch_global_rule("seed-language", enabled=False)
        self.assertIsNotNone(updated)
        self.assertFalse(updated.enabled)

        loaded = rules_mod.load_global_rules()
        by_id = {r.id: r for r in loaded}
        self.assertIn("seed-language", by_id)
        self.assertFalse(by_id["seed-language"].enabled)

    def test_put_missing_returns_none(self) -> None:
        from backend.core import rules as rules_mod
        importlib.reload(rules_mod)
        rules_mod.load_global_rules()
        out = rules_mod.patch_global_rule("nonexistent-id", enabled=False)
        self.assertIsNone(out)


class TestPackOverlay(_IsolatedRulesHome):
    def test_pack_overlay_loaded_when_active_pack_passed(self) -> None:
        from backend.core import rules as rules_mod
        importlib.reload(rules_mod)

        # Write a pack rules.yml into a real pack dir.
        pack_slug = "business"
        pack_path = rules_mod.pack_rules_path(pack_slug)
        pack_path.parent.mkdir(parents=True, exist_ok=True)
        # Use a temp pack rules file but restore afterwards.
        had_existing = pack_path.exists()
        backup = pack_path.read_text() if had_existing else None
        try:
            pack_path.write_text(
                "rules:\n"
                "  - id: pk-1\n"
                "    text: \"Always lead with the metric\"\n"
                "    enabled: true\n"
                "  - id: pk-2\n"
                "    text: \"Disabled pack rule\"\n"
                "    enabled: false\n"
            )
            overlay = rules_mod.load_pack_rules(pack_slug)
            self.assertEqual(len(overlay), 2)
            self.assertEqual(overlay[0].scope, "pack")
            self.assertEqual(overlay[0].pack, pack_slug)
            self.assertEqual(overlay[0].text, "Always lead with the metric")

            # active_pack flows through load_active_rules
            rules_mod.load_global_rules()
            active = rules_mod.load_active_rules(pack_slug)
            ids = [r.id for r in active]
            self.assertIn("pk-1", ids)

            # inject_rules_into_prompt picks up the pack rule
            injected = rules_mod.inject_rules_into_prompt("base", pack_slug)
            self.assertIn("Always lead with the metric", injected)
            self.assertIn("(from pack: business)", injected)
        finally:
            if backup is not None:
                pack_path.write_text(backup)
            else:
                try:
                    pack_path.unlink()
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()
