# Cursor overnight report — 2026-05-26

**Read this first when you wake up.** Then: `make ga-status`.

## Pushed to `main`

| Commit | What |
|--------|------|
| `75efd70` | `CURSOR-GA-STATUS.command`, `make ga-status`, `make ci-cockpit` |
| (next) | `SOAK-CRON-INSTALL`, `CURSOR-OVERNIGHT-SOAK`, `docs/OPERATOR_GA_RU.md` |

## Running while you sleep

- **Overnight soak** PID logged at start — `CURSOR-OVERNIGHT-SOAK` runs hourly × 8
- **System cron** already had `SOAK-HOURLY` (unchanged)
- **Backend** was up (`/api/health` ok, uptime ~5 days)

Check progress:

```bash
tail -20 .soak/overnight-watch.log
wc -l .soak/hourly.log    # target 72 for GA
ps aux | grep CURSOR-OVERNIGHT || true
```

## Still blocked for v10.0.0 tag (you only)

1. **Apple** — `docs/APPLE_SIGNING_SETUP.md` + 6 GH secrets
2. **Soak wall-clock** — need **72** hourly samples (was ~5–6 at sleep time; overnight adds ~8–13)

## Green without you

- Tests, cockpit e2e, Brother PROCEED
- Code path to GA is documented in `docs/OPERATOR_GA_RU.md`

## Commands on wake

```bash
make ga-status
bash scripts/PREFLIGHT-APPLE-SIGN.command   # after Apple setup
bash scripts/GA-COOKBOOK.command            # must be 0
```
