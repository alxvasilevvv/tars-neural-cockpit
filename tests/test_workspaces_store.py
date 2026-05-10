"""CRUD + membership + invite tests for the Workspaces SQLite store
(Wave 110).

Stdlib unittest only. Each test isolates its own DB via tempfile so
the operator's ``~/.tars/workspaces.sqlite`` is never touched.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
import unittest

from backend.core.workspaces import (
    Role,
    WorkspacesStore,
    reset_store,
)
from backend.core.workspaces.store import PERSONAL_ID


def _run(coro):
    return asyncio.run(coro)


class _IsolatedStoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self._tmp.close()
        os.environ["TARS_WORKSPACES_DB_PATH"] = self._tmp.name
        os.environ.pop("TARS_WORKSPACES_STORE", None)
        reset_store()
        self.store = WorkspacesStore(self._tmp.name)

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
        os.environ.pop("TARS_WORKSPACES_DB_PATH", None)
        reset_store()


class TestPersonalSeed(_IsolatedStoreCase):
    def test_personal_workspace_seeded_on_first_call(self) -> None:
        ws = _run(self.store.get_workspace(PERSONAL_ID))
        self.assertIsNotNone(ws)
        assert ws is not None
        self.assertEqual(ws.id, PERSONAL_ID)
        self.assertEqual(ws.slug, "personal")
        self.assertTrue(ws.is_active)

    def test_personal_workspace_has_owner_membership(self) -> None:
        # Force seed
        _run(self.store.list_workspaces())
        members = _run(self.store.list_members(PERSONAL_ID))
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].role, Role.OWNER.value)

    def test_personal_workspace_cannot_be_archived(self) -> None:
        with self.assertRaises(ValueError):
            _run(self.store.archive_workspace(PERSONAL_ID))


class TestWorkspaceCRUD(_IsolatedStoreCase):
    def test_create_workspace_persists(self) -> None:
        ws = _run(
            self.store.create_workspace(
                slug="acme-fund",
                name="Acme Fund",
                owner_user_id="user-1",
                plan="pro",
                settings={"region": "us"},
            )
        )
        self.assertTrue(ws.id.startswith("ws_"))
        self.assertEqual(ws.slug, "acme-fund")
        self.assertEqual(ws.plan, "pro")
        self.assertEqual(ws.settings.get("region"), "us")
        self.assertTrue(ws.is_active)

        fetched = _run(self.store.get_workspace(ws.id))
        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(fetched.id, ws.id)

    def test_get_workspace_by_slug(self) -> None:
        _run(
            self.store.create_workspace(
                slug="bravo", name="Bravo", owner_user_id="u"
            )
        )
        ws = _run(self.store.get_workspace("bravo"))
        self.assertIsNotNone(ws)

    def test_create_workspace_rejects_invalid_plan(self) -> None:
        with self.assertRaises(ValueError):
            _run(
                self.store.create_workspace(
                    slug="charlie",
                    name="Charlie",
                    owner_user_id="u",
                    plan="enterprise",
                )
            )

    def test_create_workspace_rejects_duplicate_slug(self) -> None:
        _run(self.store.create_workspace(slug="dup", name="A", owner_user_id="u"))
        with self.assertRaises(ValueError):
            _run(
                self.store.create_workspace(
                    slug="dup", name="B", owner_user_id="u2"
                )
            )

    def test_list_workspaces_filters_by_user(self) -> None:
        _run(
            self.store.create_workspace(slug="x1", name="X1", owner_user_id="alice")
        )
        _run(
            self.store.create_workspace(slug="x2", name="X2", owner_user_id="bob")
        )
        alice_only = _run(self.store.list_workspaces(user_id="alice"))
        slugs = {w.slug for w in alice_only}
        self.assertIn("x1", slugs)
        self.assertNotIn("x2", slugs)

    def test_archive_workspace(self) -> None:
        ws = _run(
            self.store.create_workspace(
                slug="arch", name="Arch", owner_user_id="u"
            )
        )
        ok = _run(self.store.archive_workspace(ws.id))
        self.assertTrue(ok)
        fetched = _run(self.store.get_workspace(ws.id))
        assert fetched is not None
        self.assertFalse(fetched.is_active)

    def test_update_workspace_changes_name_and_plan(self) -> None:
        ws = _run(
            self.store.create_workspace(
                slug="upd", name="Old", owner_user_id="u", plan="free"
            )
        )
        updated = _run(
            self.store.update_workspace(
                ws.id, name="New", plan="business", settings={"k": "v"}
            )
        )
        assert updated is not None
        self.assertEqual(updated.name, "New")
        self.assertEqual(updated.plan, "business")
        self.assertEqual(updated.settings.get("k"), "v")


class TestMembershipCRUD(_IsolatedStoreCase):
    def setUp(self) -> None:
        super().setUp()
        self.ws = _run(
            self.store.create_workspace(
                slug="team", name="Team", owner_user_id="owner-1"
            )
        )

    def test_add_member_active(self) -> None:
        m = _run(
            self.store.add_member(
                self.ws.id,
                "user-2",
                "u2@example.com",
                Role.ANALYST.value,
                invited_by="owner-1",
            )
        )
        self.assertEqual(m.user_id, "user-2")
        self.assertEqual(m.role, Role.ANALYST.value)
        self.assertEqual(m.status, "active")
        self.assertIsNotNone(m.joined_at)

    def test_add_member_rejects_duplicate(self) -> None:
        _run(
            self.store.add_member(
                self.ws.id,
                "user-2",
                "u2@example.com",
                Role.VIEWER.value,
                invited_by="owner-1",
            )
        )
        with self.assertRaises(ValueError):
            _run(
                self.store.add_member(
                    self.ws.id,
                    "user-2",
                    "u2@example.com",
                    Role.VIEWER.value,
                    invited_by="owner-1",
                )
            )

    def test_update_member_role(self) -> None:
        _run(
            self.store.add_member(
                self.ws.id,
                "user-2",
                "u2@example.com",
                Role.ANALYST.value,
            )
        )
        updated = _run(
            self.store.update_member_role(
                self.ws.id, "user-2", Role.DESIGNER.value
            )
        )
        assert updated is not None
        self.assertEqual(updated.role, Role.DESIGNER.value)

    def test_revoke_member_succeeds(self) -> None:
        _run(
            self.store.add_member(
                self.ws.id,
                "user-2",
                "u2@example.com",
                Role.VIEWER.value,
            )
        )
        ok = _run(self.store.revoke_member(self.ws.id, "user-2"))
        self.assertTrue(ok)
        members = _run(self.store.list_members(self.ws.id))
        u2 = [m for m in members if m.user_id == "user-2"][0]
        self.assertEqual(u2.status, "revoked")

    def test_revoke_owner_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _run(self.store.revoke_member(self.ws.id, "owner-1"))


class TestInviteFlow(_IsolatedStoreCase):
    def setUp(self) -> None:
        super().setUp()
        self.ws = _run(
            self.store.create_workspace(
                slug="invteam", name="InvTeam", owner_user_id="owner-1"
            )
        )

    def test_create_invite_returns_token(self) -> None:
        inv = _run(
            self.store.create_invite(
                self.ws.id,
                "new@example.com",
                Role.DESIGNER.value,
                invited_by="owner-1",
            )
        )
        self.assertEqual(inv.status, "pending")
        self.assertTrue(len(inv.token) > 20)
        self.assertEqual(inv.email, "new@example.com")

    def test_accept_invite_creates_membership(self) -> None:
        inv = _run(
            self.store.create_invite(
                self.ws.id,
                "joiner@example.com",
                Role.ANALYST.value,
                invited_by="owner-1",
            )
        )
        m = _run(self.store.accept_invite(inv.token, "user-joiner"))
        self.assertEqual(m.workspace_id, self.ws.id)
        self.assertEqual(m.user_id, "user-joiner")
        self.assertEqual(m.role, Role.ANALYST.value)
        self.assertEqual(m.status, "active")

    def test_accept_invite_rejects_unknown_token(self) -> None:
        with self.assertRaises(ValueError):
            _run(self.store.accept_invite("nonexistent", "user-x"))

    def test_revoke_invite(self) -> None:
        inv = _run(
            self.store.create_invite(
                self.ws.id,
                "rev@example.com",
                Role.VIEWER.value,
                invited_by="owner-1",
            )
        )
        ok = _run(self.store.revoke_invite(inv.id))
        self.assertTrue(ok)
        with self.assertRaises(ValueError):
            _run(self.store.accept_invite(inv.token, "user-z"))

    def test_list_pending_invites(self) -> None:
        _run(
            self.store.create_invite(
                self.ws.id,
                "p1@example.com",
                Role.VIEWER.value,
                invited_by="owner-1",
            )
        )
        _run(
            self.store.create_invite(
                self.ws.id,
                "p2@example.com",
                Role.ANALYST.value,
                invited_by="owner-1",
            )
        )
        items = _run(self.store.list_pending_invites(self.ws.id))
        self.assertEqual(len(items), 2)


if __name__ == "__main__":
    unittest.main()
