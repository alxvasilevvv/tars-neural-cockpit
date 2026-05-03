# Agent changelog

Per-batch log of edits made by autonomous agents. Read top-down; latest entry
first. Every entry: who, when, summary, files. Keep entries short and
factual; prose belongs in `AGENT_HANDOFF.md`.

## 2026-05-04 — Cursor · ops: Pages 403 diagnose (accounts OK, Pages denied)

**Summary**

**`ops_push_cloudflare_pages_api_token.sh`:** on Pages preflight failure, **GET /accounts**
check — if OK, prints RU hint that token lacks **Account → Cloudflare Pages → Edit** and
**opens** `https://dash.cloudflare.com/profile/api-tokens` unless **`OPS_CF_NO_BROWSER=1`**.

**Files**

- `scripts/ops_push_cloudflare_pages_api_token.sh`
- `docs/CHANGELOG_PUBLIC.md` (regenerated)
- `docs/CHANGELOG_AGENTS.md` (this entry)

## 2026-05-04 — Cursor · ops: cf-operator.env paste + Cloudflare → GitHub Pages deploy

**Summary**

**Operator flow:** copy **`cf-operator.env.example`** → **`cf-operator.env`** (gitignored),
paste **`CLOUDFLARE_ACCOUNT_ID`** + **`CLOUDFLARE_API_TOKEN`**, run **`make ops-cf-pages-token`**.
**`scripts/ops_push_cloudflare_pages_api_token.sh`** preflights **GET …/pages/projects/tars-meeet**,
then **`gh secret set CLOUDFLARE_API_TOKEN`** + **`gh workflow run`** (dashboard token must have
**Account → Cloudflare Pages → Edit**). **`cf-operator.env.example`** / локальный **`cf-operator.env`**
— пошаговые подсказки где взять ID и token.

**Files**

- `cf-operator.env.example` (paste template + hints)
- `.gitignore` (`cf-operator.env`)
- `scripts/ops_push_cloudflare_pages_api_token.sh`
- `Makefile` (`ops-cf-pages-token`)
- `docs/CHANGELOG_PUBLIC.md` (regenerated)
- `docs/CHANGELOG_AGENTS.md` (this entry)

## 2026-05-03 — Cursor · Pages CI: token verify + trim + OPS Account Resources

**Summary**

**Workflow:** optional **`/user/tokens/verify`** is **warning-only** (that endpoint
needs **User → User Details → Read**; Pages-only tokens skip it). **Preflight**
still trims secrets and enforces **GET pages/projects/tars-meeet**.

**Docs:** **`TARS_MEEET_OPS_TODO.md`** Step 2 — Account Resources + paste rules.

**Files**

- `.github/workflows/tars-meeet-cloudflare-pages.yml`
- `docs/TARS_MEEET_OPS_TODO.md`
- `docs/CHANGELOG_AGENTS.md` (this entry)

## 2026-05-03 — Cursor · B-001: legacy installers on tars + CF preflight + hybrid monitor

**Summary**

**TARS `public/_redirects`:** `/dl/TARS-8.4.0-*` and `/install.sh` now **302** to
GitHub Release / raw install script (replacing `/install.sh → /install`); human
page stays **`/install`**.

**CI:** **Preflight** step `GET …/pages/projects/tars-meeet` with jq — fails fast
with a clear error when the GitHub secret token lacks **Account → Cloudflare
Pages → Edit** (avoids opaque Wrangler **10000**).

**meeet-command-center** `resolution_monitor` B-001: each legacy path must
**sniff** as non-HTML on **meeet.world** *or* **tars.meeet.world** (no SPA
false positive).

**Files**

- `experiments/neural-showcase-v3/public/_redirects`
- `.github/workflows/tars-meeet-cloudflare-pages.yml`
- `meeet-command-center/tools/resolution_monitor.py` (sister repo; push separately)
- `docs/CHANGELOG_AGENTS.md` (this entry)

## 2026-05-03 — Cursor · Pages workflow: Wrangler pin + npx non-interactive

**Summary**

**`tars.meeet.world — Cloudflare Pages`:** **`NPM_CONFIG_YES=true`** on the job
and again on the **Deploy** step (so it reaches wrangler-action’s Node
subprocess), plus **`wranglerVersion: "4.14.4"`** to avoid npm 10+ npx
“no YES option” when resolving **wrangler@4.86.x**.

**Files**

- `.github/workflows/tars-meeet-cloudflare-pages.yml`
- `docs/CHANGELOG_AGENTS.md` (this entry)

## 2026-05-03 — Cursor · CHANGELOG_PUBLIC sync for Pages CI gate

**Summary**

Regenerated and committed **`docs/CHANGELOG_PUBLIC.md`** via
`python3 scripts/generate_public_changelog.py` so the “Changelog public
artefact in sync” step passes on push to `main`.

**Files**

- `docs/CHANGELOG_PUBLIC.md`
- `docs/CHANGELOG_AGENTS.md` (this entry)

## 2026-05-03 — Cursor · OPS TODO: Cloudflare token rotation after Secret Scanning

**Summary**

`docs/TARS_MEEET_OPS_TODO.md` — bullet under CURRENT STATE: if GitHub /
Cloudflare revokes an exposed token, mint a new one, update **only** the
`CLOUDFLARE_API_TOKEN` GitHub secret, re-run Pages workflow; never commit
literals (ties to 2026-05-03 history scrub + user email). **`docs/SYNC.md`**
handoff row + “Last updated” stamp for the same slice.

**Files**

- `docs/TARS_MEEET_OPS_TODO.md`
- `docs/SYNC.md`
- `docs/CHANGELOG_AGENTS.md` (this entry)

## 2026-05-03 — Cursor · Cloudflare API token leak remediation (git history)

**Summary**

GitHub Secret Scanning surfaced a **`cfat_…`** literal pasted in
`docs/TARS_MEEET_OPS_TODO.md` (May 1 cutover commits); Cloudflare auto-revoked
the token. **Current tree was already clean** (removed in a follow-up commit).
Rewrote **all** history with `git filter-repo --replace-text`, replacing the
literal with `<REDACTED_CF_API_TOKEN>`, then **force-pushed** `main`, tags, and
active branches to `origin`. **Operator:** create a **new** API token and update
GitHub Actions secret **`CLOUDFLARE_API_TOKEN`**; re-run the Pages workflow.

**Files**

- Entire repo history (no content changes at `HEAD` beyond this log).
- `docs/CHANGELOG_AGENTS.md` (this entry)

## 2026-05-03 — Cursor · TARS repo public + `scripts/install-tars.sh` (B-001)

**Summary**

`gh repo edit … --visibility public --accept-visibility-change-consequences`
so anonymous clients can fetch GitHub Release v8.4.0 assets linked from
`GET /api/product/downloads`. Added root **`scripts/install-tars.sh`**
for **`meeet.world/install.sh`** redirect (raw.githubusercontent.com).
**Security:** audit git history for any committed secrets now that the
repo is public.

**Files**

- `scripts/install-tars.sh`
- `docs/CHANGELOG_AGENTS.md` (this entry)

## 2026-05-03 — Cursor · AGENT_HANDOFF: B-001 ship + deploy refs

**Summary**

`docs/AGENT_HANDOFF.md` — block for 2026-05-03: PR #149, Pages run
25281019786, `meeet-solana-state` PR #38, public-funnel caveat (private
GitHub release → anonymous 404). `>>> SYNC: Cursor · 2026-05-03`.

**Files**

- `docs/AGENT_HANDOFF.md`
- `docs/CHANGELOG_AGENTS.md` (this entry)

## 2026-05-03 — Cursor · B-001: manifest artifact URLs → GitHub Release v8.4.0

**Summary**

Pages Function `functions/api/product/downloads.ts` embedded `RELEASES`
used `https://tars.meeet.world/TARS-8.4.0-*` paths; Cloudflare serves SPA
HTML for unknown paths (`html_ct` in `resolution_monitor`). Artifact
`url` fields now match **`state/B001_GITHUB_RELEASE_v8.4.0_URLS.md`** /
Tauri filenames on `tars-neural-cockpit` **`v8.4.0`**. UI curl/href
strings updated (Install, Pitch, GlobalCommandPalette, `og.svg`,
`og-install.svg`). **Cross-repo:** `meeet-solana-state` Supabase EF
`tars-downloads` fallback manifest same URLs — deploy that function for
offline-upstream parity.

**Files**

- `experiments/neural-showcase-v3/functions/api/product/downloads.ts`
- `experiments/neural-showcase-v3/src/pages/Install.tsx`
- `experiments/neural-showcase-v3/src/pages/Pitch.tsx`
- `experiments/neural-showcase-v3/src/components/GlobalCommandPalette.tsx`
- `experiments/neural-showcase-v3/public/og.svg`
- `experiments/neural-showcase-v3/public/og-install.svg`
- `docs/CHANGELOG_AGENTS.md` (this entry)
- `docs/CHANGELOG_PUBLIC.md` (regenerated by v3 `prebuild`)

*(external)* `…/meeet-solana-state-941a6045/supabase/functions/tars-downloads/index.ts`

## 2026-05-03 — Cursor [F] · Cockpit ⌘J jump palette (JumpPalette)

**Summary**

Ships the cockpit **⌘J / Ctrl+J** navigation palette backed by
`POST /api/search/jump`: fuzzy list over threads, attachments,
saved searches, packs, playbooks. Activation: threads + attachments
→ `tars:open-thread`; packs → `/cockpit?pack=`; playbooks + saved
searches → `tars:operator-palette-prefill` (opens ⌘. with query
pre-filled). New `JumpPalette.tsx`, `fetchJump` + types in
`lib/search.ts`, Vitest `jump.test.ts`. `OperatorPalette` listens
for `tars:operator-palette-prefill`. ⌘K empty-state hints mention
⌘J. IDEAS: Cmd+J + BM25 highlight rows updated.

**Files**

- `experiments/neural-showcase-v3/src/components/JumpPalette.tsx`
- `experiments/neural-showcase-v3/src/lib/search.ts`
- `experiments/neural-showcase-v3/src/lib/jump.test.ts`
- `experiments/neural-showcase-v3/src/components/OperatorPalette.tsx`
- `experiments/neural-showcase-v3/src/components/CommandPalette.tsx`
- `experiments/neural-showcase-v3/src/pages/Cockpit.tsx`
- `docs/IDEAS.md`
- `docs/CHANGELOG_AGENTS.md` (this entry)
- `docs/CHANGELOG_PUBLIC.md` (regenerated)

## 2026-05-03 — Cursor [E] · Release gate + downloads footer + voice doc

**Summary**

- `scripts/gate_release.sh` — new step **cockpit-changelog-check**
  before cockpit-tsc (parity with Makefile / Cloudflare CI).
- `DownloadStrip` footer variant — compact **✓ sha256** affordance
  when the primary artifact carries a checksum (`data-sha256` on
  the link unchanged).
- New operator checklist `docs/VOICE_CLONING_OPERATOR.md`
  (ElevenLabs IVC → `TARS_PERSONA_OPERATOR_ELEVENLABS_ID`).
- `docs/IDEAS.md` — voice cloning item points at the doc;
  verify-on-download marked shipped (hero + footer).

**Files**

- `scripts/gate_release.sh`
- `experiments/neural-showcase-v3/src/components/DownloadStrip.tsx`
- `docs/VOICE_CLONING_OPERATOR.md` (new)
- `docs/IDEAS.md`
- `docs/CHANGELOG_AGENTS.md` (this entry)
- `docs/CHANGELOG_PUBLIC.md` (regenerated)

## 2026-05-03 — Cursor [D] · Clickable chunk citations in ChatPane

**Summary**

Assistant / system message bodies now turn `[citation_id]` tokens
into inline pills when the id exists in persisted sources or live
retrieval; click opens the sources footer and scrolls to the
matching `<li id="tars-source-…">`. New pure helper
`splitChunkCitations` in `src/lib/chunkCitations.ts` + Vitest
suite. Makefile gains `cockpit-changelog-check` and
`gate-control-tower` / `test-all` run it before Vitest (matches
Cloudflare Pages CI).

**Files**

- `experiments/neural-showcase-v3/src/lib/chunkCitations.ts`
- `experiments/neural-showcase-v3/src/lib/chunkCitations.test.ts`
- `experiments/neural-showcase-v3/src/components/ChatPane.tsx`
- `Makefile` (`cockpit-changelog-check`, wire `test-all` +
  `gate-control-tower`)
- `docs/IDEAS.md` (mark citation rendering shipped)
- `docs/CHANGELOG_AGENTS.md` (this entry)
- `docs/CHANGELOG_PUBLIC.md` (regenerated)

## 2026-05-03 — Cursor [C] · CI guard for public changelog + IDEAS sync

**Summary**

Cloudflare Pages workflow now runs
`python3 scripts/generate_public_changelog.py --check` before
`npm ci`, so a PR that appends to `CHANGELOG_AGENTS.md` without
regenerating `CHANGELOG_PUBLIC.md` fails CI (the committed GitHub
view stays aligned with what marketing builds). Workflow `paths`
also include `docs/CHANGELOG_{AGENTS,PUBLIC}.md` and
`scripts/generate_public_changelog.py` so changelog-only edits
still trigger the full cockpit gate.

`docs/IDEAS.md` — marked **Cross-thread search** and **BM25 via
SQLite FTS5** as shipped (Phase L8); both were stale relative to
`backend/core/search/` and `POST /api/search`.

**Files**

- `.github/workflows/tars-meeet-cloudflare-pages.yml`
- `docs/IDEAS.md`
- `docs/CHANGELOG_AGENTS.md` (this entry)
- `docs/CHANGELOG_PUBLIC.md` (regenerated)

## 2026-05-03 — Cursor [A] · session closeout audit

**Summary**

