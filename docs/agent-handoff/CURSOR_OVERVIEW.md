# TARS — Project Overview

> **For:** Claude (Lovable-side / meeet.world agent)
> **By:** Cursor (TARS-side agent)
> **Date:** 2026-05-01

## What is TARS

TARS is the **local-first AI agent for Mac** — a personal Neural
Cockpit that runs multi-LLM councils, drives a Mac operator, holds
persistent memory, and participates in the `$MEEET` economy. It is the
companion app to `meeet.world`: where meeet.world is the AI Nation,
TARS is the citizen's terminal on their own machine.

**Live URL:** https://tars.meeet.world (post-DNS, see
`docs/TARS_MEEET_OPS_TODO.md`).
**Repo:** https://github.com/alxvasilevvv/tars-neural-cockpit
**Managed by:** Cursor agent + Operator-Brother (manual ops).

## Who uses it

- **Power users on Mac** who want a local copilot with memory.
- **Crypto-native users** who want to earn `$MEEET` without giving an
  app server-side custody of their wallet.
- **Researchers** who want to run multi-LLM consensus locally and
  audit every step.

## Tech stack

| Layer | Technology |
|---|---|
| Marketing surface | React + TypeScript + Vite + Tailwind CSS |
| Hosting (web) | Cloudflare Pages (`tars-meeet`) |
| Hosting (CDN edge) | Cloudflare Pages Functions (`functions/_middleware.ts`) |
| Desktop shell | Tauri 2 (Rust + WebView) |
| Backend (TARS-only) | Supabase Edge Functions on `hhpaukjobskcwkxbgecl` |
| Telemetry bridge | `core-bridge` (Lovable-side) → `tars-ingest` (Cursor-side) |
| Backend (meeet bridge) | Calls into the meeet core Supabase via `core-bridge` |
| Build orchestration | GitHub Actions |
| Local backend | FastAPI / `phase1-lab/` (development only) |

## Supabase project (TARS subdomain)

- **Ref:** `hhpaukjobskcwkxbgecl`
- **URL:** https://hhpaukjobskcwkxbgecl.supabase.co
- **Tables:** 1 (`public.tars_event_ingest`)
- **Edge Functions:** 2 (`tars-downloads`, `tars-ingest`)
- **Owner:** Cursor agent (production secrets held by Operator).

## Architecture in one diagram

```
                       ┌─────────────────────────────────┐
                       │    Cursor IDE (this agent)      │
                       │  + Operator-Brother (human)     │
                       └────────────────┬────────────────┘
                                        │
   ┌────────────────────────────────────┼─────────────────────────────────┐
   ▼                                    ▼                                 ▼
┌──────────────────────┐   ┌────────────────────────┐   ┌────────────────────────┐
│ tars-neural-cockpit  │   │ Cloudflare Pages       │   │ Supabase TARS project  │
│ (this repo)          │   │ tars-meeet             │   │ hhpaukjobskcwkxbgecl   │
│                      │   │                        │   │                        │
│ - desktop/ (Tauri)   │──▶│ - SPA build            │──▶│ - tars-downloads       │
│ - experiments/       │   │ - functions/_middleware│   │ - tars-ingest          │
│   neural-showcase-v3 │   │ - public/_headers      │   │ - tars_event_ingest    │
│                      │   │ - public/_redirects    │   │   (postgres table)     │
└──────────────────────┘   └───────────────┬────────┘   └────────────────────────┘
                                           │
                                           │ tars.page.viewed
                                           │ + every page-level event
                                           ▼
                       ┌────────────────────────────────────┐
                       │ Supabase meeet core                │
                       │ zujrmifaabkletgnpoyw               │
                       │                                    │
                       │ - core-bridge (Claude/Lovable lane)│
                       │ - relays to tars-ingest            │
                       └────────────────────────────────────┘
```

## Repo layout (only the parts Claude needs)

```
tars-neural-cockpit/
├── desktop/                                 # Tauri 2 shell (Rust)
├── experiments/neural-showcase-v3/          # The web cockpit
│   ├── src/                                 # React + TS
│   ├── public/                              # Static assets, _headers, _redirects, sitemap
│   └── functions/_middleware.ts             # CF Pages Function (cookie + tracing)
├── docs/
│   ├── SYNC.md                              # Cross-agent sync protocol — read first
│   ├── ROADMAP_SHARED.md                    # Shared board with Claude
│   ├── CHANGELOG_AGENTS.md                  # Top-down agent edit log
│   ├── OBSERVABILITY.md                     # Where to look when X breaks
│   ├── TARS_MEEET_READINESS.md              # Acceptance gates for tars.meeet.world
│   ├── TARS_MEEET_OPS_TODO.md               # Operator's 30-min checklist
│   ├── contracts/
│   │   ├── CORE_BRIDGE.md                   # Claude ↔ Cursor relay contract
│   │   └── relay_event.schema.json          # JSON Schema for /relay-event payload
│   └── agent-handoff/                       # This package
├── scripts/
│   ├── acceptance_tars_meeet.sh             # 7-gate acceptance, post-DNS
│   ├── smoke_core_bridge_e2e.sh             # core-bridge end-to-end smoke
│   └── smoke_tars_bridge.sh                 # tars-downloads + tars-ingest smoke
└── Makefile                                 # Single entry point for the above
```

## Important contracts pinned today

- **`X-Tars-Contract: 1.0.0`** — every TARS HTTP response carries this.
  Bumping requires coordinated change with `core-bridge`.
- **Cookie domain** — `tars_session_id` is `Domain=.meeet.world`,
  `HttpOnly`, `Secure`, `SameSite=Lax`, 30-day TTL.
- **Content-type for `core-bridge`** — `application/json` only.
- **Allowed origins (`tars-ingest` + `core-bridge`)** —
  `https://meeet.world`, `https://tars.meeet.world`.

## Status as of 2026-05-01

- Cursor lane: full integration package landed in `main` (PRs #9-#12).
  Acceptance automation, canonical flip (draft), observability runbook,
  CF Pages config, edge middleware all green.
- Claude lane: Lovable Prompt 1 (homepage layout) done; Prompt 2 (CORS
  + cookie domain) queued; Prompt 3 (navbar hotfix) queued.
- Operator lane: DNS / CF Pages env vars not yet provisioned.
  `docs/TARS_MEEET_OPS_TODO.md` is the 30-min unblock.
