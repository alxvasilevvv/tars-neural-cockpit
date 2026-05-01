# LAUNCH TODAY — 2026-05-01 status

> One-shot snapshot собран Cursor-агентом во второй половине дня
> 2026-05-01. Проверено всё что можно проверить локально; всё, что
> требует production-секретов, помечено и оставлено в "то-do для
> оператора".

## Что подтверждено сегодня (локально, факт)

### TARS backend (`web_extras/app:app`, port 8765)

- `python3.12 -m uvicorn web_extras.app:app` — стартует чисто, **108
  routes**.
- `pytest -q` → **686 passed in 15.23s** (включая `test_domains`,
  `test_meeet*`, `test_council`, `test_policy`, `test_playbooks`,
  `test_awareness*`, `test_real_adapters`).
- HTTP smoke matrix:
  - `/api/domains` — 200
  - `/api/domains/manifest` — 200
  - `/api/usage` — 200
  - `/api/playbooks` — 200
  - `/api/policy/recent` — 200
  - `/api/meeet/stats` — 200
  - `/api/council/voices` — 404 (роутера нет; есть `POST
    /api/council/deliberate`). Не критично, но фронт может ловить —
    проверить `experiments/neural-showcase-v3/src/lib`.

### TARS cockpit (`experiments/neural-showcase-v3`)

- `npm run build` — чисто, **3.17s**, артефакты в `dist/`.
- `npx vite preview --port 5174` → 200 на `/`.
- ENV: `VITE_TARS_API=http://127.0.0.1:8765` для `.env.local`,
  `https://tars.meeet.world` для `.env.production`.

### TARS desktop (Tauri 2)

- `desktop/src-tauri/target/` уже инициализирован — Rust toolchain в
  порядке. Полный `pnpm release` сегодня **не запускал** (5–15 мин на
  холодный кэш и блокирует чат). Готово к запуску оператором.

### meeet.world frontend (`meeet-solana-state-941a6045`)

- `npm run build` — **5.59s**, prod бандл в `dist/` (warning на
  WorldMap/index — не блокирует).
- `npx serve dist -l 8083` → 200 на `/`.
- `npm test` — **336 passed | 5 skipped** (15 файлов).
- `SOFT_SMOKE=1 bash scripts/smoke_release_gate.sh` → **GATE PASSED**
  (tars-downloads check OK, ingest и core-connectivity скипнуты без
  секретов — ожидаемо для локальной машины).
- Все открытые PR смёржены или закрыты как дубли:
  - **#10** i18n sweep — squash-merged
  - **#11** qa-suite api.core-rest — squash-merged
  - **#7** control-tower + bridge hardening — squash-merged
  - **#3** docs agent-handoff — squash-merged
  - **#6**, **#9** — закрыты как superseded.
- `gh pr list --state open` для repo пустой.

## Чтобы реально запустить пользователей сегодня — нужно от тебя

Я не могу выполнить шаги, требующие приватных ключей или CLI-логина в
твои аккаунты. Список минимальный:

1. **Supabase Edge Functions деплой (meeet.world)**

   ```bash
   cd /Users/alien/Documents/Claude/Projects/meeet-solana-state-941a6045
   supabase login          # если ещё не логинился
   supabase functions deploy entitlements
   supabase functions deploy deploy-agent
   ```

   Без этого `Deploy.tsx` будет дёргать несуществующую функцию, и
   on-chain checkout не пройдёт.

2. **Выкатить frontend meeet.world.** Lovable-проект подвязан к
   `main`; push уже произошёл (PR #3, #7, #10, #11 смёржены). Если
   автодеплой включён — проверь `meeet.world` через 2–3 минуты после
   последнего push. Если нет — кликни Deploy в Lovable.

3. **TARS landing + cockpit на `tars.meeet.world`.**
   - `cd experiments/neural-showcase-v3 && npm run build`
   - GitHub Actions workflow `cockpit-github-pages.yml` уже
     настроен — нужен push в `main` репозитория TARS (он на
     `Jarvis/jarvis` сейчас локальный; PR #34 уже смержен).
   - DNS: `CNAME tars.meeet.world → <github-pages-host>` + добавить
     `tars.meeet.world` в Pages settings репозитория.

4. **TARS desktop binary (опционально для запуска "сегодня").**

   ```bash
   cd /Users/alien/Documents/Claude/Projects/Jarvis/jarvis/desktop
   bash scripts/generate-release-keys.sh   # один раз
   gh secret set TAURI_PRIVATE_KEY < .keys/tars.key
   gh secret set TAURI_KEY_PASSWORD <<< '<password>'
   pnpm release                            # macOS dmg + Windows msi
   ```

   Без этого пользователи получат только web-cockpit; native binaries
   подождут.

5. **Секреты для прод-канала event-логирования**

   - `MEEET_INGEST_URL` (`https://meeet.world/api/ingest`)
   - `MEEET_API_KEY`
   - `TARS_INGEST_API_KEY` (для cross-проверки бриджа)
   - `BRIDGE_SHARED_SECRET` (для `gate-control-tower` без SOFT_SMOKE)

   Положить в `.env` каждого репозитория. **Не коммитить.**

## Что я вернул в репозитории за этот заход

- `meeet-solana-state-941a6045`: смержил 4 PR (см. выше), пересобрал
  i18n-конфликт и чистил пакет смоук-скриптов в `package.json`.
- `Jarvis/jarvis`: PR #34 (qa-loop + meeet-ingest heartbeat) уже на
  `main`. Этот файл — единственное добавление сегодня.

## Команды быстрого старта (для оператора)

```bash
# TARS backend
cd /Users/alien/Documents/Claude/Projects/Jarvis/jarvis
PYTHONPATH=. .venv/bin/uvicorn web_extras.app:app \
  --host 127.0.0.1 --port 8765 --log-level info

# Cockpit (preview готового бандла)
cd experiments/neural-showcase-v3
npx vite preview --port 5174 --host 127.0.0.1
# → http://127.0.0.1:5174

# meeet.world dist локально
cd /Users/alien/Documents/Claude/Projects/meeet-solana-state-941a6045
npx serve dist -l 8083
# → http://127.0.0.1:8083

# Smoke-gate (прод сетевой канал, без секретов)
SOFT_SMOKE=1 bash scripts/smoke_release_gate.sh
```

## Известные мелочи (не блокеры)

- WorldMap бандл meeet.world ~989 KB — code-split позднее.
- Cockpit `physics-*.js` 1.98 MB — три-вендор, ленивая подгрузка.
- `/api/council/voices` отсутствует на TARS API; фронт использует
  `POST /api/council/deliberate` напрямую.
- meeet.world `npx serve` стартует с предупреждением про
  глобальный install — игнорировать.
