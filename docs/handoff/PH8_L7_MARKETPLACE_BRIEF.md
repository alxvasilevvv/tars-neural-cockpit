# PH8 — Phase 8 / L7 marketplace v1 (pack format + signing + preflight + UI) implementer brief

**Owner:** next L7-lane implementer
**Release target:** v11
**Scope window:** ~3 weeks / ~8 PRs
**Estimated LoC:** ~3.6k (incl ~1.0k LoC tests + ~280 LoC cockpit)
**Status entering brief:** **v0 marketplace shipped (Wave 106, ~1.6k LoC + 267 LoC HTTP); v1 brief delivers L7-spec pack format, hard-fail signing, preflight, remote distribution, and cockpit `<MarketplaceSheet />`**

---

## 0. TL;DR for the implementer

This is a **mixed backend + cockpit** brief. Marketplace v0 (Wave 106)
shipped a "listing browser" for in-repo playbook bundles with
opportunistic ed25519 verification ("warn don't block"). The L7
contract in `docs/PHASE_L_ROADMAP.md §L7` calls for a **stronger**
shape:

1. A **pack package format** (`.tars-pack/` zip) with `manifest.json`
   + `pack.py` + `actions.py` / `awareness.py` / `prompts.py` +
   `data/` + `README.md` + `pack.sig`.
2. **Hard-fail signing**: ed25519 over sha256 of every file; on
   mismatch the install is rejected outright (no "warn and proceed").
3. **Static-analysis preflight**: no `os.system`, no `eval`, no
   `exec`, no `__import__`, restricted import set. Best-effort but
   reject on failure.
4. **Remote distribution** over plain HTTPS from `meeet.world/packs/`
   (`GET /packs/index.json`). Signing key derived from the author's
   meeet.world identity.
5. Cockpit **`<MarketplaceSheet />`** modal — browse, install,
   update, uninstall, ratings (already shipped, just rewire).

The v0 listing browser stays — it remains useful for the
playbooks-bundled-with-TARS catalog. The v1 pack path is a parallel
install lane keyed by listing `kind="pack"` (existing
`LISTING_KINDS` enum already has the slot — verified in
`backend/core/marketplace/models.py`).

