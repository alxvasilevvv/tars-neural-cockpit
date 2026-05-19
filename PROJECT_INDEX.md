# PROJECT_INDEX — every doc in the repo, one line each

> **Status:** maintained alongside `TARS_MASTER_DOC.md`. Updated W247
> (was W236; refreshed at Wave A 90% mark to add line counts on
> most-cited deep-dives and confirm W-tags of last touch).
> **How to read this file:** if you are looking for *anything* about TARS,
> start here. Find the right doc, click through. If you can't find what you
> need, that's a doc gap — fix it.

The single source of truth is `TARS_MASTER_DOC.md`. Everything below is
either a deep-dive on a section of that doc, a historical handoff, a per-feature
spec, or a release note. **If you change one of these, do not also try to
restate it in the master doc — link to it instead.**

---

## Read first

| Doc | What it is | Last touched |
|---|---|---|
| [TARS_MASTER_DOC.md](TARS_MASTER_DOC.md) | Single source of truth — North Star, architecture, roadmap, operator manual, brother brief, anti-patterns. ~1320 lines. | W264 |
| [README.md](README.md) | Repo front door — banner, what's new, quick start, pointer to master doc. | W236 |
| [PROJECT_INDEX.md](PROJECT_INDEX.md) | This file. | W264 |
| [CURRENT_STATUS.md](CURRENT_STATUS.md) | Daily-glance snapshot — last 10 commits, what works, brother dependencies, next 3 shipping. ~80 lines. | W247 |

## Strategy

| Doc | What it is | Last touched |
|---|---|---|
| [docs/COMPETITIVE_ANALYSIS_CURSOR.md](docs/COMPETITIVE_ANALYSIS_CURSOR.md) | 705-line gap matrix vs Cursor: where we lead, where we lag, surgical closure plan. | W234 |
| [docs/ROADMAP_W234_to_v10.md](docs/ROADMAP_W234_to_v10.md) | 453-line Wave A in commit-sized detail (W234-W260) + Wave B/C scope. | W234 |
| [docs/PRICING_ECONOMICS_v9.2.md](docs/PRICING_ECONOMICS_v9.2.md) | 403-line tier numbers, provider costs, markup policy, anti-abuse rules. The numbers brother needs. | W234 |
| [docs/MASTER_ROADMAP_v9.1_to_v10.0.md](docs/MASTER_ROADMAP_v9.1_to_v10.0.md) | Six-month north star, predating Wave A. Superseded by the trio above but kept for context. | W148 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Pre-v9.2 roadmap. Historical. | W74 |
| [docs/ROADMAP_v9.2_v10.md](docs/ROADMAP_v9.2_v10.md) | Earlier v9.2->v10 plan. Superseded by W234 trio. | W188 |
| [docs/PHASE_L_ROADMAP.md](docs/PHASE_L_ROADMAP.md) | Phase-L (landing polish + meeet integration). | W168 |
| [docs/PRODUCT_MASTER_PLAN.md](docs/PRODUCT_MASTER_PLAN.md) | **W310 — Post-rc1 dock + post-v10 forward roadmap.** v10 GA final push (5 external items + internal docking), v10.1/v10.2/v11 phase closure (L3/L4/L5/L6/L7/L9/L10), Claude design polish backlog, lane discipline, risks. Source-of-truth for *forward* execution; pairs with `TARS_MASTER_DOC.md §6` (historical Wave A/B/C). | W310 |
| [docs/TOKENOMICS_CANON_PROPOSAL.md](docs/TOKENOMICS_CANON_PROPOSAL.md) | $MEEET tokenomics proposal. Reference for §7.4 burn/earn logic. | W175 |
| [docs/IDEAS.md](docs/IDEAS.md) | Long-tail idea capture. Not the plan — the dump. | various |

## Architecture

