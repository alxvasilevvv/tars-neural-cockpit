# B2B Workshop — operator onboarding for funds, SaaS founders, DAOs and family offices

The TARS B2B Workshop is a four-phase, six-hour engagement that takes a
small team (2–10 operators) from "first install" to "scheduled
playbooks running on real data" inside a single working day. It exists
because the cold-start problem for an agent platform is not the install
flow — it is the moment after install, when an operator has to imagine
what to automate and assemble it without reference material.

The workshop hands them fifteen ready-to-fork playbooks across four
verticals, walks through each one, and leaves them with at least one
scheduled job hitting their own data before they go home.

## Audience

The workshop is shipped in four flavors, one per vertical. The starter
playbook packs live under `playbooks/_workshop/<vertical>/`.

- **Funds** — VC partners and analysts who want a weekly LP report,
  deal screening, founder DD, portfolio monitoring, and quarterly tax
  memos. Five playbooks, optimized for a small partnership (1–4
  partners + 1–2 analysts).
- **SaaS founders** — early-stage CEOs running a 5–25 person team,
  juggling calendar, GitHub, Slack, churn surveillance, outbound, and
  PR review. Four playbooks, focused on the daily ops loop.
- **DAOs** — operators of treasury and governance: treasury delta with
  on-chain anchor, proposal summarization, and contributor recognition
  payouts. Three playbooks, designed to be transparent by default
  (Discord webhook + Solana memo).
- **Family offices** — multi-chain wallet owners with KYC and
  compliance obligations: monthly consolidated statement (PDF), 90-day
  KYC refresh with HIL gate, and accountant-ready compliance pack.
  Three playbooks.

Total: 15 playbooks. Each is shipped as a JSON document with a
`_meta` block describing vertical, workshop phase (`learn` / `build` /
`test` / `deploy`), what it teaches, and an estimated runtime.

## Workshop format — four phases × 90 minutes each

The workshop is six hours, broken into four 90-minute phases with
short breaks between. Each phase has a single, concrete deliverable.

### Phase 1 — Learn (90 min)

- 30 min: install TARS + log in via meeet.world magic-link.
- 30 min: tour the cockpit (Watch-me-work, receipts ledger, AI Clone,
  pack picker).
- 30 min: open one starter playbook from the operator's vertical and
  walk through every step in the JSON.

**Deliverable:** the operator can read a playbook JSON top-to-bottom
and predict what each step will do.

### Phase 2 — Build (90 min)

- 60 min: fork one starter playbook into the operator's own pack
  (e.g. `playbooks/myfund/`), edit IDs, schedule, and env keys.
- 30 min: validate via the cockpit's Playbooks → Validate panel.

**Deliverable:** at least one custom playbook in the operator's pack,
ready to run.

### Phase 3 — Test (90 min)

- 45 min: trigger the custom playbook in dry-run mode (no SMTP, no
  on-chain anchor) and inspect the trace in Watch-me-work.
- 30 min: backfill or attach real data — for funds, drop in a real
  pitch deck PDF; for DAOs, point at the real treasury wallet.
- 15 min: re-run live and confirm receipts land in the ledger.

**Deliverable:** at least one trace recorded against real data, with
its receipt visible in the ledger.

### Phase 4 — Deploy (90 min)

- 30 min: schedule the playbook (cron) or wire it to a webhook trigger.
- 30 min: configure the alert/notification channel (Slack, email,
  Discord, multisig webhook).
- 30 min: walkthrough of failure modes — kill switch, supervisor budget
  cap, HIL prompt, on_block / on_error semantics.

**Deliverable:** the playbook is running on a real schedule and the
operator knows how to pause / kill / resume it.

## Per-vertical starter pack reference

| Vertical | Folder | Count | Highlight playbook |
| --- | --- | --- | --- |
| Funds | `playbooks/_workshop/fund/` | 5 | `deal_screening.json` — agent-driven 12-dim score with on-chain anchored verdict |
| SaaS | `playbooks/_workshop/saas/` | 4 | `pr_review.json` — GitHub diff + AI Clone styled review comment |
| DAO | `playbooks/_workshop/dao/` | 3 | `treasury_diff.json` — wallet delta + Solana memo + Discord webhook |
| Family office | `playbooks/_workshop/family-office/` | 3 | `monthly_statement.json` — multi-chain consolidated PDF |

