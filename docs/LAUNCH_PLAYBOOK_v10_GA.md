# TARS v10.0 GA — Launch Playbook

> **Author:** Claude lane, 2026-05-15 (rc.1 ready, GA T-7 days).
> **Audience:** operator (Alien — you), brother @ meeet.world, any future
> teammate who walks into a release week and needs a sequenced script.
> **Scope:** the seven days before GA, the launch day itself (hour-by-hour),
> the first week post-launch, and the T+30 retrospective gate.
> **Status:** canonical for v10.0 GA. Reuse the structure for v10.1+ with
> deltas appended in `docs/RETRO_v10.0.md` after T+30.
> **Companion docs:** `V10_GA_CHECKLIST.md` (the 30/30 go/no-go),
> `ROADMAP_POST_GA.md` (what we ship next), `OPERATOR_LAUNCH_PLAYBOOK.md`
> (the v9.1.0 predecessor — keep for reference).

This is not a marketing document. It is the operational script for a
single human (you) plus one AI lane to execute a software launch without
forgetting anything that matters.

---

## 0. Single source of truth — three artefacts

Before T-7 anything, confirm these three things exist and are current:

1. **`V10_GA_CHECKLIST.md`** — the 30-item go/no-go. All 30 green or GA does
   not happen.
2. **`scripts/RELEASE-v10.0.command`** — the one-shot release script. Idempotent.
3. **`scripts/FINAL-QA-GATE.command`** — the 8-gate pre-release sanity check.

If any of these are missing, stop and rebuild them. Everything below
assumes they exist.

---

## 1. T-7 days — Code freeze + audit week

**Date target:** 2026-05-15 (today) for a 2026-05-22 GA.

### Goals

- Final rc.1 audit pass: zero P0 bugs open, zero P1 bugs with no owner.
- Brother sync: every external endpoint we depend on is GA-ready or has
  a documented fallback.
- Marketing assets review: every asset that will go live on T-0 exists
  and has been proof-read by a second pair of eyes.
- Code freeze: no merges to `main` after this date except hotfix-grade
  bug fixes (P0/P1 only).

### Checklist

- [ ] Run `bash scripts/FINAL-QA-GATE.command` — all 8 gates green.
- [ ] Walk `V10_GA_CHECKLIST.md` row by row. Mark each `[x]` or `[~]`
      with a reason for any `[~]`.
- [ ] Brother sync call (30 min). Walk:
      `/api/billing/usage_event`, `/api/billing/balance`,
      `/api/billing/topup`, `/api/me`, magic-link auth. Confirm GA-ready
      or flag with documented fallback.
- [ ] Marketing assets review (90 min, second pair of eyes):
      Twitter thread, HN post draft, PH copy, Reddit posts (3), email
      to waitlist, blog post, demo video script.
- [ ] Code freeze announcement in `CURRENT_STATUS.md`. Set
      `STATUS: code-freeze` until tag day.
- [ ] Press kit assembled at `marketing/press-kit-v10/`:
      - 1-pager PDF
      - Logo pack (SVG + PNG, light + dark)
      - 5 product screenshots (Cockpit, Composer, Marketplace, Voice,
        Audit explorer)
      - Founder bio (1 paragraph)
      - Boilerplate company description (50 words)

### Exit gate

All 30 checklist items green OR all `[~]` items have a documented
fallback that the operator (you) can sign off on a yellow-pad piece
of paper.

---

## 2. T-3 days — Press week + embargo briefings

**Date target:** 2026-05-19.

### Goals

- 3 journalists have the pitch under embargo. They can publish at 7 AM
  PT on T-0.
- Demo video uploaded to YouTube unlisted, link in press kit.
- All marketing copy in final review (no more edits after T-1).

### Checklist

- [ ] Press kit final. PDF version mailed to the 3 embargoed journalists
      with the line: "Embargoed until 2026-05-22 14:00 UTC."
- [ ] Demo video uploaded to YouTube as **unlisted**. Caption: "TARS
      v10.0 — AI cockpit for everything not code." Link in press kit.
- [ ] Twitter thread (8 tweets) drafted and queued in @meeet_world's
      Buffer-equivalent. Scheduled for 8 AM PT T-0.
- [ ] HN Show HN post final. Title: "Show HN: TARS — local-first
      AI cockpit for non-code work (open source)." Body in
      `marketing/launch-hn.md`.
