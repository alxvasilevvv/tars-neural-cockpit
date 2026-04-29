# Перенос на второй компьютер + GitHub + meeet.world

Документ для **оператора** и для **Claude Code** на новой машине: распаковать
репозиторий, поднять окружение, связать интеграцию с **`meeet.world`**, не
слить секреты в git.

Этот файл можно **передавать вместе с репозиторием** (USB, AirDrop, архив —
достаточно актуальной ветки; секреты — отдельно).

---

## 0. Принимающая машина должна содержать

| Компонент | Зачем |
|-----------|--------|
| **Git** | Клонирование и дальнейшая работа с GitHub. |
| **Python ≥ 3.12** рекомендован для pip-замков в `requirements.txt` | Backend, pytest. |
| **Node.js 20+** и **npm** | `experiments/neural-showcase-v3` (Vite/React). |
| **Claude Code** (официальный CLI) | Сессии с локальным репозиторием; читает `CLAUDE.md` в корне. |
| **SSH ключ или HTTPS + PAT** для GitHub | `git push` / `git pull` под вашим аккаунтом. |

Опционально: **Rust** (если собираете Tauri десктоп из `desktop/`), **cloudflared**
(временный публичный URL для демо, см. `scripts/preview-demo-tunnel.sh`).

---

## 1. Структура проекта (ожидаемые пути)

Канонический корень кода TARS — вложенная папка **`jarvis/`** внутри клона
(исторически путь вида `…/Jarvis/jarvis/`). Все относительные команды ниже
предполагают **текущий каталог = этот `jarvis/`**.

Файлы контекста для агентов (читать по порядку при первом запуске):

1. `CLAUDE.md` — контекст продукта и границы кода.
2. `docs/AGENT_HANDOFF.md` — текущее состояние и приоритеты.
3. `docs/CHANGELOG_AGENTS.md` — журнал правок агентов.
4. `docs/contracts/README.md` — соглашения по wire-форматам между TARS и
   **meeet.world**, маркетингом и десктопом.

---

## 2. Клонирование и ветки

Рекомендуемый перенос: **голый Git**, не только ZIP архива без `.git`:

```bash
git clone <URL_репозитория_ON_GITHUB.git>
cd <repo>/Jarvis/jarvis   # путь может отличаться; цель — папка с CLAUDE.md
git checkout main           # или master — как принято у вас
git pull origin main
```

Если офлайн передали только tarball: распакуйте так же, добавьте `remote`:

```bash
git remote add origin <URL>
git fetch origin
git branch --set-upstream-to=origin/main main
```

---

## 3. Python backend (venv)

```bash
cd /path/to/jarvis   # каталог с requirements.txt и CLAUDE.md
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

Проверка:

```bash
pytest -q
```

Ожидание: тесты проходят (число может расти; «0 failed» — критерий).

---

## 4. Переменные окружения (без коммита в git)

1. Скопируйте шаблон:

   ```bash
   cp .env.example .env
   ```

2. Заполните **только на этой машине** (или возьмите переносимый сейф:
   1Password / Apple Notes с шифрованием — **не** вложение в общий архив без
   шифрования):

   | Переменная | Назначение |
   |------------|-------------|
   | `MEEET_INGEST_URL` | URL POST ingest **meeet.world**; если пусто — мост в no-op режиме, но трассировка в коде идёт. |
   | `MEEET_API_KEY` | Bearer для ingest (если требует сторона ingest). |
   | `MEEET_CONTRACT_VERSION` | Должна совпадать с тем, что принимает ingest (часто документируется в `tests/test_meeet_contract*.py` и изменениях в `docs/CHANGELOG_AGENTS.md`). |
   | `MEEET_SOURCE` | Идентификатор источника (по умолчанию `tars`). |
   | `MEEET_LOCAL_LOG` | Файл NDJSON для офлайна и последующего `replay_cli`. |

Реальные значения **не** добавляются в репозиторий; `.gitignore` уже содержит
`.env`.

---

## 5. Showcase (frontend, Vite)

```bash
cd experiments/neural-showcase-v3
cp .env.example .env.development.local   # или .env.local — оба в gitignore по шаблону *.local
npm ci
npm run typecheck
npm run test
npm run build
```

`VITE_TARS_API` должен указывать на ваш backend (часто `http://127.0.0.1:8765/api`
— уточните по фактическому mount API в `web_extras/`).