**8 mechanical steps** (~3.6k LoC). Hard-dep on PH5 vault (#202)
because the per-installation pack signing key is treated as a
secret and lives behind the vault.

---

## 1. Why this brief exists (forensic note)

Run `wc -l backend/core/marketplace/*.py web_extras/routers/marketplace.py`
on `main` and you see ~1.8k LoC of shipped surface. The CHANGELOG /
HANDOFF Wave 106 entry calls this "marketplace v0" and explicitly
calls out the deferred items:

- No `.tars-pack/` zip format.
- No hard-fail signing.
- No static-analysis preflight.
- No remote registry beyond `urllib.request` with a 5 s timeout +
  bundled seed fallback.
- No cockpit modal — only the HTTP surface.

The cockpit currently surfaces marketplace listings only via the
**raw `/api/marketplace/*` endpoints**; there is no operator-visible
sheet (verifiable: `rg -l 'marketplace' apps/cockpit/src/` returns
nothing). Operators have to curl to install — same pattern as the
planner pre-PH7.

This brief is the v1 closure. It is also the **last L0-L9 backend
brief** (after PH6 sandbox brief #205 closed L3 and PH7 planner
brief #206 closed L6's UI gap, only L10 mobile remains in the
L-roadmap).

---

## 2. Target architecture

```
       ┌───────────────────────────────────────────────────────────────┐
       │  meeet.world/packs/                                           │
       │  ─────────────────────                                        │
       │  GET /packs/index.json     → list of {slug, latest_version,   │
       │                                       sha256, pubkey,         │
       │                                       download_url}           │
       │  GET /packs/<slug>/<ver>.tars-pack  → zip                     │
       │                                                               │
       │  Author identity-based signing — pubkey is the author's       │
       │  meeet.world identity ed25519 pubkey (already used elsewhere) │
       └─────────────────────────────┬─────────────────────────────────┘
                                     │
                                     │ POST /api/marketplace/packs/install
                                     │     {slug, expected_sha256, expected_pubkey}
                                     ▼
              ┌──────────────────────────────────────────┐
              │  web_extras/routers/marketplace.py       │
              │  - new endpoints (existing surface +)    │
              │    POST /api/marketplace/packs/install   │
              │    POST /api/marketplace/packs/{slug}/   │
              │         {uninstall, update, preflight}   │
              │  - policy_gate.require_confirm on all    │
              │    state-changing ops (HIL)              │
              └─────────────┬────────────────────────────┘
                            │
                            │ install(slug, sha256, pubkey)
                            ▼
              ┌──────────────────────────────────────────┐
              │  backend/core/marketplace/pack_installer  │
              │  ─────────────────────────────────────── │
              │   1. download zip → tmp                  │
              │   2. verify sha256 (hard-fail)           │
              │   3. unzip → tmp                          │
              │   4. verify ed25519 over file hashes      │
              │      from pack.sig (hard-fail)           │
              │   5. preflight static analysis (reject   │
              │      on os.system / eval / restricted     │
              │      imports)                            │
              │   6. unpack to ~/.tars/packs/<slug>/     │
              │   7. _reload registry; emit pack.installed│
              │   8. row in installed.sqlite (existing)  │
              └─────────────────────────────────────────┘
                            │
                            ▼
              ┌──────────────────────────────────────────┐
              │  apps/cockpit MarketplaceSheet (modal)   │
              │  - tabs: Catalog, Installed, Updates     │
              │  - per-pack card with author, sha256,    │
              │    pubkey fingerprint, rating, install   │
              │  - install button → policy queue (#203)  │
              └──────────────────────────────────────────┘
```

---

## 3. Pack format v1 (canonical)

```
research-papers-1.2.3.tars-pack/         # extracted dir name
├── manifest.json                        # see §3.1
├── pack.py                              # entry point (must subclass DomainPack)
├── actions.py                           # imported by pack.py
├── awareness.py                         # optional
├── prompts.py                           # optional
├── data/                                # arbitrary bundled fixtures
│   └── ...
├── README.md
└── pack.sig                             # see §3.2
```

### 3.1 `manifest.json` (frozen schema for v11)

```json
{
  "schema_version": "1.0",
  "slug": "research-papers",
  "version": "1.2.3",
  "name": "Research Papers Concierge",
  "description": "Auto-summarises new papers from arXiv → notion.",
  "author": {
    "meeet_handle": "alice@meeet.world",
    "display_name": "Alice Cooper",
    "pubkey_ed25519_hex": "<32 byte hex>"
  },
  "license": "MIT",
  "homepage_url": "https://example.com/research-papers",
  "tars_min_version": "11.0.0",
  "tars_max_version": null,
  "kind": "pack",
  "destructive_actions": ["pack.summarise", "pack.write_to_notion"],
  "required_secrets": ["NOTION_TOKEN", "ARXIV_API_KEY"],
  "required_packs": [],
  "required_packs_min_versions": {},
  "actions_summary": [
    {"id": "pack.summarise", "destructive": true},
    {"id": "pack.daily_digest", "destructive": false}
  ],
  "data_residency": "local-only",
  "claimed_hashes": {
    "manifest.json": "sha256:...",
    "pack.py": "sha256:...",
    "actions.py": "sha256:...",
    "awareness.py": "sha256:...",
    "prompts.py": "sha256:...",
    "data/sources.json": "sha256:...",
    "README.md": "sha256:..."
  }
}
```

`claimed_hashes` is the contract: every file in the unpacked dir
**must** appear in this map (except `pack.sig` itself), and every
entry must hash-match. Any mismatch → reject install.

### 3.2 `pack.sig`

Single file, single line: hex-encoded ed25519 signature over the
JSON-serialized `claimed_hashes` map (canonical JSON: sorted keys,
no whitespace, UTF-8, NFC normalization on the map). Verification:

```python
ed25519.verify(
    pubkey=manifest["author"]["pubkey_ed25519_hex"],
    message=canonical_json(manifest["claimed_hashes"]).encode("utf-8"),
    signature=bytes.fromhex(open("pack.sig").read().strip()),
)
```

If verification fails: reject install with `MarketplacePackError(
    "signature_invalid", details={...}
)`.

---

## 4. Mechanical steps

### Step 1 — Pack types + manifest schema validator (~220 LoC)

**Files (new):**

- `backend/core/marketplace/pack_types.py` (~150 LoC):
  - `PackManifest` frozen dataclass mirroring §3.1.
  - `PackAuthor`, `PackActionSummary` sub-dataclasses.
  - `PackInstallError(MarketplaceError)` with explicit error code
    enum (`MANIFEST_INVALID`, `HASH_MISMATCH`, `SIGNATURE_INVALID`,
    `PREFLIGHT_REJECTED`, `DEPENDENCY_MISSING`, `VERSION_INCOMPATIBLE`,
    `STORAGE_FAILURE`).
  - `parse_manifest(raw: dict) -> PackManifest` w/ schema validation.
  - `CONTRACT_VERSION = "1.0"` constant.
- `backend/core/marketplace/_canonical_json.py` (~30 LoC) —
  RFC 8785-style canonical JSON for signature stability.
- `tests/test_marketplace_pack_types.py` (~40 LoC).

### Step 2 — Pack signing + verification primitives (~280 LoC)

**Files (new):**

- `backend/core/marketplace/pack_signing.py` (~180 LoC):
  - `sign_pack(manifest_path, privkey_hex) -> bytes` — sign helper
    (used by the publisher SDK, exported here for clarity).
  - `verify_pack(pack_dir: Path, manifest: PackManifest) -> None` —
    raises `PackInstallError("signature_invalid")` on mismatch.
  - `verify_claimed_hashes(pack_dir, claimed_hashes)` — file-by-file
    sha256 check; raises `PackInstallError("hash_mismatch")`.
- `tests/test_marketplace_pack_signing.py` (~100 LoC).

Reuses the existing `backend.core.entitlements` ed25519 helper if
present (verified shipped in Wave 106) — otherwise vendors a
minimal libsodium wrapper to keep the boundary thin.

### Step 3 — Pack preflight static analyzer (~390 LoC)

**Files (new):**

- `backend/core/marketplace/pack_preflight.py` (~280 LoC):
  - `preflight_pack(pack_dir: Path) -> PreflightReport` — walks
    every `.py` file in the pack dir, parses with `ast.parse`, runs
    an `ast.NodeVisitor` checking:
    - No `os.system`, `subprocess.*` calls.
    - No `eval`, `exec`, `compile`, `__import__` calls.
    - No `import socket`, `import requests`, `import httpx` unless
      `manifest.required_secrets` or `manifest.data_residency`
      explicitly opts in.
    - No `open(...)` with mode containing `"w"`/`"a"`/`"x"` outside
      `data/`.
    - No top-level imports of `os` (must `from os import` specific
      symbols).
    - No `Path("/").write_*` or `Path("/").mkdir`.
  - Reports findings as `PreflightReport(violations=[...], warnings=[...])`.
  - **Violations** reject install; **warnings** show in the
    cockpit cards but do not block.
  - Best-effort — explicitly NOT a security boundary. (L3 sandbox
    from #205 is the actual boundary; preflight is the "fail-fast
    sanity check".)
- `tests/test_marketplace_pack_preflight.py` (~110 LoC) with sample
  good + bad pack fixtures.

### Step 4 — Pack installer (zip download + extract + install) (~610 LoC)

**Files (new):**

- `backend/core/marketplace/pack_installer.py` (~490 LoC):
  - `download_pack(url: str, expected_sha256: str) -> Path` — tmp
    dir + `urllib.request` w/ 30 s timeout, hard-fail on sha256
    mismatch.
  - `install_pack(slug, expected_sha256, expected_pubkey) -> InstalledItem` — orchestrates download → unzip → verify
    sha256 → verify ed25519 (via §2) → preflight (via §3) →
    install to `~/.tars/packs/<slug>/` → reload domain registry →
    emit `pack.installed` meeet event → insert
    `installed.sqlite` row (reuses Wave 106 store).
  - `uninstall_pack(slug) -> None` — remove from
    `~/.tars/packs/<slug>/`, reload registry, emit
    `pack.uninstalled`, delete `installed.sqlite` row.
  - `update_pack(slug) -> InstalledItem` — diff installed version
    vs registry, fetch new zip if different, re-install (atomic
    via temp dir rename swap).
  - `list_installed_packs() -> list[InstalledPack]` — read
    `installed.sqlite` filtered to `kind="pack"`.
  - `get_pack_health(slug) -> PackHealth` — last load error,
    last preflight result, last successful action invocation.
- `tests/test_marketplace_pack_installer.py` (~120 LoC) with
  mocked `urllib.request` and an in-temp-dir fake pack zip.

Atomicity: installs go to `~/.tars/packs/<slug>.partial/` first;
on success rename to `~/.tars/packs/<slug>/`. On any failure
during preflight or signature check, the partial dir is removed.

### Step 5 — Remote registry client (`meeet.world/packs/index.json`) (~330 LoC)

**Files (new):**

- `backend/core/marketplace/pack_registry.py` (~250 LoC):
  - `fetch_pack_registry() -> list[PackRegistryEntry]` — fetches
    `https://meeet.world/packs/index.json` w/ 5 s timeout + 1 h
    disk cache at `~/.tars/marketplace/pack_registry.json`.
  - `get_pack_entry(slug) -> PackRegistryEntry` — by slug lookup.
  - `search_packs(query: str) -> list[PackRegistryEntry]` —
    client-side full-text on `name + description + author`.
  - `force_refresh_pack_registry() -> int` — bypass cache, return
    new count.
  - Each `PackRegistryEntry` carries `{slug, version, sha256,
    pubkey_ed25519_hex, download_url, name, description, author,
    rating_avg, install_count, claimed_destructive_actions}`.
- `tests/test_marketplace_pack_registry.py` (~80 LoC).

The brother stack on `meeet.world` side is responsible for
publishing `/packs/index.json` and `/packs/<slug>/<ver>.tars-pack`.
See coupling §6.

### Step 6 — HTTP surface extensions (~280 LoC)

**Files (modified):**

- `web_extras/routers/marketplace.py` — add 5 new endpoints:
  - `GET    /api/marketplace/packs/registry` — list of packs from
    `meeet.world` (proxies `fetch_pack_registry()` and joins with
    install state).
  - `POST   /api/marketplace/packs/install` — install via
    `pack_installer.install_pack(slug, sha256, pubkey)`. HIL-gated.
  - `POST   /api/marketplace/packs/{slug}/uninstall` — HIL-gated.
  - `POST   /api/marketplace/packs/{slug}/update` — HIL-gated.
  - `POST   /api/marketplace/packs/{slug}/preflight` — dry-run
    download + verify + preflight (no install). Returns
    `PreflightReport`. Useful for "show before install" UX.
  - `GET    /api/marketplace/packs/installed` — list installed
    packs from `installed.sqlite` filtered to `kind="pack"`.
- `tests/test_marketplace_pack_routes.py` (~100 LoC).

Each state-changing endpoint routes through the existing
`web_extras.policy_gate.require_confirm` so the policy inbox
(#203) sees the confirmation row with category `marketplace`.

### Step 7 — `<MarketplaceSheet />` cockpit modal (~1.2k LoC)

**Files (new):**

- `apps/cockpit/src/components/marketplace-sheet.ts` (~410 LoC) —
  modal with three tabs:
  - **Catalog** — pack registry list w/ search + sort by
    install_count/rating/recent.
  - **Installed** — installed packs w/ uninstall + update buttons.
  - **Updates** — installed packs w/ new versions available.
- `apps/cockpit/src/components/marketplace-pack-card.ts` (~240 LoC) —
  per-pack card (author, version, rating chip, install_count chip,
  destructive-action warning chip if any, install/uninstall/update
  button).
- `apps/cockpit/src/components/marketplace-preflight-modal.ts`
  (~210 LoC) — "Preview before install" view showing the
  `PreflightReport` violations/warnings, claimed_hashes table, and
  manifest summary.
- `apps/cockpit/src/lib/marketplace-client.ts` (~250 LoC) — HTTP
  wrapper mirroring §6 routes.
- `apps/cockpit/src/styles/marketplace.css` (~150 LoC).
- `apps/cockpit/src/pages/cockpit-entry.ts` — add "Marketplace 🛒"
  affordance in the global nav (button opens the sheet); ~30 LoC
  delta.

UX flow:

```
Operator clicks 🛒 → MarketplaceSheet opens → Catalog tab shows
N packs → click pack card → MarketplacePackCard expands → click
"Preview" → MarketplacePreflightModal opens → operator reviews
manifest + violations/warnings → click "Install" → policy inbox
gets a marketplace.pack.install entry → operator approves it (or
auto-approves if cohort rules permit) → installer runs → on
success the card flips to "Installed" + emits a toast.
```

Visual treatment matches existing cockpit token system. No new
npm deps.

### Step 8 — Publisher SDK CLI + docs (~310 LoC)

**Files (new):**

- `scripts/marketplace_pack_pack.py` (~150 LoC) — packs a
  source directory into a `.tars-pack` zip with computed
  `claimed_hashes` and signed `pack.sig`. Reads signing key
  from `~/.tars/marketplace/publisher_key` (created via:
  `python -m backend.core.marketplace.pack_signing --gen-key`).
- `scripts/marketplace_pack_publish.py` (~120 LoC) — uploads
  the zip to a configured S3-style endpoint (operator's choice,
  defaults to `meeet.world/packs/`) and updates
  `index.json`.
- `docs/MARKETPLACE_PUBLISHING.md` (~40 LoC) — author-facing
  guide ("how to write a TARS pack and publish it").

CLI smoke test should produce a 1.2 KB pack from a sample
3-file directory in <2 s on a Mac M-series.

---

## 5. Test plan summary

| Test type | Files | Count | Pass gate |
| --------- | ----- | ----- | --------- |
| Backend unit | `test_marketplace_pack_*.py` (4 files) | ~28 | 28/28 green |
| HTTP integration | `test_marketplace_pack_routes.py` | ~8 | 8/8 green |
| Cockpit unit | `marketplace-client.spec.ts` | ~12 | 12/12 green |
| Playwright e2e | `tests/e2e/marketplace/*.spec.ts` (3 files) | ~14 | 14/14 green |
| A11y | `marketplace-a11y.spec.ts` | 1 | 0 violations |
| Existing Wave 106 | unchanged | 16 | 16/16 green |

**Smoke test:** publisher generates a 3-file pack with
`marketplace_pack_pack.py` → uploads via
`marketplace_pack_publish.py` to a local `meeet.world` mock →
operator opens cockpit MarketplaceSheet → sees the pack in
Catalog → clicks Preview → preflight shows no violations →
clicks Install → policy queue gets entry → operator approves →
pack installs → action `pack.<slug>.snapshot` is callable. Total
time end-to-end <30 s.

---

## 6. Coupling notes

| Other brief / system | Hard / Soft | Reason |
| -------------------- | ----------- | ------ |
| **PH5 vault (#202)** | Hard | Publisher signing key (`~/.tars/marketplace/publisher_key`) MUST live behind the vault. Brief assumes vault is unlocked at publish time; CLI raises `VaultLockedError` if locked. |
| **PH5 policy UI (#203)** | Hard | Every `install`/`uninstall`/`update` enqueues a `marketplace.pack.*` policy confirmation (category `marketplace`). Cockpit pre-approves only when the pack is `unsigned=false` AND `destructive_actions=[]` AND under a configurable threshold. |
| **PH5 telemetry (#204)** | Soft | New bucket families `pack.install.{ok,failed,rejected}`, `pack.preflight.{ok,violation}`. Falls under `pack.*` family already in §3.2 schema; extend the allow-list. |
| **PH6 L3 sandbox (#205)** | Soft (forward) | Installed pack actions that include `runtime.run_code` go through the L3 sandbox. Already covered by #205's policy hook. |
| **PH7 planner (#206)** | Soft (forward) | New-plan composer should refresh its "available actions" hint when `pack.installed` fires. Out of scope here (deferred to a small follow-up in #206 sequel). |
| **meeet.world `/packs/` endpoint** | Hard (cross-stack) | Brother stack publishes `index.json` + `<slug>/<ver>.tars-pack` over HTTPS. Contract version `1.0` (same as `CONTRACT_VERSION` in `backend/core/marketplace/__init__.py`). Coordination ticket lives in brother handoff brief (#198) as new §extension item. |
| **Wave 106 v0 routes** | Soft | v0 routes (`GET /api/marketplace/listings/*`) stay live for in-repo playbook bundles. v1 routes are additive at `/packs/*` path. No URL clashes. |

---

## 7. Operator-side checklist (v11 GA)

Add to `docs/V11_GA_CHECKLIST.md`:

- [ ] **D1.** Operator can install at least one pack from a live
      `meeet.world/packs/index.json` end-to-end (publish → browse →
      install → invoke action).
- [ ] **D2.** Pack with corrupted `pack.sig` is rejected with the
      `signature_invalid` error before any file is written to
      `~/.tars/packs/`.
- [ ] **D3.** Pack with `os.system` in `pack.py` is rejected by
      preflight; cockpit shows the violation line + suggested fix.
- [ ] **D4.** Uninstall reclaims the disk and registry entry; the
      action becomes uncallable within 5 s.
- [ ] **D5.** Update preserves the existing `installed.sqlite` row
      (rating + audit log).
- [ ] **D6.** Existing v0 listing browser still works (regression
      check).
- [ ] **D7.** Telemetry counters increment for each pack lifecycle
      event when `telemetry_enabled=true`.

---

## 8. Open questions for operator (resolve before merge)

1. **Publisher key storage:** brief assumes vault-stored. Should
   there be a fallback "use a file path env var" for CI publishers
   (recommend yes, with a documented "less safe" warning)?
2. **Auto-update policy:** opt-in cohort default? Recommend default
   OFF (operator chooses per-pack); v11.1 could add "auto-update if
   no destructive actions" as a config preset.
3. **Pack registry mirror:** support a single configurable mirror
   URL (env `TARS_MARKETPLACE_REGISTRY_URL`) for self-hosted
   distributions? Recommend yes, low cost.
4. **Pack revocation:** how does an author revoke a malicious
   published pack? Recommend `meeet.world/packs/revocations.json`
   pulled hourly; this brief defers the cockpit "revoked" badge
   to v11.1.
5. **Dependency packs:** `required_packs` is in the manifest but
   the installer in step 4 doesn't auto-install dependencies.
   Recommend explicit operator approval for each dependency,
   chained installs in a single policy confirmation. v11 ships
   "warn and reject if missing", v11.1 ships chained installs.
6. **Pack data residency labels:** `manifest.data_residency`
   values? Recommend `{"local-only", "phones-home"}` for v11;
   v11.1 could add per-region labels.
7. **Marketplace search:** client-side full-text only for v11.
   Server-side search via `meeet.world/packs/search?q=` if
   discovery becomes a bottleneck.

---

## 9. Effort estimate

| Step | LoC | Hours |
| ---- | --- | ----- |
| 1. Pack types + manifest validator | 220 | 4 |
| 2. Pack signing + verification | 280 | 5 |
| 3. Preflight static analyzer | 390 | 7 |
| 4. Pack installer | 610 | 11 |
| 5. Remote registry client | 330 | 5 |
| 6. HTTP surface extensions | 280 | 5 |
| 7. Cockpit MarketplaceSheet | 1200 | 22 |
| 8. Publisher SDK CLI + docs | 310 | 6 |
| **Total** | **3620** | **65 hrs (~3 weeks)** |

8 small PRs are recommended (one per step). Steps 1-2-3 form a
"foundation" sub-stack that must land before 4-5-6; step 7 and 8
can land in any order after the HTTP routes (step 6) are live.

---

## 10. Out of scope (explicit non-goals)

- **Payments / payouts.** v11 ships marketplace as a free
  distribution channel. `price` field is in the manifest for
  forward-compat but the installer ignores it.
- **Multi-author packs / co-signing.** Single-author ed25519 sig
  for v11.
- **Binary native packs.** v11 is Python-only packs. Compiled
  language packs are out of scope (would need a separate sandbox
  policy in #205's L3 brief).
- **Pack analytics dashboard for authors.** Author-side dashboard
  ("how many installs?") is a `meeet.world` UI concern; this brief
  is TARS-side only.
- **Pack hot-reload without restart.** v11 reloads the domain
  registry but does not hot-swap running plan steps; operator
  must restart any in-flight playbook that depends on the
  updated pack.
- **Public listing moderation.** `meeet.world` brother stack
  owns curation/moderation policy; out of scope here.

---

## 11. Glossary

| Term | Meaning |
| ---- | ------- |
| Pack | A signed `.tars-pack/` zip with `manifest.json` + `pack.py` + signed by an ed25519 key tied to an author's meeet.world identity. |
| Listing | A registry entry (v0 marketplace term; v1 packs map to listings with `kind="pack"`). |
| Preflight | Static-analysis pass over a pack's `.py` files; reject if `os.system`/`eval`/restricted imports appear. Best-effort, not a security boundary. |
| Signing key | Author's ed25519 private key, stored at `~/.tars/marketplace/publisher_key` (vault-protected). |
| Pubkey fingerprint | First 8 hex chars of the pubkey; shown in cockpit cards for at-a-glance trust. |
| Hard-fail | Reject install outright on mismatch (opposite of v0's "warn-and-proceed"). |
| HIL | Human-In-the-Loop gate (`policy_gate.require_confirm`). |

---

## 12. Acceptance criteria (merge gate)

- [ ] All 28 backend unit tests green.
- [ ] All 8 HTTP integration tests green.
- [ ] All 12 cockpit unit tests green.
- [ ] All 14 Playwright e2e scenarios green on Mac/Win/Linux.
- [ ] Axe a11y scan: 0 violations on MarketplaceSheet.
- [ ] Existing 16 Wave 106 tests untouched & green.
- [ ] Smoke (§5): publish → install → invoke in <30 s.
- [ ] Corrupted-sig pack rejected before any FS write.
- [ ] `os.system` pack rejected by preflight with line-pointed
      error.
- [ ] No new npm deps added.
- [ ] No backwards-incompatible changes to existing Wave 106
      routes.

---

**End of brief.** Next planning briefs queued in the autonomous
orchestration window: PH9 (L10 iOS + Android companion apps),
PH10 (Claude design polish backlog).
