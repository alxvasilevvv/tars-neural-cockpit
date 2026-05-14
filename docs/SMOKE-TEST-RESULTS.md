# SMOKE-TEST.command — what it checks and how to read it

`scripts/SMOKE-TEST.command` is a single double-clickable verification step
for TARS **v9.2.0-beta2**. It hits every endpoint introduced in waves
W203 → W225 plus a handful of legacy baseline routes, then checks the
non-HTTP pieces (watchdog LaunchAgent, meeet token, installed `.app`).

It writes a full transcript to `.SMOKE-TEST.txt` in the repo root and
auto-closes the Terminal window 5 seconds after finishing.

## What it covers

### HTTP endpoints (~22 calls)

| Wave  | Endpoints                                                                                              |
| ----- | ------------------------------------------------------------------------------------------------------ |
| base  | `GET /api/health`, `/api/doctor`, `/api/entitlements`, `/api/agents`, `/api/connectors`                |
| W203  | `GET /api/vision/health`, `POST /api/vision/ocr` (multipart), `POST /api/vision/analyze`               |
| W203  | `GET /api/auth/meeet/status`, `POST /api/auth/meeet/exchange`, `DELETE /api/auth/meeet/disconnect`     |
| W204  | `GET /api/public/proof/health`, `GET /api/public/proof/anchor/{root}`, `POST /api/public/proof/verify` |
| W206  | `GET /api/briefing/today`                                                                              |
| W209  | `POST /api/digest/run`, `GET /api/digest/latest`                                                       |
| W217  | `GET /api/a11y/health`, `POST /api/a11y/ocr_speak` (multipart), `POST /api/a11y/speak`                 |
| W219  | `POST /api/auth/meeet/magic-link-start`, `GET /api/auth/meeet/oauth/{google,apple}/start`              |
| W220  | `POST /api/voice/command`                                                                              |

### System-level checks (3)

- `launchctl list | grep com.tars.backend-watchdog` — the backend
  watchdog LaunchAgent is installed and running.
- `~/.tars/meeet_token` exists and is larger than 8 bytes.
- `/Applications/TARS.app` is installed and its
  `CFBundleShortVersionString` is reported.

## Output format

Each line is one of three states:

- `✓ METHOD /path (HTTP 200)` — endpoint returned 2xx.
- `⚠ METHOD /path — skipped (HTTP 404, expected to need data)` — endpoint
  responded correctly but said "no data here" (e.g. the public-proof
  anchor lookup on a fresh box). Treated as a pass for the overall
  result.
- `✗ METHOD /path (HTTP N)` — real failure. Listed again under
  "failures" at the end with the full method + status.

The script prints a one-line summary like:

```
28/30 endpoints ok, 2 skipped, 0 failed
✓ SMOKE TEST PASSED — TARS v9.2.0-beta2 looks healthy
```

Exit code is `0` on full pass (skips OK), non-zero if pre-flight fails
(backend unreachable).

## How to run

```bash
# from Finder: double-click scripts/SMOKE-TEST.command
# or from a terminal:
bash scripts/SMOKE-TEST.command
```

Override the base URL with `TARS_BASE`:

```bash
TARS_BASE=http://127.0.0.1:9999 bash scripts/SMOKE-TEST.command
```

## How to interpret the result

### All green

You're done. TARS v9.2.0-beta2 is wired correctly. Open the TARS.app and
use it.

### Pre-flight failure: backend not reachable

The script bails before running any checks. Fix:

```bash
bash scripts/backend_tars_up.sh
# or
bash scripts/LAUNCH-NOW.command
```

Then re-run the smoke test.

### One or two ✗ failures

Look at the listed failures at the bottom. Common causes:

| Failing path                               | Probable cause                                            | Fix                                                                          |
| ------------------------------------------ | --------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `POST /api/vision/ocr` returns 500         | `pytesseract` / `Pillow` not installed                    | `pip install pytesseract Pillow && brew install tesseract`                   |
| `POST /api/vision/analyze` returns 500     | LLM key set but malformed                                 | Check `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` in `.env`                       |
| `GET /api/briefing/today` returns 500      | doctor or receipts subsystem broken                       | Run `tars-doctor` to find the failing check                                  |
| `POST /api/digest/run` returns 500         | `backend.core.playbooks.weekly_digest` raised             | Look at backend logs: `tail -100 ~/.tars/logs/backend.log`                   |
| `POST /api/voice/command` returns 500      | All three LLM branches crashed before fallback            | Check network + LLM keys                                                     |

### `⚠ watchdog LaunchAgent NOT loaded`

The watchdog has not been registered yet. Fix:

```bash
bash scripts/install-tars-watchdog.command
```

This sets up `com.tars.backend-watchdog.plist` in
`~/Library/LaunchAgents/` and loads it.

### `⚠ no meeet token at ~/.tars/meeet_token`

You haven't paired with meeet.world. The app still works fully
local-only — pairing is only needed for $MEEET economy and bridged
features. Pair from the TARS.app onboarding screen, or:

```bash
curl -X POST http://127.0.0.1:8765/api/auth/meeet/exchange \
  -H 'Content-Type: application/json' \
  -d '{"token":"<your-token-from-meeet.world>"}'
```

### `⚠ /Applications/TARS.app missing`

You haven't installed the desktop wrapper. Fix:

```bash
bash scripts/install-tars-app.command
```

## Related

- `tests/test_smoke_all_routers.py` — pytest mirror of these checks
  (one method per endpoint). Runs in CI even without a live backend
  because each test mounts the router directly via `TestClient`.
- `scripts/audit_endpoint_smoke.py` — older broader catalog used by the
  pre-launch audit; this W227 script is the focused happy-path
  successor.
- `scripts/LAUNCH-NOW.command` — what to run **before** the smoke test
  if nothing has been started yet.
