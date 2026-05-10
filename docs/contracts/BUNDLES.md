# Bundles contract (Wave 107)

Contract version: **1.0**

## What is a bundle?

A *bundle* is a one-click "ready to demo" pack for a specific
org-type vertical. Installing a bundle wires together everything
that vertical needs to look and feel finished out of the box —
playbooks, scheduled jobs, dashboard widgets, report templates,
outreach drafts, connector hints, welcome content and an optional
first-run playbook.

A new fund partner clicks "Install VC fund template" and 30 seconds
later has a working B2B workspace.

## Bundle definition format

```python
Bundle(
  id="vc_fund_bundle",      # canonical id (snake_case)
  slug="vc-fund",           # url-safe alias
  name="VC Fund template",  # human-readable
  description="...",
  org_type="vc_fund",       # one of ORG_TYPES
  version="1.0.0",
  components={
    "playbooks":           [...],   # list[str] of playbook ids
    "scheduled":           [...],   # list[{playbook_id, cron, args?}]
    "dashboard_widgets":   [...],   # list[str] widget ids in display order
    "report_templates":    [...],   # list[str] template slugs to enable
    "outreach_templates":  [...],   # list[str] outreach-template slugs
    "connectors_hints":    [...],   # list[str | {id, priority}]
    "welcome_content":     "...",   # markdown shown post-install
    "first_run_playbook":  "...",   # one playbook to queue after install
  },
)
```

All ``components`` keys are optional; missing keys collapse to empty
lists / no-ops.

### Org-type vocabulary

```
vc_fund | hedge_fund | family_office | saas | dao | research_lab | other
```

Bundles outside this set fall back to ``other_bundle`` via
``bundle_for_org_type``.

## Component types

| Key                    | Type                       | Downstream module       | Notes                                                              |
| ---------------------- | -------------------------- | ----------------------- | ------------------------------------------------------------------ |
| ``playbooks``          | ``list[str]``              | W80/W81/W106 loader     | Each id is checked against the on-disk loader; missing ids warn.   |
| ``scheduled``          | ``list[dict]``             | Wave 97 scheduler       | ``{playbook_id, cron, args?}`` — cron is 5-field stdlib syntax.    |
| ``dashboard_widgets``  | ``list[str]``              | Wave 96 dashboard       | Widget ids in display order. FE applies on next /dashboard visit.  |
| ``report_templates``   | ``list[str]``              | Wave 103 reports        | Template slugs to surface in /reports.                             |
| ``outreach_templates`` | ``list[str]``              | Wave 98 outreach        | Slugs of starter templates to seed via ``upsert_template``.        |
| ``connectors_hints``   | ``list[str \| dict]``      | W91 connectors UI       | ``"gmail"`` or ``{"id":"gmail","priority":True}``.                 |
| ``welcome_content``    | ``str`` (markdown)         | FE post-install panel   | Rendered immediately after install.                                |
| ``first_run_playbook`` | ``str \| None``            | Runner-deferred         | Recorded as ``first_run_id`` on the install report.                |

## Install lifecycle

1. **Preview** (`POST /api/bundles/{id}/preview`) — dry-run; returns
   the same shape as a real install but touches nothing.
2. **Install** (`POST /api/bundles/{id}/install`) — HIL-gated. Walks
   the bundle, calls collaborator modules (scheduler, outreach,
   receipts), persists a row in
   ``~/.tars/bundles/installed.sqlite``, records a ``bundle.installed``
   receipt via Wave 95.
3. **Use** — operator visits /dashboard. Widgets / schedules /
   templates are already there.
4. **Uninstall** (`POST /api/bundles/{id}/uninstall`) — HIL-gated.
   Removes scheduled jobs created by *this* install (looked up by
   the saved ``schedule_id``). Outreach templates and dashboard
   widgets are *not* purged — they're additive and the operator may
   have hand-edited them.

## Idempotency guarantees

- Re-installing a bundle for the same ``(bundle_id, org_id)`` reuses
  the existing ``install_id`` and refreshes ``finished_at`` /
  items snapshot. The report's ``warnings`` carries
  ``already_installed`` so the FE can adjust copy.
- Scheduler create-schedule is idempotent on
  ``(playbook_id, cron_expression)`` — duplicate entries are reused,
  not stacked.
- Outreach starters use ``upsert_template`` keyed on slug.
- Receipts are append-only; re-install records a fresh
  ``bundle.installed`` event tagged ``already_installed=True`` so
  the audit trail stays honest.
- Failures inside a sub-step (scheduler off, missing playbook,
  connector store unreachable) become **warnings** on the report —
  the install never raises. The operator gets to retry.

## Built-in bundles (7)

