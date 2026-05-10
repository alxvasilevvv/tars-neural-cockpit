# Agent handoff — TARS

Pick this up if you are continuing the work in a fresh chat. Read this file
plus `docs/CHANGELOG_AGENTS.md` and `docs/IDEAS.md` first.

> **2026-05-09 — operator UX hardening + B-017/B-018 stack landed.**
>
> Five Cursor PRs were opened across 2026-05-08/09 and **all
> merged to `main`** (CF Pages auto-deployed on each merge):
>
> - **#159** `cursor/unfreeze-prod-build` (B-018) — unblocked the
>   Cloudflare Pages production build that had been silently
>   failing since ≈Wave 65. Root cause: unguarded
>   `@tauri-apps/api` dynamic imports + stale `BrandHairline`
>   import + `tsc -b` in the `build:cf` script. Fix: marked
>   Tauri runtime modules as Rollup `external`, fixed the import,
>   aligned `build:cf` with the documented `vite build`-only
>   recipe (typecheck still runs separately as `npm run
>   typecheck` in the CI workflow).
>
> - **#155** `cursor/b017-install-funnel-fix` — same-origin
>   install funnel via Pages Function `functions/dl/[file].ts`.
>   `_redirects` no longer rewrites `/install.sh`; `public/
>   install.sh` + `scripts/install-tars.sh` resolve via
>   `tars.meeet.world/api/product/version` and download via
>   `tars.meeet.world/dl/<filename>`.
>
> - **#160** `cursor/operator-playbook-drift-fix` (re-opened from
>   closed #156 after rebase on `main`) — closes 5 factual drifts
>   between `OPERATOR_LAUNCH_PLAYBOOK.md` and the live
>   scripts/workflow (Tauri key path, `TAURI_SIGNING_PRIVATE_KEY`
>   base64 encoding, release workflow trigger, download base URL,
>   `GITHUB_RELEASE_TOKEN` table row).
>
> - **#157** `cursor/operator-misc-fixes` — `make bootstrap`
>   single-command fresh-machine setup + actionable "venv
>   missing" hints in `backend_tars_up.sh` +
>   `smoke_billing_tars_backend.sh`; new playbook **Step 0a**.
>
> - **#158** `cursor/agent-handoff-2026-05-08` (this PR) —
>   AGENT_HANDOFF pointer for next-chat pickup.
>
> **Operator actions still owed (two unblocks, both ~30 sec each):**
>
> 1. **B-019 — switch custom-domain binding** (THIS IS THE BIG ONE).
>    `tars.meeet.world` is currently bound to the legacy
>    `tars-meeet` Pages project; every deploy lands on
>    `tars-meeet-git` instead. Result: 7 successful builds on
>    `tars-meeet-git` since 2026-05-08 (B-018, B-017, playbook
>    drift, bootstrap, AGENT_HANDOFF, precheck retry, bridge
>    secret hint) are stuck on `tars-meeet-git.pages.dev` and
>    invisible to anonymous visitors at `tars.meeet.world`. Fix:
>    Cloudflare dashboard → Pages → `tars-meeet` → Custom domains
>    → Remove `tars.meeet.world`; Pages → `tars-meeet-git` →
>    Custom domains → Set up `tars.meeet.world`. Detailed recipe
>    + verification curl in `docs/TARS_MEEET_OPS_TODO.md` (search
>    "B-019").
>
> 2. **`GITHUB_RELEASE_TOKEN` paste** (only matters AFTER B-019).
>    Fine-grained PAT, `Contents: Read-only` → Cloudflare Pages
>    → `tars-meeet-git` → Settings → Environment variables →
>    Production. Detailed recipe: `docs/TARS_MEEET_OPS_TODO.md`
>    §5. Until pasted, `tars.meeet.world/dl/<file>` returns a
>    clean 503 + `operator_action_required` JSON (the install
>    funnel is fully implemented, just blocked on the PAT).
>
> GitHub Actions billing is still failing on every probe job
> (see PR #153/#154 comment threads) but no longer blocks deploy
> — branch protection is off on `main` and CF Pages auto-deploys
> via its GitHub App, separate from Actions billing.

> **2026-05-05 — Commercial-readiness tests (product surface, no marketing).**
> `tests/test_commercial_readiness_chain.py` + `make test-commercial-readiness`
> — ordered GET chain for domains / entitlements / usage / product / policy /
> meeet / playbooks + B-001 download redirects. Full pytest **2411 passed**.

> **2026-05-05 — Billing narrative:** paid tiers are **SOL + $MEEET on Solana**
> only. `TARS_PAYMENT_MODE=onchain|tokens|stripe` (``stripe`` = deprecated alias)
> → same 503 stub until settlement ships; FAQ/Privacy/i18n updated.

> **2026-05-05 — Remote billing:** `TARS_BILLING_SOURCE=remote` + `MEEET_BILLING_*`
> → tier / cloud gate / spend mirror **meeet.world** (`docs/contracts/TARS_MEEET_BILLING.md`).
> **Implementing host:** Supabase edge **`tars-billing`** + table **`tars_billing_operators`**
> in **meeet-solana-state** (`functions/v1/tars-billing` + `GET …/operator`; secrets
> **`TARS_BILLING_API_KEY`** or **`MEEET_BILLING_API_KEY`** must match TARS).
> **Usage:** `POST …/operator/usage` with `delta_usd` + optional **`trace_id`** (edge dedupe table);
> TARS mirrors priced **`usage.tokens`** on routes `cloud`/`fallback`/`mixed` from **`MeeetClient.emit`**
> (after local durable insert) with retries (`MEEET_BILLING_USAGE_RETRIES`).
> Local `entitlements.json` is fallback UI only when remote snapshot fails.
>
> **2026-05-05 — Remote billing prod baseline (start line):** meeet core Supabase
> **`zujrmifaabkletgnpoyw`** — table **`public.tars_billing_usage_dedupe`**, edge
> **`tars-billing`** redeployed with **`trace_id`** idempotency; secret **`TARS_BILLING_API_KEY`**
> set (TARS uses the same value as **`MEEET_BILLING_API_KEY`**). Operator smoke:
> **GET …/operator**, first **POST …/operator/usage** then duplicate POST (spend
> unchanged), anon **REST** on dedupe → **`[]`**. Canonical TARS remote URL:
> `MEEET_BILLING_BASE_URL=https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/tars-billing`.
> Optional **`TARS_BILLING_CHECKOUT_BASE`** / **`TARS_BILLING_ACCOUNT_URL`** unset → defaults
> `https://meeet.world/billing/tars` and `https://meeet.world/account`.
> Local operator: **`make ops-billing-remote-wizard`** — hidden key paste, prod GET+POST idempotency smoke, optional **`.env`** merge.
> After `.env` is set: **`make smoke-billing-tars`** — same machine, stdlib **`fetch_operator_snapshot`** (no uvicorn) to confirm TARS reads prod.
> One command dev server: **`make backend-tars-up`** — frees **:8765**, starts **uvicorn** with **`.env`** in background, prints **`/api/entitlements`** billing JSON; stop: **`kill $(cat /tmp/tars-backend-8765.pid)`**.
> Full local stack (API bg + Vite fg): **`make dev-tars-stack`** — same as **`backend-tars-up`**, then **`pnpm dev`** in **`experiments/neural-showcase-v3`** (cockpit **5174** talks to API **8765** by default).

> **2026-05-04 — Go-live same-day closeout.** `docs/GO_LIVE_48H.md` is the
> operator checklist (**bridge on Pages**, GitHub `BRIDGE_SHARED_SECRET`,
> acceptance, optional `TARS_INGEST_API_KEY` for QA workflow + ingest). SPA now
> has real routes **`/pricing`**, **`/faq`**, **`/compare`** (lazy pages + meta);
> nav / palette / sitemap / QA probes updated. **`pnpm typecheck`**, vitest
> **377 passed** / 27 files green.
>
> **2026-05-05 — QA env parity.** `make qa-agent`, `acceptance-tars-meeet`, and `smoke-core-bridge`
> source **`scripts/with_repo_env.sh`** (loads repo **`.env`**). QA agent accepts
> ingest via **`TARS_INGEST_API_KEY`** **or** **`MEEET_API_KEY`**. **`gate_release.sh`** sources **`.env`**
> before bridge step. Secrets for **GitHub Actions** (**`BRIDGE_SHARED_SECRET`**,
> **`TARS_INGEST_API_KEY`**, **`CLOUDFLARE_API_TOKEN`**) are not in git — configure in repo Secrets.

> **2026-05-04 — Audit-6 — Landing dividers, ScrollStory narrative, CouncilDemo, MeeetWorldStrip, CockpitPreview (`useT`).**
> Migrates remaining section chrome and long-form mocks on `/`:
> `landing.section.{00–11}`, `scrollStory.*` (pinned story + header),
> `councilDemo.{eyebrow,subtitle}` (avoids collision with `/council` page
> `council.eyebrow` / `council.subtitle`), `council.d1–d3.*`, `meeetStrip.*`,
> `cockpitPreview.*` with `cockpitLive.title.*` + `cockpitLive.cta.openReal` +
> `domains.*.name` for the mock nav strip.
>
> Verification: `pnpm typecheck`, `pnpm build`, vitest **368 passed** /
> 26 files, i18n parity guard green.
>
> **Landing still English-only inside these surfaces** (defer follow-up): FAQ
> accordion entries (`FAQ.tsx` literal `FAQS`), Compare matrix rows (`ROWS` in
> `Compare.tsx`), and illustrative chrome inside `ScrollStory` visuals
> (“today's brief”, shell transcript, etc.).
>
> **2026-05-04 20:20 — Audit-5 — Layers, Domains, ProofStrip, MeeetSection (`useT`).**
> Migrated those four prose-heavy blocks with **60 new keys × 2 locales**
> (RU↔EN parity).
>
> Verification: pnpm typecheck clean, vitest **368 passed** /
> 26 files, parity guard green, production build clean.
>
> **2026-05-04 20:10 — Audit-4 i18n coverage pass.**
> Closed the last visible Landing-page i18n gap. Three of the
> loudest above-the-fold sections (Steps, Rail, CockpitLive)
> were still hard-coded English; all three now run through
> `useT()` with 38 new keys per locale (RU at 100% parity).
>
> Verification: pnpm typecheck clean, vitest **368 passed** /
> 26 files, parity guard green, production build clean.
>
> **2026-05-04 18:55 — Audit-3 release-resilience pass.**
> v9.1.0 shipped at 18:30 with 5 of 6 expected installers — the
> macos-13 (Intel) GitHub runner pool was queue-starved and the
> mac-x64 dmg job sat in "queued" for 40+ minutes. Cancelled the
> stuck job (release was already published with the other 5
> artifacts) and shipped four follow-ups:
>
> 1. `release-desktop-tagged.yml` macos-13 row now marks itself
>    `continue-on-error: true` with a 90-min timeout. The
>    downstream `notify` + `update-download-links` flows now
>    use `!failure() && !cancelled()` so an optional mac-x64
>    failure doesn't suppress the link summary.
>
> 2. `web_extras/routers/product.py` legacy `/dl/TARS-x.y.z-x64.dmg`
>    redirects fall back to the arm64 dmg until a future tag's
>    mac-x64 build succeeds (Rosetta runs the arm64 binary
>    cleanly). `<Install />` row reflects the same fallback +
>    "Intel x64 (via Rosetta)" label. New `intelMacFallbackToArm`
>    option on `primaryAssetName` covers any other call sites.
>
> 3. `web_extras/routers/memory.py` `POST /api/packs/{slug}/memory`
>    and `DELETE /api/packs/{slug}/memory/{key}` wrapped in
>    `trace_scope` with `memory.upsert.*` / `memory.delete.*`
>    meeet events. Pack memory writes feed prompt context, so
>    provenance lands in the trail.
>
> 4. v9.1.0 GitHub release body rewritten via `gh release edit`
>    to cover audit-1 + audit-2 + audit-3 + macOS first-run +
>    Intel-Mac-via-Rosetta.
>
> **Verification:** pytest **2406 passed** (+2) / 1 skipped /
> 2 xfailed (39s), vitest **368 passed** (+3) / 26 files,
> typecheck + production build clean.
>
> **Open operator follow-up:** future v9.1.x or v9.2.0 tag will
> rebuild the Intel mac dmg if the macos-13 runner pool is no
> longer queue-starved. Until then the fallback table in
> `product.py` keeps Intel Mac downloads working.
>
> **2026-05-04 18:05 — Audit-2 hardening pass.** Direct
> continuation of the 17:50 audit pass. Operator said "продолжай"
> at 17:51 → went looking for follow-ups. Three concrete deliveries:
>
> 1. **Trace coverage** extended over `voice.speak` + `speech.intents`.
>    Both now wrap in `trace_scope`, emit `*.requested/completed/failed`
>    meeet events, honour `x-meeet-trace-id` parent header, surface
>    the `trace_id` either as `x-trace-id` response header (voice)
>    or in the JSON body (speech).
> 2. **Pure helpers** extracted from `<CockpitGate />` (runtime
>    detection) and `<Install />` (OS+arch detection) — single
>    source of truth + 30 new vitest cases pinning the heuristics.
> 3. **Trace coverage tests** — `tests/test_meeet_router_trace_coverage.py`
>    pins the contract for chat / voice / speech: each successful
>    call MUST land at least one `*.requested` and one `*.completed`
>    row in the local meeet store with the right kind.
>
> **Verification:** pytest **2404 passed** (+6) / 1 skipped /
> 2 xfailed in 40s. Vitest **365 passed** (+30) across 26 files.
> Typecheck + production build clean.
>
> **Bonus:** `favicon.svg` regenerated to match the new desktop
> PNG icon (serif T on indigo→violet gradient) so the browser
> tab matches the Dock icon.
>
> **2026-05-04 17:50 — Operator audit pass.** The operator
> screenshot-reviewed the live deployment at 17:29 and filed seven
> blockers. All seven are closed in the same pass; full per-task
> details are in the most recent `docs/CHANGELOG_AGENTS.md` entry
> (search "operator audit pass").
>
> **What changed:**
>
> 1. **App icon** — premium 1024×1024 master generated, full Tauri
>    set + .icns + .ico + 6 web favicons regenerated via the new
>    `desktop/scripts/build_icon_set.py` (idempotent, runs on any
>    new master). Old icon (purple T in a thin cyan ring) replaced
>    with a richer indigo-violet gradient + serif T + cyan halo +
>    hexagonal HUD texture. Looks like a sibling of Linear / Cursor
>    / Arc in the Dock.
>
> 2. **Install page** — full rewrite. The old page made you read
>    a curl command and click a small `.dmg` link in a footer
>    (operator's quote: "там нужно на файл нажимать"). New page
>    leads with a single giant "Download for $OS · $arch" CTA,
>    auto-detects the architecture, and surfaces the Gatekeeper
>    fix prominently in amber.
>
> 3. **Gatekeeper "TARS is damaged"** — the screenshot showed
>    Apple's classic unsigned-binary modal. Two zero-cost fixes:
>    (a) `release-desktop-tagged.yml` now ad-hoc codesigns the
>    `TARS.app` after `tauri-action` (`codesign --force --deep
>    --sign -` + `xattr -cr`), so Right-click → Open works without
>    the "damaged" wording on the next release. (b) `install.sh`
>    one-liner hosted on tars.meeet.world that handles
>    download + ad-hoc sign + de-quarantine + launch in one shot.
>    Public-launch path is still Apple Developer Program
>    notarization ($99/yr — operator follow-up).
>
> 4. **Web cockpit** — was rendering a half-broken operator console
>    every time you visit `/cockpit` from the marketing host (no
>    daemon at 127.0.0.1:8765). New `CockpitGate` runtime check
>    detects Tauri vs browser, pings local daemon with a 1s budget,
>    and shows a brand-correct upgrade card when both fail (giant
>    "Get the app" CTA + 3 secondary paths: read-only preview,
>    docs, pitch). Wraps all 6 cockpit routes in App.tsx.
>
> 5. **meeet.world brand surface** — Nav.tsx adds a small
>    "by meeet.world" pill next to the TARS logo. All new copy on
>    Install + CockpitGate explicitly references meeet.world in
>    eyebrow + body. GitHub release notes (workflow yaml) embed
>    the meeet.world install.sh one-liner.
>
> 6. **Tracing coverage** — chat router was the largest hot
>    operator-facing surface without trace emission. Wrapped
>    `POST /api/chat/threads/{id}/messages` in `trace_scope`
>    + `chat.message.{requested,completed,failed}` events. SSE
>    stream emits an inline `trace` frame so the cockpit can stamp
>    conversations with their trace_id.
>
> 7. **i18n** — Nav gets a global `<LocaleSwitcher>` (was footer-
>    only). 60+ new strings (install.* + cockpitGate.* namespaces)
>    in EN + RU with full key parity — the i18n.test.ts parity
>    guard stays green.
>
> **Verification:** pytest 2398 passed / 1 skipped / 2 xfailed in
> 47s. Vitest 335 passed across 24 files. Production build clean.
>
> **Operator follow-ups (still open):**
> - Apple Developer Program enrollment ($99/yr) — required to
>   notarize and remove the Gatekeeper fix step entirely.
> - Tag a new release (`v9.1.0`) so the new install.sh + ad-hoc
>   codesign step actually fire. Until then existing v8.4.0 DMG
>   still needs the manual `xattr` fix.
> - Optional: paid translation pass for RU (current strings are
>   product-quality but a native RU writer could polish a handful
>   of edges, especially in Cockpit operator surfaces).
>
> **2026-05-04 17:25 — Autonomous-block end-of-day.** Five rounds
> closed back-to-back during the operator's 2-3 hour off-block.
> Everything below the line still applies; this paragraph is the
> delta since 16:30:
>
> **TARS lane (commits `cc54d7d`, `e6f477e`, `b863821`, `7567e9d`):**
>
> - **Round T-2 — L5 pairing crypto reality + DX**: docstring of
>   `backend/core/pairing/__init__.py` rewritten to reflect that real
>   X25519 / XChaCha20-Poly1305 / SealedBox already ship (the previous
>   "What's mock for now" wording was 1 phase stale). Added
>   `MeeetClient.emit_encrypted()` convenience method that resolves
>   recipients from the singleton `PairingStore`, seals via
>   `encrypt_event` with proper `trace_id|kind` AAD, and forwards
>   through the existing emit pipeline. 7 new pytest cases.
> - **Round T-3 — desktop sidecar pin parity**: rewrote
>   `desktop/pyoxidizer.bzl` so its `RUNTIME_REQUIREMENTS` list mirrors
>   `requirements.txt` exactly (was missing 6 packages incl. pynacl,
>   eth-account, tonsdk, solders), enabled
>   `policy.include_distribution_resources = True` so adjacent
>   `data/*.csv|json` seeds bundle. New parity guard test
>   `test_pyoxidizer_requirements_parity.py` (5 cases) so future
>   `requirements.txt` bumps fail loudly if `pyoxidizer.bzl` drifts.
> - **Round T-4 — SMTP OAuth initial-consent**: brand-new
>   `backend/core/domains/packs/business/oauth_consent.py` ships
>   `build_consent_url` (PKCE + signed state for Google / Microsoft /
>   common-tenant), `verify_state` (HMAC + freshness + provider
>   match), `exchange_authorization_code` (full token swap, OAuth
>   error propagation, transport guard). CLI helper
>   `scripts/smtp_oauth_consent.py` opens the browser, spawns a
>   one-shot HTTPServer, prints the env line. 31 pytest cases.
> - **Round R-1 — OAuth HTTP router + vault write-back**:
>   `web_extras/routers/oauth_consent.py` exposes
>   `POST /api/oauth/smtp/{start,exchange}`. New `set_secret` /
>   `delete_secret` in `backend/core/vault/keychain.py` (Keychain
>   write via `security add-generic-password -U`, env fallback on
>   non-Darwin). New `persist_refresh_token` helper auto-writes
>   refresh_token + accompanying client_id/secret/provider/tenant.
>   Refresh token never echoed when persistence succeeds (vault is
>   canonical, browser history would leak). Audit events
>   `business.smtp.oauth.consent.{started,completed,failed}` only
>   carry `client_id_tail` (last 6) and a `had_refresh_token` bool.
>   30 new pytest cases (14 vault + 16 router).
>
> **TARS pytest after T-2/T-3/T-4/R-1 batches: 2398 passed / 1
> skipped / 2 xfailed** (was 2315 last checkpoint, +83 cases).
>
> **Lovable lane (commits `31043daf`, `6f6a6f3d`, `a197c7ae`,
> `1c716228`):**
>
> - **Round L-2 — `mst_` API key smoke test**: new
>   `src/test/meeetExternalApi.test.ts` (6 vitest cases pinning
>   `getMeeetFunctionsBase` URL composition + `MEEET_TOKEN_MINT`
>   address). New `scripts/smoke_agent_api.sh` (4 checks: anon
>   `economy_snapshot`, anon `list_tasks`, mst-bearer 401, mst-x-api
>   401) with deploy-aware diagnostics — banner if `agent-api` returns
>   401 on `economy_snapshot` (means production is older than commit
>   `e531fb0f` and needs `supabase functions deploy agent-api`).
> - **Round L-3 — PR #33 triage**: PR #33 (DRAFT since 2026-05-02,
>   161 files, `@supabase/supabase-js` SDK unification) was made
>   un-mergeable by 3 days of main drift (8 conflict files: new
>   `@2.45.0` pin landed, `verifyBearerToken` renamed to
>   `requireUser/requireAgentOwner`). Closed as superseded by a
>   fresh sed-bump on top of current main (commit `6f6a6f3d`):
>   164 files, 166 references, 0 conflicts, all 3 CI workflows
>   green. SDK matrix: 6 versions → 1 (`2.57.4` everywhere).
> - **Round L-4 — tg-* ESLint cleanup**: 27 `@typescript-eslint/
>   no-explicit-any` errors → 0 across all 6 `tg-*` edge functions
>   via new shared module `supabase/functions/_shared/tg-types.ts`
>   (TelegramUser/Chat/Message/CallbackQuery/Update + AgentRow /
>   AgentMap / CountryRow / TreasuryRow / etc). All 6 deno check
>   clean. Frontend vitest 348 passed. JSON contracts (notably
>   tg-app-data `top_countries[]` shape) preserved exactly.
> - **Round L-5 — stale TODO sweep**: 2 actionable TODOs found,
>   both implemented (not just shelved):
>   - `src/components/profile/TelegramPanel.tsx` — replaced
>     client-side mock token generation with live
>     `supabase.functions.invoke("tg-bot-link", ...)` call.
>   - `supabase/functions/purchase-subscription/index.ts` — added
>     real on-chain verification via new shared
>     `_shared/solana-rpc.ts` module (`verifySolTransaction`
>     extracted from `create-subscription`, 10-conf wait, 2%
>     tolerance, walks inner instructions for CPI-wrapped
>     payments). Fixes a real undercharge-attack window.
> - 3 pre-existing `any` cleaned up while in the neighbourhood.
>   ESLint debt: 727 → 697 errors net.
>
> **Operator follow-ups still pending (not blocking, but worth
> doing on next session):**
>
> - **Lovable**: redeploy `agent-api` edge function to production —
>   the new code (commit `e531fb0f`, 2026-05-04) drops auth on
>   public read actions and surfaces the canonical MEEET mint, but
>   `supabase functions deploy agent-api` (or Lovable auto-deploy)
>   needs to run to ship it. Smoke script
>   `scripts/smoke_agent_api.sh` will detect a stale prod deploy
>   and tell the operator exactly what to do.
> - **TARS desktop**: actually run a `pyoxidizer build` for the 6
>   target triples to confirm the bundle assembles end-to-end. The
>   new parity guard test catches drift, but only an actual build
>   catches "this dependency wheel doesn't have an aarch64-apple
>   binary" surprises.
> - **TARS SMTP OAuth**: run a real consent flow via
>   `scripts/smtp_oauth_consent.py` once Google / MS OAuth app
>   credentials exist. The dance is fully wired and tested with
>   stubs; the only "untested in prod" path is the actual round-trip
>   to `accounts.google.com`.

> **2026-05-04 16:30 — Lovable post-refactor checkpoint.** Sister repo
> `alxvasilevvv/meeet-solana-state-941a6045` is fully healthy after the
> morning's 3-commit refactor (split Developer.tsx → DeveloperPortal +
> DashboardApiKeys + meeetExternalApi helper; parametrize SDK URLs via
> env; new `mst_<64 hex>` API key format aligned across api-keys and
> generate-api-key edge functions). Forward-only fix landed too:
> migration `20260504160500_fix_academy_pro_api_developer_key_format.sql`
> updates the Academy module `pro-api-developer` content_md so the
> `mst_…` prefix matches what new users actually see in the dashboard.
> Original seed migration `20260418143829_*.sql` also patched at the
> source line so fresh database init lands the corrected docstring.
>
> **TARS itself green:** `pytest -q` → 2315 passed / 1 skipped /
> 2 xfailed (44s); cockpit `npm run typecheck` clean; cockpit vitest
> 335/335 passed. Identical to the launch-ready snapshot below.
>
> **Known follow-ups (not blocking, captured for next pickup):**
> - Lovable: B-001 dist guard workflow has path filters
>   (`dist/**`, `public/_redirects`, `index.html`) so it didn't trigger
>   on our developer/SDK/edge-function refactor. That is by design but
>   means dist-impacting future PRs have to touch one of those paths or
>   call the workflow via `workflow_dispatch`.
> - Lovable: PR #33 (claude-qa, Supabase SDK unification across 161
>   files) sits as DRAFT since 2026-05-02 — needs a triage decision
>   (revive vs close).
> - Lovable: `supabase/functions/tg-*` carry ~600 ESLint errors of
>   `@typescript-eslint/no-explicit-any` legacy debt. Pre-existing,
>   independent of any Cursor-lane work; addressable as a typed-cleanup
>   sprint when the schedule allows.
>
> **Earlier today (resolved, kept for trace):**
> Operator paid GH Actions billing this afternoon. All 5 workflows in
> `meeet-solana-state-941a6045` re-enabled and validated by a manual
> `workflow_dispatch` of `Edge Functions Type Check` (run
> `25310042203`, ✓ success). 3 commits landed on that repo's main
> (`05c57827`, `d62a5433`, `e531fb0f`), CI green on all 3
> push-triggered runs (`Unit Tests` `25310235104`, `RLS Integration
> Tests` `25310235113`, `Edge Functions Type Check` `25310235108`).
> LaunchAgent + `MORNING_TODO_2026-05-04.md` cleaned up.

> **2026-05-04 LAUNCH-READY snapshot.** `tars.meeet.world` is live
> through Cloudflare Pages **Git integration** (project
> `tars-meeet-git`, no `CLOUDFLARE_API_TOKEN` in GH). All gates green:
> `pytest -q` → **2315 passed / 1 skipped / 2 xfailed**; cockpit
> `npm run typecheck` clean + **335/335** unit tests; acceptance
> `bash scripts/acceptance_tars_meeet.sh` 5/5 reachable PASS;
> `python -m scripts.qa_agent` against prod **27 PASS · 0 FAIL · 2
> WARN · 3 SKIP** (warns/skips are `BRIDGE_SHARED_SECRET` on Pages
> prod env + `TARS_INGEST_API_KEY` for `MEEET_INGEST_URL` —
> operator-only paste-ins, see `docs/TARS_MEEET_OPS_TODO.md`
> §Outstanding 1 + 4); `tars.meeet.world — Cloudflare Pages` last
> run **#25291442109** = success. Plan A (wrangler from Actions)
> kept as documented fallback. The legacy Direct-Upload `tars-meeet`
> Pages project still exists (no domain) — safe to delete from the
> dashboard, no client uses it.
>
> `>>> SYNC: Cursor · 2026-05-04 · launch-ready snapshot`

> **2026-05-01 LAUNCH-DAY pickup:** read `docs/LAUNCH_TODAY_2026-05-01.md`
> first — it's the "what is green / what is the operator-only blocker"
> snapshot taken just before opening the gate to public users. After
> that, if you are the **second parallel Cursor window** the operator
> opened, jump to `docs/SYNC.md` §11 — it lists the branch prefix
> (`cursor-b/`), local ports (8866 / 5184 / 8084), and the file-level
> mutex protocol so the two windows don't trample each other.

> **2026-05-01 chat-handoff:** before the rest of this doc, read
> `docs/CHAT_PICKUP_2026-05-01.md` — it's a one-shot pickup written
> when the operator switched to the multi-root `tars-meeet.code-workspace`
> and the previous Cursor chat could not migrate cleanly. Contains
> the live QA Agent state, the active git remote setup (just cleaned
> up), the four PRs that landed today, and the pending lane split
> with Claude/Lovable.

> Naming: product = **TARS**. Older copy may say "Jarvis" — replace in copy
> when editing. Folder name `Jarvis/jarvis` stays for path stability.

