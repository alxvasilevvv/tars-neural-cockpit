# TARS v10.0 GA — Final Checklist

> 30-item go/no-go for the `v10.0.0` tag. Generated W267 alongside
> `scripts/FINAL-QA-GATE.command` and `scripts/RELEASE-v10.0.command`.
> Source of truth is `TARS_MASTER_DOC.md` §6.4; this is the
> operator-facing one-page version.

Status legend: `[x]` complete · `[ ]` blocking GA · `[~]` in flight (not blocking).

---

## A. Brother (`api.meeet.world`) — external lane

- [ ] **A1.** `POST /api/billing/usage_event` live, HMAC-signed `UsageEvent` ingest.
- [ ] **A2.** `GET /api/billing/balance` returns live balance for any logged-in user.
- [ ] **A3.** `POST /api/billing/topup` works for both $MEEET (Solana) and card.
- [ ] **A4.** Daily reconciliation handshake green (`scripts/reconcile-meeet-billing.py` <$0.50 drift).
- [ ] **A5.** Auth endpoints: magic-link start/redeem + OAuth start + `/api/me` (4 routes).

## B. Apple Developer + macOS distribution

- [ ] **B1.** `APPLE_TEAM_ID`, `APPLE_DEVELOPER_ID_APPLICATION`, `APPLE_NOTARY_PROFILE` set in CI secrets.
- [ ] **B2.** `.p12` certificate uploaded to GitHub Actions encrypted secrets.
- [ ] **B3.** `scripts/SIGN-AND-NOTARIZE.command` runs end-to-end on Alien's host with a fresh build.
- [ ] **B4.** `spctl --assess --type execute /Applications/TARS.app` returns `accepted` (gate 4 of FINAL-QA-GATE).
- [ ] **B5.** Tauri updater JSON published at `https://tars.meeet.world/updater/latest.json`.

## C. VS Code marketplace (`tars-tab` — W254)

- [ ] **C1.** `vscode-extension/` package builds via `vsce package` with no warnings.
- [ ] **C2.** Marketplace publisher account registered (`meeet` namespace).
- [ ] **C3.** First `vsce publish` succeeds; extension listed at marketplace.visualstudio.com.
- [ ] **C4.** Extension auto-discovers `127.0.0.1:8765` and shows the live composer panel.

## D. On-prem deployment kit (W263)

- [ ] **D1.** `scripts/ONPREM-DEPLOY/install.sh` runs clean on a fresh Ubuntu 22.04 VM.
- [ ] **D2.** `docker compose up` brings stack live with Postgres + receipt anchor + frontend.
- [ ] **D3.** First paying on-prem customer signed off acceptance test.
- [ ] **D4.** SAML/OIDC integration verified against customer IdP.
- [ ] **D5.** Backup + restore playbook drilled (`docs/ONPREM_DEPLOYMENT_GUIDE.md` §11).

## E. Perf + QA gates (Claude lane — done locally)

- [x] **E1.** `bash scripts/RUN-PERF-SUITE.command` — all 5 SLOs green (W266).
- [x] **E2.** `bash scripts/FINAL-QA-GATE.command` — all 8 gates green (W267).
- [x] **E3.** `bash scripts/SMOKE-TEST.command` clean — 60+ routes 2xx.
- [x] **E4.** Full `pytest` suite passes (excluding opt-in perf marker).
- [x] **E5.** Version constants consistent across 9 files (`web_extras/app.py`, `desktop/*`, etc).

## F. Compliance + receipts

- [x] **F1.** SOC2 Type II readiness doc shipped (W257).
- [x] **F2.** GDPR export router (`/api/gdpr/export`) returns full data bundle.
- [x] **F3.** `scripts/COMPLIANCE-BUNDLE.command` produces signed audit bundle.
- [x] **F4.** Receipts hash-chain integrity verified end-to-end on the rc1 dataset.

## G. Marketing + launch comms

- [x] **G1.** Release notes shipped (`docs/RELEASE_NOTES_v10.0-rc1.md` → renamed to `v10.0` at tag).
- [x] **G2.** CHANGELOG entry for `v10.0.0` ready.
- [ ] **G3.** Marketing assets ready: blog post + Twitter thread + HN/PH launch text.
- [ ] **G4.** Landing page "Download" CTA flipped from "Coming soon" → live `.dmg` URL.

---

## What's still on the operator (the 5 things)

These five items can't be closed from inside the repo — they are
external dependencies the operator must drive. **The repo is GA-ready
the moment all five flip to `[x]`:**

1. **rc1 soak on Alien's main host** — 1 week, daily `bash scripts/SMOKE-TEST.command`.
2. **Brother live on billing** — items A1-A5 above; un-blocks tier-cap UX from local-replay fallback to cloud reconciliation.
3. **Apple cert in CI** — items B1-B5; un-blocks every-tag auto-signed `.dmg`.
4. **VS Code marketplace publish** — items C1-C4; un-blocks `tars-tab` distribution.
5. **First paying on-prem customer** — items D1-D5; proves the W263 kit works end-to-end.

When all five are green, run:

```bash
bash scripts/RELEASE-v10.0.command
```

That script aborts immediately if `FINAL-QA-GATE.command` fails, so
there's no path to a broken GA tag.
