# Phase 4 (L9 close, v10.2 optional) — Linux `.deb` + AppImage signing

**Status:** PLANNING-SURFACE — deferred-by-design brief
**Target release:** v10.2 (optional; not a v10.0.0 or v10.1 blocker)
**Lane:** L9 — release signing trio (sibling to PR #199 Apple, PR #200 Windows, PR #201 updater)
**Effort estimate:** ~6-8 h impl + ~3 h operator (key generation + GPG agent setup) — small because Linux trust model is permissive
**Authored:** 2026-05-18 (W310-ab continuation, autonomous orchestrator)
**Depends on:** none (CI already builds unsigned `.deb` + `.AppImage`); benefits from #201 (updater bootstrap) being landed first so the `latest.json` channel can announce Linux artifacts uniformly

---

## 1. Motivation (and why v10.2, not v10.0 or v10.1)

The Tauri pipeline at `.github/workflows/release-desktop-tagged.yml`
**already produces** `.deb` and `.AppImage` artifacts on every tag push.
What it **does not produce** is signed artifacts:

| Artifact | Built today | Signed today | v10.0.0 GA need |
|---|---|---|---|
| `.deb` | ✅ via tauri-action | ❌ unsigned | not GA-blocker |
| `.AppImage` | ✅ via tauri-action | ❌ unsigned | not GA-blocker |
| `latest.json` (updater) | ✅ via #201 | ✅ via minisign | none — same updater works for Linux |

**Why not a GA blocker.** Three reasons:

1. **Install share.** The W113 download telemetry showed Linux desktop
   installs at **< 3 %** of total Mac+Win+Linux installs. The v10.0.0
   GA decision (operator D3 in `PRODUCT_MASTER_PLAN.md`) is `go_now`
   on Mac+Win, with Linux as graceful-fallback.

2. **Trust-model tolerance.** Unlike macOS Gatekeeper (hard-block) and
   Windows SmartScreen (scary warning), Linux package managers
   tolerate unsigned binaries by design:
   - `.deb`: `dpkg -i tars.deb` works without a signature; `apt`
     itself warns but does not block when adding a local file
   - `.AppImage`: chmod + run; no signature checked unless the user
     opts into `appimaged` + `gpg --verify`
   - Most Linux desktop users are technically literate enough to
     skip the warning when present

3. **Per-distro overhead.** Real `.deb` signing requires a Debian
   repository (`apt-get` integration), which means setting up
   `https://apt.tars.meeet.world/` with metadata + `.gpg` key
   distribution. This is ~2 weeks of operator work for an audience
   that's < 3 % of the install base — wrong priority ordering for
   v10.0.0.

**Why v10.2 (not v10.1).** v10.1 is dominated by:
- PH3 mobile pairing closeout (#211 brief, ~2.7 wk impl)
- PH3 keyring + pairing UX (#195 + #196 briefs)
- PH4 Windows sign (#200 brief, ~12 h impl) + updater UI (#201 brief)
- PH2 STT + voice gallery (#193 + #194 briefs)

Linux signing fits more naturally in v10.2 alongside the encrypted
vault (#202), policy UI (#203), and telemetry (#204) — the "real data"
release that also unlocks "real Linux trust". It can also slot into
v10.3 or v11 without cost.

---

## 2. Goals / non-goals

### Goals (when this brief is implemented in v10.2 or later)

1. **`.deb` GPG signing** with a Debian-style detached signature
   (`*.deb.gpg`) embedded in the GitHub Release.
2. **AppImage signature** via `signtool` (built-in `appimagetool`
   signing pass) writing the signature inside the AppImage payload.
3. **`apt` repo distribution** at `https://apt.tars.meeet.world/`
   (sub-deliverable; can be deferred to v10.3 if operator wants v10.2
   to ship only GitHub Release `.deb.gpg`).
4. **AppImage update channel** integrated with the Tauri updater
   (#201) so the in-app updater works the same way on Linux as on
   macOS/Windows.
5. **Verification script** `scripts/verify-linux-release.sh` that
   re-validates a downloaded `.deb` against the published `.gpg` key
   and an `.AppImage` against its embedded signature.

### Non-goals

- ❌ **RPM packages** (`.rpm` for Fedora/CentOS/RHEL/openSUSE) —
   roadmap is for v11+ if/when Linux install share crosses 10 %.
- ❌ **Snap / Flatpak** — same rationale.
- ❌ **Arch Linux AUR maintenance** — community-volunteer driven, not
   official channel.
- ❌ **Reproducible builds** — fun goal but orthogonal to signing.
- ❌ **NixOS module** — same; the operator's Tauri build already works
   on NixOS via the unstable channel.
- ❌ **Linux ARM** (`aarch64-unknown-linux-gnu`) — Tauri runner support
   is still spotty; revisit in v11 once GitHub Actions has stable ARM
   Linux runners.

---

## 3. Target architecture

### 3.1 `.deb` GPG signing

`.deb` files have a defined signing protocol via `debsigs` (the
official Debian tool) or just GPG detached signatures (the de-facto
standard for non-Debian-official packages):

```
TARS_10.2.0_amd64.deb                 (~50 MB, includes sidecar)
TARS_10.2.0_amd64.deb.gpg             (~500 bytes detached signature)
tars-pubkey.asc                       (operator's GPG pubkey, ASCII-armored)
```

CI signing step (after tauri-action produces the `.deb`):

```yaml
- name: Sign .deb with GPG
  if: runner.os == 'Linux'
  shell: bash
  env:
    HAS_LINUX_GPG_KEY: ${{ secrets.LINUX_GPG_PRIVATE_KEY != '' }}
  run: |
    set -e
    if [ "${HAS_LINUX_GPG_KEY}" != "true" ]; then
      echo "No LINUX_GPG_PRIVATE_KEY secret — skipping .deb signing"
      exit 0
    fi
    echo "${{ secrets.LINUX_GPG_PRIVATE_KEY }}" | base64 -d | gpg --batch --import
    DEB_PATH=$(ls desktop/src-tauri/target/${{ matrix.target }}/release/bundle/deb/*.deb | head -1)
    gpg --batch --yes --output "${DEB_PATH}.gpg" --detach-sign "${DEB_PATH}"
    echo "✓ signed: ${DEB_PATH}.gpg"
```

Verification on user side:

```bash
curl -fL -O https://tars.meeet.world/dl/TARS_10.2.0_amd64.deb
curl -fL -O https://tars.meeet.world/dl/TARS_10.2.0_amd64.deb.gpg
curl -fsSL https://tars.meeet.world/keys/tars-pubkey.asc | gpg --import
gpg --verify TARS_10.2.0_amd64.deb.gpg TARS_10.2.0_amd64.deb
# Expected: gpg: Good signature from "TARS Releases <releases@meeet.world>"
sudo dpkg -i TARS_10.2.0_amd64.deb
```

### 3.2 AppImage signature

AppImage has built-in signing via `appimagetool --sign --sign-key`.
The signature is embedded in the AppImage payload and verified by
`appimagetool --validate` (or by `appimaged` if the user runs it):

```yaml
- name: Sign AppImage
  if: runner.os == 'Linux'
  shell: bash
  env:
    HAS_LINUX_GPG_KEY: ${{ secrets.LINUX_GPG_PRIVATE_KEY != '' }}
    GPG_KEY_ID: ${{ secrets.LINUX_GPG_KEY_ID }}
  run: |
    set -e
    if [ "${HAS_LINUX_GPG_KEY}" != "true" ]; then
      echo "No LINUX_GPG_PRIVATE_KEY secret — skipping AppImage signing"
      exit 0
    fi
    APPIMAGE_PATH=$(ls desktop/src-tauri/target/${{ matrix.target }}/release/bundle/appimage/*.AppImage | head -1)
    # appimagetool re-bundles + signs in one pass
    appimagetool --sign --sign-key "${GPG_KEY_ID}" "${APPIMAGE_PATH%.AppImage}.AppDir"
    echo "✓ signed AppImage: ${APPIMAGE_PATH}"
```

Verification on user side:

```bash
chmod +x TARS-10.2.0-x86_64.AppImage
./TARS-10.2.0-x86_64.AppImage --appimage-signature
# Expected: signature key fingerprint matches https://tars.meeet.world/keys/
./TARS-10.2.0-x86_64.AppImage
```

### 3.3 `apt` repository (sub-deliverable, optional in v10.2)

For users who want `apt install tars` ergonomics:

```bash
# One-time setup by user:
echo "deb [signed-by=/usr/share/keyrings/tars.gpg] https://apt.tars.meeet.world stable main" \
  | sudo tee /etc/apt/sources.list.d/tars.list
curl -fsSL https://tars.meeet.world/keys/tars-pubkey.asc \
  | sudo gpg --dearmor -o /usr/share/keyrings/tars.gpg

# Then forever:
sudo apt update
sudo apt install tars
sudo apt upgrade tars   # auto-pulls new versions
```

Implementation: post-CI step uploads the signed `.deb` to an S3 bucket
behind `apt.tars.meeet.world`, then runs `apt-ftparchive` to regenerate
`Packages.gz` + `Release` + `Release.gpg` metadata. The bucket fronts
`https://apt.tars.meeet.world/{dists/stable/main/binary-amd64/Packages,…}`.

**~6 h additional impl on top of the basic signing**; skipping it in
v10.2 still lets users download `.deb` + `.gpg` from the GitHub
Release page directly.

### 3.4 Updater channel uniformity

After #201 (updater bootstrap) lands, `latest.json` on the GitHub
Release looks like:

```json
{
  "version": "v10.0.0",
  "notes": "…",
  "pub_date": "2026-…",
  "platforms": {
    "darwin-aarch64": { "signature": "…", "url": "…/TARS_10.0.0_aarch64.dmg" },
    "darwin-x86_64": { "signature": "…", "url": "…/TARS_10.0.0_x64.dmg" },
    "linux-x86_64":  { "signature": "…", "url": "…/TARS_10.0.0_amd64.AppImage" },
    "windows-x86_64": { "signature": "…", "url": "…/TARS_10.0.0_x64-setup.exe" }
  }
}
```

The `linux-x86_64` entry already points at the AppImage in #201
(uniform with mac/win); this brief adds a GPG signature for the
AppImage itself, which is **independent** of the Tauri updater
minisign signature (the `signature` field above remains the minisign
one for updater verification; GPG is for human-trust verification).

---

## 4. Implementation steps (mechanical, parallel-safe)

| # | PR | Scope | LoC | Effort |
|---|---|---|---|---|
| **1** | `chore(release): generate Linux GPG key + push to GitHub Secrets` | one-time operator setup, runbook in this brief §5 | ~0 (operator) | ~1 h operator |
| **2** | `ci(release): sign .deb + AppImage with GPG when secrets present` | extend `.github/workflows/release-desktop-tagged.yml` with two new conditional steps (graceful degrade) | ~50 | 1 h |
| **3** | `feat(verify): scripts/verify-linux-release.sh + docs` | new helper script + `docs/LINUX_SIGNING_SETUP.md` operator runbook | ~120 | 2 h |
| **4** | `chore(deploy): publish .deb to apt.tars.meeet.world via S3 bucket + apt-ftparchive` (OPTIONAL) | new GH Action upload step + brother-side bucket setup | ~80 | 4-6 h cross-stack |
| **5** | `docs: PH4 Linux brief executed; spec → reality reconciliation` | move brief to `docs/SHIPPED/` | ~30 | 0.5 h |
| **Total** | 5 PRs (4 if apt repo deferred) | | **~280 LoC** (200 LoC without apt) | **~6-8 h impl + ~3 h operator** |

Step 4 (apt repo) is the largest line-item and can be deferred to v10.3
or even v11 without affecting the rest of the v10.2 Linux signing story.

---

## 5. Operator runbook (one-time GPG key generation)

The Linux signing key is a single GPG keypair you generate once and
reuse for every release. Lifetime is your call; recommend 5 years.

```bash
# 1. Generate a fresh GPG key (5-year expiry, ed25519 + cv25519)
gpg --batch --gen-key <<EOF
%no-protection
Key-Type: eddsa
Key-Curve: ed25519
Key-Usage: sign
Subkey-Type: ecdh
Subkey-Curve: cv25519
Subkey-Usage: encrypt
Name-Real: TARS Releases
Name-Email: releases@meeet.world
Expire-Date: 5y
EOF

# 2. Note the key ID
KEY_ID=$(gpg --list-secret-keys --with-colons releases@meeet.world | awk -F: '/^sec/{print $5; exit}')
echo "Key ID: $KEY_ID"

# 3. Export private key as base64 (for GH Secret)
gpg --export-secret-keys --armor "$KEY_ID" | base64 | pbcopy
echo "✓ private key base64 in clipboard — paste as LINUX_GPG_PRIVATE_KEY"

# 4. Note the short fingerprint for GH Secret
echo "Key ID for LINUX_GPG_KEY_ID secret: $KEY_ID"

# 5. Export public key for user distribution
gpg --export --armor "$KEY_ID" > tars-pubkey.asc
echo "✓ tars-pubkey.asc generated — upload to tars.meeet.world/keys/"
```

GitHub Secrets to set (Settings → Secrets → Actions):

| Secret | Value |
|---|---|
| `LINUX_GPG_PRIVATE_KEY` | base64-encoded ASCII-armored private key from step 3 |
| `LINUX_GPG_KEY_ID` | short fingerprint from step 4 |

Cloudflare R2 / Pages upload of `tars-pubkey.asc`:

```bash
# Either commit to the marketing-site repo and let Cloudflare Pages deploy it,
# or upload to R2 + add a Cloudflare Worker route at /keys/tars-pubkey.asc
# The first option is simpler; recommend it.
cp tars-pubkey.asc ~/meeet.world-site/public/keys/tars-pubkey.asc
cd ~/meeet.world-site
git add public/keys/tars-pubkey.asc
git commit -m "chore(keys): publish TARS release signing pubkey"
git push origin main
```

After Cloudflare Pages rebuilds (~90 s), the key is at
`https://tars.meeet.world/keys/tars-pubkey.asc` for users to import.

---

## 6. Verification script

`scripts/verify-linux-release.sh` (Step 3 deliverable, ~120 LoC):

```bash
#!/usr/bin/env bash
# Verify a downloaded TARS Linux release against published signatures.
# Usage: scripts/verify-linux-release.sh TARS_10.2.0_amd64.deb
set -euo pipefail

FILE="${1:-}"
if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  echo "usage: $0 <path-to-deb-or-AppImage>" >&2
  exit 2
fi

# 1. Ensure GPG key is imported
if ! gpg --list-keys releases@meeet.world >/dev/null 2>&1; then
  echo "→ Importing TARS release signing key…"
  curl -fsSL https://tars.meeet.world/keys/tars-pubkey.asc | gpg --import
fi

case "$FILE" in
  *.deb)
    # Detached signature lives next to the .deb
    SIG="${FILE}.gpg"
    if [ ! -f "$SIG" ]; then
      # Try to pull from the same GH Release
      curl -fL -O "${SIG}" 2>/dev/null || {
        echo "✗ No signature found at $SIG and none could be downloaded" >&2
        exit 3
      }
    fi
    gpg --verify "$SIG" "$FILE" 2>&1 | grep -E "Good signature|BAD signature"
    ;;
  *.AppImage)
    # AppImage has embedded signature
    "$FILE" --appimage-signature 2>&1 | grep -E "signature.*valid|fingerprint"
    ;;
  *)
    echo "✗ Don't know how to verify: $FILE (expect .deb or .AppImage)" >&2
    exit 4
    ;;
esac
```

---

## 7. Test plan

This brief is **pure documentation**. When implemented:

### Unit / CI tests

- Step 2 graceful-degrade test: tag a `v10.2.0-signtest.N` with all
  Linux secrets absent → CI logs "skipping .deb signing" and "skipping
  AppImage signing", `.deb` + `.AppImage` still produced unsigned.
- Step 2 happy-path test: same tag with secrets set → CI logs
  "✓ signed: TARS_…_amd64.deb.gpg" and AppImage validates.

### Integration test (operator wall-clock: ~10 min)

1. Cut `v10.2.0-signtest.1` with secrets present
2. Wait for CI to upload artifacts to the dry-run Release page
3. Download `.deb` + `.deb.gpg` + `.AppImage` to a fresh Ubuntu 22.04
   VM (the Multipass `ubuntu` image works)
4. Run `scripts/verify-linux-release.sh TARS_…_amd64.deb` — expect
   "Good signature from TARS Releases"
5. Run `TARS_…_x86_64.AppImage --appimage-signature` — expect
   "fingerprint matches"
6. `sudo dpkg -i TARS_…_amd64.deb` — expect installs without errors
7. `tars --version` returns `v10.2.0-signtest.1`
8. Delete dry-run tag + release

### Acceptance for v10.2 GA item (Linux signing)

- `gh release view v10.2.0 --json assets` lists `.deb`, `.deb.gpg`,
  and `.AppImage` for `linux-x86_64`
- Marketing-site `https://tars.meeet.world/keys/tars-pubkey.asc`
  is served with `Content-Type: application/pgp-keys`
- A clean Ubuntu install can `dpkg -i` the `.deb` and launch TARS
  without errors

---

## 8. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **GPG key expires mid-release-cycle** | medium | medium | 5-year expiry + calendar reminder at 4y; can rotate keys with a new pubkey upload + signature on rotation announcement |
| **`appimagetool` upstream removes `--sign`** | low | medium | Pin `appimagetool` version in CI workflow; vendoring is acceptable since the binary is ~5 MB |
| **User imports wrong pubkey from MITM** | low | high | Pubkey URL is HTTPS-only via Cloudflare; future: publish fingerprint in DNS TXT + on multiple channels (release notes, README, marketing site) |
| **`apt` repo metadata corruption** | low | high | If apt repo ships in Step 4, add `apt-ftparchive` validation step + automated rollback to previous Release file |
| **GitHub Actions runner doesn't have `gpg` 2.4+** | low | low | Ubuntu 22.04 runners include `gpg 2.2.27` which is sufficient; if upgraded to `gpg 2.4+` for ed25519 KDF features, pin `runs-on: ubuntu-22.04` |
| **Brother-side resistance to apt repo S3 bucket** | medium | low | Repo can be hosted on GitHub Pages instead (`alxvasilevvv.github.io/tars-apt-repo/`); no brother dependency required |

---

## 9. Open questions for the operator

1. **v10.2 or v10.3?** — does v10.2 actually need Linux signing, or
   is v10.3 acceptable? Recommend v10.2 for round-trip closure of the
   Phase 4 trio (Apple #199, Windows #200, Linux this brief).
2. **apt repo or GitHub-Release-only?** — Step 4 (apt repo) adds ~6 h
   and brother coordination. Recommend skipping in v10.2 (ship just
   `.deb` + `.deb.gpg` on GitHub Releases); revisit in v10.3 if Linux
   install share crosses 5 %.
3. **Key lifetime** — 5 years (my recommendation) vs 2 years vs no
   expiry? 5y is the sweet spot between rotation pain and security
   hygiene.
4. **Releases@meeet.world email** — does this need to be a real
   inbox? GPG keys don't actually verify the email exists; recommend
   using a real forwarding address pointed at operator's main email
   so users with key-signing concerns can reach you.
5. **Reproducible builds opt-in?** — out of scope per §2, but if
   you want the option for v11+, this brief's signing infrastructure
   would still apply unchanged.

---

## 10. Cross-references

- **PR #199** — Apple `.dmg` v10 sign dock-down (the GA-critical sibling)
- **PR #200** — Windows `.exe`/`.msi` Authenticode sign (v10.1 sibling)
- **PR #201** — Updater channel bootstrap (provides the `latest.json`
  pattern this brief inherits for Linux)
- **`.github/workflows/release-desktop-tagged.yml`** — host workflow
  that gets extended in Step 2
- **`docs/V10_GA_CHECKLIST.md` B4** — currently marked deferred; this
  brief is the formal deferral spec
- **`docs/PRODUCT_MASTER_PLAN.md` §3.4 Phase 4** — master plan slot

---

## 11. Sign-off checklist

When all of these are true, `ph4-linux` is clear:

- [ ] Step 1 operator runbook executed (GPG key generated, secrets set)
- [ ] Step 2 CI changes merged (graceful-degrade tested with absent
      secrets, happy-path tested with secrets present)
- [ ] Step 3 verification script + docs merged
- [ ] (optional v10.2) Step 4 apt repo serving signed `.deb`s from
      `https://apt.tars.meeet.world/dists/stable/main/binary-amd64/`
- [ ] §7 acceptance criteria verified against a real v10.2.0 release
- [ ] Brief moved to `docs/SHIPPED/PH4_LINUX.md` with per-step "✅
      shipped via #PR" annotations

---

*Brief authored by the autonomous orchestrator on 2026-05-18 during the
v10.0.0 GA dock-down (W310-ab continuation). Pure planning surface for
v10.2 Linux release signing. Explicitly deferred from v10.0.0/v10.1
because (a) Linux install share < 3 %, (b) Linux trust model tolerates
unsigned binaries, (c) per-distro overhead (apt repo) competes badly
with higher-leverage v10.1 work. Brief reservedly closes the Phase 4
trio.*
