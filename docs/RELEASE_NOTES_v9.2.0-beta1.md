# TARS v9.2.0-beta1 — Early Access for Power Users

**Released:** 2026-05-14
**Channel:** beta · additive over v9.1.4
**Audience:** technical power-users
**Codename:** "Honest beta — operational layer ready, business layer roadmap"

## What's new since v9.1.4

This is the first **beta release intended for distribution to operators
outside the dev team**. It packages the v9.1.4 operational infrastructure
plus an honest framing of what works and what doesn't.

### Shipped (W175-W197)

- **W175:** OpenRouter recognized as third LLM provider in `llm_provider`
  doctor check (alongside Anthropic + OpenAI).
- **W186:** Same-origin cockpit shell at `/api/doctor/cockpit` —
  multi-panel HTML cockpit with quick-actions, live health checks, and
  daemon log tail. Talks directly to local backend.
- **W187/W188:** Orchestrated documentation audit + consolidated
  roadmap (`docs/ROADMAP_v9.2_v10.md`) — 22-26 weeks of honest plan
  from v9.2 to v10.0.
- **W194:** `BRIDGE_SHARED_SECRET` generated locally; brother instructions
  in `docs/HANDOFF_v9.2_FOR_BROTHER.md` for Supabase function side.
- **W195:** AI Clone sync webhook wired into `record_message` (debounced
  every N messages). Already operating; awaits brother's
  `/tars-ingest/clone-sync` endpoint.
- **W196:** Voice synthesis usage events flow through
  `mirror_usage.after_usage_tokens_emitted` → meeet `/operator/usage`
  endpoint. `probe-meeet-billing.command` available for E2E verification.
- **W197:** Full pytest suite verified on operator's Mac. **323 tests
  passing, 0 failing.** Fixed 2 latent issues found during audit:
  `get_clone_store` re-export + test env isolation.

### Operator launchers (new in beta)

- `scripts/tars-start.command` — **Single double-click to bring TARS up.**
- `scripts/backend-up.command` — Backend only.
- `scripts/open-doctor.command` — Cockpit + doctor in Chrome.
- `scripts/fix-all-warns.command` — Auto-close all warn rows.
- `scripts/verify-doctor.command` — Snapshot doctor state to file.
- `scripts/relaunch-cockpit.command` — Restart backend + cockpit.
- `scripts/test-categories.command` — Categorized pytest diagnostic.
- `scripts/probe-meeet-billing.command` — meeet billing reachability test.

### Honest framing — what's NOT working

This release **does not** ship:

- **Working Tauri /cockpit** — known v9.1.0-preview localStorage bug.
  Workaround: use `tars-start.command` for chromeless Chrome cockpit.
- **Voice wake-word, narration auto-loop, VAD streaming** — vapor in
  v8.x docs, code is roadmap for v9.2 (W190-W193).
- **Supervisor** — `backend/core/supervisor/` directory does not exist.
  Budget cap, HIL gate, kill switch are roadmap for v9.2 (W199-W201).
  **Implication:** do NOT install third-party plugins yet.
- **Native skills** (Quest/Stake/Arena/Discovery) — vapor; roadmap v9.3.
- **T2T agent-to-agent** — vapor; roadmap v9.3.
- **Plugin payments / 70-30 payout / publisher registry** — vapor;
  roadmap v9.3.
- **Magic-link sign-in / meeet.world OAuth broker** — vapor; brother
  endpoints pending per `HANDOFF_v9.2_FOR_BROTHER.md`.
- **iOS / Android / multi-tenant SaaS** — v10+.

This is **not** a "soft launch we hope the gaps don't matter" release.
This is an explicit beta where the operator knows the limits going in.

## Distribution

For your 10-50 power-user beta cohort:

```bash
git clone https://github.com/alxvasilevvv/tars-neural-cockpit.git ~/tars
cd ~/tars/jarvis
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Edit .env to add ANTHROPIC_API_KEY or OPENROUTER_API_KEY
```

Then double-click `scripts/tars-start.command` in Finder.

Full readme: [docs/BETA_v9.2_README.md](./BETA_v9.2_README.md).

## Migration from v9.1.4

Zero breaking changes. If you have v9.1.x running:

```bash
git pull origin main
./.venv/bin/pip install -r requirements.txt --upgrade
kill $(cat /tmp/tars-backend-8765.pid)  # stop old backend
# Double-click scripts/tars-start.command to restart
```

No env changes required. Existing `~/.tars/` data is preserved.

## Testing

Run `scripts/test-categories.command` for live diagnostic:

| Category | Count | Status |
|---|---:|:-:|
| doctor | 25 | ✅ |
| doctor_router | 14 | ✅ |
| doctor_fixers | 9 | ✅ |
| daemon | 34 | ✅ |
| clone_sync | 9 | ✅ |
| notifications | 64 | ✅ |
| billing | 7 | ✅ |
| cowork | 52 | ✅ |
| mcp | 21 | ✅ |
| receipts | 36 | ✅ |
| voice | 28 | ✅ |
| marketplace | 24 | ✅ |
| **Total** | **323** | **100%** |

## Roadmap

- **v9.2.0 stable** (4-6 weeks): voice loop, supervisor real, ack/snooze,
  fixed Tauri /cockpit, signed `.dmg`
- **v9.3.0** (6-8 weeks): marketplace payments, T2T, native skills,
  meeet OAuth broker
- **v10.0.0** (12 weeks): port v7.1 agent suite, AI Clone v1 with LoRA,
  cross-platform installers, SOC 2 Type I

See [docs/ROADMAP_v9.2_v10.md](./ROADMAP_v9.2_v10.md) for the full plan.

## Feedback

- GitHub issues: https://github.com/alxvasilevvv/tars-neural-cockpit/issues
- Roadmap: docs/ROADMAP_v9.2_v10.md
- Architecture: docs/

## Acknowledgments

- 323 tests passing thanks to the operational layer work
  (W149-W196) over the past quarter
- Honest framing thanks to the W187 orchestrated audit
- The brother on meeet.world side — your half is critical for v9.3

Now go install it and tell us what's broken.
