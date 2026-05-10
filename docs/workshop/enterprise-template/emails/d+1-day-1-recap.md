# D+1 — Day 1 recap + Day 2 prep

**Subject:** Day 1 recap + Day 2 prep

---

Good evening,

Yesterday you shipped **{N_STRATEGIES_DESIGNED}** strategies in
Strategy IR form and ran **{N_BACKTESTS}** backtests across the
room. That's a heavier first-day output than most cohorts — well
played.

## Yesterday's call-outs

A few blockers came up that are worth naming so you don't hit
them tomorrow:

- {BLOCKER_1_PLACEHOLDER} — workaround: {WORKAROUND_1}.
- {BLOCKER_2_PLACEHOLDER} — workaround: {WORKAROUND_2}.
- {BLOCKER_3_PLACEHOLDER} — fixed in tonight's sidecar push,
  please re-run `tars sidecar restart` before tomorrow morning.

If your name was on a blocker that didn't make this list, ping
`#{WORKSHOP_SLUG}-workshop-{COHORT_TAG}` and we'll address it at the
morning standup.

## Day 2 morning

We start at {DAY_2_START_TIME}. The morning is the four pieces
that turn a backtested strategy into something a risk committee
will sign off on:

1. **Risk policy** — pick a template, configure it for your
   strategy, dry-run it.
2. **Paper trade** — connect to live market data, start the
   paper session, watch receipts land in the ledger.
3. **Audit** — walk the receipts ledger, anchor a batch on-chain.
4. **Promotion gate** — the explicit checklist a strategy has to
   clear before it leaves the sandbox. Most attendees will find
   their strategy fails at least one item on first read; that's
   the point.

## Action items for tonight

Before you log off:

1. **Pick your favorite strategy from yesterday.** Not the
   prettiest backtest — the one you'd actually want to paper-
   trade tomorrow. We'll work that one through Day 2.
2. **Configure the risk policy template** — start from
   `templates/risk_policy.basic.json` in your pack. Don't try
   to be clever; copy the defaults and adjust caps to your
   strategy's exposure profile.
3. **Prep your paper-trade test data** — the live data feed
   covers the major venues by default. If your strategy needs an
   instrument outside the default universe, add it to
   `paper_trade.universe` tonight so we don't burn morning time
   on it.

## Office hours tonight

{OFFICE_HOURS_TIME} on the cohort Zoom ({ZOOM_URL}). Drop in if
you're stuck on any of the action items above. Optional — most
people won't need it — but the door is open.

See you in the morning.

— {FACILITATOR_NAME}
