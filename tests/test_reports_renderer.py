"""Renderer tests for the reports module (Wave 103).

Mocks the skill loader via the :func:`set_skill_hook` API so we
verify the lifecycle (pending -> rendering -> done) without
depending on python-pptx / reportlab / openpyxl.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest

from backend.core.reports import (
    KIND_PPTX,
    KIND_XLSX,
    ReportStore,
    reset_store,
)
from backend.core.reports.renderer import (
    InputValidationError,
    render,
    render_preview_html,
    set_skill_hook,
    validate_inputs,
)
from backend.core.reports.scheduling import (
    is_report_playbook,
    report_playbook_id,
    template_id_from_playbook,
)
from backend.core.reports.providers import (
    fund_quarterly,
    list_providers,
    monthly_kpis,
)


def _run(coro):
    return asyncio.run(coro)


class _RenderCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self._tmp.close()
        self._outdir = tempfile.mkdtemp(prefix="reports-out-")
        os.environ["TARS_REPORTS_DB_PATH"] = self._tmp.name
        os.environ["TARS_REPORTS_OUTPUT_DIR"] = self._outdir
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
        try:
            for fn in os.listdir(self._outdir):
                os.unlink(os.path.join(self._outdir, fn))
            os.rmdir(self._outdir)
        except FileNotFoundError:
            pass
        os.environ.pop("TARS_REPORTS_DB_PATH", None)
        os.environ.pop("TARS_REPORTS_OUTPUT_DIR", None)
        set_skill_hook(None)
        reset_store()


class TestRenderHappyPath(_RenderCase):
    def test_render_with_default_fallback_completes(self) -> None:
        tpl = _run(
            self.store.upsert_template(
                name="LP", slug="lp", kind=KIND_PPTX,
                schema={"quarter": {"type": "string", "required": True}},
            )
        )
        run = _run(
            render(
                tpl.id,
                {"quarter": "Q1 2026"},
                store=self.store,
                output_dir=self._outdir,
                background=False,
            )
        )
        # After the synchronous render, the row should be done.
        got = _run(self.store.get_run(run.id))
        self.assertEqual(got.status, "done")
        self.assertGreater(got.bytes_size or 0, 0)
        self.assertTrue(os.path.isfile(got.output_path))

    def test_render_with_custom_skill_hook(self) -> None:
        captured: dict = {}

        async def hook(kind, template, inputs, output_path):
            captured["kind"] = kind
            captured["template_slug"] = template.slug
            captured["inputs"] = dict(inputs)
            with open(output_path, "wb") as fh:
                fh.write(b"FAKE_PPTX_BYTES")
            return 15

        set_skill_hook(hook)
        tpl = _run(
            self.store.upsert_template(
                name="LP", slug="lp", kind=KIND_PPTX,
            )
        )
        run = _run(
            render(
                tpl.id,
                {"quarter": "Q4 2025"},
                store=self.store,
                output_dir=self._outdir,
                background=False,
            )
        )
        got = _run(self.store.get_run(run.id))
        self.assertEqual(got.status, "done")
        self.assertEqual(got.bytes_size, 15)
        self.assertEqual(captured["kind"], KIND_PPTX)
        self.assertEqual(captured["template_slug"], "lp")


class TestRenderValidation(_RenderCase):
    def test_missing_required_input_raises(self) -> None:
        tpl = _run(
            self.store.upsert_template(
                name="LP", slug="lp", kind=KIND_PPTX,
                schema={"quarter": {"type": "string", "required": True}},
            )
        )
        with self.assertRaises(InputValidationError):
            _run(
                render(
                    tpl.id,
                    {},
                    store=self.store,
                    output_dir=self._outdir,
                    background=False,
                )
            )

    def test_validate_inputs_type_check(self) -> None:
        from backend.core.reports.models import ReportTemplate
        tpl = ReportTemplate(
            id="x", name="X", slug="x", kind=KIND_XLSX,
            schema={
                "n": {"type": "number"},
                "items": {"type": "array"},
            },
        )
        with self.assertRaises(InputValidationError):
            validate_inputs(tpl, {"n": "not-a-number"})
        with self.assertRaises(InputValidationError):
            validate_inputs(tpl, {"items": "not-a-list"})
        # OK shape:
        validate_inputs(tpl, {"n": 42, "items": [1, 2]})

    def test_render_unknown_template_raises(self) -> None:
        with self.assertRaises(LookupError):
            _run(
                render(
                    "rtpl_doesnotexist",
                    {},
                    store=self.store,
                    output_dir=self._outdir,
                    background=False,
                )
            )

    def test_render_failure_records_failed_status(self) -> None:
        async def boom(kind, template, inputs, output_path):
            raise RuntimeError("skill exploded")

        set_skill_hook(boom)
        tpl = _run(
            self.store.upsert_template(
                name="LP", slug="lp", kind=KIND_PPTX,
            )
        )
        run = _run(
            render(
                tpl.id,
                {},
                store=self.store,
                output_dir=self._outdir,
                background=False,
            )
        )
        got = _run(self.store.get_run(run.id))
        self.assertEqual(got.status, "failed")
        self.assertIn("skill exploded", got.error or "")


class TestPreviewAndScheduling(_RenderCase):
    def test_preview_html_contains_inputs(self) -> None:
        tpl = _run(
            self.store.upsert_template(
                name="Board pack", slug="board", kind=KIND_PPTX,
            )
        )
        html = render_preview_html(tpl, {"quarter": "Q1 2026", "kpis": {"arr": 42}})
        self.assertIn("Board pack", html)
        self.assertIn("quarter", html)
        self.assertIn("Q1 2026", html)

    def test_schedule_id_roundtrip(self) -> None:
        pid = report_playbook_id("rtpl_abc")
        self.assertTrue(is_report_playbook(pid))
        self.assertEqual(template_id_from_playbook(pid), "rtpl_abc")
        self.assertFalse(is_report_playbook("foo"))

    def test_provider_registry_contains_three(self) -> None:
        names = list_providers()
        self.assertIn("reports.providers.fund_quarterly", names)
        self.assertIn("reports.providers.monthly_kpis", names)
        self.assertIn("reports.providers.portfolio_snapshot", names)

    def test_provider_outputs_have_required_keys(self) -> None:
        fq = _run(fund_quarterly())
        self.assertIn("quarter", fq)
        self.assertIn("aum", fq)
        mk = _run(monthly_kpis())
        self.assertIn("month", mk)
        self.assertIn("revenue", mk)


if __name__ == "__main__":
    unittest.main()
