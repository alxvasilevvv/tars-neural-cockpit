"""Outreach safety / guardrail tests (Wave 98).

Covers recipient validation, placeholder detection, send-cap, and
the unsubscribe footer helper.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
import unittest

from backend.core.outreach import (
    OutreachDraft,
    OutreachStore,
    new_draft_id,
    reset_store,
)
from backend.core.outreach.safety import (
    check_send_eligibility,
    check_unsubscribe,
)


def _run(coro):
    return asyncio.run(coro)


class _SafetyCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self._tmp.close()
        os.environ["TARS_OUTREACH_DB_PATH"] = self._tmp.name
        os.environ.pop("TARS_OUTREACH_STORE", None)
        os.environ.pop("TARS_OUTREACH_DAILY_CAP", None)
        reset_store()
        self.store = OutreachStore(self._tmp.name)
        self._tpl = _run(
            self.store.upsert_template(
                name="X",
                slug="x",
                use_case="custom",
                system_prompt="x",
            )
        )

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
        os.environ.pop("TARS_OUTREACH_DB_PATH", None)
        os.environ.pop("TARS_OUTREACH_DAILY_CAP", None)
        reset_store()

    def _draft(self, **kw) -> OutreachDraft:
        defaults = dict(
            id=new_draft_id(),
            template_id=self._tpl.id,
            recipient={"email": "ok@example.com", "name": "Sam"},
            subject="hello",
            body="hi sam, just checking in.",
            status="approved",
        )
        defaults.update(kw)
        return OutreachDraft(**defaults)


class TestRecipientValidation(_SafetyCase):
    def test_valid_email_passes(self) -> None:
        result = _run(check_send_eligibility(self._draft(), store=self.store))
        self.assertTrue(result.ok, msg=str(result))

    def test_missing_email_fails(self) -> None:
        d = self._draft(recipient={"name": "noaddr"})
        result = _run(check_send_eligibility(d, store=self.store))
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "recipient_invalid")

    def test_malformed_email_fails(self) -> None:
        d = self._draft(recipient={"email": "not-an-email"})
        result = _run(check_send_eligibility(d, store=self.store))
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "recipient_invalid")


class TestPlaceholderDetection(_SafetyCase):
    def test_double_brace_in_body_blocked(self) -> None:
        d = self._draft(body="hi {{name}}, ping")
        result = _run(check_send_eligibility(d, store=self.store))
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "placeholder_in_body")

    def test_single_brace_in_subject_blocked(self) -> None:
        d = self._draft(subject="re: {topic}")
        result = _run(check_send_eligibility(d, store=self.store))
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "placeholder_in_subject")

    def test_clean_braces_ok(self) -> None:
        d = self._draft(body="hi sam, see https://x.io for details.")
        result = _run(check_send_eligibility(d, store=self.store))
        self.assertTrue(result.ok)


class TestStatusGate(_SafetyCase):
    def test_sent_status_blocked(self) -> None:
        d = self._draft(status="sent")
        result = _run(check_send_eligibility(d, store=self.store))
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "bad_status")


class TestDailyCap(_SafetyCase):
    def test_cap_exceeded_blocks(self) -> None:
        os.environ["TARS_OUTREACH_DAILY_CAP"] = "2"
        # Pre-seed two sent drafts in the trailing 24h.
        for i in range(2):
            sent = self._draft(
                id=new_draft_id(),
                status="sent",
                sent_at=time.time() - 60,
            )
            _run(self.store.insert_draft(sent))
        candidate = self._draft()
        result = _run(check_send_eligibility(candidate, store=self.store))
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "daily_cap_exceeded")


class TestUnsubscribeFooter(unittest.TestCase):
    def test_appends_when_missing(self) -> None:
        out = check_unsubscribe("hi sam, please reply with an answer.")
        self.assertIn("Reply STOP", out)

    def test_idempotent_when_present(self) -> None:
        body = "hi sam.\n\n---\nReply STOP to opt out."
        out = check_unsubscribe(body)
        # Footer marker already present -> no duplicate appended.
        self.assertEqual(out.count("Reply STOP"), 1)


if __name__ == "__main__":
    unittest.main()
