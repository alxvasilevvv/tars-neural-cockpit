# Apple Developer Signing Setup — One-Time Operator Runbook

**Owner:** alien (operator)
**Time required:** ~15 minutes once you have an Apple Developer account
**Pre-requisite:** macOS with Keychain Access app, admin password handy

This document walks through everything required so that
`scripts/SIGN-AND-NOTARIZE.command` can run end-to-end and produce a TARS.app
that launches on any user's Mac with **zero Gatekeeper friction** — no
`xattr -cr`, no Right-click → Open, no scary "unidentified developer" modal.

Once you finish this guide, every subsequent build is one double-click:

```
scripts/REBUILD-TARS-APP.command   # → builds + auto-signs + notarizes
```

---

## Why this matters

Without a Developer ID cert + notarization ticket, macOS Gatekeeper rejects
every TARS download with:

> "TARS.app cannot be opened because the developer cannot be verified."

The user has to right-click → Open → enter their admin password → click Open
through three modals. Real-world conversion to "actually launches the app"
drops by ~80%. So we sign + notarize every release.

After the setup below:
- `.app` is signed with your **Developer ID Application** cert (a $99/yr
  Apple Developer membership grants this)
- `.app` is sent to Apple's notary service which scans it for malware and
  returns a **notarization ticket**
- The ticket is **stapled** onto the bundle so it launches offline without
  the OS calling Apple at startup
- Gatekeeper accepts the bundle and the user just double-clicks

---

## What you need

| Item | How to get it | Cost |
|---|---|---|
| Apple Developer account | https://developer.apple.com/programs/ | $99/yr |
| Mac with admin access | The Mac you'll build releases on | — |
| Apple ID with 2FA enabled | Same Apple ID as your Developer account | free |
| App-specific password | https://appleid.apple.com → Security | free |

> **Note:** You can use either an Individual or Organization developer
> account. Both grant the **Developer ID Application** cert needed here.
> Organization is required if you want the seller name shown as a company
> in the App Store, but that's irrelevant for direct-download distribution.

---

## Step 1 — Enroll in the Apple Developer Program

1. Go to https://developer.apple.com/programs/
2. Click **Enroll**, sign in with your Apple ID
3. Choose Individual or Organization
4. Pay the $99 fee — approval is usually instant (Individual) or 24-48h
   (Organization with D-U-N-S verification)
5. Note your **Team ID**: visible at https://developer.apple.com/account
   under Membership. It's a 10-character string like `ZGR2C33ZLZ`.

Save the Team ID — you'll paste it into `.env` later.

---

## Step 2 — Generate a Certificate Signing Request (CSR)

Apple needs a CSR so the cert's private key never leaves your Mac.

1. **Keychain Access** → menu **Keychain Access → Certificate Assistant →
   Request a Certificate From a Certificate Authority…**
2. Fill in:
   - **User Email Address:** the email on your Apple Developer account
   - **Common Name:** your name or company (e.g. "Alien Ram")
   - **CA Email Address:** leave blank
   - **Request is:** select **Saved to disk**
3. Click **Continue**, save the `.certSigningRequest` file to your Desktop.

---

## Step 3 — Create the Developer ID Application certificate

