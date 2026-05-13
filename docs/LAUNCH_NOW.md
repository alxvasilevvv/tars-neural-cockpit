# Launch TARS v9.1.0 — what to do right now

> One-page operator handbook. ~5 minutes total.

---

## Шаг 1 — запусти один скрипт

```bash
cd ~/Documents/Claude/Projects/Jarvis/jarvis
bash scripts/launch-v9.1.0.sh
```

Что он сделает (с подтверждением каждого шага):

1. Проверит чистоту репо
2. Запушит `main` (мои Waves 129-139)
3. Удалит протухший `v9.1.0` тэг (он на коммите 9-дневной давности)
4. Поставит свежий `v9.1.0` на текущий HEAD
5. Запушит тэг → стартует CI релиз-сборка `.dmg`/`.app`/`.msi`/`.nsis`/`.deb`/`.AppImage`

Если упадёт — скажет где. Большая часть кейсов: `TAURI_SIGNING_PRIVATE_KEY` отсутствует в GitHub Secrets. Лечится:

```bash
bash desktop/scripts/generate-release-keys.sh
# выведет два значения — скопируешь в GitHub → Settings → Secrets → Actions:
#   TAURI_SIGNING_PRIVATE_KEY
#   TAURI_SIGNING_PRIVATE_KEY_PASSWORD
# затем заново: bash scripts/launch-v9.1.0.sh
```

---

## Шаг 2 — Cloudflare custom-domain (B-019, 30 секунд)

В браузере Cloudflare dashboard:

1. **Workers & Pages → `tars-meeet` → Custom domains** → рядом с `tars.meeet.world` нажать **Remove**.
2. **Workers & Pages → `tars-meeet-git` → Custom domains** → **Set up a custom domain** → ввести `tars.meeet.world` → **Activate**.

Проверка:

```bash
curl -s https://tars.meeet.world/api/product/version | jq .version
# должно вернуть: "9.1.0"
```

---

## Всё.

После шагов 1 + 2:
- `.dmg` лежит в GitHub Releases
- `tars.meeet.world` отдаёт текущий `main` (с моей сегодняшней работой)
- Установщик доступен через `tars.meeet.world/dl/TARS_9.1.0_arm64.dmg`

---

## Если что-то пошло не так

Кидай сюда:
- URL упавшего GitHub Actions run, или
- Текст ошибки от `bash scripts/launch-v9.1.0.sh`, или
- Скриншот Cloudflare если шаг 2 не понятен

Разберу.

---

## Опциональное (можно потом, не блокирует)

- **Apple Developer cert** → `docs/handoff/APPLE_SIGNING_FOR_CURSOR.md` (~15 мин, убирает Gatekeeper warning на macOS, но `install.sh` уже снимает quarantine xattr — соцпсихологически приятно, технически опционально).
- **`GITHUB_RELEASE_TOKEN` в Cloudflare** → активирует same-origin `/dl/<file>` без 503 fallback на GitHub Release URL.
- **Брат запиливает `/api/cowork/*`** → `docs/handoff/COWORK_WIRING_FOR_CURSOR.md` (~30 мин FastAPI), активирует живой Cowork (mock в desktop сейчас, backend module уже работает).

---

## Что в продукте на сегодня

| Что | Готовность |
| --- | ---------- |
| Backend (Cowork + cohort + webhooks + receipts + scheduler + compliance_export + marketplace + bundles + workspaces) | ✅ 9/9 модулей загружаются, 38 cowork pytest зелёные |
| Desktop Tauri app | ✅ v9.1.0 в tauri.conf, 6 bundle targets, статика в `desktop/src-tauri/web/` |
| Orchestrator → Cowork hook | ✅ `runner.py` стримит `task.{started,completed,failed}` если есть `cowork_session_id` |
| Release pipeline | ✅ Apple — опционально (ad-hoc fallback), только `TAURI_SIGNING_PRIVATE_KEY` обязателен |
| Marketing SPA | ❌ удалён 2026-05-13 (Cursor решение, API-first pivot). Live `tars.meeet.world` обслуживается Cloudflare Pages Git build из `tars-meeet-git`. |
