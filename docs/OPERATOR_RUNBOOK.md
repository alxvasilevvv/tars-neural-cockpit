# TARS — Operator Runbook (release signing & publishing)

> Updated **2026-04-29** for **0.1.0-alpha.2** (Phase M backbone).
>
> This is the runbook for the **one** human-side handoff in the
> launch chain: minting the desktop release-signing keypair and
> attaching it to GitHub Actions secrets. Everything else
> (cockpit build, sidecar, manifest, updater channel, signing
> sidecars) is automated by `release-desktop.yml`.
>
> **Why this can't be automated.** The minisign private key
> never leaves the operator's terminal. The passphrase is typed
> twice into a TTY prompt that doesn't go through any agent
> process. Losing this key forces every existing installation
> through a hard reinstall (the auto-updater refuses mismatched
> signatures), so the operator owns its lifecycle end-to-end.

---

## 0. Pre-flight (already done by the agent)

- `tauri.conf.json` version bumped to **0.1.0-alpha.2**.
- Bundle targets list now covers macOS / Windows / Linux
  (`dmg`, `app`, `msi`, `nsis`, `deb`, `appimage`).
- `desktop/scripts/generate-release-keys.sh` ships the
  `--patch-tauri-conf` flag (auto-rewrites `plugins.updater.pubkey`).
- `desktop/scripts/sign-artifacts.sh` consumes
  `TAURI_SIGNING_PRIVATE_KEY` / `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`
  and emits `<artifact>.sig` sidecars.
- `release-desktop.yml` picks up both env vars from GitHub secrets,
  runs the `python -m backend.core.product.publish` CLI, and
  uploads to the GitHub release.
- Cockpit web bundle builds clean (`pnpm build`) — staged into
  `desktop/src-tauri/web/` (5.7 MB, 12 entries).
- Publish CLI dry-run is green: 7 platform/arch combos, 8 updater
  channel files emitted, sha256 + signature_url plumbing intact.
- 671 pytest + 56 vitest + 18 swift + tsc clean.

---

## 0a. Smoke-check updater pubkey placeholder (optional)

Runs no network calls and touches no secrets:

```bash
bash desktop/scripts/updater-pubkey-status.sh
```

- **Before** `generate-release-keys.sh --patch-tauri-conf` you should see
  `TODO_PUBLIC_KEY` in the message.
- **After** a successful `--patch-tauri-conf` run you should see
  `patched (minisign pubkey present)` — only then ship installers signed
  by the matching CI secret.

---

## 1. Mint the release-signing keypair (one-time, per repo)

> Skip this step if you already have a `~/.tars-release-keys/tars-desktop.key`
> from an earlier release. Reusing the same keypair across releases is
> required — the Tauri auto-updater refuses signature drift.

Run **on your local machine**, in an interactive terminal (NOT through
this agent):

```bash
cd ~/Documents/Claude/Projects/Jarvis/jarvis  # or your local repo path
bash desktop/scripts/generate-release-keys.sh --patch-tauri-conf
```

You will be prompted **twice for a passphrase**. Pick something
strong; you'll need it again for the GitHub secret. The script:

1. Mints a Minisign keypair via `tauri signer generate`.
2. Writes the **private** key to `~/.tars-release-keys/tars-desktop.key`
   (mode 600, in `~/.tars-release-keys/` mode 700).
3. Writes the **public** key to
   `~/.tars-release-keys/tars-desktop.key.pub`.
4. **Patches `desktop/src-tauri/tauri.conf.json`** —
   `plugins.updater.pubkey` is rewritten in place from
   `"TODO_PUBLIC_KEY"` to the real base64 public key.
5. Prints the two `gh secret set …` commands for step 2.

**Backup the private key now.** Copy it to a hardware token
(YubiKey/Trezor) or to an encrypted offline drive. Losing it forces
every existing installation to do a hard reinstall.

---

## 2. Install the GitHub Actions secrets

```bash
# 1) Make sure gh is authenticated for the meeet.world repo
gh auth status

# 2) Set the private key (the file is base64-encoded by Tauri)
gh secret set TAURI_SIGNING_PRIVATE_KEY \
  < ~/.tars-release-keys/tars-desktop.key

# 3) Set the passphrase you used in step 1
gh secret set TAURI_SIGNING_PRIVATE_KEY_PASSWORD
# (paste the passphrase when prompted)
```

Optional (if/when you have them — skip for the first alpha):

```bash
# Apple Developer ID for macOS notarisation
gh secret set APPLE_ID
gh secret set APPLE_TEAM_ID
gh secret set APPLE_APP_SPECIFIC_PASSWORD

# Windows Authenticode (PFX file + password)
gh secret set WINDOWS_CERTIFICATE          # base64 of .pfx
gh secret set WINDOWS_CERTIFICATE_PASSWORD
```

Verify the secrets exist:

```bash
gh secret list --repo <owner>/<repo>
# expected: TAURI_SIGNING_PRIVATE_KEY, TAURI_SIGNING_PRIVATE_KEY_PASSWORD
```

---

## 3. Commit the patched `tauri.conf.json`

The patcher only touched `plugins.updater.pubkey`. Confirm the diff
is exactly what you expect, then commit:

```bash
git diff desktop/src-tauri/tauri.conf.json

git add desktop/src-tauri/tauri.conf.json
git commit -m "release(desktop): pin minisign updater pubkey for 0.1.0-alpha.2"
```

The public key value is **safe to commit** — it's the half of the
keypair that anyone needs to verify our installers.

---