| Doc | What it is | Last touched |
|---|---|---|
| [docs/DB_AUDIT_v9.2.md](docs/DB_AUDIT_v9.2.md) | 106-line audit of every SQLite store, JSON blob, and directory under `~/.tars/`. Where data lives. | W231 |
| [docs/STORYBOARD_VOICE_COCKPIT.md](docs/STORYBOARD_VOICE_COCKPIT.md) | 398-line, 8 frames of voice cockpit UX — Boot / Idle / Listen / Think / Speak / Error / Drawer / Reduced-motion. | W230 |
| [docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md](docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md) | 495-line spec — the 4 auth endpoints brother ships. Sequence diagrams, env vars, acceptance criteria. **Re-confirmed W247.** | W233 |
| [docs/NOTIFICATIONS.md](docs/NOTIFICATIONS.md) | iMessage / Telegram / Email contract for the notification fanout. | W164 |
| [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) | Trust boundaries + adversary model. | W79 |
| [docs/SECURITY.md](docs/SECURITY.md) | Public security posture, disclosure policy. | W79 |
| [docs/SECURITY_BASELINE.md](docs/SECURITY_BASELINE.md) | Hardening defaults, key handling. | W79 |
| [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md) | OpenTelemetry contract, request_id propagation. | W32 |
| [docs/MEEET_INTEGRATION_MAP.md](docs/MEEET_INTEGRATION_MAP.md) | Per-endpoint contract for the `meeet.world` integration surface. | W148 |
| [docs/ONPREM_DEPLOYMENT_GUIDE.md](docs/ONPREM_DEPLOYMENT_GUIDE.md) | **W263 — On-prem deployment playbook.** 435 lines. Hardware reqs, one-line install, IdP setup (SAML/OIDC), backup/restore, Prometheus + OTel monitoring, air-gapped path, hardening checklist. Pairs with `scripts/ONPREM-DEPLOY/` + `backend/core/onprem/`. | W263 |
| [docs/contracts/](docs/contracts/) | JSON Schema event contracts (per-version). | various |

## Operations

| Doc | What it is | Last touched |
|---|---|---|
| [docs/OPERATOR_v9.2.md](docs/OPERATOR_v9.2.md) | 5-minute path from install to first useful action. | W213 |
| [docs/OPERATOR_RUNBOOK.md](docs/OPERATOR_RUNBOOK.md) | Full operator runbook — pre-launch, launch, post-launch, recovery. | W64 |
| [docs/OPERATOR_LAUNCH_PLAYBOOK.md](docs/OPERATOR_LAUNCH_PLAYBOOK.md) | Pre-launch playbook. Historical. | W64 |
| [docs/WHAT_WORKS_v9.2.0-beta2.md](docs/WHAT_WORKS_v9.2.0-beta2.md) | Honest per-feature ship state as of beta2. | W215 |
| [docs/WHAT_WORKS.md](docs/WHAT_WORKS.md) | Earlier WHAT_WORKS. Superseded by `_v9.2.0-beta2`. | W215 |
| [docs/SMOKE-TEST-RESULTS.md](docs/SMOKE-TEST-RESULTS.md) | 142-line latest E2E smoke output. | W227 |
| [docs/QA_DEEP_2026-05-01.md](docs/QA_DEEP_2026-05-01.md) | Deep QA pass before beta2 ship. | W197 |
| [docs/QA_LOCAL_SETUP.md](docs/QA_LOCAL_SETUP.md) | How to run QA locally. | W197 |
| [docs/QA_PASSPORT_v9.2.0-beta1.md](docs/QA_PASSPORT_v9.2.0-beta1.md) | beta1 QA passport. | W198 |
| [docs/QA_AGENT_RUNBOOK.md](docs/QA_AGENT_RUNBOOK.md) | How a QA agent picks up the test surface. | W199 |
| [docs/REALITY_AUDIT_2026-05-13.md](docs/REALITY_AUDIT_2026-05-13.md) | Pre-beta2 reality check — what really works vs claimed. | W215 |
| [docs/SYSTEM_AUDIT_2026-05-02.md](docs/SYSTEM_AUDIT_2026-05-02.md) | System-level audit (architecture, deps, security). | W197 |
| [docs/SYSTEM_AUDIT_2026-05-03.md](docs/SYSTEM_AUDIT_2026-05-03.md) | Follow-up system audit. | W197 |
| [docs/DISASTER_RECOVERY.md](docs/DISASTER_RECOVERY.md) | Recovery playbook for catastrophic data loss. | W74 |
| [docs/AUTOMATION.md](docs/AUTOMATION.md) | Background daemon + scheduler operations. | W152 |
| [docs/COWORK_HEALTH_SNAPSHOT.md](docs/COWORK_HEALTH_SNAPSHOT.md) | Cowork multiplayer status snapshot. | W129 |
| [docs/LAUNCH_NOW.md](docs/LAUNCH_NOW.md) | Pre-launch checklist for `scripts/LAUNCH-NOW.command`. | W218 |
| [docs/LAUNCH_READINESS.md](docs/LAUNCH_READINESS.md) | Launch-readiness gate. | W139 |
| [docs/LAUNCH_TODAY_2026-05-01.md](docs/LAUNCH_TODAY_2026-05-01.md) | Day-of-launch ops. | W199 |
| [docs/GO_LIVE_48H.md](docs/GO_LIVE_48H.md) | 48-hour go-live runbook. | W199 |
| [docs/RELEASE_RUNBOOK_2026-05-01.md](docs/RELEASE_RUNBOOK_2026-05-01.md) | Release runbook for beta1 cut. | W197 |

