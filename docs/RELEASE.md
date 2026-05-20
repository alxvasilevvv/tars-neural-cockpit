# Release engineering (TARS desktop)

Operator entry points for v10 GA:

- [`V10_GA_CHECKLIST.md`](V10_GA_CHECKLIST.md) — hard blockers vs nice-to-have
- [`LAUNCH_PLAYBOOK_v10_GA.md`](LAUNCH_PLAYBOOK_v10_GA.md) — comms + rollout
- [`handoff/PH11_QA_SWEEP_BRIEF.md`](handoff/PH11_QA_SWEEP_BRIEF.md) — soak + tag-cut methodology
- [`W310_WAVE_SUMMARY.md`](W310_WAVE_SUMMARY.md) — one-page merge + GA cookbook (W310-ao)

Scripts (run from repo root):

```bash
bash scripts/FINAL-QA-VERDICT.command
bash scripts/GA-COOKBOOK.command
bash scripts/RELEASE-TAG-GUARD.command
bash scripts/RELEASE-v10.0.command          # destructive — tag cut
bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command
bash scripts/POST-INSTALL-SMOKE.command
bash scripts/SOAK-HOURLY.command            # cron 72h
bash scripts/SOAK-REPORT.command
```
