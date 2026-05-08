# TARS Operator Launch Playbook

**Адресат:** Алексей (ты — оператор, твоя машина выкатывает релиз)
**Версия:** 1.0 — 2026-05-05
**Цель:** один документ, проходишь сверху вниз, на выходе — TARS v9.1.0 в production.

Каждый шаг помечен **TIME** (сколько займёт), **DEPS** (что нужно перед началом), и **VERIFY** (как понять что прошло). Если шаг блокирует следующий — отмечено `🚦 BLOCKER`.

---

## Шаг 0 — рукопожатие (1 минута)

**TIME:** 1 минута
**DEPS:** ничего

```bash
cd /Users/alien/Documents/Claude/Projects/Jarvis/jarvis
git status
```

**VERIFY:** "On branch main · Your branch is ahead of 'origin/main' by 6 commits · nothing to commit, working tree clean"

Если что-то другое — стоп, скажи мне (Claude), разберёмся.

---

## Шаг 1 — пуш (1 минута) 🚦 BLOCKER

**TIME:** 1 минута
**DEPS:** работающий интернет

```bash
cd /Users/alien/Documents/Claude/Projects/Jarvis/jarvis
git push
```

**VERIFY:** последняя строка вывода `e6e24c1..origin/main` или похожее — никаких errors.

**Если не получится:**
- `Permission denied` — твой git не аутентифицирован в GitHub. Решение: `gh auth login` или настрой SSH ключ.
- `non-fast-forward` — кто-то (Cursor) запушил пока ты спал. Решение: `git pull --rebase origin main && git push`.

---

## Шаг 2 — авто-precheck (3 минуты)

**TIME:** 3 минуты
**DEPS:** Шаг 1 ✅

Я (Claude) написал скрипт который проверяет всё что можно автоматически:

```bash
bash scripts/launch_precheck.sh
```

**VERIFY:** в конце вывода `status: GREEN — ready to launch` или `GREEN with warnings`.

**Если красное** (`status: NOT READY`) — пришли мне output, разберёмся. Скрипт точно скажет какой пункт сломался.

**Что скрипт проверяет:** working tree clean, контрактные доки на месте, .env hygiene, бэкенд/Vite на localhost (если запущены), git in sync.

**Полная версия с cargo check + smoke-billing-tars:**
```bash
bash scripts/launch_precheck.sh --full
```
(требует чтобы бэкенд был запущен и `.env` был заполнен)

---

## Шаг 3 — визуальный smoke на твоей машине (5 минут)

**TIME:** 5 минут
**DEPS:** Шаг 2 зелёный

```bash
make dev-tars-stack
```

Это поднимет Vite на :5174 (или :5175 если занято) + бэкенд на :8765.

**Открой в браузере и проверь 3 вещи:**

1. **Главная страница `/`** → проскролль до секции **"04 · How it works · Four ways TARS pays for itself"** — должно быть ровно 4 фичи которые красиво появляются по скроллу. **Не должно быть огромного чёрного провала.** (Wave 59-1 фикс).

2. **`/settings`** → должны быть 3 карточки: About, Updates, Keyboard. Кнопка "Check for updates" работает (в браузере открывает GitHub Releases).

3. **Cmd+K** → начни печатать "settings" → должно найтись.

**Ничего не сломано?** Жми Ctrl+C в терминале чтобы остановить Vite. Затем:

```bash
kill $(cat /tmp/tars-backend-8765.pid 2>/dev/null) 2>/dev/null
```

(остановит фоновый бэкенд)

**Если что-то выглядит криво** — скрин сюда, фикс за пару минут.

---

## Шаг 4 — отдай брату интеграционный документ (1 минута)

**TIME:** 1 минута (твоё действие; брат потом работает дни)
**DEPS:** Шаг 1 ✅ (после пуша файл уже на GitHub)

Открой Telegram/iMessage/Email брата. Скопируй и отправь:

