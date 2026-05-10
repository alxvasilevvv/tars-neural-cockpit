# Cresco Capital — "Algorithmic Edge" workshop kit

This folder is the operational package for the Cresco Capital
"Algorithmic Edge" workshop: a two-day in-person session bracketed
by a five-day attendee journey (D-7 invite through D+7 follow-up).
Everything an attendee receives by email and everything the
facilitator runs from lives in this folder.

The workshop sits one layer above the generic B2B engagement
described in `docs/B2B_WORKSHOP.md`. Where that doc covers the
four-vertical starter pack and the install-to-deploy arc, this kit
is the Cresco-specific cohort: quant operators bringing live or
soon-to-be-live strategies into TARS, with backtest + risk policy +
paper-trade + audit as the spine of the curriculum.

## Schedule

- **D-7** — invite goes out, pre-work assigned (~30 min install + smoke test).
- **D-3** — pre-read sent (three short articles).
- **D-1** — final logistics email.
- **D-1 through D-2** — two consecutive working days, in-person, 8 hours each.
- **D+1** — recap email + Day 2 prep.
- **D+7** — one-week follow-up + soft ask for a quote.

Day 1 covers Intake, Strategy Design, and Backtest. Day 2 covers
Risk Policy, Paper Trade, Audit, and the promotion gate that takes
a strategy from sandbox to a paper-traded signal feed.

## Audience

The cohort is drawn from three Cresco-adjacent communities:

- **CARF** — Cresco Algorithmic Research Fellows. Mostly junior
  quants with one or two strategies they want to harden into a
  research-grade workflow.
- **3V** — Cresco's "Three Verticals" group: discretionary PMs who
  are starting to systematize a piece of their book and need
  guardrails (risk policy, kill switch, audit) before they ship.
- **Crypto Fund quants** — operators running 24/7 mandates who care
  most about paper-trade telemetry, on-chain anchoring of receipts,
  and a defensible compliance trail.

Cohort size is capped at 12. Mixed-discipline by design — the
risk-policy and audit segments work better when a discretionary PM
is in the room asking the questions a junior quant doesn't yet know
to ask.

## Expected outcomes

By end of Day 2, every attendee should walk out with:

1. One strategy expressed as a Strategy IR (intermediate
   representation) checked into their own pack.
2. A backtest with Sharpe / Sortino / PF reported and a written
   one-paragraph interpretation.
3. A risk policy template configured and dry-run against the
   strategy.
4. A paper-trade session running on real market data, emitting
   receipts to the audit ledger.
5. A clear understanding of the promotion gate — what has to be
   true before a strategy moves from paper to live capital.

We do not promise live capital deployment by end of Day 2. Anyone
selling that timeline to quants is selling a fantasy.

## Files in this folder

- `README.md` — this file.
- `emails/d-7-welcome.md` — invite + pre-work.
- `emails/d-3-pre-read.md` — three articles + optional reading.
- `emails/d-1-final.md` — final logistics + Day 1 hour-by-hour.
- `emails/d+1-day-1-recap.md` — Day 1 recap + Day 2 prep.
- `emails/d+7-followup.md` — one-week check-in.
- `facilitator-runbook.md` — internal runbook for whoever is
  running the workshop (T-7 through D+7).
- `feedback-survey.md` — end-of-workshop survey (5–7 questions).

All emails use `{CURLY_BRACE}` placeholders for facilitator-filled
fields (date, location, Zoom URL, Slack URL, etc.). Facilitators
fill these in before sending — no template engine, no automation,
deliberate friction so nothing goes out wrong.

## Tone

Match the existing `docs/B2B_WORKSHOP.md` register: technical,
measured, no oversell. Quants notice marketing language faster
than most audiences and hold it against the speaker. Honest framing
about what TARS does and does not do is the through-line for every
email and every facilitator script in this kit.
