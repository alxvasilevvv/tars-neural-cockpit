# LAUNCH DAY RUNBOOK — TARS v9.1.0

> Operator runbook for launch day. Sequential checklist, designed for
> a solo operator with a coffee in one hand.
>
> Companion docs:
> - `docs/launch/twitter-thread.md` — 10-tweet thread copy
> - `docs/launch/hacker-news.md` — HN title + first comment + objections
> - `docs/launch/product-hunt.md` — PH tagline + maker comment + gallery
> - `docs/launch/reddit-r-macapps.md` — r/macapps post
> - `docs/launch/reddit-r-saas.md` — r/SaaS post
> - `docs/launch/email-waitlist-blast.md` — waitlist email (HTML + plain)
> - `docs/launch/email-cohort-invite-fund.md` — cold cohort invite
> - `docs/launch/PRESS_KIT.md` — press kit + brand assets
> - `docs/launch/ANNOUNCEMENTS.md` — Wave 77 short-form variants
>
> Goal: post HN at 8 AM PT, monitor for issues, do not break the build.

---

## T-1 day (the day before)

### Morning

- [ ] Apple Developer ID cert received? If yes:
  - [ ] Build signed `.dmg` via `npm run tauri build` on a Mac
  - [ ] Notarize: `xcrun notarytool submit ... --wait`
  - [ ] Staple: `xcrun stapler staple TARS_v9.1.0.dmg`
  - [ ] Upload to GitHub Releases as `v9.1.0` asset
  - [ ] Verify the `/dl` Cloudflare proxy resolves correctly
- [ ] If signed cert NOT ready:
  - [ ] Confirm landing page is in "coming soon" mode for downloads
  - [ ] Confirm `experiments/neural-showcase-v3/src/components/InstallStrip.tsx`
        shows the "signed .dmg this week" banner
  - [ ] Pre-write a blog post / email for "the signed .dmg dropped"
        follow-up so we can fire it the moment it's ready

### Afternoon

- [ ] Tag the release: `git tag -s v9.1.0 -m "TARS v9.1.0"` then push tag
- [ ] Verify the v9.1.0 GitHub Actions release workflow goes green
- [ ] Run the local synthetic monitor manually:
      `python scripts/synthetic_monitor.py --once` and confirm 0 alerts
- [ ] Verify `/admin/perf` page loads and shows clean numbers
- [ ] Open all 8 collateral docs in browser tabs, ready to copy-paste
- [ ] Schedule PH for 12:01 AM PT next morning
- [ ] Schedule waitlist email in ESP for 9:00 AM PT next morning
- [ ] DM 5-10 friendly operators asking for thoughtful first PH comments
      (NOT vote-asks)

### Evening

- [ ] Get a real night of sleep. Launches go badly when the operator
      is tired.

---

## T-12 hr (8 PM PT, night before)

- [ ] Final CI green check: GitHub Actions for `main` is green
- [ ] Final synthetic monitor check: 0 alerts in last 12 hr
- [ ] Verify Tauri updater channel JSON returns v9.1.0
- [ ] Verify https://tars.meeet.world loads in <2s from a phone
- [ ] Verify https://tars.meeet.world/cockpit loads (no white screen)
- [ ] Verify https://tars.meeet.world/workshop loads
- [ ] Verify https://tars.meeet.world/pricing loads
- [ ] Verify https://tars.meeet.world/install loads
- [ ] Confirm PH submission scheduled (no last-minute changes)

---

## T-1 hr (7 AM PT, launch morning)

### CDN warm-up (run from 5 different VPN regions)

```bash
# US-East
curl -o /dev/null -s -w "%{http_code} %{time_total}s\n" https://tars.meeet.world

# US-West
curl -o /dev/null -s -w "%{http_code} %{time_total}s\n" https://tars.meeet.world

# EU (London)
curl -o /dev/null -s -w "%{http_code} %{time_total}s\n" https://tars.meeet.world

# Asia (Singapore)
curl -o /dev/null -s -w "%{http_code} %{time_total}s\n" https://tars.meeet.world

# AU
curl -o /dev/null -s -w "%{http_code} %{time_total}s\n" https://tars.meeet.world
```

Expect 200 + sub-500ms TTFB everywhere. If a region 5xxs, defer launch
30 min and investigate Cloudflare Pages health.

- [ ] All 5 regions green
- [ ] Refresh the PH listing one last time — confirm it goes live at 12:01
- [ ] Open the HN submission tab, paste title + URL but DO NOT submit yet
- [ ] Open the Twitter draft, all 10 tweets queued in a thread tool

---

## T+0 (8 AM PT, launch hour)

| Time (PT) | Action |
| --- | --- |
| 8:00 | Submit HN post (`docs/launch/hacker-news.md`) |
| 8:00 +30s | Post first-comment seed on the HN thread |
| 8:01 | Fire Twitter thread (`docs/launch/twitter-thread.md`) |
| 8:05 | Confirm PH listing is live (was scheduled for 12:01 AM) |
| 9:00 | Send waitlist email (`docs/launch/email-waitlist-blast.md`) |
| 11:00 | Post r/macapps (`docs/launch/reddit-r-macapps.md`) |
| 11:30 | Post r/SaaS (`docs/launch/reddit-r-saas.md`) |
| 8:00–10:00 | Reply to every PH comment within 5 min |
| 8:00–11:00 | Reply to every HN comment within 5 min |

