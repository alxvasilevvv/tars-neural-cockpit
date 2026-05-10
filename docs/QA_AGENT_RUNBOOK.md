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
    --history-path ~/.tars/qa-agent/history.json
```

Env equivalents: `QA_AGENT_ESCALATE_ALERTS=1`, `QA_AGENT_SOFT_FAIL=1`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_OPERATOR_CHAT_ID`,
`BRIDGE_SHARED_SECRET`, `TARS_INGEST_API_KEY`.