Wrote `docs/SYSTEM_AUDIT_2026-05-03.md` — the closeout audit for
the multi-PR operator-surface batch (PR #136 → PR #144). All 9
critical bugs from `SYSTEM_AUDIT_2026-05-02.md` are closed; the
backend test suite is fully green for the first time since PR #60
broke `attachments/index.py` (2315 passed). Cockpit vitest at
328 passed across 22 files. Five new operator surfaces shipped
(`/cockpit/{traces,policy,council,awareness}` + `⌘.` palette),
multimodal image routing reaches Claude / gpt-4o natively, and
the `/changelog` chunk is 63% smaller. Three remaining items are
explicitly out of autonomous scope (live cloud creds, code
signing, live Stripe) and documented with the exact missing
inputs.

`docs/AGENT_HANDOFF.md` updated with the same batch summary in
the "Done (running list, latest first)" section so the next agent
can pick up cleanly.

**Files**

- `docs/SYSTEM_AUDIT_2026-05-03.md` (new, 168 lines)
- `docs/AGENT_HANDOFF.md` (added 2026-05-02/03 closeout block at
  the top of the running list)

## 2026-05-03 — Cursor [B] · `/changelog` chunk -63% (PR #144)

**Summary**

The `/changelog` page bundled the entire `CHANGELOG_AGENTS.md`
(551 KB, 172 entries) as a raw import — the resulting Changelog
chunk was 560 KB raw / 188 KB gzip, larger than the entire
cockpit shell. Worse, this grows every time any agent appends to
the per-edit log.

`scripts/generate_public_changelog.py` splits the source on
`## ` headers and writes `docs/CHANGELOG_PUBLIC.md` with the
most recent 60 entries plus a "view full history on GitHub"
footer. The cockpit imports the public file instead. Wired into
the cockpit lifecycle as `predev` / `prebuild` npm hooks (so
both dev runs and production builds always see fresh content),
with a `changelog:check` script (and a CLI `--check` flag) for
optional CI guard against forgotten regenerations.

**Build delta**

- `Changelog-*.js` raw: 560 KB → 216 KB (-62%)
- `Changelog-*.js` gzip: 188 KB → 69 KB (-63%)
- All other chunks unchanged
- Vitest: 328 passed (no regressions)

**Files**

- `scripts/generate_public_changelog.py` (new, 117 lines)
- `docs/CHANGELOG_PUBLIC.md` (new, generated, 210 KB)
- `experiments/neural-showcase-v3/package.json` (predev /
  prebuild hooks + `changelog:check` script)
- `experiments/neural-showcase-v3/src/pages/Changelog.tsx`
  (import switched to `CHANGELOG_PUBLIC.md`)

## 2026-05-03 — Cursor [B] · Unified duplicate `reembed` route (PR #143)

**Summary**

`POST /api/chat/attachments/{id}/reembed` had two FastAPI route
registrations in `web_extras/routers/chat.py` — the first
("promote-style", from `pipeline.reembed_attachment`) shadowed
the second ("force/batch-style", from `reembed.reembed_attachment`)
because FastAPI dispatches by registration order. This had been
silently breaking `tests/test_attachment_reembed.py::test_http_reembed_attachment_round_trip`
ever since the second endpoint was added — the test was written
for the shadowed contract that was never actually live.

Unified the two endpoints into a single dispatcher route that
inspects the request body: `force` or `target_model` → batch
impl; otherwise → promote impl. The response shape is widened to
satisfy both original test contracts. After this PR, the entire
backend test suite is fully green (2315 passed, 1 skipped, 2
xfailed).

**Files**

- `web_extras/routers/chat.py` (collapsed two routes into one,
  -47 lines net)
- `docs/CHANGELOG_AGENTS.md` (this entry)

## 2026-05-02 — Cursor [B] · Image vision routing (multimodal voices)

**Summary**

Closes the open follow-up of IDEAS line 63 — Anthropic Claude and
OpenAI gpt-4o family voices now receive image bytes natively
instead of just the OCR text-block fallback. The vision agent
already produced `VisionPayload.image_refs` with `(attachment_id,
mime, storage_path)` triples; this PR finally threads those refs
to the cloud voices and packs them into the request payload.

**Anatomy**

- `backend/core/chat/multimodal.py` — pure helpers
  `pack_anthropic_image_blocks` / `pack_openai_image_blocks` plus
  mime + base64 utilities. Budget-aware (6 images per turn,
  5 MiB per image, 18 MiB total pre-encode). Silently drops
  unsupported mimes / oversize / unreadable files so a multimodal
  turn never breaks.
- `backend/core/chat/voices.py`:
  - Abstract `ChatVoice.stream` now accepts `image_refs` kwarg.
  - `_to_anthropic_messages` / `_to_openai_messages` widen the
    **last** user turn into a content-block list only when
    `image_blocks` are passed (text-only turns stay simple strings).
  - `AnthropicChatVoice.stream` / `OpenAIChatVoice.stream` call
    the matching multimodal packer and inject blocks.
  - `LocalChatVoice.stream` accepts (and ignores) the kwarg to
    keep the abstract signature uniform.
- `backend/core/chat/orchestrator.py`: when the chosen voice
  declares `supports_multimodal=True` AND `vision_payload.has_images`,
  pass `image_refs=…` via `**voice_kwargs`. Critical: only forward
  when non-empty so legacy / third-party `ChatVoice` subclasses
  (and the `_ScriptedVoice` mock in tests) keep working with their
  pre-multimodal `stream` signatures.

**Files**

- `backend/core/chat/multimodal.py` (new, ~245 lines).
- `backend/core/chat/voices.py` (helpers + voices wiring).
- `backend/core/chat/orchestrator.py` (kwarg-conditional plumbing).
- `tests/test_chat_multimodal.py` (new, 39 cases).
- `tests/test_chat_voices_multimodal.py` (new, 9 cases — Anthropic
  + OpenAI shape integration plus LocalChatVoice safety).
- `docs/IDEAS.md` line 63 marked shipped.

**Test deltas**

- Backend full sweep: **2314 passed**, 1 skipped, 2 xfailed
  (was 2266 after PR #141; +48 multimodal). The single remaining
  failure
  (`test_attachment_reembed.py::test_http_reembed_attachment_round_trip`)
  is the pre-existing duplicate-route bug carried over from PR
  #141 — not regressed by this change.

## 2026-05-02 — Cursor [A] · Awareness explorer (`/cockpit/awareness`)

**Summary**

Closes IDEAS #30 — backend
`GET /api/domains/<slug>/awareness/<id>/snapshot` shipped Phase
K-A; this PR is the design-side surface that finally lets the
operator browse every awareness source per pack and snapshot
live feeds on demand. Caps the operator-surface batch alongside
Trace Viewer (#136), Policy Inbox (#137), Council Debug (#138),
Operator Palette (#139).

**Anatomy**

- Three-column workspace: pack rail (with awareness-count + live
  badge) → source rail (search + kind chip + last-fetched stamp)
  → snapshot pane (config preview + live data + took / fetched /
  trace badges).
- URL state: `?slug=`, `?source=`, `?q=` for deep-linkable
  navigation (so the operator palette can route operators here
  with a single click).
- Snapshot button is disabled for config-only sources (no live
  fetcher) and surfaces the daemon's `fetcher_unavailable`
  envelope inline. 500s render their `state.error` in the same
  red banner so the operator can grep daemon logs by `trace_id`.
- Per-source render state held by an in-page dictionary keyed on
  `(slug, source_id)` — every snapshot is independent and the
  page never refetches on selection.
- Pure helpers in `lib/awarenessFmt.ts` (kind tone, fmtTookMs,
  fmtAgo, prettyJson, filterAwareness, pickSlug, totalSourceCount,
  liveSourceCount, snapshotKey/emptySnapshotState) are
  side-effect-free and unit-tested in isolation (29 vitest cases).
- EN + RU strings shipped at parity (40 keys per locale).

**Files**

- `experiments/neural-showcase-v3/src/pages/Awareness.tsx` (new,
  ~520 lines).
- `experiments/neural-showcase-v3/src/lib/awarenessFmt.ts` (new,
  ~140 lines).
- `experiments/neural-showcase-v3/src/lib/i18n.tsx` (+40 EN keys
  + 40 RU translations).
- `experiments/neural-showcase-v3/src/App.tsx` (lazy import +
  `/cockpit/awareness` route).
- `experiments/neural-showcase-v3/src/pages/Cockpit.tsx` (nav
  link).
- New tests: `awarenessFmt.test.ts` (29 cases — kind routing,
  duration / age formatters, snapshot envelope state, slug
  picker, source filter, count helpers, JSON tolerance).

**Test deltas**

- Cockpit: `pnpm vitest run` → **328 passed** (was 299; +29
  awarenessFmt).
- Cockpit: `pnpm tsc -b && pnpm build` → green; cockpit chunk
  unchanged (197 KB) since Awareness lazy-loads into its own
  chunk.
- i18n parity guard kept at 100% RU coverage.

## 2026-05-02 — Cursor [A] · Operator command palette (⌘. / Ctrl+.)

**Summary**

Closes IDEAS #20 — the cockpit's existing ⌘K palette is a search
surface (chunks / messages / traces); this PR ships the
*action* counterpart: a fuzzy index over **packs**, **pack
actions**, **playbooks**, **awareness sources**, and the most
**recent traces**. Bound to ⌘. (period) so it never collides
with ⌘K.

**Anatomy**

- `lib/operatorPalette.ts` — pure helpers (no React, no DOM):
  `OperatorEntry` / `OperatorIndex` types, shapers per resource
  (`shapePack` / `shapeAction` / `shapeAwareness` / `shapePlaybook`
  / `shapeTrace`), `loadOperatorIndex` (parallel-safe loader with
  per-group error capture), `fuzzyScore` + `rankEntries` (subsequence
  scorer with title-prefix + pack bonuses), `filterByGroup` /
  `groupCounts` / `totalCount`, `loadRecentIds` / `pushRecent` /
  `pickRecent` (localStorage-backed top-5), and `entryHref` for
  pack / trace deep-links.
- `components/OperatorPalette.tsx` — modal overlay with focus trap,
  group filter chips with live counts, partial-failure banner,
  result strip, and per-row activation badge that routes by kind:
  pack / trace navigate; action / awareness / playbook invoke
  through the existing API clients (`invokeAction`,
  `snapshotAwareness`, `runPlaybook`). Destructive actions surface
  the policy gate's "blocked, approve via inbox" path with an
  amber toast.
- `pages/Cockpit.tsx` — mounts `<OperatorPalette/>` next to
  the existing `<CommandPalette/>`; activations route through
  `toast.success` / `toast.warn` / `toast.error`.
- `lib/i18n.tsx` — 38 EN keys + 38 RU translations for every
  surface (placeholder / chips / kind labels / activation outcomes
  / refresh / footer hints).

**Test deltas**

- Cockpit: `pnpm vitest run` → **299 passed** (was 267; +32
  operatorPalette).
- Cockpit: `pnpm tsc -b && pnpm build` → green; cockpit chunk
  grew 182KB → 197KB.
- i18n parity guard kept at 100% RU coverage.

## 2026-05-02 — Cursor [A] · Council Debug page (`/cockpit/council`)

**Summary**

Closes IDEAS #18 — backend `/api/council/deliberate` shipped Phase
K-C, every deliberation already drops a `sampler.decision` event
into the meeet trail, but a dedicated full-page operator surface
that exposes the dual-voice diff (confidence bars, agreement %,
contradictions, latency) had been waiting on a design pass. This
PR ships it.

**Anatomy**

- Sticky header: back to cockpit, refresh history.
- Two-column workspace:
  - Left rail: stage form (prompt + context JSON + mode), live
    JSON-validity badge that swaps in `{}` on parse fail (so the
    operator never silently sends an invalid object), and a
    newest-first history of `sampler.decision` events
    (winner / agreement / mode / time + stance pill).
  - Right pane: rendered deliberation. Six-stat header (chosen /
    agreement / mode / total tokens / total latency / voice count)
    + per-voice card grid with stance pill, **confidence bar**,
    summary, recommended actions, rationale, latency, tokens.
    Highest-confidence voice marked with a "★ winner" pill +
    accent border. Unavailable voices render an explicit
    explainer instead of the bar (matches orchestrator's
    `stance="unavailable"` filter).
  - Contradictions list rendered below; explicit "no contradictions
    surfaced" copy when empty.
- Polling: history @ 6 s (matches existing OperatorStrip cadence).
- New cockpit nav link (`cockpit · planner · traces · policy ·
  council`).

**Files**

- `experiments/neural-showcase-v3/src/pages/Council.tsx` (new,
  ~480 lines).
- `experiments/neural-showcase-v3/src/lib/councilFmt.ts` (new,
  ~110 lines — pure helpers: `stanceTone`, `fmtConfidencePct`,
  `confidenceWidth`, `pickWinningVoice`, `rollupVoices`,
  `fmtLatencyMs`, `normaliseStance`).
- `experiments/neural-showcase-v3/src/lib/i18n.tsx` (+38 EN keys
  + 38 RU translations for the council surface).
- `experiments/neural-showcase-v3/src/App.tsx` (lazy import + route).
- `experiments/neural-showcase-v3/src/pages/Cockpit.tsx` (nav link).
- New tests: `councilFmt.test.ts` (20 cases — stance routing,
  confidence clamp, winner pick, rollup tolerance to NaN,
  latency formatter).

**Test deltas**

- Cockpit: `pnpm vitest run` → **267 passed** (was 247; +20
  councilFmt).
- Cockpit: `pnpm tsc -b && pnpm build` → green.
- Backend: `pytest tests/test_council.py tests/test_meeet.py
  tests/test_meeet_contract.py` → **22 passed** (touched
  surfaces; no regressions).

## 2026-05-02 — Cursor [A] · Policy Inbox page (`/cockpit/policy`)

**Summary**

Closes IDEAS #29 — backend `/api/policy/{pending,recent,confirm,
cancel,expire}` shipped Phase K-D, `<OperatorStrip />` had a barebones
list, but a dedicated full-page operator surface for the destructive-
action queue had been waiting on a design pass. This PR ships it.

**Anatomy**

- Sticky header: back to cockpit, refresh, expire-stale (admin).
- Tab strip: pending / recent (each tab carries its own count).
- Filter strip: free-text search box (matches token / slug /
  action / requested_by / trace_id substrings, case-insensitive).
- Two-column workspace:
  - 380 px left rail with status pill, slug.action, age, time-to-
    expire (pending only), requested_by, token.
  - Right pane drill-down: copy-to-clipboard token, six-stat dl
    grid (token / created / expires / requested_by / trace / status),
    full args / result JSON dumps, confirm + cancel affordances.
- **Confirm modal**: an `alertdialog` with focus trap + ESC close +
  click-outside dismiss so the operator can never one-click a
  destructive action by mistake. Message interpolates the action
  slug + trace_id so the consequences are visible at the point of
  decision.
- Polling: pending @ 4 s, recent @ 8 s. Optimistic re-fetch after
  every confirm/cancel/expire so the rail catches up within one
  tick.
- URL state via `?tab=…&selected=…&q=…` (deep-linkable).
- New cockpit nav link (`cockpit · planner · traces · policy`).

**Files**

- `experiments/neural-showcase-v3/src/pages/Policy.tsx` (new, ~590 lines).
- `experiments/neural-showcase-v3/src/lib/policyFmt.ts` (new, ~140
  lines — pure helpers: `statusTone`, `fmtAge`, `fmtTimeLeft`,
  `compareConfirmationsNewestFirst`, `matchesQuery`, `ALL_STATUSES`).
- `experiments/neural-showcase-v3/src/lib/policy.ts` (+
  `useRecentConfirmations` hook).
- `experiments/neural-showcase-v3/src/lib/i18n.tsx` (+39 EN keys
  + 39 RU translations for the policy surface).
- `experiments/neural-showcase-v3/src/App.tsx` (lazy import + route).
- `experiments/neural-showcase-v3/src/pages/Cockpit.tsx` (nav link).
- New tests: `policyFmt.test.ts` (16 cases — status tone / age
  / time-left / sort / match), `policy.test.ts` (10 cases — list /
  confirm / cancel / expire wire shape + error envelopes).

**Test deltas**

- Cockpit: `pnpm vitest run` → **247 passed** (was 221; +16
  policyFmt, +10 policy).
- Cockpit: `pnpm tsc -b && pnpm build` → green.
- Backend: `pytest tests/` → **2249 passed, 1 skipped, 2 xfailed**
  (no regressions; pure cockpit-surface PR).

## 2026-05-01 — Cursor [A] · Re-embed attachments on demand

**Summary**

Operator workflow: install TARS, leave it on the offline
`HashEmbedder`, ingest a few months of attachments, *then*
configure `OPENAI_API_KEY` for the upgrade. Until now those
historical chunks stayed on the cheap embedder and silently
under-performed semantic recall. This slot is the **promote-on-
demand** path: hit one endpoint and the affected chunks re-embed
in place. New attachments already pick the better embedder, so
this only catches up the back-catalog.

1. **Storage primitives** (`backend/core/attachments/index.py`)
   - `AttachmentStore.update_chunk_embedding(chunk_id, model, dim,
     vector)` — single-row in-place rewrite. Returns `True` only
     when the row exists. Same `pack_vector(...)` discipline as
     the ingest path.
   - `AttachmentStore.list_chunks_by_model(embedding_model,
     thread_id?, limit)` — find chunks at a given model
     (`None` matches "never embedded"). Optional `thread_id`
     scope, `limit` defaults to 500. Used both by the orchestrator
     and the future cockpit "stuck on hash" badge.

2. **Orchestrator** (`backend/core/attachments/reembed.py`, new)
   - `reembed_chunks(chunks, *, embedder, force, target_model)`
     — base helper. Skips blank text (counted as
     `skipped_blank`), skips chunks already at the target model
     (counted as `skipped_same`) unless `force=True`. Per-batch
     upstream failures bump `failed`; nothing raises.
   - `reembed_attachment(attachment_id, ...)` — fetch every chunk
     for one attachment and call the base helper. 404 surfaces as
     `{ok: False, reason: "attachment_not_found"}`.
   - `reembed_by_model(old_model, *, thread_id?, limit, ...)` —
     list-by-model + reembed in one call. The "promote
     hash → openai" workflow: pass
     `old_model="tars-hash-bigram-v1-d384"` and the active
     embedder runs over every legacy row.

3. **HTTP** (`web_extras/routers/chat.py`)
   - `POST /api/chat/attachments/{attachment_id}/reembed` — body
     `{force?, target_model?}`. 404 when the id is missing;
     otherwise the orchestrator stats dict.
   - `POST /api/chat/attachments/reembed-by-model` — body
     `{old_model (required), thread_id?, limit?, force?,
     target_model?}`. 400 on missing `old_model`; garbage
     `limit` falls back to 500. Designed for the
     "I just configured `OPENAI_API_KEY`" promotion.

4. **Tests** (`tests/test_attachment_reembed.py`, 18 cases)
   - Storage helpers: in-place update writes, returns False for
     missing id, list-by-model filters and scopes to thread.
   - Orchestrator: blank-text skip, "same model" skip without
     force, force rewrite, embedder-unavailable → ok=False,
     batch failure isolation, attachment 404, `reembed_by_model`
     promotes only the matching rows and respects `thread_id`.
   - HTTP: per-attachment round-trip + 404, `old_model` required,
     promotion writes through, garbage `limit` clamped.

**Files**

- `backend/core/attachments/reembed.py` (new)
- `backend/core/attachments/index.py` (added
  `update_chunk_embedding`, `list_chunks_by_model`)
- `web_extras/routers/chat.py` (two new endpoints)
- `tests/test_attachment_reembed.py` (new, 18 cases)

**Verification:** full backend suite **1027 passed**, lints
clean.

## 2026-05-02 — Cursor [A] · audit follow-ups: full RU pass + Local Trace Viewer

**Summary**

Two cleanup follow-ups on top of PR #135:

1. **Full RU translation pass** — closes the partial-coverage gap
   left by Bug #5. The previous PR shipped the i18n foundation +
   the 7 highest-visibility surfaces; this PR extends `STRINGS_RU`
   to full key parity with `STRINGS_EN` (~150 keys: hero, sticky
   CTA, waitlist, cookie, footer, pricing, FAQ, compare,
   TrustStrip, MeetTars, DomainsCards, full onboarding,
   custom-role modal, press kit, build-with badge, common chrome,
   cockpit chat composer + threads-empty, locale switcher).
   Translations follow the in-file style guide ("вы" not "Вы",
   product names stay Latin, `cap` → `лимит`, `council` → `совет`).
   The test suite gains a **coverage threshold guard** that
   enforces 100% RU parity at CI time so future PRs can't
   regress; orphan-key + interpolation-slot + non-empty-value
   guards back it up.

2. **Local Trace Viewer page (`/cockpit/traces`)** — closes the
   pending IDEAS #15 design follow-up. Backend
   `/api/meeet/traces`, `/api/meeet/traces/{trace_id}`,
   `/api/meeet/traces/refresh`, `/api/meeet/events?trace_id=…`
   already shipped Phase L8; this PR is the operator-facing
   surface that finally makes the local "black box" browsable.
   Anatomy: sticky header (back to cockpit, refresh, rebuild
   rollup) + filter strip (route lozenges + free-text search
   over trace_id / kind / session_id) + 360 px left rail with
   trace summaries (kind list, route pill, cost, duration,
   error count) + drill-down detail with copy-to-clipboard
   trace_id, six-stat dl grid (cost / tokens / duration /
   started / session / contradictions), and the full event
   timeline pulled from `/api/meeet/events?trace_id=…`. URL
   state via `?selected=…&route=…&q=…` so the page is
   deep-linkable. Polls every 5 s; respects existing cockpit
   accent + alert + amber tokens (no rainbow neon). New cockpit
   nav link + new client helpers (`listTraces`, `getTrace`,
   `refreshTraces`, `useTraceSummaries`) + new pure helper
   module `lib/traces.ts` (route filter coercion, route → tone
   map, locale-aware cost / duration / timestamp formatters).

**Files**

- i18n: `experiments/neural-showcase-v3/src/lib/i18n.tsx` (+150
  RU keys + 32 trace-viewer keys),
  `experiments/neural-showcase-v3/src/lib/i18n.test.ts`
  (added coverage / interpolation-slot / non-empty-value
  guards; +5 contract tests).
- Trace viewer:
  `experiments/neural-showcase-v3/src/pages/Traces.tsx` (new,
  500 lines),
  `experiments/neural-showcase-v3/src/lib/traces.ts` (new, 95
  lines — pure helpers),
  `experiments/neural-showcase-v3/src/lib/traces.test.ts` (new,
  +15 contract tests),
  `experiments/neural-showcase-v3/src/lib/meeet.ts` (+
  `listTraces` / `getTrace` / `refreshTraces` /
  `useTraceSummaries` helpers, plus `TraceSummary` /
  optional `session_id` + `route` on `MeeetEvent`),
  `experiments/neural-showcase-v3/src/lib/meeet.test.ts` (new,
  +13 contract tests),
  `experiments/neural-showcase-v3/src/App.tsx` (lazy import +
  route registration),
  `experiments/neural-showcase-v3/src/pages/Cockpit.tsx`
  (cockpit nav link).

**Test deltas**

- Cockpit: `pnpm vitest run` → **221 passed** (was 190; +31:
  +5 i18n, +13 meeet, +15 traces; existing planner / pairing /
  recovery / etc. all still green).
- Cockpit: `pnpm tsc -b && pnpm build` → green; `Traces.tsx`
  ships as a 14 kB / 4.4 kB gzipped lazy-loaded chunk so it
  doesn't bloat the landing entry.
- Backend: `pytest tests/` → **2249 passed, 1 skipped, 2
  xfailed** (no regressions; pure cockpit-surface PR).

## 2026-05-02 — Cursor [A] · system audit closeout (PR #135 — all 8 bugs)

**Summary**

End-to-end follow-up to `docs/SYSTEM_AUDIT_2026-05-02.md`. PR #135
closes **every audit finding** in 3 rebased-on-main commits
(`c27831f` + `641694c` + `f8e889b`):

| Bug | What landed | Tests |
|-----|-------------|-------|
| #2 | `web_extras/entitlements_gate.py::require_cloud_budget` wired into chat / planner / voice / council; HTTP 402 + `payment_required`; `entitlements.cap_hit` event with `surface` label | +7 contract |
| #3 | `TARS_PAYMENT_MODE` env (off / mock / stripe); upgrade emits `entitlements.upgraded.mock`; Pricing UI shows `COMING SOON` lozenge + waitlist CTAs | +5 contract |
| #4 | `ExpensiveRoutesRateLimitMiddleware` (Starlette) — per-IP token bucket on chat / planner / voice / council; HTTP 429 + Retry-After; XFF support; `TARS_RATE_LIMIT_EXPENSIVE` kill switch | +6 contract |
| #5 | `src/lib/i18n.tsx` LocaleProvider + RU translations for hero / waitlist / cookie / footer / pricing / locale.\*; `<LocaleSwitcher/>` in Footer; `localStorage["tars.locale"]` persistence | +9 contract (Vitest) |
| #6 | Removed 30 orphan `__pycache__` directories (i18n, economy, awareness, brain, knowledge_graph, …); regression guard | +1 regression |
| #7 | `SplineScene.tsx` IntersectionObserver guard — defers the 4 MB `react-spline` + `physics` chunks until host element ≤ 600 px from viewport | covered by existing vitest |
| #8 | `.cursorrules` / `.cursor/rules/tars-architecture.mdc` / `CLAUDE.md` rewritten to point at `experiments/neural-showcase-v3/`; marked `frontend/` and `backend/core/awareness/` as retired | n/a (docs) |
| #9 | `desktop/src-tauri/tauri.conf.json` updater endpoint switched to GitHub Releases; `release-desktop-tagged.yml` adds `includeUpdaterJson: true`; `DEFAULT_MANIFEST` URLs point at GitHub Releases pattern; converted xfail → passing | +4 contract |

**Test deltas**

- Backend: `pytest tests/` → **2249 passed, 1 skipped, 2 xfailed**
  (was 2225/1/3; +22 new tests, 1 xfail closed, no regressions).
- Cockpit: `pnpm vitest run` → **190 passed** (was 181; +9 i18n
  tests).
- Cockpit: `pnpm build` green; bundle sizes unchanged but the
  4 MB visual-flair chunks now load lazily.

**Migration notes (env defaults flipped)**

- `TARS_CAP_ENFORCEMENT` — defaults `on` in production. Test
  suite flips `off` via `tests/conftest.py`. FREE-tier dev shells
  must set `off` or upgrade with `TARS_PAYMENT_MODE=mock`.
- `TARS_PAYMENT_MODE` — defaults `off` (paid upgrades return 503
  `feature_disabled`). Set `mock` in dev. `stripe` lane stubbed
  for the next PR.
- `TARS_RATE_LIMIT_EXPENSIVE` — defaults `on` (per-IP throttle on
  chat / planner / voice / council). Set `off` for single-operator
  self-hosted boxes.

**Parallel main-branch fix folded in (`f8e889b`)**

While the audit branch was in flight, two commits on `main`
(`6fbfb93` + `5984733`) bumped `tauri.conf.json` and `Cargo.toml`
to `8.4.0` for MSI compatibility but skipped
`desktop/package.json`. The PR rebased onto main inherited the
divergence and the `desktop · version lint` workflow started
failing. Folded the missing bump into the audit PR; all three
desktop version sources now agree on `8.4.0`. Pure infra fix —
no behaviour change.

**Files**

- Backend (Bug #2 + #4): `web_extras/entitlements_gate.py`,
  `web_extras/middleware/__init__.py`,
  `web_extras/middleware/expensive_routes_rate_limit.py`,
  `web_extras/app.py`, `web_extras/errors.py`,
  `web_extras/routers/{voice,council,planner,chat,entitlements}.py`,
  `tests/conftest.py`,
  `tests/test_entitlements_gate.py`,
  `tests/test_rate_limit_expensive_routes.py`,
  `tests/test_entitlements.py`.
- Backend (Bug #6): deleted `backend/core/{i18n,economy,…}/` (30
  orphan dirs), `tests/test_no_orphan_pycache.py`.
- Backend (Bug #9): `backend/core/product/manifest.py`,
  `tests/test_product_default_manifest_urls.py`,
  `tests/test_release_desktop_workflow.py`.
- Cockpit (Bug #5): `experiments/neural-showcase-v3/src/lib/i18n.tsx`
  (renamed from .ts), `src/main.tsx`,
  `src/components/{LocaleSwitcher,Footer}.tsx`,
  `src/lib/i18n.test.ts`.
- Cockpit (Bug #3): `experiments/neural-showcase-v3/src/components/Pricing.tsx`.
- Cockpit (Bug #7): `experiments/neural-showcase-v3/src/components/SplineScene.tsx`.
- CI / Tauri (Bug #9): `.github/workflows/release-desktop-tagged.yml`,
  `desktop/src-tauri/tauri.conf.json`.
- Desktop infra (folded fix): `desktop/package.json`,
  `desktop/src-tauri/tauri.conf.json` (formatting + version
  alignment).
- Docs (Bug #8): `.cursorrules`, `.cursor/rules/tars-architecture.mdc`,
  `CLAUDE.md`, `docs/SYSTEM_AUDIT_2026-05-02.md` (resolution
  log).

**Verification**

- `pytest tests/` (backend, all green).
- `pnpm vitest run` + `pnpm build` (cockpit, all green).
- `desktop · version lint` GitHub Actions: triple-version match
  enforced; rebase + folded fix unblocks the gate.

## 2026-05-02 — Cursor [A] · cron-shipped morning bundle wrapper

**Summary**

Ships `scripts/playbooks_morning_cron.sh` + `make morning-bundle` /
`make morning-bundle-dry` targets. **Single command** for cron to
run every `morning`-tagged playbook (currently 4:
`business.morning_brief`, `ops_room.morning_standup`,
`research_lab.paper_to_pitch`, `traders.morning_check`), flush the
meeet replay buffer, and write an aggregate evidence JSON.

The wrapper is **continue-on-failure** by default (one bad playbook
doesn't mask the others) with `MORNING_FAIL_FAST=1` for the legacy
stop-on-first-failure mode. Discovery is **tag-driven**: as new
`morning`-tagged playbooks land in `playbooks/`, they join the cron
bundle automatically — no script edit required.

Three exit-code lanes so cron alerts can route differently:
- `0` — every playbook ok
- `1` — at least one playbook failed
- `2` — operator error (no playbooks discovered, missing dep)

**Why this matters**: closes the Cron-as-First-Class-Operator arc.
The playbook CLI (PR #129) made cron-driven playbook execution
viable; this wrapper makes it *ergonomic*. Operator drops one line
in crontab:

```cron
0 6 * * 1-5  cd /path/to/jarvis && \
    MORNING_MODE=autopilot \
    /path/to/jarvis/scripts/playbooks_morning_cron.sh \
    >> /var/log/tars-morning.log 2>&1
```

**Changes**

1. `scripts/playbooks_morning_cron.sh` (new, 280 lines):
   - Tag-driven discovery via `playbooks_cli list` + JSON parse
     (operator override via `MORNING_PLAYBOOKS=id1,id2`).
   - Sequential execution; per-playbook stdout/stderr captured.
   - Aggregate evidence JSON sink at `$MORNING_OUTPUT_DIR/<run_id>.json`
     (default `.morning-runs/`). Filename matches printed run_id so
     `grep` finds it in one `ls`.
   - Final meeet `replay_cli` flush (skippable via
     `MORNING_SKIP_REPLAY=1` for upstream maintenance windows).
   - ANSI helpers degrade gracefully when stdout isn't a TTY (cron-safe).
   - All env knobs (`MORNING_PLAYBOOKS`, `MORNING_MODE`,
     `MORNING_OUTPUT_DIR`, `MORNING_SKIP_REPLAY`, `MORNING_FAIL_FAST`,
     `MORNING_TAG`, `PY`) documented in the header AND read by the script
     (test pins both directions).

2. `Makefile`:
   - New `morning-bundle` and `morning-bundle-dry` targets in
     `.PHONY`. `morning-bundle` accepts optional `MODE=` /
     `PLAYBOOKS=` for the common cron pattern;
     `morning-bundle-dry` hard-codes `MORNING_MODE=dry_run` so
     `make morning-bundle-dry` is *always* a safe rehearsal even
     if the operator has `MODE=autopilot` in env.

3. `.gitignore`: `.morning-runs/` and `.meeet-replays/` (the
   default sink dirs for the morning bundle and the per-run
   replay export — both should never be committed).

4. `tests/test_morning_bundle.py` (new, 23 tests, ~360 lines):
   - **Structural** (11 tests): script exists/executable, bash
     shebang, `bash -n` syntax check, every documented env knob
     is read by the script (catches doc drift in either
     direction), all three exit codes documented, script invokes
     the canonical `playbooks.cli` + `meeet.replay_cli` modules
     (no bespoke runner reimplementation).
   - **Makefile** (5 tests): both targets in `.PHONY`, both have
     `## help` comments, recipe invokes the wrapper script,
     dry-mode target hard-codes `MORNING_MODE=dry_run`.
   - **End-to-end smoke** (7 tests): no-playbooks → rc=2 +
     minimal evidence; happy override → rc=0 + full envelope;
     unknown playbook → rc=1 + `failed_ids`; mixed
     continue-on-failure → both playbooks recorded; fail-fast →
     stops + marks skipped as `aborted_by_fail_fast`; evidence
     filename matches printed run_id; `MORNING_SKIP_REPLAY=1`
     surfaces in evidence (so auditor can tell "skipped" from
     "upstream down").

**Tests**

- `pytest tests/test_morning_bundle.py` — 23/23 green.
- Full suite — 2227/2227 green.
- Manual smoke (5 modes verified before tests):
  default-discovery → 4 playbooks ok rc=0; bogus tag → rc=2 with
  no_playbooks_discovered evidence; bad id override → rc=1 with
  `failed_ids: ["no.such.playbook"]`; `MORNING_SKIP_REPLAY=1` →
  no flush, evidence shows `skipped: true`; mixed
  continue-on-failure → both runs recorded, rc=1.

**Files**

- `scripts/playbooks_morning_cron.sh` (new, +280)
- `Makefile` (+25, .PHONY + 2 targets + section header)
- `.gitignore` (+2, `.morning-runs/`, `.meeet-replays/`)
- `tests/test_morning_bundle.py` (new, +363)

## 2026-05-01 — Cursor [A] · awareness CLI bash completion (operator-CLI arc symmetry closed)

**Summary**

Ships `scripts/awareness-completion.bash` mirroring the
existing planner / playbooks completion scripts. **Closes the
operator-CLI arc symmetry**: every cockpit-facing TARS surface
(planner / awareness / playbook) now has HTTP route + `python -m
…` CLI + `make …-*` targets + bash completion script.

The awareness script handles a wrinkle the other two don't:
**two-level live positional completion** for the `snapshot`
subcommand. Positional 0 is a pack slug (live query against
`awareness_cli list`); positional 1 is a source id, scoped to
the chosen slug (live query against `awareness_cli list
<slug>`). The cache is keyed by slug name so completing slug A
then slug B doesn't pollute B's cache with A's source ids.

Avoids the `--quiet` flag-order bug from PR #130 by construction
(both query helpers invoke the CLI with `--quiet` BEFORE the
subcommand, pinned by test).

**The arc as it now stands**:

| Layer        | HTTP route                       | CLI module                              | Make targets         | Bash completion                          |
| ------------ | -------------------------------- | --------------------------------------- | -------------------- | ---------------------------------------- |
| Planner      | `web_extras/routers/planner.py`  | `backend.core.planner.cli`              | `make planner-*`     | `scripts/planner-completion.bash`        |
| Awareness    | `web_extras/routers/domains.py`  | `backend.core.domains.awareness_cli`    | `make awareness-*`   | `scripts/awareness-completion.bash` (NEW) |
| Playbook     | `web_extras/routers/playbooks.py`| `backend.core.playbooks.cli`            | `make playbooks-*`   | `scripts/playbooks-completion.bash`      |

Every surface now has the same operator-facing affordances:
inspect from cron, execute from cron, observe from cockpit (same
events emitted), tab-complete from any shell.

**Why ship awareness completion when the script is small?** Two
reasons:

1. **Two-level positional completion is the killer feature** —
   awareness sources live under `<slug>.<source_id>` namespacing
   so the operator can't reasonably memorize the source id for
   every pack. The script exposes them via tab.
2. **Cron-friendly slug discovery** — when wiring a pre-warm
   snapshot into cron (`make awareness-snapshot ARGS="<slug>
   <source_id>"`), tab-complete walks the operator through the
   full namespace without `--help` reads.

**Changes**

1. `scripts/awareness-completion.bash` (new, 240 lines):
   - Subcommand completion (`list`, `snapshot`, `snapshot-all`).
   - Per-snapshot flag table (`--thread-id`, `--trace-id`)
     grouped under one `snapshot|snapshot-all)` case (DRY).
   - **Live pack-slug completion** with a 5-second per-shell
     cache (mirrors the planner / playbooks scripts).
   - **Live per-pack source-id completion** with a separate
     5-second cache keyed by slug name (so completing slug A
     then slug B doesn't reuse A's data — explicitly pinned).
   - **Two-level positional walker**: counts non-flag words
     after the subcommand to decide which positional we're at;
     skips flag VALUES (`--thread-id thr_42`) so they don't
     get miscounted as positionals (also pinned).
   - `--quiet` invoked BEFORE the subcommand in both query
     helpers (avoids the bug fixed in PR #130, and explicitly
     asserted).

2. `tests/test_awareness_completion_script.py` (new, 9 tests):
   - Script exists + executable + shebang.
   - `bash -n` parses cleanly.
   - `_TARS_AWARENESS_CMDS` matches `cli._DISPATCH` keys (no
     drift).
   - Combined `snapshot|snapshot-all)` flag table includes
     `--thread-id` + `--trace-id`.
   - `list` case branch is intentionally empty (catch a
     future "add --pack to list" parser change as a test
     failure).
   - **Two caches**: `_TARS_AWARENESS_SLUGS_*` for the
     catalogue and `_TARS_AWARENESS_SOURCES_KEY/VAL/EXP` for
     the per-pack source list (pin the key-by-slug invariant).
   - `--quiet` invoked **before** the subcommand in both
     query helpers; the buggy `list --quiet` order is
     explicitly NOT in the script.
   - Two-level positional completion: snapshot's case branch
     checks `positional_idx == 0` (slug) and
     `positional_idx == 1` (source_id, scoped via
     `_tars_awareness_sources` with the typed slug).
   - Positional counter skips `--thread-id` / `--trace-id`
     VALUES (advances loop counter inside the inner case).

**Tests**

- `tests/test_awareness_completion_script.py` — 9 new tests,
  all green.
- Full suite: **2204 passed in 40.97s** (was 2195, +9).
- Smoke (sourced into bash):
  - `tars-awareness <TAB>` → `list snapshot snapshot-all`
  - `tars-awareness snapshot <TAB>` → 8 live pack slugs
    (business, mlm, entrepreneur, science, traders, wallet,
    research_lab, ops_room)
  - `tars-awareness snapshot traders <TAB>` → 5 live source
    ids for the traders pack (binance_ws, tradingview_alerts,
    news_feed, portfolio_local, local_alerts).

**Files**

- `scripts/awareness-completion.bash` (new, 240 lines).
- `tests/test_awareness_completion_script.py` (new, 9 tests).
- `docs/CHANGELOG_AGENTS.md`, `docs/AGENT_HANDOFF.md`.

**Follow-ups**

- Right-rail planner entrypoint from the cockpit chat thread
  (cancelled — ChatPane has no plan-aware protocol yet; needs
  product direction before we can wire the inline panel).
- Cron-shipped morning-bundle wrapper script
  (`scripts/playbooks_morning_cron.sh`) bundling traders /
  business / mlm morning playbooks + meeet replay flush;
  deferred until a concrete production schedule lands.

## 2026-05-01 — Cursor [A] · playbooks CLI: bash completion + planner script flag-order fix

**Summary**

Ships `scripts/playbooks-completion.bash` mirroring the
existing `scripts/planner-completion.bash` pattern: tab
completion for the six subcommands (`list`, `show`, `run`,
`validate`, `validate-all`, `reload`), per-subcommand flag
completion, **live playbook-id completion** sourced from the
CLI itself (5-second cache), and **filesystem-path
completion for `--context-file`** so the cron-friendly
sidecar-JSON workflow tab-completes the same as a plain
`vim path/to/file`.

While here, fixes a latent bug in the planner completion
script discovered during the smoke test: both scripts were
invoking `python -m backend.core.{planner,playbooks}.cli list
--quiet`, but `--quiet` is the **global** flag and must come
**before** the subcommand. The old order silently failed with
exit 2 and an empty completion list (the user got no
suggestions but also no error, so this never surfaced
through the test suite). Pin both fixes.

**Why ship a completion script when the playbook ID set is
small (6 today)?** Two reasons:

1. **Discoverability** — operators who don't know the
   playbook ID format (`<pack>.<name>`) get a live menu of
   what actually exists on disk. The same tab they'd use to
   complete a path now completes a playbook id.
2. **Cron template authoring** — `--context-file <TAB>` to
   pick the JSON sidecar, `--mode <TAB>` to pick from
   `autopilot|confirm|dry_run`, `<id> <TAB>` to verify the
   playbook still exists. The whole cron command now
   tab-completes end-to-end.

**Changes**

1. `scripts/playbooks-completion.bash` (new, 145 lines):
   - Subcommand completion + per-subcommand flag tables
     identical in shape to the planner script.
   - **Live playbook-id query** with a 5-second per-shell
     cache (mirrors the planner script's TTL exactly so
     the operator's mental model is uniform).
   - **`--context-file` ⇒ filesystem path completion** via
     a dedicated `compgen -f` branch. Pin: a future
     "simplify" must not collapse this into the free-form
     fallback (the cron-baked sidecar workflow depends on
     it).
   - **`--mode` ⇒ value completion** with the three
     `PolicyMode` values (`autopilot`, `confirm`, `dry_run`).
   - **id completion scoped to id-taking subcommands only**
     (`show|run|validate`) so a future "complete IDs
     everywhere" change doesn't silently shell out to
     Python on every tab inside `validate-all` /
     `reload` / `list`.

2. `scripts/planner-completion.bash`:
   - Fixed `python -m … cli list --quiet` →
     `python -m … cli --quiet list` (latent bug — argparse
     was rejecting `--quiet` as a positional after `list`,
     completion was returning an empty list).

3. `tests/test_playbooks_completion_script.py` (new, 10
   tests): contract pinning the script structure without
   sourcing it into a real subshell.
   - Script exists + executable + shebang.
   - `bash -n` parses cleanly (catches typos before the
     script lands on disk).
   - `_TARS_PLAYBOOKS_CMDS` lists every subcommand the
     CLI's `_DISPATCH` map declares (no drift between
     script and code).
   - Per-subcommand flag tables (parametrised over `list`
     / `show` / `run`) match the parser's flag declarations.
   - `--mode` value completion lists `autopilot confirm
     dry_run`.
   - `--context-file` triggers `compgen -f` (file-path
     completion).
   - Cache contract: `_TARS_PLAYBOOKS_CACHE_VAL`,
     `_TARS_PLAYBOOKS_CACHE_EXP`, 5-second TTL.
   - Live id completion scoped to `show|run|validate`
     only (the gating regex is pinned).

**Tests**

- `tests/test_playbooks_completion_script.py` — 10 new,
  all green.
- `tests/test_planner_completion_script.py` — 12, still all
  green after the flag-order fix (the existing tests didn't
  cover the runtime bug because they only assert structural
  properties).
- Full suite: **2195 passed in 41.23s** (was 2185, +10).
- Smoke (sourced into bash): subcommand tab returns
  `list show run validate validate-all reload`; `run <TAB>`
  returns the 6 live playbook ids from disk;
  `--context-file <TAB>` returns local files; `--mode <TAB>`
  returns the three policy modes.

**Files**

- `scripts/playbooks-completion.bash` (new, 145 lines).
- `scripts/planner-completion.bash` — flag-order fix.
- `tests/test_playbooks_completion_script.py` (new, 10
  tests).
- `docs/CHANGELOG_AGENTS.md`, `docs/AGENT_HANDOFF.md`.

**Follow-ups**

- Right-rail planner entrypoint from the cockpit chat thread
  (still pending).
- `awareness-completion.bash` for the awareness CLI (would
  give the same operator UX but the awareness ID set is
  pack-scoped so the live-id query is more involved;
  deferred until a concrete cron use case lands).

## 2026-05-01 — Cursor [A] · playbooks CLI parity (`python -m backend.core.playbooks.cli` + `playbooks-*` Make targets + `gate-control-tower` wiring)

**Summary**

Closes the third (and last) leg of the operator-parity arc:
**playbook execution** now has a shell-side equivalent at
`python -m backend.core.playbooks.cli` plus seven new Make
targets (`playbooks`, `playbooks-list`, `playbooks-show`,
`playbooks-run`, `playbooks-validate`, `playbooks-validate-all`,
`playbooks-reload`). The same playbooks the cockpit's
`POST /api/playbooks/<id>/run` route executes can now run from
`cron` without spinning the FastAPI process — emitted
`playbook.*` events still land in the local meeet buffer the
cockpit reads from, so dashboards count CLI runs the same as
HTTP runs.

The CI gate (`make gate-control-tower`) now runs
`playbooks-validate-all`, so a malformed playbook fails the
gate the moment it lands instead of waiting for a 5am cron
job to discover the typo. **This is the operator-facing
contract** that we couldn't ship before the CLI existed.

The arc as it now stands:

| Layer        | HTTP route                       | CLI module                              | Make targets         |
| ------------ | -------------------------------- | --------------------------------------- | -------------------- |
| Planner      | `web_extras/routers/planner.py`  | `backend.core.planner.cli`              | `make planner-*`     |
| Awareness    | `web_extras/routers/domains.py`  | `backend.core.domains.awareness_cli`    | `make awareness-*`   |
| **Playbook** | `web_extras/routers/playbooks.py`| `backend.core.playbooks.cli`            | `make playbooks-*`   |

Every cockpit-facing TARS surface that mutates state is now
reachable from cron + a venv, and emits the same meeet event
stream the HTTP route emits.

**Why now? Three concrete drivers:**

1. **Cron-driven brief execution** — `traders.morning_check`
   bakes the basket / news / portfolio snapshot triple into
   one playbook. Today wiring it into cron means a curl-in-cron
   loop with a hard-coded payload. The CLI variant skips the
   HTTP hop, surfaces a stable JSON envelope (with `trace_id`
   and `took_ms`), and the cron pattern reads cleanly:

       make playbooks-run ARGS=traders.morning_check \
                          MODE=autopilot \
                          CONTEXT='{"basket":["BTC","ETH"]}'

2. **Authoring loop** — `validate` / `validate-all` give a
   fast feedback signal when hand-editing
   `playbooks/<pack>/<name>.json`. The strict validator
   surfaces every issue in one pass instead of bouncing on
   each `run` attempt.
3. **Cold-start recovery** — when FastAPI is wedged, the CLI
   is the only path to materialise a multi-step action chain.

**Why wire `validate-all` into the gate (and not just expose
it)?** The validator already exists; the gap was an automatic
trigger. Without the gate hook, a malformed playbook would
sit on disk silent until a cron job hits the runner. With it,
the moment the bad file lands, `make gate-control-tower`
fails, and the operator sees the error in CI before the
playbook can fire in production.

**Changes**

1. `backend/core/playbooks/cli.py` (new module, 388 lines):
   - `_cmd_list` — list every playbook (or filter to one
     pack via `--pack <pack>`). Returns the loader's
     `to_dict()` shape for each row so cockpit dashboards
     can ingest CLI output 1:1 with HTTP output.
   - `_cmd_show` — single-playbook lookup with `--refresh`
     to dodge stale-cache surprises after just-edited
     files. Returns the same `{"playbook": ...}` envelope
     the HTTP `GET /api/playbooks/<id>` route returns.
   - `_cmd_run` — execute one playbook. Wraps
     `run_playbook` inside a `trace_scope(parent=<flag>,
     route="cli")` and `thread_id_scope(<flag>)` identical
     to the HTTP route, so cockpit-side trace search threads
     the CLI invocation through the same UI as HTTP. Layers
     a CLI-specific `took_ms` field on top of the runner's
     authoritative envelope. Two context input paths:
     `--context '<json>'` for ad-hoc tweaks and
     `--context-file <path>` for cron-baked sidecar JSON.
     File wins over inline if both are supplied — pinned by
     a dedicated test so a future reorder doesn't silently
     flip cron behaviour. Bad context (non-JSON, non-object,
     unreadable file) returns a clean `invalid_context`
     envelope with a human message instead of leaking a
     traceback to stdout. `--mode` is permissive
     (`resolve_mode` falls back to env / hard-coded default
     on unknown values) so a typo in a cron command line
     doesn't crash the run — pinned.
   - `_cmd_validate` — strict-validate one playbook by id
     (re-reads disk via `refresh=True`). Mirrors the HTTP
     `POST /api/playbooks/_validate` `{"id": ...}` body
     shape so cockpit + CLI consume the same envelope.
   - `_cmd_validate_all` — strict-validate every playbook
     on disk. Same shape as
     `GET /api/playbooks/_validate_all` so the CLI is
     drop-in for cockpit dashboards / CI pipes.
   - `_cmd_reload` — reset the loader cache and re-scan
     the playbooks dir (mirrors `POST /api/playbooks/_reload`).
     Surfaces `count` + `ids` so the cron job knows which
     playbooks landed.
   - `_emit` standardises JSON output (indent=2 default,
     `--quiet` for compact one-line) and exit-code mapping
     (`0` on `ok=true`, `1` else). Includes `default=str`
     so dataclass / Path values that leak through the
     runner don't crash the JSON encoder.
   - `main(argv)` returns the exit code so cron / Make
     targets can chain reliably.

2. `Makefile`:
   - New `PLAYBOOKS ?= $(PY) -m backend.core.playbooks.cli`
     macro (a future cli relocation is a one-line change).
   - Seven new targets, all on the `.PHONY` line:
     - `playbooks` — raw passthrough.
     - `playbooks-list` — optional `ARGS=--pack=<pack>`
       (forwarded directly, no guard — no-pack listing is
       the default lane).
     - `playbooks-show ARGS=<id>` — `[ -z "$(ARGS)" ]`
       guard with `exit 2`.
     - `playbooks-run ARGS=<id> [MODE=<mode>]
       [CONTEXT='<json>']` — surfaces `MODE=` /
       `CONTEXT=` as standalone vars (cron-friendly) on
       top of the standard `ARGS=` guard. Inner forward
       through `--mode` / `--context` flags.
     - `playbooks-validate ARGS=<id>` — `ARGS` guard.
     - `playbooks-validate-all` — parameter-free by design
       (the whole point is "walk every file"); pinned that
       it doesn't accept `ARGS=` so a typo doesn't get
       mistaken for a playbook id.
     - `playbooks-reload` — parameter-free.
   - `gate-control-tower` extended with
     `$(MAKE) playbooks-validate-all`. Now reads:
     `cockpit-tsc` → `cockpit-test` → `smoke-core-bridge`
     → `planner-smoke` → `playbooks-validate-all`.

3. `tests/test_playbooks_cli.py` (new, 25 tests):
   - `playbooks_root` fixture lays down a temp
     `playbooks/probe/` dir with one valid playbook
     (`probe.read_only` wrapping `business.kpi_snapshot`,
     non-destructive + deterministic) and points
     `TARS_PLAYBOOKS_DIR` at it. Decoupled from the
     shipped repo playbooks (which would couple test
     outcomes to whatever business / traders / mlm
     layouts happen to be on disk that day).
   - `list` no-filter / pack-filter (match + miss).
   - `show` happy path / unknown-id.
   - `run` happy path (envelope shape + `trace_id` +
     `mode` + `took_ms` + steps); unknown id; bad inline
     context; non-object context (list/scalar rejected);
     `--context-file` happy path; **file wins over inline
     when both supplied**; unreadable file; `--mode`
     forwarded to runner; **invalid mode falls back to
     default** (cron typo doesn't crash).
   - `validate` happy path + unknown-id; `validate-all`
     all-green envelope + **flips overall ok=false on any
     bad playbook** (the CI gate semantics).
   - `reload` picks up a freshly-added playbook (vs `list`
     which returns the cached set).
   - Argparse plumbing: missing subcommand /
     missing positional ⇒ `SystemExit(2)`; `--quiet` ⇒
     one-line JSON; `main([...])` ⇒ end-to-end smoke
     through `asyncio.run`.

4. `tests/test_makefile_playbooks_targets.py` (new, 16
   tests): contract pinning the Make wiring without
   shelling into `make`.
   - All seven targets on the `.PHONY` line; each has a
     `## help` ≥5 chars.
   - `playbooks-show` / `playbooks-run` /
     `playbooks-validate` have the standard
     `[ -z "$(ARGS)" ] ; exit 2` guard.
   - `PLAYBOOKS` macro must point at
     `backend.core.playbooks.cli`.
   - `gate-control-tower` must invoke
     `playbooks-validate-all` (the load-bearing CI gate
     wiring; pin so a future "tighten the gate" refactor
     doesn't quietly drop it).
   - `playbooks-run` recipe must surface `$(MODE)` and
     `$(CONTEXT)` as standalone vars (not require them
     wedged inside `ARGS=`); pin so a future
     "simplification" doesn't silently drop the cron
     contract.
   - `playbooks-list` must NOT guard against empty `ARGS`
     (no-pack listing is the default lane); pin the
     canonical pattern for "no positional, ARGS optional"
     targets.
   - `playbooks-validate-all` must NOT pass `$(ARGS)` so
     a typo doesn't get mistaken for a playbook id.

**Tests**

- `tests/test_playbooks_cli.py` — 25 new, all green.
- `tests/test_makefile_playbooks_targets.py` — 16 new, all
  green.
- Full Python suite: **2185 passed in 42.09s** (was 2144,
  +41 net new tests = 25 + 16).
- Smoke: `make playbooks-list` → 6 playbooks;
  `make playbooks-validate-all` → all green;
  `make playbooks-show ARGS=traders.morning_check` →
  full envelope; `make playbooks-run
  ARGS=traders.morning_check MODE=autopilot` →
  trace_id + 3 steps;
  `make playbooks-show` (no ARGS) → exits 2 with usage.

**Files**

- `backend/core/playbooks/cli.py` (new, 388 lines).
- `Makefile` — new `PLAYBOOKS` macro + 7 targets +
  `.PHONY` extension + `gate-control-tower` wiring.
- `tests/test_playbooks_cli.py` (new, 416 lines, 25 tests).
- `tests/test_makefile_playbooks_targets.py` (new, 197
  lines, 16 tests).
- `docs/CHANGELOG_AGENTS.md`, `docs/AGENT_HANDOFF.md`.

**Follow-ups**

- Right-rail planner entrypoint from the cockpit chat thread.
- Cron-shipped wrapper script
  (`scripts/playbooks_morning_cron.sh`) that bundles the
  three "morning" playbooks + meeet replay flush in one
  invocation; deferred until a concrete production
  schedule lands.
- bash completion script (`scripts/playbooks-completion.bash`)
  mirroring `scripts/planner-completion.bash`; deferred
  until the playbooks ID set is large enough that tab
  completion saves real time.

## 2026-05-01 — Cursor [A] · awareness CLI parity (`python -m backend.core.domains.awareness_cli` + `awareness-*` Make targets)

**Summary**

Closes the operator-parity gap left by the planner CLI: the
**awareness layer** (the cockpit's `GET /api/domains` /
`GET /api/domains/<slug>/awareness` /
`GET /api/domains/<slug>/awareness/<source_id>/snapshot` route)
now has a shell-side equivalent. An operator running on a
machine without the FastAPI process up — fleet rollout,
cron-driven cold-start brief, on-call recovery during an
ingest outage — can now list and materialise awareness sources
without going through HTTP, and the meeet event surface is
**bit-for-bit identical** so cockpit dashboards count CLI hits
the same as HTTP hits.

The CLI ships three subcommands plus a global `--quiet` flag:

- `list` — catalogue every pack (no slug) or one pack's
  awareness rows. Each row carries a `live` flag so the
  operator instantly sees which sources are config-only
  (webhook receivers, etc.).
- `snapshot <slug> <source_id>` — materialise one source.
  Mirrors the HTTP route's `awareness.snapshot.requested /
  completed / failed` event sequence inside a `trace_scope`,
  surfaces `trace_id` + `took_ms` in the envelope.
- `snapshot-all <slug>` — materialise every fetcher-bearing
  source on a pack. Splits results into `fetched` (real
  fetcher invocations) and `skipped` (config-only sources)
  so the operator can tell "no fetcher implemented yet"
  apart from a real fetch failure. Overall `ok` flips to
  `false` on any fetched-source failure.

**Why now?** Three concrete drivers:

1. **Cron-driven cold-start briefs** — the `traders.morning_check`
   playbook needs `binance_ws.snapshot` materialised before the
   summarise step runs. Today that's done by hitting HTTP from a
   curl-in-cron. The CLI variant skips the HTTP hop, runs in the
   same process, and pipes cleanly into `jq`.
2. **Cold-start recovery** — when the FastAPI app is wedged (rare
   but seen in production), HTTP-only operator paths leave you
   with no way to inspect awareness wiring. The CLI is the only
   path that doesn't depend on the web layer.
3. **Fleet orchestration** — higher-level orchestrators (Ansible,
   Kubernetes Jobs) prefer to shell out and parse JSON over
   maintaining a per-orchestrator HTTP client. The CLI gives
   them a stable, shell-friendly surface.

**Changes**

1. `backend/core/domains/awareness_cli.py` (new module):
   - `_cmd_list` — single-pack or catalogue listing.
     Each row exposes `id` / `name` / `description` / `kind` /
     `config` / `live` (mirror of the HTTP route's per-row
     shape). Catalogue mode adds `count` / `live_count` per
     pack so the operator can spot a pack with zero live
     sources at a glance.
   - `_cmd_snapshot` — single-source materialisation.
     Wraps the fetcher in `trace_scope(parent=<flag>,
     route="cli")` so cockpit-side trace search threads the
     CLI invocation through the same UI as HTTP. Fetcher
     exceptions return an error envelope (no traceback to
     stdout) and emit `awareness.snapshot.failed`. Config-only
     sources return `error: fetcher_unavailable` with a
     human-readable hint instead of raising.
   - `_cmd_snapshot_all` — pack-scoped bulk materialisation.
     Iterates `pack.awareness()`, materialising fetcher-backed
     sources and accumulating skipped (config-only) ones into
     a separate array. Overall `ok` is the AND of every
     fetched-source `ok` (skipped sources do *not* fail the
     envelope — they're not actionable failures, just
     not-implemented-yet).
   - `--thread-id` / `--trace-id` flags on the snapshot
     subcommands so an operator chaining CLI calls inside a
     larger orchestration can keep the trace tree intact.
   - `_emit` helper standardises JSON output (indent=2 by
     default; `--quiet` for compact one-line) and exit-code
     mapping (`0` on `ok=true`, `1` on `ok=false`).
   - `main(argv)` returns the exit code so cron / Make targets
     can chain reliably.

2. `Makefile`:
   - New `AWARENESS ?= $(PY) -m backend.core.domains.awareness_cli`
     macro so a future cli relocation is a one-line change.
   - Four new targets, all on the `.PHONY` line:
     - `awareness` — raw passthrough
       (`make awareness ARGS="snapshot traders binance_ws"`).
     - `awareness-list` — `[ARGS=<slug>]` (no slug ⇒ catalogue).
     - `awareness-snapshot ARGS="<slug> <source_id>"` — guards
       against empty `ARGS` (`exit 2`), then re-guards both
       positionals via `set -- $(ARGS)` so the operator gets a
       usage line instead of an argparse traceback when only
       one positional is supplied.
     - `awareness-snapshot-all ARGS=<slug>` — single-positional,
       forwards `$(ARGS)` directly. Same `[ -z "$(ARGS)" ] ; exit 2`
       guard pattern as the rest of the planner-* family.
   - Each target carries a `## help` comment so it shows up in
     `make help`.

3. `tests/test_awareness_cli.py` (new): 16 contract tests
   covering every subcommand × every fetcher branch.
   - `probe_pack` fixture registers a fully-controlled domain
     pack with three sources (success / raise / no-fetcher),
     so tests don't depend on the real built-in packs (which
     hit live URLs).
   - `list` no-slug returns every pack with the expected row
     shape; with-slug filters correctly; unknown slug emits
     `domain_not_found` and `rc=1`.
   - `snapshot` happy path returns `ok=true` + `data` +
     `trace_id` + `took_ms`; raising fetcher returns
     `ok=false` with the exception text + still emits the
     trace_id (so the operator can grep meeet for the
     matching `awareness.snapshot.failed`); config-only source
     returns `fetcher_unavailable` with a human hint;
     unknown slug / unknown source return distinct
     `domain_not_found` / `awareness_not_found` envelopes.
   - `snapshot-all` splits fetched vs skipped, flips overall
     `ok` only when a fetched source fails (skipped doesn't
     count); unknown slug returns `domain_not_found`.
   - Argparse plumbing: missing subcommand / missing
     positionals raise `SystemExit(2)`; `--quiet` produces
     single-line JSON (asserted by counting newlines);
     `main([...])` end-to-end smoke through `asyncio.run`.

4. `tests/test_makefile_awareness_targets.py` (new): 10
   contract tests pinning the Make wiring without shelling
   into `make` (which requires a full venv on PATH and
   couples the test runtime to the CI host).
   - All four target names appear on the `.PHONY` line.
   - Every target has a `## help` comment ≥5 chars.
   - `awareness-snapshot` and `awareness-snapshot-all` have
     the standard `[ -z "$(ARGS)" ] ; exit 2` guard so
     missing `ARGS` doesn't burrow into argparse with a
     confusing error.
   - `AWARENESS` macro must point at
     `backend.core.domains.awareness_cli` so a future
     module move surfaces here, not in production.
   - `awareness-snapshot` recipe uses
     `set -- $(ARGS)` for safe positional split, and
     re-guards both positionals via the inner
     `[ -z "$$slug" ] || [ -z "$$source_id" ]` check. Pin
     this so a future "simplification" doesn't reintroduce
     the "missing source_id ⇒ confusing argparse error"
     foot-gun.
   - `awareness-snapshot-all` recipe forwards `$(ARGS)`
     directly (single positional, no `set --` needed) — pin
     this as the canonical pattern for single-positional
     targets.

**Tests**

- `tests/test_awareness_cli.py` — 16 new tests, all green.
- `tests/test_makefile_awareness_targets.py` — 10 new tests,
  all green.
- Full Python suite: **2144 passed in 48.90s** (was 2118, +26
  net new tests = 16 + 10).
- Smoke: `make awareness-list ARGS=traders` returns 5
  sources (4 live), `make awareness-snapshot
  ARGS="traders binance_ws"` returns the live ticker
  envelope with `trace_id` + `took_ms`, missing-`ARGS`
  guards exit 2.

**Files**

- `backend/core/domains/awareness_cli.py` (new, 392 lines).
- `Makefile` — new `AWARENESS` macro + four new targets +
  `.PHONY` extension.
- `tests/test_awareness_cli.py` (new, 437 lines, 16 tests).
- `tests/test_makefile_awareness_targets.py` (new, 142 lines,
  10 tests).
- `docs/CHANGELOG_AGENTS.md`, `docs/AGENT_HANDOFF.md`.

**Follow-ups**

- Right-rail cockpit entrypoint when the agent proposes a plan
  (still pending; tracked in `AGENT_HANDOFF.md`).
- Awareness pre-warm subcommand
  (`awareness-snapshot-all --pack=*`) once a packwide ARGS
  pattern emerges; deferred until there's a concrete cron use
  case driving it.

## 2026-05-01 — Cursor [A] · meeet replay CLI: `--repush-trace` + `planner-repush-run` Make target

**Summary**

Operator follow-up to PR #124 (`planner-replay-run`). Adds the
**push-this-trace-upstream-now** flow that PR didn't ship:
`replay_cli --repush-trace <trc>` re-emits every event for one
trace to ingest, regardless of the existing `pushed` flag, so a
fleet operator can recover from a meeet ingest contract bump
without hand-editing SQLite.

The full operator pipeline now reads:

1. `make planner-replay-run ARGS="<plan_id> <run_trace>"` —
   dump the run's events to JSONL for inspection / archive.
2. (Operator audits the JSONL, fixes upstream contract.)
3. `make planner-repush-run ARGS="<run_trace>"` — push every
   matching row upstream, regardless of `pushed=0/1`.

**Why force-push and not just "push unpushed"?** The existing
`MeeetClient.replay_unpushed` only handles `pushed=0` rows.
After a contract bump, the rows the operator needs to re-emit
have `pushed=1` (they reached the *old* upstream). Without a
force-flag, those rows are stuck in the buffer with no way to
retransmit. `--repush-trace` is the audited, scoped escape
hatch.

**Why scoped to one trace?** A blanket "force re-push everything"
would drain the buffer of unrelated events at the same time. The
`trace_id` filter keeps the blast radius to one plan run, which
is the unit of audit / billing the operator actually cares about.

**Failure semantics** (load-bearing): when an upstream push fails
during a repush, the row's `pushed` flag is **NOT regressed to 0**.
Only `last_error` updates. Otherwise a half-failed repush would
let those rows leak into the next `replay_unpushed` flush and
**double-push** them once the upstream recovers — exactly the
behaviour the contract bump is trying to repair.

**Changes**

1. `backend/core/meeet/store.py`:
   - New `MeeetStore.repush_trace(push_callable, *, trace_id,
     limit=1000)` async method. Lists matching events
     (regardless of `pushed`), feeds them through the push
     loop, returns the same envelope as `replay_unpushed` plus
     a `trace_id` echo. Empty `trace_id` returns an
     `error: trace_id_required` envelope without touching the
     store (guard against silent bulk-push of empty-trace
     rows).
   - Push loop extracted into a private
     `_push_events(events, push_callable)` helper so
     `replay_unpushed` and `repush_trace` share the same
     oldest-first / mark-pushed-on-success / record-error-on-
     failure semantics.
2. `backend/core/meeet/client.py`:
   - New `MeeetClient.repush_trace(trace_id, *, limit=1000)`
     wrapper. Identical no-ingest noop behaviour as
     `replay_unpushed` (returns `enabled=false` envelope,
     stamps `last_replay`).
   - Push primitive extracted into `_push(body)` async method
     so both `replay_unpushed` and `repush_trace` use the
     same `urlopen` call (no more inline closures).
3. `backend/core/meeet/replay_cli.py`:
   - New `--repush-trace <trc>` flag. Branch precedence
     pinned: `--stats > --repush-trace > --export > replay`
     so an operator passing both `--repush-trace` and
     `--export` by mistake gets the more meaningful action
     (pushing).
   - Module docstring updated with the per-run repush usage
     example and a pointer to the `planner-repush-run` Make
     target.
4. `Makefile`:
   - New `planner-repush-run ARGS=<run_trace> [LIMIT=N]`
     target. Two-branch recipe (with-LIMIT / without) gated
     by `[ -n "$(LIMIT)" ]` so the bare invocation doesn't
     get a stray `--limit` with empty value.
   - Added to the planner `.PHONY` line.
5. `tests/test_meeet_store.py`:
   - 5 new contract tests for `repush_trace`: pushes all
     matching rows regardless of `pushed` flag, no-match ⇒
     zero counts, push failures don't regress `pushed=0`,
     disabled-store noop, empty-trace_id guard.
6. `tests/test_replay_cli.py`:
   - 4 new contract tests for `--repush-trace`: no-ingest
     disabled envelope (rc=0), happy path with hermetic HTTP
     monkeypatch, failure ⇒ rc=1 (cron-friendly), precedence
     over `--export` (export branch never executes when
     repush is set).
7. `tests/test_makefile_planner_targets.py`:
   - `_PLANNER_TARGETS` extended with `planner-repush-run`
     so `.PHONY` + help-text contracts apply.
   - `ARGS=` guard parametrize extended.
   - New test
     `test_planner_repush_run_target_wires_replay_cli_with_repush_trace`
     pinning the recipe wires `--repush-trace` (not the
     export-only `--trace-id`), forwards optional
     `LIMIT=` as `--limit $(LIMIT)`, and gates the LIMIT
     branch on `[ -n "$(LIMIT)" ]`.

**Tests**

- `pytest tests/test_meeet_store.py tests/test_replay_cli.py
   tests/test_makefile_planner_targets.py` — **47 passed**
  (was 35, +12).
- `pytest -q` — **2118 passed in 49s** (was 2106, +12).
- Manual smoke from the venv:
  - `make planner-repush-run` (no ARGS) → exit 2 with usage.
  - `make planner-repush-run ARGS=trc_synthetic` → returns
    `{enabled:false, trace_id:trc_synthetic, pushed:0,
    failed:0, remaining:0, ran_at:...}` (no ingest URL set
    in test env, exactly the cron-safe noop we wanted).
  - `make planner-repush-run ARGS=trc_synthetic LIMIT=5` →
    same envelope; LIMIT was forwarded successfully.

**Files touched**

- `backend/core/meeet/store.py`
- `backend/core/meeet/client.py`
- `backend/core/meeet/replay_cli.py`
- `Makefile`
- `tests/test_meeet_store.py`
- `tests/test_replay_cli.py`
- `tests/test_makefile_planner_targets.py`
- `docs/CHANGELOG_AGENTS.md` (this entry)
- `docs/AGENT_HANDOFF.md` (Done bullet)

**Follow-ups**

- Right-rail planner entrypoint from the cockpit chat thread
  (open the planner panel inline when the agent proposes a
  plan).
- Awareness CLI parity (`python -m backend.core.awareness.cli`)
  so operator scripting reaches awareness sources too.

---

## 2026-05-01 — Cursor [A] · cockpit: aria-live announcement on plan run completion / abort

**Summary**

Plan-detail panel now surfaces every terminal run through a
visually-hidden `aria-live="polite"` region so screen-reader
operators learn that a run finished without watching the panel.
Three lifecycle outcomes get distinct phrasing:

- **Clean completion** — `"Run completed in 1.23s · $0.0050."`
- **Soft failure** — `"Run completed with N failed step(s) in
  Xms · $cost."` (run finished but a step errored — surfaced
  because dashboards otherwise tally these as green).
- **Abort / hard failure** — `"Run aborted after Xms: <reason>."`
  (uses `abort_reason`, falls back to `exception`, finally a
  placeholder).

Running runs return null so the announcer stays quiet until a
run terminates.

**Decision split (pure helpers + thin React glue)**

Two pure exports in `PlanFullPanel.tsx`:

- `formatRunAnnouncement(run): string | null` — renders the
  message string for a single terminal run; returns `null` for
  in-flight runs.
- `pickRunAnnouncement(runs, lastAnnouncedTraceId): { traceId,
  message } | null` — walks the newest-first runs list, picks
  the first **terminal** run (skipping in-flight heads), and
  returns an announcement payload only when its `trace_id`
  differs from the one we last announced.

The "skip in-flight head" rule is load-bearing: when a rerun
fires, the new `plan.run.started` event pushes the previously
completed run to index 1. We still want to announce that
completion once, even though index 0 is now `running`.

The "trace_id dedupe, not array index" rule means SSE refreshes
that re-emit the same envelope (e.g. on reconnect) won't
re-announce the same run.

**Wiring**

`PlanFullPanel` now keeps `useRef<lastAnnouncedTraceIdRef>` +
`useState<announcement>` and runs the helper inside a
`useEffect([data])`. A separate `useEffect([planId])` resets
both when the operator switches plans (so deep-linking from
plan A to plan B re-announces plan B's newest terminal run
even if A and B happened to share a trace_id — collisions are
rare but the reset is cheap).

The aria-live region itself is always rendered (not gated by
`{message && ...}`) because some screen-reader engines skip
the initial announcement when the live region appears
mid-page-life. `role="status"` reinforces the live-region
semantics for AT that don't honour `aria-live` alone;
`aria-atomic="true"` makes the announcement re-read in full
each time it changes.

**Changes**

1. `experiments/neural-showcase-v3/src/components/PlanFullPanel.tsx`:
   - New pure helpers `formatRunAnnouncement` and
     `pickRunAnnouncement` (exported for Vitest).
   - New state slot `announcement` + ref
     `lastAnnouncedTraceIdRef`.
   - New `useEffect([data])` watcher that calls the helper and
     surfaces the message; new `useEffect([planId])` that
     resets the dedupe state on plan switch.
   - New `<div role="status" aria-live="polite" aria-atomic="true"
     className="sr-only">` rendered at the top of the panel.
2. `experiments/neural-showcase-v3/src/components/PlanFullPanel.test.ts`:
   - 14 new Vitest cases pinning every branch of both
     helpers: in-flight ⇒ null, clean completion, soft
     failure (singular + plural), aborted with reason /
     exception fallback / placeholder; plus
     `pickRunAnnouncement`'s dedupe contract (empty list,
     all-in-flight, first hydration, dedupe against last
     announced, fresh terminal after ack, null trace_id
     stays silent, in-flight head is skipped).

**Tests**

- `pnpm --dir experiments/neural-showcase-v3 test -- --run` —
  **181 passed (14 files)** (was 167, +14).
- `tsc --noEmit` — clean.
- `vite build` — clean (2.82s).
- `pytest -q` — **2106 passed** (unchanged, no Python touched).

**Files touched**

- `experiments/neural-showcase-v3/src/components/PlanFullPanel.tsx`
- `experiments/neural-showcase-v3/src/components/PlanFullPanel.test.ts`
- `docs/CHANGELOG_AGENTS.md` (this entry)
- `docs/AGENT_HANDOFF.md` (Done bullet)

**Follow-ups**

- Right-rail planner entrypoint from the cockpit chat thread
  (open the planner panel inline when the agent proposes a
  plan).
- `--force-repush --trace-id` flag pair on `replay_cli` for
  fleet ops re-emit-to-upstream workflows.
- Awareness CLI parity (`python -m backend.core.awareness.cli`)
  so operator scripting reaches awareness sources too.

---

## 2026-05-01 — Cursor [A] · cockpit: scroll-to-selected on /cockpit/planner deep links

**Summary**

Closes the long-standing planner-page polish item: when an
operator pastes a deep link like
`/cockpit/planner?selected=pln_xyz`, the rail's `<li>` for that
plan was hidden below the fold of the overflow-scroll list and
the operator had no visual confirmation of which plan they were
inspecting. Now the page imperatively scrolls the matching row
into view on first paint (and on browser-back to a different
selection) without disrupting routine clicks.

**The "should I scroll?" decision**

`shouldScrollTo(selected, plansListed, lastScrolled)` is a pure
boolean helper extracted to `lib/plannerScroll.ts`. It returns
`true` only when:

- `selected` is non-null,
- the plans list has loaded (`plansListed !== null`),
- the row is in the visible (post-filter) list, and
- `selected !== lastScrolled` (no re-scroll on SSE refresh of an
  unchanged selection).

Returns `false` for the four no-scroll cases (nothing selected,
list still loading, deep-link points at a filtered-out plan,
SSE refresh that doesn't change selection).

The actual `scrollIntoView({ block: "nearest", behavior: "smooth" })`
lives in a `useScrollSelectedIntoView` hook on the Planner page
that gates on the helper. `block: "nearest"` is load-bearing:
when the row is already visible (e.g. user just clicked it),
the call is a no-op, so we don't have to special-case "user
click vs URL change" — both go through the same path and only
the URL-change case actually scrolls.

**Changes**

1. `experiments/neural-showcase-v3/src/lib/plannerScroll.ts`
   (new): `shouldScrollTo` plus a docstring laying out the four
   no-scroll cases and a `PlanLike` interface accepting any
   shape with an `id: string`.
2. `experiments/neural-showcase-v3/src/lib/plannerScroll.test.ts`
   (new): 9 Vitest cases pinning every branch (no selection,
   loading list, deep-link to filtered-out plan, already-scrolled
   short-circuit, first-paint deep link, browser-back selection
   change, top-row scroll, empty plans array, purity contract).
3. `experiments/neural-showcase-v3/src/pages/Planner.tsx`:
   - `useRef<Map<string, HTMLLIElement | null>>` — per-row DOM
     refs keyed by plan id.
   - `useScrollSelectedIntoView` hook — wraps the helper +
     `scrollIntoView` call + `lastScrolledRef`.
   - `PlanList` accepts `rowRefs` prop and attaches the ref
     callback to each `<li>`.

**Tests**

- `pnpm --dir experiments/neural-showcase-v3 test -- --run` —
  **167 passed (14 files)** (was 158, +9 from
  `plannerScroll.test.ts`).
- `tsc --noEmit` — clean.
- `vite build` — clean (2.74s).
- `pytest -q` — **2106 passed** (unchanged, no Python touched).
- Manual smoke is best done against a populated planner, so
  this PR ships behind the existing Vitest gate; the cockpit
  test on a real local backend will be exercised when the
  next planner page session opens with `?selected=` in the URL.

**Files touched**

- `experiments/neural-showcase-v3/src/lib/plannerScroll.ts`
- `experiments/neural-showcase-v3/src/lib/plannerScroll.test.ts`
- `experiments/neural-showcase-v3/src/pages/Planner.tsx`
- `docs/CHANGELOG_AGENTS.md` (this entry)
- `docs/AGENT_HANDOFF.md` (Done bullet)

**Follow-ups**

- `aria-live` announcement when a run completes / fails so
  screen-reader operators know the run finished without
  watching the panel.
- Right-rail planner entrypoint from the cockpit chat thread
  (open the planner panel inline when the agent proposes a
  plan).
- `--force-repush --trace-id` flag pair on `replay_cli` for
  fleet ops re-emit-to-upstream workflows.

---

## 2026-05-01 — Cursor [A] · meeet replay CLI: `--trace-id` filter + `planner-replay-run` Make target

**Summary**

Adds a per-run scoping knob to the meeet event replay CLI plus
the operator wrapper that uses it. The combo:

- `python -m backend.core.meeet.replay_cli --export <path>
   --trace-id <run_trace>` — dumps just one run's events to
  JSONL.
- `make planner-replay-run ARGS="<plan_id> <run_trace>"
   [OUT=<path>]` — convenience wrapper that defaults the output
  to `.meeet-replays/<plan_id>-<run_trace>.jsonl` so cron jobs
  can grep by either id without writing custom shell.

**Use case** — meeet ingest outage backfill / single-run audit.
After fixing an upstream ingest endpoint, fleet ops want to dump
one specific run's events for re-push or evidence trail without
shoveling the entire local store. `MeeetStore.list_events` has
supported `trace_id=` for a while, but the export branch of
`replay_cli` didn't expose it. One flag + one Make target closes
the gap.

**Why JSONL export instead of force-repush?** The existing
replay path (`MeeetClient.replay_unpushed`) only handles
`pushed=0` events. A force-repush flag would need to flip
`pushed→0` for matching rows, which mutates store state and
reorders the global push queue — a bigger semantic change than
this PR wants to land in one go. Export-to-JSONL is read-only,
diff-able, and lets the operator decide how to push (curl
loop, custom script, or just keep the file as audit evidence).
A `--force-repush --trace-id` flow can layer on later if the
need is demonstrated.

**Recipe shape**

```
MEEET_REPLAY_DIR ?= .meeet-replays
planner-replay-run:
	@if [ -z "$(ARGS)" ]; then echo 'usage: ...'; exit 2; fi
	@bash -c 'set -e; \
	    set -- $(ARGS); \
	    plan_id=$$1; \
	    run_trace=$${2:-}; \
	    if [ -z "$$plan_id" ] || [ -z "$$run_trace" ]; then \
	        echo "usage: ..."; exit 2; \
	    fi; \
	    out_path="$(OUT)"; \
	    if [ -z "$$out_path" ]; then \
	        mkdir -p "$(MEEET_REPLAY_DIR)"; \
	        out_path="$(MEEET_REPLAY_DIR)/$$plan_id-$$run_trace.jsonl"; \
	    fi; \
	    PYTHONPATH=. $(PY) -m backend.core.meeet.replay_cli \
	        --export "$$out_path" --trace-id "$$run_trace" \
	        --limit 1000; \
	    echo "planner-replay-run wrote $$out_path"'
```

Both positionals are required (the plan_id is informational —
used in the default filename — but mandating it keeps the
contract memorable: "plan_id, then trace"). `MEEET_REPLAY_DIR`
uses `?=` so operators can override via env or command line
without touching the Makefile.

**Changes**

1. `backend/core/meeet/replay_cli.py`:
   - New `--trace-id <trc>` CLI flag, threaded into
     `store.list_events(trace_id=...)` in the export branch
     only (stats / replay branches are unchanged).
   - Module docstring updated with a per-run usage example
     and a pointer to the `planner-replay-run` Make target.
2. `Makefile`:
   - New `MEEET_REPLAY_DIR ?= .meeet-replays` macro.
   - New `planner-replay-run` target (added to `.PHONY`,
     gated by ARGS guard + inner positional re-guard).
3. `tests/test_replay_cli.py`:
   - `_seed` helper now accepts `trace_id` and `session_id`
     parameters so tests can fan out to multiple runs.
   - `test_cli_export_trace_id_filters_to_one_run` — pins
     that `--trace-id` only exports matching rows (run B's
     events stay in the store but don't reach the file).
   - `test_cli_export_trace_id_with_no_match_writes_empty_file`
     — pins that an unknown trace produces an empty JSONL
     and `rc=0` (cron-friendly).
4. `tests/test_makefile_planner_targets.py`:
   - `_PLANNER_TARGETS` extended with `planner-replay-run`
     so the `.PHONY` + help-text contracts apply to it.
   - `ARGS=` guard parametrize extended to cover
     `planner-replay-run`.
   - New test `test_planner_replay_run_target_wires_export_with_trace_id`
     pinning every load-bearing piece of the recipe:
     positional split, both-required guard, OUT= override,
     default `MEEET_REPLAY_DIR/$plan-$trace.jsonl` filename,
     `--trace-id` and `--export` invocation, and that the
     module is `backend.core.meeet.replay_cli` (not the
     planner CLI — different store).
   - New test `test_planner_replay_run_uses_meeet_replay_dir_macro`
     pinning that `MEEET_REPLAY_DIR` is declared with `?=`
     (override-friendly) and the default is `.meeet-replays`.

**Tests**

- `pytest tests/test_replay_cli.py
   tests/test_makefile_planner_targets.py` — **29 passed**
  (was 22, +7: 2 trace-id CLI cases plus 5 from broader
  Makefile fan-out).
- `pytest -q` — **2106 passed in 40s** (was 2100, +6).
- Manual smoke from the venv:
  - Synthesized + ran `traders.morning_check` (12 events
    emitted: started + 3×requested + 3×allowed + 3×completed
    + run.usage + run.completed).
  - `make planner-replay-run ARGS="$plan_id $trace"` →
    wrote `.meeet-replays/$plan-$trace.jsonl` with 12 lines,
    every line carrying `trace_id == $trace`.
  - `OUT=/tmp/custom.jsonl` override → wrote to the custom
    path.
  - No ARGS → exit 2 with usage line.
  - One positional only → exit 2 with usage line.

**Files touched**

- `backend/core/meeet/replay_cli.py`
- `Makefile`
- `tests/test_replay_cli.py`
- `tests/test_makefile_planner_targets.py`
- `docs/CHANGELOG_AGENTS.md` (this entry)
- `docs/AGENT_HANDOFF.md` (Done bullet)

**Follow-ups**

- `--force-repush --trace-id` flag pair on `replay_cli` if
  fleet ops actually need re-emit-to-upstream (rather than
  the current export-to-JSONL workflow). Would need to
  flip `pushed→0` for matching rows then reuse
  `replay_unpushed`.
- Right-rail planner entrypoint from the cockpit chat
  thread (open the planner panel inline when the agent
  proposes a plan).

---

## 2026-05-01 — Cursor [A] · Makefile: `planner-clone` target for plan forking

**Summary**

Adds `make planner-clone ARGS="<plan_id> [target_thread]"` so a
fleet operator can fork a known-good plan into a fresh
`proposed` row from the shell — without immediately approving
or running it (that's `planner-rerun`'s job). Use case: golden
plan lives on `thread_main`, you want a per-tenant copy queued
on `thread_acme` for the on-call operator to review and approve
manually, and you don't want to write a five-line bash wrapper
for every clone.

The recipe accepts ARGS as a positional pair so the second word
(if any) becomes `--thread-id <target_thread>`. Bare
`ARGS=<plan_id>` invokes a vanilla clone that inherits the
source's thread.

**Recipe shape**

```
planner-clone:
	@if [ -z "$(ARGS)" ]; then echo 'usage: ...'; exit 2; fi
	@bash -c 'set -e; \
	    set -- $(ARGS); \
	    plan_id=$$1; \
	    target_thread=$${2:-}; \
	    if [ -z "$$plan_id" ]; then echo ...; exit 2; fi; \
	    if [ -n "$$target_thread" ]; then \
	        PYTHONPATH=. $(PLANNER) clone "$$plan_id" \
	            --thread-id "$$target_thread"; \
	    else \
	        PYTHONPATH=. $(PLANNER) clone "$$plan_id"; \
	    fi'
```

The inner `[ -z "$plan_id" ]` re-guard catches the edge case
where ARGS expanded to whitespace-only after macro expansion
(e.g. `ARGS="  "`).

**Changes**

1. `Makefile`:
   - New `planner-clone` target with the standard `ARGS=` outer
     guard plus an inner per-positional re-guard.
   - Added to the planner `.PHONY` line between `planner-full`
     and `planner-rerun` so help-text ordering reads
     "show → full → clone → rerun → smoke" (operator mental
     model: inspect, then mutate).
2. `tests/test_makefile_planner_targets.py`:
   - `_PLANNER_TARGETS` extended with `planner-clone` so the
     `.PHONY` + help-text contracts apply to it.
   - `ARGS=` guard parametrize extended to cover
     `planner-clone`.
   - New test
     `test_planner_clone_target_supports_optional_target_thread`
     pinning the recipe's positional split, the inner
     re-guard, and both branches (with / without
     `--thread-id`).

**Tests**

- `pytest tests/test_makefile_planner_targets.py` —
  **20 passed** (was 17, +3: phony membership, ARGS guard,
  dedicated clone-recipe contract).
- `pytest -q` — **2100 passed in 41s** (was 2097, +3).
- Manual end-to-end smoke from the venv:
  - `make planner-clone ARGS=<plan_id>` → bare clone, inherits
    thread, status `proposed`, `auto_approved=false`.
  - `make planner-clone ARGS="<plan_id> thr_fleet_42"` → clone
    with `thread_id=thr_fleet_42`, source thread untouched.
  - `make planner-clone` (no ARGS) → exits 2 with usage line.

**Why a clone-only target when `planner-rerun` already exists?**

`planner-rerun` is opinionated: clone → approve → run. That's
the right default for the cockpit's one-click button. But fleet
ops sometimes want to:

- Fork a golden plan into a per-tenant thread and let the
  on-call operator approve manually (audit trail / four-eyes
  policy).
- Stage many clones overnight, then approve the curated subset
  in the morning.
- Snapshot a plan before mutating the source so a rollback
  copy exists.

All three want clone-without-side-effects, which `planner-rerun`
intentionally doesn't provide. Splitting the workflow keeps each
target single-purpose and composable: `planner-clone` →
`planner-show` (review) → `planner` ARGS="approve <id>" →
`planner` ARGS="run <id>".

**Files touched**

- `Makefile`
- `tests/test_makefile_planner_targets.py`
- `docs/CHANGELOG_AGENTS.md` (this entry)
- `docs/AGENT_HANDOFF.md` (Done bullet)

**Follow-ups**

- Right-rail entrypoint from the cockpit chat thread (open the
  planner panel inline when the agent proposes a plan).
- `make planner-replay-run ARGS="<plan_id> <run_trace>"` for
  re-emitting a single past run's events into the meeet store
  for dashboard backfill — useful when rebuilding billing
  rollups after a meeet ingest outage.

---

## 2026-05-01 — Cursor [A] · Makefile: `planner-rerun` target for cron / fleet workflows

**Summary**

Adds `make planner-rerun ARGS=<plan_id> [MODE=…]` so cron jobs
and fleet operators can reproduce the cockpit's one-click Rerun
button from a single Make invocation. Internally it shells into
`python -m backend.core.planner.cli clone $(ARGS) --approve --run`
(plus optional `--mode "$(MODE)"`) so it shares the same trace
scope, policy gate, and meeet-event payloads as the cockpit
path.

The optional `MODE=` variable is the operator's lever for pinning
policy mode at the Make boundary — useful for nightly cron where
you want `MODE=autopilot` regardless of `TARS_POLICY_MODE`'s
default. Without `MODE=`, the CLI inherits the env / header
default and the rerun follows whatever policy the host process
is configured for.

**Changes**

1. `Makefile`:
   - New `planner-rerun` target with the standard `ARGS=` guard
     (no plan id ⇒ exit 2 with usage hint).
   - Added to the planner `.PHONY` line.
2. `tests/test_makefile_planner_targets.py`:
   - `_PLANNER_TARGETS` extended with `planner-rerun` so the
     `.PHONY` + help-text contracts apply to it.
   - `ARGS=` guard parametrize extended to cover `planner-rerun`.
   - New test
     `test_planner_rerun_target_wires_clone_with_approve_and_run`
     pinning that:
     - the recipe contains `clone $(ARGS) --approve --run` so
       the workflow stays in lockstep with the cockpit's
       one-click Rerun button;
     - the optional `MODE=` branch forwards `--mode "$(MODE)"`
       so the operator can pin policy mode at the Make boundary.

**Tests**

- `tests/test_makefile_planner_targets.py` — **17 passed**
  (was 14, +3 from the new parametrize entry, the new
  `planner-rerun` `.PHONY` row, and the dedicated rerun
  contract test).
- `pytest -q` — **2097 passed in 40s** (was 2094, +3).
- Manual smoke: `make planner-rerun ARGS=<plan_id>` ran clone
  → approve → execute end-to-end and printed the rerun envelope
  with `usage_lifetime` populated.

**Operator follow-ups**

- Right-rail entrypoint from the cockpit chat thread (open the
  planner panel inline when the agent proposes a plan) — last
  cockpit-side payoff still on the planner roadmap.
- `make planner-replay-run ARGS="<plan_id> <run_trace>"` for
  re-emitting a single past run's events into the meeet store
  for dashboard backfill — useful when rebuilding billing
  rollups after a meeet ingest outage.

## 2026-05-01 — Cursor [A] · planner: `full` CLI subcommand + extracted helper

**Summary**

Brings the planner CLI to parity with the HTTP `/full` endpoint
shipped in PR #116, so an operator without a cockpit window can
inspect a plan in one command and pipe the JSON into `jq`.

The lifetime aggregation logic now lives in
`backend/core/planner/history.py::aggregate_usage_lifetime` —
extracted from the FastAPI route so the CLI calls the exact
same code path. The HTTP route now reads as a thin wrapper. The
helper is re-exported from `backend.core.planner` so external
callers (TARS-aware operator scripts, future replay tools) can
build their own lifetime rollups without speaking HTTP.

The lifetime cost rule is preserved verbatim: `cost_usd` stays
`None` when no run had a priced model so the CLI / cockpit can
render "n/a" instead of "$0.00", and mixed runs sum *only* the
priced runs' costs so a "ran but free" run never gets confused
with "no priced model fired".

The new subcommand has full operator wiring:

  - **CLI**: `python -m backend.core.planner.cli full <plan_id> [--limit N]`
    — emits the same envelope as `GET /api/planner/{id}/full`
    (keys `ok`, `plan_id`, `plan`, `runs.{count,in_flight,items}`,
    `usage_lifetime`).
  - **Makefile**: `make planner-full ARGS=<plan_id>` (with
    `ARGS=` guard — no plan id ⇒ exit 2 with usage hint).
  - **Bash completion**: `full` advertised in
    `_TARS_PLANNER_CMDS`, gets the live `plan_id` completion and
    `--limit` flag, mirrors the same QoL the rest of the CLI has.
  - **Module docstring** updated with the new line in the usage
    block.

**Changes**

1. `backend/core/planner/history.py` — new
   `aggregate_usage_lifetime(runs)` helper (zero-runs returns
   the same null-cost block, mixed runs honour the priced-only
   rule).
2. `backend/core/planner/__init__.py` — re-export
   `aggregate_usage_lifetime` from the package root.
3. `web_extras/routers/planner.py` — `/full` endpoint refactored
   to call `aggregate_usage_lifetime(runs)` instead of
   reimplementing the loop.
4. `backend/core/planner/cli.py` — new `_cmd_full` handler +
   subparser + `_DISPATCH` entry; module docstring updated.
5. `scripts/planner-completion.bash` — `full` added to
   `_TARS_PLANNER_CMDS`, `--limit` flag advertised under both
   `runs)` and `full)` case branches, plan-id completion list
   extended.
6. `Makefile` — new `planner-full` target, added to `.PHONY`,
   shares `PLANNER` macro and `ARGS=` guard pattern.
7. `tests/test_planner_full_cli.py` (new, 10 cases):
   - `aggregate_usage_lifetime`: zero runs (null cost), single
     priced run (correct sums), all-unpriced runs (null cost
     preserved), mixed priced+unpriced (only priced costs
     summed), priced-but-cost-None defensive guard, accepts
     tuple input.
   - CLI happy path (envelope shape pinned key-by-key).
   - CLI 404-style error envelope for unknown plan id.
   - CLI `--limit` flag pass-through to `reconstruct_runs_async`
     (verified via spy).
   - CLI `--quiet` global-flag placement (`--quiet full <id>`)
     keeps stdout to one JSON line.
8. `tests/test_planner_completion_script.py` — extended
   parametrize to cover `runs` and `full` carrying `--limit`.
9. `tests/test_makefile_planner_targets.py` — `planner-full`
   added to `_PLANNER_TARGETS`; `ARGS=` guard parametrize
   extended to cover it.

**Tests**

- New file `tests/test_planner_full_cli.py` — 10 passed.
- Existing planner contract tests still green
  (`test_planner_completion_script.py`, `test_makefile_planner_targets.py`,
  `test_planner_full_endpoint.py`, `test_planner_cli.py`).
- Full `pytest -q` — **2094 passed in 40s** (was 2080, +14).
- Cockpit unchanged (`vitest`, `tsc`, `vite build` still green
  from PR #120).

**Operator follow-ups**

- Add `make planner-clone ARGS="<src> [target_thread]"` so the
  whole "rerun with a different thread" flow is in the
  Makefile too.
- Right-rail entrypoint from the cockpit chat thread (open the
  planner panel inline when the agent proposes a plan) — last
  cockpit-side payoff still on the planner roadmap.

## 2026-05-01 — Cursor [A] · cockpit: URL-state sync for /cockpit/planner

**Summary**

Operators can now deep-link to any planner view. The page mirrors
three pieces of UI state in the URL via `useSearchParams`:

  - `?status=<status>` — one of the seven filter states or "all".
  - `?q=<text>` — free-text filter (id / goal / pack_slug).
  - `?selected=<id>` — currently selected plan id.

Defaults are elided (no `?status=all`, no empty `?q=`, no
`?selected=`) so the URL stays short for the common case. Parse is
permissive: unknown statuses fall back to "all", whitespace-only
q / selected become empty / null, malformed values never throw.

The wiring uses `replace` mode so URL updates don't pollute the
browser back-stack with every keystroke / click. Selection promotion
(when nothing is selected, pick the newest plan) writes through the
same updater so the URL reflects the auto-selection too.

Pure helpers (`parsePlannerSearchParams`,
`buildPlannerSearchParams`, `plannerStateEquals`) live in
`lib/plannerUrl.ts` and are pinned by 18 Vitest cases — round-trip
identity, default elision, URL-encoding (spaces / `&` / unicode),
permissive fallback for invalid input.

**Changes**

1. `experiments/neural-showcase-v3/src/lib/plannerUrl.ts` (new) —
   parse / build / equals + `DEFAULT_STATE`.
2. `experiments/neural-showcase-v3/src/lib/plannerUrl.test.ts`
   (new, 18 cases):
   - `parsePlannerSearchParams`: empty URL → defaults; every
     valid status accepted; unknown / empty / whitespace status →
     "all"; q trimmed; whitespace-only q → ""; missing / empty
     / whitespace selected → null; non-empty selected preserved.
   - `buildPlannerSearchParams`: empty for default state; status
     omitted at "all"; q omitted at ""; URL-encoding for spaces,
     `&`, unicode (`☃`); selected omitted at null; stable ordering
     `status / q / selected`.
   - Round-trip identity for default state, fully-filled state,
     status alone, q alone (with spaces).
   - `plannerStateEquals`: true on identical content; false on
     any single field difference.
3. `experiments/neural-showcase-v3/src/pages/Planner.tsx` —
   replaces local `useState` for filter / search / selection
   with `useSearchParams`-backed `urlState`. `updateUrlState`
   writes through `setSearchParams(..., { replace: true })`.
   Selection auto-promotion now flows through the same updater
   so the URL reflects auto-selection. Refetch effect dep-list
   updated to fire only on `statusFilter` (selection changes
   don't refetch the list).

**Tests**

- `pnpm vitest run` — **158 passed (13 files)**, incl. 18 new
  url-helper cases.
- `pnpm tsc --noEmit` — clean.
- `pnpm vite build` — clean.
- `pytest -q` — **2080 passed in 40s** (no Python deltas).

**Cockpit follow-ups**

- Right-rail entrypoint from the cockpit chat thread (open the
  panel inline when the agent proposes a plan) — last item on
  the planner-cockpit roadmap before declaring the operator
  workflow complete.
- Scroll-to-selected on first paint: when `?selected=` is set on
  load, scroll the selected row into view in the left rail so the
  deep-linked plan is immediately visible (small QoL fix).

## 2026-05-01 — Cursor [A] · cockpit: per-step live ticking in PlanFullPanel

**Summary**

Top-priority follow-up from PR #118. The plan panel's step list
now ticks live during a run: every `plan.step.requested` /
`plan.step.allowed` / `plan.step.completed` SSE frame flips the
matching row's status badge in place — no extra round-trip, no
flash, no out-of-order rendering.

The step-state reducer is its own module (`lib/plannerSteps.ts`)
and pure / DOM-free, so the contract with the backend's step
event payloads can be pinned without a React tree. The reducer
honours three subtle rules:

1. **Trace scoping** — only events whose `trace_id` matches the
   most recent `plan.run.started` we've seen are applied. Stray
   events from older reruns whose terminals are still flushing
   are dropped on the floor; the panel always shows the freshest
   run's progress.
2. **Resume idempotency** — re-delivery of the same start frame
   (same `trace_id`) after a `Last-Event-ID` reconnect does not
   reset mid-run progress. Test pins this with referential equality.
3. **Skipped > blocked > failed** — terminal states fall through a
   precedence ladder so a step that is `{skipped:true, ok:false,
   blocked:true}` (which the runner can emit when a previous step
   aborts the run) renders as "skipped", not "blocked" or
   "failed".

The panel seeds an "all pending" snapshot the moment the plan
envelope arrives, so the rows render immediately instead of
waiting for the first SSE frame; once `plan.run.started` lands
the snapshot is keyed to that trace.

Status badges use the same tone palette as the rest of the
cockpit (amber for in-flight via `pulse`, success for ok, alert
for blocked / failed, muted for pending / skipped). Latency on
completed steps renders next to the action via `formatLatencyMs`.

**Changes**

1. `experiments/neural-showcase-v3/src/lib/plannerSteps.ts`
   (new) — pure reducer, snapshot type, helpers
   (`pendingSnapshot`, `applyEvent`, `snapshotInFlight`,
   `stepStatusLabel`).
2. `experiments/neural-showcase-v3/src/lib/plannerSteps.test.ts`
   (new, 20 cases) — every transition pinned:
   - `pendingSnapshot` seeds + empty case.
   - `plan.run.started`: trace-lock, redelivery no-op
     (referential equality), fresh-trace mid-flight reset.
   - Scoping: drops events from a foreign trace, drops
     payloads with no `step_id`, drops cosmetic kinds.
   - `plan.step.requested`: status flip + parallel flag.
   - `plan.step.allowed`: blocked-eager (`allowed=false`) and
     allowed-tooltip (`allowed=true`) paths.
   - `plan.step.completed`: ok / failed (with error) /
     blocked-wins-over-failed / skipped-wins-over-everything /
     non-numeric `took_ms` falls back to undefined.
   - `snapshotInFlight`: true while requested, false on
     completion, false on fresh pending.
   - `stepStatusLabel`: short label for every status.
3. `experiments/neural-showcase-v3/src/components/PlanFullPanel.tsx`
   - `useState<StepLiveSnapshot>` seeded from the plan envelope.
   - SSE callback now feeds step-event kinds through the
     reducer in addition to the existing `REFETCH_KINDS`
     refresh trigger.
   - `Steps` sub-renderer rewritten to take the snapshot and
     render per-step badges + live latency. Header carries an
     amber "live · run in flight" lozenge while
     `snapshotInFlight(snapshot)` is true.

**Tests**

- `pnpm vitest run` — **140 passed (12 files)**, incl. 20 new
  step-reducer cases.
- `pnpm tsc --noEmit` — clean.
- `pnpm vite build` — clean.
- `pytest -q` — **2080 passed in 40s** (no Python deltas).

**Cockpit follow-ups**

- URL-state sync for the `<Planner />` filter strip
  (`?status=running&q=…`) so operators can deep-link to a
  view; mirror the selected `plan_id` in the path so a refresh
  stays put.
- Right-rail entrypoint from the cockpit chat thread (open the
  panel inline when the agent proposes a plan) — the next
  obvious operator workflow.

## 2026-05-01 — Cursor [A] · cockpit: PlanFullPanel + /cockpit/planner page

**Summary**

Operator-facing payoff for the planner backend work shipped in
PRs #109–#117. New page at `/cockpit/planner` lets the operator
inspect any plan's full envelope (plan + steps + reconstructed
runs + lifetime usage), one-click rerun it, and watch the
lifetime rollup update in place via the planner SSE stream.

Two pieces:

1. `<PlanFullPanel />` — self-contained panel that hydrates
   from `fetchFullPlan(planId)`, subscribes to
   `subscribePlannerEvents({ planId })`, and refetches on
   `plan.run.usage` / `plan.completed` / `plan.aborted` /
   `plan.run.started` / `plan.abort.requested` /
   `planner.cloned`. Has Rerun, Abort, and Refresh buttons.
   Honours `cost_usd === null` → "n/a" everywhere.
2. `<Planner />` page — wraps the panel with a list of plans
   (`listPlans`) on the left, status pills + free-text filter
   on top, and a global SSE subscription that refreshes the
   list when new plans land.

Pure helpers extracted from the panel (`statusTone`,
`formatLatencyMs`, `formatStartedAt`, `formatRunSummary`,
`formatLifetimeSummary`, `summariseStep`, `REFETCH_KINDS`,
`shouldAdvanceCursor`) are exported and pinned by 17 Vitest
cases — the formatting that the cockpit will read most often
is locked in without touching the DOM.

The new route is registered in `App.tsx` (lazy-loaded chunk
`Planner-*.js`, 17.6 kB / 4.96 kB gzipped) and a "planner"
anchor was added to the cockpit's top nav so the operator
can jump in with one click.

**Changes**

1. `experiments/neural-showcase-v3/src/components/PlanFullPanel.tsx`
   (new) — drawer panel + pure helpers. ~330 LoC including
   sub-renderers (`PlanMetaRow`, `Steps`, `Runs`, `Lifetime`).
2. `experiments/neural-showcase-v3/src/components/PlanFullPanel.test.ts`
   (new, 17 cases) — pinning every helper:
   - `statusTone` mapping for all 6 statuses + defensive default.
   - `formatLatencyMs`: nullish/NaN/negative → "n/a"; sub-second
     ms with one decimal; ≥1s in seconds with two decimals.
   - `formatStartedAt`: nullish → "—"; UTC string format.
   - `formatRunSummary`: cost honoured (priced + null).
   - `formatLifetimeSummary`: singular/plural "run(s)".
   - `summariseStep`: empty args → "{}", with-args → JSON.
   - `REFETCH_KINDS`: positive (must refetch) and negative
     (cosmetic-only) sets.
   - `shouldAdvanceCursor`: null → always advance, otherwise
     strict-greater.
3. `experiments/neural-showcase-v3/src/pages/Planner.tsx`
   (new) — `/cockpit/planner` page hosting the panel + list.
4. `experiments/neural-showcase-v3/src/App.tsx` — register
   `/cockpit/planner` route, lazy-loaded.
5. `experiments/neural-showcase-v3/src/pages/Cockpit.tsx` —
   add "planner" anchor to the top-bar nav so the operator
   can jump from the main cockpit to the planner page.

**Tests**

- `pnpm vitest run` — **120 passed (11 files)**, including
  17 new cases.
- `pnpm tsc --noEmit` — clean.
- `pnpm vite build` — clean. Planner chunk 17.6 kB / 4.96 kB
  gzipped.
- `pytest -q` — **2080 passed in 40s** (no Python deltas).

**Cockpit follow-ups**

- Step-level live updates: stream `plan.step.completed` into
  the panel and render a per-step status row that ticks live
  during a run.
- URL-state sync for the filter strip
  (`?status=running&q=…`) so the operator can deep-link to a
  filter view.
- Right-rail entrypoint from the main cockpit chat thread
  (open the panel inline when the agent proposes a plan).

## 2026-05-01 — Cursor [A] · cockpit: typed planner client + Vitest contract

**Summary**

First slice of cockpit ↔ planner wiring. Adds a typed
TypeScript client (`experiments/neural-showcase-v3/src/lib/planner.ts`)
that pins the shape of every backend planner endpoint shipped
in PRs #109–#116, plus a Vitest suite that locks the
contract so a backend rename can't silently break the React
cockpit.

The client speaks all five surfaces:
`GET /api/planner` (list with filters),
`GET /api/planner/{id}/runs` (history, newest-first),
`GET /api/planner/{id}/full` (aggregate envelope with
`usage_lifetime`), `POST /api/planner/{id}/abort`,
`POST /api/planner/{id}/rerun` (one-shot clone+approve+run),
and `subscribePlannerEvents` for the SSE stream
(`/api/planner/events`) — including `Last-Event-ID`-style
resume via `after_id`.

Cost rendering uses `formatCostUSD` so the n/a vs $0.00
distinction surfaced by `/full`'s `has_priced_models` flag
is preserved end-to-end. Header propagation
(`x-tars-policy-mode`, `x-meeet-trace-id`) is plumbed
through every request that mutates server state.

**Changes**

1. `experiments/neural-showcase-v3/src/lib/planner.ts`
   (new) — typed client + SSE subscriber. No deps beyond
   the browser fetch / EventSource pair already used by
   the cockpit's other clients.
2. `experiments/neural-showcase-v3/src/lib/planner.test.ts`
   (new, 17 cases) — Vitest contract:
   - URL + querystring construction (`fetchFullPlan` with
     `limit`, `listPlans` filters, `listPlanRuns`,
     `subscribePlannerEvents` filters).
   - Header propagation on `abortPlan` + `rerunPlan`.
   - JSON body shape on `rerunPlan` (and empty body
     fallback).
   - Round-tripping a synthetic `PlanFullResponse` /
     `RerunResponse` through the parser.
   - SSE: `EventSource` wiring, JSON parsing, silent
     drop of malformed frames, `onOpen`/`onError`
     forwarding.
   - `formatCostUSD`: `null` / `undefined` → `"n/a"`;
     numeric → 4-decimal `$x.xxxx`.

**Tests**

- `pnpm -C experiments/neural-showcase-v3 exec vitest run` —
  **103 passed (10 files)**, including the 17 new cases.
- `pnpm -C experiments/neural-showcase-v3 exec tsc --noEmit` —
  clean.
- `pytest -q` — **2080 passed in 40s** (no Python deltas).

**Cockpit follow-ups**

- `PlanFullPanel` React component built on top of this client
  (drawer that opens from the planner list, shows plan +
  runs + lifetime usage, has a one-click Rerun button) —
  next PR.
- Live SSE wiring: stream `plan.run.usage` / `plan.completed`
  frames into the panel so the lifetime rollup updates in
  place after a rerun finishes — same follow-up.

## 2026-05-01 — Cursor [A] · planner: GET /{plan_id}/full aggregate endpoint for cockpit drawer

**Summary**

Adds a one-shot aggregate endpoint
(`GET /api/planner/{plan_id}/full`) the cockpit's plan-detail
drawer can hit on open instead of fanning out across three
separate calls (`GET /{plan_id}`, `GET /{plan_id}/runs`, and
a separate usage rollup query). Bundles the plan envelope,
reconstructed runs (newest-first), and a `usage_lifetime`
block summing every run's per-run rollup.

The lifetime cost rollup is intentionally generous about the
`has_priced_models=false` case: `cost_usd` stays `null` (so
the cockpit renders "n/a", not "$0.00") unless at least one
run reported a priced model. Mixed runs sum *only* the priced
runs' costs. This keeps the n/a label meaningful and prevents
"plan ran but emitted no priced calls" from looking like a
free run.

**Changes**

1. `web_extras/routers/planner.py` —
   - New `GET /{plan_id}/full` route directly after
     `/{plan_id}/runs` so the two endpoints sit next to
     each other in the source. Same `limit` semantics as
     `/runs`.
   - Iterates the reconstructed runs once and sums calls /
     tokens / latency / cost into a `usage_lifetime` dict
     with `runs_aggregated` count.
   - Top-of-module docstring updated with the new
     endpoint contract (keys, null-cost rule, limit).
2. `tests/test_planner_full_endpoint.py` (new, 7 cases):
   - 404 for unknown plan id.
   - Empty plan (no runs) → empty list + zero-valued
     lifetime block + `runs_aggregated=0`.
   - Two priced runs → lifetime block sums calls / tokens
     / latency / cost.
   - Single unpriced run → `cost_usd=None`,
     `has_priced_models=False`.
   - Mixed priced + unpriced runs → lifetime cost equals
     *only* the priced run's cost; `has_priced_models=True`.
   - In-flight run surfaces in the items list with
     `in_flight=1`.
   - Top-level envelope shape pin: exact key set on
     `body`, `body["runs"]`, `body["usage_lifetime"]`.

**Tests**

- `tests/test_planner_full_endpoint.py` — 7 passed.
- Full `pytest -q` — **2080 passed in 40s**.

**Cockpit follow-ups**

- Drawer can now make one fetch on open and render
  everything (header, runs list, billing pill).
- `runs_aggregated` makes the "across N runs" label trivial.
- `has_priced_models=false` ↔ render "n/a" badge instead of
  "$0.00".

---

## 2026-05-01 — Cursor [A] · planner: Makefile targets + control-tower gate coverage

**Summary**

Wires the planner CLI into the operator-facing Makefile so the
control tower covers planner end-to-end. Adds six targets
(`planner`, `planner-stats`, `planner-list`, `planner-runs`,
`planner-show`, `planner-smoke`) and folds `planner-smoke`
into `gate-control-tower` so a planner regression cannot land
silently while other cockpit checks stay green. A 12-case
contract test pins the target shape so future changes to the
CLI prompt a Makefile update.

**Changes**

1. `Makefile` —
   - New section "Planner CLI (operator scripting +
     control-tower smoke)" with six targets.
   - All targets shell into `python -m
     backend.core.planner.cli` via the `PLANNER` macro so
     they share the same SQLite WAL DBs as the host process
     (safe to run alongside a live cockpit).
   - `planner` is a free-form passthrough
     (`make planner ARGS="list --status approved"`).
   - `planner-runs` and `planner-show` short-circuit with
     `exit 2` and a usage hint when `ARGS=<plan_id>` is
     missing.
   - `planner-smoke` runs synthesize → show → delete on a
     bundled goal (`PLANNER_GOAL`, default
     `traders.morning_check`), prints one short success
     line, and is wired into `gate-control-tower`.
   - `.PHONY` line extended.
2. `tests/test_makefile_planner_targets.py` (new, 12 cases):
   - All planner targets listed in `.PHONY`.
   - All planner targets carry a `## help text` so `make
     help` lists them.
   - `gate-control-tower` recipe invokes `planner-smoke`.
   - `planner-runs` and `planner-show` recipes guard
     `[ -z "$(ARGS)" ]` and `exit 2`.
   - `PLANNER` macro points at
     `backend.core.planner.cli` (no parallel script).
   - `planner-smoke` recipe passes `--quiet` to keep the
     gate log clean.

**Tests**

- `tests/test_makefile_planner_targets.py` — 12 passed.
- Hand-tested:
  - `make planner-smoke` → `planner-smoke ok (plan_id=…)`.
  - `make planner-stats` → JSON stats envelope.
  - `make planner-runs` (no ARGS) → "usage: …" + `exit 2`.
- Full `pytest -q` — **2073 passed in 40s**.

**Cockpit follow-ups**

- Surface `gate-control-tower` output (now including
  `planner-smoke ok (plan_id=…)`) in the release-readiness
  banner so the operator can see at a glance that planner
  scripting still works.

---

## 2026-05-01 — Cursor [A] · planner: bash completion script + drift-guard tests

**Summary**

Operator quality-of-life follow-up to the planner CLI. Adds
`scripts/planner-completion.bash` so `tab` after a planner
subcommand fills in flags, mode/status enum values, and (for
the subcommands that take a positional `plan_id`) live plan
ids fetched from `python -m backend.core.planner.cli list`.
A small Python contract test guarantees the script never
drifts out of sync with the actual CLI's `_DISPATCH` map and
flag declarations.

**Changes**

1. `scripts/planner-completion.bash` (new, executable):
   - Provides a `_tars_planner` completion function and
     registers it on the `tars-planner` alias (set up by the
     operator).
   - Handles all 11 subcommands (`list`, `show`, `runs`,
     `stats`, `synthesize`, `approve`, `reject`, `run`,
     `abort`, `clone`, `delete`).
   - Per-subcommand flag tables (`--approve`, `--run`,
     `--mode`, `--thread-id`, etc.); value completion for
     enum-typed flags (`--mode → autopilot|confirm|dry_run`,
     `--status → proposed|approved|…`).
   - Live `plan_id` completion sourced from
     `cli list --quiet`, JSON-parsed in a tiny inline Python
     snippet; cached for 5s inside the same shell session so
     back-to-back tabs do not re-shell.
   - Documented install paths in the header (Linux / macOS
     `bash-completion@2`).
2. `tests/test_planner_completion_script.py` (new, 10 cases):
   - Script exists, is executable, has a shebang.
   - `bash -n` parse-only check passes.
   - Every key in `_DISPATCH` is advertised in
     `_TARS_PLANNER_CMDS` (and vice versa — no extras).
   - Per-subcommand flag tables cover the flags actually
     declared in `_build_arg_parser` (parametrised over
     `list`, `synthesize`, `run`, `clone`, `delete`).
   - `--mode` completion lists exactly
     `autopilot|confirm|dry_run`.
   - `--status` completion lists exactly the values of
     `PlanStatus` (so a future enum add prompts an update).

**Tests**

- `tests/test_planner_completion_script.py` — 10 passed.
- Full `pytest -q` — **2061 passed in 42s**.

**Operator note**

```
alias tars-planner='python -m backend.core.planner.cli'
source scripts/planner-completion.bash
tars-planner clone --<TAB>   # → --approve --goal --help --mode --quiet --run --thread-id
tars-planner show <TAB>      # → live plan_id list
```

---

## 2026-05-01 — Cursor [A] · planner: one-shot rerun (CLI clone --approve/--run + POST /rerun)

**Summary**

Closed the loop on the rerun-via-clone flow shipped in PR #108
by adding a one-shot composition over `clone` + `approve` + `run`:

- **CLI**: `clone --approve` flips the new plan to `approved`
  in the same call; `--run` (which implies `--approve`) then
  dispatches it through `PlanRunner` so an operator can rerun
  a finished plan with a single shell invocation. `--mode`
  overrides the policy gate for the run portion.
- **HTTP**: `POST /api/planner/{plan_id}/rerun` is a
  convenience endpoint over the same composition, intended
  for the cockpit's "Rerun" button. Body / header support
  mirrors `/clone` plus optional `mode` (or
  `x-tars-policy-mode` header).
- **Audit lane**: `planner.cloned` event now carries
  `auto_approved` and `auto_run` boolean flags, and the
  timeline summariser collapses them into a single readable
  label (`· rerun` for auto_run, `· auto-approved` for the
  approve-only case).

Backwards compatibility is preserved: bare `clone` still
returns a `proposed` plan with no auto-flip, and the existing
`POST /api/planner/{plan_id}/clone` route is unchanged.

**Changes**

1. `backend/core/planner/cli.py` —
   - `_cmd_clone` now accepts `--approve`, `--run`, and
     `--mode autopilot|confirm|dry_run`. After the clone is
     persisted and `planner.cloned` is emitted, the handler
     optionally flips status to `approved` then dispatches
     `PlanRunner.run` (using `resolve_mode(request_arg=...)`
     so the env / fallback chain still applies). The
     response gains `auto_approved`, `auto_run`, and
     `run_result` keys (the latter is `None` when `--run`
     was not requested).
   - Errors during the `--run` phase surface a structured
     `plan_run_failed` envelope with `plan_id` (the new
     clone's id) and `source_plan_id` so the operator can
     still see what was created.
   - Module docstring usage block updated.
2. `web_extras/routers/planner.py` —
   - New `POST /api/planner/{plan_id}/rerun` endpoint. Body
     supports `thread_id`, `goal_override`, `mode`. Headers
     `x-meeet-trace-id`, `x-tars-thread-id`,
     `x-tars-policy-mode` carry the same semantics as the
     other endpoints. Composes clone + approve + run inside
     a single `trace_scope` so all of the resulting events
     stitch together. Emits `planner.cloned` with
     `auto_approved=true` and `auto_run=true`. Run errors
     surface as 409 with `{reason, message, plan_id,
     source_plan_id}`.
   - Top-of-module docstring updated with the new endpoint
     contract.
3. `backend/core/search/timeline.py` —
   - `_summarise_event` for `planner.cloned` now reads
     `auto_run` / `auto_approved` and renders one of
     `· rerun`, `· auto-approved`, or no extra suffix
     (legacy clones).
4. `tests/test_planner_rerun.py` (new, 13 cases):
   - CLI: `clone --approve` flips status; `clone --run`
     implies approve and produces a `run_result`; bare clone
     still proposes (compat); unknown plan id surfaces a
     proper error envelope; argparse rejects an unknown
     `--mode` choice with exit 2.
   - HTTP: 404 on unknown plan; happy path returns the new
     plan + run result with `source_plan_id`; emits
     `planner.cloned` with both auto flags; an unknown
     `mode` string falls back to the env default (pinned
     behaviour); `thread_id` body override binds to the
     clone.
   - Timeline summariser renders `· rerun` for
     `auto_run=true` (and not `auto-approved`), and
     `· auto-approved` for `auto_approved=true,
     auto_run=false`.

**Tests**

- `tests/test_planner_rerun.py` — 13 passed.
- Existing planner CLI + clone suites (`test_planner_cli.py`,
  `test_planner_clone.py`) — 36 passed (no regression).
- Full `pytest -q` — **2051 passed in 47s**.

**Cockpit follow-ups**

- Wire the existing "Rerun" button on the plan card to
  `POST /api/planner/{id}/rerun` instead of the previous
  three-call flow (clone → approve → run). The button can
  now show a loading spinner once and surface the
  `run_result.status` directly.
- Render the new timeline labels: `· rerun` for one-shot
  reruns, `· auto-approved` for clone-then-approve flows.

---

## 2026-05-01 — Cursor [A] · planner: dedicated plan.run.usage event for billing dashboards

**Summary**

The cost / token rollup for each plan run now ships as its own
top-level event (`plan.run.usage`), in addition to being
embedded in the terminal `plan.completed` / `plan.aborted`
payload (existing behaviour unchanged). This unblocks the
single-line billing query the cockpit and any meeet.world
dashboard wants:

```sql
SELECT * FROM events WHERE kind='plan.run.usage'
```

…instead of having to walk every terminal event payload and
parse a nested `usage` block.

**Changes**

1. `backend/core/planner/runner.py` —
   - Module docstring's events-emitted list now mentions
     `plan.run.usage` (between `plan.step.completed` and the
     terminal events).
   - In `PlanRunner.run`, immediately after the
     `_compute_run_usage(trace_id=trace_id)` call and before
     emitting the terminal event, the runner now emits
     `plan.run.usage` with `plan_id`, `status` (the
     terminal status that's about to be applied),
     `parent_trace_id` (plan's birth trace), and the same
     `usage` block. Always fires — even when no priced model
     ran — so "ran but emitted nothing" cases stay observable.
2. `web_extras/routers/planner.py` —
   `_PLAN_EVENT_KINDS` (the SSE allow-list)
   includes `plan.run.usage`, so the
   `GET /api/planner/events` stream picks it up.
3. `backend/core/search/timeline.py` —
   `_RELEVANT_EVENT_KINDS` now includes `plan.run.usage`;
   `_summarise_event` formats it as
   `plan=<id> · status=<status> · calls=N · tokens=A+B · cost=$X` 
   when a priced model fired, falling back to `cost=n/a` when
   `has_priced_models=false`.
4. `tests/test_planner_runner.py` —
   `test_run_happy_path_completes_and_emits_events` updated
   to expect `plan.run.usage` in the kinds-in-order list
   (between `plan.step.completed` and `plan.completed`).
5. `tests/test_planner_run_usage_event.py` (new, 8 cases):
   - `plan.run.usage` fires on completion, with the right
     payload shape (`plan_id`, `status="completed"`,
     `parent_trace_id`, `usage`).
   - Same on abort, with `status="aborted"`.
   - The `usage` block is identical to what travels on the
     terminal event (consumers see the same numbers
     regardless of which event they read).
   - The event lives on the run's per-run trace, not the
     plan's birth trace, so trace-scoped queries still work.
   - Planner SSE allow-list contains the new kind.
   - Timeline relevant-kinds list contains the new kind.
   - Timeline summariser renders priced + unpriced cost
     correctly (`$X.XXXX` vs `n/a`).

**Tests**

- `tests/test_planner_run_usage_event.py` — 8 passed.
- `tests/test_planner_runner.py` — 19 passed.
- Full `pytest -q` — **2038 passed in 52s**.

**Cockpit follow-ups**

- Activity stream can now render a single "rollup" pill per
  run instead of opening the terminal event card to read
  cost data.
- Billing dashboard query simplifies to one `kind=` filter.

---

## 2026-05-01 — Cursor [A] · tests: unbreak test_release_desktop_workflow after workflow file relocation

**Summary**

PR #4 (`d1984f1`) intentionally moved the release workflow out
of `.github/workflows/release-desktop-tagged.yml` to the repo
root (`release-desktop-tagged.yml`) to reset a stuck GitHub
`workflow_id`. The contract test still hard-coded the old path,
which dragged the full pytest suite from 2030 green down to
2024 passed + 5 errors. This patch teaches the test to look at
the new location first and fall back to the legacy path so old
branches keep working too.

**Changes**

- `tests/test_release_desktop_workflow.py` — added a
  `_resolve_workflow_path()` helper that walks
  `(REPO/release-desktop-tagged.yml,
    REPO/.github/workflows/release-desktop-tagged.yml)` in
  order and raises a clear "checked these N paths" error if
  neither exists. Module docstring updated to explain the
  relocation.

**Tests**

- `tests/test_release_desktop_workflow.py` — 9 passed.
- Full `pytest -q` — **2030 passed in 38s** (was 2024 + 5
  errors before this patch).

---

## 2026-05-01 — Cursor [A] · planner: surface trace_id + parent_trace_id on PlanRun history

**Summary**

Cockpit-facing follow-up to PR #109 (per-run trace_id). The
reconstructor now exposes the per-run `trace_id` *and* the
plan's birth `parent_trace_id` on every `PlanRun.to_dict()` and
on the JSON envelope returned by
`GET /api/planner/{plan_id}/runs`. The cockpit can now:

- deep-link from one run row straight to its trace lane
  (`trace_id`),
- group all runs of the same plan under one collapsible node
  (`parent_trace_id`),
- pivot from "rerun via clone" output back to the original
  synthesis trace without an extra API call.

**Changes**

1. `backend/core/planner/history.py` —
   - `PlanRun` gains a `parent_trace_id: Optional[str]` field
     (defaults to `None` for legacy events that pre-date PR
     #109).
   - `to_dict()` exposes both `trace_id` (per-run, stamped on
     `plan.run.started`) and `parent_trace_id` (plan's birth
     trace, copied verbatim from the event payload).
   - Both `reconstruct_runs` and `reconstruct_runs_async` /
     `_reduce_rows` now read `parent_trace_id` from the
     `plan.run.started` payload when constructing a new
     `PlanRun`.
2. `tests/test_planner_history_traces.py` (new, 4 cases):
   - `to_dict()` exposes `trace_id` + `parent_trace_id`.
   - Legacy `plan.run.started` (no `parent_trace_id` key) →
     `parent_trace_id=None`, no crash.
   - Two sibling runs share the same `parent_trace_id` and
     have distinct per-run `trace_id`s.
   - HTTP `GET /{plan_id}/runs` envelope surfaces both fields
     verbatim.
   - Tests use a `_emit_in_fresh_trace` helper that wraps
     each emit in its own `trace_scope` so they do not depend
     on whatever `current_trace()` ContextVar a prior test
     happens to have left in place.

**Tests**

- `tests/test_planner_history_traces.py` — 4 passed.
- Full `pytest -q --ignore=tests/test_release_desktop_workflow.py`
  — **2021 passed in 45s**.
- `tests/test_release_desktop_workflow.py` is pre-existing red
  (5 errors) caused by a previous merge that renamed
  `.github/workflows/release-desktop-tagged.yml`; out of scope
  for this PR.

**Cockpit follow-ups**

- Render `trace_id` as an inline pill on each run row that
  links to `/cockpit/trace/<id>` (existing trace viewer).
- Group consecutive run rows by `parent_trace_id` so the
  inbox can collapse "all runs of plan X" behind a single
  expander.

---

## 2026-05-01 — Cursor [A] · planner: per-run trace_id (each run gets its own trace, plan trace becomes the parent)

**Summary**

Made every plan run independently observable. Previously
`PlanRunner` reused the plan's birth `trace_id` for all of its
runs via `trace_scope(parent=plan.trace_id)`, which meant
concurrent runs of the same plan (and the rerun-via-clone flow)
all bled events into a single trace. As a side-effect the per-run
cost rollup needed a time-window clamp to disambiguate which
`usage.tokens` events belonged to which run.

Now each run mints a fresh `trace_id` and the plan's birth trace
travels along as `parent_trace_id` on `plan.run.started` so the
synthesis ↔ execution link is preserved. The cost rollup query
becomes a clean trace-scoped SELECT — no time clamp, no off-by-one
risks at run boundaries.

**Changes**

1. `backend/core/planner/runner.py` —
   - `PlanRunner.run` now uses `trace_scope()` (no `parent=`) so
     each invocation gets its own fresh trace id. The original
     `plan.trace_id` is added to the `plan.run.started` payload
     as `parent_trace_id`.
   - The return dict now exposes both `trace_id` (per-run) and
     `parent_trace_id` (plan birth) so callers can correlate
     across surfaces.
   - Updated module docstring to explain the new contract.
   - `_compute_run_usage(*, trace_id)` lost its `started_at` /
     `finished_at` parameters — the trace is now sufficient to
     scope the rollup. Docstring updated to reflect the new
     semantics.
2. `backend/core/planner/history.py` — refreshed the module
   docstring: noted that the runner now mints per-run traces but
   the reconstructor still groups by event order (works for
   legacy events and degrades gracefully).
3. `tests/test_planner_per_run_trace.py` (new, 4 cases):
   - Two runs of (cloned) twin plans get distinct fresh
     `trace_id`s and both report the plan's birth trace as
     `parent_trace_id`.
   - `plan.run.started` payload carries `parent_trace_id`.
   - The terminal event (`plan.completed`) for a run shares the
     trace with its `plan.run.started` (intra-run consistency).
   - `usage.tokens` events fire on the run's own trace, so the
     rollup attributes them to the right run with no time-window
     clamping required.
4. `tests/test_planner_run_usage.py` —
   - Updated all `_compute_run_usage` call sites to the new
     no-`started_at` / no-`finished_at` signature.
   - Renamed `test_compute_run_usage_clamps_to_time_window` to
     `test_compute_run_usage_does_not_clamp_by_time_window_anymore`
     and inverted the assertion: events outside the (former)
     window are now correctly summed when they share the trace.

**Tests**

- `tests/test_planner_per_run_trace.py` — 4 passed.
- `tests/test_planner_run_usage.py` — 11 passed.
- Full planner-related selection (`runner`, `history`, `clone`,
  `cli`, `sse`, `synthesis`, `thread_timeline`, plus the two
  above) — 178 passed.
- Full `pytest -q` — **2026 passed in 44s**.

**Cockpit follow-ups**

- The "rerun" button can now show `trace_id` and `parent_trace_id`
  side-by-side so operators can pivot from the new run back to
  the plan's synthesis trace.
- Activity stream entries can be grouped on `parent_trace_id`
  to render "all runs of plan X" as a single collapsible
  section.
- The cost ledger drawer no longer needs run-window awareness —
  a `WHERE trace_id=<run_trace>` is now sufficient and matches
  what `_compute_run_usage` does internally.

**Optional next step**

- Persist the per-run `trace_id` on `PlanRun.to_dict()` so the
  history endpoint can expose it alongside `started_at` /
  `finished_at` for cockpit deep-linking.

---

## 2026-05-01 — Cursor [A] · planner: clone — rerun a plan without history mutation

**Summary**

A clone-and-relaunch primitive that lets the operator "rerun"
a finished plan without mutating its terminal status. The
original keeps its `completed` / `aborted` row, the clone
enters the inbox at `proposed` so the operator can approve it
again. Exposes both an HTTP endpoint and a CLI subcommand,
plumbed into the timeline + SSE allow-lists so the cockpit
audit lane can render the parent → child relationship.

**Changes**

1. `backend/core/planner/store.py` — new
   `PlannerStore.clone(plan_id, *, thread_id=None,
   trace_id=None, goal_override=None)`. Returns a fresh
   `Plan` with a brand new `id`, `status="proposed"`, fresh
   timestamps; deep-copies steps via `PlanStep.from_dict(s.to_dict())`
   so mutating either tuple later doesn't bleed. `goal_override`
   is `.strip()`-ed to mirror the synthesizer's normalisation.
   Returns `None` when the source id is unknown.
2. `web_extras/routers/planner.py` — new
   `POST /api/planner/{plan_id}/clone`. Body may include
   `thread_id` (rebind to a different chat) and `goal_override`.
   Wraps the call in `thread_id_scope` + `trace_scope` so the
   clone gets a fresh `trace_id` for downstream correlation.
   Emits `planner.cloned` with `plan_id` (clone), `source_plan_id`
   (original), `source_status`, `model`, `pack_slug`,
   `playbook_id`, `step_count`, `thread_id_rebind`,
   `goal_overridden`. 404s on unknown source ids. Adds the
   new event kind to `_PLAN_EVENT_KINDS` so the SSE feed
   picks it up.
3. `backend/core/planner/cli.py` — new `clone` subcommand:
   `python -m … clone <plan_id> [--thread-id <id>] [--goal "..."]`.
   Mirrors the HTTP wiring exactly (same trace scope, same
   event payload). Added to the global `_DISPATCH` table and
   the docstring usage block.
4. `backend/core/search/timeline.py` —
   `_RELEVANT_EVENT_KINDS` now includes `planner.cloned`;
   `_summarise_event` formats it as
   `plan=<new_id> · from=<src_id> · steps=N` with optional
   ` · thread-rebind` / ` · goal-override` suffixes.
5. `tests/test_planner_clone.py` (new, 13 cases): store-level
   clone returns fresh proposed plan with new id and deep-copied
   steps (original untouched); thread_id override applied;
   goal_override stripped; unknown plan returns `None`; HTTP
   happy path returns the new plan + `source_plan_id` and emits
   `planner.cloned`; HTTP body `thread_id` flips
   `thread_id_rebind=true`; HTTP body `goal_override` flips
   `goal_overridden=true`; HTTP 404 envelope; CLI happy path
   + overrides + 404; timeline summariser produces the
   expected string with / without override flags.

**Tests**

`pytest -q` → 2022 passed in 44.51s (was 2009; +13 new).

**Follow-ups**

- Cockpit "Rerun" button on the plan card calls
  `POST /api/planner/{id}/clone` then immediately approves +
  runs the returned plan id (two-call flow; `clone` itself
  stays read-mostly so destructive intent is explicit).
- Optional `clone --approve` CLI flag that chains the new
  plan into the approved status without an extra subcommand.

## 2026-05-01 — Cursor [A] · planner: shell CLI (synthesize/run/list/abort/…)

**Summary**

Operator-facing scripting tool that mirrors `replay_cli`'s shape.
Exposes every planner CRUD + lifecycle operation as a subcommand
that prints one machine-friendly JSON object per call (so it
pipes cleanly into `jq`) and uses POSIX exit codes (0 on `ok`,
1 otherwise) so cron / Make targets can branch on success.
Reads the same env vars the host uses (`TARS_PLANNER_DB_PATH`,
`MEEET_STORE_PATH`, `TARS_POLICY_MODE`) and shares the SQLite
WAL DBs with the running cockpit — safe to run side-by-side
with the FastAPI surface.

Three jobs the CLI unblocks:

- **Operator scripting** — chain
  `synthesize | jq -r .plan.id | xargs -I{} python -m … approve {}`
  in cron jobs.
- **Cold-start recovery** — when the HTTP layer is down the CLI
  is the only path to inspect / reset planner state.
- **Fleet rollouts** — shell out to TARS from a higher-level
  orchestrator without going through the FastAPI surface.

**Subcommands**

`stats`, `list`, `show`, `runs`, `synthesize`, `approve`,
`reject`, `run`, `abort`, `delete`. Global `--quiet` strips the
JSON indentation so log shippers see one line per call.
`delete` requires `--yes` (otherwise returns
`confirmation_required` so a sleepy operator can't `rm -rf` a
planned op by mistake). `run` honours `--mode` to override
`TARS_POLICY_MODE` per invocation.

**Changes**

1. `backend/core/planner/cli.py` (new) —
   `argparse`-based dispatcher → 10 subcommand handlers
   (`_cmd_list / _cmd_show / _cmd_runs / _cmd_stats /
   _cmd_synthesize / _cmd_approve / _cmd_reject / _cmd_run /
   _cmd_abort / _cmd_delete`). Each handler returns a `dict`
   with `ok` plus per-call payload; the shared `_emit(...)`
   helper renders JSON and maps to exit codes. `_err(...)`
   builds the error envelope with a stable `reason` key. The
   synthesize handler reuses the HTTP route's pack / playbook
   enumeration so the deterministic mapper sees the exact same
   inputs as the API.
2. `tests/test_planner_cli.py` (new, 23 cases): `stats`
   on a fresh DB, `synthesize` happy / empty-goal / no-match,
   `show` 404 / 200, `list` returns count + plans, `list
   --status` filter, unknown status envelope, `--quiet` strips
   indent (single line), `approve` / `reject` flips, `approve`
   404, `approve` on terminal plan refused, `run` 404, `run`
   on un-approved plan refused with `plan_not_runnable`,
   `abort` when not running, `runs` 404 / empty / OK, `delete`
   without `--yes` is a dry-run, `delete --yes` actually drops,
   `delete` 404, full lifecycle round trip
   (synthesize → approve → list → delete → stats).

**Tests**

`pytest -q` → 2009 passed in 44.83s (was 1986; +23 new).

**Follow-ups**

- Tab-completion file (`scripts/planner-completion.bash`) for
  shell users.
- Optional `clone` subcommand that snapshots a finished plan as
  a fresh `proposed` plan (operator-side "rerun" without the
  history mutation).
- Wire the CLI into a `make planner-*` target group so the
  control tower runs it end-to-end as part of the gate.

## 2026-05-01 — Cursor [A] · planner: per-run cost / token rollup on terminal event

**Summary**

After a plan run finishes, the runner now rolls up every
`usage.tokens` event that fired inside its trace_id + wall-clock
window and stamps the totals (`calls`, `tokens_in`, `tokens_out`,
`cost_usd`, `latency_ms_total`, `has_priced_models`) onto the
terminal event payload (`plan.completed` / `plan.aborted`) AND
the `PlanRunner.run` return value. The `/api/planner/{id}/runs`
reflector surfaces the same block via the `PlanRun` dataclass,
so the cockpit's run history drawer can render per-run cost +
token / latency totals without an extra round-trip to the usage
ledger.

`cost_usd` is `None` (not `0.0`) when no priced model fired, so
the cockpit shows "n/a" instead of falsely advertising a free
run. Filtering by both `trace_id` AND time window keeps parallel
runs of the same plan from bleeding into each other's totals
(the runner currently inherits the plan's birth trace, so two
concurrent runs would otherwise share a trace_id).

**Changes**

1. `backend/core/planner/runner.py`:
   - New `_compute_run_usage(trace_id, started_at, finished_at)`
     async helper. Pulls `usage.tokens` events from the meeet
     store filtered by `trace_id` + `since=started_at`, clamps
     each event's `ts` to `<= finished_at + 1s` (clock-skew
     grace), sums tokens / latency / `cost_usd`. Returns
     `cost_usd=None` when no priced model was summed; otherwise
     rounded to 6 decimals.
   - `PlanRunner.run` captures `run_started_at = time.time()`
     before entering `trace_scope`, computes the rollup right
     before emitting the terminal event, and embeds it as a
     `usage` block on both `plan.completed` and `plan.aborted`
     payloads. Also added to the function's return dict.
2. `backend/core/planner/history.py`:
   - `PlanRun` dataclass gains `usage_calls`, `usage_tokens_in`,
     `usage_tokens_out`, `usage_cost_usd`, `usage_latency_ms_total`,
     `usage_has_priced_models` fields. `to_dict()` exposes them
     under a single `usage` block matching the runner's shape.
   - `_close_run(...)` reads the `usage` block off the terminal
     event payload (defaulting to a zero rollup with
     `cost_usd=None` when missing — keeps legacy events readable).
3. `tests/test_planner_run_usage.py` (new, 11 cases): zero-rollup
   for `trace_id=None`, sums matching events, returns `None` cost
   for unpriced models, filters by trace_id, clamps to time
   window, runner stamps usage on `plan.completed`, runner stamps
   usage on `plan.aborted` (handler raises mid-step), zero usage
   when no `usage.tokens` event, reconstructor surfaces the
   block, reconstructor handles legacy missing-usage payload, and
   end-to-end HTTP round trip via `POST /plan` →
   `POST /status` (approve) → `POST /run` → `GET /runs`.

**Tests**

`pytest -q` → 1986 passed in 46.85s (was 1975; +11 new).

**Follow-ups**

- Once each run gets its own trace (rather than inheriting the
  plan's birth trace), the time-window clamp in
  `_compute_run_usage` becomes redundant — drop it then.
- Cockpit run-history drawer can render `usage.cost_usd` +
  `usage.tokens_*` per row; the `has_priced_models=false` case
  should show "n/a · N tokens" instead of "$0.00".
- Consider folding the rollup into a dedicated `plan.run.usage`
  event so dashboards can query it without parsing the
  terminal event payload.

## 2026-05-01 — Cursor [A] · planner: per-plan run history + Last-Event-ID SSE resume

**Summary**

Two cockpit-facing reads land together: a new
`GET /api/planner/{plan_id}/runs` endpoint that reconstructs every
past execution of one plan from the meeet event store (no parallel
"runs" table — single source of truth), and `Last-Event-ID` header
support on `GET /api/planner/events` so a vanilla `EventSource`
reconnect picks up where it left off without cockpit-specific
glue. The header wins over the `after_id` query param when both
are supplied (matches the SSE spec).

**Changes**

1. `backend/core/planner/history.py` (new) — event-sourced
   reconstructor.
   - `RunStep` / `PlanRun` dataclasses; `to_dict()` matches the
     shape the cockpit's run inbox renders.
   - `reconstruct_runs_async(plan_id, *, store=None, limit=1000)`
     pulls every kind in `_RUN_EVENT_KINDS` (`plan.run.started` /
     `plan.step.{requested,allowed,completed}` /
     `plan.completed` / `plan.aborted` / `plan.abort.requested` /
     `plan.run.exception`), filters to the matching `plan_id`,
     and walks them id-ascending. Run boundaries: a
     `plan.run.started` opens, `plan.completed` /
     `plan.aborted` close. An open run with no terminal event
     surfaces as `status="running"`. A second start with no
     terminal in between auto-closes the prior run as
     `aborted no_terminal_event`. Authoritative counters from
     the terminal event (`steps_run` / `steps_blocked` /
     `steps_failed`) override the locally accumulated ones.
   - `reconstruct_runs(...)` is the sync sibling for callers
     that already hold the GIL (e.g. CLI tools).
2. `web_extras/routers/planner.py`:
   - `GET /api/planner/{plan_id}/runs` — 200 with newest-first
     runs + `count` + `in_flight`. 404 when the plan id is
     unknown (defensive; keeps the cockpit from rendering
     ghosts of pruned plans). Optional `limit` query (default
     1000, capped at 5000) caps the per-event-kind fetch.
   - `_resolve_after_id(query, header)` helper — picks the
     effective cursor; header wins over query, returns
     `("header" | "query" | "default")` so the `hello` frame
     can advertise `after_id_source`.
   - `GET /api/planner/events` accepts `Last-Event-ID` header
     (alias-bound) and threads `cursor_source` into
     `_planner_sse_producer`.
   - `_planner_sse_producer(..., cursor_source="default")` —
     `hello` payload now carries `after_id_source` so the
     cockpit can tell whether the resume came from a real
     reconnect or a fresh subscribe.
3. `backend/core/planner/__init__.py` — exports `PlanRun` /
   `RunStep` / `reconstruct_runs` / `reconstruct_runs_async`.
4. `tests/test_planner_history.py` (new, 16 cases): groups one
   run, two runs newest-first, in-flight (no terminal), step
   failure counts override on terminal event, unterminated prior
   run auto-aborted, orphan steps dropped, plan-id filter,
   abort.requested + exception capture, HTTP 404 for unknown
   plan, empty-list when no events, in_flight count, limit
   param, `Last-Event-ID` honoured, header overrides query,
   invalid header falls back to query, default when neither.

**Tests**

`pytest -q` → 1975 passed in 52.10s (was 1959; +16 new).

**Follow-ups**

- Cockpit "Plan Inbox" panel can now subscribe to
  `/api/planner/events?thread_id=…` *and* `GET /{plan_id}/runs`
  for the per-plan history drawer.
- Keep `_RUN_EVENT_KINDS` in `history.py` aligned with the
  runner's emit calls if a new event family is added.
- Optional next step: prune-stale-runs CLI flag (`--gc-orphans`)
  that walks the meeet store for plans where every run is
  closed and trims the oldest events past a retention horizon.

## 2026-05-01 — Cursor [A] · planner: SSE event stream + meeet.list_events(after_id)

**Summary**

The cockpit needs a live feed of `plan.*` events to render the
"approval inbox" + per-step run progress. This PR adds a polling
SSE endpoint at `GET /api/planner/events` plus the missing
`after_id` cursor on the meeet store that powers it. Mirrors the
existing `/api/awareness/stream` shape: `hello` / event frames /
`bye` on `max_duration_reached` or client disconnect.

**Changes**

1. `backend/core/meeet/store.py` — `MeeetStore.list_events` /
   `_list_sync` gain an `after_id: int | None` param. SQLite
   `id` is `INTEGER PRIMARY KEY AUTOINCREMENT` so it's a
   monotonic cursor; passing the highest id you've already
   seen returns only strictly-newer events. Combines cleanly
   with existing `kind` / `kind_prefix` / `since` / `trace_id`
   / `session_id` / `only_unpushed` filters.
2. `web_extras/routers/planner.py`:
   - New `_PLAN_EVENT_KINDS` tuple — every kind the SSE may
     surface (kept in sync with the timeline allow-list:
     `plan.proposed` / `planner.synthesis.{completed,failed}` /
     `planner.{approved,rejected,deleted}` / `plan.run.started` /
     `plan.step.{requested,allowed,completed}` /
     `plan.completed` / `plan.aborted` /
     `plan.abort.requested`).
   - `_planner_sse_producer(...)` — async generator that emits
     a `hello` frame (carries the active `after_id` + filter
     metadata), then polls the meeet store every
     `poll_interval_s` for new matching events, emits one frame
     per event in id-ascending order, advances the cursor (even
     for filter-rejected rows so they aren't re-read forever),
     and closes with `bye{reason}` when `max_duration_s` is
     reached. `asyncio.CancelledError` (client disconnect)
     emits a `bye{reason='client_disconnect'}` frame.
   - `_sse_frame(...)` helper renders the SSE wire format
     (`id: <N>\n` + `data: <json>\n\n`).
   - `_payload_matches(...)` — applies `plan_id` / `thread_id`
     filters against the event payload.
   - `GET /api/planner/events` route mounted **before**
     `/{plan_id}` so Starlette doesn't capture `events` as a
     plan id. Query params: `plan_id?` / `thread_id?` /
     `after_id` (default 0) / `poll_interval_s` (0–10s,
     default 1.0) / `max_duration_s` (0–900s, default 120).
3. `tests/test_planner_sse.py` (new, 9 cases) cover:
   - `MeeetStore.list_events(after_id=N)` returns only rows
     with `id > N`; combines with `kind_prefix` filter.
   - SSE producer emits `hello` first, plan events in
     id-ascending order, and `bye{max_duration_reached}`.
   - `after_id` skips already-seen events on resume.
   - `plan_id` and `thread_id` filters drop non-matching
     rows but still advance the cursor.
   - `hello` frame carries the active `after_id` + filter
     metadata.
   - HTTP endpoint mounts at `/api/planner/events` and does
     NOT collide with `/{plan_id}` (the latter still 404s
     for unknown plan ids).

**Tests**

`pytest -q` → **1959 passing**. `ReadLints` clean.

**Follow-ups**

- Optional `Last-Event-ID` header parsing on the SSE endpoint
  for native EventSource resumption (currently the cockpit
  passes `after_id` as a query param).
- Reverse — SSE push to the meeet bridge so a single TARS
  process can fan plan events out across multiple cockpit
  tabs without each one polling.
- Cockpit: a live "Plan inbox" panel under the cockpit
  that subscribes to `/api/planner/events?thread_id=…` for
  the active chat thread.

## 2026-05-01 — Cursor [A] · timeline: plan.* events visible in per-thread feed

**Summary**

Phase L6.2 added a full `plan.*` event family but the per-thread
timeline (`backend/core/search/timeline.py`) had not been taught
about it. Cockpit threads where the operator ran a plan rendered
gaps where the plan lifecycle should have shown. This PR teaches
the timeline allow-list + summariser the new event kinds so plan
synthesis, approval, and run progress now render alongside chat
messages, tool calls, and policy events.

**Changes**

1. `backend/core/search/timeline.py`:
   - `_RELEVANT_EVENT_KINDS` now includes `plan.proposed`,
     `planner.approved`, `planner.rejected`, `plan.run.started`,
     `plan.step.{requested,allowed,completed}`, `plan.completed`,
     `plan.aborted`, and `plan.abort.requested`.
   - `_summarise_event` gains per-kind branches for every
     planner kind. Common shape is `plan=<id> · …`. The
     `plan.step.completed` summariser ranks `skipped` >
     `blocked` > `failed` > `ok` so the first non-default
     state always wins. `plan.proposed` truncates the goal at
     60 chars to keep the row scannable.
2. `tests/test_thread_timeline.py` — 12 new cases:
   - Pin the new kinds in `_RELEVANT_EVENT_KINDS`.
   - Pin every per-kind summary shape (label, fields, edge
     cases like long goal, zero destructive, parallel tag).
   - End-to-end: emit `plan.proposed` + `plan.completed` with
     a matching `payload.thread_id` and assert both appear in
     the thread's timeline with the right summaries.

**Tests**

`pytest -q` → **1950 passing**. `ReadLints` clean.

## 2026-05-01 — Cursor [A] · Phase L6.2: planner runner (PlanRunner + abort + plan.* events)

**Summary**

Second slice of Phase L6: the runner that takes an `approved`
`Plan`, drives every step through the same policy gate the playbook
runner uses, and emits the `plan.*` lifecycle events spec'd in
L6.2 (`plan.run.started` / `plan.step.{requested,allowed,completed}`
/ `plan.completed` / `plan.aborted`, plus `plan.proposed` at synth
time). Status transitions `approved → running → completed/aborted`
are runner-owned and persisted to the planner store. Cooperative
abort is supported via a per-plan `asyncio.Event` registered in
`PlanRunRegistry`; the registry is observed at every group
boundary, so a long-running run can be stopped without surgery
on the underlying step.

**Changes**

1. `backend/core/planner/runner.py` (new) — `PlanRunner`,
   `PlanRunRegistry`, `PlanRunError` (stable reasons:
   `plan_not_found` / `plan_not_runnable` / `plan_already_running`
   / `status_update_failed`). The runner reuses
   `PlaybookRunner._dispatch` via a thin `_AdaptedStep` adapter so
   the dispatcher logic (awareness snapshots, policy gate, error
   mapping) stays single-sourced. Per-plan abort via
   `PlanRunRegistry.abort(plan_id)` flips an `asyncio.Event` that
   the runner observes between groups (cooperative — never mid-step).
   Skipped steps still emit a `plan.step.completed` with
   `skipped=True` so the cockpit can render them gray.
2. `backend/core/planner/__init__.py` — exports `PlanRunError` /
   `PlanRunner` / `PlanRunRegistry` / `get_run_registry` /
   `reset_run_registry` / `run_plan`. Top-level docstring updated
   to reflect that the runner is no longer a follow-up.
3. `web_extras/routers/planner.py`:
   - `POST /api/planner/{plan_id}/run` — synchronous run; resolves
     `PolicyMode` from the body / `x-tars-policy-mode` header /
     env (in that order). Wraps the run in `thread_id_scope` so
     downstream events inherit the plan's persisted thread id /
     trace id even when the operator pings without those
     headers.
   - `POST /api/planner/{plan_id}/abort` — cooperative abort; 404s
     when the plan isn't currently in flight, otherwise flips the
     registry event and emits `plan.abort.requested`.
   - Synthesis path now also emits `plan.proposed` (the L6.2
     event name) alongside the existing `planner.synthesis.completed`
     so cockpit subscribers can speak the spec vocabulary.
4. `tests/test_planner_runner.py` (new, 21 cases) covers:
   - `PlanRunRegistry` primitives (register / abort unknown /
     unregister / in-flight enumeration).
   - Happy-path run with autopilot mode: status transitions, all
     `plan.*` events emitted in declared order, every event
     stamped with the persisted `thread_id`.
   - Args propagation from `PlanStep.args` into the handler.
   - Entry guards: unknown plan, proposed plan, completed plan,
     already-running plan all raise `PlanRunError` with the right
     reason.
   - Step failure: `on_error="stop"` aborts with `step_failed`,
     `on_error="continue"` keeps going (status stays `completed`
     but `ok=False`).
   - Destructive step in `confirm` mode: blocked by policy gate,
     `plan.step.allowed{allowed=false, reason='blocked_by_policy'}`,
     status flips to `aborted` with `error='blocked_by_policy'`.
   - Cooperative abort: pre-flipped event skips every step; abort
     fired during step N stops step N+1 at the next group boundary.
   - HTTP `/run`: 404 unknown plan, 409 not approved, happy path
     emits `plan.completed`. HTTP `/abort`: 404 when not running,
     happy path emits `plan.abort.requested`.
   - HTTP `/plan` synthesis emits `plan.proposed` with the
     auto-injected thread id.

**Tests**

`pytest -q` → **1937 passing**. `ReadLints` clean.

**Follow-ups**

- Real cloud-LLM voices in the synthesizer (the deterministic
  heuristic-v1 maps "tokens in goal" to playbooks/actions; the
  LLM voice would synthesize a multi-step plan with rationales).
- Cockpit "approval inbox": render `proposed` plans, gate the
  `Run` button on `approved`, surface in-flight plans alongside
  policy confirmations, show step status icons driven by the
  `plan.step.*` event stream.
- Optional `mode=async` on `POST /run` for fire-and-forget
  background runs (current run is synchronous and returns the
  full per-step envelope).

## 2026-05-01 — Cursor [A] · Phase L6 v1: planner foundations (synthesis + persistence)

**Summary**

Phase L6 (Planner / Agent loop) starts here. This PR ships the
*synthesis + persistence* foundations: a deterministic planner that
maps free-form operator goals onto either a registered playbook or a
single-action fallback, persists the resulting Plan in its own
SQLite store, and exposes a complete CRUD HTTP surface. The
event-emitting runner is the next slice.

**Changes**

1. `backend/core/planner/__init__.py` — module entry, public exports.
2. `backend/core/planner/types.py` — `Plan` / `PlanStep` dataclasses
   plus `PlanStatus` enum (`proposed → approved → running → completed
   / aborted / rejected`). `terminal()` + `is_terminal()` helpers.
3. `backend/core/planner/store.py` — `PlannerStore` (SQLite at
   `~/.tars/planner.sqlite`, override via `TARS_PLANNER_DB_PATH`,
   short-circuit via `PLANNER_STORE=disabled`). Schema with
   indexes on `status` / `thread_id` / `created_at`. Additive
   migration tuple `_ADDITIVE_COLUMNS` for forward compat. Async
   CRUD (`insert` / `get` / `list` / `set_status` / `delete` /
   `stats`). Terminal statuses are immutable: `set_status` silently
   refuses to flip a `completed` / `aborted` / `rejected` row back.
4. `backend/core/planner/synthesizer.py` — `synthesize_plan(...)`
   deterministic mapper. Resolution order:
   playbook id → playbook name → playbook tag → action substring →
   single-pack snapshot fallback. Stable error reasons
   (`empty_goal` / `no_match` / `ambiguous_packs` / `unknown_pack`)
   so the HTTP layer can render localised envelopes without parsing
   English. `pinned_pack` lets the operator disambiguate.
5. `web_extras/routers/planner.py` — full HTTP surface mounted at
   `/api/planner`:
   - `POST /api/planner/plan` — synthesize + persist (auto-pulls
     registered playbooks + actions, derives is-snapshot flag from
     action id keywords).
   - `GET /api/planner/{plan_id}` — read one Plan.
   - `GET /api/planner` — list with `status` / `thread_id` /
     `limit` filters.
   - `GET /api/planner/_stats` — `total` + `by_status` counts.
   - `POST /api/planner/{plan_id}/status` — operator transitions
     (`approved` / `rejected` only; `running` / `completed` /
     `aborted` reserved for the runner).
   - `DELETE /api/planner/{plan_id}` — operator-prune.
6. `web_extras/app.py` — mounts `planner_router.router`.
7. `tests/test_planner_synthesis.py` (new, 41 cases) covers:
   - `Plan` / `PlanStep` / `PlanStatus` round-trip + counts.
   - Synthesizer resolution priority + every error reason.
   - PlannerStore CRUD + status transitions + terminal lock +
     filters + stats.
   - HTTP endpoints incl. meeet event emission
     (`planner.synthesis.completed` / `planner.synthesis.failed` /
     `planner.approved` / `planner.deleted`) and `thread_id`
     auto-injection.

**Events emitted**

- `planner.synthesis.completed` (plan_id, goal, model, pack_slug,
  playbook_id, step_count, destructive_step_count).
- `planner.synthesis.failed` (goal, reason, pinned_pack).
- `planner.approved` / `planner.rejected` (plan_id, model,
  pack_slug, playbook_id, step_count).
- `planner.deleted` (plan_id, model, pack_slug, status_at_delete).

All four ride `thread_id` via the contextvar bridge so the cockpit
per-thread audit lane shows planner activity per chat.

**Tests**

- `tests/test_planner_synthesis.py` — 41 cases.
- Full `pytest` — **1916 cases passed**.
- `ReadLints` — clean.

**Follow-up (next PR)**

`PlannerLoop` runner: ingest an `approved` Plan, drive
`PlaybookRunner` in interactive mode, emit
`plan.proposed` / `plan.step.{requested,allowed,completed}` /
`plan.completed` / `plan.aborted` events from L6.2, plus
`POST /api/planner/{plan_id}/run` and abort.

## 2026-05-01 — Cursor [A] · MeeetClient.emit auto-injects thread_id from contextvar

**Summary**

After the ContextVar bridge (PR #99), every router that handles
`x-tars-thread-id` opens `thread_id_scope(...)` so the active chat
thread id rides on the asyncio context. This PR completes the loop
by having `MeeetClient.emit(...)` automatically copy the contextvar's
value into `payload['thread_id']` when the contextvar is set AND the
caller didn't already place `thread_id` in the payload.

This collapses the manual `if x_tars_thread_id: payload['thread_id']
= ...` blocks scattered across routers and orchestrators down to a
single auto-injection at the bridge boundary. Existing call-sites
that explicitly set `thread_id` always win — the contextvar is a
fallback, not an override — so the policy router's per-row re-attach
keeps the same behaviour.

**Changes**

1. `backend/core/meeet/client.py` — `emit(...)` now reads
   `current_thread_id()` and copies it into the merged payload when
   the field is missing. The caller's payload dict is NOT mutated
   (defensive `dict(payload or {})` copy already happens).
2. `tests/test_meeet_auto_thread_id.py` (new, 8 cases) covers
   the happy path, no-op without contextvar, no-op for empty string,
   explicit-payload precedence (incl. explicit None), nested scope
   resolution, immutable caller payload, and `emit(kind)` with no
   payload arg.

**Tests**

- `tests/test_meeet_auto_thread_id.py` — 8 cases.
- `tests/test_thread_id_contextvar.py` — 12 (regression).
- `tests/test_council_thread_linkage.py` — 10 (regression).
- `tests/test_policy_thread_linkage.py` — 12 (regression).
- `tests/test_council.py` — 8 (regression).
- `tests/test_council_parallel.py` — 17 (regression).
- `tests/test_policy.py` — 10 (regression).
- `tests/test_policy_expire_loop.py` — 15 (regression).
- `tests/test_thread_timeline.py` — 27 (regression).
- `tests/test_meeet.py` — 8 (regression).
- Full `pytest` — **1875 cases passed**.

## 2026-05-01 — Cursor [A] · ContextVar bridge: action handlers auto-inherit thread_id

**Summary**

PRs #97 (policy) and #98 (council HTTP) plumbed `x-tars-thread-id`
through the gate and the council's HTTP entry. The remaining gap was
action handlers calling `get_council().deliberate(...)` from inside
`invoke_action` (e.g. `business.daily_brief`,
`traders.summarize_market`): those handlers don't see the request
thread_id directly. This PR closes that gap with a `ContextVar`
bridge so the value flows through asyncio context with no per-handler
plumbing.

**Changes**

1. `backend/core/meeet/tracing.py`
   - New `_thread: ContextVar[str | None]`, `current_thread_id()`,
     and `thread_id_scope(thread_id)` context manager.
   - `thread_id_scope(None)` and `thread_id_scope("")` are no-ops:
     they keep the outer scope's value visible (a router that didn't
     get the header doesn't accidentally clobber an outer value).
   - Nested scopes never leak (token reset in `finally`).
2. `backend/core/meeet/__init__.py` — export
   `current_thread_id`, `thread_id_scope`.
3. `web_extras/routers/domains.py` — `invoke_action` now wraps its
   trace scope in `thread_id_scope(x_tars_thread_id)`. Also added
   the same header to `awareness_snapshot` for parity.
4. `web_extras/routers/policy.py` — `confirm` route opens
   `thread_id_scope(confirmation.thread_id)` so a confirmed
   destructive action's handler runs with the persisted thread id
   bound.
5. `backend/core/council/orchestrator.py` —
   `deliberate(...)` falls back to `current_thread_id()` when no
   explicit `thread_id` kwarg is passed; explicit kwarg still wins
   for call-sites that want to retag.
6. `tests/test_thread_id_contextvar.py` (new, 12 cases) covers
   ContextVar primitives, council fallback, explicit-kwarg
   precedence, and end-to-end flow through `invoke_action` /
   `confirm` (via a fresh `thread_probe` test pack).

**Tests**

- `tests/test_thread_id_contextvar.py` — 12 cases.
- `tests/test_council_thread_linkage.py` — 10 cases (regression).
- `tests/test_policy_thread_linkage.py` — 12 cases (regression).
- Full `pytest` — **1867 cases passed**.

---

_Showing the most recent 60 of 190 entries. Full per-edit log: [`docs/CHANGELOG_AGENTS.md` on GitHub](https://github.com/alxvasilevvv/tars-neural-cockpit/blob/main/docs/CHANGELOG_AGENTS.md)._
