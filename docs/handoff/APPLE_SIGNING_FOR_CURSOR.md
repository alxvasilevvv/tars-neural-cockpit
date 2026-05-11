# TARS v9.1.0 — Apple signing handoff for Cursor

> Paste-ready prompt for the Cursor session running on Andrey Syrchin's Mac
> (the one with the working Chrome MCP bridge — same setup that successfully
> drove the Cloudflare dashboard during the B-019 incident a few days back).
>
> Expected duration: ~15 minutes wall-clock if no surprises.
> Ownership: Cursor drives, Andrey clicks Allow / enters 2FA / approves
> keychain prompts when asked.

---

## Context for Cursor

- Repo: https://github.com/alxvasilevvv/tars-neural-cockpit
- Apple Developer account: **CSA PROJECT - FZCO**, Team ID `ZGR2C33ZLZ`
  (Andrey Syrchin, the human running this Cursor session, owns this account)
- Goal: ship a signed Mac `.dmg` for the **v9.1.0** release. Currently
  `INSTALLERS_READY=false` on prod (`tars.meeet.world`) showing
  "Coming Soon" — flip to `true` after the `.dmg` is signed and uploaded
  to GitHub Releases.
- Why this is being delegated to your Cursor: the originating Claude Code
  session can drive native macOS apps but its browser tier is hard-locked
  to read-only (cannot click in Chrome / Safari / Arc). Apple Developer
  portal + GitHub Settings are both browser-only flows, so this needs your
  Chrome MCP bridge (the one that handled B-019 cleanly).
- All paths below assume Andrey's local checkout lives at
  `~/Documents/Claude/Projects/Jarvis/jarvis`. Adjust if his Cursor
  workspace is rooted elsewhere.

---

## Steps for Cursor to execute end-to-end

### Step 1 — Generate CSR via Keychain Access

Open Keychain Access app on this Mac:

- Spotlight (`Cmd+Space`) -> "Связка ключей" or "Keychain Access" -> Enter
- Menu: Связка ключей -> Ассистент сертификации -> Запросить сертификат у ЦС
  (English: Keychain Access -> Certificate Assistant -> Request a Certificate
  from a Certificate Authority)
- Form:
  - User Email: `alienram@icloud.com` (or actual Apple Developer login email)
  - Common Name: `CSA PROJECT - FZCO`
  - CA Email: leave blank
  - Request: select "Saved to disk"
- Continue -> save to `~/Desktop/CertificateSigningRequest.certSigningRequest`

### Step 2 — Apple Developer portal cert creation

Open Chrome at:

```
https://developer.apple.com/account/resources/certificates/add
```

(if you need to log in as Andrey, prompt the human)

- Pick radio "Developer ID Application" (NOT "Apple Distribution")
- Continue
- Profile Type: G2 Sub-CA (default)
- Continue
- Choose File -> upload `~/Desktop/CertificateSigningRequest.certSigningRequest`
- Continue
- Download — save the `.cer` file (defaults to `~/Downloads`)

### Step 3 — Install cert into keychain

Double-click the downloaded `.cer` (it should be in `~/Downloads`).
This imports automatically into the login keychain. Verify:

- Open Keychain Access -> login keychain -> My Certificates
- Should now see `Developer ID Application: CSA PROJECT - FZCO (ZGR2C33ZLZ)`

### Step 4 — Export to .p12 + base64 (one-liner)

Run in Terminal:

```bash
IDENTITY=$(security find-identity -v -p codesigning 2>/dev/null \
  | grep "Developer ID Application" | head -1 | sed 's/.*"\(.*\)"/\1/')
TEAM_ID=$(echo "$IDENTITY" | sed -n 's/.*(\([A-Z0-9]\{10\}\)).*/\1/p')
P12_PASS=$(openssl rand -base64 24 | tr -d '+/=' | head -c 24)
P12_PATH=~/.tars-release-keys/apple-cert.p12
mkdir -p $(dirname $P12_PATH) && chmod 700 $(dirname $P12_PATH)
rm -f $P12_PATH
security export -k login.keychain -t identities -f pkcs12 \
  -o "$P12_PATH" -P "$P12_PASS" 2>&1 | tail -3
B64=$(base64 < "$P12_PATH")
echo "$B64" | pbcopy
echo "OK APPLE_CERTIFICATE base64 in clipboard ($(echo -n "$B64" | wc -c) chars)"
echo "APPLE_CERTIFICATE_PASSWORD = $P12_PASS"
echo "APPLE_SIGNING_IDENTITY = $IDENTITY"
echo "APPLE_TEAM_ID = $TEAM_ID"
```

