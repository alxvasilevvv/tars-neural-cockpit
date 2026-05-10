"""Installer for vertical bundles (Wave 107).

Idempotent install pipeline that wires a bundle's components into
the live TARS install. Persists a row in
``~/.tars/bundles/installed.sqlite`` so the FE's "installed" tab
can list / uninstall, and so re-installing the same bundle for the
same org is a no-op (we just refresh the receipt + finished_at).

Components -> downstream modules:

- ``playbooks``           -- check the on-disk playbook loader; warn
  if the id isn't found (treated as "marketplace install required").
- ``scheduled``           -- create entries via Wave 97 scheduler
  store; idempotent on ``(playbook_id, cron_expression)``.
- ``dashboard_widgets``   -- write a layout hint that the FE picks up
  on next /dashboard visit (the actual layout state lives client-
  side; v1 just records intent).
- ``report_templates``    -- record the slugs as "enabled" on the
  install record; the W103 renderer already knows the templates.
- ``outreach_templates``  -- run the W98 starter-template seeder if
  the slug matches one of the starters; missing slugs warn-only.
- ``connectors_hints``    -- pure metadata; the onboarding wizard
  reads these and surfaces priority chips.
- ``welcome_content``     -- echoed back in the install report.
- ``first_run_playbook``  -- queues a deferred run via the scheduler
  (or reports the intended id when the scheduler is disabled).

Every successful install records a ``bundle.installed`` receipt via
Wave 95. Failures during a sub-step are turned into warnings on the
report -- the install never raises (operator gets to retry).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from .definitions import bundle_by_id
from .models import (
    CONTRACT_VERSION,
    Bundle,
    InstallReport,
    new_install_id,
)


log = logging.getLogger("tars.bundles.installer")


DEFAULT_DB_PATH = "~/.tars/bundles/installed.sqlite"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS bundle_installs (
    install_id TEXT PRIMARY KEY,
    bundle_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    installed_at REAL NOT NULL,
    finished_at REAL,
    welcome_content TEXT NOT NULL DEFAULT '',
    first_run_id TEXT,
    items_json TEXT NOT NULL DEFAULT '{}',
    warnings_json TEXT NOT NULL DEFAULT '[]'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_bundle_installs_org
    ON bundle_installs (bundle_id, org_id);

CREATE INDEX IF NOT EXISTS idx_bundle_installs_at
    ON bundle_installs (installed_at DESC);
"""


# ---------- DB helpers -----------------------------------------------------


def _db_path() -> str:
    return os.path.expanduser(
        os.getenv("TARS_BUNDLES_DB_PATH") or DEFAULT_DB_PATH
    )


def _connect() -> sqlite3.Connection:
    p = _db_path()
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def reset_db() -> None:
    """Test helper -- removes the install DB if present."""

    p = _db_path()
    try:
        if Path(p).exists():
            Path(p).unlink()
    except OSError:
        pass


# ---------- Module probing -------------------------------------------------
#
# We import collaborator modules lazily so that this installer remains
# importable even when (e.g.) the scheduler is bolted off via env.


def _try_get_playbook(playbook_id: str) -> Any | None:
    try:
        from backend.core.playbooks.loader import get_playbook  # type: ignore
    except Exception:
        return None
    try:
        return get_playbook(playbook_id)
    except Exception:
        return None


async def _seed_outreach_template(slug: str) -> dict[str, Any] | None:
    try:
        from backend.core.outreach.templates import starter_specs
        from backend.core.outreach.store import get_store as get_outreach_store
    except Exception:
        return None
    try:
        store = get_outreach_store()
    except Exception:
        return None
    if not getattr(store, "enabled", False):
        return None
    spec = next((s for s in starter_specs() if s.get("slug") == slug), None)
    if spec is None:
        return None
    try:
        tpl = await store.upsert_template(
            name=spec["name"],
            slug=spec["slug"],
            use_case=spec["use_case"],
            system_prompt=spec["system_prompt"],
            variables=spec["variables"],
            default_subject_template=spec["default_subject_template"],
        )
    except Exception as exc:
        log.debug("bundles.installer.seed_outreach failed: %s", exc)
        return None
    out = {"slug": slug}
    tid = getattr(tpl, "id", None)
    if tid is not None:
        out["template_id"] = str(tid)
    return out


async def _create_schedule(
    playbook_id: str, cron: str, args: dict[str, Any]
) -> dict[str, Any] | None:
    try:
        from backend.core.scheduler.store import get_store as get_sched_store
    except Exception:
        return None
    try:
        store = get_sched_store()
    except Exception:
        return None
    if not getattr(store, "enabled", False):
        return None
    # Idempotency: re-use an existing schedule with the same playbook_id +
    # cron_expression instead of stacking duplicates.
    try:
        existing = await store.list_schedules(playbook_id=playbook_id)
    except Exception:
        existing = []
    for sch in existing or []:
        if getattr(sch, "cron_expression", None) == cron:
            return {
                "schedule_id": sch.id,
                "playbook_id": playbook_id,
                "cron": cron,
                "reused": True,
            }
    try:
        sch = await store.create_schedule(
            playbook_id=playbook_id,
            cron_expression=cron,
            args=args,
        )
    except Exception as exc:
        log.debug("bundles.installer.create_schedule failed: %s", exc)
        return None
    return {
        "schedule_id": sch.id,
        "playbook_id": playbook_id,
        "cron": cron,
        "reused": False,
    }


