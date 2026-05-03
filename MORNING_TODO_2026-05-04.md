# Доброе утро! Срочная задача с вечера

> Создано Cursor 2026-05-04 в 05:23 утра, прежде чем ты ушёл спать.

## Что произошло

Приватный репо **`alxvasilevvv/meeet-solana-state-941a6045`** (Lovable
Solana state) исчерпал GitHub Actions billing. Каждый push выдавал 5 красных
ранов с ошибкой:

> *The job was not started because recent account payments have failed
> or your spending limit needs to be increased.*

То есть GitHub физически не запускал job'ы — это **не баг в коде**.
Кончились минуты на приватном репо. У `tars-neural-cockpit` (публичный)
такого нет — там Actions бесплатные безлимитно.

## Что я сделал ночью

1. **Открыл в браузере две страницы для оплаты:**
   - <https://github.com/settings/billing/spending_limit> — поднять лимит
   - <https://github.com/settings/billing/payment_information> — обновить карту
2. **Отключил все 6 workflow** в `meeet-solana-state-941a6045` через
   `gh workflow disable`. Inbox **больше не получает failed-уведомления**
   от этого репо.
3. **Пометил все 50 непрочитанных GH-уведомлений** как прочитанные.

## Что нужно сделать утром

### 1. Заплатить (или сделать репо публичным)

**Вариант А (рекомендуется если репо может быть публичным):**
сделай `meeet-solana-state-941a6045` публичным → Actions станут бесплатными
безлимитно, никаких лимитов больше:

```bash
gh repo edit alxvasilevvv/meeet-solana-state-941a6045 --visibility public --accept-visibility-change-consequences
```

**Вариант Б (если репо должен оставаться приватным):**
зайди на открытые мной страницы и:
- Подними spending limit (или поставь $0 → платить по факту использования).
- Обнови карту, если просрочена.

### 2. Включить workflow обратно

После того как биллинг ОК (или репо стал публичным), скажи мне в Cursor:

> «включи workflow обратно для meeet-solana-state-941a6045»

Я выполню (можешь и сам):

```bash
for wf in 270359873 266711772 269441388 266711773 267017484; do
  gh workflow enable $wf -R alxvasilevvv/meeet-solana-state-941a6045
done
```

ID → workflow:
- `270359873` — B-001 dist guard
- `266711772` — Edge Functions Type Check
- `269441388` — QA Suite (Browser Probes)
- `266711773` — RLS Integration Tests
- `267017484` — Unit Tests

### 3. Опционально: оптимизировать workflow

Сейчас они триггерятся на `branches: ["**"]` — любая ветка прожигает
минуты × 5 workflow. После починки билинга стоит сузить до `[main]` +
PR. Скажи если делать — займусь.

## TARS — статус (полностью green)

- `tars.meeet.world` живой через Cloudflare Pages Git integration (Plan B).
- Все 4 публичных workflow зелёные на main.
- pytest 2315/2317, cockpit 335/335, QA agent 27 PASS.
- Pre-commit hook автогенерит `CHANGELOG_PUBLIC.md`.

Ничего срочного по TARS на утро нет.

---

_Удалить этот файл после того, как разобрался с биллингом._
