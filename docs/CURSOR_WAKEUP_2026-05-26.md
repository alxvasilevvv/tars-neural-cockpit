# Cursor overnight report — 2026-05-26 (updated)

**Read this first when you wake up.** Then: `make ga-status`.

## Pushed to `main`

| Commit | What |
|--------|------|
| `75efd70` | `CURSOR-GA-STATUS.command`, `make ga-status`, `make ci-cockpit` |
| `2a407de` | `SOAK-CRON-INSTALL`, `CURSOR-OVERNIGHT-SOAK`, `docs/OPERATOR_GA_RU.md` |
| `daa97be` | wake report, `APPLE-GH-SECRET-TEMPLATE`, handoff + RELEASE.md |
| `1814e6b` | `CURRENT_STATUS` W312 |
| *(next)* | `CURSOR-SOAK-UNTIL-72`, `SOAK-CRON-DIAGNOSE`, macOS cron permissions doc |

## Soak progress (live)

- **`.soak/hourly.log`:** **15/72** (target for GA) — check with `wc -l .soak/hourly.log`
- **System cron:** line installed, but **`cron.log` shows `Operation not permitted`** on macOS — use `CURSOR-SOAK-UNTIL-72` in background instead
- **Backend:** `curl http://127.0.0.1:8765/api/health` should stay `ok: true`

```bash
bash scripts/SOAK-CRON-DIAGNOSE.command
tail -5 .soak/cron.log
ps aux | grep CURSOR-SOAK-UNTIL || grep CURSOR-OVERNIGHT || true
```

## Still blocked for v10.0.0 tag (operator)

1. **Apple** — `docs/APPLE_SIGNING_SETUP.md` + 6 GH secrets (`make apple-gh-hints`)
2. **Soak wall-clock** — **72** hourly samples (~57h remaining from 15/72 if one sample/hour)

## Green without Apple secrets

- `make test`, cockpit e2e 7/7, Brother PROCEED
- `make ga-status` shows Apple red only (expected until secrets)

## Commands on wake

```bash
make ga-status
make soak-cron-diagnose
# After Apple:
bash scripts/PREFLIGHT-APPLE-SIGN.command
bash scripts/GA-COOKBOOK.command
```

Full chain: `docs/W310_WAVE_SUMMARY.md` (TLDR at top). RU: `docs/OPERATOR_GA_RU.md`.
