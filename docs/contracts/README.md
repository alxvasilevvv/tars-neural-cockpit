# `docs/contracts/` — frozen wire shapes

This folder is the **handshake** between TARS and anything that talks
to it: the marketing site, **meeet.world**, the Tauri desktop shell,
the iOS / Android companions.

Every file here either:

1. **Pins** an existing contract that ships in code (mark as
   `**Status:** SHIPPED`), or
2. **Drafts** a future contract so multiple agents can build against
   the same blueprint (mark as `**Status:** DRAFT`).

Drafts must be turned into shipped contracts (or deleted) before
the matching phase declares green.

## Index

| File | Status | What it pins |
|------|--------|--------------|
| `MEEET_DOWNLOADS.md` | SHIPPED | `GET /api/product/downloads` etc. — public download manifest. |
| `download_manifest.schema.json` | SHIPPED | JSON Schema (Draft 2020-12) for `MEEET_DOWNLOADS.md`. |
| `CORE_BRIDGE.md` | SHIPPED | meeet core ↔ TARS bridge: `/health`, `/token-stats`, `/relay-event` on the old Supabase project (`zujrmifaabkletgnpoyw`). |
| `relay_event.schema.json` | SHIPPED | JSON Schema (Draft 2020-12) for `POST /functions/v1/core-bridge/relay-event`. |
| `L5_PAIRING_DRAFT.md` | DRAFT | Device pairing handshake, encrypted sync envelope (`meeet` contract 1.1.0). |

## Conventions

- **One file per contract.** Don't bundle "all of L5" into one file
  if pairing and the encrypted envelope can ship at different cadences.
- **Major-versioned.** Field renames or removals = major bump.
  Adding optional fields = minor bump. Document the bump in a
  Changelog section at the bottom of each file.
- **Always include a wire example.** Every field listed in a table
  must also appear in a JSON example so consumers can copy-paste a
  starting point.
- **Cross-link tests.** Each shipped contract names the pytest module
  that pins its shape (`tests/test_meeet_contract.py`,
  `tests/test_product_downloads.py`, …).

## Why this folder exists

When two agents (Cursor + Claude) build different surfaces against
the same backend, the contract is the only thing that prevents
"works on my machine". The folder is intentionally cheap — markdown
+ JSON Schema, no code generation, no SDK generation. If a contract
needs to be enforced at runtime, it lives in `backend/core/<x>/`
beside its tests.

**Onboarding another machine:** `docs/SECOND_MACHINE_HANDOFF.md` —
env templates, pytest/showcase verification, GitHub Pages note, links
into this folder for meeet.world integration.
