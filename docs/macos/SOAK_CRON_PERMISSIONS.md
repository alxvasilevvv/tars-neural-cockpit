# macOS: cron soak fails with "Operation not permitted"

If `.soak/cron.log` shows:

```text
bash: scripts/SOAK-HOURLY.command: Operation not permitted
```

the **hourly crontab line is installed** but **launchd/cron cannot read or execute** files under your home directory until macOS grants access.

## Quick workaround (recommended for GA)

Run soak from a shell that already works (Cursor terminal, `nohup`):

```bash
cd /Users/alien/Documents/Claude/Projects/Jarvis/jarvis
make dev-tars-stack   # keep backend up

# Until 72 lines in hourly.log (~57h wall-clock from 15/72):
nohup bash scripts/CURSOR-SOAK-UNTIL-72.command >> .soak/until-72.log 2>&1 &
```

Check:

```bash
wc -l .soak/hourly.log
tail -f .soak/until-72.log
make soak-cron-diagnose
```

## Fix cron (optional)

1. **System Settings → Privacy & Security → Full Disk Access**  
   Add **cron** (path may be `/usr/sbin/cron`) and/or **Terminal** / **Cursor**.

2. Re-run install:

   ```bash
   bash scripts/SOAK-CRON-INSTALL.command
   ```

3. Wait for the top of the hour, then:

   ```bash
   bash scripts/SOAK-CRON-DIAGNOSE.command
   tail .soak/cron.log
   ```

## Diagnose anytime

```bash
bash scripts/SOAK-CRON-DIAGNOSE.command
```

Exit **1** = permission or missing cron line; **0** = recent cron runs look healthy.
