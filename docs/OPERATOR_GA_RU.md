# TARS v10.0.0 GA — операторский чеклист (RU)

Краткая версия для возврата после сна. Полная цепочка: `docs/W310_WAVE_SUMMARY.md` (TLDR вверху).

## Одна команда — статус

```bash
cd /Users/alien/Documents/Claude/Projects/Jarvis/jarvis
make ga-status
# или: bash scripts/CURSOR-GA-STATUS.command
```

**Exit 0** = можно резать тег (если soak 72h уже набран). **Exit 1** = есть красные блокеры.

## Что уже зелёное (код + brother)

- `make test` — тысячи pytest, зелёные
- Cockpit e2e — 7 сценариев Playwright
- `BROTHER-PREFLIGHT` — PROCEED (meeet.world мост)
- Backend — `curl http://127.0.0.1:8765/api/health`

## Два блокера до тега

### 1. Apple (единственный «секретный» блокер)

Следуй **`docs/APPLE_SIGNING_SETUP.md`**:

1. Импорт `.p12` → Keychain → Developer ID Application
2. `xcrun notarytool store-credentials tars-notary`
3. В `.env`: `APPLE_TEAM_ID`, `APPLE_DEVELOPER_ID_APPLICATION`, `APPLE_NOTARY_PROFILE` (см. `.env.example`)
4. В GitHub repo `alxvasilevvv/tars-neural-cockpit` — 6 secrets (имена в `PREFLIGHT-APPLE-SIGN.command` header)

Проверка:

```bash
bash scripts/PREFLIGHT-APPLE-SIGN.command   # exit 0
bash scripts/GA-COOKBOOK.command            # exit 0
```

### 2. Soak 72 часа

```bash
make dev-tars-stack    # backend должен жить всё время
bash scripts/SOAK-CRON-INSTALL.command   # cron, если ещё нет
bash scripts/SOAK-CRON-DIAGNOSE.command  # если cron.log: Operation not permitted → см. ниже

# Если cron заблокирован macOS (частый случай):
nohup bash scripts/CURSOR-SOAK-UNTIL-72.command >> .soak/until-72.log 2>&1 &

# Или короткий цикл на 8ч:
nohup bash scripts/CURSOR-OVERNIGHT-SOAK.command >> .soak/overnight-watch.log 2>&1 &
```

**Cron «Operation not permitted»:** `docs/macos/SOAK_CRON_PERMISSIONS.md`

После **72** строк в `.soak/hourly.log`:

```bash
bash scripts/SOAK-REPORT.command
bash scripts/RELEASE-TAG-GUARD.command
```

## Цепочка тега (после Apple + soak)

```bash
bash scripts/FINAL-QA-VERDICT.command      # 0 = GO
bash scripts/GA-COOKBOOK.command           # 0 = GO
bash scripts/RELEASE-TAG-GUARD.command     # 0 = GO
bash scripts/RELEASE-v10.0.command         # destructive — только после 'yes'
# … CI, DOWNLOAD-AND-VERIFY, drag-install, POST-INSTALL-SMOKE …
```

## Cursor за ночь (2026-05-26)

- Закоммичено: `CURSOR-GA-STATUS`, `make ga-status`, `make ci-cockpit`
- Cron soak уже был на машине; добавлены `SOAK-CRON-INSTALL` и `CURSOR-OVERNIGHT-SOAK`
- Push на `main` @ `75efd70+`
