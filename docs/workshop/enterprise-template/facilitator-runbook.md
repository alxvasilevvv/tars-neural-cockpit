# {COMPANY_NAME} "{WORKSHOP_NAME}" — facilitator runbook

This is the internal runbook for whoever is running a {COMPANY_NAME}
"{WORKSHOP_NAME}" cohort. It covers everything from T-7 days
through D+7, plus the common questions and the failure modes
we've hit before. Read it once before your first cohort and skim
it again the morning of D-7.

The runbook assumes one facilitator and one floor person for a
12-person cohort. If you're solo, drop the per-attendee laptop
checks on D-1 morning to a coffee-break sweep instead of a full
pass — you'll need the time elsewhere.

## T-7 days

- **Send the D-7 email** (`emails/d-7-welcome.md`). Fill the
  placeholders before sending. Use BCC, not To-all — quants are
  unusually sensitive about their email being on a visible list
  of attendees.
- **Confirm Slack workspace and cohort channel** are created.
  Channel naming convention: `#{WORKSHOP_SLUG}-workshop-{COHORT_TAG}`
  where `{COHORT_TAG}` is `YYYY-MM` of Day 1.
- **Confirm Zoom link** is generated and recording is set to
  cloud + auto-transcript. Test the dial-in from a phone — at
  least one Zoom link per quarter ships broken.
- **Send the pre-read links to the dev team** for review. The
  three articles (`STRATEGY_IR.md`, `RISK_POLICY_PATTERNS.md`,
  `METRICS_PRIMER.md`) drift between releases; verify they
  still describe the version of TARS you'll demo.
- **Verify each attendee's pre-work confirmation** by D-5. Ping
  anyone who hasn't installed yet — give them three days, then
  call them on D-3.

## T-3 days

- **Send the D-3 email** (`emails/d-3-pre-read.md`).
- **Do a full dry-run of every demo** you'll show. The hour
  this takes will save you twice that on the day. The demo
  matrix is: Intake CSV → Strategy IR → Backtest → Risk policy
  configure → Paper trade start → Audit anchor.
- **Verify CF Pages green** at `tars.meeet.world/workshop/enterprise`.
  If it's not, kick the build and watch it land before you stop
  paying attention.
- **Verify backend reachable**: `/health` returns green from your
  laptop on the venue's expected network. If you've never been
  to the venue, ask for the guest Wi-Fi creds today, not on D-1.

## T-1 day

- **Send the D-1 email** (`emails/d-1-final.md`). Hour-by-hour
  schedule placeholders filled in.
- **Set up the venue.** Tables in pods of four. Power strips at
  every pod, not every seat — every-seat power is a luxury that
  takes setup time you don't have. One spare laptop on the
  facilitator table for the inevitable dead battery.
- **Arrive at the venue 1 hour early** for setup. Test screen-
  share from your laptop on the venue projector with the actual
  HDMI/USB-C cable you'll use, not the venue's "should work"
  promise.
- **Prepare a backup hotspot.** Phone tether is fine. Venue
  Wi-Fi has failed at two of the last six cohorts; you do not
  want to discover this on the first segment.

## D-1 morning (Day 1)

- **Arrive 30 minutes before doors.** Coffee setup, name tags
  on the table, projector on, Slack pinned on the side monitor.
- **Network check.** Run `tars workshop precheck --pack {WORKSHOP_PACK}`
  on the facilitator laptop on the venue Wi-Fi. If anything is
  amber, switch the room to the hotspot before doors open.
- **Attendee laptop checks during coffee.** Walk the room with
  the floor person; ask each attendee to open `/health` and
  show you green. Anyone red gets paired with the floor person
  for the first 30 minutes.
- **Pair people who need help.** Quants do not enjoy publicly
  asking for help. Pre-pair anyone whose pre-work failed with
  the floor person before the room sees who is struggling.

## D-1 schedule with talking points

**09:00 — Welcome, intros, room setup (45 min).** Round of
intros: name, firm, the strategy idea you brought. Keep each
intro under 90 seconds — it's a working session, not a
networking event. Cover the safety rails: kill switch, the
sidecar, the fact that nothing leaves their laptop.

**09:45 — Intake (75 min).** Walk through the canonical CSV
shape, then have everyone import their own. The trap here is
attendees with non-OHLCV data (alt data, factor zoo exports);
they need a custom adapter and the floor person should pull them
aside while the rest of the room moves on.

**11:15 — Strategy Design (75 min, then break, then 90 min).**
Strategy IR walkthrough on the projector first. Then everyone
drafts their own. The trap here is over-ambition — first-time
quants try to express their full system in IR and stall. Push
them to ship a thin slice: one signal, one entry rule, one exit.

**13:30 — Strategy design continued.** Most attendees will
finish their first IR by 14:30. Use the remaining time for
peer review in pods.

**15:15 — Backtest (90 min).** Run, read, write the
one-paragraph interpretation. This is where the "metrics primer"
pre-read pays off — if attendees skipped it, they'll spend half
the segment asking what Sortino measures.

**16:45 — Day 1 wrap.** Read tonight's homework off the
projector (it's also in the D+1 email but they'll forget). Do
not let the wrap run long; people are tired.

## D-2 morning (Day 2)

- **Review yesterday's strategies.** Ten minutes at the start,
  on the projector, looking at three or four strategies the
  cohort wants to discuss. Ask permission first; some attendees
  won't want their work shown.
