# Go-live — same-day closeout (`tars.meeet.world`)

> **Цель:** закрыть весь контур **сегодня**: публичный фронт уже live; остаётся
> вставить секреты, прогнать приёмку и (по желанию) подключить ingest.  
> Полная инфра-история: `docs/TARS_MEEET_OPS_TODO.md`, гейты:
> `docs/TARS_MEEET_READINESS.md`.

---

## Уже в репозитории (код)

- Отдельные маршруты **`/pricing`**, **`/faq`**, **`/compare`** — не 404 SPA, те же
  секции что на `/`, плюс корректный document title (SEO / шаринг).
- `public/sitemap.xml` включает эти URL.
- QA agent (`scripts/qa_agent/probes.py`) проверяет их как **HTTP 200** на проде.
- Workflow **TARS QA Agent** передаёт опциональный секрет **`TARS_INGEST_API_KEY`**
  (добавь в GitHub → *Settings → Secrets → Actions*, чтобы
  `meeet.ingest_heartbeat` стал **PASS**, а не WARN).

---

## Факт-снимок прода (проверка за 30 сек)

```bash
SKIP_LIGHTHOUSE=1 SKIP_AXE=1 bash scripts/acceptance_tars_meeet.sh
```

Ожидаемо жёлтые **SKIP** на мостовых шагах, пока не задан локальный
`BRIDGE_SHARED_SECRET` для скрипта.

---

## Чеклист оператора — всё сегодня

| # | Задача | Как |
|---|--------|-----|
| **A** | **`BRIDGE_SHARED_SECRET` на Cloudflare Pages (Production)** | Dashboard → Pages → проект с доменом `tars.meeet.world` → *Environment variables* → добавить секрет → **Save and deploy**. Либо один раз: см. ниже `make ops-bridge-secret`. |
| **B** | **Тот же секрет в GitHub** | Уже делает `make ops-bridge-secret` **или** вручную: *Repo → Settings → Secrets → `BRIDGE_SHARED_SECRET`*. |
| **C** | **Приёмка с мостом** | `BRIDGE_SHARED_SECRET="…" bash scripts/acceptance_tars_meeet.sh` → зелёный, без SKIP на шагах 5–6. |
| **D** | **`make qa-agent` локально** | `BRIDGE_SHARED_SECRET="…" TARS_INGEST_API_KEY="…" make qa-agent` — максимум PASS. |
| **E** | **`TARS_INGEST_API_KEY` в GitHub** | Тот же ключ, что **`TARS_INGEST_API_KEY`** / bearer для Supabase **`tars-ingest`**. После этого QA workflow на CI даёт зелёный heartbeat. |
| **F** | **Backend (если поднимаешь API с логированием)** | В **`.env`** (не в git): `MEEET_INGEST_URL`, `MEEET_API_KEY` — см. корневой `.env.example`. |
| **G** | **Lovable / meeet.world (параллельно)** | Cookie `meeet_session` с `Domain=.meeet.world`; sitemap главного домена дополнить URL TARS или отдельная запись в Search Console на `https://tars.meeet.world/sitemap.xml`. Не блокирует открытие TARS-сайта. |
| **H** | **Анонс** | Канон: **https://tars.meeet.world**, установка **/install**. |

### Один-shot мост (нужны `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`)

```bash
cd /path/to/jarvis   # корень репозитория TARS
export CLOUDFLARE_API_TOKEN=...
export CLOUDFLARE_ACCOUNT_ID=...
# если API/project name не `tars-meeet`:
# export PAGES_PROJECT_NAME=tars-meeet-git
make ops-bridge-secret   # секрет stdin — см. скрипт
```

Затем вручную (если ещё не сделано): **`gh secret set TARS_INGEST_API_KEY`** с ключом ingest.

---

## После выполнения

Одна строка на **[tars-neural-cockpit#8](https://github.com/alxvasilevvv/tars-neural-cockpit/issues/8)**  
(`BRIDGE ✓ ingest ✓ qa-agent ✓`).