> Привет. Я закрыл свою сторону интеграции TARS, нужно чтобы ты закрыл свою на стороне meeet.world / Lovable.
>
> Полный документ со всем что нужно делать:
> https://github.com/alxvasilevvv/tars-neural-cockpit/blob/main/docs/INTEGRATION_FOR_BROTHER.md
>
> Там в самом конце есть секция "Коротко — ОДИН раз посмотри" — 5 пунктов на минуту чтения. Сначала её, потом если есть время — детали выше.
>
> P0 минимум для launch (5 пунктов):
> 1. DNS `tars.meeet.world` → твой edge
> 2. 3 secrets синкнуть (BRIDGE_SHARED_SECRET, MEEET_BILLING_API_KEY, TARS_INGEST_API_KEY)
> 3. 2 endpoints на edge function `tars-billing`: GET /operator + POST /operator/usage
> 4. 2 страницы: /billing/tars?plan=… (checkout) + /account
> 5. Cookie `meeet_session` с Domain=.meeet.world
>
> Когда закроешь — пинг, я прогоню `make smoke-core-bridge` и `make smoke-billing-tars`, проверим end-to-end.
>
> Спека по каждому пункту в том же документе. Лови.

(Шаблон лежит в `docs/templates/BROTHER_HANDOFF_MESSAGE.md` если захочешь подправить.)

---

## Шаг 5 — operator ops: купить сертификаты (1-3 дня) 🚦 BLOCKER для signed installers

**TIME:** заказ — 30 минут; верификация Apple — несколько часов; Authenticode — 1-3 дня
**DEPS:** ничего, можно делать параллельно с шагами 6+

Это **операторская работа** — деньги + identity verification. Я этого сделать не могу.

### 5a. Apple Developer ID ($99/год)

1. Открой https://developer.apple.com/programs/
2. Нажми "Enroll" (правый верхний угол)
3. Войди с Apple ID (создай если нет — но используй email связанный с meeet.world)
4. Выбери "Individual" (если ещё нет регистрации компании в США/EU)
5. Заплати $99
6. Жди 24-48 часов на верификацию
7. После одобрения — открой Xcode → Settings → Accounts → "+" → войди → создай "Developer ID Application" certificate
8. Экспортируй .p12 в безопасное место (1Password / iCloud Keychain) — этот файл лежит в основе всех наших signed installers

**VERIFY:** в Keychain Access у тебя есть "Developer ID Application: <Your Name> (<TEAM_ID>)".

### 5b. Windows Authenticode certificate (~$200-400/год)

Опции (по возрастанию цены/скорости):
- **Sectigo OV** — дешёвый (~$200), 1-3 дня верификации, но WSmartScreen может ругаться первое время
- **DigiCert OV** — средний (~$300), 1-2 дня, чище репутация
- **DigiCert EV** — самый чистый (~$400+), мгновенный SmartScreen trust, требует hardware token (USB)

Для launch v9.1.0 рекомендую **Sectigo OV** — дешевле всего, после первых ~50 установок Windows SmartScreen перестанет ругаться.

1. Открой https://sectigo.com/ssl-certificates-tls/code-signing
2. Choose "OV Code Signing"
3. Заполни форму компании (если у тебя ИП/LLC — используй данные)
4. Получи verification call/email
5. После одобрения — скачай .pfx с паролем

**VERIFY:** у тебя файл `tars-codesign-windows.pfx` + пароль к нему.

### 5c. Tauri release key (5 минут, локально, бесплатно)

```bash
cd /Users/alien/Documents/Claude/Projects/Jarvis/jarvis
# Не нужно brew install — скрипт сам подтянет @tauri-apps/cli через npm
# (Tauri 2 использует встроенный minisign-совместимый signer, не системный
# minisign).
bash desktop/scripts/generate-release-keys.sh --patch-tauri-conf
```