Each folder has its own `README.md` documenting what each playbook
teaches and how to fork it.

## Pricing for workshop attendees

- **Workshop fee:** USD 2,400 per seat (max 10 seats per cohort), or
  USD 12,000 flat for an internal team workshop.
- **Pro tier comp:** every attendee gets the Pro tier of TARS
  comp'd for the first 90 days following the workshop. After that
  they convert to standard Pro pricing (USD 49/operator/month) or
  stay on the Free tier with the workshop pack still installed.
- **AI Clone add-on** (USD 19/operator/month) is comp'd for the first
  30 days only — it's optional but every PR-review demo uses it, so
  most attendees adopt it.

Workshop billing flows through meeet.world's usual checkout
(`/billing/workshop`). Comp codes are minted by the brother account
and emailed to attendees the morning of the workshop.

## FAQ

**Does my data leave my machine?** No. TARS runs locally; the
workshop playbooks all execute on the operator's machine. The
meeet.world relayer is only used for paid skills (and is opt-in).
On-chain anchoring posts only a hash of the receipt, never raw data.

**What if my vertical isn't represented?** Pick the closest pack — most
of the operator value is in the playbook *shape*, not the specific
domain. Funds and family-office overlap heavily; SaaS and DAO share
the standup / leaderboard pattern.

**Can we run this remotely?** Yes. The workshop is designed for
in-person delivery but ships clean over Zoom + Cowork sessions. Plan
for one extra 30-minute slot for screen-share / install troubleshooting
if remote.

**Who supports us after the workshop?** Cohort attendees get a Slack
Connect channel for 30 days, plus a 60-minute follow-up call at week
4 to review what's running in production and what fell over.

**Can we white-label the starter packs?** Yes — fork the
`playbooks/_workshop/<vertical>/` directory into your own pack name,
swap the `pack` slug, and the cockpit will surface the new pack to
your team.

**What versions are supported?** Workshop content targets TARS v9.4+
(skill marketplace, ed25519-signed manifests, Workspaces-aware
RBAC). Earlier versions can run the playbooks but won't see the
multi-tenant niceties.

## Operator preparation checklist

Two days before the workshop, attendees receive a setup email asking
them to complete the following so the in-person time is not consumed
by laptop wrangling.

- Install TARS desktop (Mac DMG or Linux AppImage).
- Confirm `tars://` deep-link works from the browser.
- Generate a meeet.world magic-link login and verify the cockpit
  loads with a logged-in session.
- For fund operators: drop one anonymized PDF deck into
  `~/TARS/attachments/` so the deal-screening playbook has data on
  Phase 3.
- For SaaS operators: connect the GitHub connector with a personal
  access token scoped to one repo.
- For DAO operators: ensure they hold the multisig signer key (not the
  treasury key — TARS never asks for the treasury private key).
- For family-office operators: list wallet addresses across SOL, EVM
  and TON in `~/TARS/wallets.txt`. The `monthly_statement.json`
  playbook reads from this file.

A short pre-workshop screen-share (15 minutes) with each cohort is
included in the fee, used purely to verify the checklist and answer
install questions.

## What attendees walk out with

By the end of the day, every attendee has:

1. A running local TARS install with at least three connectors live
   (Calendar / GitHub / wallet for the relevant vertical).
2. One forked playbook in their own pack, scheduled and emitting
   receipts to the ledger.
3. One on-chain anchored memo proving the workshop attendance (this
   doubles as the workshop completion certificate).
4. The vertical's full starter pack installed and visible in the
   cockpit's pack picker, ready for further customization.
5. A 60-day follow-up calendar invite, plus access to a private
   Slack Connect channel with the other cohort members.

## How the workshop is delivered internally

The workshop is run by one facilitator (a TARS engineer) plus one
"floor" person who roams between attendees during build phases. The
ratio is one floor person per five attendees. For cohorts above
five, a second facilitator joins for the Build and Test phases so
nobody is stuck waiting for help while the rest of the room moves on.

Materials handed to attendees:

- A printed quick-reference card with the cockpit shortcuts
  (Cmd+K, Cmd+Shift+Space, Cmd+/) and the ledger-anchor flow.
- A USB stick with the offline TARS installer + the workshop
  starter packs, in case the venue Wi-Fi misbehaves.
- A short PDF cheat-sheet for the validator's error codes (so the
  Build phase doesn't get bogged down in JSON typos).
