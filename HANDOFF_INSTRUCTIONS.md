# TARS handoff package — v9.x · launch-ready

Этот архив — полный канонический snapshot репозитория TARS на момент закрытия Wave 47 (29 апреля 2026). Backend (P5/P6/P7/P8), фронт-маркетинг и кокпит готовы к публичному launch на `tars.meeet.world`.

Читай этот файл первым. Дальше — `docs/AGENT_HANDOFF.md` (секция "Latest snapshot — waves 32-45") и `docs/CHANGELOG_AGENTS.md` (последние записи).

---

## TL;DR — что нужно сделать

1. **Распаковать**, изучить структуру
2. **Закоммитить untracked-файлы** (есть batch от Claude который Cursor не подбирал — детали ниже)
3. **Создать GitHub repo** `meeet-world/tars` (или другое имя), сделать первый push
4. **Настроить DNS/Pages** для `tars.meeet.world` → GitHub Pages artifact
5. **Прогнать lighthouse + axe** на staging deploy
6. **Public launch**

---

## 1. Структура

```
jarvis/
├── backend/                    # P5/P6/P7/P8 shipped, Python
│   └── core/
│       ├── domains/            # 4 packs + composites
│       ├── entitlements/       # tiers, checker, 402 enforcement
│       ├── roles/              # registry, custom-role synthesis
│       ├── attachments/        # P8 ingest pipeline
│       └── meeet/              # event store, contract 1.1.0
├── web_extras/                 # FastAPI app
│   ├── app.py                  # CORS allows tars.meeet.world (+ TARS_CORS_ORIGINS)
│   └── routers/                # entitlements, roles, pairing, chat, domains, etc
├── experiments/
│   └── neural-showcase-v3/     # ⭐ React + Tailwind v4 + framer-motion (production marketing/cockpit)
│       ├── src/                # 0 TS errors, всё через useT() для canonical EN copy
│       ├── public/             # 8 OG SVG, favicon, badge variants, PWA manifest
│       ├── .env.example
│       └── .env.production     # VITE_TARS_API=https://tars.meeet.world
├── docs/                       # AGENT_HANDOFF, CHANGELOG_AGENTS, контракты, ТЗ
├── tests/                      # pytest suites — domains, manifest, CORS, replay
├── .github/workflows/
│   └── cockpit-github-pages.yml  # автомат: push в main → build → deploy на Pages
├── .cursorrules                # Cursor agent rules
├── .claude/                    # Claude agent rules
└── .gitignore
```

---

## 2. Что нужно докоммитить (важно)

Cursor написал в последнем апдейте:

> "Очень много untracked-файлов от Claude (роутеры `entitlements`, `roles`, `wallet`, `chat`, `pairing` и десятки тестов) — они работают локально, но не закоммичены. Это его батч; принудительно подбирать в свой коммит не стал."

Это значит — после `git init` или при первом коммите в фрешном репо нужно осмотреть список:

```bash
cd jarvis/
git status --short          # увидишь untracked
git diff --stat HEAD        # если репо свежий — пропускай
```

