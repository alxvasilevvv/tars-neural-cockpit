# Handoff → Claude Code (design + meeet.world integration)

> **2026-05-05 — Operator brief: «полный доступ» TARS + meeet.world (одна машина).**
>
> **Репозитории (канон):**
> - TARS: `/Users/alien/Documents/Claude/Projects/Jarvis/jarvis` — запускай Claude Code **из корня этого каталога** (читается `CLAUDE.md`).
> - meeet core (Supabase / Lovable): `/Users/alien/Documents/Claude/Projects/meeet-solana-state-941a6045` — по `docs/SYNC.md` правки в GitHub **не пушим с Cursor**; на этой машине можно **редактировать локально** и отдавать дифф оператору / Lovable.
>
> **Секреты (никогда в чат, никогда в git):** корневой **`.env`** в TARS (копия с `.env.example`). Туда же кладутся **`MEEET_INGEST_*`**, **`MEEET_BILLING_*`**, **`TARS_BILLING_SOURCE=remote`**, bridge и т.д. Claude Code видит только то, что **уже есть в окружении процесса** на этой машине (или что оператор вставил через локальные скрипты). **Полный root к prod** = решение оператора (Supabase Dashboard, Lovable, Cloudflare) — в репозиторий это не кодируется.
>
> **Prod-биллинг (базовая линия):** Supabase **`zujrmifaabkletgnpoyw`**, edge **`tars-billing`**:  
> `https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/tars-billing` — см. `docs/contracts/TARS_MEEET_BILLING.md`, `docs/AGENT_HANDOFF.md` (блок remote billing prod baseline).
>
> **Команды для самопроверки (TARS):**
> - `make ops-billing-remote-wizard` — интерактив: ключ, prod-smoke POST, опционально запись в `.env`.
> - `make smoke-billing-tars` — без uvicorn: `fetch_operator_snapshot` с `.env`.
> - `make backend-tars-up` — освободить **:8765**, uvicorn + `.env` в фоне, `curl` **`/api/entitlements`**.
> - `make dev-tars-stack` — то же + **`pnpm dev`** в **`experiments/neural-showcase-v3`** (UI **5174**).
> - Тесты: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_meeet_billing_remote.py tests/test_meeet_billing_usage.py tests/test_entitlements.py -q`
> - Цепочка продукта: `make test-commercial-readiness`
>
> **Доступ к «meeet.world» в смысле кода:** публичные URL и контракты в **`docs/contracts/`**, ingest/billing base в **`.env.example`**. Браузер, аккаунты Lovable/Supabase, **cf-operator.env** — вне репо; оператор логинится сам и при необходимости даёт Claude **read-only** контекст (скрин, эталонный ответ API), без выгрузки секретов.
>
> **Синхронизация агентов:** перед правками в shared-файлах читай **`docs/SYNC.md`**; любая правка **`docs/CHANGELOG_AGENTS.md` / контрактов / AGENT_HANDOFF** — со строкой **`>>> SYNC: Claude · дата · кратко что`**.
>
> **Расширение полномочий на этой машине:** по запросу оператора Claude может трогать и backend (`backend/`, `web_extras/`, `tests/`, `scripts/`), но тогда **согласуй с Cursor lane** или оставь один понятный PR/коммит и запись в CHANGELOG, чтобы не перетирать параллельную работу.

> **2026-04-30 — Sync note from Cursor (post Wave 46):**
> Current repo health check is green:
> - backend: `PYTHONPATH=. .venv/bin/python -m pytest -q` → **674 passed**
> - showcase: `npx tsc --noEmit -p tsconfig.app.json`, `npm run test`
>   (56/56), `npm run build` all pass
>
> Local dev had transient Vite overlays caused by missing/broken
> `node_modules` after dependency churn. Resolved by reinstalling deps
> and pinning test-runtime versions in
> `experiments/neural-showcase-v3/package.json`:
> - `vitest@2.1.9`
> - `jsdom@25`
> plus required runtime deps present (`tailwindcss`,
> `@tailwindcss/vite`, `@tsparticles/react`, `@splinetool/react-spline`).
>
> **2026-04-29 — Console-warning sweep landed.**
> After the shader-lines swap, Cursor walked the live console on
> `127.0.0.1:5174/` and cleared the bulk of the dev-time noise. Net
> delta — 30+ runtime warnings → 4 (3 accepted as 3rd-party, 1
> cosmetic dev-only). Touched files:
> - `src/main.tsx` — React Router v7 future flags opted in.
> - `src/components/ScrollStory.tsx` — `useScroll` lifted to
>   `PinnedTrack`, `MotionValue<number>` threaded down to children.
>   8 redundant scroll listeners gone.
> - `src/components/Layers.tsx`, `src/components/Steps.tsx` —
>   `layoutEffect: false` on `useScroll`.
> - `src/components/CockpitLive.tsx` — iframe `sandbox` dropped
>   (same-origin), replaced with `referrerPolicy`.
> - `src/components/Hero.tsx` — demo cycle pauses on hover/focus,
>   honors reduced-motion, container is `aria-hidden`.
> - `vite.config.ts` — `dedupe = ["three", "react", "react-dom"]`
>   + `optimizeDeps.include = ["three"]` + `chunkSizeWarningLimit:
>   2200`.
>
> **Accepted ecosystem warnings** (do not chase):
> 1. `THREE.WARNING: Multiple instances of Three.js being imported.`
>    — `@splinetool/react-spline` ships its own bundled three. Their
>    issue, not ours. Spline still works.
> 2. `[@splinetool] updating from 114 to 122` — internal Spline
>    runtime drift.
> 3. `Each child in a list should have a unique "key" prop. Check
>    the render method of TrustStrip` — fires only on framer-motion
>    HMR, not on cold load and not in production. Verified with
>    `npm run build`.
> 4. One framer-motion `non-static position` warning on cold load
>    (down from many). Cosmetic.
>
> **Pre-existing brand asks still open** (priority order):
> 1. Tune the shader veil intensity in `src/components/Hero.tsx`
>    (radial gradient over the shader). First cut is
>    `rgba(7,7,10,0.78) → 0` over a 70%×55% ellipse at 50%/42%; if
>    brand wants more shader bleed-through, drop centre stop to
>    0.62 and shrink ellipse to 60%×46%. Keep the bottom fade.
> 2. Shader colour grading. The fragment shader's last line has the
>    RGB-channel swizzle — surgery point if brand wants
>    monochrome/single-accent. Don't touch the marching-line math.
> 3. DownloadStrip card chrome (glassy gold-rim treatment).
> 4. Eyebrow micro-motion (one stanza per turn, council heartbeat).
> 5. Three-beat headline kerning + size hierarchy (line1 100% →
>    line2 96% → line3 92%).

> **2026-04-29 — Hero swap: orb → shader-lines (21st.dev port).**
> Operator vetoed the orbital-reactor scene and pointed at
> `21st.dev/community/components/aliimam/shader-lines/default`.
> Cursor just shipped:
> - **Shader-lines is the new background.** Source pulled from the
>   21st.dev registry CDN, ported into
>   `src/components/ui/shader-lines.tsx` against the local
>   `three@0.184.0` instead of injecting a `<script>` tag at runtime
>   (no third-party network call on first paint, no CSP exception,
>   reproducible bundle hash for signed releases). Fragment shader is
>   preserved verbatim — visual character matches the 21st.dev preview
>   exactly.
> - **Hero veiling.** Background layer adds a centred radial gradient
>   to dim the bright centre under the headline + a 40-tall bottom
>   gradient handing off to `--color-bg-0`. This is what makes the
>   shader read as "background sculpture" rather than "competing for
>   the focal point" (Master §6).
> - **`src/three/HeroScene.tsx` deleted** — the orb + orbital rings
>   the operator called "ужасный элемент" are gone. Don't bring them
>   back.
> - Sovereignty headline, top-of-fold DownloadStrip card, and live-demo
>   prompt cycle all stay (see entry below for those).
> - `prefers-reduced-motion` honored: the shader's `time` uniform
>   freezes but the canvas still renders one calm frame so the
>   background isn't blank.
>
> **What Claude can pick up next** (priority order):
> 1. **Tune the shader veil intensity.** The radial gradient
>    (`rgba(7,7,10,0.78) → 0` over 70%×55% ellipse at 50%/42%) is a
>    first cut. If the brand pass wants more shader bleeding through,
>    drop the centre stop to 0.62 and shrink the ellipse to 60%×46%.
>    File: `src/components/Hero.tsx`, the absolute z-0 background div.
>    Keep the bottom-fade — without it the shader looks like a
>    severed section.
> 2. **Shader colour grading.** Right now the shader fragment outputs
>    raw RGB-channel-offset rays. If brand wants it monochrome
>    (gold-only or cyan-only), the fragment shader has the colour
>    channel swizzle on the last line; that's the surgery point.
>    Don't touch the marching-line math above it — that's what the
>    operator picked.
> 3. **DownloadStrip card chrome.** The hero variant sits inside a
>    `border bg-bg-1/50 backdrop-blur-sm` wrapper — works but is
>    plain. Polish target: a glassy gold-rim treatment that signals
>    "primary action" without screaming.
> 4. **Eyebrow micro-motion.** Currently a static pulsing dot. Could
>    breathe with the council heartbeat (one stanza per turn).
> 5. **Three-beat headline kerning + size hierarchy.** First two
>    lines are white, third line is gold. Consider a slight
>    descending size ladder (line1 100% → line2 96% → line3 92%) so
>    the gold line lands as a "punchline" weight.
>
> **Untouched lanes** — `/cockpit` chrome, `<CommandPalette />`,
> `<ThreadTimeline />`, pairing/recovery UX (items 3.2–3.5 below)
> are still the same brief — Cursor didn't touch any of those this
> turn.

> **As of 2026-04-29 — Phase M sweep.** Cursor agent finished:
> Phase **L9 + L5** functional ladder; **M1** multi-agent registry;
> **M2** user-owned wallets (Solana, EVM, TON with real signing);
> **O1–O4** production hardening; **P1–P4** chain-specific send forms
> + live RPC helpers; **Q1** end-to-end smoke; **D1/D4** README +
> threat model; mobile companion read-only wallet surface (iOS
> SwiftUI + Android Compose); cinematic mnemonic-reveal; **plus the
> full Phase-M backbone**: **P5** entitlements (Tier × LIMITS ×
> can_run + 5 endpoints), **P6** entrepreneur pack canonical rename
> (legacy `mlm` slug stays as a deprecated alias until 2026-07-29),
> **P7** roles registry (6 built-ins + custom-role overlay synthesis
> + 6 endpoints + orchestrator overlay hook), **P8** vision agent
> (image extractor + multimodal routing + `supports_multimodal` flag
> on Anthropic + OpenAI voices + OCR fallback). Recovery router now
> flows through the same HMAC policy gate as wallet ops; mobile
> Activity / iOS shell wiring shipped; `tauri.conf.json` public-key
> patcher landed in `generate-release-keys.sh`. This document is the
> brief Claude needs to drive the remaining brand pass and the
> marketing-site integration.

You own:

1. Brand pass on the new functional surfaces shipped this batch.
2. Landing page integration (`experiments/neural-showcase-v3/`) using the
   typed manifest client already in `src/lib/downloads.ts`.
3. **meeet.world** SSR shell — render the same download CTAs from
   `GET /api/product/downloads`, deep-link `meeet.world/tars` ↔ cockpit.
4. Pairing + recovery UX sketches (Cursor will wire the React components
   once you've approved the layout).

You **do not** own:

- Backend / API contracts. They are pinned in `docs/contracts/`.
- Crypto. The envelope, recovery seed, and pairing flow are shipped.
- Any change that bumps a contract version. Coordinate via PR.

---

## 1. What's already live (functional)

| Surface | Endpoint / file | Status |
|---|---|---|
| Public download manifest | `GET /api/product/downloads`, `…/latest`, `…/version` | ✅ shipped |
| Release publishing CLI | `python -m backend.core.product.publish …` | ✅ shipped |
| Cockpit download CTAs | `<DownloadStrip />` in `<Hero />` | ✅ shipped (visual: plain) |
| Pairing endpoints (real X25519) | `POST/GET /api/pairing/*` | ✅ shipped |
| Recovery seed (BIP-39 24 words) | `POST/GET /api/recovery/*` | ✅ shipped |
| Encrypted sync envelope | `backend/core/crypto/envelope.py` | ✅ shipped (1.1.0) |
| meeet contract bump | 1.0.0 → 1.1.0 (additive) | ✅ shipped |
| Tauri 2 desktop shell | `desktop/` | 🟡 scaffold (sidecar pyoxidizer pending) |
| Updater channel publisher | `python -m backend.core.product.publish --updater-out …` | ✅ shipped (real signing in CI) |
| Persistent host keyring | `backend/core/vault/file_vault.py` | ✅ shipped (XChaCha20-Poly1305 at rest, 0o600 perms) |
| Host identity status API | `GET /api/pairing/identity` | ✅ shipped |
| Cockpit pairing/recovery clients | `src/lib/{pairing,recovery}.ts` | ✅ shipped (typed wrappers + helpers; React components yet to land) |
| iOS / Android stubs | `mobile/{ios,android}/TARSCompanion/` | 🟡 paths-only |
| ⌘K command palette | `<CommandPalette />` | ✅ shipped (visual: plain) |
| Per-thread timeline | `<ThreadTimeline />` | ✅ shipped (visual: plain) |
| Multi-agent panel | `<AgentsPanel />` (M1) | ✅ shipped (visual: plain) |
| Wallet panel + chain send forms | `<WalletPanel />`, `<ChainSendForm />` (M2 + P1) | ✅ shipped (visual: plain) |
| Cinematic mnemonic reveal | `<MnemonicReveal />` (O5) | ✅ shipped (3D card flip + stagger) |
| Mobile companion wallet | iOS `WalletView`, Android `WalletScreen` | ✅ shipped (read-only + prove) |
| Structured error envelope | every `/api/*` route | ✅ shipped (O1) |
| HTTP policy gate | confirm-token over destructive ops | ✅ shipped (O2) |
| SLIP-0010 Phantom Solana derive | `bip44-501-phantom` scheme | ✅ shipped (O3) |
| Opt-in audit log of raw signed bytes | `TARS_AUDIT_RAW_TX` env | ✅ shipped (O4) |
| Live RPC helpers | `/api/wallet/{solana/blockhash,evm/{addr}/nonce,ton/{addr}/seqno}` | ✅ shipped (P2/3/4) |
| Release-key generator | `desktop/scripts/generate-release-keys.sh` (`--patch-tauri-conf`) | ✅ shipped (helper) |
| Entitlements (Tier × LIMITS) | `GET /api/entitlements`, `POST /upgrade`, `POST /byo`, `POST /can_run`, `GET /tiers` | ✅ shipped (P5) |
| Roles (overlay-synthesised) | `GET /api/roles`, `POST /{slug}/activate`, `POST /api/roles`, `DELETE /{slug}`, `GET /{slug}/overlay` | ✅ shipped (P7) |
| Vision agent (OCR + multimodal) | `backend/agents/vision_agent.py` + `supports_multimodal` flag on chat voices | ✅ shipped (P8) |
| Entrepreneur pack | canonical replacement for `mlm`; legacy slug deprecated | ✅ shipped (P6) |
| Recovery policy gate | `POST /api/recovery/{generate,verify,confirm}` HMAC-bound | ✅ shipped (cleanup) |
| Mobile activity wiring | Android `WalletActivity` + iOS `TARSCompanionRoot` shell | ✅ shipped (cleanup) |

Test totals: **671 pytest + 56 vitest + 18 swift** passing; tsc
`--noEmit` clean. (Android JUnit fixtures landed but require an
Android SDK on CI — same pattern as the existing pairing tests.)

---

## 2. Live API outputs (captured 2026-04-29)

These are exact responses from the running app. Use them as the contract
source for any frontend / SSR code; the curl equivalents are listed in
`docs/contracts/MEEET_DOWNLOADS.md`.

### `GET /api/product/downloads`

```json
{
  "ok": true,
  "product": "tars",
  "contract_version": "1.0.0",
  "channel": "stable",
  "released_at": "2026-04-29T00:00:00Z",
  "source": "defaults",
  "releases": [
    {
      "version": "0.1.0-alpha.2",
      "channel": "stable",
      "released_at": "2026-04-29T00:00:00Z",
      "notes": "Phase M backbone — wallets, council agents, … (see DEFAULT_NOTES in manifest.py).",
      "artifacts": [
        { "os": "macos",   "arch": "arm64", "kind": "dmg",
          "filename": "TARS-0.1.0-alpha.2-arm64.dmg",
          "url": "https://meeet.world/downloads/tars/0.1.0-alpha.2/TARS-0.1.0-alpha.2-arm64.dmg",
          "size_bytes": null, "sha256": null, "signature_url": null },
        { "os": "macos",   "arch": "x64",   "kind": "dmg",
          "filename": "TARS-0.1.0-alpha.2-x64.dmg",
          "url": "https://meeet.world/downloads/tars/0.1.0-alpha.2/TARS-0.1.0-alpha.2-x64.dmg",
          "size_bytes": null, "sha256": null, "signature_url": null },
        { "os": "windows", "arch": "x64",   "kind": "exe",
          "filename": "TARS-0.1.0-alpha.2-Setup.exe",
          "url": "https://meeet.world/downloads/tars/0.1.0-alpha.2/TARS-0.1.0-alpha.2-Setup.exe",
          "size_bytes": null, "sha256": null, "signature_url": null },
        { "os": "linux",   "arch": "x64",   "kind": "appimage",
          "filename": "TARS-0.1.0-alpha.2-x64.AppImage",
          "url": "https://meeet.world/downloads/tars/0.1.0-alpha.2/TARS-0.1.0-alpha.2-x64.AppImage",
          "size_bytes": null, "sha256": null, "signature_url": null }
      ]
    }
  ]
}
```

Headers: `X-Tars-Contract: 1.0.0`, `Cache-Control: public, max-age=60`.

### `POST /api/pairing/begin`

```json
{
  "ok": true,
  "trace_id": "trc_…",
  "pair_id": "5e40c57470f534bc",
  "accept_token": "9f20ef353462ea44f896c2af7ecb9169",
  "host_id": "9ebd45c6de53f838",
  "host_fingerprint": "D3BA-6D8A-D882",
  "host_public_key": "4iIXBeR6gsAbVLjgFm78boubCXI0dPQRlbaiojEO8hQ=",
  "expires_at": 1777414621.785266
}
```

Render the **`host_fingerprint`** as a 3-group dash string visible on
both sides; the operator confirms it matches before accept. The
**`host_public_key`** is base64 X25519 (32 bytes) — pin it on first
contact.

### `POST /api/recovery/generate`

```json
{
  "ok": true,
  "trace_id": "trc_…",
  "mnemonic": "<24 BIP-39 words — DO NOT log, copy, or screenshot in production>",
  "fingerprint": "B00DAEBD10BD",
  "word_count": 24
}
```

Audit event ``recovery.shown`` is emitted to the meeet store carrying
**only the fingerprint**. Words must never leave the operator's eyes
(see § 5).

---

## 3. Brand pass — concrete tasks

Priority order. Each item references an existing component in
`experiments/neural-showcase-v3/src/components/`.

### 3.1 `<DownloadStrip />` — Phase L9 hero CTA

File: `src/components/DownloadStrip.tsx`.

What's already there:
- UA-detected primary button labelled "Download for macOS / Windows / …".
- "all installers" pill row beneath.
- Version pill.
- `data-sha256`, `data-size-bytes`, `data-filename` already exposed for
  a future verify-on-download UI.

Wanted polish:
- OS-glyph icons (Apple, Windows, Tux, iOS, Android) with micro-motion on
  hover. Use `lucide-react` if possible to avoid new deps.
- Pulse the version pill when a fresh release lands (the manifest carries
  `released_at`).
- "verified · sha256 ✓" affordance once a checksum is present on the
  matched artifact (ignore when `sha256` is `null`).
- Mobile-friendly stacked layout — current grid wraps but feels desktop-first.
- ~~Drop a second `<DownloadStrip variant="footer" />` instance into the
  page footer for landing-page conversion (the variant prop is already in
  the API).~~ ✅ shipped — `<Footer />` mounts the footer variant.

### 3.2 ⌘K `<CommandPalette />` (Phase L8 polish — still open)

`src/components/CommandPalette.tsx`. Plain markup right now. Wanted:

- Render `<mark>` highlight tags as gold-on-bg pulses.
- Add an empty state with "recent threads" / "frequent files".
- Per-kind icons (file / chat-bubble / trace).
- Blur-slide open animation.

### 3.3 `<ThreadTimeline />` (Phase L8 polish — still open)

`src/components/ThreadTimeline.tsx`. Wanted:

- Vertical timeline-spine glyph rail.
- Group entries by hour.
- Soft fade on auto-refresh insert.

### 3.4 Pairing flow (new — Phase L5)

The endpoints **and** typed client are now live. Design the React
surfaces against `src/lib/pairing.ts`:

```ts
import {
  beginPairing, acceptPairing, pollPairingStatus, listDevices,
  revokeDevice, getIdentity, encodeQrPayload, formatFingerprint,
  fingerprintsMatch,
} from "@/lib/pairing";
```

- **Host side** — modal with `host_fingerprint` rendered in a tactile
  hero font (use `formatFingerprint(...)`), a QR code from
  `encodeQrPayload(begin)` (it's already a base64url string ready for
  any QR lib), and an "approve" button that surfaces only after the
  client scans (poll via `pollPairingStatus(pair_id)` until
  `state === "accepted"`).
- **Mobile side** (sketches only — Cursor will wire SwiftUI / Compose):
  camera permission → scan → shows the same fingerprint string the host
  is showing → operator taps "Pair" if they match
  (`fingerprintsMatch(...)`).

Style: same gold accent + OLED cyan as MASTER. Pulse the fingerprint
gently to hint that it's verifiable.

### 3.5 Recovery seed (new — Phase L5 G1)

The endpoints **and** typed client are live. Design against
`src/lib/recovery.ts`:

```ts
import {
  generateSeed, verifySeed, getWordlistInfo,
  chunkMnemonic, mnemonicsMatch, isCompleteAttempt, normaliseMnemonic,
  WORD_COUNT,
} from "@/lib/recovery";
```

- **Step 1 — show.** Full-bleed dark sheet listing 24 words in a 4×6
  grid (`chunkMnemonic(res.mnemonic)`), monospace. A "Copy to
  clipboard" button is intentionally *omitted* (operator must
  hand-write). The "Continue" button is locked until the operator
  ticks "I have written this down".
- **Step 2 — verify.** Show a fresh empty 4×6 grid; operator types
  the full phrase. Use `isCompleteAttempt(typed)` to enable the
  "Verify" button, `mnemonicsMatch(typed, original)` for an instant
  client-side hint, then POST via `verifySeed({ mnemonic: typed })`
  and reject mismatches based on the returned `fingerprint`.
- **Audit lozenge** in cockpit settings: "Last seen on 2026-04-29 ·
  fingerprint B00DAEBD10BD" (read from `meeet` store via
  `/api/chat/threads/{id}/timeline`-style pull, but filtered to
  `recovery.shown` events).
- **First-launch gating.** Hit `getIdentity()` from `lib/pairing` —
  when `vault.freshly_minted === true` and `recovery_fingerprint` is
  null, render the recovery flow before anything else.

---

## 4. meeet.world integration

The marketing site at `meeet.world` should consume **the same** download
manifest the cockpit consumes.

### Server-side fetch (Next.js / SvelteKit / etc.)

```ts
const r = await fetch("https://app.meeet.world/api/product/downloads", {
  next: { revalidate: 60 },
});
if (!r.ok) throw new Error("download manifest unavailable");
const manifest = await r.json();
const latest = manifest.releases[0];
const macos = latest.artifacts.find(a => a.os === "macos" && a.arch === "arm64");
```

### Deep links

- `meeet.world/tars` → marketing landing for TARS (this is the page where
  the download CTAs live).
- `meeet.world/tars/install` → 302 to the manifest's primary `url` for
  the visiting OS (server-detected; fall back to the manifest page).
- `meeet.world/updates/<channel>.json` → the per-channel update manifest
  consumed by `tauri-plugin-updater` (separate file from
  `/api/product/downloads`; format: see Tauri docs). Cursor will publish
  it as part of the L9 sidecar slice.

### OG / social

- OG image: live preview of the cockpit hero (the AI-Driven Dynamic
  Landing pattern is already shipped at `<Hero />`).
- OG title: "TARS — local-first neural cockpit".
- OG description: "Threads, voice, automations, files. macOS + Windows
  desktop. iOS + Android companions. Released under meeet.world."

### Contract pinning

`docs/contracts/MEEET_DOWNLOADS.md` is canonical. **Reject any manifest
whose major** of `contract_version` doesn't match the major you compiled
against.

---

## 5. Sensitive data — handling rules

- **Recovery mnemonic** must never be logged, persisted to a remote
  store, copied to clipboard automatically, or screenshotted. The
  meeet store only ever sees the 12-char fingerprint.
- **`accept_token`** in `/api/pairing/begin` responses must not appear
  in URL query strings (cookie / body only). Treat it like a CSRF
  token.
- **`host_public_key`** is *not* sensitive (it's a public key) but it
  *is* the pin operators rely on to detect MITM; render it
  prominently and call out copy-to-pin verification flows.
- **Chat ciphertext** in 1.1.0 events is opaque — never try to render
  the contents from `meeet.world` SSR; only the paired device can
  open it.

---

## 6. What Cursor is doing next

Backlog snapshot (see `docs/AGENT_HANDOFF.md` for the live list):

| Block | Status |
|---|---|
| A1 — pyoxidizer sidecar pipeline | ✅ shipped (sidecar.rs + pyoxidizer.bzl + lifecycle events) |
| Persistent host keyring (Keychain / DPAPI) | ✅ shipped (file vault + Keychain bridge) |
| Real Tauri-plugin-updater channel JSON publisher | ✅ shipped (release-desktop.yml signs with minisign) |
| iOS L10 (SwiftUI pairing) | ✅ shipped (`mobile/ios/TARSCompanion`, 18 swift tests incl. wallet decoder fixtures) |
| Android L10 (Compose pairing) | ✅ shipped (`mobile/android/TARSCompanion`, JVM unit tests, parity wallet decoders) |
| Mobile wallet surface | ✅ shipped (read-only + prove-ownership; SwiftUI WalletView, Compose WalletScreen) |
| **M1 — multi-agent registry + task queue** | ✅ shipped |
| **M2 — user-owned crypto wallets** | ✅ shipped (Solana, EVM, TON real signing) |
| **O1 — structured error envelope** | ✅ shipped |
| **O2 — HTTP policy gate (HMAC confirm tokens)** | ✅ shipped |
| **O3 — SLIP-0010 Phantom-compatible Solana derive** | ✅ shipped |
| **O4 — opt-in raw-tx audit log + retention** | ✅ shipped |
| **P1–P4 — chain send forms + live RPC helpers** | ✅ shipped |
| **Q1 — end-to-end smoke** | ✅ shipped |
| **D1/D4 — root README + threat model** | ✅ shipped |
| Release-key bootstrap helper | ✅ shipped (`desktop/scripts/generate-release-keys.sh`) |
| Real release artefacts (signed installers) | 🔴 blocked on human credentials (Apple/Authenticode/Minisign passphrase) |
| Multi-host federation | parked (out of scope for v1) |

### 6.1 New surfaces this session — claim a brand pass when ready

#### Multi-agent surface (`#ops`)

- HTTP: `POST/GET/PATCH /api/agents`, `POST /api/agents/{id}/tasks`,
  `POST /api/tasks/{id}/run`, `POST /api/tasks/{id}/cancel`.
- Cockpit component: `src/components/AgentsPanel.tsx` — minted under
  `#ops` (top of cockpit, two-column with `WalletPanel`).
- Lib client: `src/lib/agents.ts` (typed CRUD + `useAgents`).
- The orchestrator that runs tasks is the existing council, so each
  task lands as a `Deliberation` shape (mode/chosen/agreement/voices).
- Visual TODO for Claude: header chip badges per task status are
  semantic (`statusBadgeClass`), but the empty / running states could
  use a small motion treatment (skeleton row, council voices reveal).

#### Crypto wallets (`#wallets`)

- HTTP: `POST/GET/DELETE /api/wallet`, `POST /api/wallet/import`,
  `POST /api/wallet/{id}/sign`, `POST /api/wallet/{id}/build_send`.
- Cockpit component: `src/components/WalletPanel.tsx` — handles the
  one-time mnemonic reveal screen with the same red-amber language
  as `RecoverySetup`.
- Lib client: `src/lib/wallet.ts`.
- Agent-controllable: the `wallet` domain pack (`backend/core/domains/
  packs/wallet/`) exposes `wallet.list`, `wallet.address`,
  `wallet.propose_send`, `wallet.sign_message`. `propose_send` and
  `sign_message` are flagged `destructive=True`, so the policy gate
  intercepts them on every invocation.
- ✅ Cinematic mnemonic-reveal landed in `<MnemonicReveal />`
  (`src/components/MnemonicReveal.tsx`): face-down card grid, "reveal
  phrase" gating CTA, 60ms-stagger 3D flip per card, gold/amber
  brand accent, "show again / hide" once revealed, "I wrote it down"
  affirmation. Pure CSS transforms — no third-party motion deps.
  Helper unit tests cover the parsing + grid layout heuristics
  (vitest 6/6 green).
- Open visual TODO for Claude: motion polish across the rest of
  WalletPanel — running balance fetch could pulse, chain badges
  could share the same reveal stagger, send-form field focus could
  echo the same gold cue.

### 6.2 Coordination contract with Cursor

If you (Claude) are working in parallel, please respect these lanes:

- Cursor edits the **functional layer** (Python backend, Rust
  desktop, Swift/Kotlin mobile, Python contract tests, lib clients in
  TypeScript).
- Claude edits the **brand layer** (typography, motion, hero
  treatments, copy, illustration, marketing-site SSR).
- Anything that crosses lanes (a new HTTP contract, new schema
  field, a new event kind) is sealed behind a contract test before
  rolling forward — the test pins the shape Claude is rendering and
  vice versa.
- Both agents update `docs/CHANGELOG_AGENTS.md` per edit and append
  a sentence to `docs/AGENT_HANDOFF.md` "Next Cursor block" so the
  next pickup sees the dependencies.

When you're ready for review, drop a PR description that follows the
existing changelog style and reference this file from the body.

---

## 7. Quick start (for Claude's local dev)

```bash
# Backend
cd /Users/alien/Documents/Claude/Projects/Jarvis/jarvis
python -m uvicorn web_extras.app:app --host 127.0.0.1 --port 8765

# Cockpit
cd experiments/neural-showcase-v3
pnpm install   # or `npm install`
pnpm dev       # http://127.0.0.1:5174

# Tests
make test-all  # runs pytest + vitest
```

Endpoints to exercise during the brand pass:

- `curl -s http://127.0.0.1:8765/api/product/downloads | jq`
- `curl -s http://127.0.0.1:8765/api/product/version | jq`
- `curl -s http://127.0.0.1:8765/api/recovery/wordlist/info | jq`
- `curl -s http://127.0.0.1:8765/api/pairing/devices | jq`
- `curl -s http://127.0.0.1:8765/api/pairing/identity | jq`  ← *new in K1*

Manifest authoring (when uploading a real release):

```bash
python -m backend.core.product.publish ./build/release \
  --version 0.1.0 \
  --channel stable \
  --notes "First public alpha." \
  --copy-to ./dist/releases/0.1.0/ \
  --updater-out ./dist/updates/ \
  --updater-alias latest
```

Add `--updater-out` to also emit the per-target Tauri updater
JSON files at `<dir>/<target>/<version>.json` (and
`<dir>/<target>/latest.json` when `--updater-alias latest` is given).
