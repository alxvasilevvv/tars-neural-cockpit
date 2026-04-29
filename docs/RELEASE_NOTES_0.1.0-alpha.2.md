# TARS 0.1.0-alpha.2

> Released **2026-04-29** · channel **stable** · contract version **1.0.0**

This is the **Phase M backbone** alpha. It closes the last functional
gaps identified in the launch-readiness audit: tier-based
entitlements, operator roles with synthesised overlays, vision agent
with multimodal routing, and the canonical `entrepreneur` pack
(replacing the legacy `mlm` slug).

Everything below is shipped, tested, and ready for the **public binary
alpha** as soon as the operator-side signing credentials are in
place — see `docs/OPERATOR_RUNBOOK.md` for the exact tag-and-push
sequence.

---

## What's new

### Entitlements (P5)

The local-first, MIT-licensed install is unlimited — what changes
between tiers is **cloud LLM budget** and **cloud-only features** like
sync, T2T (agent-to-agent), and council voting:

| Tier         | $/mo  | Daily cloud budget | Cloud sync | T2T deals/mo | Council votes/day | Audit / RBAC |
|--------------|------:|-------------------:|:----------:|-------------:|------------------:|:------------:|
| Free         | $0    | $0.00              | —          | 0            | 0                 | —            |
| Pro          | $19   | ~$0.33             | ✓          | 50           | 100               | —            |
| Business     | $79   | ~$1.33/seat        | ✓          | unlimited    | unlimited         | ✓ / ✓        |

Five new HTTP endpoints (`/api/entitlements`, `/upgrade`, `/byo`,
`/can_run`, `/tiers`) + meeet events
(`entitlements.{upgraded,byo_toggled,cap_hit}`). The cap is enforced
against the live usage ledger; BYO key path relaxes the cap.

### Roles (P7)

Six built-in roles match the cockpit Onboarding page:

- **Founder / CEO** — daily brief from KPI + deals + calendar
- **Trader** — markets, signals, risk
- **Researcher** — citation-graph, arXiv-aware
- **Marketer** — outreach drafts in your voice
- **Engineer** — repos indexed, PR review queue
- **Operator** — generalist, all packs

Plus a **Custom** role: free-form name + description → deterministic,
auditable system-prompt overlay (the orchestrator prepends it before
the active pack prompt). Six endpoints
(`GET /api/roles`, `GET /active`, `POST /{slug}/activate`,
`POST /api/roles`, `DELETE /{slug}`, `GET /{slug}/overlay`).

### Vision agent (P8)

`backend/agents/vision_agent.py` inspects every image attachment in a
thread and folds a structured summary (filename, mime, dimensions,
OCR text or "OCR unavailable") into the system prompt — for **every**
voice. Multimodal voices (Anthropic 3.5 Sonnet, OpenAI gpt-4o family)
additionally receive native image refs through the existing
`attachments` parameter. New `context.vision` `StreamEvent` for
cockpit rendering. OCR is opt-in via pytesseract; the agent reports
`unavailable` cleanly when the binary is missing rather than crashing.

### Entrepreneur pack (P6)

Canonical replacement for the `mlm` pack with renamed action ids
(`network_snapshot`, `lead_score`, `generate_content`, `add_lead`,
`retention_alert`, `log_activity`). The legacy `mlm` slug stays
registered with `manifest.deprecated=True` and
`deprecated_in_favor_of="entrepreneur"` until **2026-07-29** — saved
cockpit state and agents pinned to it keep working.

### Recovery × policy gate

`POST /api/recovery/{generate,verify}` now flow through the same
HMAC-signed confirm-token path as wallet ops when
`TARS_REQUIRE_OPERATOR_CONFIRM=1`. Mint via
`POST /api/recovery/confirm`. Default-off so the dev / first-launch
flow doesn't change.

### Cleanup

- Stale TODO comments removed from `desktop/src-tauri/src/main.rs`
  and `web_extras/routers/recovery.py`.
- `desktop/scripts/generate-release-keys.sh` gained `--patch-tauri-conf`
  to auto-rewrite `plugins.updater.pubkey`.
- Mobile activity wiring on both platforms
  (Android `WalletActivity` + iOS `TARSCompanionRoot`).

---

## Test totals (this release)

| Suite  | Count       | Status |
|--------|------------:|--------|
| pytest | **671**     | ✅ all green |
| vitest | **56**      | ✅ all green |
| swift  | **18**      | ✅ all green |
| tsc    | `--noEmit`  | ✅ clean    |

(Was **600 pytest** before this release — net +71 across the four
new modules + cleanup-pass.)

---

## Upgrade notes (alpha → alpha.2)

- **No data migrations required.** Wallets, agents, threads,
  attachments, and sync envelopes are unchanged.
- **MLM users**: the `mlm` slug keeps resolving — the cockpit will
  point to the `entrepreneur` pack on the next session start, and
  the legacy slug is honoured via `manifest.deprecated`. After
  **2026-07-29** the legacy registration will be removed.
- **`TARS_REQUIRE_OPERATOR_CONFIRM=1`** now also gates the recovery
  router. If you had this on, mint a token via
  `POST /api/recovery/confirm` before calling `/generate` or
  `/verify`.

---

## Known limitations

- **macOS / Windows code signing**: requires Apple Developer ID +
  notarization (macOS) and Authenticode (Windows). Both are
  operator-side credentials; the CI workflow consumes them as
  GitHub secrets. Until those are in place, the alpha ships as
  unsigned binaries with a Minisign sidecar (`<artifact>.sig`).
- **Updater public key** (`plugins.updater.pubkey` in
  `tauri.conf.json`) is set during the operator runbook (see
  `docs/OPERATOR_RUNBOOK.md`).
- **Mobile companion** is read-only + prove-ownership. Hot custody
  stays on the host by design.
- **Vision OCR** requires `pytesseract` + the system `tesseract`
  binary. Without them the agent reports `unavailable` rather than
  failing the request.
- **Linux bundles** depend on `libwebkit2gtk-4.1-dev` /
  `libgtk-3-dev` / `libayatana-appindicator3-dev` /
  `librsvg2-dev` on the build host (CI installs them).

---

## How to install (once binaries are signed + published)

```bash
# macOS (Apple silicon)
curl -L https://meeet.world/downloads/tars/0.1.0-alpha.2/TARS-0.1.0-alpha.2-arm64.dmg \
  -o ~/Downloads/TARS-alpha.2.dmg && open ~/Downloads/TARS-alpha.2.dmg

# Linux (AppImage)
curl -L https://meeet.world/downloads/tars/0.1.0-alpha.2/TARS-0.1.0-alpha.2-x64.AppImage \
  -o ~/Downloads/TARS-alpha.2.AppImage && chmod +x ~/Downloads/TARS-alpha.2.AppImage

# Windows (PowerShell)
Invoke-WebRequest https://meeet.world/downloads/tars/0.1.0-alpha.2/TARS-0.1.0-alpha.2-Setup.exe `
  -OutFile $env:USERPROFILE\Downloads\TARS-alpha.2.exe
```

Or grab the binary from the GitHub release page once `desktop-v0.1.0-alpha.2`
finishes building.

---

## Verifying signatures

Every artifact ships with a `<filename>.sig` Minisign sidecar.
Verify with:

```bash
minisign -V -p ./tars-desktop.pub -m ./TARS-0.1.0-alpha.2-arm64.dmg
```

Public key lives at `desktop/src-tauri/tauri.conf.json` →
`plugins.updater.pubkey` (and is mirrored at
`https://meeet.world/.well-known/tars/pubkey.minisign`).
