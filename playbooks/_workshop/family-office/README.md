# Family-office vertical — workshop starter pack

Three playbooks for a family office: a monthly consolidated statement,
a 90-day KYC refresh, and a compliance pack for the accountant.

## Playbooks

| File | Teaches | Phase |
| ---- | ------- | ----- |
| `monthly_statement.json` | Multi-chain wallet snapshot → consolidated statement → PDF render via the `pdf` skill. | deploy |
| `kyc_refresh.json` | 90-day KYC sweep behind a HIL prompt before sending request emails. | deploy |
| `compliance_pack.json` | Bundle receipts + audit export into a single archive for the accountant. | build |

## Fork instructions

1. Copy a file into your own pack (e.g. `playbooks/myoffice/monthly_statement.json`).
2. Rename the `id` and adjust `pack`.
3. For multi-chain playbooks, configure wallet env keys per chain
   (Solana, EVM, TON).
4. Confirm the `pdf` skill is installed and the operator has provided
   the `family_office_statement_v1` template (or swap in your own).
5. Validate: `python3 -c "import json; json.load(open('<path>'))"`.

## Suggested workshop order

1. Run `monthly_statement.json` interactively so attendees see the PDF
   land in the cockpit.
2. Walk through `kyc_refresh.json` and explain the HIL prompt — this is
   the single most-quoted feature in family-office demos.
3. Schedule `compliance_pack.json` quarterly and tie it back to the
   receipt ledger model.
