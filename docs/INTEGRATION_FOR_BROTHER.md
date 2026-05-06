# TARS ↔ meeet.world — полный интеграционный документ

**Адресат:** брат (meeet.world / Lovable infra owner)
**Источник:** Claude / TARS Cowork window
**Дата:** 2026-05-05
**Версия:** 1.0 (live as of HEAD = `299c5b5`, 5 коммитов pending push)
**Цель:** один документ, после которого ты понимаешь весь интеграционный контур и можешь закрыть свою сторону.

---

## Содержание

1. [Что такое TARS и где он трогает meeet.world](#1-что-такое-tars-и-где-он-трогает-meeetworld)
2. [Архитектурная карта (что у кого)](#2-архитектурная-карта-что-у-кого)
3. [Что уже сделано на стороне TARS](#3-что-уже-сделано-на-стороне-tars)
4. [Что нужно от тебя — пошаговый чеклист](#4-что-нужно-от-тебя-пошаговый-чеклист)
5. [Контракты по точкам интеграции](#5-контракты-по-точкам-интеграции)
6. [Секреты и переменные окружения](#6-секреты-и-переменные-окружения)
7. [Smoke-тесты / верификация](#7-smoke-тесты--верификация)
8. [Финальный launch checklist](#8-финальный-launch-checklist)
9. [Источники истины (read these)](#9-источники-истины-read-these)

---

## 1. Что такое TARS и где он трогает meeet.world

**TARS** — local-first AI-агент, упакован как:
- **Desktop app** (Tauri 2 .dmg / .msi / .AppImage / .deb) — основной user-facing продукт.
- **CLI** — `curl … | sh` инсталлер для разработчиков.
- **Web cockpit** — отдельный сабдомен `tars.meeet.world` (preview/marketing/install funnel).

Бренд — `meeet.world`. Кошелёк — Solana + $MEEET. Биллинг — авторитативный на твоей стороне (meeet.world Supabase). Инсталлер — на GitHub Releases.

**Точки интеграции, которые трогают тебя:**

| # | Точка | Кто owns | Статус |
|---|-------|----------|--------|
| 1 | Сабдомен `tars.meeet.world` (DNS + routing + SSL) | **ТЫ** (meeet.world infra) | ⏳ Спека готова, не выкатано |
| 2 | Авторитативный billing edge (`tars-billing` Supabase Edge Function) | **ТЫ** (Lovable) | ✅ В проде на `zujrmifaabkletgnpoyw` |
| 3 | Core-bridge для cross-project relay (`core-bridge` Edge Function) | **ТЫ** (Lovable) | ✅ В проде |
| 4 | Унифицированная телеметрия (`unified_funnel` view) | **ТЫ** (Lovable) | ⏳ Спека готова, view не создан |
| 5 | Downloads manifest proxy на сабдомене | **ТЫ** (meeet-app) | ⏳ Опционально (fallback на GitHub Releases работает) |
| 6 | Auth: shared `meeet_session` cookie на `.meeet.world` | **ТЫ** | ⏳ Зависит от инфры |
| 7 | OAuth bridge для коннекторов (Gmail/Slack/Notion/etc.) | **ТЫ** (meeet-app + Supabase) | ⏳ Контракт есть, ничего не реализовано |
| 8 | Magic-link sign-in флоу (email → `tars://login?token=…`) | **ТЫ** (meeet-app email + auth) | ⏳ |
| 9 | $MEEET billing settlement (SOL on-chain) | **ТЫ** (существующий контракт) | ✅ Уже работает |
| 10 | Code signing (Apple Developer ID + Authenticode) | **Алексей** (operator) | ❌ Нужны деньги/аккаунты |

**Что НЕ трогает тебя:**
- Backend TARS (FastAPI, Python, sidecar) — у нас на отдельном Supabase `hhpaukjobskcwkxbgecl`.
- Tauri shell — desktop binary собирается из нашего репо.
- React cockpit — наш билд, ты только хостишь edge.

---

## 2. Архитектурная карта (что у кого)

```
┌─────────────────────────────────────────────────────────────────┐
│                         meeet.world                              │
│  ┌─────────────────────┐         ┌─────────────────────┐         │
│  │  meeet.world        │         │  app.meeet.world    │         │
│  │  (landing/account)  │  TVOJE  │  (auth/billing UI)  │         │
│  └─────────────────────┘         └─────────────────────┘         │
│         │                                  │                     │
│         │   shared cookie .meeet.world     │                     │
│         ▼                                  ▼                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  tars.meeet.world (TVOJE — нужно поднять)               │    │
│  │  serves: experiments/neural-showcase-v3/dist  (NASE)    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Supabase project: zujrmifaabkletgnpoyw  (TVOJE / Lovable)│  │
│  │  Edge Functions:                                          │   │
│  │    • core-bridge        ✅ live                           │   │
│  │    • tars-billing       ✅ live (Wave 56)                 │   │
│  │    • tars-ingest        ✅ live                           │   │
│  │  Tables:                                                  │   │
│  │    • meeet_events       ⏳ нужно подтвердить shape        │   │
│  │    • tars_billing_usage_dedupe   ✅ есть                  │   │
│  │    • unified_funnel (view)       ⏳ нужно создать         │   │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │  HTTPS, Bearer auth, x-bridge-secret
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                            TARS                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Desktop app (Tauri 2)                                   │    │
│  │    • main.rs — tray + global shortcut + tars://          │    │
│  │    • sidecar (FastAPI on 127.0.0.1:8765)                 │    │
│  │    • cockpit (React, embedded)                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Supabase project: hhpaukjobskcwkxbgecl  (NASE / Cursor) │    │
│  │  Tables:                                                 │    │
│  │    • tars_event_ingest                                   │    │
│  │    • all backend operational tables                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  GitHub Releases (NASE):                                          │
│    https://github.com/alxvasilevvv/tars-neural-cockpit            │
│    Builds: dmg / msi / AppImage / deb + latest.json (updater)     │
└──────────────────────────────────────────────────────────────────┘
```

**Канонические URL'ы:**
- Marketing/install: `https://tars.meeet.world` (нужно поднять)
- API/billing: `https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/{tars-billing,core-bridge,tars-ingest}`
- Downloads: `https://github.com/alxvasilevvv/tars-neural-cockpit/releases/latest/download/`
- Updater: `https://github.com/alxvasilevvv/tars-neural-cockpit/releases/latest/download/latest.json`
- meeet billing redirect: `https://meeet.world/billing/tars?plan=pro` (твоя страница)

---

## 3. Что уже сделано на стороне TARS

✅ **Backend** (FastAPI + tests + 2411 pytest cases passing):
- Авторитативный billing client (`backend/core/meeet_billing/client.py`) с retries + idempotency через `trace_id`.
- Mid-session sidecar crash detection (Wave 61 — Rust watcher + TS heartbeat).
- All 5 P0/P1 a11y fixes на cockpit + onboarding (Wave 53-58).

✅ **Desktop app** (Tauri 2):
- Window state persistence, system tray icon с меню, global shortcut `Cmd+Shift+Space`, deep-link handler `tars://`.
- Pre-flight build gate (`desktop/scripts/preflight-build.sh`).
- Sidecar status indicator в cockpit (Wave 60).
- `/settings` page с About + Updates + Keyboard reference (Wave 62).
- Полная документация в `docs/DESKTOP.md`.

✅ **Cockpit (React)**:
- Pricing / FAQ / Compare страницы.
- Onboarding flow с 6 ролями + custom role.
- Deep-link routing для `tars://onboarding?role=…`, `tars://thread/<id>`, `tars://login`, `tars://settings`.
- Cmd+K command palette с focus trap (WCAG 2.1.2).
- Light theme полная поддержка через design tokens.

✅ **Контракты + миграции** (доки на стороне TARS-репо):
- `docs/contracts/CORE_BRIDGE.md` — wire format relay-event.
- `docs/contracts/TARS_MEEET_BILLING.md` — billing API v1.2.0 с trace_id dedupe.
- `docs/contracts/TARS_SUBDOMAIN.md` — DNS + routing спека.
- `docs/contracts/MEEET_DOWNLOADS.md` — манифест 1.0.0.
- `docs/contracts/UNIFIED_TELEMETRY.md` — `unified_funnel` view.
- `docs/contracts/L5_PAIRING_DRAFT.md` — encrypted sync envelope.

---

## 4. Что нужно от тебя — пошаговый чеклист

Это полный список действий на твоей стороне. Каждый пункт ссылается на детальный контракт ниже.

### 4.1 P0 — обязательно для launch

- [ ] **DNS + SSL для `tars.meeet.world`**
  CNAME на твой meeet-app или вынеси в отдельный Vercel/CF проект. Wildcard сертификат `*.meeet.world` должен покрывать. См. § 5.1.

- [ ] **Routing edge для `tars.meeet.world`**
  Сервит статический build из `experiments/neural-showcase-v3/dist`. Cache-Control на HTML 60s, на assets immutable. См. § 5.1.

- [ ] **Billing edge function — публикация / проверка**
  Подтверди что функция `tars-billing` на проекте `zujrmifaabkletgnpoyw` отвечает на:
  - `GET /operator` (Bearer auth) → возвращает `{tier, byo_enabled, live, checkout, account_url}`.
  - `POST /operator/usage` (Bearer auth, body `{delta_usd, trace_id}`) → mirror cloud spend, idempotent.
  Smoke: `make smoke-billing-tars` с нашей стороны. См. § 5.2.

- [ ] **Core-bridge edge function — публикация / проверка**
  `core-bridge` на том же проекте. Endpoints: `/health`, `/token-stats`, `/relay-event`. См. § 5.3.

- [ ] **Cookie domain `.meeet.world`**
  `meeet_session` cookie с `Domain=.meeet.world` (а не `meeet.world`). Это даст shared session между meeet.world и tars.meeet.world.

- [ ] **Generate + share `BRIDGE_SHARED_SECRET`**
  Один shared secret. Положи в Supabase secrets (`tars-billing` + `core-bridge` + `tars-ingest`) и в GitHub Actions repo secrets. См. § 6.

- [ ] **Generate + share `MEEET_BILLING_API_KEY`**
  Это `Authorization: Bearer <key>` для всех вызовов в `tars-billing`. Должен совпадать с Supabase function secret `TARS_BILLING_API_KEY`. См. § 6.

- [ ] **Создать страницу `https://meeet.world/billing/tars?plan={pro|business}`**
  Туда редиректит TARS когда юзер апгрейдится. Платежи в SOL/$MEEET через твою существующую инфру. После успешного платежа → редирект назад на `tars://login?token=<...>` или просто на `meeet.world/account`. См. § 5.4.

- [ ] **Создать страницу `https://meeet.world/account`**
  Куда TARS открывает `account_url` из `/operator`. Существующая страница аккаунта.

### 4.2 P1 — желательно к launch

- [ ] **Magic-link sign-in flow** (email → `tars://login?token=...`)
  Юзер вбивает email на `tars.meeet.world/onboarding`, твой meeet-app отправляет email с ссылкой `tars://login?token=<one-time-token>`. Когда юзер кликает — TARS desktop ловит deep-link, обменивает token на сессию через твой endpoint. См. § 5.5.

- [ ] **`unified_funnel` materialized view**
  Создать view в Supabase которая JOIN-ит `tars_event_ingest` и `meeet_events` по `trace_id`. Дашборд `/admin/telemetry`. См. § 5.6.

- [ ] **OAuth bridge для коннекторов (Gmail/Slack/Notion/Calendar)**
  Когда юзер хочет подключить Gmail, TARS открывает `https://meeet.world/connect/gmail?return=tars://callback`. Твой meeet-app делает OAuth dance, кладёт токен в Supabase Vault, возвращает minimum-scope token обратно в TARS через deep-link. См. § 5.7.

- [ ] **Downloads manifest proxy** (опционально)
  Сейчас TARS использует `https://github.com/.../releases/latest/download` напрямую. Если хочешь брендированную ссылку — подними `meeet.world/downloads/tars/*` как proxy на GitHub Releases. См. § 5.8.

### 4.3 P2 — после launch

- [ ] **Status page row** для `tars.meeet.world` на `status.meeet.world`.
- [ ] **Email notifications** для `tars.subscription.upgraded`, `tars.payment.failed` events.
- [ ] **Marketing announcement banner** на meeet.world: "TARS marketing → tars.meeet.world".

---

## 5. Контракты по точкам интеграции

### 5.1 Сабдомен `tars.meeet.world`

**Полная спека:** `docs/contracts/TARS_SUBDOMAIN.md`

**Path map (минимум):**

| Path | Behaviour |
|------|-----------|
| `GET /` | Static SPA — сервится из `experiments/neural-showcase-v3/dist/index.html` |
| `GET /assets/*` | Static, `Cache-Control: public, max-age=31536000, immutable` |
| `GET /onboarding`, `/cockpit`, `/install`, `/pricing`, `/faq`, `/compare`, `/settings`, `/changelog`, `/roadmap`, `/build-with`, `/press`, `/docs`, `/status` | Same `index.html`, client-side router |
| `GET /api/product/downloads` | Прокси на GitHub Releases (или статика — см. § 5.8) |
| `GET /sw.js` | `Cache-Control: no-cache` (но фактически не используется — см. знаменитую сноску в `DESKTOP_OWNERSHIP_PASS.md`) |
| `*` (404) | `index.html` (SPA сама покажет 404 view) |

**Required headers:**
```
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
Content-Security-Policy: frame-ancestors 'self' https://meeet.world
X-Content-Type-Options: nosniff
X-Tars-Subdomain: tars.meeet.world
X-Tars-Contract: 1.0.0
```

(Эти заголовки уже зашиты в `experiments/neural-showcase-v3/public/_headers` для Cloudflare Pages.)

### 5.2 Billing edge — `tars-billing`

**Полная спека:** `docs/contracts/TARS_MEEET_BILLING.md` (v1.2.0)

**Endpoints, твоя сторона должна реализовать:**

#### `GET {BASE}/operator`
- **Auth:** `Authorization: Bearer <MEEET_BILLING_API_KEY>` + optional `X-Tars-Operator-Id`
- **Response 200 (JSON):**
  ```json
  {
    "ok": true,
    "contract_version": "1.0.0",
    "tier": "free|pro|business",
    "byo_enabled": false,
    "live": {
      "spent_usd_24h": 0.0,
      "cap_usd_daily": 0.0,
      "remaining_usd": 0.0,
      "allowed_cloud": false,
      "reason": null
    },
    "checkout": {
      "pro": "https://meeet.world/billing/tars?plan=pro",
      "business": "https://meeet.world/billing/tars?plan=business"
    },
    "account_url": "https://meeet.world/account"
  }
  ```

#### `POST {BASE}/operator/usage`
- **Auth:** same Bearer
- **Body:** `{"delta_usd": 0.012345, "trace_id": "trc_..."}`
- **Behavior:** insert into `tars_billing_usage_dedupe` keyed by `trace_id` (idempotent — повтор с тем же `trace_id` возвращает `duplicate: true` и **не** инкрементит `spent_usd_24h`).
- **Per-request cap:** 500 USD на edge.
- **Response 200:** `{ok, contract_version, operator_id, delta_usd, spent_usd_24h, cap_usd_daily, remaining_usd, allowed_cloud, reason, duplicate}`

#### Failure modes
- `401` bad Bearer → `{"error":"unauthorized"}`
- `400` invalid body → `{"error":"invalid_payload"}`
- `5xx` DB → returns 5xx, TARS retries (`MEEET_BILLING_USAGE_RETRIES`, default 3)

### 5.3 Core bridge — `core-bridge`

**Полная спека:** `docs/contracts/CORE_BRIDGE.md` (v1.0.0)

**Mounted at:** `https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/core-bridge`

#### Required headers
- `Origin`: must be in allowlist (`https://meeet.world`, `https://tars.meeet.world`)
- `x-bridge-secret`: matches `BRIDGE_SHARED_SECRET` env (constant-time compared)

#### Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness |
| GET | `/token-stats` | $MEEET stats (staked / burned) для public dashboard |
| POST | `/relay-event` | Forward `TARSEvent` to `tars-ingest` |

#### `/relay-event` body
```json
{
  "kind": "tars.page.viewed",
  "trace_id": "trace_smoke_001",
  "session_id": "ses_smoke_001",
  "contract_version": "1.0.0",
  "payload": {"path": "/install", "source": "smoke"}
}
```

### 5.4 Checkout pages

Когда юзер с TARS кликает "Upgrade to Pro" → TARS делает `POST /api/entitlements/upgrade` → backend смотрит на `MEEET_BILLING_BASE_URL` и `checkout.{tier}` из `/operator` ответа → возвращает `redirect: <URL>`.

Юзер должен попасть на твою страницу. **Что от тебя нужно:**

1. Страница принимает query: `?plan=pro|business`
2. Если юзер не залогинен → редирект на login flow (твой стандартный)
3. После успешного платежа в SOL/$MEEET:
   - Обнови `tier` в твоей DB
   - Следующий `GET /operator` от TARS вернёт новый tier с правильным `cap_usd_daily`
4. Опциональный return URL: либо обратно на `tars://cockpit`, либо просто на `meeet.world/account` со success баннером

### 5.5 Magic-link sign-in flow (P1)

**Use case:** юзер на `tars.meeet.world/onboarding` вбивает email → TARS desktop сразу авторизован без пароля.

**Шаги:**

1. TARS web sends: `POST meeet.world/api/magic-link` body `{email, target: "tars-desktop"}`
2. Твой meeet-app:
   - Mints one-time `token` (UUID, 15min TTL, single-use)
   - Sends email с ссылкой: `https://meeet.world/auth/tars-claim?token=<token>`
3. Юзер кликает в почте → попадает на твою страницу `/auth/tars-claim`
4. Твоя страница:
   - Verifies token, marks claimed
   - Redirects to: `tars://login?token=<token>&operator_id=<uuid>`
5. TARS desktop ловит deep-link через `useTarsDeepLink.ts`, парсит query, делает `POST meeet.world/api/sessions/exchange` body `{token}` → твой endpoint возвращает session JWT.
6. TARS сохраняет JWT в `~/Library/Application Support/world.meeet.tars/session.json`.

**Endpoints от тебя:**
- `POST /api/magic-link` — body `{email, target}`, returns `{ok}`, шлёт email.
- `GET /auth/tars-claim?token=…` — HTML страница с auto-redirect на `tars://login?token=…`.
- `POST /api/sessions/exchange` — body `{token}`, returns `{operator_id, jwt, expires_at}`.

### 5.6 `unified_funnel` view

**Полная спека:** `docs/contracts/UNIFIED_TELEMETRY.md`

Создать на твоём Supabase project (`zujrmifaabkletgnpoyw`):

```sql
create or replace view public.unified_funnel as
select
  coalesce(t.trace_id, m.trace_id) as trace_id,
  coalesce(t.operator_id, m.operator_id) as operator_id,
  coalesce(t.session_id, m.session_id) as session_id,
  t.kind as tars_kind,
  m.kind as meeet_kind,
  t.created_at as tars_at,
  m.created_at as meeet_at,
  t.payload as tars_payload,
  m.payload as meeet_payload
from tars_event_ingest t
full outer join meeet_events m
  on t.trace_id = m.trace_id
order by coalesce(t.created_at, m.created_at) desc;
```

⚠️ Это cross-project — `tars_event_ingest` живёт на нашем Supabase (`hhpaukjobskcwkxbgecl`), `meeet_events` на твоём. Решение: создай **foreign data wrapper** или периодический ETL (раз в 5 минут sync `tars_event_ingest` → твой проект).

Дашборд `/admin/telemetry` показывает: трейсы где `tars.install.script.fetched` есть но `meeet.payment.ok` нет → "потеряли на этапе платежа".

### 5.7 OAuth bridge для коннекторов (P1)

**Use case:** юзер хочет подключить Gmail к TARS. TARS не может хранить OAuth client secret клиентски — нужен брокер.

**Шаги:**

1. TARS cockpit делает: `window.open("https://meeet.world/connect/gmail?return=tars://callback&state=<csrf>")`
2. Твой meeet-app:
   - Verifies user is logged in to meeet
   - Redirects to Google OAuth с `client_id` + `redirect_uri=meeet.world/connect/gmail/callback`
   - Юзер approve'ит scopes → Google → твой callback
3. Твой callback:
   - Exchanges code for token, **stores token в Supabase Vault** под `operator_id × provider`
   - Mints **scoped session token** (узкий, e.g. "read gmail for operator X next 1h")
   - Redirects back: `tars://callback?provider=gmail&session=<scoped_token>&state=<csrf>`
4. TARS desktop ловит deep-link → использует scoped token для real Gmail API calls (через твой meeet-app proxy: `POST meeet.world/api/connect/gmail/list?session=<token>`)

**Endpoints от тебя:**
- `GET /connect/{provider}?return=&state=` — стандартный OAuth start
- `GET /connect/{provider}/callback?code=&state=` — OAuth finish
- `POST /api/connect/{provider}/{action}` — proxy на provider API с auto-token-refresh из Vault

**Поддерживаемые провайдеры (для launch):** Gmail, Google Calendar, Slack. Добавим Notion, GitHub, Linear позже.

### 5.8 Downloads manifest (опционально)

Сейчас работает напрямую с GitHub Releases:
- `TARS_DOWNLOAD_BASE_URL=https://github.com/alxvasilevvv/tars-neural-cockpit/releases/latest/download`

Если хочешь брендированный URL `meeet.world/downloads/tars/...`:
1. Подними proxy на edge (Cloudflare Workers / Vercel route)
2. Прокси берёт path → пробрасывает на `github.com/.../releases/latest/download/{path}`
3. Caches 5 мин (релизы не обновляются часто)
4. Ставит `X-Tars-Contract: 1.0.0` header

После — поменяй `TARS_DOWNLOAD_BASE_URL` в `.env` на `https://meeet.world/downloads/tars`. Десктоп и web подхватят автоматически.

---

## 6. Секреты и переменные окружения

Список всех секретов которые должны быть синхронизированы между:
- Supabase function secrets (`zujrmifaabkletgnpoyw` project secrets)
- TARS desktop `.env` (operator's machine)
- GitHub Actions repo secrets (для CI gates)

| Имя | Где живёт | Назначение |
|-----|-----------|------------|
| `BRIDGE_SHARED_SECRET` | Supabase secrets `core-bridge` + TARS `.env` | x-bridge-secret для relay |
| `MEEET_BILLING_API_KEY` (= `TARS_BILLING_API_KEY` на edge) | Supabase secrets `tars-billing` + TARS `.env` | Bearer для billing |
| `TARS_INGEST_API_KEY` (= `MEEET_API_KEY` на тarsих) | Supabase secrets `core-bridge` (для relay) + TARS `.env` | Bearer для ingest |
| `MEEET_INGEST_URL` | TARS `.env` | URL `https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/tars-ingest` |
| `MEEET_BILLING_BASE_URL` | TARS `.env` | URL `https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/tars-billing` (или meeet.world proxy) |
| `MEEET_CONTRACT_VERSION` | TARS `.env` | `1.1.0` |
| `MEEET_SOURCE` | TARS `.env` | `tars` |
| `TARS_PAYMENT_MODE` | TARS `.env` | `onchain` (SOL) / `tokens` ($MEEET) / `stripe` (legacy) |
| `TARS_BILLING_SOURCE` | TARS `.env` | `local` (dev) / `remote` (prod, mirrors meeet) |

**Важно:** `MEEET_BILLING_API_KEY` (TARS-сторона) и `TARS_BILLING_API_KEY` (Lovable function secret) — это **один и тот же секрет**. Просто называется по-разному в разных контекстах.

**Где взять реальные значения:** генерируешь рандомно (`openssl rand -hex 32`), кладёшь в оба места одновременно. Для launch — один раз. Ротация раз в 90 дней (рекомендация).

---

## 7. Smoke-тесты / верификация

Все смоки гоняются с **нашей стороны** (Алексей запускает локально). Вот команды по каждой точке:

### 7.1 Sub-домен живой
```bash
curl -sI https://tars.meeet.world/ | head -3
# Expect: HTTP/2 200 + Strict-Transport-Security
curl -sI https://tars.meeet.world/install | head -3
# Expect: HTTP/2 200 (SPA route)
```

### 7.2 Billing edge отвечает
```bash
cd /Users/alien/Documents/Claude/Projects/Jarvis/jarvis
make smoke-billing-tars
# Expect: green checkmarks for GET /operator + POST /operator/usage
```

### 7.3 Core bridge отвечает
```bash
BRIDGE_SHARED_SECRET=<secret> make smoke-core-bridge
# Expect:
#   GET /health → 200
#   GET /token-stats → 200
#   POST /relay-event → 200 + persisted:true
#   GET /health no-secret → 401
#   POST /relay-event bad origin → 403
```

### 7.4 Cookie domain работает
```bash
# С браузера: залогинься на meeet.world, открой devtools → Application → Cookies
# Expect: meeet_session с Domain=.meeet.world (с точкой!)
# Затем открой https://tars.meeet.world/cockpit — без релогина должен показать твой email
```

### 7.5 Downloads manifest
```bash
curl -s https://tars.meeet.world/api/product/downloads | jq '.contract_version, .releases[0].version'
# Expect: "1.0.0", current version
```

### 7.6 Magic-link round-trip (когда поднимешь)
1. Browser: open `https://tars.meeet.world/onboarding`
2. Enter email → click "Send magic link"
3. Check email — должна прийти ссылка `https://meeet.world/auth/tars-claim?token=…`
4. Click → должен открыться TARS desktop с автологином

### 7.7 Full e2e — control tower
```bash
make gate-control-tower
# Запускает все smokes выше последовательно. Должен быть зелёным.
```

---

## 8. Финальный launch checklist

Это итоговый список галочек для launch day. Я (Claude) могу подтвердить только TARS-сторону; meeet.world-сторона — на тебе.

### TARS side (мы)

- [x] Backend tests passing (2411 pytest, all green)
- [x] Frontend build clean
- [x] Desktop Tauri shell native UX (Wave 59-63)
- [x] Sidecar status indicator + crash detection (Wave 60-61)
- [x] /settings page + updater UI (Wave 62)
- [x] All P0/P1 a11y fixes (Wave 53-58)
- [x] DESKTOP.md operator guide
- [x] Билд GitHub Releases (manual triggered)

### meeet.world side (ты)

- [ ] DNS `tars.meeet.world` → твой edge
- [ ] SSL валидный, HSTS включён
- [ ] Static serve `experiments/neural-showcase-v3/dist`
- [ ] `meeet_session` cookie с `Domain=.meeet.world`
- [ ] Edge function `tars-billing` отвечает на `GET /operator` + `POST /operator/usage`
- [ ] Edge function `core-bridge` отвечает на `/health` + `/token-stats` + `/relay-event`
- [ ] `BRIDGE_SHARED_SECRET` совпадает на 3 местах (TARS .env, GitHub secrets, Supabase secrets)
- [ ] `MEEET_BILLING_API_KEY` совпадает (TARS .env + Supabase function secret)
- [ ] Страница `meeet.world/billing/tars?plan=pro|business` работает
- [ ] Страница `meeet.world/account` показывает $MEEET balance + tier
- [ ] (P1) Magic-link flow — email → `tars://login?token=…`
- [ ] (P1) `unified_funnel` view + ETL job
- [ ] (P1) OAuth bridge для как минимум Gmail + Google Calendar
- [ ] `make gate-control-tower` зелёный с нашей машины

### Operator side (Алексей)

- [ ] Apple Developer ID enrollment ($99/year)
- [ ] Windows Authenticode cert (~$200-400/year)
- [ ] `bash desktop/scripts/generate-release-keys.sh --patch-tauri-conf` — генерация minisign key для updater
- [ ] GitHub Actions secrets: `TAURI_SIGNING_PRIVATE_KEY`, `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`, Apple ID app-specific password
- [ ] Tag release `v9.1.0` → CI собирает все артефакты + signs + uploads
- [ ] Smoke install на чистой Mac → "TARS launches without security warnings"
- [ ] Twitter/blog announcement

---

## 9. Источники истины (read these)

В порядке приоритета:

1. **Этот документ** — high-level карта всего.
2. **`docs/SYNC.md`** — как я и Cursor разделяем работу, lane ownership, branch conventions.
3. **`docs/contracts/CORE_BRIDGE.md`** — точная wire-shape relay-event.
4. **`docs/contracts/TARS_MEEET_BILLING.md`** — billing API v1.2.0 (полная спека endpoints + retries + dedupe).
5. **`docs/contracts/TARS_SUBDOMAIN.md`** — DNS / routing / cookies / telemetry для `tars.meeet.world`.
6. **`docs/contracts/MEEET_DOWNLOADS.md`** — манифест 1.0.0.
7. **`docs/contracts/UNIFIED_TELEMETRY.md`** — `unified_funnel` view + dashboard.
8. **`docs/contracts/L5_PAIRING_DRAFT.md`** — encrypted sync envelope (orthogonal, не блокирует launch).
9. **`docs/DESKTOP.md`** — что юзер увидит когда установит десктоп.
10. **`docs/AGENT_HANDOFF.md`** — последние operational заметки.

Все docs живут в каноническом репо: `github.com/alxvasilevvv/tars-neural-cockpit/tree/main/docs/`.

---

## Коротко — ОДИН раз посмотри

Если у тебя 2 минуты — вот самое важное:

1. **Сабдомен** — подними `tars.meeet.world` (DNS + SSL + serve static).
2. **3 secrets** — generate `BRIDGE_SHARED_SECRET` + `MEEET_BILLING_API_KEY` + `TARS_INGEST_API_KEY`, синкни между Supabase + наш `.env` + GitHub secrets.
3. **2 billing endpoints на edge function** — `GET /operator` (вернуть JSON) + `POST /operator/usage` (idempotent через trace_id).
4. **2 страницы** — `/billing/tars?plan=…` (checkout) + `/account` (профиль).
5. **Cookie** — `Domain=.meeet.world` на `meeet_session`.

Это full P0 launch. Всё остальное (magic-link, OAuth bridge, telemetry view) — можно дописывать после launch неделями.

— Claude, 2026-05-05