## Per-feature deep-dives

| Doc | What it is | Last touched |
|---|---|---|
| [docs/B2B_WORKSHOP.md](docs/B2B_WORKSHOP.md) | B2B Workshop mode — companies/funds onboard. | W80 |
| [docs/DOMAIN_PACKS.md](docs/DOMAIN_PACKS.md) | 7 domain packs — wealth/health/family/product/brand/entrepreneur/civic. | W204 |
| [docs/ALGOTRADE.md](docs/ALGOTRADE.md) | Algotrade pack spec. | W81 |
| [docs/DESKTOP.md](docs/DESKTOP.md) | Tauri 2 desktop wrapper details. | W201 |
| [docs/DESKTOP_OWNERSHIP_PASS.md](docs/DESKTOP_OWNERSHIP_PASS.md) | Apple cert and signing ownership. | W113 |
| [docs/APPLE_SIGNING_NEXT_TIME.md](docs/APPLE_SIGNING_NEXT_TIME.md) | Apple Developer ID signing checklist for the next attempt. | W113 |
| [docs/WEB_SEARCH.md](docs/WEB_SEARCH.md) | Web search pack — Brave / SearXNG / DDG. | W104 |
| [docs/VOICE_CLONING_OPERATOR.md](docs/VOICE_CLONING_OPERATOR.md) | XTTS-v2 voice cloning operator notes. | W39 |
| [docs/PRIVACY_POLICY.md](docs/PRIVACY_POLICY.md) | Public privacy policy. | W173 |
| [docs/TERMS_OF_SERVICE.md](docs/TERMS_OF_SERVICE.md) | Public terms of service. | W173 |
| [docs/FAQ.md](docs/FAQ.md) | Public-facing FAQ. | W171 |
| [docs/BETA_v9.2_README.md](docs/BETA_v9.2_README.md) | Beta-cohort readme. | W198 |
| [docs/MEEET_HOTFIX_NAVBAR_REGRESSION.md](docs/MEEET_HOTFIX_NAVBAR_REGRESSION.md) | meeet.world side hotfix notes. | W148 |
| [docs/MEEET_PROJECT_REVIEW.md](docs/MEEET_PROJECT_REVIEW.md) | Cross-instance project review (TARS + meeet.world). | W148 |
| [docs/TARS_MEEET_OPS_TODO.md](docs/TARS_MEEET_OPS_TODO.md) | Joint TARS+meeet ops todo. | W148 |
| [docs/TARS_MEEET_READINESS.md](docs/TARS_MEEET_READINESS.md) | Joint readiness check. | W197 |
| [docs/MASTER_PLAN_v9.1_PLUS.md](docs/MASTER_PLAN_v9.1_PLUS.md) | Master plan from v9.1 era. Historical context. | W148 |
| [docs/PRODUCT_PHASE_M.md](docs/PRODUCT_PHASE_M.md) | Phase-M product spec. | W175 |

## Brother handoffs (chronological)

