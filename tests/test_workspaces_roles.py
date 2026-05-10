"""Permission-matrix tests for the Workspaces RBAC layer (Wave 110).

Stdlib unittest only. Pure / no I/O — covers ``can()`` predicate
correctness, ``roles_with()`` enumeration, the matrix totals, and a
few defensive cases (string coercion, unknown values).
"""

from __future__ import annotations

import unittest

from backend.core.workspaces.roles import (
    MATRIX,
    Permission,
    Role,
    can,
    matrix_to_dict,
    roles_with,
)


class TestMatrixShape(unittest.TestCase):
    def test_every_role_has_an_entry(self) -> None:
        for role in Role:
            self.assertIn(role, MATRIX)

    def test_role_count(self) -> None:
        self.assertEqual(len(list(Role)), 5)

    def test_permission_count(self) -> None:
        self.assertEqual(len(list(Permission)), 13)

    def test_owner_has_every_permission(self) -> None:
        self.assertEqual(MATRIX[Role.OWNER], frozenset(Permission))

    def test_admin_lacks_only_workspace_delete(self) -> None:
        diff = frozenset(Permission) - MATRIX[Role.ADMIN]
        self.assertEqual(diff, {Permission.WORKSPACE_DELETE})


class TestCanPredicate(unittest.TestCase):
    def test_owner_can_delete_workspace(self) -> None:
        self.assertTrue(can(Role.OWNER, Permission.WORKSPACE_DELETE))

    def test_admin_cannot_delete_workspace(self) -> None:
        self.assertFalse(can(Role.ADMIN, Permission.WORKSPACE_DELETE))

    def test_viewer_can_only_view_receipts(self) -> None:
        self.assertTrue(can(Role.VIEWER, Permission.RECEIPTS_VIEW))
        self.assertFalse(can(Role.VIEWER, Permission.RECEIPTS_EXPORT))
        self.assertFalse(can(Role.VIEWER, Permission.PLAYBOOKS_RUN))

    def test_designer_can_create_playbooks_but_not_invite_members(self) -> None:
        self.assertTrue(can(Role.DESIGNER, Permission.PLAYBOOKS_CREATE))
        self.assertFalse(can(Role.DESIGNER, Permission.MEMBERS_INVITE))

    def test_analyst_can_run_playbooks_but_not_send_outreach(self) -> None:
        self.assertTrue(can(Role.ANALYST, Permission.PLAYBOOKS_RUN))
        self.assertFalse(can(Role.ANALYST, Permission.OUTREACH_SEND))

    def test_can_accepts_string_role(self) -> None:
        self.assertTrue(can("owner", "workspace.delete"))
        self.assertFalse(can("viewer", "wallet.sign"))

    def test_can_handles_unknown_role(self) -> None:
        self.assertFalse(can("ceo", Permission.WORKSPACE_DELETE))

    def test_can_handles_unknown_permission(self) -> None:
        self.assertFalse(can(Role.OWNER, "workspace.nuke"))


class TestRolesWith(unittest.TestCase):
    def test_workspace_delete_only_owner(self) -> None:
        rs = roles_with(Permission.WORKSPACE_DELETE)
        self.assertEqual(rs, [Role.OWNER])

    def test_members_invite_owner_and_admin(self) -> None:
        rs = roles_with(Permission.MEMBERS_INVITE)
        self.assertEqual(set(rs), {Role.OWNER, Role.ADMIN})

    def test_receipts_view_every_role(self) -> None:
        rs = roles_with(Permission.RECEIPTS_VIEW)
        self.assertEqual(set(rs), set(Role))

    def test_playbooks_run_owner_admin_designer_analyst(self) -> None:
        rs = roles_with(Permission.PLAYBOOKS_RUN)
        self.assertEqual(
            set(rs),
            {Role.OWNER, Role.ADMIN, Role.DESIGNER, Role.ANALYST},
        )

    def test_compliance_export_owner_admin_only(self) -> None:
        rs = roles_with(Permission.COMPLIANCE_EXPORT)
        self.assertEqual(set(rs), {Role.OWNER, Role.ADMIN})

    def test_unknown_permission_returns_empty(self) -> None:
        self.assertEqual(roles_with("workspace.nuke"), [])


class TestMatrixToDict(unittest.TestCase):
    def test_serialised_matrix_keys(self) -> None:
        d = matrix_to_dict()
        self.assertEqual(set(d.keys()), {r.value for r in Role})

    def test_owner_serialised_includes_workspace_delete(self) -> None:
        d = matrix_to_dict()
        self.assertIn("workspace.delete", d["owner"])

    def test_viewer_serialised_is_minimal(self) -> None:
        d = matrix_to_dict()
        self.assertEqual(d["viewer"], ["receipts.view"])


if __name__ == "__main__":
    unittest.main()
