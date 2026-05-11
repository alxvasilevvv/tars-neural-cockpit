# QA Agent Runbook (Wave 117)

Active synthetic monitor for `tars.meeet.world`. Runs every 5 min via
GitHub Actions (`.github/workflows/qa-agent.yml`) and on every push /
PR that touches relevant files.

## What is probed

The agent is stdlib-only (no extra `pip install`). Each probe lives in
`scripts/qa_agent/probes.py` and returns a `Probe` record with one of
`pass` / `fail` / `warn` / `skip`.

### Wave 117 additions

- **`probe_route_renders(route, expected_titles)`** — for every entry
  in `WAVE117_ROUTES` (24 routes total) verifies HTTP 200, presence of
  `<div id="root"></div>`, absence of error markers (`is not defined`,
  `RENDER ERROR`, `Application error`, `Internal Server Error`,
  `Cannot GET`, etc.), and best-effort title hints.
- **`probe_sw_version()`** — fetches `/sw.js`, extracts the `VERSION`
  constant, warns if the value doesn't match the v9.x.y pattern.
- **`probe_bundle_imports()`** — pulls the main JS bundle linked from
  `index.html`, asserts >100 KB, presence of the literal `Workshop`
  (Wave 114 regression sentinel), and balanced parens.

### Pre-existing probes (kept)

- `probe_dns`, `probe_spa_root`, `probe_spa_routes`, `probe_security_headers`,
  `probe_session_cookie`, `probe_root_ttfb`
- Manifest / version: `probe_manifest_subdomain`, `probe_manifest_origin`,
  `probe_manifest_origin_blocked`, `probe_manifest_cors_meeet_world`,
  `probe_version_subdomain`, `probe_client_error_endpoint`
- Bridge: `probe_core_bridge_health`, `probe_core_bridge_unauth`,
  `probe_core_bridge_relay_roundtrip`
- Schema: `probe_sitemap`, `probe_robots`
- Heartbeat: `probe_meeet_ingest_heartbeat`

## Cadence

| Trigger          | Frequency       |
| ---------------- | --------------- |
| `schedule:` cron | every 5 minutes |
| push to `main`   | on relevant paths |
| pull request     | on relevant paths |
| `workflow_dispatch` | manual           |

Cadence was bumped from `*/30` → `*/5` in Wave 117 so that prod issues
surface in 5 minutes rather than from user reports (Waves 114-116
turnaround).

## How alerts fire

Alert escalation lives in `scripts/qa_agent/alerts.py`.

1. After each run, every probe's outcome is appended to a per-probe
   rolling history in `~/.tars/qa-agent/history.json` (last 10 runs,
   per probe).
2. `should_alert(history, threshold=3)` returns True iff the **last 3
   entries are all `fail`**. A single non-fail breaks the streak.