- [ ] Product Hunt page final. Hunter confirmed (Alien). Tagline:
      "Cursor for everything not code." Launch date set to 2026-05-22.
- [ ] Reddit drafts ready for: r/LocalLLaMA, r/macapps, r/selfhosted.
      One post per sub, each tailored to the sub's voice.
- [ ] Email to waitlist (~200 users) drafted and queued in
      Mailchimp-equivalent. Subject: "TARS v10.0 is live."
- [ ] Blog post on meeet.world drafted. URL slug: `/blog/tars-v10-ga`.
- [ ] Live demo stream scheduled — calendar invite to the embargoed
      journalists + waitlist top 50. Title: "TARS v10.0 — live walkthrough."

### Exit gate

The three embargo recipients have replied with "received, will publish
at agreed time." If any of them ghost, drop them from the embargo list
and re-allocate the slot to a Reddit post.

---

## 3. T-1 day — Final smoke + tag prep

**Date target:** 2026-05-21.

### Goals

- One last smoke test on a clean machine.
- `.dmg` signed + notarized + stapled. `spctl --assess` returns `accepted`.
- GitHub release in draft, all artifacts attached.
- VS Code `.vsix` uploaded to Marketplace as a draft (publish T-0).

### Checklist

- [ ] On a clean Mac VM, run `bash scripts/SMOKE-TEST.command`. All 60+
      routes 2xx. No regressions.
- [ ] Run `bash scripts/SIGN-AND-NOTARIZE.command` on the rc.1 build.
      Stapler completes. `spctl --assess --type execute /Applications/TARS.app`
      returns `accepted: source=Notarized Developer ID`.
- [ ] GitHub release draft created at `github.com/<org>/<repo>/releases`.
      Tag: `v10.0.0`. Title: "TARS v10.0 — GA." Body sourced from
      `docs/RELEASE_NOTES_v10.0.md`. Artifacts attached:
      - `TARS-v10.0.0.dmg` (signed + notarized)
      - `TARS-v10.0.0-arm64.dmg` (signed + notarized)
      - `TARS-v10.0.0-windows.exe`
      - `TARS-v10.0.0-linux.AppImage`
      - `tars-tab-v10.0.0.vsix`
      - Checksums file
- [ ] VS Code `.vsix` uploaded to Marketplace publisher dashboard as a
      DRAFT. Publish queued for T-0 14:00 UTC.
- [ ] Tauri updater feed `latest.json` staged at
      `tars.meeet.world/updater/latest.json` (behind feature flag — not
      live yet).
- [ ] Backend canary deployed to `api.tars.meeet.world` — health endpoint
      green.
- [ ] Brother final sync (15 min): confirm meeet.world side is GA-ready,
      no in-flight bugs, ingest endpoint healthy.
- [ ] Sleep at a reasonable hour. Set alarm for 5:30 AM PT.

### Exit gate

Draft release exists. Smoke test clean. Brother has said "we are go on
our side." If brother says "almost," delay GA by 24 hours and reschedule
all marketing artefacts.

---

## 4. T-0 — Launch day (hour-by-hour, all times PT)

**Date target:** 2026-05-22.

This is a fixed-cadence day. Move steps EARLIER if blocked, never later.

### 05:30 PT — Wake up + coffee

- Open laptop. Confirm internet connection. Open Slack/Telegram for
  brother sync.

### 06:00 PT — GitHub release published

- Run `bash scripts/RELEASE-v10.0.command`. The script:
  1. Tags `v10.0.0` on `main`.
  2. Pushes the tag to origin.
  3. Flips the draft release to **Published**.
  4. Updates `tars.meeet.world/updater/latest.json` to point to v10.0.0.
  5. Pings brother's webhook to flip `meeet.world/integrations/tars`
     to "GA" status.
- **VERIFY:** github.com release page shows `v10.0.0` as the latest
  published release. Download artifacts and check first 100 bytes are
  not corrupted.

### 07:00 PT — HN Show HN post

- Submit the post from `marketing/launch-hn.md`. Use the @meeet_world
  HN account.
- **VERIFY:** post appears on /newest. Note the post URL.
- DO NOT comment-stuff your own thread. Let it climb organically. Reply
  only to substantive questions.

### 07:30 PT — Product Hunt launch goes live

- The PH page auto-flips to live at 07:30 PT (PH launches at 12:01 AM PT
  by their clock — we requested a 07:30 PT slot via the launch desk).
- Post the launch link in @meeet_world Twitter, Telegram comms channel,
  and the 5 closest builder friends.