| Bundle                  | Org-type        | Playbooks | Schedules | Widgets | First-run                          |
| ----------------------- | --------------- | --------- | --------- | ------- | ---------------------------------- |
| ``vc_fund_bundle``      | vc_fund         | 5         | 2         | 5       | fund/portfolio_monitoring          |
| ``hedge_fund_bundle``   | hedge_fund      | 5         | 1         | 4       | algotrade/mean_reversion_strategy  |
| ``family_office_bundle``| family_office   | 3         | 2         | 3       | family-office/monthly_statement    |
| ``saas_bundle``         | saas            | 4         | 3         | 5       | saas/morning_ops                   |
| ``dao_bundle``          | dao             | 3         | 1         | 3       | dao/treasury_diff                  |
| ``research_lab_bundle`` | research_lab    | 2         | 1         | 3       | saas/morning_ops                   |
| ``other_bundle``        | other           | 6         | 0         | 4       | saas/morning_ops                   |

### vc_fund_bundle
- Playbooks: weekly_lp_report, deal_screening, founder_dd, portfolio_monitoring, tax_memo
- Schedules: LP report Monday 09:00; portfolio monitoring daily 07:00
- Widgets: calendar-today, gmail-unread, recent-receipts, active-cohorts, hil-inbox
- Reports: lp_quarterly_update, portfolio_audit_pack, deal_screening_memo
- Outreach: lp_update, founder_dd, intro, follow_up, welcome_lp
- Connectors: gmail (priority), calendar, slack

### hedge_fund_bundle
- Playbooks: mean_reversion_strategy, momentum_breakout_strategy, live_paper_session, backtest_to_live_pipeline, risk_audit_weekly
- Schedules: risk audit Monday 08:00; live paper session manual-start
- Widgets: backtest-summary, recent-receipts, hil-inbox, calendar-today

### family_office_bundle
- Playbooks: monthly_statement, kyc_refresh, compliance_pack
- Schedules: statement 1st of month 09:00; KYC every 3 months
- Widgets: wallet-balance, recent-receipts, calendar-today

### saas_bundle
- Playbooks: morning_ops, churn_alert, outreach_loop, pr_review
- Schedules: morning ops 08:30 weekdays; churn alert daily 09:00; PR review every 15min weekdays
- Widgets: github-prs, slack-mentions, gmail-unread, playbook-runs, recent-receipts
- Connectors: github (priority), slack, gmail

### dao_bundle
- Playbooks: treasury_diff, proposal_summarize, contributor_recognition
- Schedules: treasury daily 08:00
- Widgets: wallet-balance, recent-receipts, active-cohorts

### research_lab_bundle
- Mixed pack: saas/morning_ops, fund/founder_dd
- Widgets: github-prs, calendar-today, recent-receipts

### other_bundle
- Generic top-6 playbook sample across all packs
- No schedules — manual exploration
- Widgets: calendar-today, gmail-unread, recent-receipts, playbook-runs

## Authoring a custom bundle

1. Construct a ``Bundle(...)`` in
   ``backend/core/bundles/definitions.py`` (or its own module that's
   imported there).
2. Append the new instance to ``BUILTIN_BUNDLES``.
3. Optionally register a new ``org_type`` in ``models.ORG_TYPES`` so
   ``bundle_for_org_type`` can recommend it.
4. Add a Cmd+K command in ``GlobalCommandPalette.tsx`` so operators
   can preview it directly.
5. Drop a unit test in ``tests/test_bundles_install.py`` verifying
   the preview shape.

## REST surface

```
GET    /api/bundles                    # list builtins (?org_type= for recommended)
GET    /api/bundles/installed          # installs (?org_id= filter)
GET    /api/bundles/{id}               # single bundle
POST   /api/bundles/{id}/preview       # dry-run InstallReport
POST   /api/bundles/{id}/install       # HIL-gated install
POST   /api/bundles/{id}/uninstall     # HIL-gated cleanup
```

The ``/installed`` route is defined before ``/{bundle_id}`` so the
FastAPI matcher resolves it as a literal, not a parametric match.

## Storage

- ``~/.tars/bundles/installed.sqlite`` — install registry (override
  via ``TARS_BUNDLES_DB_PATH``).
- One UNIQUE row per ``(bundle_id, org_id)`` — installer uses
  ``ON CONFLICT … DO UPDATE`` for idempotency.

## Receipts

Every install / uninstall fires a Wave 95 receipt:

- ``bundle.installed`` — actor=``org:<org_id>``, resource=bundle_id,
  payload contains counts + first_run_id + ``already_installed``.
- ``bundle.uninstalled`` — same actor / resource, payload contains
  install_id.

These are hash-chained into the unified receipt ledger.