Скрипт:
- Генерирует `~/.tars-release-keys/tars-desktop.key` (защищённый паролем,
  права `0600`, директория `0700`).
- Генерирует `~/.tars-release-keys/tars-desktop.key.pub`.
- Автоматически вставляет публичный ключ в `desktop/src-tauri/tauri.conf.json`
  (заменяя `TODO_PUBLIC_KEY`).

> Если хочешь хранить ключ в другом месте: `--out
> /path/to/key.file`. Скрипт откажется перезаписывать существующий
> файл (`exit 3`) — гарантия что свежий запуск не уничтожит уже
> зарегистрированный в production публичный ключ.

**VERIFY:**
```bash
ls -la ~/.tars-release-keys/
# должны быть tars-desktop.key и tars-desktop.key.pub

grep pubkey desktop/src-tauri/tauri.conf.json
# не должно быть TODO_PUBLIC_KEY

bash desktop/scripts/updater-pubkey-status.sh
# → "updater_pubkey: patched (minisign pubkey present)"
```

Закоммить и запушь:
```bash
git add desktop/src-tauri/tauri.conf.json
git commit -m "chore(release): patch updater pubkey for v9.1.0"
git push
```

⚠️ **Никогда не коммить `~/.tars-release-keys/tars-desktop.key`** — он
только локально и в GitHub Actions secrets. Бэкапь его в hardware
token / 1Password / encrypted offline drive: потеря ключа = у всех
существующих установок auto-updater отвергнет любые подписи и
потребует ручного hard-reinstall.

---

## Шаг 6 — добавить GitHub Actions secrets (15 минут) 🚦 BLOCKER для CI билдов

**TIME:** 15 минут
**DEPS:** Шаг 5 (хотя бы 5c, остальные можно позже)

Открой https://github.com/alxvasilevvv/tars-neural-cockpit/settings/secrets/actions

Добавь следующие secrets (через кнопку "New repository secret"):

| Name | Где взять | Когда нужно |
|------|-----------|-------------|
| `TAURI_SIGNING_PRIVATE_KEY` | base64 от `~/.tars-release-keys/tars-desktop.key` | Шаг 5c сделан |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | пароль которым защитил Tauri key | — |
| `APPLE_CERTIFICATE` | base64 от .p12 экспорта Developer ID | Шаг 5a сделан |
| `APPLE_CERTIFICATE_PASSWORD` | пароль .p12 | — |
| `APPLE_SIGNING_IDENTITY` | "Developer ID Application: <Your Name> (<TEAM_ID>)" | — |
| `APPLE_ID` | твой Apple ID email | — |
| `APPLE_PASSWORD` | app-specific password из appleid.apple.com (не основной) | — |
| `APPLE_TEAM_ID` | 10-знак из Developer portal | — |
| `WINDOWS_CERTIFICATE` | base64 от .pfx | Шаг 5b сделан |
| `WINDOWS_CERTIFICATE_PASSWORD` | пароль .pfx | — |
| `BRIDGE_SHARED_SECRET` | сгенерируй: `openssl rand -hex 32` (синкни с братом!) | Брат должен использовать тот же |
| `MEEET_BILLING_API_KEY` | сгенерируй: `openssl rand -hex 32` (синкни с братом!) | Брат должен использовать тот же |
| `TARS_INGEST_API_KEY` | сгенерируй: `openssl rand -hex 32` | Используется ingest и бэкендом |
| `GITHUB_RELEASE_TOKEN` | fine-grained PAT, repo `tars-neural-cockpit`, `Contents: Read-only` | B-017: дает Pages Function `/dl/[file]` качать private-repo релизы для анонимного `curl|bash`. **Кладётся не в GitHub repo secrets, а в Cloudflare Pages env** — см. `docs/TARS_MEEET_OPS_TODO.md` §5 |