Эти файлы **рабочие, протестированные** (P5/P6/P7/P8 endpoint'ы вокруг них и frontend live-wired). Их нужно подобрать в первый коммит. Просто:

```bash
git add -A
git commit -m "feat: pre-launch snapshot — TARS v9.x

P5 entitlements + budget gate (free/pro/business, 402 enforcement)
P6 entrepreneur pack canonical, MLM deprecated until 2026-07-29
P7 6 built-in roles + custom-role synthesis with overlay
P8 vision pipeline + OCR opt-in
L5 pairing (begin/accept/reject/status/devices/revoke/identity)
Frontend: BudgetWarning, Onboarding wizard, Status page all live-wired.
i18n stripped to EN-only (useT() preserved as canonical copy dict)."
```

---

## 3. Push в GitHub

Cursor не делает push без явного разрешения (safety rule). После того как ты создашь repo и скажешь "go" — он сделает либо ты сам:

```bash
# создать пустой repo на github.com сначала (без README/license — иначе конфликт)
git remote add origin git@github.com:meeet-world/tars.git
git branch -M main
git push -u origin main
```

После первого успешного push — `cockpit-github-pages.yml` автоматически соберёт `experiments/neural-showcase-v3/dist/` и задеплоит на Pages артефакт.

---

## 4. DNS + custom domain → tars.meeet.world

В DNS провайдере (Cloudflare для meeet.world?):

```
Type:  CNAME
Name:  tars
Value: <github-pages-domain>      # типа meeet-world.github.io
TTL:   auto
```

В GitHub repo → Settings → Pages → Custom domain → `tars.meeet.world` → Save → дождаться TLS → enforce HTTPS.

Если хост не GitHub Pages а Lovable / Vercel / Cloudflare Pages — соответствующая настройка через их UI. `dist/` Vite-билда совместим со всеми статическими хостингами.

Проверка:
```bash
curl -I https://tars.meeet.world      # → 200 OK, Cloudflare/Pages headers
```

---

## 5. Lighthouse + axe аудит

Cursor добавил npm-скрипты — запустить против ЖИВОГО staging URL:

```bash
cd experiments/neural-showcase-v3
npm install
npm run audit:lighthouse    # → ./lighthouse.json
npm run audit:axe           # → exit 0 если a11y violations нет
```

Если есть P1 находки (a11y violations или performance < 80) — пинг Cursor / Claude, закроют. P2/P3 — backlog после launch.

---

## 6. Локальный smoke test (опционально перед deploy)

```bash
# backend
cd jarvis/
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m web_extras.app                # → http://127.0.0.1:8765
# в другом терминале:
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:8765/api/entitlements
curl http://127.0.0.1:8765/api/roles
curl http://127.0.0.1:8765/api/domains | jq '.domains[] | {slug, deprecated}'

# frontend
cd experiments/neural-showcase-v3
npm install
npm run dev                              # → http://localhost:5173
# открыть /cockpit, /onboarding, /status, /pricing — всё должно жить
```

---

## 7. Что я (Claude) сделал в waves 32-47

Для контекста — за последний батч закрыто:

- **Frontend live-wire** к P5/P6/P7/P8 (BudgetWarning → /api/entitlements, Onboarding → /api/roles, Cockpit pack picker фильтрует deprecated, AttachmentChip OCR-индикатор)
- **Status page** честный пинг /health (с ms latency) + /api/entitlements (degraded когда cap hit)
- **Cockpit tour** — 6 шагов с шорткатами (⌘K / ⌘⇧W / Enter / Esc / Tab)
- **OnlineCounter** в receipts header, **SitemapGrid** на /docs
- **5 OG SVG** для /onboarding, /press (привязаны), /pricing, /faq, /compare (assets-ready, ждут edge-worker если нужно per-anchor serving)
- **i18n стрип** до EN-only — `useT()` оставлен как canonical copy dict, RU/ZH/ES/JA удалены, LocaleToggle снят с Nav
- **Static audit** mobile + light-theme + a11y — 7 фиксов (CockpitTour padding, BudgetWarning color tokens, Status boxShadow color-mix, aria-hidden на decorative icons)

`npx tsc --noEmit -p tsconfig.app.json` — 0 errors на каждой волне.

Полный лог — `docs/CHANGELOG_AGENTS.md`, последние 6-7 записей.

---

## 8. Быстрые контакты для вопросов

- **Backend / API контракт** — Cursor (роутеры, тесты, meeet bridge)
- **Frontend / маркетинг** — Claude (showcase v3, копирайт, дизайн)
- **Infra / DNS / deploy / Lovable** — твоя зона

Если что-то не работает после deploy:

1. Проверь `Status` page — она честно показывает что отвалилось (daemon? entitlements? манифест?)
2. Проверь CORS если frontend на одном origin а backend на другом
3. `VITE_TARS_API` в `.env.production` смотрит на правильный backend host

---

**Green light** на public launch после: первого `git push` → automated deploy → DNS пропагирован → lighthouse аудит без P1.

Все техдолги закрыты. Удачи.