| Doc | What it is | Last touched |
|---|---|---|
| [docs/INTEGRATION_FOR_BROTHER.md](docs/INTEGRATION_FOR_BROTHER.md) | Initial integration spec. | W59 |
| [docs/BROTHER_HANDOFF_v9.1.0.md](docs/BROTHER_HANDOFF_v9.1.0.md) | v9.1.0 handoff. | W119 |
| [docs/HANDOFF_v9.1.1_FOR_BROTHER.md](docs/HANDOFF_v9.1.1_FOR_BROTHER.md) | v9.1.1 handoff. | W158 |
| [docs/HANDOFF_v9.2_FOR_BROTHER.md](docs/HANDOFF_v9.2_FOR_BROTHER.md) | v9.2 handoff. | W194 |
| [docs/HANDOFF_brother_v9.2_beta2.md](docs/HANDOFF_brother_v9.2_beta2.md) | beta2 brother brief (W214). | W214 |
| [docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md](docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md) | **The current one** — 4 auth endpoints + acceptance criteria. | W233 |
| [docs/HANDOFF_W203.md](docs/HANDOFF_W203.md) | W203 engineering handoff (vision + auth_meeet + civic). | W203 |
| [docs/HANDOFF_WAKE_UP.md](docs/HANDOFF_WAKE_UP.md) | Wake-up brief for a fresh agent picking up the repo. | various |
| [docs/HANDOFF_WAVE_52.md](docs/HANDOFF_WAVE_52.md) | Wave 52 handoff. | W52 |
| [docs/CURSOR_HANDOFF_WAVE_56.md](docs/CURSOR_HANDOFF_WAVE_56.md) | Cursor-lane handoff at Wave 56. | W56 |
| [docs/AGENT_HANDOFF.md](docs/AGENT_HANDOFF.md) | Generic agent handoff template. | various |
| [docs/SECOND_MACHINE_HANDOFF.md](docs/SECOND_MACHINE_HANDOFF.md) | Onboarding for second-machine pickup. | W139 |
| [docs/REQUEST_TO_CLAUDE.md](docs/REQUEST_TO_CLAUDE.md) | Open requests to the Claude lane. | various |
| [docs/handoff/APPLE_SIGNING_FOR_CURSOR.md](docs/handoff/APPLE_SIGNING_FOR_CURSOR.md) | Cursor-lane Apple cert handoff. | W113 |
| [docs/handoff/COWORK_WIRING_FOR_CURSOR.md](docs/handoff/COWORK_WIRING_FOR_CURSOR.md) | Cursor-lane cowork wiring handoff. | W129 |
| [docs/handoff/MCP_REWRITE_BRIEF.md](docs/handoff/MCP_REWRITE_BRIEF.md) | **W310 (a).** Cockpit MCP panel rewrite spec — Wave 100 audit-corrected baseline + 4-step implementer plan (~12-15h), 16 spec-pinned tests. Replaces closed PR #177 (architecturally wrong; tried to add panel to wrong cockpit). | W310 |

## Release notes (chronological)

| Doc | Version | Theme |
|---|---|---|
| [docs/RELEASE_NOTES_0.1.0-alpha.2.md](docs/RELEASE_NOTES_0.1.0-alpha.2.md) | 0.1.0-alpha.2 | First alpha. |
| [docs/RELEASE_NOTES_v0.1.0-rc.1.md](docs/RELEASE_NOTES_v0.1.0-rc.1.md) | 0.1.0-rc.1 | First RC. |
| [docs/RELEASE_NOTES_v9.1.0.md](docs/RELEASE_NOTES_v9.1.0.md) | v9.1.0 | Cowork + MCP + doctor + signed builds attempt + B2B Workshop. |
| [docs/RELEASE_NOTES_v9.1.1.md](docs/RELEASE_NOTES_v9.1.1.md) | v9.1.1 | `tars-doctor` CLI + `/api/doctor` HTTP + Status page live. |
| [docs/RELEASE_NOTES_v9.1.2.md](docs/RELEASE_NOTES_v9.1.2.md) | v9.1.2 | iMessage + Telegram + Email bridges + auto-fanout. |
| [docs/RELEASE_NOTES_v9.1.3.md](docs/RELEASE_NOTES_v9.1.3.md) | v9.1.3 | `tars-doctor --fix` mode + `POST /api/doctor/fix`. |
| [docs/RELEASE_NOTES_v9.1.4.md](docs/RELEASE_NOTES_v9.1.4.md) | v9.1.4 | Windows daemon parity + `--watch` mode + 3 new checks. |
| [docs/RELEASE_NOTES_v9.2.0-beta1.md](docs/RELEASE_NOTES_v9.2.0-beta1.md) | v9.2.0-beta1 | Control Center cockpit + AI Clone webhook + first usage event. |
| [docs/RELEASE_NOTES_v9.2.0-beta2.md](docs/RELEASE_NOTES_v9.2.0-beta2.md) | v9.2.0-beta2 | Auth gate + voice cockpit + meeet handshake + consumption console. |
| [docs/RELEASE_NOTES_v9.3.0-beta1.md](docs/RELEASE_NOTES_v9.3.0-beta1.md) | v9.3.0-beta1 | Wave A — Cursor parity panels + Cmd+K v2 + codebase indexer + WS event bus + tier cap UX + privacy mode. |
| [docs/RELEASE_NOTES_v10.0-rc1.md](docs/RELEASE_NOTES_v10.0-rc1.md) | v10.0.0-rc.1 | Wave A + B + C bundled — voice Composer + VS Code ext + audit explorer + SOC2 + T2T + marketplace + voice pair-prog + on-prem kit. |
| [CHANGELOG.md](CHANGELOG.md) | (rolling) | Top-level rolling changelog. |
| [docs/CHANGELOG_PUBLIC.md](docs/CHANGELOG_PUBLIC.md) | (rolling) | User-facing changelog (auto-generated from commits). |
| [docs/CHANGELOG_AGENTS.md](docs/CHANGELOG_AGENTS.md) | (rolling) | Per-edit log for agents. Append, don't rewrite. |