- **VERIFY:** PH page shows live counter, upvote count > 0 within
  10 minutes.

### 08:00 PT — Twitter thread published

- @meeet_world publishes the 8-tweet thread from
  `marketing/launch-twitter-thread.md`. The thread is pre-queued; this
  is just confirming it fired.
- First tweet: hook + 2-line product description + demo video link.
- **VERIFY:** thread is live, all 8 tweets posted in order, no broken
  links, video plays.

### 09:00 PT — Email to waitlist (~200 users)

- Send the queued Mailchimp email. Subject: "TARS v10.0 is live."
- Body: 3 paragraphs, one CTA (download link), one secondary CTA (read
  the launch blog).
- **VERIFY:** delivery > 95%, bounce rate < 5%. First clicks within
  10 minutes.

### 10:00 PT — Reddit posts

- One post each: r/LocalLLaMA, r/macapps, r/selfhosted.
- Stagger by 15 minutes (LocalLLaMA first, then macapps, then selfhosted)
  to avoid the spam filter cross-referencing them.
- Each post tailored to the sub's voice. NO copy-paste.
- **VERIFY:** all three posts live. Reply to first comment within 2h.

### 12:00 PT — Blog post on meeet.world

- Publish `/blog/tars-v10-ga`. Title: "TARS v10.0 — the cockpit for
  everything not code." Length: 1 200 words.
- Cross-post link from @meeet_world Twitter as a reply to the launch
  thread.
- **VERIFY:** blog renders. OG image loads. Mobile viewport clean.

### 13:00 PT — Live demo stream (1-hour walkthrough)

- Stream from Alien's machine via OBS to YouTube live.
- Demo script: 5 min context → 15 min cockpit demo → 15 min composer
  + voice → 10 min marketplace + cowork → 5 min on-prem callout → 10 min
  Q&A.
- **VERIFY:** stream is up, audio is clean, ≥ 20 concurrent viewers
  within first 10 minutes.

### 14:00 PT — VS Code marketplace publish

- Flip the `.vsix` from draft to published in the Marketplace publisher
  dashboard. Publishes immediately.
- Tweet from @meeet_world: "TARS-tab now on the VS Code Marketplace."
- **VERIFY:** marketplace.visualstudio.com shows tars-tab as available.
  Install on a clean VS Code instance and confirm the extension activates.

### 17:00 PT — First-day metrics review

- Pull metrics from:
  - GitHub: stars, downloads per artifact
  - HN: rank, comment count, upvote ratio
  - Product Hunt: rank, upvotes
  - Twitter: thread impressions, retweets
  - Mailchimp: opens, clicks
  - Plausible (or equivalent) on meeet.world/blog: pageviews
  - Backend telemetry: installs, first-action completions, errors
- Record snapshot in `docs/LAUNCH_DAY_METRICS_v10.md`.
- **DECISION:** if any metric is in a "panic" band (defined below),
  trigger the corresponding response. Otherwise, drink water and
  prepare for tomorrow.

### Panic bands — when to act on launch day

| Metric                         | OK band         | Warn band     | Panic band      | Action                                          |
|--------------------------------|-----------------|---------------|-----------------|-------------------------------------------------|
| HN rank by 12 PT               | Top 20          | 20-50         | Out of top 50   | Comment-bump with substantive thread (not spam) |
| PH rank by 5 PT                | Top 3           | 4-10          | Out of top 10   | Push to network for upvotes                     |
| First-action completion %      | >= 70%          | 50-70%        | < 50%           | Identify failure mode in metrics, queue v10.0.1 |
| Backend error rate             | < 0.5%          | 0.5%-2%       | > 2%            | Page brother + Cursor, rollback if needed       |
| Notarization-related installs  | 0 reports       | 1-3 reports   | > 3 reports     | Pull the build, re-notarize, re-release         |
| Apple Gatekeeper rejections    | 0               | 1-3           | > 3             | Verify staple, contact Apple Dev support        |

---

## 5. T+1 to T+7 — First week

### Daily rhythm

Every day at 9 AM PT:

- [ ] Pull metrics dashboard snapshot (same template as T-0 17:00).
- [ ] Triage new bugs in `gh issue list --label bug`. Tag P0/P1/P2.
- [ ] Reply to every HN/PH/Reddit comment within 2h of posting.
- [ ] Sync with brother for 15 min on backend health.

### Bug response SLA