**Команды для генерации secret values:**
```bash
# Для TAURI_SIGNING_PRIVATE_KEY (контракт tauri-action — base64):
base64 < ~/.tars-release-keys/tars-desktop.key | pbcopy

# Для APPLE_CERTIFICATE (после экспорта .p12 из Keychain):
base64 < ~/Downloads/DeveloperID.p12 | pbcopy

# Для WINDOWS_CERTIFICATE:
base64 < ~/Downloads/tars-codesign-windows.pfx | pbcopy

# Для shared secrets:
openssl rand -hex 32

# Альтернатива pbcopy — пайпом сразу в gh secret set:
base64 < ~/.tars-release-keys/tars-desktop.key \
  | gh secret set TAURI_SIGNING_PRIVATE_KEY \
      -R alxvasilevvv/tars-neural-cockpit
```

**VERIFY:** в Settings → Secrets and variables → Actions у тебя видны все 13 GitHub secrets (значения скрыты). `GITHUB_RELEASE_TOKEN` уже в Cloudflare Pages env (см. оп-чеклист §5).

---

## Шаг 7 — синхронизировать secrets с братом (5 минут) 🚦 BLOCKER

**TIME:** 5 минут на твоей стороне; брат тоже 5 минут на своей
**DEPS:** Шаг 6

Передай брату 3 secrets (через секретный канал — Signal, 1Password sharing, что угодно кроме email/Telegram):

- `BRIDGE_SHARED_SECRET` = `<тот же что в GitHub Actions>`
- `MEEET_BILLING_API_KEY` = `<тот же>`
- `TARS_INGEST_API_KEY` = `<тот же>`

Брат кладёт в Supabase → Project `zujrmifaabkletgnpoyw` → Edge Functions → Settings → Secrets.

Имена в Supabase:
- `BRIDGE_SHARED_SECRET` → `BRIDGE_SHARED_SECRET` (без префиксов)
- `MEEET_BILLING_API_KEY` → `TARS_BILLING_API_KEY` (на edge функция читает с этим именем!)
- `TARS_INGEST_API_KEY` → `TARS_INGEST_API_KEY`

**VERIFY:** брат отвечает "ОК, секреты в Supabase".

---

## Шаг 8 — заполнить твой локальный .env (5 минут)

**TIME:** 5 минут
**DEPS:** Шаг 7

```bash
cd /Users/alien/Documents/Claude/Projects/Jarvis/jarvis
cp .env.example .env  # если нет ещё
```

Открой `.env`, замени значения. Минимально нужно:

```bash
# meeet.world ingest
MEEET_INGEST_URL=https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/tars-ingest
MEEET_API_KEY=<тот же что TARS_INGEST_API_KEY>
TARS_INGEST_API_KEY=<тот же>
MEEET_CONTRACT_VERSION=1.1.0
MEEET_SOURCE=tars

# core-bridge
BRIDGE_SHARED_SECRET=<тот же что в GitHub Actions>

# remote billing
TARS_BILLING_SOURCE=remote
MEEET_BILLING_BASE_URL=https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/tars-billing
MEEET_BILLING_API_KEY=<тот же>

# downloads (B-017: same-origin proxy через Pages Function;
# direct github.com URLs дают 404 пока репо приватное)
TARS_DOWNLOAD_BASE_URL=https://tars.meeet.world/dl
```

**VERIFY:**
```bash
make smoke-billing-tars
```
Должно вернуть ОК — это значит твой `.env` синхронизирован с edge function брата.

---

## Шаг 9 — попроси брата прогнать его сторону (10-30 минут чтобы дождаться)

**TIME:** 10-30 минут wait time
**DEPS:** Шаги 7+8

Напиши брату:

> Готов прогнать end-to-end smoke. Подними DNS `tars.meeet.world` (минимум CNAME), задеплой `tars-billing` + `core-bridge` Edge Functions если ещё не. Когда готово — отвечай.

Когда брат скажет ОК:

