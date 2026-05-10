"""SQLite store tests for the outreach module (Wave 98).

Stdlib unittest only. Each test isolates its own DB via tempfile so
``~/.tars/outreach.sqlite`` is never touched.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
import unittest

from backend.core.outreach import (
    OutreachCampaign,
    OutreachDraft,
    OutreachStore,
    new_campaign_id,
    new_draft_id,
    reset_store,
)


def _run(coro):
    return asyncio.run(coro)


class _IsolatedStoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self._tmp.close()
        os.environ["TARS_OUTREACH_DB_PATH"] = self._tmp.name
        os.environ.pop("TARS_OUTREACH_STORE", None)
        reset_store()
        self.store = OutreachStore(self._tmp.name)

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
        reset_store()


class TestTemplateCRUD(_IsolatedStoreCase):
    def test_upsert_and_list(self) -> None:
        t = _run(
            self.store.upsert_template(
                name="LP update",
                slug="lp_update",
                use_case="lp_update",
                system_prompt="be concise",
                variables=["quarter"],
                default_subject_template="{{quarter}} update",
            )
        )
        self.assertEqual(t.slug, "lp_update")
        self.assertEqual(t.variables, ["quarter"])
        listed = _run(self.store.list_templates())
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].id, t.id)

    def test_upsert_is_idempotent_by_slug(self) -> None:
        t1 = _run(
            self.store.upsert_template(
                name="LP update",
                slug="lp_update",
                use_case="lp_update",
                system_prompt="v1",
                variables=["quarter"],
            )
        )
        t2 = _run(
            self.store.upsert_template(
                name="LP update v2",
                slug="lp_update",
                use_case="lp_update",
                system_prompt="v2",
                variables=["quarter", "aum"],
            )
        )
        # Same id (preserved across upsert), updated body fields.
        self.assertEqual(t1.id, t2.id)
        self.assertEqual(t2.system_prompt, "v2")
        self.assertEqual(t2.variables, ["quarter", "aum"])
        listed = _run(self.store.list_templates())
        self.assertEqual(len(listed), 1)

    def test_get_by_slug(self) -> None:
        t = _run(
            self.store.upsert_template(
                name="Intro",
                slug="intro",
                use_case="intro",
                system_prompt="warm intro",
            )
        )
        got = _run(self.store.get_template_by_slug("intro"))
        self.assertIsNotNone(got)
        self.assertEqual(got.id, t.id)
        missing = _run(self.store.get_template_by_slug("nope"))
        self.assertIsNone(missing)

    def test_update_template_partial(self) -> None:
        t = _run(
            self.store.upsert_template(
                name="Intro",
                slug="intro",
                use_case="intro",
                system_prompt="v1",
            )
        )
        updated = _run(
            self.store.update_template(t.id, system_prompt="v2-better")
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.system_prompt, "v2-better")
        self.assertEqual(updated.name, "Intro")  # unchanged


class TestDraftCRUD(_IsolatedStoreCase):
    def _seed_template(self):
        return _run(
            self.store.upsert_template(
                name="Intro",
                slug="intro",
                use_case="intro",
                system_prompt="warm",
            )
        )

    def test_insert_get_draft(self) -> None:
        tpl = self._seed_template()
        draft = OutreachDraft(
            id=new_draft_id(),
            template_id=tpl.id,
            recipient={"email": "founder@example.com", "name": "Sam"},
            context={"company": "Acme"},
            subject="Re: deck",
            body="hi Sam, thanks for the deck.",
        )
        _run(self.store.insert_draft(draft))
        got = _run(self.store.get_draft(draft.id))
        self.assertEqual(got.id, draft.id)
        self.assertEqual(got.recipient["email"], "founder@example.com")
        self.assertEqual(got.subject, "Re: deck")

    def test_list_drafts_filter_status(self) -> None:
        tpl = self._seed_template()
        for i, status in enumerate(["draft", "approved", "sent"]):
            d = OutreachDraft(
                id=new_draft_id(),
                template_id=tpl.id,
                recipient={"email": f"x{i}@example.com"},
                subject="s",
                body="b",
                status=status,
                sent_at=(time.time() if status == "sent" else None),
            )
            _run(self.store.insert_draft(d))
        only_drafts = _run(self.store.list_drafts(status="draft"))
        self.assertEqual(len(only_drafts), 1)
        self.assertEqual(only_drafts[0].status, "draft")
        all_three = _run(self.store.list_drafts())
        self.assertEqual(len(all_three), 3)

    def test_update_draft_status(self) -> None:
        tpl = self._seed_template()
        d = OutreachDraft(
            id=new_draft_id(),
            template_id=tpl.id,
            recipient={"email": "x@example.com"},
            subject="s",
            body="b",
        )
        _run(self.store.insert_draft(d))
        updated = _run(self.store.update_draft(d.id, status="approved"))
        self.assertEqual(updated.status, "approved")

    def test_delete_draft(self) -> None:
        tpl = self._seed_template()
        d = OutreachDraft(
            id=new_draft_id(),
            template_id=tpl.id,
            recipient={"email": "x@example.com"},
        )
        _run(self.store.insert_draft(d))
        ok = _run(self.store.delete_draft(d.id))
        self.assertTrue(ok)
        self.assertIsNone(_run(self.store.get_draft(d.id)))

    def test_count_sent_since(self) -> None:
        tpl = self._seed_template()
        now = time.time()
        for i in range(3):
            d = OutreachDraft(
                id=new_draft_id(),
                template_id=tpl.id,
                recipient={"email": f"x{i}@example.com"},
                status="sent",
                sent_at=now - i * 100,
            )
            _run(self.store.insert_draft(d))
        # Old (2 days ago) sent draft should NOT count.
        old = OutreachDraft(
            id=new_draft_id(),
            template_id=tpl.id,
            recipient={"email": "old@example.com"},
            status="sent",
            sent_at=now - 60 * 60 * 48,
        )
        _run(self.store.insert_draft(old))
        count = _run(self.store.count_sent_since(now - 60 * 60 * 24))
        self.assertEqual(count, 3)


class TestCampaignCRUD(_IsolatedStoreCase):
    def test_insert_and_counters(self) -> None:
        tpl = _run(
            self.store.upsert_template(
                name="LP update",
                slug="lp_update",
                use_case="lp_update",
                system_prompt="x",
            )
        )
        c = OutreachCampaign(
            id=new_campaign_id(),
            name="Q1 update batch",
            template_id=tpl.id,
            recipients=[{"email": "lp1@x.com"}, {"email": "lp2@x.com"}],
        )
        _run(self.store.insert_campaign(c))
        got = _run(self.store.get_campaign(c.id))
        self.assertIsNotNone(got)
        self.assertEqual(got.name, "Q1 update batch")
        self.assertEqual(len(got.recipients), 2)
        # Counters bump.
        bumped = _run(
            self.store.update_campaign_counters(
                c.id, generated_delta=2, approved_delta=1, sent_delta=1, status="sending"
            )
        )
        self.assertEqual(bumped.drafts_generated, 2)
        self.assertEqual(bumped.drafts_approved, 1)
        self.assertEqual(bumped.drafts_sent, 1)
        self.assertEqual(bumped.status, "sending")

    def test_list_campaigns_orders_by_created_desc(self) -> None:
        tpl = _run(
            self.store.upsert_template(
                name="X",
                slug="x",
                use_case="custom",
                system_prompt="x",
            )
        )
        c1 = OutreachCampaign(
            id=new_campaign_id(),
            name="first",
            template_id=tpl.id,
            recipients=[{"email": "a@x.com"}],
            created_at=time.time() - 100,
        )
        c2 = OutreachCampaign(
            id=new_campaign_id(),
            name="second",
            template_id=tpl.id,
            recipients=[{"email": "b@x.com"}],
            created_at=time.time(),
        )
        _run(self.store.insert_campaign(c1))
        _run(self.store.insert_campaign(c2))
        listed = _run(self.store.list_campaigns())
        self.assertEqual([c.name for c in listed], ["second", "first"])


if __name__ == "__main__":
    unittest.main()