---

## 6. GitHub: отправка изменений и CI

Что нужно выполнить **один раз на аккаунте / в репозитории** (делает владелец):

- **Secrets** в Settings → Secrets (если workflow требует — подписание релизов,
  токены к tap и т.д. см. заголовки в `.github/workflows/*.yml`).
- **GitHub Pages** для статической витрины Showcase: если используете
  `.github/workflows/cockpit-github-pages.yml` — включить источник
  **GitHub Actions** в Settings → Pages.

Локально перед пушем:

```bash
git status
git add -p
git commit -m "…"
git push origin <ветка>
```

---

## 7. Интеграция в meeet.world — что держать в голове

| Документ / код | Роль |
|----------------|------|
| `docs/contracts/` | Замороженные wire-контракты; синхрон с маркетингом и приложением **meeet**. |
| `docs/contracts/TARS_SUBDOMAIN.md` | Спека для **`tars.meeet.world`**: роутинг, прокси `api/product/downloads`, связка аккаунта и ingest. Строит «братний» прод meeet-app / инфра. |
| `backend/core/meeet/config.py` | Официальный список переменных `MEEET_*`. |
| `web_extras/routers/domains.py` | Действия доменов оборачиваются в `trace_scope` и уходят в ingest при настроенном URL. |

Порядок интеграции с облаком (типичный):

1. Получить от команды meeet **stage/prod ingest URL** и требования к ключу.
2. Выставить совпадающий **`MEEET_CONTRACT_VERSION`**.
3. Прогнать pytest и ручной smoke на стороне TARS.
4. Согласовать с инфрой **поддомен и прокси** по `TARS_SUBDOMAIN.md`.

---

## 8. Claude Code и skills (UI)

- Глобально по желанию: `uipro init --ai claude --force` (skill **ui-ux-pro-max**).
- Проектные копии skill лежат в `.claude/skills/` в репозитории (если есть).
- Не дублируйте секреты в промптах Claude — используйте `.env` и локальные tools.

---

## 9. Чеклист «миграция завершена»

- [ ] `pytest` проходит в активированном venv.
- [ ] `experiments/neural-showcase-v3`: `npm run build` без ошибок.
- [ ] `.env` создан из `.env.example`, секреты не в git.
- [ ] `git remote -v` указывает на нужный GitHub.
- [ ] Прочитаны `CLAUDE.md`, `docs/AGENT_HANDOFF.md`, верх `docs/contracts/README.md`.
- [ ] Для облака: известны `MEEET_INGEST_URL` и живая версия контракта.

---

## 10. Что положить на флешку / в зашифрованный архив (если без сети)

Содержимое:

- Актуальный **git bundle** или полный клон `.git` + рабочие деревья.
- Отдельно (зашифровано): копия **`.env`**, SSH **приватный ключ** или
  инструкция создать новый ключ и добавить в GitHub.

Не кладите в открытый архив: API-ключи ingest, PAT с широкими правами, пароли
Apple Developer.

---

## 11. Индекс для Claude на новой машине (копипаста в первый чат)

```
Репозиторий TARS (jarvis) только что развернут на этой машине.
Прочитай по порядку: CLAUDE.md, docs/AGENT_HANDOFF.md, docs/SECOND_MACHINE_HANDOFF.md.
Выполни проверки из раздела 9 чеклиста SECOND_MACHINE_HANDOFF.md.
Не коммить .env. Контракты с meeet.world: docs/contracts/ и backend/core/meeet/.
```

После этого Claude может сам доустановить зависимости и поправить пути под ОС,
если что-то отличается от инструкции.
