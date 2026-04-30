# TARS — Cursor lane roadmap

> **For:** Claude (Lovable-side / meeet.world agent)
> **By:** Cursor (TARS-side agent)
> **Date:** 2026-05-01

This is the slice of the shared roadmap that lives on the Cursor lane.
The full master is `docs/ROADMAP_SHARED.md` — read both together.

## Stage 0 — `tars.meeet.world` integration (this week)

**Status:** Cursor is **complete** on its lane. Landing on Operator +
Claude.

| Lane | Item | Status |
|---|---|---|
| Cursor | CF Pages config (`_headers`, `_redirects`, `_middleware.ts`) | ✅ Merged |
| Cursor | Acceptance automation (`make acceptance-tars-meeet`) | ✅ Merged |
| Cursor | Observability runbook (`docs/OBSERVABILITY.md`) | ✅ Merged |
| Cursor | Canonical flip → `tars.meeet.world` (draft PR) | 🟡 Draft PR #11 — promotes post-DNS |
| Operator | DNS CNAME + CF Pages env vars | ⏳ Pending |
| Operator | GitHub repo secrets (`CLOUDFLARE_*`) | ⏳ Pending |
| Claude | Lovable Prompt 2 (CORS + cookie domain) | ⏳ Queued |
| Claude | Lovable Prompt 3 (navbar hotfix) | ⏳ Queued |
| Claude | Handoff package (`docs/agent-handoff/`) | 🟡 3/7 files committed |

## Stage 1 — `tars.meeet.world` post-launch (next 2 weeks)

| Lane | Item | Notes |
|---|---|---|
| Cursor | First production smoke + canonical-flip merge | Post-DNS |
| Cursor | Hot-fix iteration if §3 acceptance gates regress | On-call |
| Cursor | `tars.client.error` global handler (observability §6.1) | Ships next |
| Claude | 301 from `meeet.world/{install,pricing,faq,…}` to subdomain | Coordinates with canonical PR |
| Claude | `/api/tars/downloads` proxy on meeet-app | Spec §4 Option A; optional |
| Both | Status row on `status.meeet.world` | Operator action |

## Stage 2 — Tauri release (Q3-2026)

Cursor lane:

- v0.9.0-rc.1 → v0.9.0 GA on macOS (arm64 + x64)
- Auto-updater wired to `tars-downloads` manifest
- Code-signing + notarization in `release-tagged.yml` workflow
- Linux build added (currently disabled in matrix per cost)

Coordinated change with Claude:

- `meeet.world` install page must show "Open in TARS desktop" button
  once a deep-link scheme is registered.
- `core-bridge` may emit `tars.desktop.installed` event back to
  meeet-core for analytics.

## Stage 3 — `$MEEET` economy participation (Q4-2026)

Cursor lane (planning, not committed):

- Wallet view in cockpit (read-only first; signing later via Tauri
  invoke + secure storage).
- Per-LLM-call accounting against the user's `$MEEET` balance, with
  a clear pre-flight cost preview.
- Quest completion events emitted through `core-bridge` so the meeet
  side can mint rewards.

This stage requires explicit contract work — not ship-without-design.

## Open questions (Cursor → Claude)

1. **Q1 — Cookie linking.** When a user signs into `meeet.world`, the
   meeet-app sets `meeet_session` cookie on `.meeet.world`. Cursor's
   edge middleware reads `tars_session_id` (separate cookie). Should
   we link them through `core-bridge` `link-session` event, or leave
   them unlinked? (Affects analytics fidelity, not security.)
2. **Q2 — Quest completion ingest.** Can a TARS desktop event mark a
   meeet quest as complete (via `core-bridge` `quest_completed`), or
   does that always require an authenticated meeet-app round-trip?
3. **Q3 — Wallet ownership.** When TARS holds the user's wallet
   client-side (no custody), how does meeet-app verify on-chain
   ownership without ever seeing the secret? (Probable answer: signed
   message round-trip, but I want to confirm we agree on the schema.)
4. **Q4 — Edge Function deploy ownership.** Today Lovable auto-deploys
   anything in `supabase/functions/`. Is there a way to tag a function
   "Cursor-owned" so it is reviewed on PR but not redeployed unless
   Cursor explicitly approves? (Today Cursor must mirror the change
   in two repos and is not great.)
5. **Q5 — Handoff cadence.** Should the agent-handoff package be
   refreshed quarterly, on every major release, or only on demand?
   Cursor proposes "on demand + at every major release".

## Backlog (low priority, Cursor lane)

- `phase1-lab/` end-to-end demo for the dual-Supabase architecture.
- Per-route Web Vitals into `core-bridge`.
- A `tars-meeet.workers.dev` staging slot, separate from production.
- Synthetic monitor (CF Workers cron) hitting `/api/product/downloads`
  every 5 min and alerting on persistent failures.
