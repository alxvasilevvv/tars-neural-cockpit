# Plan forward — pre-launch integration & deploy

> **Status:** living document. Updated as gates flip.
> **Audience:** Alien (operator), Cursor (functional), brother (infra),
> Claude (design + integration glue).
> **Cross-refs:** `docs/PRODUCT_PHASE_M.md` (the P-tasks), `docs/AGENT_HANDOFF.md`
> (current split of work), `docs/contracts/` (frozen wires).

This is the punch-list from "Phase M frontend ahead-of-Cursor"
(today) → "Phase M production launch". Five gates. Each gate
swaps one frontend stub for live backend, never invents a wire.

---

## Gate 1 — entitlements live (P5 backend lands)

**Cursor delivery (unblock signal):** `backend/core/entitlements/`
mod with `Tier` enum + `LIMITS` + `can_run()` + 3 endpoints, tests
green.

**Claude wires (under 30 min once endpoints live):**

1. `lib/api.ts` — add `getEntitlements()`, `getUsage(since?)`,
   `postUpgrade({tier, payment_token})` typed clients.
2. `BudgetWarning.tsx` — drop the standalone `useBudgetState()` hook,
   read from `getEntitlements()` directly. Endpoint shape pinned in
   `PRODUCT_PHASE_M.md` § 6.4.
3. `Pricing.tsx` — fetch real cap numbers from `LIMITS` so on-page
   tier bullets stay in sync with backend without hardcoding.
4. Mount `<BudgetWarning />` in cockpit header strip.
5. `Onboarding.tsx` step 1 ("sign in") — after auth callback, hit
   `getEntitlements()` to confirm tier; if `tier=free` and operator
   came in via a `?ref=lifetime` link, flash an upgrade banner.

**Acceptance:** new free user → 100 cloud-call simulation → 402 on
101st call → cockpit shows red `BudgetWarning` with upgrade CTA.
Smoke: paid Pro user → cap hit → toggle `Pro · BYO` → cap relaxed,
yellow strip dismisses.

**Telemetry to add** (backend): `entitlements.upgraded`, 
`entitlements.cap_hit`, `entitlements.byo_toggled` events into the
meeet store.

---

## Gate 2 — Entrepreneur rename (P6 backend)

**Cursor delivery:** `packs/mlm/` → `packs/entrepreneur/` rename,
`registry.py` alias `mlm → entrepreneur` until 2026-07-29, action
function renames (`recruit_score` → `lead_score` etc), startup
migration of `~/.tars/state.sqlite`.

**Claude wires (already done frontend, gate is purely sync):**

- Frontend already uses `slug=entrepreneur` in `Domains.tsx`,
  `DomainsCards.tsx`, `Compare.tsx`, `Pricing.tsx`, `Steps.tsx`,
  `Install.tsx`, `Onboarding.tsx` (role `marketer` maps to
  `entrepreneur`).
- Verify after Cursor merge: `GET /api/domains` returns slug
  `entrepreneur`, alias `mlm` resolves, migration receipt fires.

**Acceptance:** existing user with `pack=mlm` upgrades → cockpit
shows `pack=Entrepreneur`, action history preserved, audit log has
`pack.migrated` receipt.

---

## Gate 3 — roles backend (P7)

**Cursor delivery:** `backend/core/roles/` mod with `Role` dataclass
+ defaults + custom synthesis hook (Claude/GPT prompt → overlay) +
6 endpoints, hook into orchestrator (prepend overlay before pack
prompt).

**Claude wires (1-2 hours):**

1. `lib/roles.ts` — typed client + `useRoles()`, `useActiveRole()`,
   `createCustomRole({name, description, samples?})`,
   `setActiveRole(slug)`.
2. `Onboarding.tsx` step 1 — replace static `ROLES` const with
   `useRoles()` hook. Custom role submit hits `POST /api/roles`
   which synthesises overlay server-side; localStorage seed becomes
   non-authoritative.
3. New `RolesPanel.tsx` for cockpit Settings — list all roles, edit
   custom overlay, switch active, delete custom.
4. Cockpit header — current role chip with click-to-switch dropdown
   (uses `<GlobalCommandPalette />` style).
5. `Pricing.tsx` — Pro+ "AI Clone trains on you" bullet links to
   `/cockpit/settings/roles`.

**Acceptance:** new user picks "Custom" → fills name+description →
backend synthesises overlay → first chat turn uses the overlay
(visible in `context.retrieved` SSE event header). Switch role
mid-thread → next turn uses new overlay.

---

## Gate 4 — vision routing (P8)

**Cursor delivery:** image extractor in
`attachments/extractors.py`, multimodal voice routing in
`chat/orchestrator.py`, `supports_multimodal: bool` flag on voice
registry, OCR fallback via `pytesseract`, tests green.

