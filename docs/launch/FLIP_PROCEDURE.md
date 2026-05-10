# FLIP_PROCEDURE — `INSTALLERS_READY` go-live flip

> Wave 77. Pre-staged patch lives at
> [`docs/launch/wave_X_flip_installers.patch`](./wave_X_flip_installers.patch).
> This is the **single, last code change** between "Coming soon" UI
> and a fully-armed download surface on `tars.meeet.world`.

---

## TL;DR

```bash
cd /path/to/jarvis
git apply docs/launch/wave_X_flip_installers.patch
git -c user.email="alienram@icloud.com" -c user.name="Alien" \
    commit -am "chore(launch): flip INSTALLERS_READY=true (v9.1.0 live)"
git push origin main
```

That's it. Cloudflare Pages auto-builds from `main`; download buttons
go live within ~2 min of the push.

---

## 1. When to apply the patch

Only after **all four** are true:

1. `v9.1.0` git tag exists on `main` (`git tag --list | grep v9.1.0`).
2. GitHub Actions release workflow on that tag is **green**.
3. The release at `https://github.com/<org>/jarvis/releases/tag/v9.1.0`
   contains the signed artefacts:
   - `TARS_9.1.0_aarch64.dmg`
   - `TARS_9.1.0_aarch64.dmg.sig` (minisign)
   - `latest.json` updater manifest
4. `curl -sSI https://tars.meeet.world/dl/TARS_9.1.0_aarch64.dmg`
   returns **HTTP 200/302** (not 404). The `/dl` Cloudflare Function
   proxies to GitHub Releases — if it 404s, the release isn't visible yet.

If any of those is false → **do not apply**. The current "Coming soon"
state is the safe default.

---

## 2. How to apply

```bash
cd /path/to/jarvis
git checkout main
git pull --ff-only

git apply docs/launch/wave_X_flip_installers.patch

# sanity check — should show two changed lines, false→true and soon→live
git diff experiments/neural-showcase-v3/src/lib/launchFlags.ts

git -c user.email="alienram@icloud.com" -c user.name="Alien" \
    commit -am "chore(launch): flip INSTALLERS_READY=true (v9.1.0 live)

Wave 77 pre-staged flip. Signed v9.1.0 .dmg is live in GitHub
Releases and the /dl proxy returns 200, so the marketing site can
surface the download buttons."

git push origin main
```

Cloudflare Pages picks up the push automatically — first build finishes
in ~90 s, edge cache warms in another ~30 s.

---

## 3. How to verify production picked it up

After ~3 min:

1. Visit `https://tars.meeet.world` in a private/incognito window.
2. The hero `Download for Mac` button should be **enabled** (no
   "Coming soon" pill, no greyed-out style).
3. Clicking it should redirect to a `.dmg` URL (200, not 404).
4. The `/install` page should show the one-curl install snippet
   without the "available soon" banner.
5. Check the deploy:
   ```bash
   curl -s https://tars.meeet.world/_next/static/chunks/ \
     | grep -q "INSTALLERS_READY=true" || \
     echo "site may still be serving stale cache — wait 60s"
   ```
   (or simply hard-reload the landing page; the inline JS bundle
   contains the flag.)

If verification fails, see Rollback below.

---

## 4. Rollback

If the .dmg is broken, the proxy is 500-ing, or anything else burns:

**Option A — git revert (preferred, audit-friendly):**

```bash
cd /path/to/jarvis
git checkout main && git pull --ff-only
git revert HEAD --no-edit
git push origin main
```

Cloudflare Pages re-builds with `INSTALLERS_READY = false`; the
"Coming soon" surface is back within ~2 min.

**Option B — manual flip (if revert is dirty):**

Edit `experiments/neural-showcase-v3/src/lib/launchFlags.ts`,
set `INSTALLERS_READY = false as const;` and
`INSTALLER_ETA = "soon" as const;`, then commit and push.

**Option C — emergency only — Cloudflare Pages "Rollback to previous
deployment"** in the Pages dashboard. Use this if even `git push` is
blocked. Subsequent fixes should still go through git.

---

## 5. Post-flip checklist (within 1 hour)

- [ ] Twitter / X thread published from `docs/launch/ANNOUNCEMENTS.md`
- [ ] Hacker News post submitted
- [ ] Reddit posts (r/macapps, r/MacOS, r/SideProject)
- [ ] Email blast to waitlist (subject: "TARS is live")
- [ ] Product Hunt scheduled / launched
- [ ] Discord / community announcement
- [ ] `docs/CHANGELOG_PUBLIC.md` — add v9.1.0 launch entry with date

---

## 6. After verification — clean up

The patch file `docs/launch/wave_X_flip_installers.patch` can stay
in-tree as historical record (rename to `wave_77_flip_installers_APPLIED_<date>.patch`
if you like a paper trail), or delete it in a follow-up commit. Either is fine.
