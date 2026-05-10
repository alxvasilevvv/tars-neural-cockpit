"""Tests for the marketplace installer (Wave 106).

Stdlib unittest only -- runs under ``python3 -m unittest``.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path

from backend.core.marketplace import Listing
from backend.core.marketplace import installer as installer_mod
from backend.core.marketplace import registry as registry_mod


def _run(coro):
    return asyncio.run(coro)


def _fake_inline_listing() -> Listing:
    return Listing.from_dict(
        {
            "id": "mlst_test_inline",
            "kind": "playbook",
            "name": "Inline Test",
            "slug": "inline-test",
            "install_payload": {
                "format": "playbook_inline",
                "recipe": {
                    "name": "Inline",
                    "steps": ["a", "b", "c"],
                },
            },
        }
    )


class _IsolatedInstallerCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="mkt-install-")
        os.environ["TARS_MARKETPLACE_CACHE_DIR"] = str(Path(self._tmp) / "cache")
        os.environ["TARS_MARKETPLACE_INSTALL_DB"] = str(
            Path(self._tmp) / "installed.sqlite"
        )
        os.environ["TARS_MARKETPLACE_INSTALL_ROOT"] = str(
            Path(self._tmp) / "installed"
        )
        os.environ["TARS_MARKETPLACE_OFFLINE"] = "1"
        registry_mod.reset_cache()
        installer_mod.reset_db()

    def tearDown(self) -> None:
        installer_mod.reset_db()
        registry_mod.reset_cache()
        for k in (
            "TARS_MARKETPLACE_CACHE_DIR",
            "TARS_MARKETPLACE_INSTALL_DB",
            "TARS_MARKETPLACE_INSTALL_ROOT",
            "TARS_MARKETPLACE_OFFLINE",
        ):
            os.environ.pop(k, None)


class InstallTests(_IsolatedInstallerCase):
    def test_install_inline_writes_recipe(self) -> None:
        listing = _fake_inline_listing()
        out = _run(installer_mod.install(listing))
        self.assertTrue(out["ok"])
        self.assertTrue((Path(out["installed_path"]) / "recipe.json").exists())
        self.assertIn("signature_absent", out["audit"])

    def test_double_install_updates_in_place(self) -> None:
        listing = _fake_inline_listing()
        first = _run(installer_mod.install(listing))
        second = _run(installer_mod.install(listing))
        self.assertEqual(first["install_id"], second["install_id"])
        self.assertTrue(second["summary"]["reinstall"])

    def test_uninstall_removes_directory(self) -> None:
        listing = _fake_inline_listing()
        out = _run(installer_mod.install(listing))
        p = Path(out["installed_path"])
        self.assertTrue(p.exists())
        rm = _run(installer_mod.uninstall(listing.id))
        self.assertTrue(rm["ok"])
        self.assertFalse(p.exists())

    def test_uninstall_missing_returns_error(self) -> None:
        rm = _run(installer_mod.uninstall("mlst_nope"))
        self.assertFalse(rm["ok"])
        self.assertEqual(rm["error"], "not_installed")


class ListingTests(_IsolatedInstallerCase):
    def test_list_installed_filters_by_kind(self) -> None:
        a = _fake_inline_listing()
        b = Listing.from_dict(
            {
                "id": "mlst_test_skill",
                "kind": "skill",
                "name": "Skill",
                "slug": "skill",
                "install_payload": {"format": "skill_module", "module": "x"},
            }
        )
        _run(installer_mod.install(a))
        _run(installer_mod.install(b))
        skills_only = _run(installer_mod.list_installed(kind="skill"))
        self.assertEqual(len(skills_only), 1)
        self.assertEqual(skills_only[0].listing_id, "mlst_test_skill")

    def test_is_installed_true_after_install(self) -> None:
        listing = _fake_inline_listing()
        self.assertFalse(_run(installer_mod.is_installed(listing.id)))
        _run(installer_mod.install(listing))
        self.assertTrue(_run(installer_mod.is_installed(listing.id)))


class InstallByIdTests(_IsolatedInstallerCase):
    def test_resolves_via_registry(self) -> None:
        out = _run(installer_mod.install_by_id("mlst_seed_dao_pack"))
        self.assertTrue(out["ok"])
        self.assertEqual(out["listing_id"], "mlst_seed_dao_pack")

    def test_missing_listing_returns_error(self) -> None:
        out = _run(installer_mod.install_by_id("mlst_does_not_exist"))
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "listing_not_found")


if __name__ == "__main__":
    unittest.main()