> **2026-05-03 — Repo visibility:** **`alxvasilevvv/tars-neural-cockpit`**
> is **public** so `releases/download/*` works for anonymous installs (B-001).
> **Audit:** ensure no secrets in git history. **`scripts/install-tars.sh`**
> on `main` supports **`meeet.world/install.sh`** via redirect from
> **`meeet-solana-state` PR #40** (deploy meeet.world for live).
>
> `>>> SYNC: Cursor · 2026-05-03 · public repo + install script`

> **2026-05-03 — B-001 (downloads manifest):** Pages Function
> `experiments/neural-showcase-v3/functions/api/product/downloads.ts` now
> points `artifacts[].url` at **GitHub Release v8.4.0** (Tauri filenames), not
> `tars.meeet.world/TARS-*` (those paths served SPA HTML). Landed as
> **PR #149**; Cloudflare Pages workflow run **25281019786** deployed
> `tars.meeet.world`. Supabase **`tars-downloads`** fallback aligned in
> **`meeet-solana-state-941a6045` PR #38** — run
> `supabase functions deploy tars-downloads` from a credentialled account
> (403 from sandbox). **Public funnel:** anonymous `curl` to GitHub
> `releases/download` stays **404** while the repo/release is private;
> `gh release download` works with auth — for open web, publish release
> CDN or make assets reachable without GitHub session.
>
> `>>> SYNC: Cursor · 2026-05-03 · B-001 manifest ship + deploy refs`

> **New workstation / GitHub / meeet.world onboarding:** step-by-step
> checklist lives in `docs/SECOND_MACHINE_HANDOFF.md` (includes `.env.example`
> and a first-message template for Claude Code on the destination machine).

> **Active roadmap: `docs/PHASE_L_ROADMAP.md`** — Phase L is the
> Claude-tier evolution (conversation layer, attachments, encrypted
> sync via meeet.world, voice mode, Tauri desktop, **iOS and Android companions**).
> Read it once before picking up any new feature work; sub-phases are
> independent and have explicit acceptance criteria.

## Current split of work

- **Cursor agent (functional / backend / wiring):** owns domain packs,
  meeet bridge, real adapters, SSE awareness, FastAPI router, frontend
  glue (Cockpit + AwarenessTicker + OperatorStrip + UsageStrip). The
  latest batch (Phase K) shipped: route + session_id tagging in every
  event, a USD/token cost ledger fed by `usage.tokens` events, the
  `/api/usage` rollup with per-route / per-model / per-session
  buckets, composite domain packs (`research_lab`, `ops_room`) plus
  `/api/domains/manifest`, a CLI replay tool
  (`python -m backend.core.meeet.replay_cli`), the `meeet` event
  contract test suite, and SMTP outbound for `business.draft_email`
  (vault-driven). Frontend wires `<UsageStrip />` and a per-tab
  session id propagated via `x-tars-session-id`.
- **Claude Code (design polish, GLB, sound, copy):** picks up the
  remaining design work, GLB asset, content/copy passes, and the still-
  open items in `docs/IDEAS.md`.

When in doubt, the design source of truth is
`design-system/tars/MASTER.md` (generated by `ui-ux-pro-max-skill`),
plus per-page overrides in `design-system/tars/pages/`.

## Mental model

TARS is a local-first Neural Cockpit. Frontend and backend are loosely
coupled — `frontend/` is vanilla HTML/CSS/JS, the canonical SaaS-grade
surface is `experiments/neural-showcase-v3/` (React + Tailwind v4 +
framer-motion + R3F).

Phase-9: **domain packs** — plugin system that specialises the neural
core for traders, business, MLM, science.

Phase-9.1: **meeet.world bridge** — every cross-boundary action runs
inside a `trace_scope` and emits events to the meeet ingest, contract
version pinned at `1.0.0`.

Phase-9.2: **awareness SSE** — `GET /api/awareness/stream` pushes
`hello`, `system.pulse`, `domain.heartbeat`, and `bye` frames so the
cockpit can wire a live ticker.

## Where things live

- **Design system source of truth:** `design-system/tars/MASTER.md`
  (per `ui-ux-pro-max-skill`). Page overrides under
  `design-system/tars/pages/`.
- **Skill (UI/UX):**
  - Cursor global: `~/.cursor/skills-cursor/ui-ux-pro-max/`
  - Cursor project: `.cursor/skills/ui-ux-pro-max/`
  - Claude global: `~/.claude/skills/ui-ux-pro-max/`
  - Claude project: `.claude/skills/ui-ux-pro-max/`
- **Domain pack core:** `backend/core/domains/{base,registry,_http,__init__}.py`
- **Domain pack implementations:**
  `backend/core/domains/packs/{traders,business,mlm,science}/`
  Each pack has `pack.py`, `actions.py`, `awareness.py`, `prompts.py`,
  `manifest.json`. Awareness sources now have live fetchers — see
  `_fetch_*` in each pack's `awareness.py`.
- **Local data for adapters:** `data/business_kpi.json`,
  `data/business_deals.json`, `data/mlm_network.csv`,
  `data/calendar_events.json`, `data/traders_news.json`,
  `data/traders_portfolio.json`. Path overridable via env vars
  (`BUSINESS_KPI_PATH`, `BUSINESS_DEALS_PATH`, `MLM_NETWORK_PATH`,
  `CALENDAR_PATH`, `TRADERS_NEWS_PATH`, `TRADERS_PORTFOLIO_PATH`) or
  per-call `path` arg.
- **Council:** `backend/core/council/{voices,llm,orchestrator,__init__}.py`.
  Three voice flavours ship: `LocalVoice` (deterministic rules),
  `MockCloudVoice` (conservative under dispersion), and
  `AnthropicVoice` / `OpenAIVoice` (auto-detected from the vault when
  a key is configured). The orchestrator filters voices that
  fail with `stance='unavailable'` so missing keys never block a
  deliberation. Every deliberation now also emits per-voice
  `usage.tokens` events (with `cost_usd`) and bumps the active route
  to `cloud` when an LLM voice ran successfully.
- **Cost ledger:** `backend/core/usage/{__init__,ledger}.py` derives
  rollups from the meeet event store — no separate DB. Pricing is
  configurable via `TARS_PRICE_OVERRIDES_JSON`; defaults cover the
  shipped LLM voices. HTTP surface: `GET /api/usage`,
  `GET /api/usage/lines`, `GET /api/usage/prices`.
- **Secrets vault:** `backend/core/vault/{__init__,keychain}.py`.
  Env-var first, then macOS Keychain (service `tars`,
  `security find-generic-password -a tars -s <key>`). HTTP surface:
  `GET /api/vault/status` (sources only — values are never echoed).
- **Policy gate:** `backend/core/policy/{gate,store,__init__}.py`.
  Mode: `autopilot | confirm | dry_run`, default `confirm`.
  Confirmations table sits in the same SQLite DB as the meeet store.
- **Playbooks:** `backend/core/playbooks/{loader,runner,__init__}.py`,
  JSON files under `playbooks/<pack>/<name>.json`. Override the root
  with `TARS_PLAYBOOKS_DIR`. Steps with `parallel: true` are batched
  and executed via `asyncio.gather`.
- **MLM downline DB:** `backend/core/domains/packs/mlm/db.py` —
  SQLite at `~/.tars/downline.sqlite` (override `MLM_DB_PATH`),
  self-seeds from `data/mlm_network.csv` on first read. Mutations
  (`add_member`, `log_activity`) flow through the policy gate.
- **Composite packs:** `backend/core/domains/composite.py` +
  `backend/core/domains/packs/composites.py`. Two ship by default:
  `research_lab` (science + business → paper-to-pitch) and
  `ops_room` (traders + mlm → morning standup). Composite actions
  surface as `<sub_slug>__<id>` so handlers don't collide; destructive
  flags + auth keys propagate from the leaves.
- **Domain HTTP router:** `web_extras/routers/domains.py`. Adds
  `GET /api/domains/manifest` — cache-friendly summary of every
  registered pack (slug, capabilities, action/destructive counts,
  composite linkage).
- **Awareness SSE router:** `web_extras/routers/awareness.py`
- **Awareness snapshot:** `GET /api/domains/<slug>/awareness/<source_id>/snapshot`
  — same router file, separate handler.
- **meeet trace viewer:** `web_extras/routers/meeet.py`
  → `/api/meeet/{stats,events,replay,health}`.
- **Council:** `web_extras/routers/council.py`
  → `POST /api/council/deliberate`.
- **Vault status:** `web_extras/routers/vault.py`
  → `GET /api/vault/status`.
- **Usage ledger:** `web_extras/routers/usage.py`
  → `GET /api/usage`, `GET /api/usage/lines`,
    `GET /api/usage/prices`.
- **Policy:** `web_extras/routers/policy.py`
  → `GET /api/policy/{pending,recent}`,
    `POST /api/policy/confirm/{token}`,
    `POST /api/policy/cancel/{token}`,
    `POST /api/policy/expire`.
- **Playbooks:** `web_extras/routers/playbooks.py`
  → `GET /api/playbooks`, `GET /api/playbooks/{id}`,
    `POST /api/playbooks/{id}/run`, `POST /api/playbooks/_reload`.
- **FastAPI app + runner:** `web_extras/app.py`, `serve.py`. App
  lifespan starts the background replay loop (interval
  `MEEET_REPLAY_INTERVAL_S`, default 60s, set to `0` to disable).
- **meeet bridge:** `backend/core/meeet/{config,tracing,events,client,store,replay_cli,__init__}.py`.
  Durable buffer sits in `~/.tars/meeet.sqlite` (override with
  `MEEET_STORE_PATH`; disable with `MEEET_STORE=disabled`).
  `MeeetClient.last_replay` caches the most recent replay outcome and
  is surfaced by `/api/meeet/health`. `tracing.py` ships
  `session_scope`, `set_route`, and `current_session/current_route`;
  `events.py` carries optional `session_id`/`route` on every payload;
  the SQLite store has matching columns + indices (auto-migrated on
  first read for pre-K1 DBs). The CLI tool
  `python -m backend.core.meeet.replay_cli --stats|--export|--limit`
  is the cold-start recovery path.
- **Tests:** `tests/test_domains.py`, `tests/test_meeet.py`,
  `tests/test_meeet_store.py`, `tests/test_meeet_contract.py`,
  `tests/test_meeet_health_and_replay_loop.py`,
  `tests/test_real_adapters.py`, `tests/test_awareness_fetchers.py`,
  `tests/test_awareness_stream.py`, `tests/test_council.py`,
  `tests/test_policy.py`, `tests/test_playbooks.py`,
  `tests/test_mlm_db.py`, `tests/test_vault_and_llm_voice.py`,
  `tests/test_batch2_adapters.py`, `tests/test_business_smtp.py`,
  `tests/test_composite_packs.py`, `tests/test_replay_cli.py`,
  `tests/test_usage_ledger.py`,
  `tests/test_usage_router_and_manifest.py`.
  **159 tests, all green.**
- **Specs:** `docs/DOMAIN_PACKS.md`, `docs/VIDEO_TRANSCRIPTS.md`,
  `docs/IDEAS.md`.
- **Showcase v2 — vanilla:** `experiments/neural-showcase-v2/`
- **Showcase v3 — React (canonical surface):**
  `experiments/neural-showcase-v3/`. Live routes:
  - `/` → Landing (Hero + Rail + Layers + Domains + Steps + Footer)
  - `/cockpit` → operator console (live `/api/domains` + invoke +
    SSE awareness ticker)
- **Project context for AI:** `CLAUDE.md`, `.cursorrules`,
  `.cursor/rules/tars-architecture.mdc` — keep these three in sync.

## Done (running list, latest first)

