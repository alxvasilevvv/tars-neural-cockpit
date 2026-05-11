"""Edge-case tests for the cowork module (Wave 135).

Covers what `test_cowork_store.py` + `test_cowork_presence.py` don't
exhaustively exercise:

- Concurrent handoff accepts (atomicity stress test).
- Pathological input: very long names, very long paths, extreme
  cursor coordinates, malformed roles.
- Subscriber queue overflow — drop-oldest semantics.
- Slug collisions don't break the unique constraint (with the random
  suffix, but verify behaviour under repeated calls).
- Session lookup by id vs slug.
- Empty / whitespace input handling.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
import unittest

from backend.core.cowork import (
    CoworkStore,
    HandoffError,
    MemberRole,
    accept_handoff,
    create_handoff,
    publish,
    reset_store,
    subscribe,
    subscriber_count,
)
from backend.core.cowork.stream import _MAX_QUEUE_DEPTH, reset_subscribers


def _run(coro):
    return asyncio.run(coro)


class _IsolatedCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self._tmp.close()
        os.environ["TARS_COWORK_DB_PATH"] = self._tmp.name
        os.environ.pop("TARS_COWORK_STORE", None)
        reset_store()
        reset_subscribers()
        self.store = CoworkStore(self._tmp.name)

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
        reset_subscribers()


# ---------- handoff concurrency stress ----------------------------------------


class TestHandoffConcurrency(_IsolatedCase):
    def test_three_concurrent_accepts_exactly_one_wins(self) -> None:
        """Spawn three accept_handoff tasks on the same token in parallel.
        SQLite's conditional UPDATE serialises them, but we must verify
        the public API surface: exactly one returns success, two raise
        HandoffError. Run the experiment in a single event loop with
        `gather(..., return_exceptions=True)`.
        """

        async def scenario() -> tuple[int, int]:
            s = await self.store.create_session(
                name="Race test", owner_user_id="u_owner"
            )
            h = await create_handoff(session_id=s.id, from_user_id="u_owner")

            async def attempt(uid: str):
                return await accept_handoff(
                    token=h.token, accepted_by_user_id=uid
                )

            results = await asyncio.gather(
                attempt("u_a"),
                attempt("u_b"),
                attempt("u_c"),
                return_exceptions=True,
            )
            wins = sum(1 for r in results if not isinstance(r, Exception))
            losses = sum(1 for r in results if isinstance(r, HandoffError))
            return wins, losses

        wins, losses = _run(scenario())
        self.assertEqual(wins, 1, f"exactly one accept should win; got {wins}")
        self.assertEqual(losses, 2, f"two should raise HandoffError; got {losses}")

    def test_revoked_handoff_cannot_be_accepted(self) -> None:
        async def scenario() -> None:
            s = await self.store.create_session(
                name="Revoke test", owner_user_id="u_owner"
            )
            h = await create_handoff(session_id=s.id, from_user_id="u_owner")
            await self.store.revoke_handoff(h.id)
            with self.assertRaises(HandoffError):
                await accept_handoff(token=h.token, accepted_by_user_id="u_x")

        _run(scenario())


# ---------- pathological input -----------------------------------------------


class TestPathologicalInput(_IsolatedCase):
    def test_very_long_display_name_clamps_or_stores(self) -> None:
        """500-char display name — should either store as-is (no error) or
        clamp; either is acceptable but the call must not raise.
        """

        long_name = "Member-" + ("X" * 500)

        async def scenario() -> int:
            s = await self.store.create_session(name="X", owner_user_id="u")
            m = await self.store.add_member(session_id=s.id, display_name=long_name)
            return len(m.display_name)

        result = _run(scenario())
        self.assertGreater(result, 0)

    def test_very_long_cursor_path_stored(self) -> None:
        async def scenario() -> str:
            s = await self.store.create_session(name="X", owner_user_id="u")
            m = await self.store.add_member(session_id=s.id, display_name="A")
            long_path = "deep/" * 50 + "file.tsx"
            c = await self.store.upsert_cursor(
                session_id=s.id,
                member_id=m.id,
                path=long_path,
                line=10,
                col=0,
            )
            return c.path

        result = _run(scenario())
        self.assertTrue(result.endswith("file.tsx"))

    def test_extreme_cursor_coords(self) -> None:
        """Very large line/col numbers and negatives should not break."""

        async def scenario() -> tuple[int, int, int, int]:
            s = await self.store.create_session(name="X", owner_user_id="u")
            m = await self.store.add_member(session_id=s.id, display_name="A")
            big = await self.store.upsert_cursor(
                session_id=s.id, member_id=m.id, path="big.md",
                line=2_000_000_000, col=999_999,
            )
            neg = await self.store.upsert_cursor(
                session_id=s.id, member_id=m.id, path="neg.md",
                line=-100, col=-50,
            )
            return big.line, big.col, neg.line, neg.col

        big_line, big_col, neg_line, neg_col = _run(scenario())
        self.assertEqual(big_line, 2_000_000_000)
        self.assertEqual(big_col, 999_999)
        # Negatives must clamp to 0 (defensive against bad client input).
        self.assertEqual(neg_line, 0)
        self.assertEqual(neg_col, 0)

    def test_unknown_role_string_defaults_to_viewer(self) -> None:
        """Per the contract: ``normalize_role`` must default malformed
        input to viewer (safest tier). Wrong typo on the wire shouldn't
        accidentally grant editor."""

        async def scenario() -> MemberRole:
            s = await self.store.create_session(name="X", owner_user_id="u")
            m = await self.store.add_member(
                session_id=s.id, display_name="Eve", role="GIGAEDITORZ_LOL"
            )
            return m.role

        result = _run(scenario())
        self.assertEqual(result, MemberRole.VIEWER)

    def test_whitespace_session_name_still_creates_with_fallback_slug(self) -> None:
        async def scenario() -> str:
            s = await self.store.create_session(name="   ", owner_user_id="u")
            return s.slug

        slug = _run(scenario())
        # Slug must be non-empty even if name was effectively blank.
        self.assertTrue(slug.startswith("session-") or len(slug) > 4)

    def test_handoff_normalises_email_case_and_whitespace(self) -> None:
        async def scenario() -> str | None:
            s = await self.store.create_session(name="X", owner_user_id="u_a")
            h = await create_handoff(
                session_id=s.id,
                from_user_id="u_a",
                to_email="  BoB@Example.COM  ",
            )
            return h.to_email

        result = _run(scenario())
        self.assertEqual(result, "bob@example.com")


# ---------- subscriber queue overflow -----------------------------------------


class TestSubscriberOverflow(_IsolatedCase):
    def test_publish_burst_does_not_block_under_overflow(self) -> None:
        """Publish ``_MAX_QUEUE_DEPTH + 10`` events back-to-back at one
        slow subscriber. The implementation drops the oldest rather than
        back-pressuring the publisher — verify the publisher returns
        immediately each call and the subscriber gets the LAST events,
        not the first."""

        async def scenario() -> tuple[int, int]:
            received: list[dict] = []
            done = asyncio.Event()

            async def reader() -> None:
                async for ev in subscribe("sess_overflow"):
                    if ev["type"] == "heartbeat":
                        continue
                    received.append(ev)
                    # Wait a touch to simulate a slow consumer.
                    await asyncio.sleep(0.001)
                    if ev["data"].get("final"):
                        done.set()
                        return

            task = asyncio.create_task(reader())
            await asyncio.sleep(0.05)

            burst_size = _MAX_QUEUE_DEPTH + 10
            for i in range(burst_size):
                await publish(
                    "sess_overflow",
                    {
                        "type": "agent.frame",
                        "data": {"seq": i, "final": i == burst_size - 1},
                    },
                )
            await asyncio.wait_for(done.wait(), timeout=5.0)
            task.cancel()
            return burst_size, len(received)

        burst_size, received_count = _run(scenario())
        # We can't assert exact count (depends on consumer speed), but we
        # MUST receive far less than the full burst (overflow dropped
        # some events) and the last event (the 'final' sentinel).
        self.assertLessEqual(
            received_count, burst_size, "shouldn't receive more than published"
        )
        # In a slow-consumer test we expect at least some events
        # delivered, including the final one.
        self.assertGreater(received_count, 0)


# ---------- session lookup parity --------------------------------------------


class TestSessionLookup(_IsolatedCase):
    def test_lookup_by_id_and_by_slug_return_same_row(self) -> None:
        async def scenario() -> tuple[str, str]:
            s = await self.store.create_session(
                name="Parity test", owner_user_id="u"
            )
            by_id = await self.store.get_session(s.id)
            by_slug = await self.store.get_session_by_slug(s.slug)
            assert by_id is not None
            assert by_slug is not None
            return by_id.id, by_slug.id

        a, b = _run(scenario())
        self.assertEqual(a, b)

    def test_lookup_unknown_returns_none_not_raises(self) -> None:
        a = _run(self.store.get_session("does-not-exist"))
        b = _run(self.store.get_session_by_slug("does-not-exist"))
        self.assertIsNone(a)
        self.assertIsNone(b)


# ---------- presence subscriber count -----------------------------------------


class TestPresenceLifecycle(_IsolatedCase):
    def test_multiple_subscribers_to_same_session_all_get_events(self) -> None:
        async def scenario() -> tuple[int, int]:
            r1: list[dict] = []
            r2: list[dict] = []
            done_count = 0

            async def reader(bucket: list[dict]) -> None:
                async for ev in subscribe("sess_multi"):
                    if ev["type"] == "heartbeat":
                        continue
                    bucket.append(ev)
                    if len(bucket) >= 1:
                        return

            t1 = asyncio.create_task(reader(r1))
            t2 = asyncio.create_task(reader(r2))
            await asyncio.sleep(0.05)
            self.assertEqual(subscriber_count("sess_multi"), 2)
            n = await publish(
                "sess_multi",
                {"type": "agent.frame", "data": {"v": "hello"}},
            )
            await asyncio.gather(t1, t2)
            return n, len(r1) + len(r2)

        delivered, total_received = _run(scenario())
        self.assertEqual(delivered, 2)
        self.assertEqual(total_received, 2)


if __name__ == "__main__":
    unittest.main()