---

## T+0 to T+2hr — active monitoring

- [ ] Keep `/admin/perf` open in a tab — refresh every 5 min
- [ ] Keep the synthetic monitor's alert channel (Telegram) open
- [ ] Keep the waitlist ESP dashboard open — watch bounce + spam rates
- [ ] If HN front page hit: do NOT touch the deploy pipeline.
      Cancel any non-urgent commits to `main`.

### Watch for these alerts

| Symptom | Likely cause | Mitigation |
| --- | --- | --- |
| Synthetic monitor red on `/cockpit` | SW cache regression (Wave 115) | Bump SW version + force-reload. Hotfix on `main`. |
| 5xx spike on `/dl` | Cloudflare Pages function quota | Investigate `experiments/neural-showcase-v3/functions/dl/[file].ts` logs |
| Waitlist email bounce > 5% | List hygiene rot | Pause sends; re-warm the IP next day |
| HN comment ratio < 1:5 | Thread is being downvoted | Engage harder, do not delete |

---

## T+2 to T+24hr — sustain

- [ ] Reply to all comments within 30 min for the first 12 hr
- [ ] Around 2 PM PT: post an update tweet quoting top HN comment
      with a thoughtful reply (drives second wave of traffic)
- [ ] Around 6 PM PT: check PH leaderboard. If top 5, post a
      "thank you" tweet linking the PH page.

---

## T+24hr — wrap

- [ ] Thank-you tweet (one tweet, no link spam)
- [ ] Share metrics IF a milestone hit:
      - "Top 5 on HN" → tweet a screenshot
      - "Top 3 on PH" → tweet a screenshot + thanks
      - "1000 .dmg downloads" → tweet a screenshot from `/admin/perf`
      - DO NOT share metrics if they're embarrassing — silence > spin
- [ ] Post-mortem in `docs/launch/POST_LAUNCH_NOTES.md`:
      what worked, what didn't, what to do differently next launch

---

## Failure modes + mitigations

### HN downvoted off front page in <30 min

```
Cause: title pattern-matched to "another AI tool" or first comment
landed too late.

Mitigation: do NOT delete and resubmit (violates HN guidelines).
Try again next week with a different angle:
- Story-shaped title: "Why I built a local-first AI cockpit
  instead of using Cursor"
- "Show HN" prefix this time
- Link to a specific blog post, not the marketing site
```

### Cloudflare Pages goes down

```
Cause: rare but happens. Usually a global CF incident.

Mitigation:
- Check status.cloudflare.com first
- If global: wait it out, post a status update on Twitter
- If region-specific: enable origin failover via Cloudflare dashboard
- Last resort: push static-site to Vercel (DNS swap, ~10 min recovery).
  The build artifact in experiments/neural-showcase-v3/dist/ is
  Vercel-deployable as-is.
```

### Waitlist email bounces / spam-foldered

```
Cause: ESP IP reputation, missing SPF/DKIM/DMARC, or content trip.

Mitigation:
- Check sender domain SPF + DKIM + DMARC alignment via mxtoolbox
- Re-send to bouncers via different gateway (e.g. Postmark for primary,
  Resend for retries)
- For spam-foldered: include a P.S. asking subscribers to mark
  as "Not Spam" — improves future deliverability
```

### Sidecar crashes on a user's machine post-install

```
Cause: Python venv missing on first run, or port conflict on 8000.

Mitigation: 
- The sidecar crash watcher (Wave 61) auto-respawns
- If it can't, the cockpit shows "Sidecar offline" indicator (Wave 60)
- User-facing fix: restart TARS, or run install.sh again
- Operator action: tail Sentry / OpenTelemetry for the stacktrace
```

### .dmg signed but Apple Gatekeeper still warns

```
Cause: stapler step skipped, or notarization not yet propagated.

Mitigation:
- Verify staple: spctl -a -t exec -vv TARS.app
- If "rejected" → re-run xcrun notarytool log <id>
- If user-side: tell them to right-click → Open ONCE,
  then it's permanently allowed
```

---

## Roll-back procedure

If a critical bug ships in v9.1.0 within first 6 hr:

```bash
# 1. Identify the bad commit
git log --oneline -10

# 2. Revert + push
git revert <bad-commit-sha>
git push origin main

# 3. Tag a hotfix release
git tag -s v9.1.1 -m "Hotfix v9.1.1 — revert <description>"
git push origin v9.1.1

# 4. Updater channel auto-picks up the new release
# 5. Tweet that v9.1.1 is out, no panic, no detail unless asked
```

Do NOT delete the v9.1.0 tag. Customers who already downloaded
need it for rollback.

---

## Quiet hours

If you're a solo operator, schedule 11 PM PT to 6 AM PT as
genuine quiet hours. Set Telegram to silent for non-P0 alerts.
The synthetic monitor will still page you for real outages.
Burnout in week 1 is the most common failure mode of a solo launch.