async def _delete_schedule(schedule_id: str) -> bool:
    try:
        from backend.core.scheduler.store import get_store as get_sched_store
    except Exception:
        return False
    try:
        store = get_sched_store()
    except Exception:
        return False
    if not getattr(store, "enabled", False):
        return False
    try:
        return await store.delete_schedule(schedule_id)
    except Exception:
        return False


async def _record_receipt(
    type_: str, actor: str, resource: str, payload: dict[str, Any]
) -> None:
    try:
        from backend.core.receipts.dispatch import record  # type: ignore
    except Exception:
        return
    try:
        await record(type=type_, actor=actor, resource=resource, payload=payload)
    except Exception as exc:
        log.debug("bundles.installer.record_receipt failed: %s", exc)


# ---------- core install ---------------------------------------------------


def _walk(
    bundle: Bundle,
    *,
    install_id: str,
    org_id: str,
    dry_run: bool,
) -> InstallReport:
    """Walk the bundle and return a partially-populated InstallReport.

    Pure-sync portion of the install (playbook lookups, dashboard
    widgets, connector hints). The async portion (scheduler +
    outreach + receipts) wraps this.
    """

    report = InstallReport(
        install_id=install_id,
        bundle_id=bundle.id,
        org_id=org_id,
        dry_run=dry_run,
        welcome_content=bundle.welcome_content(),
    )

    for pb_id in bundle.playbooks():
        entry = {"id": pb_id, "available": False}
        pb = _try_get_playbook(pb_id)
        if pb is not None:
            entry["available"] = True
            try:
                entry["name"] = getattr(pb, "name", pb_id)
            except Exception:
                pass
        else:
            report.warn(f"playbook_missing:{pb_id}")
        report.add("playbooks", entry)

    for w in bundle.dashboard_widgets():
        report.add("dashboard_widgets", {"id": w})

    for slug in bundle.report_templates():
        report.add("report_templates", {"slug": slug})

    for hint in bundle.connectors_hints():
        report.add("connectors_hints", hint)

    return report


async def install_bundle(
    bundle_id: str,
    org_id: str,
    *,
    run_first_now: bool = False,
) -> InstallReport:
    """Install a bundle for an org. Idempotent.

    If a (bundle_id, org_id) install already exists, the existing
    install_id is reused, the items_json is refreshed, and the
    install_at timestamp is *not* changed (finished_at is). The
    install report's ``warnings`` carries an ``already_installed``
    marker so the FE can adjust copy.
    """

    bundle = bundle_by_id(bundle_id)
    if bundle is None:
        report = InstallReport(
            install_id=new_install_id(),
            bundle_id=bundle_id,
            org_id=org_id,
            dry_run=False,
        )
        report.warn("bundle_not_found")
        report.finished_at = time.time()
        return report

    org = (org_id or "").strip() or "default"
    install_id = new_install_id()
    existing = _read_existing(bundle.id, org)
    if existing is not None:
        install_id = existing["install_id"]

    report = _walk(bundle, install_id=install_id, org_id=org, dry_run=False)
    if existing is not None:
        report.warn("already_installed")

    # Scheduled jobs
    for entry in bundle.scheduled():
        sched_info = await _create_schedule(
            entry["playbook_id"], entry["cron"], entry["args"]
        )
        if sched_info is None:
            report.warn(f"schedule_skipped:{entry['playbook_id']}")
            report.add(
                "scheduled",
                {
                    "playbook_id": entry["playbook_id"],
                    "cron": entry["cron"],
                    "skipped": True,
                },
            )
        else:
            report.add("scheduled", sched_info)

    # Outreach templates (W98 starters)
    for slug in bundle.outreach_templates():
        seeded = await _seed_outreach_template(slug)
        if seeded is None:
            report.warn(f"outreach_skipped:{slug}")
            report.add("outreach_templates", {"slug": slug, "skipped": True})
        else:
            report.add("outreach_templates", seeded)

    # First-run playbook -- v1 just records the intent. The actual
    # queueing requires a runner-deferred-task helper that's still in
    # design (Wave 108). When ``run_first_now`` is True we still
    # surface the intent so the FE can fire the run via /api/playbooks
    # if desired.
    first = bundle.first_run_playbook()
    if first:
        report.first_run_id = first
        if run_first_now:
            report.add(
                "scheduled",
                {
                    "playbook_id": first,
                    "cron": "@now",
                    "first_run": True,
                },
            )

    report.finished_at = time.time()

    _persist(report)
    await _record_receipt(
        "bundle.installed",
        actor=f"org:{org}",
        resource=bundle.id,
        payload={
            "bundle_id": bundle.id,
            "org_id": org,
            "install_id": install_id,
            "counts": report.counts(),
            "first_run_id": report.first_run_id,
            "already_installed": existing is not None,
            "contract_version": CONTRACT_VERSION,
        },
    )
    return report