```bash
make gate-control-tower
```

**VERIFY:** все checks зелёные.

**Если красное:** скрипт точно скажет какой endpoint падает. Самые частые проблемы:
- 403 origin_not_allowed → брат не добавил `https://tars.meeet.world` в Origin allowlist edge function
- 401 unauthorized → secrets не синкнуты
- 404 not_found → не задеплоена соответствующая edge function

---

## Шаг 10 — tag релиз и запустить CI билд (5 минут activation; 30 минут билд)

**TIME:** 5 минут команда; 30 минут CI
**DEPS:** Шаги 1-9 ✅

```bash
cd /Users/alien/Documents/Claude/Projects/Jarvis/jarvis
git tag v9.1.0
git push origin v9.1.0
```

Это триггернёт GitHub Actions workflow `release-desktop-tagged.yml`. Он:
1. Соберёт `.dmg` (universal Apple), `.msi` + `.exe` (Windows), `.AppImage` + `.deb` (Linux)
2. Подпишет macOS bundle через Apple Developer ID
3. Подпишет Windows installer через Authenticode
4. Создаст `latest.json` с minisign signatures
5. Загрузит всё на GitHub Releases

**VERIFY:**
- Открой https://github.com/alxvasilevvv/tars-neural-cockpit/actions
- Смотри как идёт workflow `release-desktop-tagged`
- Должен закончиться зелёным через ~30 мин
- Открой https://github.com/alxvasilevvv/tars-neural-cockpit/releases/tag/v9.1.0 — должны быть 5 артефактов + `latest.json`

**Если CI красный:** проверь логи workflow, обычно проблема в одном из secrets — пришли мне ошибку, разберёмся.

---

## Шаг 11 — install smoke на чистой Mac (10 минут)

**TIME:** 10 минут
**DEPS:** Шаг 10

Возьми Mac (свой, или одолжи у друга) который **никогда не запускал TARS**:

1. Скачай `TARS-9.1.0-universal.dmg` с GitHub Releases
2. Открой .dmg, перетащи TARS.app в Applications
3. Запусти TARS из Applications
4. Должно открыться окно **БЕЗ предупреждения "TARS can't be opened because it is from an unidentified developer"**
5. Через ~3 секунды бэкенд поднимется (увидишь "Backend ready · :8765" внизу слева)
6. Cmd+Shift+Space — окно скрывается / показывается
7. Tray icon в menu bar — клик показывает меню Show TARS / Quit TARS
8. Открой Terminal, набери `open "tars://onboarding?role=founder"` — TARS должен открыться на onboarding с founder выбранным

**Если на шаге 4 предупреждение появилось:** notarization не прошла. Проверь:
```bash
codesign -dv --verbose=4 /Applications/TARS.app
spctl -a -t open --context context:primary-signature -v /Applications/TARS.app
```

**VERIFY:** TARS работает на чистой Mac, никаких security warnings.

---

## Шаг 12 — production deploy на tars.meeet.world (зависит от брата)

**TIME:** на брате — 5 минут чтобы поменять DNS / выкатить static
**DEPS:** Шаг 11 ✅

Брат уже должен иметь `tars.meeet.world` живым на staging. Сейчас он флипает в production.

**VERIFY:**
```bash
curl -sI https://tars.meeet.world/ | head -3
# Expect: HTTP/2 200
```

Зайди в браузере на https://tars.meeet.world/ — должна открыться marketing страница. Кликни Download — должна вести на `tars.meeet.world/dl/<filename>` (same-origin Pages Function проксирует через `GITHUB_RELEASE_TOKEN`, не на голый github.com — B-017). Для smoke-теста именно проксика:

```bash
curl -fsSL https://tars.meeet.world/install.sh | head -10
# должен показать shebang + комментарий-заголовок install скрипта
curl -sI https://tars.meeet.world/dl/TARS_9.1.0_aarch64.dmg | head -1
# HTTP/2 200 — хорошо;
# HTTP/2 503 — паста PAT в Pages env ещё не сделана (см. ops §5).
```