macOS will prompt for the keychain password (Andrey's Mac login password) ->
click **Always Allow**. SAVE the stdout to a temp note — you'll paste 4 of
these into GitHub Secrets in Step 6.

### Step 5 — Get app-specific password for Apple notarization

Open Chrome at:

```
https://account.apple.com/account/manage
```

(Andrey's Apple ID login)

Section: Sign-In and Security -> App-Specific Passwords -> "+"

- Name: `tars-ci-notarize`
- Generate
- COPY the 4-group password (`xxxx-xxxx-xxxx-xxxx`)

### Step 6 — Add 6 GitHub Secrets

Open Chrome at:

```
https://github.com/alxvasilevvv/tars-neural-cockpit/settings/secrets/actions
```

Click "New repository secret" 6 times. Use values:

| Name | Value source |
|---|---|
| `APPLE_CERTIFICATE` | Paste from clipboard (Step 4 output, ~3000+ char base64) |
| `APPLE_CERTIFICATE_PASSWORD` | From Step 4 stdout |
| `APPLE_SIGNING_IDENTITY` | From Step 4 stdout (full string with quotes) |
| `APPLE_TEAM_ID` | `ZGR2C33ZLZ` (from Step 4 or fixed value) |
| `APPLE_ID` | Andrey's Apple Developer email |
| `APPLE_PASSWORD` | From Step 5 (4-group, no spaces) |

After all 6 are added, the secrets list should show 6 entries (values are
hidden — that's expected).

### Step 7 — Tag v9.1.0 to trigger CI build

Run in Terminal:

```bash
cd ~/Documents/Claude/Projects/Jarvis/jarvis
git pull origin main
git tag v9.1.0
git push origin v9.1.0
```

Now monitor CI: open
https://github.com/alxvasilevvv/tars-neural-cockpit/actions

Find the `release-desktop · tagged` workflow run. Should take ~10-15 min.

If green: signed `.dmg` uploaded to
https://github.com/alxvasilevvv/tars-neural-cockpit/releases/tag/v9.1.0

If red: read the job log, identify which step failed:

- `Import Apple cert` -> re-check `APPLE_CERTIFICATE` base64 + password
- `Notarize` -> re-check `APPLE_ID` + `APPLE_PASSWORD` + Team ID
- `Build Tauri` -> likely Rust compile issue, need human review

### Step 8 — Smoke-test the signed .dmg

Download the `.dmg` from the GitHub Release. On Andrey's Mac:

- Open `.dmg` -> drag TARS to Applications
- Launch from Applications
- Should NOT show "untrusted developer" warning (that's the whole point of
  signing)
- App opens cleanly -> Step 8 done

### Step 9 — Flip INSTALLERS_READY=true

Once the `.dmg` is verified working:

```bash
cd ~/Documents/Claude/Projects/Jarvis/jarvis
# Edit experiments/neural-showcase-v3/src/lib/launchFlags.ts
# Find line:  export const INSTALLERS_READY = false as const;
# Change to:  export const INSTALLERS_READY = true as const;
git add experiments/neural-showcase-v3/src/lib/launchFlags.ts
git commit -m "chore(launch): flip INSTALLERS_READY=true — signed .dmg shipped"
git push origin main
```

CF Pages rebuilds in ~90s. `tars.meeet.world` Hero will switch from
"Coming Soon" to a real "Download for macOS" button.

### Step 10 — Final verification (5 min)

Open a private Chrome window. Visit `tars.meeet.world`:

- Hero shows `Download for macOS · DMG · v9.1.0` instead of "Coming Soon"
- Click -> downloads `TARS_9.1.0_aarch64.dmg`
- Open `.dmg` -> install -> launch -> no Gatekeeper warning
- DONE

---

## Reporting back

After each completed step (or at any failure), report progress briefly to
Andrey via the Cursor chat. Don't accumulate silently — surface failures
immediately.

If you encounter:

- "Allow" dialog -> click Allow (it's the keychain access prompt)
- 2FA prompt on Apple ID -> ask Andrey to enter the 6-digit code from his
  phone
- Anything you don't understand -> STOP, screenshot, ask
