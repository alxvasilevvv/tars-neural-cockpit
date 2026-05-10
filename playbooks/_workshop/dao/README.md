# DAO vertical — workshop starter pack

Three playbooks for DAO operators. They demonstrate the three loops a
treasury team needs: visibility, governance, and contributor recognition.

## Playbooks

| File | Teaches | Phase |
| ---- | ------- | ----- |
| `treasury_diff.json` | Wallet delta + Solana memo anchor + Discord webhook (every 30 minutes). | deploy |
| `proposal_summarize.json` | Forum-URL ingest into science.summarise and a council vote rationale. | build |
| `contributor_recognition.json` | Weekly leaderboard from receipts, posted as a multisig payout proposal. | deploy |

## Fork instructions

1. Copy a file into your own pack (e.g. `playbooks/mydao/treasury_diff.json`).
2. Rename `id` and update `pack` if you want it surfaced in the picker.
3. Provide the env keys the playbook references:
   - `TREASURY_WALLETS` — comma-separated wallet list.
   - `DISCORD_TREASURY_WEBHOOK` — webhook URL.
   - `MULTISIG_WEBHOOK` — automation endpoint that turns proposals into
     multisig transactions.
4. Validate with `python3 -c "import json; json.load(open('<path>'))"`.

## Suggested workshop order

1. Demo `treasury_diff.json` first — operators immediately see the
   anchored memo on Solana explorer.
2. Walk through `proposal_summarize.json` interactively with a real
   forum URL.
3. Schedule `contributor_recognition.json` and pair it with the receipts
   ledger walkthrough.
