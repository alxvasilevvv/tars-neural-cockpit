# TARS desktop v0.1.0-rc.1 — release notes draft

> **Status:** draft, 2026-05-01. Operator-Brother to confirm version
> bump and tag-push trigger.
> **Blockers:** macOS code signing certs (see §4) and DNS go-live.

This is the first release-candidate cut intended for distribution
beyond the developer machine. It bundles every fix shipped between
`v0.1.0-alpha.1` and now, including the Tauri WebView storage
hardening, the cockpit/marketing split (cockpit only inside the
desktop shell), and the meeet.world bridge integration.

---

## What's in this release

### Stability & correctness

- **`SecurityError` in Tauri WebView fixed.** All `localStorage` /
  `sessionStorage` calls are now wrapped in `try/catch` with in-memory
  fallbacks. Affected files: `src/lib/analytics.ts`,
  `src/components/ThemeToggle.tsx`. Issue first reported by Operator
  on 2026-04-22.
- **Cockpit/marketing split.** Marketing-only widgets (`Atmosphere`,
  `Brackets`, `MagneticCursor`, command palette, route transition,
  cookie consent) are no longer mounted when running inside the
  desktop shell. The cockpit is the entire desktop experience.
- **Storage shadowing fix.** `CookieConsent.tsx` no longer shadows
  `useT().t` with `setTimeout` capture variable.
- **`BuildWith` URL validation.** Embeddable badges now validate the
  user-supplied URL and HTML-escape before building the snippet.

### Observability

- **`tars.client.error` global handler.** Uncaught errors and
  promise rejections are deduped, rate-limited, PII-stripped, and
  forwarded through `core-bridge/relay-event` to `tars-ingest` for
  90-day retention. Zero-vendor (no Sentry, no Datadog).
- **`tars.page.viewed` events.** Every cockpit and marketing route
  view emits a structured event with `trace_id` propagation.

### Networking

- **meeet.world bridge.** Outbound events are signed with
  `MEEET_API_KEY`, contract version pinned at `1.0.0`, ingest URL
  pointing at the new TARS Supabase project
  `hhpaukjobskcwkxbgecl`.
- **Auto-update channel.** Updater feeds:
  - `https://meeet.world/updates/{target}/{version}.json`
  - `https://updates.meeet.world/tars/{target}/{version}.json`
- **CSP.** Connect-src restricted to `'self'`,
  `http://127.0.0.1:8765`, `ws://127.0.0.1:8765`, `https://meeet.world`.
  No `'unsafe-eval'`, no `'unsafe-inline'` for scripts.

### Build & packaging

- Bundle targets: `dmg`, `app`, `msi`, `nsis`, `deb`, `appimage`.
- macOS: `minimumSystemVersion: 12.0` (Monterey).
- Windows: NSIS `currentUser` installer (no admin elevation).

---

## What's not in this release (deferred)

- Bundle-size optimisation (Spline + physics chunks at ~2 MB each).
  Tracked in CHANGELOG_AGENTS as the bundle-optimisation lane.
- On-chain $MEEET transfers. Today off-chain via Edge Function;
  RPO is bounded by Supabase PITR (DR runbook §4).
- WAF tightening, pen test, field-level encryption. Documented in
  `SECURITY_BASELINE.md` §9 with rationale for deferral.
- macOS notarisation throughput optimisation (sometimes Apple takes
  >10 min). Workaround: rerun the workflow.

---

## Operator checklist before tagging

The release workflow (`.github/workflows/release-desktop-tagged.yml`)
fires on `v*` tag push. Before tagging, confirm:

- [ ] GitHub repo secrets present:
      - `APPLE_CERTIFICATE` (base64 of .p12)
      - `APPLE_CERTIFICATE_PASSWORD`
      - `APPLE_SIGNING_IDENTITY` (e.g. `Developer ID Application: meeet (XXXXXXXXXX)`)
      - `APPLE_ID` (notarisation account email)
      - `APPLE_PASSWORD` (app-specific password)
      - `APPLE_TEAM_ID`
      - `WINDOWS_CERTIFICATE` (optional, Windows authenticode)
      - `WINDOWS_CERTIFICATE_PASSWORD` (optional)
- [x] `desktop/src-tauri/tauri.conf.json` `version` already `0.1.0-rc.1`
      (triad sync 2026-05-01).
- [x] `desktop/src-tauri/Cargo.toml` `version` already `0.1.0-rc.1`.
- [x] `desktop/package.json` `version` already `0.1.0-rc.1`.
- [x] CHANGELOG_AGENTS.md has an entry for this release.
- [x] `make qa-agent` is green or has only documented warnings
      (yellow is OK when `BRIDGE_SHARED_SECRET` is not yet on Pages).

If any cert is missing the macOS build will publish an unsigned
artefact, which Gatekeeper rejects on first launch. We can ship
unsigned for internal testing only.

---

## How to release once green

```bash
# from a clean main
git checkout main && git pull
# bump version in tauri.conf.json + Cargo.toml
git add desktop/src-tauri/tauri.conf.json desktop/src-tauri/Cargo.toml
git commit -m "release: v0.1.0-rc.1"
git tag -a v0.1.0-rc.1 -m "TARS desktop v0.1.0-rc.1"
git push integration main
git push integration v0.1.0-rc.1
```

The workflow runs ~15 min on each platform. Artefacts publish to a
GitHub Release draft; Operator promotes to "published" after
manual smoke (open the .dmg, confirm launch, confirm meeet.world
event flows).

---

## Rollback

If a regression is discovered after publish:

1. Mark the GitHub Release as "pre-release" so the auto-updater
   stops serving it.
2. Update `meeet.world/updates/{target}/0.1.0-rc.1.json` to point
   at the previous artefact (the auto-updater respects whatever is
   in the JSON, not the GitHub Release order).
3. Open `regression: desktop v0.1.0-rc.1 <symptom>` issue.

CF Pages rollback semantics for the cockpit web build are
unaffected (those live in CF, not in GitHub Releases).
