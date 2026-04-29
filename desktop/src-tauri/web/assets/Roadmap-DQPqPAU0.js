import{j as n}from"./react-vendor-DRVBxK-d.js";import{L as e}from"./LegalLayout-DFQ9oT0k.js";import"./index-B8RpGBsb.js";import"./meta-C8YFV54H.js";import"./arrow-left-keFoAM4R.js";const t=`# Phase M — Monetization, packaging, и product polish

> **Status:** ТЗ зафиксировано 2026-04-29 после устной постановки от
> Alien. Делаем по готовности — каждая P# самостоятельная, можно
> запускать параллельно с Phase L (Cursor).
>
> **Owners:** дизайн / документы / экономика / UI = Claude;
> backend-контракты, vault, role registry = Cursor.
>
> Соблюдаем правила handoff: контракты выдумывать запрещено,
> только то что в \`docs/contracts/\` или уже в репо. Любые новые
> backend-сюрфейсы прописаны как ТЗ для Cursor с явным указанием
> что я **не** делаю их сам.

---

## 0. Текущее состояние (на 2026-04-29 18:30)

Всё что нужно для Phase M — этой фазы — стоит на следующих
shipped-якорях:

- \`backend/core/usage/ledger.py\` (K2/K3) — cost ledger по моделям /
  route / session с \`cost_usd\`. Это база для P5 (token control).
- \`backend/core/domains/packs/{traders,business,mlm,science}\` — текущие
  4 пакета, плюс composites. P6 переименовывает \`mlm/\` →
  \`entrepreneur/\`.
- \`backend/core/voice/personas.py\` — voice character registry. Не
  путать с product-роли (P7); это разные оси.
- \`docs/contracts/MEEET_DOWNLOADS.md\` 1.0.0 + L5 pairing 1.1.0
  (envelope + recovery seed) — база для P4 субдомена.
- \`experiments/neural-showcase-v3/src/components/{Pricing, FAQ, Compare,
  DomainsCards, MeeetWorldStrip, PairingHostCard}.tsx\` — фронт
  готов под расширение.

Чего **нет** в текущем дереве (важно для оценки P5/P7/P8):

- \`backend/agents/vision_agent.py\` — только compiled \`.pyc\` остался от
  v7.1, исходника нет. Vision переподнимается с нуля → задача
  P8 = новая разработка, не "докрутить UI".
- \`backend/core/entitlements/tiers.py\` — только compiled \`.pyc\`, tier
  gating придётся переподнять через Cursor. Это изменяет P5 —
  фронт пишу против контракта который Cursor мерджит во время /
  после.

---

## 1. Оглавление задач

| # | Название | Owner | Размер | Зависит от |
|---|----------|-------|--------|------------|
| **P1** | Полная документация + FAQ | Claude | M (3-4 ч) | — |
| **P2** | Pitch deck (pptx + HTML) | Claude | M (4-5 ч) | P1 (контент) |
| **P3** | Security + ToS + Privacy | Claude + Cursor | M (3-4 ч) | — |
| **P4** | tars.meeet.world subdomain — ТЗ для брата | Claude (spec) | S (1-2 ч) | — |
| **P5** | Token control + подписочная экономика | Claude (econ + UI) + Cursor (tiers.py) | L (6-8 ч) | tiers.py от Cursor |
| **P6** | Убрать MLM, поставить Entrepreneur | Claude (фронт) + Cursor (registry) | M (2-3 ч) | Cursor pack rename |
| **P7** | Role selection + кастомная роль | Claude (UI) + Cursor (\`/api/roles\`) | L (5-7 ч) | P6, новый /api/roles |
| **P8** | Machine vision — переподнять | Cursor (агент) + Claude (UI) | L (6-8 ч) | L2 attachments pipeline |

Параллелизм: P1, P3, P4 — без зависимостей, можно крутить в любом
порядке. P5/P6/P7 — упорядочить, P6 → P7 → P5 имеет смысл (роли
заменяют packs, тарифы биндятся к ролям). P8 — отдельно, в любой
момент.

---

## 2. P1 — Полная документация + FAQ

### Цель
Покрыть 100% вопросов которые приходят в Discord / Twitter / sales
инбокс единым документом. Frontend FAQ — выжимка топ-12; полная
версия — \`docs/FAQ.md\` для embed в meeet.world и для PR-кит.

### Объём

**Полный FAQ.md** (около 30-40 вопросов), категории:

1. Privacy + locality (5-6 q): где данные, что покидает машину,
   как удалить, GDPR, sub-processor list.
2. Pricing + billing (5-6 q): что включено в Free, что в Pro, как
   платить $MEEET, refund, downgrades, invoices.
3. Setup + install (4-5 q): требования, alternatives к curl, brew,
   uninstall, multi-machine, Apple Silicon vs Intel.
4. $MEEET + Solana (4-5 q): что такое $MEEET, нужен ли кошелёк,
   как заработать, can I cash out, какой кошелёк подходит.
5. Tech / agent (5-6 q): какие LLM поддерживаются, BYO key,
   cost transparency, on-device vs cloud, council voting, MCP
   compat.
6. Roles + packs (3-4 q): как выбрать роль, можно ли менять,
   custom role, миграция между ролями.
7. Security + audit (5-6 q): sandboxing, signed receipts, что
   логируется в meeet.world, recovery seed, multi-device.
8. Roadmap + community (3-4 q): что в работе, как влиять, Discord,
   skill SDK, marketplace.

**Frontend FAQ.tsx** — расширить с 8 до 12-16 вопросов, выбрать
самые частые из каждой категории.

**Опционально** — \`docs/FAQ.docx\` через skill \`docx\` для
sales-команды и инвесторов.

### Acceptance
- \`docs/FAQ.md\` ≥ 30 Q&A, all answered factually.
- Frontend FAQ.tsx обновлён, читается через те же якоря.
- TypeScript clean.

---

## 3. P2 — Pitch deck

### Цель
10-12 слайдов pitch-deck'а. Использовать \`pptx\` skill — выходит
готовый \`.pptx\` с meeet-палитрой. Параллельно HTML-версия на
\`/pitch\` или standalone в \`experiments/pitch/\` для самохост.

### Структура слайдов

1. **Title** — TARS · Agent Intelligence · meeet.world
2. **Problem** — операторы хотят real agent, не chat. Прокси, что
   IDE-ассистенты не покрывают — операционка, файлы, web, mail.
3. **Solution** — local-first AI cockpit. 28 agents · 14 skills ·
   6 LLM providers · 4 packs.
4. **Demo** — три скриншота: cockpit / chat with retrieval /
   council vote.
5. **Architecture diagram** — meeet.world topology (encrypted
   ingest, identity, marketplace) + TARS (host + mobile clients).
6. **Domain packs** — Traders / Entrepreneur / Researcher / Custom.
   (Note: post-P6/P7 структура.)
7. **$MEEET economy** — earn while agent works, pay in $MEEET or
   USD, T2T deals.
8. **Security** — local-first, MIT, signed receipts, X25519 +
   XChaCha20-Poly1305 sync, policy gate.
9. **Pricing** — Free / Pro / Business / Lifetime.
10. **Traction / roadmap** — Phase L shipped, M в работе, L9
    desktop releases.
11. **Team / brother / handoff** — meeet.world команда.
12. **Ask / contact** — discord, github, deck-pitch URL.

### Acceptance
- \`deliverables/TARS_Pitch_2026Q2.pptx\` — meeet-палитра,
  Share Tech Mono + Fira Code типографика.
- \`experiments/neural-showcase-v3/src/pages/Pitch.tsx\` — HTML-версия
  на \`/pitch\`, ту же структуру, embeddable iframe.
- Линки на demo-видео placeholder'ы пока, реальные подменим.

---

## 4. P3 — Security + ToS + Privacy

### Цель
Полная юридическая + техническая обвязка: SECURITY.md описывает
как мы защищаем оператора, ToS определяет правила использования,
Privacy Policy перечисляет что собираем (≈ ничего by default).

### Документы

**\`docs/SECURITY.md\`** (3-4 страницы):
- Threat model (по STRIDE): кто атакует, что защищается.
- Architecture: local daemon → sandbox-exec для destructive,
  signed receipts, X25519 master key, XChaCha20-Poly1305 sync
  envelope.
- Data flow diagram: что покидает машину когда (только cloud LLM
  при явном opt-in, encrypted blobs в meeet.world при L5 pairing).
- Vulnerability disclosure: security@meeet.world, 90-day, hall of
  fame.
- Cryptographic primitives: версии, источники (libsodium / pynacl /
  CryptoKit / Conscrypt).
- Audit log: receipt format + Solana memo anchoring.

**\`docs/TERMS_OF_SERVICE.md\`**:
- Лицензия MIT для core, отдельно EULA для $MEEET / cloud features.
- Acceptable use (что нельзя — спам, малварь, дипфейк).
- $MEEET: tokens are not securities, не investments, могут менять
  стоимость, не FDIC-insured.
- Liability disclaimer (стандартный для self-hosted SW).
- Termination + data export.
- Jurisdiction (предложу Estonia / Delaware на выбор брата).

**\`docs/PRIVACY_POLICY.md\`**:
- What we DON'T collect: prompts, files, chat history, model
  outputs (всё на устройстве).
- What we DO collect when opted in: encrypted ciphertext blobs,
  metadata (ts, kind, route, session_id), $MEEET wallet address.
- Sub-processors: только если cloud LLM включён — Anthropic /
  OpenAI / etc. с их Data Processing Agreements.
- GDPR rights, data deletion, export.
- Cookies (только functional на marketing site).

### Acceptance
- Три документа в \`docs/\`.
- Footer на v3 показывает \`/privacy\` и \`/terms\` ссылки → отдельные
  страницы или markdown render.
- Cursor проверяет техническую часть SECURITY.md (threat model + crypto
  versions).

---

## 5. P4 — tars.meeet.world subdomain · ТЗ

### Цель
Документ для брата meeet.world: как поднять \`tars.meeet.world\` со
сквозным логированием в основной meeet.world account. Только
спецификация — код пишет он или Cursor по этой спеке.

### Документ: \`docs/contracts/TARS_SUBDOMAIN.md\`

**1. DNS + SSL**
- \`tars.meeet.world\` CNAME → меееt-app.fly.io / vercel.app (как у
  основного).
- Wildcard SSL \`*.meeet.world\` — или отдельный Let's Encrypt.

**2. Reverse proxy / origin**
- Origin: либо отдельный Cloudflare worker, либо подсадка на
  существующий meeet-app роутинг.
- \`tars.meeet.world/*\` → \`meeet-app:tars-handler\` где сидит:
  - Static frontend (build из \`experiments/neural-showcase-v3/dist\`).
  - Прокси \`/api/product/downloads\` → \`meeet-app/api/tars-downloads\`
    (тот же manifest shape, наш контракт 1.0.0).
  - \`/install.sh\` → S3-hosted текущий скрипт.
  - \`/auth/callback\` → meeet-app login bridge.

**3. End-to-end logging contract**
- Каждый HTTP request на \`tars.meeet.world\` → инжектится header
  \`x-tars-session-id\` (генерится клиентом или продлевается).
- meeet-app сторит этот session_id в основной таблице events с
  \`source=tars_subdomain\`.
- При login operator получает \`meeet_user_id\` + \`tars_session_id\`
  → backend связывает их одной строкой в \`user_sessions\` таблице.
- Trace propagation: исходящие запросы из \`tars.meeet.world\` → к
  меееt API передают \`x-trace-id\` (uuid4); meeet ингестит в
  основной trace store. Один operator = один trace дерево
  через все сабдомены.

**4. Acceptance / smoke test**
- \`curl https://tars.meeet.world/api/product/downloads\` →
  возвращает manifest с \`contract_version=1.0.0\` и meeet-источником.
- \`curl -H "x-tars-session-id: ses_abc" https://tars.meeet.world/\`
  → meeet event store содержит запись с этим session_id и
  \`source=tars_subdomain\` через 30 секунд.

**5. Rollout**
- Stage: \`tars-staging.meeet.world\`, прогон 7 дней в shadow.
- Production: \`tars.meeet.world\`, мониторинг 99.9% uptime.

### Acceptance ТЗ
Документ передан брату вместе с ссылкой на \`docs/contracts/
MEEET_DOWNLOADS.md\`. Брат может имплементировать без вопросов
"что значит trace propagation".

---

## 6. P5 — Token control + подписочная экономика

### 6.1 Текущая экономика — гипотезы

- 1M output токенов на claude-sonnet-4.5 ≈ $15. Average operator
  выпускает 30k output / день ≈ $0.45/day = $13.5/mo.
- 1M input токенов claude ≈ $3. Average input 100k/day ≈ $9/mo.
- Совокупный raw COGS (cloud LLM) для активного pro-юзера:
  **$22-25/mo** при стандартном использовании.
- Pro подписка $19/mo → margin отрицательный без cap'а или
  BYO-key обязательного для cloud features.

### 6.2 Целевая модель

| Tier | $/mo | Cloud cap (LLM-USD) | T2T deals | Council votes/day | AI Clone |
|------|-----:|--------------------:|----------:|------------------:|---------:|
| Free | $0 | $0 (BYO key only) | 0 | 0 (single voice) | — |
| Pro | $19 | $10 | 50 | 100 | trained |
| Business | $79/seat | $40/seat | unlimited | unlimited | trained + shared |
| Lifetime | $299 once | $10/mo forever | 100 | 200 | trained |

Логика:
- Free всегда работает на local model (Ollama) без cloud cost'а.
- Pro имеет $10/mo cloud budget — это покрывает 70-percentile
  пользователей. Heavy users hit cap → throttle с предложением
  BYO key или upgrade.
- Business — cloud budget per seat, можно распределять между
  командой.
- Lifetime — cloud budget капнут как Pro, но без ежемесячной
  оплаты; зарабатывает на $MEEET allocation на старте.

### 6.3 Throttle поведение

Когда \`cost_used >= 0.8 * cap\`:
- Cockpit показывает yellow strip "approaching budget · 80% used".
- Соковет переключается на \`single\` voice mode (только local).
- T2T предлагает confirm перед каждой deal.

Когда \`cost_used >= cap\`:
- Cloud LLM calls 402 Payment Required.
- UI показывает upgrade modal или "switch to BYO key".
- Local model + memory + Mac actions работают как обычно.

### 6.4 ТЗ для Cursor

Новый модуль \`backend/core/entitlements/\`:

\`\`\`python
# tiers.py — replaces the lost compiled version
class Tier(Enum):
    FREE = "free"; PRO = "pro"; BUSINESS = "business"; LIFETIME = "lifetime"

@dataclass
class TierLimits:
    cloud_usd_cap_monthly: float | None  # None = unlimited
    t2t_deals_monthly: int | None
    council_votes_daily: int | None
    ai_clone: bool

# limits.py — public API
async def get_user_tier(operator_id: str) -> Tier
async def get_remaining_budget(operator_id: str) -> dict
async def can_run(operator_id: str, kind: str, est_cost_usd: float) -> tuple[bool, str]

# Хук: orchestrator перед cloud-call зовёт can_run() →
# false → возвращает 402 Payment Required, UI обрабатывает.
\`\`\`

Endpoints:

\`\`\`
GET /api/entitlements/me               → текущий tier + лимиты + использовано
GET /api/entitlements/usage?since=...  → история spend по tier
POST /api/entitlements/upgrade         → POST { tier, payment_token } -- через meeet.world
\`\`\`

### 6.5 ТЗ для меня (UI)

- В Cockpit \`<UsageStrip />\` (Cursor уже есть) — добавить tier-badge
  и progress-bar к budget.
- В Pricing.tsx — обновить cap'ы согласно таблице 6.2 (текущие
  цифры там placeholder).
- Новый \`<BudgetWarning />\` компонент: yellow при 80%, red при
  100%, embed in cockpit header.

### Acceptance
- Backend tiers.py + limits.py + endpoints — Cursor
- UI BudgetWarning + Pricing update — Claude
- Smoke: создать free user → сделать 100 cloud-calls → 402 на
  101-м.

---

## 7. P6 — Убрать MLM, поставить Entrepreneur

### Решение: rename, не delete

Сохраняем \`slug=mlm\` как hidden alias чтобы существующие сейвы
не сломались. Новое имя: \`entrepreneur\`.

### Backend (Cursor)

- \`backend/core/domains/packs/entrepreneur/\` — переименование папки
  \`mlm/\` целиком. Внутри:
  - \`actions.py\` обновить названия функций под бизнесмена:
    \`network_snapshot\` → \`team_snapshot\`, \`recruit_score\` →
    \`lead_score\`, \`retention_alert\` → \`churn_alert\`, \`generate_post\`
    → \`generate_outreach\`.
  - \`manifest.py\` — \`slug="entrepreneur"\`, \`name="Entrepreneur"\`,
    \`description="For founders, freelancers, и solopreneurs.
    Pipeline tracking, lead scoring, content drafts, churn
    alerts."\`
  - В \`registry.py\` зарегистрировать также alias \`mlm\` →
    \`entrepreneur\` для backwards-compat на 90 дней.

### Frontend (Claude)

- \`DomainsCards.tsx\` — обновить slug/name/teaser/glyph для
  entrepreneur. Glyph: можно оставить network graph (всё ещё
  про сеть людей, но тон другой), либо заменить на
  pipeline-style (3-stage funnel).
- \`Onboarding.tsx\` (если ещё используется) — обновить опции.
- \`Compare.tsx\` — пересмотреть строки про MLM.
- \`Pricing.tsx\` / \`FAQ.tsx\` — где упоминается MLM, заменить.

### Migration

- Backend: при первом старте после rebrand, если в SQLite
  user-state есть \`pack=mlm\`, конвертить в \`entrepreneur\` с
  receipt в audit log.

### Acceptance
- \`tars\` install для нового юзера предлагает Entrepreneur, не MLM.
- Существующий юзер с \`pack=mlm\` в \`~/.tars/state.sqlite\` после
  upgrade видит pack=Entrepreneur без потери data.
- Нет упоминаний "MLM" в публичной копи (FAQ/Compare/Pricing/
  DomainsCards).

---

## 8. P7 — Role selection + кастомная роль

### Концепт

Сейчас на onboarding выбирают **pack** (traders / business / mlm /
science). Это технологический термин. Заменяем на **role** —
человеческий, с кастомизацией.

Pack остаётся как backend-понятие (registry, actions, awareness),
role — UX-понятие, мапится на 1+ pack под капотом.

### Roles (default)

| Role | Maps to packs | Killer use case |
|------|---------------|-----------------|
| **Founder / CEO** | entrepreneur + business | Daily brief, KPI snapshot, deals pipeline |
| **Trader** | traders | Markets, signals, risk |
| **Researcher** | science | Papers, citations, data |
| **Marketer** | entrepreneur + content | Copy, posts, engagement |
| **Engineer** | code + science | Repos, PR review, code RAG |
| **Operator** | composite (any/all) | Generalist — full cockpit |
| **Custom →** | dynamic | Trained on your description |

### Custom role flow

1. Operator вводит **name** ("Sales Director") + **description**
   (free-form, 200-500 chars: "I run a 12-person sales team in
   B2B SaaS, focus on enterprise deals…").
2. Optional: 3 sample tasks ("morning brief from Salesforce",
   "draft outreach to lead", "Monday team check-in").
3. Backend GPT-prompt создаёт system prompt overlay для воркера,
   pinns в \`~/.tars/roles/<role_id>.json\`.
4. AI Clone v1 (task #104, shipped) обучается на первых 50
   взаимодействиях operator'а в этой роли.

### ТЗ для Cursor

Новый модуль \`backend/core/roles/\`:

\`\`\`python
# registry.py
@dataclass
class Role:
    slug: str
    display_name: str
    description: str
    backing_packs: list[str]
    system_prompt_overlay: str | None
    is_custom: bool

DEFAULT_ROLES = [Role(...) for r in 6_DEFAULT_ROLES]

# api endpoints
GET /api/roles                          # list defaults + user customs
POST /api/roles                         # create custom { name, desc, samples? }
PATCH /api/roles/{slug}                 # update overlay
DELETE /api/roles/{slug}                # only customs
GET /api/roles/active                   # current user's role
PUT /api/roles/active                   # switch role { slug }
\`\`\`

### ТЗ для меня (UI)

- \`Onboarding.tsx\` — заменить pack selector на role selector
  (6 default + 1 custom card).
- Новый \`RoleEditor.tsx\` — модал с инпутами name/description/samples,
  preview генерируемого system prompt.
- Cockpit header — текущая роль с possible-switch dropdown.
- Settings page (если её нет — создать \`pages/Settings.tsx\`) —
  manage custom roles, see AI Clone training progress.

### Acceptance
- Onboarding выдаёт 7 ролей вместо 4 packs.
- Custom role можно создать, редактировать, переключиться.
- Backend \`system_prompt_overlay\` инжектится перед каждым LLM call.

---

## 9. P8 — Machine vision

### Аудит (что есть)

- Compiled \`.pyc\` от \`vision_agent.py\` в \`backend/agents/__pycache__/\`
  но **исходник отсутствует**. Не тянем legacy код наугад.
- L2 attachments pipeline (Cursor) уже принимает images как
  attachments; они сторятся, но **assistant их не видит** (см.
  IDEAS.md: "Image vision routing — when chat voice is multimodal-
  capable, pack image bytes into payload").

### План

**Не пытаемся восстановить vision_agent — пишем заново через
attachment pipeline + multimodal LLM.**

### ТЗ для Cursor

1. Расширить \`attachment.kind\` enum: добавить \`image\` рядом с
   \`text/json/csv/md/pdf\`.
2. В \`backend/core/chat/orchestrator.py\` — когда current voice
   \`claude-sonnet-4.5\` или \`gpt-4o\`/\`gpt-5o\`, и attachment.kind ==
   "image", упаковать image bytes в payload (base64 или url) под
   правильную форму API. Под Anthropic — \`content: [{type:
   "image", source: {type: "base64", ...}}, ...]\`. Под OpenAI —
   \`{type: "image_url", image_url: ...}\`.
3. Когда voice **не** multimodal — fallback на OCR через
   \`pytesseract\` (CPU, on-device) и инжект текста в prompt с
   меткой \`[ocr from image.png]\`. Это free tier path.
4. Тесты: \`tests/test_vision_routing.py\` — multimodal + OCR
   fallback + non-image кейсы.

### ТЗ для меня (UI)

- \`ChatPane.tsx\` — drop-zone уже принимает images через
  \`useDropZone\` (L2). Добавить inline preview thumbnail в chip.
- \`MessageBubble\` — когда tool-call содержит vision result,
  рендерить thumbnail ratio-saved.
- Новый pack действие в \`business\`/\`science\`: \`analyze_image\`
  (Cursor), \`analyze_screenshot\` (Cursor) — UI чипы для них.

### Use cases

- "Опиши этот скриншот" → multimodal voice
- "Извлеки данные из этой таблицы" → OCR + structured prompt
- "Найди баг на этом UI" → multimodal voice с design-system
  prompt
- "Это инвойс? Сколько сумма?" → OCR + parse

### Acceptance
- Drop image в ChatPane → assistant отвечает осмысленно
  (multimodal) или по OCR-тексту (fallback).
- Tests proof: 3 happy-path + 1 OCR fallback + 1 unsupported
  voice.

---

## 10. План выполнения — фаза за фазой

### Wave 1 (параллельно, ничего не блокирует)

**Параллельно** (без backend coordination):

- **P1** Полный FAQ + расширение FAQ.tsx — Claude solo, ~3 ч
- **P3** SECURITY.md + ToS + Privacy — Claude pisat, Cursor проверит
  крипто-секции, ~3 ч
- **P4** Subdomain ТЗ — Claude solo (документ для брата), ~1.5 ч

Этот wave можно запустить прямо сейчас, пока Cursor доделывает L5
v1.5.

### Wave 2 (после Wave 1, нужна координация)

**Последовательно**:

- **P6** Rename MLM → Entrepreneur — Cursor сначала (registry
  rename), Claude следом (frontend копи). ~2 ч кросс-агента.
- **P7** Role selection — Cursor \`/api/roles\` endpoints + module,
  Claude UI Onboarding/RoleEditor/Settings. Зависит от P6 (роли
  мапятся на entrepreneur, не mlm). ~5-7 ч.

### Wave 3 (большие, в любом порядке)

- **P5** Token control — Cursor пишет tiers.py + endpoints, Claude
  делает BudgetWarning + Pricing update + UI. ~6-8 ч.
- **P8** Machine vision — Cursor расширяет attachment pipeline +
  orchestrator routing, Claude UI thumbnails + chip preview.
  ~6-8 ч.

### Wave 4 (финал)

- **P2** Pitch deck — после того как P5/P6/P7 settled, чтобы
  слайды показывали реальную модель. ~4-5 ч.

---

## 11. Открытые вопросы (до старта)

Прежде чем начать первый wave, ответы нужны на:

1. **P3 jurisdiction**: Estonia, Delaware, Cayman? Это важно для ToS
   термов и налоговой обвязки $MEEET.
2. **P5 caps**: предложенные $10/mo cloud cap для Pro — приемлемо,
   или хочешь $25/mo? Влияет на margin.
3. **P5 BYO key**: Pro user с своим Anthropic API key должен ли
   платить меньше ($9 вместо $19)? Standard SaaS practice — да.
4. **P6 MLM data migration**: keep alias 90 days, потом drop, или
   forever? Long-term aliases пухнут.
5. **P7 default role**: какая выбрана по умолчанию если operator
   skip'нул onboarding? Founder, Operator (composite), или ничего
   (без packs)?
6. **P8 vision provider preference**: Anthropic Claude как primary
   (лучше для UI/screenshots) или OpenAI gpt-4o как primary
   (дешевле, многоязычный)?

---

## 12. Deliverables checklist

| # | File / artefact |
|---|-----------------|
| P1 | \`docs/FAQ.md\`, \`experiments/neural-showcase-v3/src/components/FAQ.tsx\` (16 q), opt: \`deliverables/FAQ.docx\` |
| P2 | \`deliverables/TARS_Pitch_2026Q2.pptx\`, \`experiments/neural-showcase-v3/src/pages/Pitch.tsx\` |
| P3 | \`docs/SECURITY.md\`, \`docs/TERMS_OF_SERVICE.md\`, \`docs/PRIVACY_POLICY.md\`, footer routes \`/privacy\` \`/terms\` |
| P4 | \`docs/contracts/TARS_SUBDOMAIN.md\` |
| P5 | \`backend/core/entitlements/{tiers,limits,router}.py\`, \`tests/test_entitlements.py\`, frontend \`<BudgetWarning />\`, Pricing.tsx update |
| P6 | \`backend/core/domains/packs/entrepreneur/\` (rename), \`registry.py\` alias, frontend копи везде |
| P7 | \`backend/core/roles/\`, \`tests/test_roles.py\`, \`Onboarding.tsx\` overhaul, \`RoleEditor.tsx\`, \`Settings.tsx\`, cockpit role-switcher |
| P8 | \`backend/core/attachments/extractors.py\` (image OCR), \`orchestrator.py\` multimodal routing, \`tests/test_vision_routing.py\`, frontend image thumbnails |

---

*Документ останется актуальным до конца Phase M. Пометка ✅ в
\`AGENT_HANDOFF.md\` после каждого сданного P#.*
`;function c(){return n.jsx(e,{eyebrow:"07 / roadmap",title:"Phase M — what's next",lastReviewed:"2026-04-29",source:t})}export{c as Roadmap};
