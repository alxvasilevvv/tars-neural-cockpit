# Phase 4 (L9 close) — Windows `.exe` / `.msi` Authenticode sign implementer brief

**Status:** PLANNING-SURFACE — full implementer brief (zero existing scaffold)
**Owner (planning):** assistant
**Owner (execution):** alien (operator: cert purchase + setup) + implementer agent (Tauri config + CI + scripts + docs)
**Target release:** v10.1 (NOT a v10.0.0 GA blocker)
**Estimated effort:** ~12 hours implementer + ~3 hours operator (cert purchase + portal verification)
**Depends on:**
- **Operator:** Authenticode code-signing cert (OV or EV) purchased from CA (DigiCert / Sectigo / SSL.com / Certum). Lead time 1–7 days OV, 3–14 days EV.
- **Code:** None — independent of Apple sign work.
**Risk surface:** SmartScreen reputation accrual (zero downloads = warning even with valid cert), HSM/USB-token logistics for EV path, CI-only signing without an HSM-attached runner.

---

## 1. Motivation

`tauri.conf.json` already declares `msi` and `nsis` bundle targets, and the
`release-desktop` workflow already builds them on `windows-latest` runners.
The artifacts ship to GitHub Releases as:

- `TARS_<version>_x64-setup.exe` (NSIS installer, preferred)
- `TARS_<version>_x64_en-US.msi` (WiX installer)

**Both ship unsigned today.** Consequences:

1. **SmartScreen blocking:** Edge / Chrome show "Microsoft Defender SmartScreen
   prevented an unrecognized app from starting" with two clicks (`More info`
   → `Run anyway`) to bypass. Conversion drops by ~60–80% real-world.
2. **Browser download warnings:** Chrome shows "this file is not commonly
   downloaded" red banner that requires `Keep` confirmation, plus a separate
   `Keep dangerous file` confirmation.
3. **AV false positives:** Unsigned PyInstaller-bundled Python sidecar
   (`tars-sidecar-x86_64-pc-windows-msvc.exe`) is a known AV trigger; signing
   the parent installer does NOT propagate to the sidecar (separate signing
   needed).
4. **No verifiable provenance** — anyone can rebuild + redistribute a
   trojaned TARS installer with identical UI.

Goal: ship a signed installer + signed sidecar that triggers no warnings
once SmartScreen reputation accrues (immediate with EV cert, 1–4 weeks with
OV cert).

---

## 2. Goals / non-goals

### Goals

- **G1.** `TARS_<version>_x64-setup.exe` and `TARS_<version>_x64_en-US.msi`
  ship Authenticode-signed by `release-desktop` workflow on every tag.
- **G2.** Bundled Python sidecar `tars-sidecar-x86_64-pc-windows-msvc.exe`
  is signed BEFORE Tauri bundles it (otherwise the installer's
  outer signature is valid but Defender flags the inner binary).
- **G3.** `signtool verify /pa /v <file>.exe` returns `Successfully verified`
  on the published artifact (clean Windows 11 machine).
- **G4.** Local dev path: `scripts/SIGN-WINDOWS.command` (operator
  double-clickable on macOS or `.ps1` invocation on Windows) signs a
  locally-built `.exe` end-to-end using `.env` credentials.
- **G5.** CI graceful degrade: when `WIN_CERT_PFX` secret is absent, the
  build still produces an unsigned installer (current behaviour preserved).
- **G6.** Documentation: `docs/WINDOWS_SIGNING_SETUP.md` covers cert
  purchase, PFX export, GitHub Secrets push, and verification — symmetric
  shape to `docs/APPLE_SIGNING_SETUP.md`.

### Non-goals (explicit)

- **N1.** EV cert HSM/USB-token CI signing (requires self-hosted
  Windows runner with attached HSM — out of scope for v10.1, defer to v10.2
  if cert reputation is insufficient).
- **N2.** Microsoft Store (`.msix` / `.msixbundle`) publishing — separate
  pipeline, ~$99/yr publisher fee, deferred to v11 mobile/store wave.
- **N3.** Windows Defender SmartScreen "trusted publisher" appeals (manual
  Microsoft submission process, not a code change).