**Claude wires (45 min):**

1. `ChatPane.tsx` — already has `<ImageThumb />`. Verify it works
   end-to-end with a real attached image.
2. `MessageBubble` — when assistant response references an image
   chunk via `[chunk_N]`, render thumbnail inline (data already in
   citation row).
3. New action chip in `business`/`science` packs (Cursor adds
   `analyze_image` action): expose in cockpit action picker with
   image-drop affordance.
4. Marketing copy — Pricing tier bullets get "Image vision included"
   on multimodal-capable voices.

**Acceptance:** drop a screenshot of a Figma mockup into `/cockpit`
chat → assistant returns design critique referencing visible
elements (`Login button is below the fold...`), receipt logs voice
+ image bytes hashed.

---

## Gate 5 — meeet.world subdomain (brother delivery)

**Brother delivery (per `docs/contracts/TARS_SUBDOMAIN.md`):** DNS
for `tars.meeet.world`, SSL, reverse proxy / vhost, downloads
manifest pass-through, `meeet_session` cookie sharing, end-to-end
logging contract emitting `tars.<page|api|click>.<action>` events
into meeet.

**Claude wires (15 min):**

1. `index.html` — flip `<link rel="canonical">` from
   `https://meeet.world/` to `https://tars.meeet.world/` once DNS
   live. Update `og:url`. Twitter card stays the same.
2. `MeeetWorldStrip.tsx` — when daemon online AND `meeet_session`
   cookie present, hit `meeet-app/api/wallet/balance` for $MEEET
   pill (Cursor backend already wires that endpoint). When absent,
   show "Sign in" CTA.
3. `lib/session.ts` — read `tars_session_id` cookie on first load;
   if missing, expect edge to set on next request. Already idempotent.

**Acceptance:** `curl https://tars.meeet.world/api/product/downloads`
returns contract 1.0.0 manifest within 200ms p99. Page-view event
arrives in meeet event store with operator_id linked when logged in.

---

## Gate 6 — desktop binary released (L9 v1)

**Cursor delivery (separate from Phase M):** notarised macOS .dmg
arm64 + x64, Authenticode-signed Windows .exe, sha256 checksums,
GitHub release published, `releases.json` updated.

**Claude wires (5 min):**

1. `lib/downloads.ts` — auto-picks the right artifact via the live
   manifest. Already done.
2. Verify on /pitch slide 1 the install pill shows real version.
3. Update `Pricing.tsx` Lifetime tier "founders edition" copy if
   needed.

**Acceptance:** visitor on macOS arm64 lands on `/` → primary
button "Download for macOS" → click → installer downloads from
GitHub Releases → install runs → cockpit boots.

---

## Public launch sequence

Once gates 1-6 are green:

### T-72h
- Stage `tars-staging.meeet.world` for 7 days first-pass already
  done (per `TARS_SUBDOMAIN.md` § 9). Confirm staging is healthy.
- Smoke: install + cockpit + pairing + role pick + first brief on
  three machines (M1 mac, Intel mac, Linux).
- Run full `pytest` suite + `tsc` + `vite build` clean.
- Render `/pitch` to PDF for investor email batch.

### T-24h
- Pre-flight checklist (below).
- Email founders' list (Lifetime tier 1k buyers) with launch slot.
- Schedule social post drafts (X / Discord / GitHub announce).

### T-0 (launch)
- Flip DNS `tars.meeet.world` to production.
- Push release tag `v9.0.0` on GitHub → triggers
  `release.yml` workflow → publishes binaries + Homebrew tap PR.
- Activate signing on Solana memo anchor (currently optional).
- Open Discord channel `#launch-day`, monitor for issues.

### T+2h
- First metrics check:
  - install conversion (page-view → /install.sh fetch)
  - cockpit boot rate (downloaded → daemon healthy within 60s)
  - upgrade clicks on Pricing (free → Pro)
  - any 5xx spikes in `meeet.world/api/tars/*`

### T+24h
- Retrospective in `docs/AGENT_HANDOFF.md`.
- Patch tag `v9.0.1` for any field-discovered issues.

---

## Pre-flight checklist (run T-24h)

