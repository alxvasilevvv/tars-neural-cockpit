# W276 — `tars.meeet.world` landing refresh

**Date:** 2026-05-15
**Status:** code shipped, deploy pending
**Trigger:** Alien reported "tars.meeet.world не работает" the night before the v10 presentation.

## What was actually wrong

The subdomain was up the whole time — HTTPS valid, Cloudflare healthy, Pages
function returning 200. The bug was **content drift**: the landing was last
rebuilt at v9.1.0 (4 May 2026), but the desktop app is on **v10.0.0-rc.1**
(14 May 2026). So:

- Headline read `TARS — v9.1.0`.
- Meta refresh redirected to `releases/tag/v9.1.0`.
- `/api/product/version` returned `{"version":"9.1.0"}`.
- `/api/product/downloads` listed only 9.1.0 + 8.4.0 artifacts.

Anyone landing on the subdomain to see what we're shipping tomorrow would
see the *previous* generation, not the cockpit Alien is presenting.

## What changed (W276)

Four files in `experiments/neural-showcase-v3/`:

| File | Change |
|------|--------|
| `public/index.html` | Hero rewrite — version chip, gradient H1, 4 differentiator cards (local-first / voice-first / receipts-on-chain / $MEEET), GitHub release CTA, install-via-shell snippet. Auto-redirect dropped (we now want visitors to *see* the landing). |
| `functions/api/product/version.ts` | `LATEST_VERSION 9.1.0 → 10.0.0-rc.1`, `released_at 2026-05-04 → 2026-05-15`. |
| `functions/api/product/downloads.ts` | Prepended a v10.0.0-rc.1 entry with the 5 expected Tauri artifacts (`TARS_10.0.0-rc.1_aarch64.dmg`, `_x64.dmg`, `_x64-setup.exe`, `_amd64.AppImage`, `_amd64.deb`). Kept 9.1.0 + 8.4.0 entries so older pinned installers continue resolving via the `/dl/[file]` proxy. |
| `public/install.sh` | Doc-comment version reference bumped. |

Nothing in the contract changed (`contract_version` stays `1.0.0`,
`source` stays `tars.meeet.world/pages-functions`).

## Important caveat — artifact URLs

The download URLs in `downloads.ts` point at
`https://tars.meeet.world/dl/TARS_10.0.0-rc.1_*` which proxies through
`functions/dl/[file].ts` to a GitHub release. **That release must exist
on `alxvasilevvv/tars-neural-cockpit` tagged `v10.0.0-rc.1` with those
exact filenames** for the download buttons to resolve.

If the tag isn't cut yet, the landing still renders correctly, but the
"Download v10.0.0-rc.1 →" button will 404 (via the proxy). Two options:

1. **Recommended:** run `scripts/RELEASE-v10.0.command` to cut the tag,
   trigger `.github/workflows/release-desktop-tagged.yml`, and attach
   the bundles produced by `REBUILD-TARS-APP.command`.
2. **Demo-only fallback:** point the button at the GitHub releases
   *page* (`/releases`) instead of the specific tag in `index.html`
   until the tag is cut.

## Deploy procedure

```sh
# From repo root:
bash scripts/DEPLOY-TARS-LANDING.command
```

What it does:

1. Stages the four files above plus this doc.
2. Commits with a `W276:` prefix message.
3. Pushes `origin/main`.
4. Dispatches `tars-meeet-cloudflare-pages.yml` (manual `gh workflow
   run`) so we don't wait for path-filter auto-trigger.
5. Sleeps 90 seconds for CF Pages build + edge propagation.
6. Curls `https://tars.meeet.world/api/product/version` and the root
   HTML to confirm `10.0.0-rc.1` is being served end-to-end.

If verification fails after 90s, purge Cloudflare cache:
`https://dash.cloudflare.com → Caching → Purge Everything`.

## Brother handoff (meeet.world infra side)

Nothing for the brother to ship on `api.meeet.world` for this change —
this is purely the `tars.meeet.world` Pages project, which Alien owns
through `alxvasilevvv/tars-neural-cockpit` + Cloudflare account.

The 8 endpoints from `docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md` (auth +
billing on `api.meeet.world`) remain the brother's outstanding work.

## Verification checklist

- [ ] `curl https://tars.meeet.world/api/product/version` returns
      `"version":"10.0.0-rc.1"`.
- [ ] `curl https://tars.meeet.world/api/product/downloads` lists 3
      releases with 10.0.0-rc.1 first.
- [ ] Browser load of `https://tars.meeet.world/` shows hero with
      "Release candidate · v10.0.0-rc.1" badge.
- [ ] `curl -I https://tars.meeet.world/dl/TARS_10.0.0-rc.1_aarch64.dmg`
      returns 302 → GitHub release asset (only after tag is cut).
- [ ] OG/Twitter preview rendered on Twitter/Slack/iMessage shows the
      new title and description (Twitter card validator:
      `https://cards-dev.twitter.com/validator`).

## Why this matters for tomorrow

The presentation demos a voice-first local-first cockpit with seven
domain packs and signed receipts. If a prospective customer / investor
opens `tars.meeet.world` during or after the talk and sees `v9.1.0` and
a stripped redirect page, the credibility gap is bigger than the product
gap. The landing has to reflect the product on stage.