- **N4.** ARM64 Windows runners (no current request volume; `x86_64-pc-windows-msvc`
  serves Surface Pro / WoA via x86 emulation).
- **N5.** Windows 10 support testing (we declare Windows 11+ baseline per
  Tauri default `webview2`; v10.0.0 dot-releases may expand back to 10).
- **N6.** Replacing PyInstaller for the sidecar (e.g. with Nuitka or
  PyOxidizer) to reduce AV false positives — separate Phase 4 sub-task,
  not gated by sign.

---

## 3. Cert decision matrix (operator owns; ~2 hours research + 1 day–2 weeks lead)

| Option | Cert type | Cost (yr 1) | Lead time | SmartScreen | HSM required | Recommendation |
|---|---|---|---|---|---|---|
| **A** | OV from Sectigo Comodo | ~$170 | 1–3 days | 1–4 wks reputation accrual | No (PFX) | ✅ DEFAULT for v10.1 |
| **B** | OV from SSL.com | ~$160 | 1–3 days | Same as A | No (PFX) | Equivalent to A |
| **C** | EV from DigiCert | ~$400 | 3–14 days | INSTANT trust | Yes (USB token) | If A reputation insufficient |
| **D** | EV from Sectigo | ~$300 | 5–14 days | INSTANT trust | Yes (USB token) | If A reputation insufficient |
| **E** | Self-signed | $0 | 5 min | NEVER trusted | No | ❌ rejected (worse than unsigned) |
| **F** | Re-use Apple .p12 | n/a | n/a | n/a | n/a | ❌ Apple cert cannot sign Windows |

### Recommended: Option A (OV cert)

**Rationale:**

- Lowest friction (PFX file, no USB token, CI-friendly).
- SmartScreen reputation accrues in 1–4 weeks based on download count + age
  + clean reports. At ~100 downloads/week (v10 launch trajectory), reputation
  should clear in 2–3 weeks.
- Upgrade path to EV is straightforward: same workflow, swap PFX for HSM-
  attached self-hosted runner if reputation accrual is too slow.
- $170/yr is operationally trivial vs. the 60–80% conversion drop on
  unsigned downloads.

### If operator picks EV (Option C/D)

This brief still applies, but §6 step "import PFX" is replaced with "attach
HSM to self-hosted runner + configure `signtool` to use the token", and §5
estimated effort doubles (~25h implementer due to self-hosted runner
plumbing).

---

## 4. Target architecture

### 4.1 Signing happens in two passes

**Pass 1 — sign the sidecar** (BEFORE Tauri bundles it):

```
.github/workflows/release-desktop-tagged.yml
└── Build Python sidecar (Windows)
    │   pyinstaller → dist/tars-sidecar-x86_64-pc-windows-msvc.exe
    └── NEW: Sign sidecar with Authenticode  ← inserted step
        │   signtool sign /f cert.pfx /p ${{ secrets.WIN_CERT_PASSWORD }} \
        │                 /tr http://timestamp.digicert.com /td sha256 \
        │                 /fd sha256 /v dist/tars-sidecar-*.exe
        └── Copy dist/tars-sidecar-*.exe → desktop/src-tauri/binaries/
```