```bash
# 1. Frontend builds clean
cd experiments/neural-showcase-v3
npm install
npm run typecheck
npm run build
# expect: dist/ ~1.4MB gzipped, three-vendor/r3f-vendor/react-vendor splits

# 2. All routes resolve
for path in / install onboarding cockpit pitch press docs status \
            privacy terms security roadmap changelog; do
  echo "GET $path → $(curl -sI http://127.0.0.1:5174$path | head -1)"
done
# expect: HTTP/1.1 200 for every route

# 3. Backend tests
cd jarvis
pytest -x -q
# expect: 270+ green (Cursor's count post-Phase L8)

# 4. Manifest live
curl -s http://127.0.0.1:8765/api/product/downloads | jq .contract_version
# expect: "1.0.0"

# 5. Pairing endpoint live
curl -s http://127.0.0.1:8765/api/pairing/identity | jq .ok
# expect: true

# 6. PWA manifest valid
curl -s http://127.0.0.1:5174/manifest.webmanifest | jq .name
# expect: "TARS — Neural Cockpit"

# 7. Sitemap parseable
curl -s http://127.0.0.1:5174/sitemap.xml | xmllint --noout -
# expect: no error

# 8. /pitch slide count
# expect: 12 slides, keyboard nav works

# 9. install.sh syntax
bash -n jarvis/scripts/install.sh
# expect: no error
```

If any line fails — block launch, fix, re-run.

---

## Polish backlog (post-launch, prioritised)

### High value
1. **Real product screenshots in /pitch** — replace text descriptions
   on slide 4 with actual cockpit captures (need v9.0 stable build).
2. **Animated typewriter on Hero subhead** — Linear-style copy reveal.
   Pure CSS keyframes, ~30 LOC.
3. **OG card per route** — currently single `og.svg`. Per-route
   variants for `/pitch`, `/pricing`, `/install` would lift social
   share CTR.
4. **i18n EN → RU** — at least Landing + FAQ + Pricing. Operator
   audience here is largely Russian-speaking (per Discord). Use
   `react-intl` or simple route-prefix `/ru/*`.

### Medium value
5. **`<MagneticCursor />` polish on /cockpit** — currently global,
   feels heavy in dense cockpit panels.
6. **Pricing tier hover preview** — show one extra detail on hover
   (per-tier feature delta).
7. **Compare table sticky header** — 14-row matrix on mobile loses
   header context.
8. **Footer `built with TARS` badge generator** — task #69 was
   shipped backend-side; surface a `/build-with` page that outputs
   embed code.
9. **Hero animated grid floor option** — subtle moving grid on the
   bottom 30% of hero, toggleable via `prefers-reduced-motion`.

### Low value (do if time)
10. **404 deep-link to most-frequent recent route** — check
    referer + recent palette items.
11. **Cmd+K hint chip on /cockpit too** — currently hidden because
    Cursor owns ⌘K there; could surface a separate Cmd+J for
    landing-style nav.
12. **Sound design polish iter 2** — tweak ambient bed levels after
    real-user listening tests.

---

## Risk register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Cursor's `tiers.py` shape differs from my mock | Med | Med | Frontend reads typed shape; mismatch → tsc fails on build → catches before deploy |
| Custom role overlay synthesis takes too long (>5s) | Med | High (UX) | Onboarding step 1 has loading spinner; if synthesis fails, fallback to templated overlay (Cursor side) |
| Vision multimodal request payload size > 25MB | Low | Med | Existing attachment cap blocks at 25MB → 413 already wired |
| meeet.world subdomain SSL takes >24h | Low | High (launch slip) | Stage on `tars-staging.meeet.world` first per § 9 |
| GitHub Releases CDN slow for first 1k buyers | Med | Low | Brother's S3 fallback `meeet.world/dl/*` exists |
| Solana memo anchor fails on launch day | Low | Low | Anchor is optional; receipt chain works without it |
| Chrome Manifest V3 / WebAudio policy changes | Low | Low | Sound layer already opt-in (mute by default) |
| AI Clone training data leaks to wrong operator | Low | Critical | Per-user `~/.tars/roles/<role_id>.json`, never crosses operator boundary; covered by `tests/test_roles_isolation.py` (Cursor adds) |

---

## Cross-agent handoff at T-0

When everything's green and we ship:

1. Append CHANGELOG entry: `2026-MM-DD — TARS v9.0.0 launch`.
2. Bump `package.json` version to `9.0.0`.
3. Tag GitHub release.
4. Post in Discord `#announcements` (Alien drafts).
5. Email Lifetime founders (Cursor or brother handles outreach
   list).
6. Tweet thread (Alien voice).
7. Open `docs/POSTMORTEM_LAUNCH.md` for any field issues.

---

## Stopping signal

The launch is **done** when:
- 3+ days post-T-0 with no P0 issues.
- `tars.meeet.world` 99.9% uptime maintained.
- 100+ active operators (`session.opened` events) on the marketing
  funnel within 72h.
- Discord `#feedback` has < 5 unresolved threads.

After that, plan next phase (`docs/PHASE_N_*.md` — likely L4 voice
mode + L10 mobile).

---

*Pin this file: `docs/PLAN_FORWARD.md`. Updated by whichever agent
flips a gate; the other should review within 24h.*
