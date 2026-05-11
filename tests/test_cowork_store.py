"""CRUD + handoff tests for the cowork SQLite store (Wave 129).

Stdlib unittest only. Each test isolates its own DB via tempfile so
the operator's ``~/.tars/cowork.sqlite`` is never touched.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
import unittest

from backend.core.cowork import (
    CoworkStore,
    MemberRole,
    SessionStatus,
    accept_handoff,
    create_handoff,
    reset_store,
)
from backend.core.cowork.handoff import HandoffError
from backend.core.cowork.store import get_store


def _run(coro):
    return asyncio.run(coro)


class _IsolatedStoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".sqlite", delete=False
        )
        self._tmp.close()
        os.environ["TARS_COWORK_DB_PATH"] = self._tmp.name
        os.environ.pop("TARS_COWORK_STORE", None)
        reset_store()
        self.store = CoworkStore(self._tmp.name)
        # Re-bind the module singleton to point at the same temp DB so
        # handoff helpers (which call get_store()) see our isolation.
        async def _bind() -> None:
            import backend.core.cowork.store as st
            st._store_singleton = self.store  # type: ignore[attr-defined]
        _run(_bind())

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
        os.environ.pop("TARS_COWORK_DB_PATH", None)
        reset_store()


# ---------- sessions --------------------------------------------------------


class TestSessionCRUD(_IsolatedStoreCase):
    def test_create_session_persists_and_slugifies(self) -> None:
        s = _run(
            self.store.create_session(
                name="Weekly review",
                owner_user_id="u_alice",
            )
        )
        self.assertEqual(s.status, SessionStatus.LIVE)
        self.assertTrue(s.slug.startswith("weekly-review-"))
        self.assertTrue(s.is_active)

        loaded = _run(self.store.get_session(s.id))
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.name, "Weekly review")
        self.assertEqual(loaded.owner_user_id, "u_alice")

    def test_get_session_by_slug_matches(self) -> None:
        s = _run(
            self.store.create_session(
                name="Demo session", owner_user_id="u_alice"
            )
        )
        by_slug = _run(self.store.get_session_by_slug(s.slug))
        self.assertIsNotNone(by_slug)
        assert by_slug is not None
        self.assertEqual(by_slug.id, s.id)

    def test_list_filters_by_owner_and_status(self) -> None:
        a = _run(self.store.create_session(name="A", owner_user_id="u_alice"))
        _b = _run(self.store.create_session(name="B", owner_user_id="u_bob"))
        c = _run(self.store.create_session(name="C", owner_user_id="u_alice"))
        # End one to test active_only.
        _run(self.store.end_session(c.id))

        all_alice = _run(self.store.list_sessions(owner_user_id="u_alice"))
        self.assertEqual(len(all_alice), 2)
        active_alice = _run(
            self.store.list_sessions(owner_user_id="u_alice", active_only=True)
        )
        self.assertEqual(len(active_alice), 1)
        self.assertEqual(active_alice[0].id, a.id)

    def test_end_session_idempotent(self) -> None:
        s = _run(self.store.create_session(name="X", owner_user_id="u"))
        ok1 = _run(self.store.end_session(s.id))
        ok2 = _run(self.store.end_session(s.id))
        self.assertTrue(ok1)
        self.assertFalse(ok2)  # second end is a no-op
        loaded = _run(self.store.get_session(s.id))
        assert loaded is not None
        self.assertEqual(loaded.status, SessionStatus.ENDED)


# ---------- members ---------------------------------------------------------


class TestMembers(_IsolatedStoreCase):
    def test_add_member_assigns_color_per_seat(self) -> None:
        s = _run(self.store.create_session(name="X", owner_user_id="u_a"))
        m1 = _run(
            self.store.add_member(
                session_id=s.id,
                display_name="Alice",
                user_id="u_a",
                role=MemberRole.OWNER,
            )
        )
        m2 = _run(
            self.store.add_member(
                session_id=s.id, display_name="Bob", user_id="u_b", role="editor"
            )
        )
        m3 = _run(
            self.store.add_member(
                session_id=s.id,
                display_name="Carol",
                role="viewer",
            )
        )
        # First three palette entries are indigo / violet / cyan — assert
        # they're distinct rather than hardcoding hex (palette may shift).
        self.assertEqual(len({m1.color, m2.color, m3.color}), 3)
        self.assertEqual(m1.role, MemberRole.OWNER)
        self.assertEqual(m2.role, MemberRole.EDITOR)
        self.assertEqual(m3.role, MemberRole.VIEWER)

    def test_token_unique_and_lookup_works(self) -> None:
        s = _run(self.store.create_session(name="X", owner_user_id="u"))
        m = _run(
            self.store.add_member(
                session_id=s.id, display_name="Alice", user_id="u_a"
            )
        )
        loaded = _run(self.store.get_member_by_token(m.token))
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.id, m.id)

    def test_remove_member_drops_cursors(self) -> None:
        s = _run(self.store.create_session(name="X", owner_user_id="u"))
        m = _run(
            self.store.add_member(session_id=s.id, display_name="A")
        )
        _run(
            self.store.upsert_cursor(
                session_id=s.id, member_id=m.id, path="a.md", line=1, col=0
            )
        )
        cursors = _run(self.store.list_cursors(session_id=s.id))
        self.assertEqual(len(cursors), 1)

        ok = _run(self.store.remove_member(m.id))
        self.assertTrue(ok)
        cursors = _run(self.store.list_cursors(session_id=s.id))
        self.assertEqual(len(cursors), 0)


# ---------- cursors ---------------------------------------------------------


class TestCursors(_IsolatedStoreCase):
    def test_upsert_preserves_uniqueness_per_path(self) -> None:
        s = _run(self.store.create_session(name="X", owner_user_id="u"))
        m = _run(self.store.add_member(session_id=s.id, display_name="A"))
        _run(
            self.store.upsert_cursor(
                session_id=s.id, member_id=m.id, path="a.md", line=1, col=0
            )
        )
        _run(
            self.store.upsert_cursor(
                session_id=s.id, member_id=m.id, path="a.md", line=12, col=5
            )
        )
        cursors = _run(self.store.list_cursors(session_id=s.id, path="a.md"))
        self.assertEqual(len(cursors), 1)
        self.assertEqual(cursors[0].line, 12)
        self.assertEqual(cursors[0].col, 5)

    def test_upsert_stores_distinct_paths_separately(self) -> None:
        s = _run(self.store.create_session(name="X", owner_user_id="u"))
        m = _run(self.store.add_member(session_id=s.id, display_name="A"))
        _run(
            self.store.upsert_cursor(
                session_id=s.id, member_id=m.id, path="a.md", line=1, col=0
            )
        )
        _run(
            self.store.upsert_cursor(
                session_id=s.id, member_id=m.id, path="b.md", line=2, col=3
            )
        )
        all_cursors = _run(self.store.list_cursors(session_id=s.id))
        self.assertEqual(len(all_cursors), 2)

    def test_negative_coords_clamp_to_zero(self) -> None:
        s = _run(self.store.create_session(name="X", owner_user_id="u"))
        m = _run(self.store.add_member(session_id=s.id, display_name="A"))
        c = _run(
            self.store.upsert_cursor(
                session_id=s.id, member_id=m.id, path="x", line=-5, col=-2
            )
        )
        self.assertEqual(c.line, 0)
        self.assertEqual(c.col, 0)


# ---------- handoffs --------------------------------------------------------


class TestHandoff(_IsolatedStoreCase):
    def test_create_and_accept_transfers_ownership(self) -> None:
        s = _run(self.store.create_session(name="X", owner_user_id="u_alice"))
        h = _run(
            create_handoff(
                session_id=s.id,
                from_user_id="u_alice",
                to_email="bob@example.com",
            )
        )
        self.assertTrue(h.is_pending)
        self.assertFalse(h.is_expired)

        accepted = _run(
            accept_handoff(token=h.token, accepted_by_user_id="u_bob")
        )
        self.assertEqual(accepted.accepted_by_user_id, "u_bob")
        self.assertIsNotNone(accepted.accepted_at)

        reloaded = _run(self.store.get_session(s.id))
        assert reloaded is not None
        self.assertEqual(reloaded.owner_user_id, "u_bob")

    def test_double_accept_loses_race(self) -> None:
        s = _run(self.store.create_session(name="X", owner_user_id="u_alice"))
        h = _run(
            create_handoff(session_id=s.id, from_user_id="u_alice")
        )
        _run(accept_handoff(token=h.token, accepted_by_user_id="u_bob"))
        with self.assertRaises(HandoffError):
            _run(accept_handoff(token=h.token, accepted_by_user_id="u_carol"))

    def test_create_handoff_rejects_non_owner(self) -> None:
        s = _run(self.store.create_session(name="X", owner_user_id="u_alice"))
        with self.assertRaises(HandoffError):
            _run(create_handoff(session_id=s.id, from_user_id="u_intruder"))

    def test_create_handoff_rejects_ended_session(self) -> None:
        s = _run(self.store.create_session(name="X", owner_user_id="u_alice"))
        _run(self.store.end_session(s.id))
        with self.assertRaises(HandoffError):
            _run(create_handoff(session_id=s.id, from_user_id="u_alice"))

    def test_expired_handoff_cannot_be_accepted(self) -> None:
        s = _run(self.store.create_session(name="X", owner_user_id="u_alice"))
        h = _run(
            create_handoff(session_id=s.id, from_user_id="u_alice", ttl_seconds=1)
        )
        # Force expiry without sleeping a full second by stomping the
        # row's expires_at directly. We use the same conn helper as the
        # store to keep this test self-contained.
        conn = self.store._connect()
        try:
            conn.execute(
                "UPDATE handoffs SET expires_at=? WHERE id=?",
                (time.time() - 5, h.id),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(HandoffError):
            _run(accept_handoff(token=h.token, accepted_by_user_id="u_bob"))

    def test_unknown_token_raises(self) -> None:
        with self.assertRaises(HandoffError):
            _run(accept_handoff(token="bogus", accepted_by_user_id="u_x"))


if __name__ == "__main__":
    unittest.main()
