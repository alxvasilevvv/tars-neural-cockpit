# Go-live — 48h runbook (TARS · tars.meeet.world)

> **Цель:** зафиксировать публичный запуск уже сегодня и добить наблюдаемость /
> SEO / backend-bridge завтра без хаоса.  
> **Контекст:** `docs/TARS_MEEET_OPS_TODO.md` (инфра), `docs/TARS_MEEET_READINESS.md` (gates).

---

## Факт-снимок «прямо сейчас»

Последняя автоматическая проверка показала:

- `https://tars.meeet.world/` → **HTTP 200**, `X-Tars-Contract: 1.0.0`
- `Set-Cookie: tars_session_id=…; Domain=.meeet.world` (правильный scope)
- `GET /api/product/downloads` → JSON, `contract_version: 1.0.0`, `releases[]` не пустой
- Маркетинговые SPA-маршруты (`/install`, `/pricing`, `/faq`, `/compare`, `/cockpit`, `/onboarding`) → **HTTP 200** (нет ловушки `404.html`)

Скрипт: из корня репозитория

```bash
SKIP_LIGHTHOUSE=1 SKIP_AXE=1 bash scripts/acceptance_tars_meeet.sh
```

Без `BRIDGE_SHARED_SECRET` шаги 5–6 помечаются **SKIP** (это ожидаемо до вставки секрета на Pages).

---

## Сегодня (день 0) — «мы в эфире»

| # | Кто | Действие |
|---|-----|----------|
| 1 | Cursor / CI | Убедиться, что на `main` зелёный workflow **tars.meeet.world — Cloudflare Pages** (build + tests). При необходимости: *Actions → Run workflow*. |
| 2 | Оператор | **Cloudflare Pages → проект с `tars.meeet.world` → Settings → Environment variables → Production** — добавить **`BRIDGE_SHARED_SECRET`** (тот же, что на `core-bridge` в Supabase). **Save and deploy.** |
| 3 | Оператор | Локально: `BRIDGE_SHARED_SECRET="…" bash scripts/acceptance_tars_meeet.sh` — должны пройти и мостовые гейты. Затем `BRIDGE_SHARED_SECRET="…" make qa-agent` (ожидаем меньше SKIP / WARN). |
| 4 | Оператор | Опционально: `make ops-bridge-secret` (склеивает CF Pages env + редеплой, см. `Makefile` и `TARS_MEEET_OPS_TODO.md`). |
| 5 | Коммуникации | Опубликовать каноническую ссылку: **https://tars.meeet.world** (лендинг + `/install` + кокпит как маркетинговый shell). |

**Не блокирует go-live:** Lighthouse/axe, native `.dmg`, полный ingest с бэкенда.

---

## Завтра (день 1) — «добить хвосты»

| # | Владелец | Действие |
|---|----------|----------|
| 1 | Оператор | **Backend (.env на хосте TARS API, не в git):** `MEEET_INGEST_URL`, `MEEET_API_KEY`, при необходимости `MEEET_SOURCE` / `MEEET_CONTRACT_VERSION` — см. `TARS_MEEET_OPS_TODO.md` § outstanding п.4. Проверка: `TARS_INGEST_API_KEY="…" make qa-agent` → `meeet.ingest_heartbeat` **PASS**. |
| 2 | Claude / Lovable | **Sitemap:** добавить URL-ы `https://tars.meeet.world/...` в публичный sitemap meeet.world (или отдельный sitemap + ping в Search Console). |
| 3 | Claude / Lovable | **Cookie auth:** убедиться, что `meeet_session` выставляется с `Domain=.meeet.world`, чтобы субдомен видел сессию (см. `TARS_MEEET_READINESS.md` §2.2). |
| 4 | Оператор | **Post-launch:** строка на `status.meeet.world` для `tars.meeet.world` (некритично). |
| 5 | Оператор | **Desktop:** когда будут ключи подписи — релиз по `docs/LAUNCH_TODAY_2026-05-01.md` §4 (не обязателен для web go-live). |

---

## Быстрые команды

```bash
# Приёмочные пробы прод (Mac / Linux)
cd /path/to/jarvis
SKIP_LIGHTHOUSE=1 SKIP_AXE=1 bash scripts/acceptance_tars_meeet.sh

# С секретом моста (после шага Pages)
BRIDGE_SHARED_SECRET="..." bash scripts/acceptance_tars_meeet.sh

# Smoke core-bridge (нужен тот же секрет)
BRIDGE_SHARED_SECRET="..." make smoke-core-bridge

# QA-agent (heartbeat ingest — после настройки API key)
TARS_INGEST_API_KEY="..." make qa-agent
```

---

## Синк между агентами

После выполнения **дня 0** п.2–3 оставить одну строку на GitHub **[tars-neural-cockpit#8](https://github.com/alxvasilevvv/tars-neural-cockpit/issues/8)**  
и при желании добавить запись в `docs/CHANGELOG_AGENTS.md`.

Файл обновлять по факту: дата выполнения шагов, не раньше.
