# Fund vertical — workshop starter pack

Five playbooks for VC partners. Together they cover the weekly LP report
loop, deal screening, founder due diligence, daily portfolio monitoring,
and a quarterly tax memo.

## Playbooks

| File | Teaches | Phase |
| ---- | ------- | ----- |
| `weekly_lp_report.json` | Compose & email the weekly LP report from KPI snapshot + filtered daily brief. | deploy |
| `deal_screening.json` | Drive an agent to score a pitch deck across 12 dimensions and anchor the verdict on Solana. | build |
| `founder_dd.json` | Chain a science crossref lookup into entrepreneur lead-scoring and a one-page DD memo. | test |
| `portfolio_monitoring.json` | Daily KPI sweep with delta-threshold alerts. | deploy |
| `tax_memo.json` | Group ledger receipts by tax category and draft a memo for the accountant. | build |

## Fork instructions

1. Copy a file out of `_workshop/fund/` into your own pack directory, for
   example `playbooks/myfund/weekly_lp_report.json`.
2. Replace the `id` prefix with your pack slug (e.g. `myfund.weekly_lp_report`).
3. Adjust `_meta.schedule` to match your timezone and cadence.
4. Replace placeholder env keys (`LP_DISTRIBUTION_LIST`, `PARTNER_EMAIL`, …)
   with real values in `.env`.
5. Validate the file: `python3 -c "import json; json.load(open('<path>'))"`.
6. Reload playbooks from the cockpit (Settings → Playbooks → Reload) or
   restart the backend.

## Suggested workshop order

1. Run `founder_dd.json` interactively (test phase) so attendees see one
   complete trace front-to-back.
2. Build `deal_screening.json` with attendees so they understand
   agent-driven scoring + anchoring.
3. Deploy `weekly_lp_report.json` and `portfolio_monitoring.json` so they
   leave with two scheduled jobs already running on their machine.
4. Use `tax_memo.json` as homework — it forces them to load real
   receipts into the ledger before the next session.
