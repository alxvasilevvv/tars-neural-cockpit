"""SQLite store tests for the reports module (Wave 103).

Stdlib unittest only. Each test isolates its own DB via tempfile so
``~/.tars/reports.sqlite`` is never touched.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
import unittest

from backend.core.reports import (
    KIND_PPTX,
    KIND_XLSX,
    REPORT_KINDS,
    ReportRun,
    ReportStore,
    new_run_id,
    reset_store,
)
from backend.core.reports.templates_lib import (
    BUILTIN_TEMPLATES,
    seed_builtin_templates,
)


def _run(coro):
    return asyncio.run(coro)


class _IsolatedStoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self._tmp.close()
        os.environ["TARS_REPORTS_DB_PATH"] = self._tmp.name
        os.environ.pop("TARS_REPORTS_STORE", None)
        reset_store()
        self.store = ReportStore(self._tmp.name)

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
        os.environ.pop("TARS_REPORTS_DB_PATH", None)
        reset_store()


class TestTemplateCRUD(_IsolatedStoreCase):
    def test_upsert_and_list(self) -> None:
        t = _run(
            self.store.upsert_template(
                name="LP update",
                slug="lp_q",
                kind=KIND_PPTX,
                schema={"quarter": {"type": "string", "required": True}},
                description="quarterly LP update",
            )
        )
        self.assertEqual(t.slug, "lp_q")
        self.assertEqual(t.kind, KIND_PPTX)
        self.assertFalse(t.is_builtin)
        listed = _run(self.store.list_templates())
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].id, t.id)

    def test_upsert_is_idempotent_by_slug(self) -> None:
        t1 = _run(
            self.store.upsert_template(
                name="LP", slug="lp", kind=KIND_PPTX, schema={"a": 1},
            )
        )
        t2 = _run(
            self.store.upsert_template(
                name="LP v2", slug="lp", kind=KIND_PPTX, schema={"b": 2},
            )
        )
        self.assertEqual(t1.id, t2.id)
        rows = _run(self.store.list_templates())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].name, "LP v2")

    def test_filter_templates_by_kind(self) -> None:
        _run(self.store.upsert_template(name="A", slug="a", kind=KIND_PPTX))
        _run(self.store.upsert_template(name="B", slug="b", kind=KIND_XLSX))
        rows = _run(self.store.list_templates(kind=KIND_XLSX))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].slug, "b")

    def test_get_template_by_slug(self) -> None:
        _run(self.store.upsert_template(name="A", slug="a", kind=KIND_PPTX))
        got = _run(self.store.get_template_by_slug("a"))
        self.assertIsNotNone(got)
        self.assertEqual(got.slug, "a")
        missing = _run(self.store.get_template_by_slug("nope"))
        self.assertIsNone(missing)

    def test_unknown_kind_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _run(
                self.store.upsert_template(
                    name="X", slug="x", kind="bogus",
                )
            )

    def test_delete_protects_builtins(self) -> None:
        builtin = _run(
            self.store.upsert_template(
                name="A", slug="a", kind=KIND_PPTX, is_builtin=True,
            )
        )
        custom = _run(
            self.store.upsert_template(
                name="B", slug="b", kind=KIND_PPTX, is_builtin=False,
            )
        )
        self.assertFalse(_run(self.store.delete_template(builtin.id)))
        self.assertTrue(_run(self.store.delete_template(custom.id)))


class TestRunLifecycle(_IsolatedStoreCase):
    def _make_template(self):
        return _run(
            self.store.upsert_template(
                name="LP", slug="lp", kind=KIND_PPTX, schema={"q": {"type": "string"}},
            )
        )

    def test_insert_and_fetch_run(self) -> None:
        tpl = self._make_template()
        run = ReportRun(
            id=new_run_id(),
            template_id=tpl.id,
            inputs={"q": "Q1"},
            output_path="/tmp/x.pptx",
            output_kind=KIND_PPTX,
        )
        _run(self.store.insert_run(run))
        got = _run(self.store.get_run(run.id))
        self.assertIsNotNone(got)
        self.assertEqual(got.id, run.id)
        self.assertEqual(got.inputs["q"], "Q1")
        self.assertEqual(got.status, "pending")

    def test_update_run_status(self) -> None:
        tpl = self._make_template()
        run = ReportRun(id=new_run_id(), template_id=tpl.id, output_kind=KIND_PPTX)
        _run(self.store.insert_run(run))
        updated = _run(
            self.store.update_run(
                run.id,
                status="done",
                output_path="/tmp/done.pptx",
                generated_at=time.time(),
                bytes_size=1234,
            )
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, "done")
        self.assertEqual(updated.bytes_size, 1234)

    def test_list_runs_filtering(self) -> None:
        tpl = self._make_template()
        for i in range(3):
            _run(
                self.store.insert_run(
                    ReportRun(
                        id=new_run_id(),
                        template_id=tpl.id,
                        status="done" if i == 0 else "failed",
                        output_kind=KIND_PPTX,
                    )
                )
            )
        all_rows = _run(self.store.list_runs())
        self.assertEqual(len(all_rows), 3)
        done = _run(self.store.list_runs(status="done"))
        self.assertEqual(len(done), 1)
        by_template = _run(self.store.list_runs(template_id=tpl.id))
        self.assertEqual(len(by_template), 3)

    def test_count_by_status(self) -> None:
        tpl = self._make_template()
        for status in ("done", "done", "failed", "pending"):
            _run(
                self.store.insert_run(
                    ReportRun(
                        id=new_run_id(),
                        template_id=tpl.id,
                        status=status,
                        output_kind=KIND_PPTX,
                    )
                )
            )
        counts = _run(self.store.count_by_status())
        self.assertEqual(counts.get("done"), 2)
        self.assertEqual(counts.get("failed"), 1)
        self.assertEqual(counts.get("pending"), 1)


class TestBuiltinSeeding(_IsolatedStoreCase):
    def test_seed_inserts_six_templates(self) -> None:
        n = _run(seed_builtin_templates(self.store))
        self.assertEqual(n, len(BUILTIN_TEMPLATES))
        rows = _run(self.store.list_templates())
        self.assertEqual(len(rows), 6)
        slugs = {r.slug for r in rows}
        self.assertIn("lp_quarterly_update", slugs)
        self.assertIn("incident_postmortem", slugs)
        for r in rows:
            self.assertTrue(r.is_builtin)
            self.assertIn(r.kind, REPORT_KINDS)

    def test_seed_is_idempotent(self) -> None:
        _run(seed_builtin_templates(self.store))
        _run(seed_builtin_templates(self.store))
        rows = _run(self.store.list_templates())
        self.assertEqual(len(rows), 6)


if __name__ == "__main__":
    unittest.main()
