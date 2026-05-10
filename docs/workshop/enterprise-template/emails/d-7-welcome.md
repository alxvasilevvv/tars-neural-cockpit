# D-7 — welcome + pre-work

**Subject:** You're in: The {WORKSHOP_NAME} — your prep + setup

---

Hi {FIRST_NAME},

You're confirmed for the {COMPANY_NAME} "{WORKSHOP_NAME}"
workshop. This email has everything you need to show up ready on
day one.

## Logistics

- **Dates:** {DATE_DAY_1} and {DATE_DAY_2}, 09:00–17:00 local.
- **Location:** {LOCATION}.
- **Dial-in (for the few segments we record):** {ZOOM_URL}.
- **Cohort Slack:** {SLACK_URL} — please join before D-3, that's
  where pre-read questions get answered.

## Two-day agenda preview

**Day 1 — Intake, Design, Backtest.** We start by getting your
data into TARS and translating one of your strategy ideas into a
Strategy IR. Afternoon is backtest: running, reading the
metrics, and writing a one-paragraph interpretation of what you
saw.

**Day 2 — Risk, Paper Trade, Audit.** Morning is risk policy
templates and the dry-run pass. Afternoon is paper trade against
live market data, the receipts ledger, and the promotion gate
that decides whether a strategy graduates from sandbox.

## Pre-work — about 30 minutes

Please complete this before D-3 so we can resolve install issues
asynchronously instead of burning your morning on day one.

1. Install TARS:

   ```
   curl tars.meeet.world/install.sh | bash
   ```

   The installer runs a smoke test at the end — paste the output
   into Slack `#install-help` if anything fails. Mac and Linux
   are both supported; Windows attendees, please reach out and
   we'll get you on WSL2 ahead of time.

2. Open `http://localhost:{TARS_PORT}/health` in your browser and
   confirm the response is green.

3. Run one canned backtest end-to-end so the path is warm:

   ```
   tars workshop precheck --pack {WORKSHOP_PACK}
   ```

   If that command exits 0, you're set.

## What to bring

- **Your laptop**, with the install above completed.
- **Your data** — CSV preferred. OHLCV for the instruments your
  strategy touches, ideally a year or more of history. If your
  data is sensitive, that's fine — TARS runs locally and nothing
  leaves your machine without an explicit prompt.
- **One strategy idea** you want to ship by end of Day 2. It
  doesn't have to be the strategy you make money on. Pick one
  that's simple enough to express in a few rules but real enough
  that the backtest tells you something.

## Expectations

This is a working session, not a lecture series. You'll spend
more time at your keyboard than watching slides. We don't promise
live capital deployment by end of Day 2 — that's a longer arc
that depends on your firm's controls. We do promise you'll leave
with a paper-traded strategy and an audit trail you can show your
risk committee.

Reply to this email with any questions, or drop them in
`#workshop-questions` on Slack.

— {FACILITATOR_NAME}
{FACILITATOR_EMAIL} · {COMPANY_NAME} "{WORKSHOP_NAME}"