3. On True, `send_alert(probe_name, summary)` fires:
   - **Telegram** via Wave 108's `TelegramClient` if both
     `TELEGRAM_BOT_TOKEN` and `TELEGRAM_OPERATOR_CHAT_ID` are set
     (falls back to a stdlib `urllib` POST when the backend module
     isn't on `sys.path`).
   - **Webhook** event `qa.alert` via the Wave 90 dispatcher, so any
     registered outgoing webhook receives the same payload.
4. The alert state survives between runs: the workflow downloads the
   prior `qa-agent-history` artifact, stages it under
   `~/.tars/qa-agent/`, then re-uploads it.

### Suppressing flaky probes

Append the probe name to `KNOWN_FLAKY` in `scripts/qa_agent/alerts.py`
to silence false positives without removing the probe entirely. The
probe still runs and reports; only the alert escalation is skipped.

## How to add a new probe

1. Add `probe_xxx(ctx) -> Probe` to `scripts/qa_agent/probes.py`.
2. Wire it into `run_all()` in `scripts/qa_agent/runner.py`.
3. (Optional) Bump `tests/test_qa_alerts.py` if the new probe needs
   alert-side coverage.

## Manual trigger

```
gh workflow run qa-agent.yml
```

## On-call playbook (alerted at 3 am)

1. Open https://github.com/alxvasilevvv/tars-neural-cockpit/actions
2. Find the latest `TARS QA Agent` run.
3. Click into the failing job, expand the `Run QA agent (text)` step.
4. The probe name in the alert maps 1-to-1 to the failing line in the
   report (e.g. `http.route_v117/cockpit`).
5. Cross-reference with `pwa.sw_version` and `bundle.imports` lines —
   if the SW VERSION is stale or the bundle is missing `Workshop`, the
   prod deploy is broken (re-run `tars-meeet-cloudflare-pages.yml`).
6. If alerts spam without a real outage, add the probe to
   `KNOWN_FLAKY` in `alerts.py` and root-cause separately.

## CLI flags

```
python -m scripts.qa_agent --escalate-alerts \
    --alert-threshold 3 \
    --history-path ~/.tars/qa-agent/history.json \
    --write-public-snapshot \
    --snapshot-path experiments/neural-showcase-v3/public/qa-snapshot.json
```

Env equivalents: `QA_AGENT_ESCALATE_ALERTS=1`, `QA_AGENT_SOFT_FAIL=1`,
`QA_AGENT_WRITE_SNAPSHOT=1`, `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_OPERATOR_CHAT_ID`, `BRIDGE_SHARED_SECRET`,
`TARS_INGEST_API_KEY`.

## Public status page (Wave 126)

The marketing site at `tars.meeet.world/status` reads a static
`/qa-snapshot.json` projected from each probe run. Pipeline:

1. `python -m scripts.qa_agent --write-public-snapshot` (set in CI via
   `QA_AGENT_WRITE_SNAPSHOT=1`) builds the public-facing JSON via
   `scripts/qa_agent/snapshot.py::build_snapshot()` and writes it to
   `experiments/neural-showcase-v3/public/qa-snapshot.json`.
2. The runner prints `snapshot_commit=true|false` to stderr based on
   `should_commit_snapshot()`. Decision rules:
     * **first_snapshot** — no prior file on disk; commit.
     * **status_change:green->red** (any flip) — commit immediately.
     * **probes_changed** — same overall_status but a different set of
       probes is failing; commit.
     * **interval** — 30+ minutes since the last commit; commit so the
       timestamp doesn't go stale on a green deployment.
     * **no_change_within_interval** — skip; the GH Actions artefact
       still has the latest copy for retroactive debugging.
3. The `Maybe commit public snapshot` step in
   `.github/workflows/qa-agent.yml` greps for `snapshot_commit=true`
   and only pushes from `main` on scheduled / manual runs (PRs and
   forks never push). Worst case ~48 commits/day on a perfectly green
   deploy (every 30 min); a brief outage adds at most 2-4 (status
   flip + recovery flip).
4. Cloudflare Pages serves the JSON with no auth and short TTL. The FE
   fetches `/qa-snapshot.json?t=<ts>` every 60s and degrades gracefully
   (a "Status check temporarily unavailable" panel) on 404.

### Snapshot shape v1

```json
{
  "version": 1,
  "generated_at": "2026-05-11T12:34:56+00:00",
  "overall_status": "green | yellow | red",
  "probes": [
    {
      "name": "http.route/",
      "status": "green | yellow | red",
      "last_status": "pass | fail | warn | skip",
      "last_success_at": "...",
      "last_failure_at": null,
      "failure_count_24h": 0,
      "uptime_7d_pct": 99.94
    }
  ],
  "incidents": [
    {
      "id": "incident-2026-05-10-route_workshop",
      "started_at": "...",
      "resolved_at": null,
      "probes_affected": ["http.route/workshop"],
      "summary": "1 probe failing (http.route/workshop)"
    }
  ]
}
```

`uptime_7d_pct` is computed from the history.json rolling window (cap
`HISTORY_MAX_PER_PROBE = 10`). Honest naming would be "uptime in last
N runs"; we round to a 7-day-style label for human readability and
document the caveat in the FE.

### Local smoke

```
python -m scripts.qa_agent --json --no-color --write-public-snapshot \
    --snapshot-path /tmp/qa-snapshot.json
cat /tmp/qa-snapshot.json | python3 -m json.tool | head -40
python3 -m unittest tests.test_qa_snapshot
```
