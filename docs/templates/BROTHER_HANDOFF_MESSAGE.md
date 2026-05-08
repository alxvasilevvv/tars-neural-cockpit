# Brother handoff message templates

Скопируй один из вариантов ниже (зависит от канала / стиля), отправь брату.

---

## Вариант 1 — короткий (Telegram / iMessage)

> Привет. Я закрыл свою сторону интеграции TARS, нужно чтобы ты закрыл свою на стороне meeet.world / Lovable.
>
> Полный документ:
> https://github.com/alxvasilevvv/tars-neural-cockpit/blob/main/docs/INTEGRATION_FOR_BROTHER.md
>
> В нём раздел "Коротко — ОДИН раз посмотри" — 5 пунктов на минуту чтения. Сначала её.
>
> P0 для launch:
> 1. DNS `tars.meeet.world` → твой edge
> 2. 3 secrets синкнуть (BRIDGE_SHARED_SECRET, MEEET_BILLING_API_KEY, TARS_INGEST_API_KEY)
> 3. 2 endpoints: GET /operator + POST /operator/usage на функции `tars-billing`
> 4. 2 страницы: /billing/tars?plan=… + /account
> 5. Cookie `meeet_session` с Domain=.meeet.world
>
> Когда закроешь — пинг, прогоню `make gate-control-tower` end-to-end.

---

## Вариант 2 — формальный (email)

**Subject:** TARS интеграция — твоя сторона: 5 пунктов до launch

Привет.

Закрыл вечером всю свою сторону интеграционного контура TARS ↔ meeet.world. Backend готов, desktop app собирается, документация в порядке. Сейчас всё что мешает запустить — твоя сторона на meeet.world / Lovable Supabase.

Полная спека (565 строк, всё в одном месте):
https://github.com/alxvasilevvv/tars-neural-cockpit/blob/main/docs/INTEGRATION_FOR_BROTHER.md

Если нет времени читать всё — листай в самый конец, там секция **"Коротко — ОДИН раз посмотри"** с 5 пунктами.

**P0 минимум для launch:**

1. **DNS + SSL** — `tars.meeet.world` CNAME на твой meeet-app или отдельный edge. Wildcard `*.meeet.world` должен покрывать.

2. **3 shared secrets** — generate и синкни между собой → Supabase function secrets, мой `.env`, GitHub Actions secrets:
   - `BRIDGE_SHARED_SECRET`
   - `MEEET_BILLING_API_KEY` (на edge называется `TARS_BILLING_API_KEY`)
   - `TARS_INGEST_API_KEY`

3. **`tars-billing` Edge Function** на проекте `zujrmifaabkletgnpoyw`:
   - `GET /operator` — возвращает `{tier, byo_enabled, live, checkout, account_url}`
   - `POST /operator/usage` body `{delta_usd, trace_id}` — idempotent через `trace_id` (`tars_billing_usage_dedupe` table)
   - Auth: `Authorization: Bearer <MEEET_BILLING_API_KEY>`
   - Полный wire-format: `docs/contracts/TARS_MEEET_BILLING.md`

4. **Две страницы на meeet.world:**
   - `/billing/tars?plan=pro|business` — checkout (платежи в SOL/$MEEET через твою существующую инфру)
   - `/account` — профиль с tier + balance (это уже есть наверное, просто убедись)

5. **Cookie domain** — `meeet_session` должен быть с `Domain=.meeet.world` (с точкой!) чтобы расшарить session между meeet.world и tars.meeet.world.

**Smoke procedure** (когда закончишь, я прогоню с моей стороны):

```bash
make smoke-billing-tars       # билинг отвечает
make smoke-core-bridge        # bridge отвечает
make gate-control-tower       # full e2e
```

Если что-то падает — дам тебе точную ошибку, разберёмся.

После того как P0 закрыт — запускаем launch. P1 пункты (magic-link, OAuth bridge, unified_funnel view) можно дописывать неделями после launch.

В этом же документе есть раздел секций по каждой точке интеграции — там всё детально. И полный launch checklist в конце — что готово, что нет.

Скажи если что не понятно. Жду твоего ОК чтобы тегнуть v9.1.0.

Спасибо.

---

## Вариант 3 — voice memo / звонок (talking points)

Если хочешь обсудить голосом — вот пункты:

1. **Где документ** — github.com/alxvasilevvv/tars-neural-cockpit, файл docs/INTEGRATION_FOR_BROTHER.md
2. **Что от него** — поднять `tars.meeet.world` сабдомен + два endpoint'а на edge function
3. **Сроки** — желательно сегодня-завтра, я хочу тегнуть v9.1.0 в выходные
4. **Что синкнуть** — три секрета (генерим вместе по openssl)
5. **Что я покрою** — code signing (Apple + Windows), CI билды, marketing анонс
6. **Что он покрывает** — DNS, edge functions, billing pages, OAuth bridge (P1)
7. **Smoke когда готов** — `make gate-control-tower`, я прогоняю с моей стороны
8. **Tag release** — после его ОК делаю `git tag v9.1.0 && git push origin v9.1.0`, CI собирает signed artifacts ~30 минут

---

## Что НЕ говорить брату (важно для безопасности)

❌ Не отправляй секреты через email/Telegram/iMessage прямым текстом.
✅ Используй: Signal, 1Password sharing link, encrypted note в Apple Notes shared.

❌ Не публикуй секреты в GitHub Issue / Slack / любой публичный канал.
✅ Только direct channel ↔ direct channel.

❌ Не упоминай конкретные значения секретов в этом message.
✅ Просто скажи "сейчас вышлю отдельно через Signal".
