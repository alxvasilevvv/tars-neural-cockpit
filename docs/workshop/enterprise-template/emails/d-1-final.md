# D-1 — final logistics

**Subject:** Tomorrow: The {WORKSHOP_NAME} — final logistics

---

Hi {FIRST_NAME},

Tomorrow's the day. Quick rundown of everything you need.

## When and where

- **Start:** {START_TIME} sharp. Doors at {DOORS_OPEN_TIME} for
  coffee and any last-minute install help.
- **Location:** {LOCATION}. Building entry is via {ENTRY_NOTES}.
  Ask for the {COMPANY_NAME} workshop at reception.
- **Dial-in (record-only):** {ZOOM_URL}. We don't expect remote
  attendees but the link is there if you have to step out.

## What to bring

- **Laptop with TARS installed** — see the D-7 email if you
  skipped pre-work. Charger too; outlets at every seat but power
  bricks save time.
- **Your CSV data** — OHLCV for the instruments your strategy
  touches. If your data is on a corporate share you can't reach
  from your laptop, copy a sample to disk tonight.
- **One strategy idea** you want to ship by end of Day 2.
  Written down somewhere you can read — a doc, a notebook, even
  a napkin. Don't try to remember it on the drive in.

## Pre-flight check (5 min, do this tonight)

1. Open `http://localhost:{TARS_PORT}/workshop/enterprise` in your
   browser. You should see the cohort landing page.
2. Check `http://localhost:{TARS_PORT}/health` — the response
   block should be all green. If anything is amber or red, ping
   `#install-help` on Slack tonight, not tomorrow.
3. Test your wallet connection: cockpit → Settings → Wallet →
   "Test connection". This step is optional for paper trade but
   required for the on-chain audit anchor on Day 2.

## Day 1 schedule

| Time | Segment |
| --- | --- |
| {T_0900} | Welcome, intros, room setup |
| {T_0945} | Intake — your data into TARS |
| {T_1100} | Break |
| {T_1115} | Strategy Design — IR walkthrough + first draft |
| {T_1230} | Lunch ({LUNCH_PLACE_OR_CATERED}) |
| {T_1330} | Strategy Design continued — your strategy on paper |
| {T_1500} | Break |
| {T_1515} | Backtest — run, read, interpret |
| {T_1645} | Day 1 wrap + tonight's homework |
| {T_1700} | Close |

Two Q&A windows, one before lunch and one before close. Save
deeper questions for Slack — we read it through the evening.

## Slack channel

`#{WORKSHOP_SLUG}-workshop-{COHORT_TAG}` is live. Use it for in-room
questions you don't want to interrupt the room with — the floor
person watches it on a side monitor and will come find you.

See you tomorrow.

— {FACILITATOR_NAME}
