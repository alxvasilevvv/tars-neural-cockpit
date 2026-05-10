"""CRUD + invite tests for the org onboarding SQLite store (Wave 99).

Stdlib unittest only. Each test isolates its own DB via tempfile so
the operator's ``~/.tars/org.sqlite`` is never touched.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest

from backend.core.org import (
    INVITE_ROLES,
    ORG_TYPES,
    OrgStore,
    reset_store,
)


def _run(coro):
    return asyncio.run(coro)


class _IsolatedStoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".sqlite", delete=False
        )
        self._tmp.close()
        os.environ["TARS_ORG_DB_PATH"] = self._tmp.name
        os.environ.pop("TARS_ORG_STORE", None)
        reset_store()
        self.store = OrgStore(self._tmp.name)

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
        os.environ.pop("TARS_ORG_DB_PATH", None)
        reset_store()


class TestOrgCRUD(_IsolatedStoreCase):
    def test_upsert_creates_then_patches(self) -> None:
        org = _run(
            self.store.upsert_org(
                name="Acme Capital",
                type="vc fund",  # alias → vc_fund via normalize
                size="20-50",
                timezone="America/New_York",
                primary_use_case="LP reporting",
                metadata={"step": 1},
            )
        )
        self.assertTrue(org.id.startswith("org_"))
        self.assertEqual(org.name, "Acme Capital")
        self.assertEqual(org.type, "vc_fund")
        self.assertEqual(org.timezone, "America/New_York")
        self.assertEqual(org.metadata["step"], 1)

        # Re-upsert: same row patched (single-tenant), metadata merged.
        again = _run(
            self.store.upsert_org(
                name="Acme Capital II",
                type="hedge_fund",
                metadata={"step": 2, "connectors": ["slack"]},
            )
        )
        self.assertEqual(again.id, org.id)  # same row
        self.assertEqual(again.name, "Acme Capital II")
        self.assertEqual(again.type, "hedge_fund")
        self.assertEqual(again.metadata["step"], 2)
        self.assertEqual(again.metadata["connectors"], ["slack"])

    def test_upsert_requires_name(self) -> None:
        with self.assertRaises(ValueError):
            _run(self.store.upsert_org(name="   "))

    def test_get_org_returns_none_when_empty(self) -> None:
        self.assertIsNone(_run(self.store.get_org()))

    def test_patch_metadata_merges(self) -> None:
        org = _run(
            self.store.upsert_org(name="Acme", metadata={"a": 1, "b": 2})
        )
        patched = _run(self.store.patch_metadata({"b": 99, "c": 3}))
        assert patched is not None
        self.assertEqual(patched.id, org.id)
        self.assertEqual(patched.metadata, {"a": 1, "b": 99, "c": 3})

    def test_delete_org_cascades_invites(self) -> None:
        org = _run(self.store.upsert_org(name="Acme"))
        _run(
            self.store.add_invites(
                org_id=org.id,
                items=[{"email": "a@x.com", "role": "admin"}],
            )
        )
        self.assertTrue(_run(self.store.delete_org()))
        self.assertIsNone(_run(self.store.get_org()))
        # Invite list now naturally empty (org gone — we no longer
        # have an org_id to query, but the row was deleted via cascade).
        self.assertEqual(_run(self.store.list_invites(org.id)), [])


class TestInvites(_IsolatedStoreCase):
    def setUp(self) -> None:
        super().setUp()
        self.org = _run(self.store.upsert_org(name="Acme", type="saas_company"))

    def test_add_invites_dedupes_and_normalizes(self) -> None:
        items = [
            {"email": "Alice@X.COM", "role": "admin"},
            {"email": "bob@x.com", "role": "weird-role"},  # → viewer
            {"email": "  ", "role": "admin"},  # skipped
            {"email": "no-at-symbol", "role": "admin"},  # skipped
        ]
        saved = _run(self.store.add_invites(org_id=self.org.id, items=items))
        self.assertEqual(len(saved), 2)
        emails = sorted(i.email for i in saved)
        self.assertEqual(emails, ["alice@x.com", "bob@x.com"])
        self.assertEqual({i.role for i in saved} & set(INVITE_ROLES), {i.role for i in saved})

    def test_add_invites_idempotent_on_email(self) -> None:
        _run(
            self.store.add_invites(
                org_id=self.org.id,
                items=[{"email": "a@x.com", "role": "admin"}],
            )
        )
        # Re-submit same email with a different role; should replace.
        _run(
            self.store.add_invites(
                org_id=self.org.id,
                items=[{"email": "a@x.com", "role": "analyst"}],
            )
        )
        listing = _run(self.store.list_invites(self.org.id))
        self.assertEqual(len(listing), 1)
        self.assertEqual(listing[0].role, "analyst")

    def test_list_invites_descending(self) -> None:
        _run(
            self.store.add_invites(
                org_id=self.org.id,
                items=[
                    {"email": "first@x.com", "role": "admin"},
                    {"email": "second@x.com", "role": "viewer"},
                ],
            )
        )
        listing = _run(self.store.list_invites(self.org.id))
        self.assertEqual(len(listing), 2)
        self.assertGreaterEqual(listing[0].invited_at, listing[1].invited_at)
        for inv in listing:
            self.assertEqual(inv.status, "pending")

    def test_delete_invite(self) -> None:
        saved = _run(
            self.store.add_invites(
                org_id=self.org.id,
                items=[{"email": "a@x.com", "role": "viewer"}],
            )
        )
        self.assertEqual(len(saved), 1)
        ok = _run(self.store.delete_invite(saved[0].id))
        self.assertTrue(ok)
        self.assertEqual(_run(self.store.list_invites(self.org.id)), [])
        # Second delete is a no-op.
        again = _run(self.store.delete_invite(saved[0].id))
        self.assertFalse(again)


class TestConstants(unittest.TestCase):
    def test_org_types_exposed(self) -> None:
        self.assertIn("vc_fund", ORG_TYPES)
        self.assertIn("hedge_fund", ORG_TYPES)
        self.assertIn("family_office", ORG_TYPES)
        self.assertIn("saas_company", ORG_TYPES)
        self.assertIn("dao", ORG_TYPES)
        self.assertIn("research_lab", ORG_TYPES)
        self.assertIn("other", ORG_TYPES)

    def test_invite_roles_exposed(self) -> None:
        self.assertEqual(set(INVITE_ROLES), {"admin", "designer", "analyst", "viewer"})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