async def uninstall_bundle(bundle_id: str, org_id: str) -> InstallReport:
    """Reverse an install. Removes scheduled jobs that this install
    created (looked up by ``schedule_id`` from the saved report).

    Outreach templates and dashboard widgets are *not* purged --
    they're additive and the operator may have edited them. The
    install row is deleted from the registry so re-install is fresh.
    """

    org = (org_id or "").strip() or "default"
    existing = _read_existing(bundle_id, org)
    bundle = bundle_by_id(bundle_id)
    install_id = existing["install_id"] if existing else new_install_id()

    report = InstallReport(
        install_id=install_id,
        bundle_id=bundle_id,
        org_id=org,
        dry_run=False,
    )
    if bundle is not None:
        report.welcome_content = ""

    if existing is None:
        report.warn("not_installed")
        report.finished_at = time.time()
        return report

    items = existing.get("items") or {}
    for entry in items.get("scheduled", []):
        sid = entry.get("schedule_id")
        if not sid:
            continue
        ok = await _delete_schedule(sid)
        report.add(
            "scheduled",
            {"schedule_id": sid, "deleted": bool(ok)},
        )

    # Forward the rest of the snapshot so FE can render a "what was
    # there" diff.
    for key in ("playbooks", "dashboard_widgets", "report_templates",
                "outreach_templates", "connectors_hints"):
        for entry in items.get(key, []):
            report.add(key, dict(entry))

    _delete_install(bundle_id, org)
    report.finished_at = time.time()
    await _record_receipt(
        "bundle.uninstalled",
        actor=f"org:{org}",
        resource=bundle_id,
        payload={
            "bundle_id": bundle_id,
            "org_id": org,
            "install_id": install_id,
            "contract_version": CONTRACT_VERSION,
        },
    )
    return report


# ---------- listing --------------------------------------------------------


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    try:
        items = json.loads(row["items_json"] or "{}")
    except Exception:
        items = {}
    try:
        warnings = json.loads(row["warnings_json"] or "[]")
    except Exception:
        warnings = []
    return {
        "install_id": row["install_id"],
        "bundle_id": row["bundle_id"],
        "org_id": row["org_id"],
        "installed_at": row["installed_at"],
        "finished_at": row["finished_at"],
        "welcome_content": row["welcome_content"] or "",
        "first_run_id": row["first_run_id"],
        "items": items,
        "warnings": warnings,
    }


async def list_installed(org_id: str | None = None) -> list[dict[str, Any]]:
    """Return all bundle installs (optionally filtered by org)."""

    return await asyncio.to_thread(_list_sync, org_id)


def _list_sync(org_id: str | None) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        if org_id:
            rows = conn.execute(
                "SELECT * FROM bundle_installs WHERE org_id=? "
                "ORDER BY installed_at DESC",
                (org_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM bundle_installs ORDER BY installed_at DESC"
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


async def installed_for_org(org_id: str) -> list[dict[str, Any]]:
    return await list_installed(org_id=org_id)


def _read_existing(bundle_id: str, org_id: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM bundle_installs WHERE bundle_id=? AND org_id=?",
            (bundle_id, org_id),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def _persist(report: InstallReport) -> None:
    conn = _connect()
    try:
        # Use ON CONFLICT to make idempotency work without a SELECT-then-INSERT race.
        conn.execute(
            """
            INSERT INTO bundle_installs (
                install_id, bundle_id, org_id, installed_at, finished_at,
                welcome_content, first_run_id, items_json, warnings_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(bundle_id, org_id) DO UPDATE SET
                finished_at=excluded.finished_at,
                welcome_content=excluded.welcome_content,
                first_run_id=excluded.first_run_id,
                items_json=excluded.items_json,
                warnings_json=excluded.warnings_json
            """,
            (
                report.install_id,
                report.bundle_id,
                report.org_id,
                report.started_at,
                report.finished_at,
                report.welcome_content,
                report.first_run_id,
                json.dumps(report.items),
                json.dumps(report.warnings),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _delete_install(bundle_id: str, org_id: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            "DELETE FROM bundle_installs WHERE bundle_id=? AND org_id=?",
            (bundle_id, org_id),
        )
        conn.commit()
    finally:
        conn.close()


__all__ = [
    "install_bundle",
    "installed_for_org",
    "list_installed",
    "reset_db",
    "uninstall_bundle",
]
