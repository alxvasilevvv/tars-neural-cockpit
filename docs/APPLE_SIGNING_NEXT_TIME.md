# Apple Signing — 15-minute completion path (v9.1.0 → v9.1.1)

**Status:** Web cockpit + waitlist live now at [tars.meeet.world](https://tars.meeet.world).
Mac signed `.dmg` ships in 1–2 days, the moment you complete the steps below.

This guide is the operator runbook (`alien`) for the one missing piece between
"soft launch" and "real download button on the marketing site": a Developer ID
Application certificate exported from your Mac into GitHub Secrets.

---

## Why this is needed

Without a signed `.dmg`, macOS Gatekeeper rejects every TARS download with
**"TARS.app cannot be opened because the developer cannot be verified"** —
the user sees a scary modal and bounces. Worse, no fix is one-click; even
Right-click → Open requires admin password and three confirmations.

Currently `experiments/neural-showcase-v3/src/lib/launchFlags.ts` ships with
`INSTALLERS_READY = false`, so the download surfaces show a **"Coming Soon ·
Notify me"** waitlist instead of a broken download. That's honest, but it's
still a launch with one CTA disabled. Flipping the flag back to `true` after
this guide gets the real "Download for macOS" button live.

---

## What you need

- **15 minutes** (one sitting, ~no waiting on Apple)
- **Apple Developer account** — `CSA PROJECT - FZCO`, Team ID `ZGR2C33ZLZ`
  (already provisioned and paid; nothing to set up portal-side)
- **Mac with Keychain Access app** (any Mac you've used to log into the Apple
  Developer portal)

---

## Step-by-step

### 1. Generate CSR via Keychain Access

Apple needs a Certificate Signing Request (CSR) generated on your Mac so the
private key never leaves the machine.

- `⌘+Space` → type **"Связка ключей"** (or **"Keychain Access"**) → ↵
- Top menu: **Связка ключей → Ассистент сертификации → Запросить сертификат у
  ЦС…** (in English: **Keychain Access → Certificate Assistant → Request a
  Certificate From a Certificate Authority…**)
- Fill in:
  - **User Email Address:** `alienram@icloud.com` (or whatever the Apple
    Developer account uses)
  - **Common Name:** `CSA PROJECT - FZCO`
  - **CA Email Address:** *leave blank*
  - **Request is:** ✓ **Saved to disk** (NOT "Email to CA")
- Click **Continue**
- Save to **Desktop** as `CertificateSigningRequest.certSigningRequest`

### 2. Apple Developer portal — request the cert

- Open <https://developer.apple.com/account/resources/certificates/add>
  (sign in if prompted)
- Pick **Developer ID Application** under the **Software** section.
  *Do NOT pick Apple Distribution / Mac Distribution / Mac Installer
  Distribution — those are for the App Store.*
- Click **Continue**
- **Profile Type:** select **G2 Sub-CA** → **Continue**
- **Choose File** → pick the CSR you saved on Desktop in step 1
- Click **Continue**
- Click **Download** → saves `developerID_application.cer` to your Downloads
  folder

### 3. Install cert in keychain

- Double-click the downloaded `.cer` file in Finder
- Keychain Access opens automatically and imports the cert into your **login**
  keychain
- Verify it's there: Keychain Access → **login** → **My Certificates** → you
  should see a cert named:

  ```
  Developer ID Application: CSA PROJECT - FZCO (ZGR2C33ZLZ)
  ```

  with a private key nested under it.

### 4. Run the export bash one-liner

Open Terminal.app and paste this single block:

```bash
IDENTITY=$(security find-identity -v -p codesigning 2>/dev/null | grep "Developer ID Application" | head -1 | sed 's/.*"\(.*\)"/\1/'); TEAM_ID=$(echo "$IDENTITY" | sed -n 's/.*(\([A-Z0-9]\{10\}\)).*/\1/p'); P12_PASS=$(openssl rand -base64 24 | tr -d '+/=' | head -c 24); P12_PATH=~/.tars-release-keys/apple-cert.p12; mkdir -p $(dirname $P12_PATH) && chmod 700 $(dirname $P12_PATH); rm -f $P12_PATH; security export -k login.keychain -t identities -f pkcs12 -o "$P12_PATH" -P "$P12_PASS" 2>&1 | tail -3; B64=$(base64 < "$P12_PATH"); echo "$B64" | pbcopy; echo "✅ APPLE_CERTIFICATE base64 in clipboard"; echo "APPLE_CERTIFICATE_PASSWORD = $P12_PASS"; echo "APPLE_SIGNING_IDENTITY = $IDENTITY"; echo "APPLE_TEAM_ID = $TEAM_ID"
```

When macOS prompts for the keychain password — enter your **Mac login
password** → click **Always Allow** (so re-runs don't re-prompt).

The script prints:

- `APPLE_CERTIFICATE_PASSWORD` (random 24-char string — copy somewhere safe
  for the next step)
- `APPLE_SIGNING_IDENTITY` (the full identity string, e.g. `Developer ID
  Application: CSA PROJECT - FZCO (ZGR2C33ZLZ)`)
- `APPLE_TEAM_ID` (`ZGR2C33ZLZ`)

…and puts the base64-encoded `.p12` cert into your **clipboard**, ready to
paste into GitHub.

### 5. Get app-specific password for notarization

The cert above signs the binary. Notarization (Apple's malware scan) needs an
**app-specific password** for your Apple ID.

- Open <https://account.apple.com/account/manage> → sign in
- Click **Sign-In and Security** → **App-Specific Passwords** → click the **+**
- Name: `tars-ci-notarize`
- Click **Generate** → copy the 4-group password (e.g. `abcd-efgh-ijkl-mnop`)
- Save it somewhere safe — Apple won't show it again

### 6. Add 6 GitHub Secrets

- Open <https://github.com/alxvasilevvv/tars-neural-cockpit/settings/secrets/actions>
- Click **New repository secret** **6 times** in total, one per row:

  | Secret name                  | Value                                                    |
  | ---------------------------- | -------------------------------------------------------- |
  | `APPLE_CERTIFICATE`          | (paste from clipboard — base64 .p12 from step 4)         |
  | `APPLE_CERTIFICATE_PASSWORD` | (the random string from step 4 output)                   |
  | `APPLE_SIGNING_IDENTITY`     | `Developer ID Application: CSA PROJECT - FZCO (ZGR2C33ZLZ)` (from step 4) |
  | `APPLE_TEAM_ID`              | `ZGR2C33ZLZ`                                             |
  | `APPLE_ID`                   | (your Apple Developer email — usually `alienram@icloud.com`) |
  | `APPLE_PASSWORD`             | (the app-specific password from step 5, with the dashes) |

  Note: the Tauri updater key (`TAURI_SIGNING_PRIVATE_KEY` +
  `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`) was already populated by the Wave 79
  release-pipeline hardening pass; you don't need to re-add those.

### 7. Tag v9.1.0 to trigger CI build

```bash
cd ~/Documents/Claude/Projects/Jarvis/jarvis
git tag v9.1.0
git push origin v9.1.0
```

GitHub Actions [`release-desktop-tagged.yml`](../.github/workflows/release-desktop-tagged.yml)
fires on the tag push and:

1. Builds `.dmg` with Tauri (macos-14 runner, aarch64 + x64 matrix)
2. Signs each `.dmg` with the Apple Developer ID cert (uses the 6 secrets you
   just added)
3. Notarizes via Apple's notary service (`notarytool submit --wait`)
4. Staples the notarization ticket into the `.dmg`
5. Uploads to GitHub Releases as `TARS_9.1.0_aarch64.dmg` /
   `TARS_9.1.0_x64.dmg` plus `latest.json` for the Tauri updater

Watch progress: <https://github.com/alxvasilevvv/tars-neural-cockpit/actions>

Build typically takes ~25 minutes (most of it is the notarytool wait).

### 8. Flip `INSTALLERS_READY=true` after `.dmg` uploads

Once the GitHub Release page shows the signed `.dmg` files:

```bash
cd ~/Documents/Claude/Projects/Jarvis/jarvis
# Edit experiments/neural-showcase-v3/src/lib/launchFlags.ts
# Change:  export const INSTALLERS_READY = false → true
git add experiments/neural-showcase-v3/src/lib/launchFlags.ts
git commit -m "chore(launch): flip INSTALLERS_READY=true — signed .dmg shipped"
git push origin main
```

Cloudflare Pages auto-rebuilds the marketing site on `main` push (~90
seconds). After the rebuild, [tars.meeet.world](https://tars.meeet.world)
shows the real **"Download for macOS · DMG · v9.1.0"** button instead of
"Coming Soon · Notify me".

---

## Verification after launch

Open a **private** Chrome window (so you don't pick up cached HTML / cached
JS bundles) → navigate to <https://tars.meeet.world>.

Expected UX:

- Hero shows **"Download for macOS · DMG · v9.1.0"** primary button
  (purple gradient, OS-glyph in front, version pill on the right).
- Click → browser downloads `TARS_9.1.0_aarch64.dmg` (~80 MB) from the
  `/dl/<file>` proxy → GitHub Releases.
- Open the `.dmg` in Finder → drag **TARS** into **Applications**.
- Launch TARS from Applications → **should NOT** show the
  "Apple cannot verify…" Gatekeeper warning. The first launch may show a
  much milder "TARS is an app downloaded from the internet — Open?" dialog,
  which is normal for any signed-but-not-yet-reputation-built app and goes
  away after the first run.

If you DO see the "untrusted developer" hard-block, something in the
signing chain failed silently. Likely culprits:

- `APPLE_CERTIFICATE` base64 was truncated when pasting → re-export, re-paste.
- `APPLE_CERTIFICATE_PASSWORD` typo → re-paste from your password manager.
- `APPLE_PASSWORD` is the regular Apple ID password instead of the
  app-specific one → regenerate at step 5 and re-add.

---

## Cross-references

- Marketing flag controlling the Coming-Soon vs Download UI:
  [`experiments/neural-showcase-v3/src/lib/launchFlags.ts`](../experiments/neural-showcase-v3/src/lib/launchFlags.ts)
- Coming-Soon download strip:
  [`experiments/neural-showcase-v3/src/components/DownloadStrip.tsx`](../experiments/neural-showcase-v3/src/components/DownloadStrip.tsx)
  (function `ComingSoonStrip`)
- CI workflow that runs on tag push:
  [`.github/workflows/release-desktop-tagged.yml`](../.github/workflows/release-desktop-tagged.yml)
- Updater minisign key generator (already done in Wave 79):
  `desktop/scripts/generate-release-keys.sh`
- Release notes that announce v9.1.0 and reference this guide:
  [`docs/RELEASE_NOTES_v9.1.0.md`](RELEASE_NOTES_v9.1.0.md)
- Honest capability ledger: [`docs/WHAT_WORKS.md`](WHAT_WORKS.md)
- Forward roadmap (v9.1.1 lands signed `.dmg` + Quick Connect Chrome flow):
  [`docs/ROADMAP.md`](ROADMAP.md)

---

*Last updated: 2026-05-11 (Wave 113 — soft-launch polish).*