---

## Шаг 13 — публичный анонс (15 минут)

**TIME:** 15 минут
**DEPS:** Шаги 11+12

Я подготовил два варианта (Twitter + блог) в `docs/templates/MARKETING_ANNOUNCEMENT.md`. Скопируй, отредактируй под свой голос, опубликуй.

**Минимум для launch:**
1. Tweet — линк на tars.meeet.world + краткое описание + 1 demo gif
2. Пост в meeet.world community (если есть)
3. Сообщение в свой канал/чат

**Опционально:**
- Hacker News submission
- Show HN
- Product Hunt
- Indie Hackers

---

## Шаг 14 — мониторинг 24h (passive)

**TIME:** твоё время по 5 минут несколько раз в день
**DEPS:** Шаг 13

В первые 24 часа после анонса проверяй:

1. **Crashes** (если есть Sentry / error reporting): любые `tars.client.error`?
2. **Backend health**: брат может проверить через `/admin/telemetry` сколько `tars.install.script.fetched` событий прошло
3. **Twitter mentions** + DMs — реагируй на bug reports быстро
4. **`meeet.mirror.usage.exhausted` events** — это новый алерт из Wave 56, должен звонить если billing edge упал
5. **GitHub Releases download stats**

Если что-то полыхает — пиши мне, делаем hotfix patch v9.1.1.

---

## Шаг 15 — post-launch retro (через 7 дней)

**TIME:** 30 минут на размышления
**DEPS:** 7 дней после launch

Записать:
- Что сработало
- Что пошло не так
- Какие фичи теперь в очереди (Phase M)
- TTFR / retention cohort metrics

Я могу помочь синтезировать это в `docs/POST_LAUNCH_RETRO_v9.1.0.md`.

---

## Cheat sheet — что у меня в руках, что у тебя

| Шаг | Может сделать Claude | Только ты |
|-----|----------------------|-----------|
| 0. git status | ✅ (уже сделал) | — |
| 1. git push | ❌ (sandbox blocked) | ✅ |
| 2. precheck script | ✅ написал, ты запустишь | ✅ запустить |
| 3. визуальный smoke | ❌ нет браузера | ✅ |
| 4. отдать брату | ✅ написал шаблон | ✅ отправить |
| 5a. Apple Developer | ❌ требует деньги/Apple ID | ✅ |
| 5b. Windows cert | ❌ требует деньги/identity | ✅ |
| 5c. minisign keys | ❌ создаёт secrets на твоей машине | ✅ |
| 6. GitHub secrets | ❌ требует web UI access | ✅ |
| 7. синк с братом | ❌ не могу слать сообщения | ✅ |
| 8. .env | ❌ values секретные | ✅ |
| 9. control tower | ✅ запустим вместе | ✅ |
| 10. tag release | ❌ нет push access | ✅ |
| 11. install smoke | ❌ нет Mac | ✅ |
| 12. production deploy | ❌ ничего на серверах | ✅ (брат + ты) |
| 13. announcement | ✅ написал шаблоны | ✅ публикуешь |
| 14. monitoring | ✅ help analyze incidents | ✅ |
| 15. retro | ✅ help synthesize | ✅ |

---

## Если застрянешь

Любой шаг — пиши мне, копируешь сюда output ошибки. Я разберу за 2 минуты.

**Самые вероятные камни:**
1. Apple notarization первый раз идёт долго (24-48h после enrollment)
2. Брат может заминаться на edge function deploy — я знаю спеку наизусть, могу подсказать
3. CI workflow может падать из-за неправильно закодированных secrets — base64 без переноса строк, с переносом строк, с trailing newline... 5-10 минут возни

Удачи. TARS launch-ready на 99%, осталась одна миля.

— Claude, 2026-05-05
