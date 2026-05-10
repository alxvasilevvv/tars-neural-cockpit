"""Webhook-event → cohort-action translation + phase inference tests
for Wave 94.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest

from backend.core.cohort import (
    AttendeeAction,
    CohortStore,
    compute_active_now,
    infer_phase_advance,
    record_from_webhook_event,
    reset_store,
)


def _run(coro):
    return asyncio.run(coro)


class _IsolatedStoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self._tmp.close()
        os.environ["TARS_COHORT_DB_PATH"] = self._tmp.name
        os.environ.pop("TARS_COHORT_STORE", None)
        reset_store()
        self.store = CohortStore(self._tmp.name)
        self.cohort = _run(self.store.create_cohort(name="C", slug="c"))

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


class TestRecordFromWebhookEvent(_IsolatedStoreCase):
    def test_match_by_email_records_action(self) -> None:
        att = _run(
            self.store.add_attendee(
                cohort_id=self.cohort.id,
                display_name="Alice",
                email="alice@x.com",
            )
        )
        event = {
            "id": "evt_123",
            "type": "playbook.started",
            "occurred_at": 1700000000.0,
            "data": {"email": "ALICE@x.com", "playbook_id": "pb_1"},
        }
        result = _run(record_from_webhook_event(self.cohort.id, event, store=self.store))
        self.assertTrue(result["matched"])
        self.assertEqual(result["attendee_id"], att.id)
        self.assertEqual(result["action_type"], "playbook_start")
        timeline = _run(self.store.attendee_timeline(att.id, limit=5))
        self.assertEqual(timeline[0].type, "playbook_start")
        self.assertEqual(timeline[0].payload["source_event_id"], "evt_123")

    def test_match_by_token(self) -> None:
        att = _run(
            self.store.add_attendee(cohort_id=self.cohort.id, display_name="Bob")
        )
        event = {
            "id": "evt_42",
            "type": "playbook.finished",
            "data": {"attendee_token": att.token, "ok": True},
        }
        result = _run(record_from_webhook_event(self.cohort.id, event, store=self.store))
        self.assertTrue(result["matched"])
        self.assertEqual(result["action_type"], "playbook_finish")

    def test_no_attendee_returns_unmatched(self) -> None:
        event = {
            "id": "evt_x",
            "type": "playbook.started",
            "data": {"email": "ghost@x.com"},
        }
        result = _run(record_from_webhook_event(self.cohort.id, event, store=self.store))
        self.assertTrue(result["ok"])
        self.assertFalse(result["matched"])
        self.assertEqual(result["reason"], "no_attendee")

    def test_unknown_event_type_falls_through(self) -> None:
        att = _run(
            self.store.add_attendee(
                cohort_id=self.cohort.id, display_name="A", email="a@x.com"
            )
        )
        event = {
            "id": "evt_q",
            "type": "custom.thing",
            "data": {"email": "a@x.com"},
        }
        result = _run(record_from_webhook_event(self.cohort.id, event, store=self.store))
        self.assertTrue(result["matched"])
        # Unknown types pass through verbatim.
        self.assertEqual(result["action_type"], "custom.thing")

    def test_token_outside_cohort_is_ignored(self) -> None:
        other = _run(self.store.create_cohort(name="Other", slug="other"))
        att_other = _run(
            self.store.add_attendee(cohort_id=other.id, display_name="X")
        )
        event = {
            "id": "evt_z",
            "type": "playbook.started",
            "data": {"attendee_token": att_other.token},
        }
        # We pass cohort.id (not other.id) — should not match.
        result = _run(record_from_webhook_event(self.cohort.id, event, store=self.store))
        self.assertFalse(result["matched"])


class TestInferPhaseAdvance(unittest.TestCase):
    def _action(self, type_: str, **payload) -> AttendeeAction:
        return AttendeeAction(
            id="act_x", attendee_id="att_y", type=type_, payload=dict(payload)
        )

    def test_intake_advances_to_design_after_playbook_start(self) -> None:
        suggestion = infer_phase_advance(
            "intake", [self._action("playbook_start")]
        )
        self.assertEqual(suggestion, "design")

    def test_design_advances_to_test_after_hil_gate(self) -> None:
        suggestion = infer_phase_advance("design", [self._action("hil_gate")])
        self.assertEqual(suggestion, "test")

    def test_no_advance_when_signals_below_current(self) -> None:
        suggestion = infer_phase_advance("test", [self._action("join")])
        self.assertIsNone(suggestion)

    def test_explicit_phase_advance_payload_wins(self) -> None:
        suggestion = infer_phase_advance(
            "intake", [self._action("phase_advance", to="design")]
        )
        # We always step exactly one phase forward — even an explicit
        # 'design' from intake is fine since that *is* one step.
        self.assertEqual(suggestion, "design")

    def test_step_only_one_phase(self) -> None:
        # Even if the strongest signal implies deploy, we step once.
        suggestion = infer_phase_advance(
            "intake", [self._action("phase_advance", to="deploy")]
        )
        self.assertEqual(suggestion, "design")

    def test_done_phase_is_terminal(self) -> None:
        suggestion = infer_phase_advance(
            "done", [self._action("phase_advance", to="deploy")]
        )
        self.assertIsNone(suggestion)

    def test_dict_actions_supported(self) -> None:
        suggestion = infer_phase_advance(
            "intake", [{"type": "playbook_start", "payload": {}}]
        )
        self.assertEqual(suggestion, "design")


class TestComputeActiveNow(_IsolatedStoreCase):
    def test_active_now_counts_only_recent(self) -> None:
        a = _run(
            self.store.add_attendee(
                cohort_id=self.cohort.id, display_name="A", email="a@x.com"
            )
        )
        b = _run(
            self.store.add_attendee(
                cohort_id=self.cohort.id, display_name="B", email="b@x.com"
            )
        )
        # A has a recent action, B does not (uses default joined_at).
        _run(self.store.record_action(attendee_id=a.id, action_type="join"))
        # Push B way into the past
        _run(
            self.store.patch_attendee(
                b.id, {"last_activity_at": 1.0}
            )
        )
        count = _run(
            compute_active_now(self.cohort.id, window_s=120, store=self.store)
        )
        self.assertEqual(count, 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