- **2026-05-02 / 03 — operator-surface batch + critical bug pass (Cursor [A]):**
  Closeout session that landed seven PRs in a row, finished the
  cockpit operator surfaces, and unblocked the silent test gate:
  - **#136** `/cockpit/traces` — local trace viewer over
    `/api/meeet/traces` + `/api/meeet/events` (route filter, fuzzy
    search, two-column drill-down, copy-to-clipboard trace_id,
    polling).
  - **#137** `/cockpit/policy` — pending confirmations inbox over
    `/api/policy/{pending,recent,confirm,cancel}` with grouped
    queue + recent log + token cards.
  - **#138** `/cockpit/council` — debug page over
    `/api/council/deliberate` (manual prompts, voice toggles,
    contradiction surfacing, agreement / cost / latency badges).
  - **#139** Operator command palette (`⌘.` / `Ctrl+.`) — fuzzy
    index over packs / actions / playbooks / awareness sources /
    recent traces; routes destructive actions through the policy
    gate; deep-link nav.
  - **#140** `/cockpit/awareness` — three-column awareness
    explorer: pack rail with live-source badge, source rail with
    kind chip + filter, snapshot pane with config preview + live
    data + took / fetched / trace badges. URL state for deep-link.
  - **#141** **CRITICAL FIX** — restored
    `backend/core/attachments/index.py` from a Python 3.12 syntax
    error (mangled f-string from PR #60 swallowed methods from
    PR #67). The bug had been silently hiding 40 backend test
    modules from the suite. After: 2266 tests run instead of
    collection-erroring.
  - **#142** Image vision routing — Anthropic Claude / OpenAI
    gpt-4o voices now receive image bytes natively (not just the
    OCR text-block fallback). New
    `backend/core/chat/multimodal.py` (budget-aware: 6 imgs/turn,
    5 MiB/img, 18 MiB total). Orchestrator only forwards
    `image_refs` when voice declares `supports_multimodal=True`
    AND vision attachments exist, so legacy mocks keep working.
  - **#143** Unified duplicate `POST /api/chat/attachments/{id}/reembed`
    route (two endpoints fought over the same path — the older
    promote-style shadowed the newer batch-style). Now dispatches
    by body shape (`force` / `target_model` → batch impl;
    otherwise → promote impl). Last failing test now green.
  - **#144** `/changelog` page bundle: 560 → 216 KB raw / -63%
    gzip. New `scripts/generate_public_changelog.py` truncates
    `CHANGELOG_AGENTS.md` to top-60 entries → `CHANGELOG_PUBLIC.md`.
    Wired into `predev` / `prebuild` npm hooks. `changelog:check`
    script for CI guard.

  **Test deltas at end of session:**
  - Backend: **2315 passed**, 1 skipped, 2 xfailed (full sweep
    runs end-to-end for the first time; was 0 before #141).
  - Cockpit vitest: **328 passed**, 22 files (+162 from
    operator-surface batch).
  - `gate-control-tower` local subset: cockpit-tsc ✓,
    cockpit-test ✓, planner-smoke ✓, playbooks-validate-all ✓
    (every shipped playbook validated, 0 errors / warnings).
  - `smoke-core-bridge` requires `BRIDGE_SHARED_SECRET` (cloud
    creds) — out of scope for autonomous runs; documented.

  **Background loops sanity check** — all 7 lifespan loops in
  `web_extras/app.py` confirmed wired (no IDEAS regressions):
  `_replay_loop` (meeet replay), `autopilot_loop` (agents),
  `_trace_summary_loop`, `_message_embed_loop`,
  `_saved_search_poll_loop`, `_memory_purge_loop`,
  `_policy_expire_loop`. Each opt-in via env interval (`0` =
  off); never crashes the host.

  **Known carry-over** for next session:
  - Live API tests against Anthropic / OpenAI / DexScreener /
    arXiv / meeet ingest — need keys / cloud creds.
  - Desktop installer signing (Apple Developer ID + Windows
    Authenticode certs) — workflow exists at
    `.github/workflows/release-desktop-tagged.yml` but needs
    `TAURI_SIGNING_PRIVATE_KEY` secret to actually sign.
  - Live SOL / $MEEET billing / consumption-limit end-to-end —
    needs operator with test card.

- **2026-05-02 — cron-shipped morning bundle wrapper (Cursor [A]):**
  Ships `scripts/playbooks_morning_cron.sh` + `make morning-bundle`
  / `make morning-bundle-dry` targets. **Single command** for
  cron to run every `morning`-tagged playbook (currently 4:
  `business.morning_brief`, `ops_room.morning_standup`,
  `research_lab.paper_to_pitch`, `traders.morning_check`),
  flush the meeet replay buffer, and write an aggregate
  evidence JSON to `.morning-runs/<run_id>.json`.
  **Continue-on-failure** by default (one bad playbook doesn't
  mask the others) with `MORNING_FAIL_FAST=1` for legacy
  stop-on-first behaviour. Discovery is **tag-driven**, so as
  new `morning`-tagged playbooks land in `playbooks/`, they
  join cron automatically — no script edit. Three exit-code
  lanes so cron alerts route differently: `0` (all green), `1`
  (playbook failure), `2` (operator error / no playbooks
  discovered). The `morning-bundle-dry` target hard-codes
  `MORNING_MODE=dry_run` so rehearsals are *always* safe even
  if the operator's env has `MODE=autopilot`. **Closes the
  Cron-as-First-Class-Operator arc**: PR #129 made
  cron-driven playbook execution viable; this wrapper makes
  it ergonomic. Pinned by 23 new pytest cases (11 structural
  — bash syntax, every documented env knob is read by the
  script, all three exit codes documented, canonical CLI
  modules invoked; 5 Makefile — `.PHONY`, help comments,
  recipe wires script, dry-mode forces dry_run; 7 end-to-end
  smoke — no-playbooks → rc=2, happy override → rc=0,
  unknown id → rc=1, mixed continue-on-failure, fail-fast,
  evidence filename matches printed run_id, skip-replay
  surfaces in evidence). Full Python suite: **2227 passed in
  54.04s** (was 2204, +23). Sample cron line:
  `MORNING_MODE=autopilot /path/to/jarvis/scripts/playbooks_morning_cron.sh`.
  Files: `scripts/playbooks_morning_cron.sh` (new, 280 lines),
  `Makefile` (+25), `.gitignore` (+2), `tests/test_morning_bundle.py`
  (new, 363 lines).

- **2026-05-01 — awareness CLI bash completion (operator-CLI arc symmetry closed) (Cursor [A]):**
  Ships `scripts/awareness-completion.bash` mirroring the
  existing planner / playbooks completion scripts. **Closes
  the operator-CLI arc symmetry**: every cockpit-facing TARS
  surface (planner / awareness / playbook) now has HTTP route
  + `python -m …` CLI + `make …-*` targets + bash completion.
  The awareness script handles a wrinkle the other two don't:
  **two-level live positional completion** for the `snapshot`
  subcommand. Positional 0 is a pack slug (live query against
  `awareness_cli list`); positional 1 is a source id, **scoped
  to the chosen slug** (live query against `awareness_cli list
  <slug>`, with the cache keyed by slug name so completing
  slug A then slug B doesn't pollute B's cache with A's
  source ids — explicitly pinned). Avoids the `--quiet`
  flag-order bug from PR #130 by construction (both query
  helpers invoke the CLI with `--quiet` BEFORE the subcommand,
  pinned). Pinned by 9 new pytest cases covering script
  structure, no-drift between cli._DISPATCH and the script,
  per-subcommand flag tables, the two-cache invariant, the
  two-level positional walker, and the flag-VALUES skip
  (so `--thread-id thr_42 traders` correctly identifies
  `traders` as positional 0). Full Python suite: **2204
  passed in 40.97s** (was 2195, +9). Smoke (sourced into
  bash): tab returns 3 subcommands, then 8 live pack slugs,
  then 5 source ids scoped to the chosen pack. The arc as it
  now stands: planner / awareness / playbook each have HTTP
  + CLI + Make + completion, all sharing the same trace +
  event surface. Follow-ups: right-rail planner entrypoint
  (cancelled — needs ChatPane plan-aware protocol first);
  cron-shipped morning-bundle wrapper script.

- **2026-05-01 — playbooks bash completion + planner script flag-order fix (Cursor [A]):**
  Ships `scripts/playbooks-completion.bash` mirroring the
  existing planner script: tab completion for the 6
  subcommands, per-subcommand flag tables, **live
  playbook-id completion** sourced from the CLI itself
  (5-second cache), and **filesystem-path completion for
  `--context-file`** so the cron-friendly sidecar-JSON
  workflow tab-completes end-to-end. While here, fixes a
  latent bug in `scripts/planner-completion.bash`: both
  scripts were invoking `… cli list --quiet` but `--quiet`
  is the global flag and must come before the subcommand.
  The old order silently failed with exit 2 and an empty
  completion list (no error visible to the user).
  Discovered during the playbook script's smoke test;
  pinned by 10 new pytest cases (script structure + flag
  drift + cache contract + scoped id completion).
  Full Python suite: **2195 passed in 41.23s** (was 2185,
  +10). Follow-ups: right-rail planner entrypoint from the
  cockpit chat thread; `awareness-completion.bash`
  deferred until a concrete cron use case driving it.

- **2026-05-01 — playbooks CLI parity + control-tower gate wiring (Cursor [A]):**
  Closes the third (and last) leg of the operator-parity arc.
  Playbook execution now has a shell-side equivalent at
  `python -m backend.core.playbooks.cli` plus seven Make
  targets (`playbooks`, `playbooks-list`, `playbooks-show`,
  `playbooks-run`, `playbooks-validate`,
  `playbooks-validate-all`, `playbooks-reload`). Same playbooks
  the cockpit's `POST /api/playbooks/<id>/run` route executes
  can now run from cron without the FastAPI process — emitted
  `playbook.*` events still land in the local meeet buffer the
  cockpit reads from. Cron-friendly pattern reads:
  `make playbooks-run ARGS=traders.morning_check MODE=autopilot
  CONTEXT='{"basket":["BTC","ETH"]}'`. **Load-bearing CI gate
  wiring**: `make gate-control-tower` now runs
  `playbooks-validate-all` after planner-smoke, so a malformed
  playbook fails the gate the moment it lands instead of
  waiting for a 5am cron to discover the typo. `--context-file`
  wins over `--context` when both are supplied (cron-baked
  sidecar JSON ⇆ ad-hoc operator override); `resolve_mode` is
  permissive (typo in cron command line falls back to default
  rather than crashing) — both pinned. Pinned by 41 new pytest
  cases (25 CLI, 16 Makefile contract). Full Python suite:
  **2185 passed in 42.09s** (was 2144, +41). The arc as it now
  stands: planner / awareness / playbook each have HTTP route +
  `python -m …` CLI + `make …-*` targets, all sharing the same
  trace + event surface. Follow-ups: right-rail planner
  entrypoint from the cockpit chat thread; cron-shipped
  morning-bundle wrapper script; `scripts/playbooks-completion.bash`
  bash completion.

- **2026-05-01 — awareness CLI parity (Cursor [A]):** Closes the
  operator-parity gap left by the planner CLI batch. The
  awareness layer (the cockpit's `GET /api/domains` /
  `…/awareness` / `…/awareness/<src>/snapshot` route) now has a
  shell-side equivalent at
  `python -m backend.core.domains.awareness_cli` plus four new
  Make targets (`awareness`, `awareness-list`,
  `awareness-snapshot`, `awareness-snapshot-all`). An operator
  on a machine without FastAPI up — fleet rollout, cron-driven
  cold-start brief, on-call recovery during ingest outage —
  can now list and materialise awareness sources without HTTP,
  and the meeet event surface is **bit-for-bit identical**
  (`awareness.snapshot.requested / completed / failed` inside
  a `trace_scope`) so cockpit dashboards count CLI hits the
  same as HTTP hits. Snapshot subcommands accept
  `--thread-id` / `--trace-id` so chained CLI calls keep the
  trace tree intact. `snapshot-all` splits results into
  `fetched` (real fetcher invocations) and `skipped`
  (config-only sources, e.g. webhook receivers) — overall
  `ok` flips on fetched-source failures only, so an operator
  can tell "no fetcher implemented yet" apart from a real
  fetch error. Pinned by 26 new pytest cases (16 CLI, 10
  Makefile contract). Full Python suite: **2144 passed in
  48.90s** (was 2118, +26). Smoke: `make awareness-list
  ARGS=traders` returns 5 sources (4 live), `make
  awareness-snapshot ARGS="traders binance_ws"` returns the
  live ticker envelope with `trace_id` + `took_ms`,
  missing-`ARGS` guards exit 2 cleanly. Follow-ups: right-rail
  planner entrypoint from the cockpit chat thread; pre-warm
  cron driver once a packwide ARGS pattern emerges.

- **2026-05-01 — meeet replay CLI: `--repush-trace` + `planner-repush-run` Make target (Cursor [A]):**
  Operator follow-up to PR #124 (`planner-replay-run`). Adds
  the **push-this-trace-upstream-now** flow that PR didn't
  ship: `replay_cli --repush-trace <trc>` re-emits every event
  for one trace to ingest regardless of the existing `pushed`
  flag, so a fleet operator can recover from a meeet ingest
  contract bump without hand-editing SQLite. The full operator
  pipeline now reads: dump (`make planner-replay-run`) → audit
  → repush (`make planner-repush-run ARGS="<run_trace>"
  [LIMIT=N]`). Load-bearing failure semantics: when an
  upstream push fails during repush, the row's `pushed` flag
  is **NOT regressed to 0** (only `last_error` updates) —
  otherwise a half-failed repush would let those rows leak
  into the next `replay_unpushed` flush and double-push them
  once the upstream recovers, exactly the behaviour the
  contract bump is trying to repair. Push primitive extracted
  to `MeeetClient._push` so `replay_unpushed` and
  `repush_trace` share the same `urlopen` call. Pinned by 12
  new pytest cases (5 store, 4 CLI, 3 makefile). Full suite:
  **2118 passing** (was 2106, +12). Manual smoke: bare,
  with-ARGS, with-LIMIT, no-ingest-URL all behave correctly.
  Follow-ups: right-rail planner entrypoint from the cockpit
  chat thread; awareness CLI parity (`python -m
  backend.core.awareness.cli`).

- **2026-05-01 — cockpit: aria-live announcement on plan run completion / abort (Cursor [A]):**
  Plan-detail panel now surfaces every terminal run through a
  visually-hidden `aria-live="polite"` region so screen-reader
  operators learn that a run finished without watching the
  panel. Three lifecycle outcomes get distinct phrasing —
  clean completion (with latency + cost), soft failure (`status
  === "completed"` AND `steps_failed > 0`, otherwise dashboards
  tally these as green), and abort / hard failure (uses
  `abort_reason` → `exception` → placeholder). Decision split
  via two pure helpers (`formatRunAnnouncement`,
  `pickRunAnnouncement`) so the dedupe logic ("trace_id, not
  array index" + "skip in-flight head to find newest terminal")
  is testable without DOM. Region is always rendered (not
  conditionally mounted) because some screen-reader engines
  skip the initial announcement when the live region appears
  mid-page-life. Pinned by 14 new Vitest cases. Cockpit suite:
  **181 passed (14 files)** (was 167, +14); `tsc --noEmit`
  clean; `vite build` clean (2.82s); Python unchanged (2106
  green). Follow-ups: right-rail planner entrypoint from the
  cockpit chat thread; `--force-repush --trace-id` for fleet
  ops re-emit-to-upstream; awareness CLI parity.

- **2026-05-01 — cockpit: scroll-to-selected on /cockpit/planner deep links (Cursor [A]):**
  Closes the long-standing planner-page polish item: when an
  operator pastes `/cockpit/planner?selected=pln_xyz`, the
  matching `<li>` was hidden below the fold of the
  overflow-scroll list. Page now imperatively scrolls the row
  into view on first paint (and on browser-back to a different
  selection) without disrupting routine clicks. Decision lives
  in a pure `shouldScrollTo` helper (`lib/plannerScroll.ts`)
  that returns `true` only for the deep-link / browser-nav
  case (skips when nothing selected, list still loading,
  deep-link points at a filtered-out plan, or SSE refresh
  didn't change selection); side-effect lives in a
  `useScrollSelectedIntoView` hook on the Planner page that
  calls `scrollIntoView({ block: "nearest", behavior: "smooth" })`
  on the matching ref. `block: "nearest"` is load-bearing —
  it's a no-op when the row is already visible (e.g. user just
  clicked it), so we don't need to discriminate "click vs URL
  change". Pinned by 9 new Vitest cases (every no-scroll branch
  plus first-paint, browser-back, top-row, empty list, and
  purity). Full cockpit suite: **167 passed (14 files)**;
  `tsc --noEmit` clean; `vite build` clean (2.74s); Python
  unchanged (2106 green). Follow-ups: `aria-live` announcement
  on run completion / failure for screen-reader operators;
  right-rail planner entrypoint from the cockpit chat thread.

- **2026-05-01 — meeet replay CLI: `--trace-id` filter + `planner-replay-run` Make target (Cursor [A]):**
  Adds a per-run scoping knob to the meeet event replay CLI plus
  the operator wrapper that uses it. CLI gains
  `--trace-id <run_trace>` (export branch only) and Makefile
  ships `planner-replay-run ARGS="<plan_id> <run_trace>"
  [OUT=<path>]` defaulting the export to
  `$(MEEET_REPLAY_DIR)/$plan_id-$run_trace.jsonl` (default dir
  `.meeet-replays`, override-friendly via `?=`). Use case:
  meeet ingest outage backfill or single-run audit — fleet ops
  dump one specific run's events to JSONL without shoveling the
  whole local store, then push / inspect / archive however they
  want. Read-only, diff-able, and doesn't mutate `pushed` flags
  (a future force-repush flow can layer on if demonstrated).
  Pinned by 7 new pytest cases: 2 in `test_replay_cli` (trace
  filter narrows export, unknown trace ⇒ empty file rc=0) and
  5 in `test_makefile_planner_targets` (`.PHONY` membership,
  ARGS guard, dedicated recipe contract pinning OUT override
  + default filename + replay_cli module + `--trace-id` /
  `--export` invocation, MEEET_REPLAY_DIR macro shape). Manual
  smoke: end-to-end `synthesize → run → planner-replay-run`
  produced a 12-line JSONL with every row carrying the run's
  trace id; `OUT=` override worked; both empty-ARGS branches
  exit 2 with usage. Full suite: **2106 passing** (was 2100,
  +6). Follow-ups: `--force-repush --trace-id` flag pair if
  fleet ops need re-emit-to-upstream rather than the current
  export-to-JSONL workflow; right-rail planner entrypoint from
  the cockpit chat thread.

- **2026-05-01 — Makefile: `planner-clone` target for plan forking (Cursor [A]):**
  Adds `make planner-clone ARGS="<plan_id> [target_thread]"` so a
  fleet operator can fork a known-good plan into a fresh `proposed`
  row from the shell — without immediately approving or running it
  (that's what `planner-rerun` is for). Recipe parses ARGS
  positionally via `set --` so the second word, when present,
  becomes `--thread-id <target_thread>`; bare `ARGS=<plan_id>`
  invokes a vanilla clone that inherits the source's thread. Two
  guards: outer `ARGS=` empty check (exit 2 with usage) plus an
  inner `[ -z "$plan_id" ]` re-guard catching whitespace-only
  expansions. Use cases this unlocks (that `planner-rerun` doesn't):
  per-tenant golden-plan fork for manual approval (audit trail /
  four-eyes), overnight staging of many clones for morning curation,
  rollback snapshots before mutating a source plan. Pinned by 3
  new pytest cases (`.PHONY` membership, `ARGS=` guard,
  `test_planner_clone_target_supports_optional_target_thread`
  asserting the positional split + both branches). Manual smoke:
  bare clone, thread-rebound clone, no-ARGS error path all behave
  as expected. Full suite: **2100 passing** (was 2097, +3).
  Follow-ups: right-rail planner entrypoint from the cockpit chat
  thread; `make planner-replay-run` for backfilling billing rollups
  after a meeet ingest outage.

- **2026-05-01 — Makefile: `planner-rerun` target for cron / fleet (Cursor [A]):**
  Adds `make planner-rerun ARGS=<plan_id> [MODE=autopilot|confirm|dry_run]`
  so cron jobs and fleet operators can reproduce the cockpit's
  one-click Rerun button from a single Make invocation. Recipe
  shells into `clone $(ARGS) --approve --run` (plus optional
  `--mode "$(MODE)"`), inheriting the same trace scope, policy gate,
  and meeet payloads as the cockpit path. Optional `MODE=` lever
  lets the operator pin policy mode at the Make boundary — useful
  for nightly `MODE=autopilot` runs regardless of host
  `TARS_POLICY_MODE`. Added to `.PHONY`, gated by the standard
  `ARGS=` guard. Pinned by 3 new pytest cases in
  `test_makefile_planner_targets.py` (`.PHONY` membership, ARGS
  guard, recipe wires `clone --approve --run` and forwards `--mode`).
  Manual smoke: end-to-end `synthesize → make planner-rerun`
  produced a populated `usage_lifetime` envelope. Full suite:
  **2097 passing** (was 2094, +3). Follow-ups: right-rail planner
  entrypoint from the cockpit chat thread; `make planner-replay-run`
  for backfilling billing rollups after a meeet ingest outage.

- **2026-05-01 — planner: `full` CLI subcommand + extracted helper (Cursor [A]):**
  Brings the planner CLI to parity with the HTTP `/full` endpoint
  shipped in PR #116, so an operator without a cockpit window can
  inspect a plan in one command and pipe the JSON into `jq`. The
  lifetime aggregation logic moves into
  `backend/core/planner/history.py::aggregate_usage_lifetime` —
  extracted from the FastAPI route so the CLI calls the exact same
  code path. `cost_usd` rule preserved verbatim (None when no run
  had a priced model; mixed runs sum priced costs only). Full
  operator wiring: CLI subcommand
  (`python -m backend.core.planner.cli full <plan_id> [--limit]`),
  Makefile target (`make planner-full ARGS=<plan_id>` with `ARGS=`
  guard), bash completion (`full` advertised + `--limit` flag).
  Pinned by 10 new cases in `tests/test_planner_full_cli.py`
  (helper alone: zero runs, all-unpriced, mixed priced-only-cost
  rule, defensive guards; CLI: 404, happy path with full envelope
  shape, `--limit` pass-through, `--quiet` placement). Full suite:
  **2094 passing** (was 2080, +14). Follow-ups: `make planner-clone
  ARGS="..."` for parity with rerun; right-rail planner entrypoint
  from the cockpit chat thread.

- **2026-05-01 — cockpit: URL-state sync for /cockpit/planner (Cursor [A]):**
  Operators can now deep-link to any planner view. Page mirrors three
  pieces of UI state to the URL via `useSearchParams`:
  `?status=<state>` (one of the seven filter states or "all"),
  `?q=<text>` (free-text filter on id / goal / pack), `?selected=<id>`
  (currently selected plan id). Defaults are elided so the URL stays
  short for the common case; parse is permissive (unknown statuses
  fall back to "all", malformed values never throw); writes use
  `replace` mode so the back-stack stays clean. Pure helpers
  (`parsePlannerSearchParams`, `buildPlannerSearchParams`,
  `plannerStateEquals`) in `lib/plannerUrl.ts` pinned by 18 Vitest
  cases (round-trip identity, default elision, URL-encoding
  permissive fallback). Cockpit suite: **158 passed (13 files)**;
  `tsc --noEmit` clean; `vite build` clean; Python unchanged
  (2080 green). Follow-ups: right-rail entrypoint from the chat
  thread; scroll-to-selected on first paint when `?selected=` is set.

- **2026-05-01 — cockpit: per-step live ticking in PlanFullPanel (Cursor [A]):**
  Top-priority follow-up from PR #118. The plan panel's step list
  now ticks live during a run: every `plan.step.requested` /
  `plan.step.allowed` / `plan.step.completed` SSE frame flips the
  matching row's status badge in place — no extra round-trip, no
  flash, no out-of-order rendering. Reducer lives in
  `experiments/neural-showcase-v3/src/lib/plannerSteps.ts`
  (pure, DOM-free) and honours trace scoping (events from a foreign
  trace are dropped), `Last-Event-ID` re-delivery (same start frame
  is a referential no-op), and a `skipped > blocked > failed`
  precedence ladder for terminal states. Pinned by 20 Vitest cases
  in `plannerSteps.test.ts`. Panel seeds an "all pending" snapshot
  on envelope arrival so rows render immediately; a "live · run in
  flight" amber lozenge in the section header signals an active
  run; per-step latency renders next to the action via
  `formatLatencyMs`. Cockpit suite: **140 passed (12 files)**;
  `tsc --noEmit` clean; `vite build` clean; Python unchanged
  (2080 green). Follow-ups: URL-state sync for the planner
  filter strip + deep-link plan_id; right-rail entrypoint from the
  chat thread when the agent proposes a plan.

- **2026-05-01 — cockpit: PlanFullPanel + /cockpit/planner page (Cursor [A]):**
  Operator-facing payoff for the planner backend work shipped in
  PRs #109–#117. New page at `/cockpit/planner` lets the operator
  inspect any plan's full envelope (plan + steps + reconstructed
  runs + lifetime usage), one-click rerun it, and watch the
  lifetime rollup update in place via the planner SSE stream.
  Two pieces: `<PlanFullPanel />` (self-contained drawer that
  hydrates from `fetchFullPlan` and stays live via
  `subscribePlannerEvents`, refetches on every lifecycle event)
  and `<Planner />` page (list + filter strip + panel). Pure
  helpers (`statusTone`, `formatLatencyMs`, `formatStartedAt`,
  `formatRunSummary`, `formatLifetimeSummary`, `summariseStep`,
  `REFETCH_KINDS`, `shouldAdvanceCursor`) extracted and pinned by
  17 Vitest cases. Cockpit suite: **120 passed (11 files)**;
  `tsc --noEmit` clean; `vite build` clean (Planner chunk 17.6 kB
  / 4.96 kB gzipped); Python unchanged (2080 green). Route
  registered in `App.tsx` and a "planner" anchor added to the
  cockpit's top nav so operators jump in with one click.
  Follow-ups: per-step live updates, URL-state sync for filters,
  inline open from the chat thread.

- **2026-05-01 — cockpit: typed planner client + Vitest contract (Cursor [A]):**
  First slice of cockpit ↔ planner wiring. Adds
  `experiments/neural-showcase-v3/src/lib/planner.ts` — a
  typed TS client that pins every backend planner endpoint
  shipped in PRs #109–#116 (`/api/planner` list, `/runs`,
  `/full`, `/abort`, `/rerun`, plus the `/api/planner/events`
  SSE stream with `after_id` resume). Header propagation
  (`x-tars-policy-mode`, `x-meeet-trace-id`) flows through
  every mutating call; `formatCostUSD` preserves the n/a vs
  $0.00 distinction surfaced by `/full`'s
  `has_priced_models`. Pinned by
  `experiments/neural-showcase-v3/src/lib/planner.test.ts`
  (17 Vitest cases — URLs, querystrings, header propagation,
  `EventSource` wiring, malformed-frame drop, response
  round-trip, formatter edge cases). Cockpit suite:
  **103 passed (10 files)**; `tsc --noEmit` clean; Python
  unchanged (2080 green). Next: `PlanFullPanel` React
  component built on top of this client (drawer with rerun
  button + live SSE updates).

- **2026-05-01 — planner: GET /{plan_id}/full aggregate (Cursor [A]):**
  One-shot aggregate endpoint for the cockpit's plan-detail
  drawer. Returns plan envelope + reconstructed runs
  (newest-first) + a `usage_lifetime` block summing every
  run's per-run rollup. The lifetime `cost_usd` stays
  `null` (cockpit renders "n/a") unless at least one run
  had `has_priced_models=true`; mixed runs sum *only* the
  priced runs' costs so "$0.00" never gets confused with
  "no priced model fired". Pinned by
  `tests/test_planner_full_endpoint.py` (7 cases). Full
  suite: **2080 passing**. Follow-ups: cockpit drawer can
  collapse three fetches into one; `runs_aggregated` makes
  "across N runs" label trivial.

- **2026-05-01 — planner: Makefile targets + control-tower gate (Cursor [A]):**
  Wires the planner CLI into the operator-facing Makefile so
  the control tower covers planner end-to-end. Six new
  targets (`planner`, `planner-stats`, `planner-list`,
  `planner-runs`, `planner-show`, `planner-smoke`); all
  shell into `python -m backend.core.planner.cli` via the
  `PLANNER` macro and share the host process's SQLite WAL
  DBs. `planner-smoke` is folded into `gate-control-tower`
  so a planner regression now blocks the release-readiness
  gate. Operator passthrough via `make planner ARGS="…"`.
  Pinned by `tests/test_makefile_planner_targets.py` (12
  cases) — guards `.PHONY` membership, help-text presence,
  `ARGS` invariants, and the `gate-control-tower` wiring.
  Full suite: **2073 passing**. Follow-ups: cockpit can
  surface gate output banner with the planner-smoke line.

- **2026-05-01 — planner: bash completion script + drift-guard tests (Cursor [A]):**
  Operator quality-of-life follow-up: `scripts/planner-completion.bash`
  provides tab-completion for every planner subcommand and
  flag, plus enum value completion for `--mode` /
  `--status`, plus live `plan_id` completion sourced from
  `cli list --quiet` (cached 5s inside the same shell). A
  10-case Python contract test
  (`tests/test_planner_completion_script.py`) guarantees the
  script never drifts out of sync with `_DISPATCH` or
  `_build_arg_parser`. Install paths and the `tars-planner`
  alias documented in the script header. Full suite:
  **2061 passing**.

- **2026-05-01 — planner: one-shot rerun (CLI + HTTP) (Cursor [A]):**
  Closed the loop on the rerun-via-clone flow shipped in PR
  #108. CLI: `clone --approve [--run [--mode ...]]` composes
  clone + approve + (optional) run into a single shell call.
  HTTP: `POST /api/planner/{plan_id}/rerun` is the matching
  cockpit-facing endpoint (body / header support mirrors
  `/clone` plus `mode`). Audit lane: `planner.cloned` event
  grows `auto_approved` and `auto_run` boolean flags; the
  timeline summariser renders them as `· rerun` (auto_run) or
  `· auto-approved` (approve-only). Backwards compatible —
  bare `clone` and `POST /clone` still produce a proposed
  plan with no auto-flip. Pinned by
  `tests/test_planner_rerun.py` (13 cases). Full suite:
  **2051 passing**. Follow-ups: cockpit "Rerun" button now
  one network call away (clone+approve+run merged).

- **2026-05-01 — planner: dedicated plan.run.usage event (Cursor [A]):**
  Cost / token rollup for each plan run now ships as its own
  top-level event in addition to being embedded in the
  terminal event payload (existing behaviour unchanged).
  Unblocks single-line billing queries
  (`SELECT * FROM events WHERE kind='plan.run.usage'`) and
  lets the cockpit render a "rollup" pill per run without
  parsing the terminal payload. Fires on every run regardless
  of priced-model presence; carries `plan_id`, `status`
  (matching the upcoming terminal status), `parent_trace_id`
  (plan's birth trace), and the same `usage` block. Wired
  into the planner SSE allow-list and timeline summariser.
  Pinned by `tests/test_planner_run_usage_event.py` (8 cases)
  + the runner happy-path event-order assertion. Full suite:
  **2038 passing**. Follow-ups: cockpit "Rollup" pill on each
  run row; billing dashboard query simplification.

- **2026-05-01 — planner: surface trace_id + parent_trace_id on PlanRun (Cursor [A]):**
  Cockpit-facing follow-up to PR #109. `PlanRun.to_dict()` and
  the `GET /api/planner/{plan_id}/runs` envelope now expose
  both the per-run `trace_id` (from `plan.run.started.trace_id`)
  and the plan's birth `parent_trace_id` (copied from the same
  event's payload). Lets the cockpit deep-link from a single
  run row to its trace lane, and group sibling runs of the
  same plan under one collapsible "all runs of plan X" node
  without an extra API call. Pinned by
  `tests/test_planner_history_traces.py` (4 cases). Full suite
  (excluding pre-existing `test_release_desktop_workflow`
  errors): **2021 passing**.

- **2026-05-01 — planner: per-run trace_id (Cursor [A]):**
  Made every plan run independently observable. `PlanRunner.run`
  now mints a fresh `trace_id` per invocation (was: reused the
  plan's birth trace via `trace_scope(parent=plan.trace_id)`),
  and the original plan trace travels along as
  `parent_trace_id` on the `plan.run.started` payload + the
  return dict. Side benefit: the per-run cost rollup
  (`_compute_run_usage`) lost its `started_at`/`finished_at`
  time-window clamp because the trace itself is now sufficient
  to scope the SELECT — no off-by-one risk at run boundaries,
  no double-attribution between concurrent runs, and the
  rerun-via-clone flow gets correct rollups for free. Pinned by
  `tests/test_planner_per_run_trace.py` (4 new cases) and the
  refreshed `tests/test_planner_run_usage.py` (renamed
  `…_clamps_to_time_window` → `…_does_not_clamp_by_time_window_anymore`
  with inverted assertion). Full suite: **2026 passing**.
  Follow-ups: surface per-run `trace_id` on `PlanRun.to_dict()`
  for cockpit deep-linking; cockpit can now group activity-
  stream entries by `parent_trace_id` to render "all runs of
  plan X" as a collapsible section.

- **2026-05-01 — planner: clone — rerun a plan without history mutation (Cursor [A]):**
  Lets the operator "rerun" a finished plan without mutating its
  terminal status. The original keeps its `completed`/`aborted`
  row; the clone enters the inbox at `proposed` so the operator
  can approve it again. Three matching surfaces:
  `PlannerStore.clone(plan_id, *, thread_id, trace_id, goal_override)`,
  `POST /api/planner/{plan_id}/clone`, and a CLI subcommand
  (`python -m … clone <id> [--thread-id <t>] [--goal "..."]`).
  Emits `planner.cloned` with `plan_id` (clone) +
  `source_plan_id` (original) + `thread_id_rebind` /
  `goal_overridden` flags; the timeline allow-list and
  summariser pick it up so the cockpit audit lane renders the
  parent → child link. Pinned by `tests/test_planner_clone.py`
  (13 cases). Full suite: **2022 passing**. Follow-ups: cockpit
  "Rerun" button (clone → approve → run); optional
  `clone --approve` CLI flag for one-shot rerun.

- **2026-05-01 — planner: shell CLI (Cursor [A]):**
  Operator-facing scripting tool at
  `python -m backend.core.planner.cli` mirroring `replay_cli`.
  Ten subcommands (`stats`, `list`, `show`, `runs`, `synthesize`,
  `approve`, `reject`, `run`, `abort`, `delete`); each prints
  one machine-friendly JSON object per call (compact with
  `--quiet`) and returns exit 0 on `ok`/1 otherwise so cron
  / Make targets can branch cleanly. `delete` requires `--yes`
  (otherwise returns `confirmation_required`). `run` honours
  `--mode` to override `TARS_POLICY_MODE` per call. Shares the
  same SQLite WAL DBs (`TARS_PLANNER_DB_PATH`,
  `MEEET_STORE_PATH`) as the host process — safe to run side-
  by-side with the cockpit. Unblocks operator scripting,
  cold-start recovery (when HTTP is down), and fleet rollouts
  via shell. Pinned by `tests/test_planner_cli.py` (23 cases).
  Full suite: **2009 passing**. Follow-ups: bash completion
  script, optional `clone` subcommand, `make planner-*` target
  group in the control tower.

- **2026-05-01 — planner: per-run cost / token rollup on terminal event (Cursor [A]):**
  After every plan run, the runner now rolls up `usage.tokens`
  events that fired inside its `trace_id` + wall-clock window and
  stamps the totals (`calls` / `tokens_in` / `tokens_out` /
  `cost_usd` / `latency_ms_total` / `has_priced_models`) on the
  terminal event payload (`plan.completed` / `plan.aborted`), the
  `PlanRunner.run` return dict, and the
  `GET /api/planner/{id}/runs` reflector. `cost_usd` is `None`
  when no priced model fired so the cockpit can render "n/a"
  rather than falsely advertising a free run for a paid call
  whose price isn't in the table. Filtering by both `trace_id`
  AND time window keeps parallel runs of the same plan from
  bleeding into each other (the runner currently inherits the
  plan's birth trace). Pinned by `tests/test_planner_run_usage.py`
  (11 cases: zero-rollup, sums by trace, unpriced cost=None,
  trace-id filter, time-window clamp, runner stamps on completed,
  runner stamps on aborted+raise, zero when silent, reconstructor
  reads usage, reconstructor handles legacy payload, end-to-end
  HTTP). Full suite: **1986 passing**. Follow-ups: drop the
  time-window clamp once each run mints its own trace; cockpit
  drawer renders `has_priced_models=false` as "n/a · N tokens".

- **2026-05-01 — planner: per-plan run history + Last-Event-ID SSE resume (Cursor [A]):**
  Two cockpit reads land together. `GET /api/planner/{plan_id}/runs`
  reconstructs every past execution of one plan from the meeet event
  store (no parallel "runs" table — single source of truth shared with
  the timeline / SSE / gold-pill audit lane). Walks
  `plan.run.started → plan.completed | plan.aborted` windows;
  authoritative counters (`steps_run` / `steps_blocked` /
  `steps_failed`) come from the terminal event when present, locally
  derived otherwise. Returns runs newest-first with `count` and
  `in_flight` rolled up. The SSE stream now honours the standard
  `Last-Event-ID` HTTP header (header wins over `after_id` query;
  invalid header silently falls back to query / default), so a vanilla
  `EventSource` reconnect resumes correctly without cockpit-specific
  glue. The `hello` frame advertises `after_id_source` so the cockpit
  can tell whether the cursor came from a real reconnect or a fresh
  subscribe. Pinned by `tests/test_planner_history.py` (16 cases).
  Full suite: **1975 passing**. Follow-ups: cockpit "Plan Inbox"
  panel can now consume `/events?thread_id=…` *and* the new runs
  drawer; optional `--gc-orphans` CLI flag for pruning stale
  partial-run events past a retention horizon.

- **2026-05-01 — planner: SSE event stream + meeet.list_events(after_id) (Cursor [A]):**
  Live feed for the cockpit "approval inbox". New
  `GET /api/planner/events` SSE endpoint mirrors `/api/awareness/stream`:
  emits `hello` (with active filter + cursor), then per-event frames in
  id-ascending order, then `bye` on `max_duration_reached` /
  `client_disconnect`. Optional query params `plan_id` / `thread_id`
  filter on payload; `after_id` is the resume cursor; `poll_interval_s`
  / `max_duration_s` tune the loop. Powered by a new
  `MeeetStore.list_events(after_id=N)` filter (SQLite `id` is
  monotonic). Surfaces every kind in the L6.2 family
  (`plan.proposed` / `planner.synthesis.{completed,failed}` /
  `planner.{approved,rejected,deleted}` / `plan.run.started` /
  `plan.step.{requested,allowed,completed}` / `plan.completed` /
  `plan.aborted` / `plan.abort.requested`). Pinned by
  `tests/test_planner_sse.py` (9 cases incl. cursor advance,
  filter rejection still advancing cursor, no-collision with
  `/{plan_id}`). Full suite: **1959 passing**. Follow-ups: native
  `Last-Event-ID` header parsing, reverse push from a single
  TARS process, cockpit "Plan inbox" panel.

- **2026-05-01 — timeline: plan.* events visible in per-thread feed (Cursor [A]):**
  Phase L6.2 shipped the planner runner + a full `plan.*` event family
  but the per-thread timeline (`backend/core/search/timeline.py`) had
  not been taught about it. Cockpit threads where the operator ran a
  plan rendered gaps. This PR adds every new event kind
  (`plan.proposed`, `planner.{approved,rejected}`,
  `plan.run.started`, `plan.step.{requested,allowed,completed}`,
  `plan.completed`, `plan.aborted`, `plan.abort.requested`) to
  `_RELEVANT_EVENT_KINDS` and adds matching `_summarise_event` branches
  with a consistent `plan=<id> · …` shape. The
  `plan.step.completed` summariser ranks `skipped` > `blocked` >
  `failed` > `ok`. `plan.proposed` truncates the goal at 60 chars.
  Pinned by `tests/test_thread_timeline.py` (12 new cases incl.
  end-to-end flow). Full suite: **1950 passing**.

- **2026-05-01 — Phase L6.2: planner runner (PlanRunner + abort + plan.* events) (Cursor [A]):**
  Second slice of Phase L6. New `backend/core/planner/runner.py` ships
  the `PlanRunner` that takes an `approved` `Plan`, drives every step
  through the same policy gate the playbook runner uses, and emits the
  `plan.*` lifecycle events spec'd in L6.2 (`plan.run.started` /
  `plan.step.{requested,allowed,completed}` / `plan.completed` /
  `plan.aborted`, plus `plan.proposed` at synthesis time). The runner
  reuses `PlaybookRunner._dispatch` via a thin `_AdaptedStep` adapter so
  the dispatcher logic (awareness snapshots, policy gate, error mapping)
  stays single-sourced. Status transitions `approved → running →
  completed/aborted` are runner-owned and persisted to the planner
  store. Cooperative abort: `PlanRunRegistry.abort(plan_id)` flips an
  `asyncio.Event` that the runner observes between groups (never
  mid-step). New HTTP: `POST /api/planner/{plan_id}/run` (resolves
  policy mode from body / `x-tars-policy-mode` header / env, wraps in
  `thread_id_scope` so events inherit the persisted thread id) and
  `POST /api/planner/{plan_id}/abort` (404s when not in flight,
  otherwise emits `plan.abort.requested`). Pinned by
  `tests/test_planner_runner.py` (21 cases). Full suite:
  **1937 passing**. Follow-ups: real cloud-LLM voices in the
  synthesizer, cockpit "approval inbox" UI driven by `plan.*` events,
  optional `mode=async` for fire-and-forget runs.

- **2026-05-01 — Phase L6 v1: planner foundations (synthesis + persistence) (Cursor [A]):**
  Phase L6 (Planner / Agent loop) starts here. New module
  `backend/core/planner/` ships the foundations: `Plan` /
  `PlanStep` dataclasses + `PlanStatus` enum,
  `PlannerStore` (SQLite at `~/.tars/planner.sqlite`, override
  `TARS_PLANNER_DB_PATH`), and a deterministic
  `synthesize_plan(goal, …)` that maps operator goals onto either
  a registered playbook or a single-action fallback. Resolution
  priority: playbook id → name → tag → action substring →
  pack-snapshot fallback. Stable error reasons (`empty_goal` /
  `no_match` / `ambiguous_packs` / `unknown_pack`) so the HTTP
  layer can render localised envelopes. New router at
  `/api/planner` exposes a complete CRUD surface (POST /plan,
  GET /{id}, GET /, GET /_stats, POST /{id}/status,
  DELETE /{id}). Operator transitions (`approved` / `rejected`)
  emit `planner.{approved,rejected}` events; the runner-owned
  `running` / `completed` / `aborted` transitions land in the
  next slice. Pinned by `tests/test_planner_synthesis.py`
  (41 cases). Full suite: **1916 passing**. Follow-up:
  `PlannerLoop` runner that consumes `approved` plans and drives
  `PlaybookRunner` in interactive mode (`plan.*` events from
  L6.2 spec).

- **2026-05-01 — MeeetClient.emit auto-injects thread_id from contextvar (Cursor [A]):**
  After the ContextVar bridge (PR #99), every router that handles
  `x-tars-thread-id` opens `thread_id_scope(...)` so the active
  chat thread id rides on the asyncio context. This PR completes
  the loop by having `MeeetClient.emit(...)` automatically copy
  the contextvar's value into `payload['thread_id']` when the
  contextvar is set AND the caller didn't already place
  `thread_id` in the payload. Net result: every meeet event
  emitted from inside an `invoke_action` / `confirm` /
  `awareness_snapshot` scope automatically carries the chat
  thread id, so the cockpit per-thread audit lane fills in for
  every emitted event kind without per-router plumbing. Explicit
  call-site values always win. Pinned by
  `tests/test_meeet_auto_thread_id.py` (8 cases) plus regression
  on the previous PRs. Full suite: **1875 passing**.

- **2026-05-01 — ContextVar bridge: action handlers auto-inherit thread_id (Cursor [A]):**
  PRs #97 (policy) and #98 (council HTTP) plumbed `x-tars-thread-id`
  through the gate and the council's HTTP entry. The remaining gap
  was action handlers calling `get_council().deliberate(...)` from
  inside `invoke_action` — those handlers don't see the request
  thread_id directly. This PR closes that gap with a `ContextVar`
  bridge: new `current_thread_id()` + `thread_id_scope(...)` in
  `backend/core/meeet/tracing.py`. `invoke_action` and the policy
  `confirm` route open the scope; the council orchestrator falls
  back to `current_thread_id()` when no explicit `thread_id` kwarg
  is passed (explicit still wins). Net result: an action invoked
  from a chat thread auto-propagates `thread_id` into every
  council/sampler/policy event it triggers, no per-handler
  plumbing needed. Pinned by `tests/test_thread_id_contextvar.py`
  (12 cases) plus regression on `test_council_thread_linkage.py`
  (10) and `test_policy_thread_linkage.py` (12). Full suite:
  **1867 passing**.

- **2026-05-01 — Council/sampler events thread chat thread_id end-to-end (Cursor [A]):**
  After the policy-event linkage (PR #97), the next gap in the
  per-thread audit lane was the council layer. The timeline already
  accepts `council.deliberation.{started,completed}` and
  `sampler.decision`, but none of those events carried a `thread_id`.
  This PR adds `thread_id: str | None = None` kwarg to
  `CouncilOrchestrator.deliberate(...)` and surfaces it on every
  event the orchestrator emits (started, per-voice `usage.tokens`,
  `sampler.decision`, completed) — only when present (exact-match
  filter downstream). The HTTP surface
  `POST /api/council/deliberate` reads `x-tars-thread-id` and
  forwards. Pinned by `tests/test_council_thread_linkage.py`
  (10 cases) plus regression on `test_council.py` (8) and
  `test_council_parallel.py` (17). Full suite: **1855 passing**.
  Follow-up: action handlers calling `get_council().deliberate(...)`
  from inside `invoke_action` (e.g. `business.daily_brief`,
  `traders.summarize_market`) don't yet see the request thread_id.
  A clean fix is a `current_thread_id` ContextVar set in
  `invoke_action` and read by the orchestrator; out of scope for
  this PR.

- **2026-05-01 — Policy gate threads chat thread_id end-to-end through every policy.* event (Cursor [A]):**
  Last PR's per-thread timeline now renders policy event summaries
  correctly *if* the events carry a `thread_id` — but no policy event
  ever did. This PR threads `x-tars-thread-id` from the action HTTP
  entry through `policy.gate.check()`, persists it on the
  `confirmations` row (additive SQLite migration via
  `_ADDITIVE_COLUMNS`), and re-attaches it to every follow-up policy
  event so the cockpit per-thread audit lane finally fills in for
  chat-driven destructive actions. Wires: `web_extras/routers/domains.py`
  (`policy.queued` / `policy.blocked` / `policy.allowed`),
  `web_extras/routers/policy.py` via the new `_attach_thread_id`
  helper (`policy.confirm` / `policy.cancelled` / `policy.expired`),
  and `web_extras/app.py::_policy_expire_loop` (`policy.expired` from
  the background tick). The `thread_id` field is omitted when the
  header is absent (timeline filter is exact-match). Pinned by
  `tests/test_policy_thread_linkage.py` (12 cases) plus regression
  on `test_policy.py`, `test_policy_expire_loop.py`,
  `test_thread_timeline.py`. Full suite: **1845 passing**.

- **2026-05-01 — Per-thread timeline: fix policy event names + summariser bug, expand kinds (Cursor [A]):**
  The per-thread timeline (`backend/core/search/timeline.py`,
  `GET /api/chat/threads/{id}/timeline`) was untested and three things
  were quietly wrong: (1) `_RELEVANT_EVENT_KINDS` listed event names
  nobody emits (`policy.confirmed`, `policy.rejected`,
  `playbook.step.failed`) and missed real ones (`policy.confirm`,
  `policy.cancelled`, `policy.blocked`, `policy.expired`,
  `playbook.started`, `playbook.completed`, both
  `council.deliberation.*`); (2) the `policy.*` summariser read
  `payload['action_id']` but every router emits `payload['action']` —
  the cockpit always rendered `action=?`; (3) no summarisers existed
  for playbook / sampler / council events. All three fixed in this
  PR. The `policy.*` summariser now renders `slug=… · action=… ·
  token=…` (with `expired_at=…` for `policy.expired`); new
  summarisers for `sampler.decision` (winner / stance / agreement /
  cost / parallel), `council.deliberation.{started,completed}`, and
  `playbook.{started,step.completed,completed}` give the cockpit
  audit panel rich descriptions per event. Pinned by
  `tests/test_thread_timeline.py` (27 cases — module was previously
  untested). Full suite: **1833 passing**.

- **2026-05-01 — Policy gate auto-expires stale confirmations + emits `policy.expired` (Cursor [A]):**
  Closed two operator-workflow gaps in the destructive-action policy
  gate. (1) Nothing automatically reaped stale `pending` confirmations
  — a token sat in the cockpit's "approval inbox" forever unless an
  operator manually hit `POST /api/policy/expire`. (2) The expire path
  emitted no meeet event, so the audit lane saw `policy.queued` going
  in but never the matching expiry. New `_policy_expire_loop` in
  `web_extras/app.py` ticks every `TARS_POLICY_EXPIRE_INTERVAL_S`
  (default `0` = off, opt-in like memory-purge), reaps stale tokens
  via the refactored `PolicyStore.expire_stale()` (now returns
  `list[PendingConfirmation]` so callers can emit per-token events),
  and emits a `policy.expired` meeet event per reaped token carrying
  `{token, slug, action, expired_at, trace_id}`. The
  `POST /api/policy/expire` HTTP route emits the same event shape so
  the cockpit treats both paths uniformly. Pinned by
  `tests/test_policy_expire_loop.py` (15 cases) plus the existing
  `tests/test_policy.py` test updated for the new return shape. Full
  suite: **1806 passing**.

- **2026-05-01 — Council orchestrator runs voices in parallel (Cursor [A]):**
  `CouncilOrchestrator.deliberate(...)` now fans every chosen voice out
  through `asyncio.gather(..., return_exceptions=True)` instead of
  awaiting each `propose(...)` call serially. With three LLM voices
  configured (12 s transport timeout each) deliberation wall-clock
  drops from up to ~36 s to `max(per-voice latency)`. Per-voice
  exceptions are isolated as `unavailable` proposals so one broken
  adapter cannot crash a council turn. `usage.tokens` events still
  emit serially in input order after the gather to keep the cost
  ledger deterministic. `sampler.decision` adds three additive keys
  (`latency_ms` is now wall-clock, `cumulative_latency_ms` keeps the
  sum, `parallel: bool`) without breaking existing consumers. New
  `_propose_one(...)` helper backfills `latency_ms` for voices that
  forget to stamp it. Pinned by `tests/test_council_parallel.py`
  (17 cases). Existing council suite + chat orchestrator suite pass
  unchanged. Full suite: **1791 passing**.

- **2026-05-01 — `science.hypothesis_tree` real deterministic generator (Cursor [A]):**
  Promotes the last user-facing stub in the science pack
  (`hypothesis_tree` returned `{node, children: []}`) into a
  deterministic, audit-friendly hypothesis decomposition. New
  `backend/core/domains/packs/science/hypothesis.py` ships a
  `grow_tree(seed, *, depth=1)` builder that fans out along five
  canonical dimensions (`mechanism / alternatives / confounders /
  conditions / evidence`) with per-dimension grandchild templates
  (steps, alternatives, confounders, conditions, tests). At depth=2
  the tree is 16 nodes (1 seed + 5 children + 5×2 grandchildren).
  Stable `h-NNNN` ids and typed `kind` per node so the cockpit
  can pin expand state and colour-code layers. Seed normaliser
  strips trailing punctuation so prompts read cleanly. Depth
  clamped to `[0, 3]`. Action returns the *effective* depth
  post-clamp + `model="heuristic-v1"` label. Pinned by 24 new
  tests; full suite: **1774 green**.

- **2026-05-01 — `mlm.update_member` + `mlm.list_members` close downline lifecycle (Cursor [A]):**
  Closes the MLM downline lifecycle: `add_member` writes,
  `downline_snapshot` / `retention_alert` summarise, but operators
  had no patch-style update path and no read-only "show me everyone
  in this branch" side door. New `update_member` (destructive, patch
  semantics, idempotent, emits `mlm.member_updated` listing
  `changed_fields`) and `list_members` (non-destructive, filter by
  sponsor / rank / `recent_days` / `limit`, returns `summary.by_rank`
  + `summary.total_volume_usd` rollups). Pinned by 33 new tests +
  destructive-spec membership pin update; full suite: **1750 green**.

- **2026-05-01 — `business.local_deals` awareness source (Cursor [A]):**
  Mirrors `traders.local_alerts` for the business pack. New
  `_fetch_local_deals` returns a structurally-stable envelope
  (`count` / `pipeline_usd` / `by_stage` / `by_owner` / `deals` /
  `filters`) defaulting to `active_only=True`, `limit=50` (clamped
  to 200). `pipeline_usd` excludes terminal stages so the ticker
  shows only money still in motion. Registered as
  `business.local_deals` (`kind="local"`) advertising the default
  store path so the cockpit form renders sensible defaults. 13 new
  tests cover defaults, terminal-stage handling, missing store,
  path override, aggregations, owner/stage normalisation, limit
  clamping, and pack wiring; the live-fetcher membership pin in
  `tests/test_awareness_fetchers.py` is extended. Full suite:
  **1717 green**.

- **2026-05-01 — `business.list_deals` read-only side door (Cursor [A]):**
  Mirrors `traders.list_alerts` for the business pack. New
  `read_local_deals` helper + `list_deals` action provide a fast,
  non-destructive read on the local deals store with filters
  (`active_only / stage / owner / limit`) and pre-computed rollups
  (`by_stage`, `total_amount`). Avoids spinning up the council just
  to enumerate deals. Pinned by 18 new tests; full suite:
  **1703 green**.

- **2026-05-01 — `business.update_deal` closes the deal lifecycle (Cursor [A]):**
  Mirrors today's `traders.cancel_alert` work for the business pack.
  New `update_local_deal` helper + `update_deal` action handler patch
  any subset of `name / amount / stage / owner / next_step / due /
  notes` on a previously-logged local row, stamp `updated_at`, and
  emit `business.deal_updated` listing `changed_fields`. Optional
  strings: `""` clears a field, `None` (or omission) leaves it
  untouched. Idempotent: a no-op patch returns `unchanged=True` and
  emits no event. Policy gate routes `business.update_deal` through
  confirmation alongside `log_deal`. Pinned by 30 new tests
  (including end-to-end `log → update → daily_brief reflects won
  deal`); full suite: **1685 green**.

- **2026-05-01 — `traders.local_alerts` awareness source (Cursor [A]):**
  Closes the cockpit-side loop on the new local-first alerts store.
  New `_fetch_local_alerts` returns a structurally-stable envelope
  (`count` / `by_direction` / `by_ticker` / `alerts` / `filters`)
  defaulting to `active_only=True`, `limit=50` (clamped to 200).
  Registered as `traders.local_alerts` (`kind="local"`) advertising
  the default store path so the cockpit form can render sensible
  defaults. 12 new tests cover defaults, inactive inclusion, missing
  store, path override, aggregations, ticker normalisation, limit
  clamping, and pack wiring; the live-fetcher membership pin in
  `tests/test_awareness_fetchers.py` is extended to include the
  new source. Full suite: **1656 green**.

- **2026-05-01 — `traders.cancel_alert` closes the alerts lifecycle (Cursor [A]):**
  Natural follow-up to the `place_alert` real adapter. Adds a new
  `cancel_local_alert` helper to
  `backend/core/domains/packs/traders/local_alerts.py` plus a
  `cancel_alert` action handler. Marks the row `active=False`, stamps
  `cancelled_at` (UTC ISO Z) + optional `cancel_reason`, leaves all
  other fields untouched for the audit trail. Idempotent: a second
  cancel of the same id returns `already_inactive=True` and emits no
  duplicate meeet event. Policy gate now routes `traders.cancel_alert`
  through confirmation alongside `place_alert`. Action surfaces
  stable error codes (`alert_id_required`, `alert_not_found`,
  `local_store_unwritable`). Pinned by 14 new tests + 1 update to the
  destructive-spec membership pin; full suite: **1644 green**.

- **2026-05-01 — `traders.place_alert` real local-first store + `list_alerts` (Cursor [A]):**
  Promotes the last hardcoded stub in the traders pack
  (`return {"alert_id": "stub-0001"}`) into a real local-first
  adapter. New `backend/core/domains/packs/traders/local_alerts.py`
  persists every alert into `~/.tars/traders_alerts.json` (override
  via `TARS_LOCAL_ALERTS_PATH` or `path` kwarg), mints monotonic
  `local-alert-NNNN` ids, validates inputs strictly with stable
  error codes (`ticker_required`, `price_invalid`,
  `direction_invalid`), and emits `traders.alert_placed` meeet
  events. Allowed directions expanded to
  `above / below / cross_above / cross_below`. The destructive-action
  policy gate now confirms a real persisted receipt instead of a
  hardcoded echo. New non-destructive `list_alerts` action lets
  operators / playbooks read the queue back with `ticker`,
  `active_only`, `limit` filters. Pinned by 69 new tests covering
  path resolution, store IO, atomic writes, ID generation,
  coercion edge cases, the action handlers, and ActionSpec
  wiring; full suite: **1630 green**.

- **2026-05-01 — entrepreneur pack schema parity for `generate_content` (Cursor [A]):**
  Syncs the entrepreneur pack's `generate_content` `ActionSpec`
  schema with the upgraded MLM drafter that landed earlier
  today. Exposes the new `tone` / `language` / `cta` knobs and
  the `linkedin` channel through the entrepreneur namespace so
  the cockpit can render full dropdowns. Imports the enum
  tuples directly from `mlm.post_drafter` so the entrepreneur
  pack can never drift from the underlying drafter. Pinned by
  2 new tests; full suite: **1561 green**.

- **2026-05-01 — `mlm.generate_post` real multi-channel drafter (Cursor [A]):**
  Promotes the last user-facing stub in the MLM pack to a real
  deterministic drafter. New
  `backend/core/domains/packs/mlm/post_drafter.py` lands a 4×4×3
  template registry (channel × tone × language) plus per-format
  overlays (story / reel / dm), language-aware CTAs, and
  ASCII-safe hashtag generation for ig + linkedin. Channels now
  cover ig / tg / wa / linkedin; tones add warm / professional /
  urgent / celebratory; languages cover en / ru / es. The action
  surfaces `draft`, `cta`, `hashtags`, `char_count`,
  `word_count` per platform-budget UX, and emits `mlm.post_drafted`
  per the cross-cutting adapter rule. Backward compat
  preserved for `playbooks/mlm/retention_round.json`. Pinned by
  33 new tests covering full-matrix template coverage,
  determinism, coercion, format overlays, hashtag rules, and
  retention_round playbook compatibility; full suite:
  **1559 green**.

- **2026-05-01 — `daily_brief` unions locally-logged deals (Cursor [A]):**
  Closes the loop on the `log_deal` adapter shipped earlier today.
  `daily_brief` now reads `~/.tars/business_deals.json` (override
  via `TARS_LOCAL_DEALS_PATH` or new `local_deals_path` arg) and
  unions it with the bundled snapshot. Local rows whose id
  collides with a bundled row replace the bundled payload
  (operator's latest action wins); brand-new local ids append.
  Response gains `deals_local_logged` count, `local_deals_path`
  (resolved), and a `"local-store"` source marker. Defensive
  against missing / corrupt local files; refuses to double-load
  when both paths resolve to the same file. Pinned by 10 new
  tests including the end-to-end "log_deal → daily_brief"
  closed-loop test; full suite: **1526 green**.

- **2026-05-01 — `mlm.score_recruit` over real downline signals (Cursor [A]):**
  Promotes the score_recruit action from a one-line `hash()`
  heuristic — which was non-deterministic across machines because
  `hash()` is randomised by PYTHONHASHSEED — to a real local-first
  scorer over the downline DB. New
  `backend/core/domains/packs/mlm/scoring.py` lands a pure
  scoring engine: `RecruitSignals` dataclass, recency / volume /
  rank / tenure components with sane saturation thresholds,
  weighted composition (`0.40 / 0.30 / 0.20 / 0.10`), a curated
  7-step rank ladder (`junior → founder`), and a stable
  SHA-256-derived fallback mapped onto `[0.40, 0.95]` for
  unknown handles. The action now consults the downline DB,
  surfaces `signals{}`, `rank`, `volume_usd`, `days_silent`,
  and switches `model` between `"downline-v1"` (real) and
  `"heuristic-v1"` (fallback). DB failures fall through cleanly
  to the unknown-handle branch. Pinned by 40 new tests covering
  per-component math, composition + clamping, and action
  integration; full suite: **1516 green**.

- **2026-05-01 — `business.log_deal` real local-first adapter (Cursor [A]):**
  Promotes the last open stub in the business pack to a real
  local-first action. When neither HubSpot nor Pipedrive
  credentials are configured, deals append to a local JSON
  store at `~/.tars/business_deals.json` (override via
  `TARS_LOCAL_DEALS_PATH` or the new `store_path` arg) — the
  same shape `daily_brief` already reads, so logged deals show
  up next morning. New
  `backend/core/domains/packs/business/local_deals.py` covers
  path resolution, defensive load (corrupted JSON / non-list /
  mixed rows tolerated), atomic tmp+rename writes,
  monotonically-incrementing `local-NNNN` ids that ignore
  unrelated CRM rows, and a process-local lock. Each successful
  append emits `business.deal_logged` per the cross-cutting
  adapter rule. The `log_deal` action's `ActionSpec` schema
  also gains `owner` / `next_step` / `due` / `notes` /
  `store_path` plus a `stage` enum for cockpit dropdowns.
  Pinned by 43 new tests (incl. `OSError` surface, corrupt-store
  recovery, monotonic ids, CRM short-circuit untouching the
  local store); full suite: **1476 green**.

- **2026-05-01 — `science.extract_dataset` reads attachments (Cursor [A]):**
  Closes the natural follow-up to the real-adapter promotion:
  the action now accepts `attachment_id` alongside `text` and
  `ref`. Resolves chat attachments via the existing
  `AttachmentStore.get_attachment(id)` async API, runs the same
  deterministic detector against `record.extracted_text`, and
  surfaces `attachment_id` / `filename` / `mime` / `thread_id`
  on the response so the cockpit can label result rows with
  the source paper. New error codes `attachment_not_found` and
  `attachment_empty` (with a `hint`) cover the missing /
  ingestion-still-running cases. Lazy import keeps the science
  pack importable in offline / unit-test envs. Priority order
  documented in the docstring + `ActionSpec` schema:
  `text` > `attachment_id` > `ref`. Pinned by 7 new tests
  (incl. priority enforcement and attachment-not-found / empty
  paths); full suite: **1433 green**.

- **2026-05-01 — `science.extract_dataset` real adapter (Cursor [A]):**
  Promotes the science pack's `extract_dataset` action from a typed
  stub to a deterministic detector. Surfaces dataset references in
  a paper (arXiv ref) or operator text via two complementary
  detectors: a curated `KnownDataset` registry (~25 entries —
  ImageNet, COCO, GLUE, SQuAD, MMLU, LibriSpeech, UK Biobank, …)
  with case-insensitive whole-word matching, and a `RepoPattern`
  library covering Zenodo / Figshare / HuggingFace / Kaggle /
  OpenML / OSF / Dryad. Output dedupes per `(canonical_id, source)`
  and ships an `evidence` snippet so operators can verify the
  call. Pinned by 27 new tests; full suite: 1426 green.

- **2026-05-01 — Recovery challenge rate-limit (Cursor [A]):**
  Closes the open follow-up from PR #74 by extending the per-IP
  token-bucket pattern to the `/api/recovery/challenge/{start,
  verify}` endpoints. Default 5 burst + 1/30s on `start` and
  10 burst + 1/10s on `verify` (env-tunable via
  `TARS_RECOVERY_CHALLENGE_{START,VERIFY}_{BURST,RATE_PER_S}`).
  429 envelopes use `TARSAPIError` and emit a
  `recovery.rate_limited` meeet event so the
  `/api/pairing/audit` feed (PR #77) surfaces brute-force
  attempts. Pinned by 7 new tests; full suite: 1399 green.

- **2026-05-01 — Pairing audit feed + meeet kind_prefix (Cursor [A]):**
  Adds the missing read-side for the pairing audit lane.
  `MeeetStore.list_events()` gains a `kind_prefix` filter
  (`kind LIKE ? ESCAPE '\\'` with defensive metachar escape);
  `GET /api/meeet/events` exposes it as a query param. New
  `GET /api/pairing/audit` folds `pair.*` + `recovery.*` into one
  newest-first deduped feed, returning the public-safe
  `{id, ts, trace_id, kind, payload}` shape so internal-only
  fields (`pushed`, `last_error`, `source`) don't bleed into the
  operator timeline. Pinned by 12 new tests; full suite: 1392 green.
  The cockpit gold-pill audit lane (Claude lane) can now consume
  this directly.

- **2026-05-01 — Rotate-identity epoch bump (Cursor [A]):**
  Closes the open follow-up on the rotate-identity endpoint. The
  rotate now snapshots paired devices, calls `store.revoke()` on
  each (because their pinned public keys reference the old host
  identity), and emits `pair.epoch_bumped` with the cleared list
  so the cockpit gold-pill audit lane can render a distinct epoch
  bump row. `pair.host_rotated` gains a `cleared_device_count`
  field for replay correlation. Zero-device rotates intentionally
  omit `pair.epoch_bumped` to keep the timeline clean. 4 new
  tests; full suite: 1380 green.

- **2026-05-01 — Rotate-identity gated by 3-of-24 challenge (Cursor [A]):**
  Wires the first real consumer for the seed-challenge primitive
  shipped in PR #73. New `consume_passed_challenge` helper
  atomically transitions a `passed` challenge to `consumed`
  (single-use, fingerprint-bound), and a new
  `POST /api/pairing/rotate-identity` endpoint mints a fresh host
  keypair only when the operator can prove they still hold the
  seed bound to the current identity. Optional
  `new_recovery_fingerprint` body knob lets the operator rebind
  the seed at the same time as the keypair (e.g. after a seed-leak
  event). 409 envelopes for `recovery_not_bound`,
  `challenge_not_passed`, `fingerprint_mismatch`; 404 for
  `challenge_not_found`; all via `TARSAPIError`. Emits
  `pair.host_rotated` on success with old/new public key + bound
  fingerprint. Tests: 10 unit + 9 HTTP. Full suite: 1376 green.

- **2026-05-01 — Pairing relay rate-limit (Cursor [A]):**
  Added stdlib-only token-bucket rate limiter
  (`web_extras/rate_limit.py`) and wired it into
  `POST /api/pairing/begin` so pairing-token mints from a single IP
  cannot be spammed. Defaults: 10 burst + 30/min (env-tunable via
  `TARS_PAIR_BEGIN_CAPACITY` / `TARS_PAIR_BEGIN_REFILL_PER_MIN`).
  Trust of `X-Forwarded-For` is opt-in via
  `TARS_TRUST_FORWARDED_FOR=1`. 429 responses use the unified
  `TARSAPIError` envelope with `Retry-After`,
  `X-RateLimit-{Remaining,Reset,Bucket}` headers and emit a
  `pair.rate_limited` meeet event; allowed calls also surface a
  `rate_limit` block on the JSON body and the `pair.attempted`
  event so operators can see how close the IP is to the cap.
  Tests: 25 cases in `tests/test_rate_limit.py`; the
  `test_pairing_contract.py` fixture also resets the limiter
  singleton to avoid cross-test bleed. Full suite: 1312 green.

- **2026-05-01 — Master release roadmap + default-EN + QA browser suite (Cursor, cross-repo):**
  Drafted the single source-of-truth release plan in
  `docs/ROADMAP_TO_RELEASE.md` (Phases A–D: i18n parity, QA-suite,
  TARS finalisation, release-readiness gate; with slices, owners,
  acceptance, calendar, secrets matrix, and rollback). Then delivered
  Phase A and the QA-suite skeleton (Phase B) as **core PR #8**
  (`cursor/i18n-default-en-and-qa-suite`):
  1. **Default-EN on first visit** — bumped `meeet-lang`→`meeet-lang-v2`
     in `LanguageContext`; legacy `ru` is intentionally not migrated;
     all visitors get English on first refresh.
  2. **EN baseline on the most-mixed pages** — `Tars.tsx` (full),
     `Tokenomics.tsx` (SEO meta), `Settings.tsx` (notif/profile/danger).
     Remaining ~38 RU-mixed pages are Lovable's per the roadmap.
  3. **QA-suite (Layer 2)** — new top-level `qa-suite/` with isolated
     Playwright config, `qa-report/1.0.0` JSON schema (matches TARS
     Layer-1 in `scripts/qa_agent/`), and four probes: `routing.discover`,
     `i18n.parity`, `navigation.navbar`, `assets.console`.
     `package.json` exposes `qa:browser`/`qa:browser:headed`/`qa:browser:report`.
     Standalone strict tsconfig.
  4. Bundles the navbar e2e fix from PR #6 → branch is green on its own.

  Validation (core repo): `npx vitest run` → 332/337 (5 skipped),
  `npm run build` → green ~4.9s, `tsc --noEmit -p qa-suite/tsconfig.json`
  → green. Full PR description: <https://github.com/alxvasilevvv/meeet-solana-state-941a6045/pull/8>.

- **2026-05-01 — Cross-repo: Control Tower in core repo (Cursor):**
  Landed 4 commits in **`meeet-solana-state-941a6045`** (Lovable lane,
  not pushed — awaiting Lovable review per SYNC rule):
  1. `chore(control-tower): add cross-lane control plane and bridge hardening`
     — `COORDINATION.md`, `docs/CONTROL_TOWER.md`, runbook env knob,
     three smoke scripts, three npm scripts (`smoke:tars-bridge`,
     `smoke:core-connectivity`, `gate:control-tower`), and explicit
     `TARS_ALLOWED_ORIGINS` allowlist on `tars-downloads` /
     `tars-ingest` edge functions.
  2. `fix(pricing,content)` — Deploy.tsx reads `plan.price_meeet` from
     API instead of hardcoded `MEEET_PRICES`; toned-down FAQ copy on
     Deploy + Tars; navbar mobile bottom nav test aligned with current
     copy.
  3. `content(tokenomics)` — distribution rebalance (Liquidity
     5%→15%, Reserve 5% replaces Staking 15%) + APY copy 25%→30%.
  4. `chore(control-tower): SOFT_SMOKE mode` — dev-only flag that lets
     the bridge gate pass without `TARS_INGEST_API_KEY` (downloads
     health only). Production gate must keep `SOFT_SMOKE` unset.

  Also reverted an unstaged delete of cron `schedule` directives in
  `supabase/config.toml` (Lovable-authored). Validation:
  `npm run test` 326/331, `npm run build` ok,
  `SOFT_SMOKE=1 npm run gate:control-tower` PASS,
  `tars-downloads` reachable from `Origin: https://meeet.world`.
  Full file list in `docs/CHANGELOG_AGENTS.md` entry of same date.

- **2026-04-30 — Global verification pass + frontend deps sanity (Cursor):**
  Full backend suite green: `pytest -q` → **674 passed**. Showcase checks
  green: `npx tsc --noEmit -p tsconfig.app.json`, `npm run test`
  (56/56), `npm run build`. Local dev runtime was unstable due broken/
  missing `node_modules`; reinstalled and aligned dev deps so Vite
  overlay errors stopped (`tailwindcss` unresolved, missing
  `@tsparticles/react`, missing `@splinetool/react-spline`, missing
  `vitest`). `vitest`/`jsdom` now pinned to project-compatible versions.

- **2026-04-29 — Wave 46 launch gate (`tars.meeet.world`):**
  Backend now exposes ``deprecated`` + ``deprecated_in_favor_of`` on
  ``GET /api/domains`` and the manifest endpoint
  (``backend/core/domains/base.py``, ``web_extras/routers/domains.py``).
  Frontend ``listDomains`` / ``getDomainManifest`` filter on
  ``deprecated === true`` (slug fallback removed). CORS allow-list adds
  ``https://tars.meeet.world`` and accepts comma-separated
  ``TARS_CORS_ORIGINS``. Showcase ``.env.production`` baked
  ``VITE_TARS_API=https://tars.meeet.world``. Pairing router docstring
  + smoke covers all 7 endpoints (``identity`` / ``begin`` /
  ``status`` / ``accept`` / ``devices`` / ``revoke`` / ``reject``).
  Wave 37/40/43 wire glue restored (``getEntitlements`` /
  ``activateRole`` / ``createCustomRole``). Lighthouse + axe scripts
  added (``audit:lighthouse`` / ``audit:axe``). Pytest **674 passed**;
  ``tsc -b`` 0 errors; vite ``build`` + vitest 56/56 green.

- **2026-04-29 — Tauri desktop icons committed (cargo unblocked):**
  ``desktop/src-tauri/icons/`` was empty of PNG/ICNS/ICO despite
  ``tauri.conf.json`` listing them — ``cargo test`` failed on every
  clone. Added ``assets/icon-source.png`` (placeholder), ``scripts/mint_placeholder_icon.py``, ran ``tauri icon`` → 53 files;
  ``npm run tauri:icons`` in ``desktop/package.json``; removed stray
  ``use tauri::Manager`` warning. ``cargo test`` clean.

- **2026-04-29 — Downloads default manifest + npm version aligned alpha.2:**
  `DEFAULT_MANIFEST` bumped from `0.1.0-alpha.1` → `0.1.0-alpha.2`;
  Linux x64 AppImage added to placeholders, `_DEFAULT_NOTES` Phase M.
  `desktop/package.json` version matches `tauri.conf.json`.
  `desktop/scripts/updater-pubkey-status.sh` prints whether
  `plugins.updater.pubkey` is still `TODO_PUBLIC_KEY`; OPERATOR_RUNBOOK
  §0a references it. `pubkey` in repo intentionally still TODO —
  operators patch via existing `generate-release-keys.sh`.

- **2026-04-29 — Console-warning sweep (post shader swap):**
  Operator asked for another audit pass. Pulled the live console
  on `127.0.0.1:5174/` and cleared 25 of 30 runtime warnings/errors.
  - **React Router v7 future flags** wired in `src/main.tsx`
    (`v7_startTransition`, `v7_relativeSplatPath`) → kills 2 warnings.
  - **`useScroll` ref-not-hydrated** (9 errors per page load) →
    `ScrollStory` refactored so `PinnedTrack` computes
    `scrollYProgress` once and passes the `MotionValue<number>` down
    to `ProgressRail` / `CopyPane` / `VisualPane`; 8 redundant
    scroll listeners removed in the process. `Layers` and `Steps`
    got `layoutEffect: false` on their `useScroll`.
  - **iframe sandbox warning** in `CockpitLive` → dropped the
    `sandbox` attribute (same-origin iframe, no protection gained,
    only the browser warning lost). Replaced with
    `referrerPolicy="no-referrer-when-downgrade"`.
  - **Three.js multiple-instances** → `vite.config.ts` got
    `resolve.dedupe = ["three", "react", "react-dom"]` +
    `optimizeDeps.include = ["three"]`. Single bundled `three`
    across the app / R3F / drei / postprocessing / our shader port.
    Spline still bundles its own internally — accepted.
  - **Hero live demo a11y** → cycles only when not hovered/focused
    and not under `prefers-reduced-motion`; container is
    `aria-hidden` because the surfaces are already named in plain
    text in the subline.
  - **Vite chunk warning** → raised `chunkSizeWarningLimit` to 2200
    so the build log only screams on real regressions, not on the
    intentionally-lazy Spline runtime (physics 1.99 MB / react-spline
    2.04 MB).
  - Tests: `pytest -q` 671/671, `tsc --noEmit` clean,
    `npx vitest run` 56/56, `npm run build` clean (no chunk warns).

- **2026-04-29 — Hero swap: orb → shader-lines (21st.dev port, local three):**
  Operator vetoed the orbital-reactor scene shipped earlier today
  ("ужасный элемент") and pointed at
  `21st.dev/community/components/aliimam/shader-lines/default`.
  Pulled the source from the registry CDN and ported it into
  `src/components/ui/shader-lines.tsx` against the local
  `three@0.184.0` instead of injecting `<script
  src="cdnjs.cloudflare.com/.../three.min.js">` at runtime — no
  third-party network call on first paint, no CSP exception, bundle
  hash stays reproducible for signed releases. Fragment shader is
  preserved verbatim so the visual character matches the 21st.dev
  preview exactly. ResizeObserver on the container (not `window`) so
  the shader resizes cleanly with the hero layout. Pixel ratio
  capped at 1.5. `prefers-reduced-motion` freezes the time uniform
  but still renders one calm frame so the visual is not blank.
  Cleanup is StrictMode-safe.
  `<Hero />` background layer renders the shader plus two veils — a
  centred radial gradient (`rgba(7,7,10,0.78) → 0` over 78% of the
  ellipse) to dim the bright centre under the headline, and a 40-tall
  bottom gradient handing off to `--color-bg-0`. Old
  `src/three/HeroScene.tsx` deleted (dead code after swap). Tests:
  `tsc --noEmit` clean / `npx vitest run` 56/56 / `npm run build`
  clean / live verify on `http://127.0.0.1:5174/`.

- **2026-04-29 — Hero refresh (3D scene + sovereignty headline + top-of-fold downloads):**
  Operator pass on `/`. Three asks closed in one turn:
  - **3D animation lit up.** `<HeroScene />` was defined in
    `src/three/HeroScene.tsx` but **never mounted** — fixed via
    `React.lazy` import in `<Hero />`. Reactor now ships with two
    perpendicular orbital rings (cyan + gold) spinning at
    independent sub-Hz rates around an indigo distort-icosa core.
    Camera tuned (z=14, FOV 22) so the orb fills ~25% of viewport
    height — visibly behind the headline, never as a HUD frame
    around it. Bloom intensity 0.28 / threshold 0.86 per Master §6.
    `prefers-reduced-motion` freezes ring rotation + slows orb
    rotation to 0.02 rad/s.
  - **New sovereignty headline.** Three-beat rhythm in both locales:
    EN "Your AI. / Your machine. / Your terms." · RU "Твой ИИ. /
    Твоя машина. / Твои правила." Last line is the gold accent
    (Master §3, single primary accent only). Subline lists every
    Phase-M surface explicitly (files / voice / calendar / code /
    vision / on-chain) with the council-of-agents framing.
  - **DownloadStrip moved top-of-fold.** OS-detected primary button
    + version pill + all-installers chip row are now the FIRST
    action surface a visitor reaches — between subline and demo.
    Wrapped in a backdrop-blur card so it reads cleanly over the 3D
    scene. The footer variant was already mounted in `<Footer />`
    (Cursor shipped that in an earlier batch — Claude's handoff doc
    item 11 was stale, now updated).
  - **Live demo refreshed.** 5 cycling prompts show the surfaces
    that actually shipped this phase: morning-brief, Phantom-wallet
    `propose_send` flow with policy-gate confirm token, entrepreneur
    lead-scoring on CSV, RAG with `[chunk_N]` citations, vision-OCR
    whiteboard pass. No invented features.
  - **Audit collateral.** Killed a dangling-symbol false positive
    in `MarkdownView.tsx` (stale `.tsbuildinfo` cache); pinned
    `VITE_TARS_API=http://127.0.0.1:8765` in `.env.local` so the
    DownloadStrip doesn't render `offline` in local dev; replaced
    `<MeetTars />` h2 ("Your machine, awakened.") with "Two voices.
    One verdict." so it stops shadowing the new hero headline.
  - **Tests:** pytest 671 / vitest 56 / `tsc --noEmit` clean /
    `npm run build` clean. Zero deltas — pure presentation pass.

- **2026-04-29 — K4 cockpit React surfaces (pairing + recovery):**
  Wired `src/lib/{pairing,recovery}.ts` into the v3 cockpit.
  **`RecoverySetup.tsx`** — generate → grid → checkbox → verify typed
  phrase (`verifySeed`). **`PairingPanel.tsx`** — fingerprint, pubkey copy,
  `accept_token` paste + accept, device list + revoke. **`Cockpit.tsx`**
  — `#security` section with both panels + first-launch recovery overlay
  when persisted vault marks `freshly_minted` and no verified fp / skip.
  Plain HUD styling — Claude polishes visuals later. pytest 368 /
  vitest 38 / `tsc --noEmit` clean.

- **2026-04-29 — K2 updater channel + K1 host vault + K3 cockpit clients:**
  Continuation of the same multi-block session. Three more blocks
  from the «Next Cursor block» backlog landed.
  - **K2 — Tauri updater channel publisher**
    (`backend/core/product/updater.py` + CLI flags
    `--updater-out`/`--updater-alias`). Maps sniffed artifacts to
    Tauri target slugs (`darwin-aarch64`, `windows-x86_64`, …);
    reads `<artifact>.sig` sidecars from `tauri signer sign`;
    writes per-target `<target>/<version>.json` plus optional
    aliases (`latest.json`).
  - **K1 — Persistent host keyring**
    (`backend/core/vault/file_vault.py`). XChaCha20-Poly1305 + PBKDF2
    encryption at rest, `0o600` permissions enforced on POSIX hosts,
    atomic writes via temp file + `os.replace`, public-key
    consistency check on load.
    `PairingStore` now accepts a `vault=` arg; default singleton
    picks one from `TARS_PAIRING_VAULT*` env vars. `GET
    /api/pairing/identity` surfaces vault status to the cockpit.
  - **K3 — Cockpit typed clients**
    (`experiments/neural-showcase-v3/src/lib/{pairing,recovery}.ts`).
    Framework-free wrappers + pure helpers (fingerprint format /
    match, QR base64url payload, 4×6 mnemonic grid). Vitest
    coverage: 14 pairing + 12 recovery cases.
  - **Tests:** pytest 368 (+25), vitest 38 (+26), `tsc --noEmit`
    clean.

- **2026-04-29 — L5 contract 1.1.0 + real crypto + recovery seed + Claude handoff:**
  same multi-block session continued. Phase **L5** functionally
  complete on the host side.
  - **meeet contract → 1.1.0** (`backend/core/meeet/`): additive
    `ciphertext` + `envelope` fields on `TARSEvent`; SQLite store +
    replay round-trip them; `client.emit()` accepts the new kwargs.
    Existing 1.0.0 events ride the same wire unchanged.
  - **Real X25519 + XChaCha20-Poly1305 envelope**
    (`backend/core/crypto/envelope.py`): `encrypt_event` /
    `decrypt_event` / `decode_envelope` / `generate_device_key` —
    AAD binds `trace_id|kind` so any tamper invalidates the AEAD
    tag. `pynacl` added to `requirements.txt`.
  - **Pairing real keys** (`backend/core/pairing/store.py`):
    long-term X25519 host keypair on init; `host_public_key`
    surfaced on `begin`; `client_epk` validated as 32-byte base64;
    paired devices register a `DeviceKey` so the envelope can
    encrypt-to-all-paired with one call.
  - **BIP-39 24-word recovery seed** (`backend/core/crypto/recovery.py`,
    `web_extras/routers/recovery.py`): stdlib-only BIP-39 (canonical
    2048-word English list bundled at
    `backend/core/crypto/data/bip39_english.txt`); PBKDF2-HMAC-SHA512
    matches the spec exactly; `seed_to_master_key()` derives an
    X25519 master key. Endpoints
    `POST /api/recovery/{generate,verify}`, `GET .../wordlist/info`
    emit `recovery.{shown,verified}` events carrying **only the
    12-char fingerprint** — never the mnemonic.
  - **Claude handoff package** (`docs/handoff-claude.md`): live API
    outputs, prioritised polish list per cockpit surface, pairing +
    recovery UX sketches, meeet.world SSR recipe, sensitive-data
    rules, quick-start commands.
  - **Tests:** +37 pytest (`test_meeet_contract_v11.py` × 9,
    `test_crypto_envelope.py` × 10, `test_pairing_envelope_e2e.py`
    × 3, `test_recovery_seed.py` × 15); existing
    `test_pairing_contract.py` reworked to use real X25519 keys
    + new field assertions. Full suite **343 pytest + 12 vitest**
    green; cockpit `tsc --noEmit` clean.

- **2026-04-29 — L5 pairing endpoints (mock crypto) + publish CLI + cockpit Vitest:**
  follow-on slice in the same session — turned the L5 *draft* into
  shape-correct, mock-crypto endpoints; landed the release publishing
  CLI; added Vitest for the cockpit download client.
  - **Pairing (`backend/core/pairing/`, `web_extras/routers/pairing.py`):**
    six endpoints — `POST /api/pairing/{begin,accept/{token},reject/{token},revoke}`,
    `GET /api/pairing/{status,devices}` — all emitting
    `pair.{attempted,linked,rejected,revoked}` events into the meeet
    store. In-memory `PairingStore` with stable `host_fingerprint`,
    idempotent `begin`, expiry handling. Crypto stays mock for now
    (the wire shape is final).
  - **Publish CLI (`backend/core/product/publish.py`):** `python -m
    backend.core.product.publish <dir> --version=<v>` sniffs
    artifacts, computes SHA256, writes `~/.tars/releases.json`.
    `--copy-to <dir>` mirrors into staging, `--dry-run` prints to
    stdout, idempotent re-publish of `version+channel`.
  - **Cockpit Vitest:** `vitest@^2` + `jsdom@^25` dev-deps,
    `vite.config.ts` test registration, 12 cases pinning UA
    detection edges (iPhone vs Mac, Pixel vs Linux, Apple Silicon vs
    Intel) and `pickArtifact` fallbacks. Fixed an ordering bug —
    mobile checks now run before desktop.
  - **Tests:** +21 (`test_pairing_contract.py` × 12,
    `test_product_publish.py` × 9, `downloads.test.ts` × 12);
    full suite **305 pytest + 12 vitest** green; cockpit `tsc --noEmit`
    clean.
  - **Tooling:** `Makefile` gains `cockpit-test` + `test-all`.

- **2026-04-29 — L9 desktop scaffold + product manifest API + L5/L10 contracts:**
  full website-direct download channel landed end-to-end on backend +
  cockpit, plus pinned wire shapes for the next phases.
  - **Desktop (`desktop/`):** Tauri 2 layout (`pnpm tauri:dev/build`),
    `src-tauri/` Rust shell with sidecar TODO, `tauri.conf.json` CSP +
    `tauri-plugin-updater` endpoints. Package script copies the v3
    cockpit dist into Tauri's web root before `tauri build`.
  - **Manifest API:** `backend/core/product/{__init__,manifest}.py` +
    `web_extras/routers/product.py` — `GET /api/product/downloads`,
    `/downloads/latest?os=&channel=`, `/version`. Soft-fails to a
    bundled `DEFAULT_MANIFEST`; relative URLs resolved at request
    time via `TARS_DOWNLOAD_BASE_URL`; emits `X-Tars-Contract: 1.0.0`
    + `Cache-Control: public, max-age=60`.
  - **Contracts (`docs/contracts/`):** `MEEET_DOWNLOADS.md` (prose
    contract), `download_manifest.schema.json` (JSON Schema), and
    `L5_PAIRING_DRAFT.md` (full draft of pairing handshake +
    XChaCha20-Poly1305 + X25519 sync envelope).
  - **Landing CTAs:** new `lib/downloads.ts` + `<DownloadStrip />`
    auto-target the visitor's OS via UA detection (macOS Apple
    Silicon vs Intel via `userAgentData`, Windows, Linux, iOS,
    Android); mounted in `<Hero />` beneath the existing CTAs.
  - **Mobile stubs (`mobile/`):** `mobile/README.md`,
    `mobile/ios/TARSCompanion/` (Swift Package skeleton + tests +
    `Package.swift`), `mobile/android/TARSCompanion/`
    (`settings.gradle.kts` + planned layout in README) — paths stable
    in git so L10 implementation slices can drop straight into Xcode
    or Android Studio.
  - **Tests:** +14 (`test_product_downloads.py` × 10,
    `test_product_schema.py` × 4); full suite **284 passed**;
    cockpit `tsc --noEmit` clean.
  - **Tooling:** root `Makefile` with `help / test / test-product /
    cockpit{,-build,-tsc} / desktop-{dev,build} / clean`. No new
    runner deps.

- **2026-04-29 — Phase L8 (Search & observability v2):** unified
  hybrid search + per-thread structured timeline. The cockpit can now
  answer "where did I see that?" in one keystroke.
  - **Backend module.** New `backend/core/search/`:
    - `fts.py` — three SQLite **FTS5** virtual tables behind a single
      stdlib-only API: `chunks_fts` (over `attachment_chunks.text`),
      `messages_fts` (over `messages.content`), `events_fts` (over
      `events.payload` in the meeet store). `unicode61
      remove_diacritics 2` tokeniser → cyrillic + latin friendly.
      Tables are content-less (no schema coupling), backfilled on
      first creation, and synced from the chat / attachment write
      paths via `index_chunk(s)` / `index_message` / `index_event`.
      `sanitise_query()` strips FTS5 syntax (`AND/OR/NOT/NEAR`,
      punctuation, stray quotes) and quotes individual tokens to
      avoid injection.
    - `engine.py` — unified `search(query, scope='all|chunks|
      messages|traces')` dispatching to per-scope helpers
      (`search_chunks`, `search_messages`, `search_traces`).
      Chunk search runs hybrid: FTS5 BM25 + vector cosine fused with
      reciprocal-rank (k=60). Cross-thread by default; `thread_id`
      argument restricts to one thread. All hits carry a structured
      `ref` with thread / message / attachment / trace ids so the
      cockpit can deep-link.
    - `timeline.py` — `get_thread_timeline(thread_id)` joins messages
      + tool calls + attachments + relevant `meeet` events
      (`voice.tts`, `usage.tokens`, `chat.context.retrieved`,
      `council.*`, `policy.*`, `playbook.step.*`) and sorts by `ts`.
  - **L2 retrieval moved off TF-overlap onto FTS5 BM25** (with the
    old scorer kept as a graceful fallback). Same `RetrievedChunk`
    contract — orchestrator side untouched.
  - **HTTP surface.** New `web_extras/routers/search.py`:
    `POST /api/search` (unified), `POST /api/search/chunks`,
    `POST /api/search/messages`, `POST /api/search/traces`, plus
    `GET /api/chat/threads/{id}/timeline`. All endpoints honour the
    cockpit's `x-tars-session-id` / `x-meeet-trace-id` headers and
    cap `top_k` at 50 / `limit` at 1000.
  - **Sync hooks.** `ChatStore.insert_message` mirrors writes into
    `messages_fts`. `attachments.pipeline.ingest()` bulk-indexes new
    chunks into `chunks_fts`; `delete_attachment()` clears them.
    All best-effort — search outage never breaks chat.
  - **Frontend.**
    - `experiments/neural-showcase-v3/src/lib/search.ts` — typed
      client (`unifiedSearch`, `searchChunks`, `searchMessages`,
      `searchTraces`, `fetchThreadTimeline`) plus three React hooks:
      `useDebouncedSearch` (220 ms debounce, abort on stale),
      `useGlobalShortcut` (⌘K / Ctrl-K), `useThreadTimeline`
      (auto-refresh).
    - `<CommandPalette />` (`src/components/CommandPalette.tsx`) —
      ⌘K modal, scope chips (`all` · `files` · `messages` ·
      `traces`), arrow-key navigation, BM25 `<mark>` highlights
      (currently stripped — Claude can light them up). Selecting a
      hit dispatches `tars:open-thread` so `<ChatPane />` jumps to
      the right thread.
    - `<ThreadTimeline />` (`src/components/ThreadTimeline.tsx`) —
      collapsible per-thread observability feed mounted under the
      conversation; shows `attachment / message / tool_call / event`
      rows with timestamp + summary. Auto-refreshes every 6 s while
      open.
    - `<ChatPane />` listens for `tars:open-thread` to flip the
      active thread when the operator picks a search hit.
  - **Tests** (+21 new, 270 total green):
    `tests/test_search_fts.py` (sanitiser, indexing, backfill,
    delete cascade), `tests/test_search_engine.py` (cross-thread,
    scope, cyrillic, vector fallback), `tests/test_search_router.py`
    (HTTP unified / chunks / messages / traces / timeline + scope
    validation + 400 on empty query). Fixed an unrelated voice test
    that was sensitive to event-table fan-in.
  - **Smoke.** `TestClient` end-to-end: 2 threads with KPI + trade
    docs, full SSE chat turn, `/api/search` returns
    `count=2 · {chunks:1, messages:1, traces:0}` for "EMEA blocker
    GDPR" with the highlighted snippet,
    `/api/chat/threads/{a}/timeline` returns 3 chronologically-
    ordered entries (attachment ingest → operator question → TARS
    reply).

- **2026-04-29 — Phase L2 (Attachments + RAG with citations):** end-to-end
  pipeline so operators can drop PDFs / Markdown / CSV / JSON / plain
  text into a thread and have TARS ground answers in those files with
  stable `[chunk_N]` citation markers.
  - **Backend module.** New `backend/core/attachments/`:
    - `extractors.py` — per-mime text extraction. `text/*`, `text/markdown`,
      `application/json` (pretty-print + shape), `text/csv` (markdown
      preview + raw text), `application/pdf` (lazy `pypdf`,
      page-by-page → `## page N`). Image stub keeps bytes for L4 vision
      routing. Best-effort: every error lands in `meta["error"]`
      instead of bubbling out.
    - `chunking.py` — token-aware (~800-token target via 4-char
      heuristic), paragraph-first then sentence-aware splitting with
      configurable overlap. Resolves nearest markdown heading + PDF
      page for every slice.
    - `embeddings.py` — two embedders behind one ABC. `OpenAIEmbedder`
      hits `/v1/embeddings` (`text-embedding-3-small` by default,
      env-pinned model + key from vault). `HashEmbedder` is a fully
      offline deterministic hash-bigram fallback so the pipeline runs
      with zero deps. `detect_embedder()` picks the best one available;
      `TARS_EMBEDDER=openai|hash` pins explicitly.
    - `index.py` — durable store on the same SQLite as chat
      (`~/.tars/chat.sqlite`). Auto-migrates the existing `attachments`
      table with `content_hash`, `status`, `error`, `meta_json`,
      `char_count` columns; adds `attachment_chunks` (text + raw
      float32 vector blob + heading/page/ord). All access wrapped in
      `asyncio.to_thread`; singleton via `get_attachment_store()`.
    - `retrieval.py` — hybrid search: cosine on vectors + tf-style
      keyword overlap, fused with reciprocal rank (k=60). Returns
      `RetrievedChunk` rows with stable `[chunk_N]` citation ids.
      Gracefully handles dim-mismatched vectors (e.g. switched
      embedder model) by skipping them.
    - `pipeline.py` — `ingest()` orchestrates upload → extract →
      chunk → embed → store, dedupes on `(thread_id, content_hash)`,
      caps at 25 MB (env-tunable), writes bytes to
      `~/.tars/attachments/<id>/<safe_filename>`, emits
      `attachment.ingested` + `usage.tokens` (cost = $0.02/1M tokens
      for `text-embedding-3-small`, $0 for hash). Bumps the meeet
      route to `cloud` whenever a cloud embedder runs.
      `delete_attachment()` removes row + chunks + bytes + parent
      directory.
  - **Chat orchestrator integration.**
    `ChatOrchestrator._maybe_retrieve()` runs hybrid retrieval per
    operator turn (skipped for prompts < 6 chars, gracefully empty
    when no chunks). `_compose_system_prompt()` layers a "Reference
    materials" block over the pack's system prompt with each
    chunk labelled `[chunk_N] file.md · heading · pageK`,
    instructing the assistant to cite. New stream event
    `context.retrieved` is emitted before token streaming so the
    cockpit can render sources live; `message.completed` carries a
    final `sources: [...]` payload, also persisted in the assistant
    message's `extra` so "Sources" footers survive reload.
  - **HTTP surface (under `/api/chat`).**
    `POST /threads/{id}/attachments` (multipart upload),
    `GET /threads/{id}/attachments`,
    `GET /attachments/{id}` (record + chunk previews),
    `GET /attachments/{id}/download`,
    `GET /attachments/{id}/extracted`,
    `DELETE /attachments/{id}`,
    `POST /threads/{id}/retrieve` (manual top-K query).
  - **Frontend (`experiments/neural-showcase-v3/`).**
    - New `lib/attachments.ts` — typed client + `useThreadAttachments`
      hook (list / upload / progress / remove / refresh) + `useDropZone`
      helper (drag-depth-counted, no flicker on inner-element
      transitions).
    - `<ChatPane />` enhancements: thread-scoped chip strip with
      filename + KB + delete; "+ file" composer button + native file
      input; full-pane drag overlay ("drop to attach · pdf · md · txt
      · json · csv · up to 25 MB"); error toast row.
    - `<MessageBubble />` grew a collapsible **Sources** footer:
      `[chunk_1] kpi.md · heading · pK` with optional inline preview
      for live retrieval (the persisted version reads from
      `message.extra.sources`).
    - `useChatThread` reducer now handles `context.retrieved` and
      threads `RetrievedChunkRef[]` through `turn.retrieved` so the
      footer can render before the LLM finishes streaming.
  - **Tests (+39 new):**
    - `test_attachments_extractors.py` (8) — sniff, plaintext line
      endings, JSON pretty + invalid fallback, CSV markdown preview,
      image stub, unknown mime, broken PDF.
    - `test_attachments_chunking.py` (6) — empty input, single-slice
      short docs, paragraph splitting with overlap, heading + page
      resolution, dedup.
    - `test_attachments_embeddings.py` (7) — hash always-on,
      normalisation, similarity, empty handling, env pin, fallback,
      OpenAI mocked endpoint.
    - `test_attachments_pipeline.py` (7) — record + chunk persist,
      dedupe, oversize, empty, retrieval ranking, empty-thread
      retrieval, full delete.
    - `test_attachments_router.py` (8) — multipart upload + dedupe,
      404 unknown thread, list ordering, describe with previews,
      extracted text, retrieve top-K, retrieve query required,
      delete.
    - `test_chat_with_rag.py` (3) — orchestrator emits
      `context.retrieved`, persists `sources` on the assistant message,
      skips retrieval for empty thread / short query.
  - **Smoke proof.** Live HTTP run on `:8767`: created thread,
    uploaded `kpi.md`, retrieved chunk_1 with score 0.0328 from both
    semantic and keyword pools, then `POST /messages` SSE streamed
    `message.started → context.retrieved → token… → usage → message.completed`
    with `sources=[{citation_id: "chunk_1", filename: "kpi.md", …}]`,
    matching the cockpit's expected wire format.
  - **Doc surface.** `docs/PHASE_L_ROADMAP.md` §L2 marked shipped,
    `docs/IDEAS.md` updated with post-L2 follow-ups (cross-thread
    search, BM25-via-FTS5, image vision routing, zip walking,
    streaming ingestion progress).

- **2026-04-29 — Phase L4.1 (Voice persona layer — TTS + mic dictation):**
  - **Backend.** New module `backend/core/voice/`:
    - `personas.py` — registry of six characters (Jarvis · British
      butler, Stark · Iron Man, HAL 9000, GLaDOS, Interstellar TARS,
      Operator default) each with per-provider mappings:
      ElevenLabs voice id (public starter library), OpenAI voice +
      stylistic `instructions` for `gpt-4o-mini-tts`, macOS `say`
      voice + rate. Env-overridable
      (`TARS_PERSONA_<ID>_ELEVENLABS_ID`, `..._OPENAI_VOICE`,
      `..._MAC_SAY_VOICE`). Plugin-extensible via
      `register_persona`.
    - `engines.py` — three providers: `ElevenLabsEngine` (best
      character voices, mp3), `OpenAITTSEngine` (very natural,
      `gpt-4o-mini-tts` honours persona instructions, mp3),
      `MacSayEngine` (offline, WAV via `say -o file.wav
      --file-format=WAVE --data-format=LEI16@22050`). Smart fallback
      picks accent-appropriate substitute when the preferred mac
      voice isn't installed (Daniel for British, Alex for American,
      etc.). All engines wrap the network/process call in
      `asyncio.to_thread`, never raise on transport errors —
      they return `None` so `synthesize()` falls through.
    - `synthesis.py` — orchestrator: pin via `provider="…"` arg or
      `TARS_VOICE_PROVIDER` env, else walks
      `elevenlabs → openai → mac_say`. Emits `voice.tts` and
      `usage.tokens` events (model `voice/<provider>`, chars as
      tokens, char-based USD pricing — defaults: ElevenLabs $0.18 /
      1k chars, OpenAI $12 / 1M chars, mac say $0; all overridable
      via `TARS_VOICE_PRICE_<PROVIDER>`). Cloud providers bump the
      meeet route to `cloud` so the cost ledger reflects it.
  - **HTTP.** New `web_extras/routers/voice.py` — `GET
    /api/voice/personas` (full roster), `GET /api/voice/health`
    (per-engine availability + preferred order), `POST
    /api/voice/speak` (returns audio bytes, headers carry
    `x-tars-voice-provider/voice-id/bytes/duration-ms`). Mounted
    in `web_extras/app.py`.
  - **Frontend.** New `lib/voice.ts` — typed client + four hooks:
    `useVoicePlayback` (single shared `<audio>`, persona / provider
    / autoplay / mute persisted in `localStorage`),
    `usePersonas`, `useVoiceHealth`, and `useMicTranscription`
    (browser Web Speech API — zero deps, degrades cleanly where
    unsupported). `<ChatPane />` grew a `<VoiceControls />` row
    (persona + provider picker, autoplay toggle, mute, "via …"
    last-provider indicator), a per-assistant-message
    `▶ speak` button, autoplay-on-new-reply, and a 🎙 mic button
    in the composer that mirrors transcript into the textarea.
  - **Tests.** 28 new pytest cases:
    - `test_voice_personas.py` (8) — roster shape, provider matrix,
      env override, default fallback, registry extension.
    - `test_voice_engines.py` (6) — accent-aware mac say fallback,
      duration heuristic.
    - `test_voice_synthesis.py` (8) — provider order, fallback on
      `None`, fallback on exception, env pin, arg pin, all-fail
      raises, `voice.tts` + `usage.tokens` events emitted.
    - `test_voice_router.py` (6) — personas/health/speak shapes,
      503 when no engine, 400 on empty / oversized text.
    - **Total: 210 passing** (182 → 210).
  - **Smoke proof.** Live curl against the running server: Jarvis
    rendered on macOS `say` as 131 KB WAV via Daniel (British
    male); Stark fell back from "Aaron" (not installed) to "Tom"
    via the new accent-aware fallback. Cost ledger shows
    `voice/mac_say` row alongside chat models.
  - **License note.** All persona names map to *generic* preset
    voices (no Disney / Marvel / Valve / Paramount asset is
    reused). The character names are inspirational; an operator
    that wants a tighter likeness can drop in a custom ElevenLabs
    voice id via env.

- **2026-04-29 — Phase L1 (Conversation Layer):**
  - **Plan first.** `docs/PHASE_L_ROADMAP.md` is now the canonical
    spec for Phase L (chat, attachments, code exec, voice, encrypted
    sync, planner, marketplace, search, Tauri desktop, iOS/Android companions).
    `IDEAS.md` and this file point at it as the active roadmap.
  - **Backend chat layer.** New module `backend/core/chat/`:
    `models.py` (Thread / Message / ToolCall / Attachment / StreamEvent
    + AttachmentRef), `store.py` (SQLite WAL at `~/.tars/chat.sqlite`,
    disable with `TARS_CHAT_STORE=disabled`, override path with
    `TARS_CHAT_DB_PATH`, full async API mirroring the meeet store),
    `voices.py` (`ChatVoice` ABC + `LocalChatVoice` /
    `AnthropicChatVoice` / `OpenAIChatVoice` streaming via stdlib
    `urllib`, all wrapped in `asyncio.Queue`, no httpx),
    `orchestrator.py` (ties chat to council + policy + meeet — opens
    `trace_scope(session=…, route=edge)`, persists operator/assistant
    rows, parses `<tool name="slug.action_id">{...}</tool>` sentinels
    on the fly, runs them through `PolicyGate`, emits per-turn
    `usage.tokens` events so the cost ledger automatically picks
    chat costs up).
  - **HTTP surface.** New `web_extras/routers/chat.py` mounts under
    `/api/chat`: `POST/GET /threads`, `GET/PATCH/DELETE
    /threads/{id}`, `GET/POST /threads/{id}/messages`. The POST is
    a real SSE stream (`text/event-stream`) emitting
    `message.started`, `token`, `tool_call.{proposed,queued,allowed,
    completed,failed}`, `usage`, `message.completed`, `stream.closed`.
    Honours `x-tars-session-id` and `x-tars-policy-mode` headers.
  - **Frontend.** New `lib/chat.ts` (typed client + `useChatThread`
    React hook with optimistic operator bubble + token-by-token
    assistant reducer + tool-call card state) and `<ChatPane />`
    component (thread sidebar + message stream + composer with
    `⌘↵ to send`, inline tool-call cards). Mounted on `/cockpit` as
    the primary panel; existing JSON invocation grid stays for
    operators that want to drive packs raw.
  - **Tests:** 23 new pytest cases — `test_chat_models.py` (models +
    store CRUD, archive flow, attachment table), `test_chat_orchest
    rator.py` (local stream, persisted rows, error path, scripted
    tool-call routing through both autopilot and confirm modes,
    sentinel parser including partial-block hold-back),
    `test_chat_router.py` (CRUD over the HTTP API, SSE wire shape,
    operator/tars persistence after stream drain, empty-text 400).
    **Total: 182 passing** (was 159).
  - **Smoke proof.** Live SSE round-trip on a clean port creates a
    thread, streams the local-voice reply, persists both messages,
    and surfaces in `/api/usage?session_id=…` under the
    `tars-local-chat-v1` model bucket on the `edge` route.

- **2026-04-29 — Phase K (operator-grade observability + extensibility):**
  - **Phase K1 — route + session_id everywhere.** Added
    `session_scope`, `set_route`, `current_route`, `current_session`
    to `meeet.tracing`. `TARSEvent` and the durable store carry
    optional `session_id` + `route`; SQLite store auto-migrates with
    `ALTER TABLE` between table creation and index creation. Domain
    router accepts `x-tars-session-id` and stamps every action scope
    with `route="edge"` by default; LLM voices bump it to `cloud` on
    a successful call.
  - **Phase K2 — cost ledger.** `backend/core/usage/ledger.py` with a
    configurable `PriceTable` (defaults for sonnet, haiku, opus,
    gpt-4o, gpt-4o-mini, gpt-4.1; `TARS_PRICE_OVERRIDES_JSON` for
    overrides). Council orchestrator emits per-voice `usage.tokens`
    events with `tokens_in/out`, `latency_ms`, and `cost_usd`; the
    `sampler.decision` event now also carries an aggregate `cost_usd`.
  - **Phase K3 — `/api/usage` rollup.** `web_extras/routers/usage.py`
    derives buckets (`by_model`, `by_route`, `by_session`) from the
    meeet store. Two read paths: rollup (`GET /api/usage`) and raw
    lines (`GET /api/usage/lines`). Frontend ships `useUsageRollup`
    + `<UsageStrip />` mounted on `/cockpit`.
  - **Phase K4 — composite packs + manifest.**
    `backend/core/domains/composite.py` + `packs/composites.py`
    register `research_lab` (science + business) and `ops_room`
    (traders + mlm). Composite actions surface as
    `<sub_slug>__<id>`, destructive flags + auth keys propagate.
    New endpoint `GET /api/domains/manifest` for cache-friendly
    install/discovery.
  - **Phase K5 — replay CLI + contract test.** New
    `python -m backend.core.meeet.replay_cli` with
    `--stats / --export / --limit / --since / --kind / --session-id`.
    `tests/test_meeet_contract.py` pins the wire shape and the
    session/route round-trip through replay.
  - **Phase K6 — SMTP outbound for `business.draft_email`.**
    `backend/core/domains/packs/business/smtp.py` reads SMTP_*
    config from the vault (env or Keychain), supports STARTTLS on
    587 and implicit TLS on 465. With `send=true` and SMTP
    configured (and the policy gate confirmed), `draft_email`
    actually delivers; otherwise it returns the draft + a
    `delivery.status` hint. Pack now declares `SMTP_HOST/USER/
    PASSWORD/FROM` in `auth_vault_keys()`.
  - **Frontend (Cursor lane).** `lib/usage.ts` (rollup hook),
    `lib/session.ts` (per-tab `ses_<id>` via `sessionStorage`),
    `<UsageStrip />` with per-route + per-model tables. The
    Cockpit invocation now stamps every call with the session id.
    `getDomainManifest()` typed client wraps `/api/domains/manifest`.
    `composite` + `composed_of` flags exposed on `DomainPack`.
  - **Tests:** total now **159 passing** (was 122 — added 37 across
    contract, ledger, composite, manifest, smtp, replay-cli).

- **2026-04-29 — Adapters + per-pack auth + cockpit chunking:**
  `DomainPack.auth_vault_keys()` + `status_for_keys()` feeds
  `GET /api/domains/<slug>["auth"]`. `traders.news_feed` honours
  `TRADERS_NEWS_RSS_URL` / `rss_url` (RSS/Atom parse + tone heuristics)
  before falling back to JSON. `science/summarize_paper` appends
  `openalex` when the DOI bridge resolves. `business.log_deal` POSTs
  to HubSpot then Pipedrive when keys exist. New playbook
  `mlm.recruitment_round`; `retention_round` uses `threshold_days`.
  Frontend: `React.lazy` splits Landing vs Cockpit; Vite
  `manualChunks` for react / r3f / three; OperatorStrip shows recent
  `sampler.decision` rows.

- **Phase F-J — second functional batch (LLM voice → cockpit hooks):**
  - **Phase F — Real LLM voice + Keychain vault.** New
    `backend/core/vault/` reads env first, then `security
    find-generic-password -a tars -s <key>`. New
    `backend/core/council/llm.py` with `AnthropicVoice` and
    `OpenAIVoice` (stdlib `urllib`); auto-detected by the orchestrator
    via `detect_llm_voice()`. Voices that can't reach their provider
    return `stance='unavailable'` and are filtered from votes.
    Endpoint `GET /api/vault/status` lists sources for known keys
    (env / keychain / missing) — values are never echoed.
  - **Phase G — Parallel playbook steps.** `PlaybookStep.parallel`
    flag groups consecutive parallel-flagged steps; each group runs
    via `asyncio.gather`. Step results land in declared order.
    `traders.morning_check` runs `news` + `portfolio` concurrently
    (≈ 50 % wall-clock saving).
  - **Phase H — SQLite MLM downline DB.**
    `backend/core/domains/packs/mlm/db.py`. Self-seeds from
    `data/mlm_network.csv` on first read. New destructive actions
    `mlm.add_member` (sponsor must exist) and `mlm.log_activity`
    (timestamps + volume delta) are gated through the policy queue.
    `downline_snapshot` and `retention_alert` now report
    `source: "sqlite"|"csv"`.
  - **Phase I — Background replay loop + meeet health.**
    `web_extras/app.py` starts a periodic task (`MEEET_REPLAY_INTERVAL_S`,
    default 60s) that flushes pending events. `MeeetClient.last_replay`
    is cached and exposed by `GET /api/meeet/health` together with
    store stats and bridge config.
  - **Phase J — Cockpit clients + OperatorStrip.** New typed
    modules under `experiments/neural-showcase-v3/src/lib/`:
    `policy.ts`, `council.ts`, `playbooks.ts`, `meeet.ts`,
    `vault.ts`. New `<OperatorStrip />` mounted on `/cockpit` with
    a pending-confirmations panel (confirm/cancel inline), a
    playbook runner with mode selector, and a bridge panel
    (meeet store stats + last-replay age, vault sources, on-demand
    council deliberation). Visual polish stays Claude's job.
- **Phase K — Tier 1 functional roadmap (council / policy / persistence):**
  - **Awareness wiring (Phase A).** `AwarenessSource.fetcher` contract
    + `GET /api/domains/<slug>/awareness/<id>/snapshot`. Live fetchers
    for calendar, hubspot deals, kpi sheet, traders binance/news/portfolio
    (NAV-enriched), mlm downline, arxiv, local-papers, datasets-dir.
    `business.daily_brief` now surfaces `calendar_today[]`.
  - **Durable event log (Phase B).** `backend/core/meeet/store.py`
    SQLite WAL DB. Every event flows through the store before any
    network attempt; offline events sit at `pushed=0` and
    `replay_unpushed()` flushes them. New endpoints:
    `GET /api/meeet/stats`, `GET /api/meeet/events`,
    `POST /api/meeet/replay`.
  - **Council orchestrator (Phase C).** Two voices
    (`tars-local-rules-v1`, `tars-mock-cloud-v1`), modes
    `single | dual_vote | n_vote`. Emits
    `council.deliberation.{started,completed}` and `sampler.decision`
    on every call. Wired into `traders.summarize_market` and
    `business.daily_brief`. New endpoint:
    `POST /api/council/deliberate`.
  - **Policy gate (Phase D).** `ActionSpec.destructive` flag;
    destructive actions (`traders.place_alert`, `business.draft_email`,
    `business.log_deal`, `mlm.generate_post`) flow through the gate.
    Modes: `autopilot | confirm | dry_run`, default `confirm`. Token
    confirmations persisted in the same SQLite DB. New endpoints:
    `GET /api/policy/{pending,recent}`,
    `POST /api/policy/{confirm,cancel}/{token}`,
    `POST /api/policy/expire`. Header `x-tars-policy-mode` switches
    mode per request.
  - **Playbook runner (Phase E).** JSON playbooks under
    `playbooks/<pack>/<name>.json`. Steps support
    `<slug>.<action_id>` and `<slug>.awareness.<source_id>.snapshot`,
    `${steps.<id>...}` and `${context.<key>}` templating, `when`
    clauses, `store_as`, `on_error`. Sample playbooks shipped:
    `traders.morning_check`, `business.morning_brief`,
    `mlm.retention_round`. New endpoints:
    `GET /api/playbooks`, `POST /api/playbooks/{id}/run`,
    `POST /api/playbooks/_reload`.
- **Phase J — Real adapters + SSE awareness:**
  - `business.kpi_snapshot` reads `data/business_kpi.json`.
  - `business.daily_brief` composes deltas + next steps from KPI + deals
    JSONs (deterministic; council can drop in without surface change).
  - `mlm.downline_snapshot` reads `data/mlm_network.csv`, computes
    depth/active/dormant/ranks/by_depth/volume.
  - `mlm.retention_alert` filters by `threshold_days`.
  - `mlm.score_recruit`, `mlm.generate_post` upgraded to deterministic
    heuristics with model labels and hints.
  - `science.summarize_paper` accepts arxiv id / `arxiv:<id>` / full URL,
    fetches via the Atom API, returns title/authors/tldr/abstract.
  - `traders.summarize_market` aggregates a basket via DexScreener,
    surfaces bias (risk-on/off/neutral) and dispersion contradictions.
  - `/api/awareness/stream` SSE producer with `hello`/`pulse`/
    `heartbeat`/`bye` frames + `<AwarenessTicker/>` consumer in Cockpit.
  - Smoke verified end-to-end against `:9911`. 34 pytest tests passing.
- **Phase I — v3 cinematic everything-at-once:**
  - Router (`/`, `/cockpit`) + page transitions.
  - Cockpit page: domain picker → action picker → JSON args → invoke
    → response viewer + live trace timeline (real `traders.fetch_quote`
    smoke verified, e.g. WBTC/H2O at $76k with trace_id propagated).
  - Sound layer (`lib/sound.ts`) + nav `<SoundToggle/>`.
  - Footer rewrite — kinetic OPEN COCKPIT with liquid-metal mask.
  - Domains rewritten as orbital R3F scene with hover-expand panels.
  - Layers rewritten as isometric stack with parallax.
  - Steps with kinetic massive numerals + scroll-progress line.
- **Phase H — `ui-ux-pro-max-skill` install + design system generated.**
- **Phase G — v3 cinematic hero rebuild** (multi-mesh GLSL Fresnel,
  HUD plates, KineticText, Marquee, SectionDivider).
- Earlier phases: Phase A (Iron-Man core), Phase B (domain packs
  scaffold), Phase C (sync infra), Phase D (tone-down), Phase E
  (meeet.world bridge), Phase F (Jarvis → TARS rename).

## Pending — split between agents

### Owned by **Claude Code (design)**

1. **GLB asset.** Source a CC0 brain or stylised core mesh and drop
   into `experiments/neural-showcase-v2/public/models/brain.glb`.
   Procedural stays as the offline-safe fallback.
2. **Polish v3 micro-interactions.** Re-run the
   `ui-ux-pro-max-skill` for `--page cockpit`, `--page hero` and
   apply any deltas. Particularly the Cockpit page deserves more
   refined empty / loading / error states.
3. **Page-transition richness.** The blur-slide is already in
   `App.tsx`; consider a shared overlay sweep on route change.
4. **Copy pass on Landing.** Tighten Hero subhead, Domains bullets,
   Steps cues. Match `MASTER.md` voice (operator-grade, no fluff).
5. **Brand dressing.** Favicon + OG image generated from the v3
   palette (gold accent + cyan hud on OLED).
6. **Sound design polish.** Replace the 3-osc hum with a richer
   ambient bed (4-5 tones, slow LFO), and add explicit press
   confirmation cues. Respect `prefers-reduced-motion`. Already
   muted by default.
7. **Design rev for `<AwarenessTicker/>`.** Currently a 3-pane card
   strip — consider a single ticker bar / chart variant.
8. **`<ChatPane />` polish (Phase L1 + L2).** Functional surface ships
   under `experiments/neural-showcase-v3/src/components/ChatPane.tsx`
   and is mounted on `/cockpit`. Motion, copy, hover, focus, mobile
   layout and tool-call card visual treatment are open. Ledger /
   policy / sessions / voice / **attachment chips + sources footer**
   are wired — touch only the chrome.
9. **Attachment + sources visual treatment (Phase L2).** Drag-and-drop
   overlay (`drop to attach · pdf · md · txt · json · csv`),
   `AttachmentChipStrip`, and the collapsible sources footer in
   `MessageBubble` are all functional (cite previews on live
   retrieval, persisted citations on reload). Recommended polish:
   richer chip motion on upload progress (`queued → uploading →
   ingesting → ready`), inline mini icons by mime, and a hover state
   that surfaces the chunk preview as a floating card.
10. **Search palette + timeline visual treatment (Phase L8).**
    `<CommandPalette />` (`src/components/CommandPalette.tsx`) is
    fully wired — ⌘K toggles, scope chips, BM25 highlights stripped
    for now. Polish open: render `<mark>` tags as gold-on-bg pulses,
    add a "recent threads" / "frequent files" empty state, blur-slide
    open animation, and per-kind icons (file / chat-bubble / trace).
    `<ThreadTimeline />` (`src/components/ThreadTimeline.tsx`) is a
    collapsible feed mounted under the conversation; consider a
    timeline-spine motif (vertical glyph rail), grouping by hour, and
    soft fade on auto-refresh insert. Cytoscape trace-graph view is
    explicitly deferred for a future visual pass.
11. **Landing download CTAs (Phase L9 brand pass).**
    `<DownloadStrip />` (`src/components/DownloadStrip.tsx`) is mounted
    in `<Hero />` and auto-targets the visitor's OS via the public
    manifest — but the visual treatment is deliberately plain. Polish
    open: OS-glyph icons (Apple, Windows, Tux, iOS, Android) with
    micro-motion on hover, version pill that pulses on a fresh
    release, "verified · sha256 ✓" affordance once a checksum is in
    the manifest, mobile-friendly stacked layout. A second
    `<DownloadStrip variant="footer" />` instance in the page footer
    is a free win for landing-page conversion.
12. **meeet.world embed (`docs/contracts/MEEET_DOWNLOADS.md`).**
    The marketing site at `meeet.world` should consume
    `GET /api/product/downloads` with the same shape — render
    matching CTAs, OG cards, deep-link from `meeet.world/tars` into
    the cockpit, and respect the contract version pin (1.0.0).
    Coordinate any contract bump with a Cursor PR — never silently
    invent fields.
13. **Pairing flow visual (Phase L5 draft).**
    `docs/contracts/L5_PAIRING_DRAFT.md` describes the QR + envelope
    handshake. Before code lands, sketch the desktop UI (host
    fingerprint pulse, accept-token confirm sheet) and the matching
    iOS / Android scan UX so Cursor can wire components against a
    pre-approved layout.

### Owned by **Cursor agent (functional)**

Tier-1 (Phase K), Phase F-J, the 2026-04-29 adapter batch, and the
fresh Phase K observability/extensibility batch are **shipped**.

**Phase L (Claude-tier elevation)** is now the active roadmap —
see `docs/PHASE_L_ROADMAP.md` for full functional descriptions,
contracts, tests, and acceptance criteria per sub-phase. Sequence:

1. L1 — Conversation Layer ✅ shipped
2. L4.1 — Voice persona TTS + Web Speech mic ✅ shipped
3. L2 — Attachments & context graph (RAG with citations) ✅ shipped
4. L8 — Search & observability v2 (paired with L2) ✅ shipped (this batch)
5. **L9 — Tauri desktop shell (macOS + Windows).** ✅ scaffolded
   2026-04-29 (`desktop/`); ✅ public download manifest API live
   (`/api/product/downloads`); ✅ release publishing CLI live
   (`python -m backend.core.product.publish`); 🟡 next slice =
   pyoxidizer sidecar, icons + branded assets, real signing pipeline,
   first signed `.dmg`/`.exe` artifacts uploaded to the site.

   **Public showcase (investor demo):**
   `.github/workflows/cockpit-github-pages.yml` builds
   `experiments/neural-showcase-v3` with `/REPO/` as `base`/`basename`
   (repo name substituted in CI); one-time enable **Pages → GitHub Actions**
   in repo settings. For a disposable public URL locally, run
   `scripts/preview-demo-tunnel.sh` (install `cloudflared` for the
   tunnel).
6. L5 — Encrypted sync via meeet.world (bumps contract → 1.1.0). 🟡
   pairing endpoints shipped 2026-04-29 with **mock crypto**; pin tests
   ride in `tests/test_pairing_contract.py`. Next slice = real
   XChaCha20-Poly1305 + X25519 envelope, sync fields on meeet events,
   `pair.linked` recovery seed UI.
7. L4 — Voice mode (full duplex: faster-whisper STT relay + iOS native loop)
8. **L10 — Mobile companions:** native **iOS** (Swift/SwiftUI) + **Android** (Kotlin/Jetpack Compose); shared HTTP/SSE contract with desktop **L9**; pairing + E2E sync via **L5** (`PHASE_L_ROADMAP` § L10)
9. L3 — Code execution & artifacts
10. L6 — Planner / agent loop
11. L7 — Skill marketplace v1

Smaller functional items still pending in parallel:

1. **meeet contract evolution.** Align event kinds with the
   `meeet.world` ingest contract when it lands. Keep
   `contract_version` pin updated; the durable buffer + the new
   `tests/test_meeet_contract.py` make schema evolution cheap
   (replay + transform).
2. **Cockpit polish (Claude-owned).** `<OperatorStrip />` and
   `<UsageStrip />` are functionally complete (pending queue,
   playbooks, bridges, vault, council, sampler.decision poll, plus
   route/model/session cost tables) — both still need visual
   integration with the main cockpit grid.
3. **Voice gallery UI.** Surface per-voice latency + token usage +
   model id in a dedicated panel (Proposal fields already carry the
   data; `usage.tokens` events expose it durably).
4. **CRM hardening.** HubSpot/Pipedrive `log_deal` uses minimal
   properties; production portals may require pipeline IDs / stage
   enums — evolve when real Hub IDs are supplied.
5. ~~**OLD arXiv ids** (`cs.AI/010203`) skip OpenAlex DOI
   enrichment — Crossref fallback could layer in later.~~ **shipped**
   (2026-05-01) — `backend/core/domains/packs/science/crossref.py`
   resolves legacy ids (`cs/9901001`, `cs.AI/0301001`,
   `math.AT/0701035`) via Crossref's bibliographic search with a
   ≥0.4 Jaccard title gate. `summarize_paper` returns a `crossref`
   block + `sources=["arxiv","crossref"]` only when the candidate
   match is plausible; new-style ids never hit Crossref. Pinned by
   `tests/test_science_crossref_fallback.py` (11 cases).
6. **OAuth / JMAP outbound.** SMTP covers the local-first path for
   `draft_email`. ✅ partial (2026-05-01) — SASL **XOAUTH2** wired
   into `business.send_email` so Gmail / Office365 / Fastmail OAuth2
   bearer tokens (or app passwords) authenticate cleanly via
   `smtplib.SMTP.auth("XOAUTH2", ...)`. Provider shorthand
   `SMTP_PROVIDER=gmail|office365|outlook|fastmail|yahoo|zoho`
   pre-fills host/port/TLS so a Gmail setup is two env vars:
   `SMTP_PROVIDER=gmail` + `SMTP_USER=…` + `SMTP_OAUTH_TOKEN=…`.
   **Refresh-token flow shipped 2026-05-01:**
   `backend/core/domains/packs/business/oauth.py` exchanges
   `SMTP_OAUTH_REFRESH_TOKEN` + `SMTP_OAUTH_CLIENT_ID`
   (+ optional `SMTP_OAUTH_CLIENT_SECRET` / `..._TOKEN_URL` /
   `..._TENANT` / `..._SCOPE`) for a fresh access token via the
   provider's OAuth2 token endpoint, caches it in-process, and
   refreshes 5 minutes before expiry. Manual `SMTP_OAUTH_TOKEN`
   still wins. Refresh failure degrades to password fallback
   without crashing. Provider shorthand
   `gmail` / `office365` / `outlook` resolves the token URL
   (Microsoft uses the configurable tenant). `SmtpResult.to_dict`
   now surfaces `oauth_token_source` (`manual` / `refresh` /
   `cache` / `none`) + `oauth_expires_in` so the cockpit can show
   token freshness. `tests/test_business_smtp_oauth_refresh.py`
   (18 cases) pin parser, cache, refresh, and degradation paths.
   **Still pending:** initial consent / authorization-code flow
   (operator-side once-per-account dance) and JMAP
   (Fastmail-native protocol) — both require operator-side
   infrastructure (consent UI, persistent token store).
7. ~~**Composite playbooks.** Composite domain packs are live; the
   playbook runner still scopes to a single pack — extend so a
   playbook in `playbooks/research_lab/...` can call
   `business__log_deal` etc. directly.~~ — Already shipped (audited
   2026-05-01): the runner's `slug.action_id` split + `get_pack`
   lookup is pack-agnostic;
   `tests/test_composite_playbooks.py::test_runner_dispatches_atomic_action_from_composite_dir`
   pins the cross-pack call from a composite-dir playbook.
8. ~~**Vector + BM25 blend for messages.**~~ **shipped** (2026-05-01)
   — `messages` carries `embedding_model/dim/blob`,
   `embed_pending_messages` + `POST /api/search/embed-messages`
   batch-embed pending rows, and `search_messages` now RRF-fuses BM25
   with cosine the same way chunk search does. Both `rank_keyword`
   and `rank_semantic` surface on every hit.
   `tests/test_chat_message_embeddings.py` (13 cases) pins the path.
   Periodic backfill via `_message_embed_loop` in `_lifespan` shipped
   in the same day (PR #43) — opt-in via
   `TARS_MESSAGE_EMBED_INTERVAL_S` (default 0 = off; clamps negatives
   and garbage); `TARS_MESSAGE_EMBED_LIMIT` (default 100, capped at
   1000) tunes the pending-scan window. Loop is "self-healing":
   logs `debug` on embedder-unavailable and keeps ticking until the
   upstream comes back. `tests/test_message_embed_loop.py` (8 cases)
   pins the wiring.
9. ~~**Saved searches.**~~ **shipped** (2026-05-01) — new
   `saved_searches` table in `~/.tars/chat.sqlite` (cols `id label
   query scope filters_json pinned created_at updated_at
   last_run_at`, composite index on `(pinned DESC, updated_at DESC)`).
   Full CRUD on `/api/search/saved` (`GET` list, `POST` create,
   `GET/{id}`, `PATCH/{id}`, `DELETE/{id}`) plus
   `POST /api/search/saved/{id}/run` that executes via the existing
   search engine and stamps `last_run_at`. Filters honoured per
   scope (`thread_id`, `role`, `kind`, `trace_id`).
   `tests/test_saved_searches.py` (16 cases) pins store CRUD + HTTP +
   run shortcut. Cockpit "pinned rail" UI is the Claude-lane
   follow-up.
10. ~~**Scoped operator filters DSL.**~~ **shipped** (2026-05-01) —
    `backend/core/search/filters.py` parses `role:`, `pack:`,
    `thread:`, `trace:`, `kind:`, `since:`, `until:`, `mime:`
    (positive + negation) directly out of the search query; time
    bounds accept relative (`7d`, `24h`, `45m`, `2w`) and ISO
    date / timestamp. `search` / `search_messages` / `search_traces`
    honour every token (messages get `pack`/`since`/`until` JOINs,
    traces get `since`/`until` JOINs); `search_chunks` strips tokens
    and honours `thread:` + (since 2026-05-01 follow-up)
    `pack:` / `mime:` / `since:` / `until:` filters via JOINs to
    `threads` and `attachments` (same DB — single SQLite file).
    `mime:` accepts literal (`application/pdf`) or wildcard prefix
    (`image/*` → LIKE `image/%`).
    `SearchResult` carries `filters` + `cleaned_query` so the cockpit
    can show what matched and what was stripped.
    `tests/test_search_filters.py` (29 cases) pin parser + engine +
    HTTP wiring. Saved-search bodies inherit the DSL automatically.
13. ~~**Cross-thread Cmd+J jump.**~~ **backend shipped** (2026-05-01) —
    `backend/core/search/jump.py` is a navigation-focused fuzzy
    picker (distinct from the content-search ⌘K palette). Sources:
    threads, attachments, saved searches, packs, playbooks. Scoring
    is intentionally cheap (`fuzzy_score`: exact / prefix / substring
    / token-prefix / subsequence with a coverage-based subseq score).
    Empty query returns "recent first" candidates so the palette is
    useful before typing. `POST /api/search/jump` body
    `{q?, query?, limit?, kinds?}` — clamped to 100 hits, unknown
    kinds dropped silently. `tests/test_jump_picker.py` (23 cases).
    Cockpit ⌘J palette UI is the Claude-lane follow-up.
20. ~~**Re-embed attachments on demand.**~~ **shipped** (2026-05-01) —
    `backend/core/attachments/reembed.py` is the promote-on-demand
    path for chunks stuck on a legacy embedder. Storage primitives
    landed on `AttachmentStore`: `update_chunk_embedding` (single-
    row in-place rewrite) and `list_chunks_by_model` (find by
    current model, optional thread scope). Three orchestrators:
    `reembed_chunks` (base helper, skips blank text and
    same-model rows unless `force=True`, isolates per-batch
    failures), `reembed_attachment` (per-id), `reembed_by_model`
    (promote hash → openai workflow, optional `thread_id` /
    `limit`). HTTP: `POST /api/chat/attachments/{id}/reembed` and
    `POST /api/chat/attachments/reembed-by-model`. Both return
    structured stats with `ok` / `embedded` / `skipped_blank` /
    `skipped_same` / `failed` / `batches` / `model` / `dim`.
    `tests/test_attachment_reembed.py` (18 cases) pin storage,
    orchestrator, and HTTP. Designed for the operator who installs
    TARS offline, ingests months of files on the hash embedder,
    then configures `OPENAI_API_KEY` and wants the back-catalog
    to catch up.
32. ~~**Recovery seed verification challenge (3-of-24).**~~ **shipped**
    (2026-05-01) — closes the "Recovery seed verification
    policy" idea from IDEAS' Pairing & sync section. New
    pure-stdlib state machine in
    `backend/core/crypto/seed_challenge.py` with
    `SeedChallenge` + `mint_challenge()` +
    `verify_challenge()` + `SeedChallengeStore` (thread-safe
    in-memory dict with expiry-aware reads). Asks the
    operator to confirm 3 random word **positions** out of
    24 instead of retyping the entire phrase — balances
    friction against meaningful proof-of-knowledge. `count`
    clamped `[1, 8]`, `ttl_s` clamped `[30, 1800]` (default
    5 min), `max_attempts` clamped `[1, 10]`. Wrong answers
    decrement attempts; exhausted attempts mark the
    challenge `exhausted`; expired pending challenges flip
    to `expired`. Case + whitespace insensitive matching.
    `to_public_dict()` strips `expected_words` so the
    cockpit can never leak them. New HTTP routes
    `POST /api/recovery/challenge/start` (mint),
    `POST /api/recovery/challenge/verify` (404 unknown id,
    410 expired, 200 + `ok=false` on wrong answers),
    `GET /api/recovery/challenge/{id}` (public-safe state
    for resume-after-refresh). All three emit
    `recovery.challenge.{started, passed, failed, expired,
    exhausted}` meeet events with the fingerprint shape so
    the timeline UI can render the challenge cycle on the
    same gold-pill lane as existing `recovery.shown` /
    `recovery.verified`. Pinned by
    `tests/test_seed_challenge.py` (30 cases). Follow-up
    (deferred): gate the destructive "rotate identity"
    flow on a fresh `recovery.challenge.passed` event for
    the same fingerprint.

31. ~~**Streaming ingestion progress (SSE).**~~ **shipped**
    (2026-05-01) — closes the "streaming ingestion progress"
    idea from IDEAS' attachments section. The ingest pipeline
    now accepts a `progress: ProgressCallback | None` kwarg
    that fires once per phase (`started` → `extracted` →
    `chunked` → `embedding` → `embedded` → `indexed` →
    `completed`, plus `dedup_hit` / `zip_walked` / `error`
    terminal variants). A defensive `_safe_progress()`
    wrapper swallows + logs any exception inside the callback
    so a flaky SSE consumer can never break the ingest flow.
    Three new meeet events `attachment.extracting`,
    `attachment.embedding`, `attachment.indexed` accompany the
    callback for cross-cutting observability. New HTTP route
    `POST /api/chat/threads/{id}/attachments/stream` is a
    thin adapter that pipes the callback into a
    `StreamingResponse` queue — frames are SSE
    (`event: <phase>\ndata: <json>\n\n`), terminal `result`
    frame carries the same envelope as the legacy upload so
    the cockpit can update the chip without an extra GET.
    Headers include `Cache-Control: no-cache` and
    `X-Accel-Buffering: no` so nginx flushes immediately. The
    original non-streaming endpoint is unchanged. Pinned by
    `tests/test_attachments_streaming_upload.py` (10 cases).
    Cockpit "indexing 12 chunks…" pill UI is the Claude-lane
    follow-up.

30. ~~**business.hubspot_pull_pipeline (read-only).**~~ **shipped**
    (2026-05-01) — closes the `business.hubspot_pull_pipeline`
    slot from IDEAS' "real adapters" list. New
    `backend/core/domains/packs/business/hubspot.py` ships
    `pull_pipeline(args)` against
    `https://api.hubapi.com/crm/v3/objects/deals` (vault key
    `HUBSPOT_API_KEY`). Returns a `PipelineResult` envelope
    (per-deal `id`/`name`/`amount`/`stage_id`/`stage_label`/
    `pipeline`/`close_date`/`created_at`/`updated_at`) with
    derived rollups (`active_count`, `won_count`,
    `lost_count`, `pipeline_amount`) when deals are present,
    plus the opaque `next_cursor` from HubSpot's
    `paging.next.after`. Stage labels resolve HubSpot's
    default-pipeline ids to human strings; unknown / custom
    stages pass through as the raw id. Defensive: structured
    errors for `auth_missing` / `auth_invalid` (401) /
    `invalid_limit` / `network_error` /
    `upstream_status` / `upstream_payload_invalid` —
    handler never raises on bad operator input. Emits
    `integration.hubspot.deals_list` events
    (`request` / `completed` / `error`) per the
    meeet × TARS adapter rule. Optional `include_raw=true`
    attaches each deal's raw HubSpot row under `raw` for
    debugging. `pipeline=<id>` filters client-side. Action is
    `destructive=False` — read-only, policy gate stays out
    of the way. Pinned by
    `tests/test_business_hubspot_pipeline.py` (35 cases).
    Cockpit "deals strip" UI is the Claude-lane follow-up.

29. ~~**Re-embed attachment chunks on demand.**~~ **shipped**
    (2026-05-01) — closes the "re-embed on demand" idea from
    IDEAS' attachments section. New
    `reembed_attachment(attachment_id, *, embedder=None,
    embedder_name=None, store=None, session_id=None)` in
    `backend.core.attachments.pipeline` re-vectorises every
    chunk of an existing attachment with a fresh embedder
    while preserving chunk ids and ords (so any cockpit
    permalinks survive the rebuild). `_resolve_embedder_by_name`
    accepts the short aliases `hash` / `openai` and any
    OpenAI model id (e.g. `text-embedding-3-large`); unknown
    or blank names fall back to `detect_embedder()`. The
    function emits `attachment.reembedded` and
    `usage.tokens` with full pre/post model + cost payloads,
    and refuses bad inputs structurally
    (`attachment_not_found`, `no_chunks`,
    `embedder_args_conflict`, `embedder_failed`) without
    raising. New HTTP route
    `POST /api/chat/attachments/{id}/reembed` accepts an
    optional body `{model: "openai" | "hash" |
    "text-embedding-3-large"}` and `x-tars-session-id`
    forwards into the trace; 404 only on unknown id, every
    other failure surfaces 200 + `ok=false`. Pinned by
    `tests/test_attachments_reembed.py` (21 cases). Cockpit
    "promote to OpenAI" / "swap embedder" UI is the
    Claude-lane follow-up.

28. ~~**Per-persona system-prompt overlay.**~~ **shipped**
    (2026-05-01) — closes the "per-persona system-prompt
    overlay" idea from IDEAS' Voice section. Persona dataclass
    learns an optional `system_prompt_overlay` field; the five
    named personas (Jarvis, Stark, HAL 9000, GLaDOS, TARS)
    each carry a tone block wrapped in a stable header and a
    safety footer that reminds the model voice overlays never
    override pack guardrails. The default `operator` persona
    opts out so the base prompt drives the response unchanged.
    New helpers `get_system_prompt_overlay(persona_id)` and
    `compose_system_prompt(*, role_overlay, pack_prompt,
    persona_overlay)` are re-exported from
    `backend.core.voice`. The chat orchestrator's
    `_system_prompt_for` now stitches role → pack → persona in
    that intentional order — persona last keeps voice closest
    to the user message so tone wins for ambiguous cases
    without overriding role / pack instructions. Defensive:
    if the persona registry raises, the orchestrator
    gracefully falls back to role + pack. Pinned by
    `tests/test_persona_prompt_overlay.py` (23 cases).
    `Persona.to_dict()` now exposes `has_system_prompt_overlay`
    so the cockpit voice picker can render an info chip.

27. ~~**Per-thread voice persona pinning.**~~ **shipped**
    (2026-05-01) — closes the "per-thread persona pinning"
    idea from IDEAS' Voice section. Threads now carry an
    optional `voice_persona_id` (additive migration on
    `threads`), exposed on the dataclass + every API
    response. `POST /api/chat/threads` and
    `PATCH /api/chat/threads/{id}` accept the field with
    validation: `None` / blank string clear the pin, unknown
    ids 400 with `voice_persona_id_unknown`, non-string types
    400 with `voice_persona_id_invalid`. The validator
    cross-checks against `iter_personas()` so any persona
    registered at runtime (built-in or domain-pack) is
    accepted automatically. Voice routing follow-up:
    `POST /api/voice/speak` now accepts an optional
    `thread_id` body field — when the caller didn't pass an
    explicit `persona`, the endpoint resolves the thread and
    uses its pinned id as a fallback. Response carries an
    `x-tars-voice-persona-source` header
    (`request` / `thread`) so the cockpit can render a
    "voice from this thread" badge. Pinned by
    `tests/test_thread_persona_pinning.py` (26 cases).
    Cockpit voice picker UI is the Claude-lane follow-up.

26. ~~**Attachment chunk-neighbours endpoint.**~~ **shipped**
    (2026-05-01) — backs the "per-attachment hover preview"
    surface from IDEAS. New
    `AttachmentStore.get_chunk_neighbours(chunk_id, *, before,
    after)` returns `(target, before_chunks, after_chunks)` by
    `ord` adjacency on the same `attachment_id`. The chunker
    doesn't emit dense `ord` values (overlap windows leave
    gaps), so "neighbours" means the closest chunks by `ord`,
    not by `ord ± 1`. Window args clamp to `[0, 10]`. New HTTP
    route `GET /api/chat/attachments/{attachment_id}/chunks/
    {chunk_id}/neighbours` (plus a `/neighbors` US alias)
    returns `{ok, attachment, chunk, before, after, window}`
    with optional `full_text=false` to ship only the 240-char
    `preview`. Two 404 paths defended (unknown attachment +
    chunk-not-in-attachment, so a typo can't leak chunks across
    attachments) and 422 on negative / oversized window.
    `tests/test_attachments_chunk_neighbours.py` (19 cases) pin
    the store unit + window semantics + HTTP shape +
    cross-attachment leak guard. Cockpit hover-card UI is the
    Claude-lane follow-up.

25. ~~**mlm.tg_outreach_draft (deterministic Telegram drafter).**~~
    **shipped** (2026-05-01) — closes the `mlm.tg_outreach_draft`
    slot from IDEAS' real-adapters list.
    `backend/core/domains/packs/mlm/tg_outreach.py` ships
    `tg_outreach_draft(args)` — a deterministic markdown
    generator with no I/O and no LLM. Six intents (`welcome`,
    `checkin`, `winback`, `recruit`, `celebrate`, `upsell`),
    three tones (`warm`, `direct`, `celebratory`), three
    languages (`en`, `ru`, `es`). The handler renders an opener
    (with `{name}` substitution and a `there` fallback for
    unnamed recipients), a body sentence, and a closer (the
    operator-supplied `cta` overrides the default closer when
    present), then optionally appends a `signature` after a
    dash separator. Output: `{ok, intent, tone, language,
    recipient, cta, markdown, plain_text, subject_hint, tags,
    length_chars, send_status:"draft"}`. The
    `send_status="draft"` field is mirrored on every response
    so cockpit code never has to remember the no-auto-send
    promise. Hard cap at `MAX_DRAFT_CHARS=4096` (Telegram's
    per-message limit) — over-cap drafts surface as
    `draft_too_long`. Input hardening: name / cta / signature
    strip newlines and clamp to length so a pasted blob can't
    break the markdown layout. Missing translations fall back
    to EN silently — adding a new language is one dict entry
    per intent. New `ActionSpec` registered on the MLM pack
    with `destructive=False` (the action produces only a
    preview; sending is a separate, currently absent action).
    `tests/test_mlm_tg_outreach.py` (34 cases) covers argument
    validation, parametrised happy paths over every intent /
    tone / language, determinism (same args ⇒ same output;
    different intents / languages ⇒ different drafts),
    personalisation (name substitution, default fallback,
    signature, CTA override, multi-line CTA flattening),
    length cap (monkey-patched
    `MAX_DRAFT_CHARS=50` triggers `draft_too_long`), action
    wiring, and JSON-serialisability.

24. ~~**Real adapter: traders.pull_klines (Binance).**~~ **shipped**
    (2026-05-01) — closes the `traders.binance_pull_klines` slot
    from IDEAS' real-adapters list.
    `backend/core/domains/packs/traders/binance.py` ships
    `pull_klines(args)` against Binance's public REST endpoint
    (no API key required). Symbol normalisation strips common
    separators (`BTC/USDT` → `BTCUSDT`), interval enum
    (`1s..1M`, default `1h`), limit clamped `1..1000`. Defensive
    row parsing tolerates string-typed numbers and drops corrupt
    rows. Derived `close_first` / `close_last` / `change_pct`
    fields land on the response when at least one candle
    resolved. Errors surface as
    `symbol_required` / `invalid_interval` / `invalid_limit`
    (validation), `network_error` (transport),
    `upstream_status` + `upstream_payload_invalid` (Binance
    responded but the payload wasn't a JSON array). Telemetry:
    three meeet event phases — `request`, `completed`,
    `error` — under `integration.binance.klines` so the cost
    ledger sees real-adapter calls. New `ActionSpec` registered
    on the traders pack with `destructive=False` and a JSON
    schema that enumerates valid intervals for the cockpit
    dropdown. `tests/test_traders_binance_klines.py` (21 cases)
    pin the parser, validation, happy / error paths, action
    wiring, and meeet event emission. Backend suite:
    **1137 passed**.

23. ~~**Playbook schema validator (CI gate).**~~ **shipped** (2026-05-01)
    — closes the "open work: schema validator" follow-up under the
    Phase K4 playbooks slot. The loader is permissive (`str()` /
    `bool()` casts) which is fine for bundled playbooks but lets
    operator typos through silently — `on_error: stoip` ran the
    default `stop`, forward `${steps.next.value}` resolved to
    `None`, unknown step keys never surfaced. The new validator
    (`backend/core/playbooks/validator.py`) produces a structured
    `ValidationResult(ok, issues)` with `Issue(severity, code,
    path, message)` so an operator can fix every problem in one
    pass. Errors block (`ok=False`) and warnings are surfaced
    verbatim. Strict checks: top-level + step key whitelists,
    duplicate step ids, action grammar
    (`<slug>.<action_id>` and `<slug>.awareness.<source>.snapshot`,
    dotted action ids like `pack.memory.set` are first-class),
    `${steps.<id>...}` references for unknown / forward ids,
    `args` type, `when` / `on_error` / `parallel` shapes,
    leading-`parallel` no-op. HTTP:
    `POST /api/playbooks/_validate` (literal payload or `id`,
    mutually exclusive) and `GET /api/playbooks/_validate_all`
    (every playbook on disk; wire to CI). Routing fix:
    `_reload` / `_validate` / `_validate_all` now register
    **before** the dynamic `/{playbook_id}` route so FastAPI
    doesn't shadow them. Smoke test pins every bundled playbook
    against the validator. `tests/test_playbook_validator.py`
    (40 cases). Backend suite: **1116 passed**.

22. ~~**Live updater channel HTTP (Tauri lock-step).**~~ **shipped**
    (2026-05-01) — closes the desktop distribution loop. The
    publish CLI has been writing `<target>/<version>.json` files
    since PR #44, but the live wire `tauri-plugin-updater`
    consumes was missing. This slot adds
    `GET /updates/{target}/{current_version}.json` (mounted on a
    new `updates_router` outside `/api/product` because the
    marketing URL pattern lives at the root) and a discovery
    helper `GET /api/product/updater/targets`. Both endpoints
    pull from the same `load_manifest()` as
    `/api/product/downloads`, so the two surfaces never drift.
    `backend/core/product/updater.build_channel_from_release()`
    is the bridge: it converts a `ReleaseEntry` to a
    `TauriChannel`, optionally filtered to a single target.
    `known_targets()` and `target_to_os_arch(slug)` are
    derived from the existing `_TARGET_BY_OS_ARCH` map so
    adding a new target only touches one source. Custom header
    `x-tars-updater-target` for log filtering; cache `max-age=60`.
    `tests/test_updater_channel_http.py` (18 cases) include a
    **lock-step assertion** (`channel.version` == `/api/product/
    downloads/latest`) and exhaustive coverage of every known
    target via the discovery endpoint. Backend suite: **1076
    passed**.

21. ~~**`speech.intents` extraction.**~~ **shipped** (2026-05-01) —
    Deterministic parser for TARS slash + voice commands so
    confident actions fire without an LLM round-trip and only the
    ambiguous residue routes to chat.
    `backend/core/speech/intents.py` exposes
    `parse_intent(transcript, *, known_playbook_ids=None)`
    returning a frozen `Intent(kind, target, query, args,
    duration_s, cleaned, consumed, confidence, error)`. Vocabulary:
    `run_action / run_playbook / jump / search / snooze / help /
    none`. Wake-word stripping for `TARS / Hey TARS / Ok TARS /
    Computer / Jarvis`. Slash forms `/run pack.action [json-args]`,
    `/run playbook_id`, `/jump <q>`, `/search <q>`,
    `/snooze <id> [for] <duration>`, `/help`. Voice forms with
    `dot`-keyword normalisation
    (`"traders dot morning check"` → `traders.morning_check`).
    Snooze duration parser handles `s / m / h / d / w` units.
    Registry-aware playbook arbitration: `known_playbook_ids` wins;
    bare-token bodies optimistic-dispatch when no registry is
    supplied; an empty registry rejects unknown tokens with
    `run_target_unrecognised`. JSON args parse only on
    `{ ... }` bodies; non-objects + invalid JSON surface
    `args_must_be_object` / `invalid_json_args`. HTTP:
    `POST /api/speech/intents` body
    `{transcript, use_playbook_registry=true}`. A flapping loader
    is caught and degrades to empty-registry. Side fix: deflaked
    `test_recovery_seed.py::test_generate_emits_recovery_shown_event`
    using the same `tmp_path / meeet.sqlite` isolation pattern as
    pairing. `tests/test_speech_intents.py` (35 cases). Backend
    suite: **1045 passed** + 13 pairing = 1058.

20. ~~**`application/zip` walker.**~~ **shipped** (2026-05-01) —
    Zip uploads previously fell through the binary path so the
    operator got nothing useful. With this slot, dragging a zip
    onto the cockpit fans the archive out: every safe member is
    fully ingested (extract → chunk → embed → FTS) and linked back
    to the parent zip via `meta.parent_attachment_id`. Parent stays
    opaque (no chunks) and carries a `zip_walk` summary on its meta
    so the cockpit can render per-member outcome.
    `backend/core/attachments/zip_walker.py` exposes
    `walk_zip(parent_record, blob, …)` with `ZipEntryResult` /
    `ZipWalkSummary` dataclasses and three env knobs:
    `TARS_ZIP_MAX_ENTRIES` (default 200, cap 5 000),
    `TARS_ZIP_MAX_ENTRY_BYTES` (default 25 MB, floor 1 KB),
    `TARS_ZIP_MAX_DEPTH` (default 2, cap 5). Safety: rejects
    absolute paths, traversal segments, `__MACOSX/*`, directory
    entries, oversize members, and corrupt archives never crash
    the parent ingest. `pipeline.ingest()` grew
    `parent_attachment_id` + `walk_archives` parameters; auto-walks
    on detection, emits `attachment.zip_walked` with counts +
    truncated flag. `tests/test_zip_walker.py` (14 cases): MIME /
    magic / suffix detection, unsafe-name predicate, env clamps,
    fan-out + parent linkage, directory + traversal skipping,
    entries cap (`truncated=True`), oversize skip, corrupt archive
    handled, `walk_archives=False` opt-out, depth-limited nested
    walks, dedup across same-thread duplicates. Backend suite:
    **1010 passed**.

19. ~~**Memory purge background loop.**~~ **shipped** (2026-05-01) —
    Closes the per-pack memory series. `_memory_purge_loop` in
    `web_extras/app.py` ticks every
    `TARS_MEMORY_PURGE_INTERVAL_S` seconds (default `0` = off) and
    calls `MemoryStore.purge_expired()` globally so TTL'd rows do
    not accumulate without operator intervention. Logs INFO when a
    tick deletes rows, WARN on transient failures, never raises.
    `tests/test_memory_purge_loop.py` (9 cases) pin env helper,
    short-circuits, single-tick semantics, exception isolation,
    and lifespan integration. Memory series (foundations + action
    family + purge loop) complete on the backend; cockpit "facts"
    view is the Claude-lane follow-up.
18. ~~**`pack.memory.*` action family.**~~ **shipped** (2026-05-01) —
    Activates the storage core (PR #56) as a uniform action surface
    on every domain pack. `backend/core/domains/memory_actions.py`
    is a closure factory binding six `ActionSpec`s to the pack slug:
    `set`, `get`, `list`, `delete`, `purge_expired`, `stats`.
    `DomainPack.all_actions()` yields `actions() + memory_actions(slug)`;
    `find_action` / `to_dict` / manifest counts now walk the
    composed view. `CompositePack.actions()` flattens via
    `sub.all_actions()` so a `research_lab` playbook hits
    `business__pack.memory.set` and lands in the business
    partition (sub-pack ownership preserved via the bound closure).
    Optional `pack_slug` arg lets a caller redirect into a sibling
    partition without going through the composite. Only `delete`
    is `destructive=True` so the policy gate gates it; reads, list,
    purge, and stats are first-class non-destructive ops.
    `tests/test_memory_actions.py` (27 cases) pin factory, injection
    invariants, handlers (TTL, validation, partitioning, filters),
    composites, HTTP describe / manifest counts, and the policy
    gate's confirm-vs-autopilot path. Full backend suite is now
    1000 passed.
17. ~~**Per-pack memory partitions (foundations).**~~ **shipped**
    (2026-05-01) — every domain pack now has its own SQLite-backed
    key-value store for facts/notes/preferences with optional TTL.
    `backend/core/memory/{models,store}.py` ship `MemoryEntry` +
    `MemoryStore` (DB at `~/.tars/memory.sqlite`, override
    `TARS_MEMORY_DB_PATH`, disable with `MEMORY_STORE=disabled`).
    `pack_memory` table has `UNIQUE(pack_slug, key)` so re-upserts
    update in place; four indexes cover slug, slug+kind, ttl, recency.
    HTTP surface in `web_extras/routers/memory.py`:
    `GET/POST /api/packs/{slug}/memory`,
    `GET/DELETE /api/packs/{slug}/memory/{key:path}`,
    `POST /api/packs/{slug}/memory/_purge_expired`,
    `GET  /api/packs/{slug}/memory/_stats`,
    `GET  /api/memory/stats`,
    `POST /api/memory/_purge_expired`. Upsert body accepts either
    `ttl_seconds` (relative) or `ttl_until` (POSIX). Expired rows are
    hidden by default and purgeable scoped or globally.
    `tests/test_memory_store.py` (28 cases) pins partitioning, TTL,
    stats, and full HTTP round-trip. **Next slices:** `pack.memory.*`
    action family on every pack so the agent loop and playbooks can
    use it through the standard interface, periodic purge loop, and a
    cockpit "facts" view. Same PR also deflakes
    `tests/test_pairing_contract.py` (was overflowing
    `list_events(limit=500)` once the suite grew); full backend
    suite is now 973 passed without `--deselect`.
16. ~~**Saved-search snooze.**~~ **shipped** (2026-05-01) —
    Completes the saved-search alert lifecycle. Snooze is "mute the
    alarm, keep the watcher" — `poll_saved_search` keeps the
    fingerprint snapshot current during the snooze window so when it
    lifts only genuinely new hits fire. New schema column
    `snoozed_until REAL`, `SavedSearch.is_snoozed()`, and
    `POST /api/search/saved/{id}/snooze` accepting `minutes` /
    `hours` / `until` (past timestamps + empty body clear).
    `tests/test_saved_search_snooze.py` (15 cases) pin migration,
    store, poll cycle, and HTTP shapes.
15. ~~**Domains health endpoint.**~~ **shipped** (2026-05-01) —
    `GET /api/domains/health` walks every registered pack, resolves
    its declared `auth_vault_keys` against env + macOS Keychain, and
    returns per-pack `{slug, name, ready, key_count, available_count,
    missing, keys: [{key, source, available}]}`. Probes both
    unprefixed and `TARS_`-prefixed forms; never echoes the secret
    value (only `source` ∈ `env` / `keychain` / `missing`).
    `tests/test_domains_health.py` (10 cases) pin shape, env vs
    keychain wins, missing-array completeness, and the
    no-secret-leak invariant. Operator dashboard for "what packs
    actually work on this machine".
14. ~~**Saved-search auto-poll loop.**~~ **shipped** (2026-05-01) —
    Lifespan loop in `web_extras/app.py` (default off,
    opt-in via `TARS_SAVED_SEARCH_POLL_INTERVAL_S=120` etc.) that
    walks every saved search and triggers
    `poll_all_saved_searches`. Combined with PR #49's emit path,
    saved-search alerts now fire automatically without manual
    cockpit triggers. `tests/test_saved_search_auto_poll.py`
    (12 cases) pin env helpers, loop short-circuit when disabled,
    a one-tick alert flow with stub MeeetClient, and lifespan
    start/stop hygiene.
12. ~~**Saved-search alerts.**~~ **shipped** (2026-05-01) —
    `backend/core/search/alerts.py` adds passive watchers on top of
    the saved-search store. `poll_saved_search` runs the query via
    the existing `search_*` family, fingerprints hits
    (`chunk:<id>` / `message:<msg_id>` / `trace:<event_id>`),
    diffs against the persisted snapshot, and emits
    `saved_search.new_hits` via `MeeetClient.emit` only when the
    diff is non-empty *and* a baseline existed (first poll seeds
    quietly so operators don't get a flood). Snapshot capped at
    `MAX_SEEN_HITS=1000`. New endpoints
    `POST /api/search/saved/{id}/poll` and
    `POST /api/search/saved/poll-all`. `tests/test_saved_search_alerts.py`
    (18 cases) pin the cycle, MeeetClient failure isolation, legacy
    schema migration, and HTTP wiring.
11. ~~**FTS5 backfill on schema bump.**~~ **shipped** (2026-05-01) —
    `verify_and_repair_chat_fts` + `verify_and_repair_events_fts`
    do row-count drift detection (not just empty-FTS fallback) and
    rebuild on demand. `POST /api/search/fts-repair` body
    `{force?, scopes?}` is the manual path; opt-in boot-time hook
    via `TARS_FTS_VERIFY_ON_BOOT=1` runs the same check on lifespan
    enter, never crashes the host. `tests/test_fts_auto_backfill.py`
    (15 cases) pin chat + events + HTTP + boot-hook behaviour.
    Default off so cold starts stay fast.

## Conventions to keep

- Aesthetic = minimalism + futurism (HUD/Sci-Fi FUI + OLED). Two
  accent colours max (gold `#CA8A04` + cyan `#00FFFF`); alert is
  red `#EF4444`. Fonts are Share Tech Mono + Fira Code.
- Action handlers: `async`, return a dict with `ok`, never raise on
  bad user input, never auto-execute destructive ops.
- Every cross-boundary call must run inside `trace_scope` and emit
  at least `*.invoked` and `*.completed` events.
- Manifests: slug is kebab-case-or-lower; color is hex; capabilities
  are short snake_case strings.
- Don't bleed `experiments/neural-showcase-{v2,v3}/` deps into the
  canonical `frontend/`.
- Update `docs/CHANGELOG_AGENTS.md` after every meaningful edit batch.

## How to run locally

```bash
# Backend (real adapters + SSE + council + policy + playbooks)
cd Jarvis/jarvis
PYTHONPATH=. PORT=9911 .venv/bin/python serve.py

# Frontend (v3)
cd experiments/neural-showcase-v3
npm install
npm run dev          # http://127.0.0.1:5174
# Cockpit reads VITE_TARS_API; the project ships a .env.local pinned
# to http://127.0.0.1:9911. Point it elsewhere if you change the port.

# Tests
PYTHONPATH=. .venv/bin/python -m pytest -q
```

### Useful curl recipes

```bash
# Live awareness snapshot
curl -s http://127.0.0.1:9911/api/domains/business/awareness/gcalendar/snapshot

# Council deliberation directly
curl -s -XPOST -H 'content-type: application/json' \
  http://127.0.0.1:9911/api/council/deliberate \
  -d '{"prompt":"interpret","context":{"topic":"market","avg_change_24h":-1.5}}'

# Run a playbook in autopilot
curl -s -XPOST -H 'content-type: application/json' \
  -H 'x-tars-policy-mode: autopilot' \
  http://127.0.0.1:9911/api/playbooks/business.morning_brief/run -d '{}'

# Stage destructive action → confirm
TOKEN=$(curl -s -XPOST -H 'content-type: application/json' \
  http://127.0.0.1:9911/api/domains/business/actions/draft_email \
  -d '{"to":"x@y.z","tone":"warm"}' \
  | jq -r .result.policy.confirmation_token)
curl -s -XPOST http://127.0.0.1:9911/api/policy/confirm/$TOKEN

# Browse the SQLite event log
curl -s 'http://127.0.0.1:9911/api/meeet/events?limit=10' | jq

# Cost / token rollup (optional ?session_id=ses_…)
curl -s http://127.0.0.1:9911/api/usage | jq

# Static manifest of every registered pack (incl. composites)
curl -s http://127.0.0.1:9911/api/domains/manifest | jq

# CLI replay tool — dump newest-first events to JSONL
PYTHONPATH=. .venv/bin/python -m backend.core.meeet.replay_cli \
  --export /tmp/tars-events.jsonl --limit 500
```

### Env vars that matter

- `MEEET_STORE_PATH` — durable buffer location (default `~/.tars/meeet.sqlite`).
- `MEEET_STORE=disabled` — bypass the SQLite buffer (events go to
  ingest / local-log only).
- `MEEET_INGEST_URL`, `MEEET_API_KEY`, `MEEET_CONTRACT_VERSION`,
  `MEEET_LOCAL_LOG`, `MEEET_SOURCE` — meeet bridge config.
- `TARS_POLICY_MODE` — default policy mode for the gate.
- `TARS_PLAYBOOKS_DIR` — override the playbooks discovery root.
- `TARS_PRICE_OVERRIDES_JSON` — JSON map (`{"model": {"input_per_mtok":
  X, "output_per_mtok": Y}}`) merged into the cost ledger's price
  table. Useful for plugging real (negotiated) prices.
- `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` /
  `SMTP_FROM` (or vault keys with `TARS_SMTP_*` prefix) — outbound
  mail relay for `business.draft_email` when called with `send=true`.
- `BUSINESS_KPI_PATH`, `BUSINESS_DEALS_PATH`, `MLM_NETWORK_PATH`,
  `CALENDAR_PATH`, `TRADERS_NEWS_PATH`, `TRADERS_PORTFOLIO_PATH`
  — local data overrides.

---

## Next Cursor block (~5–6 hours dense functional work)

> **Update — 2026-04-29 (Phase M sweep · backbone closed):**
> Following the late-session "code-side complete" milestone, this
> session closed the remaining functional gaps from the
> launch-readiness audit:
>
> - **Cleanup pass** (4 items) — stale TODO comments in
>   `desktop/src-tauri/src/main.rs` and `web_extras/routers/recovery.py`
>   removed; recovery `/generate` + `/verify` now flow through the
>   same HMAC policy gate as wallet ops (default-off, opt-in via
>   `TARS_REQUIRE_OPERATOR_CONFIRM=1`); `generate-release-keys.sh`
>   gained `--patch-tauri-conf` to auto-rewrite the
>   `plugins.updater.pubkey` placeholder; mobile activity wiring on
>   both platforms (Android `WalletActivity` + manifest + "open
>   wallets" CTA from PairingScreen Linked state, iOS
>   `TARSCompanionRoot` SwiftUI shell with `TabView { Pair, Wallets }`).
> - **P5 — Entitlements**: `backend/core/entitlements/` ships the
>   `Tier × LIMITS × can_run` module (free / pro / business with
>   daily cap, BYO toggle relaxes), 5 HTTP endpoints
>   (`/api/entitlements`, `/upgrade`, `/byo`, `/can_run`, `/tiers`),
>   `entitlements.{upgraded,byo_toggled,cap_hit}` events to meeet,
>   18 contract tests.
> - **P6 — Entrepreneur pack**: canonical replacement for `mlm` with
>   renamed action ids (`network_snapshot`, `lead_score`,
>   `generate_content`, `add_lead`, `retention_alert`, `log_activity`).
>   Legacy `mlm` slug stays registered with `manifest.deprecated=True`
>   + `deprecated_in_favor_of="entrepreneur"` until 2026-07-29 — saved
>   cockpit state and agents pinned to it keep working. Domain
>   registry gained `register_alias` / `aliases()` / `resolve_alias`
>   for future renames.
> - **P7 — Roles**: `backend/core/roles/` ships 6 built-in roles
>   matching the cockpit Onboarding page (founder / trader /
>   researcher / marketer / engineer / operator) plus deterministic
>   `synthesise_overlay()` for custom roles, single-tenant JSON
>   persistence, 6 endpoints, and an orchestrator hook that prepends
>   the active role's overlay before the pack prompt.
>   24 contract tests.
> - **P8 — Vision agent**: `backend/agents/vision_agent.py` runs an
>   OCR fallback (pytesseract opt-in; reports `unavailable` cleanly
>   when the binary is missing), folds image summaries into the
>   system prompt for every voice, and surfaces native image refs to
>   multimodal voices through the existing `attachments` parameter.
>   `ChatVoice.supports_multimodal` flag set on Anthropic + OpenAI
>   voices; LocalChatVoice stays text-only. New `context.vision`
>   StreamEvent for cockpit rendering. 13 contract tests.
>
> Test totals: **671 pytest + 56 vitest + 18 swift + tsc clean**
> (was 600 pytest pre-session). Phase M backbone complete.
>
> See `docs/CHANGELOG_AGENTS.md` for the per-file diff and
> `docs/handoff-claude.md` for the brand-pass brief.

> **Previous update — 2026-04-29 (final sweep · code-side complete):**
> Following the O+P+Q+D close-out, this session closes the last
> three Cursor-lane items on `LAUNCH_READINESS.md`:
> - **Mobile companion wallet surface** — iOS `WalletClient.swift`
>   + SwiftUI `WalletView`/`WalletViewModel`; Android
>   `WalletClient.kt` + Compose `WalletScreen`/`WalletViewModel`.
>   Read-only list + live balance fetch + prove-ownership over the
>   paired channel. Mirrored decoder fixtures: 7 new Swift cases
>   (now **18 swift tests**) + symmetric `WalletDecodersTest.kt`
>   for Android.
> - **Cinematic mnemonic-reveal** — `<MnemonicReveal />` ships a
>   face-down card grid with a 60ms-stagger 3D card flip per word,
>   gold/amber accent, "show again / hide / I wrote it down" gate,
>   and pure-CSS perspective (no third-party motion libs). Helper
>   tests: 6 new vitest cases (now **56 vitest tests**).
> - **Release-key bootstrap** —
>   `desktop/scripts/generate-release-keys.sh` is a guarded helper
>   that mints a Tauri/minisign keypair locally, refuses to
>   overwrite existing keys, prints the public key for
>   `tauri.conf.json`, and prints the two `gh secret set …`
>   commands needed to install the GitHub Actions secrets. Never
>   uploads anything.
>
> Test totals: **600 pytest + 56 vitest + 18 swift + tsc clean**.
> Code-side launch readiness is now **complete**. The only
> remaining blockers are non-code (Apple/Windows/Minisign/Play
> credentials — operational, project lead) and brand-grade
> motion polish across the rest of the cockpit (Claude lane;
> the cinematic-reveal foundation is shipped).
>
> See `docs/handoff-claude.md` for the updated brand-pass brief.

> **Update — 2026-04-29 (O + P + Q + D close-out, binary-alpha-ready):**
> Following M / N / N1–N5, this session shipped Phases **O1**
> (structured error envelope + stable `error_code` taxonomy across
> `/api/wallet`, `/api/agents`, `/api/pairing`), **O2** (HTTP-level
> policy gate behind `TARS_REQUIRE_OPERATOR_CONFIRM=1` —
> HMAC-SHA256 confirm tokens bound to wallet+action+params hash),
> **O3** (SLIP-0010 Phantom-compatible Solana derivation
> side-by-side with the legacy `tars-v1` scheme; pinned to the
> canonical zero-mnemonic Phantom address), **O4** (audit log of
> raw signed bytes in meeet — privacy-by-default, opt-in via
> `TARS_AUDIT_RAW_TX=1`, TTL via `TARS_AUDIT_RETENTION_DAYS`,
> prune endpoint), **P2/P3/P4** (live RPC helpers:
> `/api/wallet/solana/blockhash`, `/api/wallet/evm/{addr}/nonce`,
> `/api/wallet/ton/{addr}/seqno`), **P1** (chain-specific send
> forms in the cockpit: per-chain inputs + autofill button +
> auto-confirm-token plumbing), **Q1** (end-to-end smoke test:
> pair → mint → sign → verify with independent crypto), **D1**
> (root `README.md`), and **D4** (`docs/THREAT_MODEL.md`).
> Test totals are now **600 pytest + 50 vitest + 11 swift + tsc clean**.
> The launch-readiness audit (`docs/LAUNCH_READINESS.md`) updates to
> **GO for local-first private alpha** AND **GO for a public binary
> alpha as soon as operational signing keys exist**. The only
> remaining blockers are non-code: minisign / Apple / Windows / Play
> credentials (1–2h ops, project lead) and the cinematic
> mnemonic-reveal pass (Claude lane).

Rough order (pause after each milestone; run `pytest`, `vitest`, `tsc`):

| Block | Time | Goal | Why deferred |
| ----- | ---: | ---- | ------------ |
| **~~A1. Sidecar pipeline~~** | ~~2 h~~ | ✅ **Shipped:** `desktop/pyoxidizer.bzl` (CPython 3.12 + repo → `tars-backend`); `src-tauri/src/sidecar.rs` resolves binary (`TARS_BACKEND_BIN` → bundled → `python3 serve.py`), polls `/health`, emits `desktop.sidecar.{started,failed,exited}` (schema v1.0.0 at `desktop/src-tauri/sidecar-events.schema.json`, pinned by `tests/test_desktop_sidecar_events_contract.py`). | — |
| **~~K4. Cockpit React surfaces~~** | ~~3 h~~ | ✅ **Shipped:** `RecoverySetup`, `PairingPanel`, `/cockpit` overlays + `#security` section (functional wiring; Claude owns visual polish). See `docs/handoff-claude.md` § 3.4–3.5. | — |
| **~~K5. Domain-pack secret rotation~~** | ~~1 h~~ | ✅ **Shipped:** `VaultSecretsPanel` on `/cockpit`; `GET /api/vault/status` merges `KNOWN_KEYS` + pack `auth_vault_keys()`; copyable macOS Keychain add command per key. | — |
| **~~L1. iOS pairing-first slice~~** | ~~3 h~~ | ✅ **Shipped:** `mobile/ios/TARSCompanion/` SPM library (CryptoKit + URLSession + AVFoundation QR + SwiftUI shell). `swift test` runs 11 cases; the `idle → linked` state machine matches the host's pairing endpoints. | — |
| **~~L2. Android pairing-first slice~~** | ~~3 h~~ | ✅ **Shipped:** `mobile/android/TARSCompanion/` (Compose + OkHttp + java.security XDH); JVM-only `PairingDecodersTest.kt` runs once Android SDK is installed. iOS↔Android symmetry pinned by `tests/test_mobile_pairing_contract.py`. | — |
| **~~L3. Updater channel CI signer~~** | ~~1 h~~ | ✅ **Shipped:** `.github/workflows/release-desktop.yml` (matrix build × pyoxidizer × `tauri signer sign` × publish manifest + updater channel) + `desktop/scripts/sign-artifacts.sh`. Pinned by `tests/test_release_desktop_workflow.py`. Real minisign key still lives in repo secrets. | — |
| **~~M1. Multi-agent registry + task queue~~** | ~~3 h~~ | ✅ **Shipped:** `backend/core/agents/{models,store,runner}.py` + `web_extras/routers/agents.py` (`POST /api/agents`, `…/tasks`, `…/run`, `…/cancel`). SQLite-backed; tasks run through the council orchestrator and emit `agent.created`, `agent.task.{queued,started,completed,failed,cancelled}` to meeet. Cockpit panel `AgentsPanel.tsx`. Tests: `tests/test_agents_router.py` (15 cases). | — |
| **~~M2. Crypto wallets + wallet pack~~** | ~~3 h~~ | ✅ **Shipped:** `backend/core/wallet/` (BIP-39 mnemonic, XChaCha20-Poly1305 secrets at rest, Solana ed25519 signing, EVM/TON address derivation flagged `signing_supported=False`). HTTP under `/api/wallet/*`. Agent-controllable via the `wallet` domain pack — `propose_send`/`sign_message` are destructive and flow through the policy gate. Cockpit panel `WalletPanel.tsx` with one-time mnemonic reveal. Tests: `tests/test_wallet_{service,router,pack}.py` (31 cases). | — |
| **~~N1. Wallet balance reader~~** | ~~1 h~~ | ✅ **Shipped:** `backend/core/wallet/balance.py` (stdlib `urllib` JSON-RPC for Solana / EVM / TON, env-overridable RPC URLs, structured `BalanceError`). New `GET /api/wallet/{id}/balance` route + `wallet.balance` action + cockpit "balance" pill in `WalletPanel.tsx`. Tests: `tests/test_wallet_balance.py` (15 cases). | — |
| **~~N2. Agent autopilot loop~~** | ~~1 h~~ | ✅ **Shipped:** `backend/core/agents/autopilot.py` (`tick_once` + `autopilot_loop`, interval `TARS_AGENTS_AUTOPILOT_INTERVAL_S` default 30s, `0` disables). Per-agent toggle (`metadata.autopilot=true`), HTTP `POST /api/agents/{id}/autopilot?enabled=…` + force-tick endpoint, cockpit per-row autopilot pill + global "tick" button. Lifespan spawns the loop. Tests: `tests/test_agents_autopilot.py` (8 cases). | — |
| **~~N3. Real EVM signing~~** | ~~2 h~~ | ✅ **Shipped:** `eth-account` dependency. `backend/core/wallet/sign_evm.py` (BIP-44 m/44'/60'/0'/0/{index}, EIP-191 personal_sign, EIP-1559 typed-2 + legacy tx). `Wallet.signing_supported = True` for EVM. New route `POST /api/wallet/{id}/sign_evm_tx`, new pack action `wallet.sign_evm_tx` (destructive). Cockpit "prove ownership" button. `mnemonic_to_entropy` accepts 12/15/18/21/24-word phrases for third-party imports. Anvil canonical mnemonic test vector pinned. Tests: `tests/test_wallet_evm_signing.py` (17 cases) + adjacent suite updates (+19 pytest total). | — |
| **~~N4. Real TON signing~~** | ~~2 h~~ | ✅ **Shipped:** `tonsdk` dependency. `backend/core/wallet/sign_ton.py` (`derive_ton_account` → canonical wallet v3R2 contract address, `sign_ton_message` ed25519, `sign_ton_transfer` builds + signs broadcastable BoC). `Wallet.signing_supported = True` for TON (all three chains complete). New route `POST /api/wallet/{id}/sign_ton_transfer`, new pack action `wallet.sign_ton_transfer` (destructive). `parse_amount` helper accepts nanoton ints / digit-strings / decimal TON. Tests: `tests/test_wallet_ton_signing.py` (23 cases) + adjacent suite updates (+23 pytest total). | — |
| **~~N5. Real Solana tx signing~~** | ~~1.5 h~~ | ✅ **Shipped:** `solders` dependency. `backend/core/wallet/sign_sol.py` (`derive_solana_keypair`, `sign_solana_transfer` builds `system_program::transfer` and emits raw_b64/b58/hex + tx_signature). New route `POST /api/wallet/{id}/sign_solana_transfer`, new pack action `wallet.sign_solana_transfer` (destructive). `parse_lamports` helper accepts lamports / SOL decimals / hex. Caller supplies `recent_blockhash` (matches EVM/TON trust model). Tests: `tests/test_wallet_sol_signing.py` (22 cases). | — |
| **~~O1. Structured error envelope~~** | ~~1 h~~ | ✅ **Shipped:** `web_extras/errors.py` — `TARSAPIError` + `ERROR_CODES` taxonomy + `ERROR_HINTS`; handlers for `HTTPException` / `RequestValidationError` / `StarletteHTTPException`. Every error response carries `{ok:false, error_code, message, hint?, detail}`. Validation 422 surfaces a per-field `errors` list. Legacy FastAPI `detail` is preserved. Tests: `tests/test_error_envelope.py` (8 cases). | — |
| **~~O2. HTTP policy gate~~** | ~~1.5 h~~ | ✅ **Shipped:** `web_extras/policy_gate.py` — HMAC-SHA256 confirm tokens bound to `(wallet_id, action, params_hash, expires_at)`, opt-in via `TARS_REQUIRE_OPERATOR_CONFIRM=1`. New `POST /api/wallet/{id}/confirm` mints; destructive routes call `policy_gate.require_confirm(...)`. Header is `X-TARS-Confirm: <token>`. Tests: `tests/test_policy_gate.py` (17 cases). | — |
| **~~O3. SLIP-0010 Phantom derivation~~** | ~~1.5 h~~ | ✅ **Shipped:** `backend/core/wallet/slip10.py` implements official SLIP-0010 ed25519. `Wallet.derivation_scheme` field (default `tars-v1`, opt-in `bip44-501-phantom`). Idempotent SQLite ALTER for legacy DBs. Phantom-compat `m/44'/501'/0'/0'` pinned to canonical zero-mnemonic address `HAgk14JpMQLgt6rVgv7cBQFJWFto5Dqxi472uT3DKpqk`. Tests: `tests/test_wallet_slip10.py` (13 cases). | — |
| **~~O4. Audit log raw signed bytes~~** | ~~1 h~~ | ✅ **Shipped:** `backend/core/wallet/audit.py` — `enrich_signed_event` attaches raw fields when `TARS_AUDIT_RAW_TX=1`. `MeeetStore.prune_kind_before` + `prune_signed_events` enforce TTL. New `POST /api/wallet/audit/prune`. Privacy-by-default. Tests: `tests/test_wallet_audit.py` (14 cases). | — |
| **~~P2 / P3 / P4. Live RPC helpers~~** | ~~1 h~~ | ✅ **Shipped:** `backend/core/wallet/chain_helpers.py` (stdlib only). New routes: `GET /api/wallet/solana/blockhash`, `GET /api/wallet/evm/{address}/nonce?block_tag=`, `GET /api/wallet/ton/{address}/seqno`. All degrade to `502 wallet_balance_rpc_failure` envelope on transport error. Tests: `tests/test_wallet_chain_helpers.py` (19 cases). | — |
| **~~P1. Chain-specific send forms~~** | ~~1.5 h~~ | ✅ **Shipped:** `experiments/neural-showcase-v3/src/components/ChainSendForm.tsx` (per-chain inputs, ⚡ autofill button, auto-confirm-token, signed-result viewer with copy buttons). `lib/wallet.ts` adds `fetchSolanaBlockhash` / `fetchEVMNonce` / `fetchTONSeqno` / `fetchPolicyStatus` / `mintConfirmToken`; sign functions accept optional `confirmToken`. WalletPanel toggles to `ChainSendForm` for any signing-capable wallet. | — |
| **~~Q1. End-to-end smoke test~~** | ~~1 h~~ | ✅ **Shipped:** `tests/test_e2e_smoke.py` walks pair → mint Solana/EVM/TON → message-sign each → real-tx-sign each → independent crypto verify (Account.recover_transaction, b58decode 64-byte, TON body_hash) → agent + task lifecycle → meeet event presence assertions. (4 cases.) | — |
| **~~D1. Root README.md~~** | ~~1 h~~ | ✅ **Shipped:** `README.md` — quickstart, full env-var reference (wallets / hardening / pairing / meeet), architecture diagram, common ops (Phantom-compat wallet, real Solana send), troubleshooting, test commands. | — |
| **~~D4. THREAT_MODEL.md~~** | ~~1 h~~ | ✅ **Shipped:** `docs/THREAT_MODEL.md` — trust zones Z0–Z7, where every piece of crypto material lives + its at-rest encryption, attack surfaces ranked by blast radius, what we deliberately do not do, logging policy, primitive choices. | — |

Carry **`AGENT_HANDOFF.md` § Handoff → Claude** below into the prompt when swapping agents.

---

## Handoff → Claude Code (design + meeet.world integration)

**Owner:** Claude Code (`design-system/tars/MASTER.md`, Landing, brand,
`meeet.world` frontend if that repo exists alongside this mono).

Synchronise against shipped functional surfaces (**ChatPane**, ⌘K
palette, timeline, attachment chips). Do **not** change HTTPS event
contracts without a coordinating Cursor PR.

Suggested sequence (prioritised):

1. **Cockpit chrome (Phase L)** — ⌘K **`<CommandPalette />`**, **`<ThreadTimeline />`**, **`<ChatPane />`**: hover, motion, typography, **`mark`** highlight styling for BM25 hits, timeline spine / grouping-by-hour, responsive polish per **`design-system/tars/pages/cockpit.md`** (create if missing from skill output).
2. **Landing `/` downloads** — primary CTAs fetching manifest from **`GET /api/product/downloads`** (or static JSON bundled at build-time with env substitution). Buttons: **Download for macOS**, **Windows**; checksum copy; version string.
3. **meeet.world integration** — match **meeet** marketing shell: OG image, canonical URL, **`meeet.world` → TARS** deep links, optional embed iframe or CTA strip reusing MASTER palette (**gold accent + OLED cyan**). Respect existing ingest contract (**1.0.0**) — no silent bumps; flag **L5** when pairing UI ships.
4. **Brand artefacts** — favicon, social card, typography pass aligned with MASTER voice (*operator-grade, minimal fluff*).

Deliverable Claude should leave behind: screenshots or Storybook notes +
short **PR description** referencing `HANDOFF § Handoff → Claude`
so Cursor can sanity-check routes.

Copy-paste cue for Claude:

```
Read Jarvis/jarvis/docs/AGENT_HANDOFF.md → sections «Next Cursor block»
and «Handoff → Claude». Design source: design-system/tars/MASTER.md.
Functional manifest: GET /api/product/downloads (after Cursor merges).
Polish ⌘K, timeline, ChatPane; Landing download CTAs; meeet.world visual
alignment. Do not invent backend contracts beyond docs/contracts/.
```

## Notes from Claude → Cursor / Brother (Waves 7–10, 2026-04-29)

The marketing surface (`experiments/neural-showcase-v3/`) shipped four
polish waves on top of Phase L. Inventory below — pick what to wire on
the cloud side.

### New routes (already lazy-loaded in `App.tsx`)

| Path             | What                                                          | Static asset?                      |
| ---------------- | ------------------------------------------------------------- | ---------------------------------- |
| `/build-with`    | Viral badge generator. Two sizes × two themes, paste-ready embeds. | yes — `public/badge/*.svg` (4 files) |
| `/privacy`       | Renders `docs/PRIVACY_POLICY.md` via `?raw` import.           | n/a                                |
| `/terms`         | `docs/TERMS_OF_SERVICE.md`.                                   | n/a                                |
| `/security`      | `docs/SECURITY.md`.                                           | n/a                                |
| `/roadmap`       | `docs/ROADMAP.md`.                                            | n/a                                |
| `/changelog`     | `docs/CHANGELOG_PUBLIC.md`.                                   | n/a                                |

All five legal/info pages share `<LegalLayout/>` which auto-derives a
one-line `og:description` from the markdown lede. Update the markdown
once and every surface picks it up.

### Static badge endpoint (brother needs to host)

`/build-with` Markdown embed points at:

```
https://meeet.world/badge/built-with-tars.svg              # full · dark
https://meeet.world/badge/built-with-tars-light.svg        # full · light
https://meeet.world/badge/built-with-tars-compact.svg      # compact · dark
https://meeet.world/badge/built-with-tars-compact-light.svg
```

Files live in `experiments/neural-showcase-v3/public/badge/`. They are
`<svg>` inline (~1 KB each), no external font loads. When the deploy
moves to `tars.meeet.world`, mirror them under `/badge/` so existing
embedded badges keep working.

### Analytics contract (`docs/contracts/ANALYTICS.md`)

Frontend now emits `tars.<page|api|click>.<action>` events to
`POST /api/log` via `src/lib/analytics.ts`. Pre-launch they buffer in
`localStorage["tars-analytics-buffer"]` (cap 200, oldest-evicted).
Wired today:

- `tars.page.view` on every route change.
- `tars.click.install_copy_(install|brew)` with `os` prop.
- `tars.click.badge_copy_(html|md)` with `size`, `theme`.
- `tars.click.download_<os>_<arch>` with `version`, `kind`, `surface`.

Next click events I'd like Cursor to wire if it touches Hero / Pricing:
`tars.click.cta_cockpit`, `tars.click.tier_selected`, `tars.click.faq_open`.

Brother's responsibilities (full list in the ANALYTICS.md):

1. Validate name regex `^tars\.(page|api|click)\.[a-z0-9_]+$`.
2. Drop events with stale `ts` (>24h past or future).
3. Stamp server-side `received_at`, `country` (CF-Country header), `ua`.
4. Persist to ClickHouse, respond `204 No Content`.

### Cookie posture (frontend already discloses functional-only)

`<CookieConsent/>` ships globally. We declare four cookies:
`tars-session`, theme, lang, Cloudflare bot-management. Anything else
the brother adds (e.g. analytics consent variants) needs a cookie-
inventory entry in `docs/PRIVACY_POLICY.md § 9` first.

### Per-page SEO (titles + og)

Every page now calls `useDocumentMeta({ title, description, ogImage })`
from `src/lib/meta.ts`. The hook updates `document.title`, `<meta
name=description>`, and the og/twitter pair on mount; restores defaults
on unmount. Crawlers still read the static defaults baked into
`index.html`, so brother's edge worker (when it stands up) should
inject the per-route values at HTML send time for proper SSR SEO.

### Don't-touch list (Cursor-owned)

`src/lib/downloads.ts`, `src/lib/api.ts`, `src/lib/wallet.ts`, the
backend, and the Cockpit's `<CommandPalette/>` (separate from the
landing-side `<GlobalCommandPalette/>`). I added one minor change —
`onClick` analytics on the download anchors in `DownloadStrip.tsx` —
that's purely additive and doesn't alter the manifest contract.

## 2026-05-10 — Wave 81 (Claude → Cursor) — algotrade FE/BE handshake

### What I shipped (Wave 80-D + Wave 81-A FE)
- /workshop generic 4-phase wizard (Intake → Design → Test → Deploy)
- /workshop/cresco branded landing for Cresco Capital workshop
- Workshop FE components: AgentDesigner, BacktestPanel, PhaseDeploy, OutputSchemaBuilder, RetuneDialog
- Compliance console at /compliance + ReceiptVerifier
- 20 starter playbooks across 5 verticals (fund / saas / dao / family-office / algotrade)

### What my FE expects from your backend (proposed API contract)
Treat this as a draft — push back in this doc if shape needs to change before W2-PR2.

POST /api/algotrade/strategies          → register Strategy IR, returns {fingerprint, version}
GET  /api/algotrade/strategies          → list with filters (tag, instrument, author)
POST /api/algotrade/backtest            → body {fingerprint, instrument, range, capital}, SSE stream of {bar_idx, equity, position, fills[]} + final {sharpe, sortino, max_drawdown, win_rate, expectancy, cagr}
POST /api/algotrade/sessions            → start paper session, body {strategy_fingerprint, risk_policy, instrument}
GET  /api/algotrade/sessions/{id}       → status, current_position, todays_pnl, audit_count
POST /api/algotrade/sessions/{id}/stop  → graceful close
GET  /api/algotrade/sessions/{id}/audit → JSONL stream of AuditEvent
POST /api/algotrade/risk/policy         → save RiskPolicy named template (kill_switch, max_*, allowed_instruments)

My BacktestPanel.tsx (in components/workshop/) is wired with mock fallback — when these endpoints land, swap mock for real with zero FE changes if the response shape matches the above.

### Lane discipline
- I don't touch backend/core/algotrade/ or backend/core/domains/packs/algotrade/
- You don't touch experiments/neural-showcase-v3/src/components/workshop/ or pages/Workshop.tsx | CrescoWorkshop.tsx | Compliance.tsx
- Shared: docs/AGENT_HANDOFF.md (append-only), docs/contracts/* (gated — comment in doc which agent owns active edit)

### Pending operator (Alien) actions blocking the launch
- GITHUB_RELEASE_TOKEN in CF Pages env (without it /dl/* returns 503)
- BRIDGE_SHARED_SECRET in CF Pages env (without it core-bridge /health red)
- Apple Developer .p12 → GitHub Actions secrets (without it .dmg unsigned + Gatekeeper rejects)
- Tag v9.1.0 → GitHub Actions builds signed .dmg

>>> SYNC: Claude · 2026-05-10 · Wave 81-A.