**Pass 2 — sign the installer** (Tauri's built-in):

```
└── tauri-action build step
    │   reads tauri.conf.json: windows.certificateThumbprint
    │                          windows.timestampUrl
    │                          windows.digestAlgorithm
    └── Tauri internally calls signtool on the produced .exe + .msi
```

### 4.2 Cert lookup strategy

Tauri's `windows.certificateThumbprint` field expects the SHA-1 thumbprint
of a cert ALREADY in the Windows cert store. CI flow:

1. Decode `WIN_CERT_PFX` (base64) → `cert.pfx`
2. `Import-PfxCertificate -FilePath cert.pfx -Password <SecureString> -CertStoreLocation Cert:\CurrentUser\My`
3. Capture the thumbprint: `Get-ChildItem Cert:\CurrentUser\My | Select-Object -ExpandProperty Thumbprint`
4. Export thumbprint as env var → Tauri reads it via `${{ env.WIN_CERT_THUMBPRINT }}` placeholder OR (cleaner) we patch `tauri.conf.json` at build time.

**Decision needed (Q1 below):** patch `tauri.conf.json` at build time vs. use a
secondary `tauri.windows.conf.json` overlay (Tauri 2.x supports merge).

### 4.3 Local dev signing

`scripts/SIGN-WINDOWS.command` is a wrapper that:

- On macOS: SSHs into a Windows VM / WSL2 / a cloud Windows runner (TBD,
  see Q4 below).
- On Windows native: invokes the PowerShell sub-script directly.

For v10.1, scope to **CI-only signing**. Local dev unsigned `.exe` is OK
for testing — devs run via `pnpm tauri dev` which skips Tauri's sign step
entirely.

---

## 5. Implementation steps (6 mechanical, mergeable independently)

### Step 1 — Tauri config (Windows sign fields) — ~1.5h

**Change:** `desktop/src-tauri/tauri.conf.json` — extend `bundle.windows.nsis`
+ `bundle.windows.wix`:

```json
{
  "bundle": {
    "windows": {
      "wix": {
        "language": "en-US"
      },
      "nsis": {
        "installMode": "currentUser"
      },
      "certificateThumbprint": null,
      "digestAlgorithm": "sha256",
      "timestampUrl": "http://timestamp.digicert.com",
      "tsp": false
    }
  }
}
```

`certificateThumbprint: null` is the safe default — Tauri skips signing when
null, preserving current unsigned behaviour. CI injects the thumbprint at
build time (Step 4).

**Test:** `pnpm tauri build` locally on a clean machine — should produce
unsigned `.exe` + `.msi` exactly as today. **No regression.**

**Files touched:** `desktop/src-tauri/tauri.conf.json` (+5 lines).
**PR size:** ~10 LoC diff.

### Step 2 — Local sign script (PowerShell + .command wrapper) — ~2.5h

**New files:**

- `scripts/sign-windows.ps1` (~80 LoC) — actual signing logic
- `scripts/SIGN-WINDOWS.command` (~40 LoC) — macOS double-clickable that calls
  `pwsh` (PowerShell Core) or aborts cleanly if `pwsh` missing.

**Contract:**

```bash
$ scripts/SIGN-WINDOWS.command
=== SIGN-WINDOWS at 2026-XX-XXTXX:XX:XXZ ===
[1/6] load Windows signing credentials from .env
  ✓ WIN_CERT_PFX_PATH = ~/.tars-release-keys/win-cert.pfx
  ✓ WIN_CERT_PASSWORD = ********
[2/6] locate Windows artifacts (.exe + .msi)
  ✓ desktop/src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/TARS_*.exe
[3/6] verify cert + signtool available
[4/6] sign sidecar binary
[5/6] sign installer artifacts (.exe + .msi)
[6/6] verify signatures (signtool verify /pa /v)
  ✓ All signatures verified
```

**Test:** dry-run (no real cert) on a Windows VM → script exits cleanly at
Step 1 with "missing WIN_CERT_PFX_PATH in .env" message.

**Files touched:** `scripts/sign-windows.ps1` (new), `scripts/SIGN-WINDOWS.command` (new).
**PR size:** ~120 LoC.

### Step 3 — Sidecar sign CI step — ~2h

**Change:** `.github/workflows/release-desktop-tagged.yml` — insert NEW step
AFTER `Build Python sidecar (Windows)` and BEFORE `Copy dist/tars-sidecar-*.exe`:

```yaml
- name: Sign Python sidecar (Windows)
  if: matrix.target == 'x86_64-pc-windows-msvc' && env.WIN_CERT_PFX != ''
  env:
    WIN_CERT_PFX: ${{ secrets.WIN_CERT_PFX }}
    WIN_CERT_PASSWORD: ${{ secrets.WIN_CERT_PASSWORD }}
  shell: pwsh
  run: |
    $pfxBytes = [Convert]::FromBase64String($env:WIN_CERT_PFX)
    [IO.File]::WriteAllBytes("cert.pfx", $pfxBytes)
    & signtool sign /f cert.pfx /p $env:WIN_CERT_PASSWORD `
                    /tr http://timestamp.digicert.com /td sha256 `
                    /fd sha256 /v dist/tars-sidecar-x86_64-pc-windows-msvc.exe
    Remove-Item cert.pfx
```

**Graceful degrade:** the `env.WIN_CERT_PFX != ''` gate means absent secret
= step skipped = sidecar ships unsigned (current behaviour preserved). Same
pattern as the existing Apple fallback in §10 of the workflow.

**Test:** push a commit on a branch with no `WIN_CERT_PFX` secret → CI should
log "Sign Python sidecar (Windows) … skipped" and complete normally.

**Files touched:** `.github/workflows/release-desktop-tagged.yml` (+15 lines).
**PR size:** ~20 LoC.

### Step 4 — Cert import + thumbprint injection CI step — ~3h

**Change:** `.github/workflows/release-desktop-tagged.yml` — insert NEW step
BEFORE `tauri-action` build step:

```yaml
- name: Import Windows code-signing cert (Windows)
  if: matrix.target == 'x86_64-pc-windows-msvc' && env.WIN_CERT_PFX != ''
  env:
    WIN_CERT_PFX: ${{ secrets.WIN_CERT_PFX }}
    WIN_CERT_PASSWORD: ${{ secrets.WIN_CERT_PASSWORD }}
  shell: pwsh
  id: import-win-cert
  run: |
    $pfxBytes = [Convert]::FromBase64String($env:WIN_CERT_PFX)
    [IO.File]::WriteAllBytes("cert.pfx", $pfxBytes)
    $securePass = ConvertTo-SecureString -String $env:WIN_CERT_PASSWORD -AsPlainText -Force
    $cert = Import-PfxCertificate -FilePath cert.pfx -Password $securePass `
                                  -CertStoreLocation Cert:\CurrentUser\My
    Remove-Item cert.pfx
    echo "thumbprint=$($cert.Thumbprint)" >> $env:GITHUB_OUTPUT

- name: Patch tauri.conf.json with thumbprint (Windows)
  if: matrix.target == 'x86_64-pc-windows-msvc' && env.WIN_CERT_PFX != ''
  shell: pwsh
  run: |
    $conf = Get-Content desktop/src-tauri/tauri.conf.json -Raw | ConvertFrom-Json
    $conf.bundle.windows.certificateThumbprint = "${{ steps.import-win-cert.outputs.thumbprint }}"
    $conf | ConvertTo-Json -Depth 100 | Set-Content desktop/src-tauri/tauri.conf.json
```

Tauri then picks up `certificateThumbprint` during bundle and signs `.exe` + `.msi` automatically.

**Test:** unit test for the patch script in `scripts/sign-windows.test.ps1`
(new, ~30 LoC) that asserts the JSON structure survives a round-trip.

**Files touched:** `.github/workflows/release-desktop-tagged.yml` (+30 lines), `scripts/sign-windows.test.ps1` (new, ~30 LoC).
**PR size:** ~60 LoC + 30 LoC test.

### Step 5 — Verify-sign CI step (gate) — ~1.5h

**Change:** `.github/workflows/release-desktop-tagged.yml` — insert NEW step
AFTER `tauri-action` build, BEFORE upload:

```yaml
- name: Verify Windows signatures
  if: matrix.target == 'x86_64-pc-windows-msvc' && env.WIN_CERT_PFX != ''
  shell: pwsh
  run: |
    $artifacts = Get-ChildItem -Recurse -Filter "TARS_*-setup.exe","TARS_*.msi" `
                 -Path desktop/src-tauri/target/x86_64-pc-windows-msvc/release/bundle/
    foreach ($file in $artifacts) {
      & signtool verify /pa /v $file.FullName
      if ($LASTEXITCODE -ne 0) {
        Write-Error "Signature verification FAILED on $($file.Name)"
        exit 1
      }
    }
    Write-Host "✓ All Windows artifacts signed + verified"
```

**Hard gate:** if any artifact fails `signtool verify /pa`, the build job
fails. This catches misconfigured thumbprint, expired cert, broken
timestamp server — all before publishing to GH Release.

**Files touched:** `.github/workflows/release-desktop-tagged.yml` (+15 lines).
**PR size:** ~20 LoC.

### Step 6 — Operator setup runbook — ~1.5h

**New file:** `docs/WINDOWS_SIGNING_SETUP.md` (~250 LoC, symmetric to
`APPLE_SIGNING_SETUP.md`):

Sections:

1. Why this matters (SmartScreen impact, conversion drop)
2. What you need (CA selection per §3 above, payment, business verification docs)
3. Step-by-step OV cert purchase from Sectigo/DigiCert/SSL.com
4. PFX export from cert installer
5. PFX → base64 → clipboard one-liner (PowerShell or `base64 < cert.pfx | pbcopy` on macOS)
6. GitHub Secrets push (2 secrets: `WIN_CERT_PFX`, `WIN_CERT_PASSWORD`)
7. Manual dispatch dry-run + log check (`Sign Python sidecar (Windows)` step should NOT show "skipped")
8. Verification of published artifact on factory-clean Windows 11 machine
9. SmartScreen reputation tracker (Microsoft's reporting form URL, weekly download count check)
10. Cert renewal calendar (1 year window)

**Files touched:** `docs/WINDOWS_SIGNING_SETUP.md` (new, ~250 LoC).
**PR size:** doc-only.

---

## 6. Estimated effort

| Step | Implementer hours | Operator hours | PR LoC |
|---|---|---|---|
| 1. Tauri config | 1.5 | 0 | 10 |
| 2. Local sign script | 2.5 | 0 | 120 |
| 3. Sidecar sign CI | 2.0 | 0 | 20 |
| 4. Cert import + thumbprint CI | 3.0 | 0 | 90 |
| 5. Verify-sign CI gate | 1.5 | 0 | 20 |
| 6. Operator runbook | 1.5 | 3.0 (cert purchase + verification) | 250 |
| **Total** | **12.0** | **3.0** | **510** |

Plus ~$170/yr OV cert (operator).

---

## 7. Test plan

### Unit tests (new)

| File | Tests | LoC |
|---|---|---|
| `scripts/sign-windows.test.ps1` | JSON round-trip patch + cert lookup mock | 30 |

### CI smoke (no real cert)

Each step's "graceful degrade" path is tested by running the workflow on a
PR branch WITHOUT secrets: Steps 3/4/5 must skip cleanly and produce
unsigned artifacts identical to today.

### Real-cert validation (operator)

1. Push real `WIN_CERT_PFX` to GitHub Secrets.
2. Manual workflow dispatch on `main`.
3. Download produced `.exe` from artifact.
4. On factory-clean Windows 11 VM:
   - `signtool verify /pa /v TARS_*.exe` → "Successfully verified"
   - Browser download → no "blocked" red banner (after reputation accrual)
   - Run installer → SmartScreen may still show "More info" for the first
     ~1 wk; "Run anyway" should NOT require admin prompt
   - Installed `TARS.exe` launches cleanly

### Soak (couples to PH11 brief)

Windows soak is NOT in the v10.0.0 72h soak (Mac-only soak per PH11 §4.3).
v10.1 introduces Windows soak as a separate 24h test on a dedicated VM.

---

## 8. Files touched (summary)

**New (5 files):**
- `docs/handoff/PH4_WINDOWS_SIGN_BRIEF.md` (this file)
- `docs/WINDOWS_SIGNING_SETUP.md`
- `scripts/sign-windows.ps1`
- `scripts/SIGN-WINDOWS.command`
- `scripts/sign-windows.test.ps1`

**Modified (2 files):**
- `desktop/src-tauri/tauri.conf.json` (+5 lines)
- `.github/workflows/release-desktop-tagged.yml` (+60 lines across 3 inserted steps)

**Total diff:** ~510 LoC (most in the new operator runbook).

---

## 9. Open questions (6)

1. **Q1.** Patch `tauri.conf.json` at CI build time (Step 4) vs. use a
   secondary `tauri.windows.conf.json` overlay (Tauri 2.x merge)?
   _Lean: patch at build time. Overlay file would need to be `.gitignore`d
   to avoid leaking thumbprint to commits. Patch-and-revert is cleaner._

2. **Q2.** Sign the sidecar with the same cert as the installer, or a
   separate cert?
   _Lean: same cert. Two certs doubles cost + complexity for no measurable
   trust gain (both signed by same CA chain)._

3. **Q3.** Timestamp server: DigiCert (`http://timestamp.digicert.com`)
   vs. Sectigo (`http://timestamp.sectigo.com`) vs. Comodo
   (`http://timestamp.comodoca.com`)?
   _Lean: DigiCert. Highest uptime per anecdata, free for everyone, no
   rate-limit issues reported. SSL.com runs their own at
   `http://ts.ssl.com` if cert is bought from them — adds vendor lock-in._

4. **Q4.** Local dev sign on macOS: SSH to a Windows VM, WSL2, or skip?
   _Lean: skip for v10.1. Local devs run `pnpm tauri dev` which bypasses
   the sign step entirely. Operator signs via CI manual dispatch. Revisit
   for v10.2 if a real desktop-dev-on-Windows workflow emerges._

5. **Q5.** Should SmartScreen reputation be actively boosted via
   Microsoft Partner Center submission (free, ~1 wk review)?
   _Lean: yes, but separate non-blocking task. File as v10.1 follow-up
   `WIN_SMARTSCREEN_SUBMISSION.md`._

6. **Q6.** EV cert upgrade trigger threshold?
   _Lean: if OV cert reputation has NOT cleared after 6 wks of v10.1
   public availability (defined as zero new "blocked" reports on
   tars.meeet.world support email for 14 consecutive days), upgrade to EV
   for v10.2 release. Otherwise stay on OV._

---

## 10. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| OV cert SmartScreen reputation doesn't clear in 4 wks | Medium | High (drops conv) | Upgrade to EV (§Q6) |
| `.pfx` leaks via base64 logged in CI | Low | Critical | `Remove-Item cert.pfx` after import; GH Secrets masking |
| Timestamp server down → unsigned timestamp | Low | Medium (rebuild required) | Try 2 servers (DigiCert + Sectigo fallback) |
| Sidecar AV false positive even after signing | Medium | Medium (Defender quarantine) | Submit to Microsoft AV team (separate task), consider Nuitka migration |
| Cert revoked by CA (e.g. compliance issue) | Low | Critical | Maintain 2nd cert from different CA as backup (~$170 extra/yr) |
| WiX/NSIS bundle format change breaks signing | Low | Medium | Pin Tauri version in `Cargo.toml`, surface upgrades in `desktop-version-lint.yml` |

---

## 11. Coupling to v10 GA arc

| Phase | Brief | Windows sign role |
|---|---|---|
| v10.0.0 GA | PH11_QA_SWEEP_BRIEF | Windows artifact ships **unsigned** (current behaviour preserved); marketing labels Windows as "Preview" |
| v10.1 | **this brief** | Implement steps 1–6; operator pushes `WIN_CERT_*` secrets; SmartScreen reputation begins accruing |
| v10.2 | follow-up | Decision per Q6: stay OV or upgrade EV |
| v11 | future | Microsoft Store `.msix` distribution (separate brief, not gated by this work) |

**Critical:** this brief is **NOT a v10.0.0 GA blocker**. Mac launch ships
first; Windows preview ships unsigned. v10.1 closes the Windows sign gap.
The brief is queued for implementation only after v10.0.0 ships.

---

## 12. References

- `docs/APPLE_SIGNING_SETUP.md` — sister doc, follow same shape
- `docs/handoff/PH4_APPLE_SIGN_V10_BRIEF.md` — sister brief (PR #199)
- Tauri 2.x bundle docs: <https://v2.tauri.app/distribute/sign/windows/>
- Microsoft Authenticode reference: <https://learn.microsoft.com/en-us/windows/win32/seccrypto/cryptography-tools>
- SmartScreen reputation system: <https://learn.microsoft.com/en-us/windows/security/operating-system-security/virus-and-threat-protection/microsoft-defender-smartscreen/microsoft-defender-smartscreen-overview>
- `desktop/src-tauri/tauri.conf.json` — bundle config
- `.github/workflows/release-desktop-tagged.yml` — release pipeline

---

*Brief authored as part of the W310 wave (sub-wave `W310-o`). Companion
briefs: `PH4_APPLE_SIGN_V10_BRIEF.md` (PR #199, on GA critical path),
`PH4_UPDATER_BOOTSTRAP_BRIEF.md` (next, T0 with Apple sign).*
