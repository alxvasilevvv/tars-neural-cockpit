"""SQLite store CRUD + run history + restart-safety tests for the
scheduler module (Wave 97). Stdlib unittest only.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
import unittest

from backend.core.scheduler import SchedulerStore, reset_store


def _run(coro):
    return asyncio.run(coro)


class _IsolatedStoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".sqlite", delete=False
        )
        self._tmp.close()
        os.environ["TARS_SCHEDULER_DB_PATH"] = self._tmp.name
        os.environ.pop("TARS_SCHEDULER_STORE", None)
        reset_store()
        self.store = SchedulerStore(self._tmp.name)

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
        os.environ.pop("TARS_SCHEDULER_DB_PATH", None)
        reset_store()


class TestScheduleCRUD(_IsolatedStoreCase):
    def test_create_persists_and_computes_next_run(self) -> None:
        sched = _run(
            self.store.create_schedule(
                playbook_id="pb-1",
                cron_expression="*/15 * * * *",
                timezone="UTC",
                args={"k": "v"},
            )
        )
        self.assertTrue(sched.id.startswith("sched_"))
        self.assertEqual(sched.playbook_id, "pb-1")
        self.assertEqual(sched.cron_expression, "*/15 * * * *")
        self.assertTrue(sched.enabled)
        self.assertIsNotNone(sched.next_run_at)
        self.assertGreater(sched.next_run_at or 0, time.time())
        self.assertEqual(sched.args, {"k": "v"})

    def test_create_rejects_bad_cron(self) -> None:
        with self.assertRaises(ValueError):
            _run(
                self.store.create_schedule(
                    playbook_id="pb-1",
                    cron_expression="bogus * * * *",
                )
            )

    def test_create_requires_playbook_id(self) -> None:
        with self.assertRaises(ValueError):
            _run(
                self.store.create_schedule(
                    playbook_id="",
                    cron_expression="* * * * *",
                )
            )

    def test_get_returns_none_for_missing(self) -> None:
        out = _run(self.store.get_schedule("sched_nope"))
        self.assertIsNone(out)

    def test_list_filters_by_playbook(self) -> None:
        a = _run(
            self.store.create_schedule(
                playbook_id="pb-A", cron_expression="@daily"
            )
        )
        b = _run(
            self.store.create_schedule(
                playbook_id="pb-B", cron_expression="@hourly"
            )
        )
        a_only = _run(self.store.list_schedules(playbook_id="pb-A"))
        self.assertEqual([s.id for s in a_only], [a.id])
        all_ = _run(self.store.list_schedules())
        self.assertEqual({s.id for s in all_}, {a.id, b.id})

    def test_update_disables_and_changes_cron(self) -> None:
        sched = _run(
            self.store.create_schedule(
                playbook_id="pb-1", cron_expression="@daily"
            )
        )
        first_next = sched.next_run_at
        updated = _run(
            self.store.update_schedule(
                sched.id, {"cron_expression": "*/5 * * * *", "enabled": False}
            )
        )
        assert updated is not None
        self.assertEqual(updated.cron_expression, "*/5 * * * *")
        self.assertFalse(updated.enabled)
        self.assertNotEqual(updated.next_run_at, first_next)

    def test_delete_returns_false_for_missing(self) -> None:
        deleted = _run(self.store.delete_schedule("sched_nope"))
        self.assertFalse(deleted)

    def test_delete_cascades_history(self) -> None:
        sched = _run(
            self.store.create_schedule(
                playbook_id="pb-1", cron_expression="@daily"
            )
        )
        _run(
            self.store.record_run(
                schedule_id=sched.id,
                started_at=time.time(),
                finished_at=time.time(),
                status="ok",
            )
        )
        deleted = _run(self.store.delete_schedule(sched.id))
        self.assertTrue(deleted)
        # History gone too.
        runs = _run(self.store.history(sched.id))
        self.assertEqual(runs, [])


class TestRunHistory(_IsolatedStoreCase):
    def test_record_and_query_history(self) -> None:
        sched = _run(
            self.store.create_schedule(
                playbook_id="pb-1", cron_expression="@hourly"
            )
        )
        for i in range(3):
            _run(
                self.store.record_run(
                    schedule_id=sched.id,
                    started_at=time.time() - (3 - i) * 10,
                    finished_at=time.time() - (3 - i) * 10 + 1.0,
                    status="ok" if i < 2 else "failed",
                    output_summary=f"run {i}",
                )
            )
        runs = _run(self.store.history(sched.id, limit=10))
        self.assertEqual(len(runs), 3)
        # Most-recent first.
        self.assertEqual(runs[0].status, "failed")
        # Duration computed.
        self.assertIsNotNone(runs[0].to_dict()["duration_ms"])

    def test_history_limit_clamps(self) -> None:
        sched = _run(
            self.store.create_schedule(
                playbook_id="pb-1", cron_expression="@hourly"
            )
        )
        for _ in range(5):
            _run(
                self.store.record_run(
                    schedule_id=sched.id,
                    started_at=time.time(),
                    status="ok",
                )
            )
        runs = _run(self.store.history(sched.id, limit=2))
        self.assertEqual(len(runs), 2)


class TestRecoverState(_IsolatedStoreCase):
    def test_recover_recomputes_next_run(self) -> None:
        sched = _run(
            self.store.create_schedule(
                playbook_id="pb-1", cron_expression="*/15 * * * *"
            )
        )
        # Pretend the next_run_at cache has been wiped.
        _run(self.store.set_next_run(sched.id, None))
        before = _run(self.store.get_schedule(sched.id))
        assert before is not None
        self.assertIsNone(before.next_run_at)
        out = _run(self.store.recover_state())
        self.assertEqual(out["recovered"], 1)
        after = _run(self.store.get_schedule(sched.id))
        assert after is not None
        self.assertIsNotNone(after.next_run_at)


class TestPersistenceAcrossReconnect(_IsolatedStoreCase):
    def test_data_survives_new_store_instance(self) -> None:
        sched = _run(
            self.store.create_schedule(
                playbook_id="pb-keep", cron_expression="@daily"
            )
        )
        # Discard the current handle and open a fresh one against the
        # same file.
        fresh = SchedulerStore(self._tmp.name)
        loaded = _run(fresh.get_schedule(sched.id))
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.cron_expression, "@daily")


class TestDueNow(_IsolatedStoreCase):
    def test_due_now_returns_overdue_only(self) -> None:
        # Build two schedules, then nudge one of them backwards in
        # time so it counts as due.
        s1 = _run(
            self.store.create_schedule(
                playbook_id="pb-due", cron_expression="@hourly"
            )
        )
        s2 = _run(
            self.store.create_schedule(
                playbook_id="pb-future", cron_expression="@hourly"
            )
        )
        _run(self.store.set_next_run(s1.id, time.time() - 5))
        due = _run(self.store.due_now())
        ids = {s.id for s in due}
        self.assertIn(s1.id, ids)
        self.assertNotIn(s2.id, ids)


if __name__ == "__main__":
    unittest.main()
