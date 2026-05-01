# Release-gate evidence

This folder is where `make gate-release` (`scripts/gate_release.sh`)
drops the structured outcome of every run.

Format: one `release-gate/1.0.0` JSON per run plus an accompanying
`*.qa-agent.json` (Layer-1 probe report).

Naming: `rel-<utc-timestamp>-<random>.json`.

The evidence files themselves are gitignored (they contain a unique
trace per run); only this README and the `.gitignore` are tracked.

To inspect the latest run:

```bash
ls -t docs/release-evidence/*.json | head -1 | xargs cat | jq .
```

To enforce a clean run before a release:

```bash
make gate-release        # exits non-zero if anything failed
ls docs/release-evidence/ # check the freshest evidence file
```

CI can upload these as artefacts; locally they're handy for postmortems.
