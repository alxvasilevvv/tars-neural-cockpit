# SaaS vertical — workshop starter pack

Four playbooks for SaaS founders running an early-stage company. The set
covers daily ops, churn surveillance, outbound, and code review with the
operator's voice.

## Playbooks

| File | Teaches | Phase |
| ---- | ------- | ----- |
| `morning_ops.json` | Calendar + GitHub stand-up + Slack digest at 08:30 daily. | deploy |
| `churn_alert.json` | Daily entrepreneur churn alert that pages the CS channel only when there's risk. | deploy |
| `outreach_loop.json` | Generate per-contact outreach drafts and stage them for human review. | build |
| `pr_review.json` | Wrap GitHub diff fetch + automated review + AI Clone restyle into one trace. | build |

## Fork instructions

1. Copy any file out of `_workshop/saas/` into your own pack directory.
2. Rewrite `id` so it doesn't collide with the workshop pack
   (e.g. `acmesaas.morning_ops`).
3. For scheduled playbooks, edit `_meta.schedule` (the cron field) for
   your timezone.
4. Confirm referenced actions exist in your environment by running
   `jarvis playbooks validate <path>` (or hitting the validator endpoint).
5. Reload playbooks from the cockpit.

## Suggested workshop order

1. Wire `morning_ops.json` first — every founder feels its value within a
   single day.
2. Build `pr_review.json` together so attendees understand the AI Clone
   loop.
3. Deploy `churn_alert.json` and `outreach_loop.json` as scheduled
   surface-level wins.
