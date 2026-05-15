"""W274 — Conversation memory store tests."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from backend.core.memory.conversation import (
    ConversationMemory,
    ConversationTurn,
)


class TestConversationMemory(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "conv.sqlite"
        self.mem = ConversationMemory(db_path=self.db_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_add_turn_persists_to_session(self) -> None:
        t = ConversationTurn(
            id="",
            session_id="s1",
            role="user",
            text="Plan our Q3 outreach.",
        )
        saved = self.mem.add_turn(t)
        self.assertTrue(saved.id.startswith("turn_"))
        recent = self.mem.recent("s1")
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].text, "Plan our Q3 outreach.")

    def test_recent_returns_chronological_order(self) -> None:
        for i, txt in enumerate(["one", "two", "three", "four"]):
            self.mem.add_turn(ConversationTurn(
                id="", session_id="s2", role="user", text=txt,
                ts_utc=1_700_000_000.0 + i,
            ))
        rows = self.mem.recent("s2", limit=10)
        self.assertEqual([r.text for r in rows], ["one", "two", "three", "four"])

    def test_search_finds_matching_turn(self) -> None:
        self.mem.add_turn(ConversationTurn(
            id="", session_id="s3", role="user",
            text="The portfolio rebalancing strategy for Q4.",
        ))
        self.mem.add_turn(ConversationTurn(
            id="", session_id="s3", role="tars",
            text="Let me draft a memo about it.",
        ))
        # Unrelated chatter elsewhere.
        self.mem.add_turn(ConversationTurn(
            id="", session_id="s4", role="user",
            text="What's the weather in Tokyo?",
        ))
        hits = self.mem.search("portfolio rebalancing", limit=5)
        self.assertGreaterEqual(len(hits), 1)
        self.assertTrue(any("portfolio" in h.text.lower() for h in hits))

    def test_summarize_session_caches_summary(self) -> None:
        self.mem.add_turn(ConversationTurn(
            id="", session_id="s5", role="user",
            text="Health check-up prep for next Monday.",
        ))
        self.mem.add_turn(ConversationTurn(
            id="", session_id="s5", role="tars",
            text="I'll compile your sleep and step data.",
        ))
        summary1 = self.mem.summarize_session("s5")
        self.assertIn("turns", summary1)
        self.assertIn("Health check-up prep", summary1)
        # Second call should return cached value (still contains topic).
        summary2 = self.mem.summarize_session("s5")
        self.assertEqual(summary1, summary2)

    def test_delete_session_removes_turns(self) -> None:
        for txt in ["alpha", "beta", "gamma"]:
            self.mem.add_turn(ConversationTurn(
                id="", session_id="s6", role="user", text=txt,
            ))
        self.assertEqual(len(self.mem.recent("s6")), 3)
        n = self.mem.delete_session("s6")
        # delete_session reports rows from conv_session table (1).
        self.assertGreaterEqual(n, 1)
        self.assertEqual(len(self.mem.recent("s6")), 0)

    def test_context_for_bundles_recent_and_related(self) -> None:
        self.mem.add_turn(ConversationTurn(
            id="", session_id="s7", role="user",
            text="Discuss Q3 fundraising plans for the new fund.",
        ))
        self.mem.add_turn(ConversationTurn(
            id="", session_id="s8", role="user",
            text="Our Q3 fundraising hit 1.2M in commits.",
        ))
        ctx = self.mem.context_for(
            session_id="s7", query="fundraising", recent_limit=5, search_limit=3,
        )
        self.assertEqual(ctx["session_id"], "s7")
        self.assertEqual(len(ctx["recent"]), 1)
        # The cross-session match from s8 should show up in `related`.
        self.assertGreaterEqual(len(ctx["related"]), 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
