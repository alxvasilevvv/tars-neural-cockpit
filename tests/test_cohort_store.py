"""CRUD + status aggregation + timeline + flag tests for the cohort
SQLite store (Wave 94).

Stdlib unittest only. Each test isolates its own DB via tempfile so
the operator's ``~/.tars/cohort.sqlite`` is never touched.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
import unittest

from backend.core.cohort import (
    CohortStore,
    PHASES,
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
        os.environ["TARS_COHORT_DB_PATH"] = self._tmp.name
        os.environ.pop("TARS_COHORT_STORE", None)
        reset_store()
        self.store = CohortStore(self._tmp.name)

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
        os.environ.pop("TARS_COHORT_DB_PATH", None)
        reset_store()


class TestCohortCRUD(_IsolatedStoreCase):
    def test_create_cohort_persists(self) -> None:
        cohort = _run(
            self.store.create_cohort(
                name="Spring B2B",
                slug="spring-b2b",
                facilitator_user_id="user-1",
                max_attendees=20,
                metadata={"company": "Acme"},
            )
        )
        self.assertTrue(cohort.id.startswith("coh_"))
        self.assertEqual(cohort.name, "Spring B2B")
        self.assertEqual(cohort.slug, "spring-b2b")
        self.assertEqual(cohort.metadata["company"], "Acme")
        self.assertTrue(cohort.is_active)

        fetched = _run(self.store.get_cohort(cohort.id))
        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(fetched.id, cohort.id)
        self.assertEqual(fetched.metadata, {"company": "Acme"})

    def test_create_cohort_requires_name(self) -> None:
        with self.assertRaises(ValueError):
            _run(self.store.create_cohort(name="", slug="x"))

    def test_create_cohort_requires_slug(self) -> None:
        with self.assertRaises(ValueError):
            _run(self.store.create_cohort(name="N", slug=""))

    def test_get_cohort_by_slug(self) -> None:
        cohort = _run(self.store.create_cohort(name="A", slug="a-slug"))
        again = _run(self.store.get_cohort_by_slug("A-Slug"))
        assert again is not None
        self.assertEqual(again.id, cohort.id)

    def test_list_cohorts_filters_by_facilitator(self) -> None:
        _run(self.store.create_cohort(name="C1", slug="c1", facilitator_user_id="u1"))
        _run(self.store.create_cohort(name="C2", slug="c2", facilitator_user_id="u2"))
        u1_only = _run(self.store.list_cohorts(facilitator_user_id="u1"))
        self.assertEqual([c.slug for c in u1_only], ["c1"])

    def test_end_cohort_marks_ended(self) -> None:
        cohort = _run(self.store.create_cohort(name="X", slug="x"))
        ended = _run(self.store.end_cohort(cohort.id))
        assert ended is not None
        self.assertIsNotNone(ended.ended_at)
        self.assertFalse(ended.is_active)

    def test_delete_cohort_cascades(self) -> None:
        cohort = _run(self.store.create_cohort(name="X", slug="x"))
        att = _run(
            self.store.add_attendee(
                cohort_id=cohort.id, display_name="Alice", email="alice@x.com"
            )
        )
        _run(self.store.record_action(attendee_id=att.id, action_type="join"))
        ok = _run(self.store.delete_cohort(cohort.id))
        self.assertTrue(ok)
        self.assertIsNone(_run(self.store.get_cohort(cohort.id)))
        self.assertIsNone(_run(self.store.get_attendee(att.id)))


class TestAttendeeCRUD(_IsolatedStoreCase):
    def setUp(self) -> None:
        super().setUp()
        self.cohort = _run(self.store.create_cohort(name="C", slug="c"))

    def test_add_attendee_returns_token(self) -> None:
        att = _run(
            self.store.add_attendee(
                cohort_id=self.cohort.id,
                display_name="Alice",
                email="alice@x.com",
            )
        )
        self.assertTrue(att.id.startswith("att_"))
        self.assertGreater(len(att.token), 30)
        self.assertEqual(att.email, "alice@x.com")
        self.assertEqual(att.current_phase, "intake")

    def test_add_attendee_unknown_cohort(self) -> None:
        with self.assertRaises(ValueError):
            _run(
                self.store.add_attendee(
                    cohort_id="coh_missing", display_name="x"
                )
            )

    def test_get_attendee_by_token_roundtrips(self) -> None:
        att = _run(
            self.store.add_attendee(
                cohort_id=self.cohort.id, display_name="Bob"
            )
        )
        again = _run(self.store.get_attendee_by_token(att.token))
        assert again is not None
        self.assertEqual(again.id, att.id)

    def test_find_attendee_by_email_lowercases(self) -> None:
        att = _run(
            self.store.add_attendee(
                cohort_id=self.cohort.id,
                display_name="Carol",
                email="Carol@X.COM",
            )
        )
        match = _run(self.store.find_attendee_by_email("carol@x.com"))
        assert match is not None
        self.assertEqual(match.id, att.id)

    def test_list_attendees_filter_phase(self) -> None:
        a = _run(self.store.add_attendee(cohort_id=self.cohort.id, display_name="A"))
        b = _run(self.store.add_attendee(cohort_id=self.cohort.id, display_name="B"))
        _run(self.store.patch_attendee(b.id, {"current_phase": "deploy"}))
        intake = _run(self.store.list_attendees(self.cohort.id, filter="intake"))
        self.assertEqual([x.id for x in intake], [a.id])
        deploy = _run(self.store.list_attendees(self.cohort.id, filter="deploy"))
        self.assertEqual([x.id for x in deploy], [b.id])

    def test_list_attendees_filter_active_idle(self) -> None:
        a = _run(self.store.add_attendee(cohort_id=self.cohort.id, display_name="A"))
        b = _run(self.store.add_attendee(cohort_id=self.cohort.id, display_name="B"))
        # Push B's last_activity into the past beyond the active window.
        _run(self.store.patch_attendee(b.id, {"last_activity_at": time.time() - 10_000}))
        active = _run(
            self.store.list_attendees(self.cohort.id, filter="active", active_window_s=60)
        )
        idle = _run(
            self.store.list_attendees(self.cohort.id, filter="idle", active_window_s=60)
        )
        self.assertEqual([x.id for x in active], [a.id])
        self.assertEqual([x.id for x in idle], [b.id])

    def test_flag_and_unflag(self) -> None:
        att = _run(self.store.add_attendee(cohort_id=self.cohort.id, display_name="A"))
        flagged = _run(self.store.flag_attendee(att.id, "stuck on intake"))
        assert flagged is not None
        self.assertTrue(flagged.flagged)
        self.assertEqual(flagged.flag_reason, "stuck on intake")
        unflagged = _run(self.store.unflag_attendee(att.id))
        assert unflagged is not None
        self.assertFalse(unflagged.flagged)
        self.assertIsNone(unflagged.flag_reason)


class TestActionsAndStatus(_IsolatedStoreCase):
    def setUp(self) -> None:
        super().setUp()
        self.cohort = _run(self.store.create_cohort(name="C", slug="c"))

    def test_record_action_updates_counters(self) -> None:
        att = _run(self.store.add_attendee(cohort_id=self.cohort.id, display_name="A"))
        _run(self.store.record_action(attendee_id=att.id, action_type="playbook_start"))
        _run(self.store.record_action(attendee_id=att.id, action_type="playbook_finish"))
        _run(self.store.record_action(attendee_id=att.id, action_type="error"))
        refreshed = _run(self.store.get_attendee(att.id))
        assert refreshed is not None
        self.assertEqual(refreshed.playbook_runs, 1)
        self.assertEqual(refreshed.errors, 1)

    def test_phase_advance_action_updates_phase(self) -> None:
        att = _run(self.store.add_attendee(cohort_id=self.cohort.id, display_name="A"))
        _run(
            self.store.record_action(
                attendee_id=att.id,
                action_type="phase_advance",
                payload={"to": "design"},
            )
        )
        refreshed = _run(self.store.get_attendee(att.id))
        assert refreshed is not None
        self.assertEqual(refreshed.current_phase, "design")

    def test_record_action_unknown_attendee(self) -> None:
        with self.assertRaises(ValueError):
            _run(self.store.record_action(attendee_id="att_missing", action_type="x"))

    def test_attendee_timeline_descending(self) -> None:
        att = _run(self.store.add_attendee(cohort_id=self.cohort.id, display_name="A"))
        first = _run(self.store.record_action(attendee_id=att.id, action_type="join"))
        time.sleep(0.005)
        second = _run(
            self.store.record_action(attendee_id=att.id, action_type="playbook_start")
        )
        timeline = _run(self.store.attendee_timeline(att.id, limit=10))
        self.assertEqual([t.id for t in timeline], [second.id, first.id])

    def test_get_cohort_status_aggregates(self) -> None:
        a = _run(self.store.add_attendee(cohort_id=self.cohort.id, display_name="A"))
        b = _run(self.store.add_attendee(cohort_id=self.cohort.id, display_name="B"))
        c = _run(self.store.add_attendee(cohort_id=self.cohort.id, display_name="C"))
        _run(self.store.patch_attendee(b.id, {"current_phase": "design"}))
        _run(self.store.patch_attendee(c.id, {"current_phase": "deploy"}))
        _run(self.store.record_action(attendee_id=a.id, action_type="error"))
        _run(self.store.flag_attendee(b.id, "needs help"))
        # Push c into idle territory
        _run(self.store.patch_attendee(c.id, {"last_activity_at": time.time() - 9999}))
        status = _run(
            self.store.get_cohort_status(self.cohort.id, active_window_s=60)
        )
        self.assertTrue(status["ok"])
        self.assertEqual(status["total_attendees"], 3)
        self.assertEqual(status["by_phase"]["intake"], 1)
        self.assertEqual(status["by_phase"]["design"], 1)
        self.assertEqual(status["by_phase"]["deploy"], 1)
        self.assertEqual(status["errors"], 1)
        self.assertEqual(status["flagged"], 1)
        self.assertEqual(status["active_now"], 2)  # a + b are recent

    def test_get_cohort_status_missing_cohort(self) -> None:
        status = _run(self.store.get_cohort_status("coh_nope"))
        self.assertFalse(status["ok"])
        self.assertEqual(status["reason"], "not_found")

    def test_broadcast_creates_timeline_rows(self) -> None:
        a = _run(self.store.add_attendee(cohort_id=self.cohort.id, display_name="A"))
        b = _run(self.store.add_attendee(cohort_id=self.cohort.id, display_name="B"))
        result = _run(
            self.store.broadcast_message(
                self.cohort.id, message="lunch in 5", sender_user_id="u1"
            )
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 2)
        a_timeline = _run(self.store.attendee_timeline(a.id, limit=5))
        b_timeline = _run(self.store.attendee_timeline(b.id, limit=5))
        self.assertEqual(a_timeline[0].type, "broadcast")
        self.assertEqual(a_timeline[0].payload["message"], "lunch in 5")
        self.assertEqual(b_timeline[0].type, "broadcast")

    def test_broadcast_requires_message(self) -> None:
        with self.assertRaises(ValueError):
            _run(self.store.broadcast_message(self.cohort.id, message="   "))

    def test_recent_actions_for_cohort(self) -> None:
        a = _run(self.store.add_attendee(cohort_id=self.cohort.id, display_name="A"))
        _run(self.store.record_action(attendee_id=a.id, action_type="join"))
        _run(self.store.record_action(attendee_id=a.id, action_type="playbook_start"))
        actions = _run(self.store.recent_actions_for_cohort(self.cohort.id, limit=10))
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0].type, "playbook_start")


class TestPhasesConstant(unittest.TestCase):
    def test_phases_are_ordered(self) -> None:
        self.assertEqual(
            PHASES, ("intake", "design", "test", "deploy", "done")
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