- **Risk policy session.** Walk the five patterns from the
  pre-read, then everyone configures one for their strategy.
  Floor person watches for the attendee who silently sets all
  caps to infinity — that's the pattern that breaks paper trade
  on first run.
- **Paper trade demo.** Start the facilitator's reference
  strategy on the projector. Watch the first receipts land in
  the ledger. Then everyone starts their own.
- **Audit segment.** Walk the receipts ledger, anchor a batch
  on-chain. Some attendees will skip the on-chain anchor for
  internal-policy reasons; that's fine, they can still anchor to
  a local hash chain.
- **End-of-workshop ceremony.** Five minutes. Hand out the
  cohort badge (or email it post-event). Collect the feedback
  survey on paper if you can — paper has higher response rate
  than the digital version.

## D+1

- **Send the recap email** (`emails/d+1-day-1-recap.md`). Note
  that the file is named `d+1` for the recap of Day 1; for a
  two-day workshop the recap goes out the morning of Day 2 if
  you're running a different cadence, or the morning after Day
  2 if you are running the standard cadence and treating "Day
  1 recap" as the morning-after summary of the whole prior day.
  Pick one and stick to it — don't switch mid-cohort.
- **Post Day-1 highlights to Slack.** A short message in
  `#{WORKSHOP_SLUG}-workshop-{COHORT_TAG}`: total backtests run, a few
  named call-outs (with permission), and the link to office
  hours.
- **Schedule individual office hours.** Default to 30 minutes
  per attendee within the next two weeks. Most won't book; the
  ones who do are the ones most likely to convert into long-term
  TARS users, so prioritize their time.

## D+7

- **Send the follow-up email** (`emails/d+7-followup.md`).
- **Send the feedback survey** (`feedback-survey.md`) if you
  didn't collect it on paper at the workshop.
- **Read the survey responses within 48 hours of receipt.** Any
  pattern across 3+ responses goes into the next cohort's
  pre-read or schedule. Don't let feedback rot in a folder.

## Common attendee questions + answers

**"Does my data leave my machine?"** No. TARS runs locally;
all backtests, paper trades and audit anchors happen on your
laptop. The on-chain anchor posts only a hash of the receipt,
never raw data. The meeet.world relayer is opt-in and used only
for paid skills, none of which the workshop touches.

**"Can I keep using TARS after the workshop?"** Yes. The
workshop install is the standard install. After 90 days the Pro
tier comp expires and you either convert to standard pricing or
fall back to Free, with your strategies and ledger intact.

**"What if I want live execution?"** Live execution lands in
v9.2 (current ETA in `docs/ROADMAP.md`). For the workshop and
the immediate aftermath, paper trade is the supported mode.
Anyone running live capital today is doing it via their existing
broker integration with TARS as the signal source.

**"How is this different from Backtrader / vectorbt / quantlib?"**
TARS is not a backtest library. It is an operator platform that
includes a backtester. The interesting part is the spine that
goes Strategy IR → backtest → risk policy → paper trade → audit
ledger → promotion gate, with receipts at every step. If you
want a faster backtester, use vectorbt and pipe the results into
TARS.

**"Can I use my own LLM?"** Yes. Settings → LLM provider. We
support Anthropic, OpenAI, Gemini, Ollama and any
OpenAI-compatible endpoint. None of the strategy logic uses an
LLM by default; the LLM is for the assistant layer.

## Things that have gone wrong before

**TARS sidecar crashes mid-segment.** The sidecar emits a
heartbeat to the cockpit; when the heartbeat stops the cockpit
shows an amber pill. Resolution: `tars sidecar restart`. If it
crashes twice in a session, ask the attendee for the sidecar
log (`~/Library/Logs/tars/sidecar.log` on Mac) and pull them
aside — they almost certainly have a corrupt local DB.

**Wifi dies for the room.** Switch to the hotspot (you brought
one, see T-1). The paper-trade segment needs internet for the
market data feed; everything else can run offline. If both fail,
swap the schedule and do the audit segment first — it's the
most internet-tolerant segment.

**"My CSV is too big."** Files over ~500 MB choke the default
intake path. Tell the attendee to chunk by date range, or use
the parquet adapter (`tars data import --format parquet`). For
truly huge data (multi-GB tick data), suggest they downsample
to bars for the workshop and revisit tick later.

**Attendee laptop won't run TARS.** Old Macs without AVX2 hit
this. Pair them with another attendee for the workshop and
follow up with a remote-cockpit setup post-workshop so they can
keep using it from a phone or tablet.

**Strategy IR rejected by the validator.** Most often a bad
schema version pin. Check the IR's `schema_version` matches the
TARS install — workshop materials sometimes lag a release. If
the validator error is unhelpful, the floor person can pull the
attendee aside for a five-minute hand-fix; don't let it block
the room.

**Risk policy with all caps set to infinity.** Discussed above.
The paper-trade segment will kill the strategy within 30 seconds
of start because the position-sizing calc divides by zero
somewhere downstream. Catch this in the risk policy segment, not
in paper trade.

**On-chain anchor fails.** Attendee's wallet isn't funded, or
the network is congested. Skip on-chain for that attendee and
let them anchor locally; they can do the on-chain anchor at home
once their wallet is sorted. Don't burn group time on it.
