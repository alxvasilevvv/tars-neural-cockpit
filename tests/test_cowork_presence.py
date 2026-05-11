"""Presence + stream tests for the cowork module (Wave 129)."""

from __future__ import annotations

import asyncio
import time
import unittest

from backend.core.cowork import (
    PresenceTracker,
    publish,
    reset_tracker,
    subscribe,
    subscriber_count,
)
from backend.core.cowork.stream import reset_subscribers


def _run(coro):
    return asyncio.run(coro)


class TestPresenceTracker(unittest.TestCase):
    def setUp(self) -> None:
        reset_tracker()
        self.t = PresenceTracker()

    def test_heartbeat_records_and_returns_state(self) -> None:
        st = self.t.heartbeat("sess_1", "m_alice", focus_path="plan.md")
        self.assertEqual(st.member_id, "m_alice")
        self.assertEqual(st.focus_path, "plan.md")
        self.assertTrue(st.is_present())

    def test_who_is_present_excludes_stale(self) -> None:
        self.t.heartbeat("sess_1", "m_alice")
        self.t.heartbeat("sess_1", "m_bob")
        # Stomp Alice's last_seen far in the past.
        self.t._state["sess_1"]["m_alice"].last_seen_at = time.time() - 60
        present = self.t.who_is_present("sess_1")
        self.assertEqual(len(present), 1)
        self.assertEqual(present[0].member_id, "m_bob")

    def test_leave_removes_member(self) -> None:
        self.t.heartbeat("sess_1", "m_alice")
        self.t.leave("sess_1", "m_alice")
        self.assertEqual(self.t.who_is_present("sess_1"), [])

    def test_gc_drops_stale_records(self) -> None:
        self.t.heartbeat("sess_1", "m_alice")
        self.t.heartbeat("sess_2", "m_bob")
        self.t._state["sess_1"]["m_alice"].last_seen_at = time.time() - 600
        dropped = self.t.gc()
        self.assertEqual(dropped, 1)
        # Empty bucket should also be cleaned up.
        self.assertNotIn("sess_1", self.t._state)
        self.assertIn("sess_2", self.t._state)

    def test_member_state_returns_none_for_unknown(self) -> None:
        self.assertIsNone(self.t.member_state("nope", "nope"))


class TestStream(unittest.TestCase):
    def setUp(self) -> None:
        reset_subscribers()

    def test_publish_to_no_subscribers_returns_zero(self) -> None:
        n = _run(publish("sess_1", {"type": "agent.frame", "data": {}}))
        self.assertEqual(n, 0)

    def test_publish_fans_out_to_subscribers(self) -> None:
        async def scenario() -> int:
            received: list[dict] = []

            async def reader() -> None:
                async for ev in subscribe("sess_x"):
                    if ev["type"] == "heartbeat":
                        continue
                    received.append(ev)
                    if len(received) >= 2:
                        return

            task = asyncio.create_task(reader())
            # Give the reader a chance to register.
            await asyncio.sleep(0.05)
            n1 = await publish("sess_x", {"type": "agent.frame", "data": {"v": 1}})
            n2 = await publish("sess_x", {"type": "chat", "data": {"v": 2}})
            await asyncio.wait_for(task, timeout=2.0)
            self.assertEqual(n1, 1)
            self.assertEqual(n2, 1)
            self.assertEqual(len(received), 2)
            self.assertEqual(received[0]["data"]["v"], 1)
            self.assertEqual(received[1]["data"]["v"], 2)
            return 0

        _run(scenario())

    def test_publish_assigns_id_and_timestamp(self) -> None:
        async def scenario() -> None:
            received: list[dict] = []

            async def reader() -> None:
                async for ev in subscribe("sess_y"):
                    if ev["type"] == "heartbeat":
                        continue
                    received.append(ev)
                    return

            task = asyncio.create_task(reader())
            await asyncio.sleep(0.05)
            await publish("sess_y", {"type": "cursor", "data": {}})
            await asyncio.wait_for(task, timeout=2.0)
            self.assertIn("id", received[0])
            self.assertIn("occurred_at", received[0])
            self.assertTrue(received[0]["id"].startswith("ev_"))

        _run(scenario())

    def test_subscriber_count_tracks_lifecycle(self) -> None:
        async def scenario() -> None:
            self.assertEqual(subscriber_count("sess_z"), 0)

            async def reader() -> None:
                async for _ev in subscribe("sess_z"):
                    return  # exit after first event

            task = asyncio.create_task(reader())
            await asyncio.sleep(0.05)
            self.assertEqual(subscriber_count("sess_z"), 1)
            await publish("sess_z", {"type": "chat", "data": {}})
            await asyncio.wait_for(task, timeout=2.0)
            # After the generator returns, _unregister should fire.
            await asyncio.sleep(0.05)
            self.assertEqual(subscriber_count("sess_z"), 0)

        _run(scenario())

    def test_empty_session_id_publish_is_noop(self) -> None:
        n = _run(publish("", {"type": "agent.frame", "data": {}}))
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