- **P0 (crash, data loss, security):** fix and ship a `v10.0.1` hotfix
  within 24h.
- **P1 (broken feature, no workaround):** fix in `v10.0.2` within 7
  days.
- **P2 (annoyance, workaround exists):** queue for v10.1.

### Day-by-day focus

- **T+1 (2026-05-23):** Bug triage day. Expect 10-30 new issues. Triage
  all of them. Ship v10.0.1 if any P0 surfaces.
- **T+2:** Press follow-up day. Reach out to journalists who didn't
  publish — offer fresh angles.
- **T+3:** Community day. Host an AMA on HN or Reddit.
- **T+4:** Sales day. Reach out to the 10 on-prem leads collected during
  launch.
- **T+5:** First customer success call (with the most engaged user
  identified via telemetry).
- **T+6:** Retrospective notes start. What's working, what's broken.
- **T+7:** Week-one wrap. Public metrics tweet from @meeet_world ("Week
  one: X installs, Y stars, Z bug reports — here's what's next").

### Hotfix discipline

If a P0 bug ships in v10.0.0, the response is:

1. Verify it's actually P0 (reproduce on a clean machine).
2. Page brother if it touches the meeet.world side.
3. Write the fix + regression test in a single PR.
4. Re-run `bash scripts/FINAL-QA-GATE.command`.
5. Tag `v10.0.1`. Run `bash scripts/RELEASE-v10.0.command`.
6. Communicate: tweet from @meeet_world, edit the GH release notes for
   v10.0.0 to point at v10.0.1, update the updater feed.
7. The updater pushes the patch to existing installs within 24h.

---

## 6. T+30 — Retrospective + v10.1 planning

**Date target:** 2026-06-22.

### Goals

- Honest retro of the launch month.
- v10.1 planning locked.
- First on-prem deployment milestone confirmed.
- Partnership conversations seeded with 5 target companies.

### Retrospective template

Write to `docs/RETRO_v10.0.md`:

1. **What we shipped** — 1 paragraph factual recap.
2. **What worked** — 3 bullets, evidence-backed.
3. **What broke** — 3 bullets, evidence-backed.
4. **What we learned** — 3 bullets, opinion permitted.
5. **What changes in v10.1** — 3 bullets, actionable.

### v10.1 planning gate

- All five v10.1 features from `ROADMAP_POST_GA.md` have an owner.
- Success metric instrumented in telemetry (or a ticket to instrument).
- Gating dependency (brother's back-pressure response) confirmed
  unblocked.

### First on-prem deployment

- Customer signs the contract OR signs acceptance test results from a
  pilot deployment.
- `docs/ONPREM_DEPLOYMENT_GUIDE.md` updated with any field corrections.
- First on-prem customer logo (with permission) goes on
  `tars.meeet.world` homepage.

### Partnership conversations — 5 target companies

By T+30, we have *seeded* (not closed) conversations with 5 companies
across the on-prem, marketplace publisher, and enterprise verticals.

Targets to consider:

- 2 mid-market SaaS companies with internal AI ops teams
- 1 family office or small fund (algotrade pack early adopter)
- 1 design or product agency (workshop pack early adopter)
- 1 systems integrator who can OEM-deliver TARS on-prem to their
  customers

### Exit gate

The retrospective is written. v10.1 plan is locked. v10.0 era closes.
The next playbook (`LAUNCH_PLAYBOOK_v10.1.md`) is a 50-line delta on
this one — no need to rewrite.

---

## 7. Operator survival rules

For Alien, specifically. From hard-won experience across the W237-W267
arc:

1. **Sleep on T-1.** No heroics the night before launch. Tired operators
   ship bugs.
2. **Don't read HN comments on launch day past 1 PM PT.** Engagement
   negativity hits hardest in the 2-6 PM window. Read in the morning,
   reply once, move on.
3. **Brother is your only external dependency.** If he is delayed, you
   are delayed. Bake 24h slack into every milestone.
4. **One channel, one message.** No re-posting the same launch tweet
   from a personal account. Authenticity > reach.
5. **The first 1 000 installs are the only ones that matter for
   product feedback.** Talk to as many of them as humanly possible.
6. **If a journalist offers to publish later in exchange for an
   exclusive angle, say yes.** Spread the press over a week, not a day.
7. **The launch isn't the product.** It is the moment the product
   starts having a chance to compound. Treat T+1 to T+30 as more
   important than T-0.

— end —
