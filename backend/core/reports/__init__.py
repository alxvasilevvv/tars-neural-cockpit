"""TARS reporting export module (Wave 103).

Generate PDF / PPTX / XLSX / DOCX reports from operator-supplied
inputs + built-in templates. Built on top of the existing
:mod:`backend.core.outreach`, :mod:`backend.core.scheduler` and
:mod:`backend.core.receipts` modules.

Persistence: SQLite at ``~/.tars/reports.sqlite`` (override via
``TARS_REPORTS_DB_PATH``; ``TARS_REPORTS_STORE=disabled`` short-
circuits the entire module). Rendered files live under
``~/.tars/reports/<run_id>.<ext>``.

Public surface:

- :mod:`.models`        dataclasses (``ReportTemplate``, ``ReportRun``).
- :mod:`.store`         SQLite-backed CRUD + lifecycle queries.
- :mod:`.templates_lib` six built-in starter templates.
- :mod:`.renderer`      template execution; routes by ``kind`` to the
  matching rendering skill (pptx / docx / xlsx / pdf).
- :mod:`.delivery`      auto-send via Wave 98 outreach + Wave 90 webhooks.
- :mod:`.scheduling`    wraps the Wave 97 scheduler.
- :mod:`.providers`     opt-in inputs providers (fund quarterly, monthly
  KPIs, portfolio snapshot).

Contract version: 1.0 (see ``docs/contracts/REPORTS.md``).
"""

from __future__ import annotations

from .models import (
    CONTRACT_VERSION,
    KIND_DOCX,
    KIND_PDF,
    KIND_PPTX,
    KIND_XLSX,
    REPORT_KINDS,
    REPORT_STATUSES,
    ReportRun,
    ReportTemplate,
    new_run_id,
    new_template_id,
)
from .store import ReportStore, get_store, reset_store

__all__ = [
    "CONTRACT_VERSION",
    "KIND_DOCX",
    "KIND_PDF",
    "KIND_PPTX",
    "KIND_XLSX",
    "REPORT_KINDS",
    "REPORT_STATUSES",
    "ReportRun",
    "ReportStore",
    "ReportTemplate",
    "get_store",
    "new_run_id",
    "new_template_id",
    "reset_store",
]