1. Go to https://developer.apple.com/account/resources/certificates/list
2. Click the **+** button → choose **Developer ID Application** (NOT
   "Developer ID Installer" — that's for pkg installers, not .app bundles)
3. Click **Continue**, upload the `.certSigningRequest` from Step 2
4. Click **Continue** again — Apple generates the cert in ~1 second
5. Click **Download** to get `developerID_application.cer`
6. Double-click the downloaded `.cer` — Keychain Access opens and installs
   it. The cert appears under **login** keychain → My Certificates with
   name like:
   ```
   Developer ID Application: Your Name (XXXXX)
   ```
   where `(XXXXX)` is your 10-char Team ID.

**Verify it's there:**

```bash
security find-identity -v -p codesigning
```

You should see a line like:
```
  1) ABCD1234... "Developer ID Application: Your Name (ZGR2C33ZLZ)"
```

The exact string in quotes is what goes into `APPLE_DEVELOPER_ID_APPLICATION`
in your `.env`.

---

## Step 4 — (Optional but recommended) Export cert + key as .p12

This lets you restore the cert on a different Mac or back it up offline.

1. Keychain Access → **login** keychain → **My Certificates**
2. Right-click the "Developer ID Application: …" entry → **Export**
3. Save as `developer_id_application.p12`, pick a strong password
4. Stash the `.p12` and password in 1Password / your secret store

You don't need this for the local pipeline — only for moving between Macs
or recovering after a disk wipe.

---

## Step 5 — Create an app-specific password

The notary service authenticates with an app-specific password, NOT your
regular Apple ID password (which would require interactive 2FA on every run).

1. Go to https://appleid.apple.com
2. Sign in → **Sign-In and Security** → **App-Specific Passwords**
3. Click **+** → label it `TARS notarization` (or anything memorable)
4. Apple gives you a password like `abcd-efgh-ijkl-mnop` — copy it RIGHT
   NOW, you cannot see it again. If you lose it, just regenerate.

---

## Step 6 — Store credentials in notarytool's keychain profile

This bundles your Apple ID + team ID + app-specific password into a single
named entry that `xcrun notarytool` can reference. The password is stored
encrypted in the macOS keychain — never written to disk in plaintext.

```bash
xcrun notarytool store-credentials "tars-notary" \
  --apple-id "your-apple-id@example.com" \
  --team-id "ZGR2C33ZLZ" \
  --password "abcd-efgh-ijkl-mnop"
```

Replace:
- `tars-notary` — profile name (anything you want; this goes into `.env`)
- `your-apple-id@example.com` — the Apple ID you enrolled with
- `ZGR2C33ZLZ` — your Team ID from Step 1
- `abcd-efgh-ijkl-mnop` — the app-specific password from Step 5

Verify:
```bash
xcrun notarytool history --keychain-profile "tars-notary"
```
It should print `No data found` (you haven't submitted anything yet) — but
the fact that it doesn't error means the profile works.

---

## Step 7 — Wire into `.env`

Edit `.env` at the repo root (copy from `.env.example` if needed) and add:

```
APPLE_TEAM_ID=ZGR2C33ZLZ
APPLE_DEVELOPER_ID_APPLICATION=Developer ID Application: Your Name (ZGR2C33ZLZ)
APPLE_NOTARY_PROFILE=tars-notary
```

**Exact-string warning:** `APPLE_DEVELOPER_ID_APPLICATION` must match the
quoted string `security find-identity` printed in Step 3 character-for-
character — including spaces, the colon, the parenthesised team ID. If
codesign reports `no identity found`, this is almost always the cause.

---

## Step 8 — Test the pipeline

1. Build the unsigned .app first:
   ```
   scripts/REBUILD-TARS-APP.command
   ```
2. Run the signing pipeline:
   ```
   scripts/SIGN-AND-NOTARIZE.command
   ```
   First-run timing:
   - Codesign: ~10s
   - Zip + upload: ~30s
   - Notary `--wait`: 1-5 min typical, can spike to 30+ min if Apple's
     queue is backed up (e.g. post-WWDC week)
   - Staple + spctl: instant

   Total: usually 2-7 minutes.

3. Confirm success — last line should be:
   ```
   spctl assessment: accepted
   ```

4. Sanity-test on a clean account:
   - Copy the resulting `.dmg` to a Mac that has NEVER had TARS installed
   - Mount it, drag to /Applications, double-click TARS.app
   - It should launch with zero scary modals (you may see a one-time
     Gatekeeper prompt "TARS is from the Internet, are you sure?" — that
     is normal first-launch behaviour for ANY downloaded app)

---

## Troubleshooting

### `errSecInternalComponent` during codesign

The cert is in the keychain but locked. Unlock it:
```bash
security unlock-keychain ~/Library/Keychains/login.keychain-db
```

### `no identity found` during codesign

Your `APPLE_DEVELOPER_ID_APPLICATION` string doesn't match what's in the
keychain. Run:
```bash
security find-identity -v -p codesigning
```
and copy the quoted string EXACTLY into `.env` (including spaces, colons,
parentheses, and the team ID).

### `The signature does not include a secure timestamp`

You forgot `--timestamp` on the codesign call. The `SIGN-AND-NOTARIZE.command`
script includes it; if you're running codesign manually, add `--timestamp`.

### Notarization returns `Invalid` — "The binary is not signed with a valid
Developer ID certificate"

A nested binary inside the .app (probably the Python sidecar at
`Contents/Resources/binaries/tars-sidecar`) was signed with a non-Developer-ID
cert, or wasn't signed at all. The `--deep` flag on codesign should catch
this, but if your sidecar bundles its own .dylibs in odd locations, you may
need to sign them individually first. Inspect the developer log that
`SIGN-AND-NOTARIZE.command` prints on failure — it lists the offending
path(s).

### Notarization hangs > 30 min

Apple's queue is backed up. The submission is queued; you can detach and
check later with:
```bash
xcrun notarytool history --keychain-profile tars-notary
```
Once `Accepted` appears, manually staple:
```bash
xcrun stapler staple /Applications/TARS.app
```

### `The application "TARS" can't be opened` even after notarization

Stapling failed silently. Re-run:
```bash
xcrun stapler staple -v /Applications/TARS.app
```
If it errors with "could not find ticket" — wait 2-3 min for Apple's CDN to
propagate the ticket, then retry.

### App-specific password rejected (`Authentication credentials are missing
or invalid`)

You either:
- typed the password wrong (no spaces, no quotes — it's literally
  `abcd-efgh-ijkl-mnop`), or
- regenerated it on appleid.apple.com after running `store-credentials`

Re-run `xcrun notarytool store-credentials` with the current password.

### `EXTENDED_BAD_ACCESS` (com.apple.security.cs.disable-library-validation)

The hardened runtime is blocking the sidecar from loading its dynamic
libraries. Open `desktop/src-tauri/entitlements.plist` and confirm
`com.apple.security.cs.disable-library-validation` is `<true/>`. If you
just edited it, rebuild + re-sign — entitlements only take effect at sign
time, not at runtime.

---

## What this guide does NOT cover

- **Windows code signing** (separate cert from DigiCert/Sectigo; tracked
  separately in W251+)
- **Sparkle / Tauri updater signing** — already done via the `pubkey` in
  `tauri.conf.json` (minisign, not Apple)
- **App Store distribution** — that's an entirely different flow using
  `altool` / Xcode and the App Store Connect API. Direct-download via .dmg
  is what TARS ships today; App Store is post-v10.0.

---

## Quick reference — for muscle memory

After setup, the day-to-day commands you actually run:

```bash
# Build + sign + notarize in one shot (if .env is configured):
scripts/REBUILD-TARS-APP.command

# Re-sign an already-built bundle without rebuilding Rust:
scripts/SIGN-AND-NOTARIZE.command

# Inspect what's signed:
codesign -dvv /Applications/TARS.app

# Inspect what notary thinks:
xcrun notarytool history --keychain-profile tars-notary

# Force Gatekeeper re-evaluation (should always say "accepted" now):
spctl --assess --type execute --verbose /Applications/TARS.app
```

---

**Last updated:** 2026-05-15 (W250)
**See also:**
- `docs/APPLE_SIGNING_NEXT_TIME.md` — older partial notes from W121 (kept
  for history; this doc supersedes it)
- `desktop/src-tauri/entitlements.plist` — the hardened-runtime
  entitlements applied at sign time
- `scripts/SIGN-AND-NOTARIZE.command` — the actual pipeline
