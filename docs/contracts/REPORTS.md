# REPORTS contract — Wave 103

Contract version: **1.0**.

The reports module generates PDF / PPTX / XLSX / DOCX artefacts from
operator-supplied inputs + a template. Built on top of Wave 95
(receipts), Wave 97 (scheduler), Wave 98 (outreach) and Wave 90
(webhooks).

## Surfaces

- HTTP router: `web_extras/routers/reports.py` (mounted at
  `/api/reports`).
- Backend module: `backend/core/reports/`.
- Frontend page: `experiments/neural-showcase-v3/src/pages/Reports.tsx`
  served at `/reports`.

## Persistence

SQLite at `~/.tars/reports.sqlite` (override via
`TARS_REPORTS_DB_PATH`; disable the entire module with
`TARS_REPORTS_STORE=disabled`). Rendered files live under
`~/.tars/reports/<run_id>.<ext>` (override via
`TARS_REPORTS_OUTPUT_DIR`).

## Template schema

Each `ReportTemplate.schema` is a dict of
`field_name -> { type, label, required?, description?, default?, items? }`.

`type` is one of: `string`, `number`, `int`, `boolean`, `array`,
`object`. `items` is the inner type for `array` (or a nested schema
for `object`). The FE auto-generates form inputs from the schema;
unknown / nested shapes degrade to a JSON textarea.

## Built-in templates

Six templates ship out of the box (slug + kind + use case):

| slug                    | kind | use case                                  |
|-------------------------|------|-------------------------------------------|
| `lp_quarterly_update`   | pptx | 8-slide deck for fund LPs                 |
| `board_meeting_pack`    | pdf  | 10-page board pre-read                    |
| `monthly_kpi_dashboard` | xlsx | 5-sheet operating workbook                |
| `portfolio_audit_pack`  | pdf  | one page per portfolio company            |
| `deal_screening_memo`   | docx | VC founder review writeup                 |
| `incident_postmortem`   | docx | blameless tech postmortem                 |

Built-in slugs cannot be shadowed by custom templates; the router
returns HTTP 409 on conflicting POSTs.

## Creating a custom template

```http
POST /api/reports/templates
Content-Type: application/json

{
  "name": "Weekly investor digest",
  "slug": "weekly_investor_digest",
  "kind": "docx",
  "schema": {
    "week": { "type": "string", "required": true, "label": "Week" },
    "wins": { "type": "array", "items": "string", "label": "Wins" }
  },
  "description": "Short 1-page weekly digest for active LPs.",
  "template_path": ""
}
```

## Skill dependencies

The renderer dispatches by `kind` to a pluggable skill hook
(`set_skill_hook`). Recommended host renderers:

- **pptx** → python-pptx (or the Anthropic pptx skill).
- **docx** → python-docx (or the Anthropic docx skill).
- **xlsx** → openpyxl (or the Anthropic xlsx skill).
- **pdf**  → reportlab (or the Anthropic pdf skill).

When no hook is mounted, the fallback renderer writes a deterministic
plain-text body so the lifecycle never gets stuck in `rendering`.

## Lifecycle

`pending → rendering → done` (terminal) or
`pending|rendering → failed` on error. Every successful render emits
a Wave 95 receipt of type `report.generated`.

## Scheduling

`POST /api/reports/schedule` registers a Wave 97 schedule whose
playbook id is `report:<template_id>`. The scheduler runner can
dispatch into `backend.core.reports.scheduling.fire_scheduled_report`
to resolve the inputs provider and call `render` with FRESH data.

Built-in providers:

- `reports.providers.fund_quarterly` — for `lp_quarterly_update`.
- `reports.providers.monthly_kpis` — for `monthly_kpi_dashboard`.
- `reports.providers.portfolio_snapshot` — for `portfolio_audit_pack`.

Register additional providers via
`backend.core.reports.providers.register_provider`.

## Delivery

Three channels:

1. **outreach** — drafts an email per recipient via Wave 98.
2. **webhook** — POSTs `report.generated` to outgoing webhooks.
3. **download** — `GET /api/reports/runs/{id}/download` streams the
   bytes.

`POST /api/reports/runs/{id}/send` is HIL gated when
`TARS_REQUIRE_OPERATOR_CONFIRM=1`.

## Privacy

Rendered files stay on the local disk. No bytes leave the host
unless an operator explicitly hits `send` (outreach) or a webhook
endpoint subscribes. Cloud upload is opt-in via the vault module.

## Receipts

Successful renders emit `report.generated` receipts with
`{ template_slug, kind, output_path }` payloads. The Wave 95 hash
chain anchors each daily Merkle root on Solana when the anchor is
configured.
