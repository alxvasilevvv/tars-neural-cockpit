"""Tests for the bundles module (Wave 107).

Stdlib unittest only -- runs under ``python3 -m unittest``.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path

from backend.core.bundles import (
    BUILTIN_BUNDLES,
    bundle_by_id,
    bundle_for_org_type,
    list_bundles,
)
from backend.core.bundles import installer as installer_mod
from backend.core.bundles.previewer import preview_bundle


def _run(coro):
    return asyncio.run(coro)


class _IsolatedBundleCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="bundles-")
        self._db = str(Path(self._tmp) / "installed.sqlite")
        os.environ["TARS_BUNDLES_DB_PATH"] = self._db
        # Disable side-effect modules so the install path is hermetic.
        os.environ["TARS_SCHEDULER_STORE"] = "disabled"
        os.environ["TARS_OUTREACH_STORE"] = "disabled"
        os.environ["TARS_RECEIPT_STORE"] = "disabled"
        installer_mod.reset_db()

    def tearDown(self) -> None:
        installer_mod.reset_db()
        for k in (
            "TARS_BUNDLES_DB_PATH",
            "TARS_SCHEDULER_STORE",
            "TARS_OUTREACH_STORE",
            "TARS_RECEIPT_STORE",
        ):
            os.environ.pop(k, None)


class BundleDefinitionsTests(unittest.TestCase):
    def test_seven_bundles_present(self) -> None:
        self.assertEqual(len(BUILTIN_BUNDLES), 7)
        ids = [b.id for b in BUILTIN_BUNDLES]
        for needle in (
            "vc_fund_bundle",
            "hedge_fund_bundle",
            "family_office_bundle",
            "saas_bundle",
            "dao_bundle",
            "research_lab_bundle",
            "other_bundle",
        ):
            self.assertIn(needle, ids)

    def test_recommended_bundle_for_org_type(self) -> None:
        self.assertEqual(
            bundle_for_org_type("vc_fund").id, "vc_fund_bundle"
        )
        self.assertEqual(
            bundle_for_org_type("hedge_fund").id, "hedge_fund_bundle"
        )
        self.assertEqual(
            bundle_for_org_type("saas").id, "saas_bundle"
        )
        # Unknown / empty -> other_bundle fallback.
        self.assertEqual(bundle_for_org_type("nonsense").id, "other_bundle")
        self.assertEqual(bundle_for_org_type(None).id, "other_bundle")
        self.assertEqual(bundle_for_org_type("").id, "other_bundle")

    def test_bundle_lookup_by_id_or_slug(self) -> None:
        self.assertIsNotNone(bundle_by_id("vc_fund_bundle"))
        # slug form should also work.
        self.assertEqual(bundle_by_id("vc-fund").id, "vc_fund_bundle")
        self.assertIsNone(bundle_by_id("does_not_exist"))

    def test_each_bundle_has_required_keys(self) -> None:
        for b in list_bundles():
            d = b.to_dict()
            self.assertIn("components", d)
            comps = d["components"]
            self.assertIn("playbooks", comps)
            self.assertIn("dashboard_widgets", comps)
            self.assertIn("welcome_content", comps)
            self.assertGreater(len(b.welcome_content()), 10)
            # Most bundles have at least one playbook.
            self.assertGreaterEqual(len(b.playbooks()), 2)


class BundlePreviewTests(unittest.TestCase):
    def test_preview_returns_components_for_vc_fund(self) -> None:
        out = preview_bundle("vc_fund_bundle")
        self.assertTrue(out["ok"])
        prev = out["preview"]
        self.assertTrue(prev["dry_run"])
        self.assertEqual(len(prev["items"]["playbooks"]), 5)
        self.assertEqual(len(prev["items"]["scheduled"]), 2)
        self.assertEqual(len(prev["items"]["dashboard_widgets"]), 5)
        self.assertEqual(len(prev["items"]["report_templates"]), 3)
        self.assertEqual(len(prev["items"]["outreach_templates"]), 5)
        # gmail hint is priority for VC.
        hints = prev["items"]["connectors_hints"]
        self.assertTrue(any(h.get("id") == "gmail" and h.get("priority") for h in hints))

    def test_preview_unknown_bundle(self) -> None:
        out = preview_bundle("does_not_exist")
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "bundle_not_found")

    def test_preview_for_hedge_fund_has_one_schedule(self) -> None:
        out = preview_bundle("hedge_fund_bundle")
        self.assertTrue(out["ok"])
        prev = out["preview"]
        self.assertEqual(len(prev["items"]["scheduled"]), 1)


class BundleInstallTests(_IsolatedBundleCase):
    def test_install_creates_install_row(self) -> None:
        report = _run(installer_mod.install_bundle("vc_fund_bundle", "org_test"))
        self.assertEqual(report.bundle_id, "vc_fund_bundle")
        self.assertEqual(report.org_id, "org_test")
        self.assertFalse(report.dry_run)
        # First install should not warn ``already_installed``.
        self.assertNotIn("already_installed", report.warnings)
        # Items contain at least the playbooks + widgets + connectors_hints.
        self.assertEqual(len(report.items["playbooks"]), 5)
        self.assertEqual(len(report.items["dashboard_widgets"]), 5)
        # Sanity: install row is on disk.
        installs = _run(installer_mod.list_installed("org_test"))
        self.assertEqual(len(installs), 1)
        self.assertEqual(installs[0]["bundle_id"], "vc_fund_bundle")

    def test_install_is_idempotent(self) -> None:
        first = _run(installer_mod.install_bundle("saas_bundle", "org_x"))
        second = _run(installer_mod.install_bundle("saas_bundle", "org_x"))
        # Same install_id reused.
        self.assertEqual(first.install_id, second.install_id)
        self.assertIn("already_installed", second.warnings)
        # Only one row ever in the registry.
        installs = _run(installer_mod.list_installed("org_x"))
        self.assertEqual(len(installs), 1)

    def test_install_first_run_recorded(self) -> None:
        report = _run(
            installer_mod.install_bundle(
                "dao_bundle", "org_dao", run_first_now=True
            )
        )
        self.assertEqual(report.first_run_id, "dao/treasury_diff")
        # When ``run_first_now=True`` the scheduled list grows by 1
        # (the @now intent marker), even when scheduler store is off.
        first_run_entries = [
            s for s in report.items["scheduled"] if s.get("first_run")
        ]
        self.assertEqual(len(first_run_entries), 1)

    def test_install_unknown_bundle_returns_warning_report(self) -> None:
        report = _run(installer_mod.install_bundle("does_not_exist", "org_y"))
        self.assertIn("bundle_not_found", report.warnings)

    def test_uninstall_clears_install_row(self) -> None:
        _run(installer_mod.install_bundle("family_office_bundle", "org_fo"))
        report = _run(
            installer_mod.uninstall_bundle("family_office_bundle", "org_fo")
        )
        self.assertNotIn("not_installed", report.warnings)
        installs = _run(installer_mod.list_installed("org_fo"))
        self.assertEqual(len(installs), 0)

    def test_uninstall_nonexistent_warns(self) -> None:
        report = _run(installer_mod.uninstall_bundle("vc_fund_bundle", "org_z"))
        self.assertIn("not_installed", report.warnings)

    def test_install_isolated_per_org(self) -> None:
        _run(installer_mod.install_bundle("vc_fund_bundle", "org_a"))
        _run(installer_mod.install_bundle("vc_fund_bundle", "org_b"))
        all_rows = _run(installer_mod.list_installed())
        self.assertEqual(len(all_rows), 2)
        a_only = _run(installer_mod.list_installed("org_a"))
        self.assertEqual(len(a_only), 1)
        self.assertEqual(a_only[0]["org_id"], "org_a")


if __name__ == "__main__":
    unittest.main()