## Sign-offs and ownership passes

| Doc | What it is | Last touched |
|---|---|---|
| [docs/WAVE_53_LAUNCH_SIGNOFF.md](docs/WAVE_53_LAUNCH_SIGNOFF.md) | Wave 53 sign-off. | W53 |
| [docs/WAVE_55_SIGNOFF.md](docs/WAVE_55_SIGNOFF.md) | Wave 55 sign-off. | W55 |
| [docs/WAVE_59_DESKTOP_SIGNOFF.md](docs/WAVE_59_DESKTOP_SIGNOFF.md) | Desktop wrap-up sign-off. | W59 |
| [docs/V9_1_0_LAUNCH_PLAN.md](docs/V9_1_0_LAUNCH_PLAN.md) | v9.1.0 launch plan. | W119 |
| [docs/V9_1_0_LAUNCH_READINESS.md](docs/V9_1_0_LAUNCH_READINESS.md) | v9.1.0 readiness. | W119 |
| [docs/CHAT_PICKUP_2026-05-01.md](docs/CHAT_PICKUP_2026-05-01.md) | Cross-chat pickup notes. | W199 |
| [docs/SYNC.md](docs/SYNC.md) | Cross-lane sync state (Claude lane <-> Cursor lane). | various |
| [docs/PLAN_FORWARD.md](docs/PLAN_FORWARD.md) | Forward plan. | W185 |
| [docs/ROADMAP_TO_RELEASE.md](docs/ROADMAP_TO_RELEASE.md) | Path to release. | W139 |
| [docs/ROADMAP_SHARED.md](docs/ROADMAP_SHARED.md) | Shared roadmap (Claude + Cursor). | W148 |
| [docs/handoff-claude.md](docs/handoff-claude.md) | Claude-lane handoff. | various |

## Misc / supporting

| Doc | What it is | Last touched |
|---|---|---|
| [docs/VIDEO_TRANSCRIPTS.md](docs/VIDEO_TRANSCRIPTS.md) | Reference video transcripts (visual-design references). | W115 |
| [docs/templates/](docs/templates/) | Doc templates (release notes, handoff briefs, sign-offs). | various |
| [docs/audit/](docs/audit/) | Per-wave audit outputs. | various |
| [docs/handoff/](docs/handoff/) | Cursor-lane handoffs subdirectory. | various |
| [docs/launch/](docs/launch/) | Launch artefacts subdirectory. | various |
| [docs/release-evidence/](docs/release-evidence/) | Release-evidence artefacts. | various |
| [docs/security/](docs/security/) | Security artefacts. | various |
| [docs/agent-handoff/](docs/agent-handoff/) | Agent-handoff artefacts. | various |
| [docs/qa-snapshot.json](docs/qa-snapshot.json) | Latest QA snapshot blob. | W199 |
| [HANDOFF_INSTRUCTIONS.md](HANDOFF_INSTRUCTIONS.md) | Top-level handoff instructions. | various |
| [CLAUDE.md](CLAUDE.md) | Claude-lane operating instructions for picking up the repo. | various |

---

**Doc count:** ~95 markdown files under `docs/` + 5 at the root
(`README.md`, `TARS_MASTER_DOC.md`, `PROJECT_INDEX.md`, `CURRENT_STATUS.md`,
`CHANGELOG.md`, plus `CLAUDE.md` + `HANDOFF_INSTRUCTIONS.md`). If you
write a new doc, add it here, and link it from the relevant master-doc
section.