## 4. Tag and push

The release workflow triggers on `desktop-v*.*.*` tags:

```bash
git tag -a desktop-v0.1.0-alpha.2 -m "TARS 0.1.0-alpha.2 — Phase M backbone"
git push origin desktop-v0.1.0-alpha.2
```

Watch the run:

```bash
gh run watch --exit-status
```

The workflow will:

1. Build the cockpit web bundle.
2. Stage it via `package-cockpit.sh`.
3. Build the pyoxidizer sidecar per target triple.
4. Build the Tauri installers (4 matrix cells: macOS arm64,
   macOS x64, Windows x64, Linux x64).
5. Sign every installer with `tauri signer sign` →
   `<artifact>.sig` sidecar.
6. Run the publish CLI to mint `dist/releases.json` +
   `dist/updates/<target>/{0.1.0-alpha.2,latest}.json`.
7. Upload everything to the GitHub release.

If a job fails, re-run with `gh run rerun --failed` after fixing.

---

## 5. Mirror the manifest to meeet.world

Once the release is green:

```bash
# Pull the artifact bundle
gh run download $(gh run list --workflow release-desktop.yml --json databaseId --jq '.[0].databaseId') \
  --name dist-bundle -D /tmp/tars-dist

# Inspect
ls /tmp/tars-dist
#   releases.json
#   releases/0.1.0-alpha.2/...
#   updates/darwin-aarch64/{0.1.0-alpha.2,latest}.json
#   updates/darwin-x86_64/{0.1.0-alpha.2,latest}.json
#   updates/linux-x86_64/{0.1.0-alpha.2,latest}.json
#   updates/windows-x86_64/{0.1.0-alpha.2,latest}.json

# Upload to meeet.world's downloads bucket (replace with your CDN command)
rsync -av /tmp/tars-dist/releases/   meeet.world:/var/www/downloads/tars/
rsync -av /tmp/tars-dist/updates/    meeet.world:/var/www/updates/
rsync -av /tmp/tars-dist/releases.json meeet.world:/var/www/api/product/

# Sanity-check both URLs the desktop installer pings on launch
curl -sSL https://meeet.world/api/product/downloads | jq '.releases[0].version'
# → "0.1.0-alpha.2"

curl -sSL https://meeet.world/updates/darwin-aarch64/latest.json | jq .version
# → "0.1.0-alpha.2"
```

---

## 6. Post-release checklist

- [ ] GitHub release page shows 7 artifacts + their `.sig` sidecars
      + `releases.json`.
- [ ] `https://meeet.world/api/product/downloads/latest` returns
      version `0.1.0-alpha.2`.
- [ ] `https://meeet.world/updates/darwin-aarch64/latest.json`
      returns version `0.1.0-alpha.2` and a non-empty `signature`.
- [ ] Test-install the macOS arm64 DMG on a clean machine; the app
      boots, the cockpit loads, and `tail -f ~/.tars/sidecar.log`
      shows the FastAPI sidecar starting.
- [ ] Verify a sample artifact with the public key:
      ```bash
      minisign -V \
        -p ~/.tars-release-keys/tars-desktop.key.pub \
        -m TARS-0.1.0-alpha.2-arm64.dmg
      ```
- [ ] Tweet / Telegram / Discord announcement (Claude lane — handoff
      copy lives at `docs/RELEASE_NOTES_0.1.0-alpha.2.md`).

---

## Recovery scenarios

### "I lost the private key"

You need a new keypair AND a hard cut-over for every installation:

1. Mint a new pair (step 1).
2. Bump to a new minor version (e.g. `0.2.0-alpha.1`) so the
   updater sees a fresh stream.
3. Operators on the old key must download the new build manually
   (the auto-updater will refuse the new signature against the old
   pubkey). Telegraph this in the release notes.

### "I want to rotate the key"

Same as "lost" — there's no in-place key rotation in Tauri 2's
updater. Treat rotation as a hard cut-over.

### "CI signed an artifact but `releases.json` shows `signature_url=null`"

The publish CLI looks for `<filename>.sig` in the same directory.
Confirm the upload step in `release-desktop.yml` actually staged
the `.sig` files — the `find` filter must include `*.sig`. (It
does as of this release; this is mostly a regression-watchpoint.)

---

## What the agent already did

The agent (Cursor/Claude in this session) completed every code-side
preparation for this release. The split below is for reference:

| Step                                        | Done by | Status |
|---------------------------------------------|---------|--------|
| `tauri.conf.json` version bump              | agent   | ✅      |
| Linux bundle targets added                  | agent   | ✅      |
| `--patch-tauri-conf` helper flag            | agent   | ✅      |
| Cockpit web bundle build                    | agent   | ✅      |
| `package-cockpit.sh` staging                | agent   | ✅      |
| Publish CLI dry-run                         | agent   | ✅      |
| `RELEASE_NOTES_0.1.0-alpha.2.md`            | agent   | ✅      |
| `OPERATOR_RUNBOOK.md`                       | agent   | ✅      |
| Mint Minisign keypair                       | **operator** | 🔒 |
| `gh secret set` for Tauri secrets           | **operator** | 🔒 |
| Commit `tauri.conf.json` pubkey patch       | **operator** | 🔒 |
| Tag + push `desktop-v0.1.0-alpha.2`         | **operator** | 🔒 |
| Apple / Windows / Play credentials          | **operator** | 🔒 |
| Mirror manifest to meeet.world CDN          | **operator** | 🔒 |

🔒 = security-boundary item; the agent must not run it.
